"""Isy.One Shell Automation API — ponto de entrada do FastAPI."""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.seed import seed_demo
from app.routes import admin, health, registro, tenants
from app.services import scheduler

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.seed_demo:
        with SessionLocal() as db:
            seed_demo(db)
    # Agendador: thread daemon que dispara execucoes cron a cada minuto.
    stop_event = threading.Event()
    thread: threading.Thread | None = None
    if settings.scheduler_enabled:
        thread = threading.Thread(
            target=scheduler.run_loop,
            args=(stop_event,),
            name="isyone-scheduler",
            daemon=True,
        )
        thread.start()
    try:
        yield
    finally:
        stop_event.set()
        if thread is not None:
            thread.join(timeout=2)


_DESCRIPTION = """
Execucao controlada e auditada de shell scripts de manutencao em servidores de
clientes (multi-tenant), sem SSH manual.

## Autenticacao

Todas as rotas protegidas usam o header **`X-Isy-Token`**. Clique em **Authorize**
e informe o token:

- **Admin** (gestao de tenants, catalogo e bindings): abre todas as rotas.
- **Cliente** (token do proprio tenant): acessa apenas os recursos daquele cliente.

## Envelope de resposta

Toda resposta segue o formato `{ "status": "success" | "error", "data": ..., "message": "..." }`.
"""

_TAGS = [
    {"name": "health", "description": "Liveness e config publica do painel (sem token)."},
    {"name": "Self-service", "description": "Cadastro publico que provisiona o cliente sozinho (SSE)."},
    {"name": "Administracao", "description": "Gestao de tenants, catalogo de scripts, bindings e tokens. Exige token admin."},
    {"name": "Cliente", "description": "Operacao por cliente: scripts disponiveis, execucao, logs e saude."},
]

app = FastAPI(
    title="Isy.One Shell Automation API",
    version="1.0.0",
    description=_DESCRIPTION,
    summary="API de automacao de shell multi-tenant com execucao auditada.",
    openapi_tags=_TAGS,
    contact={"name": "Isy.One", "url": "https://isy.one/hackaton/"},
    license_info={"name": "Proprietario"},
    lifespan=lifespan,
    # Doc principal e o Scalar branded em /docs (rota abaixo); o Swagger fica
    # disponivel em /swagger para debug e o ReDoc padrao e desligado.
    docs_url="/swagger",
    redoc_url=None,
)

# CORS restrito a origens conhecidas (ex.: Swagger no GitHub Pages). Sem cookies:
# a autenticacao e so pelo header X-Isy-Token.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-Isy-Token", "Content-Type"],
)

app.include_router(health.router)
app.include_router(registro.router)
app.include_router(admin.router)
app.include_router(tenants.router)


# Referencia de API branded (Scalar) servida em /docs.
@app.get("/docs", include_in_schema=False)
def scalar_docs() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "scalar.html"))


# Pagina publica de cadastro self-service.
@app.get("/registro", include_in_schema=False)
def registro_page() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "registro.html"))


# UI de demonstracao (pagina estatica servida pelo proprio FastAPI) em /ui.
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")
