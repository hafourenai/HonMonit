# Deployment Guide

This document covers deploying HonMonit in a production or long‑running environment.

---

## Architecture Options

### Single Server (Recommended)

```text
[Agent] ──WS──► [Server :8000] ◄──WS── [Dashboard (Browser)]
                                     ◄──HTTP── [curl / API clients]
```

Simplest setup — one machine runs the server, agents connect directly.

### With Reverse Proxy (Production)

```text
[Agent] ──WSS──► [Proxy :443] ──► [Server :8000]
[Browser] ──WSS──► [Proxy :443] ──► [Server :8000]
```

Adds TLS termination and optional authentication at the proxy layer.

---

## Production Server Setup

### 1. System Preparation

```bash
# Create a dedicated user
sudo useradd -r -s /bin/false honmonit

# Create directory structure
sudo mkdir -p /opt/honmonit
sudo chown honmonit:honmonit /opt/honmonit
```

### 2. Deploy the Code

```bash
cd /opt/honmonit
sudo -u honmonit git clone https://github.com/your-org/honmonit.git .
# OR copy the files manually
sudo -u honmonit cp -r /path/to/honmonit/* .

# Create virtual environment
sudo -u honmonit python3 -m venv .venv
sudo -u honmonit .venv/bin/pip install -r requirements.txt
```

### 3. systemd Service

Create `/etc/systemd/system/honmonit-server.service`:

```ini
[Unit]
Description=HonMonit Server
After=network.target

[Service]
Type=simple
User=honmonit
Group=honmonit
WorkingDirectory=/opt/honmonit
ExecStart=/opt/honmonit/.venv/bin/uvicorn server.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> **Note:** `--workers 1` is required. HonMonit uses in‑process state (`ConnectionManager`, `DeviceStore`) that does not synchronise across multiple worker processes.

```bash
sudo systemctl daemon-reload
sudo systemctl enable honmonit-server
sudo systemctl start honmonit-server
sudo systemctl status honmonit-server
```

### 4. Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name honmonit.example.com;

    ssl_certificate     /etc/ssl/certs/honmonit.crt;
    ssl_certificate_key /etc/ssl/private/honmonit.key;

    # REST API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket endpoints
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Static files
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Dashboard
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5. Firewall

```bash
# Allow HTTPS (recommended)
sudo ufw allow 443/tcp

# OR allow direct HTTP (development only)
sudo ufw allow 8000/tcp
```

---

## Windows Server Deployment

### Using NSSM

```powershell
# Install NSSM (chocolatey)
choco install nssm

# Install the service
nssm install HonMonitServer "C:\path\to\python.exe" "-m uvicorn server.main:app --host 0.0.0.0 --port 8000"

# Set working directory
nssm set HonMonitServer AppDirectory "C:\path\to\honmonit"

# Configure auto-restart
nssm set HonMonitServer AppExit Default Restart
nssm set HonMonitServer AppThrottle 5000

# Start
nssm start HonMonitServer
```

### Windows Firewall

```powershell
New-NetFirewallRule -DisplayName "HonMonit Server (TCP 8000)" `
    -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Deploying Agents

### Linux

```bash
# Copy the agent file
scp agent/agent.py user@target-machine:/opt/honmonit-agent.py

# Install dependencies
pip install websockets psutil

# Run as a service
```

Create `/etc/systemd/system/honmonit-agent.service`:

```ini
[Unit]
Description=HonMonit Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/honmonit-agent.py ws://server-ip:8000/ws/agent
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable honmonit-agent
sudo systemctl start honmonit-agent
```

### Windows

```powershell
# Create a scheduled task that runs on startup
$action = New-ScheduledTaskAction -Execute "python.exe" `
    -Argument "C:\path\to\agent.py ws://server-ip:8000/ws/agent"

$trigger = New-ScheduledTaskTrigger -AtStartup -RandomDelay "00:00:30"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "HonMonitAgent" `
    -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
```

---

## TLS / WSS

### Using Caddy (simplest)

```caddyfile
honmonit.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy automatically provisions and renews Let's Encrypt certificates.

### Self-signed (internal)

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Then configure nginx as shown above with `ssl_certificate` and `ssl_certificate_key`.

---

## Monitoring the Deployment

### Logs

```bash
# Server logs
journalctl -u honmonit-server -f

# Agent logs (Linux)
journalctl -u honmonit-agent -f
```

### Health Check

```bash
curl http://localhost:8000/api/devices
# → [{"device_id": "...", "hostname": "...", ...}]
```

### Metrics

The server logs every device online/offline transition. Example:

```
2026-06-06 14:49:11 [INFO] honmonit.server: Agent connected: <uuid> (workstation) — 10.0.0.10
2026-06-06 15:30:00 [INFO] honmonit.server: Device <uuid> (workstation) went offline (no heartbeat for 92s)
```

---

## Performance Considerations

| Resource | Limit | Mitigation |
|----------|-------|------------|
| **Concurrent dashboards** | Unlimited per connection set | Each dashboard receives one broadcast per event |
| **Concurrent agents** | Limited by file descriptors | Each agent = 1 TCP socket; default ulimit 1024 supports ~1000 agents |
| **Pending commands** | No explicit limit | Each pending future is ~200 bytes; cleanup on disconnect prevents leaks |
| **Device store size** | Memory only | ~1 KB per device; 10,000 devices = ~10 MB |
