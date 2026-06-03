"""Validador de qualidade do contrato OpenAPI da API IsyShell.

CLI que busca o /openapi.json da app, roda checks nomeados, calcula uma nota
0-100 e sai com PASS/FAIL. Uso:

    python -m tools.contract_validator --url http://localhost:8000
"""
