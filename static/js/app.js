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
        if (!hb) return '<span class="hb-status offline">Offline</span>';
        var now = Date.now();
        var then = new Date(hb).getTime();
        var diffSec = Math.floor((now - then) / 1000);
        var text, cls;
        if (diffSec < 30)      { text = "Just now";  cls = "online"; }
        else if (diffSec < 60) { text = diffSec + "s ago"; cls = "online"; }
        else if (diffSec < 300){ text = Math.floor(diffSec / 60) + "m ago"; cls = "online"; }
        else if (diffSec < 3600){ text = Math.floor(diffSec / 60) + "m ago"; cls = "warning"; }
        else if (diffSec < 86400){ text = Math.floor(diffSec / 3600) + "h ago"; cls = "warning"; }
        else                   { text = Math.floor(diffSec / 86400) + "d ago"; cls = "offline"; }
        return '<span class="hb-status ' + cls + '"><span class="hb-dot ' + cls + '"></span>' + text + '</span>';
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
        var bg = type === "success" ? "toast success" : "toast error";
        div.className = bg;
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
            list.innerHTML = '<div class="notif-empty">No recent events.</div>';
            return;
        }
        var html = "";
        deviceNotifications.forEach(function (n) {
            var dot = n.type === "online" ? "online" : n.type === "offline" ? "offline" : "info";
            html += '<div class="notif-item">' +
                '<span class="hb-dot ' + dot + '" style="margin-top:4px"></span>' +
                '<div class="notif-content"><p>' + escapeHtml(n.title) + '</p>' +
                '<p>' + escapeHtml(n.desc) + ' \u2022 ' + n.time + '</p></div></div>';
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
        panelProcessList.innerHTML = '<div class="empty-state"><p>Loading processes...</p></div>';

        fetch(API + "/api/devices/" + deviceId + "/processes", { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success && data.data && data.data.processes) {
                    _lastProcessList = data.data.processes;
                    renderProcessList(_lastProcessList);
                } else {
                    panelProcessList.innerHTML = '<div class="empty-state"><p>' + escapeHtml(data.error || "Failed") + "</p></div>";
                }
            })
            .catch(function () {
                panelProcessList.innerHTML = '<div class="empty-state"><p>Failed to retrieve process list</p></div>';
            });
    }

    function renderProcessList(list) {
        if (!panelProcessList) return;
        if (!list || list.length === 0) {
            panelProcessList.innerHTML = '<div class="empty-state"><p>No processes found.</p></div>';
            return;
        }
        var html = '<div class="process-list-header">' +
            '<span>Process Name</span>' +
            '<span>PID</span>' +
            '<span>Memory</span>' +
            '<span>Action</span></div>' +
            '<div style="padding:4px 8px;font-family:var(--font-mono);font-size:12px;color:var(--text-muted)">' + list.length + " processes</div>";
        list.forEach(function (p) {
            var safeName = escapeHtml(p.name);
            html += '<div class="process-item">' +
                '<span class="name">' + safeName + "</span>" +
                '<span class="pid">' + p.pid + "</span>" +
                '<span class="mem">' + p.memory_mb.toFixed(1) + " MB</span>" +
                '<span class="action">' +
                '<button class="kill-btn" data-pid="' + p.pid + '" data-name="' + safeName.replace(/"/g, "&quot;") + '">KILL</button></span></div>';
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
            deviceTableBody.innerHTML = '<tr><td colspan="8" style="padding:40px 20px;text-align:center;color:var(--text-muted);font-size:12px">' +
                "NO DEVICES FOUND. START AN AGENT TO SEE IT HERE.</td></tr>";
            return;
        }

        deviceTableBody.innerHTML = list.map(function (d) {
            var selected = d.device_id === selectedDeviceId;
            var rowClass = "cursor-pointer transition-colors" + (selected ? " selected" : "");

            var badgeClass = d.status === "online"
                ? "badge-online"
                : "badge-offline";

            var cpuWidth = (d.cpu_usage || 0) + "%";
            var ramWidth = (d.ram_usage || 0) + "%";

            return '<tr class="' + rowClass + '" data-device-id="' + d.device_id + '">' +
                '<td><div class="device-name-cell">' +
                '<span class="material-symbols-outlined">laptop_mac</span>' +
                '<span class="device-name">' + escapeHtml(d.hostname) + "</span></div></td>" +
                '<td class="device-ip">' + escapeHtml(d.ip) + "</td>" +
                '<td style="font-size:12px">' + escapeHtml(d.os) + "</td>" +
                '<td><span class="badge ' + badgeClass + '">' +
                (d.status === "online" ? "ONLINE" : "OFFLINE") + "</span></td>" +
                '<td style="min-width:140px"><div style="display:flex;flex-direction:column;gap:4px">' +
                '<div class="mini-bar"><span class="mini-bar-label">CPU</span>' +
                '<div class="mini-bar-track"><div class="mini-bar-fill blue" style="width:' + cpuWidth + '"></div></div>' +
                '<span class="mini-bar-value">' + (d.cpu_usage || 0) + "%</span></div>" +
                '<div class="mini-bar"><span class="mini-bar-label">RAM</span>' +
                '<div class="mini-bar-track"><div class="mini-bar-fill amber" style="width:' + ramWidth + '"></div></div>' +
                '<span class="mini-bar-value">' + (d.ram_usage || 0) + "%</span></div></div></td>" +
                '<td style="min-width:110px">' + formatHeartbeat(d.last_heartbeat) + "</td>" +
                '<td style="width:40px"><button class="row-more-btn" data-device-id="' + d.device_id + '">' +
                '<span class="material-symbols-outlined">more_vert</span></button></td></tr>';
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

        var dotColor = device.status === "online" ? "#33cc66" : "#ee3333";
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
        if (panelOverlay) panelOverlay.classList.add("active");
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

    var panelOverlay = $("sidePanelOverlay");

    function closeSidePanel() {
        sidePanel.classList.add("translate-x-full");
        if (panelOverlay) panelOverlay.classList.remove("active");
        selectedDeviceId = null;
        renderDeviceTable();
    }

    if (panelCloseBtn && sidePanel) {
        panelCloseBtn.addEventListener("click", closeSidePanel);
    }

    if (panelOverlay) {
        panelOverlay.addEventListener("click", closeSidePanel);
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
            if (isAdminMode) {
                isAdminMode = false;
                btnAdminMode.classList.remove("active");
                if (adminModeLabel) adminModeLabel.textContent = "ADMIN";
                showNotification("Admin mode disabled", "success");
                hideRowActions();
                return;
            }
            showAdminPasswordModal();
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

    var navLinks = document.querySelectorAll(".sidebar-link[data-view]");
    var viewContainers = document.querySelectorAll(".view-container");

    navLinks.forEach(function (link) {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            var view = this.dataset.view;
            if (!view) return;

            navLinks.forEach(function (l) {
                l.classList.remove("active");
            });
            this.classList.add("active");

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

        var filterOptions = filterDropdown.querySelectorAll(".dropdown-item");
        filterOptions.forEach(function (opt) {
            opt.addEventListener("click", function () {
                filterDropdown.querySelectorAll(".dropdown-item").forEach(function (i) { i.classList.remove("active"); });
                this.classList.add("active");
                currentFilter = this.dataset.filter;
                if (filterBadge) {
                    filterBadge.style.display = currentFilter !== "all" ? "block" : "none";
                }
                renderDeviceTable();
                filterDropdown.classList.remove("active");
            });
        });
    }

    var sidebarToggle = $("sidebarToggle");
    var appSidebar = $("appSidebar");
    if (sidebarToggle && appSidebar) {
        sidebarToggle.addEventListener("click", function () {
            appSidebar.classList.toggle("collapsed");
        });
    }

    var panelTabs = document.querySelectorAll(".panel-tab");
    panelTabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            panelTabs.forEach(function (t) { t.classList.remove("active"); });
            this.classList.add("active");
            var tabName = this.dataset.tab;
            var contents = document.querySelectorAll(".panel-tab-content");
            contents.forEach(function (c) { c.classList.remove("active"); });
            var target = $("tab-" + tabName);
            if (target) target.classList.add("active");
        });
    });

    var btnClearAlerts = $("btnClearAlerts");
    if (btnClearAlerts) {
        btnClearAlerts.addEventListener("click", function () {
            var alertsList = $("alertsList");
            if (alertsList) {
                alertsList.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined">notifications_off</span><p>No alerts recorded yet.</p></div>';
                showNotification("All alerts cleared", "success");
            }
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

    function showAdminPasswordModal() {
        var modal = $("adminPasswordModal");
        var input = $("adminPasswordInput");
        var error = $("adminPwdError");
        if (!modal || !input) return;
        input.value = "";
        error.style.display = "none";
        modal.classList.add("active");
        setTimeout(function () { input.focus(); }, 100);

        function cleanup() {
            modal.classList.remove("active");
            input.value = "";
            error.style.display = "none";
            $("adminPwdSubmit").removeEventListener("click", onSubmit);
            $("adminPwdCancel").removeEventListener("click", onCancel);
            $("adminPwdClose").removeEventListener("click", onCancel);
            input.removeEventListener("keydown", onKeydown);
        }
        function onSuccess() {
            isAdminMode = true;
            btnAdminMode.classList.add("active");
            if (adminModeLabel) adminModeLabel.textContent = "UNLOCKED";
            showNotification("Admin mode enabled", "success");
            hideRowActions();
            cleanup();
        }
        function onCancel() {
            hideRowActions();
            cleanup();
        }
        function onSubmit() {
            if (input.value === "honeyyy") {
                onSuccess();
            } else {
                error.style.display = "block";
                input.value = "";
                input.focus();
            }
        }
        function onKeydown(e) {
            if (e.key === "Enter") onSubmit();
            if (e.key === "Escape") onCancel();
        }

        $("adminPwdSubmit").addEventListener("click", onSubmit);
        $("adminPwdCancel").addEventListener("click", onCancel);
        $("adminPwdClose").addEventListener("click", onCancel);
        input.addEventListener("keydown", onKeydown);
        modal.addEventListener("click", function (e) {
            if (e.target === modal) onCancel();
        });
    }

    var btnFullscreen = $("btnFullscreen");
    if (btnFullscreen) {
        btnFullscreen.addEventListener("click", function () {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
                btnFullscreen.querySelector(".material-symbols-outlined").textContent = "fullscreen_exit";
            } else {
                document.exitFullscreen();
                btnFullscreen.querySelector(".material-symbols-outlined").textContent = "fullscreen";
            }
        });
    }

    function init() {
        document.body.classList.add("power-on");
        setTimeout(function () { document.body.classList.remove("power-on"); }, 600);

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
