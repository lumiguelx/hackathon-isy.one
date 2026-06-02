from app.core import events as ev
from app.core.db import SessionLocal
from app.repositories import events_repo
from tests.conftest import client  # noqa: F401  (fixture cria/limpa tabelas)


def test_append_e_list_por_tenant(client):
    with SessionLocal() as db:
        events_repo.append(
            db, ev.EXECUTION_COMPLETED, {"status": "sucesso"}, tenant_id=1
        )
        events_repo.append(db, ev.EXECUTION_COMPLETED, {"status": "falha"}, tenant_id=1)
        events_repo.append(
            db, ev.EXECUTION_COMPLETED, {"status": "sucesso"}, tenant_id=2
        )

        do_tenant1 = events_repo.list_by_tenant(db, 1)
        assert len(do_tenant1) == 2
        # ordem desc: o ultimo inserido vem primeiro
        assert do_tenant1[0].payload["status"] == "falha"
