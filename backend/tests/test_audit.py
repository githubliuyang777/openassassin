class TestAuditLogsUnauthenticated:
    def test_list_unauthenticated(self, client):
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 403


class TestAuditLogs:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/audit-logs", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    def test_audit_logged_on_create(self, client, auth_headers):
        """Creating a host should produce an audit log entry."""
        resp = client.post(
            "/api/v1/hosts",
            json={"name": "audit-test", "hostname": "10.0.0.1", "username": "root"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

        resp2 = client.get("/api/v1/audit-logs", headers=auth_headers)
        assert resp2.status_code == 200
        body = resp2.json()
        assert body["total"] >= 1

    def test_list_with_filters(self, client, auth_headers):
        resp = client.get("/api/v1/audit-logs?action=DELETE&page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 10

    def test_invalid_page(self, client, auth_headers):
        resp = client.get("/api/v1/audit-logs?page=0", headers=auth_headers)
        assert resp.status_code == 422
