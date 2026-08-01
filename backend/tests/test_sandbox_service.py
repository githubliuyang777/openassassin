"""sandbox_service.execute_script 超时/成功/失败/密钥掩码/容器安全参数测试。

mock docker SDK（docker.from_env），不真实启动容器。
"""
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-jwt-secret-key-32-chars!!"
os.environ["MASTER_KEY"] = "test-master-key-needs-32-byte!"
os.environ["SANDBOX_TMP_DIR"] = "/tmp/openassassin-sandbox-test"

from app.services.sandbox_service import execute_script


class FakeContainer:
    """模拟 docker SDK 的 container 对象，通过 status 控制超时/成功/失败场景。"""

    def __init__(self, status="running", exit_code=0, logs="hello"):
        self._status = status
        self.exit_code = exit_code
        self._logs = logs
        self.killed = False
        self.removed = False
        self.waited = False
        self.reload_count = 0

    @property
    def status(self):
        return self._status

    def reload(self):
        self.reload_count += 1

    def kill(self):
        self.killed = True
        self._status = "exited"

    def wait(self):
        self.waited = True
        return {"StatusCode": self.exit_code}

    def logs(self, stdout=True, stderr=True):
        return self._logs.encode("utf-8")

    def remove(self, force=True):
        self.removed = True


class ExitingContainer(FakeContainer):
    """第 2 次 reload 后容器自行退出，用于验证轮询循环。"""

    def reload(self):
        super().reload()
        if self.reload_count >= 2:
            self._status = "exited"


def _mock_docker(container):
    client = MagicMock()
    client.images.get.return_value = object()  # 镜像已存在，不触发 pull
    client.containers.run.return_value = container
    return client


def _fast_clock(*seconds):
    """返回 time.time 的 side_effect：第一次调用为当前时间，后续调用直接跳到 deadline 之后。

    这样不需要真实等待超时时间，轮询循环立即判定"已超时"。
    """
    it = iter(seconds)
    return lambda: next(it, 9999.0)


class TestExecuteTimeout:
    def test_timeout_kills_running_container(self):
        """容器一直 running → 超时后 kill，返回 status=timeout、exit_code=-1。"""
        container = FakeContainer(status="running")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.time", side_effect=_fast_clock(1000.0, 2000.0)):
            result = execute_script(
                script_type="shell", content="sleep 100", timeout=1,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "timeout"
        assert result["exit_code"] == -1
        assert container.killed is True
        assert container.removed is True  # finally 清理容器
        assert result["log"] == "hello"  # 超时后仍收集已产生的日志

    def test_timeout_cleans_up_tmp_dir(self):
        """超时后临时脚本目录必须被删除。"""
        container = FakeContainer(status="running")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.time", side_effect=_fast_clock(1000.0, 2000.0)):
            execute_script(script_type="shell", content="x", timeout=1, env_vars={}, credential_values={})
        from app.config import settings
        leftovers = os.listdir(settings.sandbox_tmp_dir)
        assert leftovers == []

    def test_timeout_logs_masked_secrets(self):
        """超时场景下日志同样要掩码密钥值。"""
        container = FakeContainer(status="running", logs="TOKEN=supersecret-value\nfinished")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.time", side_effect=_fast_clock(1000.0, 2000.0)):
            result = execute_script(
                script_type="shell", content="x", timeout=1,
                env_vars={}, credential_values={"API_TOKEN": "supersecret-value"},
            )
        assert result["status"] == "timeout"
        assert "supersecret-value" not in result["log"]
        assert "***" in result["log"]

    def test_timeout_is_capped_at_max_timeout(self, monkeypatch):
        """请求的超时时间超过上限时按 sandbox_max_timeout 截断。"""
        from app.config import settings
        monkeypatch.setattr(settings, "sandbox_max_timeout", 2)
        container = FakeContainer(status="running")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.time", side_effect=_fast_clock(1000.0, 1002.1)):
            result = execute_script(
                script_type="shell", content="x", timeout=3600,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "timeout"
        # 若未截断（deadline=1000+3600），第二次 time.time()=1002.1 < 4600 会进入轮询循环，
        # reload 至少 2 次；截断后只发生循环外的 1 次 reload。
        assert container.reload_count == 1

    def test_timeout_zero_falls_back_to_default(self, monkeypatch):
        """timeout=0 时使用 sandbox_default_timeout，而不是立即超时。"""
        from app.config import settings
        monkeypatch.setattr(settings, "sandbox_default_timeout", 30)
        monkeypatch.setattr(settings, "sandbox_max_timeout", 60)
        container = FakeContainer(status="running")
        # 第二次 time.time()=1010.0 < deadline(1000+30=1030) → 必须进入轮询循环；
        # 若 0 被当成 0s（deadline=1000），1010 >= 1000 → 直接退出循环，reload 只有 1 次。
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.time", side_effect=_fast_clock(1000.0, 1010.0)):
            result = execute_script(
                script_type="shell", content="x", timeout=0,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "timeout"
        assert container.reload_count == 2  # 1 次循环内轮询 + 1 次循环后检查


class TestExecuteOutcome:
    def test_success_exit_zero(self):
        container = FakeContainer(status="exited", exit_code=0, logs="hello world")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.sleep", return_value=None):
            result = execute_script(
                script_type="python", content="print(1)", timeout=5,
                env_vars={"FOO": "bar"}, credential_values={},
            )
        assert result["status"] == "success"
        assert result["exit_code"] == 0
        assert result["log"] == "hello world"
        assert container.killed is False
        assert container.removed is True
        assert container.waited is True

    def test_failed_exit_nonzero(self):
        container = FakeContainer(status="exited", exit_code=2, logs="boom")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.sleep", return_value=None):
            result = execute_script(
                script_type="shell", content="exit 2", timeout=5,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "failed"
        assert result["exit_code"] == 2
        assert result["log"] == "boom"

    def test_polling_loop_exits_when_container_finishes(self):
        """轮询循环在容器自行退出时提前结束，而不是等到超时。"""
        container = ExitingContainer(status="running", exit_code=0, logs="done")
        with patch("app.services.sandbox_service.docker.from_env", return_value=_mock_docker(container)), \
             patch("app.services.sandbox_service.time.sleep", return_value=None):
            result = execute_script(
                script_type="shell", content="echo done", timeout=5,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "success"
        assert container.waited is True
        assert container.killed is False
        assert container.reload_count >= 2  # 循环内至少轮询了 2 次

    def test_docker_error_returns_failed(self):
        with patch("app.services.sandbox_service.docker.from_env", side_effect=Exception("Docker down")):
            result = execute_script(
                script_type="shell", content="x", timeout=5,
                env_vars={}, credential_values={},
            )
        assert result["status"] == "failed"
        assert result["exit_code"] == -1
        assert "Docker down" in result["log"]


class TestContainerSecurityOptions:
    def test_run_with_hardening_options(self):
        """容器必须带网络隔离/只读/降权/资源限制等加固参数。"""
        container = FakeContainer(status="exited", exit_code=0, logs="")
        client = _mock_docker(container)
        with patch("app.services.sandbox_service.docker.from_env", return_value=client), \
             patch("app.services.sandbox_service.time.sleep", return_value=None):
            execute_script(script_type="shell", content="echo hi", timeout=5, env_vars={}, credential_values={})

        kwargs = client.containers.run.call_args.kwargs
        assert kwargs["network_mode"] == "none"
        assert kwargs["read_only"] is True
        assert kwargs["cap_drop"] == ["ALL"]
        assert kwargs["pids_limit"] == 128
        assert kwargs["user"] == "nobody"
        assert kwargs["security_opt"] == ["no-new-privileges:true"]
        assert "tmpfs" in kwargs  # 可写 /tmp 挂载, 不落盘
        assert kwargs["image"] is not None
