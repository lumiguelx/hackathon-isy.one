"""Testes da camada de seguranca (criterio de 25% da banca)."""

from tests.conftest import AUTH, make_script


def test_rota_sem_token_retorna_401(client):
    assert client.get("/api/v1/scripts").status_code == 401
    assert client.get("/api/v1/logs").status_code == 401
    assert client.get("/api/v1/admin/scripts").status_code == 401


def test_token_invalido_retorna_401(client):
    resp = client.get("/api/v1/scripts", headers={"X-Isy-Token": "errado"})
    assert resp.status_code == 401


def test_health_e_publico(client):
    assert client.get("/health").status_code == 200


def test_command_injection_param_e_argv_literal(client):
    """Parametros maliciosos entram como argv literais, sem virar comando."""
    script_id = make_script(client)
    payloads = ["; rm -rf /", "&& whoami", "$(id)", "`cat /etc/passwd`"]
    resp = client.post(
        f"/api/v1/scripts/{script_id}/run",
        json={"parametros": payloads},
        headers=AUTH,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "sucesso"
    # Cada payload aparece intacto como UM unico argumento (prefixo ARG:).
    for payload in payloads:
        assert f"ARG:{payload}" in data["stdout"]
    # Nenhum comando extra foi executado: a saida tem exatamente uma linha por payload.
    linhas = [l for l in data["stdout"].splitlines() if l.startswith("ARG:")]
    assert len(linhas) == len(payloads)


def test_path_traversal_no_cadastro_e_rejeitado(client):
    resp = client.post(
        "/api/v1/admin/scripts",
        json={"nome": "evil", "caminho": "../../../etc/passwd"},
        headers=AUTH,
    )
    assert resp.status_code == 422
