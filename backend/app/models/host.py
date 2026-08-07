from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from app.database import Base, china_now


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    hostname = Column(String(256), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(64), nullable=False)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=True)
    aws_instance_id = Column(String(32), nullable=True)
    aws_region = Column(String(32), nullable=True)
    aws_credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=True)
    description = Column(String(512), default="")
    # Agent monitoring fields
    agent_token = Column(String(64), nullable=True, unique=True)
    agent_version = Column(String(16), default="")
    last_seen_at = Column(DateTime, nullable=True)
    is_online = Column(Boolean, default=False)
    cpu_usage = Column(Float, default=0.0)
    mem_usage = Column(Float, default=0.0)
    disk_usage = Column(Float, default=0.0)
    alert_enabled = Column(Boolean, default=True)
    notification_group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=True)
    last_alerted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
