"""Exporta o contrato OpenAPI para o site estatico do GitHub Pages (docs/openapi.json).

Uso: python -m tools.export_openapi [destino]

Acrescenta a lista de `servers` para o "Try it out" do Swagger publicado:
a API local (make run / docker compose) e o deploy na Railway.
"""

import json
import os
import sys
from pathlib import Path

# Import da app sem efeitos colaterais: nada de agendador nem banco real.
os.environ.setdefault("ISY_SCHEDULER_ENABLED", "false")
os.environ.setdefault("ISY_DATABASE_URL", "sqlite://")

from app.main import app  # noqa: E402

SERVERS = [
    {"url": "http://localhost:8000", "description": "Local (docker compose up / uvicorn)"},
    {"url": "https://hackathon-api-production-5f01.up.railway.app", "description": "Railway (demo)"},
]


def main() -> None:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/openapi.json")
    spec = app.openapi()
    spec["servers"] = SERVERS
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI exportado: {dest} ({len(spec['paths'])} rotas)")


if __name__ == "__main__":
    main()
