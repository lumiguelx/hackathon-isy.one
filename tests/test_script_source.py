"""Testa os endpoints de codigo do script (editor inline, Modulo 2)."""

from pathlib import Path

import pytest

from app.core.config import settings
from tests.conftest import AUTH

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scripts"


def _script(client, nome, caminho):
    r = client.post(
        "/api/v1/admin/scripts",
        headers=AUTH,
        json={"nome": nome, "caminho": caminho, "categoria": "other"},
    )
    return r.json()["data"]["id"]


def test_get_source_le_arquivo(client):
    sid = _script(client, "echo", "echo_args.sh")
    r = client.get(f"/api/v1/admin/scripts/{sid}/source", headers=AUTH)
    assert r.status_code == 200
    assert "ARG:" in r.json()["data"]["conteudo"]


def test_put_desabilitado_por_padrao_403(client):
    sid = _script(client, "echo2", "echo_args.sh")
    r = client.put(
        f"/api/v1/admin/scripts/{sid}/source",
        headers=AUTH,
        json={"conteudo": "#!/bin/bash\necho oi\n"},
    )
    assert r.status_code == 403


def test_extensao_nao_permitida_422(client):
    sid = _script(client, "notas", "notes.txt")
    r = client.get(f"/api/v1/admin/scripts/{sid}/source", headers=AUTH)
    assert r.status_code == 422


def test_put_grava_quando_habilitado(client):
    settings.script_edit_enabled = True
    alvo = _FIXTURES / "tmp_src.sh"
    try:
        sid = _script(client, "tmpsrc", "tmp_src.sh")
        r = client.put(
            f"/api/v1/admin/scripts/{sid}/source",
            headers=AUTH,
            json={"conteudo": "#!/usr/bin/env bash\necho gravado\n"},
        )
        assert r.status_code == 200
        assert alvo.is_file() and "gravado" in alvo.read_text()
        g = client.get(f"/api/v1/admin/scripts/{sid}/source", headers=AUTH)
        assert "gravado" in g.json()["data"]["conteudo"]
    finally:
        settings.script_edit_enabled = False
        alvo.unlink(missing_ok=True)


@pytest.mark.parametrize("metodo", ["get", "put"])
def test_exige_token_admin(client, metodo):
    sid = _script(client, f"sec_{metodo}", "echo_args.sh")
    fn = client.get if metodo == "get" else (
        lambda url, **k: client.put(url, json={"conteudo": ""}, **k)
    )
    r = fn(f"/api/v1/admin/scripts/{sid}/source", headers={"X-Isy-Token": "errado"})
    assert r.status_code == 401
