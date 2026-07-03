import asyncio
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.config import settings

logger = logging.getLogger(__name__)

READ_METHODS = {"GET", "HEAD", "OPTIONS"}
SKIP_PREFIXES = ("/api/health", "/api/v1/audit-logs", "/api/v1/auth/login", "/api/v1/auth/logout")

# Maps the third URL segment (module name) to human-readable Chinese name
_MODULE_LABEL = {
    "hosts": "主机运维",
    "scripts": "脚本管理",
    "credentials": "密钥管理",
    "executions": "执行历史",
    "domains": "域名证书",
    "whois-domains": "域名WHOIS",
    "notifications": "消息通知",
    "network": "网络测试",
    "auth": "认证",
    "users": "用户管理",
}

_ACTION_VERB = {"POST": "新建", "PUT": "更新", "PATCH": "修改", "DELETE": "删除"}

_ACTION_MAP = {
    ("POST", "主机运维"): "新建主机",
    ("PUT", "主机运维"): "更新主机",
    ("DELETE", "主机运维"): "删除主机",
    ("POST", "脚本管理"): "创建脚本",
    ("PUT", "脚本管理"): "更新脚本",
    ("DELETE", "脚本管理"): "删除脚本",
    ("POST", "密钥管理"): "新建密钥",
    ("PUT", "密钥管理"): "更新密钥",
    ("DELETE", "密钥管理"): "删除密钥",
    ("POST", "域名证书"): "添加域名",
    ("DELETE", "域名证书"): "删除域名",
    ("POST", "域名WHOIS"): "添加域名",
    ("DELETE", "域名WHOIS"): "删除域名",
    ("POST", "网络测试"): "TCP 连通性测试",
    ("POST", "认证"): "用户登录",
    ("PUT", "认证"): "修改密码",
}


def _get_client_ip(request: StarletteRequest) -> str:
    source = settings.audit_ip_source
    if source == "direct":
        return _raw_client_ip(request)
    if source == "forwarded":
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        xri = request.headers.get("X-Real-IP")
        if xri:
            return xri.strip()
        return _raw_client_ip(request)
    return request.headers.get(source, _raw_client_ip(request))


def _raw_client_ip(request: StarletteRequest) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def _extract_user_from_auth(request: StarletteRequest) -> dict | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    try:
        from app.services.auth_service import decode_token
        payload = decode_token(token)
        return {
            "user_id": int(payload["sub"]),
            "username": payload.get("username", ""),
        }
    except Exception:
        return None


def _parse_path(path: str) -> tuple[str, str, str]:
    """Parse an API path into (module, resource_type, detail_suffix).

    e.g. /api/v1/hosts/5  ->  (hosts, 主机运维, :id)
    """
    clean = path.split("?")[0].rstrip("/")
    parts = [p for p in clean.split("/") if p]

    if len(parts) < 3 or parts[0] != "api" or parts[1] != "v1":
        return ("", "", "")

    module = parts[2]
    label = _MODULE_LABEL.get(module, module)

    # figure out the resource ID suffix
    sub_parts = parts[3:]
    suffix = ""
    for p in sub_parts:
        if p.isdigit():
            suffix += "/:id"
        else:
            suffix += f"/{p}"

    return (module, label, suffix)


def _build_detail(method: str, module: str, resource_type: str, suffix: str) -> str:
    """Build a human-readable detail message."""
    key = (method, resource_type)

    # Special sub-actions based on suffix
    if suffix == "/execute" and method == "POST":
        return "执行脚本"
    if suffix == "/refresh" and method == "POST":
        return f"刷新{resource_type}"
    if suffix == "/toggle-alert" and method == "PUT":
        return "切换告警"
    if suffix == "/batch-toggle-alert" and method == "POST":
        return "批量切换告警"
    if suffix == "/batch-import" and method == "POST":
        return f"批量导入"

    # Check action map
    if key in _ACTION_MAP:
        return _ACTION_MAP[key]

    # Generic: verb + resource type
    verb = _ACTION_VERB.get(method, method)
    return f"{verb}{resource_type}"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if not settings.audit_enabled:
            return await call_next(request)

        if request.method in READ_METHODS:
            return await call_next(request)

        # Use scope path for consistent behaviour
        scope_path = request.scope.get("path", "")
        if scope_path.startswith(SKIP_PREFIXES):
            return await call_next(request)

        user_info = _extract_user_from_auth(request)
        ip = _get_client_ip(request)
        ua = request.headers.get("User-Agent", "")
        module, resource_type, suffix = _parse_path(scope_path)
        detail = _build_detail(request.method, module, resource_type, suffix)
        resource = _build_resource_str(scope_path)

        response = await call_next(request)

        if user_info:
            asyncio.create_task(
                self._write_audit(
                    user_id=user_info["user_id"],
                    username=user_info["username"],
                    action=request.method,
                    resource=resource,
                    resource_type=resource_type,
                    detail=detail,
                    ip_address=ip,
                    user_agent=ua,
                    status_code=response.status_code,
                )
            )

        return response

    async def _write_audit(self, **kwargs):
        try:
            from app.services.audit_service import create_log_async
            await create_log_async(**kwargs)
        except Exception:
            pass


def _build_resource_str(path: str) -> str:
    parts = [p if not p.isdigit() else ":id" for p in path.split("/")]
    return "/".join(parts)
