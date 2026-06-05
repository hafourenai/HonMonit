/**
 * HonMonit Dashboard — Sprint 1.
 *
 * On page load:
 *   1. Fetch all devices from GET /api/devices
 *   2. Render device inventory table
 *   3. Open WebSocket to /ws/dashboard
 *   4. Keep the table in sync with device_added / device_offline events
 */
(function () {
    "use strict";

    var API = window.location.origin;
    var WS_URL = API.replace(/^http/, "ws") + "/ws/dashboard";

    var devices = {};
    var selectedDeviceId = null;

    // ── DOM references ─────────────────────────────────────────────────────

    var $ = function (id) { return document.getElementById(id); };

    var deviceTableBody = $("deviceTableBody");

    var sidePanel = $("sidePanel");
    var panelCloseBtn = $("panelCloseBtn");
    var panelDeviceName = $("panelDeviceName");
    var panelStatusDot = $("panelStatusDot");
    var panelSessionUser = $("panelSessionUser");
    var panelCpuModel = $("panelCpuModel");
    var panelRamTotal = $("panelRamTotal");
    var panelOsName = $("panelOsName");
    var panelOsBuild = $("panelOsBuild");
    var panelIpAddress = $("panelIpAddress");
    var panelMacAddress = $("panelMacAddress");
    var panelLastSeen = $("panelLastSeen");
    var panelStatusText = $("panelStatusText");
    var panelCpuCircle = $("panelCpuCircle");
    var panelCpuValue = $("panelCpuValue");
    var panelRamCircle = $("panelRamCircle");
    var panelRamValue = $("panelRamValue");
    var panelDiskCircle = $("panelDiskCircle");
    var panelDiskValue = $("panelDiskValue");

    var panelProcessList = $("panelProcessList");
    var processSearchInput = $("processSearchInput");
    var btnRefresh = $("btnRefresh");

    var statTotal = $("totalDevices");
    var statOnline = $("onlineCount");
    var statOffline = $("offlineCount");

    // ── Helpers ────────────────────────────────────────────────────────────

    function formatHeartbeat(hb) {
        if (!hb) return "\u2014";
        var d = new Date(hb);
        return d.toLocaleTimeString();
    }

    function updateStats() {
        var list = Object.values(devices);
        var total = list.length;
        var onlineList = list.filter(function (d) { return d.status === "online"; });
        var online = onlineList.length;
        var offline = total - online;
        if (statTotal) statTotal.textContent = total;
        if (statOnline) statOnline.textContent = online;
        if (statOffline) statOffline.textContent = offline;

        var avgCpu = online
            ? Math.round(onlineList.reduce(function (s, d) { return s + (d.cpu_usage || 0); }, 0) / online)
            : 0;
        var avgRam = online
            ? Math.round(onlineList.reduce(function (s, d) { return s + (d.ram_usage || 0); }, 0) / online)
            : 0;

        var l = $("avgCpuLabel");
        var b = $("avgCpuBar");
        if (l) l.textContent = avgCpu + "%";
        if (b) b.style.width = avgCpu + "%";

        l = $("avgRamLabel");
        b = $("avgRamBar");
        if (l) l.textContent = avgRam + "%";
        if (b) b.style.width = avgRam + "%";
    }

    function escapeHtml(text) {
        if (!text) return "";
        var d = document.createElement("div");
        d.textContent = String(text);
        return d.innerHTML;
    }

    // ── Notifications ──────────────────────────────────────────────────────

    function showNotification(msg, type) {
        var div = document.createElement("div");
        div.className =
            "fixed top-4 right-4 z-[100] px-4 py-3 rounded-xl text-body-sm font-semibold shadow-lg transition-all duration-300 " +
            (type === "success"
                ? "bg-[#10b981]/90 text-white"
                : "bg-[#f43f5e]/90 text-white");
        div.textContent = msg;
        document.body.appendChild(div);
        setTimeout(function () { div.remove(); }, 4000);
    }

    // ── Kill process ───────────────────────────────────────────────────────

    function doKill(deviceId, pid, name) {
        fetch(API + "/api/devices/" + deviceId + "/kill", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pid: pid }),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showNotification(
                        name + " (PID " + pid + ") terminated successfully",
                        "success"
                    );
                    loadProcesses(deviceId);
                } else {
                    showNotification(
                        "Failed to kill " + name + ": " + (data.error || "Unknown error"),
                        "error"
                    );
                }
            })
            .catch(function () {
                showNotification("Failed to kill " + name + ": Network error", "error");
            });
    }

    // ── Process list ───────────────────────────────────────────────────────

    var _lastProcessList = [];

    function loadProcesses(deviceId) {
        if (!panelProcessList) return;
        panelProcessList.innerHTML =
            '<div class="p-4 text-center text-on-surface-variant text-body-sm">Loading processes...</div>';

        fetch(API + "/api/devices/" + deviceId + "/processes", { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success && data.data && data.data.processes) {
                    _lastProcessList = data.data.processes;
                    renderProcessList(_lastProcessList);
                } else {
                    var errMsg = data.error || "Failed to retrieve process list";
                    panelProcessList.innerHTML =
                        '<div class="p-4 text-center text-[#f43f5e] text-body-sm">' + escapeHtml(errMsg) + "</div>";
                }
            })
            .catch(function () {
                panelProcessList.innerHTML =
                    '<div class="p-4 text-center text-[#f43f5e] text-body-sm">Failed to retrieve process list</div>';
            });
    }

    function renderProcessList(list) {
        if (!panelProcessList) return;
        if (!list || list.length === 0) {
            panelProcessList.innerHTML =
                '<div class="p-4 text-center text-on-surface-variant text-body-sm">No processes found.</div>';
            return;
        }
        var html =
            '<div class="flex items-center justify-between px-3 py-1.5 text-label-caps text-on-surface-variant border-b border-white/5">' +
            '<span class="flex-1">Process Name</span>' +
            '<span class="w-12 text-right">PID</span>' +
            '<span class="w-16 text-right">Memory</span>' +
            '<span class="w-10 text-right">Action</span>' +
            "</div>" +
            '<div class="text-body-sm text-on-surface-variant px-3 py-1">' +
            list.length +
            " processes</div>";
        list.forEach(function (p) {
            var safeName = escapeHtml(p.name);
            html +=
                '<div class="flex items-center justify-between px-3 py-1.5 hover:bg-white/5 rounded text-body-sm">' +
                '<span class="text-on-surface truncate flex-1">' +
                safeName +
                "</span>" +
                '<span class="text-on-surface-variant w-12 text-right font-data-mono">' +
                p.pid +
                "</span>" +
                '<span class="text-on-surface-variant w-16 text-right font-data-mono">' +
                p.memory_mb.toFixed(1) +
                " MB</span>" +
                '<span class="w-10 text-right">' +
                '<button class="text-[10px] font-bold text-[#f43f5e] hover:text-white hover:bg-[#f43f5e] px-1.5 py-0.5 rounded transition-all kill-btn" data-pid="' +
                p.pid +
                '" data-name="' +
                safeName.replace(/"/g, "&quot;") +
                '">Kill</button>' +
                "</span>" +
                "</div>";
        });
        panelProcessList.innerHTML = html;

        // Bind kill buttons
        Array.from(panelProcessList.querySelectorAll(".kill-btn")).forEach(
            function (btn) {
                btn.addEventListener("click", function (e) {
                    e.stopPropagation();
                    var pid = parseInt(this.dataset.pid, 10);
                    var name = this.dataset.name;
                    if (
                        confirm(
                            "Are you sure you want to terminate " +
                                name +
                                " (PID " +
                                pid +
                                ")?"
                        )
                    ) {
                        doKill(selectedDeviceId, pid, name);
                    }
                });
            }
        );
    }

    // ── Device table ───────────────────────────────────────────────────────

    function renderDeviceTable() {
        if (!deviceTableBody) {
            console.error("[HonMonit] deviceTableBody not found");
            return;
        }
        var list = Object.values(devices);
        if (list.length === 0) {
            deviceTableBody.innerHTML =
                '<tr><td colspan="8" class="px-6 py-8 text-center text-on-surface-variant text-body-md">' +
                "No devices connected. Start an agent to see it here.</td></tr>";
            return;
        }

        deviceTableBody.innerHTML = list
            .map(function (d) {
                var selected = d.device_id === selectedDeviceId;
                var rowClass = selected
                    ? "hover:bg-primary/5 cursor-pointer bg-primary/10 transition-colors"
                    : "hover:bg-primary/5 cursor-pointer transition-colors";

                var badgeClass =
                    d.status === "online"
                        ? "bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/30"
                        : "bg-[#f43f5e]/20 text-[#f43f5e] border border-[#f43f5e]/30";

                var cpuWidth = (d.cpu_usage || 0) + "%";
                var ramWidth = (d.ram_usage || 0) + "%";

                return (
                    '<tr class="' +
                    rowClass +
                    '" data-device-id="' +
                    d.device_id +
                    '">' +
                    '<td class="px-6 py-4">' +
                    '<div class="flex items-center gap-3">' +
                    '<span class="material-symbols-outlined text-primary">laptop_mac</span>' +
                    '<span class="text-body-md font-semibold text-on-surface">' +
                    escapeHtml(d.hostname) +
                    "</span>" +
                    "</div>" +
                    "</td>" +
                    '<td class="px-6 py-4 text-body-md text-on-surface-variant">' +
                    escapeHtml(d.username) +
                    "</td>" +
                    '<td class="px-6 py-4 text-data-mono font-data-mono text-on-surface-variant">' +
                    escapeHtml(d.ip) +
                    "</td>" +
                    '<td class="px-6 py-4 text-body-sm text-on-surface-variant">' +
                    escapeHtml(d.os) +
                    "</td>" +
                    '<td class="px-6 py-4">' +
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold ' +
                    badgeClass +
                    '">' +
                    (d.status === "online" ? "ONLINE" : "OFFLINE") +
                    "</span>" +
                    "</td>" +
                    '<td class="px-6 py-4 w-40">' +
                    '<div class="flex flex-col gap-1.5">' +
                    '<div class="flex items-center gap-2">' +
                    '<span class="text-[10px] text-on-surface-variant w-7">CPU</span>' +
                    '<div class="flex-1 h-1 bg-white/10 rounded-full w-full">' +
                    '<div class="h-full bg-primary rounded-full" style="width:' +
                    cpuWidth +
                    '"></div>' +
                    "</div>" +
                    '<span class="text-[10px] text-on-surface-variant w-7 text-right">' +
                    cpuWidth +
                    "</span>" +
                    "</div>" +
                    '<div class="flex items-center gap-2">' +
                    '<span class="text-[10px] text-on-surface-variant w-7">RAM</span>' +
                    '<div class="flex-1 h-1 bg-white/10 rounded-full w-full">' +
                    '<div class="h-full bg-[#fbbf24] rounded-full" style="width:' +
                    ramWidth +
                    '"></div>' +
                    "</div>" +
                    '<span class="text-[10px] text-on-surface-variant w-7 text-right">' +
                    ramWidth +
                    "</span>" +
                    "</div>" +
                    "</div>" +
                    "</td>" +
                    '<td class="px-6 py-4 text-body-sm text-on-surface-variant">' +
                    formatHeartbeat(d.last_heartbeat) +
                    "</td>" +
                    '<td class="px-6 py-4">' +
                    '<button class="p-1.5 hover:bg-white/10 rounded transition-all text-on-surface-variant">' +
                    '<span class="material-symbols-outlined">more_vert</span>' +
                    "</button>" +
                    "</td>" +
                    "</tr>"
                );
            })
            .join("");

        // Bind row clicks
        Array.from(deviceTableBody.querySelectorAll("tr[data-device-id]")).forEach(
            function (row) {
                row.addEventListener("click", function () {
                    var id = row.dataset.deviceId;
                    selectDevice(id);
                    loadProcesses(id);
                });
            }
        );
    }

    // ── Side panel ─────────────────────────────────────────────────────────

    function selectDevice(deviceId) {
        selectedDeviceId = deviceId;
        renderDeviceTable();

        var device = devices[deviceId];
        if (!device) return;

        // Populate basic info
        if (panelDeviceName) panelDeviceName.textContent = device.hostname || "Unknown";

        var dotColor = device.status === "online" ? "#10b981" : "#f43f5e";
        if (panelStatusDot) {
            panelStatusDot.style.background = dotColor;
            panelStatusDot.classList.toggle("status-pulse", device.status === "online");
        }

        if (panelSessionUser)
            panelSessionUser.textContent =
                "Session " +
                (device.status === "online" ? "Active" : "Inactive") +
                " - " +
                (device.username || "Unknown");

        if (panelOsName) panelOsName.textContent = device.os || "Unknown";
        if (panelIpAddress) panelIpAddress.textContent = "IP: " + (device.ip || "0.0.0.0");

        if (panelCpuModel) panelCpuModel.textContent = "CPU: " + (device.cpu_usage || 0) + "%";
        if (panelRamTotal) panelRamTotal.textContent = "RAM: " + (device.ram_usage || 0) + "%";
        if (panelOsBuild) panelOsBuild.textContent = "Disk: " + (device.disk_usage || 0) + "%";
        if (panelMacAddress) panelMacAddress.textContent = "—";

        if (device.last_heartbeat) {
            var lastSeen = new Date(device.last_heartbeat);
            if (panelLastSeen) panelLastSeen.textContent = lastSeen.toLocaleString();
        } else {
            if (panelLastSeen) panelLastSeen.textContent = "Connected";
        }

        if (panelStatusText)
            panelStatusText.textContent =
                device.status === "online"
                    ? "Device is online and connected"
                    : "Device is offline";

        // Update gauge circles
        var circ = 175.9;
        var cpu = device.cpu_usage || 0;
        var ram = device.ram_usage || 0;
        var disk = device.disk_usage || 0;
        if (panelCpuCircle) panelCpuCircle.style.strokeDashoffset = circ - (circ * cpu / 100);
        if (panelCpuValue) panelCpuValue.textContent = cpu + "%";
        if (panelRamCircle) panelRamCircle.style.strokeDashoffset = circ - (circ * ram / 100);
        if (panelRamValue) panelRamValue.textContent = ram + "%";
        if (panelDiskCircle) panelDiskCircle.style.strokeDashoffset = circ - (circ * disk / 100);
        if (panelDiskValue) panelDiskValue.textContent = disk + "%";

        if (sidePanel) sidePanel.classList.remove("translate-x-full");
    }

    // ── WebSocket ──────────────────────────────────────────────────────────

    function connectDashboardWS() {
        console.log("[HonMonit] Connecting WS:", WS_URL);
        var ws = new WebSocket(WS_URL);

        ws.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data);
                switch (data.type) {
                    case "device_added":
                        if (data.device) {
                            console.log("[HonMonit] device_added:", data.device.device_id);
                            devices[data.device.device_id] = data.device;
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === data.device.device_id) {
                                selectDevice(data.device.device_id);
                            }
                        }
                        break;
                    case "device_offline":
                        if (data.device && devices[data.device.device_id]) {
                            console.log("[HonMonit] device_offline:", data.device.device_id);
                            devices[data.device.device_id].status = "offline";
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === data.device.device_id) {
                                selectDevice(data.device.device_id);
                            }
                        }
                        break;
                    case "device_updated":
                        if (data.device && data.device.device_id) {
                            var updated = data.device;
                            devices[updated.device_id] = updated;
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === updated.device_id) {
                                selectDevice(updated.device_id);
                            }
                        }
                        break;
                }
            } catch (err) {
                console.error("WS message error:", err);
            }
        };

        ws.onopen = function () {
            console.log("[HonMonit] WS connected");
        };

        ws.onclose = function () {
            console.log("[HonMonit] WS closed, reconnecting in 3s");
            setTimeout(connectDashboardWS, 3000);
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    // ── Side panel close ───────────────────────────────────────────────────

    if (panelCloseBtn && sidePanel) {
        panelCloseBtn.addEventListener("click", function () {
            sidePanel.classList.add("translate-x-full");
            selectedDeviceId = null;
            renderDeviceTable();
        });
    }

    // ── Search / Refresh ───────────────────────────────────────────────────

    if (processSearchInput) {
        processSearchInput.addEventListener("input", function () {
            var q = this.value.toLowerCase();
            var filtered = _lastProcessList.filter(function (p) {
                return p.name.toLowerCase().indexOf(q) !== -1;
            });
            renderProcessList(filtered);
        });
    }

    if (btnRefresh) {
        btnRefresh.addEventListener("click", function () {
            if (selectedDeviceId) {
                loadProcesses(selectedDeviceId);
            }
        });
    }

    // ── Init ───────────────────────────────────────────────────────────────

    function init() {
        console.log("[HonMonit] init()");
        fetch(API + "/api/devices")
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (list) {
                console.log("[HonMonit] Fetched devices:", list.length);
                devices = {};
                list.forEach(function (d) {
                    devices[d.device_id] = d;
                });
                renderDeviceTable();
                updateStats();
            })
            .catch(function (err) {
                console.error("[HonMonit] Fetch failed:", err);
                renderDeviceTable();
            });

        connectDashboardWS();
    }

    init();
})();
