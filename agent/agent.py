#!/usr/bin/env python3
"""HonMonit Agent — Sprint 1.

Collects device identity, connects to the server via WebSocket,
and registers itself. Holds the connection open so the server
knows the device is online.
"""

import os
import sys
import json
import asyncio
import uuid
import socket
import platform

import websockets
import psutil


# ── Info collectors ──────────────────────────────────────────────────────────

def get_device_id() -> str:
    return str(uuid.uuid4())


def get_hostname() -> str:
    return socket.gethostname()


def get_username() -> str:
    try:
        return os.getlogin()
    except Exception:
        import getpass
        return getpass.getuser()


def get_ip() -> str:
    """Obtain the LAN IP by creating a dummy outbound socket."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_os() -> str:
    system = platform.system()
    release = platform.release()
    if system == "Windows":
        return f"Windows {release}"
    if system == "Linux":
        return f"Linux {release}"
    if system == "Darwin":
        return f"macOS {release}"
    return f"{system} {release}"


# ── Process list ──────────────────────────────────────────────────────────────

def get_process_list() -> list:
    """Collect top-100 processes sorted by memory usage descending."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            mem_info = info.get("memory_info")
            mem_mb = mem_info.rss / (1024 * 1024) if mem_info else 0
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "memory_mb": round(mem_mb, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    processes.sort(key=lambda p: p["memory_mb"], reverse=True)
    return processes[:100]


# ── Heartbeat ─────────────────────────────────────────────────────────────────

async def heartbeat_loop(ws, device_id):
    """Send a heartbeat every 30 seconds with system metrics."""
    psutil.cpu_percent(interval=0.1)  # initialize first call delta
    while True:
        await asyncio.sleep(30)
        heartbeat = {
            "type": "heartbeat",
            "device_id": device_id,
            "cpu_usage": psutil.cpu_percent(interval=None),
            "ram_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
        }
        await ws.send(json.dumps(heartbeat))
        print(f"[Agent] Heartbeat — CPU:{heartbeat['cpu_usage']}% "
              f"RAM:{heartbeat['ram_usage']}% "
              f"DISK:{heartbeat['disk_usage']}%")


# ── Main agent loop ──────────────────────────────────────────────────────────

async def main():
    server_url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws/agent"

    device_id = get_device_id()
    register_payload = {
        "type": "register",
        "device_id": device_id,
        "hostname": get_hostname(),
        "username": get_username(),
        "ip": get_ip(),
        "os": get_os(),
    }

    print(f"[Agent] device_id = {device_id}")
    print(f"[Agent] hostname   = {register_payload['hostname']}")
    print(f"[Agent] username   = {register_payload['username']}")
    print(f"[Agent] ip         = {register_payload['ip']}")
    print(f"[Agent] os         = {register_payload['os']}")
    print(f"[Agent] target     = {server_url}")

    while True:
        try:
            async with websockets.connect(server_url) as ws:
                await ws.send(json.dumps(register_payload))
                print(f"[Agent] Registered — starting heartbeat")

                hb_task = asyncio.create_task(heartbeat_loop(ws, device_id))

                try:
                    # Stay connected. The server detects the disconnect
                    # when this loop exits.
                    # Also process incoming commands from the server.
                    async for raw in ws:
                        data = json.loads(raw)
                        if data.get("type") != "command":
                            continue
                        cmd = data.get("command")

                        if cmd == "get_processes":
                            processes = get_process_list()
                            print(f"[Agent] Sending {len(processes)} processes")
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "get_processes",
                                "id": data.get("id"),
                                "success": True,
                                "data": {"processes": processes},
                            }))

                        elif cmd == "restart":
                            print(f"[Agent] Restarting system...")
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "restart",
                                "id": data.get("id"),
                                "success": True,
                                "data": {"message": "System restarting..."},
                            }))
                            await asyncio.sleep(1)
                            if platform.system() == "Windows":
                                os.system("shutdown /r /t 10")
                            else:
                                os.system("shutdown -r +1")

                        elif cmd == "shutdown":
                            print(f"[Agent] Shutting down system...")
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "shutdown",
                                "id": data.get("id"),
                                "success": True,
                                "data": {"message": "System shutting down..."},
                            }))
                            await asyncio.sleep(1)
                            if platform.system() == "Windows":
                                os.system("shutdown /s /t 10")
                            else:
                                os.system("shutdown -h +1")

                        elif cmd == "kill_process":
                            pid = data.get("params", {}).get("pid")
                            if not isinstance(pid, int):
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": False,
                                    "error": "Invalid PID",
                                }))
                                continue
                            try:
                                proc = psutil.Process(pid)
                                proc.terminate()
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                                    proc.wait(timeout=2)
                                print(f"[Agent] Killed PID {pid}")
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": True,
                                    "data": {"pid": pid},
                                }))
                            except psutil.NoSuchProcess:
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": False,
                                    "error": "Process already exited",
                                }))
                            except psutil.AccessDenied:
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": False,
                                    "error": "Access denied",
                                }))
                finally:
                    hb_task.cancel()

        except (websockets.exceptions.ConnectionClosed, OSError) as exc:
            print(f"[Agent] Disconnected: {exc}")
        except KeyboardInterrupt:
            print("\n[Agent] Shutting down")
            break

        print("[Agent] Reconnecting in 5 seconds...")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
