class TestSubscriptionUnauthenticated:
    def test_list_unauthenticated(self, client):
        resp = client.get("/api/v1/subscriptions")
        assert resp.status_code == 403


class TestSubscriptionCRUD:
    def _create(self, client, auth_headers, overrides=None):
        data = {"name": "nginx", "repo_url": "https://github.com/nginx/nginx"}
        if overrides:
            data.update(overrides)
        return client.post("/api/v1/subscriptions", json=data, headers=auth_headers)

    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/subscriptions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create(self, client, auth_headers):
        resp = self._create(client, auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "nginx"
        assert body["alert_count"] == 0

    def test_create_missing_name(self, client, auth_headers):
        resp = client.post("/api/v1/subscriptions", json={"repo_url": "https://github.com/a/b"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_update(self, client, auth_headers):
        resp = self._create(client, auth_headers)
        sub_id = resp.json()["id"]
        resp = client.put(f"/api/v1/subscriptions/{sub_id}", json={"name": "nginx-updated"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "nginx-updated"

    def test_delete(self, client, auth_headers):
        resp = self._create(client, auth_headers)
        sub_id = resp.json()["id"]
        resp = client.delete(f"/api/v1/subscriptions/{sub_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_list_alerts_empty(self, client, auth_headers):
        resp = self._create(client, auth_headers)
        sub_id = resp.json()["id"]
        resp = client.get(f"/api/v1/subscriptions/{sub_id}/alerts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lookup_repo(self, client, auth_headers):
        resp = client.post("/api/v1/subscriptions/lookup", json={"repo_url": "https://github.com/nginx/nginx"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["repo_owner"] == "nginx"
        assert body["repo_name"] == "nginx"
        assert body["repo_platform"] == "github"
