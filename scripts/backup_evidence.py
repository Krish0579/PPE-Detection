#!/usr/bin/env python3
"""Evidence backup + retention enforcement for cron / systemd / operator use.

Example:
    python3 scripts/backup_evidence.py --retention-days 30 --backup-dir /var/backups/safesight
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import DB_PATH, EVIDENCE_DIR
from src.observability.logging_setup import configure_logging, get_logger
from src.storage.backup import backup_sqlite, enforce_retention


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up evidence DB and enforce retention.")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "data" / "backups")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    configure_logging()
    log = get_logger("backup")

    if not args.no_backup:
        receipt = backup_sqlite(DB_PATH, args.backup_dir)
        log.info("backup receipt: %s", receipt)
        print(receipt)
    purge = enforce_retention(EVIDENCE_DIR, retention_days=args.retention_days)
    log.info("retention receipt: %s", purge)
    print(purge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
