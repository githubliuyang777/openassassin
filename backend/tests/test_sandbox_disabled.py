from unittest.mock import patch

from app.config import Settings, settings
from app.services.sandbox_service import execute_script


class TestSandboxEnabledSetting:
    def test_default_is_true(self):
        assert Settings.model_fields["sandbox_enabled"].default is True

    def test_env_false_overrides(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_ENABLED", "false")
        assert Settings(_env_file=None).sandbox_enabled is False


class TestSandboxDisabledExecution:
    def test_returns_failed_without_docker(self, monkeypatch):
        monkeypatch.setattr(settings, "sandbox_enabled", False)
        with patch("app.services.sandbox_service.docker.from_env") as mock_docker:
            result = execute_script("shell", "echo hi", 5, {}, {})
        assert result["status"] == "failed"
        assert result["exit_code"] == -1
        assert "[SANDBOX_DISABLED]" in result["log"]
        mock_docker.assert_not_called()

    def test_does_not_create_tmp_dir(self, monkeypatch):
        monkeypatch.setattr(settings, "sandbox_enabled", False)
        with patch("app.services.sandbox_service.os.makedirs") as mock_makedirs:
            execute_script("python", "print(1)", 5, {}, {})
        mock_makedirs.assert_not_called()

    def test_does_not_leak_credential_values(self, monkeypatch):
        monkeypatch.setattr(settings, "sandbox_enabled", False)
        result = execute_script("shell", "echo hi", 5, {}, {"API_TOKEN": "super-secret-value"})
        assert "super-secret-value" not in result["log"]

    def test_enabled_path_still_reports_docker_error(self, monkeypatch):
        monkeypatch.setattr(settings, "sandbox_enabled", True)
        with patch(
            "app.services.sandbox_service.docker.from_env",
            side_effect=Exception("Docker not available"),
        ):
            result = execute_script("shell", "echo hi", 5, {}, {})
        assert result["status"] == "failed"
        assert "Docker not available" in result["log"]
        assert "[SANDBOX_DISABLED]" not in result["log"]
