#!/usr/bin/env bash
# Limpa/rotaciona logs antigos do Odoo (cupons, /var/log/odoo/odoo.log).
# Uso: cleanup_logs.sh [dias_retencao]   (default 30)
# Saida simulada para a demo do hackathon.
set -euo pipefail

RETENCAO_DIAS="${1:-30}"

echo "Iniciando limpeza de logs com retencao de ${RETENCAO_DIAS} dias..."
echo "Rotacionando /var/log/odoo/odoo.log ..."
echo "Removendo logs de cupons anteriores a ${RETENCAO_DIAS} dias ... 3 arquivos."
echo "Limpeza concluida com sucesso."
