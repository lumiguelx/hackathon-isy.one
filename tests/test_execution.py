"""Testes de execucao, whitelist e auditoria."""

from tests.conftest import AUTH, make_script


def test_lista_so_scripts_ativos(client):
    make_script(client, nome="ativo", caminho="echo_args.sh", ativo=True)
    make_script(client, nome="inativo", caminho="echo_args.sh", ativo=False)
    resp = client.get("/api/v1/scripts", headers=AUTH)
    nomes = [s["nome"] for s in resp.json()["data"]]
    assert nomes == ["ativo"]


def test_executar_script_inexistente_404(client):
    resp = client.post("/api/v1/scripts/999/run", json={"parametros": []}, headers=AUTH)
    assert resp.status_code == 404


def test_executar_script_inativo_409(client):
    script_id = make_script(client, nome="off", ativo=False)
    resp = client.post(f"/api/v1/scripts/{script_id}/run", json={"parametros": []}, headers=AUTH)
    assert resp.status_code == 409


def test_falha_de_script_e_registrada_sem_quebrar_api(client):
    script_id = make_script(client, nome="falho", caminho="fail.sh")
    resp = client.post(f"/api/v1/scripts/{script_id}/run", json={"parametros": []}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "falha"
    assert data["exit_code"] == 3


def test_execucao_gera_auditoria(client):
    script_id = make_script(client, nome="aud", caminho="echo_args.sh")
    client.post(f"/api/v1/scripts/{script_id}/run", json={"parametros": ["x"]}, headers=AUTH)
    client.post(f"/api/v1/scripts/{script_id}/run", json={"parametros": ["y"]}, headers=AUTH)
    logs = client.get("/api/v1/logs", headers=AUTH).json()["data"]
    assert len(logs) == 2
    assert {l["script_nome"] for l in logs} == {"aud"}
    assert {l["status"] for l in logs} == {"sucesso"}


def test_rotacao_de_token_invalida_token_antigo(client):
    novo = "novo-token-abcdef"
    resp = client.put("/api/v1/admin/token", json={"token": novo}, headers=AUTH)
    assert resp.status_code == 200
    # Token antigo deixa de valer.
    assert client.get("/api/v1/scripts", headers=AUTH).status_code == 401
    # Novo token funciona.
    assert client.get("/api/v1/scripts", headers={"X-Isy-Token": novo}).status_code == 200
