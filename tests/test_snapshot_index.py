"""B4 regression tests — DB-backed snapshot index (query/filter/delete/backfill)."""

import numpy as np
import pytest

from src.storage.evidence import EvidenceManager

BASE_TS = 1_700_000_000.0  # fixed epoch for deterministic day filters


@pytest.fixture()
def mgr(tmp_path):
    return EvidenceManager(
        storage_dir=tmp_path / "evidence",
        max_snapshots=20,
        db_path=tmp_path / "events.db",
    )


def _frame() -> np.ndarray:
    return np.full((64, 64, 3), 128, dtype=np.uint8)


def test_save_indexes_snapshot_in_db(mgr: EvidenceManager):
    rec = mgr.save_snapshot(_frame(), ["no-helmet"], timestamp=BASE_TS)
    assert rec is not None
    snaps = mgr.query_snapshots(limit=10)
    assert len(snaps) == 1
    assert snaps[0]["filename"] == rec["filename"]
    assert "helmet" in snaps[0]["labels"].lower()
    assert snaps[0]["size_bytes"] > 0


def test_query_newest_first(mgr: EvidenceManager):
    for i in range(5):
        mgr.save_snapshot(_frame(), ["no-vest"], timestamp=BASE_TS + i)
    snaps = mgr.query_snapshots(limit=10)
    ts_list = [s["timestamp"] for s in snaps]
    assert ts_list == sorted(ts_list, reverse=True)
    assert len(snaps) == 5


def test_limit_and_cumulative_window(mgr: EvidenceManager):
    for i in range(12):
        mgr.save_snapshot(_frame(), ["no-gloves"], timestamp=BASE_TS + i)
    first = mgr.query_snapshots(limit=8)
    assert len(first) == 8
    more = mgr.query_snapshots(limit=8, offset=8)
    assert len(more) == 4
    # Windows must not overlap and must be contiguous newest-first
    first_ids = {s["filename"] for s in first}
    more_ids = {s["filename"] for s in more}
    assert not (first_ids & more_ids)
    all_ids = {s["filename"] for s in mgr.query_snapshots(limit=100)}
    assert first_ids | more_ids == all_ids


def test_day_filter(mgr: EvidenceManager):
    mgr.save_snapshot(_frame(), ["no-helmet"], timestamp=BASE_TS)
    mgr.save_snapshot(_frame(), ["no-helmet"], timestamp=BASE_TS + 60)
    day = mgr.get_snapshot_days()[0]
    assert mgr.count_snapshots(day=day) == 2
    assert mgr.count_snapshots(day="1999-01-01") == 0
    assert mgr.query_snapshots(day="1999-01-01") == []


def test_label_filter(mgr: EvidenceManager):
    mgr.save_snapshot(_frame(), ["no-helmet"], timestamp=BASE_TS)
    mgr.save_snapshot(_frame(), ["no-vest"], timestamp=BASE_TS + 1)
    assert mgr.count_snapshots(label="helmet") == 1
    assert mgr.count_snapshots(label="vest") == 1
    assert mgr.count_snapshots(label="goggles") == 0
    # LIKE-injection attempts must be neutralized by the sanitizer
    assert mgr.count_snapshots(label="%") == 0
    assert mgr.count_snapshots(label="helmet' OR 1=1 --") == 0
    assert "helmet" in mgr.get_snapshot_labels()


def test_backfill_from_disk(mgr: EvidenceManager):
    fake = mgr.storage_dir / "viol_20260101_120000_000_no-helmet.jpg"
    fake.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    snaps = mgr.query_snapshots()
    names = [s["filename"] for s in snaps]
    assert fake.name in names
    row = next(s for s in snaps if s["filename"] == fake.name)
    # timestamp derived from the filename, not the mtime
    assert 1_767_225_600 <= row["timestamp"] <= 1_767_312_000  # 2026-01-01 ±1d


def test_delete_snapshot(mgr: EvidenceManager):
    rec = mgr.save_snapshot(_frame(), ["no-vest"], timestamp=BASE_TS)
    fn = rec["filename"]
    assert (mgr.storage_dir / fn).is_file()
    assert mgr.delete_snapshot(fn) is True
    assert not (mgr.storage_dir / fn).exists()
    assert mgr.count_snapshots() == 0


def test_delete_rejects_malicious_names(mgr: EvidenceManager):
    assert mgr.delete_snapshot("../../etc/passwd") is False
    assert mgr.delete_snapshot("viol_../../evil.jpg") is False
    assert mgr.delete_snapshot("") is False
    assert mgr.delete_snapshot(None) is False  # type: ignore[arg-type]


def test_delete_missing_file_prunes_stale_row(mgr: EvidenceManager):
    stale = mgr.storage_dir / "viol_20260101_090000_000_x.jpg"
    stale.write_bytes(b"\xff\xd8fake")
    mgr.query_snapshots()  # trigger backfill so the row exists
    stale.unlink()
    assert mgr.delete_snapshot(stale.name) is False
    assert mgr.count_snapshots() == 0  # stale row self-healed away


def test_prune_removes_index_rows(mgr: EvidenceManager):
    small = EvidenceManager(
        storage_dir=mgr.storage_dir,
        max_snapshots=3,
        db_path=mgr.db_path,
    )
    for i in range(5):
        small.save_snapshot(_frame(), ["no-helmet"], timestamp=BASE_TS + i)
    files = list(small.storage_dir.glob("viol_*.jpg"))
    assert len(files) == 3
    assert small.count_snapshots() == 3
