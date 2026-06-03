"""Healthcheck e config publica do painel (sem token)."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import ok

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness do servico")
def health() -> dict:
    """Liveness do servico: responde 200 com {alive: true} sem tocar no banco."""
    return ok({"alive": True})


@router.get("/api/v1/config", summary="Config publica do painel")
def ui_config() -> dict:
    """Config nao-sensivel consumida pelo painel /ui (ex.: link do Grafana)."""
    return ok({"grafana_url": settings.grafana_url})
