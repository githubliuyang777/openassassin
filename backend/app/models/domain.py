from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base, china_now


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(256), unique=True, nullable=False)
    port = Column(Integer, default=443)
    ssl_subject = Column(String(512), nullable=True)
    ssl_issuer = Column(String(512), nullable=True)
    ssl_not_before = Column(DateTime, nullable=True)
    ssl_not_after = Column(DateTime, nullable=True)
    ssl_expired = Column(Boolean, default=False)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
