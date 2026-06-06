import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("honmonit.device_store")


class DeviceStore:
    def __init__(self):
        self._devices: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def register(self, device_id: str, info: dict) -> dict:
        async with self._lock:
            is_new = device_id not in self._devices
            device = {
                "device_id": device_id,
                "hostname": info.get("hostname", "Unknown"),
                "username": info.get("username", "Unknown"),
                "ip": info.get("ip", "0.0.0.0"),
                "os": info.get("os", "Unknown"),
                "status": "online",
                "cpu_usage": 0,
                "ram_usage": 0,
                "disk_usage": 0,
                "last_heartbeat": None,
            }
            self._devices[device_id] = device
            if not is_new:
                logger.info("Device %s (%s) re-registered", device_id, device["hostname"])
            return dict(device)

    async def get(self, device_id: str) -> Optional[dict]:
        async with self._lock:
            d = self._devices.get(device_id)
            return dict(d) if d else None

    async def get_all(self) -> list:
        async with self._lock:
            return [dict(d) for d in self._devices.values()]

    async def mark_offline(self, device_id: str):
        async with self._lock:
            if device_id in self._devices:
                self._devices[device_id]["status"] = "offline"

    async def remove(self, device_id: str):
        async with self._lock:
            self._devices.pop(device_id, None)

    async def update_heartbeat(
        self, device_id: str, cpu_usage: float, ram_usage: float, disk_usage: float
    ) -> Optional[dict]:
        async with self._lock:
            if device_id in self._devices:
                self._devices[device_id]["cpu_usage"] = cpu_usage
                self._devices[device_id]["ram_usage"] = ram_usage
                self._devices[device_id]["disk_usage"] = disk_usage
                self._devices[device_id]["last_heartbeat"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                self._devices[device_id]["status"] = "online"
                return dict(self._devices[device_id])
        return None


store = DeviceStore()
