from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.notification import (
    NotificationRecipientCreate, NotificationRecipientUpdate, NotificationRecipientResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/notification-recipients", tags=["notification-recipients"])


@router.get("", response_model=list[NotificationRecipientResponse])
def list_recipients(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notification_service.list_recipients(db)


@router.post("", response_model=NotificationRecipientResponse, status_code=status.HTTP_201_CREATED)
def create_recipient(
    data: NotificationRecipientCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return notification_service.create_recipient(db, data)


@router.put("/{recipient_id}", response_model=NotificationRecipientResponse)
def update_recipient(
    recipient_id: int,
    data: NotificationRecipientUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    r = notification_service.get_recipient(db, recipient_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知对象不存在")
    return notification_service.update_recipient(db, r, data)


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient(
    recipient_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    r = notification_service.get_recipient(db, recipient_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知对象不存在")
    notification_service.delete_recipient(db, r)
