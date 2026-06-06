# Screenshots

> **Note:** HonMonit is a dark‑theme dashboard. The images below are text descriptions of each view.

---

## Dashboard — Device Inventory

The main view displays a summary header with aggregate statistics and a filterable, searchable device table.

```
┌─────────────────────────────────────────────────────────────────┐
│  HonMonit  [Search devices…]         [Admin] [🔔] [⚙] [?] HM │
├─────────┬─────────┬─────────┬──────────┬───────────────────────┤
│  Total  │ Online  │ Offline │  Avg CPU │      Avg RAM          │
│    3    │    2    │    1    │ ███ 45%  │      ██ 62%           │
├─────────┴─────────┴─────────┴──────────┴───────────────────────┤
│  Device Inventory                     [Filter ▼] [Export]      │
│                                                                 │
│  Device         │ IP         │ OS        │ Status  │ CPU  RAM  │
│  ───────────────┼────────────┼───────────┼─────────┼────────── │
│  🖥 workstation  │ 10.0.0.10 │ Win 10    │ ● Online│ ██ ███    │
│  🖥 server-01   │ 10.0.0.20 │ Ubuntu 22 │ ● Online│ █   ██    │
│  🖥 old-pc      │ 10.0.0.30 │ Win 7     │ ○ Offlin│           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Device Detail Panel

Clicking a device row opens a slide‑out side panel with four tabs.

### Overview Tab

```
┌──────────────────────────────────────┐
│ 🖥 workstation                        │
│ ● Active • jdoe             [✕]     │
├──────────────────────────────────────┤
│ [Overview] [Processes] [Control] [Network]
│                                      │
│  ┌──────┐  ┌──────┐  ┌──────┐      │
│  │ CPU  │  │ RAM  │  │ DISK │      │
│  │  \   │  │  /   │  │  —   │      │
│  │  45% │  │  62% │  │  27% │     │
│  └──────┘  └──────┘  └──────┘      │
│                                      │
│  Hardware                            │
│  CPU: 45%                            │
│  RAM: 16 GB • 62% used              │
│                                      │
│  Operating System                    │
│  Windows 10                          │
│  Disk: 27% used                      │
│                                      │
│  Network                             │
│  IP: 10.0.0.10                      │
│  MAC: AA:BB:CC:DD:EE:FF            │
│                                      │
│  Last Seen                           │
│  2:45:30 PM                          │
│  Device is online and connected      │
└──────────────────────────────────────┘
```

### Processes Tab

```
┌──────────────────────────────────────┐
│ [Overview] [Processes] [Control] [Network]
│                                      │
│  🔍 [Filter processes...]           │
│                                      │
│  Process Name          │ PID │ Mem   │
│  ──────────────────────┼─────┼───────│
│  chrome.exe            │ 4521│ 342 MB│
│  python.exe            │ 1234│ 128 MB│
│  explorer.exe          │ 7890│ 89 MB │
│  slack.exe             │ 3456│ 210 MB│
│  ...                                 │
│                                      │
│  [Kill] buttons on each row          │
└──────────────────────────────────────┘
```

### Control Tab

```
┌──────────────────────────────────────┐
│ [Overview] [Processes] [Control] [Network]
│                                      │
│  ┌────────────┐  ┌───────────────┐  │
│  │ 🔄 Restart │  │ ⏻ Shutdown   │  │
│  └────────────┘  └───────────────┘  │
│                                      │
│  ┌────────────┐                      │
│  │ 🔃 Refresh │                     │
│  └────────────┘                      │
│                                      │
│  ❗ Restart and Shutdown require     │
│     confirmation via browser dialog  │
└──────────────────────────────────────┘
```

---

## Alerts View

```
┌─────────────────────────────────────────────────────────────────┐
│  Alert History                                    [Clear All]  │
│                                                                 │
│  ● Device Connected — workstation (10.0.0.10) • 2:45:00 PM     │
│  ● Device Offline — old-pc (10.0.0.30) went offline • 2:30 PM  │
│  ● Device Connected — server-01 (10.0.0.20) • 2:15:00 PM       │
│  ● Process Killed — chrome.exe (PID 4521) • 2:10:00 PM         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Row Actions Menu

```
┌─────────────────────────────────────────────────────────────────┐
│  Device         │ IP         │ Status  │ CPU  RAM  │ H/B  │ ⋮  │
│  ───────────────┼────────────┼─────────┼───────────┼──────┼────┤
│  🖥 workstation  │ 10.0.0.10 │ ● Online│ ██ ███    │ 2:45 │ ⋮  │
│                                                       ┌──────┤
│                                                       │ 📋   │
│                                                       │ Info │
│                                                       │ 🔄   │
│                                                       │ Rest.│
│                                                       │ ⏻    │
│                                                       │ Shut.│
│                                                       └──────┤
└─────────────────────────────────────────────────────────────────┘
```

> The Restart and Shutdown actions are only visible when **Admin mode** is enabled.

---

## Settings Modal

```
┌──────────────────────────────────┐
│  ⚙ Settings                      │
├──────────────────────────────────┤
│  Auto-refresh              [═══] │
│  Automatically refresh data      │
│                                  │
│  Sound alerts              [    ]│
│  Play sound on device events     │
│                                  │
│  Show offline devices      [═══] │
│  Display offline inventory       │
├──────────────────────────────────┤
│                        [Close]  │
└──────────────────────────────────┘
```
