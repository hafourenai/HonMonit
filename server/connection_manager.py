import uuid
import asyncio
import logging

from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger("honmonit.connection_manager")


class ConnectionManager:
    def __init__(self):
        self._agents: dict[str, WebSocket] = {}
        self._dashboards: set[WebSocket] = set()
        self._pending: dict[str, dict] = {}

    async def connect_agent(self, device_id: str, ws: WebSocket):
        old = self._agents.get(device_id)
        if old is not None:
            logger.warning(
                "Agent %s reconnecting — closing old connection", device_id
            )
            try:
                await old.close(code=1000)
            except Exception:
                pass
        self._agents[device_id] = ws

    async def connect_dashboard(self, ws: WebSocket):
        await ws.accept()
        self._dashboards.add(ws)

    def disconnect_agent(self, device_id: str):
        self._agents.pop(device_id, None)
        failed = []
        for cmd_id, entry in list(self._pending.items()):
            if entry.get("device_id") == device_id:
                future = entry["future"]
                if not future.done():
                    future.set_exception(
                        asyncio.TimeoutError("Agent disconnected")
                    )
                failed.append(cmd_id)
        for cmd_id in failed:
            self._pending.pop(cmd_id, None)
        if failed:
            logger.info(
                "Cleaned %d pending command(s) for disconnected agent %s",
                len(failed),
                device_id,
            )

    def disconnect_dashboard(self, ws: WebSocket):
        self._dashboards.discard(ws)

    async def broadcast_dashboard(self, message: dict):
        dead: set[WebSocket] = set()
        for ws in self._dashboards:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._dashboards -= dead

    async def send_command(
        self, device_id: str, command: str, params: dict = None
    ) -> Optional[asyncio.Future]:
        ws = self._agents.get(device_id)
        if not ws:
            return None
        cmd_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = {"device_id": device_id, "future": future}
        msg = {
            "type": "command",
            "id": cmd_id,
            "command": command,
        }
        if params:
            msg["params"] = params
        try:
            await ws.send_json(msg)
        except Exception:
            self._pending.pop(cmd_id, None)
            if not future.done():
                future.set_exception(
                    ConnectionError("Failed to send command")
                )
        return future

    def resolve_command(self, cmd_id: str, result: dict):
        entry = self._pending.pop(cmd_id, None)
        if entry:
            future = entry["future"]
            if not future.done():
                future.set_result(result)


manager = ConnectionManager()
