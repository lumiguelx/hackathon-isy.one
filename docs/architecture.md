# Arquitetura

Material de referência do projeto — útil também para a apresentação.
Stack e justificativas em [ADR 0004](adr/0004-stack-python-fastapi.md).
Escopo completo no [PRD](specs/2026-06-01-isy-shell-automation-api.md).

## Visão geral

Serviço único em **Python (FastAPI)** que executa, de forma controlada e auditada, os
shell scripts de manutenção dos servidores Isy.One — substituindo o acesso manual via SSH.
Tudo roda dentro de um container Docker; os scripts vivem no host e são lidos via volume.

```
Operador / curl / Swagger
   │  HTTP + header X-Isy-Token
   ▼
[api]  FastAPI  ──▶  rota → service → repository
   │        │
   │        └─▶ subprocess.run([script, *params], shell=False, timeout)
   │                          │  lê .sh via volume
   │                          ▼
   │                    [/opt/isyone/scripts]  (volume Docker, host)
   ▼
[banco]  SQLite (demo) / PostgreSQL  — auditoria de cada execução
```

## Estrutura do serviço

```
.
├── app/
│   ├── routes/        # entrada HTTP; valida input (Pydantic), monta response
│   ├── services/      # regra de negócio (execução, whitelist) — não conhece HTTP nem SQL
│   ├── repositories/  # acesso a dados (scripts, executions, config)
│   ├── core/          # auth (X-Isy-Token), config, db, segurança
│   └── main.py        # cria o app FastAPI
├── scripts/           # exemplos de .sh (no deploy, vêm via volume do host)
├── Dockerfile         # imagem leve python:3.11-slim/alpine
├── requirements.txt
└── docs/
```

## Camadas do backend

| Camada | Responsabilidade | Conhece |
|--------|------------------|---------|
| rota/controller | receber request, validar input (Pydantic), montar response | HTTP |
| service | regra de negócio (execução, whitelist, validação de path) | nada de HTTP nem SQL |
| repository | ler/gravar dados (scripts, execuções, config) | SQL/ORM |

Regra: dependências apontam só para dentro (rota → service → repository), nunca o contrário.

## Segurança

- **Auth por header `X-Isy-Token`** em todas as rotas sensíveis (dependency do FastAPI);
  ausência/divergência → 401. Comparação com `secrets.compare_digest`.
- **Whitelist:** só executa scripts cadastrados e ativos (resolvidos por id no banco),
  nunca string arbitrária do request.
- **Anti command injection:** `subprocess.run` sempre com lista de argumentos e
  `shell=False`; parâmetros entram como itens da lista, nunca interpolados.
- **Anti path traversal:** caminho normalizado e obrigado a residir no diretório montado.
- **Timeout** em toda execução; token nunca aparece em logs nem em respostas.

## Persistência

Banco relacional (SQLite na demo, PostgreSQL para ambiente mais real). Tabelas:
`scripts` (cadastro), `executions` (auditoria: horário, script, parâmetros, status,
exit code) e `config` (token rotacionável).

## Deploy

- Entregável é um **Dockerfile** sobre `python:3.11-slim` (ou `-alpine`); só deps de
  runtime na imagem final.
- **Volume** monta o diretório de scripts do host → `/opt/isyone/scripts` (read-only).
- Execução sempre via container — **nunca** no terminal do host.
- Config via env (`ISY_TOKEN` inicial, `DATABASE_URL`, `SCRIPTS_DIR`).
- Railway segue viável (build por Dockerfile), mas não é requisito do desafio.

## Pitch (1 parágrafo)

> API em Python/FastAPI que elimina o SSH manual: o suporte dispara, por uma requisição
> autenticada com token, os scripts de manutenção dos servidores Isy.One. A execução usa
> `subprocess` de forma isolada num container Docker (scripts lidos por volume), só roda
> itens de uma whitelist — blindando contra command injection — e grava auditoria completa
> de cada chamada no banco. Diferencial: alertas em tempo real no Discord/Telegram.
