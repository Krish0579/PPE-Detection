"""Phase 5 production-hardening tests (offline, no model weights required)."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.__version__ import __version__
from src.alerts.webhooks import _is_allowed, build_violation_payload, post_json
from src.config.runtime import load_runtime_config
from src.observability.health import build_health_payload
from src.privacy.blur import blur_person_boxes, blur_regions
from src.security.auth import can, hash_password, is_auth_configured, verify_password
from src.storage.backup import backup_sqlite, enforce_retention
from src.video.camera_registry import default_sources, parse_camera_sources


def test_version_is_pinned():
    assert __version__ == "1.0.0"


def test_runtime_secure_defaults():
    cfg = load_runtime_config(env={})
    assert cfg.allow_external_model_path is False
    assert cfg.enable_model_upload is False
    assert cfg.max_image_mb == 25
    assert cfg.is_production is True


def test_runtime_env_override_and_warnings():
    cfg = load_runtime_config(env={"PPE_ALLOW_EXTERNAL_MODEL_PATH": "true", "PPE_ENABLE_MODEL_UPLOAD": "1"})
    assert cfg.allow_external_model_path is True
    assert any("trusted-checkpoint" in w for w in cfg.validated())


def test_runtime_bool_parsing_tolerant():
    cfg = load_runtime_config(env={"PPE_ALLOW_EXTERNAL_MODEL_PATH": "YES", "PPE_MAX_IMAGE_MB": "not-a-number"})
    assert cfg.allow_external_model_path is True
    assert cfg.max_image_mb == 25


def test_runtime_auth_and_webhook_warnings():
    cfg = load_runtime_config(
        env={
            "SAFE_SIGHT_AUTH_REQUIRED": "true",
            "SAFE_SIGHT_WEBHOOK_URL": "https://evil.example/x",
            "SAFE_SIGHT_WEBHOOK_ALLOWLIST": "https://hooks.slack.com/",
        }
    )
    assert cfg.is_auth_enabled is False
    joined = " ".join(cfg.validated())
    assert "OPERATOR_PASSWORD" in joined
    assert "ALLOWLIST" in joined


def test_settings_secure_defaults_without_env(monkeypatch):
    monkeypatch.delenv("PPE_ALLOW_EXTERNAL_MODEL_PATH", raising=False)
    monkeypatch.delenv("PPE_ENABLE_MODEL_UPLOAD", raising=False)
    import importlib

    from src.config import settings

    importlib.reload(settings)
    assert settings.ALLOW_EXTERNAL_MODEL_PATH is False
    assert settings.MODEL_UPLOAD_ENABLED is False


def test_health_payload_status():
    degraded = build_health_payload(model_loaded=False)
    assert degraded["status"] == "degraded"
    assert degraded["version"] == "1.0.0"
    ok = build_health_payload(model_name="best.pt", device="cpu", model_loaded=True, started_at=0.0)
    assert ok["status"] == "ok"
    assert ok["uptime_sec"] >= 0.0


def test_auth_hash_verify_and_roles():
    digest = hash_password("operator-secret")
    assert digest == hashlib.sha256(b"operator-secret").hexdigest()
    assert verify_password("operator-secret", digest) is True
    assert verify_password("wrong", digest) is False
    assert verify_password("", digest) is False
    assert is_auth_configured(True, digest) is True
    assert is_auth_configured(True, "") is False
    assert can("operator", "view") is True
    assert can("operator", "purge") is False
    assert can("supervisor", "resolve") is True
    assert can("admin", "purge") is True
    assert can("unknown", "view") is False


def test_webhook_payload_and_guards():
    payload = build_violation_payload(["no-vest", "no-vest", "no-helmet"], 3, 1, 66.66, model_name="m")
    assert payload["event"] == "ppe-violation"
    assert payload["labels"] == ["no-helmet", "no-vest"]
    bad = post_json("ftp://x", {})
    assert bad.ok is False
    blocked = post_json("https://evil.example/hook", {}, allowlist=("https://hooks.slack.com/",))
    assert blocked.ok is False and "allowlist" in blocked.reason


def test_webhook_allowlist_host_hardening():
    """SSRF regression: string-prefix allowlists admitted domain-suffix attacks."""
    allow = ("https://hooks.slack.com/",)
    assert _is_allowed("https://hooks.slack.com/services/T/B/x", allow) is True
    # Domain suffix attack must fail even though the URL starts with the entry string.
    assert _is_allowed("https://hooks.slack.com.evil.example/", allow) is False
    # Userinfo redirect trick must fail.
    assert _is_allowed("https://hooks.slack.com@evil.example/x", allow) is False
    # Scheme downgrade (https entry -> http candidate) must fail.
    assert _is_allowed("http://hooks.slack.com/services/T/B/x", allow) is False
    # Path-scoped entries: match beneath the path, not string-lookalikes.
    scoped = ("https://example.com/hooks/",)
    assert _is_allowed("https://example.com/hooks/a", scoped) is True
    assert _is_allowed("https://example.com/hooksetc", scoped) is False
    assert _is_allowed("https://example.com/other", scoped) is False
    # Host lookalike with shared prefix must fail.
    assert _is_allowed("https://example.com.evil.example/hooks/a", scoped) is False
    # Bare-host entries match the whole host.
    assert _is_allowed("https://hooks.slack.com/anything", ("hooks.slack.com",)) is True
    # Empty allowlist keeps the documented allow-all behaviour.
    assert _is_allowed("https://anything.example/x", ()) is True
    # Unparseable or credential-bearing URLs fail closed.
    assert _is_allowed("https://user:pw@example.example/x", allow) is False
    credentialed = post_json("https://user:pw@hooks.slack.com/services/T/B/x", {}, allowlist=allow)
    assert credentialed.ok is False and "credentials" in credentialed.reason


def test_rotating_file_logging_behaviour(monkeypatch, tmp_path):
    import logging

    import src.observability.logging_setup as ls

    # Env resolution matrix
    monkeypatch.setenv("SAFE_SIGHT_LOG_FILE", "off")
    assert ls._resolve_log_file() is None
    monkeypatch.setenv("SAFE_SIGHT_LOG_FILE", str(tmp_path / "custom.log"))
    assert ls._resolve_log_file() == tmp_path / "custom.log"
    monkeypatch.delenv("SAFE_SIGHT_LOG_FILE")
    monkeypatch.setenv("SAFE_SIGHT_CONTAINER", "1")
    assert ls._resolve_log_file() is None

    # End-to-end: a log line must land in the rotating file without breaking stdout logging.
    root = logging.getLogger()
    saved_handlers, saved_flag = list(root.handlers), ls._CONFIGURED
    monkeypatch.delenv("SAFE_SIGHT_CONTAINER")
    monkeypatch.setenv("SAFE_SIGHT_LOG_FILE", str(tmp_path / "safesight.log"))
    try:
        ls._CONFIGURED = False
        ls.configure_logging("DEBUG")
        from logging.handlers import RotatingFileHandler

        assert any(isinstance(h, RotatingFileHandler) for h in logging.getLogger().handlers)
        logging.getLogger("safesight.test").info("rotation-smoke")
        for h in root.handlers:
            h.flush()
        assert "rotation-smoke" in (tmp_path / "safesight.log").read_text()
    finally:
        for h in list(root.handlers):
            h.close()
            root.removeHandler(h)
        for h in saved_handlers:
            root.addHandler(h)
        ls._CONFIGURED = saved_flag


def test_camera_registry_parsing_and_redaction():
    sources = parse_camera_sources("usb:0, rtsp:rtsp://admin:secret@cam-02:554/s, https://cam-03/mjpeg, demo, junk")
    kinds = [s.kind for s in sources]
    assert kinds == ["usb", "rtsp", "http", "demo"]
    assert "secret" not in sources[1].redacted
    assert "cam-02" in sources[1].redacted
    assert default_sources()[0].id == "CAM-01"
    assert parse_camera_sources("") == []


def test_privacy_blur_changes_roi_only():
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    # High-frequency stripe pattern: Gaussian blur must attenuate it.
    frame[5:15, 5:15, :] = (np.arange(100).reshape(10, 10, 1) % 2 * 255).astype(np.uint8)
    out = blur_regions(frame, [(5, 5, 15, 15)], strength=9)
    assert out.shape == frame.shape
    assert not np.array_equal(out[5:15, 5:15], frame[5:15, 5:15])
    assert np.array_equal(out[25:35, 25:35], frame[25:35, 25:35])
    untouched = blur_regions(frame, [])
    assert np.array_equal(untouched, frame)


def test_privacy_blur_person_detections():
    frame = np.full((30, 30, 3), 128, dtype=np.uint8)
    dets = [
        {"label": "person", "x1": 2, "y1": 2, "x2": 12, "y2": 12},
        {"label": "helmet", "x1": 0, "y1": 0, "x2": 5, "y2": 5},
    ]
    out = blur_person_boxes(frame, dets)
    assert out.shape == frame.shape


def test_backup_sqlite_roundtrip():
    with tempfile.TemporaryDirectory(prefix="safesight_backup_") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "src.db"
        with sqlite3.connect(str(src)) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
            conn.execute("INSERT INTO t (v) VALUES ('audit')")
            conn.commit()
        receipt = backup_sqlite(src, tmp_path / "backups")
        assert receipt["ok"] is True
        dest = Path(receipt["path"])
        assert dest.is_file()
        with sqlite3.connect(str(dest)) as conn:
            rows = conn.execute("SELECT v FROM t").fetchall()
        assert rows == [("audit",)]
        missing = backup_sqlite(tmp_path / "nope.db", tmp_path / "backups")
        assert missing["ok"] is False


def test_enforce_retention_deletes_only_stale():
    with tempfile.TemporaryDirectory(prefix="safesight_ret_") as tmp:
        tmp_path = Path(tmp)
        old = tmp_path / "viol_20200101_000000_000_old.jpg"
        new = tmp_path / "viol_20990101_000000_000_new.jpg"
        old.write_bytes(b"x" * 16)
        new.write_bytes(b"y" * 16)
        import os
        import time

        ancient = time.time() - 40 * 86400.0
        os.utime(old, (ancient, ancient))
        mirrored: list[list[str]] = []

        def _mirror(names: list[str]) -> None:
            mirrored.append(list(names))

        receipt = enforce_retention(tmp_path, snapshots_table_purge=_mirror, retention_days=30)
        assert receipt["deleted"] == 1
        assert receipt["files"] == [old.name]
        assert mirrored == [[old.name]]
        assert new.is_file()
        assert not old.exists()
