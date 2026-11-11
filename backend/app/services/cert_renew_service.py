import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal, china_now
from app.models.domain import Domain
from app.services import cert_provider_service
from app.services.domain_service import check_domain_cert
from app.services.notification_service import send_group_notification

logger = logging.getLogger(__name__)

RENEW_COOLDOWN_HOURS = 72
TLS_POLL_INTERVAL = 10
TLS_POLL_SECONDS = 180
DEPLOY_POLL_SECONDS = 120

# shortcut: 进程内锁，多副本部署时需升级为数据库/分布式锁
_renew_lock = threading.Lock()


def is_renew_running() -> bool:
    return _renew_lock.locked()


def _is_extended(old_before, old_after, info: dict) -> bool:
    new_after = info.get("ssl_not_after")
    new_before = info.get("ssl_not_before")
    if not new_after:
        return False
    if old_after is None:
        return True
    if new_after <= old_after:
        return False
    if old_before is not None and new_before is not None and new_before <= old_before:
        return False
    return True


def _poll_for_new_cert(domain: str, port: int, old_before, old_after, seconds: int):
    deadline = time.monotonic() + seconds
    while True:
        info = check_domain_cert(domain, port)
        if info and _is_extended(old_before, old_after, info):
            return info
        if time.monotonic() >= deadline:
            return None
        time.sleep(TLS_POLL_INTERVAL)


def _safe_error(exc: Exception) -> str:
    text = re.sub(r"-----BEGIN.*?-----END[^-]*-----", "[redacted]", str(exc), flags=re.S)
    return f"{type(exc).__name__}: {text}"[:300]


def _set_status(domain_id: int, status: str, error: str = "", info: dict | None = None) -> None:
    db = SessionLocal()
    try:
        dom = db.get(Domain, domain_id)
        if not dom:
            return
        dom.last_renew_status = status
        dom.last_renew_error = (error or "")[:512]
        if info:
            dom.ssl_subject = info.get("ssl_subject")
            dom.ssl_issuer = info.get("ssl_issuer")
            dom.ssl_not_before = info.get("ssl_not_before")
            dom.ssl_not_after = info.get("ssl_not_after")
            dom.ssl_expired = bool(info.get("ssl_expired"))
            dom.last_checked_at = info.get("last_checked_at")
        db.commit()
    finally:
        db.close()


def _notify(domain_id: int, success: bool, detail: str) -> None:
    db = SessionLocal()
    try:
        dom = db.get(Domain, domain_id)
        if not dom:
            return
        subject = f"[openAssassin] 域名证书自动续签{'成功' if success else '失败'}: {dom.domain}"
        body = (
            f"域名: {dom.domain}\n"
            f"维护平台: {dom.cert_provider}\n"
            f"{detail}"
        )
        send_group_notification(
            db, dom.notification_group_id, settings.alert_email, subject, body,
        )
    except Exception as exc:
        logger.warning("cert renewal notification failed: %s", type(exc).__name__)
    finally:
        db.close()


def _renew_domain(domain_id: int, force: bool = False) -> int:
    db = SessionLocal()
    try:
        dom = db.get(Domain, domain_id)
        if not dom:
            return 0
        provider_key = dom.cert_provider or "none"
        if provider_key == "none":
            return 0
        provider = cert_provider_service.get_provider(provider_key)
        if not provider:
            dom.last_renew_status = "skipped"
            dom.last_renew_error = "不支持的证书维护平台"
            db.commit()
            return 0

        domain_name = dom.domain
        port = dom.port
        old_before = dom.ssl_not_before
        old_after = dom.ssl_not_after
        config = dom.cert_provider_config or {}
        auto_renew = bool(dom.cert_auto_renew)
        last_attempt = dom.last_renew_attempt_at

        if not force:
            if not auto_renew:
                return 0
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            if old_after is not None and old_after > now_utc + timedelta(days=settings.alert_before_days):
                return 0
            now_local = china_now()
            if last_attempt and (dom.last_renew_status or "") == "pending" and now_local - last_attempt > timedelta(minutes=15):
                dom.last_renew_status = "failed"
                dom.last_renew_error = "上次续签未完成（进程中断或超时）"
                db.commit()
            if last_attempt and now_local - last_attempt < timedelta(hours=RENEW_COOLDOWN_HOURS):
                return 0

        try:
            config = provider.validate_config(db, config)
        except ValueError as exc:
            dom.last_renew_status = "skipped"
            dom.last_renew_error = str(exc)[:512]
            db.commit()
            return 0

        dom.last_renew_attempt_at = china_now()
        dom.last_renew_status = "pending"
        dom.last_renew_error = ""
        db.commit()
    finally:
        db.close()

    try:
        renewal = provider.start_renewal(domain_name, config)
        info = _poll_for_new_cert(domain_name, port, old_before, old_after, TLS_POLL_SECONDS)
        if info is None and (renewal.get("index") or renewal.get("ssl_hash")):
            provider.deploy(domain_name, config, renewal)
            info = _poll_for_new_cert(domain_name, port, old_before, old_after, DEPLOY_POLL_SECONDS)

        if info:
            _set_status(domain_id, "success", "", info)
            _notify(domain_id, True, f"新证书到期时间: {info['ssl_not_after']:%Y-%m-%d %H:%M:%S}")
            return 1

        if renewal.get("mode") == "docker":
            message = "Docker/反向代理项目已重新申请，但未观察到新证书；请检查宝塔 Docker 项目是否已重载证书"
        elif renewal.get("direct") and not renewal.get("index") and not renewal.get("ssl_hash"):
            message = "宝塔返回了内联证书但未提供订单/证书 hash，无法自动部署；请检查面板版本或改用订单模式"
        else:
            message = "已触发申请但未观察到新证书（可能等待签发、CDN 代理或多节点未同步）"
        _set_status(domain_id, "failed", message)
        _notify(domain_id, False, message)
        return 0
    except Exception as exc:
        message = _safe_error(exc)
        logger.warning("cert renewal failed for %s: %s", domain_name, message)
        _set_status(domain_id, "failed", message)
        _notify(domain_id, False, message)
        return 0


def renew_domain(domain_id: int) -> int:
    """Manual renewal. Returns 1 when attempted, 0 on failure/skip, -1 when busy."""
    if not _renew_lock.acquire(blocking=False):
        return -1
    try:
        return _renew_domain(domain_id, force=True)
    finally:
        _renew_lock.release()


def auto_renew_domains() -> int:
    """Run automatic renewals. Returns attempted count, or -1 when another run holds the lock."""
    if not _renew_lock.acquire(blocking=False):
        return -1
    try:
        db = SessionLocal()
        try:
            threshold = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                days=settings.alert_before_days
            )
            ids = [
                row[0]
                for row in db.query(Domain.id).filter(
                    Domain.cert_auto_renew.is_(True),
                    Domain.cert_provider.isnot(None),
                    Domain.cert_provider != "none",
                    (Domain.ssl_not_after.is_(None)) | (Domain.ssl_not_after <= threshold),
                ).all()
            ]
        finally:
            db.close()

        total = 0
        for domain_id in ids:
            try:
                total += _renew_domain(domain_id, force=False)
            except Exception as exc:
                logger.warning("cert auto renew failed for domain %s: %s", domain_id, type(exc).__name__)
        return total
    finally:
        _renew_lock.release()
