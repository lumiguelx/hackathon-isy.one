"""Testa execucao com valores nomeados (param_schema) pela rota de run."""

from tests.conftest import AUTH

TOK1 = {"X-Isy-Token": "tok-cliente-1-aaaaaa"}


def _tenant(client):
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


def _script(client, nome, caminho, param_schema):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": nome, "caminho": caminho, "categoria": "status",
              "param_schema": param_schema},
    )
    assert r.status_code == 201, r.text
    sid = r.json()["data"]["id"]
    client.put(
        "/api/v1/admin/tenants/cliente-1/scripts",
        headers=AUTH,
        json={"script_id": sid, "ativo": True},
    )
    return sid


def test_run_monta_argv_e_audita(client):
    _tenant(client)
    sid = _script(client, "echo", "echo_args.sh", [
        {"nome": "acao", "tipo": "select", "arg": "--acao", "choices": ["restart"]},
        {"nome": "alvo", "tipo": "text"},
    ])
    r = client.post(
        f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
        headers=TOK1,
        json={"valores": {"acao": "restart", "alvo": "odoo"}},
    )
    assert r.status_code == 200, r.text
    out = r.json()["data"]["stdout"]
    assert "ARG:--acao" in out and "ARG:restart" in out and "ARG:odoo" in out
    # auditoria registra o comando montado
    log = client.get("/api/v1/tenants/cliente-1/logs", headers=TOK1).json()["data"][0]
    assert log["parametros"] == "--acao restart odoo"


def test_run_valor_invalido_422(client):
    _tenant(client)
    sid = _script(client, "echo2", "echo_args.sh", [
        {"nome": "alvo", "tipo": "text", "arg": "-a"},
    ])
    r = client.post(
        f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
        headers=TOK1,
        json={"valores": {"alvo": "a; rm -rf /"}},
    )
    assert r.status_code == 422


def test_run_secret_mascarado_na_auditoria(client):
    _tenant(client)
    sid = _script(client, "echo3", "echo_args.sh", [
        {"nome": "senha", "tipo": "text", "arg": "-p", "secret": True},
    ])
    client.post(
        f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
        headers=TOK1,
        json={"valores": {"senha": "segredo123"}},
    )
    log = client.get("/api/v1/tenants/cliente-1/logs", headers=TOK1).json()["data"][0]
    assert "segredo123" not in log["parametros"] and "***" in log["parametros"]


def test_docker_ctl_local_simulado(client):
    _tenant(client)
    sid = _script(client, "dctl", "docker_ctl.sh", [
        {"nome": "acao", "tipo": "select", "arg": "--acao", "choices": ["status"]},
        {"nome": "papel", "tipo": "select", "arg": "--papel", "choices": ["odoo"]},
    ])
    r = client.post(
        f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
        headers=TOK1,
        json={"valores": {"acao": "status", "papel": "odoo"}},
    )
    assert r.status_code == 200, r.text
    out = r.json()["data"]["stdout"]
    assert "isyone-cliente-1-odoo" in out and "simulado" in out


def test_run_posicional_ainda_funciona(client):
    """Compat: script sem param_schema continua recebendo parametros posicionais."""
    _tenant(client)
    sid = _script(client, "echo_pos", "echo_args.sh", [])
    r = client.post(
        f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
        headers=TOK1,
        json={"parametros": ["um", "dois"]},
    )
    assert r.status_code == 200
    out = r.json()["data"]["stdout"]
    assert "ARG:um" in out and "ARG:dois" in out
