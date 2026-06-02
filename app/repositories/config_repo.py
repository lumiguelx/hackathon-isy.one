"""Acesso a tabela config (token vigente, linha unica id=1)."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Config

_ROW_ID = 1


def get_token(db: Session) -> str:
    """Retorna o token vigente, semeando a partir do env no primeiro acesso."""
    row = db.get(Config, _ROW_ID)
    if row is None:
        row = Config(id=_ROW_ID, token=settings.token)
        db.add(row)
        db.commit()
    return row.token


def set_token(db: Session, token: str) -> None:
    row = db.get(Config, _ROW_ID)
    if row is None:
        row = Config(id=_ROW_ID, token=token)
        db.add(row)
    else:
        row.token = token
    db.commit()
