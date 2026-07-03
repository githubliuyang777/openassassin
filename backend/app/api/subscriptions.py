from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.subscription import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionAlertResponse, RepoLookupRequest, RepoLookupResponse,
)
from app.services import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return subscription_service.list_subscriptions(db)


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return subscription_service.create_subscription(db, data)


@router.put("/{sub_id}", response_model=SubscriptionResponse)
def update_subscription(
    sub_id: int,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    sub = subscription_service.get_subscription(db, sub_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    return subscription_service.update_subscription(db, sub, data)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    sub = subscription_service.get_subscription(db, sub_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    subscription_service.delete_subscription(db, sub)


@router.get("/{sub_id}/alerts", response_model=list[SubscriptionAlertResponse])
def list_alerts(
    sub_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return subscription_service.list_alerts(db, sub_id)


@router.put("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    subscription_service.mark_alert_read(db, alert_id)
    return {"message": "已标记为已读"}


@router.post("/lookup", response_model=RepoLookupResponse)
def lookup_repo(
    body: RepoLookupRequest,
    _user: dict = Depends(get_current_user),
):
    return subscription_service.lookup_repo(body.repo_url)
