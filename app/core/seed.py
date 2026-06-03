"""Seed de demonstracao: 5 clientes, catalogo, bindings e eventos historicos.

Ativado por ISY_SEED_DEMO. So roda se nao houver tenants (idempotente por boot).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.repositories import (
    events_repo,
    schedules_repo,
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import ScheduleCreate, ScriptCreate, TenantCreate

CATALOGO = [
    ScriptCreate(
        nome="provisionar",
        caminho="provisionar.sh",
        categoria="provision",
        descricao="Provisiona/recria a stack do cliente.",
    ),
    ScriptCreate(
        nome="backup_db",
        caminho="backup_db.sh",
        categoria="backup",
        descricao="Backup do banco + filestore.",
    ),
    ScriptCreate(
        nome="cleanup_logs",
        caminho="cleanup_logs.sh",
        categoria="cleanup",
        descricao="Limpa/rotaciona logs antigos.",
        param_schema=[
            {
                "nome": "dias",
                "rotulo": "Dias de retenção",
                "tipo": "int",
                "default": "30",
                "minimo": 1,
                "maximo": 365,
            },
        ],
    ),
    ScriptCreate(
        nome="update_agent",
        caminho="update_agent.sh",
        categoria="update",
        descricao="Atualiza o agente/instancia e reinicia.",
    ),
    ScriptCreate(
        nome="docker_status",
        caminho="docker_status.sh",
        categoria="status",
        descricao="Status dos containers.",
        param_schema=[
            {
                "nome": "filtro",
                "rotulo": "Filtro de nome (opcional)",
                "tipo": "text",
                "default": "",
            },
        ],
    ),
    ScriptCreate(
        nome="docker_ctl",
        caminho="docker_ctl.sh",
        categoria="status",
        descricao="Gerencia um container do cliente (status/restart/stop/logs).",
        param_schema=[
            {
                "nome": "acao",
                "rotulo": "Ação",
                "tipo": "select",
                "arg": "--acao",
                "obrigatorio": True,
                "default": "status",
                "choices": ["status", "restart", "stop", "logs"],
            },
            {
                "nome": "papel",
                "rotulo": "Container",
                "tipo": "select",
                "arg": "--papel",
                "obrigatorio": True,
                "default": "odoo",
                "choices": ["db", "odoo", "agent"],
            },
            {
                "nome": "linhas",
                "rotulo": "Linhas (logs)",
                "tipo": "int",
                "arg": "--linhas",
                "default": "100",
                "minimo": 1,
                "maximo": 5000,
            },
        ],
    ),
]


def _now():
    return datetime.now(timezone.utc)


def _seed_historico(db: Session, i: int, tenant, scripts: dict) -> None:
    """Eventos historicos por cliente, definindo o status inicial do dashboard."""
    if i == 1:  # vermelho: ultima manutencao falhou
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {
                "script_nome": "update_agent",
                "categoria": "update",
                "status": "falha",
                "exit_code": 1,
                "stdout": "",
                "stderr": "conexao recusada",
                "parametros": f"db_cliente{i}",
            },
            tenant_id=tenant.id,
            script_id=scripts["update_agent"].id,
            ocorrido_em=_now() - timedelta(hours=2),
        )
    elif i == 2:  # amarelo: backup antigo
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {
                "script_nome": "backup_db",
                "categoria": "backup",
                "status": "sucesso",
                "exit_code": 0,
                "stdout": "Backup concluido.",
                "stderr": "",
                "parametros": f"db_cliente{i}",
            },
            tenant_id=tenant.id,
            script_id=scripts["backup_db"].id,
            ocorrido_em=_now() - timedelta(days=12),
        )
    else:  # verde: backup recente + status ok
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {
                "script_nome": "backup_db",
                "categoria": "backup",
                "status": "sucesso",
                "exit_code": 0,
                "stdout": "Backup concluido.",
                "stderr": "",
                "parametros": f"db_cliente{i}",
            },
            tenant_id=tenant.id,
            script_id=scripts["backup_db"].id,
            ocorrido_em=_now() - timedelta(days=1),
        )
        events_repo.append(
            db,
            ev.EXECUTION_COMPLETED,
            {
                "script_nome": "docker_status",
                "categoria": "status",
                "status": "sucesso",
                "exit_code": 0,
                "stdout": f"isyone-cliente{i}-db Up (healthy)\nisyone-cliente{i}-odoo Up (healthy)",
                "stderr": "",
                "parametros": f"cliente{i}",
            },
            tenant_id=tenant.id,
            script_id=scripts["docker_status"].id,
            ocorrido_em=_now() - timedelta(minutes=10),
        )


def seed_demo(db: Session) -> None:
    if tenants_repo.list_all(db):
        return

    scripts = {c.nome: scripts_repo.create(db, c) for c in CATALOGO}

    for i in range(1, 6):
        slug = f"cliente-{i}"
        # cliente-1 e o alvo da demo real: aponta para a caixa AWS quando
        # ISY_DEMO_SSH_HOST esta setado (senao roda simulado).
        ssh_host = settings.demo_ssh_host if (i == 1 and settings.demo_ssh_host) else None
        tenant = tenants_repo.create(
            db,
            TenantCreate(
                slug=slug,
                nome=f"Cliente {i}",
                dominio=f"cliente{i}.isy.one",
                porta=8150 + i,
                db_name=f"db_cliente{i}",
                token=f"tok-{slug}-000000",
                ssh_host=ssh_host,
                ssh_port=settings.demo_ssh_port if ssh_host else None,
            ),
        )
        defaults = {
            "provisionar": f"cliente{i} cliente{i}.isy.one {8150 + i}",
            "backup_db": f"db_cliente{i}",
            "cleanup_logs": "30",
            "update_agent": f"db_cliente{i}",
            "docker_status": f"cliente{i}",
            "docker_ctl": "",
        }
        for nome, script in scripts.items():
            tenant_scripts_repo.upsert(db, tenant.id, script.id, defaults[nome], True)

        _seed_historico(db, i, tenant, scripts)

        # Piloto automatico ao vivo: cliente-1 roda docker_status a cada minuto,
        # para a banca ver execucoes surgindo sozinhas na auditoria.
        if i == 1:
            schedules_repo.create(
                db,
                tenant.id,
                ScheduleCreate(
                    script_id=scripts["docker_status"].id,
                    cron_expr="* * * * *",
                    parametros=f"cliente{i}",
                    ativo=True,
                ),
            )
