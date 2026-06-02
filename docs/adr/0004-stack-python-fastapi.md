# 0004. Stack Python/FastAPI para o desafio Isy.One

- **Data:** 2026-06-01
- **Status:** aceita
- **Relacionada:** substitui [ADR 0003](0003-stack-e-arquitetura.md)

## Contexto

O ADR 0003 cravou um stack TypeScript (Next.js + Fastify) enquanto o tema do hackathon
ainda estava em aberto. Definido o desafio real — **Isy.One Shell Automation API**
(ver [PRD](../specs/2026-06-01-isy-shell-automation-api.md)) — a banca tornou a stack
**mandatória** e incompatível com a escolha anterior:

- API REST em **Python** usando obrigatoriamente a biblioteca nativa `subprocess`.
- Empacotamento em **Docker** com imagem leve (`python:3.11-slim`/`-alpine`) e scripts do
  host lidos via **volume**.
- Persistência em **SQLite ou PostgreSQL**.
- Critérios de avaliação pontuam exatamente esses pontos (Arquitetura/API 25%,
  Segurança/Token 25%, Logs 20%, Deploy/Docker 20%, Pitch 10%).

Não há liberdade de stack: seguir o ADR 0003 reprovaria nos critérios técnicos.

## Decisão

Stack único em **Python 3.11**, serviço único containerizado:

| Peça | Escolha |
|------|---------|
| Framework HTTP | FastAPI + Uvicorn (Swagger automático em `/docs`) |
| Execução de SO | `subprocess.run`, `shell=False`, com `timeout` |
| Acesso a dados | SQLAlchemy (ou `sqlite3`/`asyncpg` se preferir leveza) |
| Banco primário | SQLite na demo; PostgreSQL para ambiente mais real |
| Empacotamento | Docker `python:3.11-slim` (ou `-alpine`) + volume de scripts |
| Auth | Header `X-Isy-Token` (dependency FastAPI, token rotacionável) |

Backend em camadas: `rota → service (regra de negócio) → repository (acesso a dados)
→ banco`. A execução de scripts é isolada num service dedicado que só roda itens de uma
**whitelist** cadastrada, nunca string arbitrária do request.

### Não escolhido (e por quê)

- **Manter TypeScript/Next/Fastify (ADR 0003):** incompatível com a exigência de
  `subprocess` em Python; reprovaria na avaliação.
- **Flask:** viável, mas FastAPI entrega Swagger, validação (Pydantic) e tipagem de graça,
  acelerando a demo.
- **Frontend dedicado (Next.js):** opcional e fora do MVP; o Swagger já cobre a operação e
  a demo. Uma UI de gestão fica como evolução (v2.0 no PRD).
- **Monorepo Turborepo + pnpm:** desnecessário para um serviço único em Python.

## Consequências

- O repo deixa de ser monorepo TS: passa a hospedar um serviço Python. A estrutura
  `apps/`/`packages/` do ADR 0003 não se aplica.
- Ganhamos aderência total aos critérios da banca (subprocess, Docker leve, volumes, token,
  auditoria em banco).
- O risco central passa a ser **command injection**; mitigado por whitelist + `shell=False`
  + validação de path + timeout (detalhado no PRD).
- Deploy: o entregável é um **Dockerfile**; execução sempre via container, nunca no terminal
  do host. Railway segue viável (build por Dockerfile), mas não é requisito do desafio.
- `docs/architecture.md` e `README.md` foram reescritos para refletir esta decisão.
