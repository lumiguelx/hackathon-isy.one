#!/usr/bin/env bash
# Limpa logs de cupons iFood antigos do cliente.
# Uso: cleanup_logs.sh [dias_retencao]   (default 30)
# Remoto: com ISY_SSH_HOST setado, roda no servidor do cliente via helper.
# Local:  sem ISY_SSH_HOST, saida simulada para a demo offline.
set -euo pipefail

RETENCAO_DIAS="${1:-30}"
DIR="$(cd "$(dirname "$0")" && pwd)"

# O valor vira parte de um comando remoto; restringe a numeros para evitar injecao.
if ! printf '%s' "$RETENCAO_DIAS" | grep -qE '^[0-9]+$'; then
  echo "dias de retencao invalido: use apenas numeros." >&2
  exit 2
fi

if [ -n "${ISY_SSH_HOST:-}" ]; then
  SLUG="${ISY_TENANT_SLUG:?ISY_TENANT_SLUG nao definido}"
  if ! printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$'; then
    echo "slug invalido: use apenas letras minusculas, numeros ou '-'." >&2
    exit 2
  fi
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}]"
  exec "$DIR/_ssh.sh" "/opt/isyone/bin/cleanup_logs $SLUG $RETENCAO_DIAS"
fi

echo "[local]"
echo "Iniciando limpeza de logs com retencao de ${RETENCAO_DIAS} dias..."
echo "Rotacionando /var/log/odoo/odoo.log ..."
echo "Removendo logs de cupons anteriores a ${RETENCAO_DIAS} dias ... 3 arquivos."
echo "Limpeza concluida com sucesso."
