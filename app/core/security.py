"""Autenticacao por X-Isy-Token e resolucao segura de caminho de script."""

import secrets
from pathlib import Path

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.repositories import config_repo


def verify_token(
    x_isy_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """Valida o header X-Isy-Token contra o token vigente no banco.

    Comparacao em tempo constante (compare_digest) para evitar timing attack.
    """
    current = config_repo.get_token(db)
    if not x_isy_token or not secrets.compare_digest(x_isy_token, current):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou ausente.",
        )


class ScriptPathError(ValueError):
    """Caminho de script invalido ou fora do diretorio permitido."""


def resolve_script_path(caminho: str) -> Path:
    """Resolve o caminho do script dentro do diretorio montado.

    Rejeita path traversal: o arquivo resolvido precisa residir sob scripts_dir.
    Nao executa nada; so valida e devolve o Path absoluto.
    """
    base = Path(settings.scripts_dir).resolve()
    candidate = (base / caminho).resolve()
    if base != candidate and base not in candidate.parents:
        raise ScriptPathError("Caminho fora do diretorio de scripts permitido.")
    return candidate
