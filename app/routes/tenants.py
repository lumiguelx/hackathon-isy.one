"""Rotas por cliente: scripts disponiveis, execucao, auditoria e saude."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_tenant
from app.models import Tenant
from app.repositories import (
    events_repo,
    schedules_repo,
    scripts_repo,
    tenant_scripts_repo,
)
from app.schemas import RunRequest, ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.services import execution_service, health_service, template_service

router = APIRouter(prefix="/api/v1/tenants/{slug}", tags=["Cliente"])


@router.get("/scripts", summary="Scripts disponiveis para o cliente")
def list_scripts(
    tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)
) -> dict:
    """Lista os scripts liberados para o cliente, com o schema de parametros de cada um."""
    disponiveis = tenant_scripts_repo.list_active_scripts(db, tenant.id)
    data = [
        {
            "script_id": s.id,
            "nome": s.nome,
            "categoria": s.categoria,
            "descricao": s.descricao,
            "tipo": s.tipo,
            "parametros_default": b.parametros_default,
            "parametros_schema": (
                template_service.extract_params(s.template)
                if s.tipo == "template" and s.template
                else []
            ),
        }
        for s, b in disponiveis
    ]
    return ok(data)


@router.post("/scripts/{script_id}/run", summary="Executar script")
def run_script(
    script_id: int,
    body: RunRequest,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Executa um script liberado para o cliente e devolve a saida auditada da execucao."""
    binding = tenant_scripts_repo.get(db, tenant.id, script_id)
    if binding is None or not binding.ativo:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Script nao disponivel para este cliente."
        )
    script = scripts_repo.get(db, script_id)
    if script is None or not script.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Script inativo.")

    if body.parametros:
        parametros = body.parametros
    else:
        parametros = (
            binding.parametros_default.split() if binding.parametros_default else []
        )

    try:
        event = execution_service.run(db, tenant, script, parametros)
    except execution_service.ScriptNotExecutable as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    p = event.payload
    msg = (
        "Script executado com sucesso."
        if p["status"] == "sucesso"
        else "Script retornou falha."
    )
    return ok({"id": event.id, **p, "executado_em": event.ocorrido_em.isoformat()}, msg)


@router.get("/logs", summary="Auditoria de execucoes do cliente")
def list_logs(
    tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)
) -> dict:
    """Retorna os ultimos 50 eventos de auditoria (execucoes) do cliente."""
    eventos = events_repo.list_by_tenant(db, tenant.id, limit=50)
    data = [
        {
            "id": e.id,
            "tipo": e.tipo,
            "ocorrido_em": e.ocorrido_em.isoformat(),
            **e.payload,
        }
        for e in eventos
    ]
    return ok(data)


@router.get("/health", summary="Saude do cliente")
def health(
    tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)
) -> dict:
    """Retorna as metricas de saude da frota daquele cliente."""
    return ok(health_service.calcular_saude(db, tenant))


@router.get("/schedules", summary="Agendamentos do cliente")
def list_schedules(
    tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)
) -> dict:
    """Lista os agendamentos (cron) configurados para o cliente."""
    data = [
        ScheduleOut.model_validate(s).model_dump(mode="json")
        for s in schedules_repo.list_by_tenant(db, tenant.id)
    ]
    return ok(data)


@router.post("/schedules", status_code=status.HTTP_201_CREATED, summary="Criar agendamento")
def create_schedule(
    body: ScheduleCreate,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Agenda a execucao automatica de um script liberado para o cliente."""
    binding = tenant_scripts_repo.get(db, tenant.id, body.script_id)
    if binding is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Script nao disponivel para este cliente."
        )
    schedule = schedules_repo.create(db, tenant.id, body)
    return ok(
        ScheduleOut.model_validate(schedule).model_dump(mode="json"),
        "Agendamento criado.",
    )


@router.put("/schedules/{schedule_id}", summary="Atualizar agendamento")
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Atualiza um agendamento do cliente (horario, parametros ou ativo)."""
    schedule = schedules_repo.get(db, schedule_id)
    if schedule is None or schedule.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento nao encontrado.")
    schedule = schedules_repo.update(db, schedule, body)
    return ok(
        ScheduleOut.model_validate(schedule).model_dump(mode="json"),
        "Agendamento atualizado.",
    )


@router.delete("/schedules/{schedule_id}", summary="Remover agendamento")
def delete_schedule(
    schedule_id: int,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Remove um agendamento do cliente."""
    schedule = schedules_repo.get(db, schedule_id)
    if schedule is None or schedule.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento nao encontrado.")
    schedules_repo.delete(db, schedule)
    return ok(message="Agendamento removido.")
