# Imagem leve exigida pela banca.
FROM python:3.11-slim

# Nao gera .pyc e nao bufferiza stdout (logs em tempo real).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# openssh-client: o painel alcanca o servidor de cada cliente por SSH.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Instala deps primeiro para aproveitar cache de camada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo da aplicacao.
COPY app ./app

# Scripts embarcados na imagem (em deploys sem volume, ex.: Railway). No
# docker-compose local, o volume ./scripts:ro sobrepoe este diretorio.
COPY scripts /opt/isyone/scripts
ENV ISY_SCRIPTS_DIR=/opt/isyone/scripts

EXPOSE 8000

# Shell form para expandir $PORT (Railway injeta PORT; default 8000 local).
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
