# Arquitetura

Material de referência do projeto — útil também para a apresentação.
Stack e justificativas em [ADR 0004](adr/0004-stack-python-fastapi.md); a evolução
multi-tenant em [ADR 0005](adr/0005-multi-tenant-event-sourcing.md) e no
[design](specs/2026-06-01-multi-tenant-event-sourcing-design.md). Escopo no
[PRD](specs/2026-06-01-isy-shell-automation-api.md).

## Visão geral

Painel central de manutenção **multi-cliente** em **Python (FastAPI)** que executa, de
forma controlada e auditada, os shell scripts de manutenção dos servidores Isy.One —
substituindo o acesso manual via SSH. Cada cliente é um **tenant isolado** por credencial;
cada execução vira um **evento imutável** e a saúde de cada cliente é uma **projeção
calculada on-read** desses eventos. Tudo roda num container Docker.

```
Operador / curl / Swagger / UI (/ui)
   │  HTTP + header X-Isy-Token  (token admin OU token do tenant)
   ▼
[api]  FastAPI  ──▶  rota → service → repository
   │        │
   │        ├─▶ local:  subprocess.run([script, *params], shell=False, timeout)
   │        │              lê .sh via volume → [/opt/isyone/scripts]
   │        └─▶ remoto: script faz SSH no servidor do cliente (tenant.ssh_host)
   │                       chave do secret ISY_SSH_KEY
   ▼
[banco]  SQLite (demo) / PostgreSQL
         tenants · scripts · tenant_scripts · events (auditoria imutável) · config
```

## Camadas do backend

| Camada | Responsabilidade | Conhece |
|--------|------------------|---------|
| rota/controller (`routes/`) | receber request, validar input (Pydantic), montar response | HTTP |
| service (`services/`) | regra de negócio (execução, saúde, alertas) | nada de HTTP nem SQL |
| repository (`repositories/`) | ler/gravar dados | SQL/ORM |
| core (`core/`) | auth, config, db, segurança, tipos de evento | infra |

Regra: dependências apontam só para dentro (rota → service → repository).

## Modelo de dados

- **`tenants`** — cliente (slug, nome, domínio, porta, db_name, token próprio, `ssh_host`/`ssh_port`).
- **`scripts`** — catálogo de scripts (nome, caminho, categoria, status ativo/inativo).
- **`tenant_scripts`** — binding tenant↔script: whitelist + parâmetros default por cliente.
- **`events`** — event store append-only (`ExecutionCompleted`, `TokenRotated`); auditoria
  imutável com horário, script, parâmetros, status, exit code, duração.
- **`config`** — token admin rotacionável.

A saúde (verde/amarelo/vermelho) é derivada on-read dos eventos — não há tabela de status.

## Segurança

- **Auth em dois níveis:** token **admin** (gestão de tenants/catálogo) e token **por tenant**
  (opera só o próprio cliente). O token de um cliente nunca acessa outro → isolamento.
  Comparação com `secrets.compare_digest`.
- **Whitelist por tenant:** só executa scripts cadastrados, ativos e *bindados* ao cliente.
- **Anti command injection:** `subprocess.run` sempre com lista de argumentos e `shell=False`.
  No caminho SSH, parâmetros interpolados em comando remoto são validados (charset seguro).
- **Anti path traversal:** caminho normalizado e obrigado a residir no diretório montado.
- **Timeout** em toda execução; tokens nunca aparecem em logs nem em respostas.

## Execução remota (SSH)

Quando um tenant tem `ssh_host`, o painel injeta o endpoint no ambiente do subprocess
(`ISY_SSH_HOST`/`ISY_SSH_PORT`/`ISY_SSH_USER`) e o script alcança o servidor do cliente por
SSH (chave privada do secret `ISY_SSH_KEY`). Sem `ssh_host`, o script roda localmente
(modo demo). Detalhes em [`deploy/client-box/README.md`](../deploy/client-box/README.md).

## Persistência

Banco relacional via SQLAlchemy 2.0. SQLite na demo local; **PostgreSQL** no deploy
(o driver é normalizado para `psycopg` v3 automaticamente). Auditoria transacional por evento.

## Deploy

- **Dockerfile** sobre `python:3.11-slim` + `openssh-client`; só deps de runtime.
- **Local (compose):** scripts via **volume** do host → `/opt/isyone/scripts` (read-only).
- **Railway:** scripts embarcados na imagem (sem volume), Postgres do projeto, seedado com
  5 clientes de demonstração. Config em `railway.json`.
- Execução sempre via container — **nunca** no terminal do host.
- Config via env (`ISY_TOKEN`, `ISY_DATABASE_URL`, `ISY_SCRIPTS_DIR`, `ISY_SEED_DEMO`, `ISY_SSH_KEY`).

## Diferenciais (pitch)

> Painel multi-cliente que elimina o SSH manual: o suporte dispara, por requisição
> autenticada e isolada por tenant, os scripts de manutenção. Execução `subprocess` segura
> (whitelist + `shell=False`) num container, com **execução SSH real** no servidor de cada
> cliente. Toda chamada vira **evento imutável** (event sourcing) e a **saúde** de cada
> cliente é uma projeção on-read. Extras: alertas em tempo real (Discord/Telegram),
> dashboard neutro e base pronta para o self-service ("free") de provisionamento de clientes.
