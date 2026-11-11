from datetime import timedelta

from app.database import china_now
from app.config import settings
from app.models.credential import Credential
from app.models.domain import Domain
from app.models.domain_whois import DomainWhois
from app.models.host import Host
from app.models.subscription import Subscription, SubscriptionAlert


def _make_host(db, **overrides):
    data = {
        "name": "web-1",
        "hostname": "10.0.0.10",
        "username": "root",
        "alert_active": True,
        "alert_enabled": True,
        "is_online": True,
        "cpu_usage": 95.0,
        "mem_usage": 60.0,
        "disk_usage": 91.0,
    }
    data.update(overrides)
    host = Host(**data)
    db.add(host)
    db.commit()
    db.refresh(host)
    return host


class TestAlertsUnauthenticated:
    def test_unauthorized(self, client):
        assert client.get("/api/v1/alerts/summary").status_code == 403


class TestAlertsEmpty:
    def test_empty(self, client, auth_headers):
        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestAlertsCredential:
    def test_credential_expiring(self, client, auth_headers, db_session):
        now = china_now()
        cred = Credential(
            name="test-token", key="TEST_TOKEN",
            encrypted_value="encrypted",
            expires_at=now + timedelta(days=3),
            alert_enabled=True,
        )
        db_session.add(cred)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == f"cred-{cred.id}"
        assert data[0]["source"] == "credential"
        assert "test-token" in data[0]["message"]
        assert data[0]["severity"] == "warning"
        assert data[0]["link"] == "/credentials"

    def test_credential_expired_danger(self, client, auth_headers, db_session):
        now = china_now()
        cred = Credential(
            name="expired-token", key="EXP_TOKEN",
            encrypted_value="encrypted",
            expires_at=now - timedelta(days=1),
            alert_enabled=True,
        )
        db_session.add(cred)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "danger"
        assert "已过期" in data[0]["message"]

    def test_credential_alert_disabled_excluded(self, client, auth_headers, db_session):
        now = china_now()
        cred = Credential(
            name="disabled-token", key="DIS_TOKEN",
            encrypted_value="encrypted",
            expires_at=now + timedelta(days=1),
            alert_enabled=False,
        )
        db_session.add(cred)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.json() == []

    def test_credential_no_expiry_excluded(self, client, auth_headers, db_session):
        cred = Credential(
            name="noexpiry-token", key="NO_TOKEN",
            encrypted_value="encrypted",
            alert_enabled=True,
        )
        db_session.add(cred)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.json() == []

    def test_credential_far_expiry_excluded(self, client, auth_headers, db_session):
        now = china_now()
        cred = Credential(
            name="far-token", key="FAR_TOKEN",
            encrypted_value="encrypted",
            expires_at=now + timedelta(days=settings.alert_before_days + 10),
            alert_enabled=True,
        )
        db_session.add(cred)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.json() == []


class TestAlertsDomainCert:
    def test_domain_cert_expiring(self, client, auth_headers, db_session):
        now = china_now()
        domain = Domain(
            domain="example.com", port=443,
            ssl_not_after=now + timedelta(days=5),
            alert_enabled=True,
        )
        db_session.add(domain)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == f"cert-{domain.id}"
        assert data[0]["source"] == "domain_cert"
        assert "example.com" in data[0]["message"]
        assert data[0]["severity"] == "warning"

    def test_domain_cert_alert_disabled_excluded(self, client, auth_headers, db_session):
        now = china_now()
        domain = Domain(
            domain="disabled.example.com", port=443,
            ssl_not_after=now + timedelta(days=2),
            alert_enabled=False,
        )
        db_session.add(domain)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.json() == []


class TestAlertsDomainWhois:
    def test_domain_whois_expiring(self, client, auth_headers, db_session):
        now = china_now()
        whois = DomainWhois(
            domain="expiring.example.com",
            whois_expiry_date=now + timedelta(days=3),
            alert_enabled=True,
        )
        db_session.add(whois)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == f"whois-{whois.id}"
        assert data[0]["source"] == "domain_whois"
        assert "expiring.example.com" in data[0]["message"]


class TestAlertsSubscription:
    def test_unread_subscription_alert(self, client, auth_headers, db_session):
        sub = Subscription(name="test-repo", repo_url="https://github.com/test/repo")
        db_session.add(sub)
        db_session.commit()

        alert = SubscriptionAlert(
            subscription_id=sub.id,
            alert_type="release",
            title="v2.0.0 released",
            is_read=False,
        )
        db_session.add(alert)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == f"sub-{sub.id}"
        assert data[0]["source"] == "subscription"
        assert data[0]["severity"] == "info"
        assert "test-repo" in data[0]["message"]
        assert "1 条新动态" in data[0]["message"]

    def test_read_subscription_alert_excluded(self, client, auth_headers, db_session):
        sub = Subscription(name="read-repo", repo_url="https://github.com/test/read-repo")
        db_session.add(sub)
        db_session.commit()

        alert = SubscriptionAlert(
            subscription_id=sub.id,
            alert_type="advisory",
            title="CVE-2024-1234",
            is_read=True,
        )
        db_session.add(alert)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.json() == []


class TestAlertsHost:
    def test_active_host_alert(self, client, auth_headers, db_session):
        host = _make_host(db_session)

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = [item for item in resp.json() if item["source"] == "host"]
        assert len(data) == 1
        assert data[0]["id"] == f"host-{host.id}"
        assert data[0]["severity"] == "danger"
        assert data[0]["link"] == f"/hosts/{host.id}"
        assert "web-1" in data[0]["message"]
        assert "CPU 95%" in data[0]["message"]
        assert "磁盘 91%" in data[0]["message"]

    def test_offline_host_still_shown_with_note(self, client, auth_headers, db_session):
        _make_host(db_session, is_online=False)

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = [item for item in resp.json() if item["source"] == "host"]
        assert len(data) == 1
        assert "离线" in data[0]["message"]

    def test_inactive_or_disabled_host_excluded(self, client, auth_headers, db_session):
        _make_host(db_session, name="recovered", alert_active=False)
        _make_host(db_session, name="muted", alert_enabled=False)

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert [item for item in resp.json() if item["source"] == "host"] == []


class TestAlertsSorting:
    def test_danger_before_warning_before_info(self, client, auth_headers, db_session):
        now = china_now()

        cred = Credential(
            name="warn-cred", key="WK",
            encrypted_value="enc",
            expires_at=now + timedelta(days=2),
            alert_enabled=True,
        )
        db_session.add(cred)
        db_session.flush()

        domain = Domain(
            domain="danger.example.com", port=443,
            ssl_not_after=now - timedelta(days=1),
            alert_enabled=True,
        )
        db_session.add(domain)
        db_session.flush()

        sub = Subscription(name="info-repo", repo_url="https://github.com/test/repo")
        db_session.add(sub)
        db_session.flush()
        alert = SubscriptionAlert(
            subscription_id=sub.id,
            alert_type="release",
            title="v1.0",
            is_read=False,
        )
        db_session.add(alert)
        db_session.commit()

        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        data = resp.json()
        assert len(data) == 3
        assert data[0]["severity"] == "danger"
        assert data[1]["severity"] == "warning"
        assert data[2]["severity"] == "info"
