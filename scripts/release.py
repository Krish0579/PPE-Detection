#!/usr/bin/env python3
"""Release helper enforcing the §8 release process (version bump + changelog + gate).

Usage:
    python3 scripts/release.py --bump patch --dry-run
    python3 scripts/release.py --bump minor

Updates ``src/__version__.py``, prepends a CHANGELOG entry, then runs the offline
readiness gate. Tagging (``git tag vX.Y.Z``) is left to the operator on purpose.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "src" / "__version__.py"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
GATE = PROJECT_ROOT / "scripts" / "prod_readiness_check.py"

_VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


def read_version() -> tuple[int, int, int]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise SystemExit(f"Cannot parse version from {VERSION_FILE}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bumped(current: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    if part == "patch":
        return major, minor, patch + 1
    raise SystemExit("--bump must be major, minor, or patch")


def render_version(version: tuple[int, int, int]) -> str:
    return f"{version[0]}.{version[1]}.{version[2]}"


def prepend_changelog(version: str, notes: str) -> None:
    entry = f"\n## [{version}] — {datetime.now(timezone.utc).date().isoformat()}\n\n{notes.strip()}\n"
    text = CHANGELOG.read_text(encoding="utf-8")
    anchor = "Release discipline:"
    position = text.find(anchor)
    if position == -1:
        raise SystemExit("CHANGELOG anchor line not found; refusing to edit")
    line_end = text.find("\n", position)
    CHANGELOG.write_text(text[: line_end + 1] + entry + text[line_end + 1 :], encoding="utf-8")


def run_gate() -> int:
    completed = subprocess.run([sys.executable, str(GATE)], cwd=str(PROJECT_ROOT), check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump version, update changelog, run readiness gate.")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    parser.add_argument("--notes", default="### Changed\n\n- Describe customer-visible changes here.\n")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    args = parser.parse_args(argv)

    current = read_version()
    new_version = render_version(bumped(current, args.bump))
    print(f"version: {render_version(current)} -> {new_version}")
    if args.dry_run:
        print("dry-run: no files changed")
        return 0

    VERSION_FILE.write_text(
        _VERSION_RE.sub(f'__version__ = "{new_version}"', VERSION_FILE.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    prepend_changelog(new_version, args.notes)
    print(f"updated {VERSION_FILE.name} and CHANGELOG.md")

    if args.skip_gate:
        print("gate skipped (--skip-gate); do not ship without a green gate")
        return 0
    code = run_gate()
    print(f"readiness gate exit: {code}")
    if code != 0:
        print("BLOCKED: gate failed — fix findings before tagging a release")
    else:
        print(f"ready to tag: git tag v{new_version}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
