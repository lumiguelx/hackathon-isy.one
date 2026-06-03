"""Documentacao de API: Scalar branded em /docs, Swagger movido para /swagger."""


def test_docs_serve_scalar_branded(client):
    """/docs devolve a pagina Scalar com a identidade ISYOPS."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    body = resp.text
    # Marcador do Scalar e referencia de marca presentes.
    assert 'id="api-reference"' in body
    assert "/ui/brand/c_dark.svg" in body
    # Aponta para o spec da propria origem.
    assert 'data-url="/openapi.json"' in body


def test_swagger_movido_para_swagger(client):
    """O Swagger UI continua acessivel, agora em /swagger."""
    assert client.get("/swagger").status_code == 200


def test_openapi_intacto(client):
    """O spec OpenAPI segue disponivel para o Scalar consumir."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Isy.One Shell Automation API"


def test_redoc_desligado(client):
    """O ReDoc padrao foi desligado."""
    assert client.get("/redoc").status_code == 404
