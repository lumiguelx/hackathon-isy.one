"""Rotas administrativas: tenants, catalogo de scripts, bindings, tokens, dashboard."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_admin
from app.repositories import (
    config_repo,
    events_repo,
    schedules_repo,
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import (
    ScheduleOut,
    ScriptCreate,
    ScriptOut,
    ScriptSource,
    ScriptUpdate,
    TenantCreate,
    TenantOut,
    TenantScriptBinding,
    TenantScriptOut,
    TenantUpdate,
    TokenUpdate,
)
from app.services import execution_service, health_service, script_service, template_service

router = APIRouter(
    prefix="/api/v1/admin", tags=["Administracao"], dependencies=[Depends(verify_admin)]
)


def _tenant_out(t) -> dict:
    return TenantOut.model_validate(t).model_dump(mode="json")


def _script_out(s) -> dict:
    out = ScriptOut.model_validate(s).model_dump(mode="json")
    # Inclui os parametros declarados no template para uso no frontend.
    out["parametros_schema"] = (
        template_service.extract_params(s.template)
        if s.tipo == "template" and s.template
        else []
    )
    return out


@router.get("/tenants", summary="Listar clientes")
def list_tenants(db: Session = Depends(get_db)) -> dict:
    """Lista todos os clientes (tenants) cadastrados na plataforma."""
    return ok([_tenant_out(t) for t in tenants_repo.list_all(db)])


@router.post("/tenants", status_code=status.HTTP_201_CREATED, summary="Cadastrar cliente")
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)) -> dict:
    """Cadastra um novo cliente; falha com 409 se o slug ja existir."""
    if tenants_repo.get_by_slug(db, body.slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug ja existe.")
    return ok(_tenant_out(tenants_repo.create(db, body)), "Cliente cadastrado.")


@router.put("/tenants/{slug}", summary="Atualizar cliente")
def update_tenant(slug: str, body: TenantUpdate, db: Session = Depends(get_db)) -> dict:
    """Atualiza os dados de um cliente existente, identificado pelo slug."""
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    return ok(_tenant_out(tenants_repo.update(db, tenant, body)), "Cliente atualizado.")


@router.delete("/tenants/{slug}", summary="Desprovisionar e remover cliente")
def delete_tenant(slug: str, db: Session = Depends(get_db)) -> dict:
    """Desprovisiona o servidor do cliente (se houver) e remove o cadastro."""
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    # Desprovisiona o servidor (remove containers) antes de apagar o cadastro.
    if tenant.ssh_host:
        execution_service.deprovision_remote(tenant)
    tenants_repo.delete(db, tenant)
    return ok(message="Cliente desprovisionado e removido.")


@router.get("/scripts", summary="Listar catalogo de scripts")
def list_scripts(db: Session = Depends(get_db)) -> dict:
    """Lista o catalogo completo de scripts, com o schema de parametros de cada um."""
    return ok([_script_out(s) for s in scripts_repo.list_all(db)])


@router.post("/scripts", status_code=status.HTTP_201_CREATED, summary="Cadastrar script")
def create_script(body: ScriptCreate, db: Session = Depends(get_db)) -> dict:
    """Cadastra um script no catalogo (tipo arquivo ou template)."""
    try:
        return ok(_script_out(script_service.create(db, body)), "Script cadastrado.")
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/scripts/{script_id}", summary="Atualizar script")
def update_script(
    script_id: int, body: ScriptUpdate, db: Session = Depends(get_db)
) -> dict:
    """Atualiza um script do catalogo (patch parcial), validando a coerencia tipo/conteudo."""
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        return ok(
            _script_out(script_service.update(db, script, body)), "Script atualizado."
        )
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/scripts/{script_id}/source", summary="Ler codigo do script")
def get_script_source(script_id: int, db: Session = Depends(get_db)) -> dict:
    """Le o codigo do .sh/.py do script para o editor inline."""
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        conteudo = script_service.read_source(script)
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ok({"caminho": script.caminho, "conteudo": conteudo})


@router.put("/scripts/{script_id}/source", summary="Gravar codigo do script")
def put_script_source(
    script_id: int, body: ScriptSource, db: Session = Depends(get_db)
) -> dict:
    """Grava o codigo do script no diretorio de scripts (atras de flag, path-guarded)."""
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        script_service.write_source(script, body.conteudo)
    except script_service.ScriptEditDisabled as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ok(message="Codigo salvo.")


@router.put("/tenants/{slug}/scripts", summary="Vincular script a um cliente")
def bind_script(
    slug: str, body: TenantScriptBinding, db: Session = Depends(get_db)
) -> dict:
    """Vincula um script a um cliente; bloqueia scripts exclusivos de outro tenant."""
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    script = scripts_repo.get(db, body.script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    # Impede vincular um script exclusivo de outro cliente.
    if script.tenant_id is not None and script.tenant_id != tenant.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Script pertence a outro cliente."
        )
    binding = tenant_scripts_repo.upsert(
        db, tenant.id, body.script_id, body.parametros_default, body.ativo
    )
    return ok(
        TenantScriptOut.model_validate(binding).model_dump(mode="json"),
        "Binding salvo.",
    )


@router.put("/token", summary="Rotacionar token admin")
def rotate_admin_token(body: TokenUpdate, db: Session = Depends(get_db)) -> dict:
    """Substitui o token de admin por um novo valor."""
    config_repo.set_token(db, body.token)
    return ok(message="Token admin rotacionado.")


@router.put("/tenants/{slug}/token", summary="Rotacionar token do cliente")
def rotate_tenant_token(
    slug: str, body: TokenUpdate, db: Session = Depends(get_db)
) -> dict:
    """Rotaciona o token de acesso de um cliente especifico e audita a troca."""
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    tenants_repo.set_token(db, tenant, body.token)
    events_repo.append(db, ev.TOKEN_ROTATED, {"alvo": slug}, tenant_id=tenant.id)
    return ok(message="Token do cliente rotacionado.")


@router.get("/tenants/health", summary="Dashboard de saude da frota")
def dashboard(db: Session = Depends(get_db)) -> dict:
    """Calcula e retorna a saude de toda a frota de clientes para o dashboard."""
    saudes = [health_service.calcular_saude(db, t) for t in tenants_repo.list_all(db)]
    return ok(saudes)


@router.get("/schedules", summary="Listar agendamentos de todos os clientes")
def list_schedules(db: Session = Depends(get_db)) -> dict:
    """Lista os agendamentos de toda a frota, com nome do cliente e do script."""
    tenants = {t.id: t for t in tenants_repo.list_all(db)}
    scripts = {s.id: s for s in scripts_repo.list_all(db)}
    data = []
    for s in schedules_repo.list_all(db):
        out = ScheduleOut.model_validate(s).model_dump(mode="json")
        tenant = tenants.get(s.tenant_id)
        script = scripts.get(s.script_id)
        out["tenant_nome"] = tenant.nome if tenant else None
        out["tenant_slug"] = tenant.slug if tenant else None
        out["script_nome"] = script.nome if script else None
        data.append(out)
    return ok(data)
