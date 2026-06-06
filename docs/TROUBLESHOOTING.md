# Troubleshooting Guide

Common issues, their causes, and solutions.

---

## Server Won't Start

### Symptom: `Address already in use` / `Errno 10048`

```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**Cause:** Another process is already listening on port 8000.

**Solutions:**

```bash
# Linux — find and kill the process
sudo lsof -i :8000
kill <PID>

# Windows — find and kill the process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or change the port
python -m uvicorn server.main:app --host 0.0.0.0 --port 8001
```

---

## Agent Won't Connect

### Symptom: Agent repeatedly prints "Disconnected"

```
2026-06-06 14:49:11 [WARNING] honmonit.agent: Disconnected: no host found
```

**Causes and fixes:**

| Check | Command / Action |
|-------|-----------------|
| Server is running? | `curl http://<server-ip>:8000/api/devices` — should return `[]` |
| Port reachable? | `telnet <server-ip> 8000` or `Test-NetConnection <server-ip> -Port 8000` |
| URL correct? | Agent URL must end with `/ws/agent` — e.g. `ws://10.0.0.1:8000/ws/agent` |
| Firewall? | Open TCP port 8000 on the server's firewall |
| DNS resolution? | Use the IP directly if hostname doesn't resolve |

### Symptom: `websockets.exceptions.InvalidURI`

```
websockets.exceptions.InvalidURI: invalid uri ...
```

**Cause:** The WebSocket URL is malformed.

**Fix:** Ensure the URL starts with `ws://` (not `http://`). Correct format:

```
ws://192.168.1.100:8000/ws/agent
```

### Symptom: Agent connects but shows "Disconnected" immediately

```
2026-06-06 14:49:11 [WARNING] honmonit.agent: Disconnected: code = 1003
```

**Cause:** Server rejected the connection — likely the first message was not a valid `register` payload.

**Fix:** Check the agent code; ensure `type: "register"` is the first JSON message sent.

---

## Dashboard Issues

### Symptom: Dashboard loads but shows "No devices found"

```
No devices found. Start an agent to see it here.
```

**Causes:**

1. **No agent is running** — start one on any machine that can reach the server.
2. **Agent cannot reach the server** — check network connectivity (see "Agent Won't Connect" above).
3. **Dashboard WebSocket not connected** — open browser DevTools → Console. Look for WebSocket errors.

### Symptom: Devices appear but don't update

```
CPU / RAM gauges stay at 0%
```

**Cause:** Heartbeats are not reaching the dashboard.

**Check:**

1. Agent logs show heartbeats being sent: `Heartbeat — CPU:23% RAM:45% DISK:12%`
2. Server logs show heartbeats received (enable debug logging if needed)
3. Dashboard WebSocket status is `Open` in DevTools → Network → WS
4. Check for `device_updated` messages in the WebSocket frame viewer

### Symptom: Dashboard WebSocket reconnects infinitely

```
WebSocket connection to 'ws://.../ws/dashboard' failed:
```

**Cause:** Server is unreachable or the WebSocket endpoint is wrong.

**Fix:** Verify the dashboard JS constructs the correct URL:

```
WS_URL = window.location.origin.replace(/^http/, "ws") + "/ws/dashboard"
```

For example, if the dashboard is served at `http://10.0.0.1:8000/`:
- Correct URL: `ws://10.0.0.1:8000/ws/dashboard`

---

## Command Failures

### Symptom: "Device is offline"

```
{"success": false, "error": "Device is offline"}
```

**Causes:**

1. The device was online but hasn't sent a heartbeat for > 90 seconds — `offline_checker` marked it offline.
2. The agent process crashed.
3. Network partition between the agent and the server.
4. The agent reconnected with a different `device_id` (if `.device_id` was deleted).

### Symptom: "Command timed out"

```
{"success": false, "error": "Command timed out"}
```

**Causes:**

1. Agent received the command but took > 10 seconds to respond (e.g., large process list on a slow machine).
2. Agent process is stuck or unresponsive (e.g., a process is hanging on `wait()`).
3. Network latency > 10 seconds round-trip.

**Solutions:**

- Retry the command.
- Check agent logs for clues about slow command execution.
- If this happens frequently, increase the timeout in `server/main.py:86` (change `10.0` to a larger value).

### Symptom: "Failed to retrieve process list"

```
{"success": false, "error": "Failed to retrieve process list"}
```

**Cause:** The agent raised an exception while collecting processes.

**Fix:** Check the agent logs for `psutil` errors. If a specific process causes `AccessDenied`, it is silently skipped by the agent. If all processes fail, ensure the agent has permission to enumerate processes.

Run on the agent machine to verify:

```bash
python -c "import psutil; print(len(list(psutil.process_iter())))"
```

---

## Windows-Specific Issues

### Symptom: `psutil` import error

```
ImportError: DLL load failed while importing psutil
```

**Fix:**

```powershell
# Uninstall and reinstall with a pre-built wheel
pip uninstall psutil -y
pip install psutil

# If issues persist, install Visual C++ Redistributable or use Python from python.org
```

### Symptom: `shutdown` / `restart` command does nothing

**Cause:** The agent may not have sufficient privileges to shut down the system.

**Fix:** Run the agent as Administrator (right‑click → "Run as administrator" or run the script from an elevated command prompt / scheduled task).

---

## Linux-Specific Issues

### Symptom: `psutil.NoSuchProcess` spam in agent logs

**Cause:** Processes that exit between enumeration and data collection.

**Fix:** This is normal — the agent handles it gracefully with `try/except`. If the log volume is too high, adjust the logging level.

### Symptom: `Permission denied` when accessing `/`

**Cause:** The agent is running as a non‑root user and `psutil.disk_usage('/')` requires read access.

**Fix:** Ensure the agent runs with a user that can read the root filesystem stats (most Linux configurations allow this by default).

---

## Logs Reference

### Where to find logs

| Component | Location |
|-----------|----------|
| Server (systemd) | `journalctl -u honmonit-server -f` |
| Server (direct) | stdout / stderr |
| Agent (systemd) | `journalctl -u honmonit-agent -f` |
| Agent (direct) | stdout / stderr |
| Dashboard | Browser DevTools → Console |

### Log format

```
2026-06-06 14:49:11 [INFO] honmonit.server: HonMonit server starting — listening on port 8000
2026-06-06 14:49:11 [INFO] honmonit.connection_manager: Agent connected: <uuid> (<hostname>) — <ip>
2026-06-06 14:49:11 [WARNING] honmonit.connection_manager: Agent <uuid> reconnecting — closing old connection
2026-06-06 14:49:11 [INFO] honmonit.connection_manager: Cleaned 3 pending command(s) for disconnected agent <uuid>
```

---

## Debugging Checklist

1. **Can the server start?** → Run `python -m uvicorn server.main:app --host 0.0.0.0 --port 8000` and look for no errors.
2. **Is the server reachable?** → `curl http://localhost:8000/api/devices` returns `[]` or a JSON array.
3. **Can an agent connect?** → Run the agent with `--verbose` (or check logs) for successful registration.
4. **Does the dashboard work?** → Open `http://localhost:8000` in a browser and verify the page loads.
5. **Are heartbeats flowing?** → Agent logs show `Heartbeat — CPU:...` and server logs show no `offline` events.
6. **Can you run a command?** → Click a device row, open the Processes tab, and click Refresh.
