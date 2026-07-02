import pytest

CRED_PAYLOAD = {
    "name": "API Token",
    "key": "API_TOKEN",
    "value": "secret-abc-123",
    "description": "test credential",
}


class TestCredentialsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/credentials").status_code == 403

    def test_create_unauthenticated(self, client):
        assert client.post("/api/v1/credentials", json=CRED_PAYLOAD).status_code == 403


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
