# 0002. Monorepo com ferramentas adiadas até definir a ideia

- **Data:** 2026-05-27
- **Status:** aceita

## Contexto

O projeto será um monorepo, mas a ideia do hackathon ainda não foi definida.
Cravar agora as ferramentas (Turborepo + pnpm, Nx, etc.) amarraria o stack a
JS/TS antes de sabermos o que vamos construir.

## Decisão

- Adotar monorepo desde já.
- **Não** adicionar ferramentas de monorepo agora. Manter apenas `docs/` com o processo.
- Quando o stack for confirmado, adicionar a ferramenta adequada. Preferência atual,
  se for JS/TS: **Turborepo + pnpm workspaces** (`apps/*`, `packages/*`), pela
  leveza e cache de build/test. Essa escolha será registrada num novo ADR na hora.

## Consequências

- Liberdade para escolher o stack certo quando a ideia estiver fechada.
- Setup de monorepo fica como uma pequena tarefa no início do evento.
- Risco baixo: a estrutura `docs/` e o fluxo spec-driven funcionam independente do stack.
