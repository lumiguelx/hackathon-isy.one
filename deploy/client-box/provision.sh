#!/usr/bin/env bash
# Roda NO VPS (como root/sudo) para transformar este host no "servidor do cliente".
# Cria o usuario isyone com a chave publica do painel, da acesso ao Docker e sobe
# servicos de exemplo para o docker_status mostrar algo real.
#
# Uso:  sudo bash provision.sh "<conteudo-da-chave-publica>" [slug]
#   ex: sudo bash provision.sh "$(cat isyone_deploy.pub)" cliente1
set -euo pipefail

PUBKEY="${1:?uso: provision.sh '<chave publica>' [slug]}"
SLUG="${2:-cliente1}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker nao encontrado. Instale antes (https://docs.docker.com/engine/install/)." >&2
  exit 1
fi

id isyone >/dev/null 2>&1 || useradd -m -s /bin/bash isyone
install -d -m 700 -o isyone -g isyone /home/isyone/.ssh
printf '%s\n' "$PUBKEY" > /home/isyone/.ssh/authorized_keys
chmod 600 /home/isyone/.ssh/authorized_keys
chown isyone:isyone /home/isyone/.ssh/authorized_keys

# Acesso ao Docker do host (socket) para docker_status / backup reais.
getent group docker >/dev/null || groupadd docker
usermod -aG docker isyone

# Servicos de exemplo (nomeados por cliente) para popular o 'docker ps'.
docker rm -f "isyone-${SLUG}-db" "isyone-${SLUG}-odoo" >/dev/null 2>&1 || true
docker run -d --name "isyone-${SLUG}-db" --restart unless-stopped \
  -e POSTGRES_PASSWORD=demo postgres:16-alpine >/dev/null
docker run -d --name "isyone-${SLUG}-odoo" --restart unless-stopped \
  nginx:alpine >/dev/null

echo "OK. Este host agora e o servidor de '${SLUG}'."
echo "Teste local:  sudo -u isyone docker ps"
echo "No painel, configure o tenant com ssh_host=<IP deste host> e ssh_port=22."
