import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.services.auth_service import get_or_create_admin
from app.api import auth, scripts, credentials, executions, notifications, domains, domain_whois


def _migrate(table: str, columns: list[tuple[str, str]]):
    """Add new columns to an existing table if missing (SQLite)."""
    from sqlalchemy import text
    with engine.begin() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass


def _migrate_users_table():
    _migrate("users", [
        ("email", "VARCHAR(128) DEFAULT ''"),
        ("reset_code", "VARCHAR(8)"),
        ("reset_code_expires_at", "DATETIME"),
    ])


def _migrate_credentials_table():
    _migrate("credentials", [
        ("type", "VARCHAR(32) DEFAULT 'generic'"),
        ("expires_at", "DATETIME"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_alerted_at", "DATETIME"),
    ])


def _migrate_domains_table():
    _migrate("domains", [
        ("ssl_subject", "VARCHAR(512)"),
        ("ssl_issuer", "VARCHAR(512)"),
        ("ssl_not_before", "DATETIME"),
        ("ssl_not_after", "DATETIME"),
        ("ssl_expired", "BOOLEAN DEFAULT 0"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_checked_at", "DATETIME"),
    ])


def _migrate_domain_whois_table():
    _migrate("domain_whois", [
        ("whois_expiry_date", "DATETIME"),
        ("whois_creation_date", "DATETIME"),
        ("whois_registrar", "VARCHAR(256)"),
        ("whois_statuses", "TEXT"),
        ("whois_nameservers", "TEXT"),
        ("alert_enabled", "BOOLEAN DEFAULT 1"),
        ("last_checked_at", "DATETIME"),
    ])


async def _alert_check_loop():
    """Background task: periodically check for expiring credentials and send alerts."""
    while True:
        await asyncio.sleep(settings.alert_check_interval_minutes * 60)
        try:
            from app.services.alert_service import check_and_alert
            db = SessionLocal()
            try:
                check_and_alert(db)
            finally:
                db.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.log_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    _migrate_credentials_table()
    _migrate_domains_table()
    _migrate_domain_whois_table()
    db = SessionLocal()
    get_or_create_admin(db)
    db.close()
    task = asyncio.create_task(_alert_check_loop())
    yield
    task.cancel()


app = FastAPI(title="Ops Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(scripts.router, prefix="/api/v1")
app.include_router(credentials.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(domains.router, prefix="/api/v1")
app.include_router(domain_whois.router, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok"}
