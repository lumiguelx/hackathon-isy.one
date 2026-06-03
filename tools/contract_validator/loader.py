"""Carrega o spec OpenAPI de uma URL (app rodando) ou de um arquivo local."""

import json
from pathlib import Path

import httpx


class SpecLoadError(RuntimeError):
    """Falha ao obter ou parsear o spec OpenAPI."""


def from_url(base_url: str, timeout: float = 5.0) -> dict:
    """Busca GET {base_url}/openapi.json da app rodando."""
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SpecLoadError(
            f"nao foi possivel obter o spec em {url}: {exc}. A app esta no ar?"
        ) from exc
    try:
        return resp.json()
    except ValueError as exc:
        raise SpecLoadError(f"resposta de {url} nao e JSON valido.") from exc


def from_file(path: str) -> dict:
    """Le o spec de um arquivo openapi.json local."""
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpecLoadError(f"arquivo de spec nao encontrado: {path}") from exc
    except ValueError as exc:
        raise SpecLoadError(f"spec em {path} nao e JSON valido.") from exc
