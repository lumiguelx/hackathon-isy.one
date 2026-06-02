"""Rotas de operacao: listar scripts ativos e executar."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_token
from app.repositories import scripts_repo
from app.schemas import ExecutionOut, RunRequest, ScriptOut
from app.services import execution_service

router = APIRouter(
    prefix="/api/v1/scripts",
    tags=["Operacao"],
    dependencies=[Depends(verify_token)],
)


@router.get("")
def list_scripts(db: Session = Depends(get_db)) -> dict:
    scripts = scripts_repo.list_active(db)
    return ok([ScriptOut.model_validate(s).model_dump(mode="json") for s in scripts])


@router.post("/{script_id}/run")
def run_script(
    script_id: int,
    body: RunRequest,
    db: Session = Depends(get_db),
) -> dict:
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    if not script.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Script inativo.")

    try:
        execution = execution_service.run(db, script, body.parametros)
    except execution_service.ScriptNotExecutable as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    data = ExecutionOut.model_validate(execution).model_dump(mode="json")
    message = "Script executado com sucesso." if execution.status == "sucesso" else "Script retornou falha."
    return ok(data, message)
