<div align="center">
  <br/>
  <h1>HonMonit</h1>
  <p><strong>Real‑time PC Monitoring &amp; Remote Control</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square&logo=python" alt="Python 3.9+"/>
    <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/WebSocket-realtime-4fc08d?style=flat-square" alt="WebSocket"/>
    <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License"/>
  </p>
  <br/>
</div>

**HonMonit** is a lightweight, self-hosted system for monitoring and managing remote Windows / Linux / macOS machines from a single browser dashboard. Agents collect system metrics in real time and relay them to a central server, while the web UI provides live resource gauges, process management, and one‑click remote commands — restart, shutdown, and kill unresponsive processes.

---

## At a Glance

| Layer | Technology | Role |
|-------|-----------|------|
| **Server** | Python + FastAPI + Uvicorn | REST API, WebSocket hub, in‑memory device store |
| **Agent** | Python + websockets + psutil | Metrics collector, command executor, heartbeat sender |
| **Dashboard** | Vanilla JS (ES5) + CSS3 | Responsive dark‑theme UI, no build step required |
| **Transport** | WebSocket (full‑duplex) | Real‑time push for metrics and command results |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# 3. Launch an agent on any machine that can reach the server
python agent/agent.py ws://<server-ip>:8000/ws/agent

# 4. Open the dashboard
# → http://<server-ip>:8000
```

---

## Repository

```text
honmonit/
├── agent/            # Agent — runs on monitored machines
├── server/           # FastAPI server — REST + WebSocket endpoints
├── static/           # Frontend assets (CSS, JS)
├── docs/             # Project documentation
├── index.html        # Single‑page dashboard
└── requirements.txt  # Python dependencies
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/INSTALLATION.md) | Step‑by‑step setup for server and agents |
| [Architecture Overview](docs/ARCHITECTURE.md) | System design, data flow, WebSocket lifecycle |
| [Features List](docs/FEATURES.md) | Complete catalog of capabilities |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Directory layout and module responsibilities |
| [Technology Stack](docs/TECH_STACK.md) | Framework and library decisions |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment with systemd / NSSM |
| [Troubleshooting Guide](docs/TROUBLESHOOTING.md) | Common issues and solutions |

---

## Use Cases

- **IT Administrators** — Monitor fleet resource usage, detect runaway processes, and reboot machines remotely.
- **Lab Environments** — Keep an eye on compute nodes without requiring SSH or RDP access to every machine.
- **Home Labs** — Track CPU, RAM, and disk on your homelab servers from a single pane of glass.
- **Development & Testing** — Quickly verify agent behaviour across platforms without complex observability stacks.

---

## License

This project is provided under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with Python, FastAPI, WebSockets, and psutil.</sub>
</div>
