from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.notification import NotificationGroup, NotificationRecipient
from app.schemas.notification import (
    NotificationGroupCreate, NotificationGroupUpdate,
    NotificationRecipientCreate, NotificationRecipientUpdate,
)


# ── Groups ────────────────────────────────────────────────────────────────────

def list_groups(db: Session) -> List[NotificationGroup]:
    return db.query(NotificationGroup).options(
        joinedload(NotificationGroup.recipients)
    ).order_by(NotificationGroup.name).all()


def get_group(db: Session, group_id: int) -> Optional[NotificationGroup]:
    return db.query(NotificationGroup).options(
        joinedload(NotificationGroup.recipients)
    ).filter(NotificationGroup.id == group_id).first()


def create_group(db: Session, data: NotificationGroupCreate) -> NotificationGroup:
    g = NotificationGroup(name=data.name)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def update_group(db: Session, group: NotificationGroup, data: NotificationGroupUpdate) -> NotificationGroup:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group: NotificationGroup) -> None:
    db.delete(group)
    db.commit()


# ── Recipients ────────────────────────────────────────────────────────────────

def list_recipients(db: Session) -> List[NotificationRecipient]:
    return db.query(NotificationRecipient).order_by(NotificationRecipient.name).all()


def get_recipient(db: Session, recipient_id: int) -> Optional[NotificationRecipient]:
    return db.query(NotificationRecipient).filter(NotificationRecipient.id == recipient_id).first()


def create_recipient(db: Session, data: NotificationRecipientCreate) -> NotificationRecipient:
    r = NotificationRecipient(**data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def update_recipient(db: Session, recipient: NotificationRecipient, data: NotificationRecipientUpdate) -> NotificationRecipient:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(recipient, field, value)
    db.commit()
    db.refresh(recipient)
    return recipient


def delete_recipient(db: Session, recipient: NotificationRecipient) -> None:
    db.delete(recipient)
    db.commit()


# ── Email helpers ─────────────────────────────────────────────────────────────

def get_recipient_emails(db: Session, group_id: int) -> List[str]:
    """Get all recipient email addresses for a group."""
    recipients = (
        db.query(NotificationRecipient)
        .filter(NotificationRecipient.group_id == group_id)
        .all()
    )
    return [r.address for r in recipients if r.channel_type == "email"]
