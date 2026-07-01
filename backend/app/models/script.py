from sqlalchemy import Column, Integer, String, Text, JSON, DateTime

from app.database import Base, china_now


class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), default="")
    type = Column(String(16), nullable=False)  # shell | python
    content = Column(Text, nullable=False)
    timeout = Column(Integer, default=300)
    env_vars = Column(JSON, default=dict)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
