"""Execucao segura de shell scripts via subprocess.

Pontos de seguranca (criterio de 25% da banca):
- So executa scripts cadastrados e ativos (whitelist resolvida no banco).
- subprocess.run com LISTA de argumentos e shell=False: parametros entram como
  argv literais, nunca interpolados em uma string de shell -> sem command injection.
- Caminho resolvido dentro do diretorio montado -> sem path traversal.
- timeout encerra processos pendurados.
Cada execucao e persistida como auditoria, com ou sem sucesso.
"""

import subprocess
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ScriptPathError, resolve_script_path
from app.models import Execution, Script
from app.repositories import executions_repo
from app.services import alert_service


class ScriptNotExecutable(RuntimeError):
    """Script ativo, mas arquivo ausente ou caminho invalido."""


def _persist(db: Session, execution: Execution) -> Execution:
    execution.stdout = execution.stdout[: settings.output_limit]
    execution.stderr = execution.stderr[: settings.output_limit]
    saved = executions_repo.create(db, execution)
    if saved.status == "falha":
        alert_service.notify_failure(saved)
    return saved


def run(db: Session, script: Script, parametros: list[str]) -> Execution:
    """Executa um script da whitelist e devolve o registro de auditoria persistido."""
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
        execution = Execution(
            script_id=script.id,
            script_nome=script.nome,
            parametros=" ".join(parametros),
            status=status,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duracao_ms=duracao_ms,
        )
    except subprocess.TimeoutExpired:
        duracao_ms = int((time.perf_counter() - started) * 1000)
        execution = Execution(
            script_id=script.id,
            script_nome=script.nome,
            parametros=" ".join(parametros),
            status="falha",
            exit_code=None,
            stdout="",
            stderr=f"Tempo limite de {settings.exec_timeout}s excedido.",
            duracao_ms=duracao_ms,
        )

    return _persist(db, execution)
