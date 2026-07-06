import pytest

NOTEPAD_PAYLOAD = {"title": "测试记事本", "content": "第一行\n第二行\n第三行"}


class TestNotepadsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/notepads").status_code == 403

    def test_create_unauthenticated(self, client):
        assert client.post("/api/v1/notepads", json=NOTEPAD_PAYLOAD).status_code == 403


class TestNotepadsCRUD:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/notepads", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    def test_create(self, client, auth_headers):
        resp = client.post("/api/v1/notepads", json=NOTEPAD_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "测试记事本"
        assert data["content"] == "第一行\n第二行\n第三行"
        assert data["id"] is not None

    def test_create_missing_title(self, client, auth_headers):
        resp = client.post("/api/v1/notepads", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_get(self, client, auth_headers):
        c = client.post("/api/v1/notepads", json=NOTEPAD_PAYLOAD, headers=auth_headers)
        nid = c.json()["id"]
        resp = client.get(f"/api/v1/notepads/{nid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "测试记事本"

    def test_get_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/notepads/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update(self, client, auth_headers):
        c = client.post("/api/v1/notepads", json=NOTEPAD_PAYLOAD, headers=auth_headers)
        nid = c.json()["id"]
        resp = client.put(f"/api/v1/notepads/{nid}", json={"title": "已更新"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "已更新"
        assert resp.json()["content"] == "第一行\n第二行\n第三行"  # unchanged

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put("/api/v1/notepads/99999", json={"title": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_delete(self, client, auth_headers):
        c = client.post("/api/v1/notepads", json=NOTEPAD_PAYLOAD, headers=auth_headers)
        nid = c.json()["id"]
        assert client.delete(f"/api/v1/notepads/{nid}", headers=auth_headers).status_code == 204
        assert client.get(f"/api/v1/notepads/{nid}", headers=auth_headers).status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/v1/notepads/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_with_items(self, client, auth_headers):
        client.post("/api/v1/notepads", json={"title": "A"}, headers=auth_headers)
        client.post("/api/v1/notepads", json={"title": "B"}, headers=auth_headers)
        resp = client.get("/api/v1/notepads", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert len(resp.json()["items"]) == 2


class TestNotepadsSearch:
    def test_search_title(self, client, auth_headers):
        client.post("/api/v1/notepads", json={"title": "nginx配置"}, headers=auth_headers)
        client.post("/api/v1/notepads", json={"title": "mysql备份"}, headers=auth_headers)
        resp = client.get("/api/v1/notepads?search=nginx", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "nginx配置"

    def test_search_content(self, client, auth_headers):
        client.post("/api/v1/notepads", json={"title": "A", "content": "docker compose up"}, headers=auth_headers)
        client.post("/api/v1/notepads", json={"title": "B", "content": "kubectl apply"}, headers=auth_headers)
        resp = client.get("/api/v1/notepads?search=docker", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "A"

    def test_search_no_match(self, client, auth_headers):
        client.post("/api/v1/notepads", json={"title": "测试"}, headers=auth_headers)
        resp = client.get("/api/v1/notepads?search=nonexistent", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestNotepadsPagination:
    def test_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/v1/notepads", json={"title": f"笔记{i}"}, headers=auth_headers)
        resp = client.get("/api/v1/notepads?page=1&page_size=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) == 2
