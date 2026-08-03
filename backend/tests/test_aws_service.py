"""Unit tests for aws_service — all boto3 calls are mocked."""

import json
import pytest
from unittest import mock

from app.config import settings
from app.services import credential_service
from app.services.aws_service import (
    AwsError,
    _decrypt_aws_data,
    validate_aws_credentials,
    list_ec2_instances,
    ec2_instance_action,
    list_aws_regions,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_aws_cred(name="test-aws", region="ap-southeast-1"):
    """Encrypt an AWS credential JSON and return a mock Credential."""
    payload = {
        "access_key_id": "AKIATEST123",
        "secret_access_key": "secret123456789",
        "region": region,
    }
    encrypted = credential_service.encrypt(json.dumps(payload))
    cred = mock.MagicMock()
    cred.id = 1
    cred.type = "aws"
    cred.encrypted_value = encrypted
    return cred, payload


# ---------------------------------------------------------------------------
# _decrypt_aws_data
# ---------------------------------------------------------------------------

class TestDecryptAwsData:
    def test_decrypt_valid_aws_credential(self):
        cred, payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        result = _decrypt_aws_data(db, 1)
        assert result["access_key_id"] == payload["access_key_id"]
        assert result["secret_access_key"] == payload["secret_access_key"]

    def test_decrypt_not_found(self):
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(AwsError, match="不存在"):
            _decrypt_aws_data(db, 999)

    def test_decrypt_wrong_type(self):
        cred = mock.MagicMock()
        cred.type = "generic"
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred
        with pytest.raises(AwsError, match="不是 AWS 类型"):
            _decrypt_aws_data(db, 1)


# ---------------------------------------------------------------------------
# validate_aws_credentials
# ---------------------------------------------------------------------------

class TestValidateAwsCredentials:
    def test_valid_credentials(self):
        """Successful sts:GetCallerIdentity returns identity metadata."""
        data = {
            "access_key_id": "AKIATEST",
            "secret_access_key": "secret",
            "region": "us-east-1",
        }
        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_sts = mock.MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
                "UserId": "AIDATEST",
            }
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_sts
            MockSession.return_value = mock_session

            result = validate_aws_credentials(data)
            assert result["account_id"] == "123456789012"
            assert result["arn"].startswith("arn:aws:iam::")

    def test_missing_access_key(self):
        with pytest.raises(AwsError, match="缺少必需字段"):
            validate_aws_credentials({"secret_access_key": "x"})

    def test_invalid_credentials(self):
        data = {
            "access_key_id": "AKIAINVALID",
            "secret_access_key": "bad",
        }
        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_sts = mock.MagicMock()
            from botocore.exceptions import ClientError
            mock_sts.get_caller_identity.side_effect = ClientError(
                {"Error": {"Code": "InvalidClientTokenId", "Message": "bad"}}, "GetCallerIdentity"
            )
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_sts
            MockSession.return_value = mock_session

            with pytest.raises(AwsError, match="凭据验证失败"):
                validate_aws_credentials(data)


# ---------------------------------------------------------------------------
# list_ec2_instances
# ---------------------------------------------------------------------------

class TestListEc2Instances:
    def test_returns_parsed_instances(self):
        cred, _payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        raw_inst = {
            "InstanceId": "i-abc123",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "PrivateIpAddress": "10.0.0.1",
            "PublicIpAddress": "54.1.2.3",
            "LaunchTime": mock.MagicMock(),
            "Placement": {"AvailabilityZone": "ap-southeast-1a"},
            "Tags": [{"Key": "Name", "Value": "web-server"}],
        }
        raw_inst["LaunchTime"].isoformat.return_value = "2025-01-01T00:00:00"

        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_ec2 = mock.MagicMock()
            mock_paginator = mock.MagicMock()
            mock_paginator.paginate.return_value = [{"Reservations": [{"Instances": [raw_inst]}]}]
            mock_ec2.get_paginator.return_value = mock_paginator
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_ec2
            MockSession.return_value = mock_session

            result = list_ec2_instances(db, 1, "ap-southeast-1")
            assert len(result) == 1
            assert result[0]["instance_id"] == "i-abc123"
            assert result[0]["name"] == "web-server"
            assert result[0]["state"] == "running"

    def test_empty_result(self):
        cred, _payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_ec2 = mock.MagicMock()
            mock_paginator = mock.MagicMock()
            mock_paginator.paginate.return_value = [{"Reservations": []}]
            mock_ec2.get_paginator.return_value = mock_paginator
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_ec2
            MockSession.return_value = mock_session

            result = list_ec2_instances(db, 1, "us-east-1")
            assert result == []


# ---------------------------------------------------------------------------
# ec2_instance_action
# ---------------------------------------------------------------------------

class TestEc2InstanceAction:
    def test_start_instance(self):
        cred, _payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_ec2 = mock.MagicMock()
            # start_instances → no return
            mock_ec2.start_instances.return_value = {}
            # subsequent describe for new state
            mock_paginator = mock.MagicMock()
            mock_paginator.paginate.return_value = [
                {"Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]}
            ]
            mock_ec2.get_paginator.return_value = mock_paginator
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_ec2
            MockSession.return_value = mock_session

            result = ec2_instance_action(db, 1, "ap-southeast-1", "i-abc", "start")
            assert result["action"] == "start"
            assert result["new_state"] == "running"

    def test_stop_instance(self):
        cred, _payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        with mock.patch("app.services.aws_service.boto3.Session") as MockSession:
            mock_ec2 = mock.MagicMock()
            mock_ec2.stop_instances.return_value = {}
            mock_paginator = mock.MagicMock()
            mock_paginator.paginate.return_value = [
                {"Reservations": [{"Instances": [{"State": {"Name": "stopped"}}]}]}
            ]
            mock_ec2.get_paginator.return_value = mock_paginator
            mock_session = mock.MagicMock()
            mock_session.client.return_value = mock_ec2
            MockSession.return_value = mock_session

            result = ec2_instance_action(db, 1, "ap-southeast-1", "i-abc", "stop")
            assert result["new_state"] == "stopped"

    def test_invalid_action(self):
        cred, _payload = _make_aws_cred()
        db = mock.MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cred

        with pytest.raises(AwsError, match="无效操作"):
            ec2_instance_action(db, 1, "ap-southeast-1", "i-abc", "delete")


# ---------------------------------------------------------------------------
# list_aws_regions
# ---------------------------------------------------------------------------

class TestListAwsRegions:
    def test_returns_list(self):
        regions = list_aws_regions()
        assert isinstance(regions, list)
        assert "ap-southeast-1" in regions
