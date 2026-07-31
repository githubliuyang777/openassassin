from sqlalchemy import Column, Integer, Text, Boolean, DateTime

from app.database import Base, china_now


class DingTalkConfig(Base):
    __tablename__ = "dingtalk_config"

    id = Column(Integer, primary_key=True, index=True)
    webhook_url = Column(Text, default="")
    secret = Column(Text, default="")
    is_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)
