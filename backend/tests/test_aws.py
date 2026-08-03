"""API-layer tests for /api/v1/aws endpoints."""

import json
import pytest
from unittest import mock

from app.services import credential_service
from app.services.aws_service import AwsError


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def aws_credential_id(db_session):
    """Create a real AWS-type credential in the test DB so the API can resolve it."""
    payload = {
        "access_key_id": "AKIATEST123",
        "secret_access_key": "secret123456789",
        "region": "ap-southeast-1",
    }
    encrypted = credential_service.encrypt(json.dumps(payload))
    from app.models.credential import Credential
    cred = Credential(
        name="test-aws",
        key="AWS_ACCOUNT",
        encrypted_value=encrypted,
        type="aws",
    )
    db_session.add(cred)
    db_session.commit()
    db_session.refresh(cred)
    return cred.id


# ---------------------------------------------------------------------------
# GET /aws/ec2/regions
# ---------------------------------------------------------------------------

class TestGetRegions:
    def test_returns_regions_list(self, client, auth_headers):
        resp = client.get("/api/v1/aws/ec2/regions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "regions" in data
        assert isinstance(data["regions"], list)
        assert "ap-southeast-1" in data["regions"]

    def test_unauthorized(self, client):
        resp = client.get("/api/v1/aws/ec2/regions")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /aws/ec2/instances
# ---------------------------------------------------------------------------

class TestListInstances:
    def test_list_instances(self, client, auth_headers, aws_credential_id):
        with mock.patch("app.api.aws.list_ec2_instances") as mock_list:
            mock_list.return_value = [
                {
                    "instance_id": "i-abc123",
                    "name": "web-server",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "private_ip": "10.0.0.1",
                    "public_ip": "54.1.2.3",
                    "launch_time": "2025-01-01T00:00:00",
                    "availability_zone": "ap-southeast-1a",
                    "tags": {"Name": "web-server"},
                }
            ]
            resp = client.get(
                f"/api/v1/aws/ec2/instances?credential_id={aws_credential_id}&region=ap-southeast-1",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["instance_id"] == "i-abc123"

    def test_list_instances_missing_params(self, client, auth_headers):
        resp = client.get("/api/v1/aws/ec2/instances", headers=auth_headers)
        assert resp.status_code == 422  # FastAPI validation error

    def test_list_instances_service_error(self, client, auth_headers, aws_credential_id):
        with mock.patch("app.api.aws.list_ec2_instances") as mock_list:
            mock_list.side_effect = AwsError("EC2 DescribeInstances 失败: auth error")
            resp = client.get(
                f"/api/v1/aws/ec2/instances?credential_id={aws_credential_id}&region=ap-southeast-1",
                headers=auth_headers,
            )
            assert resp.status_code == 400
            assert "auth error" in resp.json()["detail"]

    def test_unauthorized(self, client):
        resp = client.get("/api/v1/aws/ec2/instances?credential_id=1&region=ap-southeast-1")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /aws/ec2/instances/{instance_id}
# ---------------------------------------------------------------------------

class TestInstanceDetail:
    def test_instance_detail(self, client, auth_headers, aws_credential_id):
        with mock.patch("app.api.aws.get_ec2_instance") as mock_get:
            mock_get.return_value = {
                "instance_id": "i-xyz",
                "name": "db-server",
                "instance_type": "t3.large",
                "state": "running",
                "private_ip": "10.0.1.1",
                "public_ip": "",
                "launch_time": "2025-01-01T00:00:00",
                "availability_zone": "ap-southeast-1b",
                "tags": {"Role": "db"},
                "security_groups": [{"id": "sg-123", "name": "default"}],
                "volumes": [{"id": "vol-456", "device": "/dev/xvda", "size_gb": 30}],
                "vpc_id": "vpc-xxx",
                "subnet_id": "subnet-yyy",
            }
            resp = client.get(
                f"/api/v1/aws/ec2/instances/i-xyz?credential_id={aws_credential_id}&region=ap-southeast-1",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["vpc_id"] == "vpc-xxx"
            assert len(data["security_groups"]) == 1

    def test_not_found(self, client, auth_headers, aws_credential_id):
        with mock.patch("app.api.aws.get_ec2_instance") as mock_get:
            mock_get.side_effect = AwsError("实例 i-xxx 在 ap-southeast-1 中未找到")
            resp = client.get(
                f"/api/v1/aws/ec2/instances/i-xxx?credential_id={aws_credential_id}&region=ap-southeast-1",
                headers=auth_headers,
            )
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /aws/ec2/instances/{instance_id}/action
# ---------------------------------------------------------------------------

class TestInstanceAction:
    def test_start_action(self, client, auth_headers, aws_credential_id):
        with mock.patch("app.api.aws.ec2_instance_action") as mock_action:
            mock_action.return_value = {
                "instance_id": "i-abc",
                "action": "start",
                "new_state": "running",
            }
            resp = client.post(
                "/api/v1/aws/ec2/instances/i-abc/action",
                json={
                    "credential_id": aws_credential_id,
                    "region": "ap-southeast-1",
                    "action": "start",
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["new_state"] == "running"

    def test_invalid_action(self, client, auth_headers, aws_credential_id):
        resp = client.post(
            "/api/v1/aws/ec2/instances/i-abc/action",
            json={
                "credential_id": aws_credential_id,
                "region": "ap-southeast-1",
                "action": "terminate",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_unauthorized(self, client, aws_credential_id):
        resp = client.post(
            "/api/v1/aws/ec2/instances/i-abc/action",
            json={"credential_id": aws_credential_id, "region": "ap-southeast-1", "action": "start"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /aws/credentials/validate
# ---------------------------------------------------------------------------

class TestValidateAwsCredential:
    def test_validate_success(self, client, auth_headers):
        with mock.patch("app.api.aws.validate_aws_credentials") as mock_val:
            mock_val.return_value = {
                "account_id": "123456789012",
                "arn": "arn:aws:iam::123456789012:user/test",
                "user_id": "AIDATEST",
            }
            payload = json.dumps({
                "access_key_id": "AKIATEST",
                "secret_access_key": "secret",
                "region": "us-east-1",
            })
            resp = client.post(
                "/api/v1/aws/credentials/validate",
                json={"value": payload},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["account_id"] == "123456789012"

    def test_validate_invalid_json(self, client, auth_headers):
        resp = client.post(
            "/api/v1/aws/credentials/validate",
            json={"value": "not json"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "JSON" in resp.json()["detail"]

    def test_validate_unauthorized(self, client):
        resp = client.post("/api/v1/aws/credentials/validate", json={"value": "{}"})
        assert resp.status_code == 403
