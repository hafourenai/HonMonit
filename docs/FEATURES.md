# Features

A complete catalog of HonMonit capabilities.

---

## Device Monitoring

| Feature | Details |
|---------|---------|
| **Real‑time resource gauges** | CPU, RAM, and disk usage displayed as animated SVG circular gauges in the device detail panel |
| **Live heartbeat stream** | Agents push metrics every 30 seconds; server broadcasts to all dashboards |
| **Automatic offline detection** | Server marks devices offline after 90 seconds without a heartbeat |
| **Device status badges** | Visual "Online" / "Offline" badges with coloured status dots in the device table |
| **Aggregate statistics** | Total device count, online/offline counts, average CPU and RAM bars in the header |
| **Heartbeat timestamps** | Last‑seen time displayed for every device in the inventory table |

---

## Remote Command Execution

> **Requires Admin mode** — toggle the shield icon in the top‑right corner.

| Command | Endpoint | Description |
|---------|----------|-------------|
| **Restart** | `POST /api/devices/{id}/restart` | Remotely reboot the target machine |
| **Shutdown** | `POST /api/devices/{id}/shutdown` | Remotely power off the target machine |
| **List Processes** | `POST /api/devices/{id}/processes` | Fetch the top‑100 processes by memory usage |
| **Kill Process** | `POST /api/devices/{id}/kill` | Terminate a specific process by PID |

All commands:
- Return immediately with an error if the device is offline
- Have a **10‑second timeout** — if the agent does not respond in time, the command fails
- Are confirmed by the user before execution (e.g. `confirm("Terminate ...?")`)

---

## Dashboard UI

| Feature | Details |
|---------|---------|
| **Dark theme** | Carefully designed dark colour scheme with CSS custom properties |
| **Responsive layout** | Works on desktop and tablet screens |
| **Sidebar navigation** | Switch between Dashboard and Alerts views |
| **Side panel** | Slide‑out detail panel with four tabs: Overview, Processes, Control, Network |
| **Device search** | Filter the inventory table by hostname, IP, username, or OS |
| **Status filter** | Quickly switch between All / Online / Offline devices |
| **Row actions menu** | Right‑click‑style menu on each device row for Details, Restart, Shutdown |
| **Export CSV** | One‑click download of all device data (UTF‑8 BOM for Excel compatibility) |
| **Keyboard shortcuts** | Toggle sidebar, close panels with overlay click |

---

## Notifications & Alerts

| Feature | Details |
|---------|---------|
| **Toast notifications** | Slide‑in messages for connection events and command results |
| **Notification dropdown** | Scrollable list of recent events (capped at 50) with coloured status dots |
| **Badge indicator** | Unread notification count badge on the bell icon |
| **Alerts page** | Dedicated view with persistent event history |
| **Clear alerts** | One‑click clear of all event history |

---

## Agent Capabilities

| Feature | Details |
|---------|---------|
| **Automatic registration** | Agent sends identity (hostname, IP, OS, username) on connect |
| **Stable device identity** | Device ID persisted to `.device_id` file — survives agent restarts |
| **Exponential backoff reconnection** | 2s → 60s delay between reconnect attempts |
| **Cross‑platform** | Runs on Windows, Linux, and macOS |
| **Heartbeat diagnostics** | Agent logs total heartbeats sent on disconnect |
| **Graceful shutdown** | Catches `Ctrl+C` and logs before exiting |

---

## REST API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the dashboard HTML |
| `GET` | `/api/devices` | List all registered devices |
| `POST` | `/api/devices/{id}/processes` | Get process list from a device |
| `POST` | `/api/devices/{id}/restart` | Restart a device |
| `POST` | `/api/devices/{id}/shutdown` | Shutdown a device |
| `POST` | `/api/devices/{id}/kill` | Kill a process on a device |

All POST commands return `{success: bool, error?: string, data?: object}`.

---

## Infrastructure

| Capability | Description |
|------------|-------------|
| **No database required** | In‑memory device store — server start is always clean |
| **No build step** | Dashboard is plain HTML + JS + CSS — open and go |
| **Single binary deployment** | Server is pure Python; agents are a single file |
| **Structured logging** | ISO‑8601 timestamps, log levels, namespaced loggers |
| **Portable agents** | Only dependency is `websockets` + `psutil` — copy `agent.py` to any machine |
