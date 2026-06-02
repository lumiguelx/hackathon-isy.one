# 0005. Multi-tenant, token de dois niveis e event sourcing pragmatico

- **Data:** 2026-06-01
- **Status:** aceita
- **Relacionada:** evolui o [ADR 0004](0004-stack-python-fastapi.md); detalhada no
  [design](../specs/2026-06-01-multi-tenant-event-sourcing-design.md)

## Contexto

A v1 da API executa scripts de uma whitelist global, com token unico e auditoria
simples. A Isy.One opera centenas de restaurantes, cada um com seu Odoo (db, dominio,
porta) num servidor. A manutencao real e **por cliente**. Precisamos evoluir para um
painel central multi-cliente sem perder a base ja testada, e queremos um diferencial
forte para o pitch dentro do tempo de um hackathon.

## Decisao

Tres decisoes de arquitetura, validadas no brainstorming:

### 1. Tenant como entidade de primeira classe

Surge `tenants` (slug, dominio, porta, db_name, status, token proprio). Scripts passam
a ser um **catalogo hibrido**: globais (compartilhados) + extras por cliente, ligados ao
tenant por `tenant_scripts` (binding com parametros default por cliente). A execucao e
sempre tenant-scoped, e a whitelist passa a ser **por cliente**.

### 2. Autenticacao em dois niveis

- **Token admin** (em `config`): gerencia tenants/catalogo e enxerga todos.
- **Token do tenant** (em `tenants.token`): so executa/audita o proprio cliente.

Nas rotas de um tenant vale o token dele ou o admin. Comparacao com `compare_digest`.

### 3. Event sourcing pragmatico (Abordagem B)

O dominio **operacional** vira um event store append-only e imutavel (`events`), com
`ExecutionCompleted` e `TokenRotated`. A **saude de cada tenant e uma projecao calculada
on-read** a partir dos eventos (ultima manutencao, ultimo backup, containers, status
geral). O **cadastro** (tenants, scripts) continua CRUD — nao e event-sourced.

Nao adotamos event sourcing canonico (replay, snapshots, CQRS): fica como evolucao.

## Alternativas descartadas

- **Event-source tudo** (cadastro inclusive): cerimonia pesada para dado de config; risco
  alto num fim de semana.
- **Token unico** com tenant so como rotulo: mais simples, mas perde o isolamento por
  credencial — que e o diferencial de seguranca.
- **Tabela de saude mutavel** (sem eventos): perde o discurso de auditoria/event sourcing
  e introduz estado que dessincroniza.

## Consequencias

- A whitelist por cliente reforca o criterio de Seguranca (token do tenant A nao roda
  nada do B), somando a `shell=False`, anti path-traversal e `compare_digest`.
- A auditoria da banca passa a ser o proprio event store (append-only).
- A saude nao e estado guardado: reconstroi do historico. Com poucos tenants, custo
  desprezivel; em escala, exigiria projecao materializada/snapshots (evolucao).
- `executions` da v1 migra para `events` (tipo `ExecutionCompleted`), reaproveitando a
  logica de execucao ja testada.
- Mais superficie (tenants, bindings, auth de dois niveis, projecao, UI multi-cliente),
  mas e o que entrega o diferencial e o cenario real da Isy.One.
