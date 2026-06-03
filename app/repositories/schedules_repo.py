"""Acesso a tabela schedules (agendamentos cron por cliente)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Schedule
from app.schemas import ScheduleCreate, ScheduleUpdate


def list_by_tenant(db: Session, tenant_id: int) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.tenant_id == tenant_id).order_by(Schedule.id)
    return list(db.scalars(stmt))


def list_all(db: Session) -> list[Schedule]:
    return list(db.scalars(select(Schedule).order_by(Schedule.id)))


def list_active(db: Session) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.ativo.is_(True)).order_by(Schedule.id)
    return list(db.scalars(stmt))


def get(db: Session, schedule_id: int) -> Schedule | None:
    return db.get(Schedule, schedule_id)


def create(db: Session, tenant_id: int, data: ScheduleCreate) -> Schedule:
    schedule = Schedule(
        tenant_id=tenant_id,
        script_id=data.script_id,
        cron_expr=data.cron_expr,
        parametros=data.parametros,
        ativo=data.ativo,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def update(db: Session, schedule: Schedule, data: ScheduleUpdate) -> Schedule:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


def delete(db: Session, schedule: Schedule) -> None:
    db.delete(schedule)
    db.commit()


def set_ultima_exec(db: Session, schedule: Schedule, quando: datetime) -> None:
    schedule.ultima_exec = quando
    db.commit()
