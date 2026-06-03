#!/usr/bin/env bash
# Gestao de um container Docker do cliente: status / restart / stop / logs.
# Parametros (flags, montados pelo painel a partir do param_schema):
#   --acao status|restart|stop|logs   (obrigatorio)
#   --papel db|odoo|agent             (obrigatorio; resolve o container do cliente)
#   --linhas N                        (opcional; nro de linhas no 'logs', default 100)
# Container alvo: isyone-${ISY_TENANT_SLUG}-${role}.
# Remoto: com ISY_SSH_HOST setado, roda 'docker ...' no servidor do cliente via _ssh.sh.
# Local:  sem ISY_SSH_HOST, saida simulada para a demo offline.
set -euo pipefail

ACAO=""
PAPEL=""
LINHAS="100"
while (( $# >= 1 )); do
  case "$1" in
    --acao)   ACAO="${2:-}"; shift 2 ;;
    --papel)  PAPEL="${2:-}"; shift 2 ;;
    --linhas) LINHAS="${2:-}"; shift 2 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

DIR="$(cd "$(dirname "$0")" && pwd)"
SLUG="${ISY_TENANT_SLUG:?ISY_TENANT_SLUG nao definido}"

# Defesa em profundidade: o painel ja valida (select/int), mas o script tambem.
case "$ACAO" in status|restart|stop|logs) ;; *) echo "acao invalida: '$ACAO'" >&2; exit 2 ;; esac
case "$PAPEL" in
  db)    ROLE="db" ;;
  odoo)  ROLE="odoo" ;;
  agent) ROLE="ifood-agent" ;;
  *) echo "papel invalido: '$PAPEL'" >&2; exit 2 ;;
esac
if ! printf '%s' "$LINHAS" | grep -qE '^[0-9]+$'; then
  echo "linhas invalido: use apenas numeros." >&2; exit 2
fi
if ! printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$'; then
  echo "slug invalido." >&2; exit 2
fi

CONTAINER="isyone-${SLUG}-${ROLE}"
case "$ACAO" in
  status)  CMD="docker ps -a --filter name=${CONTAINER} --format 'table {{.Names}}\t{{.Status}}'" ;;
  restart) CMD="docker restart ${CONTAINER}" ;;
  stop)    CMD="docker stop ${CONTAINER}" ;;
  logs)    CMD="docker logs --tail ${LINHAS} ${CONTAINER}" ;;
esac

if [ -n "${ISY_SSH_HOST:-}" ]; then
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}] ${ACAO} ${CONTAINER}"
  exec "$DIR/_ssh.sh" "$CMD"
fi

echo "[local simulado] ${CMD}"
case "$ACAO" in
  status)  echo "${CONTAINER}    Up 3 hours (healthy)" ;;
  restart) echo "${CONTAINER}"; echo "container reiniciado." ;;
  stop)    echo "${CONTAINER}"; echo "container parado." ;;
  logs)    echo "[ultimas ${LINHAS} linhas de ${CONTAINER}]"; echo "... worker iniciado"; echo "... requisicao 200 OK" ;;
esac
