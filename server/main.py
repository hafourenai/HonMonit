"""HonMonit Server — Sprint 1.

Serves the dashboard UI and provides:
  - GET  /api/devices        — list all registered devices
  - WS   /ws/agent           — agent registration endpoint
  - WS   /ws/dashboard        — real-time push to browser clients
"""

import os
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.device_store import store
from server.connection_manager import manager

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="HonMonit")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")


# ── Offline detection ────────────────────────────────────────────────────────

async def offline_checker():
    """Periodically mark devices offline when no heartbeat for 90 seconds."""
    while True:
        await asyncio.sleep(30)
        now = datetime.now(timezone.utc)
        for device in store.get_all():
            if device["status"] != "online":
                continue
            last_hb = device.get("last_heartbeat")
            if not last_hb:
                continue
            elapsed = (now - datetime.fromisoformat(last_hb)).total_seconds()
            if elapsed > 90:
                device_id = device["device_id"]
                store.mark_offline(device_id)
                updated = store.get(device_id)
                if updated:
                    await manager.broadcast_dashboard({
                        "type": "device_offline",
                        "device": updated,
                    })


@app.on_event("startup")
async def startup():
    asyncio.create_task(offline_checker())


# ── REST — list devices ──────────────────────────────────────────────────────

@app.get("/api/devices")
async def list_devices():
    return store.get_all()


@app.post("/api/devices/{device_id}/processes")
async def get_device_processes(device_id: str):
    device = store.get(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    if device["status"] != "online":
        return {"success": False, "error": "Device is offline"}

    future = await manager.send_command(device_id, "get_processes")
    if not future:
        return {"success": False, "error": "Device is offline"}

    try:
        result = await asyncio.wait_for(future, timeout=10.0)
        return {"success": True, "data": result.get("data", {"processes": []})}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Failed to retrieve process list"}


@app.post("/api/devices/{device_id}/restart")
async def restart_device(device_id: str):
    device = store.get(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    if device["status"] != "online":
        return {"success": False, "error": "Device is offline"}

    future = await manager.send_command(device_id, "restart")
    if not future:
        return {"success": False, "error": "Device is offline"}

    try:
        result = await asyncio.wait_for(future, timeout=10.0)
        resp = {"success": result.get("success", False)}
        if result.get("error"):
            resp["error"] = result["error"]
        if result.get("data"):
            resp["data"] = result["data"]
        return resp
    except asyncio.TimeoutError:
        return {"success": False, "error": "Command timed out"}


@app.post("/api/devices/{device_id}/shutdown")
async def shutdown_device(device_id: str):
    device = store.get(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    if device["status"] != "online":
        return {"success": False, "error": "Device is offline"}

    future = await manager.send_command(device_id, "shutdown")
    if not future:
        return {"success": False, "error": "Device is offline"}

    try:
        result = await asyncio.wait_for(future, timeout=10.0)
        resp = {"success": result.get("success", False)}
        if result.get("error"):
            resp["error"] = result["error"]
        if result.get("data"):
            resp["data"] = result["data"]
        return resp
    except asyncio.TimeoutError:
        return {"success": False, "error": "Command timed out"}


@app.post("/api/devices/{device_id}/kill")
async def kill_device_process(device_id: str, request: Request):
    device = store.get(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    if device["status"] != "online":
        return {"success": False, "error": "Device is offline"}

    body = await request.json()
    pid = body.get("pid")
    if not isinstance(pid, int):
        return {"success": False, "error": "Invalid PID"}

    future = await manager.send_command(device_id, "kill_process", {"pid": pid})
    if not future:
        return {"success": False, "error": "Device is offline"}

    try:
        result = await asyncio.wait_for(future, timeout=10.0)
        resp = {"success": result.get("success", False)}
        if result.get("error"):
            resp["error"] = result["error"]
        if result.get("data"):
            resp["data"] = result["data"]
        return resp
    except asyncio.TimeoutError:
        return {"success": False, "error": "Command timed out"}


# ── Serve the dashboard ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE, "index.html"))


# ── WebSocket — agent endpoint ───────────────────────────────────────────────

@app.websocket("/ws/agent")
async def agent_websocket(ws: WebSocket):
    await ws.accept()
    device_id = None

    try:
        # First message MUST be a register payload
        data = await ws.receive_json()
        if data.get("type") != "register":
            await ws.close(code=1003)
            return

        device_id = data["device_id"]
        await manager.connect_agent(device_id, ws)
        device = store.register(device_id, data)

        # Notify all dashboards
        await manager.broadcast_dashboard({
            "type": "device_added",
            "device": device,
        })

        # Process messages (heartbeats + command results) until disconnect
        while True:
            data = await ws.receive_json()
            if data.get("type") == "heartbeat":
                device = store.update_heartbeat(
                    data["device_id"],
                    data["cpu_usage"],
                    data["ram_usage"],
                    data["disk_usage"],
                )
                if device:
                    await manager.broadcast_dashboard({
                        "type": "device_updated",
                        "device": device,
                    })
            elif data.get("type") == "command_result":
                manager.resolve_command(data.get("id"), data)

    except WebSocketDisconnect:
        if device_id:
            store.mark_offline(device_id)
            manager.disconnect_agent(device_id)
            device = store.get(device_id)
            if device:
                await manager.broadcast_dashboard({
                    "type": "device_offline",
                    "device": device,
                })

    except Exception:
        if device_id:
            store.mark_offline(device_id)
            manager.disconnect_agent(device_id)


# ── WebSocket — dashboard endpoint ───────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket):
    await manager.connect_dashboard(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(ws)
