"""Testa o repositorio de agendamentos (schedules_repo)."""

from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.repositories import schedules_repo, scripts_repo, tenants_repo
from app.schemas import ScheduleCreate, ScheduleUpdate, ScriptCreate, TenantCreate
from tests.conftest import client  # noqa: F401


def _tenant_e_script(db):
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
    return tenant, script


def test_create_e_list(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _tenant_e_script(db)
        sched = schedules_repo.create(
            db,
            tenant.id,
            ScheduleCreate(script_id=script.id, cron_expr="0 3 * * *", parametros="x"),
        )
        assert sched.id is not None
        assert [s.id for s in schedules_repo.list_by_tenant(db, tenant.id)] == [sched.id]
        assert [s.id for s in schedules_repo.list_active(db)] == [sched.id]


def test_update_desativa_some_de_list_active(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _tenant_e_script(db)
        sched = schedules_repo.create(
            db, tenant.id, ScheduleCreate(script_id=script.id, cron_expr="* * * * *")
        )
        schedules_repo.update(db, sched, ScheduleUpdate(ativo=False))
        assert schedules_repo.list_active(db) == []
        assert len(schedules_repo.list_by_tenant(db, tenant.id)) == 1


def test_set_ultima_exec_e_delete(client):  # noqa: F811
    with SessionLocal() as db:
        tenant, script = _tenant_e_script(db)
        sched = schedules_repo.create(
            db, tenant.id, ScheduleCreate(script_id=script.id, cron_expr="* * * * *")
        )
        agora = datetime.now(timezone.utc)
        schedules_repo.set_ultima_exec(db, sched, agora)
        assert schedules_repo.get(db, sched.id).ultima_exec is not None
        schedules_repo.delete(db, sched)
        assert schedules_repo.get(db, sched.id) is None
