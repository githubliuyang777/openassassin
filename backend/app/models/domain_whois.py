from sqlalchemy import Column, Integer, String, Text, DateTime
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
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=china_now)
