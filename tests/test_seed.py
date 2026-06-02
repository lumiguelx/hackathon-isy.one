from app.core.db import SessionLocal
from app.core.seed import seed_demo
from app.repositories import tenants_repo
from app.services import health_service
from tests.conftest import client  # noqa: F401


def test_seed_cria_5_clientes_com_status_variado(client):
    with SessionLocal() as db:
        seed_demo(db)
        tenants = tenants_repo.list_all(db)
        assert len(tenants) == 5
        status = {t.slug: health_service.calcular_saude(db, t)["status_geral"] for t in tenants}
        assert status["cliente-1"] == "vermelho"
        assert status["cliente-2"] == "amarelo"
        assert status["cliente-3"] == "verde"
