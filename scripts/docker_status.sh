#!/usr/bin/env bash
# Checa status dos containers Docker (Postgres + Odoo) do cliente.
# Uso: docker_status.sh [slug]
# Saida simulada para a demo do hackathon (sem docker real).
set -euo pipefail

SLUG="${1:-fmu}"

echo "NAME                     STATUS          PORTS"
echo "isyone-${SLUG}-db        Up (healthy)    5432/tcp"
echo "isyone-${SLUG}-odoo      Up (healthy)    0.0.0.0:8155->8069/tcp"
echo "isyone-proxy             Up (healthy)    0.0.0.0:443->443/tcp"
