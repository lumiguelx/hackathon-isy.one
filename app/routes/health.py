"""Healthcheck publico (sem token)."""

from fastapi import APIRouter

from app.core.responses import ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return ok({"alive": True})
