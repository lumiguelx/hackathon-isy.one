#!/usr/bin/env bash
# Backup do banco + filestore de um cliente Odoo (saida simulada para a demo).
# Uso: backup_db.sh <db>
set -euo pipefail

DB="${1:?uso: backup_db.sh <db>}"

echo "Iniciando backup de ${DB}..."
echo "pg_dump ${DB} > /backups/${DB}_$(date +%F).sql ... OK"
echo "tar filestore ~/.local/share/Odoo/filestore/${DB} ... OK"
echo "Backup de ${DB} concluido."
