# hackathon-isy.one

Repositório do time para o hackathon. Organizado por **spec-driven design**:
nada de código sem uma spec aprovada antes.

## Status

Tema definido: **Isy.One Shell Automation API** — API REST que executa, de forma
controlada e auditada, os shell scripts de manutenção dos servidores dos restaurantes
parceiros (Agente de Impressão do iFood), eliminando o acesso manual via SSH.

Stack **mandatória pela banca**: **Python 3.11 + FastAPI**, execução via `subprocess`,
auth por header **`X-Isy-Token`**, persistência **SQLite/PostgreSQL**, empacotamento em
**Docker** (`python:3.11-slim`/`-alpine`) com scripts lidos por **volume**.

- Escopo completo (PRD): [docs/specs/2026-06-01-isy-shell-automation-api.md](docs/specs/2026-06-01-isy-shell-automation-api.md)
- Arquitetura e diagramas: [docs/architecture.md](docs/architecture.md)
- Decisão de stack: [ADR 0004](docs/adr/0004-stack-python-fastapi.md) (substitui o [0003](docs/adr/0003-stack-e-arquitetura.md))

## Critérios de avaliação (banca)

| Critério | Peso |
|----------|------|
| Arquitetura & API (`subprocess`, JSON padronizado, rotas admin) | 25% |
| Segurança (validação do `X-Isy-Token`, anti command injection) | 25% |
| Persistência de logs (auditoria em SQLite/PostgreSQL) | 20% |
| Deploy & Docker (imagem leve, volumes) | 20% |
| Pitch & inovação (diferenciais, ex.: alertas Telegram/Discord) | 10% |

## Estrutura

```
.
├── app/         # serviço FastAPI (routes / services / repositories / core)
├── scripts/     # exemplos de .sh (no deploy vêm via volume do host)
├── Dockerfile   # imagem leve python:3.11-slim/alpine
└── docs/
    ├── architecture.md
    ├── specs/   # PRD e specs por feature (problema → critério de sucesso)
    └── adr/     # decisões de arquitetura registradas
```

## Como rodar (demo)

```bash
# Local (use Python 3.11 — a stack do Docker)
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ISY_SEED_DEMO=true uvicorn app.main:app --reload

# ou via Docker (ja sobe com seed e volume de scripts)
docker compose up --build
```

- Swagger: http://127.0.0.1:8000/docs
- UI de demonstracao: http://127.0.0.1:8000/ui
- Token inicial: `544c5787-613a-4ac2-8e61-9e6486f8d74a` (rotacionavel via `PUT /api/v1/admin/token`)
- `ISY_SEED_DEMO=true` pre-cadastra os scripts de exemplo (`provisionar`, `update_agent`, `cleanup_logs`, `docker_status`).
- Testes: `pytest` (cobrem token/401, anti command injection, whitelist e auditoria).

## Fluxo de trabalho

1. **Spec primeiro** — copie `docs/specs/TEMPLATE.md` para `docs/specs/AAAA-MM-DD-<nome>.md` e preencha.
2. **Decisão técnica** — toda escolha de arquitetura relevante vira um ADR em `docs/adr/`.
3. **Plano** — quebre a spec em tarefas pequenas e fechadas.
4. **Implementação** — uma branch por feature, PR pequeno, revisão rápida.

## Time

| Nome | GitHub | Função |
|------|--------|--------|
| Miguel | @lumiguelx | — |
