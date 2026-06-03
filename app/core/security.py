"""Autenticacao em dois niveis (admin + tenant) e resolucao segura de caminho.

- verify_admin: exige o token administrativo (gestao de tenants/catalogo).
- verify_tenant: aceita o token do proprio tenant OU o token admin (que abre tudo),
  e nunca o token de outro tenant -> isolamento entre clientes.
Comparacao em tempo constante (compare_digest) para evitar timing attack.
"""

import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import Tenant
from app.repositories import config_repo, tenants_repo

# Declara o X-Isy-Token como esquema de seguranca: liga o botao "Authorize" no
# Swagger e o cadeado nas rotas protegidas. auto_error=False para mantermos as
# mensagens de erro proprias (401 com texto em pt-br) em vez do default do FastAPI.
api_key_header = APIKeyHeader(
    name="X-Isy-Token",
    auto_error=False,
    scheme_name="X-Isy-Token",
    description="Token de autenticacao (admin ou do proprio cliente).",
)


def verify_admin(
    x_isy_token: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
) -> None:
    admin = config_repo.get_token(db)
    if not x_isy_token or not secrets.compare_digest(x_isy_token, admin):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token admin invalido ou ausente."
        )


def verify_tenant(
    slug: str,
    x_isy_token: str | None = Security(api_key_header),
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


class ScriptPathError(ValueError):
    """Caminho de script invalido ou fora do diretorio permitido."""


def resolve_script_path(caminho: str) -> Path:
    """Resolve o caminho do script dentro do diretorio montado.

    Rejeita path traversal: o arquivo resolvido precisa residir sob scripts_dir.
    Nao executa nada; so valida e devolve o Path absoluto.
    """
    base = Path(settings.scripts_dir).resolve()
    candidate = (base / caminho).resolve()
    if base != candidate and base not in candidate.parents:
        raise ScriptPathError("Caminho fora do diretorio de scripts permitido.")
    return candidate
