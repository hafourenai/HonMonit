import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    username = Column(String(255))
    ip = Column(String(15), nullable=False)
    os = Column(String(255), nullable=False)
    status = Column(String(20), default="offline", nullable=False)
    
    cpu_usage = Column(Float, default=0.0)
    ram_usage = Column(Float, default=0.0)
    disk_usage = Column(Float, default=0.0)
    
    last_heartbeat = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    metrics = relationship("Metric", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_device_id_status", "device_id", "status"),)


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    
    cpu_usage = Column(Float, nullable=False)
    ram_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    device = relationship("Device", back_populates="metrics")

    __table_args__ = (Index("idx_device_timestamp", "device_id", "timestamp"),)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    
    alert_type = Column(String(50), nullable=False)  # cpu_high, ram_high, disk_high, offline
    metric_type = Column(String(20))  # cpu, ram, disk
    threshold = Column(Float)
    current_value = Column(Float)
    
    severity = Column(String(20), default="warning")  # info, warning, critical
    is_resolved = Column(Boolean, default=False)
    
    triggered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="alerts")

    __table_args__ = (Index("idx_device_alert_type", "device_id", "alert_type"),)


class AlertThreshold(Base):
    __tablename__ = "alert_thresholds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    
    metric_type = Column(String(20), nullable=False)  # cpu, ram, disk
    threshold_value = Column(Float, nullable=False)
    is_enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    key_type = Column(String(20), default="agent")  # agent, dashboard, admin
    
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
