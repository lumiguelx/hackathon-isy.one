#!/usr/bin/env bash
# Imprime o contexto SSH recebido via ambiente, para verificar a injecao do painel.
echo "HOST:${ISY_SSH_HOST:-}"
echo "PORT:${ISY_SSH_PORT:-}"
echo "USER:${ISY_SSH_USER:-}"
