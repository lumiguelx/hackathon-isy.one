from app.core import events as ev
from app.core.db import SessionLocal
from app.repositories import events_repo, tenants_repo
from app.schemas import TenantCreate
from app.services import health_service
from tests.conftest import client  # noqa: F401


def _tenant(db, slug="c1", porta=8151):
    return tenants_repo.create(
        db,
        TenantCreate(
            slug=slug,
            nome=slug.upper(),
            dominio=f"{slug}.isy.one",
            porta=porta,
            db_name=f"db_{slug}",
            token=f"tok-{slug}-aaaaaa",
        ),
    )


def test_config_publica_expoe_grafana_url(client):
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    assert "grafana_url" in res.json()["data"]


def test_status_vermelho_quando_ultima_falhou(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {"categoria": "cleanup", "status": "falha"},
            tenant_id=t.id,
        )
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "vermelho"


def test_status_amarelo_sem_backup_recente(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {"categoria": "cleanup", "status": "sucesso"},
            tenant_id=t.id,
        )
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "amarelo"


def test_status_verde_com_backup_recente(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {"categoria": "backup", "status": "sucesso"},
            tenant_id=t.id,
        )
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "verde"
        assert saude["ultimo_backup"] is not None
