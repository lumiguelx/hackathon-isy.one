#!/usr/bin/env bash
# Backup do banco Postgres do cliente.
# Uso: backup_db.sh [db]   (o cliente vem de ISY_TENANT_SLUG)
# Remoto: com ISY_SSH_HOST setado, roda pg_dump no servidor do cliente via helper.
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
  exec "$DIR/_ssh.sh" "/opt/isyone/bin/backup_db $SLUG"
fi

DB="${1:-db_demo}"
echo "[local]"
echo "Iniciando backup de ${DB}..."
echo "pg_dump ${DB} > /backups/${DB}_$(date +%F).sql ... OK"
echo "tar filestore ~/.local/share/Odoo/filestore/${DB} ... OK"
echo "Backup de ${DB} concluido."
