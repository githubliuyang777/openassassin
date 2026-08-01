import os
from unittest.mock import patch

import pytest

from app.config import settings

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


class TestScriptExecute:
    """POST /scripts/{id}/execute: 通过 mock sandbox 覆盖超时/成功/凭据注入场景。"""

    def _create(self, client, auth_headers):
        resp = client.post("/api/v1/scripts", json=SCRIPT_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_execute_nonexistent(self, client, auth_headers):
        resp = client.post("/api/v1/scripts/99999/execute", json={"credential_ids": []}, headers=auth_headers)
        assert resp.status_code == 404

    def test_execute_timeout_recorded(self, client, auth_headers):
        """sandbox 返回 timeout → 执行记录落库为 timeout、exit_code=-1、日志文件可读。"""
        sid = self._create(client, auth_headers)
        with patch("app.api.scripts.execute_script") as mock_exec:
            mock_exec.return_value = {"status": "timeout", "exit_code": -1, "log": "run too long\n"}
            resp = client.post(f"/api/v1/scripts/{sid}/execute", json={"credential_ids": []}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "timeout"
        assert data["exit_code"] == -1
        assert data["log"] == "run too long\n"

        exid = data["id"]
        try:
            rec = client.get(f"/api/v1/executions/{exid}", headers=auth_headers).json()
            assert rec["status"] == "timeout"
            assert rec["exit_code"] == -1
            log = client.get(f"/api/v1/executions/{exid}/log", headers=auth_headers).json()
            assert log["log"] == "run too long\n"
        finally:
            os.remove(os.path.join(settings.log_dir, f"{exid}.log"))  # 清理临时日志

    def test_execute_success_recorded(self, client, auth_headers):
        sid = self._create(client, auth_headers)
        with patch("app.api.scripts.execute_script") as mock_exec:
            mock_exec.return_value = {"status": "success", "exit_code": 0, "log": "ok"}
            resp = client.post(f"/api/v1/scripts/{sid}/execute", json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["exit_code"] == 0
        exid = data["id"]
        rec = client.get(f"/api/v1/executions/{exid}", headers=auth_headers).json()
        assert rec["status"] == "success"
        os.remove(os.path.join(settings.log_dir, f"{exid}.log"))

    def test_execute_failure_recorded(self, client, auth_headers):
        sid = self._create(client, auth_headers)
        with patch("app.api.scripts.execute_script") as mock_exec:
            mock_exec.return_value = {"status": "failed", "exit_code": 2, "log": "boom"}
            resp = client.post(f"/api/v1/scripts/{sid}/execute", json={"credential_ids": []}, headers=auth_headers)
        assert resp.json()["status"] == "failed"
        assert resp.json()["exit_code"] == 2
        os.remove(os.path.join(settings.log_dir, f"{resp.json()['id']}.log"))

    def test_execute_injects_decrypted_credentials(self, client, auth_headers):
        """传入 credential_ids → sandbox 收到解密后的明文值（内存中解密，响应不回显）。"""
        c = client.post("/api/v1/credentials", json={
            "name": "API Token", "key": "API_TOKEN", "value": "secret-abc-123", "description": "t",
        }, headers=auth_headers)
        cid = c.json()["id"]
        sid = self._create(client, auth_headers)
        with patch("app.api.scripts.execute_script") as mock_exec:
            mock_exec.return_value = {"status": "success", "exit_code": 0, "log": ""}
            resp = client.post(f"/api/v1/scripts/{sid}/execute", json={"credential_ids": [cid]}, headers=auth_headers)
        assert resp.status_code == 200
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["credential_values"] == {"API_TOKEN": "secret-abc-123"}
        # 响应与日志中不得出现明文值
        assert "secret-abc-123" not in resp.json()["log"]
        os.remove(os.path.join(settings.log_dir, f"{resp.json()['id']}.log"))
