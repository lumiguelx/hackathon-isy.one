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


def test_script_owned_auto_bind_aparece_no_cliente(client):
    assert _criar_tenant(client, slug="tux-burger", porta=8201).status_code == 201
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "tux-burger"
    )
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "bespoke-tux",
            "tipo": "template",
            "template": "docker ps {{container:db}}",
            "categoria": "status",
            "tenant_id": tid,
        },
    )
    assert r.status_code == 201, r.text
    lst = client.get("/api/v1/tenants/tux-burger/scripts", headers=AUTH).json()["data"]
    assert any(s["nome"] == "bespoke-tux" for s in lst)


def test_script_owned_tenant_inexistente_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "orfao",
            "tipo": "template",
            "template": "echo {{slug}}",
            "categoria": "other",
            "tenant_id": 99999,
        },
    )
    assert r.status_code == 422


def test_update_arquivo_nao_pode_limpar_caminho(client):
    sid = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "arq1", "caminho": "cleanup_logs.sh", "categoria": "cleanup"},
    ).json()["data"]["id"]
    r = client.put(
        f"/api/v1/admin/scripts/{sid}",
        headers=AUTH,
        json={"caminho": ""},
    )
    assert r.status_code == 422


def test_bind_script_owned_em_outro_cliente_403(client):
    _criar_tenant(client, slug="dono", porta=8301)
    _criar_tenant(client, slug="intruso", porta=8302)
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "dono"
    )
    sid = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "so-do-dono",
            "tipo": "template",
            "template": "docker ps {{container:db}}",
            "categoria": "status",
            "tenant_id": tid,
        },
    ).json()["data"]["id"]
    r = client.put(
        "/api/v1/admin/tenants/intruso/scripts",
        headers=AUTH,
        json={"script_id": sid, "parametros_default": "", "ativo": True},
    )
    assert r.status_code == 403


def test_list_global_exclui_scripts_owned(client):
    # Garante que o auto-bind do self-service (que usa list_global) nunca vincula
    # scripts exclusivos de outro cliente a um novo tenant.
    from app.core.db import SessionLocal
    from app.repositories import scripts_repo

    _criar_tenant(client, slug="dono2", porta=8311)
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "dono2"
    )
    client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "global-x", "caminho": "cleanup_logs.sh", "categoria": "cleanup"},
    )
    client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "owned-x",
            "tipo": "template",
            "template": "echo {{slug}}",
            "categoria": "other",
            "tenant_id": tid,
        },
    )
    with SessionLocal() as db:
        nomes = {s.nome for s in scripts_repo.list_global(db)}
    assert "global-x" in nomes
    assert "owned-x" not in nomes
