"""Self-service publico: cadastro que provisiona o ambiente do cliente sozinho.

POST /api/v1/registro cria o tenant (slug+token unicos), dispara o provisionar.sh
e devolve o progresso ao vivo via SSE (text/event-stream), terminando com as
credenciais. Sem token de admin — protegido por validacao + rate-limit simples.
"""

import json
import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.repositories import (
    events_repo,
    scripts_repo,
    tenant_scripts_repo,
    tenants_repo,
)
from app.schemas import RegistroRequest, TenantCreate
from app.services import execution_service, notifications

router = APIRouter(tags=["Self-service"])

# Rate-limit simples em memoria: no maximo N cadastros por IP por janela.
_RATE_MAX = 5
_RATE_JANELA_S = 3600
_acessos: dict[str, list[float]] = {}


def _rate_limit(ip: str) -> None:
    agora = time.time()
    recentes = [t for t in _acessos.get(ip, []) if agora - t < _RATE_JANELA_S]
    if len(recentes) >= _RATE_MAX:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitos cadastros deste IP. Tente novamente mais tarde.",
        )
    recentes.append(agora)
    _acessos[ip] = recentes


def _slugify(nome: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return base or "cliente"


def _slug_unico(db: Session, nome: str) -> str:
    base = _slugify(nome)
    slug = base
    n = 2
    while tenants_repo.get_by_slug(db, slug) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _sse(evento: str, data: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/api/v1/registro", summary="Cadastro self-service (SSE)")
def registro(
    body: RegistroRequest, request: Request, db: Session = Depends(get_db)
) -> StreamingResponse:
    """Cadastra um cliente self-service e transmite o provisionamento via SSE.

    Cria o tenant (slug e token unicos), dispara o provisionar.sh e emite os
    eventos tenant/log/done em text/event-stream ate devolver as credenciais.
    """
    _rate_limit(request.client.host if request.client else "desconhecido")

    slug = _slug_unico(db, body.nome)
    dominio = f"{slug}.isy.one"
    porta = 8200 + len(tenants_repo.list_all(db))
    # Token de autenticacao do cliente: parte aleatoria com 256 bits de entropia.
    # O prefixo com o slug e so para leitura humana, nao e o segredo.
    token = f"tok-{slug}-{secrets.token_urlsafe(32)}"
    ssh_host = settings.self_service_ssh_host or None
    ssh_port = settings.self_service_ssh_port if ssh_host else None

    tenant = tenants_repo.create(
        db,
        TenantCreate(
            slug=slug,
            nome=body.nome,
            dominio=dominio,
            porta=porta,
            db_name=f"db_{slug.replace('-', '_')}",
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            token=token,
        ),
    )

    script = scripts_repo.get_by_nome(db, "provisionar")
    if script is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Catalogo sem script 'provisionar'."
        )

    # Disponibiliza o catalogo para o novo cliente operar pelo painel depois.
    for s in scripts_repo.list_global(db):
        default = slug if s.nome == "docker_status" else ("30" if s.nome == "cleanup_logs" else "")
        tenant_scripts_repo.upsert(db, tenant.id, s.id, default, True)

    tenant_id, script_id = tenant.id, script.id

    def stream():
        yield _sse("tenant", {"slug": slug, "nome": body.nome, "plano": body.plano})
        payload: dict = {"status": "falha"}
        try:
            with SessionLocal() as db2:
                t = tenants_repo.get(db2, tenant_id)
                sc = scripts_repo.get(db2, script_id)
                for kind, data in execution_service.stream_script(
                    t, sc, [slug, dominio, str(porta)]
                ):
                    if kind == "out":
                        yield _sse("log", {"line": data})
                    else:
                        payload = data  # type: ignore[assignment]
                events_repo.append(
                    db2,
                    ev.EXECUTION_COMPLETED,
                    payload,
                    tenant_id=tenant_id,
                    script_id=script_id,
                )
                if t is not None:
                    notifications.notify_execution(db2, t, payload, origem="registro")
        except execution_service.ScriptNotExecutable as exc:
            yield _sse("log", {"line": f"ERRO: {exc}"})
        yield _sse(
            "done",
            {
                "slug": slug,
                "token": token,
                "url": f"https://{dominio}",
                "status": payload.get("status"),
            },
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
