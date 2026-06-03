"""Configuracao dos testes: banco e diretorio de scripts isolados.

As variaveis de ambiente sao definidas ANTES de importar a aplicacao, para que
o objeto Settings (instanciado no import) ja use os valores de teste.
"""

import os
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_FIXTURE_SCRIPTS = _TESTS_DIR / "fixtures" / "scripts"
_TEST_DB = _TESTS_DIR / "test_isyone.db"

os.environ["ISY_TOKEN"] = "test-token-123456"
os.environ["ISY_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ISY_SCRIPTS_DIR"] = str(_FIXTURE_SCRIPTS)
os.environ["ISY_ALERT_WEBHOOK_URL"] = ""
# A thread do agendador nao deve subir nos testes (o tick e testado direto).
os.environ["ISY_SCHEDULER_ENABLED"] = "false"
os.environ["ISY_SEED_DEMO"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

TOKEN = "test-token-123456"
AUTH = {"X-Isy-Token": TOKEN}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
