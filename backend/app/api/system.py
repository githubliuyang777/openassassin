from fastapi import APIRouter, Depends, Response

from app.config import settings
from app.middleware.auth_middleware import get_current_admin_user
from app.schemas.system import VersionInfo

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
