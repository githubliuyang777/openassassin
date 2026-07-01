import pytest


class TestExecutionsUnauthenticated:
    def test_list_unauthenticated(self, client):
        assert client.get("/api/v1/executions").status_code == 403

    def test_get_unauthenticated(self, client):
        assert client.get("/api/v1/executions/1").status_code == 403


class TestExecutions:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/executions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/executions/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_log_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/executions/99999/log", headers=auth_headers)
        assert resp.status_code == 404

    def test_filter_by_script_id(self, client, auth_headers):
        resp = client.get("/api/v1/executions?script_id=1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_pagination(self, client, auth_headers):
        resp = client.get("/api/v1/executions?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "items" in data
