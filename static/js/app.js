(function () {
    "use strict";

    var API = window.location.origin;
    var WS_URL = API.replace(/^http/, "ws") + "/ws/dashboard";

    var devices = {};
    var selectedDeviceId = null;
    var currentFilter = "all";
    var searchQuery = "";
    var isAdminMode = false;
    var deviceNotifications = [];

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

    function showNotification(msg, type) {
        var div = document.createElement("div");
        var bg = type === "success" ? "bg-emerald-500" : "bg-red-500";
        div.className = "fixed top-4 right-4 z-[110] px-4 py-3 rounded-xl text-sm font-semibold shadow-lg text-white transition-all duration-300 " + bg;
        div.textContent = msg;
        document.body.appendChild(div);
        setTimeout(function () { div.style.opacity = "0"; setTimeout(function () { div.remove(); }, 300); }, 3500);
    }

    function addNotificationEvent(title, desc, type) {
        deviceNotifications.unshift({ title: title, desc: desc, type: type, time: new Date().toLocaleTimeString() });
        if (deviceNotifications.length > 20) deviceNotifications.pop();
        renderNotifications();
        var badge = $("notifBadge");
        if (badge) badge.style.display = "block";
    }

    function renderNotifications() {
        var list = $("notifList");
        if (!list) return;
        if (deviceNotifications.length === 0) {
            list.innerHTML = '<div class="px-3 py-4 text-center text-slate-400 text-sm">No recent events.</div>';
            return;
        }
        var html = "";
        deviceNotifications.forEach(function (n) {
            var dot = n.type === "online" ? "bg-emerald-500" : n.type === "offline" ? "bg-red-500" : "bg-blue-500";
            html += '<div class="flex items-start gap-3 px-3 py-2.5 hover:bg-slate-50 rounded-lg text-sm">' +
                '<div class="w-2 h-2 rounded-full ' + dot + ' mt-1.5 shrink-0"></div>' +
                '<div><p class="text-slate-700 font-medium">' + escapeHtml(n.title) + '</p>' +
                '<p class="text-xs text-slate-400">' + escapeHtml(n.desc) + ' \u2022 ' + n.time + '</p></div></div>';
        });
        list.innerHTML = html;
    }

    function doKill(deviceId, pid, name) {
        fetch(API + "/api/devices/" + deviceId + "/kill", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pid: pid }),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showNotification(name + " (PID " + pid + ") terminated successfully", "success");
                    loadProcesses(deviceId);
                } else {
                    showNotification("Failed to kill " + name + ": " + (data.error || "Unknown error"), "error");
                }
            })
            .catch(function () {
                showNotification("Failed to kill " + name + ": Network error", "error");
            });
    }

    function doRestartDevice(deviceId) {
        fetch(API + "/api/devices/" + deviceId + "/restart", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (d.success) showNotification("Restart command sent to device", "success");
                else showNotification("Restart failed: " + (d.error || "Unknown"), "error");
            })
            .catch(function () { showNotification("Restart failed: Network error", "error"); });
    }

    function doShutdownDevice(deviceId) {
        fetch(API + "/api/devices/" + deviceId + "/shutdown", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (d.success) showNotification("Shutdown command sent to device", "success");
                else showNotification("Shutdown failed: " + (d.error || "Unknown"), "error");
            })
            .catch(function () { showNotification("Shutdown failed: Network error", "error"); });
    }

    var _lastProcessList = [];

    function loadProcesses(deviceId) {
        if (!panelProcessList) return;
        panelProcessList.innerHTML = '<div class="p-4 text-center text-slate-400 text-sm">Loading processes...</div>';

        fetch(API + "/api/devices/" + deviceId + "/processes", { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success && data.data && data.data.processes) {
                    _lastProcessList = data.data.processes;
                    renderProcessList(_lastProcessList);
                } else {
                    panelProcessList.innerHTML = '<div class="p-4 text-center text-red-500 text-sm">' + escapeHtml(data.error || "Failed") + "</div>";
                }
            })
            .catch(function () {
                panelProcessList.innerHTML = '<div class="p-4 text-center text-red-500 text-sm">Failed to retrieve process list</div>';
            });
    }

    function renderProcessList(list) {
        if (!panelProcessList) return;
        if (!list || list.length === 0) {
            panelProcessList.innerHTML = '<div class="p-4 text-center text-slate-400 text-sm">No processes found.</div>';
            return;
        }
        var html = '<div class="flex items-center justify-between px-3 py-1.5 text-xs font-semibold text-slate-400 border-b border-slate-100">' +
            '<span class="flex-1">Process Name</span>' +
            '<span class="w-12 text-right">PID</span>' +
            '<span class="w-16 text-right">Memory</span>' +
            '<span class="w-10 text-right">Action</span></div>' +
            '<div class="text-xs text-slate-400 px-3 py-1">' + list.length + " processes</div>";
        list.forEach(function (p) {
            var safeName = escapeHtml(p.name);
            html += '<div class="flex items-center justify-between px-3 py-1.5 hover:bg-slate-50 rounded text-sm">' +
                '<span class="text-slate-700 truncate flex-1">' + safeName + "</span>" +
                '<span class="text-slate-400 w-12 text-right font-mono">' + p.pid + "</span>" +
                '<span class="text-slate-400 w-16 text-right font-mono">' + p.memory_mb.toFixed(1) + " MB</span>" +
                '<span class="w-10 text-right">' +
                '<button class="text-[10px] font-bold text-red-500 hover:text-white hover:bg-red-500 px-1.5 py-0.5 rounded transition-all kill-btn" data-pid="' + p.pid + '" data-name="' + safeName.replace(/"/g, "&quot;") + '">Kill</button></span></div>';
        });
        panelProcessList.innerHTML = html;

        Array.from(panelProcessList.querySelectorAll(".kill-btn")).forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var pid = parseInt(this.dataset.pid, 10);
                var name = this.dataset.name;
                if (confirm("Terminate " + name + " (PID " + pid + ")?")) {
                    doKill(selectedDeviceId, pid, name);
                }
            });
        });
    }

    function getFilteredDevices() {
        var list = Object.values(devices);
        if (currentFilter === "online") list = list.filter(function (d) { return d.status === "online"; });
        else if (currentFilter === "offline") list = list.filter(function (d) { return d.status === "offline"; });
        if (searchQuery) {
            var q = searchQuery.toLowerCase();
            list = list.filter(function (d) {
                return (d.hostname && d.hostname.toLowerCase().indexOf(q) !== -1) ||
                       (d.ip && d.ip.toLowerCase().indexOf(q) !== -1) ||
                       (d.username && d.username.toLowerCase().indexOf(q) !== -1) ||
                       (d.os && d.os.toLowerCase().indexOf(q) !== -1);
            });
        }
        return list;
    }

    function renderDeviceTable() {
        if (!deviceTableBody) return;
        var list = getFilteredDevices();
        if (list.length === 0) {
            deviceTableBody.innerHTML = '<tr><td colspan="8" class="px-5 py-8 text-center text-slate-400 text-sm">' +
                "No devices found. Start an agent to see it here.</td></tr>";
            return;
        }

        deviceTableBody.innerHTML = list.map(function (d) {
            var selected = d.device_id === selectedDeviceId;
            var rowClass = selected
                ? "hover:bg-blue-50 cursor-pointer bg-blue-50/60 transition-colors"
                : "hover:bg-slate-50 cursor-pointer transition-colors";

            var badgeClass = d.status === "online"
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-red-50 text-red-700 border border-red-200";

            var cpuWidth = (d.cpu_usage || 0) + "%";
            var ramWidth = (d.ram_usage || 0) + "%";

            return '<tr class="' + rowClass + '" data-device-id="' + d.device_id + '">' +
                '<td class="px-5 py-3"><div class="flex items-center gap-3">' +
                '<span class="material-symbols-outlined text-blue-500">laptop_mac</span>' +
                '<span class="text-sm font-semibold text-slate-700">' + escapeHtml(d.hostname) + "</span></div></td>" +
                '<td class="px-5 py-3 text-sm text-slate-500">' + escapeHtml(d.username) + "</td>" +
                '<td class="px-5 py-3 text-sm font-mono text-slate-500">' + escapeHtml(d.ip) + "</td>" +
                '<td class="px-5 py-3 text-sm text-slate-500">' + escapeHtml(d.os) + "</td>" +
                '<td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ' + badgeClass + '">' +
                (d.status === "online" ? "ONLINE" : "OFFLINE") + "</span></td>" +
                '<td class="px-5 py-3 w-44"><div class="flex flex-col gap-1">' +
                '<div class="flex items-center gap-2"><span class="text-[10px] text-slate-400 w-6">CPU</span>' +
                '<div class="flex-1 h-1.5 bg-slate-100 rounded-full"><div class="h-full bg-blue-500 rounded-full" style="width:' + cpuWidth + '"></div></div>' +
                '<span class="text-[10px] text-slate-400 w-7 text-right">' + (d.cpu_usage || 0) + "%</span></div>" +
                '<div class="flex items-center gap-2"><span class="text-[10px] text-slate-400 w-6">RAM</span>' +
                '<div class="flex-1 h-1.5 bg-slate-100 rounded-full"><div class="h-full bg-amber-500 rounded-full" style="width:' + ramWidth + '"></div></div>' +
                '<span class="text-[10px] text-slate-400 w-7 text-right">' + (d.ram_usage || 0) + "%</span></div></div></td>" +
                '<td class="px-5 py-3 text-sm text-slate-400">' + formatHeartbeat(d.last_heartbeat) + "</td>" +
                '<td class="px-5 py-3"><button class="row-more-btn p-1 hover:bg-slate-100 rounded transition-all text-slate-400 hover:text-slate-600" data-device-id="' + d.device_id + '">' +
                '<span class="material-symbols-outlined text-[18px]">more_vert</span></button></td></tr>';
        }).join("");

        Array.from(deviceTableBody.querySelectorAll("tr[data-device-id]")).forEach(function (row) {
            row.addEventListener("click", function (e) {
                if (e.target.closest(".row-more-btn")) return;
                var id = row.dataset.deviceId;
                selectDevice(id);
                loadProcesses(id);
            });
        });

        Array.from(deviceTableBody.querySelectorAll(".row-more-btn")).forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var id = this.dataset.deviceId;
                showRowActions(this, id);
            });
        });
    }

    var activeRowMenu = null;

    function showRowActions(btn, deviceId) {
        hideRowActions();
        var menu = $("rowActionsMenu");
        if (!menu) return;
        var rect = btn.getBoundingClientRect();
        menu.style.left = Math.min(rect.left - 80, window.innerWidth - 180) + "px";
        menu.style.top = rect.bottom + 4 + "px";
        menu.classList.add("active");
        menu.dataset.deviceId = deviceId;
        activeRowMenu = menu;

        var adminItems = menu.querySelectorAll(".admin-only");
        adminItems.forEach(function (el) {
            el.style.display = isAdminMode ? "flex" : "none";
        });
    }

    function hideRowActions() {
        if (activeRowMenu) {
            activeRowMenu.classList.remove("active");
            activeRowMenu = null;
        }
    }

    document.addEventListener("click", function (e) {
        if (!e.target.closest(".row-more-btn") && !e.target.closest("#rowActionsMenu")) {
            hideRowActions();
        }
    });

    function selectDevice(deviceId) {
        selectedDeviceId = deviceId;
        renderDeviceTable();

        var device = devices[deviceId];
        if (!device) return;

        if (panelDeviceName) panelDeviceName.textContent = device.hostname || "Unknown";

        var dotColor = device.status === "online" ? "#10b981" : "#ef4444";
        if (panelStatusDot) {
            panelStatusDot.style.background = dotColor;
            panelStatusDot.classList.toggle("status-pulse", device.status === "online");
        }

        if (panelSessionUser)
            panelSessionUser.textContent = "Session " + (device.status === "online" ? "Active" : "Inactive") + " - " + (device.username || "Unknown");

        if (panelOsName) panelOsName.textContent = device.os || "Unknown";
        if (panelIpAddress) panelIpAddress.textContent = "IP: " + (device.ip || "0.0.0.0");

        if (panelCpuModel) panelCpuModel.textContent = "CPU: " + (device.cpu_usage || 0) + "%";
        if (panelRamTotal) panelRamTotal.textContent = "RAM: " + (device.ram_usage || 0) + "%";
        if (panelOsBuild) panelOsBuild.textContent = "Disk: " + (device.disk_usage || 0) + "%";
        if (panelMacAddress) panelMacAddress.textContent = "\u2014";

        if (device.last_heartbeat) {
            if (panelLastSeen) panelLastSeen.textContent = new Date(device.last_heartbeat).toLocaleString();
        } else {
            if (panelLastSeen) panelLastSeen.textContent = "Connected";
        }

        if (panelStatusText)
            panelStatusText.textContent = device.status === "online" ? "Device is online and connected" : "Device is offline";

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

    var _wsReconnectAttempt = 0;
    var WS_RECONNECT_BASE = 1000;
    var WS_RECONNECT_MAX = 30000;

    function connectDashboardWS() {
        var ws = new WebSocket(WS_URL);

        ws.onmessage = function (event) {
            _wsReconnectAttempt = 0;
            try {
                var data = JSON.parse(event.data);
                switch (data.type) {
                    case "device_added":
                        if (data.device) {
                            devices[data.device.device_id] = data.device;
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === data.device.device_id) selectDevice(data.device.device_id);
                            addNotificationEvent("Device Connected", data.device.hostname + " (" + data.device.ip + ")", "online");
                        }
                        break;
                    case "device_offline":
                        if (data.device && devices[data.device.device_id]) {
                            devices[data.device.device_id].status = "offline";
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === data.device.device_id) selectDevice(data.device.device_id);
                            addNotificationEvent("Device Offline", data.device.hostname + " went offline", "offline");
                        }
                        break;
                    case "device_updated":
                        if (data.device && data.device.device_id) {
                            devices[data.device.device_id] = data.device;
                            renderDeviceTable();
                            updateStats();
                            if (selectedDeviceId === data.device.device_id) selectDevice(data.device.device_id);
                        }
                        break;
                }
            } catch (err) {
                console.error("WS message error:", err);
            }
        };

        ws.onclose = function () {
            var delay = Math.min(
                WS_RECONNECT_BASE * Math.pow(2, _wsReconnectAttempt),
                WS_RECONNECT_MAX
            );
            _wsReconnectAttempt++;
            setTimeout(connectDashboardWS, delay);
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    if (panelCloseBtn && sidePanel) {
        panelCloseBtn.addEventListener("click", function () {
            sidePanel.classList.add("translate-x-full");
            selectedDeviceId = null;
            renderDeviceTable();
        });
    }

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
            if (selectedDeviceId) loadProcesses(selectedDeviceId);
        });
    }

    var globalSearch = $("globalSearch");
    if (globalSearch) {
        globalSearch.addEventListener("input", function () {
            searchQuery = this.value;
            renderDeviceTable();
        });
    }

    var btnAdminMode = $("btnAdminMode");
    var adminModeLabel = $("adminModeLabel");
    if (btnAdminMode) {
        btnAdminMode.addEventListener("click", function () {
            isAdminMode = !isAdminMode;
            if (isAdminMode) {
                btnAdminMode.classList.remove("bg-blue-50", "text-blue-700", "border-blue-200");
                btnAdminMode.classList.add("bg-blue-600", "text-white", "border-blue-600");
                if (adminModeLabel) adminModeLabel.textContent = "Admin ON";
                showNotification("Admin mode enabled", "success");
            } else {
                btnAdminMode.classList.add("bg-blue-50", "text-blue-700", "border-blue-200");
                btnAdminMode.classList.remove("bg-blue-600", "text-white", "border-blue-600");
                if (adminModeLabel) adminModeLabel.textContent = "Admin Mode";
                showNotification("Admin mode disabled", "success");
            }
            hideRowActions();
        });
    }

    var btnNotifications = $("btnNotifications");
    var notifDropdown = $("notifDropdown");
    var notifBadge = $("notifBadge");

    if (btnNotifications && notifDropdown) {
        btnNotifications.addEventListener("click", function (e) {
            e.stopPropagation();
            notifDropdown.classList.toggle("active");
            if (notifBadge) notifBadge.style.display = "none";
        });
        document.addEventListener("click", function (e) {
            if (!e.target.closest("#btnNotifications") && !e.target.closest("#notifDropdown")) {
                notifDropdown.classList.remove("active");
            }
        });
    }

    initModal("btnSettings", "settingsModal");

    initModal("btnHelp", "helpModal");

    initModal("btnSupport", "supportModal");

    function initModal(triggerId, modalId) {
        var trigger = $(triggerId);
        var modal = $(modalId);
        if (!trigger || !modal) return;
        trigger.addEventListener("click", function () {
            modal.classList.add("active");
        });
        var closeBtns = modal.querySelectorAll(".modal-close-btn");
        closeBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                modal.classList.remove("active");
            });
        });
        modal.addEventListener("click", function (e) {
            if (e.target === modal) modal.classList.remove("active");
        });
    }

    var navLinks = document.querySelectorAll(".nav-link");
    var viewContainers = document.querySelectorAll(".view-container");

    navLinks.forEach(function (link) {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            var view = this.dataset.view;
            if (!view) return;

            navLinks.forEach(function (l) {
                l.classList.remove("active", "text-blue-600", "bg-blue-50");
                l.classList.add("text-slate-500");
            });
            this.classList.add("active", "text-blue-600", "bg-blue-50");
            this.classList.remove("text-slate-500");

            viewContainers.forEach(function (vc) {
                vc.classList.remove("active");
            });
            var target = $("view-" + view);
            if (target) target.classList.add("active");

            if (view !== "dashboard") {
                sidePanel.classList.add("translate-x-full");
                selectedDeviceId = null;
            }
        });
    });

    var btnFilter = $("btnFilter");
    var filterDropdown = $("filterDropdown");
    var filterBadge = $("filterBadge");

    if (btnFilter && filterDropdown) {
        btnFilter.addEventListener("click", function (e) {
            e.stopPropagation();
            filterDropdown.classList.toggle("active");
        });
        document.addEventListener("click", function (e) {
            if (!e.target.closest("#btnFilter") && !e.target.closest("#filterDropdown")) {
                filterDropdown.classList.remove("active");
            }
        });

        var filterOptions = filterDropdown.querySelectorAll(".filter-option");
        filterOptions.forEach(function (opt) {
            opt.addEventListener("click", function () {
                currentFilter = this.dataset.filter;
                if (filterBadge) {
                    filterBadge.style.display = currentFilter !== "all" ? "block" : "none";
                }
                renderDeviceTable();
                filterDropdown.classList.remove("active");
            });
        });
    }

    var btnExport = $("btnExport");
    if (btnExport) {
        btnExport.addEventListener("click", function () {
            var list = Object.values(devices);
            if (list.length === 0) {
                showNotification("No devices to export", "error");
                return;
            }
            var csv = "\uFEFFDevice Name,Username,IP Address,OS,Status,CPU%,RAM%,Disk%,Last Heartbeat\n";
            list.forEach(function (d) {
                csv += (d.hostname || "") + "," + (d.username || "") + "," + (d.ip || "") + "," +
                    (d.os || "") + "," + (d.status || "") + "," + (d.cpu_usage || 0) + "," +
                    (d.ram_usage || 0) + "," + (d.disk_usage || 0) + "," + (d.last_heartbeat || "") + "\n";
            });
            var blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = "honmonit_devices_" + new Date().toISOString().slice(0, 10) + ".csv";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showNotification("Exported " + list.length + " devices", "success");
        });
    }

    var rowActionsMenu = $("rowActionsMenu");
    if (rowActionsMenu) {
        rowActionsMenu.querySelectorAll(".row-action-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var action = this.dataset.action;
                var deviceId = rowActionsMenu.dataset.deviceId;
                if (!deviceId) return;
                hideRowActions();

                if (action === "details") {
                    selectDevice(deviceId);
                    loadProcesses(deviceId);
                } else if (action === "restart") {
                    if (confirm("Restart device " + (devices[deviceId] || {}).hostname + "?")) {
                        doRestartDevice(deviceId);
                    }
                } else if (action === "shutdown") {
                    if (confirm("Shutdown device " + (devices[deviceId] || {}).hostname + "?")) {
                        doShutdownDevice(deviceId);
                    }
                }
            });
        });
    }

    var btnRestart = $("btnRestart");
    var btnShutdown = $("btnShutdown");

    if (btnRestart) {
        btnRestart.addEventListener("click", function () {
            if (!selectedDeviceId) { showNotification("No device selected", "error"); return; }
            var dev = devices[selectedDeviceId];
            if (confirm("Restart device " + (dev ? dev.hostname : "") + "?")) {
                doRestartDevice(selectedDeviceId);
            }
        });
    }

    if (btnShutdown) {
        btnShutdown.addEventListener("click", function () {
            if (!selectedDeviceId) { showNotification("No device selected", "error"); return; }
            var dev = devices[selectedDeviceId];
            if (confirm("Shutdown device " + (dev ? dev.hostname : "") + "? This will power off the machine.")) {
                doShutdownDevice(selectedDeviceId);
            }
        });
    }

    var btnLogout = $("btnLogout");
    if (btnLogout) {
        btnLogout.addEventListener("click", function () {
            if (confirm("Are you sure you want to logout?")) {
                showNotification("Logged out successfully", "success");
            }
        });
    }

    function init() {
        fetch(API + "/api/devices")
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (list) {
                devices = {};
                list.forEach(function (d) { devices[d.device_id] = d; });
                renderDeviceTable();
                updateStats();
            })
            .catch(function () {
                renderDeviceTable();
            });

        connectDashboardWS();
    }

    init();
})();
