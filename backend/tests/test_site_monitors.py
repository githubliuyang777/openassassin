MONITOR_PAYLOAD = {"name": "测试站点", "target": "https://httpbin.org/get", "monitor_type": "http"}


class TestSiteMonitorsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/site-monitors").status_code == 403

    def test_create_unauthenticated(self, client):
        assert client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD).status_code == 403


class TestSiteMonitorsCRUD:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/site-monitors", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create(self, client, auth_headers):
        resp = client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试站点"
        assert data["monitor_type"] == "http"
        assert data["is_up"] is True
        assert data["alert_enabled"] is True

    def test_create_tcp(self, client, auth_headers):
        resp = client.post("/api/v1/site-monitors", json={
            "name": "TCP 测试", "target": "1.2.3.4:80", "monitor_type": "tcp",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["monitor_type"] == "tcp"

    def test_create_missing_name(self, client, auth_headers):
        resp = client.post("/api/v1/site-monitors", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_get(self, client, auth_headers):
        c = client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
        mid = c.json()["id"]
        resp = client.get(f"/api/v1/site-monitors/{mid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试站点"

    def test_get_nonexistent(self, client, auth_headers):
        assert client.get("/api/v1/site-monitors/99999", headers=auth_headers).status_code == 404

    def test_update(self, client, auth_headers):
        c = client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
        mid = c.json()["id"]
        resp = client.put(f"/api/v1/site-monitors/{mid}", json={
            "name": "已更新", "timeout": 30,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "已更新"
        assert resp.json()["timeout"] == 30

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put("/api/v1/site-monitors/99999", json={"name": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete(self, client, auth_headers):
        c = client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
        mid = c.json()["id"]
        assert client.delete(f"/api/v1/site-monitors/{mid}", headers=auth_headers).status_code == 204
        assert client.get(f"/api/v1/site-monitors/{mid}", headers=auth_headers).status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        assert client.delete("/api/v1/site-monitors/99999", headers=auth_headers).status_code == 404

    def test_list_with_items(self, client, auth_headers):
        client.post("/api/v1/site-monitors", json={"name": "A", "target": "https://a.com"}, headers=auth_headers)
        client.post("/api/v1/site-monitors", json={"name": "B", "target": "https://b.com"}, headers=auth_headers)
        resp = client.get("/api/v1/site-monitors", headers=auth_headers)
        assert len(resp.json()) == 2

    def test_defaults(self, client, auth_headers):
        resp = client.post("/api/v1/site-monitors", json={"name": "D", "target": "https://d.com"}, headers=auth_headers)
        data = resp.json()
        assert data["timeout"] == 10
        assert data["retries"] == 2
        assert data["check_interval"] == 300
        assert data["http_method"] == "GET"
        assert data["expected_status_codes"] == "200"

    def test_history(self, client, auth_headers):
        c = client.post("/api/v1/site-monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
        mid = c.json()["id"]
        resp = client.get(f"/api/v1/site-monitors/{mid}/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
