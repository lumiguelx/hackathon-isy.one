"""Acesso a tabela tenants."""

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Schedule, Script, Tenant, TenantScript
from app.schemas import TenantCreate, TenantUpdate


def list_all(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.id)))


def get(db: Session, tenant_id: int) -> Tenant | None:
    return db.get(Tenant, tenant_id)


def get_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def create(db: Session, data: TenantCreate) -> Tenant:
    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update(db: Session, tenant: Tenant, data: TenantUpdate) -> Tenant:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


def set_token(db: Session, tenant: Tenant, token: str) -> None:
    tenant.token = token
    db.commit()


def delete(db: Session, tenant: Tenant) -> None:
    # Remove dependentes antes do tenant (FKs sem ON DELETE CASCADE):
    # agendamentos, eventos, bindings e scripts exclusivos do cliente.
    db.execute(sa_delete(Schedule).where(Schedule.tenant_id == tenant.id))
    db.execute(sa_delete(Event).where(Event.tenant_id == tenant.id))
    db.execute(sa_delete(TenantScript).where(TenantScript.tenant_id == tenant.id))
    db.execute(sa_delete(Script).where(Script.tenant_id == tenant.id))
    db.delete(tenant)
    db.commit()
