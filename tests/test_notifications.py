"""Testes do notificador best-effort (Slack webhook)."""

import httpx
import pytest

from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.models import Tenant
from app.repositories import events_repo, tenants_repo
from app.schemas import TenantCreate
from app.services import notifications
from app.core import events as ev


@pytest.fixture()
def captura(monkeypatch):
    """Captura as mensagens postadas no webhook (sem rede)."""
    enviadas: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        enviadas.append({"url": url, "json": json})

        class _R:
            status_code = 200

        return _R()

    monkeypatch.setattr(notifications.httpx, "post", fake_post)
    notifications._ultimo_status.clear()
    # Estado-base previsivel dos toggles (cada teste ajusta o que precisa).
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    monkeypatch.setattr(settings, "notify_on_failure", True)
    monkeypatch.setattr(settings, "notify_on_success", True)
    monkeypatch.setattr(settings, "notify_on_scheduled", True)
    monkeypatch.setattr(settings, "notify_on_fleet_red", True)
    return enviadas


def _tenant(slug="c1", webhook=None):
    return Tenant(id=1, slug=slug, nome=slug.upper(), dominio=f"{slug}.x", porta=8000,
                  db_name=f"db_{slug}", alert_webhook_url=webhook, token="tok-aaaa")


def _payload(status="falha", script="backup_db", **extra):
    base = {"script_nome": script, "status": status, "exit_code": 1 if status == "falha" else 0,
            "stderr": "boom" if status == "falha" else "", "duracao_ms": 1200, "categoria": "backup"}
    base.update(extra)
    return base


def test_webhook_tenant_sobrepoe_global(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "https://global")
    assert notifications._webhook_para(_tenant(webhook="https://tenant")) == "https://tenant"


def test_webhook_cai_no_global(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "https://global")
    assert notifications._webhook_para(_tenant(webhook=None)) == "https://global"


def test_sem_webhook_nao_envia(captura):
    notifications._enviar_execucao(_tenant(webhook=None), _payload("falha"), "manual")
    assert captura == []


def test_falha_envia_vermelho(captura):
    notifications._enviar_execucao(_tenant(webhook="https://t"), _payload("falha"), "manual")
    assert len(captura) == 1
    msg = captura[0]["json"]
    assert msg["attachments"][0]["color"] == "#dc2626"
    assert "Falha" in msg["attachments"][0]["blocks"][0]["text"]["text"]


def test_sucesso_respeita_toggle(captura, monkeypatch):
    monkeypatch.setattr(settings, "notify_on_success", False)
    notifications._enviar_execucao(_tenant(webhook="https://t"), _payload("sucesso"), "manual")
    assert captura == []


def test_agendado_tem_titulo_proprio(captura):
    notifications._enviar_execucao(_tenant(webhook="https://t"), _payload("sucesso"), "agendamento")
    assert "Agendado" in captura[0]["json"]["attachments"][0]["blocks"][0]["text"]["text"]


def test_best_effort_nao_propaga_erro(captura, monkeypatch):
    def boom(url, json=None, timeout=None):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(notifications.httpx, "post", boom)
    # Nao deve levantar excecao.
    notifications._enviar_execucao(_tenant(webhook="https://t"), _payload("falha"), "manual")


def test_send_test_sem_webhook_retorna_false(captura):
    assert notifications.send_test(_tenant(webhook=None)) is False
    assert captura == []


def test_send_test_com_webhook(captura):
    assert notifications.send_test(_tenant(webhook="https://t")) is True
    assert "Teste" in captura[0]["json"]["attachments"][0]["blocks"][0]["text"]["text"]


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_frota_vermelha_dispara_uma_vez_na_transicao(captura, db):
    tenant = tenants_repo.create(db, TenantCreate(
        slug="tux", nome="Tux", dominio="tux.x", porta=8001, db_name="db_tux",
        alert_webhook_url="https://t", token="tok-tuxxxx"))
    # Execucao com falha -> saude vermelha.
    events_repo.append(db, ev.EXECUTION_COMPLETED, _payload("falha", script="docker_status"),
                       tenant_id=tenant.id)
    notifications.notify_execution(db, tenant, _payload("falha", script="docker_status"), "manual")
    fleet = [m for m in captura if "Frota vermelha" in m["json"]["attachments"][0]["blocks"][0]["text"]["text"]]
    assert len(fleet) == 1
    # Segunda execucao ainda vermelha: nao repete o alerta de frota.
    events_repo.append(db, ev.EXECUTION_COMPLETED, _payload("falha", script="docker_status"),
                       tenant_id=tenant.id)
    notifications.notify_execution(db, tenant, _payload("falha", script="docker_status"), "manual")
    fleet2 = [m for m in captura if "Frota vermelha" in m["json"]["attachments"][0]["blocks"][0]["text"]["text"]]
    assert len(fleet2) == 1
