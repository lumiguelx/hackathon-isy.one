"""Healthcheck e config publica do painel (sem token)."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return ok({"alive": True})


@router.get("/api/v1/config")
def ui_config() -> dict:
    """Config nao-sensivel consumida pelo painel /ui (ex.: link do Grafana)."""
    return ok({"grafana_url": settings.grafana_url})
