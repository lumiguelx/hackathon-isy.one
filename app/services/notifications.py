"""Notificacoes best-effort via Slack Incoming Webhook.

Diferencial do pitch: avisa falha de script, sucesso de manutencao, execucao
agendada (cron) e quando a saude de um cliente vira vermelho. Best-effort: um erro
de notificacao NUNCA quebra a execucao. O webhook do proprio tenant tem prioridade;
na ausencia dele, cai no webhook global (ISY_ALERT_WEBHOOK_URL).
"""

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Tenant

logger = logging.getLogger("isyone.notifications")

# Barra lateral colorida no Slack, alinhada a paleta de status da frota.
_GREEN = "#1f9d57"
_RED = "#dc2626"
_AMBER = "#e8920c"

# Ultimo status de saude notificado por tenant (em memoria, por processo). Evita
# repetir o alerta de "frota vermelha" a cada execucao: so dispara na transicao.
_ultimo_status: dict[int, str] = {}


def _webhook_para(tenant: Tenant | None) -> str:
    if tenant is not None and tenant.alert_webhook_url:
        return tenant.alert_webhook_url
    return settings.alert_webhook_url


def _post(url: str, message: dict) -> None:
    try:
        httpx.post(url, json=message, timeout=5)
    except httpx.HTTPError:
        # Best-effort: nao propaga erro de notificacao.
        logger.warning("falha ao enviar notificacao (ignorado)")


def _slack_message(
    cor: str, titulo: str, resumo: str, campos: list[tuple[str, str]]
) -> dict:
    """Mensagem Slack com barra colorida (attachment) + Block Kit."""
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": titulo[:150]}}
    ]
    if campos:
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{k}:*\n{v}"} for k, v in campos[:10]
                ],
            }
        )
    return {"text": resumo, "attachments": [{"color": cor, "blocks": blocks}]}


def _dur(payload: dict) -> str:
    ms = payload.get("duracao_ms")
    return f"{ms / 1000:.1f}s" if isinstance(ms, (int, float)) else "-"


def _enviar_execucao(tenant: Tenant, payload: dict, origem: str) -> None:
    status = payload.get("status")
    script = payload.get("script_nome", "?")
    # Precedencia: agendado > falha > sucesso (uma mensagem por execucao).
    if origem == "agendamento":
        if not settings.notify_on_scheduled:
            return
        cor = _GREEN if status == "sucesso" else _RED
        titulo = f":robot_face: Agendado: {script} — {tenant.nome}"
    elif status == "falha":
        if not settings.notify_on_failure:
            return
        cor = _RED
        titulo = f":rotating_light: Falha: {script} — {tenant.nome}"
    elif status == "sucesso":
        if not settings.notify_on_success:
            return
        cor = _GREEN
        titulo = f":white_check_mark: OK: {script} — {tenant.nome}"
    else:
        return

    campos = [
        ("Cliente", tenant.slug),
        ("Script", script),
        ("Status", status or "-"),
        ("Exit", str(payload.get("exit_code"))),
        ("Origem", origem),
        ("Duracao", _dur(payload)),
    ]
    stderr = (payload.get("stderr") or "").strip()
    if stderr:
        campos.append(("Erro", f"`{stderr[:300]}`"))
    url = _webhook_para(tenant)
    if url:
        _post(url, _slack_message(cor, titulo, f"{tenant.nome}: {script} -> {status}", campos))


def _checar_frota_vermelha(db: Session, tenant: Tenant) -> None:
    if not settings.notify_on_fleet_red:
        return
    from app.services import health_service  # import tardio: evita ciclo de import

    saude = health_service.calcular_saude(db, tenant)
    novo = saude["status_geral"]
    anterior = _ultimo_status.get(tenant.id)
    _ultimo_status[tenant.id] = novo
    if novo != "vermelho" or anterior == "vermelho":
        return
    url = _webhook_para(tenant)
    if not url:
        return
    campos = [("Cliente", tenant.slug), ("Saude", "VERMELHO")]
    ultima = saude.get("ultima_manutencao") or {}
    if ultima:
        campos.append(
            ("Ultima manutencao", f"{ultima.get('script_nome', '-')} ({ultima.get('status', '-')})")
        )
    _post(
        url,
        _slack_message(
            _RED,
            f":red_circle: Frota vermelha — {tenant.nome}",
            f"{tenant.nome}: saude do cliente virou vermelho",
            campos,
        ),
    )


def notify_execution(db: Session, tenant: Tenant, payload: dict, origem: str) -> None:
    """Notifica o resultado de uma execucao e o flip da saude para vermelho.

    Best-effort: qualquer erro aqui e engolido para nao afetar a execucao.
    """
    try:
        _enviar_execucao(tenant, payload, origem)
        _checar_frota_vermelha(db, tenant)
    except Exception:  # noqa: BLE001 - notificacao nunca propaga erro
        logger.exception("erro ao notificar execucao (ignorado)")


def send_test(tenant: Tenant) -> bool:
    """Envia uma notificacao de teste. Retorna False se nao ha webhook configurado."""
    url = _webhook_para(tenant)
    if not url:
        return False
    origem_wh = "proprio" if tenant.alert_webhook_url else "global"
    _post(
        url,
        _slack_message(
            _AMBER,
            f":bell: Teste de notificacao — {tenant.nome}",
            f"Teste de notificacao para {tenant.nome}",
            [("Cliente", tenant.slug), ("Webhook", origem_wh)],
        ),
    )
    return True
