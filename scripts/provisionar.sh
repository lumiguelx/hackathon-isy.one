#!/usr/bin/env bash
# Provisiona um novo cliente (estrutura + containers db/odoo/agente).
# Uso: provisionar.sh <slug> <dominio> <porta>
# Remoto: com ISY_SSH_HOST setado, sobe a stack DE VERDADE no servidor via helper.
# Local:  sem ISY_SSH_HOST, saida simulada para a demo offline.
set -euo pipefail

SLUG="${1:?uso: provisionar.sh <slug> <dominio> <porta>}"
DOMINIO="${2:?dominio obrigatorio}"
PORTA="${3:?porta obrigatoria}"
DIR="$(cd "$(dirname "$0")" && pwd)"

# Os valores viram parte de um comando remoto; valida charset (anti command injection).
printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$' || { echo "slug invalido." >&2; exit 2; }
printf '%s' "$DOMINIO" | grep -qE '^[A-Za-z0-9.-]+$' || { echo "dominio invalido." >&2; exit 2; }
printf '%s' "$PORTA" | grep -qE '^[0-9]+$' || { echo "porta invalida." >&2; exit 2; }

if [ -n "${ISY_SSH_HOST:-}" ]; then
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}]"
  exec "$DIR/_ssh.sh" "/opt/isyone/bin/provisionar $SLUG $DOMINIO $PORTA"
fi

echo "[local]"
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
