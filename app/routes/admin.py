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
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import (
    ScriptCreate,
    ScriptOut,
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


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)) -> dict:
    return ok([_tenant_out(t) for t in tenants_repo.list_all(db)])


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)) -> dict:
    if tenants_repo.get_by_slug(db, body.slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug ja existe.")
    return ok(_tenant_out(tenants_repo.create(db, body)), "Cliente cadastrado.")


@router.put("/tenants/{slug}")
def update_tenant(slug: str, body: TenantUpdate, db: Session = Depends(get_db)) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    return ok(_tenant_out(tenants_repo.update(db, tenant, body)), "Cliente atualizado.")


@router.delete("/tenants/{slug}")
def delete_tenant(slug: str, db: Session = Depends(get_db)) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    # Desprovisiona o servidor (remove containers) antes de apagar o cadastro.
    if tenant.ssh_host:
        execution_service.deprovision_remote(tenant)
    tenants_repo.delete(db, tenant)
    return ok(message="Cliente desprovisionado e removido.")


@router.get("/scripts")
def list_scripts(db: Session = Depends(get_db)) -> dict:
    return ok([_script_out(s) for s in scripts_repo.list_all(db)])


@router.post("/scripts", status_code=status.HTTP_201_CREATED)
def create_script(body: ScriptCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_script_out(script_service.create(db, body)), "Script cadastrado.")
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/scripts/{script_id}")
def update_script(
    script_id: int, body: ScriptUpdate, db: Session = Depends(get_db)
) -> dict:
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        return ok(
            _script_out(script_service.update(db, script, body)), "Script atualizado."
        )
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/tenants/{slug}/scripts")
def bind_script(
    slug: str, body: TenantScriptBinding, db: Session = Depends(get_db)
) -> dict:
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


@router.put("/token")
def rotate_admin_token(body: TokenUpdate, db: Session = Depends(get_db)) -> dict:
    config_repo.set_token(db, body.token)
    return ok(message="Token admin rotacionado.")


@router.put("/tenants/{slug}/token")
def rotate_tenant_token(
    slug: str, body: TokenUpdate, db: Session = Depends(get_db)
) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    tenants_repo.set_token(db, tenant, body.token)
    events_repo.append(db, ev.TOKEN_ROTATED, {"alvo": slug}, tenant_id=tenant.id)
    return ok(message="Token do cliente rotacionado.")


@router.get("/tenants/health")
def dashboard(db: Session = Depends(get_db)) -> dict:
    saudes = [health_service.calcular_saude(db, t) for t in tenants_repo.list_all(db)]
    return ok(saudes)
