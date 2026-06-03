.PHONY: contract test

# Valida a qualidade do contrato OpenAPI: sobe a API, roda o validador, nota + PASS/FAIL.
contract:
	./scripts/check-contract.sh

# Roda a suite de testes.
test:
	pytest
