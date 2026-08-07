from sqlalchemy import Column, Integer, Float, BigInteger, DateTime, ForeignKey
from app.database import Base, china_now


class HostMetric(Base):
    __tablename__ = "host_metrics"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable=False, index=True)
    cpu_percent = Column(Float, default=0.0)
    mem_total_mb = Column(Float, default=0.0)
    mem_used_mb = Column(Float, default=0.0)
    mem_percent = Column(Float, default=0.0)
    disk_total_gb = Column(Float, default=0.0)
    disk_used_gb = Column(Float, default=0.0)
    disk_percent = Column(Float, default=0.0)
    load_1m = Column(Float, default=0.0)
    load_5m = Column(Float, default=0.0)
    load_15m = Column(Float, default=0.0)
    net_rx_bytes = Column(BigInteger, default=0)
    net_tx_bytes = Column(BigInteger, default=0)
    process_count = Column(Integer, default=0)
    uptime_seconds = Column(Integer, default=0)
    collected_at = Column(DateTime, default=china_now, index=True)
