from app.core import events as ev
from app.core.db import SessionLocal
from app.repositories import events_repo, tenants_repo
from app.schemas import TenantCreate
from tests.conftest import client  # noqa: F401


def test_create_e_get_by_slug(client):
    with SessionLocal() as db:
        tenants_repo.create(
            db,
            TenantCreate(
                slug="cliente-1",
                nome="Cliente 1",
                dominio="cliente1.isy.one",
                porta=8151,
                db_name="db_cliente1",
                token="tok-cliente-1-xyz",
            ),
        )
        t = tenants_repo.get_by_slug(db, "cliente-1")
        assert t is not None
        assert t.db_name == "db_cliente1"


def test_delete_remove_tenant_com_eventos(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="cliente-x",
                nome="Cliente X",
                dominio="x.isy.one",
                porta=8160,
                db_name="db_x",
                token="tok-cliente-x-xyz",
            ),
        )
        events_repo.append(
            db, ev.EXECUTION_COMPLETED, {"status": "sucesso"}, tenant_id=t.id
        )
        tenants_repo.delete(db, t)
        assert tenants_repo.get_by_slug(db, "cliente-x") is None
