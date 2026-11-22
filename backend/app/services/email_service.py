import logging
import smtplib
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)

PROVIDER_PRIMARY = "primary"
PROVIDER_FALLBACK = "fallback"
PROVIDER_AUTO = "auto"

RECIPIENT_ERROR_CODES = {550, 551, 553}


class EmailNotConfiguredError(Exception):
    pass


@dataclass(frozen=True)
class EmailProvider:
    name: str
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    from_addr: str
    use_tls: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    @property
    def sender(self) -> str:
        return self.from_addr or self.username


@dataclass
class EmailError:
    provider: str
    kind: str  # provider | recipient | config | circuit | budget
    message: str
    smtp_code: int | None = None
    recipients: list[str] = field(default_factory=list)


@dataclass
class EmailDeliveryResult:
    provider: str | None
    delivered: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: list[EmailError] = field(default_factory=list)
    failover: bool = False


@dataclass(frozen=True)
class CircuitStatus:
    state: str  # closed | open | half_open
    consecutive_failures: int
    opened_at: datetime | None
    retry_at: datetime | None
    last_error: str | None
    last_success_at: datetime | None


class CircuitBreaker:
    """In-memory per-provider circuit breaker.

    A dispatch attempt that reaches the provider counts once, regardless of
    how many recipients are in the batch. Recipient-level refusals mean the
    provider is reachable and must not open the circuit.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int,
        cooldown_seconds: int,
        clock=time.monotonic,
    ):
        self.name = name
        self._threshold = max(1, int(failure_threshold))
        self._cooldown = max(1, int(cooldown_seconds))
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_until: float | None = None
        self._opened_at: datetime | None = None
        self._half_open_in_flight = False
        self._last_error: str | None = None
        self._last_success_at: datetime | None = None

    def allow(self) -> bool:
        with self._lock:
            now = self._clock()
            if self._opened_until is None:
                return True
            if now < self._opened_until:
                return False
            # Cooldown elapsed: allow exactly one half-open probe.
            if self._half_open_in_flight:
                return False
            self._half_open_in_flight = True
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_until = None
            self._opened_at = None
            self._half_open_in_flight = False
            self._last_error = None
            self._last_success_at = datetime.now(timezone.utc)

    def record_failure(self, message: str) -> None:
        with self._lock:
            self._failures += 1
            self._last_error = message
            self._half_open_in_flight = False
            if self._failures >= self._threshold:
                self._opened_until = self._clock() + self._cooldown
                self._opened_at = datetime.now(timezone.utc)

    def release(self) -> None:
        """Release a half-open probe that was allowed but never attempted."""
        with self._lock:
            self._half_open_in_flight = False

    def snapshot(self) -> CircuitStatus:
        with self._lock:
            now = self._clock()
            if self._opened_until is None:
                state = "closed"
                retry_at = None
            elif now < self._opened_until:
                state = "open"
                retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=max(0.0, self._opened_until - now)
                )
            else:
                state = "half_open"
                retry_at = None
            return CircuitStatus(
                state=state,
                consecutive_failures=self._failures,
                opened_at=self._opened_at,
                retry_at=retry_at,
                last_error=self._last_error,
                last_success_at=self._last_success_at,
            )


# In-process health: the backend is single-replica; a restart resets it.
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def _breaker_for(name: str) -> CircuitBreaker:
    with _breakers_lock:
        breaker = _breakers.get(name)
        if breaker is None:
            breaker = CircuitBreaker(
                name,
                failure_threshold=settings.smtp_alert_circuit_failures,
                cooldown_seconds=settings.smtp_alert_circuit_open_seconds,
            )
            _breakers[name] = breaker
        return breaker


def reset_email_state() -> None:
    """Test helper: clear in-memory provider health."""
    with _breakers_lock:
        _breakers.clear()


def _primary_provider() -> EmailProvider:
    return EmailProvider(
        name=PROVIDER_PRIMARY,
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_addr=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )


def _fallback_provider() -> EmailProvider:
    return EmailProvider(
        name=PROVIDER_FALLBACK,
        host=settings.smtp_fallback_host,
        port=settings.smtp_fallback_port,
        username=settings.smtp_fallback_username,
        password=settings.smtp_fallback_password,
        from_addr=settings.smtp_fallback_from or settings.smtp_fallback_username,
        use_tls=settings.smtp_fallback_use_tls,
    )


def get_providers() -> tuple[EmailProvider, EmailProvider]:
    return _primary_provider(), _fallback_provider()


def is_transactional_configured() -> bool:
    return _primary_provider().is_configured


def is_alert_configured() -> bool:
    primary, fallback = get_providers()
    return primary.is_configured or fallback.is_configured


def _candidate_providers(mode: str) -> list[EmailProvider]:
    primary, fallback = get_providers()
    if mode == PROVIDER_PRIMARY:
        return [primary] if primary.is_configured else []
    if mode == PROVIDER_FALLBACK:
        return [fallback] if fallback.is_configured else []
    return [p for p in (primary, fallback) if p.is_configured]


def _dedupe(recipients: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for recipient in recipients:
        if recipient and recipient not in seen:
            seen.add(recipient)
            result.append(recipient)
    return result


def _smtp_code(exc: Exception) -> int | None:
    code = getattr(exc, "smtp_code", None)
    if isinstance(code, int):
        return code
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        for recipient_code, _ in exc.recipients.values():
            if isinstance(recipient_code, int):
                return recipient_code
    return None


def _is_recipient_error(exc: Exception) -> bool:
    if not isinstance(exc, smtplib.SMTPRecipientsRefused):
        return False
    codes = [code for code, _ in exc.recipients.values() if isinstance(code, int)]
    return bool(codes) and all(code in RECIPIENT_ERROR_CODES for code in codes)


def _safe_message(provider: EmailProvider, exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    if provider.password:
        text = text.replace(provider.password, "***")
    return text[:200]


def _email_error(provider: EmailProvider, exc: Exception, kind: str | None = None) -> EmailError:
    error_kind = kind or ("recipient" if _is_recipient_error(exc) else "provider")
    recipients: list[str] = []
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        recipients = list(exc.recipients.keys())
    return EmailError(
        provider=provider.name,
        kind=error_kind,
        message=_safe_message(provider, exc),
        smtp_code=_smtp_code(exc),
        recipients=recipients,
    )


def _build_message(provider: EmailProvider, to: str, subject: str, body: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = provider.sender
    msg["To"] = to
    return msg


def _open_connection(provider: EmailProvider, timeout: float):
    context = ssl.create_default_context()
    server = None
    try:
        if provider.port == 465:
            server = smtplib.SMTP_SSL(
                provider.host, provider.port, timeout=timeout, context=context
            )
        else:
            server = smtplib.SMTP(provider.host, provider.port, timeout=timeout)
            if provider.use_tls:
                server.starttls(context=context)
        if provider.username:
            server.login(provider.username, provider.password)
        return server
    except Exception:
        if server is not None:
            try:
                server.close()
            except Exception:
                pass
        raise


def _close_quietly(server) -> None:
    if server is None:
        return
    try:
        server.quit()
    except Exception:
        try:
            server.close()
        except Exception:
            pass


def _send_one(provider: EmailProvider, to: str, subject: str, body: str, timeout: float) -> None:
    server = _open_connection(provider, timeout)
    try:
        msg = _build_message(provider, to, subject, body)
        server.sendmail(provider.sender, [to], msg.as_string())
    finally:
        _close_quietly(server)


def _send_batch_on_provider(
    provider: EmailProvider,
    recipients: list[str],
    subject: str,
    body: str,
    deadline: float,
) -> tuple[list[str], dict[str, str], list[str], list[EmailError], bool, bool]:
    """Send to recipients over one connection.

    Returns (delivered, failed_by_recipient, remaining, errors, provider_failed, connected).
    A provider-level failure marks the in-flight recipient failed and does not
    resend it on the fallback, avoiding ambiguous duplicates.
    """
    delivered: list[str] = []
    failed: dict[str, str] = {}
    errors: list[EmailError] = []
    pending = list(recipients)

    remaining_budget = deadline - time.monotonic()
    if remaining_budget < 1:
        message = "dispatch budget exhausted"
        for recipient in pending:
            failed[recipient] = message
        errors.append(EmailError(provider.name, "budget", message, recipients=pending.copy()))
        return delivered, failed, [], errors, False, False

    timeout = max(1.0, min(float(settings.smtp_alert_timeout_seconds), remaining_budget))
    try:
        server = _open_connection(provider, timeout)
    except Exception as exc:
        errors.append(_email_error(provider, exc))
        return delivered, failed, pending, errors, True, False

    try:
        while pending:
            if deadline - time.monotonic() < 1:
                message = "dispatch budget exhausted"
                for recipient in pending:
                    failed[recipient] = message
                errors.append(EmailError(provider.name, "budget", message, recipients=pending.copy()))
                pending = []
                break

            recipient = pending[0]
            try:
                msg = _build_message(provider, recipient, subject, body)
                refused = server.sendmail(provider.sender, [recipient], msg.as_string())
                if refused:
                    failed[recipient] = "recipient refused"
                    errors.append(
                        EmailError(provider.name, "recipient", "recipient refused", recipients=[recipient])
                    )
                else:
                    delivered.append(recipient)
                pending.pop(0)
            except Exception as exc:
                if _is_recipient_error(exc):
                    failed[recipient] = _safe_message(provider, exc)
                    errors.append(_email_error(provider, exc, "recipient"))
                    pending.pop(0)
                    continue
                # Provider-level failure; the in-flight recipient is ambiguous.
                error = _email_error(provider, exc)
                failed[recipient] = error.message
                errors.append(error)
                pending.pop(0)
                return delivered, failed, pending, errors, True, True
    finally:
        _close_quietly(server)

    return delivered, failed, pending, errors, False, True


def _send_alert(
    recipients: list[str],
    subject: str,
    body: str,
    provider: str = PROVIDER_AUTO,
) -> EmailDeliveryResult:
    recipients = _dedupe(recipients)
    if not recipients:
        return EmailDeliveryResult(provider=None)

    candidates = _candidate_providers(provider)
    if not candidates:
        error = EmailError("", "config", "邮件服务未配置")
        return EmailDeliveryResult(provider=None, failed=list(recipients), errors=[error])

    deadline = time.monotonic() + max(1, int(settings.smtp_alert_total_budget_seconds))
    delivered: list[str] = []
    failed: dict[str, str] = {}
    errors: list[EmailError] = []
    pending = list(recipients)
    last_provider: str | None = None
    forced = provider in (PROVIDER_PRIMARY, PROVIDER_FALLBACK)

    for candidate in candidates:
        breaker = _breaker_for(candidate.name)
        if deadline - time.monotonic() < 1:
            message = "dispatch budget exhausted"
            for recipient in pending:
                failed[recipient] = message
            errors.append(EmailError(candidate.name, "budget", message, recipients=pending.copy()))
            pending = []
            break

        if not forced and not breaker.allow():
            errors.append(EmailError(candidate.name, "circuit", "provider circuit open"))
            continue

        result = _send_batch_on_provider(candidate, pending, subject, body, deadline)
        batch_delivered, batch_failed, remaining, batch_errors, provider_failed, connected = result
        delivered.extend(batch_delivered)
        failed.update(batch_failed)
        errors.extend(batch_errors)
        pending = remaining

        if provider_failed:
            breaker.record_failure(
                "; ".join(e.message for e in batch_errors if e.kind == "provider")[:200]
                or "provider error"
            )
            logger.warning(
                "SMTP alert provider %s failed: %s",
                candidate.name,
                "; ".join(e.message for e in batch_errors)[:200],
            )
        elif connected:
            breaker.record_success()
        else:
            # Budget expired before the connection was attempted; don't leave
            # a half-open probe permanently in flight.
            breaker.release()

        if batch_delivered:
            last_provider = candidate.name
        if not pending:
            break

    if pending:
        for recipient in pending:
            failed[recipient] = "no available provider"
        if not any(error.kind in ("provider", "circuit", "budget") for error in errors):
            errors.append(EmailError("", "provider", "no available provider", recipients=pending.copy()))

    # A delivery through fallback while primary was a candidate is a failover,
    # including the case where primary was skipped because its circuit was open.
    failover = (
        not forced
        and last_provider == PROVIDER_FALLBACK
        and any(candidate.name == PROVIDER_PRIMARY for candidate in candidates)
    )

    if not delivered and errors:
        logger.error("SMTP alert delivery failed: %s", "; ".join(e.message for e in errors)[:300])
    elif failover:
        logger.warning("SMTP alert delivered via fallback provider")

    return EmailDeliveryResult(
        provider=last_provider,
        delivered=delivered,
        failed=list(failed.keys()),
        errors=errors,
        failover=failover,
    )


def send_alert_email(
    to: str,
    subject: str,
    body: str,
    provider: str = PROVIDER_AUTO,
) -> EmailDeliveryResult:
    return _send_alert([to], subject, body, provider=provider)


def send_alert_bulk(
    recipients: list[str],
    subject: str,
    body: str,
    provider: str = PROVIDER_AUTO,
) -> EmailDeliveryResult:
    return _send_alert(recipients, subject, body, provider=provider)


def send_email(to: str, subject: str, body: str) -> None:
    """Transactional email: primary SMTP only, no failover or circuit breaker."""
    provider = _primary_provider()
    if not provider.is_configured:
        raise EmailNotConfiguredError("邮件服务未配置，请联系管理员设置 SMTP 环境变量")
    _send_one(provider, to, subject, body, max(1, int(settings.smtp_timeout_seconds)))


def send_reset_code(email: str, code: str) -> None:
    body = f"""您的 openAssassin 密码重置验证码为：

    {code}

该验证码 5 分钟内有效。如非本人操作，请忽略此邮件。
"""
    send_email(email, "openAssassin 密码重置验证码", body)


def _provider_status(provider: EmailProvider) -> dict:
    if not provider.is_configured:
        return {
            "configured": False,
            "host": None,
            "port": None,
            "from": None,
            "use_tls": provider.use_tls,
            "health": "closed",
            "last_error": None,
            "last_success_at": None,
        }
    snapshot = _breaker_for(provider.name).snapshot()
    return {
        "configured": True,
        "host": provider.host,
        "port": provider.port,
        "from": provider.sender,
        "use_tls": provider.use_tls,
        "health": snapshot.state,
        "last_error": snapshot.last_error,
        "last_success_at": snapshot.last_success_at.isoformat() if snapshot.last_success_at else None,
    }


def get_smtp_status() -> dict:
    primary, fallback = get_providers()
    primary_status = _provider_status(primary)
    fallback_status = _provider_status(fallback)
    active_circuit = None
    for name, status in (("primary", primary_status), ("fallback", fallback_status)):
        if status["configured"] and status["health"] != "closed":
            active_circuit = name
            break
    return {
        "configured": primary.is_configured or fallback.is_configured,
        "alert_configured": primary.is_configured or fallback.is_configured,
        "transactional_configured": primary.is_configured,
        "alert_failover_enabled": fallback.is_configured,
        "primary": primary_status,
        "fallback": fallback_status,
        "active_circuit": active_circuit,
        # Legacy top-level fields: primary SMTP only.
        "host": primary_status["host"],
        "port": primary_status["port"],
        "from": primary_status["from"],
        "use_tls": primary.use_tls,
    }
