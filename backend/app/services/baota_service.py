import hashlib
import json
import logging
import re
import time
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.baota_panel import BaotaPanel
from app.models.domain import Domain
from app.services import credential_service

logger = logging.getLogger(__name__)

BAOTA_TIMEOUT = 90
SITE_LIMIT = 10000
_PEM_RE = re.compile(r"-----BEGIN.*?-----END[^-]*-----", re.S)
_SECRET_FIELD_RE = re.compile(
    r'(?i)("?(?:private[_-]?key|cert(?:ificate)?)"?\s*[:=]\s*)("[^"]*"|[^\s,}]+)'
)


class BaotaError(Exception):
    pass


def _sign(api_key: str, request_time: int) -> str:
    return hashlib.md5(
        f"{request_time}{hashlib.md5(api_key.encode()).hexdigest()}".encode()
    ).hexdigest()


def _sanitize(value) -> str:
    text = _PEM_RE.sub("[redacted]", str(value or ""))
    text = _SECRET_FIELD_RE.sub(r"\1[redacted]", text)
    return text.strip()[:200]


def _validate_url(value: str) -> str:
    base = (value or "").strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise BaotaError("宝塔面板地址不合法")
    return base


def _panel_ctx(panel: BaotaPanel) -> dict:
    return {
        "url": _validate_url(panel.panel_url),
        "encrypted_api_key": panel.encrypted_api_key,
        "verify_tls": True if panel.verify_tls is None else bool(panel.verify_tls),
    }


def _post(ctx: dict, path: str, data: dict) -> dict:
    try:
        api_key = credential_service.decrypt(ctx["encrypted_api_key"])
    except Exception as exc:
        raise BaotaError("无法解密宝塔 API 密钥（请检查 MASTER_KEY 是否变更）") from exc

    request_time = int(time.time())
    payload = dict(data)
    payload["request_time"] = str(request_time)
    payload["request_token"] = _sign(api_key, request_time)

    try:
        resp = httpx.post(
            f"{ctx['url']}{path}",
            data=payload,
            timeout=BAOTA_TIMEOUT,
            verify=ctx["verify_tls"],
            follow_redirects=False,
        )
    except httpx.RequestError as exc:
        raise BaotaError(f"无法连接宝塔面板: {type(exc).__name__}") from exc

    if resp.status_code in (301, 302, 303, 307, 308):
        raise BaotaError("宝塔面板返回重定向，请检查面板地址/HTTPS 配置")
    if resp.status_code >= 400:
        raise BaotaError(f"宝塔面板返回 HTTP {resp.status_code}")

    try:
        body = resp.json()
    except ValueError as exc:
        raise BaotaError(f"宝塔面板返回非 JSON 响应 (HTTP {resp.status_code})") from exc
    if not isinstance(body, dict):
        raise BaotaError("宝塔面板返回格式不正确")
    return body


def _raise_if_failed(data: dict, action: str) -> None:
    status = data.get("status")
    if status is False or status == 0 or str(status).strip().lower() in ("false", "0"):
        raise BaotaError(_sanitize(data.get("msg") or data.get("error") or f"{action}失败"))


def _normalize_sites(payload: dict) -> list[dict]:
    raw = payload.get("sites")
    if not isinstance(raw, list):
        raw = payload.get("data")
        if isinstance(raw, dict):
            raw = raw.get("data")
    if not isinstance(raw, list):
        return []

    sites = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            site_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        name = str(item.get("name") or item.get("site_name") or "").strip()
        path = str(item.get("path") or item.get("site_path") or "").strip()
        if site_id > 0 and name and path:
            sites.append({"id": site_id, "name": name, "path": path})
    return sites


def list_sites(ctx: dict) -> list[dict]:
    try:
        data = _post(ctx, "/site", {"action": "GetSiteList", "limit": SITE_LIMIT, "p": 1})
        sites = _normalize_sites(data)
        if sites:
            return sites
    except BaotaError:
        pass

    data = _post(ctx, "/data", {"action": "getData", "table": "sites", "limit": SITE_LIMIT, "p": 1})
    sites = _normalize_sites(data)
    if not sites:
        raise BaotaError("无法读取宝塔站点列表（请检查面板版本/API 权限）")
    return sites


def _resolve_site(sites: list[dict], site_name: str, domain_name: str) -> dict:
    site_name = (site_name or "").strip()
    if site_name:
        matches = [s for s in sites if s["name"].lower() == site_name.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise BaotaError(f"未找到宝塔站点: {site_name}")
        raise BaotaError(f"宝塔站点名不唯一: {site_name}")

    domain = domain_name.lower()
    candidates = {domain}
    if domain.startswith("www."):
        candidates.add(domain[4:])
    else:
        candidates.add(f"www.{domain}")
    matches = [s for s in sites if s["name"].lower() in candidates]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise BaotaError("未匹配到宝塔站点，请填写站点名")
    raise BaotaError("匹配到多个宝塔站点，请填写站点名")


def get_panel(db: Session, panel_id: int) -> BaotaPanel:
    panel = db.get(BaotaPanel, panel_id)
    if not panel:
        raise BaotaError("宝塔面板不存在")
    if not panel.enabled:
        raise BaotaError("宝塔面板已禁用")
    return panel


def validate_domain_config(db: Session, config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("宝塔配置格式不正确")
    try:
        panel_id = int(config.get("panel_id"))
    except (TypeError, ValueError):
        raise ValueError("请选择宝塔面板")
    panel = db.get(BaotaPanel, panel_id)
    if not panel:
        raise ValueError("宝塔面板不存在")
    if not panel.enabled:
        raise ValueError("宝塔面板已禁用")
    site_name = str(config.get("site_name") or "").strip()
    if len(site_name) > 128:
        raise ValueError("站点名过长")
    return {"panel_id": panel_id, "site_name": site_name}


def create_panel(db: Session, data) -> BaotaPanel:
    panel = BaotaPanel(
        name=data.name,
        panel_url=data.panel_url,
        encrypted_api_key=credential_service.encrypt(data.api_key),
        verify_tls=data.verify_tls,
        enabled=data.enabled,
    )
    db.add(panel)
    db.commit()
    db.refresh(panel)
    return panel


def update_panel(db: Session, panel: BaotaPanel, data) -> BaotaPanel:
    if data.name is not None:
        panel.name = data.name
    if data.panel_url is not None:
        panel.panel_url = data.panel_url
    if data.api_key is not None and data.api_key.strip():
        panel.encrypted_api_key = credential_service.encrypt(data.api_key.strip())
    if data.verify_tls is not None:
        panel.verify_tls = data.verify_tls
    if data.enabled is not None:
        panel.enabled = data.enabled
    db.commit()
    db.refresh(panel)
    return panel


def panel_in_use(db: Session, panel_id: int) -> bool:
    rows = db.query(Domain).filter(Domain.cert_provider == "baota").all()
    for row in rows:
        config = row.cert_provider_config or {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except ValueError:
                continue
        if not isinstance(config, dict):
            continue
        try:
            if int(config.get("panel_id")) == panel_id:
                return True
        except (TypeError, ValueError):
            continue
    return False


def test_panel(db: Session, panel_id: int) -> list[dict]:
    panel = get_panel(db, panel_id)
    sites = list_sites(_panel_ctx(panel))
    return [{"id": site["id"], "name": site["name"]} for site in sites]


def start_renewal(domain_name: str, config: dict) -> dict:
    try:
        panel_id = int(config.get("panel_id"))
    except (TypeError, ValueError):
        raise BaotaError("宝塔面板配置不完整")

    db = SessionLocal()
    try:
        ctx = _panel_ctx(get_panel(db, panel_id))
    finally:
        db.close()

    sites = list_sites(ctx)
    site = _resolve_site(sites, config.get("site_name", ""), domain_name)
    data = _post(ctx, "/acme", {
        "action": "apply_cert_api",
        "id": site["id"],
        "domains": json.dumps([domain_name]),
        "auth_type": "http",
        "auth_to": site["path"],
        "auto_wildcard": "0",
    })
    _raise_if_failed(data, "申请证书")
    index = data.get("index")
    direct = bool(data.get("cert") or data.get("private_key"))
    if index is None and not direct:
        raise BaotaError(_sanitize(data.get("msg") or "宝塔未返回订单索引"))
    return {
        "site_name": site["name"],
        "index": str(index) if index is not None else "",
        "direct": direct,
    }


def deploy_order(domain_name: str, config: dict, renewal: dict) -> None:
    if not renewal.get("index"):
        return
    db = SessionLocal()
    try:
        ctx = _panel_ctx(get_panel(db, int(config.get("panel_id"))))
    finally:
        db.close()
    data = _post(ctx, "/acme", {
        "action": "SetCertToSite",
        "index": renewal["index"],
        "siteName": renewal["site_name"],
    })
    _raise_if_failed(data, "部署证书")
