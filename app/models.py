"""Models SQLAlchemy: scripts, execucoes e config (token)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    execucoes: Mapped[list["Execution"]] = relationship(back_populates="script")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    # Snapshot do nome, preservado mesmo se o script for removido depois.
    script_nome: Mapped[str] = mapped_column(String(120))
    parametros: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16))  # "sucesso" | "falha"
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    executado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    duracao_ms: Mapped[int] = mapped_column(Integer, default=0)

    script: Mapped["Script | None"] = relationship(back_populates="execucoes")


class Config(Base):
    __tablename__ = "config"

    # Linha unica (id=1) com o token vigente, rotacionavel via API.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(255))
