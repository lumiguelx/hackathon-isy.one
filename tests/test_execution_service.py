from app.core.db import SessionLocal
from app.repositories import events_repo, scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from app.services import execution_service
from tests.conftest import client  # noqa: F401


def _setup(db):
    t = tenants_repo.create(db, TenantCreate(
        slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
        db_name="db_c1", token="tok-c1-aaaaaa"))
    s = scripts_repo.create(db, ScriptCreate(
        nome="echo", caminho="echo_args.sh", categoria="other"))
    return t, s


def test_execucao_grava_evento_sucesso(client):
    with SessionLocal() as db:
        t, s = _setup(db)
        event = execution_service.run(db, t, s, ["ola", "mundo"])
        assert event.payload["status"] == "sucesso"
        assert "ARG:ola" in event.payload["stdout"]
        eventos = events_repo.list_by_tenant(db, t.id)
        assert len(eventos) == 1


def test_command_injection_argv_literal(client):
    with SessionLocal() as db:
        t, s = _setup(db)
        event = execution_service.run(db, t, s, ["; rm -rf /", "$(id)"])
        linhas = [l for l in event.payload["stdout"].splitlines() if l.startswith("ARG:")]
        assert "ARG:; rm -rf /" in event.payload["stdout"]
        assert len(linhas) == 2
