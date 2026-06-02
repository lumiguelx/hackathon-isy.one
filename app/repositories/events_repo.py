"""Acesso append-only ao event store."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event


def append(
    db: Session,
    tipo: str,
    payload: dict,
    tenant_id: int | None = None,
    script_id: int | None = None,
    ocorrido_em: datetime | None = None,
) -> Event:
    event = Event(tipo=tipo, payload=payload, tenant_id=tenant_id, script_id=script_id)
    if ocorrido_em is not None:
        event.ocorrido_em = ocorrido_em
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_by_tenant(
    db: Session, tenant_id: int, tipo: str | None = None, limit: int = 100
) -> list[Event]:
    stmt = select(Event).where(Event.tenant_id == tenant_id)
    if tipo is not None:
        stmt = stmt.where(Event.tipo == tipo)
    stmt = stmt.order_by(Event.id.desc()).limit(limit)
    return list(db.scalars(stmt))
