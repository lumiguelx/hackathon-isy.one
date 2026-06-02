from app.core.db import SessionLocal
from app.repositories import scripts_repo, tenants_repo
from app.schemas import ScriptCreate
from tests.conftest import client  # noqa: F401


def _provisionar(db):
    # echo_args.sh existe nas fixtures e ecoa os argumentos -> simula o provisionar.
    return scripts_repo.create(
        db,
        ScriptCreate(nome="provisionar", caminho="echo_args.sh", categoria="provision"),
    )


def test_registro_provisiona_e_devolve_credenciais(client):
    with SessionLocal() as db:
        _provisionar(db)

    res = client.post(
        "/api/v1/registro",
        json={"nome": "Tux Burger", "email": "dono@tux.com", "plano": "free"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    body = res.text
    assert "event: tenant" in body
    assert "event: done" in body

    with SessionLocal() as db:
        t = tenants_repo.get_by_slug(db, "tux-burger")
        assert t is not None
        assert t.token.startswith("tok-tux-burger-")
        assert t.db_name == "db_tux_burger"


def test_registro_gera_slug_unico(client):
    with SessionLocal() as db:
        _provisionar(db)
    client.post("/api/v1/registro", json={"nome": "Bar X", "email": "a@b.com"})
    client.post("/api/v1/registro", json={"nome": "Bar X", "email": "c@d.com"})
    with SessionLocal() as db:
        assert tenants_repo.get_by_slug(db, "bar-x") is not None
        assert tenants_repo.get_by_slug(db, "bar-x-2") is not None


def test_registro_rejeita_email_invalido(client):
    res = client.post(
        "/api/v1/registro",
        json={"nome": "Valido", "email": "nao-eh-email", "plano": "free"},
    )
    assert res.status_code == 422
