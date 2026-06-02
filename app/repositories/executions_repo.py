"""Acesso a tabela executions (auditoria)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Execution


def create(db: Session, execution: Execution) -> Execution:
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def list_recent(db: Session, limit: int = 100) -> list[Execution]:
    stmt = select(Execution).order_by(Execution.id.desc()).limit(limit)
    return list(db.scalars(stmt))
