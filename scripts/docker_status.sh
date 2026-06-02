#!/usr/bin/env bash
# Status dos containers Docker do cliente.
# Remoto: se o painel injetar ISY_SSH_HOST (tenant.ssh_host setado), roda 'docker ps'
#         no servidor do cliente via SSH.
# Local:  sem ISY_SSH_HOST, inspeciona o Docker da propria maquina (modo demo local).
# Uso: docker_status.sh [filtro_nome]
set -euo pipefail

FILTRO="${1:-}"
FORMATO='table {{.Names}}\t{{.Status}}\t{{.Ports}}'
DIR="$(cd "$(dirname "$0")" && pwd)"

# O filtro vira parte de um comando remoto via SSH; restringe a um charset seguro
# (nome de container) para evitar injecao no servidor do cliente.
if [ -n "$FILTRO" ] && ! printf '%s' "$FILTRO" | grep -qE '^[A-Za-z0-9._-]+$'; then
  echo "filtro invalido: use apenas letras, numeros, '.', '_' ou '-'." >&2
  exit 2
fi

if [ -n "${ISY_SSH_HOST:-}" ]; then
  echo "[remoto ${ISY_SSH_USER:-isyone}@${ISY_SSH_HOST}:${ISY_SSH_PORT:-22}]"
  if [ -n "$FILTRO" ]; then
    exec "$DIR/_ssh.sh" "docker ps --filter name=$FILTRO --format '$FORMATO'"
  fi
  exec "$DIR/_ssh.sh" "docker ps --format '$FORMATO'"
fi

echo "[local]"
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "daemon do docker indisponivel nesta maquina." >&2
  exit 1
fi
if [ -n "$FILTRO" ]; then
  docker ps --filter "name=${FILTRO}" --format "$FORMATO"
else
  docker ps --format "$FORMATO"
fi
