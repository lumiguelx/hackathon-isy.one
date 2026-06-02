#!/usr/bin/env bash
# Provisiona um novo cliente Odoo (estrutura, templates, Nginx/SSL, containers).
# Uso: provisionar.sh <slug> <dominio> <porta>
# Saida simulada para a demo do hackathon (nao toca em infra real).
set -euo pipefail

SLUG="${1:?uso: provisionar.sh <slug> <dominio> <porta>}"
DOMINIO="${2:?dominio obrigatorio}"
PORTA="${3:?porta obrigatoria}"

echo "--- [1/6] Criando estrutura e isolamento para: ${SLUG}"
echo "--- [2/6] Aplicando Templates (Compose e Odoo Config)"
echo "--- [3/6] Configurando Nginx e SSL"
echo "--- [4/6] Gerando Configuracao Nginx Final (HTTPS + Websocket)"
echo "--- [5/6] Iniciando Containers na porta ${PORTA} (10s...)"
sleep 2
echo "--- [6/6] Finalizando e Recarregando Containers (DB, App, Proxy)"
echo "========================================"
echo "CLIENTE ${SLUG} PROVISIONADO COM SUCESSO"
echo "URL: https://${DOMINIO}"
echo "DB: db_${SLUG}"
