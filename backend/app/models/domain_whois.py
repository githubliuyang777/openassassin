from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from app.database import Base, china_now


class DomainWhois(Base):
    __tablename__ = "domain_whois"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(256), unique=True, nullable=False)
    whois_expiry_date = Column(DateTime, nullable=True)
    whois_creation_date = Column(DateTime, nullable=True)
    whois_registrar = Column(String(256), nullable=True)
    whois_statuses = Column(Text, nullable=True)
    whois_nameservers = Column(Text, nullable=True)
    alert_enabled = Column(Boolean, default=True)
    notification_group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
