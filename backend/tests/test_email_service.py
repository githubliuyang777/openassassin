import smtplib

import pytest

from app.config import settings
from app.services import email_service
from app.services.email_service import (
    CircuitBreaker,
    EmailNotConfiguredError,
    PROVIDER_FALLBACK,
    PROVIDER_PRIMARY,
    RECIPIENT_ERROR_CODES,
)


class FakeSMTP:
    kind = "plain"
    plans: dict = {}
    events: list = []

    def __init__(self, host, port, timeout=None, context=None, **kwargs):
        self.host = host
        self.plan = self.plans.get(host, {})
        self.events.append(("connect", self.kind, host, port))
        on_connect = self.plan.get("on_connect")
        if on_connect:
            on_connect()
        error = self.plan.get("connect_error")
        if error:
            raise error

    def starttls(self, context=None):
        self.events.append(("starttls", self.host))
        if "starttls_error" in self.plan:
            raise self.plan["starttls_error"]

    def login(self, username, password):
        self.events.append(("login", self.host, username))
        if "login_error" in self.plan:
            raise self.plan["login_error"]

    def sendmail(self, sender, recipients, message):
        self.events.append(("send", self.host, tuple(recipients)))
        behavior = self.plan.get("send")
        outcome = behavior(recipients) if behavior else None
        if isinstance(outcome, Exception):
            raise outcome
        return outcome or {}

    def quit(self):
        self.events.append(("quit", self.host))

    def close(self):
        self.events.append(("close", self.host))


class FakeSMTPSSL(FakeSMTP):
    kind = "ssl"


@pytest.fixture(autouse=True)
def _reset_email_state():
    email_service.reset_email_state()
    yield
    email_service.reset_email_state()


@pytest.fixture
def smtp_env(monkeypatch):
    events: list = []
    plans: dict = {}

    class SMTP(FakeSMTP):
        pass

    class SMTP_SSL(FakeSMTPSSL):
        pass

    SMTP.events = events
    SMTP.plans = plans
    SMTP_SSL.events = events
    SMTP_SSL.plans = plans
    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SMTP_SSL)
    return events, plans


def _configure(
    monkeypatch,
    *,
    primary=True,
    fallback=False,
    primary_port=587,
    primary_use_tls=False,
    fallback_port=587,
    fallback_use_tls=False,
):
    monkeypatch.setattr(settings, "smtp_host", "smtp.primary.test" if primary else "")
    monkeypatch.setattr(settings, "smtp_port", primary_port)
    monkeypatch.setattr(settings, "smtp_username", "primary-user")
    monkeypatch.setattr(settings, "smtp_password", "primary-secret")
    monkeypatch.setattr(settings, "smtp_from", "primary@example.com")
    monkeypatch.setattr(settings, "smtp_use_tls", primary_use_tls)
    monkeypatch.setattr(settings, "smtp_fallback_host", "smtp.fallback.test" if fallback else "")
    monkeypatch.setattr(settings, "smtp_fallback_port", fallback_port)
    monkeypatch.setattr(settings, "smtp_fallback_username", "fallback-user")
    monkeypatch.setattr(settings, "smtp_fallback_password", "fallback-secret")
    monkeypatch.setattr(settings, "smtp_fallback_from", "fallback@example.com")
    monkeypatch.setattr(settings, "smtp_fallback_use_tls", fallback_use_tls)


def _connects(events):
    return [event for event in events if event[0] == "connect"]


class TestSingleAlertDelivery:
    def test_primary_success_does_not_connect_fallback(self, monkeypatch, smtp_env):
        events, _ = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.provider == PROVIDER_PRIMARY
        assert result.delivered == ["a@example.com"]
        assert result.failed == []
        assert result.failover is False
        assert _connects(events) == [("connect", "plain", "smtp.primary.test", 587)]

    def test_primary_provider_error_fails_over(self, monkeypatch, smtp_env):
        events, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {"connect_error": OSError("connection refused")}

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.delivered == ["a@example.com"]
        assert result.provider == PROVIDER_FALLBACK
        assert result.failover is True
        assert [error.kind for error in result.errors] == ["provider"]
        assert [host for _, _, host, _ in _connects(events)] == [
            "smtp.primary.test",
            "smtp.fallback.test",
        ]
        breaker = email_service._breaker_for(PROVIDER_PRIMARY)
        assert breaker.snapshot().consecutive_failures == 1

    def test_both_providers_fail(self, monkeypatch, smtp_env):
        _, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {"connect_error": OSError("primary down")}
        plans["smtp.fallback.test"] = {"connect_error": OSError("fallback down")}

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.delivered == []
        assert result.provider is None
        assert result.failed == ["a@example.com"]
        assert [error.kind for error in result.errors] == ["provider", "provider"]

    def test_unconfigured_primary_uses_fallback(self, monkeypatch, smtp_env):
        events, _ = smtp_env
        _configure(monkeypatch, primary=False, fallback=True)

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.delivered == ["a@example.com"]
        assert result.provider == PROVIDER_FALLBACK
        assert result.failover is False
        assert [host for _, _, host, _ in _connects(events)] == ["smtp.fallback.test"]

    def test_no_provider_configured(self, monkeypatch, smtp_env):
        _configure(monkeypatch, primary=False, fallback=False)

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.delivered == []
        assert result.failed == ["a@example.com"]
        assert [error.kind for error in result.errors] == ["config"]

    @pytest.mark.parametrize("code", sorted(RECIPIENT_ERROR_CODES))
    def test_recipient_refusal_does_not_fail_over(self, monkeypatch, smtp_env, code):
        events, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {
            "send": lambda recipients: smtplib.SMTPRecipientsRefused(
                {"a@example.com": (code, b"rejected")}
            )
        }

        result = email_service.send_alert_email("a@example.com", "subject", "body")

        assert result.delivered == []
        assert result.failed == ["a@example.com"]
        assert [error.kind for error in result.errors] == ["recipient"]
        assert all(host == "smtp.primary.test" for _, _, host, _ in _connects(events))
        # The provider answered, so it is reachable and must not be opened.
        snapshot = email_service._breaker_for(PROVIDER_PRIMARY).snapshot()
        assert snapshot.state == "closed"
        assert snapshot.last_success_at is not None


class TestBulkAlertDelivery:
    def test_one_connection_per_provider(self, monkeypatch, smtp_env):
        events, _ = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)

        result = email_service.send_alert_bulk(
            ["a@example.com", "b@example.com", "a@example.com"], "s", "b"
        )

        assert result.delivered == ["a@example.com", "b@example.com"]
        assert result.provider == PROVIDER_PRIMARY
        assert len(_connects(events)) == 1
        sends = [event for event in events if event[0] == "send"]
        assert [recipients for _, _, recipients in sends] == [
            ("a@example.com",),
            ("b@example.com",),
        ]

    def test_provider_error_retries_only_remaining_recipients(self, monkeypatch, smtp_env):
        events, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        calls = {"count": 0}

        def primary_send(recipients):
            calls["count"] += 1
            if calls["count"] == 2:
                raise smtplib.SMTPServerDisconnected("connection lost")
            return {}

        plans["smtp.primary.test"] = {"send": primary_send}

        result = email_service.send_alert_bulk(
            ["a@example.com", "b@example.com", "c@example.com"], "s", "b"
        )

        # The in-flight recipient is ambiguous and must not be resent.
        assert result.delivered == ["a@example.com", "c@example.com"]
        assert result.failed == ["b@example.com"]
        assert result.provider == PROVIDER_FALLBACK
        assert result.failover is True
        fallback_sends = [
            event[2] for event in events
            if event[0] == "send" and event[1] == "smtp.fallback.test"
        ]
        assert fallback_sends == [("c@example.com",)]

    def test_recipient_refusal_keeps_same_connection(self, monkeypatch, smtp_env):
        events, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)

        def primary_send(recipients):
            if recipients == ["a@example.com"]:
                raise smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"no such user")})
            return {}

        plans["smtp.primary.test"] = {"send": primary_send}

        result = email_service.send_alert_bulk(["a@example.com", "b@example.com"], "s", "b")

        assert result.delivered == ["b@example.com"]
        assert result.failed == ["a@example.com"]
        assert [error.kind for error in result.errors] == ["recipient"]
        assert len(_connects(events)) == 1
        assert [event[2] for event in events if event[0] == "send"] == [
            ("a@example.com",),
            ("b@example.com",),
        ]

    def test_budget_stops_second_provider(self, monkeypatch, smtp_env):
        events, plans = smtp_env

        class FakeTime:
            def __init__(self):
                self.now = 100.0

            def monotonic(self):
                return self.now

        fake_time = FakeTime()
        monkeypatch.setattr(email_service, "time", fake_time)
        monkeypatch.setattr(settings, "smtp_alert_total_budget_seconds", 5)
        _configure(monkeypatch, primary=True, fallback=True)

        def slow_failure():
            fake_time.now += 10

        plans["smtp.primary.test"] = {
            "on_connect": slow_failure,
            "connect_error": OSError("primary timeout"),
        }

        result = email_service.send_alert_email("a@example.com", "s", "b")

        assert result.delivered == []
        assert result.failed == ["a@example.com"]
        assert "budget" in [error.kind for error in result.errors]
        assert [host for _, _, host, _ in _connects(events)] == ["smtp.primary.test"]


class TestCircuitBreaker:
    def test_state_transitions(self):
        clock = [0.0]
        breaker = CircuitBreaker("primary", 2, 10, clock=lambda: clock[0])

        assert breaker.allow() is True
        breaker.record_failure("first")
        assert breaker.allow() is True
        breaker.record_failure("second")
        assert breaker.allow() is False
        assert breaker.snapshot().state == "open"

        clock[0] = 10
        assert breaker.snapshot().state == "half_open"
        assert breaker.allow() is True
        assert breaker.allow() is False  # only one probe at a time
        breaker.release()
        assert breaker.allow() is True
        breaker.record_success()
        assert breaker.snapshot().state == "closed"
        assert breaker.allow() is True

    def test_failed_probe_reopens(self):
        clock = [0.0]
        breaker = CircuitBreaker("primary", 1, 10, clock=lambda: clock[0])
        breaker.record_failure("down")
        clock[0] = 10
        assert breaker.allow() is True
        breaker.record_failure("still down")
        assert breaker.allow() is False
        assert breaker.snapshot().state == "open"

    def test_open_circuit_skips_provider(self, monkeypatch, smtp_env):
        events, plans = smtp_env
        monkeypatch.setattr(settings, "smtp_alert_circuit_failures", 1)
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {"connect_error": OSError("down")}

        first = email_service.send_alert_email("a@example.com", "s", "b")
        second = email_service.send_alert_email("a@example.com", "s", "b")

        assert first.delivered == ["a@example.com"]
        assert first.failover is True
        assert second.delivered == ["a@example.com"]
        assert second.failover is True
        assert [error.kind for error in second.errors] == ["circuit"]
        # Primary is never dialed again while its circuit is open.
        assert [host for _, _, host, _ in _connects(events)].count("smtp.primary.test") == 1


class TestTransactionalEmail:
    def test_requires_primary(self, monkeypatch, smtp_env):
        _configure(monkeypatch, primary=False, fallback=True)
        with pytest.raises(EmailNotConfiguredError):
            email_service.send_email("a@example.com", "s", "b")

    def test_does_not_fail_over(self, monkeypatch, smtp_env):
        events, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {"connect_error": OSError("down")}

        with pytest.raises(OSError):
            email_service.send_reset_code("a@example.com", "123456")

        assert [host for _, _, host, _ in _connects(events)] == ["smtp.primary.test"]

    def test_no_circuit_breaker(self, monkeypatch, smtp_env):
        _, plans = smtp_env
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {"connect_error": OSError("down")}

        for _ in range(3):
            with pytest.raises(OSError):
                email_service.send_email("a@example.com", "s", "b")

        assert email_service._breaker_for(PROVIDER_PRIMARY).snapshot().state == "closed"


class TestConnectionAndStatus:
    def test_port_465_uses_ssl(self, monkeypatch, smtp_env):
        events, _ = smtp_env
        _configure(monkeypatch, primary=True, primary_port=465)

        email_service.send_alert_email("a@example.com", "s", "b")

        assert _connects(events) == [("connect", "ssl", "smtp.primary.test", 465)]
        assert "starttls" not in [event[0] for event in events]

    def test_starttls_only_when_enabled(self, monkeypatch, smtp_env):
        events, _ = smtp_env
        _configure(monkeypatch, primary=True, primary_port=587, primary_use_tls=True)
        email_service.send_alert_email("a@example.com", "s", "b")
        assert "starttls" in [event[0] for event in events]

        email_service.reset_email_state()
        events.clear()
        _configure(monkeypatch, primary=True, primary_port=587, primary_use_tls=False)
        email_service.send_alert_email("a@example.com", "s", "b")
        assert "starttls" not in [event[0] for event in events]

    def test_status_has_providers_without_secrets(self, monkeypatch, smtp_env):
        _, plans = smtp_env
        monkeypatch.setattr(settings, "smtp_alert_circuit_failures", 1)
        _configure(monkeypatch, primary=True, fallback=True)
        plans["smtp.primary.test"] = {
            "connect_error": OSError("auth rejected primary-secret")
        }

        email_service.send_alert_email("a@example.com", "s", "b")
        status = email_service.get_smtp_status()

        assert status["alert_failover_enabled"] is True
        assert status["transactional_configured"] is True
        assert status["primary"]["configured"] is True
        assert status["fallback"]["configured"] is True
        assert status["primary"]["from"] == "primary@example.com"
        assert status["active_circuit"] == PROVIDER_PRIMARY
        assert status["host"] == "smtp.primary.test"
        rendered = repr(status)
        assert "primary-secret" not in rendered
        assert "fallback-secret" not in rendered
        assert "primary-user" not in rendered
        assert status["primary"]["last_error"]
        assert "***" in status["primary"]["last_error"]
