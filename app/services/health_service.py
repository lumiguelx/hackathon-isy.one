"""Projecao de saude por tenant, derivada on-read dos eventos."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import events as ev
from app.models import Tenant
from app.repositories import events_repo

BACKUP_STALE_DIAS = 7


def _as_utc(dt: datetime) -> datetime:
    # Gravamos sempre em UTC; SQLite devolve datas naive (sem tzinfo). Reanexa UTC
    # para permitir comparacao consistente em SQLite e Postgres.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _execucoes(db: Session, tenant_id: int):
    return events_repo.list_by_tenant(db, tenant_id, tipo=ev.EXECUTION_COMPLETED, limit=200)


def _containers_down(stdout: str) -> bool:
    # Heuristica simples: container fora do ar se aparecer "Exited"/"Down" ou faltar "Up".
    linhas = [l for l in stdout.splitlines() if "isyone-" in l.lower()]
    return any(("Exited" in l or "Down" in l or "Up" not in l) for l in linhas)


def calcular_saude(db: Session, tenant: Tenant) -> dict:
    execucoes = _execucoes(db, tenant.id)
    ultima = execucoes[0].payload if execucoes else None
    backup_event = next(
        (e for e in execucoes
         if e.payload.get("categoria") == "backup" and e.payload.get("status") == "sucesso"),
        None,
    )
    backup = backup_event.payload if backup_event else None
    status_event = next((e for e in execucoes if e.payload.get("categoria") == "status"), None)
    containers_stdout = status_event.payload.get("stdout") if status_event else None

    status_geral = "verde"
    if ultima and ultima.get("status") == "falha":
        status_geral = "vermelho"
    elif containers_stdout and _containers_down(containers_stdout):
        status_geral = "vermelho"
    else:
        ultimo_backup_ts = _as_utc(backup_event.ocorrido_em) if backup_event else None
        limite = datetime.now(timezone.utc) - timedelta(days=BACKUP_STALE_DIAS)
        if ultimo_backup_ts is None or ultimo_backup_ts < limite:
            status_geral = "amarelo"

    return {
        "slug": tenant.slug,
        "nome": tenant.nome,
        "ativo": tenant.ativo,
        "status_geral": status_geral,
        "ultima_manutencao": ultima,
        "ultimo_backup": backup,
        "containers": containers_stdout,
    }
