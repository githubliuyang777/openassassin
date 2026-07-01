import pytest

SCRIPT_PAYLOAD = {
    "name": "test-script",
    "type": "shell",
    "content": "echo hello",
    "timeout": 30,
}

SCRIPT_PAYLOAD2 = {
    "name": "another-script",
    "type": "python",
    "content": "print('hi')",
    "timeout": 60,
}


class TestScriptsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/scripts").status_code == 403

    def test_create_unauthenticated(self, client):
        assert client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD).status_code == 403

    def test_get_unauthenticated(self, client):
        assert client.get("/api/v1/scripts/1").status_code == 403

    def test_update_unauthenticated(self, client):
        assert client.put("/api/v1/scripts/1", json={}).status_code == 403

    def test_delete_unauthenticated(self, client):
        assert client.delete("/api/v1/scripts/1").status_code == 403


class TestScriptsCRUD:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/scripts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_create_script(self, client, auth_headers):
        resp = client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-script"
        assert data["type"] == "shell"
        assert data["id"] > 0

    def test_create_missing_name(self, client, auth_headers):
        resp = client.post("/api/v1/scripts", json={"type": "shell"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_get_existing(self, client, auth_headers):
        c = client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        sid = c.json()["id"]
        resp = client.get(f"/api/v1/scripts/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-script"

    def test_get_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/scripts/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_script(self, client, auth_headers):
        c = client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        sid = c.json()["id"]
        resp = client.put(f"/api/v1/scripts/{sid}", json={"name": "renamed"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put("/api/v1/scripts/99999", json={"name": "x"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_script(self, client, auth_headers):
        c = client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        sid = c.json()["id"]
        resp = client.delete(f"/api/v1/scripts/{sid}", headers=auth_headers)
        assert resp.status_code == 204
        # verify deleted
        assert client.get(f"/api/v1/scripts/{sid}", headers=auth_headers).status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/v1/scripts/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_search(self, client, auth_headers):
        client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD2, headers=auth_headers)
        resp = client.get("/api/v1/scripts?search=another", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "another-script"

    def test_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/v1/scripts", json={**SCRIPT_PAYLOAD, "name": f"s{i}"}, headers=auth_headers)
        resp = client.get("/api/v1/scripts?page=1&page_size=3", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
