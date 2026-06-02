"""Envelope JSON padronizado da API."""

from typing import Any


def ok(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def fail(message: str, data: Any = None) -> dict[str, Any]:
    return {"status": "error", "data": data, "message": message}
