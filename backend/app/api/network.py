from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.network import NetworkTestRequest, NetworkTestResponse
from app.services import network_service

router = APIRouter(prefix="/network", tags=["network"])


@router.post("/test", response_model=NetworkTestResponse)
def test_connectivity(
    body: NetworkTestRequest,
    _user: dict = Depends(get_current_user),
):
    return network_service.test_tcp(body.host, body.port, body.timeout)
