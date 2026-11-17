from fastapi import APIRouter, Depends, Response

from app.config import settings
from app.middleware.auth_middleware import get_current_admin_user, get_current_user
from app.schemas.system import TracingInfo, VersionInfo

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/version", response_model=VersionInfo)
def get_version(
    response: Response,
    _admin: dict = Depends(get_current_admin_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"
    return VersionInfo(version=settings.app_version)


@router.get("/tracing", response_model=TracingInfo)
def get_tracing_info(
    response: Response,
    _user: dict = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    return TracingInfo(
        enabled=settings.tracing_enabled,
        ui_url=settings.tracing_ui_url,
    )
