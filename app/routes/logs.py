"""Rota de auditoria: historico de execucoes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_token
from app.repositories import executions_repo
from app.schemas import ExecutionOut

router = APIRouter(
    prefix="/api/v1/logs",
    tags=["Auditoria"],
    dependencies=[Depends(verify_token)],
)


@router.get("")
def list_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    execucoes = executions_repo.list_recent(db, limit=limit)
    return ok([ExecutionOut.model_validate(e).model_dump(mode="json") for e in execucoes])
