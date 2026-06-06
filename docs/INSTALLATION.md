# Installation Guide

This document walks through setting up the HonMonit server and connecting your first agent.

---

## Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.9 | 3.11+ |
| RAM (server) | 128 MB | 512 MB |
| RAM (agent) | 64 MB | 256 MB |
| Network | TCP port 8000 open | Static IP or DNS name for the server |

### Supported Agent Platforms

- Windows 10 / 11 / Server 2016+
- Linux (kernel 4.15+, any distribution)
- macOS 11+ (Big Sur and later)

---

## Step 1 — Install the Server

### 1a. Clone the repository

```bash
git clone https://github.com/hafourenai/HonMonit.git
cd HonMonit
```

### 1b. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 1c. Install Python packages

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**requirements.txt** includes:
- `fastapi>=0.115.0` — modern async web framework
- `uvicorn[standard]>=0.32.0` — ASGI server (adds `watchfiles` for hot‑reload)
- `websockets>=13.0` — WebSocket protocol implementation
- `psutil>=5.9.0` — system metrics collection (used by the agent)

### 1d. Start the server

```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
2026-06-06 14:49:11 [INFO] honmonit.server: HonMonit server starting — listening on port 8000
INFO:     Application startup complete.
```

Open **http://localhost:8000** in a browser. You will see the empty dashboard.

---

## Step 2 — Install the Agent

### 2a. On the machine to be monitored

Ensure Python 3.9+ and pip are installed, then:

```bash
pip install websockets psutil
```

> The agent package is self‑contained in `agent/agent.py` — no server‑side code needed on the client.

### 2b. Run the agent

```bash
python agent/agent.py ws://<server-ip>:8000/ws/agent
```

Replace `<server-ip>` with the IP address or hostname of the HonMonit server.

**Example:**
```bash
python agent/agent.py ws://192.168.1.100:8000/ws/agent
```

If no URL is provided, the agent defaults to `ws://localhost:8000/ws/agent`:

```bash
python agent/agent.py
```

### 2c. Verify the agent connected

On the server terminal you will see:

```
2026-06-06 14:49:11 [INFO] honmonit.connection_manager: Agent connected: <uuid> (<hostname>) — <ip>
```

On the dashboard the device appears with live CPU, RAM, and disk gauges.

---

## Step 3 — Run as a Service (Optional)

### Linux — systemd

Create `/etc/systemd/system/honmonit-server.service`:

```ini
[Unit]
Description=HonMonit Server
After=network.target

[Service]
Type=simple
User=honmonit
WorkingDirectory=/opt/honmonit
ExecStart=/opt/honmonit/.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable honmonit-server
sudo systemctl start honmonit-server
```

### Windows — NSSM (Non‑Sucking Service Manager)

```powershell
nssm install HonMonitServer "C:\path\to\python.exe" "-m uvicorn server.main:app --host 0.0.0.0 --port 8000"
nssm set HonMonitServer AppDirectory "C:\path\to\honmonit"
nssm start HonMonitServer
```

---

## Step 4 — Network Configuration

If agents are on a different subnet than the server:

1. Configure the server's firewall to allow inbound TCP on port **8000**.
2. Ensure agents can resolve the server hostname (or use the IP directly).
3. For WAN deployments, consider a reverse proxy (see [Deployment Guide](DEPLOYMENT.md)).

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Agent prints "Disconnected" | Server unreachable or port blocked | Verify `ws://<ip>:8000/ws/agent` is reachable; check firewalls |
| Dashboard shows "No devices" | Agent not running or wrong URL | Start agent; verify the URL ends with `/ws/agent` |
| Core DLL / psutil import error | Missing build tools on Windows | Install `psutil` from a pre‑built wheel: `pip install psutil` |
| Port 8000 already in use | Another process on that port | Change port via `--port 8001` or kill the conflicting process |

For more issues, see the [Troubleshooting Guide](TROUBLESHOOTING.md).
