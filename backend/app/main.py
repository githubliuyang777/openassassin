import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.audit_middleware import AuditMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.services.auth_service import get_or_create_admin
from app.api import auth, scripts, credentials, executions, notifications, domains, domain_whois, hosts, network, audit_logs, subscriptions, alerts, notepads, site_monitors, notification_groups, notification_recipients, dingtalk


def _migrate(table: str, columns: list[tuple[str, str]]):
    """Add new columns to an existing table if missing (SQLite)."""
    from sqlalchemy import text
    with engine.begin() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass


def _migrate_users_table():
    _migrate("users", [
        ("email", "VARCHAR(128) DEFAULT ''"),
        ("reset_code", "VARCHAR(8)"),
        ("reset_code_expires_at", "DATETIME"),
        ("totp_secret", "VARCHAR(512)"),
        ("totp_enabled", "INTEGER DEFAULT 0"),
        ("totp_email_code", "VARCHAR(8)"),
        ("totp_email_code_expires_at", "DATETIME"),
        ("totp_failed_attempts", "INTEGER DEFAULT 0"),
        ("totp_failed_at", "DATETIME"),
        ("backup_codes", "TEXT"),
        ("backup_codes_used", "INTEGER DEFAULT 0"),
        ("login_failed_attempts", "INTEGER DEFAULT 0"),
        ("login_failed_at", "DATETIME"),
        ("login_alert_sent", "INTEGER DEFAULT 0"),
    ])


def _migrate_credentials_table():
    _migrate("credentials", [
        ("type", "VARCHAR(32) DEFAULT 'generic'"),
        ("expires_at", "DATETIME"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_alerted_at", "DATETIME"),
        ("notification_group_id", "INTEGER"),
    ])


def _migrate_domains_table():
    _migrate("domains", [
        ("ssl_subject", "VARCHAR(512)"),
        ("ssl_issuer", "VARCHAR(512)"),
        ("ssl_not_before", "DATETIME"),
        ("ssl_not_after", "DATETIME"),
        ("ssl_expired", "BOOLEAN DEFAULT 0"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_checked_at", "DATETIME"),
        ("notification_group_id", "INTEGER"),
    ])


def _migrate_audit_logs_table():
    _migrate("audit_logs", [
        ("user_agent", "VARCHAR(256) DEFAULT ''"),
        ("status_code", "INTEGER DEFAULT 0"),
        ("resource_type", "VARCHAR(64) DEFAULT ''"),
        ("ip_location", "VARCHAR(128) DEFAULT ''"),
    ])


def _migrate_hosts_table():
    _migrate("hosts", [
        ("description", "VARCHAR(512) DEFAULT ''"),
        ("updated_at", "DATETIME"),
    ])


def _migrate_subscriptions_table():
    _migrate("subscriptions", [
        ("last_version", "VARCHAR(64) DEFAULT ''"),
        ("last_advisory_ghsa_id", "VARCHAR(32) DEFAULT ''"),
        ("last_checked_at", "DATETIME"),
        ("updated_at", "DATETIME"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("notification_group_id", "INTEGER"),
    ])
    _migrate("subscription_alerts", [
        ("ref_id", "VARCHAR(64) DEFAULT ''"),
        ("url", "VARCHAR(512) DEFAULT ''"),
    ])


def _migrate_domain_whois_table():
    _migrate("domain_whois", [
        ("whois_expiry_date", "DATETIME"),
        ("whois_creation_date", "DATETIME"),
        ("whois_registrar", "VARCHAR(256)"),
        ("whois_statuses", "TEXT"),
        ("whois_nameservers", "TEXT"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_checked_at", "DATETIME"),
        ("notification_group_id", "INTEGER"),
    ])


def _migrate_site_monitors_table():
    _migrate("site_monitors", [
        ("last_alerted_at", "DATETIME"),
        ("group_name", "VARCHAR(64) DEFAULT ''"),
        ("notification_group_id", "INTEGER"),
    ])


def _repair_stale_data():
    """Backfill NULL/empty fields for existing rows after schema changes."""
    from sqlalchemy import text
    with engine.begin() as conn:
        # Fill NULL booleans with their intended defaults
        for table, col, default in [
            ("domains", "alert_enabled", "1"),
            ("domain_whois", "alert_enabled", "1"),
            ("credentials", "alert_enabled", "1"),
            ("subscriptions", "alert_enabled", "1"),
            ("credentials", "type", "'generic'"),
            ("users", "totp_enabled", "0"),
            ("users", "totp_failed_attempts", "0"),
            ("users", "backup_codes_used", "0"),
        ]:
            try:
                conn.execute(text(f"UPDATE {table} SET {col} = {default} WHERE {col} IS NULL"))
            except Exception:
                pass

        # Fill NULL text fields with empty string
        for table, col in [
            ("hosts", "description"),
            ("hosts", "updated_at"),
            ("audit_logs", "user_agent"),
            ("audit_logs", "resource_type"),
            ("audit_logs", "ip_location"),
        ]:
            try:
                conn.execute(text(f"UPDATE {table} SET {col} = '' WHERE {col} IS NULL"))
            except Exception:
                pass

        # Set updated_at from created_at where NULL (hosts)
        try:
            conn.execute(text(
                "UPDATE hosts SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''"
            ))
        except Exception:
            pass

        # Backfill audit_logs.resource_type from resource path
        _module_map = {
            "hosts": "主机运维", "scripts": "脚本管理", "credentials": "密钥管理",
            "executions": "执行历史", "domains": "域名证书", "whois-domains": "域名WHOIS",
            "notifications": "消息通知", "network": "网络测试", "auth": "认证",
        }
        for module, label in _module_map.items():
            try:
                conn.execute(text(
                    "UPDATE audit_logs SET resource_type = :label "
                    "WHERE (resource_type IS NULL OR resource_type = '') "
                    "AND resource LIKE :pat"
                ), {"label": label, "pat": f"/api/v1/{module}%"})
            except Exception:
                pass

        # Backfill audit_logs.ip_location for known IP types
        _private_prefixes = [
            "127.", "192.168.", "10.",
            "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
            "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
            "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
        ]
        try:
            conn.execute(text(
                "UPDATE audit_logs SET ip_location = '本机' "
                "WHERE (ip_location IS NULL OR ip_location = '') "
                "AND (ip_address = '127.0.0.1' OR ip_address = 'localhost' OR ip_address = '::1')"
            ))
        except Exception:
            pass
        for prefix in _private_prefixes:
            try:
                conn.execute(text(
                    "UPDATE audit_logs SET ip_location = '内网' "
                    "WHERE (ip_location IS NULL OR ip_location = '') "
                    "AND ip_address LIKE :pat"
                ), {"pat": f"{prefix}%"})
            except Exception:
                pass
        try:
            conn.execute(text(
                "UPDATE audit_logs SET ip_location = '未知' "
                "WHERE (ip_location IS NULL OR ip_location = '') AND ip_address != '' AND ip_address != 'unknown'"
            ))
        except Exception:
            pass

        # Regenerate audit_logs.detail for old entries (format: "METHOD /api/v1/...")
        _action_map = {
            ("POST", "主机运维"): "新建主机", ("PUT", "主机运维"): "更新主机", ("DELETE", "主机运维"): "删除主机",
            ("POST", "脚本管理"): "创建脚本", ("PUT", "脚本管理"): "更新脚本", ("DELETE", "脚本管理"): "删除脚本",
            ("POST", "密钥管理"): "新建密钥", ("PUT", "密钥管理"): "更新密钥", ("DELETE", "密钥管理"): "删除密钥",
            ("POST", "域名证书"): "添加域名", ("DELETE", "域名证书"): "删除域名",
            ("POST", "域名WHOIS"): "添加域名", ("DELETE", "域名WHOIS"): "删除域名",
            ("POST", "网络测试"): "TCP 连通性测试",
            ("POST", "认证"): "用户登录", ("PUT", "认证"): "修改密码",
        }
        for (act, rt), detail in _action_map.items():
            try:
                conn.execute(text(
                    "UPDATE audit_logs SET detail = :detail "
                    "WHERE resource_type = :rt AND action = :act "
                    "AND (detail LIKE '/api/v1/%' OR detail LIKE 'POST /%' OR "
                    "    detail LIKE 'PUT /%' OR detail LIKE 'DELETE /%' OR detail LIKE 'PATCH /%')"
                ), {"detail": detail, "rt": rt, "act": act})
            except Exception:
                pass


async def _subscription_check_loop():
    """Background task: at 9am daily, check subscriptions for new releases/advisories."""
    from datetime import datetime, timezone
    while True:
        await asyncio.sleep(settings.alert_check_interval_minutes * 60)
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now.hour != 1:  # UTC 1:00 = CST 9:00
                continue
            from app.services.subscription_service import check_all_subscriptions
            db = SessionLocal()
            try:
                today = now.strftime("%Y-%m-%d")
                last_run = getattr(_subscription_check_loop, "_last_run_date", "")
                if last_run == today:
                    continue
                check_all_subscriptions()
                _subscription_check_loop._last_run_date = today
            finally:
                db.close()
        except Exception:
            pass


async def _audit_cleanup_loop():
    """Background task: periodically delete audit logs older than retention period."""
    while True:
        await asyncio.sleep(3600)
        try:
            from app.services.audit_service import cleanup_old_logs
            db = SessionLocal()
            try:
                cleanup_old_logs(db)
            finally:
                db.close()
        except Exception:
            pass


async def _alert_check_loop():
    """Background task: periodically check for expiring credentials and send alerts."""
    while True:
        await asyncio.sleep(settings.alert_check_interval_minutes * 60)
        try:
            from app.services.alert_service import check_and_alert
            db = SessionLocal()
            try:
                check_and_alert(db)
            finally:
                db.close()
        except Exception:
            pass


async def _site_monitor_check_loop():
    """Background task: periodically check all site monitors."""
    while True:
        await asyncio.sleep(30)
        try:
            from app.services.site_monitor_service import check_all_monitors
            check_all_monitors()
        except Exception:
            pass


async def _host_agent_check_loop():
    """Background task: detect offline hosts and clean up old metrics."""
    _last_cleanup_date = ""
    while True:
        await asyncio.sleep(60)
        try:
            from app.services.agent_service import check_offline_hosts, cleanup_old_metrics
            from datetime import datetime, timezone
            db = SessionLocal()
            try:
                await asyncio.to_thread(check_offline_hosts, db)
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if _last_cleanup_date != today:
                    await asyncio.to_thread(cleanup_old_metrics, db)
                    _last_cleanup_date = today
            finally:
                db.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.log_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    _migrate_credentials_table()
    _migrate_domains_table()
    _migrate_domain_whois_table()
    _migrate_hosts_table()
    _migrate_audit_logs_table()
    _migrate_subscriptions_table()
    _migrate_site_monitors_table()
    _repair_stale_data()
    db = SessionLocal()
    get_or_create_admin(db)
    db.close()
    task = asyncio.create_task(_alert_check_loop())
    cleanup_task = asyncio.create_task(_audit_cleanup_loop())
    sub_task = asyncio.create_task(_subscription_check_loop())
    site_task = asyncio.create_task(_site_monitor_check_loop())
    agent_task = asyncio.create_task(_host_agent_check_loop())
    yield
    task.cancel()
    cleanup_task.cancel()
    sub_task.cancel()
    site_task.cancel()
    agent_task.cancel()


app = FastAPI(title="openAssassin", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(scripts.router, prefix="/api/v1")
app.include_router(credentials.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(domains.router, prefix="/api/v1")
app.include_router(domain_whois.router, prefix="/api/v1")
app.include_router(hosts.router, prefix="/api/v1")
app.include_router(network.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(notepads.router, prefix="/api/v1")
app.include_router(site_monitors.router, prefix="/api/v1")
app.include_router(notification_groups.router, prefix="/api/v1")
app.include_router(notification_recipients.router, prefix="/api/v1")
app.include_router(dingtalk.router, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok"}
