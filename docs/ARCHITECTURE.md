# Architecture Overview

---

## System Context

```text
┌──────────────────┐          WebSocket           ┌──────────────────┐
│                  │ ◄──────────────────────────► │                  │
│  Dashboard       │          wss://host/         │  Server          │
│  (Browser)       │       /ws/dashboard          │  (FastAPI)       │
│                  │                               │                  │
└──────────────────┘                               └────────┬─────────┘
                                                            │
                                           WebSocket        │ REST
                                           /ws/agent        │ /api/devices/…
                                                            │
                                                  ┌─────────▼─────────┐
                                                  │                   │
                                                  │  Agent            │
                                                  │  (Python)         │
                                                  │                   │
                                                  └───────────────────┘
```

The system uses a **hub‑and‑spoke** topology:

- **One server** acts as the central hub — it accepts agent connections, routes commands, and broadcasts device state to all connected dashboards.
- **N agents** (one per monitored machine) maintain a persistent WebSocket connection to the server and send heartbeats every 30 seconds.
- **M dashboards** (browser tabs) subscribe to a separate WebSocket channel and receive real‑time updates.

---

## Data Flow

### Registration & Heartbeat

```text
Agent                           Server                     Dashboard
  │                               │                            │
  │  ── register {device_id,…} ──►│                            │
  │                               │  ── device_added ────────►│
  │                               │                            │
  │  ── heartbeat (30s) ────────►│                            │
  │                               │  ── device_updated ──────►│
  │  ── heartbeat (30s) ────────►│                            │
  │                               │  ── device_updated ──────►│
  │                               │                            │
```

### Command Execution

```text
Dashboard/API                    Server                     Agent
     │                              │                          │
     │  POST /api/devices/{id}/     │                          │
     │  processes/restart/shutdown  │                          │
     │ ──────────────────────────►  │                          │
     │                              │  ── command (id, cmd) ──►│
     │                              │                          │
     │                              │  ◄── command_result ────│
     │  ◄── {success, data} ──────  │                          │
```

---

## WebSocket Lifecycle

### Agent Connection (`/ws/agent`)

```
1. Agent opens WebSocket ───────────────────► Server
2. Agent sends "register" message
3. Server stores agent in ConnectionManager
4. Server broadcasts "device_added" to all dashboards
5. Loop (until disconnect):
     a. Agent sends "heartbeat" every 30 seconds
     b. Server updates device store
     c. Server broadcasts "device_updated" to dashboards
     d. When server sends a command, agent replies with "command_result"
6. On disconnect:
     - Server marks device offline
     - Server cleans up pending command futures
     - Server broadcasts "device_offline" to dashboards
```

### Dashboard Connection (`/ws/dashboard`)

```
1. Dashboard opens WebSocket ────────────► Server
2. Server accepts and adds to dashboard set
3. Loop (until disconnect):
     a. Server pushes broadcast messages (device_added, device_updated, device_offline)
     b. Dashboard receives and updates the UI
4. On disconnect:
     - Server removes dashboard from the set
```

---

## Component Breakdown

### `server/main.py` — Application Entry Point

- FastAPI application with CORS middleware
- REST endpoints for device listing and command dispatch
- WebSocket handlers for agent and dashboard connections
- Background task (`offline_checker`) that marks devices offline after 90 seconds without a heartbeat
- Structured logging on startup and shutdown

### `server/connection_manager.py` — Connection Hub

- Tracks agent WebSockets indexed by `device_id`
- Tracks dashboard WebSockets in a set for broadcast
- Maintains a pending command map: `{cmd_id: {device_id, future}}`
- On agent disconnect, fails all pending futures for that device
- On agent re‑registration, closes the stale WebSocket before storing the new one

### `server/device_store.py` — In‑Memory Device Registry

- `asyncio.Lock`-protected dictionary of device state
- Methods: `register`, `get`, `get_all`, `mark_offline`, `update_heartbeat`, `remove`
- Returns shallow copies to prevent callers from mutating internal state

### `agent/agent.py` — Client Agent

- Collects host identity (hostname, IP, OS, username) on startup
- Persists a stable `device_id` to `.device_id` for identity across restarts
- Connects to the server via WebSocket and registers
- Sends heartbeats every 30 seconds with CPU, RAM, and disk usage
- Listens for commands: `get_processes`, `restart`, `shutdown`, `kill_process`
- Implements exponential backoff reconnection (2‑60 seconds)

### Dashboard — `index.html` + `static/js/app.js`

- Single‑page application, no framework, no build step
- Vanilla JS (ES5 compatible) with IIFE pattern for scope isolation
- WebSocket client with exponential backoff reconnection
- Dynamic device table, detail side panel, gauge SVGs, notification system
- Admin mode toggle that reveals restart/shutdown controls

---

## Resilience Features

| Mechanism | Description |
|-----------|-------------|
| **Exponential backoff** | Agent reconnect delay doubles per attempt (2s base, 60s max) |
| **Dashboard reconnect** | Browser WS reconnects with backoff (1s base, 30s max) |
| **Stale connection close** | Server closes old WebSocket when an agent re‑registers |
| **Pending future cleanup** | Disconnected agent fails all outstanding command futures |
| **Offline detection** | Background checker marks devices offline after 90s without heartbeat |
| **Exception isolation** | Each handler catches its own exceptions; one crash never takes down the server |

---

## Security Boundaries

```
                     Untrusted Network
┌─────────────────────────────────────────────────┐
│                                                 │
│   Agent ──WebSocket──► Server ◄──HTTP── Browser │
│                                                 │
│   × No authentication                           │
│   × CORS allow_origins=["*"]                    │
│   × Commands execute without authorization      │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Current limitations** (documented risks — see audit):
- No authentication or API keys
- CORS allows all origins
- No transport encryption (use a reverse proxy with TLS in production)

---

## Logging Architecture

All server components use the `logging` standard library with the `honmonit.*` namespace:

| Logger | Purpose |
|--------|---------|
| `honmonit.server` | Server lifecycle, device online/offline events |
| `honmonit.connection_manager` | Connection state, pending future cleanup |
| `honmonit.device_store` | Device registration and re‑registration |
| `honmonit.agent` | Agent lifecycle, heartbeat stats, command execution |

Log format: `2026-06-06 14:49:11 [LEVEL] name: message`
