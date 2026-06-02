# Comandos de manutenção por template — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir cadastrar comandos de manutenção como templates parametrizados (e como scripts exclusivos de um cliente), executados via API com substituição segura amarrada ao container do tenant certo.

**Architecture:** Estende o `Script` com `tipo` (`arquivo`|`template`) + `template`, e reusa `Script.tenant_id` para scripts donos-de-cliente. Um módulo novo `template_service` faz parse, validação (sem metacaracteres de shell) e render seguro a partir do tenant vinculado. O `execution_service` ganha um branch de template que executa via o `_ssh.sh` existente (remoto) ou simula (local). O isolamento cross-tenant é preservado: slug/container vêm sempre do tenant, nunca do input.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Pydantic v2, pytest. Spec: `docs/superpowers/specs/2026-06-02-comandos-manutencao-template-design.md`.

**Commits:** O usuário pediu para **não commitar sem autorização**. Trate os passos "Commit" como checkpoints — execute-os só quando ele autorizar (ou agrupe no fim). Mensagens no imperativo, sem atribuição de IA.

**Verificação geral:** rode a suíte com `.venv/bin/python -m pytest -q`.

---

## File Structure

- **Create** `app/services/template_service.py` — parse, validação e render de templates (puro, sem DB).
- **Create** `tests/test_template_service.py` — testes unitários do módulo acima.
- **Modify** `app/models.py` — colunas `tipo` e `template` em `Script`.
- **Modify** `app/schemas.py` — `tipo`/`template`/`tenant_id` em ScriptCreate/Update/Out + validação cruzada.
- **Modify** `app/services/script_service.py` — validação de template, dono (tenant_id) e auto-bind.
- **Modify** `app/repositories/tenants_repo.py` — cascade dos scripts owned no delete de tenant.
- **Modify** `app/routes/admin.py` — ownership guard no `bind_script`; `_script_out` inclui `parametros_schema`.
- **Modify** `app/routes/tenants.py` — `list_scripts` devolve `tipo` e `parametros_schema`.
- **Modify** `app/services/execution_service.py` — branch de template no `run` + helper `_record`.
- **Modify** `app/static/index.html` — toggle Tipo, seletor Dono, coluna Dono, inputs tipados no run.
- **Modify** `tests/test_admin_routes.py`, `tests/test_execution_service.py`, `tests/test_tenants_repo.py` — novos testes.

---

## Task 1: template_service — parse e validação

**Files:**
- Create: `app/services/template_service.py`
- Test: `tests/test_template_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template_service.py
import pytest

from app.services import template_service as ts


def test_validate_aceita_placeholders_conhecidos():
    ts.validate("docker restart {{container:agent}} {{slug}}")
    ts.validate("find {{logdir}} -mtime +{{param:dias:int}} -delete")


def test_validate_rejeita_placeholder_desconhecido():
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{container:web}}")
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{nao_existe}}")
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{param:x:float}}")


def test_validate_rejeita_metacaractere_no_texto_fixo():
    for ruim in [
        "docker restart {{container:agent}}; rm -rf /",
        "echo {{slug}} && reboot",
        "cat {{logdir}} | sh",
        "echo $(id) {{slug}}",
        "echo `id`",
        "echo {{slug}} > /etc/x",
    ]:
        with pytest.raises(ts.TemplateError):
            ts.validate(ruim)


def test_validate_rejeita_vazio():
    with pytest.raises(ts.TemplateError):
        ts.validate("   ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_template_service.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.template_service'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/template_service.py
"""Parse, validacao e render seguro de templates de comando de manutencao.

Um template e uma linha de comando com placeholders tipados. O texto literal nao
pode conter metacaracteres de shell; os placeholders sao resolvidos a partir do
tenant vinculado (slug/container/db/logdir) ou de parametros tipados fornecidos no
run. O resultado e uma string livre de metacaracteres -- segura para interpolar no
comando SSH remoto -- e nunca executa nada por conta propria.
"""

import re

# Conjunto permitido em segmentos literais e na string final renderizada. Exclui
# todos os metacaracteres de shell (; & | ` $ ( ) { } < > \\ " ' * ? [ ]).
_SAFE_CHARS = r"A-Za-z0-9 _.,/=:+-"
_LITERAL_RE = re.compile(rf"^[{_SAFE_CHARS}]*$")
_RENDERED_RE = re.compile(rf"^[{_SAFE_CHARS}]+$")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_PARAM_RE = re.compile(r"^param:([a-z][a-z0-9_]*):(int|slug)$")

_CONTAINER_ROLES = {"db": "db", "odoo": "odoo", "agent": "ifood-agent"}
_PARAM_VALIDADORES = {
    "int": re.compile(r"^[0-9]+$"),
    "slug": re.compile(r"^[a-z0-9-]+$"),
}
_MAX_LEN = 2000


class TemplateError(ValueError):
    """Template invalido ou valor de parametro fora do tipo declarado."""


def _check_placeholder(inner: str) -> None:
    if inner in ("slug", "db", "logdir"):
        return
    if inner.startswith("container:"):
        role = inner.split(":", 1)[1]
        if role not in _CONTAINER_ROLES:
            raise TemplateError(f"Container invalido: '{role}'.")
        return
    if _PARAM_RE.match(inner):
        return
    raise TemplateError(f"Placeholder invalido: '{{{{{inner}}}}}'.")


def validate(template: str | None) -> None:
    """Valida tamanho, placeholders conhecidos e literais sem metacaractere."""
    if not template or not template.strip():
        raise TemplateError("Template vazio.")
    if len(template) > _MAX_LEN:
        raise TemplateError(f"Template excede {_MAX_LEN} caracteres.")
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        if not _LITERAL_RE.match(template[pos : m.start()]):
            raise TemplateError("Texto fixo contem caractere proibido.")
        _check_placeholder(m.group(1))
        pos = m.end()
    if not _LITERAL_RE.match(template[pos:]):
        raise TemplateError("Texto fixo contem caractere proibido.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_template_service.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add app/services/template_service.py tests/test_template_service.py
git commit -m "feat: parse e validacao de templates de comando"
```

---

## Task 2: template_service — extract_params e render

**Files:**
- Modify: `app/services/template_service.py`
- Test: `tests/test_template_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template_service.py  (acrescente ao final)
from types import SimpleNamespace


def _tenant(slug="tux-burger"):
    return SimpleNamespace(slug=slug, ssh_host=None)


def test_extract_params_dedup_por_nome_em_ordem():
    params = ts.extract_params("a {{param:dias:int}} {{slug}} {{param:dias:int}}")
    assert params == [{"nome": "dias", "tipo": "int"}]


def test_extract_params_tipo_conflitante():
    with pytest.raises(ts.TemplateError):
        ts.extract_params("{{param:x:int}} {{param:x:slug}}")


def test_render_resolve_container_do_tenant():
    out = ts.render("docker restart {{container:agent}}", _tenant(), [])
    assert out == "docker restart isyone-tux-burger-ifood-agent"


def test_render_db_e_logdir():
    assert ts.render("{{db}}", _tenant("tux-burger"), []) == "db_tux_burger"
    assert ts.render("{{logdir}}", _tenant("tux-burger"), []) == (
        "/opt/isyone/clientes/tux-burger/logs/cupons"
    )


def test_render_valida_param_int():
    assert ts.render("limpa {{param:dias:int}}", _tenant(), ["30"]) == "limpa 30"
    with pytest.raises(ts.TemplateError):
        ts.render("limpa {{param:dias:int}}", _tenant(), ["abc"])


def test_render_faltando_valor():
    with pytest.raises(ts.TemplateError):
        ts.render("limpa {{param:dias:int}}", _tenant(), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_template_service.py -q`
Expected: FAIL com `AttributeError: module ... has no attribute 'extract_params'`.

- [ ] **Step 3: Write minimal implementation**

Acrescente ao final de `app/services/template_service.py`:

```python
def extract_params(template: str) -> list[dict]:
    """Params {nome, tipo} deduplicados por nome, na ordem de primeira aparicao."""
    params: list[dict] = []
    vistos: dict[str, str] = {}
    for m in _PLACEHOLDER_RE.finditer(template):
        pm = _PARAM_RE.match(m.group(1))
        if not pm:
            continue
        nome, tipo = pm.group(1), pm.group(2)
        if nome in vistos:
            if vistos[nome] != tipo:
                raise TemplateError(f"Parametro '{nome}' com tipos divergentes.")
            continue
        vistos[nome] = tipo
        params.append({"nome": nome, "tipo": tipo})
    return params


def _db_name(slug: str) -> str:
    return "db_" + slug.replace("-", "_")


def render(template: str, tenant, valores: list[str]) -> str:
    """Renderiza o template para uma string segura, resolvendo placeholders.

    Tenant (slug/container/db/logdir) vem do tenant vinculado; params vem de
    `valores` (posicional, na ordem declarada). Levanta TemplateError em qualquer
    inconsistencia.
    """
    validate(template)
    params = extract_params(template)
    if len(valores) < len(params):
        raise TemplateError(
            f"Faltam parametros: esperado {len(params)}, recebido {len(valores)}."
        )
    valor_por_nome: dict[str, str] = {}
    for i, p in enumerate(params):
        valor = valores[i]
        if not _PARAM_VALIDADORES[p["tipo"]].match(valor):
            raise TemplateError(
                f"Parametro '{p['nome']}' invalido para tipo {p['tipo']}: '{valor}'."
            )
        valor_por_nome[p["nome"]] = valor

    def _sub(m: "re.Match") -> str:
        inner = m.group(1)
        if inner == "slug":
            return tenant.slug
        if inner == "db":
            return _db_name(tenant.slug)
        if inner == "logdir":
            return f"/opt/isyone/clientes/{tenant.slug}/logs/cupons"
        if inner.startswith("container:"):
            role = inner.split(":", 1)[1]
            return f"isyone-{tenant.slug}-{_CONTAINER_ROLES[role]}"
        return valor_por_nome[_PARAM_RE.match(inner).group(1)]

    rendered = _PLACEHOLDER_RE.sub(_sub, template).strip()
    if not _RENDERED_RE.match(rendered):
        raise TemplateError("Comando renderizado contem caractere inesperado.")
    return rendered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_template_service.py -q`
Expected: PASS (10 testes).

- [ ] **Step 5: Commit**

```bash
git add app/services/template_service.py tests/test_template_service.py
git commit -m "feat: render seguro de templates com params tipados"
```

---

## Task 3: Modelo + schemas (tipo, template, tenant_id)

**Files:**
- Modify: `app/models.py:23-37` (classe `Script`)
- Modify: `app/schemas.py:8-36` (Script schemas)
- Test: `tests/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin_routes.py  (acrescente ao final)
from tests.conftest import AUTH  # ja importado no topo; ignore se duplicar


def test_criar_script_template(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "reinicia-agente",
            "tipo": "template",
            "template": "docker restart {{container:agent}}",
            "categoria": "update",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["tipo"] == "template"


def test_criar_script_template_sem_corpo_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "x", "tipo": "template", "categoria": "update"},
    )
    assert r.status_code == 422


def test_criar_script_arquivo_sem_caminho_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "y", "tipo": "arquivo", "categoria": "other"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: FAIL (criar template retorna 422 porque `tipo`/`template` ainda não existem / 500).

- [ ] **Step 3: Write minimal implementation**

Em `app/models.py`, dentro de `class Script`, logo após a coluna `caminho` (linha 29) acrescente:

```python
    tipo: Mapped[str] = mapped_column(String(20), default="arquivo")
    template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

Em `app/schemas.py`, troque o import e os três schemas de Script:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScriptCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    caminho: str = Field(default="", max_length=255)
    template: str | None = Field(default=None, max_length=2000)
    tipo: str = "arquivo"
    parametros: str = Field(default="", max_length=255)
    descricao: str = Field(default="", max_length=255)
    categoria: str = "other"
    tenant_id: int | None = None
    ativo: bool = True

    @model_validator(mode="after")
    def _coerente(self) -> "ScriptCreate":
        if self.tipo not in ("arquivo", "template"):
            raise ValueError("tipo deve ser 'arquivo' ou 'template'.")
        if self.tipo == "arquivo" and not self.caminho:
            raise ValueError("caminho e obrigatorio para tipo 'arquivo'.")
        if self.tipo == "template" and not (self.template and self.template.strip()):
            raise ValueError("template e obrigatorio para tipo 'template'.")
        return self


class ScriptUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    caminho: str | None = Field(default=None, max_length=255)
    template: str | None = Field(default=None, max_length=2000)
    tipo: str | None = None
    parametros: str | None = Field(default=None, max_length=255)
    descricao: str | None = Field(default=None, max_length=255)
    categoria: str | None = None
    ativo: bool | None = None


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    caminho: str
    template: str | None
    tipo: str
    parametros: str
    descricao: str
    categoria: str
    tenant_id: int | None
    ativo: bool
    criado_em: datetime
    parametros_schema: list[dict] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: PASS (incluindo os 3 novos). `tipo='template'` válido cria 201.

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/schemas.py tests/test_admin_routes.py
git commit -m "feat: campos tipo/template/tenant_id no script"
```

---

## Task 4: script_service — validação de template, dono e auto-bind

**Files:**
- Modify: `app/services/script_service.py`
- Test: `tests/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin_routes.py  (acrescente ao final)
def test_script_owned_auto_bind_aparece_no_cliente(client):
    assert _criar_tenant(client, slug="tux-burger", porta=8201).status_code == 201
    # descobre o id do tenant
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "tux-burger"
    )
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "bespoke-tux",
            "tipo": "template",
            "template": "docker ps {{container:db}}",
            "categoria": "status",
            "tenant_id": tid,
        },
    )
    assert r.status_code == 201, r.text
    # o cliente ja enxerga o script (auto-bind)
    lst = client.get("/api/v1/tenants/tux-burger/scripts", headers=AUTH).json()["data"]
    assert any(s["nome"] == "bespoke-tux" for s in lst)


def test_script_owned_tenant_inexistente_falha(client):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "orfao",
            "tipo": "template",
            "template": "echo {{slug}}",
            "categoria": "other",
            "tenant_id": 99999,
        },
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: FAIL (sem auto-bind o script não aparece; tenant inexistente não é checado).

- [ ] **Step 3: Write minimal implementation**

Substitua `app/services/script_service.py` por:

```python
"""Regra de negocio do CRUD de scripts e validacao de caminho/template."""

from sqlalchemy.orm import Session

from app.core.security import ScriptPathError, resolve_script_path
from app.models import Script
from app.repositories import scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, ScriptUpdate
from app.services import template_service


class ScriptValidationError(ValueError):
    """Dados de script invalidos (nome duplicado, caminho/template/dono invalido)."""


def _validate_caminho(caminho: str) -> None:
    try:
        resolve_script_path(caminho)
    except ScriptPathError as exc:
        raise ScriptValidationError(str(exc)) from exc


def _validate_template(template: str | None) -> None:
    try:
        template_service.validate(template)
    except template_service.TemplateError as exc:
        raise ScriptValidationError(str(exc)) from exc


def create(db: Session, data: ScriptCreate) -> Script:
    if scripts_repo.get_by_nome(db, data.nome):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    if data.tipo == "template":
        _validate_template(data.template)
    else:
        _validate_caminho(data.caminho)
    if data.tenant_id is not None and tenants_repo.get(db, data.tenant_id) is None:
        raise ScriptValidationError("Tenant dono nao encontrado.")
    script = scripts_repo.create(db, data)
    # Script dono-de-cliente fica disponivel para esse cliente via binding ativo.
    if script.tenant_id is not None:
        tenant_scripts_repo.upsert(db, script.tenant_id, script.id, "", True)
    return script


def update(db: Session, script: Script, data: ScriptUpdate) -> Script:
    if (
        data.nome
        and data.nome != script.nome
        and scripts_repo.get_by_nome(db, data.nome)
    ):
        raise ScriptValidationError(f"Ja existe script com nome '{data.nome}'.")
    # Dono (tenant_id) e imutavel apos a criacao: ScriptUpdate nao o expoe.
    tipo_final = data.tipo or script.tipo
    if tipo_final == "template":
        template_final = data.template if data.template is not None else script.template
        _validate_template(template_final)
    elif data.caminho is not None:
        _validate_caminho(data.caminho)
    return scripts_repo.update(db, script, data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: PASS (auto-bind aparece; tenant inexistente → 422).

- [ ] **Step 5: Commit**

```bash
git add app/services/script_service.py tests/test_admin_routes.py
git commit -m "feat: validacao de template, dono e auto-bind no script_service"
```

---

## Task 5: Ownership guard no bind + parametros_schema na saída

**Files:**
- Modify: `app/routes/admin.py:39-41` (`_script_out`) e `:103-118` (`bind_script`)
- Test: `tests/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin_routes.py  (acrescente ao final)
def test_bind_script_owned_em_outro_cliente_403(client):
    _criar_tenant(client, slug="dono", porta=8301)
    _criar_tenant(client, slug="intruso", porta=8302)
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "dono"
    )
    sid = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "so-do-dono",
            "tipo": "template",
            "template": "docker ps {{container:db}}",
            "categoria": "status",
            "tenant_id": tid,
        },
    ).json()["data"]["id"]
    r = client.put(
        "/api/v1/admin/tenants/intruso/scripts",
        headers=AUTH,
        json={"script_id": sid, "parametros_default": "", "ativo": True},
    )
    assert r.status_code == 403


def test_list_global_exclui_scripts_owned(client):
    # Garante que o auto-bind do self-service (que usa list_global) nunca vincula
    # scripts exclusivos de outro cliente a um novo tenant.
    from app.core.db import SessionLocal
    from app.repositories import scripts_repo

    _criar_tenant(client, slug="dono2", porta=8311)
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "dono2"
    )
    client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": "global-x", "caminho": "cleanup_logs.sh", "categoria": "cleanup"},
    )
    client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "owned-x",
            "tipo": "template",
            "template": "echo {{slug}}",
            "categoria": "other",
            "tenant_id": tid,
        },
    )
    with SessionLocal() as db:
        nomes = {s.nome for s in scripts_repo.list_global(db)}
    assert "global-x" in nomes
    assert "owned-x" not in nomes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py::test_bind_script_owned_em_outro_cliente_403 -q`
Expected: FAIL (bind retorna 200 hoje).

- [ ] **Step 3: Write minimal implementation**

Em `app/routes/admin.py`, adicione o import de `template_service` na linha de imports de services:

```python
from app.services import execution_service, health_service, script_service, template_service
```

Troque `_script_out` (linhas 39-40):

```python
def _script_out(s) -> dict:
    out = ScriptOut.model_validate(s).model_dump(mode="json")
    out["parametros_schema"] = (
        template_service.extract_params(s.template)
        if s.tipo == "template" and s.template
        else []
    )
    return out
```

Na função `bind_script`, troque o bloco que valida o script (atualmente
`if scripts_repo.get(db, body.script_id) is None: ...`) por:

```python
    script = scripts_repo.get(db, body.script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    if script.tenant_id is not None and script.tenant_id != tenant.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Script pertence a outro cliente."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: PASS (bind cross-owner → 403).

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin.py tests/test_admin_routes.py
git commit -m "feat: ownership guard no bind e parametros_schema na saida"
```

---

## Task 6: execution_service — branch de template no run

**Files:**
- Modify: `app/services/execution_service.py`
- Test: `tests/test_execution_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_execution_service.py  (acrescente ao final)
from app.schemas import ScriptCreate as _SC  # alias para clareza


def test_run_template_local_simulado_grava_evento(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="tux-burger",
                nome="Tux",
                dominio="tux.isy.one",
                porta=8201,
                db_name="db_tux_burger",
                token="tok-tux-aaaaaa",
            ),
        )
        s = scripts_repo.create(
            db,
            _SC(
                nome="reinicia",
                tipo="template",
                template="docker restart {{container:agent}}",
                categoria="update",
            ),
        )
        event = execution_service.run(db, t, s, [])
        assert event.payload["status"] == "sucesso"
        assert "isyone-tux-burger-ifood-agent" in event.payload["stdout"]


def test_run_template_param_invalido_levanta(client):
    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="c2",
                nome="C2",
                dominio="c2.isy.one",
                porta=8202,
                db_name="db_c2",
                token="tok-c2-aaaaaa",
            ),
        )
        s = scripts_repo.create(
            db,
            _SC(
                nome="limpa",
                tipo="template",
                template="cleanup {{param:dias:int}}",
                categoria="cleanup",
            ),
        )
        with pytest.raises(execution_service.ScriptNotExecutable):
            execution_service.run(db, t, s, ["abc"])
```

Garanta que o topo do arquivo tem `import pytest` (acrescente se faltar).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_execution_service.py -q`
Expected: FAIL (run trata o template como arquivo e não acha o .sh → ScriptNotExecutable no caso de sucesso).

- [ ] **Step 3: Write minimal implementation**

Em `app/services/execution_service.py`, adicione `template_service` ao import de
services:

```python
from app.services import alert_service, template_service
```

Acrescente o helper `_record` e `_run_template` (antes da função `run`):

```python
def _record(
    db: Session,
    tenant: Tenant,
    script: Script,
    parametros: list[str],
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    duracao_ms: int,
) -> Event:
    payload = {
        "script_nome": script.nome,
        "categoria": script.categoria,
        "parametros": " ".join(parametros),
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout[: settings.output_limit],
        "stderr": stderr[: settings.output_limit],
        "duracao_ms": duracao_ms,
    }
    event = events_repo.append(
        db, ev.EXECUTION_COMPLETED, payload, tenant_id=tenant.id, script_id=script.id
    )
    if status == "falha":
        alert_service.notify_failure(tenant.slug, payload)
    return event


def _run_template(
    tenant: Tenant, script: Script, valores: list[str]
) -> tuple[str, str, str, int | None]:
    """Renderiza e executa um template. Remoto via _ssh.sh; local simulado."""
    rendered = template_service.render(script.template, tenant, valores)
    if tenant.ssh_host:
        ssh = resolve_script_path("_ssh.sh")
        proc = subprocess.run(
            [str(ssh), rendered],
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
            env=_build_env(tenant),
        )
        status = "sucesso" if proc.returncode == 0 else "falha"
        return status, proc.stdout, proc.stderr, proc.returncode
    return "sucesso", f"[local simulado] {rendered}\nOK (simulado).", "", 0
```

Substitua a função `run` inteira por:

```python
def run(db: Session, tenant: Tenant, script: Script, parametros: list[str]) -> Event:
    if script.tipo == "template":
        started = time.perf_counter()
        try:
            status, stdout, stderr, exit_code = _run_template(tenant, script, parametros)
        except template_service.TemplateError as exc:
            raise ScriptNotExecutable(str(exc)) from exc
        except subprocess.TimeoutExpired:
            status, stdout, stderr, exit_code = (
                "falha",
                "",
                f"Tempo limite de {settings.exec_timeout}s excedido.",
                None,
            )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        return _record(
            db, tenant, script, parametros, status, stdout, stderr, exit_code, duracao_ms
        )

    try:
        path = resolve_script_path(script.caminho)
    except ScriptPathError as exc:
        raise ScriptNotExecutable(str(exc)) from exc
    if not path.is_file():
        raise ScriptNotExecutable(f"Arquivo do script nao encontrado: {script.caminho}")

    parametros = _effective_params(tenant, script, parametros)
    argv = [str(path), *parametros]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
            check=False,
            env=_build_env(tenant),
        )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status = "sucesso" if proc.returncode == 0 else "falha"
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status, exit_code = "falha", None
        stdout, stderr = "", f"Tempo limite de {settings.exec_timeout}s excedido."
    return _record(
        db, tenant, script, parametros, status, stdout, stderr, exit_code, duracao_ms
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_execution_service.py -q`
Expected: PASS (template local simulado grava evento; param inválido levanta).

- [ ] **Step 5: Commit**

```bash
git add app/services/execution_service.py tests/test_execution_service.py
git commit -m "feat: execucao de scripts template (render seguro + sim local)"
```

---

## Task 7: Cascade de scripts owned no delete de tenant

**Files:**
- Modify: `app/repositories/tenants_repo.py:7` (import) e `:44-50` (`delete`)
- Test: `tests/test_tenants_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenants_repo.py  (acrescente ao final)
from app.repositories import scripts_repo as _scripts_repo
from app.schemas import ScriptCreate as _ScriptCreate


def test_delete_tenant_remove_scripts_owned(client):
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        t = tenants_repo.create(
            db,
            TenantCreate(
                slug="dono-del",
                nome="Dono",
                dominio="dono.isy.one",
                porta=8401,
                db_name="db_dono",
                token="tok-dono-aaaaaa",
            ),
        )
        s = _scripts_repo.create(
            db,
            _ScriptCreate(
                nome="owned-del",
                tipo="template",
                template="echo {{slug}}",
                categoria="other",
                tenant_id=t.id,
            ),
        )
        sid = s.id
        tenants_repo.delete(db, t)
        assert _scripts_repo.get(db, sid) is None
```

Confira os imports já presentes no topo de `tests/test_tenants_repo.py`
(`tenants_repo`, `TenantCreate`); acrescente os que faltarem.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tenants_repo.py -q`
Expected: FAIL (script owned permanece após o delete).

- [ ] **Step 3: Write minimal implementation**

Em `app/repositories/tenants_repo.py`, troque o import de models (linha 7):

```python
from app.models import Event, Script, Tenant, TenantScript
```

E na função `delete`, acrescente a remoção dos scripts owned **antes** de
`db.delete(tenant)`:

```python
def delete(db: Session, tenant: Tenant) -> None:
    # Remove dependentes antes do tenant (FKs sem ON DELETE CASCADE):
    # eventos, bindings e scripts exclusivos do cliente.
    db.execute(sa_delete(Event).where(Event.tenant_id == tenant.id))
    db.execute(sa_delete(TenantScript).where(TenantScript.tenant_id == tenant.id))
    db.execute(sa_delete(Script).where(Script.tenant_id == tenant.id))
    db.delete(tenant)
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tenants_repo.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/repositories/tenants_repo.py tests/test_tenants_repo.py
git commit -m "fix: delete de tenant remove scripts exclusivos do cliente"
```

---

## Task 8: Rota do cliente expõe tipo e parametros_schema

**Files:**
- Modify: `app/routes/tenants.py:17-32` (`list_scripts`)
- Test: `tests/test_tenant_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenant_routes.py  (acrescente; use o helper de criacao ja existente
# no arquivo, ou crie tenant+script via API admin como abaixo)
from tests.conftest import AUTH


def test_list_scripts_expoe_tipo_e_params(client):
    client.post(
        "/api/v1/admin/tenants",
        headers=AUTH,
        json={
            "slug": "tux-burger",
            "nome": "Tux",
            "dominio": "tux.isy.one",
            "porta": 8201,
            "db_name": "db_tux_burger",
            "token": "tok-tux-aaaaaa",
        },
    )
    tid = next(
        t["id"]
        for t in client.get("/api/v1/admin/tenants", headers=AUTH).json()["data"]
        if t["slug"] == "tux-burger"
    )
    client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={
            "nome": "limpa-cupons",
            "tipo": "template",
            "template": "cleanup {{param:dias:int}}",
            "categoria": "cleanup",
            "tenant_id": tid,
        },
    )
    data = client.get("/api/v1/tenants/tux-burger/scripts", headers=AUTH).json()["data"]
    item = next(s for s in data if s["nome"] == "limpa-cupons")
    assert item["tipo"] == "template"
    assert item["parametros_schema"] == [{"nome": "dias", "tipo": "int"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tenant_routes.py::test_list_scripts_expoe_tipo_e_params -q`
Expected: FAIL com `KeyError: 'tipo'`.

- [ ] **Step 3: Write minimal implementation**

Em `app/routes/tenants.py`, acrescente ao import de services:

```python
from app.services import execution_service, health_service, template_service
```

Na função `list_scripts`, troque o list-comprehension `data` por:

```python
    data = [
        {
            "script_id": s.id,
            "nome": s.nome,
            "categoria": s.categoria,
            "descricao": s.descricao,
            "tipo": s.tipo,
            "parametros_default": b.parametros_default,
            "parametros_schema": (
                template_service.extract_params(s.template)
                if s.tipo == "template" and s.template
                else []
            ),
        }
        for s, b in disponiveis
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tenant_routes.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/tenants.py tests/test_tenant_routes.py
git commit -m "feat: rota do cliente expoe tipo e schema de parametros"
```

---

## Task 9: UI — toggle Tipo, seletor Dono, coluna Dono, inputs tipados

**Files:**
- Modify: `app/static/index.html` (seções Scripts CRUD e drawer do cliente)

Sem teste automatizado (HTML/JS estático). Verificação manual no fim.

- [ ] **Step 1: Coluna Dono na tabela de scripts**

Em `loadScripts` (linha ~391), troque a linha do `caminho`/categoria para incluir
o dono. Substitua o template da `<tr>` por:

```javascript
        $("scripts-body").innerHTML = data.map(s => `
          <tr>
            <td><strong>${esc(s.nome)}</strong></td>
            <td class="mono" style="font-size:12px">${s.tipo === "template" ? esc(s.template || "") : esc(s.caminho)}</td>
            <td class="muted">${esc((s.parametros_schema||[]).map(p=>p.nome).join(", ") || s.parametros || '—')}</td>
            <td class="muted">${esc(s.descricao||'—')}</td>
            <td><span class="badge neutral">${esc(s.categoria)}</span></td>
            <td class="muted">${s.tenant_id ? esc((state.tenants.find(t=>t.id===s.tenant_id)||{}).nome || ("#"+s.tenant_id)) : "Global"}</td>
            <td><label class="switch"><input type="checkbox" ${s.ativo?'checked':''} onchange="toggleScript(${s.id}, this.checked)"><span class="slider"></span></label></td>
            <td><button class="btn ghost sm" onclick='openScript(${s.id})'>Editar</button></td>
          </tr>`).join("") || `<tr><td colspan="8" class="empty">Catálogo vazio.</td></tr>`;
```

Atualize o cabeçalho da tabela (linha 171) para incluir a coluna **Dono** entre
`Categoria` e `Ativo`:

```html
        <thead><tr><th>Nome</th><th>Arquivo/Template</th><th>Parâmetros</th><th>Descrição</th><th>Categoria</th><th>Dono</th><th>Ativo</th><th></th></tr></thead>
```

`state.tenants` é populado por `loadClientes()` (aba Clientes). Para garantir que a
aba Scripts tenha os nomes dos donos, faça `loadScripts` carregar os clientes antes
se ainda não houver. No início de `loadScripts` (linha ~389), acrescente:

```javascript
      if (!state.tenants.length) { try { await loadClientes(); } catch (_) {} }
```

- [ ] **Step 2: Toggle Tipo + seletor Dono no modal**

Substitua o corpo de `openScript` (linhas ~405-413) por:

```javascript
      const tenantsOpts = ['<option value="">Global</option>']
        .concat(state.tenants.map(t => `<option value="${t.id}" ${s?.tenant_id===t.id?'selected':''}>${esc(t.nome)}</option>`))
        .join("");
      modal(s ? "Editar script" : "Novo script", `
        <div class="field"><label>Nome *</label><input id="sc-nome" value="${esc(s?.nome||'')}" placeholder="ex.: reinicia-agente" /></div>
        <div class="field"><label>Tipo</label>
          <select id="sc-tipo" onchange="toggleTipoCampos()">
            <option value="arquivo" ${s?.tipo!=='template'?'selected':''}>Arquivo (.sh no volume)</option>
            <option value="template" ${s?.tipo==='template'?'selected':''}>Template</option>
          </select></div>
        <div class="field" id="campo-arquivo"><label>Arquivo (.sh) *</label><input id="sc-caminho" value="${esc(s?.caminho||'')}" placeholder="cleanup_logs.sh" class="mono" /></div>
        <div class="field" id="campo-template"><label>Template *</label>
          <textarea id="sc-template" rows="3" class="mono" placeholder="docker restart {{container:agent}}">${esc(s?.template||'')}</textarea>
          <div class="muted" style="font-size:11px">Placeholders: {{slug}} {{container:db|odoo|agent}} {{db}} {{logdir}} {{param:nome:int|slug}}</div></div>
        <div class="field"><label>Dono</label><select id="sc-dono" ${s?'disabled':''}>${tenantsOpts}</select></div>
        <div class="field"><label>Descrição curta</label><input id="sc-desc" value="${esc(s?.descricao||'')}" /></div>
        <div class="field"><label>Categoria</label>
          <select id="sc-cat">${["cleanup","backup","update","status","provision","other"].map(c=>`<option ${s?.categoria===c?'selected':''}>${c}</option>`).join("")}</select></div>
        <div class="field" style="display:flex;align-items:center;gap:8px"><label style="margin:0">Ativo</label>
          <label class="switch"><input id="sc-ativo" type="checkbox" ${s?(s.ativo?'checked':''):'checked'}><span class="slider"></span></label></div>
      `, [
        { label: "Cancelar", cls: "ghost", act: closeModal },
        { label: s ? "Salvar" : "Cadastrar", cls: "", act: () => saveScript(id) },
      ]);
      toggleTipoCampos();
```

Adicione a função auxiliar logo após `openScript`:

```javascript
    function toggleTipoCampos() {
      const t = $("sc-tipo").value;
      $("campo-arquivo").style.display = t === "arquivo" ? "" : "none";
      $("campo-template").style.display = t === "template" ? "" : "none";
    }
```

- [ ] **Step 3: saveScript envia tipo/template/tenant_id**

Substitua o objeto `body` em `saveScript` (linhas ~420-425) por:

```javascript
      const tipo = $("sc-tipo").value;
      const body = {
        nome: $("sc-nome").value.trim(), tipo,
        caminho: tipo === "arquivo" ? $("sc-caminho").value.trim() : "",
        template: tipo === "template" ? $("sc-template").value.trim() : null,
        descricao: $("sc-desc").value.trim(),
        categoria: $("sc-cat").value, ativo: $("sc-ativo").checked,
      };
      if (!id) { const dono = $("sc-dono").value; if (dono) body.tenant_id = parseInt(dono, 10); }
      if (!body.nome || (tipo === "arquivo" && !body.caminho) || (tipo === "template" && !body.template)) {
        toast("Preencha nome e arquivo/template", "err"); return;
      }
```

(Remova a linha antiga `parametros:` redundante; o backend deriva os params do
template.)

- [ ] **Step 4: Inputs tipados no drawer do cliente**

Em `openCliente` (linha ~298), troque o `data.map(...)` que monta `dr-scripts`
por uma versão que renderiza um input por param quando houver `parametros_schema`
(preserva a classe `exec-row`/`.nm` existente):

```javascript
        $("dr-scripts").innerHTML = data.map(s => {
          const ps = s.parametros_schema || [];
          const inputs = ps.length
            ? ps.map(p => `<input id="p-${s.script_id}-${p.nome}" type="${p.tipo==='int'?'number':'text'}" placeholder="${esc(p.nome)} (${esc(p.tipo)})" style="max-width:140px" />`).join("")
            : `<input id="p-${s.script_id}" placeholder="${esc(s.parametros_default || 'sem parâmetros')}" />`;
          return `
          <div class="exec-row">
            <span class="nm">${esc(s.nome)}</span>
            ${inputs}
            <button class="btn sm" onclick="runScript(${s.script_id}, ${ps.length})">executar</button>
          </div>`;
        }).join("") || `<div class="muted">Sem scripts vinculados.</div>`;
```

Troque `runScript` (linhas ~309-319) para coletar os params tipados em ordem,
mantendo o comportamento atual (escreve em `dr-out`, recarrega logs e cards):

```javascript
    async function runScript(sid, nparams) {
      let parametros;
      if (nparams) {
        parametros = Array.from(document.querySelectorAll(`[id^="p-${sid}-"]`)).map(c => c.value.trim());
      } else {
        const raw = ($(`p-${sid}`)?.value || "").trim();
        parametros = raw ? raw.split(/\s+/) : [];
      }
      $("dr-out").textContent = "Executando...";
      try {
        const { data } = await api(`/api/v1/tenants/${state.current}/scripts/${sid}/run`, { method: "POST", body: JSON.stringify({ parametros }) });
        $("dr-out").textContent = `# ${data.status} (exit ${data.exit_code}) · ${data.duracao_ms}ms\n\n` + (data.stdout || "") + (data.stderr ? "\n[stderr]\n" + data.stderr : "");
        toast(data.status === "sucesso" ? "Executado com sucesso" : "Script retornou falha", data.status === "sucesso" ? "ok" : "err");
        loadDrawerLogs(); loadClientes();
      } catch (e) { $("dr-out").textContent = e.message; toast(e.message, "err"); }
    }
```

- [ ] **Step 5: Verificação manual**

```bash
ISY_SEED_DEMO=1 .venv/bin/python -m uvicorn app.main:app --port 8000
```

No navegador em `http://localhost:8000/ui`:
- Aba Scripts: cabeçalho tem coluna **Dono**; scripts seed aparecem como "Global".
- "+ Novo script" → Tipo "Template" mostra textarea + legenda; Dono lista clientes.
- Cadastrar template `docker ps {{container:db}}` para um cliente → aparece "owned".
- Abrir o cliente → o script aparece; com `{{param:dias:int}}` o run mostra input number.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat: UI de templates e scripts exclusivos por cliente"
```

---

## Task 10: Suíte completa + verificação final

- [ ] **Step 1: Rodar tudo**

Run: `.venv/bin/python -m pytest -q`
Expected: todos os testes passam (27 anteriores + novos).

- [ ] **Step 2: Sanidade dos scripts shell (não regrediram)**

Run: `bash -n deploy/client-box/provision.sh && for f in scripts/*.sh; do bash -n "$f"; done && echo OK`
Expected: `OK`.

- [ ] **Step 3 (opcional, com autorização): Commit final / abrir PR**

Só com o OK do usuário.

---

## Notas de migração

Banco com `create_all` não adiciona colunas a tabela existente. Para a demo,
recriar o banco (seed roda em banco vazio). Para preservar dados, rodar uma vez:

```sql
ALTER TABLE scripts ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'arquivo';
ALTER TABLE scripts ADD COLUMN template VARCHAR(2000);
```
