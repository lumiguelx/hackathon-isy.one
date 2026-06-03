"""Regra de negocio do CRUD de scripts e validacao de caminho/template."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ScriptPathError, resolve_script_path
from app.models import Script
from app.repositories import scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, ScriptUpdate
from app.services import command, template_service

_SOURCE_MAX = 100_000
_SOURCE_EXTS = (".sh", ".py")


class ScriptValidationError(ValueError):
    """Dados de script invalidos (nome duplicado, caminho/template/dono invalido)."""


class ScriptEditDisabled(RuntimeError):
    """Edicao de codigo desabilitada (ISY_SCRIPT_EDIT_ENABLED=false)."""


def _validate_caminho(caminho: str) -> None:
    try:
        resolve_script_path(caminho)
    except ScriptPathError as exc:
        raise ScriptValidationError(str(exc)) from exc


def _validate_param_schema(param_schema) -> None:
    try:
        command.validate_schema(param_schema)
    except command.ParamError as exc:
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
    _validate_param_schema(data.param_schema)
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
    if data.param_schema is not None:
        _validate_param_schema(data.param_schema)
    return scripts_repo.update(db, script, data)


def _safe_source_path(caminho: str):
    if not caminho.endswith(_SOURCE_EXTS):
        raise ScriptValidationError("So e permitido editar arquivos .sh ou .py.")
    try:
        return resolve_script_path(caminho)
    except ScriptPathError as exc:
        raise ScriptValidationError(str(exc)) from exc


def read_source(script: Script) -> str:
    """Le o codigo do .sh/.py do script (editor inline). Vazio se ainda nao existe."""
    if script.tipo != "arquivo":
        raise ScriptValidationError("So scripts do tipo 'arquivo' tem codigo editavel.")
    path = _safe_source_path(script.caminho)
    return path.read_text()[:_SOURCE_MAX] if path.is_file() else ""


def write_source(script: Script, conteudo: str) -> None:
    """Grava o codigo do script no diretorio de scripts (guardado por path/extensao)."""
    if not settings.script_edit_enabled:
        raise ScriptEditDisabled("Edicao de codigo desabilitada (ISY_SCRIPT_EDIT_ENABLED).")
    if script.tipo != "arquivo":
        raise ScriptValidationError("So scripts do tipo 'arquivo' tem codigo editavel.")
    if len(conteudo) > _SOURCE_MAX:
        raise ScriptValidationError("Codigo excede o tamanho maximo.")
    path = _safe_source_path(script.caminho)
    path.write_text(conteudo)
    path.chmod(0o755)
