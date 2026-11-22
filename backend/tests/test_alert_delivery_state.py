import logging
import time
from datetime import timedelta

import pytest

from app.api import auth as auth_api
from app.config import settings
from app.database import china_now
from app.models.credential import Credential
from app.models.domain import Domain
from app.models.host import Host
from app.models.site_monitor import SiteMonitor
from app.models.user import User
from app.schemas.agent import AgentReportRequest
from app.services import (
    agent_service,
    alert_service,
    cert_renew_service,
    notification_service,
    site_monitor_service,
)
from app.services.email_service import EmailDeliveryResult, EmailError
from app.services.notification_service import NotificationDispatchResult


def _delivered():
    return NotificationDispatchResult(
        email_delivered=["ops@example.com"], dingtalk_delivered=False,
    )


def _undelivered():
    return NotificationDispatchResult(
        email_failed=["ops@example.com"],
        errors=["email/primary/provider: connection refused"],
    )


@pytest.fixture(autouse=True)
def _clear_site_retry():
    site_monitor_service._down_alert_retry_at.clear()
    yield
    site_monitor_service._down_alert_retry_at.clear()


def _credential(db):
    cred = Credential(
        name="expiring", key="TOKEN", encrypted_value="encrypted",
        expires_at=china_now() + timedelta(days=2), alert_enabled=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


def _host(db, **overrides):
    data = {
        "name": "web-1",
        "hostname": "10.0.0.1",
        "username": "root",
        "alert_enabled": True,
        "alert_active": False,
        "consecutive_alerts": 2,
    }
    data.update(overrides)
    host = Host(**data)
    db.add(host)
    db.commit()
    db.refresh(host)
    return host


def _monitor(db):
    monitor = SiteMonitor(
        name="site", target="https://example.com", monitor_type="http",
        alert_enabled=True, retries=0,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


class TestCredentialAlertState:
    def test_undelivered_does_not_advance_last_alerted_at(self, db_session, monkeypatch):
        cred = _credential(db_session)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )

        assert alert_service.check_and_alert(db_session) == 0
        db_session.refresh(cred)
        assert cred.last_alerted_at is None

    def test_delivered_advances_last_alerted_at(self, db_session, monkeypatch):
        cred = _credential(db_session)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _delivered(),
        )

        assert alert_service.check_and_alert(db_session) == 1
        db_session.refresh(cred)
        assert cred.last_alerted_at is not None


class TestHostUsageAlertState:
    def test_undelivered_usage_alert_stays_inactive(self, db_session, monkeypatch):
        host = _host(db_session)
        report = AgentReportRequest(cpu_percent=99.0)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )

        agent_service._check_usage_alerts(db_session, host, report)

        db_session.refresh(host)
        assert host.alert_active is False
        assert host.last_alerted_at is None
        assert host.consecutive_alerts == 3

    def test_delivered_usage_alert_sets_active(self, db_session, monkeypatch):
        host = _host(db_session)
        report = AgentReportRequest(cpu_percent=99.0)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _delivered(),
        )

        agent_service._check_usage_alerts(db_session, host, report)

        db_session.refresh(host)
        assert host.alert_active is True
        assert host.last_alerted_at is not None

    def test_undelivered_recovery_keeps_alert_active(self, db_session, monkeypatch):
        host = _host(db_session, alert_active=True, consecutive_alerts=5)
        report = AgentReportRequest(cpu_percent=10.0, mem_percent=10.0, disk_percent=10.0)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )

        agent_service._check_usage_alerts(db_session, host, report)

        db_session.refresh(host)
        assert host.alert_active is True
        assert host.consecutive_alerts == 5

    def test_delivered_recovery_clears_alert(self, db_session, monkeypatch):
        host = _host(db_session, alert_active=True, consecutive_alerts=5)
        report = AgentReportRequest(cpu_percent=10.0, mem_percent=10.0, disk_percent=10.0)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _delivered(),
        )

        agent_service._check_usage_alerts(db_session, host, report)

        db_session.refresh(host)
        assert host.alert_active is False
        assert host.consecutive_alerts == 0


class TestSiteMonitorAlertState:
    def test_down_alert_failure_is_returned_and_scheduled(self, db_session, monkeypatch):
        monitor = _monitor(db_session)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )

        assert site_monitor_service._send_down_alert(db_session, monitor, "down") is False
        db_session.refresh(monitor)
        assert monitor.last_alerted_at is None
        assert monitor.id in site_monitor_service._down_alert_retry_at

    def test_down_alert_success_sets_cooldown(self, db_session, monkeypatch):
        monitor = _monitor(db_session)
        site_monitor_service._down_alert_retry_at[monitor.id] = time.monotonic() - 1
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _delivered(),
        )

        assert site_monitor_service._send_down_alert(db_session, monitor, "down") is True
        db_session.refresh(monitor)
        assert monitor.last_alerted_at is not None
        assert monitor.id not in site_monitor_service._down_alert_retry_at

    def test_up_alert_result(self, db_session, monkeypatch):
        monitor = _monitor(db_session)
        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )
        assert site_monitor_service._send_up_alert(db_session, monitor) is False

        monkeypatch.setattr(
            notification_service, "send_group_notification",
            lambda *args, **kwargs: _delivered(),
        )
        assert site_monitor_service._send_up_alert(db_session, monitor) is True

    def test_down_alert_retries_on_later_check(self, db_session, monkeypatch):
        monitor = _monitor(db_session)
        calls = []
        monkeypatch.setattr(
            site_monitor_service, "_probe_http",
            lambda monitor: (False, None, 0, "down"),
        )
        monkeypatch.setattr(
            site_monitor_service, "_send_down_alert",
            lambda db, monitor, error: calls.append(monitor.id) or False,
        )

        site_monitor_service.run_single_check(monitor)
        assert calls == [monitor.id]

        db_session.expire_all()
        current = db_session.get(SiteMonitor, monitor.id)
        assert current.is_up is False

        # Not due yet: no second alert.
        site_monitor_service.run_single_check(current)
        assert calls == [monitor.id]

        site_monitor_service._down_alert_retry_at[monitor.id] = time.monotonic() - 1
        site_monitor_service.run_single_check(current)
        assert calls == [monitor.id, monitor.id]


class TestLoginAlertState:
    def test_login_alert_flag_requires_delivery(self, client, admin_user, db_session, monkeypatch):
        monkeypatch.setattr(settings, "admin_email", "admin@example.com")
        undelivered = EmailDeliveryResult(
            provider=None,
            failed=["admin@example.com"],
            errors=[EmailError("primary", "provider", "smtp down")],
        )
        sent = []

        def fake_email(*args, **kwargs):
            sent.append(args)
            return undelivered

        monkeypatch.setattr(auth_api, "send_alert_email", fake_email)

        for _ in range(3):
            client.post("/api/v1/auth/login", json={
                "username": "admin", "password": "wrong",
            })

        db_session.expire_all()
        user = db_session.query(User).filter(User.username == "admin").one()
        assert user.login_alert_sent == 0
        assert len(sent) == 1

        delivered = EmailDeliveryResult(
            provider="primary", delivered=["admin@example.com"],
        )
        monkeypatch.setattr(auth_api, "send_alert_email", lambda *a, **k: delivered)
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

        db_session.expire_all()
        user = db_session.query(User).filter(User.username == "admin").one()
        assert user.login_alert_sent == 1

        # Suppressed after a delivered alert.
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert len(sent) == 1


class TestCertNotification:
    def test_undelivered_notification_is_logged_but_not_raised(
        self, db_session, monkeypatch, caplog,
    ):
        domain = Domain(domain="cert-state.example.com", port=443)
        db_session.add(domain)
        db_session.commit()
        db_session.refresh(domain)
        monkeypatch.setattr(
            cert_renew_service, "send_group_notification",
            lambda *args, **kwargs: _undelivered(),
        )

        with caplog.at_level(logging.WARNING):
            cert_renew_service._notify(domain.id, True, "renewed")

        assert "was not delivered" in caplog.text

    def test_none_result_is_tolerated(self, db_session, monkeypatch):
        domain = Domain(domain="cert-none.example.com", port=443)
        db_session.add(domain)
        db_session.commit()
        db_session.refresh(domain)
        monkeypatch.setattr(
            cert_renew_service, "send_group_notification",
            lambda *args, **kwargs: None,
        )

        cert_renew_service._notify(domain.id, False, "failed")
