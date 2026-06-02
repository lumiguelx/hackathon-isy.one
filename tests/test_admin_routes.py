from tests.conftest import AUTH


def _criar_tenant(client, slug="cliente-1", porta=8151):
    return client.post(
        "/api/v1/admin/tenants",
        headers=AUTH,
        json={
            "slug": slug,
            "nome": slug,
            "dominio": f"{slug}.isy.one",
            "porta": porta,
            "db_name": f"db_{slug}",
            "token": f"tok-{slug}-aaaaaa",
        },
    )


def test_crud_tenant_e_binding(client):
    assert _criar_tenant(client).status_code == 201
    # duplicado -> 409
    assert _criar_tenant(client).status_code == 409
    # cria script no catalogo
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "cleanup", "caminho": "cleanup_logs.sh", "categoria": "cleanup"},
    )
    sid = r.json()["data"]["id"]
    # binda no tenant
    rb = client.put(
        "/api/v1/admin/tenants/cliente-1/scripts",
        headers=AUTH,
        json={"script_id": sid, "parametros_default": "7", "ativo": True},
    )
    assert rb.status_code == 200
    # dashboard responde
    rd = client.get("/api/v1/admin/tenants/health", headers=AUTH)
    assert rd.status_code == 200
    assert len(rd.json()["data"]) == 1


def test_admin_exige_token(client):
    assert client.get("/api/v1/admin/tenants").status_code == 401


def test_criar_script_template(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "reinicia-agente",
            "tipo": "template",
            "template": "docker restart {{container:agent}}",
            "categoria": "update",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["tipo"] == "template"


def test_criar_script_template_sem_corpo_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "x", "tipo": "template", "categoria": "update"},
    )
    assert r.status_code == 422


def test_criar_script_arquivo_sem_caminho_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "y", "tipo": "arquivo", "categoria": "other"},
    )
    assert r.status_code == 422
