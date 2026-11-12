.PHONY: contract test pages

# Valida a qualidade do contrato OpenAPI: sobe a API, roda o validador, nota + PASS/FAIL.
contract:
	./scripts/check-contract.sh

# Roda a suite de testes.
test:
	pytest

# Regenera o contrato OpenAPI usado pelo Swagger do GitHub Pages (docs/).
pages:
	python -m tools.export_openapi docs/openapi.json
