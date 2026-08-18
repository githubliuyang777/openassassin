from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.database import Base, china_now


class HostEvent(Base):
    __tablename__ = "host_events"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable=False, index=True)
    category = Column(String(32), default="")       # oom / container
    severity = Column(String(16), default="info")    # critical / warning / info
    source = Column(String(32), default="")          # kernel / docker
    title = Column(String(256), default="")
    detail = Column(Text, default="")
    labels = Column(Text, default="{}")              # JSON
    created_at = Column(DateTime, default=china_now, index=True)
