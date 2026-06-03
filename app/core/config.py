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

    # Webhook global de notificacao (Slack Incoming Webhook). Vazio = desativado.
    # Cada tenant pode sobrescrever com o seu (tenant.alert_webhook_url); este e o fallback.
    alert_webhook_url: str = ""

    # Gatilhos de notificacao (best-effort; nunca quebram a execucao).
    notify_on_failure: bool = True  # script terminou com erro
    notify_on_success: bool = True  # manutencao manual concluida com sucesso
    notify_on_scheduled: bool = True  # execucao disparada pelo agendador (cron)
    notify_on_fleet_red: bool = True  # saude do cliente virou vermelho

    # URL do Grafana de observabilidade da frota. Vazio = botao oculto no painel.
    grafana_url: str = ""

    # Se True, semeia scripts de demonstracao no primeiro boot (banco vazio).
    seed_demo: bool = False

    # Se True, sobe a thread do agendador (cron) no startup. Desligado nos testes.
    scheduler_enabled: bool = True

    # Usuario SSH para alcancar o servidor do cliente (quando tenant.ssh_host esta setado).
    # A chave privada vem de ISY_SSH_KEY (secret), lida pelos scripts via env.
    ssh_user: str = "isyone"

    # Servidor onde o self-service (POST /registro) provisiona novos clientes.
    # Vazio = provisionamento roda local (saida simulada).
    self_service_ssh_host: str = ""
    self_service_ssh_port: int = 22

    # SSH do cliente de demo (caixa AWS); setado, o seed liga o docker_ctl real.
    demo_ssh_host: str = ""
    demo_ssh_port: int = 22

    # Habilita gravar o codigo do .sh pela UI (sensivel: codigo executavel em disco).
    script_edit_enabled: bool = False


settings = Settings()
