"""AWS API routes — EC2 instance management and credential validation."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.aws import (
    Ec2ActionRequest,
    Ec2ActionResponse,
    Ec2InstanceResponse,
    Ec2InstanceDetailResponse,
    ValidateAwsRequest,
    ValidateAwsResponse,
)
from app.services.aws_service import (
    AwsError,
    list_aws_regions,
    list_ec2_instances,
    get_ec2_instance,
    ec2_instance_action,
    validate_aws_credentials,
)
from app.services import credential_service

import json

router = APIRouter(prefix="/aws", tags=["aws"])


# -- Regions ----------------------------------------------------------------

@router.get("/ec2/regions")
def get_regions(_user: dict = Depends(get_current_user)):
    """Return the configured AWS region list (from settings)."""
    return {"regions": list_aws_regions()}


# -- EC2 instances ----------------------------------------------------------

@router.get("/ec2/instances", response_model=list[Ec2InstanceResponse])
def list_instances(
    credential_id: int = Query(..., description="AWS 凭证 ID"),
    region: str = Query(..., description="AWS 区域，如 ap-southeast-1"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """List EC2 instances for a credential + region."""
    try:
        return list_ec2_instances(db, credential_id, region)
    except AwsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/ec2/instances/{instance_id}", response_model=Ec2InstanceDetailResponse)
def instance_detail(
    instance_id: str,
    credential_id: int = Query(..., description="AWS 凭证 ID"),
    region: str = Query(..., description="AWS 区域"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Return detailed information for a single EC2 instance."""
    try:
        return get_ec2_instance(db, credential_id, region, instance_id)
    except AwsError as exc:
        code = status.HTTP_404_NOT_FOUND if "未找到" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/ec2/instances/{instance_id}/action", response_model=Ec2ActionResponse)
def instance_action(
    instance_id: str,
    body: Ec2ActionRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Start / stop / reboot an EC2 instance."""
    try:
        return ec2_instance_action(db, body.credential_id, body.region, instance_id, body.action)
    except AwsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# -- Credential validation (called from the credentials page) ---------------

@router.post("/credentials/validate", response_model=ValidateAwsResponse)
def validate_credential(
    body: ValidateAwsRequest,
    _user: dict = Depends(get_current_user),
):
    """Validate AWS credentials by calling sts:GetCallerIdentity."""
    try:
        data = json.loads(body.value)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AWS 凭证 JSON 格式无效")
    try:
        return validate_aws_credentials(data)
    except AwsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
