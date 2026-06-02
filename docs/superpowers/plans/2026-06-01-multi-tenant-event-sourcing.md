# Multi-tenant + Event Sourcing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evoluir a Shell Automation API para um painel de manutencao multi-cliente, com tenants isolados por credencial, event store append-only e saude derivada on-read.

**Architecture:** Tenants/scripts sao CRUD; o operacional vira eventos imutaveis (`events`). A saude de cada tenant e uma projecao calculada on-read dos eventos. Auth em dois niveis (token admin + token por tenant). UI neutra servida pelo FastAPI. Deploy no Railway seedado com 5 clientes.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, subprocess, pytest, Docker, Railway.

**Base:** [design](../specs/2026-06-01-multi-tenant-event-sourcing-design.md), [ADR 0005](../../adr/0005-multi-tenant-event-sourcing.md). Codigo atual em `app/` (ver `docs/architecture.md`).

> **Convencao de execucao:** rodar sempre no venv (`. .venv/bin/activate`, Python 3.11). Testes com `python -m pytest`. Cada task fecha com commit na branch `feat/shell-automation-api`.

---

## File Structure (alvo)

```
app/
├── core/
│   ├── config.py        # +seed_demo ja existe; sem mudanca estrutural
│   ├── db.py            # init_db registra novos models
│   ├── events.py        # NOVO: constantes de tipos de evento
│   ├── responses.py     # sem mudanca
│   └── security.py      # verify_admin + verify_tenant (substitui verify_token)
├── models.py            # +Tenant, +TenantScript, +Event; Script ganha categoria/tenant_id; remove Execution
├── schemas.py           # +Tenant*, +TenantScriptBinding, +EventOut, +HealthOut; remove ExecutionOut
├── repositories/
│   ├── config_repo.py   # sem mudanca
│   ├── tenants_repo.py  # NOVO
│   ├── scripts_repo.py  # +list_global, ajustes
│   ├── tenant_scripts_repo.py  # NOVO
│   └── events_repo.py   # NOVO (substitui executions_repo.py)
├── services/
│   ├── execution_service.py  # tenant-scoped, emite ExecutionCompleted
│   ├── script_service.py     # sem mudanca relevante
│   ├── tenant_service.py     # NOVO (validacao de tenant)
│   ├── health_service.py     # NOVO (projecao de saude)
│   └── alert_service.py      # sem mudanca
├── routes/
│   ├── health.py        # liveness (sem mudanca)
│   ├── admin.py         # tenants CRUD + catalogo + bindings + tokens + dashboard
│   └── tenants.py       # NOVO: scripts/run/logs/health por cliente (substitui scripts.py + logs.py)
├── static/index.html    # dashboard neutro multi-cliente
└── main.py              # wiring dos routers + seed
scripts/backup_db.sh     # NOVO
tests/                   # test_auth_isolation, test_health (novos); execution/security/tenants adaptados
```

Arquivos removidos: `app/repositories/executions_repo.py`, `app/routes/scripts.py`, `app/routes/logs.py`.

---

## Milestone 1 — Modelo de dados (event store + tenants)

### Task 1: Event model + tipos + events_repo

**Files:**
- Create: `app/core/events.py`
- Modify: `app/models.py` (adiciona `Event`, remove `Execution`)
- Create: `app/repositories/events_repo.py`
- Delete: `app/repositories/executions_repo.py`
- Test: `tests/test_events_repo.py`

- [ ] **Step 1: Constantes de tipos de evento**

Create `app/core/events.py`:

```python
"""Tipos de evento do event store (append-only)."""

EXECUTION_COMPLETED = "ExecutionCompleted"
TOKEN_ROTATED = "TokenRotated"
```

- [ ] **Step 2: Model Event e remocao do Execution**

In `app/models.py`, remove a classe `Execution` inteira e adicione (mantenha imports existentes; adicione `JSON` ao import do sqlalchemy):

```python
from sqlalchemy import JSON  # adicionar ao import existente


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
```

> Nota: `Tenant` e `Script.tenant_id` entram nas Tasks 2-3; o FK para `tenants.id` ja referencia a tabela que sera criada. `create_all` resolve a ordem.

- [ ] **Step 3: events_repo**

Create `app/repositories/events_repo.py`:

```python
"""Acesso append-only ao event store."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event


def append(
    db: Session,
    tipo: str,
    payload: dict,
    tenant_id: int | None = None,
    script_id: int | None = None,
    ocorrido_em: datetime | None = None,
) -> Event:
    event = Event(tipo=tipo, payload=payload, tenant_id=tenant_id, script_id=script_id)
    if ocorrido_em is not None:
        event.ocorrido_em = ocorrido_em
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_by_tenant(
    db: Session, tenant_id: int, tipo: str | None = None, limit: int = 100
) -> list[Event]:
    stmt = select(Event).where(Event.tenant_id == tenant_id)
    if tipo is not None:
        stmt = stmt.where(Event.tipo == tipo)
    stmt = stmt.order_by(Event.id.desc()).limit(limit)
    return list(db.scalars(stmt))
```

- [ ] **Step 4: Remover executions_repo**

Run: `git rm app/repositories/executions_repo.py`
Expected: arquivo removido.

- [ ] **Step 5: Teste do events_repo**

Create `tests/test_events_repo.py`:

```python
from app.core import events as ev
from app.core.db import SessionLocal
from app.repositories import events_repo
from tests.conftest import client  # noqa: F401  (fixture cria/limpa tabelas)


def test_append_e_list_por_tenant(client):
    with SessionLocal() as db:
        events_repo.append(db, ev.EXECUTION_COMPLETED, {"status": "sucesso"}, tenant_id=1)
        events_repo.append(db, ev.EXECUTION_COMPLETED, {"status": "falha"}, tenant_id=1)
        events_repo.append(db, ev.EXECUTION_COMPLETED, {"status": "sucesso"}, tenant_id=2)

        do_tenant1 = events_repo.list_by_tenant(db, 1)
        assert len(do_tenant1) == 2
        # ordem desc: o ultimo inserido vem primeiro
        assert do_tenant1[0].payload["status"] == "falha"
```

- [ ] **Step 6: Rodar (deve falhar antes da impl. completa, passar depois)**

Run: `python -m pytest tests/test_events_repo.py -v`
Expected: PASS (apos Steps 1-3).

> Se `tests/conftest.py` ainda referenciar models antigos, este teste pode quebrar no import — sera ajustado na Task 11/atualizacao de testes. Caso quebre aqui, rode so apos a Task 3.

- [ ] **Step 7: Commit**

```bash
git add app/core/events.py app/models.py app/repositories/events_repo.py tests/test_events_repo.py
git rm --cached app/repositories/executions_repo.py 2>/dev/null || true
git commit -m "feat: event store append-only (Event + events_repo)"
```

---

### Task 2: Tenant model + tenants_repo

**Files:**
- Modify: `app/models.py` (add `Tenant`)
- Create: `app/repositories/tenants_repo.py`
- Modify: `app/schemas.py` (add Tenant schemas)
- Test: `tests/test_tenants_repo.py`

- [ ] **Step 1: Model Tenant**

In `app/models.py`, adicione:

```python
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    dominio: Mapped[str] = mapped_column(String(120))
    porta: Mapped[int] = mapped_column(Integer)
    db_name: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    token: Mapped[str] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
```

- [ ] **Step 2: Schemas de Tenant**

In `app/schemas.py`, adicione:

```python
class TenantCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=60)
    nome: str = Field(min_length=1, max_length=120)
    dominio: str = Field(min_length=1, max_length=120)
    porta: int = Field(ge=1, le=65535)
    db_name: str = Field(min_length=1, max_length=120)
    token: str = Field(min_length=8, max_length=255)
    ativo: bool = True


class TenantUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    dominio: str | None = Field(default=None, max_length=120)
    porta: int | None = Field(default=None, ge=1, le=65535)
    db_name: str | None = Field(default=None, max_length=120)
    ativo: bool | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    dominio: str
    porta: int
    db_name: str
    ativo: bool
    criado_em: datetime
```

- [ ] **Step 3: tenants_repo**

Create `app/repositories/tenants_repo.py`:

```python
"""Acesso a tabela tenants."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tenant
from app.schemas import TenantCreate, TenantUpdate


def list_all(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.id)))


def get(db: Session, tenant_id: int) -> Tenant | None:
    return db.get(Tenant, tenant_id)


def get_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def create(db: Session, data: TenantCreate) -> Tenant:
    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update(db: Session, tenant: Tenant, data: TenantUpdate) -> Tenant:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


def set_token(db: Session, tenant: Tenant, token: str) -> None:
    tenant.token = token
    db.commit()


def delete(db: Session, tenant: Tenant) -> None:
    db.delete(tenant)
    db.commit()
```

- [ ] **Step 4: Teste do tenants_repo**

Create `tests/test_tenants_repo.py`:

```python
from app.core.db import SessionLocal
from app.repositories import tenants_repo
from app.schemas import TenantCreate
from tests.conftest import client  # noqa: F401


def test_create_e_get_by_slug(client):
    with SessionLocal() as db:
        tenants_repo.create(db, TenantCreate(
            slug="cliente-1", nome="Cliente 1", dominio="cliente1.isy.one",
            porta=8151, db_name="db_cliente1", token="tok-cliente-1-xyz",
        ))
        t = tenants_repo.get_by_slug(db, "cliente-1")
        assert t is not None
        assert t.db_name == "db_cliente1"
```

- [ ] **Step 5: Rodar**

Run: `python -m pytest tests/test_tenants_repo.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/schemas.py app/repositories/tenants_repo.py tests/test_tenants_repo.py
git commit -m "feat: entidade Tenant + tenants_repo"
```

---

### Task 3: Script com categoria/tenant_id + TenantScript + tenant_scripts_repo

**Files:**
- Modify: `app/models.py` (Script ganha `categoria`, `tenant_id`; add `TenantScript`)
- Modify: `app/schemas.py` (Script ganha `categoria`; add binding schemas)
- Modify: `app/repositories/scripts_repo.py` (add `list_global`)
- Create: `app/repositories/tenant_scripts_repo.py`
- Test: `tests/test_tenant_scripts_repo.py`

- [ ] **Step 1: Ajustar Script e adicionar TenantScript**

In `app/models.py`, na classe `Script` adicione os campos `categoria` e `tenant_id` (logo apos `descricao`):

```python
    categoria: Mapped[str] = mapped_column(String(20), default="other")
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
```

E adicione a classe de binding:

```python
from sqlalchemy import UniqueConstraint  # adicionar ao import existente


class TenantScript(Base):
    __tablename__ = "tenant_scripts"
    __table_args__ = (UniqueConstraint("tenant_id", "script_id", name="uq_tenant_script"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"))
    parametros_default: Mapped[str] = mapped_column(String(255), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 2: Schemas (categoria + binding)**

In `app/schemas.py`: adicione `categoria: str = "other"` em `ScriptCreate` (apos `descricao`) e `categoria: str | None = None` em `ScriptUpdate`; adicione `categoria: str` em `ScriptOut` (apos `descricao`). Depois adicione:

```python
class TenantScriptBinding(BaseModel):
    script_id: int
    parametros_default: str = Field(default="", max_length=255)
    ativo: bool = True


class TenantScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    script_id: int
    parametros_default: str
    ativo: bool
```

- [ ] **Step 3: scripts_repo.list_global**

In `app/repositories/scripts_repo.py`, adicione:

```python
def list_global(db: Session) -> list[Script]:
    stmt = select(Script).where(Script.tenant_id.is_(None)).order_by(Script.id)
    return list(db.scalars(stmt))
```

- [ ] **Step 4: tenant_scripts_repo**

Create `app/repositories/tenant_scripts_repo.py`:

```python
"""Binding entre tenant e script (whitelist + defaults por cliente)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Script, TenantScript


def get(db: Session, tenant_id: int, script_id: int) -> TenantScript | None:
    stmt = select(TenantScript).where(
        TenantScript.tenant_id == tenant_id, TenantScript.script_id == script_id
    )
    return db.scalar(stmt)


def upsert(
    db: Session, tenant_id: int, script_id: int, parametros_default: str, ativo: bool
) -> TenantScript:
    binding = get(db, tenant_id, script_id)
    if binding is None:
        binding = TenantScript(tenant_id=tenant_id, script_id=script_id)
        db.add(binding)
    binding.parametros_default = parametros_default
    binding.ativo = ativo
    db.commit()
    db.refresh(binding)
    return binding


def list_active_scripts(db: Session, tenant_id: int) -> list[tuple[Script, TenantScript]]:
    """Scripts ativos disponiveis para o tenant, com o binding correspondente."""
    stmt = (
        select(Script, TenantScript)
        .join(TenantScript, TenantScript.script_id == Script.id)
        .where(
            TenantScript.tenant_id == tenant_id,
            TenantScript.ativo.is_(True),
            Script.ativo.is_(True),
        )
        .order_by(Script.id)
    )
    return [(row[0], row[1]) for row in db.execute(stmt)]
```

- [ ] **Step 5: Teste**

Create `tests/test_tenant_scripts_repo.py`:

```python
from app.core.db import SessionLocal
from app.repositories import scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from tests.conftest import client  # noqa: F401


def test_binding_define_whitelist_do_tenant(client):
    with SessionLocal() as db:
        t = tenants_repo.create(db, TenantCreate(
            slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
            db_name="db_c1", token="tok-c1-xyz",
        ))
        s = scripts_repo.create(db, ScriptCreate(
            nome="cleanup", caminho="cleanup_logs.sh", categoria="cleanup",
        ))
        tenant_scripts_repo.upsert(db, t.id, s.id, parametros_default="7", ativo=True)

        disponiveis = tenant_scripts_repo.list_active_scripts(db, t.id)
        assert len(disponiveis) == 1
        script, binding = disponiveis[0]
        assert script.nome == "cleanup"
        assert binding.parametros_default == "7"
```

- [ ] **Step 6: Rodar**

Run: `python -m pytest tests/test_tenant_scripts_repo.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/schemas.py app/repositories/scripts_repo.py app/repositories/tenant_scripts_repo.py tests/test_tenant_scripts_repo.py
git commit -m "feat: Script com categoria/tenant_id + binding tenant_scripts"
```

---

## Milestone 2 — Autenticacao em dois niveis

### Task 4: verify_admin e verify_tenant

**Files:**
- Modify: `app/core/security.py` (substitui `verify_token` por `verify_admin` + `verify_tenant`)
- Test: `tests/test_auth_isolation.py`

- [ ] **Step 1: Reescrever security.py (auth)**

In `app/core/security.py`, substitua a funcao `verify_token` por (mantenha `resolve_script_path` e `ScriptPathError` como estao):

```python
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings  # ja importado
from app.core.db import get_db
from app.models import Tenant
from app.repositories import config_repo, tenants_repo


def verify_admin(
    x_isy_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    admin = config_repo.get_token(db)
    if not x_isy_token or not secrets.compare_digest(x_isy_token, admin):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token admin invalido ou ausente.")


def verify_tenant(
    slug: str,
    x_isy_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> Tenant:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None or not tenant.ativo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    admin = config_repo.get_token(db)
    if x_isy_token and (
        secrets.compare_digest(x_isy_token, tenant.token)
        or secrets.compare_digest(x_isy_token, admin)
    ):
        return tenant
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido ou ausente.")
```

> Remova o import antigo de `Path`/config nao usados se sobrarem; mantenha o que `resolve_script_path` precisa.

- [ ] **Step 2: Teste de isolamento (escreve antes de rotas existirem usando as dependencies direto)**

Create `tests/test_auth_isolation.py`:

```python
import pytest
from fastapi import HTTPException

from app.core.db import SessionLocal
from app.core.security import verify_tenant
from app.repositories import tenants_repo
from app.schemas import TenantCreate
from tests.conftest import client  # noqa: F401


def _seed_dois_tenants(db):
    tenants_repo.create(db, TenantCreate(
        slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
        db_name="db_c1", token="tok-c1-aaaaaa"))
    tenants_repo.create(db, TenantCreate(
        slug="c2", nome="C2", dominio="c2.isy.one", porta=8152,
        db_name="db_c2", token="tok-c2-bbbbbb"))


def test_token_do_tenant_so_acessa_o_proprio(client):
    with SessionLocal() as db:
        _seed_dois_tenants(db)
        # token do c1 acessa c1
        t = verify_tenant("c1", x_isy_token="tok-c1-aaaaaa", db=db)
        assert t.slug == "c1"
        # token do c1 NAO acessa c2
        with pytest.raises(HTTPException) as exc:
            verify_tenant("c2", x_isy_token="tok-c1-aaaaaa", db=db)
        assert exc.value.status_code == 401


def test_token_admin_acessa_qualquer_tenant(client):
    with SessionLocal() as db:
        _seed_dois_tenants(db)
        # token admin default vem do config (settings.token)
        from app.repositories import config_repo
        admin = config_repo.get_token(db)
        t = verify_tenant("c2", x_isy_token=admin, db=db)
        assert t.slug == "c2"
```

- [ ] **Step 3: Rodar**

Run: `python -m pytest tests/test_auth_isolation.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/core/security.py tests/test_auth_isolation.py
git commit -m "feat: auth em dois niveis (verify_admin + verify_tenant isolado)"
```

---

## Milestone 3 — Execucao + eventos

### Task 5: execution_service tenant-scoped emitindo ExecutionCompleted

**Files:**
- Modify: `app/services/execution_service.py`
- Modify: `app/services/alert_service.py` (assinatura recebe dados do evento)
- Test: `tests/test_execution_service.py`

- [ ] **Step 1: Reescrever execution_service**

Replace `app/services/execution_service.py` por:

```python
"""Execucao segura de scripts (tenant-scoped) gravando evento ExecutionCompleted.

Seguranca: whitelist por tenant (resolvida na rota), subprocess shell=False +
timeout, caminho dentro do diretorio montado (anti command injection / traversal).
"""

import subprocess
import time

from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.core.security import ScriptPathError, resolve_script_path
from app.models import Event, Script, Tenant
from app.repositories import events_repo
from app.services import alert_service


class ScriptNotExecutable(RuntimeError):
    """Script ativo, mas arquivo ausente ou caminho invalido."""


def run(db: Session, tenant: Tenant, script: Script, parametros: list[str]) -> Event:
    try:
        path = resolve_script_path(script.caminho)
    except ScriptPathError as exc:
        raise ScriptNotExecutable(str(exc)) from exc
    if not path.is_file():
        raise ScriptNotExecutable(f"Arquivo do script nao encontrado: {script.caminho}")

    argv = [str(path), *parametros]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True,
            timeout=settings.exec_timeout, check=False,
        )
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status = "sucesso" if proc.returncode == 0 else "falha"
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        duracao_ms = int((time.perf_counter() - started) * 1000)
        status, exit_code = "falha", None
        stdout, stderr = "", f"Tempo limite de {settings.exec_timeout}s excedido."

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
```

- [ ] **Step 2: Ajustar alert_service**

Replace a funcao `notify_failure` em `app/services/alert_service.py`:

```python
def notify_failure(tenant_slug: str, payload: dict) -> None:
    if not settings.alert_webhook_url:
        return
    content = (
        f":rotating_light: Falha em `{tenant_slug}` / `{payload.get('script_nome')}`\n"
        f"exit_code={payload.get('exit_code')} | params={payload.get('parametros') or '-'}\n"
        f"stderr: {str(payload.get('stderr'))[:500]}"
    )
    try:
        httpx.post(settings.alert_webhook_url, json={"content": content}, timeout=5)
    except httpx.HTTPError:
        pass
```

Remova o import de `Execution` no topo de `alert_service.py` se existir.

- [ ] **Step 3: Teste**

Create `tests/test_execution_service.py`:

```python
from app.core.db import SessionLocal
from app.repositories import events_repo, scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate
from app.services import execution_service
from tests.conftest import client  # noqa: F401


def _setup(db):
    t = tenants_repo.create(db, TenantCreate(
        slug="c1", nome="C1", dominio="c1.isy.one", porta=8151,
        db_name="db_c1", token="tok-c1-aaaaaa"))
    s = scripts_repo.create(db, ScriptCreate(
        nome="echo", caminho="echo_args.sh", categoria="other"))
    return t, s


def test_execucao_grava_evento_sucesso(client):
    with SessionLocal() as db:
        t, s = _setup(db)
        event = execution_service.run(db, t, s, ["ola", "mundo"])
        assert event.payload["status"] == "sucesso"
        assert "ARG:ola" in event.payload["stdout"]
        eventos = events_repo.list_by_tenant(db, t.id)
        assert len(eventos) == 1


def test_command_injection_argv_literal(client):
    with SessionLocal() as db:
        t, s = _setup(db)
        event = execution_service.run(db, t, s, ["; rm -rf /", "$(id)"])
        linhas = [l for l in event.payload["stdout"].splitlines() if l.startswith("ARG:")]
        assert "ARG:; rm -rf /" in event.payload["stdout"]
        assert len(linhas) == 2
```

> Usa as fixtures `echo_args.sh` ja existentes em `tests/fixtures/scripts/` e o `ISY_SCRIPTS_DIR` do conftest.

- [ ] **Step 4: Rodar**

Run: `python -m pytest tests/test_execution_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/execution_service.py app/services/alert_service.py tests/test_execution_service.py
git commit -m "feat: execucao tenant-scoped gravando ExecutionCompleted"
```

---

## Milestone 4 — Projecao de saude

### Task 6: health_service (calcular_saude on-read)

**Files:**
- Create: `app/services/health_service.py`
- Modify: `app/schemas.py` (HealthOut)
- Test: `tests/test_health.py`

- [ ] **Step 1: health_service**

Create `app/services/health_service.py`:

```python
"""Projecao de saude por tenant, derivada on-read dos eventos."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.models import Tenant
from app.repositories import events_repo

BACKUP_STALE_DIAS = 7


def _execucoes(db: Session, tenant_id: int):
    return events_repo.list_by_tenant(db, tenant_id, tipo=ev.EXECUTION_COMPLETED, limit=200)


def _containers_down(stdout: str) -> bool:
    # Heuristica simples: container fora do ar se aparecer "Exited"/"Down" ou faltar "Up".
    linhas = [l for l in stdout.splitlines() if "isyone-" in l.lower()]
    return any(("Exited" in l or "Down" in l or "Up" not in l) for l in linhas)


def calcular_saude(db: Session, tenant: Tenant) -> dict:
    execucoes = _execucoes(db, tenant.id)
    ultima = execucoes[0].payload if execucoes else None
    backup = next(
        (e.payload for e in execucoes
         if e.payload.get("categoria") == "backup" and e.payload.get("status") == "sucesso"),
        None,
    )
    status_event = next((e for e in execucoes if e.payload.get("categoria") == "status"), None)
    containers_stdout = status_event.payload.get("stdout") if status_event else None

    status_geral = "verde"
    if ultima and ultima.get("status") == "falha":
        status_geral = "vermelho"
    elif containers_stdout and _containers_down(containers_stdout):
        status_geral = "vermelho"
    else:
        ultimo_backup_ts = None
        if backup:
            backup_event = next(
                e for e in execucoes
                if e.payload.get("categoria") == "backup" and e.payload.get("status") == "sucesso"
            )
            ultimo_backup_ts = backup_event.ocorrido_em
        limite = datetime.now(timezone.utc) - timedelta(days=BACKUP_STALE_DIAS)
        if ultimo_backup_ts is None or ultimo_backup_ts < limite:
            status_geral = "amarelo"

    return {
        "slug": tenant.slug,
        "nome": tenant.nome,
        "ativo": tenant.ativo,
        "status_geral": status_geral,
        "ultima_manutencao": ultima,
        "ultimo_backup": backup,
        "containers": containers_stdout,
    }
```

> `settings` importado por consistencia futura (limite configuravel); `BACKUP_STALE_DIAS` fixo por ora.

- [ ] **Step 2: Schema HealthOut (resposta livre)**

A saude e um dict heterogeneo; expomos como dict no envelope (sem schema rigido). Nenhuma mudanca obrigatoria em `schemas.py` — pular se preferir. (Mantido simples por YAGNI.)

- [ ] **Step 3: Teste da projecao**

Create `tests/test_health.py`:

```python
from datetime import datetime, timedelta, timezone

from app.core import events as ev
from app.core.db import SessionLocal
from app.repositories import events_repo, tenants_repo
from app.schemas import TenantCreate
from app.services import health_service
from tests.conftest import client  # noqa: F401


def _tenant(db, slug="c1", porta=8151):
    return tenants_repo.create(db, TenantCreate(
        slug=slug, nome=slug.upper(), dominio=f"{slug}.isy.one", porta=porta,
        db_name=f"db_{slug}", token=f"tok-{slug}-aaaaaa"))


def test_status_vermelho_quando_ultima_falhou(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(db, ev.EXECUTION_COMPLETED,
                           {"categoria": "cleanup", "status": "falha"}, tenant_id=t.id)
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "vermelho"


def test_status_amarelo_sem_backup_recente(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(db, ev.EXECUTION_COMPLETED,
                           {"categoria": "cleanup", "status": "sucesso"}, tenant_id=t.id)
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "amarelo"


def test_status_verde_com_backup_recente(client):
    with SessionLocal() as db:
        t = _tenant(db)
        events_repo.append(db, ev.EXECUTION_COMPLETED,
                           {"categoria": "backup", "status": "sucesso"}, tenant_id=t.id)
        saude = health_service.calcular_saude(db, t)
        assert saude["status_geral"] == "verde"
        assert saude["ultimo_backup"] is not None
```

- [ ] **Step 4: Rodar**

Run: `python -m pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/health_service.py tests/test_health.py
git commit -m "feat: projecao de saude por tenant (on-read dos eventos)"
```

---

## Milestone 5 — Rotas

### Task 7: Rotas admin (tenants, catalogo, bindings, tokens, dashboard)

**Files:**
- Modify: `app/routes/admin.py` (reescrita)
- Modify: `app/services/script_service.py` (sem mudanca de assinatura; manter `create`/`update`)
- Test: `tests/test_admin_routes.py`

- [ ] **Step 1: Reescrever admin.py**

Replace `app/routes/admin.py` por:

```python
"""Rotas administrativas: tenants, catalogo de scripts, bindings, tokens, dashboard."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_admin
from app.repositories import config_repo, scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import (
    ScriptCreate, ScriptOut, ScriptUpdate,
    TenantCreate, TenantOut, TenantScriptBinding, TenantScriptOut, TenantUpdate, TokenUpdate,
)
from app.services import health_service, script_service

router = APIRouter(prefix="/api/v1/admin", tags=["Administracao"], dependencies=[Depends(verify_admin)])


def _tenant_out(t) -> dict:
    return TenantOut.model_validate(t).model_dump(mode="json")


def _script_out(s) -> dict:
    return ScriptOut.model_validate(s).model_dump(mode="json")


# --- Tenants ---

@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)) -> dict:
    return ok([_tenant_out(t) for t in tenants_repo.list_all(db)])


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)) -> dict:
    if tenants_repo.get_by_slug(db, body.slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug ja existe.")
    return ok(_tenant_out(tenants_repo.create(db, body)), "Cliente cadastrado.")


@router.put("/tenants/{slug}")
def update_tenant(slug: str, body: TenantUpdate, db: Session = Depends(get_db)) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    return ok(_tenant_out(tenants_repo.update(db, tenant, body)), "Cliente atualizado.")


@router.delete("/tenants/{slug}")
def delete_tenant(slug: str, db: Session = Depends(get_db)) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    tenants_repo.delete(db, tenant)
    return ok(message="Cliente removido.")


# --- Catalogo de scripts ---

@router.get("/scripts")
def list_scripts(db: Session = Depends(get_db)) -> dict:
    return ok([_script_out(s) for s in scripts_repo.list_all(db)])


@router.post("/scripts", status_code=status.HTTP_201_CREATED)
def create_script(body: ScriptCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return ok(_script_out(script_service.create(db, body)), "Script cadastrado.")
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/scripts/{script_id}")
def update_script(script_id: int, body: ScriptUpdate, db: Session = Depends(get_db)) -> dict:
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        return ok(_script_out(script_service.update(db, script, body)), "Script atualizado.")
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


# --- Binding tenant<->script ---

@router.put("/tenants/{slug}/scripts")
def bind_script(slug: str, body: TenantScriptBinding, db: Session = Depends(get_db)) -> dict:
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    if scripts_repo.get(db, body.script_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    binding = tenant_scripts_repo.upsert(
        db, tenant.id, body.script_id, body.parametros_default, body.ativo
    )
    return ok(TenantScriptOut.model_validate(binding).model_dump(mode="json"), "Binding salvo.")


# --- Tokens ---

@router.put("/token")
def rotate_admin_token(body: TokenUpdate, db: Session = Depends(get_db)) -> dict:
    config_repo.set_token(db, body.token)
    return ok(message="Token admin rotacionado.")


@router.put("/tenants/{slug}/token")
def rotate_tenant_token(slug: str, body: TokenUpdate, db: Session = Depends(get_db)) -> dict:
    from app.core import events as ev
    from app.repositories import events_repo
    tenant = tenants_repo.get_by_slug(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado.")
    tenants_repo.set_token(db, tenant, body.token)
    events_repo.append(db, ev.TOKEN_ROTATED, {"alvo": slug}, tenant_id=tenant.id)
    return ok(message="Token do cliente rotacionado.")


# --- Dashboard ---

@router.get("/tenants/health")
def dashboard(db: Session = Depends(get_db)) -> dict:
    saudes = [health_service.calcular_saude(db, t) for t in tenants_repo.list_all(db)]
    return ok(saudes)
```

> Nota de roteamento: `GET /tenants/health` e `PUT /tenants/{slug}/scripts` coexistem porque `health` casa antes como literal; o FastAPI resolve por ordem/declaracao. `health` esta declarado depois mas como path fixo nao conflita com `{slug}` nas mesmas combinacoes verbo+path. Verificar no teste.

- [ ] **Step 2: Teste das rotas admin**

Create `tests/test_admin_routes.py`:

```python
from tests.conftest import AUTH


def _criar_tenant(client, slug="cliente-1", porta=8151):
    return client.post("/api/v1/admin/tenants", headers=AUTH, json={
        "slug": slug, "nome": slug, "dominio": f"{slug}.isy.one", "porta": porta,
        "db_name": f"db_{slug}", "token": f"tok-{slug}-aaaaaa",
    })


def test_crud_tenant_e_binding(client):
    assert _criar_tenant(client).status_code == 201
    # duplicado -> 409
    assert _criar_tenant(client).status_code == 409
    # cria script no catalogo
    r = client.post("/api/v1/admin/scripts", headers=AUTH, json={
        "nome": "cleanup", "caminho": "cleanup_logs.sh", "categoria": "cleanup"})
    sid = r.json()["data"]["id"]
    # binda no tenant
    rb = client.put("/api/v1/admin/tenants/cliente-1/scripts", headers=AUTH, json={
        "script_id": sid, "parametros_default": "7", "ativo": True})
    assert rb.status_code == 200
    # dashboard responde
    rd = client.get("/api/v1/admin/tenants/health", headers=AUTH)
    assert rd.status_code == 200
    assert len(rd.json()["data"]) == 1


def test_admin_exige_token(client):
    assert client.get("/api/v1/admin/tenants").status_code == 401
```

- [ ] **Step 3: Rodar**

Run: `python -m pytest tests/test_admin_routes.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/routes/admin.py tests/test_admin_routes.py
git commit -m "feat: rotas admin (tenants, catalogo, bindings, tokens, dashboard)"
```

---

### Task 8: Rotas por tenant (scripts, run, logs, health) + remover rotas antigas

**Files:**
- Create: `app/routes/tenants.py`
- Delete: `app/routes/scripts.py`, `app/routes/logs.py`
- Test: `tests/test_tenant_routes.py`

- [ ] **Step 1: Criar tenants.py**

Create `app/routes/tenants.py`:

```python
"""Rotas por cliente: scripts disponiveis, execucao, auditoria e saude."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_tenant
from app.models import Tenant
from app.repositories import events_repo, scripts_repo, tenant_scripts_repo
from app.schemas import RunRequest
from app.services import execution_service, health_service

router = APIRouter(prefix="/api/v1/tenants/{slug}", tags=["Cliente"])


@router.get("/scripts")
def list_scripts(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    disponiveis = tenant_scripts_repo.list_active_scripts(db, tenant.id)
    data = [{
        "script_id": s.id, "nome": s.nome, "categoria": s.categoria,
        "descricao": s.descricao, "parametros_default": b.parametros_default,
    } for s, b in disponiveis]
    return ok(data)


@router.post("/scripts/{script_id}/run")
def run_script(
    script_id: int,
    body: RunRequest,
    tenant: Tenant = Depends(verify_tenant),
    db: Session = Depends(get_db),
) -> dict:
    binding = tenant_scripts_repo.get(db, tenant.id, script_id)
    if binding is None or not binding.ativo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao disponivel para este cliente.")
    script = scripts_repo.get(db, script_id)
    if script is None or not script.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Script inativo.")

    if body.parametros:
        parametros = body.parametros
    else:
        parametros = binding.parametros_default.split() if binding.parametros_default else []

    try:
        event = execution_service.run(db, tenant, script, parametros)
    except execution_service.ScriptNotExecutable as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    p = event.payload
    msg = "Script executado com sucesso." if p["status"] == "sucesso" else "Script retornou falha."
    return ok({"id": event.id, **p, "executado_em": event.ocorrido_em.isoformat()}, msg)


@router.get("/logs")
def list_logs(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    eventos = events_repo.list_by_tenant(db, tenant.id, limit=50)
    data = [{
        "id": e.id, "tipo": e.tipo, "ocorrido_em": e.ocorrido_em.isoformat(), **e.payload,
    } for e in eventos]
    return ok(data)


@router.get("/health")
def health(tenant: Tenant = Depends(verify_tenant), db: Session = Depends(get_db)) -> dict:
    return ok(health_service.calcular_saude(db, tenant))
```

- [ ] **Step 2: Remover rotas antigas**

Run:
```bash
git rm app/routes/scripts.py app/routes/logs.py
```
Expected: arquivos removidos.

- [ ] **Step 3: Teste das rotas de tenant**

Create `tests/test_tenant_routes.py`:

```python
from tests.conftest import AUTH


def _setup(client):
    client.post("/api/v1/admin/tenants", headers=AUTH, json={
        "slug": "cliente-1", "nome": "Cliente 1", "dominio": "cliente1.isy.one",
        "porta": 8151, "db_name": "db_cliente1", "token": "tok-cliente-1-aaaaaa"})
    r = client.post("/api/v1/admin/scripts", headers=AUTH, json={
        "nome": "echo", "caminho": "echo_args.sh", "categoria": "other"})
    sid = r.json()["data"]["id"]
    client.put("/api/v1/admin/tenants/cliente-1/scripts", headers=AUTH, json={
        "script_id": sid, "parametros_default": "padrao", "ativo": True})
    return sid


def test_executa_usando_default_e_audita(client):
    sid = _setup(client)
    tok = {"X-Isy-Token": "tok-cliente-1-aaaaaa"}
    # lista disponiveis com token do cliente
    rl = client.get("/api/v1/tenants/cliente-1/scripts", headers=tok)
    assert rl.status_code == 200 and len(rl.json()["data"]) == 1
    # executa sem passar params -> usa default "padrao"
    rr = client.post(f"/api/v1/tenants/cliente-1/scripts/{sid}/run", headers=tok, json={"parametros": []})
    assert rr.status_code == 200
    assert "ARG:padrao" in rr.json()["data"]["stdout"]
    # auditoria registra
    rlog = client.get("/api/v1/tenants/cliente-1/logs", headers=tok)
    assert len(rlog.json()["data"]) == 1


def test_token_de_outro_cliente_nao_executa(client):
    sid = _setup(client)
    rr = client.post(f"/api/v1/tenants/cliente-1/scripts/{sid}/run",
                     headers={"X-Isy-Token": "tok-errado"}, json={"parametros": []})
    assert rr.status_code == 401
```

- [ ] **Step 4: Rodar**

Run: `python -m pytest tests/test_tenant_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/tenants.py tests/test_tenant_routes.py
git rm --cached app/routes/scripts.py app/routes/logs.py 2>/dev/null || true
git commit -m "feat: rotas por tenant (scripts/run/logs/health); remove rotas globais antigas"
```

---

### Task 9: Wiring do main.py

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_app_boot.py`

- [ ] **Step 1: Atualizar main.py**

In `app/main.py`, troque os includes de router. Remova `from app.routes import admin, health, logs, scripts` e os `include_router` de `scripts`/`logs`; use:

```python
from app.routes import admin, health, tenants

# ... apos criar `app`:
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(tenants.router)
```

Mantenha o restante (lifespan, seed, mount de `/ui`) como esta.

- [ ] **Step 2: Teste de boot**

Create `tests/test_app_boot.py`:

```python
def test_health_publico(client):
    assert client.get("/health").status_code == 200


def test_ui_serve(client):
    assert client.get("/ui/").status_code == 200
```

- [ ] **Step 3: Rodar a suite inteira**

Run: `python -m pytest -q`
Expected: todos PASS. (Se algum teste antigo — `test_security.py`, `test_execution.py` — referenciar rotas removidas, atualizar/remover na Task 11.)

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_app_boot.py
git commit -m "feat: wiring dos routers admin/tenants/health"
```

---

## Milestone 6 — Seed + scripts

### Task 10: backup_db.sh

**Files:**
- Create: `scripts/backup_db.sh`

- [ ] **Step 1: Criar o script**

Create `scripts/backup_db.sh`:

```bash
#!/usr/bin/env bash
# Backup do banco + filestore de um cliente Odoo (saida simulada para a demo).
# Uso: backup_db.sh <db>
set -euo pipefail

DB="${1:?uso: backup_db.sh <db>}"

echo "Iniciando backup de ${DB}..."
echo "pg_dump ${DB} > /backups/${DB}_$(date +%F).sql ... OK"
echo "tar filestore ~/.local/share/Odoo/filestore/${DB} ... OK"
echo "Backup de ${DB} concluido."
```

- [ ] **Step 2: Permissao de execucao**

Run: `chmod +x scripts/backup_db.sh && ./scripts/backup_db.sh db_cliente1`
Expected: imprime as linhas de backup, exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/backup_db.sh
git commit -m "feat: script backup_db.sh de exemplo"
```

---

### Task 11: Seed dos 5 clientes + catalogo + bindings + eventos historicos; atualizar testes antigos

**Files:**
- Modify: `app/core/seed.py` (reescrita)
- Modify: `tests/conftest.py` (helper de seed se necessario)
- Delete/adapt: `tests/test_execution.py`, `tests/test_security.py` (rotas antigas)
- Test: `tests/test_seed.py`

- [ ] **Step 1: Reescrever seed.py**

Replace `app/core/seed.py` por:

```python
"""Seed de demonstracao: 5 clientes, catalogo, bindings e eventos historicos.

Ativado por ISY_SEED_DEMO. So roda se nao houver tenants (idempotente por boot).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import events as ev
from app.repositories import events_repo, scripts_repo, tenant_scripts_repo, tenants_repo
from app.schemas import ScriptCreate, TenantCreate

CATALOGO = [
    ScriptCreate(nome="provisionar", caminho="provisionar.sh", categoria="provision",
                 descricao="Provisiona/recria a stack do cliente."),
    ScriptCreate(nome="backup_db", caminho="backup_db.sh", categoria="backup",
                 descricao="Backup do banco + filestore."),
    ScriptCreate(nome="cleanup_logs", caminho="cleanup_logs.sh", categoria="cleanup",
                 descricao="Limpa/rotaciona logs antigos."),
    ScriptCreate(nome="update_agent", caminho="update_agent.sh", categoria="update",
                 descricao="Atualiza o agente/instancia e reinicia."),
    ScriptCreate(nome="docker_status", caminho="docker_status.sh", categoria="status",
                 descricao="Status dos containers."),
]


def _now():
    return datetime.now(timezone.utc)


def seed_demo(db: Session) -> None:
    if tenants_repo.list_all(db):
        return

    scripts = {c.nome: scripts_repo.create(db, c) for c in CATALOGO}

    for i in range(1, 6):
        slug = f"cliente-{i}"
        tenant = tenants_repo.create(db, TenantCreate(
            slug=slug, nome=f"Cliente {i}", dominio=f"cliente{i}.isy.one",
            porta=8150 + i, db_name=f"db_cliente{i}", token=f"tok-{slug}-000000",
        ))
        # defaults por cliente
        defaults = {
            "provisionar": f"cliente{i} cliente{i}.isy.one {8150 + i}",
            "backup_db": f"db_cliente{i}",
            "cleanup_logs": "30",
            "update_agent": f"db_cliente{i}",
            "docker_status": f"cliente{i}",
        }
        for nome, script in scripts.items():
            tenant_scripts_repo.upsert(db, tenant.id, script.id, defaults[nome], True)

        # eventos historicos variados (status inicial do dashboard)
        if i == 1:  # vermelho: ultima manutencao falhou
            events_repo.append(db, ev.EXECUTION_COMPLETED,
                {"script_nome": "update_agent", "categoria": "update", "status": "falha",
                 "exit_code": 1, "stdout": "", "stderr": "conexao recusada", "parametros": f"db_cliente{i}"},
                tenant_id=tenant.id, script_id=scripts["update_agent"].id,
                ocorrido_em=_now() - timedelta(hours=2))
        elif i == 2:  # amarelo: backup antigo
            events_repo.append(db, ev.EXECUTION_COMPLETED,
                {"script_nome": "backup_db", "categoria": "backup", "status": "sucesso",
                 "exit_code": 0, "stdout": "Backup concluido.", "stderr": "", "parametros": f"db_cliente{i}"},
                tenant_id=tenant.id, script_id=scripts["backup_db"].id,
                ocorrido_em=_now() - timedelta(days=12))
        else:  # verde: backup recente + status ok
            events_repo.append(db, ev.EXECUTION_COMPLETED,
                {"script_nome": "backup_db", "categoria": "backup", "status": "sucesso",
                 "exit_code": 0, "stdout": "Backup concluido.", "stderr": "", "parametros": f"db_cliente{i}"},
                tenant_id=tenant.id, script_id=scripts["backup_db"].id,
                ocorrido_em=_now() - timedelta(days=1))
            events_repo.append(db, ev.EXECUTION_COMPLETED,
                {"script_nome": "docker_status", "categoria": "status", "status": "sucesso",
                 "exit_code": 0,
                 "stdout": f"isyone-cliente{i}-db Up (healthy)\nisyone-cliente{i}-odoo Up (healthy)",
                 "stderr": "", "parametros": f"cliente{i}"},
                tenant_id=tenant.id, script_id=scripts["docker_status"].id,
                ocorrido_em=_now() - timedelta(minutes=10))
```

- [ ] **Step 2: Remover testes antigos obsoletos**

Os arquivos `tests/test_execution.py` e `tests/test_security.py` testam as rotas globais removidas (`/api/v1/scripts`, `/api/v1/logs`, `/api/v1/admin/scripts` com fluxo antigo). A cobertura equivalente migrou para `test_tenant_routes.py`, `test_execution_service.py`, `test_auth_isolation.py` e `test_admin_routes.py`.

Run:
```bash
git rm tests/test_execution.py tests/test_security.py
```

> O conftest atual (TOKEN/AUTH e fixture `client`) permanece valido — `verify_admin` usa o mesmo token de `config`. Manter `make_script` removido se nao usado, ou deixar (sem efeito).

- [ ] **Step 3: Teste do seed**

Create `tests/test_seed.py`:

```python
from app.core.db import SessionLocal
from app.core.seed import seed_demo
from app.repositories import tenants_repo
from app.services import health_service
from tests.conftest import client  # noqa: F401


def test_seed_cria_5_clientes_com_status_variado(client):
    with SessionLocal() as db:
        seed_demo(db)
        tenants = tenants_repo.list_all(db)
        assert len(tenants) == 5
        status = {t.slug: health_service.calcular_saude(db, t)["status_geral"] for t in tenants}
        assert status["cliente-1"] == "vermelho"
        assert status["cliente-2"] == "amarelo"
        assert status["cliente-3"] == "verde"
```

- [ ] **Step 4: Rodar a suite inteira**

Run: `python -m pytest -q`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add app/core/seed.py tests/test_seed.py
git rm --cached tests/test_execution.py tests/test_security.py 2>/dev/null || true
git commit -m "feat: seed de 5 clientes com catalogo, bindings e eventos historicos"
```

---

## Milestone 7 — UI neutra

### Task 12: Dashboard neutro multi-cliente

**Files:**
- Modify: `app/static/index.html` (reescrita neutra)
- Manual verification (sem teste automatizado de UI)

- [ ] **Step 1: Reescrever index.html (visual neutro)**

Replace `app/static/index.html` por uma pagina simples (sem tema): campo de token; grid de cartoes de clientes via `GET /api/v1/admin/tenants/health`; ao clicar num cartao, carrega `GET /api/v1/tenants/{slug}/scripts`, permite executar (`POST .../run`) e mostra `GET .../logs`. Conteudo:

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Isy.One — Manutencao</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; color: #111; background: #f6f7f9; }
    header { padding: 12px 20px; background: #fff; border-bottom: 1px solid #ddd; display: flex; gap: 10px; align-items: center; }
    header input { padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; min-width: 280px; }
    button { padding: 6px 10px; border: 1px solid #ccc; background: #fff; border-radius: 4px; cursor: pointer; }
    main { padding: 20px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
    .card { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; cursor: pointer; }
    .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
    .verde { background: #2e7d32; } .amarelo { background: #f9a825; } .vermelho { background: #c62828; }
    .muted { color: #666; font-size: 12px; }
    pre { background: #f0f0f0; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
    .row { display: flex; gap: 8px; align-items: center; margin: 6px 0; }
    .row input { flex: 1; padding: 5px; border: 1px solid #ccc; border-radius: 4px; }
    section { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin-top: 16px; }
  </style>
</head>
<body>
  <header>
    <strong>Isy.One — Manutencao</strong>
    <span class="muted">Token</span>
    <input id="token" value="544c5787-613a-4ac2-8e61-9e6486f8d74a" />
    <button onclick="loadDashboard()">Atualizar</button>
  </header>
  <main>
    <div class="grid" id="grid"></div>
    <section id="detalhe" style="display:none">
      <h3 id="d-nome"></h3>
      <div id="d-scripts"></div>
      <h4>Saida</h4>
      <pre id="d-out">-</pre>
      <h4>Historico</h4>
      <div id="d-logs"></div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const token = () => $("token").value.trim();
    const headers = () => ({ "Content-Type": "application/json", "X-Isy-Token": token() });
    let slugAtual = null;

    async function api(path, opts = {}) {
      const res = await fetch(path, { headers: headers(), ...opts });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      return body;
    }

    async function loadDashboard() {
      try {
        const { data } = await api("/api/v1/admin/tenants/health");
        $("grid").innerHTML = data.map((t) => `
          <div class="card" onclick="abrir('${t.slug}')">
            <div><span class="dot ${t.status_geral}"></span><strong>${t.nome}</strong></div>
            <div class="muted">ult. manut.: ${t.ultima_manutencao ? t.ultima_manutencao.script_nome + " (" + t.ultima_manutencao.status + ")" : "nenhuma"}</div>
            <div class="muted">backup: ${t.ultimo_backup ? "ok" : "nunca"}</div>
          </div>`).join("");
      } catch (e) { $("grid").innerHTML = `<div>${e.message}</div>`; }
    }

    async function abrir(slug) {
      slugAtual = slug;
      $("detalhe").style.display = "block";
      $("d-nome").textContent = slug;
      $("d-out").textContent = "-";
      const { data } = await api(`/api/v1/tenants/${slug}/scripts`);
      $("d-scripts").innerHTML = data.map((s) => `
        <div class="row">
          <strong>${s.nome}</strong>
          <input id="p-${s.script_id}" placeholder="${s.parametros_default || "sem parametros"}" />
          <button onclick="run(${s.script_id})">executar</button>
        </div>`).join("");
      loadLogs();
    }

    async function run(sid) {
      const raw = $(`p-${sid}`).value.trim();
      const parametros = raw ? raw.split(/\s+/) : [];
      $("d-out").textContent = "Executando...";
      try {
        const { data } = await api(`/api/v1/tenants/${slugAtual}/scripts/${sid}/run`, {
          method: "POST", body: JSON.stringify({ parametros }) });
        $("d-out").textContent = `# ${data.status} (exit ${data.exit_code})\n\n` + (data.stdout || "") + (data.stderr ? "\n[stderr]\n" + data.stderr : "");
        loadLogs(); loadDashboard();
      } catch (e) { $("d-out").textContent = e.message; }
    }

    async function loadLogs() {
      const { data } = await api(`/api/v1/tenants/${slugAtual}/logs`);
      $("d-logs").innerHTML = data.map((l) => `<div class="muted">${l.ocorrido_em} — ${l.script_nome || l.tipo} ${l.status || ""}</div>`).join("") || "<div class='muted'>sem registros</div>";
    }

    loadDashboard();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verificacao manual**

Run:
```bash
rm -f isyone.db
ISY_SEED_DEMO=true uvicorn app.main:app --port 8000 &
sleep 2
curl -s -o /dev/null -w "ui=%{http_code}\n" localhost:8000/ui/
curl -s localhost:8000/api/v1/admin/tenants/health -H "X-Isy-Token: 544c5787-613a-4ac2-8e61-9e6486f8d74a" | head -c 300
kill %1; rm -f isyone.db
```
Expected: `ui=200` e JSON com 5 clientes e `status_geral` variando.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat: dashboard neutro multi-cliente"
```

---

## Milestone 8 — Deploy Railway

### Task 13: Config de deploy Railway (seedado) + plano B local

**Files:**
- Create: `railway.json`
- Modify: `docker-compose.yml` (garantir seed; sem mudanca de volume)
- Modify: `README.md` (secao deploy)

- [ ] **Step 1: railway.json**

Create `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": { "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT", "restartPolicyType": "ON_FAILURE" }
}
```

> Variaveis no painel do Railway: `ISY_TOKEN`, `ISY_DATABASE_URL` (referencia ao Postgres do projeto, ex.: `${{Postgres.DATABASE_URL}}` convertido para `postgresql+psycopg://...`), `ISY_SEED_DEMO=true`, `ISY_SCRIPTS_DIR=/opt/isyone/scripts`. Se usar Postgres, adicionar `psycopg[binary]` ao `requirements.txt`.

- [ ] **Step 2: Dependencia Postgres (se for usar Postgres no Railway)**

In `requirements.txt`, adicione (apenas se o deploy usar Postgres; SQLite nao precisa):

```
psycopg[binary]==3.2.3
```

- [ ] **Step 3: Atualizar README (deploy)**

In `README.md`, na secao "Como rodar (demo)", adicione um bloco de deploy:

```markdown
### Deploy (Railway)

- Build pelo `Dockerfile` (config em `railway.json`).
- Variaveis: `ISY_TOKEN`, `ISY_DATABASE_URL` (Postgres do projeto), `ISY_SEED_DEMO=true`, `ISY_SCRIPTS_DIR=/opt/isyone/scripts`.
- Sobe seedado com os 5 clientes de demonstracao.
- Plano B (video): `docker compose up --build` local — nunca depender de rede ao vivo.
```

- [ ] **Step 4: Verificacao local do build Docker**

Run: `docker compose build`
Expected: build conclui sem erro. (Se Docker indisponivel no ambiente, pular e validar no Railway.)

- [ ] **Step 5: Commit**

```bash
git add railway.json requirements.txt README.md
git commit -m "chore: config de deploy Railway seedado"
```

---

## Verificacao final

- [ ] Rodar a suite inteira: `python -m pytest -q` — todos PASS.
- [ ] Smoke local: `ISY_SEED_DEMO=true uvicorn app.main:app` → abrir `/ui`, ver 5 clientes com status variado, executar uma manutencao, ver auditoria e dashboard atualizarem.
- [ ] Atualizar `docs/architecture.md` se algum detalhe divergir (camadas continuam validas; mencionar event store e tenants).

---

## Self-Review (cobertura do spec)

- Tenant de primeira classe → Tasks 2, 7.
- Scripts hibridos (catalogo + extras + defaults por tenant) → Tasks 3, 7, 8, 11.
- Auth dois niveis → Task 4 (+ uso em 7, 8).
- Event sourcing pragmatico (events + ExecutionCompleted/TokenRotated) → Tasks 1, 5, 7.
- Projecao de saude on-read → Task 6 (+ dashboard 7, health 8).
- UI neutra → Task 12.
- Seed 5 clientes + eventos historicos → Task 11.
- Deploy Railway seedado + plano B local → Task 13.
- Seguranca (shell=False, whitelist por tenant, anti traversal, compare_digest, isolamento) → Tasks 4, 5, 8 (+ testes em test_auth_isolation, test_execution_service, test_tenant_routes).
