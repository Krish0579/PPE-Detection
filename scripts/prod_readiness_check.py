#!/usr/bin/env python3
"""Offline production readiness gate — no model weights required.

Checks: secure defaults, trusted model dir policy, lockfile freshness hint,
required deploy artifacts, evidence DB schema, and new hardening modules.
Exit 0 = ready, exit 2 = blocking findings.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

findings: list[str] = []
warnings_list: list[str] = []


def check(name: str, ok: bool, hint: str = "", blocking: bool = True) -> None:
    status = "PASS" if ok else ("FAIL" if blocking else "WARN")
    print(f"[{status}] {name}" + (f" — {hint}" if hint and not ok else ""))
    if not ok and blocking:
        findings.append(name)
    elif not ok:
        warnings_list.append(name)


def main() -> int:
    from src.config.runtime import load_runtime_config

    cfg = load_runtime_config()
    check("secure default: external model paths OFF", not cfg.allow_external_model_path)
    check("secure default: browser model upload OFF", not cfg.enable_model_upload)
    for w in cfg.validated():
        print(f"[WARN] config: {w}")
        warnings_list.append(w)

    for rel in [
        "models/best.pt",
        "requirements-lock.txt",
        "Dockerfile",
        ".streamlit/config.toml",
        "config/prod/docker-compose.prod.yml",
        "config/prod/nginx.example.conf",
        "config/prod/k8s-deployment.example.yaml",
        ".github/workflows/ci.yml",
        "Makefile",
    ]:
        check(f"artifact present: {rel}", (PROJECT_ROOT / rel).is_file())

    try:
        import tempfile

        from src.storage.evidence import EvidenceManager

        with tempfile.TemporaryDirectory(prefix="safesight_gate_") as tmp:
            mgr = EvidenceManager(storage_dir=Path(tmp) / "ev", db_path=Path(tmp) / "t.db")
            sid = mgr.start_session()
            eid = mgr.log_event(event_type="VIOLATION", violation_type="gate-check", session_id=sid)
            check("evidence DB round-trip", bool(sid and eid))
    except Exception as exc:
        check("evidence DB round-trip", False, str(exc)[:160])

    try:
        from src.alerts.webhooks import build_violation_payload
        from src.observability.health import build_health_payload
        from src.privacy.blur import blur_regions
        from src.security.auth import can, verify_password
        from src.storage.backup import backup_sqlite, enforce_retention
        from src.video.camera_registry import parse_camera_sources

        check("health payload", build_health_payload(model_loaded=False)["status"] == "degraded")
        check("auth + RBAC", verify_password("x", __import__("hashlib").sha256(b"x").hexdigest()) and can("admin", "purge"))
        check("webhook payload", build_violation_payload(["no-helmet"], 1, 1, 50.0)["event"] == "ppe-violation")
        check("camera registry", parse_camera_sources("usb:0, demo")[0].kind == "usb")
        import numpy as np

        check("privacy blur", blur_regions(np.zeros((20, 20, 3), np.uint8), [(0, 0, 10, 10)]).shape == (20, 20, 3))
        check("backup helpers", callable(backup_sqlite) and callable(enforce_retention))
    except Exception as exc:
        check("hardening modules import", False, str(exc)[:200])

    db_default = PROJECT_ROOT / "data" / "ppe_events.db"
    if db_default.exists():
        print(f"[INFO] production DB present: {db_default}")
    else:
        print("[INFO] production DB not yet created (created on first run)")

    print(f"\nGate: {0 if not findings else len(findings)} blocking, {len(warnings_list)} warnings")
    print("Commercial reminder: Ultralytics YOLO AGPL — obtain a commercial license before proprietary sale.")
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
