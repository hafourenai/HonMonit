"""In-memory device store for Sprint 1.

Thread-safe dict that holds registered devices.
No database — restarting the server clears all data.
Agents re-register automatically on reconnect.
"""

import threading
from datetime import datetime, timezone
from typing import Optional


class DeviceStore:
    def __init__(self):
        self._devices: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(self, device_id: str, info: dict) -> dict:
        """Store or overwrite a device entry. Returns the stored snapshot."""
        with self._lock:
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
            return dict(device)

    def get(self, device_id: str) -> Optional[dict]:
        with self._lock:
            d = self._devices.get(device_id)
            return dict(d) if d else None

    def get_all(self) -> list:
        with self._lock:
            return [dict(d) for d in self._devices.values()]

    def mark_offline(self, device_id: str):
        """Set a device's status to offline (no removal — row stays visible)."""
        with self._lock:
            if device_id in self._devices:
                self._devices[device_id]["status"] = "offline"

    def update_heartbeat(
        self, device_id: str, cpu_usage: float, ram_usage: float, disk_usage: float
    ) -> Optional[dict]:
        """Update live resource metrics and set status back to online."""
        with self._lock:
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
