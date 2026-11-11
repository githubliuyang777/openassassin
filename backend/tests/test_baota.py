from datetime import datetime, timedelta, timezone

import pytest

from app.database import china_now
from app.models.baota_panel import BaotaPanel
from app.models.domain import Domain
from app.models.user import User
from app.services import baota_service, cert_provider_service, cert_renew_service, credential_service
from app.services.auth_service import create_token, hash_password


def _panel(db, **overrides):
    data = {
        "name": "panel-1",
        "panel_url": "https://panel.example.com:8888",
        "encrypted_api_key": credential_service.encrypt("test-key"),
        "verify_tls": True,
        "enabled": True,
    }
    data.update(overrides)
    panel = BaotaPanel(**data)
    db.add(panel)
    db.commit()
    db.refresh(panel)
    return panel


def _domain(db, panel_id=None, **overrides):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "domain": "example.com",
        "port": 443,
        "cert_provider": "baota",
        "cert_provider_config": (
            {"panel_id": panel_id, "site_name": "example.com"} if panel_id else {}
        ),
        "cert_auto_renew": True,
        "ssl_not_before": now - timedelta(days=60),
        "ssl_not_after": now + timedelta(days=3),
    }
    data.update(overrides)
    dom = Domain(**data)
    db.add(dom)
    db.commit()
    db.refresh(dom)
    return dom


def _cert_info(days=90):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "ssl_subject": "CN=example.com",
        "ssl_issuer": "CN=Test CA",
        "ssl_not_before": now,
        "ssl_not_after": now + timedelta(days=days),
        "ssl_expired": False,
        "last_checked_at": now,
    }


class TestSignature:
    def test_request_token_vector(self):
        assert baota_service._sign("test-key", 1700000000) == "51e1827b3668b612a4fa76e79caa10d0"


class TestSiteParsing:
    def test_normalize_new_response(self):
        sites = baota_service._normalize_sites({
            "sites": [{"id": 1, "name": "example.com", "path": "/www/example"}],
        })
        assert sites == [{"id": 1, "name": "example.com", "path": "/www/example"}]

    def test_normalize_classic_response(self):
        sites = baota_service._normalize_sites({
            "data": [{"id": "2", "name": "api.example.com", "path": "/www/api"}],
        })
        assert sites == [{"id": 2, "name": "api.example.com", "path": "/www/api"}]

    def test_missing_path_is_ignored(self):
        assert baota_service._normalize_sites({
            "data": [{"id": 1, "name": "example.com"}],
        }) == []

    def test_resolve_site_exact_and_www(self):
        sites = [{"id": 1, "name": "example.com", "path": "/www/example"}]
        assert baota_service._resolve_site(sites, "", "www.example.com")["id"] == 1
        assert baota_service._resolve_site(sites, "Example.com", "other.com")["id"] == 1

    def test_resolve_site_missing_or_ambiguous(self):
        with pytest.raises(baota_service.BaotaError):
            baota_service._resolve_site([], "", "example.com")
        sites = [
            {"id": 1, "name": "example.com", "path": "/www/example"},
            {"id": 2, "name": "www.example.com", "path": "/www/www"},
        ]
        with pytest.raises(baota_service.BaotaError):
            baota_service._resolve_site(sites, "", "example.com")


class TestProviderRegistry:
    def test_providers(self):
        providers = cert_provider_service.list_providers()
        assert {item["key"] for item in providers} == {"baota"}
        assert cert_provider_service.get_provider("baota") is not None
        assert cert_provider_service.get_provider("none") is None
        assert cert_provider_service.get_provider("unknown") is None

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError):
            cert_provider_service.validate_domain_config(None, "unknown", {})


class TestPanelAPI:
    def test_crud_and_key_masking(self, client, auth_headers, db_session):
        resp = client.post(
            "/api/v1/baota/panels",
            json={
                "name": "panel-1",
                "panel_url": "https://panel.example.com:8888/",
                "api_key": "secret-key",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["api_key_configured"] is True
        assert body["panel_url"] == "https://panel.example.com:8888"
        assert "api_key" not in body and "encrypted_api_key" not in body

        panel = db_session.query(BaotaPanel).first()
        assert panel.encrypted_api_key != "secret-key"
        assert credential_service.decrypt(panel.encrypted_api_key) == "secret-key"

        resp = client.get("/api/v1/baota/panels", headers=auth_headers)
        assert resp.status_code == 200
        assert "secret-key" not in resp.text

        resp = client.put(
            f"/api/v1/baota/panels/{panel.id}",
            json={"name": "renamed", "api_key": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"
        db_session.expire_all()
        assert credential_service.decrypt(db_session.get(BaotaPanel, panel.id).encrypted_api_key) == "secret-key"

        resp = client.put(
            f"/api/v1/baota/panels/{panel.id}",
            json={"api_key": "new-key"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        db_session.expire_all()
        assert credential_service.decrypt(db_session.get(BaotaPanel, panel.id).encrypted_api_key) == "new-key"

        assert client.delete(f"/api/v1/baota/panels/{panel.id}", headers=auth_headers).status_code == 204
        assert client.delete(f"/api/v1/baota/panels/{panel.id}", headers=auth_headers).status_code == 404

    def test_invalid_url(self, client, auth_headers):
        resp = client.post(
            "/api/v1/baota/panels",
            json={"name": "bad", "panel_url": "ftp://panel.example.com", "api_key": "key"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_non_admin_forbidden(self, client, db_session):
        user = User(username="viewer", password_hash=hash_password("x"), role="user")
        db_session.add(user)
        db_session.commit()
        token = create_token(user.id, user.username, user.role)
        resp = client.post(
            "/api/v1/baota/panels",
            json={"name": "panel", "panel_url": "https://p.example.com", "api_key": "key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_in_use(self, client, auth_headers, db_session):
        panel = _panel(db_session)
        _domain(db_session, panel_id=panel.id)
        resp = client.delete(f"/api/v1/baota/panels/{panel.id}", headers=auth_headers)
        assert resp.status_code == 409

    def test_test_endpoint_returns_sites_without_paths(self, client, auth_headers, db_session, monkeypatch):
        panel = _panel(db_session)
        monkeypatch.setattr(
            baota_service, "list_sites",
            lambda ctx: [{"id": 1, "name": "example.com", "path": "/www/example"}],
        )
        resp = client.post(f"/api/v1/baota/panels/{panel.id}/test", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["sites"] == [{"id": 1, "name": "example.com"}]


class TestDomainUpdateAPI:
    def test_update_provider_config(self, client, auth_headers, db_session):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=None, cert_provider="none", cert_auto_renew=False)

        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={
                "cert_provider": "baota",
                "cert_provider_config": {"panel_id": panel.id, "site_name": "example.com"},
                "cert_auto_renew": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cert_provider"] == "baota"
        assert body["cert_provider_config"]["panel_id"] == panel.id
        assert body["cert_auto_renew"] is True
        assert "notification_group_id" in body

        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"cert_provider": "none"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cert_provider"] == "none"
        assert resp.json()["cert_auto_renew"] is False

    def test_auto_renew_without_provider_rejected(self, client, auth_headers, db_session):
        dom = _domain(db_session, cert_provider="none", cert_auto_renew=False)
        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"cert_auto_renew": True},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_unknown_provider_rejected(self, client, auth_headers, db_session):
        dom = _domain(db_session, cert_provider="none", cert_auto_renew=False)
        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"cert_provider": "unknown"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_update_missing_domain(self, client, auth_headers):
        resp = client.put("/api/v1/domains/99999", json={"port": 8443}, headers=auth_headers)
        assert resp.status_code == 404


class TestRenewalService:
    def test_success_updates_status_and_notifies(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)
        old_after = dom.ssl_not_after
        notified = []

        monkeypatch.setattr(
            baota_service, "start_renewal",
            lambda domain_name, config: {"site_name": "example.com", "index": "1", "direct": False},
        )
        monkeypatch.setattr(cert_renew_service, "_poll_for_new_cert", lambda *args, **kwargs: _cert_info())
        monkeypatch.setattr(
            cert_renew_service, "send_group_notification",
            lambda *args, **kwargs: notified.append(args),
        )

        assert cert_renew_service._renew_domain(dom.id) == 1
        db_session.expire_all()
        dom = db_session.get(Domain, dom.id)
        assert dom.last_renew_status == "success"
        assert dom.last_renew_attempt_at is not None
        assert dom.ssl_not_after > old_after
        assert notified

    def test_deploy_when_initial_poll_misses(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)
        deployed = []
        polls = [None, _cert_info()]

        monkeypatch.setattr(
            baota_service, "start_renewal",
            lambda domain_name, config: {"site_name": "example.com", "index": "1", "direct": False},
        )
        monkeypatch.setattr(cert_renew_service, "_poll_for_new_cert", lambda *args, **kwargs: polls.pop(0))
        monkeypatch.setattr(baota_service, "deploy_order", lambda *args, **kwargs: deployed.append(True))
        monkeypatch.setattr(cert_renew_service, "send_group_notification", lambda *args, **kwargs: None)

        assert cert_renew_service._renew_domain(dom.id) == 1
        assert deployed == [True]

    def test_provider_error_sets_failed_and_cooldown(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)

        def _boom(*args, **kwargs):
            raise baota_service.BaotaError("API Key 无效")

        monkeypatch.setattr(baota_service, "start_renewal", _boom)
        monkeypatch.setattr(cert_renew_service, "send_group_notification", lambda *args, **kwargs: None)

        assert cert_renew_service._renew_domain(dom.id) == 0
        db_session.expire_all()
        dom = db_session.get(Domain, dom.id)
        assert dom.last_renew_status == "failed"
        assert "API Key 无效" in dom.last_renew_error
        assert dom.last_renew_attempt_at is not None

    def test_cooldown_skips_auto_renew(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id, last_renew_attempt_at=china_now())

        def _unexpected(*args, **kwargs):
            raise AssertionError("should not be called")

        monkeypatch.setattr(baota_service, "start_renewal", _unexpected)
        assert cert_renew_service._renew_domain(dom.id, force=False) == 0

    def test_manual_bypasses_cooldown(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id, last_renew_attempt_at=china_now())
        monkeypatch.setattr(
            baota_service, "start_renewal",
            lambda domain_name, config: {"site_name": "example.com", "index": "1", "direct": False},
        )
        monkeypatch.setattr(cert_renew_service, "_poll_for_new_cert", lambda *args, **kwargs: _cert_info())
        monkeypatch.setattr(cert_renew_service, "send_group_notification", lambda *args, **kwargs: None)

        assert cert_renew_service._renew_domain(dom.id, force=True) == 1

    def test_busy_lock(self, db_session):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)
        cert_renew_service._renew_lock.acquire()
        try:
            assert cert_renew_service.renew_domain(dom.id) == -1
        finally:
            cert_renew_service._renew_lock.release()


class TestRenewAPI:
    def test_renew_accepted(self, client, auth_headers, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)
        monkeypatch.setattr(cert_renew_service, "renew_domain", lambda domain_id: 1)

        resp = client.post(f"/api/v1/domains/{dom.id}/renew-cert", headers=auth_headers)
        assert resp.status_code == 202

    def test_renew_without_provider(self, client, auth_headers, db_session):
        dom = _domain(db_session, cert_provider="none", cert_auto_renew=False)
        resp = client.post(f"/api/v1/domains/{dom.id}/renew-cert", headers=auth_headers)
        assert resp.status_code == 422

    def test_renew_busy(self, client, auth_headers, db_session):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id)
        cert_renew_service._renew_lock.acquire()
        try:
            resp = client.post(f"/api/v1/domains/{dom.id}/renew-cert", headers=auth_headers)
            assert resp.status_code == 409
        finally:
            cert_renew_service._renew_lock.release()

    def test_renew_missing_domain(self, client, auth_headers):
        resp = client.post("/api/v1/domains/99999/renew-cert", headers=auth_headers)
        assert resp.status_code == 404
