"""Alerta opcional via webhook (Discord/Telegram-compativel).

Diferencial do pitch. Best-effort: falha de alerta nunca quebra a execucao do script.
"""

import httpx

from app.core.config import settings
from app.models import Execution


def notify_failure(execution: Execution) -> None:
    if not settings.alert_webhook_url:
        return
    content = (
        f":rotating_light: Falha na execucao do script `{execution.script_nome}`\n"
        f"exit_code={execution.exit_code} | params={execution.parametros or '-'}\n"
        f"stderr: {execution.stderr[:500]}"
    )
    try:
        httpx.post(settings.alert_webhook_url, json={"content": content}, timeout=5)
    except httpx.HTTPError:
        # Best-effort: nao propaga erro de alerta.
        pass
