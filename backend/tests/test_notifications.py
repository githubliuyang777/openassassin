from app.config import settings
from app.services import email_service
from app.services.email_service import EmailDeliveryResult, EmailError


class TestSmtpStatus:
    def test_requires_auth(self, client):
        assert client.get("/api/v1/notifications/smtp-status").status_code == 403

    def test_reports_primary_and_fallback_without_secrets(
        self, client, auth_headers, monkeypatch,
    ):
        monkeypatch.setattr(settings, "smtp_host", "smtp.primary.test")
        monkeypatch.setattr(settings, "smtp_port", 587)
        monkeypatch.setattr(settings, "smtp_username", "primary-user")
        monkeypatch.setattr(settings, "smtp_password", "primary-secret")
        monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
        monkeypatch.setattr(settings, "smtp_fallback_host", "smtp.fallback.test")
        monkeypatch.setattr(settings, "smtp_fallback_port", 465)
        monkeypatch.setattr(settings, "smtp_fallback_username", "fallback-user")
        monkeypatch.setattr(settings, "smtp_fallback_password", "fallback-secret")
        monkeypatch.setattr(settings, "smtp_fallback_from", "backup@example.com")
        email_service.reset_email_state()

        resp = client.get("/api/v1/notifications/smtp-status", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_failover_enabled"] is True
        assert data["transactional_configured"] is True
        assert data["primary"]["host"] == "smtp.primary.test"
        assert data["primary"]["from"] == "noreply@example.com"
        assert data["fallback"]["host"] == "smtp.fallback.test"
        assert data["fallback"]["from"] == "backup@example.com"
        assert data["fallback"]["health"] == "closed"
        assert data["host"] == "smtp.primary.test"
        rendered = resp.text
        assert "primary-secret" not in rendered
        assert "fallback-secret" not in rendered
        assert "primary-user" not in rendered
        assert "fallback-user" not in rendered

    def test_unconfigured_fallback(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "smtp_host", "smtp.primary.test")
        monkeypatch.setattr(settings, "smtp_fallback_host", "")
        email_service.reset_email_state()

        data = client.get(
            "/api/v1/notifications/smtp-status", headers=auth_headers,
        ).json()

        assert data["configured"] is True
        assert data["alert_failover_enabled"] is False
        assert data["fallback"]["configured"] is False
        assert data["fallback"]["host"] is None

    def test_legacy_configured_means_primary(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "smtp_host", "")
        monkeypatch.setattr(settings, "smtp_fallback_host", "smtp.fallback.test")
        email_service.reset_email_state()

        data = client.get(
            "/api/v1/notifications/smtp-status", headers=auth_headers,
        ).json()

        assert data["configured"] is False
        assert data["alert_configured"] is True
        assert data["transactional_configured"] is False
        assert data["alert_failover_enabled"] is True
        assert data["host"] is None
        assert data["fallback"]["configured"] is True


class TestTestEmail:
    def test_requires_auth(self, client):
        assert client.post(
            "/api/v1/notifications/test-email", json={"email": "a@example.com"},
        ).status_code == 403

    def test_rejects_unknown_provider(self, client, auth_headers):
        resp = client.post(
            "/api/v1/notifications/test-email",
            json={"email": "a@example.com", "provider": "other"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_rejects_invalid_email(self, client, auth_headers):
        for email in ["", "not-an-email", "a@b", "a@b.com\nBcc: x@example.com"]:
            resp = client.post(
                "/api/v1/notifications/test-email",
                json={"email": email},
                headers=auth_headers,
            )
            assert resp.status_code == 422, email

    def test_not_configured_returns_400(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "smtp_host", "")
        monkeypatch.setattr(settings, "smtp_fallback_host", "")

        resp = client.post(
            "/api/v1/notifications/test-email",
            json={"email": "a@example.com"},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "未配置" in resp.json()["detail"]

    def test_auto_uses_alert_chain(self, client, auth_headers, monkeypatch):
        calls = []

        def fake_send(to, subject, body, provider="auto"):
            calls.append(provider)
            return EmailDeliveryResult(
                provider="fallback", delivered=[to], failover=True,
            )

        monkeypatch.setattr(email_service, "send_alert_email", fake_send)

        resp = client.post(
            "/api/v1/notifications/test-email",
            json={"email": "a@example.com"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert calls == ["auto"]
        data = resp.json()
        assert data["provider"] == "fallback"
        assert data["failover"] is True
        assert "备用" in data["message"]

    def test_explicit_provider_is_forwarded(self, client, auth_headers, monkeypatch):
        calls = []

        def fake_send(to, subject, body, provider="auto"):
            calls.append(provider)
            return EmailDeliveryResult(provider="fallback", delivered=[to])

        monkeypatch.setattr(email_service, "send_alert_email", fake_send)

        resp = client.post(
            "/api/v1/notifications/test-email",
            json={"email": "a@example.com", "provider": "fallback"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert calls == ["fallback"]
        assert resp.json()["provider"] == "fallback"
        assert resp.json()["failover"] is False

    def test_delivery_failure_returns_502(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(
            email_service, "send_alert_email",
            lambda *args, **kwargs: EmailDeliveryResult(
                provider=None,
                failed=["a@example.com"],
                errors=[EmailError("primary", "provider", "connection refused")],
            ),
        )

        resp = client.post(
            "/api/v1/notifications/test-email",
            json={"email": "a@example.com"},
            headers=auth_headers,
        )

        assert resp.status_code == 502
        assert "connection refused" in resp.json()["detail"]
