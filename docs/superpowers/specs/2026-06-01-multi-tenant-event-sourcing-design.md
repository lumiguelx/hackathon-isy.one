# Design — Multi-tenant + Event Sourcing (Isy.One Shell Automation)

- **Data:** 2026-06-01
- **Autor(es):** @lumiguelx
- **Status:** aprovado (brainstorming)
- **Base:** evolui o [PRD](../../specs/2026-06-01-isy-shell-automation-api.md) e o [ADR 0004](../../adr/0004-stack-python-fastapi.md)

## Contexto e problema

A primeira versao da API executa shell scripts de uma whitelist global, com token
unico e auditoria simples. A Isy.One, porem, opera **centenas de restaurantes**, cada
um com seu proprio Odoo (db, dominio, porta) num servidor. A manutencao real e por
cliente, e hoje exige SSH manual em cada um.

Esta evolucao transforma a API num **painel central de manutencao multi-cliente**, onde
cada restaurante e um tenant isolado, e a saude de cada um e derivada de um historico
imutavel de eventos.

## Objetivos

- Tenant (cliente) como entidade de primeira classe, com credencial propria.
- Catalogo de scripts compartilhado + extras por cliente, com parametros default por tenant.
- Auditoria como **event store append-only** (event sourcing pragmatico).
- **Painel de saude por cliente** derivado dos eventos (diferencial de pitch).
- Demo com **>= 5 clientes** e deploy publico no Railway, ja seedado.

## Nao-objetivos (YAGNI)

- Event sourcing canonico (replay, snapshots, CQRS) — fica como evolucao.
- Event-source de cadastro (tenant/script seguem CRUD).
- UI sofisticada — agora ela e **neutra/minima e funcional**; repaginacao visual vem depois.
- Operacao em frota (rodar em todos os clientes de uma vez) — evolucao futura.
- Health check HTTP externo (`https://<slug>.isy.one`) — fora do escopo.

## Decisoes (resumo)

| Tema | Decisao |
|------|---------|
| Multi-tenancy | Tenant de primeira classe (slug, dominio, porta, db, status, token proprio) |
| Scripts | Hibrido: catalogo global + extras por cliente; defaults por tenant, sobrescriveis |
| Auth | Dois niveis: token admin (gerencia tudo) + token do tenant (so executa o dele) |
| Arquitetura | Event sourcing pragmatico (Abordagem B): operacional event-sourced, cadastro CRUD |
| Diferencial | Painel de saude por cliente (status geral + containers + ultima manutencao + ultimo backup) |
| Saude | Projecao calculada on-read a partir dos eventos (sem tabela de estado) |
| Demo | >= 5 tenants + eventos historicos seedados |
| Deploy | Railway (publico, seedado com clientes de demo); local via Docker como plano B |

## Modelo de dados

### Tabelas CRUD (config)

- **`tenants`** — `id`, `slug` (unico), `nome`, `dominio`, `porta`, `db_name`, `ativo`,
  `token` (proprio, rotacionavel), `criado_em`.
- **`scripts`** (catalogo) — `id`, `nome`, `caminho`, `parametros` (descricao), `descricao`,
  `categoria` (`provision` | `backup` | `cleanup` | `status` | `update` | `other`),
  `tenant_id` (nullable; preenchido so em script especifico de um cliente), `ativo`, `criado_em`.
- **`tenant_scripts`** (binding) — `id`, `tenant_id`, `script_id`, `parametros_default`,
  `ativo`. Define o que cada cliente pode rodar e com quais defaults. Os scripts disponiveis
  de um tenant = `tenant_scripts` ativos dele.
- **`config`** — token admin (rotacionavel).

### Event store (append-only, imutavel)

- **`events`** — `id` (ordenado), `tipo`, `tenant_id` (nullable), `script_id` (nullable),
  `payload` (JSON), `ocorrido_em`. Nunca sofre UPDATE/DELETE.
- Taxonomia:
  - **`ExecutionCompleted`** — payload `{categoria, status, exit_code, stdout, stderr, duracao_ms}`.
    Substitui a tabela `executions` atual. Base da auditoria e da saude.
  - **`TokenRotated`** — auditoria de rotacao (admin ou tenant).
- `stdout/stderr` ficam no payload (cap de 10k mantido).

## Autenticacao (dois niveis)

- **Token admin** (em `config`): gerencia tudo, enxerga todos.
- **Token do tenant** (em `tenants.token`): so lista/executa/audita o proprio cliente.
- Regra nas rotas de tenant: vale o token daquele tenant **ou** o admin. Sempre `compare_digest`.
- Dependencies: `verify_admin` e `verify_tenant(slug)`.

## Rotas

### Admin (`verify_admin`)

- `GET/POST/PUT/DELETE /api/v1/admin/tenants` — CRUD de clientes.
- `GET/POST/PUT/DELETE /api/v1/admin/scripts` — catalogo (e scripts especificos).
- `PUT /api/v1/admin/tenants/{slug}/scripts` — ativar/desativar e setar defaults por cliente.
- `PUT /api/v1/admin/token` — rotaciona token admin.
- `PUT /api/v1/admin/tenants/{slug}/token` — rotaciona token do cliente (gera `TokenRotated`).
- `GET /api/v1/admin/tenants/health` — dashboard: saude de todos.

### Tenant (`verify_tenant`)

- `GET /api/v1/tenants/{slug}/scripts` — manutencoes disponiveis (whitelist via `tenant_scripts`).
- `POST /api/v1/tenants/{slug}/scripts/{script_id}/run` — executa (defaults + override opcional).
- `GET /api/v1/tenants/{slug}/logs` — auditoria do cliente.
- `GET /api/v1/tenants/{slug}/health` — saude do cliente.

## Fluxo de execucao (tenant-scoped)

1. Resolve `slug` -> 404 se inexistente/inativo.
2. `verify_tenant` (token do cliente ou admin).
3. Resolve script pelo binding `tenant_scripts` (whitelist **por cliente**) -> 404 se indisponivel.
4. `params = override or parametros_default`.
5. `resolve_script_path` (anti traversal) + `subprocess` `shell=False` + timeout.
6. Append `ExecutionCompleted` no event store.
7. Alerta em falha (Discord/Telegram — reusa `alert_service`).
8. Envelope JSON padrao.

Ganho de seguranca (criterio 25%): whitelist agora e **por cliente** (token do tenant A nao
roda nada do tenant B), somando a `shell=False`, anti path-traversal e `compare_digest`.

## Projecao de saude (on-read)

`calcular_saude(tenant)` le os `ExecutionCompleted` do cliente e devolve:

- **ultima manutencao** — evento mais recente (script, sucesso/falha, quando).
- **ultimo backup** — evento mais recente com `categoria=backup` e `status=sucesso` (ou "nunca").
- **containers** — stdout do evento mais recente com `categoria=status`.
- **status geral**:
  - vermelho — ultima manutencao falhou, ou container fora do ar.
  - amarelo — sem backup ha mais de N dias (default 7), ou nunca rodou status.
  - verde — resto.

Nada e estado guardado: e derivado na hora. Com 5 tenants, instantaneo.

## UI (neutra/minima, funcional)

- Visual padrao/neutro, sem tema/firula. Sera repaginada depois.
- Tela principal: grid de cartoes, um por cliente (nome, bolinha de status, containers,
  ultima manutencao, ultimo backup).
- Clicar num cartao: abre o cliente — manutencoes disponiveis (defaults preenchidos),
  botao executar, e historico do cliente.
- Campo de token no topo (admin ve todos; token de cliente abre so ele).
- Servida pelo proprio FastAPI em `/ui`, sem build.

## Seed (demo viva)

- 5 tenants: `cliente-1` .. `cliente-5` (slug `cliente-N`, dominio `clienteN.isy.one`,
  db `db_clienteN`, porta sequencial a partir de 8151), cada um com token proprio.
- Catalogo global com categorias: `provisionar`, `backup_db`, `cleanup_logs`, `update_agent`,
  `docker_status`. Criar `backup_db.sh` (simulado: pg_dump + tar do filestore).
- Bindings `tenant_scripts` com defaults por cliente.
- **Eventos historicos seedados**: alguns `ExecutionCompleted` no passado (ultimo backup ha 2
  dias, cleanup hoje, uma falha) para o painel abrir com status variados sem rodar nada.

## Deploy

- Entregavel: Dockerfile + `docker-compose` (volume de scripts, banco persistido).
- **Railway** como alvo principal: build pelo Dockerfile, Postgres gerenciado, URL publica,
  **seedado com os clientes de demo** (`ISY_SEED_DEMO=true`).
- **Local via Docker** como plano B garantido para o video (sem depender de rede ao vivo).

## Testes

- Os 11 atuais adaptados ao novo fluxo.
- Novos: isolamento por token de tenant (A nao acessa B), whitelist por cliente,
  projecao de saude a partir de eventos, rotacao de token de tenant.

## Migracao a partir do codigo atual

- `executions` -> `events` (tipo `ExecutionCompleted`); reusa a logica de execucao ja testada.
- `scripts` ganha `categoria` e `tenant_id`; surge `tenants` e `tenant_scripts`.
- `security` ganha `verify_admin` / `verify_tenant`; rotas reorganizadas em admin/tenant.
- `seed` evolui para tenants + catalogo + bindings + eventos historicos.

## Mapeamento ao pitch / criterios da banca

- **Arquitetura & API (25%)** — multi-tenant, event store, projecao.
- **Seguranca (25%)** — isolamento por credencial de tenant + blindagens existentes.
- **Persistencia (20%)** — event store append-only e a propria auditoria.
- **Deploy & Docker (20%)** — Railway + Dockerfile + volume.
- **Pitch & Inovacao (10%)** — painel de saude vivo + discurso de event sourcing.

## Evolucao futura (mencionar no fechamento)

- Operacao em frota (rodar manutencao em N clientes de uma vez).
- Replay/snapshots/CQRS.
- Fila assincrona para execucoes longas.
- Health check HTTP externo real por cliente.
