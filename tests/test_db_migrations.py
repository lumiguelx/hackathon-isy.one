"""Migracao idempotente de colunas em tabelas ja existentes (init_db)."""

from sqlalchemy import inspect, text

from app.core.db import Base, engine, init_db


def test_migra_adiciona_tipo_e_template_em_scripts_antigo():
    # Simula um banco provisionado antes da feature: scripts SEM tipo/template.
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE scripts ("
                "id INTEGER PRIMARY KEY, nome VARCHAR(120), caminho VARCHAR(255), "
                "parametros VARCHAR(255), descricao VARCHAR(255), "
                "categoria VARCHAR(20), tenant_id INTEGER, ativo BOOLEAN, "
                "criado_em DATETIME)"
            )
        )
    antes = {c["name"] for c in inspect(engine).get_columns("scripts")}
    assert "tipo" not in antes and "template" not in antes

    init_db()  # create_all (nao toca scripts existente) + migracao de coluna

    depois = {c["name"] for c in inspect(engine).get_columns("scripts")}
    assert "tipo" in depois
    assert "template" in depois

    # idempotente: rodar de novo nao levanta.
    init_db()

    # restaura o schema completo para os demais testes.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
