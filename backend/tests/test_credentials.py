import base64
from datetime import datetime, timedelta, timezone

import pytest
import yaml

CRED_PAYLOAD = {
    "name": "API Token",
    "key": "API_TOKEN",
    "value": "secret-abc-123",
    "description": "test credential",
}


def _make_kubeconfig(expiry_days: int = 30) -> str:
    """Build a minimal kubeconfig carrying a client cert with a known expiry."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=expiry_days))
        .sign(key, hashes.SHA256())
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    return (
        "apiVersion: v1\nkind: Config\nusers:\n- name: test\n  user:\n"
        f"    client-certificate-data: {base64.b64encode(der).decode()}\n"
    )


class TestCredentialsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/credentials").status_code == 403

    def test_create_unauthenticated(self, client):
        assert client.post("/api/v1/credentials", json=CRED_PAYLOAD).status_code == 403

    def test_parse_kubeconfig_requires_auth(self, client):
        """parse-kubeconfig must not be callable without a valid JWT."""
        resp = client.post("/api/v1/credentials/parse-kubeconfig", json={"value": "x"})
        assert resp.status_code in (401, 403)

    def test_parse_kubeconfig_requires_content(self, client, auth_headers):
        resp = client.post("/api/v1/credentials/parse-kubeconfig", json={"value": ""}, headers=auth_headers)
        assert resp.status_code == 400


class TestParseKubeconfig:
    def test_parse_kubeconfig_ok(self, client, auth_headers):
        resp = client.post("/api/v1/credentials/parse-kubeconfig",
                           json={"value": _make_kubeconfig(30)}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_left"] > 0
        assert "T" in data["expires_at"]

    def test_parse_kubeconfig_days_left_matches_cert(self, client, auth_headers):
        """days_left 应与证书剩余有效期一致（允许 1 天舍入误差）。"""
        resp = client.post("/api/v1/credentials/parse-kubeconfig",
                           json={"value": _make_kubeconfig(90)}, headers=auth_headers)
        assert resp.status_code == 200
        assert 85 <= resp.json()["days_left"] <= 90

    def test_parse_kubeconfig_no_cert(self, client, auth_headers):
        resp = client.post("/api/v1/credentials/parse-kubeconfig",
                           json={"value": "apiVersion: v1\nkind: Config\nusers: []"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_parse_kubeconfig_oversized(self, client, auth_headers):
        resp = client.post("/api/v1/credentials/parse-kubeconfig",
                           json={"value": "x" * (1024 * 1024 + 1)}, headers=auth_headers)
        assert resp.status_code == 400


class TestCredentialsCRUD:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/credentials", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_credential(self, client, auth_headers):
        resp = client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Token"
        assert data["key"] == "API_TOKEN"
        assert "encrypted_value" not in data  # never exposed in list/detail response
        assert "value" not in data

    def test_create_missing_fields(self, client, auth_headers):
        resp = client.post("/api/v1/credentials", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_reveal_credential(self, client, auth_headers):
        c = client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        cid = c.json()["id"]
        resp = client.get(f"/api/v1/credentials/{cid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "secret-abc-123"  # decrypted value

    def test_reveal_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/credentials/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_credential(self, client, auth_headers):
        c = client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        cid = c.json()["id"]
        assert client.delete(f"/api/v1/credentials/{cid}", headers=auth_headers).status_code == 204
        assert client.get(f"/api/v1/credentials/{cid}", headers=auth_headers).status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/v1/credentials/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_with_items(self, client, auth_headers):
        client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        client.post("/api/v1/credentials", json={**CRED_PAYLOAD, "name": "T2", "key": "K2"}, headers=auth_headers)
        resp = client.get("/api/v1/credentials", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_create_credential_alert_defaults_true(self, client, auth_headers):
        resp = client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["alert_enabled"] is True

    def test_create_credential_with_alert_disabled(self, client, auth_headers):
        payload = {**CRED_PAYLOAD, "expires_at": "2099-12-31T00:00:00", "alert_enabled": False}
        resp = client.post("/api/v1/credentials", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["alert_enabled"] is False

    def test_update_credential_toggle_alert(self, client, auth_headers):
        c = client.post("/api/v1/credentials", json=CRED_PAYLOAD, headers=auth_headers)
        cid = c.json()["id"]
        # toggle off
        resp = client.put(f"/api/v1/credentials/{cid}", json={"alert_enabled": False}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["alert_enabled"] is False
        # toggle on
        resp = client.put(f"/api/v1/credentials/{cid}", json={"alert_enabled": True}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["alert_enabled"] is True
