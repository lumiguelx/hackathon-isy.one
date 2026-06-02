from app.core.db import SessionLocal
from app.repositories import scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from app.services import execution_service
from tests.conftest import client  # noqa: F401


def _script(db):
    return scripts_repo.create(
        db, ScriptCreate(nome="env", caminho="echo_env.sh", categoria="status")
    )


def test_injeta_endpoint_ssh_quando_tenant_tem_ssh_host(client):
    with SessionLocal() as db:
        t = tenants_repo.create(db, TenantCreate(
            slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
            db_name="db_c1", ssh_host="10.0.0.9", ssh_port=2201, token="tok-c1-aaaaaa"))
        event = execution_service.run(db, t, _script(db), [])
        assert "HOST:10.0.0.9" in event.payload["stdout"]
        assert "PORT:2201" in event.payload["stdout"]
        assert "USER:isyone" in event.payload["stdout"]


def test_ssh_port_default_22_quando_omitido(client):
    with SessionLocal() as db:
        t = tenants_repo.create(db, TenantCreate(
            slug="c3", nome="C3", dominio="c3.isy.one", porta=8153,
            db_name="db_c3", ssh_host="10.0.0.7", token="tok-c3-cccccc"))
        event = execution_service.run(db, t, _script(db), [])
        assert "PORT:22" in event.payload["stdout"]


def test_sem_ssh_host_nao_injeta_endpoint(client):
    with SessionLocal() as db:
        t = tenants_repo.create(db, TenantCreate(
            slug="c2", nome="C2", dominio="c2.isy.one", porta=2202,
            db_name="db_c2", token="tok-c2-bbbbbb"))
        event = execution_service.run(db, t, _script(db), [])
        # Sem ssh_host, nenhuma variavel SSH e injetada -> linhas vazias.
        assert "HOST:\n" in event.payload["stdout"] or event.payload["stdout"].startswith("HOST:\n")
        assert "PORT:\n" in event.payload["stdout"]
