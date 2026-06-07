import os
import json
import tempfile
from typing import Optional
from unittest import mock

import pytest

from agent.identity import DeviceIdentity, IDENTITY_FILENAME, LEGACY_FILENAME


def _write_json(dirpath: str, data: dict):
    path = os.path.join(dirpath, IDENTITY_FILENAME)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _read_json(dirpath: str) -> Optional[dict]:
    path = os.path.join(dirpath, IDENTITY_FILENAME)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_legacy(dirpath: str, uuid_str: str):
    path = os.path.join(dirpath, LEGACY_FILENAME)
    with open(path, "w") as f:
        f.write(uuid_str)


FAKE_FINGERPRINT = {
    "hostname": "fake-host",
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "os": "FakeOS 1.0",
    "machine_id": "fake-machine-id",
}

LOCAL_FP = DeviceIdentity._collect_fingerprint()


class TestFirstRun:
    """Tidak ada file identitas → generate device_id baru."""

    def test_creates_new_identity_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id is not None
            assert len(ident.device_id) == 36

    def test_persists_identity_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            DeviceIdentity(identity_dir=tmp)
            data = _read_json(tmp)
            assert data is not None
            assert "device_id" in data
            assert "fingerprint" in data
            assert "created_at" in data

    def test_device_id_is_uuid(self):
        from uuid import UUID
        with tempfile.TemporaryDirectory() as tmp:
            ident = DeviceIdentity(identity_dir=tmp)
            UUID(ident.device_id)


class TestRestartSameMachine:
    """Restart normal di mesin yang sama → device_id tetap."""

    def test_reuses_existing_device_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = DeviceIdentity(identity_dir=tmp)
            first_id = first.device_id

            second = DeviceIdentity(identity_dir=tmp)
            assert second.device_id == first_id

    def test_single_component_change_tolerated(self):
        """Perubahan 1 komponen fingerprint (misal hostname) tidak trigger clone."""
        with tempfile.TemporaryDirectory() as tmp:
            first = DeviceIdentity(identity_dir=tmp)
            first_id = first.device_id

            modified_fp = dict(first.fingerprint)
            modified_fp["hostname"] = "renamed-host"

            _write_json(tmp, {
                "device_id": first_id,
                "fingerprint": modified_fp,
                "created_at": "2026-01-01T00:00:00+00:00",
            })

            second = DeviceIdentity(identity_dir=tmp)
            assert second.device_id == first_id


class TestCloneDetection:
    """Project di-copy ke mesin lain → fingerprint berbeda → device_id baru."""

    def test_generates_new_id_when_fingerprint_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_id = "00000000-0000-0000-0000-000000000001"
            _write_json(tmp, {
                "device_id": old_id,
                "fingerprint": FAKE_FINGERPRINT,
                "created_at": "2026-01-01T00:00:00+00:00",
            })

            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id != old_id
            assert ident.device_id is not None

    def test_updates_fingerprint_on_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(tmp, {
                "device_id": "00000000-0000-0000-0000-000000000001",
                "fingerprint": FAKE_FINGERPRINT,
                "created_at": "2026-01-01T00:00:00+00:00",
            })

            ident = DeviceIdentity(identity_dir=tmp)
            stored = _read_json(tmp)
            assert stored["fingerprint"] == LOCAL_FP

    def test_clone_detected_log_message(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(tmp, {
                "device_id": "00000000-0000-0000-0000-000000000001",
                "fingerprint": FAKE_FINGERPRINT,
                "created_at": "2026-01-01T00:00:00+00:00",
            })

            DeviceIdentity(identity_dir=tmp)
            assert any("DEVICE CLONE DETECTED" in msg for msg in caplog.messages)
            assert any("Device ID regenerated" in msg for msg in caplog.messages)


class TestCorruptedFile:
    """File identitas corrupt → device_id baru."""

    def test_corrupted_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, IDENTITY_FILENAME)
            with open(path, "w") as f:
                f.write("this is not valid json {{{")

            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id is not None
            assert len(ident.device_id) == 36

    def test_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(tmp, {"device_id": "abc"})
            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id != "abc"

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, IDENTITY_FILENAME)
            with open(path, "w") as f:
                f.write("")
            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id is not None


class TestLegacyMigration:
    """Migrasi dari format .device_id lama ke format JSON baru."""

    def test_migrates_legacy_file(self):
        old_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with tempfile.TemporaryDirectory() as tmp:
            _write_legacy(tmp, old_uuid)
            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id == old_uuid
            assert os.path.exists(os.path.join(tmp, IDENTITY_FILENAME))
            assert not os.path.exists(os.path.join(tmp, LEGACY_FILENAME))

    def test_migrated_file_has_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_legacy(tmp, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
            DeviceIdentity(identity_dir=tmp)
            data = _read_json(tmp)
            assert data is not None
            assert "fingerprint" in data
            assert "device_id" in data

    def test_corrupted_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, LEGACY_FILENAME)
            with open(path, "w") as f:
                f.write("not-a-uuid")
            ident = DeviceIdentity(identity_dir=tmp)
            assert ident.device_id != "not-a-uuid"
            assert len(ident.device_id) == 36


class TestEdgeCases:
    """Skenario batas dan fallback."""

    def test_unknown_mac_fallback(self):
        """uuid.getnode gagal → tetap jalan dengan 'unknown'."""
        with mock.patch("uuid.getnode", side_effect=Exception("no mac")):
            mac = DeviceIdentity._get_mac_address()
            assert mac == "unknown"

    def test_unknown_hostname_fallback(self):
        with mock.patch("socket.gethostname", side_effect=Exception("no hostname")):
            host = DeviceIdentity._get_hostname()
            assert host == "unknown"

    def test_unknown_os_fallback(self):
        with mock.patch("platform.system", side_effect=Exception("no os")):
            os_info = DeviceIdentity._get_os_info()
            assert os_info == "unknown"

    def test_unknown_machine_id_fallback(self):
        with mock.patch("platform.system", return_value="UnknownOS"):
            mid = DeviceIdentity._get_machine_id()
            assert mid == "unknown"

    def test_all_unknown_fingerprints_match(self):
        """Dua fingerprint yg semua 'unknown' dianggap sama (tidak trigger clone)."""
        fp = {
            "hostname": "unknown",
            "mac_address": "unknown",
            "os": "unknown",
            "machine_id": "unknown",
        }
        assert DeviceIdentity._fingerprint_differs(fp, fp) is False


class TestFingerprintComparison:
    """Unit test untuk _fingerprint_differs."""

    def test_identical_fingerprints(self):
        assert DeviceIdentity._fingerprint_differs(LOCAL_FP, LOCAL_FP) is False

    def test_one_field_differs(self):
        fp2 = dict(LOCAL_FP)
        fp2["hostname"] = "different"
        assert DeviceIdentity._fingerprint_differs(LOCAL_FP, fp2) is False

    def test_two_fields_differ(self):
        fp2 = dict(LOCAL_FP)
        fp2["hostname"] = "different"
        fp2["mac_address"] = "ff:ff:ff:ff:ff:ff"
        assert DeviceIdentity._fingerprint_differs(LOCAL_FP, fp2) is True

    def test_all_fields_differ(self):
        assert DeviceIdentity._fingerprint_differs(LOCAL_FP, FAKE_FINGERPRINT) is True

    def test_none_fingerprint(self):
        assert DeviceIdentity._fingerprint_differs(None, LOCAL_FP) is True
        assert DeviceIdentity._fingerprint_differs(LOCAL_FP, None) is True
        assert DeviceIdentity._fingerprint_differs({}, {}) is True
