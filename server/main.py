import os
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.device_store import store
from server.connection_manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("honmonit.server")

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


async def offline_checker():
    while True:
        await asyncio.sleep(30)
        now = datetime.now(timezone.utc)
        for device in await store.get_all():
            if device["status"] != "online":
                continue
            last_hb = device.get("last_heartbeat")
            if not last_hb:
                continue
            try:
                elapsed = (now - datetime.fromisoformat(last_hb)).total_seconds()
            except (ValueError, TypeError):
                continue
            if elapsed > 90:
                device_id = device["device_id"]
                await store.mark_offline(device_id)
                updated = await store.get(device_id)
                if updated:
                    logger.info(
                        "Device %s (%s) went offline (no heartbeat for %.0fs)",
                        device_id, device.get("hostname", "?"), elapsed,
                    )
                    await manager.broadcast_dashboard({
                        "type": "device_offline",
                        "device": updated,
                    })


@app.on_event("startup")
async def startup():
    logger.info(
        "HonMonit server starting — listening on port %s",
        os.environ.get("PORT", "8000"),
    )
    asyncio.create_task(offline_checker())


@app.on_event("shutdown")
async def shutdown():
    logger.info("HonMonit server shutting down")


@app.get("/api/devices")
async def list_devices():
    return await store.get_all()


@app.post("/api/devices/{device_id}/processes")
async def get_device_processes(device_id: str):
    device = await store.get(device_id)
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
        return {"success": False, "error": "Command timed out"}


@app.post("/api/devices/{device_id}/restart")
async def restart_device(device_id: str):
    device = await store.get(device_id)
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
    device = await store.get(device_id)
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
    device = await store.get(device_id)
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


@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE, "index.html"))


@app.websocket("/ws/agent")
async def agent_websocket(ws: WebSocket):
    await ws.accept()
    device_id = None

    try:
        data = await ws.receive_json()
        if data.get("type") != "register":
            await ws.close(code=1003)
            return

        device_id = data["device_id"]
        await manager.connect_agent(device_id, ws)
        device = await store.register(device_id, data)

        logger.info(
            "Agent connected: %s (%s) — %s",
            device_id, device.get("hostname", "?"), device.get("ip", "?"),
        )

        await manager.broadcast_dashboard({
            "type": "device_added",
            "device": device,
        })

        while True:
            data = await ws.receive_json()
            if data.get("type") == "heartbeat":
                device = await store.update_heartbeat(
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
            logger.info("Agent disconnected: %s", device_id)
            await store.mark_offline(device_id)
            manager.disconnect_agent(device_id)
            device = await store.get(device_id)
            if device:
                await manager.broadcast_dashboard({
                    "type": "device_offline",
                    "device": device,
                })

    except Exception:
        logger.exception("Unexpected error in agent WebSocket handler")
        if device_id:
            await store.mark_offline(device_id)
            manager.disconnect_agent(device_id)
            device = await store.get(device_id)
            if device:
                await manager.broadcast_dashboard({
                    "type": "device_offline",
                    "device": device,
                })


@app.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket):
    await manager.connect_dashboard(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(ws)
    except Exception:
        logger.exception("Unexpected error in dashboard WebSocket handler")
        manager.disconnect_dashboard(ws)
