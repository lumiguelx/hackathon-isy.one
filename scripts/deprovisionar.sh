#!/usr/bin/env bash
# Desprovisiona um cliente: remove os containers e o diretorio do cliente.
# Uso: deprovisionar.sh <slug>
# Remoto: com ISY_SSH_HOST setado, remove no servidor via helper.
# Local:  sem ISY_SSH_HOST, saida simulada para a demo offline.
set -euo pipefail

SLUG="${1:-${ISY_TENANT_SLUG:-}}"
DIR="$(cd "$(dirname "$0")" && pwd)"

printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$' || { echo "slug invalido." >&2; exit 2; }

if [ -n "${ISY_SSH_HOST:-}" ]; then
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}]"
  exec "$DIR/_ssh.sh" "/opt/isyone/bin/deprovisionar $SLUG"
fi

echo "[local]"
echo "Removendo containers do cliente ${SLUG} (simulado)..."
echo "Cliente ${SLUG} desprovisionado."
