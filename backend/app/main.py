import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.services.auth_service import get_or_create_admin
from app.api import auth, scripts, credentials, executions


def _migrate_users_table():
    """Add new columns to existing users table if missing (SQLite)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE users ADD COLUMN email VARCHAR(128) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN reset_code VARCHAR(8)",
        "ALTER TABLE users ADD COLUMN reset_code_expires_at DATETIME",
    ]
    with engine.begin() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # column already exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.log_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    db = SessionLocal()
    get_or_create_admin(db)
    db.close()
    yield


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
