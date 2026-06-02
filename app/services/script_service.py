"""Regra de negocio do CRUD de scripts e validacao de caminho."""

from sqlalchemy.orm import Session

from app.core.security import ScriptPathError, resolve_script_path
from app.models import Script
from app.repositories import scripts_repo
from app.schemas import ScriptCreate, ScriptUpdate


class ScriptValidationError(ValueError):
    """Dados de script invalidos (nome duplicado, caminho fora da raiz)."""


def _validate_caminho(caminho: str) -> None:
    try:
        resolve_script_path(caminho)
    except ScriptPathError as exc:
        raise ScriptValidationError(str(exc)) from exc


def create(db: Session, data: ScriptCreate) -> Script:
    if scripts_repo.get_by_nome(db, data.nome):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    _validate_caminho(data.caminho)
    return scripts_repo.create(db, data)


def update(db: Session, script: Script, data: ScriptUpdate) -> Script:
    if (
        data.nome
        and data.nome != script.nome
        and scripts_repo.get_by_nome(db, data.nome)
    ):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    if data.caminho is not None:
        _validate_caminho(data.caminho)
    return scripts_repo.update(db, script, data)
