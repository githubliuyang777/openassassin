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


class TestChangePassword:
    def test_change_password_ok(self, client, auth_headers, admin_user):
        resp = client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "newpass123",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "密码修改成功" in resp.json()["message"]

    def test_old_password_becomes_invalid(self, client, auth_headers, admin_user):
        client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "newpass123",
        }, headers=auth_headers)
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin",
        })
        assert resp.status_code == 401

    def test_new_password_works(self, client, auth_headers, admin_user):
        client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "newpass123",
        }, headers=auth_headers)
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "newpass123",
        })
        assert resp.status_code == 200

    def test_change_password_wrong_old(self, client, auth_headers, admin_user):
        resp = client.put("/api/v1/auth/password", json={
            "old_password": "wrong", "new_password": "newpass123",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_change_password_unauth(self, client):
        resp = client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "x",
        })
        assert resp.status_code == 403

    def test_change_password_short_new(self, client, auth_headers, admin_user):
        resp = client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "12345",
        }, headers=auth_headers)
        assert resp.status_code == 422


class TestForgotPassword:
    def test_forgot_password_no_smtp(self, client):
        """Without SMTP configured, returns 503."""
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
        assert resp.status_code in (200, 503)  # 503 if no SMTP, 200 with "如该邮箱已注册"

    def test_reset_password_no_code(self, client):
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": "admin@test.com", "code": "000000", "new_password": "newpass123",
        })
        assert resp.status_code == 400

