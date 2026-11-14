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

    def test_sanitize_redacts_secrets(self):
        pem = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
        assert "PRIVATE KEY" not in baota_service._sanitize(pem)
        text = baota_service._sanitize('{"private_key": "abc", "msg": "x"}')
        assert "abc" not in text


class TestClientRequest:
    def test_post_signs_form_without_key(self, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"status": True}

        def fake_post(url, data, timeout, verify, follow_redirects):
            captured.update({"url": url, "data": data})
            return FakeResponse()

        monkeypatch.setattr(baota_service.httpx, "post", fake_post)
        baota_service._post(baota_service._panel_ctx(panel), "/acme", {"action": "test"})

        assert captured["url"] == "https://panel.example.com:8888/acme"
        assert captured["data"]["action"] == "test"
        assert "request_time" in captured["data"]
        assert "request_token" in captured["data"]
        assert "test-key" not in str(captured["data"])

    def test_get_signs_query_without_key(self, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return []

        def fake_get(url, params, timeout, verify, follow_redirects):
            captured.update({"url": url, "params": params, "follow_redirects": follow_redirects})
            return FakeResponse()

        monkeypatch.setattr(baota_service.httpx, "get", fake_get)
        baota_service._get(
            baota_service._panel_ctx(panel),
            "/btdocker/project/get_project_list",
            raw=True,
        )

        assert captured["url"] == "https://panel.example.com:8888/btdocker/project/get_project_list"
        assert captured["follow_redirects"] is False
        request_time = int(captured["params"]["request_time"])
        assert captured["params"]["request_token"] == baota_service._sign("test-key", request_time)
        assert "test-key" not in str(captured["params"])


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

    def test_resolve_site_exact_and_explicit(self):
        sites = [{"id": 1, "name": "example.com", "path": "/www/example"}]
        assert baota_service._resolve_site(sites, "", "example.com")["id"] == 1
        assert baota_service._resolve_site(sites, "Example.com", "other.com")["id"] == 1
        with pytest.raises(baota_service.BaotaError):
            baota_service._resolve_site(sites, "", "www.example.com")

    def test_resolve_site_missing_or_ambiguous(self):
        with pytest.raises(baota_service.BaotaError):
            baota_service._resolve_site([], "", "example.com")
        sites = [
            {"id": 1, "name": "example.com", "path": "/www/example"},
            {"id": 2, "name": "example.com", "path": "/www/example-2"},
        ]
        with pytest.raises(baota_service.BaotaError):
            baota_service._resolve_site(sites, "", "example.com")


class TestDockerProjects:
    def test_normalize_maps_server_name_and_filters_invalid(self):
        body = [
            {"id": 2, "server_name": "beta"},
            {"id": "1", "name": "alpha"},
            {"id": 0, "server_name": "zero"},
            {"id": "x", "server_name": "bad"},
            {"id": 4.9, "server_name": "float"},
            {"id": True, "server_name": "bool"},
            {"id": float("inf"), "server_name": "inf"},
            {"server_name": "no-id"},
            "not-a-dict",
        ]
        assert baota_service._normalize_docker_projects(body) == [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]

    def test_normalize_accepts_wrappers_and_empty(self):
        item = {"id": 3, "server_name": "gamma"}
        assert baota_service._normalize_docker_projects({"data": [item]}) == [
            {"id": 3, "name": "gamma"},
        ]
        assert baota_service._normalize_docker_projects({"data": {"list": [item]}}) == [
            {"id": 3, "name": "gamma"},
        ]
        assert baota_service._normalize_docker_projects({"data": {"data": [item]}}) == [
            {"id": 3, "name": "gamma"},
        ]
        assert baota_service._normalize_docker_projects({"data": {"project_list": [item]}}) == [
            {"id": 3, "name": "gamma"},
        ]
        assert baota_service._normalize_docker_projects({"data": []}) == []
        assert baota_service._normalize_docker_projects([]) == []
        with pytest.raises(baota_service.BaotaError):
            baota_service._normalize_docker_projects({"status": True})

    def test_normalize_status_false_is_sanitized(self):
        with pytest.raises(baota_service.BaotaError) as exc:
            baota_service._normalize_docker_projects({
                "status": False,
                "msg": "IP校验失败 private_key=super-secret",
            })
        assert "IP校验失败" in str(exc.value)
        assert "super-secret" not in str(exc.value)


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
        monkeypatch.setattr(baota_service, "get_orders", lambda ctx: [])
        monkeypatch.setattr(
            baota_service, "list_sites",
            lambda ctx: [{"id": 1, "name": "example.com", "path": "/www/example"}],
        )
        resp = client.post(f"/api/v1/baota/panels/{panel.id}/test", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["sites"] == [{"id": 1, "name": "example.com"}]
        assert resp.json()["orders"] == []

    def test_test_endpoint_orders_when_site_list_fails(self, client, auth_headers, db_session, monkeypatch):
        panel = _panel(db_session)
        monkeypatch.setattr(
            baota_service, "get_orders",
            lambda ctx: [{
                "index": "abc123",
                "domains": ["example.com"],
                "status": "valid",
                "cert_timeout": 123,
                "auth_type": "http",
            }],
        )

        def _no_sites(ctx):
            raise baota_service.BaotaError("站点列表不可用")

        monkeypatch.setattr(baota_service, "list_sites", _no_sites)
        resp = client.post(f"/api/v1/baota/panels/{panel.id}/test", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["sites"] == []
        assert body["orders"][0]["index"] == "abc123"


class TestDockerProjectAPI:
    def test_list_projects_admin(self, client, auth_headers, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        def fake_get(ctx, path, params=None, raw=False):
            captured.update({"path": path, "params": params, "raw": raw})
            return [{"id": 1, "server_name": "nextcloud"}]

        monkeypatch.setattr(baota_service, "_get", fake_get)
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == [{"id": 1, "name": "nextcloud"}]
        assert captured == {
            "path": "/btdocker/project/get_project_list",
            "params": {"p": 1, "limit": baota_service.SITE_LIMIT},
            "raw": True,
        }

    def test_list_projects_empty_and_error(self, client, auth_headers, db_session, monkeypatch):
        panel = _panel(db_session)
        monkeypatch.setattr(baota_service, "_get", lambda *args, **kwargs: [])
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

        def fail(*args, **kwargs):
            raise baota_service.BaotaError("IP校验失败")

        monkeypatch.setattr(baota_service, "_get", fail)
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers=auth_headers,
        )
        assert resp.status_code == 502
        assert "IP校验失败" in resp.json()["detail"]

    def test_list_projects_unauthenticated(self, client, db_session):
        panel = _panel(db_session)
        resp = client.get(f"/api/v1/baota/panels/{panel.id}/docker-projects")
        # 共享的 HTTPBearer 在缺少凭据时返回 403
        assert resp.status_code == 403
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    def test_list_projects_missing_panel(self, client, auth_headers):
        resp = client.get("/api/v1/baota/panels/999999/docker-projects", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "宝塔面板不存在"

    def test_list_projects_disabled_panel(self, client, auth_headers, db_session):
        panel = _panel(db_session, enabled=False)
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "宝塔面板已禁用"

    def test_list_projects_invalid_panel_id(self, client, auth_headers):
        resp = client.get("/api/v1/baota/panels/abc/docker-projects", headers=auth_headers)
        assert resp.status_code == 422

    def test_list_projects_non_admin(self, client, db_session):
        panel = _panel(db_session)
        user = User(username="docker-viewer", password_hash=hash_password("x"), role="user")
        db_session.add(user)
        db_session.commit()
        token = create_token(user.id, user.username, user.role)
        resp = client.get(
            f"/api/v1/baota/panels/{panel.id}/docker-projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestOrders:
    def test_get_orders_parses_list(self, monkeypatch):
        captured = {}

        def fake_post(ctx, path, data, raw=False):
            captured.update({"path": path, "data": data, "raw": raw})
            return [{
                "index": "abc123",
                "domains": ["example.com"],
                "status": "valid",
                "cert_timeout": 123,
                "auth_type": "http",
            }]

        monkeypatch.setattr(baota_service, "_post", fake_post)
        orders = baota_service.get_orders({"url": "https://p", "encrypted_api_key": "x", "verify_tls": True})
        assert orders == [{
            "index": "abc123",
            "domains": ["example.com"],
            "status": "valid",
            "cert_timeout": 123,
            "auth_type": "http",
        }]
        assert captured["data"] == {"action": "get_orders"}
        assert captured["raw"] is True

    def test_select_order_prefers_latest_valid(self):
        orders = [
            {"index": "old", "domains": ["example.com"], "status": "valid", "cert_timeout": 100},
            {"index": "new", "domains": ["example.com"], "status": "valid", "cert_timeout": 200},
            {"index": "pending", "domains": ["example.com"], "status": "pending", "cert_timeout": 300},
        ]
        assert baota_service._select_order(orders, "example.com")["index"] == "new"
        assert baota_service._select_order(orders, "www.example.com")["index"] == "new"
        with pytest.raises(baota_service.BaotaError):
            baota_service._select_order(orders, "example.com", "missing")

    def test_start_renewal_uses_existing_order(self, db_session, monkeypatch):
        panel = _panel(db_session)
        orders = [
            {"index": "old", "domains": ["example.com"], "status": "valid", "cert_timeout": 100},
            {"index": "new", "domains": ["example.com"], "status": "valid", "cert_timeout": 200},
        ]
        captured = {}

        def fake_post(ctx, path, data, raw=False):
            captured.update({"path": path, "data": data})
            return {"status": True, "cert": "pem", "cert_timeout": 300}

        monkeypatch.setattr(baota_service, "get_orders", lambda ctx: orders)
        monkeypatch.setattr(baota_service, "_post", fake_post)
        result = baota_service.start_renewal("example.com", {
            "panel_id": panel.id,
            "site_name": "",
            "order_index": "",
            "site_id": None,
            "site_path": "",
        })
        assert result["index"] == "new"
        assert result["site_name"] == "example.com"
        assert result["mode"] == "order"
        assert captured["data"] == {"action": "renew_cert", "index": "new"}

    def test_start_renewal_manual_site_when_no_order(self, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        def fake_post(ctx, path, data, raw=False):
            captured.update({"path": path, "data": data})
            return {"status": True, "index": "idx"}

        def _no_sites(ctx):
            raise AssertionError("should not list sites")

        monkeypatch.setattr(baota_service, "get_orders", lambda ctx: [])
        monkeypatch.setattr(baota_service, "_post", fake_post)
        monkeypatch.setattr(baota_service, "list_sites", _no_sites)
        result = baota_service.start_renewal("example.com", {
            "panel_id": panel.id,
            "site_name": "",
            "order_index": "",
            "site_id": 7,
            "site_path": "/www/example",
        })
        assert result["mode"] == "apply"
        assert captured["data"]["id"] == 7
        assert captured["data"]["auth_to"] == "/www/example"

    def test_start_renewal_docker_mode(self, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        def fake_post(ctx, path, data, raw=False):
            captured.update({"path": path, "data": data})
            return {
                "status": True,
                "msg": "申请成功!",
                "cert": "pem",
                "private_key": "key",
                "cert_timeout": 300,
            }

        def _unexpected(ctx):
            raise AssertionError("should not read orders in docker mode")

        monkeypatch.setattr(baota_service, "get_orders", _unexpected)
        monkeypatch.setattr(baota_service, "_post", fake_post)
        result = baota_service.start_renewal("dashboard.example.com", {
            "panel_id": panel.id,
            "site_name": "",
            "mode": "docker",
            "docker_id": 1,
            "order_index": "",
            "site_id": None,
            "site_path": "",
        })
        assert result["mode"] == "docker"
        assert result["direct"] is True
        assert result["index"] == ""
        assert "cert" not in result and "private_key" not in result
        assert captured["path"] == "/mod/docker/com/apply_cert_api"
        assert captured["data"] == {
            "domains": '["dashboard.example.com"]',
            "auth_type": "http",
            "auth_to": '["dashboard.example.com"]',
            "auto_wildcard": "0",
            "id": 1,
            "ca": "letsencrypt",
            "cert_algorithm": "rsa4096",
            "site_name": "dashboard.example.com",
        }

    def test_validate_docker_mode(self, db_session):
        panel = _panel(db_session)
        config = baota_service.validate_domain_config(db_session, {
            "panel_id": panel.id,
            "mode": "docker",
            "docker_id": 1,
            "site_name": "dashboard.example.com",
        })
        assert config["mode"] == "docker"
        assert config["docker_id"] == 1
        with pytest.raises(ValueError):
            baota_service.validate_domain_config(db_session, {
                "panel_id": panel.id, "mode": "docker",
            })
        for invalid in (1.5, True, float("inf")):
            with pytest.raises(ValueError):
                baota_service.validate_domain_config(db_session, {
                    "panel_id": panel.id, "mode": "docker", "docker_id": invalid,
                })

    def test_validate_advanced_fields(self, db_session):
        panel = _panel(db_session)
        config = baota_service.validate_domain_config(db_session, {
            "panel_id": panel.id,
            "site_name": "",
            "order_index": "abc123",
            "site_id": 7,
            "site_path": "/www/example",
        })
        assert config["order_index"] == "abc123"
        assert config["site_id"] == 7
        assert config["site_path"] == "/www/example"
        with pytest.raises(ValueError):
            baota_service.validate_domain_config(db_session, {
                "panel_id": panel.id, "site_path": "relative",
            })


class TestDeployOrder:
    def test_ssl_hash_deploys_via_ssl_endpoint(self, db_session, monkeypatch):
        panel = _panel(db_session)
        captured = {}

        def fake_post(ctx, path, data):
            captured.update({"path": path, "data": data})
            return {"status": True}

        monkeypatch.setattr(baota_service, "_post", fake_post)
        baota_service.deploy_order(
            "example.com",
            {"panel_id": panel.id},
            {"site_name": "example.com", "index": "", "ssl_hash": "abc123", "direct": True},
        )
        assert captured["path"] == "/ssl"
        assert captured["data"] == {
            "action": "SetCertToSite",
            "ssl_hash": "abc123",
            "siteName": "example.com",
        }


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

    def test_update_requires_admin(self, client, db_session):
        user = User(username="viewer2", password_hash=hash_password("x"), role="user")
        db_session.add(user)
        db_session.commit()
        dom = _domain(db_session, cert_provider="none", cert_auto_renew=False)
        token = create_token(user.id, user.username, user.role)
        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"port": 8443},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_empty_provider_normalized(self, client, auth_headers, db_session):
        dom = _domain(db_session, cert_provider="none", cert_auto_renew=False)
        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"cert_provider": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cert_provider"] == "none"

        resp = client.put(
            f"/api/v1/domains/{dom.id}",
            json={"cert_provider": "", "cert_auto_renew": True},
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

    def test_null_expiry_is_auto_renew_candidate(self, db_session, monkeypatch):
        panel = _panel(db_session)
        dom = _domain(db_session, panel_id=panel.id, ssl_not_after=None)
        called = []
        monkeypatch.setattr(
            cert_renew_service, "_renew_domain",
            lambda domain_id, force=False: called.append(domain_id) or 1,
        )

        assert cert_renew_service.auto_renew_domains() == 1
        assert called == [dom.id]

    def test_stale_pending_marked_failed(self, db_session):
        panel = _panel(db_session)
        dom = _domain(
            db_session,
            panel_id=panel.id,
            last_renew_status="pending",
            last_renew_attempt_at=china_now() - timedelta(hours=1),
        )

        assert cert_renew_service._renew_domain(dom.id, force=False) == 0
        db_session.expire_all()
        dom = db_session.get(Domain, dom.id)
        assert dom.last_renew_status == "failed"
        assert "上次续签未完成" in dom.last_renew_error

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
