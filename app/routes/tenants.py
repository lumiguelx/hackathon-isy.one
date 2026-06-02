"""Rotas por cliente: scripts disponiveis, execucao, auditoria e saude."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_tenant
from app.models import Tenant
from app.repositories import events_repo, scripts_repo, tenant_scripts_repo
from app.schemas import RunRequest
from app.services import execution_service, health_service

router = APIRouter(prefix="/api/v1/tenants/{slug}", tags=["Cliente"])


@router.get("/scripts")
def list_scripts(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    disponiveis = tenant_scripts_repo.list_active_scripts(db, tenant.id)
    data = [{
        "script_id": s.id, "nome": s.nome, "categoria": s.categoria,
        "descricao": s.descricao, "parametros_default": b.parametros_default,
    } for s, b in disponiveis]
    return ok(data)


@router.post("/scripts/{script_id}/run")
def run_script(
    script_id: int,
    body: RunRequest,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    binding = tenant_scripts_repo.get(db, tenant.id, script_id)
    if binding is None or not binding.ativo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao disponivel para este cliente.")
    script = scripts_repo.get(db, script_id)
    if script is None or not script.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Script inativo.")

    if body.parametros:
        parametros = body.parametros
    else:
        parametros = binding.parametros_default.split() if binding.parametros_default else []

    try:
        event = execution_service.run(db, tenant, script, parametros)
    except execution_service.ScriptNotExecutable as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    p = event.payload
    msg = "Script executado com sucesso." if p["status"] == "sucesso" else "Script retornou falha."
    return ok({"id": event.id, **p, "executado_em": event.ocorrido_em.isoformat()}, msg)


@router.get("/logs")
def list_logs(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    eventos = events_repo.list_by_tenant(db, tenant.id, limit=50)
    data = [{
        "id": e.id, "tipo": e.tipo, "ocorrido_em": e.ocorrido_em.isoformat(), **e.payload,
    } for e in eventos]
    return ok(data)


@router.get("/health")
def health(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    return ok(health_service.calcular_saude(db, tenant))
