import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from sqlalchemy.orm import Session, joinedload

from app.models.notification import NotificationGroup, NotificationRecipient
from app.schemas.notification import (
    NotificationGroupCreate, NotificationGroupUpdate,
    NotificationRecipientCreate, NotificationRecipientUpdate,
)

logger = logging.getLogger(__name__)


@dataclass
class NotificationDispatchResult:
    email_delivered: list[str] = field(default_factory=list)
    email_failed: list[str] = field(default_factory=list)
    dingtalk_delivered: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def delivered(self) -> bool:
        return bool(self.email_delivered) or self.dingtalk_delivered


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


def _merge_email_result(
    result: NotificationDispatchResult, email_result,
) -> None:
    result.email_delivered = email_result.delivered
    result.email_failed = email_result.failed
    result.errors.extend(
        f"email/{error.provider or 'unknown'}/{error.kind}: {error.message}"
        for error in email_result.errors
    )


def send_group_notification(
    db: Session,
    notification_group_id: int | None,
    fallback_email: str,
    subject: str,
    body: str,
) -> NotificationDispatchResult:
    """Send a notification through email (primary→fallback) and DingTalk.

    Email is alert-scoped: it uses the dual-SMTP chain. DingTalk is an
    independent channel. Channel failures are collected and logged; callers
    use ``result.delivered`` to decide whether alert state may advance.
    """
    from app.services.email_service import send_alert_bulk, send_alert_email
    from app.services.dingtalk_service import send_alert as send_dingtalk_alert

    result = NotificationDispatchResult()

    if notification_group_id:
        channels = get_recipient_channels(db, notification_group_id)

        email_recipients = channels.get("email", [])
        if email_recipients:
            try:
                email_result = send_alert_bulk(email_recipients, subject, body)
            except Exception as exc:
                result.errors.append(f"email: {type(exc).__name__}")
                logger.warning(
                    "Email alert dispatch failed for group %s: %s",
                    notification_group_id,
                    type(exc).__name__,
                )
            else:
                _merge_email_result(result, email_result)

        dingtalk_recipients = channels.get("dingtalk", [])
        if dingtalk_recipients:
            try:
                result.dingtalk_delivered = bool(
                    send_dingtalk_alert(
                        db,
                        at_mobiles=dingtalk_recipients,
                        title=subject,
                        body=body,
                    )
                )
            except Exception as exc:
                result.errors.append(f"dingtalk: {type(exc).__name__}")
                logger.warning(
                    "DingTalk alert dispatch failed for group %s: %s",
                    notification_group_id,
                    type(exc).__name__,
                )
    elif fallback_email:
        try:
            email_result = send_alert_email(fallback_email, subject, body)
        except Exception as exc:
            result.errors.append(f"email: {type(exc).__name__}")
            logger.warning("Fallback email alert dispatch failed: %s", type(exc).__name__)
        else:
            _merge_email_result(result, email_result)

    if not result.delivered and not result.errors:
        result.errors.append("no notification channel configured")
    if result.errors:
        logger.warning(
            "Notification dispatch for group %s had errors: %s",
            notification_group_id,
            "; ".join(result.errors),
        )
    return result
