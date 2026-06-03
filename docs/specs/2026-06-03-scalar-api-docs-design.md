# Design — Documentação de API branded com Scalar

- **Data:** 2026-06-03
- **Autor(es):** @lumiguelx
- **Status:** aprovado (brainstorming)
- **Tipo:** design de feature

## Problema

O `/docs` hoje serve o Swagger UI padrão do FastAPI — funcional, mas genérico e sem
nenhuma identidade visual. Para o pitch, queremos uma página de documentação de API com a
cara da ISYOPS (navy/gold, Inter Tight, logo). Além disso, no OpenAPI as respostas das
rotas aparecem sem schema, o que deixa a doc pobre — mas tipar respostas é um trabalho
separado (ver revisão da API) e está **fora do escopo** desta spec.

## Objetivo

Substituir o Swagger no `/docs` por uma referência de API renderizada pelo **Scalar**
(MIT/OSS), com tema custom ISYOPS, mantendo o Swagger acessível para debug.

## Decisões (brainstorming)

| Decisão | Escolha |
|---|---|
| Colocação | Scalar em `/docs`; Swagger movido para `/swagger` |
| Carregamento do JS | CDN (`cdn.jsdelivr.net/npm/@scalar/api-reference`) |
| Branding | Tema custom completo ISYOPS (navy/gold, Inter Tight, logo, favicon) |
| Integração | Rota HTML própria + Scalar standalone (sem dependência Python nova) |

## Abordagem

Rota HTML própria servindo o Scalar standalone via CDN. Sem pacote `scalar-fastapi`
(evita dependência e dá controle total de CSS).

## Componentes

### 1. `app/main.py`

- Construir o app com `docs_url="/swagger"` e `redoc_url=None`. Isso move o Swagger UI
  para `/swagger` e desliga o ReDoc; `openapi_url` permanece o default `/openapi.json`.
- Nova rota `GET /docs` (`include_in_schema=False`) que devolve a página Scalar via
  `FileResponse` do template estático.

### 2. `app/static/scalar.html`

Template estático servido no `GET /docs`. Conteúdo:

- `<script id="api-reference" data-url="/openapi.json"></script>` apontando para o spec
  da própria origem.
- `<script>` do Scalar via CDN **com versão fixa + SRI**:
  `src="https://cdn.jsdelivr.net/npm/@scalar/api-reference@<versao>"` mais
  `integrity="sha384-..."` e `crossorigin="anonymous"`. Evita risco de CDN comprometida
  (carregar `@latest` sem hash deixa a página à mercê do bundle servido).
- Objeto `configuration` com `theme: 'none'` (nosso CSS assume) e
  `withDefaultFonts: false` (usamos Inter Tight).
- `<link rel="icon" href="/ui/brand/favicon-32.png">` e logo ISYOPS
  (`/ui/brand/c_dark.svg`) no topo da página/sidebar.

### 3. Tema ISYOPS (`<style>` inline no template)

- Inter Tight via Google Fonts (CDN), coerente com a decisão de carregamento.
- Variáveis Scalar (fonte do `brand-spec.md`):
  - `:root { --scalar-font: "Inter Tight", sans-serif; --scalar-color-accent: #fcb400; }`
  - `.dark-mode { --scalar-background-1: #010128; --scalar-background-2: #0e113a;
    --scalar-background-3: #15163a; --scalar-color-1: rgba(255,255,255,.9);
    --scalar-border-color: rgba(255,255,255,.08); }`
  - Modo claro calibrado para o off-white `#f6f5f1` da marca.

## Fluxo de dados

```
GET /docs
  → FastAPI serve app/static/scalar.html
    → browser baixa @scalar/api-reference (jsdelivr) + Inter Tight (Google Fonts)
      → Scalar busca /openapi.json (mesma origem)
        → renderiza a referência com o tema ISYOPS
```

## Tratamento de erros

A rota apenas serve um arquivo estático. Se `/openapi.json` falhar, o próprio Scalar
exibe seu aviso de erro. Nenhum novo caminho de erro é introduzido no backend.

## Testes

- `GET /docs` → 200 e o corpo contém o marcador do Scalar (`id="api-reference"`) e a
  referência de marca (ex.: caminho do logo/brand).
- `GET /swagger` → 200 (Swagger movido com sucesso).
- `GET /openapi.json` → 200 (spec intacto).
- Verificar/ajustar qualquer teste atual que aponte para `/docs`.

## Fora de escopo (YAGNI)

- Vendorizar o JS do Scalar localmente (decisão foi CDN).
- Tipar response models no OpenAPI (item separado da revisão da API).
- Alternância de tema custom além do que o Scalar já oferece (calibramos os dois modos).
