"""Testa as rotas de agendamento (CRUD por cliente + overview admin)."""

from tests.conftest import AUTH

TOK1 = {"X-Isy-Token": "tok-cliente-1-aaaaaa"}


def _setup(client):
    client.post(
        "/api/v1/admin/tenants",
        headers=AUTH,
        json={
            "slug": "cliente-1",
            "nome": "Cliente 1",
            "dominio": "cliente1.isy.one",
            "porta": 8151,
            "db_name": "db_cliente1",
            "token": "tok-cliente-1-aaaaaa",
        },
    )
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "echo", "caminho": "echo_args.sh", "categoria": "other"},
    )
    sid = r.json()["data"]["id"]
    client.put(
        "/api/v1/admin/tenants/cliente-1/scripts",
        headers=AUTH,
        json={"script_id": sid, "parametros_default": "padrao", "ativo": True},
    )
    return sid


def test_cria_lista_atualiza_remove(client):
    sid = _setup(client)
    # cria
    rc = client.post(
        "/api/v1/tenants/cliente-1/schedules",
        headers=TOK1,
        json={"script_id": sid, "cron_expr": "0 3 * * *", "parametros": "x"},
    )
    assert rc.status_code == 201
    schedule_id = rc.json()["data"]["id"]
    # lista (token do cliente)
    rl = client.get("/api/v1/tenants/cliente-1/schedules", headers=TOK1)
    assert rl.status_code == 200 and len(rl.json()["data"]) == 1
    # atualiza (desativa)
    ru = client.put(
        f"/api/v1/tenants/cliente-1/schedules/{schedule_id}",
        headers=TOK1,
        json={"ativo": False},
    )
    assert ru.status_code == 200 and ru.json()["data"]["ativo"] is False
    # remove
    rd = client.delete(
        f"/api/v1/tenants/cliente-1/schedules/{schedule_id}", headers=TOK1
    )
    assert rd.status_code == 200
    assert client.get("/api/v1/tenants/cliente-1/schedules", headers=TOK1).json()["data"] == []


def test_rejeita_script_nao_liberado(client):
    _setup(client)
    # script_id inexistente / nao vinculado
    r = client.post(
        "/api/v1/tenants/cliente-1/schedules",
        headers=TOK1,
        json={"script_id": 999, "cron_expr": "* * * * *"},
    )
    assert r.status_code == 404


def test_rejeita_cron_invalido(client):
    sid = _setup(client)
    r = client.post(
        "/api/v1/tenants/cliente-1/schedules",
        headers=TOK1,
        json={"script_id": sid, "cron_expr": "nao-eh-cron"},
    )
    assert r.status_code == 422


def test_isolamento_entre_clientes(client):
    sid = _setup(client)
    # segundo cliente
    client.post(
        "/api/v1/admin/tenants",
        headers=AUTH,
        json={
            "slug": "cliente-2",
            "nome": "Cliente 2",
            "dominio": "cliente2.isy.one",
            "porta": 8152,
            "db_name": "db_cliente2",
            "token": "tok-cliente-2-bbbbbb",
        },
    )
    rc = client.post(
        "/api/v1/tenants/cliente-1/schedules",
        headers=TOK1,
        json={"script_id": sid, "cron_expr": "* * * * *"},
    )
    schedule_id = rc.json()["data"]["id"]
    # cliente-2 nao enxerga nem mexe no agendamento do cliente-1
    tok2 = {"X-Isy-Token": "tok-cliente-2-bbbbbb"}
    assert client.delete(
        f"/api/v1/tenants/cliente-2/schedules/{schedule_id}", headers=tok2
    ).status_code == 404
    assert client.put(
        f"/api/v1/tenants/cliente-2/schedules/{schedule_id}",
        headers=tok2,
        json={"ativo": False},
    ).status_code == 404


def test_overview_admin_enriquece_nomes(client):
    sid = _setup(client)
    client.post(
        "/api/v1/tenants/cliente-1/schedules",
        headers=TOK1,
        json={"script_id": sid, "cron_expr": "* * * * *"},
    )
    r = client.get("/api/v1/admin/schedules", headers=AUTH)
    assert r.status_code == 200
    item = r.json()["data"][0]
    assert item["tenant_slug"] == "cliente-1"
    assert item["tenant_nome"] == "Cliente 1"
    assert item["script_nome"] == "echo"
