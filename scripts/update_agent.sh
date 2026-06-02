#!/usr/bin/env bash
# Atualiza/reinicia o agente de impressao iFood do cliente.
# Uso: update_agent.sh [db]   (o cliente vem de ISY_TENANT_SLUG)
# Remoto: com ISY_SSH_HOST setado, reinicia o container do agente no servidor.
# Local:  sem ISY_SSH_HOST, saida simulada para a demo offline.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -n "${ISY_SSH_HOST:-}" ]; then
  SLUG="${ISY_TENANT_SLUG:?ISY_TENANT_SLUG nao definido}"
  if ! printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$'; then
    echo "slug invalido: use apenas letras minusculas, numeros ou '-'." >&2
    exit 2
  fi
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}]"
  exec "$DIR/_ssh.sh" "/opt/isyone/bin/update_agent $SLUG"
fi

DB="${1:-db_demo}"
echo "[local]"
echo "Atualizando agente do cliente: ${DB}"
echo "git pull origin main ... ja atualizado (3 commits)"
echo "odoo-bin -d ${DB} -u isy_printer --stop-after-init ... OK"
echo "systemctl restart odoo ... OK"
echo "health check: HTTP 200 em https://${DB#db_}.isy.one"
echo "Agente atualizado com sucesso."
