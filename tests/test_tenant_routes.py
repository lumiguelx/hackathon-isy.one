from tests.conftest import AUTH


def _setup(client):
    client.post("/api/v1/admin/tenants", headers=AUTH, json={
        "slug": "cliente-1", "nome": "Cliente 1", "dominio": "cliente1.isy.one",
        "porta": 8151, "db_name": "db_cliente1", "token": "tok-cliente-1-aaaaaa"})
    r = client.post("/api/v1/admin/scripts", headers=AUTH, json={
        "nome": "echo", "caminho": "echo_args.sh", "categoria": "other"})
    sid = r.json()["data"]["id"]
    client.put("/api/v1/admin/tenants/cliente-1/scripts", headers=AUTH, json={
        "script_id": sid, "parametros_default": "padrao", "ativo": True})
    return sid


def test_executa_usando_default_e_audita(client):
    sid = _setup(client)
    tok = {"X-Isy-Token": "tok-cliente-1-aaaaaa"}
    # lista disponiveis com token do cliente
    rl = client.get("/api/v1/tenants/cliente-1/scripts", headers=tok)
    assert rl.status_code == 200 and len(rl.json()["data"]) == 1
    # executa sem passar params -> usa default "padrao"
    rr = client.post(f"/api/v1/tenants/cliente-1/scripts/{sid}/run", headers=tok, json={"parametros": []})
    assert rr.status_code == 200
    assert "ARG:padrao" in rr.json()["data"]["stdout"]
    # auditoria registra
    rlog = client.get("/api/v1/tenants/cliente-1/logs", headers=tok)
    assert len(rlog.json()["data"]) == 1


def test_token_de_outro_cliente_nao_executa(client):
    sid = _setup(client)
    rr = client.post(f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
                     headers={"X-Isy-Token": "tok-errado"}, json={"parametros": []})
    assert rr.status_code == 401
