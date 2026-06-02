"""Regra de negocio do CRUD de scripts e validacao de caminho/template."""

from sqlalchemy.orm import Session

from app.core.security import ScriptPathError, resolve_script_path
from app.models import Script
from app.repositories import scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, ScriptUpdate
from app.services import template_service


class ScriptValidationError(ValueError):
    """Dados de script invalidos (nome duplicado, caminho/template/dono invalido)."""


def _validate_caminho(caminho: str) -> None:
    try:
        resolve_script_path(caminho)
    except ScriptPathError as exc:
        raise ScriptValidationError(str(exc)) from exc


def _validate_template(template: str | None) -> None:
    try:
        template_service.validate(template)
    except template_service.TemplateError as exc:
        raise ScriptValidationError(str(exc)) from exc


def create(db: Session, data: ScriptCreate) -> Script:
    if scripts_repo.get_by_nome(db, data.nome):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    if data.tipo == "template":
        _validate_template(data.template)
    else:
        _validate_caminho(data.caminho)
    if data.tenant_id is not None and tenants_repo.get(db, data.tenant_id) is None:
        raise ScriptValidationError("Tenant dono nao encontrado.")
    script = scripts_repo.create(db, data)
    # Script dono-de-cliente fica disponivel para esse cliente via binding ativo.
    if script.tenant_id is not None:
        tenant_scripts_repo.upsert(db, script.tenant_id, script.id, "", True)
    return script


def update(db: Session, script: Script, data: ScriptUpdate) -> Script:
    if (
        data.nome
        and data.nome != script.nome
        and scripts_repo.get_by_nome(db, data.nome)
    ):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    # Dono (tenant_id) e imutavel apos a criacao: ScriptUpdate nao o expoe.
    # Reforca a coerencia tipo/caminho/template considerando o patch parcial.
    tipo_final = data.tipo or script.tipo
    if tipo_final == "template":
        template_final = data.template if data.template is not None else script.template
        _validate_template(template_final)
    else:
        caminho_final = data.caminho if data.caminho is not None else script.caminho
        if not caminho_final:
            raise ScriptValidationError("caminho e obrigatorio para tipo 'arquivo'.")
        _validate_caminho(caminho_final)
    return scripts_repo.update(db, script, data)
