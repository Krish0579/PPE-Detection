"""Tests for the §8 release helper (no files touched outside tmp dirs)."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.release import bumped, render_version


def test_version_bump_matrix():
    assert render_version(bumped((1, 2, 3), "major")) == "2.0.0"
    assert render_version(bumped((1, 2, 3), "minor")) == "1.3.0"
    assert render_version(bumped((1, 2, 3), "patch")) == "1.2.4"


def test_release_dry_run_changes_nothing(capsys):
    from scripts.release import main

    before_version = (PROJECT_ROOT / "src" / "__version__.py").read_text(encoding="utf-8")
    before_changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert main(["--bump", "patch", "--dry-run"]) == 0
    assert (PROJECT_ROOT / "src" / "__version__.py").read_text(encoding="utf-8") == before_version
    assert (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8") == before_changelog
    assert "dry-run" in capsys.readouterr().out
