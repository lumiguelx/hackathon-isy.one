# hackathon-isy.one

Repositório do time para o hackathon. Monorepo, organizado por **spec-driven design**:
nada de código sem uma spec aprovada antes.

## Status

Ideia do hackathon ainda em aberto. Stack e arquitetura já definidos:
monorepo **TypeScript** (Turborepo + pnpm), front **Next.js** e back **Fastify**,
**Postgres** + **Redis** (opcional), deploy no **Railway**.

- Arquitetura e diagramas: [docs/architecture.md](docs/architecture.md)
- Decisão de stack: [ADR 0003](docs/adr/0003-stack-e-arquitetura.md)

## Estrutura

```
.
├── apps/        # web (Next.js) e api (Fastify) — entram ao iniciar o build
├── packages/    # shared (tipos + schemas Zod)
└── docs/
    ├── architecture.md
    ├── specs/   # uma spec por feature/ideia (problema → critério de sucesso)
    └── adr/     # decisões de arquitetura registradas
```

## Fluxo de trabalho

1. **Spec primeiro** — copie `docs/specs/TEMPLATE.md` para `docs/specs/AAAA-MM-DD-<nome>.md` e preencha.
2. **Decisão técnica** — toda escolha de arquitetura relevante vira um ADR em `docs/adr/`.
3. **Plano** — quebre a spec em tarefas pequenas e fechadas.
4. **Implementação** — uma branch por feature, PR pequeno, revisão rápida.

## Time

| Nome | GitHub | Função |
|------|--------|--------|
| Miguel | @lumiguelx | — |
