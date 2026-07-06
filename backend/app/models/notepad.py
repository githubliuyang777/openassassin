from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base, china_now


class Notepad(Base):
    __tablename__ = "notepads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
