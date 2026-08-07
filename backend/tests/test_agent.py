"""Tests for host-agent report API and agent token authentication."""

import pytest
from app.services.agent_service import generate_agent_token_unique


class TestAgentReport:
    def test_report_unauthenticated(self, client):
        """No Authorization header at all — returns 403 (HTTPBearer)."""
        resp = client.post("/api/v1/agents/report", json={})
        assert resp.status_code == 403

    def test_report_invalid_token(self, client):
        """Garbage bearer token should return 401."""
        resp = client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": 10},
            headers={"Authorization": "Bearer invalid-token-xxxx"},
        )
        assert resp.status_code == 401

    def test_report_valid_token(self, client, auth_headers):
        """A valid agent token should accept the report and update host snapshot."""
        # Create a host so we have an agent_token
        create_resp = client.post("/api/v1/hosts", json={
            "name": "agent-test", "hostname": "10.0.0.1", "username": "root",
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        host_id = create_resp.json()["id"]

        # Grab the agent token (must use the dedicated endpoint)
        token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        assert token_resp.status_code == 200
        agent_token = token_resp.json()["agent_token"]
        assert agent_token.startswith("oa_")
        assert len(agent_token) == 35  # "oa_" + 32 hex chars

        # Report with the agent token
        report_data = {
            "hostname": "agent-test",
            "cpu_percent": 45.2,
            "mem_percent": 62.1,
            "mem_total_mb": 7984.0,
            "mem_used_mb": 4956.0,
            "disk_percent": 33.0,
            "disk_total_gb": 50.0,
            "disk_used_gb": 16.5,
            "load_1m": 1.2,
            "load_5m": 0.8,
            "load_15m": 0.6,
            "net_rx_bytes": 1000000,
            "net_tx_bytes": 500000,
            "process_count": 187,
            "uptime_seconds": 3600,
            "agent_version": "0.1.0",
        }
        resp = client.post(
            "/api/v1/agents/report",
            json=report_data,
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Verify host snapshot updated
        host_resp = client.get(f"/api/v1/hosts/{host_id}", headers=auth_headers)
        assert host_resp.status_code == 200
        host = host_resp.json()
        assert host["is_online"] is True
        assert host["cpu_usage"] == 45.2
        assert host["mem_usage"] == 62.1
        assert host["disk_usage"] == 33.0
        assert host["agent_version"] == "0.1.0"
        assert host["last_seen_at"] is not None

    def test_report_partial_payload(self, client, auth_headers):
        """Report with only CPU should still work (all fields have defaults)."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "partial-test", "hostname": "10.0.0.2", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]
        token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        agent_token = token_resp.json()["agent_token"]

        resp = client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": 12.3},
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert resp.status_code == 200

    def test_report_invalid_payload(self, client, auth_headers):
        """Non-numeric cpu_percent should return 422."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "bad-test", "hostname": "10.0.0.3", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]
        token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        agent_token = token_resp.json()["agent_token"]

        resp = client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": "not-a-number"},
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert resp.status_code == 422


class TestAgentStatus:
    def test_status_unauthenticated(self, client):
        resp = client.get("/api/v1/agents/status")
        assert resp.status_code == 403

    def test_status_with_auth(self, client, auth_headers):
        resp = client.get("/api/v1/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_status_includes_host(self, client, auth_headers):
        """After creating a host, it should appear in status list."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "status-test", "hostname": "10.0.0.4", "username": "root",
        }, headers=auth_headers)
        assert create_resp.status_code == 201

        resp = client.get("/api/v1/agents/status", headers=auth_headers)
        hosts = resp.json()
        assert any(h["name"] == "status-test" for h in hosts)


class TestAgentToken:
    def test_get_token(self, client, auth_headers):
        """GET /hosts/{id}/agent-token returns the token."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "token-test", "hostname": "10.0.0.5", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        assert resp.status_code == 200
        token = resp.json()["agent_token"]
        assert token.startswith("oa_")

    def test_get_token_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/hosts/99999/agent-token", headers=auth_headers)
        assert resp.status_code == 404

    def test_regenerate_token(self, client, auth_headers):
        """POST /hosts/{id}/regenerate-token gives a new token, old one invalidated."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "regen-test", "hostname": "10.0.0.6", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]

        old_token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        old_token = old_token_resp.json()["agent_token"]

        regen_resp = client.post(f"/api/v1/hosts/{host_id}/regenerate-token", headers=auth_headers)
        assert regen_resp.status_code == 200
        new_token = regen_resp.json()["agent_token"]
        assert new_token != old_token
        assert new_token.startswith("oa_")

        # Old token should now be rejected
        resp = client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": 10},
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert resp.status_code == 401

        # New token should work
        resp = client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": 10},
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert resp.status_code == 200

    def test_regenerate_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/hosts/99999/regenerate-token", headers=auth_headers)
        assert resp.status_code == 404


class TestHostMetrics:
    def test_metrics_empty(self, client, auth_headers):
        """GET /hosts/{id}/metrics returns empty for host with no data."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "no-metrics", "hostname": "10.0.0.7", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/hosts/{host_id}/metrics", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_metrics_with_data(self, client, auth_headers):
        """After a report, metrics should appear."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "has-metrics", "hostname": "10.0.0.8", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]
        token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        agent_token = token_resp.json()["agent_token"]

        # Submit 2 reports
        for _ in range(2):
            client.post(
                "/api/v1/agents/report",
                json={"cpu_percent": 25.0, "mem_percent": 50.0},
                headers={"Authorization": f"Bearer {agent_token}"},
            )

        resp = client.get(f"/api/v1/hosts/{host_id}/metrics", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1  # bucketed, so at least 1 bucket

    def test_latest_metrics(self, client, auth_headers):
        """GET /hosts/{id}/metrics/latest returns most recent data."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "latest-test", "hostname": "10.0.0.9", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]
        token_resp = client.get(f"/api/v1/hosts/{host_id}/agent-token", headers=auth_headers)
        agent_token = token_resp.json()["agent_token"]

        client.post(
            "/api/v1/agents/report",
            json={"cpu_percent": 99.9, "mem_percent": 88.8, "disk_percent": 77.7},
            headers={"Authorization": f"Bearer {agent_token}"},
        )

        resp = client.get(f"/api/v1/hosts/{host_id}/metrics/latest", headers=auth_headers)
        assert resp.status_code == 200
        latest = resp.json()
        assert latest["cpu_percent"] == 99.9
        assert latest["mem_percent"] == 88.8
        assert latest["disk_percent"] == 77.7

    def test_latest_metrics_not_found(self, client, auth_headers):
        """Host with no data should 404 on latest."""
        create_resp = client.post("/api/v1/hosts", json={
            "name": "no-latest", "hostname": "10.0.0.10", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/hosts/{host_id}/metrics/latest", headers=auth_headers)
        assert resp.status_code == 404

    def test_metrics_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/hosts/99999/metrics", headers=auth_headers)
        assert resp.status_code == 404


class TestAgentService:
    def test_generate_token_unique(self, db_session):
        """generate_agent_token_unique should produce unique tokens."""
        tokens = {generate_agent_token_unique(db_session) for _ in range(100)}
        assert len(tokens) == 100

    def test_cleanup_old_metrics(self, db_session):
        """cleanup_old_metrics should delete rows older than retention."""
        from app.services.agent_service import cleanup_old_metrics
        from app.models.host_metric import HostMetric
        from datetime import timedelta
        from app.database import china_now
        from app.config import settings

        # Insert old metric
        old_time = china_now() - timedelta(days=settings.host_agent_metrics_retention_days + 1)
        m = HostMetric(host_id=1, cpu_percent=50, collected_at=old_time)
        db_session.add(m)

        # Insert fresh metric
        m2 = HostMetric(host_id=1, cpu_percent=60, collected_at=china_now())
        db_session.add(m2)
        db_session.commit()

        cleanup_old_metrics(db_session)

        remaining = db_session.query(HostMetric).all()
        assert len(remaining) == 1
        assert remaining[0].cpu_percent == 60

    def test_check_offline_hosts(self, db_session, auth_headers, client):
        """check_offline_hosts should mark hosts offline after threshold."""
        from app.services.agent_service import check_offline_hosts
        from app.models.host import Host
        from datetime import timedelta
        from app.database import china_now

        # Create a host and set it online with a stale last_seen_at
        create_resp = client.post("/api/v1/hosts", json={
            "name": "offline-test", "hostname": "10.0.0.11", "username": "root",
        }, headers=auth_headers)
        host_id = create_resp.json()["id"]

        # Manually update to look like it was online but hasn't reported recently
        host = db_session.query(Host).filter(Host.id == host_id).first()
        host.is_online = True
        host.last_seen_at = china_now() - timedelta(minutes=10)
        host.agent_token = "test-stale-token"
        db_session.commit()

        check_offline_hosts(db_session)

        db_session.refresh(host)
        assert host.is_online is False
