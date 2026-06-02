#!/usr/bin/env bash
# Executa um comando no servidor do cliente via SSH.
# Endpoint vem do tenant (injetado pelo painel via env): ISY_SSH_HOST / ISY_SSH_PORT /
# ISY_SSH_USER. A chave privada vem do secret ISY_SSH_KEY. Uso: _ssh.sh <comando...>
# SEGURANCA: o comando roda num shell remoto; quem chama deve validar qualquer
# parametro interpolado (ver docker_status.sh) para evitar injecao no host do cliente.
set -euo pipefail

: "${ISY_SSH_HOST:?ISY_SSH_HOST nao definido (tenant sem ssh_host)}"
: "${ISY_SSH_KEY:?ISY_SSH_KEY nao definido (configure o secret no Railway)}"
PORTA="${ISY_SSH_PORT:-22}"
USUARIO="${ISY_SSH_USER:-isyone}"

KEYFILE="$(mktemp)"
trap 'rm -f "$KEYFILE"' EXIT
printf '%s\n' "$ISY_SSH_KEY" > "$KEYFILE"
chmod 600 "$KEYFILE"

ssh -i "$KEYFILE" -p "$PORTA" \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile=/tmp/isy_known_hosts \
  -o ConnectTimeout=10 \
  "${USUARIO}@${ISY_SSH_HOST}" "$@"
