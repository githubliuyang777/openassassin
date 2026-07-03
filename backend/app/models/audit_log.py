from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base, china_now


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(64), nullable=False)
    action = Column(String(16), nullable=False)
    resource = Column(String(256), nullable=False, default="")
    resource_type = Column(String(64), default="")
    detail = Column(Text, default="")
    ip_address = Column(String(45), default="")
    ip_location = Column(String(128), default="")
    user_agent = Column(String(256), default="")
    status_code = Column(Integer, default=0)
    created_at = Column(DateTime, default=china_now)
