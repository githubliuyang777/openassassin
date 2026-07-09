import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-jwt-secret-key-32-chars!!"
os.environ["MASTER_KEY"] = "test-master-key-needs-32-byte!"
os.environ["SANDBOX_TMP_DIR"] = "/tmp/openassassin-sandbox-test"
os.environ["LOG_DIR"] = "/tmp/ops-test-logs"

os.environ["AUDIT_ENABLED"] = "false"

from app.database import Base, get_db, engine
from app.main import app
from app.services.auth_service import create_token, hash_password
from app.models.user import User

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user():
    """Create an admin user and return (user_dict, password)."""
    db = TestingSessionLocal()
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        db.close()
        return {"id": existing.id, "username": existing.username, "role": existing.role}, "admin"
    user = User(
        username="admin",
        password_hash=hash_password("admin"),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"id": user.id, "username": user.username, "role": user.role}, "admin"


@pytest.fixture
def auth_headers(admin_user):
    """Return Authorization header dict for admin user."""
    u, _ = admin_user
    token = create_token(u["id"], u["username"], u["role"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()
