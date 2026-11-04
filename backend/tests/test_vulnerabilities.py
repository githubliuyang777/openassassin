import pytest

from app.models.vulnerability import VulnerabilityComponent, VulnerabilityFinding
from app.services import vulnerability_service


def _finding(vuln_id: str = "CVE-2024-0001", severity: str = "high", fixed_version: str = "1.2.3") -> dict:
    return {
        "vuln_id": vuln_id,
        "title": "test vulnerability",
        "severity": severity,
        "cvss_score": 7.5,
        "fixed_version": fixed_version,
        "url": f"https://osv.dev/vulnerability/{vuln_id}",
        "source": "osv",
        "published_at": None,
    }


def _component(db, component_key: str = "npm", version: str = "4.17.20", package_name: str = "lodash", **kwargs):
    comp = VulnerabilityComponent(
        name=package_name or component_key,
        component_key=component_key,
        version=version,
        package_name=package_name,
        **kwargs,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@pytest.fixture
def no_findings(monkeypatch):
    monkeypatch.setattr(vulnerability_service, "_fetch_findings", lambda *args, **kwargs: [])


class TestCatalog:
    def test_unauthenticated(self, client):
        assert client.get("/api/v1/vulnerabilities/catalog").status_code == 403

    def test_catalog(self, client, auth_headers):
        resp = client.get("/api/v1/vulnerabilities/catalog", headers=auth_headers)
        assert resp.status_code == 200
        items = {item["key"]: item for item in resp.json()}
        assert items["nginx"]["source"] == "nvd"
        assert items["golang"]["source"] == "osv"
        assert items["npm"]["needs_package"] is True
        assert items["nodejs"]["needs_package"] is False


class TestComponentCRUD:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/vulnerabilities/components", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_defaults(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "nginx", "version": "1.24.0"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "NGINX"
        assert body["open_count"] == 0
        assert body["severity_counts"]["critical"] == 0

    def test_create_maven_package(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={
                "component_key": "maven",
                "version": "2.14.1",
                "package_name": "org.apache.logging.log4j:log4j-core",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["package_name"] == "org.apache.logging.log4j:log4j-core"

    def test_create_package_requires_name(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "npm", "version": "4.17.20"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_unknown_key(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "unknown", "version": "1.0.0"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_invalid_version(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "nginx", "version": "../etc/passwd"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_update_and_delete(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "php", "version": "8.1.0"},
            headers=auth_headers,
        )
        comp_id = resp.json()["id"]

        resp = client.put(
            f"/api/v1/vulnerabilities/components/{comp_id}",
            json={"version": "8.1.2", "alert_enabled": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == "8.1.2"
        assert resp.json()["alert_enabled"] is False

        assert client.delete(f"/api/v1/vulnerabilities/components/{comp_id}", headers=auth_headers).status_code == 204
        assert client.delete(f"/api/v1/vulnerabilities/components/{comp_id}", headers=auth_headers).status_code == 404
        assert client.get(
            f"/api/v1/vulnerabilities/components/{comp_id}/findings", headers=auth_headers
        ).status_code == 404


class TestParsers:
    def test_osv_dedupe_and_severity(self):
        vulns = [
            {
                "id": "PYSEC-2024-1",
                "aliases": ["CVE-2024-0001"],
                "summary": "first record",
                "database_specific": {"severity": "MODERATE"},
                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}]}],
            },
            {
                "id": "GHSA-xxxx",
                "aliases": ["CVE-2024-0001"],
                "summary": "second record",
                "database_specific": {"severity": "HIGH"},
                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}]}],
            },
        ]
        parsed = vulnerability_service._parse_osv_vulns(vulns, "4.17.20")
        assert len(parsed) == 1
        assert parsed[0]["vuln_id"] == "CVE-2024-0001"
        assert parsed[0]["severity"] == "high"
        assert parsed[0]["fixed_version"] == "4.17.21"

    def test_fixed_version_range_selection(self):
        affected = [{
            "ranges": [{
                "events": [
                    {"introduced": "0"}, {"fixed": "1.21.4"},
                    {"introduced": "1.22.0"}, {"fixed": "1.22.1"},
                ],
            }],
        }]
        assert vulnerability_service._fixed_for_version(affected, "1.21.0") == "1.21.4"
        assert vulnerability_service._fixed_for_version(affected, "1.22.0") == "1.22.1"

    def test_nvd_parse(self):
        items = [{
            "cve": {
                "id": "CVE-2024-0002",
                "vulnStatus": "Analyzed",
                "descriptions": [{"lang": "en", "value": "nginx vulnerability"}],
                "metrics": {
                    "cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}],
                },
                "configurations": [{
                    "nodes": [{
                        "cpeMatch": [{
                            "vulnerable": True,
                            "criteria": "cpe:2.3:a:nginx:nginx:1.24.0:*:*:*:*:*:*:*",
                            "versionEndExcluding": "1.24.1",
                        }],
                    }],
                }],
                "published": "2024-01-01T00:00:00.000",
            },
        }]
        parsed = vulnerability_service._parse_nvd_vulns(items, "nginx", "nginx", "1.24.0")
        assert len(parsed) == 1
        assert parsed[0]["vuln_id"] == "CVE-2024-0002"
        assert parsed[0]["severity"] == "critical"
        assert parsed[0]["cvss_score"] == 9.8
        assert parsed[0]["fixed_version"] == "1.24.1"
        assert parsed[0]["url"].endswith("CVE-2024-0002")

    def test_nvd_skips_rejected(self):
        items = [{"cve": {"id": "CVE-2024-0003", "vulnStatus": "Rejected"}}]
        assert vulnerability_service._parse_nvd_vulns(items, "php", "php", "8.1.0") == []


class TestSync:
    def test_upsert_idempotent_and_ignore_preserved(self, db_session, monkeypatch):
        comp = _component(db_session)
        monkeypatch.setattr(vulnerability_service, "_fetch_findings", lambda *args, **kwargs: [_finding()])

        assert vulnerability_service.check_component(comp.id) == 1
        db_session.expire_all()
        rows = db_session.query(VulnerabilityFinding).all()
        assert len(rows) == 1
        rows[0].status = "ignored"
        db_session.commit()

        assert vulnerability_service.check_component(comp.id) == 1
        db_session.expire_all()
        rows = db_session.query(VulnerabilityFinding).all()
        assert len(rows) == 1
        assert rows[0].status == "ignored"

        comp = db_session.get(VulnerabilityComponent, comp.id)
        assert comp.last_checked_at is not None
        assert comp.last_check_error == ""

    def test_stale_findings_removed(self, db_session, monkeypatch):
        comp = _component(db_session)
        monkeypatch.setattr(vulnerability_service, "_fetch_findings", lambda *args, **kwargs: [_finding()])
        vulnerability_service.check_component(comp.id)

        comp = db_session.get(VulnerabilityComponent, comp.id)
        comp.version = "5.0.0"
        db_session.commit()
        monkeypatch.setattr(vulnerability_service, "_fetch_findings", lambda *args, **kwargs: [])

        assert vulnerability_service.check_component(comp.id) == 0
        db_session.expire_all()
        assert db_session.query(VulnerabilityFinding).count() == 0

    def test_fetch_failure_keeps_findings(self, db_session, monkeypatch):
        comp = _component(db_session)
        monkeypatch.setattr(vulnerability_service, "_fetch_findings", lambda *args, **kwargs: [_finding()])
        vulnerability_service.check_component(comp.id)

        def _boom(*args, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(vulnerability_service, "_fetch_findings", _boom)
        assert vulnerability_service.check_component(comp.id) == 0

        db_session.expire_all()
        comp = db_session.get(VulnerabilityComponent, comp.id)
        assert comp.last_checked_at is not None
        assert "network down" in comp.last_check_error
        assert db_session.query(VulnerabilityFinding).count() == 1


class TestFindingStatus:
    def test_toggle_status(self, client, auth_headers, db_session):
        comp = _component(db_session)
        finding = VulnerabilityFinding(component_id=comp.id, **_finding())
        db_session.add(finding)
        db_session.commit()
        db_session.refresh(finding)

        resp = client.put(
            f"/api/v1/vulnerabilities/findings/{finding.id}/status",
            json={"status": "ignored"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        db_session.expire_all()
        assert db_session.get(VulnerabilityFinding, finding.id).status == "ignored"

        resp = client.put(
            f"/api/v1/vulnerabilities/findings/{finding.id}/status",
            json={"status": "foo"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert client.put(
            "/api/v1/vulnerabilities/findings/99999/status",
            json={"status": "ignored"},
            headers=auth_headers,
        ).status_code == 404


class TestCheckEndpoints:
    def test_check_component(self, client, auth_headers, no_findings):
        resp = client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "nodejs", "version": "20.11.0"},
            headers=auth_headers,
        )
        comp_id = resp.json()["id"]
        resp = client.post(f"/api/v1/vulnerabilities/components/{comp_id}/check", headers=auth_headers)
        assert resp.status_code == 202

    def test_check_all(self, client, auth_headers, no_findings):
        client.post(
            "/api/v1/vulnerabilities/components",
            json={"component_key": "jenkins", "version": "2.426.1"},
            headers=auth_headers,
        )
        resp = client.post("/api/v1/vulnerabilities/check-all", headers=auth_headers)
        assert resp.status_code == 202

    def test_check_missing_component(self, client, auth_headers):
        resp = client.post("/api/v1/vulnerabilities/components/99999/check", headers=auth_headers)
        assert resp.status_code == 404


class TestAlertIntegration:
    def _add_finding(self, db_session, severity: str):
        comp = _component(db_session, component_key="nginx", version="1.24.0", package_name="")
        db_session.add(VulnerabilityFinding(
            component_id=comp.id,
            vuln_id="CVE-2024-0004",
            title="nginx vuln",
            severity=severity,
            status="open",
        ))
        db_session.commit()

    def test_high_severity_is_danger(self, client, auth_headers, db_session):
        self._add_finding(db_session, "high")
        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        assert resp.status_code == 200
        items = [item for item in resp.json() if item["source"] == "vulnerability"]
        assert len(items) == 1
        assert items[0]["severity"] == "danger"
        assert items[0]["link"] == "/vulnerabilities"

    def test_medium_severity_is_warning(self, client, auth_headers, db_session):
        self._add_finding(db_session, "medium")
        resp = client.get("/api/v1/alerts/summary", headers=auth_headers)
        items = [item for item in resp.json() if item["source"] == "vulnerability"]
        assert len(items) == 1
        assert items[0]["severity"] == "warning"
