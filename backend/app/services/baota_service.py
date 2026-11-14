import hashlib
import json
import logging
import math
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
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise BaotaError("宝塔面板地址不合法")
    return base


def _panel_ctx(panel: BaotaPanel) -> dict:
    return {
        "url": _validate_url(panel.panel_url),
        "encrypted_api_key": panel.encrypted_api_key,
        "verify_tls": True if panel.verify_tls is None else bool(panel.verify_tls),
    }


def _signed_params(ctx: dict, data: dict | None = None) -> dict:
    try:
        api_key = credential_service.decrypt(ctx["encrypted_api_key"])
    except Exception as exc:
        raise BaotaError("无法解密宝塔 API 密钥（请检查 MASTER_KEY 是否变更）") from exc

    request_time = int(time.time())
    payload = dict(data or {})
    payload["request_time"] = str(request_time)
    payload["request_token"] = _sign(api_key, request_time)
    return payload


def _post(ctx: dict, path: str, data: dict, raw: bool = False):
    payload = _signed_params(ctx, data)
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
    if raw:
        if not isinstance(body, (dict, list)):
            raise BaotaError("宝塔面板返回格式不正确")
        return body
    if not isinstance(body, dict):
        raise BaotaError("宝塔面板返回格式不正确")
    return body


def _raise_if_failed(data: dict, action: str) -> None:
    status = data.get("status")
    if status is False or status == 0 or str(status).strip().lower() in ("false", "0"):
        raise BaotaError(_sanitize(data.get("msg") or data.get("error") or f"{action}失败"))


def _normalize_sites(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
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
        raw_id = item.get("id")
        if isinstance(raw_id, bool):
            continue
        if isinstance(raw_id, float) and (not math.isfinite(raw_id) or not raw_id.is_integer()):
            continue
        try:
            site_id = int(raw_id)
        except (TypeError, ValueError, OverflowError):
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
        raise BaotaError("无法读取宝塔站点列表（请检查 API 密钥、IP 白名单、面板版本或面板是否已有站点）")
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

    # 仅按域名精确匹配，避免把 www 域名错误套用到 apex 站点的多域名证书上
    domain = domain_name.strip().lower()
    matches = [s for s in sites if s["name"].lower() == domain]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise BaotaError("未匹配到宝塔站点，请填写站点名（留空时按域名精确匹配）")
    raise BaotaError("匹配到多个宝塔站点，请填写站点名")


def get_orders(ctx: dict) -> list[dict]:
    body = _post(ctx, "/acme", {"action": "get_orders"}, raw=True)
    if isinstance(body, dict):
        _raise_if_failed(body, "读取证书订单")
        for key in ("data", "list", "orders"):
            if isinstance(body.get(key), list):
                body = body[key]
                break
        else:
            return []
    if not isinstance(body, list):
        raise BaotaError("宝塔返回的证书订单格式不正确")

    orders = []
    for item in body:
        if not isinstance(item, dict):
            continue
        index = str(item.get("index") or "").strip()
        if not re.match(r"^[A-Za-z0-9._-]{1,64}$", index):
            continue
        domains = [
            str(name).strip()
            for name in (item.get("domains") or [])
            if isinstance(name, str) and name.strip()
        ]
        if not domains:
            continue
        try:
            cert_timeout = int(item.get("cert_timeout") or 0)
        except (TypeError, ValueError):
            cert_timeout = 0
        orders.append({
            "index": index,
            "domains": domains,
            "status": str(item.get("status") or ""),
            "cert_timeout": cert_timeout,
            "auth_type": str(item.get("auth_type") or ""),
        })
    return orders


def _order_matches(order: dict, domain_name: str) -> bool:
    names = {str(name).lower() for name in order.get("domains") or []}
    domain = domain_name.strip().lower()
    return (
        domain in names
        or (domain.startswith("www.") and domain[4:] in names)
        or f"www.{domain}" in names
    )


def _select_order(orders: list[dict], domain_name: str, order_index: str = "") -> dict | None:
    if order_index:
        for order in orders:
            if order["index"] == order_index:
                return order
        raise BaotaError("指定的 ACME 订单不存在")
    matches = [order for order in orders if _order_matches(order, domain_name)]
    if not matches:
        return None
    valid = [order for order in matches if order.get("status") == "valid"]
    return max(valid or matches, key=lambda order: int(order.get("cert_timeout") or 0))


def get_panel(db: Session, panel_id: int) -> BaotaPanel:
    panel = db.get(BaotaPanel, panel_id)
    if not panel:
        raise BaotaError("宝塔面板不存在")
    if not panel.enabled:
        raise BaotaError("宝塔面板已禁用")
    return panel


def _normalize_docker_sites(body) -> list[dict]:
    if not isinstance(body, dict):
        raise BaotaError("宝塔返回的 Docker 站点列表格式不正确")
    _raise_if_failed(body, "读取 Docker 站点列表")
    data = body.get("data")
    if isinstance(data, dict):
        for key in ("list", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            raise BaotaError("宝塔返回的 Docker 站点列表格式不正确")
    if not isinstance(data, list):
        raise BaotaError("宝塔返回的 Docker 站点列表格式不正确")

    sites = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        if isinstance(raw_id, bool):
            continue
        if isinstance(raw_id, float) and (not math.isfinite(raw_id) or not raw_id.is_integer()):
            continue
        try:
            site_id = int(raw_id)
        except (TypeError, ValueError, OverflowError):
            continue
        if site_id <= 0:
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        site_type = str(item.get("type") or "").strip()
        project_name = ""
        service_info = item.get("service_info")
        if isinstance(service_info, str):
            try:
                service_info = json.loads(service_info)
            except ValueError:
                service_info = {}
        if isinstance(service_info, dict):
            project_name = str(service_info.get("project_name") or "").strip()
        sites.append({
            "id": site_id,
            "name": name[:256],
            "type": site_type[:32],
            "project_name": project_name[:128],
        })
    sites.sort(key=lambda site: (site["name"].lower(), site["id"]))
    return sites


def list_docker_sites(db: Session, panel_id: int) -> list[dict]:
    # shortcut: 宝塔 Docker 站点接口随版本可能变化，失败时前端保留手工填写站点 ID
    ctx = _panel_ctx(get_panel(db, panel_id))
    body = _post(ctx, "/mod/docker/com/get_site_list", {
        "type": "all",
        "p": 1,
        "row": SITE_LIMIT,
        "query": "",
        # 不要传 classify：面板默认值是整数 999，传入字符串会按 classify="999" 过滤
    })
    return _normalize_docker_sites(body)


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
    if len(site_name) > 256:
        raise ValueError("站点名过长")

    mode = str(config.get("mode") or "auto").strip().lower()
    if mode not in ("auto", "docker"):
        raise ValueError("续签方式不正确")

    docker_id = config.get("docker_id")
    if docker_id in (None, ""):
        docker_id = None
    else:
        if isinstance(docker_id, bool) or (
            isinstance(docker_id, float)
            and (not math.isfinite(docker_id) or not docker_id.is_integer())
        ):
            raise ValueError("Docker 站点 ID 必须是整数")
        try:
            docker_id = int(docker_id)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Docker 站点 ID 必须是数字")
        if docker_id <= 0:
            raise ValueError("Docker 站点 ID 不正确")
    if mode == "docker" and not docker_id:
        raise ValueError("Docker 模式需要选择或填写 Docker 站点 ID")

    order_index = str(config.get("order_index") or "").strip()
    if order_index and not re.match(r"^[A-Za-z0-9._-]{1,64}$", order_index):
        raise ValueError("ACME 订单 ID 格式不正确")

    site_id = config.get("site_id")
    if site_id in (None, ""):
        site_id = None
    else:
        if isinstance(site_id, bool) or (
            isinstance(site_id, float)
            and (not math.isfinite(site_id) or not site_id.is_integer())
        ):
            raise ValueError("站点 ID 必须是整数")
        try:
            site_id = int(site_id)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("站点 ID 必须是数字")
        if site_id <= 0:
            raise ValueError("站点 ID 不正确")

    site_path = str(config.get("site_path") or "").strip()
    if site_path:
        if not site_path.startswith("/"):
            raise ValueError("站点根目录必须以 / 开头")
        if len(site_path) > 512:
            raise ValueError("站点根目录过长")

    return {
        "panel_id": panel_id,
        "site_name": site_name,
        "mode": mode,
        "docker_id": docker_id,
        "order_index": order_index,
        "site_id": site_id,
        "site_path": site_path,
    }


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


def test_panel(db: Session, panel_id: int) -> dict:
    panel = get_panel(db, panel_id)
    ctx = _panel_ctx(panel)

    orders = []
    try:
        orders = get_orders(ctx)
    except BaotaError:
        pass
    sites = []
    try:
        sites = list_sites(ctx)
    except BaotaError:
        pass
    if not orders and not sites:
        raise BaotaError("无法读取宝塔证书订单或站点列表（请检查 API 密钥、IP 白名单、面板版本）")
    return {
        "orders": orders,
        "sites": [{"id": site["id"], "name": site["name"]} for site in sites],
    }


def start_renewal(domain_name: str, config: dict) -> dict:
    try:
        panel_id = int(config.get("panel_id"))
    except (TypeError, ValueError):
        raise BaotaError("宝塔面板配置不完整")

    db = SessionLocal()
    try:
        ctx = _panel_ctx(get_panel(db, panel_id))
        docker_sites = None
        if config.get("mode") == "docker":
            try:
                docker_sites = list_docker_sites(db, panel_id)
            except BaotaError:
                # 站点列表接口不可用时保留手工配置，避免阻断续签
                docker_sites = None
    finally:
        db.close()

    if config.get("mode") == "docker":
        # docker_id 是宝塔 docker_sites.id（Docker 站点 ID），不是 Compose 项目 ID
        docker_id = int(config["docker_id"])
        site_name = (config.get("site_name") or "").strip() or domain_name
        if docker_sites is not None:
            site = next((item for item in docker_sites if item["id"] == docker_id), None)
            if not site:
                raise BaotaError("已保存的 Docker 站点 ID 不在面板站点列表中，请重新选择站点")
            if site_name.lower() != site["name"].lower():
                raise BaotaError("Docker 站点名与站点 ID 不匹配，请重新选择站点")
        data = _post(ctx, "/mod/docker/com/apply_cert_api", {
            "domains": json.dumps([domain_name]),
            "auth_type": "http",
            "auth_to": json.dumps([site_name]),
            "auto_wildcard": "0",
            "id": docker_id,
            "ca": "letsencrypt",
            "cert_algorithm": "rsa4096",
            "site_name": site_name,
        })
        if not isinstance(data, dict):
            raise BaotaError("宝塔 Docker 证书接口返回格式不正确")
        _raise_if_failed(data, "重新申请证书")
        return {
            "site_name": site_name,
            "index": "",
            "ssl_hash": "",
            "direct": bool(data.get("cert") or data.get("private_key")),
            "mode": "docker",
        }

    order_index = config.get("order_index", "")
    if order_index:
        orders = get_orders(ctx)
    else:
        try:
            orders = get_orders(ctx)
        except BaotaError:
            orders = []
    order = _select_order(orders, domain_name, order_index)
    if order:
        index = order["index"]
        renew = _post(ctx, "/acme", {"action": "renew_cert", "index": index})
        if not isinstance(renew, dict):
            raise BaotaError("宝塔续签返回格式不正确")
        _raise_if_failed(renew, "续签证书")
        site_name = (config.get("site_name") or "").strip() or order["domains"][0]
        return {
            "site_name": site_name,
            "index": index,
            "ssl_hash": "",
            "direct": bool(renew.get("cert")),
            "mode": "order",
        }

    site_id = config.get("site_id")
    site_path = config.get("site_path")
    if site_id and site_path:
        site = {
            "id": int(site_id),
            "name": (config.get("site_name") or "").strip() or domain_name,
            "path": site_path,
        }
    else:
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
    if not isinstance(data, dict):
        raise BaotaError("宝塔申请证书返回格式不正确")
    _raise_if_failed(data, "申请证书")
    index = data.get("index")
    direct = bool(data.get("cert") or data.get("private_key"))
    ssl_hash = data.get("ssl_hash") or data.get("hash")
    if index is None and not direct:
        raise BaotaError(_sanitize(data.get("msg") or "宝塔未返回订单索引"))
    return {
        "site_name": site["name"],
        "index": str(index) if index is not None else "",
        "ssl_hash": str(ssl_hash) if ssl_hash else "",
        "direct": direct,
        "mode": "apply",
    }


def deploy_order(domain_name: str, config: dict, renewal: dict) -> None:
    if not renewal.get("index") and not renewal.get("ssl_hash"):
        return
    db = SessionLocal()
    try:
        ctx = _panel_ctx(get_panel(db, int(config.get("panel_id"))))
    finally:
        db.close()

    if renewal.get("ssl_hash") and not renewal.get("index"):
        data = _post(ctx, "/ssl", {
            "action": "SetCertToSite",
            "ssl_hash": renewal["ssl_hash"],
            "siteName": renewal["site_name"],
        })
    else:
        data = _post(ctx, "/acme", {
            "action": "SetCertToSite",
            "index": renewal["index"],
            "siteName": renewal["site_name"],
        })
    _raise_if_failed(data, "部署证书")
