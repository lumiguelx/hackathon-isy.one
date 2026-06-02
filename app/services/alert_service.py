"""Alerta opcional via webhook (Discord/Telegram-compativel).

Diferencial do pitch. Best-effort: falha de alerta nunca quebra a execucao do script.
"""

import httpx

from app.core.config import settings


def notify_failure(tenant_slug: str, payload: dict) -> None:
    if not settings.alert_webhook_url:
        return
    content = (
        f":rotating_light: Falha em `{tenant_slug}` / `{payload.get('script_nome')}`\n"
        f"exit_code={payload.get('exit_code')} | params={payload.get('parametros') or '-'}\n"
        f"stderr: {str(payload.get('stderr'))[:500]}"
    )
    try:
        httpx.post(settings.alert_webhook_url, json={"content": content}, timeout=5)
    except httpx.HTTPError:
        # Best-effort: nao propaga erro de alerta.
        pass
