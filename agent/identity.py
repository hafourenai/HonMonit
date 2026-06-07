import os
import sys
import json
import uuid
import socket
import platform
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("honmonit.identity")

IDENTITY_FILENAME = ".device-identity.json"
LEGACY_FILENAME = ".device_id"


class DeviceIdentity:
    """Manages persistent device identity with clone detection via machine fingerprinting.

    Generates a unique device_id on first run and persists it alongside a machine
    fingerprint. On subsequent runs the fingerprint is compared against the current
    environment to detect clones (project copied to another machine).
    """

    def __init__(self, identity_dir: Optional[str] = None):
        if identity_dir is None:
            identity_dir = self._default_identity_dir()
        self._filepath = os.path.join(identity_dir, IDENTITY_FILENAME)
        self._legacy_filepath = os.path.join(identity_dir, LEGACY_FILENAME)
        self._identity = self._load_or_create()

    @staticmethod
    def _default_identity_dir() -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    @property
    def device_id(self) -> str:
        return self._identity["device_id"]

    @property
    def fingerprint(self) -> dict:
        return dict(self._identity.get("fingerprint", {}))

    @staticmethod
    def _get_hostname() -> str:
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    @staticmethod
    def _get_mac_address() -> str:
        """Return the MAC address of the primary interface as ``aa:bb:cc:dd:ee:ff``.

        Uses ``uuid.getnode()`` which prefers the real MAC of the primary
        network interface.  Falls back to ``"unknown"``.
        """
        try:
            mac = uuid.getnode()
            if mac is not None and (mac >> 40) % 2 == 0:
                return ":".join(
                    f"{(mac >> bits) & 0xFF:02x}"
                    for bits in range(40, -1, -8)
                )
        except Exception:
            pass
        return "unknown"

    @staticmethod
    def _get_os_info() -> str:
        try:
            return f"{platform.system()} {platform.release()}"
        except Exception:
            return "unknown"

    @staticmethod
    def _get_machine_id() -> str:
        """Return an OS-level stable machine identifier.

        Windows  ``MachineGuid`` from the registry
        Linux    content of ``/etc/machine-id`` or ``/var/lib/dbus/machine-id``
        macOS    ``IOPlatformUUID`` from the I/O registry

        Falls back to ``"unknown"`` when nothing is available.
        """
        system = platform.system()
        try:
            if system == "Windows":
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                )
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                return str(val)

            if system == "Linux":
                for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                    if os.path.exists(path):
                        with open(path, "r") as f:
                            return f.read().strip()

            if system == "Darwin":
                import subprocess

                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.splitlines():
                    if "IOPlatformUUID" in line:
                        parts = line.split('"')
                        if len(parts) >= 4:
                            return parts[3]
        except Exception:
            pass
        return "unknown"

    @staticmethod
    def _collect_fingerprint() -> dict:
        return {
            "hostname": DeviceIdentity._get_hostname(),
            "mac_address": DeviceIdentity._get_mac_address(),
            "os": DeviceIdentity._get_os_info(),
            "machine_id": DeviceIdentity._get_machine_id(),
        }

    @staticmethod
    def _fingerprint_differs(fp_a: dict, fp_b: dict) -> bool:
        """Return ``True`` when the two fingerprints differ significantly.

        "Significantly" means **two or more** individual components differ.
        A single change (e.g. hostname rename) is tolerated and does *not*
        trigger clone detection.
        """
        if not fp_a or not fp_b:
            return True
        differing = sum(
            1 for key in fp_a if fp_a.get(key) != fp_b.get(key)
        )
        return differing >= 2

    def _load_or_create(self) -> dict:
        identity = self._try_load()
        if identity is not None:
            return identity
        return self._create_new()

    def _try_load(self) -> Optional[dict]:
        data = self._try_load_json(self._filepath)
        if data is not None:
            return data

        data = self._try_load_legacy()
        if data is not None:
            return data

        return None

    def _try_load_json(self, path: str) -> Optional[dict]:
        try:
            with open(path, "r") as f:
                content = f.read().strip()
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning("Error reading identity file: %s", exc)
            return None

        if not content:
            return None

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Corrupted identity file (invalid JSON) — will regenerate")
            return None

        if "device_id" not in data or "fingerprint" not in data:
            logger.warning("Corrupted identity file (missing fields) — will regenerate")
            return None

        current_fp = self._collect_fingerprint()
        stored_fp = data.get("fingerprint", {})

        if self._fingerprint_differs(stored_fp, current_fp):
            logger.warning("=== DEVICE CLONE DETECTED ===")
            logger.warning("Stored fingerprint: %s", stored_fp)
            logger.warning("Current fingerprint: %s", current_fp)
            logger.warning("Device ID regenerated")
            return None

        logger.info("Existing device ID loaded: %s", data["device_id"])
        return data

    def _try_load_legacy(self) -> Optional[dict]:
        try:
            with open(self._legacy_filepath, "r") as f:
                content = f.read().strip()
        except (FileNotFoundError, OSError):
            return None

        if not content:
            return None

        try:
            uuid.UUID(content)
        except ValueError:
            logger.warning(
                "Corrupted legacy identity file (invalid UUID) — will regenerate"
            )
            return None

        logger.info("Existing device ID loaded (legacy format): %s", content)

        identity = {
            "device_id": content,
            "fingerprint": self._collect_fingerprint(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(identity)
        logger.info("Migrated legacy identity to new format")

        try:
            os.remove(self._legacy_filepath)
        except OSError:
            pass

        return identity

    def _create_new(self) -> dict:
        identity = {
            "device_id": str(uuid.uuid4()),
            "fingerprint": self._collect_fingerprint(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(identity)
        logger.info("New device ID generated: %s", identity["device_id"])
        return identity

    def _save(self, identity: dict) -> None:
        try:
            with open(self._filepath, "w") as f:
                json.dump(identity, f, indent=2)
        except OSError as exc:
            logger.warning("Failed to save identity file: %s", exc)
