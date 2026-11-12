"""CORS: o Swagger publicado no GitHub Pages precisa chamar a API pelo navegador."""

PAGES = "https://lumiguelx.github.io"


def _preflight(client, origin):
    return client.options(
        "/api/v1/admin/tenants",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Isy-Token",
        },
    )


def test_cors_libera_origem_do_github_pages(client):
    r = _preflight(client, PAGES)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == PAGES
    assert "x-isy-token" in r.headers["access-control-allow-headers"].lower()


def test_cors_bloqueia_origem_desconhecida(client):
    r = _preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in r.headers
