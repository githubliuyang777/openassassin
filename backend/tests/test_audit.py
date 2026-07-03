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

    def test_audit_logged(self, client, auth_headers, db_session):
        """Directly write an audit log and verify it appears in the list."""
        from app.services.audit_service import create_log
        create_log(
            db_session,
            user_id=1,
            username="admin",
            action="POST",
            resource="/api/v1/hosts",
            resource_type="主机运维",
            detail="新建主机",
            ip_address="127.0.0.1",
            ip_location="本机",
        )

        resp = client.get("/api/v1/audit-logs", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert body["items"][0]["username"] == "admin"
        assert body["items"][0]["resource_type"] == "主机运维"

    def test_list_with_filters(self, client, auth_headers):
        resp = client.get("/api/v1/audit-logs?action=DELETE&page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 10

    def test_invalid_page(self, client, auth_headers):
        resp = client.get("/api/v1/audit-logs?page=0", headers=auth_headers)
        assert resp.status_code == 422
