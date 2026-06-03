#!/usr/bin/env bash
# Sobe a API em background, espera o /health responder, roda o validador de
# contrato contra ela e propaga o exit code (0 = PASS, 1 = FAIL).
# Uso: scripts/check-contract.sh [--min-score N]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8000}"
BASE_URL="http://127.0.0.1:${PORT}"
API_PID=""

# Usa o python do virtualenv local quando existir; senao cai no python do PATH.
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python}"
fi

cleanup() {
  if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Banco efemero e dados de demo para um spec completo, sem tocar no banco real.
export ISY_SEED_DEMO=true
export ISY_DATABASE_URL="sqlite:///./contract-check.db"

echo "[check-contract] subindo a API em ${BASE_URL} ..."
"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
API_PID=$!

# Espera o /health ficar de pe (ate ~15s).
for _ in $(seq 1 30); do
  if curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "[check-contract] a API morreu ao subir." >&2
    exit 2
  fi
  sleep 0.5
done

if ! curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "[check-contract] timeout esperando ${BASE_URL}/health." >&2
  exit 2
fi

echo "[check-contract] validando contrato ..."
"$PYTHON" -m tools.contract_validator --url "$BASE_URL" "$@"
