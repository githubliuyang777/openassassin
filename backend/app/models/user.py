from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base, china_now


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="admin")
    email = Column(String(128), default="")
    reset_code = Column(String(8), nullable=True)
    reset_code_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
