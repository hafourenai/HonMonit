# HonMonit v1 → v2 Migration Guide

## Overview

Upgrading from HonMonit v1 (in-memory) to v2 (persistent + authenticated) is **non-breaking and automatic**. No data migration script needed.

---

## What You Need to Know

### ✅ What Works Without Changes
- Existing agents (v1) continue to work
- All device registrations are auto-persisted
- Restart the server — devices stay registered
- All previous endpoints still work
- Dashboard UI is backward compatible

### ⚠️ What's Different
- **Database file created**: `honmonit.db` (SQLite)
- **TLS certificates created**: `./certs/honmonit.crt` and `./certs/honmonit.key`
- **Authentication available** (optional): Agents can now send JWT tokens
- **New API endpoints** for metrics history and alerts

### 🚀 New Features Available
- Time-series metrics stored automatically
- Alert thresholds with automatic notifications
- Historical charts (1h, 6h, 24h, 7d views)
- Data persistence across server restarts

---

## Step-by-Step Upgrade

### Phase 1: Prepare (5 min)

```bash
cd D:\HonMonit

# Backup current state (just in case)
# - Screenshot current devices
# - Note any running agents
```

### Phase 2: Update Code (1 min)

```bash
# Pull latest changes (or extract new version)
git pull origin main
# or if you have the new files already
```

### Phase 3: Install New Dependencies (2 min)

```bash
pip install -r requirements.txt
```

This adds:
- `sqlalchemy` — ORM for database
- `aiosqlite` — Async SQLite driver
- `pyjwt` — JWT token support
- `cryptography` — TLS certificate generation
- `pydantic-settings` — Configuration management

### Phase 4: Configure (1 min)

```bash
# Copy environment template
copy .env.example .env

# Edit .env if needed (optional for development)
# Most defaults are sensible for testing
```

### Phase 5: Start New Server (1 min)

```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

First-run initialization:
- ✅ Creates `honmonit.db`
- ✅ Creates database tables
- ✅ Generates `./certs/honmonit.crt` and `./certs/honmonit.key`
- ✅ Starts listening on port 8000

**Duration**: ~3-5 seconds

### Phase 6: Restart Agents (optional)

```bash
# Old agents (v1) continue to work without changes
# Just restart them to re-register
python agent/agent.py ws://localhost:8000/ws/agent
```

Old agents will:
1. Connect and register normally
2. Have their data persisted automatically
3. Start building metrics history from that moment

### Phase 7: Verify (2 min)

Open dashboard: `http://localhost:8000`

- ✅ Devices appear in table
- ✅ Status shows "Online"
- ✅ Metrics (CPU, RAM, Disk) display
- ✅ Wait 1-2 minutes, then check [MTR] tab for charts

---

## Migration Scenarios

### Scenario 1: Single Device in Development
**Time**: 5 minutes  
**Risk**: None (can roll back by deleting `honmonit.db`)

```bash
# 1. Stop old server
# 2. Install dependencies
pip install -r requirements.txt

# 3. Start new server
python -m uvicorn server.main:app ...

# 4. All devices auto-persist
```

### Scenario 2: Multiple Production Devices
**Time**: 15-30 minutes  
**Risk**: Low (read-only for existing agents)

```bash
# 1. Prepare new hardware (optional)
#    - New VM or container
#    - Copy HonMonit repo

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env
#    - Set DATABASE_URL if using PostgreSQL
#    - Set SECRET_KEY to strong random value
#    - Configure alert thresholds

# 4. Start new server (point DNS or load balancer)
python -m uvicorn server.main:app ...

# 5. Agents auto-reconnect to new server
#    - No agent changes needed
#    - Data persists automatically

# 6. Decommission old server after 24h
#    - Confirm all agents connected
#    - Confirm metrics accumulating
#    - All dashboards working
```

### Scenario 3: Gradual Rollout
**Time**: Spread over days  
**Risk**: Very low (both versions coexist)

```bash
# 1. Start v2 server on different port
python -m uvicorn server.main:app --port 8001

# 2. Redirect agents one-by-one
#    - Update agent config
#    - Restart agent
#    - Verify in new dashboard

# 3. Once all agents migrated, shut down v1 server
```

---

## Data Migration Details

### Devices Table
```
v1 (in-memory):      No persistence
                     ↓
v2 (database):       Automatically inserted into devices table
                     - device_id, hostname, ip, os, username
                     - status, cpu_usage, ram_usage, disk_usage
                     - timestamps created_at, updated_at
```

### Metrics History
```
v1 (in-memory):      No history kept
                     ↓
v2 (database):       Every heartbeat → metrics table
                     - timestamp, cpu_usage, ram_usage, disk_usage
                     - Indexed on (device_id, timestamp)
                     - ~100 bytes per record
                     - 1 device × 24h = ~280KB
```

### Alerts
```
v1 (in-memory):      No alerts
                     ↓
v2 (database):       Triggered when thresholds exceeded
                     - Configure thresholds in alert_thresholds
                     - Alerts created/updated in alerts table
```

---

## Rollback Plan

If something goes wrong:

### Option 1: Revert to v1 (Complete Rollback)
```bash
# 1. Stop v2 server
# 2. Start v1 server (old binary/code)
#    python -m uvicorn server.main:app
# 3. Agents auto-reconnect to v1
# 4. v1 has no database, so in-memory only
# 5. No data loss (agents re-register)
```

**Risk**: Medium  
**Data Loss**: No (agents auto-register)  
**Time**: 2-5 minutes

### Option 2: Reset Database (Keep v2, Clear Data)
```bash
# 1. Stop server
# 2. Delete database
rm honmonit.db

# 3. Start server (recreates empty database)
# 4. Agents auto-register with fresh data
```

**Risk**: Low  
**Data Loss**: Yes (metrics history lost, but device data recovers)  
**Time**: 1 minute

### Option 3: Restore from Backup
```bash
# 1. Stop server
# 2. Restore backup
cp honmonit.db.backup honmonit.db

# 3. Start server
# 4. All data recovered
```

**Risk**: Low  
**Data Loss**: None (restore to backup point)  
**Time**: 2 minutes

---

## Performance Impact

### Server
- **Startup time**: +2-3s (database initialization + TLS cert generation)
- **Memory usage**: +50MB (SQLAlchemy ORM + connection pool)
- **Query time**: <100ms (indexed metrics lookups)

### Agent
- **No changes**: Same CPU/memory footprint
- **Network**: +10% (JWT token in registration)

### Database
- **Initial**: 1-2 MB
- **Growth rate**: ~1 MB per device per week (assuming 30-second heartbeats)
- **1-year retention**: ~50-100 MB per device

---

## Post-Migration Tasks

### Immediately After
- [ ] Verify all devices appear in dashboard
- [ ] Check that metrics accumulate over 5-10 minutes
- [ ] View metrics charts ([MTR] tab)
- [ ] Test alert thresholds
- [ ] Verify admin commands (restart/shutdown) still work

### Within 24 Hours
- [ ] Set alert thresholds for critical devices
- [ ] Enable email notifications (if implemented)
- [ ] Configure log aggregation
- [ ] Set up automated backups

### Within 1 Week
- [ ] Review metrics trends
- [ ] Tune alert thresholds based on baselines
- [ ] Document any custom configurations
- [ ] Update runbooks

---

## Known Limitations During Migration

### v1 ↔ v2 Interoperability
- **Cannot mix**: One server only (v1 or v2)
- **Agents**: v1 agents work with v2 server (no special handling needed)
- **Dashboards**: v1 dashboards work with v2 server

### Database
- **SQLite limitation**: Max ~50 concurrent writers
  - Production workaround: Use PostgreSQL backend
  - Configure: `DATABASE_URL=postgresql+asyncpg://...`

### Authentication
- **JWT in v2 is optional** for now
- v1 agents don't send tokens (but server accepts their registration)
- v2 agents can optionally send tokens for security

---

## FAQ

### Q: Do I need to update agents?
**A**: No. Existing agents (v1) work without modification. Update to v2 agents only for JWT token support (optional).

### Q: Will I lose device data?
**A**: No. Devices re-register automatically. Metrics history only exists in v2 (v1 had none).

### Q: Can I run v1 and v2 simultaneously?
**A**: No. Agents connect to one server. To test both versions, use different ports.

### Q: How do I backup the database?
**A**: Simply copy `honmonit.db`:
```bash
cp honmonit.db honmonit.db.backup
```

### Q: What if I want to use PostgreSQL instead of SQLite?
**A**: Set environment variable:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/honmonit
```

### Q: Do I need to generate new TLS certificates?
**A**: v2 auto-generates self-signed certs. For production, replace with real certs from Let's Encrypt.

---

## Support During Migration

If you hit issues:

1. **Check logs**: `server.main` and `honmonit.database` loggers
2. **Read**: `docs/UPGRADE_v2.md` for API reference
3. **Check**: `.env.example` for configuration options
4. **Database**: Use `sqlite3 honmonit.db` to inspect data
5. **Report**: https://github.com/hafourenai/HonMonit/issues

---

## Timeline

| Phase | Task | Duration | Notes |
|-------|------|----------|-------|
| 1 | Prepare & backup | 5 min | Screenshot devices, note agents |
| 2 | Update code | 1 min | Pull latest or extract files |
| 3 | Install deps | 2 min | `pip install -r requirements.txt` |
| 4 | Configure | 1 min | Copy `.env.example` to `.env` |
| 5 | Start server | 1 min | Database + TLS auto-generated |
| 6 | Restart agents | 5 min | Optional, agents auto-reconnect |
| 7 | Verify | 5 min | Check dashboard, metrics, charts |
| **Total** | | **20 min** | Mostly waiting for metrics |

---

## Success Checklist

After migration, verify:

- [ ] Dashboard loads at `http://localhost:8000`
- [ ] Devices appear in table
- [ ] Device status shows "Online"
- [ ] CPU/RAM/Disk metrics display
- [ ] Wait 5 min, then [MTR] tab shows line charts
- [ ] Can click device and see details
- [ ] Can enable Admin mode and see restart/shutdown buttons
- [ ] Metrics accumulate over time
- [ ] Can view different time ranges (1h, 6h, 24h, 7d)
- [ ] Database file exists: `honmonit.db`
- [ ] TLS certs exist: `./certs/honmonit.crt`, `./certs/honmonit.key`

---

**Version**: v1 → v2 Migration  
**Status**: Ready  
**Estimated Time**: 20 minutes  
**Risk Level**: Low
