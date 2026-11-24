import time

import pytest

from app.middleware.audit_middleware import _build_detail
from app.models.baota_panel import BaotaPanel
from app.models.credential import Credential
from app.models.domain import Domain
from app.models.domain_whois import DomainWhois
from app.models.execution import Execution
from app.models.host import Host
from app.models.host_event import HostEvent
from app.models.host_metric import HostMetric
from app.models.notepad import Notepad
from app.models.notification import NotificationGroup, NotificationRecipient
from app.models.script import Script
from app.models.site_monitor import SiteCheckResult, SiteMonitor
from app.models.subscription import Subscription, SubscriptionAlert
from app.models.vulnerability import VulnerabilityComponent, VulnerabilityFinding
from app.services import site_monitor_service
from app.services.credential_service import encrypt

BATCH_PATHS = [
    "/api/v1/site-monitors/batch-delete",
    "/api/v1/domains/batch-delete",
    "/api/v1/whois-domains/batch-delete",
    "/api/v1/scripts/batch-delete",
    "/api/v1/credentials/batch-delete",
    "/api/v1/hosts/batch-delete",
    "/api/v1/subscriptions/batch-delete",
    "/api/v1/vulnerabilities/components/batch-delete",
    "/api/v1/notepads/batch-delete",
    "/api/v1/notification-groups/batch-delete",
    "/api/v1/notification-recipients/batch-delete",
    "/api/v1/baota/panels/batch-delete",
]


def _monitor(db, name="monitor"):
    row = SiteMonitor(name=name, target="https://example.com", monitor_type="http")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _host(db, **overrides):
    values = {
        "name": "host",
        "hostname": "10.0.0.1",
        "username": "root",
    }
    values.update(overrides)
    row = Host(**values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _credential(db):
    row = Credential(name="cred", key="TOKEN", encrypted_value=encrypt("value"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _domain(db, name="example.com"):
    row = Domain(domain=name, port=443)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _whois(db, name="whois.example.com"):
    row = DomainWhois(domain=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestBatchDeleteAuthAndValidation:
    @pytest.mark.parametrize("path", BATCH_PATHS)
    def test_requires_auth(self, client, path):
        resp = client.post(path, json={"ids": [1]})
        assert resp.status_code == 403

    @pytest.mark.parametrize("ids", [[], list(range(1, 502)), [0], [-1]])
    def test_rejects_invalid_ids(self, client, auth_headers, ids):
        resp = client.post(
            "/api/v1/site-monitors/batch-delete",
            json={"ids": ids},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_deduplicates_ids_and_reports_missing(self, client, auth_headers, db_session):
        monitor = _monitor(db_session)
        resp = client.post(
            "/api/v1/site-monitors/batch-delete",
            json={"ids": [monitor.id, monitor.id, 99999]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 1, "missing": [99999]}

    def test_all_missing_is_idempotent(self, client, auth_headers):
        resp = client.post(
            "/api/v1/notepads/batch-delete",
            json={"ids": [99999]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 0, "missing": [99999]}


class TestMonitoringBatchDelete:
    def test_site_monitors_delete_history_and_retry_state(
        self, client, auth_headers, db_session,
    ):
        first = _monitor(db_session, "a")
        second = _monitor(db_session, "b")
        db_session.add(SiteCheckResult(monitor_id=first.id, is_up=True))
        db_session.commit()
        site_monitor_service._down_alert_retry_at[first.id] = time.monotonic()

        resp = client.post(
            "/api/v1/site-monitors/batch-delete",
            json={"ids": [first.id, second.id]},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2
        assert db_session.query(SiteMonitor).count() == 0
        assert db_session.query(SiteCheckResult).count() == 0
        assert first.id not in site_monitor_service._down_alert_retry_at

    def test_single_site_monitor_delete_cleans_history(self, client, auth_headers, db_session):
        monitor = _monitor(db_session)
        db_session.add(SiteCheckResult(monitor_id=monitor.id, is_up=True))
        db_session.commit()

        assert client.delete(
            f"/api/v1/site-monitors/{monitor.id}", headers=auth_headers,
        ).status_code == 204
        assert db_session.query(SiteCheckResult).count() == 0

    def test_domains_and_whois(self, client, auth_headers, db_session):
        domain = _domain(db_session)
        whois = _whois(db_session)

        resp = client.post(
            "/api/v1/domains/batch-delete",
            json={"ids": [domain.id, 99999]}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 1, "missing": [99999]}

        resp = client.post(
            "/api/v1/whois-domains/batch-delete",
            json={"ids": [whois.id]}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1
        assert db_session.query(Domain).count() == 0
        assert db_session.query(DomainWhois).count() == 0

    def test_existing_batch_toggle_still_works(self, client, auth_headers, db_session):
        first = _domain(db_session, "first.example.com")
        second = _domain(db_session, "second.example.com")

        resp = client.post(
            "/api/v1/domains/batch-toggle-alert",
            json={"ids": [first.id], "enabled": False},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        db_session.expire_all()
        assert db_session.get(Domain, first.id).alert_enabled is False
        assert db_session.get(Domain, second.id).alert_enabled is True

    @pytest.mark.parametrize("path,action_body", [
        ("/api/v1/domains/batch-toggle-alert", {"ids": []}),
        ("/api/v1/domains/batch-set-notification-group", {"ids": []}),
        ("/api/v1/whois-domains/batch-toggle-alert", {"ids": []}),
        ("/api/v1/whois-domains/batch-set-notification-group", {"ids": []}),
    ])
    def test_existing_batch_actions_reject_empty_ids(
        self, client, auth_headers, db_session, path, action_body,
    ):
        domain = _domain(db_session)
        whois = _whois(db_session)
        resp = client.post(path, json=action_body, headers=auth_headers)
        assert resp.status_code == 422
        db_session.expire_all()
        assert db_session.query(Domain).count() == 1
        assert db_session.query(DomainWhois).count() == 1


class TestOtherBatchDelete:
    def test_scripts_keep_execution_history(self, client, auth_headers, db_session):
        script = Script(name="s", type="shell", content="echo ok")
        db_session.add(script)
        db_session.commit()
        db_session.refresh(script)
        db_session.add(Execution(script_id=script.id, status="success"))
        db_session.commit()

        resp = client.post(
            "/api/v1/scripts/batch-delete",
            json={"ids": [script.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(Script).count() == 0
        assert db_session.query(Execution).count() == 1

    def test_hosts_delete_metrics_and_events(self, client, auth_headers, db_session):
        host = _host(db_session)
        db_session.add(HostMetric(host_id=host.id, cpu_percent=10))
        db_session.add(HostEvent(host_id=host.id, title="event"))
        db_session.commit()

        resp = client.post(
            "/api/v1/hosts/batch-delete",
            json={"ids": [host.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(Host).count() == 0
        assert db_session.query(HostMetric).count() == 0
        assert db_session.query(HostEvent).count() == 0

    def test_single_host_delete_cleans_children(self, client, auth_headers, db_session):
        host = _host(db_session)
        db_session.add(HostMetric(host_id=host.id, cpu_percent=10))
        db_session.commit()

        assert client.delete(
            f"/api/v1/hosts/{host.id}", headers=auth_headers,
        ).status_code == 204
        assert db_session.query(HostMetric).count() == 0

    def test_subscriptions_delete_alerts(self, client, auth_headers, db_session):
        sub = Subscription(name="repo", repo_url="https://github.com/a/b")
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        db_session.add(SubscriptionAlert(subscription_id=sub.id, alert_type="release"))
        db_session.commit()

        resp = client.post(
            "/api/v1/subscriptions/batch-delete",
            json={"ids": [sub.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(Subscription).count() == 0
        assert db_session.query(SubscriptionAlert).count() == 0

    def test_vulnerability_components_delete_findings(
        self, client, auth_headers, db_session,
    ):
        comp = VulnerabilityComponent(
            name="lodash", component_key="npm", version="1.0.0", package_name="lodash",
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)
        db_session.add(VulnerabilityFinding(component_id=comp.id, vuln_id="CVE-1"))
        db_session.commit()

        resp = client.post(
            "/api/v1/vulnerabilities/components/batch-delete",
            json={"ids": [comp.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(VulnerabilityComponent).count() == 0
        assert db_session.query(VulnerabilityFinding).count() == 0

    def test_notepads_delete(self, client, auth_headers, db_session):
        note = Notepad(title="note", content="body")
        db_session.add(note)
        db_session.commit()
        db_session.refresh(note)

        resp = client.post(
            "/api/v1/notepads/batch-delete",
            json={"ids": [note.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(Notepad).count() == 0


class TestReferenceGuards:
    def test_credential_in_use_is_blocked(self, client, auth_headers, db_session):
        cred = _credential(db_session)
        host = _host(db_session, credential_id=cred.id)

        resp = client.post(
            "/api/v1/credentials/batch-delete",
            json={"ids": [cred.id]}, headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "主机" in resp.json()["detail"]
        assert db_session.query(Credential).count() == 1

        host.credential_id = None
        db_session.commit()
        resp = client.post(
            "/api/v1/credentials/batch-delete",
            json={"ids": [cred.id]}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert db_session.query(Credential).count() == 0

    def test_single_credential_in_use_is_blocked(self, client, auth_headers, db_session):
        cred = _credential(db_session)
        _host(db_session, credential_id=cred.id)

        resp = client.delete(f"/api/v1/credentials/{cred.id}", headers=auth_headers)

        assert resp.status_code == 409
        assert db_session.query(Credential).count() == 1

    def test_single_notification_group_in_use_is_blocked(
        self, client, auth_headers, db_session,
    ):
        group = NotificationGroup(name="ops")
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)
        _host(db_session, notification_group_id=group.id)

        resp = client.delete(
            f"/api/v1/notification-groups/{group.id}", headers=auth_headers,
        )

        assert resp.status_code == 409
        assert db_session.query(NotificationGroup).count() == 1

    def test_notification_group_in_use_is_blocked_and_recipients_cascade(
        self, client, auth_headers, db_session,
    ):
        group = NotificationGroup(name="ops")
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)
        db_session.add(NotificationRecipient(
            name="email", channel_type="email", address="a@example.com",
            group_id=group.id,
        ))
        host = _host(db_session, notification_group_id=group.id)

        resp = client.post(
            "/api/v1/notification-groups/batch-delete",
            json={"ids": [group.id]}, headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "通知组仍被引用" in resp.json()["detail"]
        assert db_session.query(NotificationGroup).count() == 1

        host.notification_group_id = None
        db_session.commit()
        resp = client.post(
            "/api/v1/notification-groups/batch-delete",
            json={"ids": [group.id]}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert db_session.query(NotificationGroup).count() == 0
        assert db_session.query(NotificationRecipient).count() == 0

    def test_baota_panel_in_use_is_blocked(self, client, auth_headers, db_session):
        panel = BaotaPanel(
            name="panel",
            panel_url="https://panel.example.com",
            encrypted_api_key=encrypt("api-key"),
        )
        db_session.add(panel)
        db_session.commit()
        db_session.refresh(panel)
        domain = Domain(
            domain="panel.example.com",
            port=443,
            cert_provider="baota",
            cert_provider_config={"panel_id": panel.id},
        )
        db_session.add(domain)
        db_session.commit()

        resp = client.post(
            "/api/v1/baota/panels/batch-delete",
            json={"ids": [panel.id]}, headers=auth_headers,
        )
        assert resp.status_code == 409
        assert db_session.query(BaotaPanel).count() == 1

        domain.cert_provider_config = {}
        db_session.commit()
        resp = client.post(
            "/api/v1/baota/panels/batch-delete",
            json={"ids": [panel.id]}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert db_session.query(BaotaPanel).count() == 0

    def test_recipients_batch_delete(self, client, auth_headers, db_session):
        group = NotificationGroup(name="ops")
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)
        recipient = NotificationRecipient(
            name="dingtalk", channel_type="dingtalk", address="13800138000",
            group_id=group.id,
        )
        db_session.add(recipient)
        db_session.commit()
        db_session.refresh(recipient)

        resp = client.post(
            "/api/v1/notification-recipients/batch-delete",
            json={"ids": [recipient.id]}, headers=auth_headers,
        )

        assert resp.status_code == 200
        assert db_session.query(NotificationRecipient).count() == 0


def test_audit_detail_for_batch_delete():
    assert _build_detail("POST", "site-monitors", "站点监控", "/batch-delete") == "批量删除站点监控"
    assert _build_detail(
        "POST", "vulnerabilities", "漏洞监控", "/components/batch-delete",
    ) == "批量删除漏洞监控"
    assert _build_detail(
        "POST", "baota", "证书维护平台", "/panels/batch-delete",
    ) == "批量删除证书维护平台"
