from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/ops.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    master_key: str = "change-me-master-key-32-bytes!!"
    admin_default_password: str = "admin"
    # CORS: comma-separated allowlist. Production is same-origin via nginx
    # proxy, so no wildcard is needed. Never combine "*" with credentials.
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    admin_email: str = ""
    sandbox_image_shell: str = "alpine:3.20"
    sandbox_image_python: str = "python:3.12-alpine"
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_limit: float = 0.5
    sandbox_default_timeout: int = 300
    sandbox_max_timeout: int = 3600
    sandbox_tmp_dir: str = "/tmp/openassassin-sandbox"
    sandbox_image_awscli: str = "amazon/aws-cli:2.x"
    aws_default_region: str = "ap-southeast-1"
    aws_regions: str = "ap-southeast-1,us-east-1,eu-west-1"
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
    # Off by default: when enabled, public client IPs are sent to
    # ip-api.com for geolocation. Private/loopback IPs never leave the host.
    audit_ip_geolocation: bool = False
    # login rate limiting (failed attempts per window)
    login_failed_limit: int = 5
    login_ip_limit: int = 30
    login_window_seconds: int = 300
    # password reset code attempts per (ip, email)
    reset_code_limit: int = 5
    reset_code_window_seconds: int = 900
    # MFA backup code attempts per user
    mfa_recovery_limit: int = 5
    mfa_recovery_window_seconds: int = 600
    # TOTP / MFA
    totp_issuer: str = "openAssassin"
    totp_mfa_token_minutes: int = 2
    totp_setup_token_minutes: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
