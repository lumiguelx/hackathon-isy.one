"""Loop de agendamento: dispara execucoes cron sem ninguem clicar.

Roda numa thread daemon iniciada no lifespan. A cada minuto avalia os agendamentos
ativos e executa os que casam o horario, reusando o execution_service — ou seja, a
mesma auditoria (Event ExecutionCompleted) das execucoes manuais, com origem='agendamento'.
"""

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Schedule
from app.repositories import schedules_repo, scripts_repo, tenants_repo
from app.services import cron, execution_service

logger = logging.getLogger("isyone.scheduler")


def _as_utc(dt: datetime) -> datetime:
    # SQLite devolve datetimes naive (sem tz); como sempre gravamos UTC, naive=UTC.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _mesmo_minuto(a: datetime, b: datetime) -> bool:
    a = _as_utc(a).replace(second=0, microsecond=0)
    b = _as_utc(b).replace(second=0, microsecond=0)
    return a == b


def due(schedules: list[Schedule], now: datetime) -> list[Schedule]:
    """Agendamentos a disparar agora: ativos, cron casa o minuto e ainda nao rodaram nele."""
    pendentes: list[Schedule] = []
    for s in schedules:
        if not s.ativo:
            continue
        try:
            if not cron.matches(s.cron_expr, now):
                continue
        except ValueError:
            logger.warning("cron invalido no agendamento %s: %r", s.id, s.cron_expr)
            continue
        if s.ultima_exec is not None and _mesmo_minuto(s.ultima_exec, now):
            continue
        pendentes.append(s)
    return pendentes


def tick(db: Session, now: datetime) -> int:
    """Dispara os agendamentos vencidos neste minuto. Retorna quantos rodaram."""
    rodados = 0
    for s in due(schedules_repo.list_active(db), now):
        tenant = tenants_repo.get(db, s.tenant_id)
        script = scripts_repo.get(db, s.script_id)
        if tenant is None or script is None or not script.ativo:
            schedules_repo.set_ultima_exec(db, s, now)
            continue
        parametros = s.parametros.split() if s.parametros else []
        try:
            execution_service.run(db, tenant, script, parametros, origem="agendamento")
        except execution_service.ScriptNotExecutable as exc:
            logger.warning("agendamento %s nao executavel: %s", s.id, exc)
        schedules_repo.set_ultima_exec(db, s, now)
        rodados += 1
    return rodados


def run_loop(stop_event: threading.Event) -> None:
    """Tica a cada minuto ate stop_event. Cada tick usa sua propria Session."""
    logger.info("scheduler iniciado")
    while not stop_event.is_set():
        # Alinha na virada do minuto para os horarios cron baterem.
        agora = datetime.now(timezone.utc)
        espera = 60 - agora.second - agora.microsecond / 1_000_000
        if stop_event.wait(timeout=espera):
            break
        with SessionLocal() as db:
            try:
                tick(db, datetime.now(timezone.utc))
            except Exception:  # noqa: BLE001 - um erro de tick nao pode derrubar o loop
                logger.exception("erro no tick do scheduler")
    logger.info("scheduler parado")
