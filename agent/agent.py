import os
import sys
import json
import asyncio
import uuid
import socket
import platform
import subprocess
import logging

import websockets
import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("honmonit.agent")

DEVICE_ID_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".device_id"
)
RECONNECT_BASE = 2
RECONNECT_MAX = 60


def load_device_id() -> str:
    try:
        with open(DEVICE_ID_FILE, "r") as f:
            val = f.read().strip()
            if val:
                return val
    except (FileNotFoundError, OSError):
        pass
    val = str(uuid.uuid4())
    try:
        with open(DEVICE_ID_FILE, "w") as f:
            f.write(val)
    except OSError:
        pass
    return val


def get_hostname() -> str:
    return socket.gethostname()


def get_username() -> str:
    try:
        return os.getlogin()
    except Exception:
        import getpass
        return getpass.getuser()


def get_ip() -> str:
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


def get_process_list() -> list:
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


async def heartbeat_loop(ws, device_id, hb_stats: dict):
    psutil.cpu_percent(interval=0.1)
    while True:
        await asyncio.sleep(30)
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
        except Exception as exc:
            logger.warning("Failed to collect metrics: %s", exc)
            continue

        heartbeat = {
            "type": "heartbeat",
            "device_id": device_id,
            "cpu_usage": cpu,
            "ram_usage": ram,
            "disk_usage": disk,
        }
        try:
            await ws.send(json.dumps(heartbeat))
            hb_stats["sent"] += 1
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Heartbeat failed — connection closed")
            break
        except Exception as exc:
            logger.warning("Heartbeat send failed: %s", exc)
            break


async def main():
    server_url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws/agent"

    device_id = load_device_id()
    register_payload = {
        "type": "register",
        "device_id": device_id,
        "hostname": get_hostname(),
        "username": get_username(),
        "ip": get_ip(),
        "os": get_os(),
    }

    logger.info("device_id = %s", device_id)
    logger.info("hostname   = %s", register_payload["hostname"])
    logger.info("username   = %s", register_payload["username"])
    logger.info("ip         = %s", register_payload["ip"])
    logger.info("os         = %s", register_payload["os"])
    logger.info("target     = %s", server_url)

    attempt = 0

    while True:
        try:
            async with websockets.connect(server_url) as ws:
                attempt = 0
                await ws.send(json.dumps(register_payload))
                logger.info("Registered — starting heartbeat")

                hb_stats = {"sent": 0}
                hb_task = asyncio.create_task(
                    heartbeat_loop(ws, device_id, hb_stats)
                )

                try:
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError as exc:
                            logger.warning("Invalid JSON from server: %s", exc)
                            continue

                        if data.get("type") != "command":
                            continue
                        cmd = data.get("command")

                        if cmd == "get_processes":
                            processes = get_process_list()
                            logger.info(
                                "Sending %d processes", len(processes)
                            )
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "get_processes",
                                "id": data.get("id"),
                                "success": True,
                                "data": {"processes": processes},
                            }))

                        elif cmd == "restart":
                            logger.info("Restarting system...")
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "restart",
                                "id": data.get("id"),
                                "success": True,
                            }))
                            await asyncio.sleep(1)
                            if platform.system() == "Windows":
                                subprocess.run(["shutdown", "/r", "/t", "0"])
                            else:
                                subprocess.run(["shutdown", "-r", "+0"])

                        elif cmd == "shutdown":
                            logger.info("Shutting down system...")
                            await ws.send(json.dumps({
                                "type": "command_result",
                                "command": "shutdown",
                                "id": data.get("id"),
                                "success": True,
                            }))
                            await asyncio.sleep(1)
                            if platform.system() == "Windows":
                                subprocess.run(["shutdown", "/s", "/t", "0"])
                            else:
                                subprocess.run(["shutdown", "-h", "+0"])

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
                                if platform.system() == "Windows":
                                    subprocess.run(
                                        ["taskkill", "/f", "/pid", str(pid)],
                                        capture_output=True, timeout=5,
                                    )
                                else:
                                    subprocess.run(
                                        ["kill", "-9", str(pid)],
                                        capture_output=True, timeout=5,
                                    )
                                logger.info("Killed PID %d", pid)
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": True,
                                    "data": {"pid": pid},
                                }))
                            except subprocess.TimeoutExpired:
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": False,
                                    "error": "Command timed out",
                                }))
                            except Exception as exc:
                                await ws.send(json.dumps({
                                    "type": "command_result",
                                    "command": "kill_process",
                                    "id": data.get("id"),
                                    "success": False,
                                    "error": str(exc),
                                }))
                finally:
                    hb_task.cancel()
                    try:
                        await hb_task
                    except asyncio.CancelledError:
                        pass
                    logger.info(
                        "Heartbeat stats: %d sent", hb_stats["sent"]
                    )

        except (websockets.exceptions.ConnectionClosed, OSError) as exc:
            logger.warning("Disconnected: %s", exc)
        except KeyboardInterrupt:
            logger.info("Shutting down")
            break

        attempt += 1
        delay = min(RECONNECT_BASE * 2 ** (attempt - 1), RECONNECT_MAX)
        logger.info(
            "Reconnecting in %ds (attempt %d)...", delay, attempt
        )
        await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(main())
