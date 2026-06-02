"""Schemas Pydantic de entrada e saida da API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScriptCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    caminho: str = Field(min_length=1, max_length=255)
    parametros: str = Field(default="", max_length=255)
    descricao: str = Field(default="", max_length=255)
    ativo: bool = True


class ScriptUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    caminho: str | None = Field(default=None, max_length=255)
    parametros: str | None = Field(default=None, max_length=255)
    descricao: str | None = Field(default=None, max_length=255)
    ativo: bool | None = None


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    caminho: str
    parametros: str
    descricao: str
    ativo: bool
    criado_em: datetime


class RunRequest(BaseModel):
    # Lista de argumentos a passar ao script. Cada item vira um argv separado.
    parametros: list[str] = Field(default_factory=list)


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    script_nome: str
    parametros: str
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    executado_em: datetime
    duracao_ms: int


class TokenUpdate(BaseModel):
    token: str = Field(min_length=8, max_length=255)
