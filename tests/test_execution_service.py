import pytest

from app.core.db import SessionLocal
from app.repositories import events_repo, scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from app.schemas import ScriptCreate as _SC
from app.services import execution_service
from tests.conftest import client  # noqa: F401


def _setup(db):
    t = tenants_repo.create(
        db,
        TenantCreate(
            slug="c1",
            nome="C1",
            dominio="c1.isy.one",
            porta=8151,
            db_name="db_c1",
            token="tok-c1-aaaaaa",
        ),
    )
    s = scripts_repo.create(
        db, ScriptCreate(nome="echo", caminho="echo_args.sh", categoria="other")
    )
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
        linhas = [
            linha
            for linha in event.payload["stdout"].splitlines()
            if linha.startswith("ARG:")
        ]
        assert "ARG:; rm -rf /" in event.payload["stdout"]
        assert len(linhas) == 2


def test_run_template_local_simulado_grava_evento(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="tux-burger",
                nome="Tux",
                dominio="tux.isy.one",
                porta=8201,
                db_name="db_tux_burger",
                token="tok-tux-aaaaaa",
            ),
        )
        s = scripts_repo.create(
            db,
            _SC(
                nome="reinicia",
                tipo="template",
                template="docker restart {{container:agent}}",
                categoria="update",
            ),
        )
        event = execution_service.run(db, t, s, [])
        assert event.payload["status"] == "sucesso"
        assert "isyone-tux-burger-ifood-agent" in event.payload["stdout"]


def test_run_template_param_invalido_levanta(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="c2",
                nome="C2",
                dominio="c2.isy.one",
                porta=8202,
                db_name="db_c2",
                token="tok-c2-aaaaaa",
            ),
        )
        s = scripts_repo.create(
            db,
            _SC(
                nome="limpa",
                tipo="template",
                template="cleanup {{param:dias:int}}",
                categoria="cleanup",
            ),
        )
        with pytest.raises(execution_service.ScriptNotExecutable):
            execution_service.run(db, t, s, ["abc"])
