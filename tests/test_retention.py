from __future__ import annotations

import os
import time

import pytest

from src.storage.retention import RetentionPolicy, prune_directory


def test_retention_policy_defaults():
    policy = RetentionPolicy()
    assert policy.evidence_days == 30
    assert policy.audit_days == 365
    assert policy.reports_days == 180
    assert policy.raw_frames_days == 2

def test_retention_policy_validation():
    with pytest.raises(ValueError):
        RetentionPolicy(evidence_days=0)
    with pytest.raises(ValueError):
        RetentionPolicy(audit_days=-5)

def test_retention_policy_from_env():
    env = {
        "PPE_EVIDENCE_RETENTION_DAYS": "45",
        "SAFE_SIGHT_AUDIT_RETENTION_DAYS": "invalid",
        "SAFE_SIGHT_REPORT_RETENTION_DAYS": "100"
    }
    policy = RetentionPolicy.from_env(env)
    assert policy.evidence_days == 45
    assert policy.audit_days == 365  # fallback to default
    assert policy.reports_days == 100
    assert policy.raw_frames_days == 2

def test_prune_directory(tmp_path):
    # Setup test directory
    (tmp_path / "old.txt").write_text("old")
    (tmp_path / "new.txt").write_text("new")
    
    # Manipulate mtime
    now = time.time()
    os.utime(tmp_path / "old.txt", (now - 86400 * 5, now - 86400 * 5))
    os.utime(tmp_path / "new.txt", (now - 86400 * 1, now - 86400 * 1))
    
    # Test dry run
    result = prune_directory(tmp_path, max_age_days=3, dry_run=True, now=now)
    assert result.scanned == 2
    assert len(result.deleted) == 1
    assert "old.txt" in result.deleted
    assert (tmp_path / "old.txt").exists()  # Not actually deleted
    
    # Test actual prune
    result = prune_directory(tmp_path, max_age_days=3, dry_run=False, now=now)
    assert result.scanned == 2
    assert len(result.deleted) == 1
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").exists()

def test_prune_directory_invalid_dir():
    result = prune_directory("nonexistent_directory_999", max_age_days=1)
    assert result.scanned == 0
    assert result.deleted == ()
