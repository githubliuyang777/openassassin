import os
import time
import uuid
import docker
from docker.errors import ImageNotFound

from app.config import settings


def _mask_secrets(line: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            line = line.replace(s, "***")
    return line


def execute_script(
    script_type: str,
    content: str,
    timeout: int,
    env_vars: dict,
    credential_values: dict[str, str],
) -> dict:
    timeout = min(timeout or settings.sandbox_default_timeout, settings.sandbox_max_timeout)

    SCRIPT_CONFIG = {
        "shell":  (settings.sandbox_image_shell,  "script.sh", ["sh", "script.sh"],     "none"),
        "python": (settings.sandbox_image_python, "script.py", ["python", "script.py"],  "none"),
        "aws":    (settings.sandbox_image_awscli, "script.sh", ["sh", "script.sh"],     "bridge"),
    }
    config = SCRIPT_CONFIG.get(script_type)
    if config is None:
        config = SCRIPT_CONFIG["shell"]
    image, script_file, command, network_mode = config
    work_dir = "/workspace"

    sandbox_env = {**env_vars, **credential_values}
    secrets_to_mask = list(credential_values.values())

    log_lines: list[str] = []
    container = None
    tmp_dir = None

    try:
        client = docker.from_env()
        try:
            client.images.get(image)
        except ImageNotFound:
            client.images.pull(image)
        os.makedirs(settings.sandbox_tmp_dir, exist_ok=True)
        tmp_dir = os.path.join(settings.sandbox_tmp_dir, uuid.uuid4().hex)
        os.makedirs(tmp_dir)
        script_path = os.path.join(tmp_dir, script_file)
        with open(script_path, "w") as f:
            f.write(content)
        os.chmod(script_path, 0o555)

        container = client.containers.run(
            image=image,
            command=command,
            environment=sandbox_env,
            working_dir=work_dir,
            volumes={tmp_dir: {"bind": work_dir, "mode": "ro"}},
            mem_limit=settings.sandbox_memory_limit,
            nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
            network_mode=network_mode,
            read_only=True,
            cap_drop=["ALL"],                       # no capabilities at all
            pids_limit=128,                         # fork-bomb guard
            user="nobody",                          # non-root inside container
            tmpfs={"/tmp": "size=64m"},             # writable scratch, no disk leak
            security_opt=["no-new-privileges:true"],
            detach=True,
        )

        deadline = time.time() + timeout
        exit_code = -1
        while time.time() < deadline:
            container.reload()
            if container.status != "running":
                break
            time.sleep(0.5)

        container.reload()
        if container.status == "running":
            container.kill()
            status = "timeout"
        else:
            result = container.wait()
            exit_code = result["StatusCode"]
            status = "success" if exit_code == 0 else "failed"

        raw_logs = container.logs(stdout=True, stderr=True).decode(errors="replace")
        for line in raw_logs.splitlines():
            masked = _mask_secrets(line, secrets_to_mask)
            log_lines.append(masked)

    except Exception as exc:
        status = "failed"
        exit_code = -1
        log_lines.append(f"[SANDBOX_ERROR] {str(exc)}")
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if tmp_dir:
            try:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    return {
        "status": status,
        "exit_code": exit_code,
        "log": "\n".join(log_lines),
    }
