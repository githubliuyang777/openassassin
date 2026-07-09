from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.notification import (
    NotificationGroupCreate, NotificationGroupUpdate, NotificationGroupResponse,
    NotificationRecipientCreate, NotificationRecipientUpdate, NotificationRecipientResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/notification-groups", tags=["notification-groups"])


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationGroupResponse])
def list_groups(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notification_service.list_groups(db)


@router.post("", response_model=NotificationGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    data: NotificationGroupCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notification_service.create_group(db, data)


@router.put("/{group_id}", response_model=NotificationGroupResponse)
def update_group(
    group_id: int,
    data: NotificationGroupUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    g = notification_service.get_group(db, group_id)
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知组不存在")
    return notification_service.update_group(db, g, data)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    g = notification_service.get_group(db, group_id)
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知组不存在")
    notification_service.delete_group(db, g)
