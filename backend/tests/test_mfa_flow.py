"""MFA/TOTP 全流程 API 测试：绑定 → 登录二次验证 → 备用码恢复 → 禁用。

邮件发送通过 mock（app.api.auth.send_email）完成，不依赖真实 SMTP。
"""
import urllib.parse
from unittest.mock import patch

import pyotp

from app.models.user import User


class TestMfaFullFlow:
    def _setup_mfa(self, client, auth_headers, db_session, admin_user):
        """完成 TOTP 绑定，返回 (secret, backup_codes)。"""
        uid = admin_user[0]["id"]

        # 1. 先设置邮箱（绑定前置条件）
        resp = client.put("/api/v1/auth/me/email", json={"email": "admin@test.com"}, headers=auth_headers)
        assert resp.status_code == 200

        # 2. 发起绑定 → 生成邮件验证码（mock 邮件发送）
        with patch("app.api.auth.send_email") as mock_mail:
            resp = client.post("/api/v1/auth/mfa/setup/init", headers=auth_headers)
        assert resp.status_code == 200
        mock_mail.assert_called_once()

        # 3. 从数据库读取 6 位邮件验证码
        user = db_session.query(User).filter(User.id == uid).first()
        email_code = user.totp_email_code
        assert email_code and len(email_code) == 6

        # 4. 校验邮箱验证码 → provisioning_uri + setup_token
        resp = client.post("/api/v1/auth/mfa/setup/verify-email", json={"email_code": email_code}, headers=auth_headers)
        assert resp.status_code == 200
        uri = resp.json()["provisioning_uri"]
        setup_token = resp.json()["setup_token"]
        secret = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)["secret"][0]

        # 5. 输入 TOTP 确认绑定 → 返回 8 个备用码
        totp_code = pyotp.TOTP(secret).now()
        resp = client.post(
            "/api/v1/auth/mfa/setup/confirm",
            json={"setup_token": setup_token, "totp_code": totp_code},
            headers={"Authorization": f"Bearer {setup_token}"},
        )
        assert resp.status_code == 200
        backup_codes = resp.json()["backup_codes"]
        assert len(backup_codes) == 8
        assert all(len(c) == 12 for c in backup_codes)  # XXXX-XXXX-XX 格式
        return secret, backup_codes

    def test_full_mfa_flow(self, client, auth_headers, db_session, admin_user):
        secret, backup_codes = self._setup_mfa(client, auth_headers, db_session, admin_user)

        # 1. 登录 → 要求 MFA，不直接发放 access_token
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_required"] is True
        mfa_token = data["mfa_token"]
        assert "access_token" not in data

        # 2. TOTP 验证通过 → 发放正式 token
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_token": mfa_token, "totp_code": pyotp.TOTP(secret).now()},
            headers={"Authorization": f"Bearer {mfa_token}"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "admin"

        # 3. MFA 状态查询
        status = client.get("/api/v1/auth/mfa/status", headers={"Authorization": f"Bearer {token}"})
        assert status.status_code == 200
        assert status.json()["totp_enabled"] is True
        assert status.json()["backup_codes_remaining"] == 8

        # 4. 错误 TOTP → 401
        bad = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_token": mfa_token, "totp_code": "000000"},
            headers={"Authorization": f"Bearer {mfa_token}"},
        )
        assert bad.status_code == 401

        # 5. 备用码恢复登录
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        mfa_token2 = resp.json()["mfa_token"]
        resp = client.post(
            "/api/v1/auth/mfa/recovery",
            json={"mfa_token": mfa_token2, "recovery_code": backup_codes[0]},
            headers={"Authorization": f"Bearer {mfa_token2}"},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

        # 6. 备用码一次性使用：再次使用同一备用码 → 401
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        mfa_token3 = resp.json()["mfa_token"]
        resp = client.post(
            "/api/v1/auth/mfa/recovery",
            json={"mfa_token": mfa_token3, "recovery_code": backup_codes[0]},
            headers={"Authorization": f"Bearer {mfa_token3}"},
        )
        assert resp.status_code == 401

        # 7. 禁用 TOTP → 登录不再要求 MFA
        resp = client.post("/api/v1/auth/mfa/disable", json={"password": "admin"},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_mfa_setup_requires_email_first(self, client, auth_headers):
        """未设置邮箱时不允许发起 TOTP 绑定。"""
        resp = client.post("/api/v1/auth/mfa/setup/init", headers=auth_headers)
        assert resp.status_code == 400
        assert "邮箱" in resp.json()["detail"]

    def test_mfa_setup_wrong_email_code(self, client, auth_headers):
        client.put("/api/v1/auth/me/email", json={"email": "admin@test.com"}, headers=auth_headers)
        with patch("app.api.auth.send_email"):
            client.post("/api/v1/auth/mfa/setup/init", headers=auth_headers)
        resp = client.post("/api/v1/auth/mfa/setup/verify-email", json={"email_code": "000000"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_mfa_verify_rate_limited(self, client, auth_headers, db_session, admin_user):
        """连续 5 次 TOTP 错误后，第 6 次返回 429。"""
        self._setup_mfa(client, auth_headers, db_session, admin_user)  # 只用错误验证码

        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        mfa_token = resp.json()["mfa_token"]
        headers = {"Authorization": f"Bearer {mfa_token}"}
        for _ in range(5):
            r = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp_code": "000000"},
                            headers=headers)
            assert r.status_code == 401
        r = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp_code": "000000"},
                        headers=headers)
        assert r.status_code == 429
