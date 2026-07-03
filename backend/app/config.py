from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/ops.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    master_key: str = "change-me-master-key-32-bytes!!"
    admin_default_password: str = "admin"
    admin_email: str = ""
    sandbox_image_shell: str = "alpine:3.20"
    sandbox_image_python: str = "python:3.12-alpine"
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_limit: float = 0.5
    sandbox_default_timeout: int = 300
    sandbox_max_timeout: int = 3600
    sandbox_tmp_dir: str = "/tmp/infra-ops-sandbox"
    log_dir: str = "./data/logs"
    # SMTP for password reset
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # alert notification
    alert_email: str = ""
    alert_before_days: int = 7
    alert_check_interval_minutes: int = 60
    # SSH / bastion host
    ssh_connect_timeout: int = 10
    ssh_terminal_idle_timeout: int = 3600
    # audit log
    audit_enabled: bool = True
    audit_ip_source: str = "forwarded"
    audit_log_retention_days: int = 180

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
