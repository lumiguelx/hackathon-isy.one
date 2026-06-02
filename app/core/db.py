"""Engine e sessao do SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _normalize_db_url(url: str) -> str:
    """Forca o driver psycopg v3 em URLs Postgres.

    Railway/Heroku entregam 'postgres://' ou 'postgresql://', que o SQLAlchemy
    mapeia para psycopg2 (nao instalado). Reescreve para 'postgresql+psycopg://'.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


_db_url = _normalize_db_url(settings.database_url)

# check_same_thread so importa para SQLite; ignorado por outros drivers.
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: abre e fecha uma sessao por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria as tabelas. Para o hackathon basta create_all; migracoes ficam como evolucao."""
    # Import local para registrar os models no metadata antes do create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
