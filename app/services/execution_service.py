"""Execucao segura de scripts (tenant-scoped) gravando evento ExecutionCompleted.

Seguranca: whitelist por tenant (resolvida na rota), subprocess shell=False +
timeout, caminho dentro do diretorio montado (anti command injection / traversal).
Cada execucao vira um evento imutavel no event store, com ou sem sucesso.
"""

import os
import subprocess
import threading
import time
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.core.security import ScriptPathError, resolve_script_path
from app.models import Event, Script, Tenant
from app.repositories import events_repo
from app.services import alert_service, template_service


class ScriptNotExecutable(RuntimeError):
    """Script ativo, mas arquivo ausente ou caminho invalido."""


def _effective_params(tenant: Tenant, script: Script, parametros: list[str]) -> list[str]:
    """Parametros efetivos da execucao, fixando o alvo de provisao no proprio tenant.

    provisionar.sh recebe <slug> <dominio> <porta> por posicao. Aceitar esses valores
    do cliente permitiria provisionar/recriar a stack de OUTRO tenant (os containers e o
    banco sao recriados do zero). Para a categoria 'provision' o alvo e sempre o proprio
    tenant; quaisquer parametros recebidos sao ignorados.
    """
    if script.categoria == "provision":
        return [tenant.slug, tenant.dominio, str(tenant.porta)]
    return parametros


def _build_env(tenant: Tenant) -> dict:
    """Env do subprocess com o slug e o endpoint SSH do tenant, quando configurado.

    ISY_TENANT_SLUG identifica o cliente para os scripts (ex.: diretorio de logs,
    nome dos containers no servidor remoto). ISY_SSH_KEY (chave privada) ja vem do
    ambiente do container e e repassada. Sem ssh_host, nenhuma variavel SSH e
    injetada e o script roda localmente.
    """
    env = os.environ.copy()
    env["ISY_TENANT_SLUG"] = tenant.slug
    if tenant.ssh_host:
        env["ISY_SSH_HOST"] = tenant.ssh_host
        env["ISY_SSH_PORT"] = str(tenant.ssh_port or 22)
        env["ISY_SSH_USER"] = settings.ssh_user
    return env


def _record(
    db: Session,
    tenant: Tenant,
    script: Script,
    parametros: list[str],
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    duracao_ms: int,
) -> Event:
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


def _run_template(
    tenant: Tenant, script: Script, valores: list[str]
) -> tuple[str, str, str, int | None]:
    """Renderiza e executa um template. Remoto via _ssh.sh; local simulado."""
    rendered = template_service.render(script.template, tenant, valores)
    if tenant.ssh_host:
        ssh = resolve_script_path("_ssh.sh")
        proc = subprocess.run(
            [str(ssh), rendered],
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
            env=_build_env(tenant),
        )
        status = "sucesso" if proc.returncode == 0 else "falha"
        return status, proc.stdout, proc.stderr, proc.returncode
    return "sucesso", f"[local simulado] {rendered}\nOK (simulado).", "", 0


def run(db: Session, tenant: Tenant, script: Script, parametros: list[str]) -> Event:
    if script.tipo == "template":
        started = time.perf_counter()
        try:
            status, stdout, stderr, exit_code = _run_template(tenant, script, parametros)
        except template_service.TemplateError as exc:
            raise ScriptNotExecutable(str(exc)) from exc
        except subprocess.TimeoutExpired:
            status, stdout, stderr, exit_code = (
                "falha",
                "",
                f"Tempo limite de {settings.exec_timeout}s excedido.",
                None,
            )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        return _record(
            db, tenant, script, parametros, status, stdout, stderr, exit_code, duracao_ms
        )

    try:
        path = resolve_script_path(script.caminho)
    except ScriptPathError as exc:
        raise ScriptNotExecutable(str(exc)) from exc
    if not path.is_file():
        raise ScriptNotExecutable(f"Arquivo do script nao encontrado: {script.caminho}")

    # shell=False (default): cada item da lista e um argv isolado, sem interpretacao
    # de metacaracteres de shell. Esta e a barreira contra command injection.
    parametros = _effective_params(tenant, script, parametros)
    argv = [str(path), *parametros]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
            env=_build_env(tenant),
        )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status = "sucesso" if proc.returncode == 0 else "falha"
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status, exit_code = "falha", None
        stdout, stderr = "", f"Tempo limite de {settings.exec_timeout}s excedido."
    return _record(
        db, tenant, script, parametros, status, stdout, stderr, exit_code, duracao_ms
    )


def deprovision_remote(tenant: Tenant) -> str:
    """Best-effort: remove os containers do cliente no servidor (deprovisionar.sh).

    Nao levanta excecao se falhar — a remocao do tenant no banco prossegue mesmo
    que o servidor esteja inacessivel. Retorna a saida para log/debug.
    """
    try:
        path = resolve_script_path("deprovisionar.sh")
        if not path.is_file():
            return ""
        proc = subprocess.run(
            [str(path), tenant.slug],
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
            env=_build_env(tenant),
        )
        return proc.stdout + proc.stderr
    except (OSError, subprocess.SubprocessError):
        return ""


def stream_script(
    tenant: Tenant, script: Script, parametros: list[str]
) -> Iterator[tuple[str, object]]:
    """Roda o script emitindo a saida linha-a-linha para feedback ao vivo (SSE).

    Gera ("out", linha) por linha e, ao final, ("end", payload) com o resultado
    completo. Nao grava evento nem dispara alerta: isso fica a cargo do chamador,
    fora do streaming (a sessao de banco da request ja pode estar fechada).
    """
    try:
        path = resolve_script_path(script.caminho)
    except ScriptPathError as exc:
        raise ScriptNotExecutable(str(exc)) from exc
    if not path.is_file():
        raise ScriptNotExecutable(f"Arquivo do script nao encontrado: {script.caminho}")

    parametros = _effective_params(tenant, script, parametros)
    argv = [str(path), *parametros]
    started = time.perf_counter()
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # funde stderr no stream para feedback unico
        text=True,
        bufsize=1,
        env=_build_env(tenant),
    )
    # Watchdog: mata o processo se passar do timeout (a leitura bloqueante de stdout
    # nao detecta timeout sozinha).
    timed_out = {"v": False}

    def _kill() -> None:
        timed_out["v"] = True
        proc.kill()

    watchdog = threading.Timer(settings.exec_timeout, _kill)
    watchdog.start()
    out_lines: list[str] = []
    try:
        for line in proc.stdout or []:
            out_lines.append(line)
            yield ("out", line.rstrip("\n"))
        proc.wait()
    finally:
        watchdog.cancel()
        if proc.stdout:
            proc.stdout.close()

    duracao_ms = int((time.perf_counter() - started) * 1000)
    if timed_out["v"]:
        status, exit_code = "falha", None
        stderr = f"Tempo limite de {settings.exec_timeout}s excedido."
    else:
        exit_code = proc.returncode
        status = "sucesso" if exit_code == 0 else "falha"
        stderr = ""

    payload = {
        "script_nome": script.nome,
        "categoria": script.categoria,
        "parametros": " ".join(parametros),
        "status": status,
        "exit_code": exit_code,
        "stdout": "".join(out_lines)[: settings.output_limit],
        "stderr": stderr,
        "duracao_ms": duracao_ms,
    }
    yield ("end", payload)
