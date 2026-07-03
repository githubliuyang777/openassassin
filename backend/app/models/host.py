from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.database import Base, china_now


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    hostname = Column(String(256), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(64), nullable=False)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=True)
    description = Column(String(512), default="")
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
