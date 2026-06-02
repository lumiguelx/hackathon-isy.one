"""Configuracao do servico via variaveis de ambiente."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ISY_", env_file=".env", extra="ignore"
    )

    # Token inicial; semeado no banco no primeiro boot. Depois e rotacionavel via API.
    token: str = "544c5787-613a-4ac2-8e61-9e6486f8d74a"

    # Banco relacional. SQLite por padrao; troque por uma URL Postgres em producao.
    database_url: str = "sqlite:///./isyone.db"

    # Diretorio onde residem os shell scripts (montado por volume no container).
    scripts_dir: str = "./scripts"

    # Timeout maximo (segundos) por execucao de script.
    exec_timeout: int = 30

    # Limite de caracteres de stdout/stderr persistidos por execucao.
    output_limit: int = 10_000

    # Webhook opcional para alertas (Discord/Telegram-compativel). Vazio = desativado.
    alert_webhook_url: str = ""

    # Se True, semeia scripts de demonstracao no primeiro boot (banco vazio).
    seed_demo: bool = False


settings = Settings()
