from app.core.db import SessionLocal
from app.repositories import scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from tests.conftest import client  # noqa: F401


def test_binding_define_whitelist_do_tenant(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="c1",
                nome="C1",
                dominio="c1.isy.one",
                porta=8151,
                db_name="db_c1",
                token="tok-c1-xyz",
            ),
        )
        s = scripts_repo.create(
            db,
            ScriptCreate(
                nome="cleanup",
                caminho="cleanup_logs.sh",
                categoria="cleanup",
            ),
        )
        tenant_scripts_repo.upsert(db, t.id, s.id, parametros_default="7", ativo=True)

        disponiveis = tenant_scripts_repo.list_active_scripts(db, t.id)
        assert len(disponiveis) == 1
        script, binding = disponiveis[0]
        assert script.nome == "cleanup"
        assert binding.parametros_default == "7"
