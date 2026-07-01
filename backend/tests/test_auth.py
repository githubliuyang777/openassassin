import pytest


class TestAuthLogin:
    def test_login_ok(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "wrong",
        })
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_login_nonexistent_user(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "nobody", "password": "x",
        })
        assert resp.status_code == 401


class TestAuthMe:
    def test_me_ok(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert "id" in data

    def test_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 403

    def test_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
