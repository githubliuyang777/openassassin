from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base, china_now


class BaotaPanel(Base):
    __tablename__ = "baota_panels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    panel_url = Column(String(512), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    verify_tls = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
