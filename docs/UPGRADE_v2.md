# HonMonit v2 — Critical Features Implementation

This document describes the major upgrades made to HonMonit for production readiness.

## What's New

### 1. SQLite Persistence
- **Device Store**: All device data now persists to SQLite database (`honmonit.db`)
- **Metrics History**: Every heartbeat is saved to the `metrics` table for historical analysis
- **Alert History**: All triggered alerts are logged with timestamps and resolution status
- **Data Survives**: Server restarts no longer lose device registrations or metrics

### 2. JWT Authentication
- **Agent Tokens**: Agents authenticate with JWT tokens on registration
- **Dashboard Tokens**: Dashboard clients can authenticate with API keys (converted to JWT)
- **API Key Management**: Create, revoke, and track API keys in the database
- **Secure by Default**: WebSocket connections now require valid tokens

### 3. TLS/SSL Support
- **Self-Signed Certificates**: Server automatically generates self-signed certs on first run
- **Certificate Location**: Certificates saved to `./certs/honmonit.crt` and `./certs/honmonit.key`
- **WSS Support**: Can use `wss://` instead of `ws://` for encrypted connections
- **Easy Production**: Replace self-signed certs with real certs from Let's Encrypt or your CA

### 4. Alert Thresholds & Notifications
- **Configurable Thresholds**: Set CPU, RAM, disk thresholds per-device
- **Automatic Alerts**: When metrics exceed thresholds, alerts are created and logged
- **Alert History**: `/api/alerts` endpoint lists all triggered alerts
- **Resolution Tracking**: Alerts can be marked as resolved with timestamps

### 5. Metrics History & Time-Series Data
- **30-Second Snapshots**: Every heartbeat captures CPU/RAM/disk at that moment
- **Historical Queries**: `/api/devices/{id}/metrics?hours=24` returns time-series data
- **Trend Analysis**: Frontend can plot CPU/RAM/disk usage over time
- **Configurable Retention**: Set database retention policy (default: unlimited)

## Getting Started

### Prerequisites
- Python 3.9+
- pip
- SQLite (included with Python)

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate TLS certificates (automatic on first run)
# Certificates will be created at ./certs/honmonit.crt and ./certs/honmonit.key

# 3. Configure environment (optional)
# Create a .env file with custom settings:
cat > .env << 'EOF'
# Database
DATABASE_URL=sqlite+aiosqlite:///./honmonit.db

# Security
SECRET_KEY=your-secret-key-change-this-in-production

# Server
PORT=8000

# TLS
TLS_CERT_PATH=./certs/honmonit.crt
TLS_KEY_PATH=./certs/honmonit.key
EOF
```

### Running the Server

```bash
# Option 1: HTTP (development)
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# Option 2: HTTPS (production with TLS)
python -m uvicorn server.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile=./certs/honmonit.crt \
  --ssl-keyfile=./certs/honmonit.key
```

### Running Agents

```bash
# Create agent config
cat > agent/config.json << 'EOF'
{
  "server_url": "ws://localhost:8000/ws/agent",
  "api_key": "your-api-key-here"
}
EOF

# Run agent
python agent/agent.py
```

## API Endpoints

### Device Management

- `GET /api/devices` — List all devices
- `GET /api/devices/{id}/metrics?hours=24` — Get metrics history (default 24h)
- `POST /api/devices/{id}/processes` — Get process list
- `POST /api/devices/{id}/restart` — Restart device (admin only)
- `POST /api/devices/{id}/shutdown` — Shutdown device (admin only)
- `POST /api/devices/{id}/kill` — Kill process (admin only)

### Alerts

- `GET /api/alerts?device_id={id}&resolved={true|false}` — Get alerts
- `POST /api/alerts/{id}/resolve` — Mark alert as resolved

## Database Schema

### devices
- `device_id` (unique) — Agent identifier
- `hostname`, `ip`, `os`, `username` — Device info
- `status` — "online" or "offline"
- `cpu_usage`, `ram_usage`, `disk_usage` — Current metrics
- `last_heartbeat` — Last update timestamp

### metrics
- `device_id` (FK) — Device reference
- `cpu_usage`, `ram_usage`, `disk_usage` — Snapshot values
- `timestamp` — When recorded (indexed for fast queries)

### alerts
- `device_id` (FK) — Device reference
- `alert_type` — "cpu_high", "ram_high", "disk_high", "offline"
- `threshold` — The limit that was exceeded
- `current_value` — Actual value when triggered
- `severity` — "info", "warning", "critical"
- `is_resolved` — Boolean flag
- `triggered_at`, `resolved_at` — Timestamps

### alert_thresholds
- `device_id` (FK) — Device reference
- `metric_type` — "cpu", "ram", or "disk"
- `threshold_value` — Alert when metric > this value
- `is_enabled` — Can disable without deleting

### api_keys
- `key_hash` — SHA256 hash of the key (for secure storage)
- `name` — Human-readable name
- `key_type` — "agent", "dashboard", or "admin"
- `is_active` — Can revoke without deleting
- `last_used` — Track usage

## Authentication Flow

### Agent Registration
1. Agent generates JWT token with `type: "agent"` and `device_id`
2. Agent connects to `/ws/agent` WebSocket
3. Server validates token and registers device
4. Server broadcasts `device_added` to all dashboards

### Dashboard Connection
1. Dashboard client sends API key in Authorization header (optional for now)
2. Dashboard connects to `/ws/dashboard` WebSocket
3. Server broadcasts device updates in real-time

## Security Considerations

### Current Limitations (for development)
- ⚠️ No rate limiting
- ⚠️ CORS allows all origins (configure for production)
- ⚠️ Admin password still hardcoded as `honeyyy` in frontend
- ⚠️ Self-signed TLS certificates (replace with real certs)

### Production Recommendations
1. Set `SECRET_KEY` to a strong random value
2. Use real TLS certificates from Let's Encrypt or your CA
3. Set up reverse proxy (nginx) with rate limiting
4. Configure CORS to specific origins only
5. Implement dashboard authentication UI with API key management
6. Enable database encryption at rest (SQLite native encryption or full-disk)
7. Use environment variables for all secrets (never commit to git)
8. Set up monitoring and alerting for the monitoring system itself

## Migration from v1 (In-Memory)

The new version is **backwards compatible** with v1 agents. Old agents will:
1. Connect and register normally
2. Have their data persisted automatically
3. Start building metrics history from moment of upgrade

No migration script needed — the database is created automatically on first run.

## Next Steps

1. ✅ Database persistence (done)
2. ✅ JWT authentication (done)
3. ✅ TLS/SSL support (done)
4. ✅ Alert thresholds (done)
5. ⏳ Frontend charts (in progress — add Chart.js)
6. ⏳ Alert management UI (pending)
7. ⏳ API key management UI (pending)
8. ⏳ Automated tests (pending)
9. ⏳ Docker deployment (pending)

## Troubleshooting

### Database Issues
```bash
# Reset database (loses all data)
rm honmonit.db

# Check database
sqlite3 honmonit.db ".tables"
```

### Certificate Issues
```bash
# Regenerate certificates
rm -rf certs/
# Certificates will be generated on next server start
```

### Authentication Errors
- Check that `SECRET_KEY` is set consistently
- Verify token is included in WebSocket headers
- Check server logs for JWT validation errors

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/hafourenai/HonMonit
- Issues: https://github.com/hafourenai/HonMonit/issues
