"""Models SQLAlchemy: scripts, eventos (event store) e config (token)."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    # Caminho do .sh relativo ao diretorio montado (validado no service).
    caminho: Mapped[str] = mapped_column(String(255))
    parametros: Mapped[str] = mapped_column(String(255), default="")
    descricao: Mapped[str] = mapped_column(String(255), default="")
    categoria: Mapped[str] = mapped_column(String(20), default="other")
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    dominio: Mapped[str] = mapped_column(String(120))
    porta: Mapped[int] = mapped_column(Integer)
    db_name: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    token: Mapped[str] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True
    )
    script_id: Mapped[int | None] = mapped_column(
        ForeignKey("scripts.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TenantScript(Base):
    __tablename__ = "tenant_scripts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "script_id", name="uq_tenant_script"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"))
    parametros_default: Mapped[str] = mapped_column(String(255), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Config(Base):
    __tablename__ = "config"

    # Linha unica (id=1) com o token vigente, rotacionavel via API.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(255))
