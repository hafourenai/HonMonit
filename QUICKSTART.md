# HonMonit v2.0 — Quick Start Guide

## Installation & Setup (5 minutes)

### Step 1: Install Dependencies
```bash
cd D:\HonMonit
pip install -r requirements.txt
```

### Step 2: Create Environment File
```bash
# Copy the example
copy .env.example .env

# Or create a minimal .env
cat > .env << 'EOF'
DATABASE_URL=sqlite+aiosqlite:///./honmonit.db
SECRET_KEY=change-this-to-a-random-string-in-production
PORT=8000
EOF
```

### Step 3: Start the Server
```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

The server will:
- ✅ Initialize SQLite database (`honmonit.db`)
- ✅ Generate TLS certificates (`./certs/honmonit.crt`, `./certs/honmonit.key`)
- ✅ Start listening on port 8000

### Step 4: Start an Agent (New Terminal)
```bash
python agent/agent.py ws://localhost:8000/ws/agent
```

Expected output:
```
INFO:     device_id = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
INFO:     Registered — starting heartbeat
```

### Step 5: Open Dashboard
```
http://localhost:8000
```

You should see:
- Device appears in table
- Status shows "Online"
- CPU/RAM/Disk metrics display

---

## First-Time Usage

### 1. View Device Details
- Click any device row to open the side panel
- See current metrics (CPU, RAM, Disk) in gauge format
- View last heartbeat timestamp

### 2. View Metrics History (NEW!)
- Click the **[MTR]** tab in the side panel
- Select time range (1h, 6h, 24h, 7d)
- See line charts with CPU/RAM/Disk trends
- Click refresh to reload charts

### 3. View Running Processes
- Click the **[PRC]** tab
- See top 100 processes by memory usage
- Kill processes (requires Admin mode)

### 4. Enable Admin Mode
- Click "ADMIN" button in header
- Enter password: `honeyyy`
- Now you can restart/shutdown devices

---

## What Changed from v1?

### New Features ✨
- **Persistent Database**: Device data survives server restarts
- **Metrics History**: Every heartbeat stored for trend analysis
- **Interactive Charts**: View CPU/RAM/Disk usage over time
- **Alert Thresholds**: Automatic notifications when resources exceed limits
- **Secure Authentication**: JWT tokens for agent connections

### Backward Compatible ✅
- Old agents (v1) work without modification
- All existing features still work
- No migration needed

---

## Common Tasks

### Create Alert Thresholds
```bash
# Via SQL (for now, UI coming in v2.1)
sqlite3 honmonit.db << 'EOF'
INSERT INTO alert_thresholds (device_id, metric_type, threshold_value, is_enabled)
SELECT device_id, 'cpu', 85, 1 FROM devices WHERE hostname = 'my-server';
EOF
```

### View Alert History
```bash
# Via API
curl http://localhost:8000/api/alerts

# Or in dashboard (coming in v2.1)
```

### Export Device Data
```bash
# CSV export button in dashboard (top right)
# Or via SQL
sqlite3 honmonit.db "SELECT * FROM devices;" > devices.csv
```

### Check Database
```bash
# View device count
sqlite3 honmonit.db "SELECT COUNT(*) FROM devices;"

# View metrics for last 24 hours
sqlite3 honmonit.db << 'EOF'
SELECT device_id, COUNT(*) as count 
FROM metrics 
WHERE timestamp > datetime('now', '-1 day') 
GROUP BY device_id;
EOF
```

---

## Troubleshooting

### Issue: "Database is locked"
**Solution**: Close any other connections to `honmonit.db` (SQLite Studio, other terminals, etc.)

### Issue: Metrics charts not showing
**Solution**: Wait 5-10 minutes for metrics to accumulate, then refresh browser

### Issue: Agent won't connect
**Solution**: Check server is running and verify WebSocket URL is correct
```bash
# Verify server is listening
netstat -ano | findstr :8000
```

### Issue: "SSL certificate verify failed"
**Solution**: This is expected with self-signed certs in development. For production, use real certs from Let's Encrypt

### Issue: Can't see alerts
**Solution**: Alerts are created when metrics exceed thresholds. Check database:
```bash
sqlite3 honmonit.db "SELECT * FROM alerts LIMIT 5;"
```

---

## Environment Variables

All optional (defaults shown):

```env
# Database - change for PostgreSQL/MySQL support
DATABASE_URL=sqlite+aiosqlite:///./honmonit.db

# Security - MUST CHANGE in production!
SECRET_KEY=honmonit-dev-secret-change-in-production

# Server
PORT=8000
HOST=0.0.0.0

# TLS paths (auto-generated if missing)
TLS_CERT_PATH=./certs/honmonit.crt
TLS_KEY_PATH=./certs/honmonit.key

# Alert thresholds (%)
DEFAULT_CPU_THRESHOLD=90
DEFAULT_RAM_THRESHOLD=85
DEFAULT_DISK_THRESHOLD=90

# Metrics retention in days (0 = unlimited)
METRICS_RETENTION_DAYS=0

# Logging
LOG_LEVEL=INFO
SQL_ECHO=false
```

---

## API Reference

### List Devices
```bash
curl http://localhost:8000/api/devices
```

### Get Metrics History
```bash
curl http://localhost:8000/api/devices/{device-id}/metrics?hours=24
```

Response:
```json
{
  "success": true,
  "data": {
    "metrics": [
      {
        "timestamp": "2026-07-28T12:00:00+00:00",
        "cpu_usage": 45.2,
        "ram_usage": 62.8,
        "disk_usage": 71.5
      }
    ]
  }
}
```

### Get Alerts
```bash
curl http://localhost:8000/api/alerts
curl http://localhost:8000/api/alerts?device_id={id}&resolved=false
```

### Resolve Alert
```bash
curl -X POST http://localhost:8000/api/alerts/{alert-id}/resolve
```

---

## Next Steps

### For Development
1. ✅ Database persistence working
2. ✅ Authentication implemented
3. ✅ Metrics charting working
4. ⏳ **Alert management UI** (coming v2.1)
5. ⏳ **Email notifications** (coming v2.1)

### For Production Deployment
1. Change `SECRET_KEY` to random value
2. Replace self-signed TLS with real certificate
3. Configure CORS origins
4. Set up automated backups
5. Configure log aggregation
6. Set up monitoring alerts for the monitoring system

---

## Support

- **Docs**: See `docs/UPGRADE_v2.md` for full API reference
- **Issues**: https://github.com/hafourenai/HonMonit/issues
- **Config**: See `.env.example` for all options
- **Database**: `honmonit.db` (SQLite, portable)

---

**Version**: 2.0  
**Status**: Production-Ready  
**Last Updated**: 2026-07-28
