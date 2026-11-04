from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.vulnerability import (
    CatalogItem,
    ComponentCreate,
    ComponentResponse,
    ComponentUpdate,
    FindingResponse,
    FindingStatusUpdate,
)
from app.services import vulnerability_service

router = APIRouter(prefix="/vulnerabilities", tags=["vulnerabilities"])


@router.get("/catalog", response_model=list[CatalogItem])
def list_catalog(_user: dict = Depends(get_current_user)):
    return vulnerability_service.list_catalog()


@router.get("/components", response_model=list[ComponentResponse])
def list_components(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return vulnerability_service.list_components(db)


@router.post("/components", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED)
def create_component(
    data: ComponentCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        comp = vulnerability_service.create_component(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    background.add_task(vulnerability_service.check_component, comp.id, wait=True)
    return vulnerability_service.component_dict(comp)


@router.put("/components/{component_id}", response_model=ComponentResponse)
def update_component(
    component_id: int,
    data: ComponentUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    comp = vulnerability_service.get_component(db, component_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组件不存在")
    try:
        comp, changed = vulnerability_service.update_component(db, comp, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if changed:
        background.add_task(vulnerability_service.check_component, comp.id, wait=True)
    return vulnerability_service.component_dict(comp, vulnerability_service.finding_counts(db, comp.id))


@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_component(
    component_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    comp = vulnerability_service.get_component(db, component_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组件不存在")
    vulnerability_service.delete_component(db, comp)


@router.get("/components/{component_id}/findings", response_model=list[FindingResponse])
def list_findings(
    component_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if not vulnerability_service.get_component(db, component_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组件不存在")
    return vulnerability_service.list_findings(db, component_id)


@router.post("/components/{component_id}/check", status_code=status.HTTP_202_ACCEPTED)
def check_component(
    component_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if not vulnerability_service.get_component(db, component_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组件不存在")
    if vulnerability_service.is_check_running():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有检查进行中，请稍后重试")
    background.add_task(vulnerability_service.check_component, component_id, wait=True)
    return {"message": "已开始检查"}


@router.post("/check-all", status_code=status.HTTP_202_ACCEPTED)
def check_all(
    background: BackgroundTasks,
    _user: dict = Depends(get_current_user),
):
    if vulnerability_service.is_check_running():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有检查进行中，请稍后重试")
    background.add_task(vulnerability_service.check_all_components, wait=True)
    return {"message": "已开始检查全部组件"}


@router.put("/findings/{finding_id}/status")
def update_finding_status(
    finding_id: int,
    data: FindingStatusUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    finding = vulnerability_service.get_finding(db, finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="漏洞记录不存在")
    vulnerability_service.set_finding_status(db, finding, data.status)
    return {"message": "已更新"}
