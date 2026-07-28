import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, and_
from server.models import Device, Metric, Alert, AlertThreshold

logger = logging.getLogger("honmonit.device_store")


class DeviceStore:
    """SQLite-backed device store with persistence and history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, device_id: str, info: dict) -> dict:
        """Register or update a device."""
        existing = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = existing.scalars().first()

        if device:
            device.hostname = info.get("hostname", device.hostname)
            device.username = info.get("username", device.username)
            device.ip = info.get("ip", device.ip)
            device.os = info.get("os", device.os)
            device.status = "online"
            device.updated_at = datetime.now(timezone.utc)
            logger.info("Device %s (%s) re-registered", device_id, device.hostname)
        else:
            device = Device(
                device_id=device_id,
                hostname=info.get("hostname", "Unknown"),
                username=info.get("username", "Unknown"),
                ip=info.get("ip", "0.0.0.0"),
                os=info.get("os", "Unknown"),
                status="online",
            )
            self.db.add(device)
            logger.info("Device %s (%s) registered", device_id, device.hostname)

        await self.db.commit()
        return self._device_to_dict(device)

    async def get(self, device_id: str) -> Optional[dict]:
        """Get a device by ID."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalars().first()
        return self._device_to_dict(device) if device else None

    async def get_all(self) -> List[dict]:
        """Get all devices."""
        result = await self.db.execute(select(Device))
        devices = result.scalars().all()
        return [self._device_to_dict(d) for d in devices]

    async def mark_offline(self, device_id: str):
        """Mark a device as offline."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalars().first()
        if device:
            device.status = "offline"
            device.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

    async def update_heartbeat(
        self, device_id: str, cpu_usage: float, ram_usage: float, disk_usage: float
    ) -> Optional[dict]:
        """Update device metrics and save to history."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalars().first()

        if device:
            device.cpu_usage = cpu_usage
            device.ram_usage = ram_usage
            device.disk_usage = disk_usage
            device.status = "online"
            device.last_heartbeat = datetime.now(timezone.utc)
            device.updated_at = datetime.now(timezone.utc)

            # Save metric to history
            metric = Metric(
                device_id=device_id,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                disk_usage=disk_usage,
            )
            self.db.add(metric)

            await self.db.commit()
            return self._device_to_dict(device)

        return None

    async def get_metrics_history(
        self,
        device_id: str,
        hours: int = 24,
    ) -> List[dict]:
        """Get metrics history for a device."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.db.execute(
            select(Metric)
            .where(
                and_(
                    Metric.device_id == device_id,
                    Metric.timestamp >= since,
                )
            )
            .order_by(Metric.timestamp)
        )
        metrics = result.scalars().all()

        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "cpu_usage": m.cpu_usage,
                "ram_usage": m.ram_usage,
                "disk_usage": m.disk_usage,
            }
            for m in metrics
        ]

    async def check_thresholds_and_create_alerts(self, device_id: str):
        """Check if metrics exceed thresholds and create alerts."""
        # Get device
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalars().first()
        if not device:
            return

        # Get alert thresholds
        result = await self.db.execute(
            select(AlertThreshold).where(
                and_(
                    AlertThreshold.device_id == device_id,
                    AlertThreshold.is_enabled == True,
                )
            )
        )
        thresholds = result.scalars().all()

        for threshold in thresholds:
            metric_type = threshold.metric_type
            current_value = None

            if metric_type == "cpu":
                current_value = device.cpu_usage
            elif metric_type == "ram":
                current_value = device.ram_usage
            elif metric_type == "disk":
                current_value = device.disk_usage

            if current_value is not None and current_value > threshold.threshold_value:
                # Check if alert already exists and is unresolved
                result = await self.db.execute(
                    select(Alert).where(
                        and_(
                            Alert.device_id == device_id,
                            Alert.metric_type == metric_type,
                            Alert.is_resolved == False,
                        )
                    )
                )
                existing_alert = result.scalars().first()

                if not existing_alert:
                    alert = Alert(
                        device_id=device_id,
                        alert_type=f"{metric_type}_high",
                        metric_type=metric_type,
                        threshold=threshold.threshold_value,
                        current_value=current_value,
                        severity="warning" if current_value < 95 else "critical",
                    )
                    self.db.add(alert)
                    logger.warning(
                        "Alert triggered: %s %s at %.1f%% (threshold: %.1f%%)",
                        device_id,
                        metric_type,
                        current_value,
                        threshold.threshold_value,
                    )
                else:
                    # Update existing alert with new value
                    existing_alert.current_value = current_value
                    existing_alert.updated_at = datetime.now(timezone.utc)

                await self.db.commit()

    async def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalars().first()
        if alert:
            alert.is_resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            await self.db.commit()

    async def get_alerts(
        self,
        device_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get alerts with optional filtering."""
        query = select(Alert)

        if device_id:
            query = query.where(Alert.device_id == device_id)
        if resolved is not None:
            query = query.where(Alert.is_resolved == resolved)

        query = query.order_by(desc(Alert.triggered_at)).limit(limit)

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        return [
            {
                "id": a.id,
                "device_id": a.device_id,
                "alert_type": a.alert_type,
                "metric_type": a.metric_type,
                "threshold": a.threshold,
                "current_value": a.current_value,
                "severity": a.severity,
                "is_resolved": a.is_resolved,
                "triggered_at": a.triggered_at.isoformat(),
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in alerts
        ]

    @staticmethod
    def _device_to_dict(device: Device) -> dict:
        """Convert a Device object to a dictionary."""
        return {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "username": device.username,
            "ip": device.ip,
            "os": device.os,
            "status": device.status,
            "cpu_usage": device.cpu_usage,
            "ram_usage": device.ram_usage,
            "disk_usage": device.disk_usage,
            "last_heartbeat": device.last_heartbeat.isoformat()
            if device.last_heartbeat
            else None,
            "created_at": device.created_at.isoformat(),
            "updated_at": device.updated_at.isoformat(),
        }
