# 0003. Stack e arquitetura do projeto

- **Data:** 2026-05-27
- **Status:** substituída por [ADR 0004](0004-stack-python-fastapi.md)
- **Relacionada:** substitui a parte "tooling adiado" de [ADR 0002](0002-monorepo-tooling-deferred.md)

> **Obsoleta.** Decidida antes da definição do tema, com o pressuposto de stack livre.
> O desafio Isy.One tornou Python/FastAPI mandatório — ver [ADR 0004](0004-stack-python-fastapi.md).
> Conteúdo abaixo mantido por registro histórico.

## Contexto

Definido o alvo de deploy (Railway) e a topologia (frontend + backend + Postgres,
Redis opcional). Precisamos cravar o stack para ter velocidade de hackathon e uma
arquitetura limpa e defensável na apresentação. Prioridade: uma única linguagem,
deploy simples no Railway e separação clara de responsabilidades.

## Decisão

Stack único em **TypeScript**, monorepo **Turborepo + pnpm**:

| Peça | Escolha |
|------|---------|
| Frontend | Next.js (App Router) — serviço `web` |
| Backend | Fastify (Node/TS) — serviço `api` |
| Dados no front | TanStack Query (server state cliente) + RSC para dados iniciais |
| Validação/tipos | Zod em `packages/shared`, usado por web e api |
| ORM | Prisma |
| Banco primário | Postgres (gerenciado pelo Railway) |
| Cache/fila/sessão | Redis via ioredis (só quando necessário) |

Backend em camadas: `rota/controller → service (regra de negócio) → repository
(acesso a dados) → Postgres/Redis`. Service não conhece HTTP nem SQL.

### Não escolhido (e por quê)

- **NestJS**: mais estrutura pronta, mas peso/curva desnecessários para hackathon.
- **tRPC**: type-safety ponta a ponta atraente, mas acopla front↔back; fica como
  opção futura, não padrão.
- **SWR**: mais leve que TanStack Query, porém menos completo (mutations/devtools).
- **Next.js fullstack** (sem `api` separado): simples, mas o time quer front e back
  como serviços independentes no Railway.

## Consequências

- Uma linguagem ponta a ponta reduz atrito num time pequeno.
- `packages/shared` garante tipos/validação coerentes entre web e api.
- No Railway, `web` e `api` são serviços separados (Root Directory por app),
  buildados pelo Railpack; Postgres e Redis são plugins gerenciados.
- Camadas no backend custam um pouco de boilerplate, mas mantêm o código testável
  e a apresentação clara.
