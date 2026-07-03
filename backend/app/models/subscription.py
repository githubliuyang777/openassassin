from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from app.database import Base, china_now


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    repo_url = Column(String(512), nullable=False)
    repo_platform = Column(String(32), default="github")
    repo_owner = Column(String(128), default="")
    repo_name = Column(String(128), default="")
    last_version = Column(String(64), default="")
    last_advisory_ghsa_id = Column(String(32), default="")
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)


class SubscriptionAlert(Base):
    __tablename__ = "subscription_alerts"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    alert_type = Column(String(16), nullable=False)
    title = Column(String(256), default="")
    summary = Column(Text, default="")
    url = Column(String(512), default="")
    ref_id = Column(String(64), default="")
    occurred_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=china_now)
