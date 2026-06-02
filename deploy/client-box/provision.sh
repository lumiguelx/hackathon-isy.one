#!/usr/bin/env bash
# Roda NO VPS (como root/sudo) para transformar este host no "servidor do cliente".
# Instala Docker (se ausente), cria o usuario isyone com a chave publica do painel,
# da acesso ao Docker, instala helpers de manutencao em /opt/isyone/bin e sobe um
# cenario realista (containers + logs de cupons iFood antigos) para a demo.
#
# Uso:  sudo bash provision.sh "<conteudo-da-chave-publica>" [slug]
#   ex: sudo bash provision.sh "$(cat isyone_deploy.pub)" tux-burger
set -euo pipefail

PUBKEY="${1:?uso: provision.sh '<chave publica>' [slug]}"
SLUG="${2:-tux-burger}"
DB_NAME="db_$(printf '%s' "$SLUG" | tr '-' '_')"
CLIENTE_DIR="/opt/isyone/clientes/${SLUG}"
CUPONS_DIR="${CLIENTE_DIR}/logs/cupons"
BACKUP_DIR="${CLIENTE_DIR}/backups"

echo "=== [1/6] Docker ==="
if ! command -v docker >/dev/null 2>&1; then
  echo "Instalando Docker..."
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true

echo "=== [2/6] Usuario isyone + chave ==="
id isyone >/dev/null 2>&1 || useradd -m -s /bin/bash isyone
install -d -m 700 -o isyone -g isyone /home/isyone/.ssh
printf '%s\n' "$PUBKEY" > /home/isyone/.ssh/authorized_keys
chmod 600 /home/isyone/.ssh/authorized_keys
chown isyone:isyone /home/isyone/.ssh/authorized_keys
getent group docker >/dev/null || groupadd docker
usermod -aG docker isyone

echo "=== [3/6] Helpers de manutencao em /opt/isyone/bin ==="
install -d -m 755 /opt/isyone/bin

cat > /opt/isyone/bin/cleanup_logs <<'EOF'
#!/usr/bin/env bash
# Apaga logs de cupons iFood mais antigos que N dias e reporta o efeito real.
set -euo pipefail
SLUG="${1:?uso: cleanup_logs <slug> [dias]}"
DIAS="${2:-30}"
BASE="/opt/isyone/clientes/${SLUG}/logs/cupons"
[ -d "$BASE" ] || { echo "sem diretorio de logs para ${SLUG}"; exit 0; }
human() { numfmt --to=iec --suffix=B "${1:-0}" 2>/dev/null || echo "${1:-0}B"; }
antes_n=$(find "$BASE" -type f -name '*.log' | wc -l)
remov=$(find "$BASE" -type f -name '*.log' -mtime +"$DIAS" -print | wc -l)
liber=$(find "$BASE" -type f -name '*.log' -mtime +"$DIAS" -printf '%s\n' | awk '{s+=$1} END{print s+0}')
find "$BASE" -type f -name '*.log' -mtime +"$DIAS" -delete
depois_n=$(find "$BASE" -type f -name '*.log' | wc -l)
echo "Limpeza de cupons iFood — cliente: ${SLUG} (retencao ${DIAS} dias)"
echo "Cupons antes: ${antes_n} | removidos: ${remov} | restantes: ${depois_n}"
echo "Espaco liberado: $(human "$liber")"
echo "Limpeza concluida com sucesso."
EOF

cat > /opt/isyone/bin/update_agent <<'EOF'
#!/usr/bin/env bash
# Reinicia o container do agente de impressao iFood do cliente.
set -euo pipefail
SLUG="${1:?uso: update_agent <slug>}"
CONT="isyone-${SLUG}-ifood-agent"
echo "Atualizando agente de impressao iFood — cliente: ${SLUG}"
docker restart "$CONT" >/dev/null
sleep 1
echo "docker restart ${CONT} ... OK"
echo "status: $(docker ps --filter "name=${CONT}" --format '{{.Names}} {{.Status}}')"
echo "Agente atualizado com sucesso."
EOF

cat > /opt/isyone/bin/backup_db <<'EOF'
#!/usr/bin/env bash
# pg_dump do banco do cliente para um arquivo .sql.gz e reporta tamanho real.
set -euo pipefail
SLUG="${1:?uso: backup_db <slug>}"
CONT="isyone-${SLUG}-db"
DB="db_$(printf '%s' "$SLUG" | tr '-' '_')"
DEST="/opt/isyone/clientes/${SLUG}/backups"
mkdir -p "$DEST"
OUT="${DEST}/${DB}_$(date +%Y%m%d-%H%M%S).sql.gz"
echo "Iniciando backup de ${DB} (container ${CONT})..."
docker exec "$CONT" pg_dump -U postgres "$DB" | gzip > "$OUT"
echo "pg_dump ${DB} -> ${OUT}"
echo "Tamanho: $(du -h "$OUT" | cut -f1)"
echo "Backup concluido com sucesso."
EOF

chmod 755 /opt/isyone/bin/cleanup_logs /opt/isyone/bin/update_agent /opt/isyone/bin/backup_db

echo "=== [4/6] Diretorios do cliente (${SLUG}) ==="
install -d -m 755 -o isyone -g isyone "$CUPONS_DIR" "$BACKUP_DIR"

echo "=== [5/6] Semeando logs de cupons iFood antigos ==="
# ~12.000 cupons antigos (mtime 45 dias) que o cleanup vai remover, e ~300 recentes
# que devem permanecer. Cada arquivo carrega algumas linhas para ter volume real.
seed_cupons() {
  local quantos="$1" idade="$2" prefixo="$3"
  for i in $(seq 1 "$quantos"); do
    local f
    f="$(printf '%s/cupom-ifood-%s-%05d.log' "$CUPONS_DIR" "$prefixo" "$i")"
    {
      echo "pedido=IFOOD-${prefixo}-${i} status=concluido"
      for _ in $(seq 1 40); do echo "item=produto valor=R\$ ${RANDOM}.00 imposto=ok"; done
    } > "$f"
    touch -d "${idade}" "$f"
  done
}
seed_cupons 12000 "45 days ago" "old"
seed_cupons 300 "2 days ago" "new"
chown -R isyone:isyone "$CLIENTE_DIR"
echo "cupons antigos: $(find "$CUPONS_DIR" -name 'cupom-ifood-old-*' | wc -l) | recentes: $(find "$CUPONS_DIR" -name 'cupom-ifood-new-*' | wc -l)"
echo "volume total: $(du -sh "$CUPONS_DIR" | cut -f1)"

echo "=== [6/6] Containers de exemplo (${SLUG}) ==="
docker rm -f "isyone-${SLUG}-db" "isyone-${SLUG}-odoo" "isyone-${SLUG}-ifood-agent" >/dev/null 2>&1 || true
docker run -d --name "isyone-${SLUG}-db" --restart unless-stopped \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_DB="$DB_NAME" postgres:16-alpine >/dev/null
docker run -d --name "isyone-${SLUG}-odoo" --restart unless-stopped \
  nginx:alpine >/dev/null
# Agente de impressao: sobe e e parado de proposito para simular "agente caiu"
# (docker_status mostra Exited -> dashboard VERMELHO; update_agent corrige).
docker run -d --name "isyone-${SLUG}-ifood-agent" --restart no \
  alpine sh -c 'while true; do echo "imprimindo cupom"; sleep 5; done' >/dev/null
docker stop "isyone-${SLUG}-ifood-agent" >/dev/null

echo
echo "OK. Este host agora e o servidor de '${SLUG}'."
echo "Teste local:  sudo -u isyone docker ps -a --filter name=isyone-${SLUG}"
echo "No painel, configure o tenant com ssh_host=<IP deste host> e ssh_port=22."
