import os
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import init_db, AsyncSessionLocal
from server.device_store_db import DeviceStore
from server.connection_manager import manager
from server.auth import verify_token, extract_token_from_header
from server.tls import TLSManager

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


async def get_device_store(db: AsyncSession = Depends(lambda: AsyncSessionLocal())) -> DeviceStore:
    """Get device store instance."""
    return DeviceStore(db)


async def verify_agent_token(authorization: str = Header(None)) -> dict:
    """Verify agent API token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    payload = verify_token(token)
    if not payload or payload.get("type") != "agent":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload


async def verify_dashboard_token(authorization: str = Header(None)) -> dict:
    """Verify dashboard API token (optional for now, but logged)."""
    if authorization:
        token = extract_token_from_header(authorization)
        if token:
            payload = verify_token(token)
            if payload and payload.get("type") == "dashboard":
                return payload
    return {"type": "dashboard", "sub": "anonymous"}


async def offline_checker(db: AsyncSession):
    """Check for offline devices and mark them accordingly."""
    while True:
        await asyncio.sleep(30)
        try:
            async with AsyncSessionLocal() as session:
                store = DeviceStore(session)
                devices = await store.get_all()
                now = datetime.now(timezone.utc)
                
                for device in devices:
                    if device["status"] != "online":
                        continue
                    
                    last_hb = device.get("last_heartbeat")
                    if not last_hb:
                        continue
                    
                    try:
                        last_hb_dt = datetime.fromisoformat(last_hb)
                        elapsed = (now - last_hb_dt).total_seconds()
                    except (ValueError, TypeError):
                        continue
                    
                    if elapsed > 90:
                        device_id = device["device_id"]
                        await store.mark_offline(device_id)
                        updated = await store.get(device_id)
                        
                        if updated:
                            logger.info(
                                "Device %s (%s) went offline (no heartbeat for %.0fs)",
                                device_id,
                                device.get("hostname", "?"),
                                elapsed,
                            )
                            await manager.broadcast_dashboard({
                                "type": "device_offline",
                                "device": updated,
                            })
        except Exception as e:
            logger.error("Error in offline checker: %s", e)


@app.on_event("startup")
async def startup():
    logger.info("HonMonit server starting...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize TLS
    tls_manager = TLSManager()
    tls_manager.ensure_certificates()
    
    # Start background tasks
    asyncio.create_task(offline_checker(AsyncSessionLocal()))
    
    logger.info(
        "HonMonit server ready — listening on port %s",
        os.environ.get("PORT", "8000"),
    )


@app.on_event("shutdown")
async def shutdown():
    logger.info("HonMonit server shutting down")


@app.get("/api/devices")
async def list_devices(
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """List all devices."""
    store = DeviceStore(db)
    return await store.get_all()


@app.post("/api/devices/{device_id}/processes")
async def get_device_processes(
    device_id: str,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Get processes for a device."""
    store = DeviceStore(db)
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
async def restart_device(
    device_id: str,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Restart a device."""
    store = DeviceStore(db)
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
async def shutdown_device(
    device_id: str,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Shutdown a device."""
    store = DeviceStore(db)
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
async def kill_device_process(
    device_id: str,
    request: Request,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Kill a process on a device."""
    store = DeviceStore(db)
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


@app.get("/api/devices/{device_id}/metrics")
async def get_device_metrics(
    device_id: str,
    hours: int = 24,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Get metrics history for a device."""
    store = DeviceStore(db)
    device = await store.get(device_id)
    
    if not device:
        return {"success": False, "error": "Device not found"}
    
    metrics = await store.get_metrics_history(device_id, hours=hours)
    return {"success": True, "data": {"metrics": metrics}}


@app.get("/api/alerts")
async def get_alerts(
    device_id: str = None,
    resolved: bool = None,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Get alerts."""
    store = DeviceStore(db)
    alerts = await store.get_alerts(device_id=device_id, resolved=resolved)
    return {"success": True, "data": {"alerts": alerts}}


@app.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    dashboard_token: dict = Depends(verify_dashboard_token),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
):
    """Resolve an alert."""
    store = DeviceStore(db)
    await store.resolve_alert(alert_id)
    return {"success": True}


@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE, "index.html"))


@app.websocket("/ws/agent")
async def agent_websocket(ws: WebSocket, db: AsyncSession = Depends(lambda: AsyncSessionLocal())):
    """WebSocket endpoint for agents."""
    await ws.accept()
    device_id = None

    try:
        data = await ws.receive_json()
        if data.get("type") != "register":
            await ws.close(code=1003)
            return

        device_id = data["device_id"]
        
        # Verify agent token if provided
        token = data.get("token")
        if token:
            payload = verify_token(token)
            if not payload or payload.get("type") != "agent":
                await ws.close(code=1008, reason="Invalid token")
                return

        await manager.connect_agent(device_id, ws)
        
        store = DeviceStore(db)
        device = await store.register(device_id, data)

        logger.info(
            "Agent connected: %s (%s) — %s",
            device_id,
            device.get("hostname", "?"),
            device.get("ip", "?"),
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
                
                # Check thresholds and create alerts
                await store.check_thresholds_and_create_alerts(device_id)
                
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
            store = DeviceStore(db)
            await store.mark_offline(device_id)
            manager.disconnect_agent(device_id)
            device = await store.get(device_id)
            if device:
                await manager.broadcast_dashboard({
                    "type": "device_offline",
                    "device": device,
                })

    except Exception as e:
        logger.exception("Unexpected error in agent WebSocket handler: %s", e)
        if device_id:
            store = DeviceStore(db)
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
    """WebSocket endpoint for dashboards."""
    await manager.connect_dashboard(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(ws)
    except Exception as e:
        logger.exception("Unexpected error in dashboard WebSocket handler: %s", e)
        manager.disconnect_dashboard(ws)
