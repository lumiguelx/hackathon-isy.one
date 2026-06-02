"""Execucao segura de scripts (tenant-scoped) gravando evento ExecutionCompleted.

Seguranca: whitelist por tenant (resolvida na rota), subprocess shell=False +
timeout, caminho dentro do diretorio montado (anti command injection / traversal).
Cada execucao vira um evento imutavel no event store, com ou sem sucesso.
"""

import subprocess
import time

from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.core.security import ScriptPathError, resolve_script_path
from app.models import Event, Script, Tenant
from app.repositories import events_repo
from app.services import alert_service


class ScriptNotExecutable(RuntimeError):
    """Script ativo, mas arquivo ausente ou caminho invalido."""


def run(db: Session, tenant: Tenant, script: Script, parametros: list[str]) -> Event:
    try:
        path = resolve_script_path(script.caminho)
    except ScriptPathError as exc:
        raise ScriptNotExecutable(str(exc)) from exc
    if not path.is_file():
        raise ScriptNotExecutable(f"Arquivo do script nao encontrado: {script.caminho}")

    # shell=False (default): cada item da lista e um argv isolado, sem interpretacao
    # de metacaracteres de shell. Esta e a barreira contra command injection.
    argv = [str(path), *parametros]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
        )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status = "sucesso" if proc.returncode == 0 else "falha"
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status, exit_code = "falha", None
        stdout, stderr = "", f"Tempo limite de {settings.exec_timeout}s excedido."

    payload = {
        "script_nome": script.nome,
        "categoria": script.categoria,
        "parametros": " ".join(parametros),
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout[: settings.output_limit],
        "stderr": stderr[: settings.output_limit],
        "duracao_ms": duracao_ms,
    }
    event = events_repo.append(
        db, ev.EXECUTION_COMPLETED, payload, tenant_id=tenant.id, script_id=script.id
    )
    if status == "falha":
        alert_service.notify_failure(tenant.slug, payload)
    return event
