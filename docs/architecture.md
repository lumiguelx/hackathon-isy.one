# Arquitetura

Material de referência do projeto — útil também para a apresentação.
Stack e justificativas em [ADR 0003](adr/0003-stack-e-arquitetura.md).

## Visão geral

Monorepo TypeScript (Turborepo + pnpm). Frontend e backend são apps separados que
viram serviços independentes no Railway, conversando pela rede privada do projeto.

```
Navegador
   │  HTTPS
   ▼
[web]  Next.js (App Router)
   │  HTTP (rede interna Railway)
   ▼
[api]  Fastify  ──▶  rota → service → repository
   │                                   │
   ├──────────────▶ [Postgres]  (banco primário, via Prisma)
   └──────────────▶ [Redis]     (cache / fila / sessão — opcional, via ioredis)
```

## Estrutura do monorepo

```
.
├── apps/
│   ├── web/                 # Next.js — serviço "web"
│   └── api/                 # Fastify — serviço "api"
│       └── src/
│           ├── routes/      # entrada HTTP; valida input com schema de shared
│           ├── services/    # regra de negócio (não conhece HTTP nem SQL)
│           ├── repositories/# acesso a dados (Prisma / Redis)
│           ├── lib/         # db, redis, config
│           └── server.ts
├── packages/
│   └── shared/              # tipos + schemas Zod compartilhados por web e api
├── turbo.json
├── pnpm-workspace.yaml
└── docs/
```

## Camadas do backend

| Camada | Responsabilidade | Conhece |
|--------|------------------|---------|
| rota/controller | receber request, validar input (Zod), montar response | HTTP |
| service | regra de negócio | nada de HTTP nem SQL |
| repository | ler/gravar dados | Prisma / Redis |

Regra: dependências apontam só para dentro (rota → service → repository), nunca o contrário.

## Dados no frontend

- **RSC (Server Components)**: dados iniciais/estáticos buscados no servidor.
- **TanStack Query**: server state interativo no cliente — cache, refetch, mutations,
  invalidação, optimistic updates.

## Deploy no Railway

- **1 projeto Railway** com 4 serviços: `web`, `api`, `Postgres`, `Redis`.
- `web` e `api` apontam para o mesmo repo, cada um com **Root Directory** próprio
  (`apps/web`, `apps/api`). O **Railpack** containeriza cada um automaticamente
  (sem Dockerfile; dá para adicionar um se precisar de controle fino).
- `Postgres` e `Redis` são plugins gerenciados — injetam `DATABASE_URL` / `REDIS_URL`
  via *reference variables* na rede interna; nada de banco exposto à internet.
- Fluxo: **navegador → web → api → Postgres/Redis**.

## Pitch (1 parágrafo)

> Monorepo TypeScript com Turborepo. Frontend Next.js e backend Fastify em camadas
> (rota → serviço → repositório), com tipos e validação compartilhados via Zod.
> Postgres como banco primário e Redis para cache/filas. No Railway cada parte é um
> serviço containerizado automaticamente pelo Railpack, comunicando pela rede privada
> do projeto.
