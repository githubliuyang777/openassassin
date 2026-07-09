from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, china_now


class NotificationGroup(Base):
    __tablename__ = "notification_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=china_now)
    updated_at = Column(DateTime, default=china_now, onupdate=china_now)

    recipients = relationship("NotificationRecipient", back_populates="group", cascade="all, delete-orphan")


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    channel_type = Column(String(16), default="email")
    address = Column(String(128), nullable=False)
    group_id = Column(Integer, ForeignKey("notification_groups.id"), nullable=False)
    created_at = Column(DateTime, default=china_now)

    group = relationship("NotificationGroup", back_populates="recipients")
