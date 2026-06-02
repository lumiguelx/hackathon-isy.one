from app.core.db import SessionLocal
from app.repositories import tenants_repo
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
