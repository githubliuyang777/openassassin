from typing import List, Optional, Dict

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


def get_recipient_channels(db: Session, group_id: int) -> Dict[str, List[str]]:
    """Get recipients grouped by channel_type.

    Returns dict like: {'email': ['a@b.com'], 'dingtalk': ['13800138000']}
    """
    recipients = (
        db.query(NotificationRecipient)
        .filter(NotificationRecipient.group_id == group_id)
        .all()
    )
    result: Dict[str, List[str]] = {}
    for r in recipients:
        result.setdefault(r.channel_type, []).append(r.address)
    return result


def send_group_notification(
    db: Session,
    notification_group_id: int | None,
    fallback_email: str,
    subject: str,
    body: str,
) -> None:
    """Send notification to all recipients in a group via their channels.

    Falls back to fallback_email (email only) if no group is configured.
    Swallows errors from individual channels so one failure doesn't block others.
    """
    from app.config import settings
    from app.services.email_service import send_email, EmailNotConfiguredError
    from app.services.dingtalk_service import send_alert as send_dingtalk_alert

    if notification_group_id:
        channels = get_recipient_channels(db, notification_group_id)

        # Email channel
        for addr in channels.get("email", []):
            try:
                if settings.smtp_host:
                    send_email(addr, subject, body)
            except EmailNotConfiguredError:
                pass
            except Exception:
                pass

        # DingTalk channel
        if channels.get("dingtalk"):
            dingtalk_body = body
            try:
                import logging
                send_dingtalk_alert(
                    db,
                    at_mobiles=channels.get("dingtalk"),
                    title=subject,
                    body=dingtalk_body,
                )
            except Exception:
                logging.getLogger(__name__).warning(
                    "DingTalk alert dispatch failed for group %s", notification_group_id
                )
    elif fallback_email:
        try:
            if settings.smtp_host:
                send_email(fallback_email, subject, body)
        except EmailNotConfiguredError:
            pass
        except Exception:
            pass
