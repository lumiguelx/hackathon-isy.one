# PRD — Isy.One Shell Automation API

- **Data:** 2026-06-01
- **Autor(es):** @lumiguelx
- **Status:** rascunho
- **Tipo:** PRD (fonte de verdade do escopo do hackathon)
- **Relacionada:** conflita com [ADR 0003](../adr/0003-stack-e-arquitetura.md) (stack TS) — ver seção *Decisão de stack*

> Documento-base do desafio Isy.One. A stack aqui (Python/FastAPI/Docker) é
> **mandatória pela banca** e substitui as escolhas de TypeScript do ADR 0003 para
> este escopo. A formalização (novo ADR + ajuste de README/arquitetura) é tarefa
> à parte.

---

## 1. Resumo executivo

**Problema.** O suporte da Isy.One mantém centenas de servidores Linux/Ubuntu de
restaurantes parceiros (Agente de Impressão do iFood). Toda manutenção — atualizar o
agente, limpar logs de cupons antigos, checar containers Docker do banco — exige acesso
manual via SSH para rodar shell scripts. Isso é lento, não tem rastreabilidade e vira
gargalo operacional.

**Solução.** Uma API REST em Python (FastAPI) que executa, de forma controlada e
auditada, os shell scripts de manutenção do host. A execução é autorizada por token,
isolada em container Docker (scripts lidos via volume), com registro transacional de
cada chamada. Elimina o SSH manual e dá histórico de auditoria.

**Critérios de sucesso (KPIs da demo).**

- Disparar a execução de um `.sh` real via `POST` autenticado e devolver `stdout`/`stderr`
  em JSON padronizado, em < 2 s para scripts de manutenção típicos.
- 100% das execuções gravadas no banco (horário, script, parâmetros, status) — auditoria
  sem furos.
- 0 rotas sensíveis acessíveis sem o header `X-Isy-Token` válido (todas retornam 401).
- 0 execução de comando fora da whitelist de scripts cadastrados (proteção contra command
  injection comprovada com payload malicioso na demo).
- Imagem Docker leve (`python:3.11-slim`/`alpine`) sobe o serviço com os scripts montados
  por volume, sem execução direta no terminal do host.

### Mapa para os critérios da banca

| Critério (peso) | Onde este PRD cobre |
|---|---|
| Arquitetura & API (25%) | §4 Endpoints, §4 `subprocess`, JSON padronizado, rotas admin |
| Segurança / Token (25%) | §4 Segurança — `X-Isy-Token`, whitelist, anti-injection |
| Persistência de Logs (20%) | §4 Modelo de dados — tabela `executions` |
| Deploy & Docker (20%) | §4 Empacotamento — imagem leve + volumes |
| Pitch & Inovação (10%) | §5 Diferenciais — alertas Discord/Telegram |

---

## 2. Experiência & funcionalidade

### Personas

- **Operador de suporte (primário).** Precisa rodar manutenções rotineiras sem abrir SSH,
  com confirmação de sucesso/falha e histórico.
- **Administrador da plataforma.** Cadastra/edita os scripts disponíveis, ativa/desativa e
  rotaciona o token de acesso.
- **Auditor / liderança técnica.** Consulta o histórico de execuções para rastrear o que
  rodou, quando, com quais parâmetros e resultado.

### User stories e critérios de aceite

**US-1 — Listar scripts disponíveis.**
*Como operador, quero listar os scripts ativos para saber o que posso executar.*
- `GET /api/v1/scripts` exige `X-Isy-Token` válido; sem ele → 401.
- Retorna só scripts com `status = ativo`: nome, descrição curta, parâmetros esperados.
- Resposta JSON padronizada (envelope `status`/`data`).

**US-2 — Executar script parametrizado.**
*Como operador, quero disparar um script com parâmetros e ver a saída.*
- `POST /api/v1/scripts/{id}/run` (ou rota parametrizável equivalente) exige token.
- Executa via `subprocess` capturando `stdout` e `stderr`.
- Sucesso → `{ "status": "success", "output": <stdout>, "exit_code": 0 }`.
- Falha do script → `{ "status": "error", "error": <stderr>, "exit_code": <n> }` com HTTP
  apropriado, **sem derrubar a API**.
- Só executa script **cadastrado e ativo**; id inexistente/inativo → 404/409.

**US-3 — Administrar scripts.**
*Como admin, quero cadastrar e manter os scripts da automação.*
- CRUD em `/api/v1/admin/scripts`: campos `script` (caminho/arquivo), `parametros`,
  `descricao` curta e `status` lógico (ativo/inativo).
- Validação de entrada (caminho dentro do diretório montado; sem `..`/path traversal).

**US-4 — Rotacionar token.**
*Como admin, quero trocar o token de autenticação dinamicamente.*
- Endpoint admin altera o token vigente; chamadas seguintes exigem o novo valor.
- Token nunca aparece em logs nem em respostas.

**US-5 — Auditar execuções.**
*Como auditor, quero o histórico completo das execuções.*
- `GET /api/v1/logs` (admin/token) lista: horário exato, script invocado, parâmetros e
  status de retorno (sucesso/falha).
- Cada execução de US-2 gera exatamente um registro persistido (transacional).

### Não-objetivos (fora de escopo do fim de semana)

- Execução assíncrona / fila de mensageria (fica como evolução).
- UI web completa de gestão (admin pode ser via Swagger + endpoints; UI é opcional).
- RBAC com múltiplos usuários/papéis — usamos um único token compartilhado.
- Multi-host / orquestração de vários servidores ao mesmo tempo.
- Streaming de saída em tempo real (basta `stdout`/`stderr` ao final).

---

## 3. Fluxo principal

```
Operador / curl / Swagger
   │  POST /api/v1/scripts/{id}/run   (header X-Isy-Token)
   ▼
[API FastAPI]  verify_token ──(inválido)──▶ 401
   │ (válido)
   ▼
busca script no banco ──(inexistente/inativo)──▶ 404/409
   │ (ativo)
   ▼
subprocess.run([script, *params], shell=False, capture_output, timeout)
   │
   ├─▶ grava execução (timestamp, script, params, status, exit_code) em [DB]
   └─▶ (diferencial) dispara alerta Discord/Telegram em falha
   │
   ▼
JSON padronizado { status, output | error, exit_code }
```

Scripts vivem no **host** e são lidos pelo container via **volume Docker** (`/opt/isyone/scripts`).

---

## 4. Especificações técnicas

### Stack (mandatória pela banca)

| Peça | Escolha |
|---|---|
| Linguagem/runtime | Python 3.11 |
| Framework | FastAPI + Uvicorn (Swagger automático em `/docs`) |
| Execução de SO | `subprocess.run` (nativo), `shell=False`, `timeout` |
| Banco | PostgreSQL **ou** SQLite (SQLite default para a demo; ver *Decisão de stack*) |
| Acesso a dados | SQLAlchemy (ou `sqlite3`/`asyncpg` se preferir leveza) |
| Empacotamento | Docker, imagem `python:3.11-slim` (ou `-alpine`) |

### Endpoints (todos sob `X-Isy-Token`, exceto `/docs` e healthcheck)

| Método | Rota | Função |
|---|---|---|
| `GET` | `/api/v1/scripts` | Lista scripts ativos |
| `POST` | `/api/v1/scripts/{id}/run` | Executa script parametrizado |
| `GET` | `/api/v1/admin/scripts` | Lista todos (inclui inativos) |
| `POST` | `/api/v1/admin/scripts` | Cadastra script |
| `PUT` | `/api/v1/admin/scripts/{id}` | Edita / ativa / desativa |
| `DELETE` | `/api/v1/admin/scripts/{id}` | Remove script |
| `PUT` | `/api/v1/admin/token` | Rotaciona o token |
| `GET` | `/api/v1/logs` | Histórico de execuções |
| `GET` | `/health` | Liveness (sem token) |

**Envelope JSON padrão:** `{ "status": "success" | "error", "data": ..., "message": ... }`.

### Modelo de dados

`scripts`
- `id` (PK)
- `nome` — identificador legível
- `caminho` — arquivo `.sh` (relativo ao diretório montado; validado)
- `parametros` — descrição/contrato dos parâmetros esperados
- `descricao` — texto curto
- `ativo` — boolean (status lógico)
- `criado_em`

`executions` (auditoria)
- `id` (PK)
- `script_id` (FK) / `script_nome` (snapshot)
- `parametros` — o que foi enviado
- `status` — `sucesso` | `falha`
- `exit_code`
- `stdout` / `stderr` (truncados a um limite)
- `executado_em` — horário exato
- `duracao_ms`

`config`
- `token` — valor vigente (rotacionável)

### Segurança (peso 25% — bloco mais estratégico)

- **Autenticação por header.** Dependency `verify_token` valida `X-Isy-Token` em todas as
  rotas sensíveis; ausência/divergência → 401. Comparação com `secrets.compare_digest`
  (evita timing attack).
- **Whitelist de execução.** Nunca se executa string arbitrária do request. Só roda
  scripts **cadastrados e ativos**, resolvidos por `id` → caminho do banco.
- **Anti command injection.** `subprocess.run` sempre com **lista de argumentos** e
  `shell=False` (jamais `shell=True` nem concatenação de string). Parâmetros entram como
  itens da lista, nunca interpolados em comando.
- **Path traversal.** Caminho do script normalizado e obrigado a residir dentro do
  diretório montado; rejeita `..` e caminhos absolutos fora da raiz.
- **Timeout** em toda execução para evitar processo pendurado.
- **Token fora de logs/respostas.**
- *Demo de segurança:* enviar um parâmetro malicioso (ex.: `; rm -rf /`) e mostrar que
  ele entra como argumento literal, sem efeito — ponto alto do pitch.

### Empacotamento & deploy (peso 20%)

- **Dockerfile** multi-stage enxuto sobre `python:3.11-slim` (ou `-alpine`); só deps de
  runtime na imagem final.
- **Volume** mapeando o diretório de scripts do host → `/opt/isyone/scripts` (read-only).
- **Proibido** rodar direto no terminal do host: tudo dentro do container.
- Variáveis via env (`ISY_TOKEN` inicial, `DATABASE_URL`, `SCRIPTS_DIR`).
- Banco: SQLite em volume nomeado para a demo; PostgreSQL como container/serviço quando
  for para ambiente mais real.

---

## 5. Riscos & roadmap

### Rollout faseado

- **MVP (obrigatório p/ demo):** listar scripts, executar com token, auditar em banco,
  Dockerfile + volume, Swagger. Cobre 90% dos pontos da banca.
- **v1.1 (diferenciais — peso 10% + robustez):** alertas em tempo real para
  **Discord/Telegram** em falha (ou em toda execução); rate limiting; sanitização
  reforçada demonstrável.
- **v2.0 (evolução, mencionar no fechamento):** fila de mensageria para execução
  assíncrona; UI web de gestão; múltiplos servidores; RBAC.

### Riscos técnicos

- **Command injection** (alto impacto): mitigado por whitelist + `shell=False` + validação
  de path. É o risco que a banca mais testa.
- **Script pendurado / runaway:** mitigado por `timeout` e captura de retorno.
- **Permissões no host/volume:** scripts precisam de bit de execução e o container do
  usuário certo; validar cedo no setup.
- **Falha ao vivo na demo:** mitigada pelo vídeo de 30 s gravado do fluxo principal.

### Roteiro do pitch (≈2 min40)

1. Grupo + problema (20s): automação de infra eliminando SSH manual.
2. Arquitetura (40s): FastAPI + `subprocess` isolado em Docker, scripts via volume.
3. Vídeo do fluxo funcionando (30s, silencioso, narrado ao vivo): request com token → `.sh`
   rodando no servidor.
4. Diferencial (40s): anti command injection + alerta em tempo real no Discord.
5. Evolução e fechamento (30s): fila assíncrona + UI de gestão; humildade técnica.

---

## 6. Decisão de stack (pendente de OK)

Este PRD adota **Python/FastAPI**, mandatório pela banca, o que **invalida o ADR 0003**
(TypeScript/Next/Fastify) para o escopo do hackathon. Antes de mexer em
`README.md`/`docs/architecture.md`, proponho registrar um **novo ADR** substituindo o 0003.
Não alterado ainda — aguardando aprovação.

## 7. Tarefas

- [ ] Aprovar este PRD e a troca de stack (novo ADR substituindo 0003).
- [ ] Scaffold do serviço Python (FastAPI + estrutura de pastas).
- [ ] Modelo de dados + migrações (scripts, executions, config).
- [ ] Auth `X-Isy-Token` (dependency + rotação).
- [ ] Execução via `subprocess` com whitelist, `shell=False` e timeout.
- [ ] CRUD admin de scripts.
- [ ] Persistência de auditoria em cada execução.
- [ ] Dockerfile leve + volume de scripts + healthcheck.
- [ ] Diferencial: alerta Discord/Telegram.
- [ ] Gravar vídeo de 30s do fluxo principal.
