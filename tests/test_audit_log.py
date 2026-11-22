"""Tests for the hash-chained, tamper-evident audit log."""

from __future__ import annotations

import sqlite3

import pytest

from src.storage.audit_log import AuditLog


@pytest.fixture
def log(tmp_path):
    return AuditLog(str(tmp_path / "audit.db"))


@pytest.fixture
def hmac_log(tmp_path):
    return AuditLog(str(tmp_path / "audit_hmac.db"), hmac_key=b"test-secret-key")


class TestRecordAndVerify:
    def test_record_appends_entries(self, log):
        log.record("admin", "login", "system", {"ip": "127.0.0.1"})
        log.record("admin", "data_access", "settings", {"page": "config"})
        valid, broken = log.verify_chain()
        assert valid is True
        assert broken is None

    def test_hmac_mode_verify(self, hmac_log):
        hmac_log.record("admin", "login", "system")
        hmac_log.record("admin", "data_access", "settings")
        valid, broken = hmac_log.verify_chain()
        assert valid is True
        assert broken is None

    def test_empty_log_verifies(self, log):
        valid, broken = log.verify_chain()
        assert valid is True
        assert broken is None


class TestTamperDetection:
    def test_modified_content_detected(self, tmp_path):
        db_path = tmp_path / "tamper.db"
        log = AuditLog(str(db_path))
        log.record("admin", "login", "system")
        log.record("admin", "data_access", "settings")
        log.close()

        # Directly tamper with the SQLite database
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE audit_log SET action = 'hacked' WHERE seq = 1")
        conn.commit()
        conn.close()

        log2 = AuditLog(str(db_path))
        valid, broken_seq = log2.verify_chain()
        assert valid is False
        assert broken_seq is not None
        assert broken_seq == 1

    def test_hmac_tamper_detected(self, tmp_path):
        db_path = tmp_path / "tamper_hmac.db"
        log = AuditLog(str(db_path), hmac_key=b"secret")
        log.record("admin", "login", "system")
        log.record("admin", "data_access", "settings")
        log.close()

        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE audit_log SET action = 'hacked' WHERE seq = 1")
        conn.commit()
        conn.close()

        log2 = AuditLog(str(db_path), hmac_key=b"secret")
        valid, _broken_seq = log2.verify_chain()
        assert valid is False


class TestEntriesFiltering:
    def test_filter_by_target(self, log):
        log.record("admin", "login", "user-1")
        log.record("admin", "login", "user-2")
        log.record("admin", "data_access", "user-1")

        entries = log.entries(target="user-1")
        assert len(entries) == 2
        assert all(e.target == "user-1" for e in entries)

    def test_all_entries(self, log):
        log.record("admin", "login", "user-1")
        log.record("admin", "login", "user-2")
        entries = log.entries()
        assert len(entries) == 2


class TestCallableAdapter:
    def test_call_records(self, log):
        log("admin", "config.update", "INC-001", {"key": "value"})
        entries = log.entries()
        assert len(entries) == 1
        assert entries[0].action == "config.update"
        assert entries[0].target == "INC-001"

    def test_record_requires_actor_and_action(self, log):
        with pytest.raises(ValueError):
            log.record("", "login", "system")
        with pytest.raises(ValueError):
            log.record("admin", "", "system")
