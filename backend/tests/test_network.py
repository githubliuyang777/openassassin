from unittest.mock import patch


class TestNetworkUnauthenticated:
    def test_unauthenticated(self, client):
        resp = client.post("/api/v1/network/test", json={"host": "127.0.0.1", "port": 80})
        assert resp.status_code == 403


class TestNetworkConnectivity:
    def test_missing_fields(self, client, auth_headers):
        resp = client.post("/api/v1/network/test", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_invalid_port(self, client, auth_headers):
        resp = client.post("/api/v1/network/test", json={"host": "127.0.0.1", "port": 0}, headers=auth_headers)
        assert resp.status_code == 422

    def test_unreachable_host(self, client, auth_headers):
        with patch("app.services.network_service.socket.create_connection", side_effect=ConnectionRefusedError):
            resp = client.post("/api/v1/network/test", json={"host": "10.0.0.1", "port": 22}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "连接被拒绝"

    def test_timeout(self, client, auth_headers):
        import socket
        with patch("app.services.network_service.socket.create_connection", side_effect=socket.timeout):
            resp = client.post("/api/v1/network/test", json={"host": "10.0.0.1", "port": 22}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "超时" in body["error"]

    def test_dns_failure(self, client, auth_headers):
        import socket
        with patch("app.services.network_service.socket.create_connection", side_effect=socket.gaierror):
            resp = client.post("/api/v1/network/test", json={"host": "invalid.zzz", "port": 80}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "解析" in body["error"]

    def test_reachable(self, client, auth_headers):
        with patch("app.services.network_service.socket.create_connection") as mock_connect:
            resp = client.post("/api/v1/network/test", json={"host": "127.0.0.1", "port": 8000}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["latency_ms"] is not None
        assert body["latency_ms"] > 0
