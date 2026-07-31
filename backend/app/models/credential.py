from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey

from app.database import Base, china_now


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
    notification_group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=True)
    last_alerted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
