"""Seed opcional de scripts de demonstracao (ativado por ISY_SEED_DEMO).

So roda se a tabela de scripts estiver vazia, para nao duplicar em reboots.
"""

from sqlalchemy.orm import Session

from app.repositories import scripts_repo
from app.schemas import ScriptCreate

DEMO_SCRIPTS = [
    ScriptCreate(
        nome="provisionar",
        caminho="provisionar.sh",
        parametros="<slug> <dominio> <porta>",
        descricao="Provisiona novo cliente Odoo (estrutura, Nginx/SSL, containers).",
    ),
    ScriptCreate(
        nome="update_agent",
        caminho="update_agent.sh",
        parametros="<db>",
        descricao="Atualiza o agente/instancia Odoo do cliente e reinicia.",
    ),
    ScriptCreate(
        nome="cleanup_logs",
        caminho="cleanup_logs.sh",
        parametros="[dias_retencao]",
        descricao="Limpa e rotaciona logs antigos do Odoo.",
    ),
    ScriptCreate(
        nome="docker_status",
        caminho="docker_status.sh",
        parametros="[slug]",
        descricao="Checa status dos containers Docker (Postgres + Odoo).",
    ),
]


def seed_demo(db: Session) -> None:
    if scripts_repo.list_all(db):
        return
    for data in DEMO_SCRIPTS:
        scripts_repo.create(db, data)
