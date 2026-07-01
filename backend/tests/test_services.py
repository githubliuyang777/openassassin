import os
import time
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-jwt-secret-key-32-chars!!"
os.environ["MASTER_KEY"] = "test-master-key-needs-32-byte!"

from app.services.auth_service import hash_password, verify_password, create_token, decode_token, authenticate
from app.services.credential_service import encrypt, decrypt
from app.services.sandbox_service import _mask_secrets


class TestAuthService:
    def test_hash_and_verify(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed)
        assert not verify_password("wrong", hashed)

    def test_create_and_decode_token(self):
        token = create_token(42, "alice", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_authenticate_success(self, db_session, admin_user):
        from app.models.user import User
        user = authenticate(db_session, "admin", "admin")
        assert user is not None
        assert user.username == "admin"

    def test_authenticate_wrong_password(self, db_session, admin_user):
        assert authenticate(db_session, "admin", "wrong") is None

    def test_authenticate_nonexistent(self, db_session, admin_user):
        assert authenticate(db_session, "ghost", "x") is None


class TestCredentialService:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-secret-value-12345"
        ciphertext = encrypt(plaintext)
        assert ":" in ciphertext
        assert decrypt(ciphertext) == plaintext

    def test_encrypt_produces_different_ciphertexts(self):
        c1 = encrypt("same-value")
        c2 = encrypt("same-value")
        assert c1 != c2  # nonce ensures uniqueness
        assert decrypt(c1) == decrypt(c2) == "same-value"

    def test_encrypt_empty_string(self):
        ct = encrypt("")
        assert decrypt(ct) == ""

    def test_encrypt_unicode(self):
        original = "密钥值🔑"
        ct = encrypt(original)
        assert decrypt(ct) == original


class TestSandboxMaskSecrets:
    def test_masks_secrets_in_lines(self):
        lines = ["export TOKEN=abc123", "TOKEN=abc123 found"]
        masked = [_mask_secrets(l, ["abc123"]) for l in lines]
        assert "abc123" not in masked[0]
        assert "***" in masked[0]
        assert "abc123" not in masked[1]

    def test_no_mask_when_secret_empty(self):
        assert _mask_secrets("hello", []) == "hello"
        assert _mask_secrets("hello", [""]) == "hello"

    def test_handles_empty_strings(self):
        assert _mask_secrets("", ["x"]) == ""


class TestSandboxServiceMocks:
    def test_execute_sandbox_error_returns_failed(self):
        """Verify sandbox service gracefully handles Docker errors."""
        from app.services.sandbox_service import execute_script
        with patch("app.services.sandbox_service.docker.from_env") as mock_docker:
            mock_docker.side_effect = Exception("Docker not available")
            result = execute_script(
                script_type="shell",
                content="echo test",
                timeout=5,
                env_vars={},
                credential_values={},
            )
            assert result["status"] == "failed"
            assert result["exit_code"] == -1
            assert "Docker not available" in result["log"]
