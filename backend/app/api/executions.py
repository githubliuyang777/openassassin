from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.execution import ExecutionResponse, ExecutionListResponse
from app.models.execution import Execution

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=ExecutionListResponse)
def list_executions(
    page: int = 1,
    page_size: int = 20,
    script_id: int = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    q = db.query(Execution)
    if script_id:
        q = q.filter(Execution.script_id == script_id)
    total = q.count()
    items = q.order_by(Execution.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return ex


@router.get("/{execution_id}/log")
def get_execution_log(
    execution_id: int,
    tail: int = 0,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    if not ex.log_path:
        return {"log": ""}
    try:
        with open(ex.log_path) as f:
            lines = f.readlines()
            if tail > 0:
                lines = lines[-tail:]
            return {"log": "".join(lines)}
    except FileNotFoundError:
        return {"log": ""}
