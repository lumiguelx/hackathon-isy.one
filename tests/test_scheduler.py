"""Testa a logica do agendador (due/tick) sem subir a thread."""

from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.repositories import (
    events_repo,
    schedules_repo,
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import ScheduleCreate, ScriptCreate, TenantCreate
from app.services import scheduler
from tests.conftest import client  # noqa: F401


def _setup(db):
    tenant = tenants_repo.create(
        db,
        TenantCreate(
            slug="cliente-1",
            nome="Cliente 1",
            dominio="cliente1.isy.one",
            porta=8151,
            db_name="db_cliente1",
            token="tok-cliente-1-aaaaaa",
        ),
    )
    script = scripts_repo.create(
        db, ScriptCreate(nome="echo", caminho="echo_args.sh", categoria="other")
    )
    tenant_scripts_repo.upsert(db, tenant.id, script.id, "padrao", True)
    return tenant, script


def test_due_seleciona_agendamento_no_minuto(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _setup(db)
        sched = schedules_repo.create(
            db, tenant.id, ScheduleCreate(script_id=script.id, cron_expr="* * * * *")
        )
        agora = datetime.now(timezone.utc)
        assert [s.id for s in scheduler.due([sched], agora)] == [sched.id]
        # Apos marcar a execucao no mesmo minuto, nao dispara de novo.
        schedules_repo.set_ultima_exec(db, sched, agora)
        assert scheduler.due([sched], agora) == []


def test_due_ignora_inativo_e_fora_de_horario(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _setup(db)
        inativo = schedules_repo.create(
            db,
            tenant.id,
            ScheduleCreate(script_id=script.id, cron_expr="* * * * *", ativo=False),
        )
        # 03:30 todo dia: nao casa um horario qualquer fora desse minuto.
        fora = schedules_repo.create(
            db, tenant.id, ScheduleCreate(script_id=script.id, cron_expr="30 3 * * *")
        )
        agora = datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc)
        ids = {s.id for s in scheduler.due([inativo, fora], agora)}
        assert ids == set()


def test_tick_executa_e_audita_com_origem_agendamento(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _setup(db)
        schedules_repo.create(
            db,
            tenant.id,
            ScheduleCreate(
                script_id=script.id, cron_expr="* * * * *", parametros="oi"
            ),
        )
        rodados = scheduler.tick(db, datetime.now(timezone.utc))
        assert rodados == 1
        eventos = events_repo.list_by_tenant(db, tenant.id)
        assert len(eventos) == 1
        payload = eventos[0].payload
        assert payload["origem"] == "agendamento"
        assert payload["status"] == "sucesso"
        assert "ARG:oi" in payload["stdout"]


def test_tick_nao_repete_no_mesmo_minuto(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _setup(db)
        schedules_repo.create(
            db, tenant.id, ScheduleCreate(script_id=script.id, cron_expr="* * * * *")
        )
        agora = datetime.now(timezone.utc)
        assert scheduler.tick(db, agora) == 1
        assert scheduler.tick(db, agora) == 0  # ja rodou neste minuto
        # Um minuto depois, dispara de novo.
        assert scheduler.tick(db, agora + timedelta(minutes=1)) == 1
