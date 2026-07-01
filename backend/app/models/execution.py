from sqlalchemy import Column, Integer, String, Text, JSON, DateTime

from app.database import Base, china_now


class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    script_id = Column(Integer, nullable=False, index=True)
    status = Column(String(16), default="pending")  # pending | running | success | failed | timeout
    started_at = Column(DateTime, default=china_now)
    finished_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    log_path = Column(String(512), nullable=True)
    triggered_by = Column(String(64), default="")
    credential_ids = Column(JSON, default=list)
