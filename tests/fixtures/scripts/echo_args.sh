#!/usr/bin/env bash
# Imprime cada argumento recebido em uma linha, prefixado, para provar que cada
# parametro chega como um argv literal (sem interpretacao de shell).
for arg in "$@"; do
  echo "ARG:${arg}"
done
