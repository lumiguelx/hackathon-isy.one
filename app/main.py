"""Isy.One Shell Automation API — ponto de entrada do FastAPI."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.seed import seed_demo
from app.routes import admin, health, logs, scripts

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.seed_demo:
        with SessionLocal() as db:
            seed_demo(db)
    yield


app = FastAPI(
    title="Isy.One Shell Automation API",
    version="1.0.0",
    description="Execucao controlada e auditada de shell scripts de manutencao.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(scripts.router)
app.include_router(admin.router)
app.include_router(logs.router)

# UI de demonstracao (pagina estatica servida pelo proprio FastAPI) em /ui.
app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")
