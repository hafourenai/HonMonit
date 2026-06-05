"""WebSocket connection manager for Sprint 1.

Agents are indexed by device_id so the server can route commands later.
Dashboards are a set — every dashboard receives all broadcast events.
"""

import uuid
import asyncio
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._agents: dict[str, WebSocket] = {}
        self._dashboards: set[WebSocket] = set()
        self._pending: dict[str, asyncio.Future] = {}

    async def connect_agent(self, device_id: str, ws: WebSocket):
        self._agents[device_id] = ws

    async def connect_dashboard(self, ws: WebSocket):
        await ws.accept()
        self._dashboards.add(ws)

    def disconnect_agent(self, device_id: str):
        self._agents.pop(device_id, None)

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

    async def send_command(self, device_id: str, command: str, params: dict = None) -> asyncio.Future:
        """Send a command to an agent and return a Future for the result."""
        ws = self._agents.get(device_id)
        if not ws:
            return None
        cmd_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future
        msg = {
            "type": "command",
            "id": cmd_id,
            "command": command,
        }
        if params:
            msg["params"] = params
        await ws.send_json(msg)
        return future

    def resolve_command(self, cmd_id: str, result: dict):
        future = self._pending.pop(cmd_id, None)
        if future and not future.done():
            future.set_result(result)


manager = ConnectionManager()
