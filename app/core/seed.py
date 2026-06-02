"""Seed de demonstracao: 5 clientes, catalogo, bindings e eventos historicos.

Ativado por ISY_SEED_DEMO. So roda se nao houver tenants (idempotente por boot).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import events as ev
from app.repositories import (
    events_repo,
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import ScriptCreate, TenantCreate

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
        tenant = tenants_repo.create(
            db,
            TenantCreate(
                slug=slug,
                nome=f"Cliente {i}",
                dominio=f"cliente{i}.isy.one",
                porta=8150 + i,
                db_name=f"db_cliente{i}",
                token=f"tok-{slug}-000000",
            ),
        )
        defaults = {
            "provisionar": f"cliente{i} cliente{i}.isy.one {8150 + i}",
            "backup_db": f"db_cliente{i}",
            "cleanup_logs": "30",
            "update_agent": f"db_cliente{i}",
            "docker_status": f"cliente{i}",
        }
        for nome, script in scripts.items():
            tenant_scripts_repo.upsert(db, tenant.id, script.id, defaults[nome], True)

        _seed_historico(db, i, tenant, scripts)
