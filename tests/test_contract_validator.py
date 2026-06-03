"""Testes do validador de contrato (offline, sem subir servidor)."""

from tools.contract_validator import checks, scoring


def _spec(**overrides) -> dict:
    """Spec OpenAPI minimo e saudavel; overrides ajustam partes para cada caso."""
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "API", "version": "1.2.0"},
        "components": {"securitySchemes": {"ApiKey": {"type": "apiKey", "name": "X-Token", "in": "header"}}},
        "security": [{"ApiKey": []}],
        "paths": {
            "/items": {
                "get": {
                    "summary": "Listar",
                    "description": "Lista itens.",
                    "responses": {"200": {"description": "ok"}, "401": {"description": "no"}},
                }
            }
        },
    }
    spec.update(overrides)
    return spec


def test_spec_saudavel_passa_com_nota_alta():
    spec = _spec()
    results = checks.run_all(spec)
    score = scoring.total_score(results)
    assert score == 100
    assert scoring.passed(results, score, min_score=80)


def test_routes_conta_documentadas():
    spec = _spec()
    spec["paths"]["/raw"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    r = next(c for c in checks.run_all(spec) if c.label == "routes")
    assert r.status == checks.WARN
    assert "1/2" in r.message


def test_auth_falha_sem_security_scheme():
    spec = _spec()
    spec["components"]["securitySchemes"] = {}
    r = checks.check_auth(spec)
    assert r.status == checks.FAIL
    assert r.score == 0.0


def test_auth_warn_quando_scheme_nao_referenciado():
    spec = _spec()
    spec.pop("security")
    r = checks.check_auth(spec)
    assert r.status == checks.WARN


def test_semver_invalido_reprova():
    r_ok = checks.check_semver(_spec(info={"title": "A", "version": "v2.0.1"}))
    assert r_ok.status == checks.PASS
    r_bad = checks.check_semver(_spec(info={"title": "A", "version": "1.0"}))
    assert r_bad.status == checks.FAIL
    r_empty = checks.check_semver(_spec(info={"title": "A"}))
    assert r_empty.status == checks.FAIL


def test_descriptions_warn_sem_zerar():
    spec = _spec()
    spec["paths"]["/x"] = {"get": {"summary": "X", "responses": {"200": {"description": "ok"}}}}
    r = checks.check_descriptions(spec)
    assert r.status == checks.WARN
    assert "1 rota" in r.message
    assert r.score > 0


def test_responses_penaliza_operacao_sem_2xx():
    spec = _spec()
    spec["paths"]["/items"]["get"]["responses"] = {"404": {"description": "no"}}
    r = checks.check_responses(spec)
    assert r.status == checks.FAIL


def test_responses_warn_sem_codigo_de_erro():
    spec = _spec()
    spec["paths"]["/items"]["get"]["responses"] = {"200": {"description": "ok"}}
    r = checks.check_responses(spec)
    assert r.status == checks.WARN


def test_deprecations_lista_rotas_depreciadas():
    spec = _spec()
    spec["paths"]["/old"] = {
        "get": {"summary": "old", "deprecated": True, "responses": {"200": {"description": "ok"}}}
    }
    r = checks.check_deprecations(spec)
    assert r.status == checks.WARN
    assert "GET /old" in r.message


def test_gate_reprova_check_critico_mesmo_com_nota_alta():
    # auth e critico: FAIL nele reprova o gate ainda que a nota passe do minimo.
    spec = _spec()
    spec["components"]["securitySchemes"] = {}
    results = checks.run_all(spec)
    score = scoring.total_score(results)
    assert score >= 80
    assert not scoring.passed(results, score, min_score=80)
