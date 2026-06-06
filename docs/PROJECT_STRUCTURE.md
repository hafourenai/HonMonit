# Project Structure

```text
honmonit/
├── agent/                        # Agent — deployed on each monitored machine
│   ├── agent.py                  #   Main agent entrypoint
│   └── .device_id                #   (auto‑generated) Persistent device UUID
│
├── server/                       # Server — FastAPI application
│   ├── __init__.py               #   (implicit package)
│   ├── main.py                   #   Application entry: routes, WebSocket handlers,
│                                 #     offline checker, startup/shutdown hooks
│   ├── connection_manager.py     #   WebSocket registry, command routing,
│                                 #     pending future management, broadcast
│   └── device_store.py           #   In‑memory device repository with async lock
│
├── static/                       # Frontend — served at /static/
│   ├── css/
│   │   └── style.css             #   Dark theme (1670 lines), responsive layout,
│   │                             #     gauge SVGs, animation keyframes
│   └── js/
│       └── app.js                #   Dashboard client (vanilla JS, 820 lines)
│
├── docs/                         # Project documentation
│   ├── ARCHITECTURE.md           #   System design and data flow
│   ├── DEPLOYMENT.md             #   Production deployment guide
│   ├── FEATURES.md               #   Complete feature catalog
│   ├── INSTALLATION.md           #   Setup guide for server and agents
│   ├── PROJECT_STRUCTURE.md      #   This file
│   ├── SCREENSHOTS.md            #   Visual tour of the dashboard
│   ├── TECH_STACK.md             #   Technology decisions
│   └── TROUBLESHOOTING.md        #   Common issues and solutions
│
├── index.html                    # Single‑page dashboard served at /
├── requirements.txt              # Python dependencies
└── README.md                     # Project overview
```

---

## Module Ownership

| Module | Lines | Responsibilities |
|--------|-------|------------------|
| `server/main.py` | 260 | FastAPI app, CORS, REST endpoints (5), WebSocket handlers (2), offline checker background task, startup/shutdown lifecycle |
| `server/connection_manager.py` | 99 | Agent registry (`dict[device_id → WebSocket]`), dashboard set, pending command map, broadcast, stale connection close, future cleanup |
| `server/device_store.py` | 68 | Async‑safe device CRUD, heartbeat update, status management |
| `agent/agent.py` | 284 | Device identity, metrics collection, WebSocket lifecycle, command execution, exponential backoff reconnection, heartbeat loop |
| `static/js/app.js` | 822 | DOM manipulation, WebSocket client, device table rendering, side panel, process list, notifications, modals, CSV export |
| `static/css/style.css` | 1670 | Full dark theme, responsive grid, animated gauges, component styles, utility classes |
| `index.html` | 490 | Semantic HTML structure for dashboard, side panel, modals, row actions |

---

## Data Dependencies

```text
main.py
  ├── device_store.py    (store — device CRUD)
  ├── connection_manager.py  (manager — WebSocket hub)
  │     └── FastAPI WebSocket
  └── index.html / static/
        └── app.js       (dashboard client)
              └── style.css

agent.py
  ├── websockets         (client library)
  └── psutil             (system metrics)
```

No external database, no message queue, no cache layer. The entire system runs in‑process with zero infrastructure dependencies beyond Python.
