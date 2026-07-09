from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from app.database import Base, china_now


class SiteMonitor(Base):
    __tablename__ = "site_monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    target = Column(String(512), nullable=False)
    group_name = Column(String(64), default="")
    monitor_type = Column(String(8), nullable=False, default="http")
    http_method = Column(String(8), default="GET")
    expected_status_codes = Column(String(64), default="200")
    timeout = Column(Integer, default=10)
    retries = Column(Integer, default=2)
    check_interval = Column(Integer, default=300)
    alert_enabled = Column(Boolean, default=True)
    is_up = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_response_ms = Column(Float, nullable=True)
    last_alerted_at = Column(DateTime, nullable=True)
    notification_group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=True)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)


class SiteCheckResult(Base):
    __tablename__ = "site_check_results"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("site_monitors.id"), nullable=False)
    is_up = Column(Boolean, default=False)
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Float, nullable=True)
    error = Column(String(256), nullable=True)
    checked_at = Column(DateTime, default=china_now)
