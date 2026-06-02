"""Binding entre tenant e script (whitelist + defaults por cliente)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Script, TenantScript


def get(db: Session, tenant_id: int, script_id: int) -> TenantScript | None:
    stmt = select(TenantScript).where(
        TenantScript.tenant_id == tenant_id, TenantScript.script_id == script_id
    )
    return db.scalar(stmt)


def upsert(
    db: Session, tenant_id: int, script_id: int, parametros_default: str, ativo: bool
) -> TenantScript:
    binding = get(db, tenant_id, script_id)
    if binding is None:
        binding = TenantScript(tenant_id=tenant_id, script_id=script_id)
        db.add(binding)
    binding.parametros_default = parametros_default
    binding.ativo = ativo
    db.commit()
    db.refresh(binding)
    return binding


def list_active_scripts(
    db: Session, tenant_id: int
) -> list[tuple[Script, TenantScript]]:
    """Scripts ativos disponiveis para o tenant, com o binding correspondente."""
    stmt = (
        select(Script, TenantScript)
        .join(TenantScript, TenantScript.script_id == Script.id)
        .where(
            TenantScript.tenant_id == tenant_id,
            TenantScript.ativo.is_(True),
            Script.ativo.is_(True),
        )
        .order_by(Script.id)
    )
    return [(row[0], row[1]) for row in db.execute(stmt)]
