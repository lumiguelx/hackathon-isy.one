"""Schemas Pydantic de entrada e saida da API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ParamSpec(BaseModel):
    """Definicao estruturada de um parametro de script (estilo script-server)."""

    nome: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=40)
    rotulo: str = Field(default="", max_length=80)
    tipo: str = Field(default="text", max_length=10)  # int | text | select | bool
    arg: str = Field(default="", max_length=40)  # flag (ex.: -s, --size); vazio=posicional
    obrigatorio: bool = False
    default: str = Field(default="", max_length=255)
    minimo: int | None = None
    maximo: int | None = None
    choices: list[str] = Field(default_factory=list)
    secret: bool = False
    env: str = Field(default="", max_length=60)  # injeta como env var em vez de argv
    constante: str = Field(default="", max_length=255)  # forca valor, ignora input
    sem_valor: bool = False  # flag sem valor (bool): inclui so o arg quando true


class ScriptCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    caminho: str = Field(default="", max_length=255)
    template: str | None = Field(default=None, max_length=2000)
    tipo: str = Field(default="arquivo", max_length=20)
    parametros: str = Field(default="", max_length=255)
    param_schema: list[ParamSpec] = Field(default_factory=list)
    descricao: str = Field(default="", max_length=255)
    categoria: str = "other"
    tenant_id: int | None = None
    ativo: bool = True

    @model_validator(mode="after")
    def _coerente(self) -> "ScriptCreate":
        if self.tipo not in ("arquivo", "template"):
            raise ValueError("tipo deve ser 'arquivo' ou 'template'.")
        if self.tipo == "arquivo" and not self.caminho:
            raise ValueError("caminho e obrigatorio para tipo 'arquivo'.")
        if self.tipo == "template" and not (self.template and self.template.strip()):
            raise ValueError("template e obrigatorio para tipo 'template'.")
        return self


class ScriptUpdate(BaseModel):
    # Patch parcial: a coerencia tipo/caminho/template e o dono (imutavel) sao
    # validados em script_service.update, nao por model_validator aqui.
    nome: str | None = Field(default=None, max_length=120)
    caminho: str | None = Field(default=None, max_length=255)
    template: str | None = Field(default=None, max_length=2000)
    tipo: str | None = Field(default=None, max_length=20)
    parametros: str | None = Field(default=None, max_length=255)
    param_schema: list[ParamSpec] | None = None
    descricao: str | None = Field(default=None, max_length=255)
    categoria: str | None = None
    ativo: bool | None = None


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    caminho: str
    template: str | None
    tipo: str
    parametros: str
    descricao: str
    categoria: str
    tenant_id: int | None
    ativo: bool
    criado_em: datetime
    param_schema: list[dict] = Field(default_factory=list)
    parametros_schema: list[dict] = Field(default_factory=list)

    @field_validator("param_schema", mode="before")
    @classmethod
    def _none_para_lista(cls, v):
        # Linhas migradas (ADD COLUMN) podem vir com param_schema NULL.
        return v or []


class ScriptSource(BaseModel):
    # Codigo do .sh/.py a gravar no diretorio de scripts (editor inline).
    conteudo: str = Field(default="", max_length=100_000)


class RunRequest(BaseModel):
    # Compat: lista posicional (cada item vira um argv). Usada quando o script
    # nao tem param_schema estruturado.
    parametros: list[str] = Field(default_factory=list)
    # Valores nomeados por parametro estruturado ({nome: valor}); o backend monta
    # o argv/env a partir do param_schema do script.
    valores: dict[str, str] = Field(default_factory=dict)


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


class TenantCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=60)
    nome: str = Field(min_length=1, max_length=120)
    dominio: str = Field(min_length=1, max_length=120)
    porta: int = Field(ge=1, le=65535)
    db_name: str = Field(min_length=1, max_length=120)
    ssh_host: str | None = Field(default=None, max_length=255)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    token: str = Field(min_length=8, max_length=255)
    ativo: bool = True


class TenantUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    dominio: str | None = Field(default=None, max_length=120)
    porta: int | None = Field(default=None, ge=1, le=65535)
    db_name: str | None = Field(default=None, max_length=120)
    ssh_host: str | None = Field(default=None, max_length=255)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ativo: bool | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    dominio: str
    porta: int
    db_name: str
    ssh_host: str | None
    ssh_port: int | None
    ativo: bool
    criado_em: datetime


class RegistroRequest(BaseModel):
    """Cadastro self-service publico (plano free)."""

    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=180)
    plano: str = Field(default="free", max_length=20)


class TenantScriptBinding(BaseModel):
    script_id: int
    parametros_default: str = Field(default="", max_length=255)
    ativo: bool = True


class TenantScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    script_id: int
    parametros_default: str
    ativo: bool


def _validar_cron(expr: str) -> None:
    # Import local para evitar acoplar o carregamento dos schemas ao pacote services.
    from app.services import cron

    try:
        cron.validate(expr)
    except ValueError as exc:
        raise ValueError(f"cron invalido: {exc}") from exc


class ScheduleCreate(BaseModel):
    script_id: int
    cron_expr: str = Field(min_length=1, max_length=100)
    parametros: str = Field(default="", max_length=255)
    ativo: bool = True

    @model_validator(mode="after")
    def _cron_valido(self) -> "ScheduleCreate":
        _validar_cron(self.cron_expr)
        return self


class ScheduleUpdate(BaseModel):
    cron_expr: str | None = Field(default=None, max_length=100)
    parametros: str | None = Field(default=None, max_length=255)
    ativo: bool | None = None

    @model_validator(mode="after")
    def _cron_valido(self) -> "ScheduleUpdate":
        if self.cron_expr is not None:
            _validar_cron(self.cron_expr)
        return self


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    script_id: int
    cron_expr: str
    parametros: str
    ativo: bool
    ultima_exec: datetime | None
    criado_em: datetime
    # Enriquecidos na rota admin para a tabela do console (None na rota por cliente).
    script_nome: str | None = None
    tenant_nome: str | None = None
    tenant_slug: str | None = None
