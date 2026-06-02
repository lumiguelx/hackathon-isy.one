import pytest
from fastapi import HTTPException

from app.core.db import SessionLocal
from app.core.security import verify_tenant
from app.repositories import tenants_repo
from app.schemas import TenantCreate
from tests.conftest import client  # noqa: F401


def _seed_dois_tenants(db):
    tenants_repo.create(db, TenantCreate(
        slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
        db_name="db_c1", token="tok-c1-aaaaaa"))
    tenants_repo.create(db, TenantCreate(
        slug="c2", nome="C2", dominio="c2.isy.one", porta=8152,
        db_name="db_c2", token="tok-c2-bbbbbb"))


def test_token_do_tenant_so_acessa_o_proprio(client):
    with SessionLocal() as db:
        _seed_dois_tenants(db)
        # token do c1 acessa c1
        t = verify_tenant("c1", x_isy_token="tok-c1-aaaaaa", db=db)
        assert t.slug == "c1"
        # token do c1 NAO acessa c2
        with pytest.raises(HTTPException) as exc:
            verify_tenant("c2", x_isy_token="tok-c1-aaaaaa", db=db)
        assert exc.value.status_code == 401


def test_token_admin_acessa_qualquer_tenant(client):
    with SessionLocal() as db:
        _seed_dois_tenants(db)
        # token admin default vem do config (settings.token)
        from app.repositories import config_repo
        admin = config_repo.get_token(db)
        t = verify_tenant("c2", x_isy_token=admin, db=db)
        assert t.slug == "c2"
