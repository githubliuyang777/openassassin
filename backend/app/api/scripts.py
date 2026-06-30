import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.script import ScriptCreate, ScriptUpdate, ScriptExecuteRequest, ScriptResponse
from app.services import script_service, credential_service
from app.services.sandbox_service import execute_script
from app.models.credential import Credential
from app.models.execution import Execution
from app.config import settings

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("")
def list_scripts(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return script_service.list_scripts(db, page, page_size, search)


@router.post("", response_model=ScriptResponse, status_code=201)
def create_script(
    data: ScriptCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return script_service.create_script(db, data)


@router.get("/{script_id}", response_model=ScriptResponse)
def get_script(
    script_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    s = script_service.get_script(db, script_id)
    if not s:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return s


@router.put("/{script_id}", response_model=ScriptResponse)
def update_script(
    script_id: int,
    data: ScriptUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    s = script_service.get_script(db, script_id)
    if not s:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return script_service.update_script(db, s, data)


@router.delete("/{script_id}", status_code=204)
def delete_script(
    script_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    s = script_service.get_script(db, script_id)
    if not s:
        raise HTTPException(status_code=404, detail="脚本不存在")
    script_service.delete_script(db, s)


@router.post("/{script_id}/execute")
def execute_script_endpoint(
    script_id: int,
    body: ScriptExecuteRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    s = script_service.get_script(db, script_id)
    if not s:
        raise HTTPException(status_code=404, detail="脚本不存在")

    credential_values = {}
    if body.credential_ids:
        creds = db.query(Credential).filter(Credential.id.in_(body.credential_ids)).all()
        for c in creds:
            credential_values[c.key] = credential_service.decrypt(c.encrypted_value)

    execution = Execution(
        script_id=script_id,
        status="running",
        triggered_by=user["username"],
        credential_ids=body.credential_ids,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    os.makedirs(settings.log_dir, exist_ok=True)
    log_path = os.path.join(settings.log_dir, f"{execution.id}.log")

    result = execute_script(
        script_type=s.type,
        content=s.content,
        timeout=s.timeout,
        env_vars=s.env_vars or {},
        credential_values=credential_values,
    )

    with open(log_path, "w") as f:
        f.write(result["log"])

    execution.status = result["status"]
    execution.exit_code = result["exit_code"]
    execution.log_path = log_path
    db.commit()
    db.refresh(execution)

    return {
        "id": execution.id,
        "status": execution.status,
        "exit_code": execution.exit_code,
        "log": result["log"],
    }
