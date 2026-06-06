# Agentless Device Support — Pengembangan Hybrid

Dokumen ini menjelaskan rencana pengembangan untuk menambahkan dukungan **device tanpa agent** ke HonMonit. Sistem saat ini hanya mendukung device yang menjalankan Python agent (`agent/agent.py`). Dengan pengembangan ini, admin dapat memonitor dan mengontrol device yang tidak bisa atau tidak ingin dipasangi agent.

---

## Status Saat Ini

```text
┌─────────────────────┐         WebSocket          ┌─────────────────────┐
│   Dashboard         │ ◄───────────────────────── │   Server (FastAPI)  │
│   (Browser)         │    /ws/dashboard           │                     │
└─────────────────────┘                            └──────────┬──────────┘
                                                               │ WebSocket
                                                               │ /ws/agent
                                                     ┌─────────▼──────────┐
                                                     │   Agent Python     │
                                                     │   WAJIB dipasang   │
                                                     │   di setiap device │
                                                     └────────────────────┘
```

**Keterbatasan:**
- Setiap device target harus menjalankan `agent/agent.py`
- Device non-Python (router, switch, IoT) tidak bisa dimonitor
- Device yang tidak bisa diinstal Python otomatis tidak terdeteksi

---

## Target Arsitektur Hybrid

```text
┌─────────────────────┐         WebSocket          ┌─────────────────────┐
│   Dashboard         │ ◄───────────────────────── │   Server (FastAPI)  │
│   (Browser)         │    /ws/dashboard           │                     │
└─────────────────────┘                            └──────┬──────┬───────┘
                                                           │      │
                           ┌───────────────────────────────┘      └───────────────┐
                           │ WebSocket /ws/agent           SSH TCP              ICMP
                           ▼                               ▼                     ▼
                  ┌──────────────────┐          ┌──────────────────┐   ┌───────────────┐
                  │  Agent Python    │          │  Device via SSH  │   │  Device via   │
                  │  (existing)      │          │  (baru)          │   │  Ping (baru)  │
                  │  CPU, RAM, Disk  │          │  CPU, RAM, Disk  │   │  Status saja  │
                  │  Process, Ctrl   │          │  Process, Ctrl   │   │               │
                  └──────────────────┘          └──────────────────┘   └───────────────┘
```

---

## Tipe Device

| Tipe | Sumber Data | Koneksi | Metrics | Kontrol | Credential |
|------|-------------|---------|---------|---------|------------|
| `agent` | WebSocket dari agent | Device → Server (outbound) | CPU, RAM, Disk, Process | Restart, Shutdown, Kill | Tidak perlu |
| `ssh` | SSH remote command | Server → Device (outbound) | CPU, RAM, Disk, Process | Restart, Shutdown, Kill | SSH key/password |
| `ping` | ICMP ping | Server → Device (outbound) | Status online/offline saja | Tidak ada | Tidak perlu |

---

## Struktur File

```
honmonit/
├── server/
│   ├── __init__.py                  # package marker
│   ├── main.py                      # [MODIFY] — endpoint + background task baru
│   ├── device_store.py              # [MODIFY] — field type, manual CRUD
│   ├── connection_manager.py        # [MODIFY] — broadcast device_removed
│   ├── ssh_manager.py               # [NEW]    — SSH connection & command execution
│   └── ping_scanner.py              # [NEW]    — ICMP ping checker
├── agent/
│   └── agent.py                     # [UNCHANGED]
├── static/
│   ├── css/style.css                # [MODIFY] — form, tag tipe device
│   └── js/app.js                    # [MODIFY] — add/remove device, type-aware render
├── index.html                       # [MODIFY] — modal Add Device
├── requirements.txt                 # [MODIFY] — +asyncssh
└── README.md                        # [MODIFY] — update dokumentasi
```

---

## Detail Implementasi per Komponen

### 1. `server/device_store.py` — Model Data

**Tambah field baru di dictionary device:**

```python
device = {
    # ── Existing ──
    "device_id":       "uuid-string",
    "hostname":        "pc-01",
    "username":        "admin",
    "ip":              "192.168.1.10",
    "os":              "Linux 6.2",
    "status":          "online" | "offline",
    "cpu_usage":       45.2,
    "ram_usage":       72.1,
    "disk_usage":      33.8,
    "last_heartbeat":  "2026-06-06T12:00:00+00:00",

    # ── Baru ──
    "type":            "agent" | "ssh" | "ping",
    "config": { ... },           # internal, TIDAK di-expose ke API/dashboard
}
```

**Method baru:**

| Method | Fungsi |
|--------|--------|
| `add_manual(type, hostname, ip, config)` | Tambah device SSH/Ping, generate UUID |
| `mark_online(device_id)` | Set status jadi online |
| `update_metrics(device_id, cpu, ram, disk)` | Update metrics (mirip update_heartbeat) |
| `update_config(device_id, config)` | Update konfigurasi SSH |
| `remove(device_id)` | Hapus device dari store (existing, perlu dipastikan) |

**Perubahan di method `register()`:**
- Set `type = "agent"` secara otomatis.

**Keamanan:**
- Method `get()` dan `get_all()` harus **strip field `config`** dari response agar credential SSH tidak bocor ke dashboard.

---

### 2. `server/ssh_manager.py` — File Baru

Class `SSHManager` untuk mengelola koneksi SSH ke device target.

**Koneksi:**
- Koneksi dibuat saat device didaftarkan
- Disimpan dalam connection pool (`dict[str, asyncssh.SSHClient]`)
- Timeout per koneksi: 10 detik
- Reconnect otomatis jika koneksi putus

**Collection metrics via SSH command:**

```text
Metrik          Command Linux                         Command macOS
───────         ─────────────                         ────────────
CPU%            top -bn1 | grep "Cpu(s)"              top -l 1 | grep "CPU usage"
RAM%            free -m | grep Mem                    vm_stat | pages
Disk%           df -h / | tail -1                     df -h / | tail -1
Process list    ps aux --sort=-%mem | head -100       ps aux -r | head -100
```

**Command execution:**

| Aksi | SSH Command |
|------|-------------|
| Restart | `sudo shutdown -r +1` |
| Shutdown | `sudo shutdown -h +1` |
| Kill process | `kill -9 <PID>` |

**Method:**

```python
class SSHManager:
    async def connect(device_id: str, config: dict) -> bool
    async def disconnect(device_id: str)
    async def collect_metrics(device_id: str) -> dict | None
    async def get_processes(device_id: str) -> list[dict] | None
    async def restart(device_id: str) -> dict
    async def shutdown(device_id: str) -> dict
    async def kill_process(device_id: str, pid: int) -> dict
    async def test_connection(host: str, port: int, user: str, password: str | None, key: str | None) -> bool
```

**Dependency:** `asyncssh>=2.14` — ditambahkan ke `requirements.txt`.

---

### 3. `server/ping_scanner.py` — File Baru

Class `PingScanner` untuk deteksi device via ICMP ping.

**Cara kerja:**
- Jalankan ping via `asyncio.create_subprocess_exec()`
- Platform-aware:
  - Windows: `ping -n 1 -w 2000 <ip>`
  - Linux/macOS: `ping -c 1 -W 2 <ip>`
- Parsing return code untuk tentukan online/offline

**Method:**

```python
class PingScanner:
    async def check_device(ip: str) -> bool    # True = alive, False = dead/timeout
    async def check_all(devices: list[dict]) -> dict[str, bool]
```

---

### 4. `server/main.py` — Endpoint & Background Tasks

**Endpoint baru:**

| Method | Path | Fungsi |
|--------|------|--------|
| `POST` | `/api/devices/manual` | Tambah device SSH atau Ping |
| `DELETE` | `/api/devices/{device_id}` | Hapus device |
| `PUT` | `/api/devices/{device_id}` | Update konfigurasi device |
| `POST` | `/api/devices/test-ssh` | Test koneksi SSH sebelum simpan |

**Endpoint existing — dispatch by type:**

Setiap command endpoint perlu logic dispatch:

```python
# Contoh pattern di main.py
async def execute_command(device_id, command, params=None):
    device = await store.get(device_id)
    if not device or device["status"] != "online":
        return {"success": False, "error": "Device unavailable"}

    if device["type"] == "agent":
        # Via WebSocket (existing flow)
        future = await manager.send_command(device_id, command, params)
        ...
    elif device["type"] == "ssh":
        # Via SSHManager
        if command == "restart":
            result = await ssh_manager.restart(device_id)
        elif command == "shutdown":
            result = await ssh_manager.shutdown(device_id)
        elif command == "kill_process":
            result = await ssh_manager.kill_process(device_id, params["pid"])
        elif command == "get_processes":
            processes = await ssh_manager.get_processes(device_id)
            result = {"success": True, "data": {"processes": processes}}
        ...
    elif device["type"] == "ping":
        return {"success": False, "error": "Command not supported for ping devices"}
```

**Background task baru:**

```python
async def ssh_scanner_loop():
    """Setiap 30 detik, collect metrics dari semua device bertipe SSH."""
    while True:
        await asyncio.sleep(30)
        devices = await store.get_all()
        for device in devices:
            if device["type"] != "ssh":
                continue
            metrics = await ssh_manager.collect_metrics(device["device_id"])
            if metrics:
                await store.update_metrics(...)
                await store.mark_online(...)
                broadcast "device_updated"
            else:
                await store.mark_offline(...)
                broadcast "device_offline"

async def ping_scanner_loop():
    """Setiap 30 detik, ping semua device bertipe Ping."""
    while True:
        await asyncio.sleep(30)
        devices = await store.get_all()
        for device in devices:
            if device["type"] != "ping":
                continue
            alive = await ping_scanner.check_device(device["ip"])
            ...
```

**Perubahan `offline_checker` —** Hanya untuk device `type == "agent"` (yang punya heartbeat via WebSocket). Device SSH/Ping di-handle oleh scanner masing-masing.

---

### 5. `static/js/app.js` — Dashboard

**Tambah fungsi:**

| Fungsi | Kegunaan |
|--------|----------|
| `showAddDeviceModal()` | Buka modal untuk tambah device |
| `addManualDevice(data)` | POST `/api/devices/manual` |
| `removeDevice(deviceId)` | DELETE `/api/devices/{id}` + konfirmasi |
| `getDeviceTypeIcon(type)` | Icon beda per tipe (agent/ssh/ping) |
| `canControl(device)` | Cek apakah device bisa dikontrol |

**Perubahan di WebSocket handler:**

```javascript
// Tambah handler baru
case "device_removed":
    delete devices[data.device.device_id];
    renderDeviceTable();
    updateStats();
    break;
```

**Perubahan render device table:**
- Kolom/icon indikator tipe device (misal: 🤖 agent, 🔒 ssh, 📡 ping)
- Untuk device tipe `ping`: metrics CPU/RAM/Disk tampilkan `—`

**Perubahan side panel:**
- Tab Overview: metrics gauges hanya untuk agent/ssh, untuk ping tampilkan "No metrics available"
- Tab Control: hidden untuk ping device

**Modal "Add Device":**
- Dropdown pilih tipe: Agent | SSH | Ping
- Agent: menampilkan info cara install agent
- SSH: form input IP, Port (22), Username, Password / SSH Key
- Ping: form input IP saja

---

### 6. `index.html` — Modal Baru

```html
<!-- Add Device Modal -->
<div id="addDeviceModal" class="modal">
  <div class="modal-content max-w-md">
    <div class="modal-header">
      <h2>Add Device</h2>
      <button class="modal-close-btn">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label>Connection Type</label>
        <select id="deviceType">
          <option value="agent">Agent (Python)</option>
          <option value="ssh">SSH</option>
          <option value="ping">Ping (ICMP)</option>
        </select>
      </div>

      <!-- Agent info -->
      <div id="agentInfo" class="form-section">
        <p class="text-sm text-slate-400">
          To monitor a device via agent, run <code>agent/agent.py</code>
          on the target machine pointing to this server.
        </p>
      </div>

      <!-- SSH form -->
      <div id="sshForm" class="form-section hidden">
        <div class="form-group">
          <label>IP Address</label>
          <input type="text" id="sshIp" placeholder="192.168.1.100">
        </div>
        <div class="form-group">
          <label>Port</label>
          <input type="number" id="sshPort" value="22">
        </div>
        <div class="form-group">
          <label>Username</label>
          <input type="text" id="sshUser" placeholder="root">
        </div>
        <div class="form-group">
          <label>Auth Type</label>
          <select id="sshAuthType">
            <option value="password">Password</option>
            <option value="key">SSH Key</option>
          </select>
        </div>
        <div class="form-group" id="sshPasswordGroup">
          <label>Password</label>
          <input type="password" id="sshPassword">
        </div>
        <div class="form-group hidden" id="sshKeyGroup">
          <label>SSH Private Key (PEM)</label>
          <textarea id="sshKey" rows="5"></textarea>
        </div>
      </div>

      <!-- Ping form -->
      <div id="pingForm" class="form-section hidden">
        <div class="form-group">
          <label>IP Address</label>
          <input type="text" id="pingIp" placeholder="192.168.1.200">
        </div>
      </div>

      <button id="btnTestConnection" class="btn btn-secondary">Test Connection</button>
      <button id="btnSaveDevice" class="btn btn-primary">Add Device</button>
    </div>
  </div>
</div>
```

---

## Matriks Kemampuan per Tipe Device

| Fitur | Agent | SSH | Ping |
|-------|-------|-----|------|
| CPU Usage | ✅ Realtime (30s) | ✅ Via SSH (30s) | ❌ |
| RAM Usage | ✅ Realtime (30s) | ✅ Via SSH (30s) | ❌ |
| Disk Usage | ✅ Realtime (30s) | ✅ Via SSH (30s) | ❌ |
| Process List | ✅ Detail via psutil | ✅ Top 100 via `ps aux` | ❌ |
| Restart | ✅ | ✅ Via `shutdown -r` | ❌ |
| Shutdown | ✅ | ✅ Via `shutdown -h` | ❌ |
| Kill Process | ✅ | ✅ Via `kill -9` | ❌ |
| Cross-network | ✅ (WS outbound) | ⚠️ SSH port harus terbuka | ⚠️ ICMP harus allowed |
| Install di target | ✅ Wajib install Python + agent | ❌ Tidak perlu | ❌ Tidak perlu |
| Credential | ❌ Tidak perlu | ✅ SSH key/password | ❌ Tidak perlu |
| Autodiscovery | ❌ Manual deploy | ❌ Manual daftar | ❌ Manual daftar |

---

## Alur Lengkap per Skenario

### Skenario A: Tambah Device SSH

```
1. Admin buka dashboard
2. Klik "+ Add Device"
3. Pilih "SSH"
4. Isi: IP=192.168.1.50, Port=22, User=root, Password=***
5. Klik "Test Connection"
   ├─ Server SSH ke 192.168.1.50:22
   ├─ Berhasil → toast "Connection successful"
   └─ Gagal   → toast "Connection failed: ..."
6. Klik "Add Device"
   ├─ POST /api/devices/manual {type: "ssh", ip: "...", config: {...}}
   ├─ Server simpan di DeviceStore
   ├─ status = online (jika SSH connect) / offline
   ├─ Broadcast "device_added" via WebSocket
   └─ Dashboard muncul device baru
7. Background ssh_scanner_loop() jalan setiap 30s
   └─ Collect metrics → update store → broadcast
```

### Skenario B: Tambah Device Ping

```
1. Admin buka dashboard
2. Klik "+ Add Device"
3. Pilih "Ping"
4. Isi: IP=192.168.1.100
5. Klik "Add Device"
   ├─ POST /api/devices/manual {type: "ping", ip: "192.168.1.100"}
   ├─ Server simpan di DeviceStore
   ├─ status = online (jika reachable) / offline
   └─ Broadcast "device_added"
6. Background ping_scanner_loop() jalan setiap 30s
   └─ Ping IP → update status → broadcast
```

### Skenario C: Hapus Device

```
1. Admin klik icon hapus di table / side panel
2. Confirm dialog "Remove device ...?"
3. DELETE /api/devices/{device_id}
   ├─ SSH: disconnect koneksi
   ├─ Hapus dari DeviceStore
   └─ Broadcast "device_removed"
4. Dashboard hilang dari table
```

---

## Credential Management SSH

| Opsi | Cara | Kelebihan | Kekurangan |
|------|------|-----------|------------|
| **In-memory** | Simpan di `config` dict dalam DeviceStore | Sederhana, cepat | Hilang jika server restart |
| **Environment** | `SSH_KEY_PATH`, `SSH_DEFAULT_USER` | Persisten, aman | Global, tidak per-device |
| **Encrypted file** | AES encrypt di `config/ssh.json` | Persisten | Tambah dependensi crypto |
| **SSH Agent** | Forward ke SSH agent system | Paling aman | Kompleks, dependensi OS |

**Rekomendasi MVP:** Opsi 1 (in-memory) + Opsi 2 (env var fallback).

---

## Dependensi Baru

**`requirements.txt`:**
```
asyncssh>=2.14
```

---

## Pertimbangan Keamanan

1. **Credential SSH tidak boleh bocor** — field `config` harus distrip sebelum dikirim ke dashboard.
2. **Rate limiting** — batasi jumlah koneksi SSH bersamaan (misal max 10 concurrent).
3. **IP whitelist** — opsi batasi IP mana yang bisa ditambahkan sebagai SSH/Ping device.
4. **Timeout** — setiap koneksi SSH harus punya timeout (10s).
5. **Logging** — semua aktivitas SSH (connect, disconnect, command) harus di-log.
6. **No auth** — sistem saat ini tidak punya autentikasi. SSH credential adalah satu-satunya lapisan keamanan. Jika diperlukan auth di level server, itu pengembangan terpisah.

---

## Batasan yang Perlu Dicatat

1. **SSH hanya untuk Linux/macOS** — Windows memerlukan OpenSSH Server atau PowerShell Remoting (WinRM) yang tidak dicakup di sini.
2. **Ping hanya memberi tahu online/offline** — tidak bisa membedakan antara device mati, network down, atau firewall block ICMP.
3. **Semua device adalah manual register** — tidak ada autodiscovery (ARP scan, mDNS, dll).
4. **Single server** — sistem saat ini tidak punya mekanisme high-availability atau clustering.
5. **In-memory** — semua data hilang jika server restart. Device agent akan re-register otomatis, tapi device SSH/Ping harus ditambahkan ulang.
