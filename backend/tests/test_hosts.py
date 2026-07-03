class TestHostsUnauthenticated:
    def test_list_unauthenticated(self, client):
        resp = client.get("/api/v1/hosts")
        assert resp.status_code == 403

    def test_create_unauthenticated(self, client):
        resp = client.post("/api/v1/hosts", json={"name": "test", "hostname": "1.2.3.4", "username": "root"})
        assert resp.status_code == 403


class TestHostsCRUD:
    def _create(self, client, auth_headers, overrides=None):
        data = {"name": "test-host", "hostname": "192.168.1.1", "port": 22, "username": "root", "description": ""}
        if overrides:
            data.update(overrides)
        return client.post("/api/v1/hosts", json=data, headers=auth_headers)

    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/hosts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_host(self, client, auth_headers):
        resp = self._create(client, auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "test-host"
        assert body["hostname"] == "192.168.1.1"
        assert body["port"] == 22
        assert body["username"] == "root"
        assert body["credential_id"] is None
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_missing_name(self, client, auth_headers):
        resp = client.post("/api/v1/hosts", json={"hostname": "1.2.3.4", "username": "root"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_list_with_items(self, client, auth_headers):
        self._create(client, auth_headers, {"name": "host-a"})
        self._create(client, auth_headers, {"name": "host-b"})
        resp = client.get("/api/v1/hosts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_update_host(self, client, auth_headers):
        create_resp = self._create(client, auth_headers)
        host_id = create_resp.json()["id"]
        resp = client.put(f"/api/v1/hosts/{host_id}", json={"name": "renamed"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"
        assert resp.json()["hostname"] == "192.168.1.1"

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put("/api/v1/hosts/9999", json={"name": "x"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_host(self, client, auth_headers):
        create_resp = self._create(client, auth_headers)
        host_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/hosts/{host_id}", headers=auth_headers)
        assert resp.status_code == 204
        resp2 = client.get("/api/v1/hosts", headers=auth_headers)
        assert resp2.json() == []

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/v1/hosts/9999", headers=auth_headers)
        assert resp.status_code == 404
