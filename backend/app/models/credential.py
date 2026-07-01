from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func

from app.database import Base


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    key = Column(String(128), nullable=False)  # env var name, e.g. K8S_TOKEN
    encrypted_value = Column(Text, nullable=False)
    description = Column(String(512), default="")
    type = Column(String(32), default="generic")
    expires_at = Column(DateTime, nullable=True)
    alert_enabled = Column(Boolean, default=True)
    last_alerted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
