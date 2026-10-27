from app.config import settings
from app.main import app
from app.models.user import User
from app.services.auth_service import create_token, hash_password

VERSION_URL = "/api/v1/system/version"


def _create_user(db, username: str, role: str) -> User:
    user = User(username=username, password_hash=hash_password("password"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestVersionEndpoint:
    def test_admin_can_read_version(self, client, auth_headers):
        resp = client.get(VERSION_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"version": "test-version"}
        assert resp.json()["version"] == settings.app_version
        assert "no-store" in resp.headers["cache-control"]
        assert resp.headers["pragma"] == "no-cache"
        assert resp.headers["vary"] == "Authorization"

    def test_no_token_is_denied(self, client):
        assert client.get(VERSION_URL).status_code == 403

    def test_invalid_token_is_denied(self, client):
        resp = client.get(VERSION_URL, headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_non_admin_is_denied(self, client, db_session):
        user = _create_user(db_session, "viewer", "viewer")
        token = create_token(user.id, user.username, user.role)
        resp = client.get(VERSION_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_deleted_user_is_denied(self, client):
        token = create_token(999999, "ghost", "admin")
        resp = client.get(VERSION_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_token_role_is_not_trusted_after_db_demotion(self, client, db_session):
        user = _create_user(db_session, "demoted", "admin")
        token = create_token(user.id, user.username, "admin")
        user.role = "viewer"
        db_session.commit()

        resp = client.get(VERSION_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_db_admin_role_overrides_stale_token_role(self, client, admin_user):
        user, _ = admin_user
        token = create_token(user["id"], user["username"], "user")

        resp = client.get(VERSION_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestVersionPublicSurface:
    def test_api_docs_are_disabled_by_default(self, client):
        for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            assert client.get(path).status_code == 404

    def test_openapi_version_is_api_contract_not_build_version(self):
        assert app.version == "v1"
        assert app.version != settings.app_version

    def test_health_does_not_expose_version(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
