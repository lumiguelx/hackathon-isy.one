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


# Colunas adicionadas depois do primeiro deploy. create_all nao altera tabelas
# existentes, entao bancos ja provisionados (ex.: Postgres de producao) precisam
# de um ADD COLUMN idempotente no boot.
_MIGRACOES: dict[str, dict[str, str]] = {
    "scripts": {
        "tipo": "VARCHAR(20) NOT NULL DEFAULT 'arquivo'",
        "template": "VARCHAR(2000)",
    },
}


def _migrar_colunas_faltantes() -> None:
    """Adiciona colunas novas em tabelas ja existentes (idempotente, multi-dialeto).

    Compara o schema real com o esperado e so executa ADD COLUMN para o que falta,
    evitando depender de 'IF NOT EXISTS' (que o SQLite nao suporta).
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tabelas = set(inspector.get_table_names())
    for tabela, colunas in _MIGRACOES.items():
        if tabela not in tabelas:
            continue
        existentes = {c["name"] for c in inspector.get_columns(tabela)}
        faltando = {n: ddl for n, ddl in colunas.items() if n not in existentes}
        if not faltando:
            continue
        with engine.begin() as conn:
            for nome, ddl in faltando.items():
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {ddl}"))


def init_db() -> None:
    """Cria as tabelas e aplica migracoes leves de coluna (idempotentes)."""
    # Import local para registrar os models no metadata antes do create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrar_colunas_faltantes()
