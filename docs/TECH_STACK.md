# Technology Stack

---

## Server

| Technology | Version | Purpose | Why |
|-----------|---------|---------|-----|
| **Python** | 3.9+ | Runtime | Ubiquitous, excellent async support, large standard library |
| **FastAPI** | 0.115+ | Web framework | Native async support, automatic WebSocket integration, lightweight, excellent performance |
| **Uvicorn** | 0.32+ | ASGI server | Production‑ready, supports WebSocket upgrades, graceful shutdown |
| **websockets** | 13.0+ | Protocol | Low‑level WebSocket client for the agent; FastAPI uses it internally for the server |
| **asyncio** | stdlib | Concurrency | Single‑threaded async I/O; no GIL contention for I/O‑bound workloads |

### Why FastAPI over alternatives?

| Criterion | FastAPI | Flask | Django |
|-----------|---------|-------|--------|
| Native WebSocket | ✅ Built‑in | ❌ Extension needed | ❌ Channels required |
| Async request handlers | ✅ | ❌ (limited) | ✅ (3.1+) |
| Startup time | < 100 ms | < 50 ms | > 1 s |
| Memory footprint | ~30 MB | ~20 MB | ~60 MB |
| Learning curve | Low | Low | High |
| Built‑in validation | ✅ Pydantic | ❌ | ✅ DRF |

---

## Agent

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.9+ | Cross‑platform runtime |
| **websockets** | 13.0+ | WebSocket client — persistent connection to server |
| **psutil** | 5.9+ | System metrics — CPU, RAM, disk, process enumeration, process termination |

### Why psutil?

- Single library for Windows, Linux, and macOS — same API on every platform
- Provides process iteration with filtering (`NoSuchProcess`, `AccessDenied`, `ZombieProcess`)
- CPU measurement that accounts for idle time correctly via `cpu_percent(interval=…)`

---

## Dashboard

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Vanilla JavaScript** | ES5 | No transpilation, no build step, runs in every browser |
| **CSS3** | — | Custom properties for theming, flexbox/grid for layout, SVG for gauges |
| **Google Fonts** | — | Inter (UI) + JetBrains Mono (metrics), Material Symbols (icons) |

### Why no framework?

- **Zero build step** — open `index.html` directly or serve it; no Webpack, Vite, or npm
- **Tiny payload** — 820 lines of JS + 1670 lines of CSS + HTML; total < 60 KB
- **Universal compatibility** — ES5 runs on every browser including legacy Edge and older mobile browsers
- **Simpler debugging** — no source maps, no virtual DOM, no framework‑specific errors
- **Perfectly adequate** — the dashboard is a single view with a handful of interactions; React/Vue would be over‑engineering

---

## Transport

| Protocol | Where | Why |
|----------|-------|-----|
| **WebSocket** | Agent ↔ Server, Dashboard ↔ Server | Persistent full‑duplex channel; server pushes updates without polling |
| **HTTP REST** | Dashboard ↔ Server (commands) | Request‑response pattern fits command dispatch naturally; no state needed |

### Why not pure WebSocket for everything?

Commands are request‑response with an expected structure:

```
Browser  ──POST──► Server ──ws.send──► Agent
         ◄──JSON─── Server ◄──ws.send─── Agent
```

Using REST for the command trigger keeps the API discoverable, testable with `curl`, and compatible with any HTTP client.

---

## Infrastructure

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Database** | None (in‑memory) | No persistence requirements; agents re‑register on reconnect |
| **Caching** | None | State is in‑memory; broadcasts are immediate |
| **Reverse proxy** | Optional (nginx / Caddy) | For TLS termination and WAN deployments |
| **Process manager** | systemd / NSSM | Auto‑restart on crash |
| **Monitoring** | Built‑in logging | Structured logs to stdout; pipe to systemd journal or file |

---

## Development Tools

| Tool | Purpose |
|------|---------|
| **Python** `‑m py_compile` | Syntax verification during development |
| **Node.js** `node -c` | JS syntax check |
| **Live reload** | `uvicorn --reload` for automatic server restart on file changes |
| **curl** | API testing: `curl http://localhost:8000/api/devices` |
