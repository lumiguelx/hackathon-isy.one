"""Rotas administrativas: CRUD de scripts e rotacao de token."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.responses import ok
from app.core.security import verify_token
from app.repositories import config_repo, scripts_repo
from app.schemas import ScriptCreate, ScriptOut, ScriptUpdate, TokenUpdate
from app.services import script_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Administracao"],
    dependencies=[Depends(verify_token)],
)


def _out(script) -> dict:
    return ScriptOut.model_validate(script).model_dump(mode="json")


@router.get("/scripts")
def list_all(db: Session = Depends(get_db)) -> dict:
    return ok([_out(s) for s in scripts_repo.list_all(db)])


@router.post("/scripts", status_code=status.HTTP_201_CREATED)
def create_script(body: ScriptCreate, db: Session = Depends(get_db)) -> dict:
    try:
        script = script_service.create(db, body)
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ok(_out(script), "Script cadastrado.")


@router.put("/scripts/{script_id}")
def update_script(script_id: int, body: ScriptUpdate, db: Session = Depends(get_db)) -> dict:
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    try:
        script = script_service.update(db, script, body)
    except script_service.ScriptValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ok(_out(script), "Script atualizado.")


@router.delete("/scripts/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db)) -> dict:
    script = scripts_repo.get(db, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script nao encontrado.")
    scripts_repo.delete(db, script)
    return ok(message="Script removido.")


@router.put("/token")
def rotate_token(body: TokenUpdate, db: Session = Depends(get_db)) -> dict:
    config_repo.set_token(db, body.token)
    return ok(message="Token rotacionado. Use o novo valor nas proximas chamadas.")
