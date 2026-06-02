"""Acesso a tabela scripts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Script
from app.schemas import ScriptCreate, ScriptUpdate


def list_all(db: Session) -> list[Script]:
    return list(db.scalars(select(Script).order_by(Script.id)))


def list_active(db: Session) -> list[Script]:
    return list(db.scalars(select(Script).where(Script.ativo.is_(True)).order_by(Script.id)))


def get(db: Session, script_id: int) -> Script | None:
    return db.get(Script, script_id)


def get_by_nome(db: Session, nome: str) -> Script | None:
    return db.scalar(select(Script).where(Script.nome == nome))


def create(db: Session, data: ScriptCreate) -> Script:
    script = Script(**data.model_dump())
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def update(db: Session, script: Script, data: ScriptUpdate) -> Script:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(script, field, value)
    db.commit()
    db.refresh(script)
    return script


def delete(db: Session, script: Script) -> None:
    db.delete(script)
    db.commit()
