from app.core.db import _normalize_db_url


def test_normaliza_postgres_para_psycopg():
    assert _normalize_db_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert _normalize_db_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_nao_mexe_em_sqlite_nem_em_url_ja_normalizada():
    assert _normalize_db_url("sqlite:///./isyone.db") == "sqlite:///./isyone.db"
    assert _normalize_db_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
