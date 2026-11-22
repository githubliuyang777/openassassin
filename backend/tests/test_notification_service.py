import pytest

from app.models.notification import NotificationGroup, NotificationRecipient
from app.services import dingtalk_service, email_service, notification_service
from app.services.email_service import EmailDeliveryResult, EmailError


def _group(db, email_addresses=(), dingtalk_addresses=()):
    group = NotificationGroup(name="ops")
    db.add(group)
    db.commit()
    for index, address in enumerate(email_addresses):
        db.add(NotificationRecipient(
            name=f"email-{index}", channel_type="email",
            address=address, group_id=group.id,
        ))
    for index, address in enumerate(dingtalk_addresses):
        db.add(NotificationRecipient(
            name=f"dingtalk-{index}", channel_type="dingtalk",
            address=address, group_id=group.id,
        ))
    db.commit()
    return group


def _delivered(*addresses):
    return EmailDeliveryResult(
        provider="primary", delivered=list(addresses), failover=False,
    )


class TestNotificationDispatch:
    def test_email_and_dingtalk(self, db_session, monkeypatch):
        group = _group(db_session, ["a@example.com"], ["13800138000"])
        email_calls = []
        dingtalk_calls = []

        def fake_bulk(recipients, subject, body):
            email_calls.append((recipients, subject, body))
            return _delivered(*recipients)

        def fake_dingtalk(db, at_mobiles, title, body):
            dingtalk_calls.append((at_mobiles, title, body))
            return True

        monkeypatch.setattr(email_service, "send_alert_bulk", fake_bulk)
        monkeypatch.setattr(dingtalk_service, "send_alert", fake_dingtalk)

        result = notification_service.send_group_notification(
            db_session, group.id, "fallback@example.com", "title", "body",
        )

        assert result.delivered is True
        assert result.email_delivered == ["a@example.com"]
        assert result.dingtalk_delivered is True
        assert email_calls == [(["a@example.com"], "title", "body")]
        assert dingtalk_calls == [(["13800138000"], "title", "body")]

    def test_dingtalk_only_group(self, db_session, monkeypatch):
        group = _group(db_session, dingtalk_addresses=["13800138000"])

        def unexpected_email(*args, **kwargs):
            raise AssertionError("email must not be sent")

        monkeypatch.setattr(email_service, "send_alert_bulk", unexpected_email)
        monkeypatch.setattr(dingtalk_service, "send_alert", lambda *a, **k: True)

        result = notification_service.send_group_notification(
            db_session, group.id, "", "title", "body",
        )

        assert result.delivered is True
        assert result.email_delivered == []
        assert result.dingtalk_delivered is True

    def test_group_without_recipients_does_not_use_fallback(self, db_session, monkeypatch):
        group = _group(db_session)

        def unexpected_email(*args, **kwargs):
            raise AssertionError("fallback email must not be used for a group")

        monkeypatch.setattr(email_service, "send_alert_email", unexpected_email)

        result = notification_service.send_group_notification(
            db_session, group.id, "fallback@example.com", "title", "body",
        )

        assert result.delivered is False
        assert result.errors == ["no notification channel configured"]

    def test_no_group_uses_fallback_email(self, db_session, monkeypatch):
        calls = []

        def fake_email(address, subject, body):
            calls.append((address, subject, body))
            return _delivered(address)

        monkeypatch.setattr(email_service, "send_alert_email", fake_email)

        result = notification_service.send_group_notification(
            db_session, None, "fallback@example.com", "title", "body",
        )

        assert result.delivered is True
        assert result.email_delivered == ["fallback@example.com"]
        assert calls == [("fallback@example.com", "title", "body")]

    def test_partial_email_failure_with_dingtalk_success(self, db_session, monkeypatch):
        group = _group(db_session, ["a@example.com", "b@example.com"], ["13800138000"])

        monkeypatch.setattr(email_service, "send_alert_bulk", lambda *a, **k: EmailDeliveryResult(
            provider="fallback",
            delivered=["a@example.com"],
            failed=["b@example.com"],
            errors=[EmailError("primary", "provider", "primary refused")],
            failover=True,
        ))
        monkeypatch.setattr(dingtalk_service, "send_alert", lambda *a, **k: True)

        result = notification_service.send_group_notification(
            db_session, group.id, "", "title", "body",
        )

        assert result.delivered is True
        assert result.email_delivered == ["a@example.com"]
        assert result.email_failed == ["b@example.com"]
        assert result.dingtalk_delivered is True
        assert any("email/primary/provider" in error for error in result.errors)

    def test_email_exception_does_not_block_dingtalk(self, db_session, monkeypatch):
        group = _group(db_session, ["a@example.com"], ["13800138000"])

        def broken_email(*args, **kwargs):
            raise RuntimeError("unexpected smtp failure")

        monkeypatch.setattr(email_service, "send_alert_bulk", broken_email)
        monkeypatch.setattr(dingtalk_service, "send_alert", lambda *a, **k: True)

        result = notification_service.send_group_notification(
            db_session, group.id, "", "title", "body",
        )

        assert result.delivered is True
        assert result.dingtalk_delivered is True
        assert result.errors == ["email: RuntimeError"]

    def test_dingtalk_error_does_not_leak_webhook(self, db_session, monkeypatch):
        group = _group(db_session, dingtalk_addresses=["13800138000"])
        webhook = "https://oapi.dingtalk.com/robot/send?access_token=SECRET_TOKEN"

        def fake_dingtalk(*args, **kwargs):
            raise RuntimeError(f"cannot reach {webhook}")

        monkeypatch.setattr(dingtalk_service, "send_alert", fake_dingtalk)

        result = notification_service.send_group_notification(
            db_session, group.id, "", "title", "body",
        )

        assert result.delivered is False
        assert result.errors == ["dingtalk: RuntimeError"]
        assert "SECRET_TOKEN" not in "; ".join(result.errors)

    def test_disabled_dingtalk_reports_no_channel(self, db_session, monkeypatch):
        group = _group(db_session, dingtalk_addresses=["13800138000"])
        monkeypatch.setattr(dingtalk_service, "send_alert", lambda *a, **k: False)

        result = notification_service.send_group_notification(
            db_session, group.id, "", "title", "body",
        )

        assert result.delivered is False
        assert result.errors == ["no notification channel configured"]


@pytest.mark.parametrize("delivered", [True, False])
def test_delivery_property(delivered):
    result = notification_service.NotificationDispatchResult(
        email_delivered=["a@example.com"] if delivered else [],
        errors=[] if delivered else ["smtp down"],
    )
    assert result.delivered is delivered
