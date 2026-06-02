#!/usr/bin/env bash
# Atualiza o agente/instancia Odoo de um cliente: pull, upgrade de modulo e restart.
# Uso: update_agent.sh <db>
# Saida simulada para a demo do hackathon.
set -euo pipefail

DB="${1:?uso: update_agent.sh <db>}"

echo "Atualizando agente do cliente: ${DB}"
echo "git pull origin main ... ja atualizado (3 commits)"
echo "odoo-bin -d ${DB} -u isy_printer --stop-after-init ... OK"
echo "systemctl restart odoo ... OK"
echo "health check: HTTP 200 em https://${DB#db_}.isy.one"
echo "Agente atualizado com sucesso."
