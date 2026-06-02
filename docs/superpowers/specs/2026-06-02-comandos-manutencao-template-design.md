# Comandos de manutenção por template — Design

Data: 2026-06-02
Branch alvo: `feat/shell-automation-api`

## Contexto e problema

A Isy.One atende centenas de restaurantes parceiros, cada um com um servidor
Linux/Ubuntu rodando o Agente de Impressão iFood em containers Docker. As
manutenções recorrentes — atualizar o agente, limpar logs de cupons antigos,
checar o status dos containers de banco — hoje exigem que o suporte acesse cada
servidor manualmente via SSH e rode shell scripts. Isso gera gargalo operacional.

O objetivo é permitir que o suporte **crie e dispare comandos de manutenção pela
API/console**, sem SSH manual, com a garantia de que cada comando atinge
**exatamente** os containers do restaurante alvo (`isyone-<slug>-*`) e nunca os
de outro cliente.

### Como o CRUD de scripts funciona hoje (ponto de partida)

O CRUD atual é **só metadado**: cadastra um ponteiro, não o script.

1. O console cadastra `nome`, `caminho` (ex.: `cleanup_logs.sh`), `parametros`
   (texto de dica), `descricao`, `categoria`, `ativo`.
2. `POST /api/v1/admin/scripts` -> `script_service.create` valida nome único e
   `resolve_script_path` (anti path-traversal: o caminho tem que cair dentro de
   `scripts_dir`). **Não checa se o arquivo existe.**
3. Na execução, `execution_service.run` faz `path.is_file()`; se faltar, 422.

Consequência: "criar um comando" pelo console gera um registro órfão a menos que
alguém faça deploy do `.sh` em paralelo. O CRUD e o arquivo executável são
desacoplados. Este design fecha esse buraco para uma classe de comandos simples,
mantendo os scripts complexos como helpers curados.

## Decisões tomadas

- **Modelo de autoria:** template com placeholders (não shell livre, não operação
  100% tipada).
- **Texto fixo:** proíbe metacaracteres de shell (`; & | \` $ ( ) { } < > \ " ' * ? [ ]`
  e quebra de encadeamento), mas sem allowlist de binários. Isso elimina
  encadeamento/injeção via texto fixo; um comando destrutivo de linha única ainda
  é possível (aceito — é admin-only).
- **Pipelines** (`pg_dump | gzip`, `find | wc`, `awk`) **não** são expressáveis em
  template. Continuam como **helpers curados** em `/opt/isyone/bin/*` (revisados em
  PR); o template os invoca pelo nome com argumentos tipados.
- **Abordagem A:** template no banco, renderizado server-side e executado pelo
  caminho SSH atual. Coexiste com os `.sh` curados.

## Modelo de dados

Estende `app/models.py::Script`:

- `tipo: str` — `'arquivo'` (default) | `'template'`.
- `template: str | None` — texto do template; obrigatório quando `tipo='template'`.
- `caminho` permanece; obrigatório para `'arquivo'`, vazio/ignorado para `'template'`.

Scripts existentes assumem `tipo='arquivo'` (sem quebra de comportamento).

O schema de parâmetros **não** é persistido: é derivado por parse de
`{{param:NOME:tipo}}` do template, tanto no save quanto na leitura (`ScriptOut`).

Para os scripts exclusivos por cliente reusa-se a coluna **já existente**
`Script.tenant_id` (nullable): `NULL` = script global; `= X` = pertence ao tenant
X. Nenhuma coluna nova. Ver a seção "Scripts exclusivos por cliente".

## Gramática de placeholders

Novo módulo `app/services/template_service.py`. Conjunto fechado e pequeno:

| Placeholder              | Renderiza para                                  | Origem / validação            |
|--------------------------|-------------------------------------------------|-------------------------------|
| `{{slug}}`               | `<slug>`                                         | tenant (`^[a-z0-9-]+$`)       |
| `{{container:db}}`       | `isyone-<slug>-db`                               | role em allowlist             |
| `{{container:odoo}}`     | `isyone-<slug>-odoo`                             | role em allowlist             |
| `{{container:agent}}`    | `isyone-<slug>-ifood-agent`                      | role em allowlist             |
| `{{db}}`                 | `db_<slug com '-' -> '_'>`                       | tenant                        |
| `{{logdir}}`             | `/opt/isyone/clientes/<slug>/logs/cupons`        | tenant                        |
| `{{param:NOME:int}}`     | valor fornecido no run                           | `^[0-9]+$`                    |
| `{{param:NOME:slug}}`    | valor fornecido no run                           | `^[a-z0-9-]+$`                |

Não existe placeholder de container "cru": o nome do container sempre é derivado
do slug do tenant vinculado, no servidor. Essa é a garantia de "exatamente aquele
docker", por construção. Kind/role/tipo desconhecido => erro de validação.

`NOME` de param: `^[a-z][a-z0-9_]*$`. Roles válidos: `db`, `odoo`, `agent`.
Tipos de param válidos: `int`, `slug`.

## Validação no save (`script_service` quando `tipo='template'`)

1. Template não-vazio e dentro de um limite de tamanho (ex.: 2000 chars).
2. Tokeniza em segmentos literais alternados com placeholders `{{...}}`.
3. Cada placeholder tem que casar a gramática (kind/role/tipo conhecidos), senão 422.
4. Cada segmento **literal** só pode conter `[A-Za-z0-9 _.,/=:+-]`. Qualquer outro
   caractere (incluindo os metacaracteres listados) => 422.
5. Deriva a lista de params `[{nome, tipo}]` a partir das ocorrências
   `{{param:...}}`, **deduplicada por nome na ordem de primeira aparição**. Nome
   repetido com tipo divergente => 422. Repetição com o mesmo tipo é permitida: o
   param é declarado uma vez e o valor fornecido é aplicado a todas as ocorrências.

O template é salvo como está. O `parametros_schema` derivado é recomputado na
leitura e devolvido em `ScriptOut` para a UI.

## Render + execução no run (`execution_service`, branch para `tipo='template'`)

1. **Re-valida** o template (defense in depth — nunca confia cegamente no dado
   persistido).
2. Resolve `{{slug}}`, `{{container:*}}`, `{{db}}`, `{{logdir}}` **a partir do
   tenant vinculado** (`tenant.slug`), nunca do input do chamador. Preserva o
   isolamento cross-tenant já corrigido em `_effective_params`.
3. Para cada param declarado (lista deduplicada por nome, na ordem de primeira
   aparição), pega o valor correspondente da lista `parametros` por posição e
   valida pelo tipo. Quantidade insuficiente de valores ou tipo inválido => 422.
4. Renderiza a string final e aplica a **rede de segurança**: a string tem que
   casar `^[A-Za-z0-9 _.,/=:+-]+$`. Se não casar, aborta (não executa).
5. Executa:
   - **Remoto** (`tenant.ssh_host` setado): `_ssh.sh "<string renderizada>"`,
     rodando no host do cliente como usuário `isyone`. Como a string é livre de
     metacaracteres, a interpolação no comando SSH é segura; `_ssh.sh` não muda.
   - **Local** (demo, sem `ssh_host`): execução **simulada** (echo do comando
     renderizado + status de sucesso canônico), espelhando como os `.sh` atuais se
     comportam sem `ISY_SSH_HOST`. Nada de `docker` arbitrário no host da API.
6. Mesmo pipeline de evento (`ExecutionCompleted`), timeout (`exec_timeout`) e
   limite de saída (`output_limit`). Auditoria registra os params efetivos.

Um renderizador compartilhado em `template_service` é usado tanto por `run` quanto
por `stream_script`.

## API / schemas (`app/schemas.py`)

- `ScriptCreate` / `ScriptUpdate` ganham `tipo: str` e `template: str | None`.
  `caminho` vira opcional; validação cruzada: `tipo='arquivo'` exige `caminho`,
  `tipo='template'` exige `template`.
- `ScriptOut` ganha `tipo`, `template` e `parametros_schema: list[{nome, tipo}]`
  (derivado).
- `RunRequest` permanece `parametros: list[str]` — valores na ordem dos params
  declarados pelo template. O backend mapeia posicionalmente.

## UI (`app/static/index.html`)

- Modal de script: toggle **Tipo** (Arquivo / Template).
  - Arquivo: campo "Arquivo (.sh no volume)" atual.
  - Template: textarea do template + legenda dos placeholders disponíveis + chips
    mostrando os params derivados ao digitar.
- Drawer do cliente (run): quando o script vinculado é `tipo='template'` e declara
  params, renderiza inputs tipados (number para `int`) no lugar da caixinha única
  de parâmetros. Sem params declarados => botão executa direto.
- Tabela de auditoria: sem mudança (já exibe `parametros`).
- Todo dado dinâmico continua passando por `esc()` (sem regressão de XSS).

## Scripts exclusivos por cliente (tenant-owned)

Um script pode pertencer a um cliente específico: a definição (incluindo template)
é criada **para** aquele cliente e só ele (e o admin) a vê e executa. Reusa
`Script.tenant_id`.

- **Criação:** `ScriptCreate` ganha `tenant_id: int | None` (default `None` =
  global). Quando setado:
  1. valida que o tenant existe (404 senão);
  2. cria o `Script` com `tenant_id = X`;
  3. **auto-cria o binding** (`tenant_scripts`) para X — `ativo=True` e
     `parametros_default=""` (o valor é fornecido no run, igual ao auto-bind do
     `registro`) — reusando o caminho de listagem/run/authz existente sem fluxo
     novo.

- **Ownership guard (regra de segurança):** em `bind_script` e em qualquer criação
  de binding, se `script.tenant_id` não é `NULL`, o binding só é permitido para o
  **tenant dono**; vincular a outro tenant => 403. O auto-bind do `registro` usa
  `scripts_repo.list_global` (só `tenant_id IS NULL`), então scripts owned de um
  cliente nunca vazam para outro. Combinado com `verify_tenant` (caller = tenant ou
  admin) e o check de binding em `run_script`, um script owned por X só é
  executável por X ou pelo admin.

- **Listagem:**
  - Admin `GET /api/v1/admin/scripts` (`list_all`) devolve tudo; `ScriptOut` inclui
    `tenant_id` para a UI rotular o dono.
  - Drawer do cliente: `tenant_scripts_repo.list_active_scripts` já devolve os
    bindings; com o auto-bind, o script owned aparece naturalmente.

- **Imutabilidade:** o dono é definido na criação e **não** pode ser alterado por
  update (YAGNI — evita binding inconsistente). Demais campos são editáveis. O
  `nome` continua globalmente único (constraint atual da coluna).

- **Cascade na exclusão de tenant:** `tenants_repo.delete` hoje apaga `Event` e
  `TenantScript` do tenant, mas **não** os scripts owned. Passa a apagar também
  `Script` com `tenant_id == X`, na ordem: eventos -> bindings -> scripts owned ->
  tenant (sem deixar FK órfã).

- **Composição:** ortogonal ao `tipo`. Um script owned pode ser `arquivo` ou
  `template`; "comando bespoke de um restaurante" = owned + template.

### Impacto nos schemas (consolidado)

- `ScriptCreate`: `tipo`, `template`, `tenant_id` (todos novos); `caminho` opcional.
- `ScriptUpdate`: `tipo`, `template` editáveis; `tenant_id` **ignorado** (dono
  imutável).
- `ScriptOut`: `tipo`, `template`, `tenant_id`, `parametros_schema`.

### Impacto na UI (consolidado)

- Modal de script: toggle **Tipo** (Arquivo/Template) + seletor **Dono**
  (Global / cliente específico, dropdown de `state.tenants`).
- Tabela de scripts: coluna **Dono** (Global ou nome do cliente).

## Testes

- **Parser** (`template_service`): placeholders válidos/inválidos; rejeição de cada
  metacaractere proibido; derivação correta de params; nome de param inválido.
- **Render**: scoping do tenant -> container correto (`isyone-<slug>-<role>`);
  validação de tipo de param (int/slug); assert final de metachar.
- **Segurança**:
  - Container não é forçável a outro tenant (não há placeholder de container cru;
    slug vem só do tenant).
  - Literal com `;`, `|`, `$()`, backtick, `>` rejeitado no save.
  - Param de tipo errado (`int` recebendo `abc`) rejeitado no run.
  - String renderizada com metacaractere (não deveria ocorrer) é barrada pelo
    assert final.
  - **Ownership:** binding de um script owned por X para o tenant Y => 403;
    tenant Y não vê nem executa o script owned por X; `registro` não vincula
    scripts owned a novos tenants.
  - **Cascade:** ao apagar o tenant X, seus scripts owned são removidos (sem FK
    órfã).
- **Rota**: criar script template -> bind a um tenant -> run (modo local
  simulado) -> evento `ExecutionCompleted` gravado com os params efetivos. Criar
  script owned (tenant_id) -> auto-bind -> run pelo dono ok.

## Fora de escopo (YAGNI)

- Pipelines / redirecionamento em template (ficam como helpers curados).
- Upload de `.sh` arbitrário.
- Tipos de param além de `int` e `slug`.
- Versionamento / histórico de templates.

## Migração

`init_db` usa `create_all`, que **não** adiciona colunas a uma tabela já existente.
Como o seed só roda em banco vazio, o caminho limpo para a demo é recriar o banco
no deploy. Se for necessário preservar dados existentes, adicionar no `init_db` um
passo idempotente leve:

```sql
ALTER TABLE scripts ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'arquivo';
ALTER TABLE scripts ADD COLUMN template TEXT;
```

executado dentro de um try/except que ignora "coluna já existe" (SQLite não tem
`ADD COLUMN IF NOT EXISTS`). Decisão padrão para a demo: recriar o banco; o
`ALTER TABLE` fica documentado como alternativa se houver dados a preservar.
