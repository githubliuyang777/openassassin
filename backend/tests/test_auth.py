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


class TestCaptcha:
    def test_generate_captcha_ok(self, client):
        resp = client.post("/api/v1/auth/captcha/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert "captcha_token" in data
        assert len(data["captcha_token"]) > 32

    def test_verify_captcha_correct_position(self, client):
        import app.services.captcha_service as cs
        gen = client.post("/api/v1/auth/captcha/generate")
        captcha_token = gen.json()["captcha_token"]
        target_x = cs._captcha_store[captcha_token]["target_x"]

        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token,
            "user_x": target_x,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["verification_token"] is not None
        assert "验证通过" in data["message"]

    def test_verify_captcha_wrong_position(self, client):
        import app.services.captcha_service as cs
        gen = client.post("/api/v1/auth/captcha/generate")
        captcha_token = gen.json()["captcha_token"]
        target_x = cs._captcha_store[captcha_token]["target_x"]
        wrong_x = target_x - 30  # offset 30 > CAPTCHA_TOLERANCE=25, stays in [0,300]

        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token,
            "user_x": wrong_x,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["verification_token"] is None

    def test_verify_captcha_invalid_token(self, client):
        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": "fake-token-that-does-not-exist",
            "user_x": 150,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_verify_captcha_too_many_attempts(self, client):
        import app.services.captcha_service as cs
        gen = client.post("/api/v1/auth/captcha/generate")
        captcha_token = gen.json()["captcha_token"]
        target_x = cs._captcha_store[captcha_token]["target_x"]
        wrong_x = target_x - 30  # offset 30 > CAPTCHA_TOLERANCE=25, stays in [0,300]

        for _ in range(3):
            client.post("/api/v1/auth/captcha/verify", json={
                "captcha_token": captcha_token, "user_x": wrong_x,
            })
        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token, "user_x": wrong_x,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "次数过多" in data["message"]

    def test_captcha_token_one_time_use(self, client):
        import app.services.captcha_service as cs
        gen = client.post("/api/v1/auth/captcha/generate")
        captcha_token = gen.json()["captcha_token"]
        target_x = cs._captcha_store[captcha_token]["target_x"]

        client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token, "user_x": target_x,
        })
        # Second attempt with same token should fail
        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token, "user_x": target_x,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_user_x_out_of_range(self, client):
        resp = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": "test",
            "user_x": 999,
        })
        assert resp.status_code == 422


class TestForgotPassword:
    def _get_verification_token(self, client):
        import app.services.captcha_service as cs
        gen = client.post("/api/v1/auth/captcha/generate")
        captcha_token = gen.json()["captcha_token"]
        target_x = cs._captcha_store[captcha_token]["target_x"]
        verify = client.post("/api/v1/auth/captcha/verify", json={
            "captcha_token": captcha_token, "user_x": target_x,
        })
        return verify.json()["verification_token"]

    def test_forgot_password_no_smtp(self, client):
        token = self._get_verification_token(client)
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "admin@test.com", "verification_token": token,
        })
        assert resp.status_code in (200, 503)

    def test_forgot_password_missing_verification_token(self, client):
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
        assert resp.status_code == 422

    def test_forgot_password_invalid_verification_token(self, client):
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "admin@test.com", "verification_token": "fake-token",
        })
        assert resp.status_code == 400
        assert "人机验证失败" in resp.json()["detail"]

    def test_verification_token_one_time_use(self, client):
        token = self._get_verification_token(client)
        # First use should consume the token
        client.post("/api/v1/auth/forgot-password", json={
            "email": "admin@test.com", "verification_token": token,
        })
        # Second use should fail
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "admin@test.com", "verification_token": token,
        })
        assert resp.status_code == 400
        assert "人机验证失败" in resp.json()["detail"]

    def test_reset_password_no_code(self, client):
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": "admin@test.com", "code": "000000", "new_password": "newpass123",
        })
        assert resp.status_code == 400



class TestLoginRateLimit:
    def test_login_locked_after_repeated_failures(self, client, admin_user):
        for _ in range(5):
            resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
            assert resp.status_code == 401
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_successful_login_resets_failures(self, client, admin_user):
        # 上限为 5 次失败：第 5 次之后即被锁定，因此用 4 次失败来观察"成功登录重置计数"
        for _ in range(4):
            client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        # correct password resets the per-user bucket
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_correct_password_also_locked_after_limit(self, client, admin_user):
        """达到失败上限后，即使密码正确也应被 429 拦截（限流检查先于认证）。"""
        for _ in range(5):
            client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 429

    def test_login_ip_bucket(self, client, admin_user):
        # 30 failures per IP are allowed across usernames, then blocked
        for i in range(30):
            client.post("/api/v1/auth/login", json={"username": f"user{i}", "password": "wrong"})
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 429


class TestResetPasswordRateLimit:
    def test_reset_locked_after_repeated_failures(self, client, admin_user):
        payload = {"email": "admin@test.com", "code": "000000", "new_password": "newpass123"}
        for _ in range(5):
            assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400
        resp = client.post("/api/v1/auth/reset-password", json=payload)
        assert resp.status_code == 429


class TestTokenRevocation:
    def test_old_token_invalid_after_password_change(self, client, auth_headers, admin_user):
        assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 200
        resp = client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "newpass123",
        }, headers=auth_headers)
        assert resp.status_code == 200
        # the previously issued JWT must now be rejected
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 401

    def test_new_token_works_after_password_change(self, client, auth_headers, admin_user):
        client.put("/api/v1/auth/password", json={
            "old_password": "admin", "new_password": "newpass123",
        }, headers=auth_headers)
        login = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "newpass123",
        })
        assert login.status_code == 200
        new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
