from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_user
from app.schemas.baota import CertProviderItem
from app.services import cert_provider_service

router = APIRouter(prefix="/cert-providers", tags=["cert-providers"])


@router.get("", response_model=list[CertProviderItem])
def list_providers(_user: dict = Depends(get_current_user)):
    return cert_provider_service.list_providers()
