from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.storage.repositories import InMemoryIncidentRepository, SQLiteIncidentRepository


class DummyIncident:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "test-1")
        self.camera_id = kwargs.get("camera_id", "cam1")
        self.zone_id = kwargs.get("zone_id", "zone1")
        self.violation = kwargs.get("violation", "no_helmet")
        self.track_id = kwargs.get("track_id", 123)
        self.state = kwargs.get("state", "new")
        self.severity = kwargs.get("severity", "high")
        self.opened_at = kwargs.get("opened_at", "2023-01-01T12:00:00Z")
        self.updated_at = kwargs.get("updated_at", "2023-01-01T12:00:00Z")
        self.is_open = kwargs.get("is_open", True)
        self.dedupe_key = (self.camera_id, self.zone_id, self.violation, self.track_id)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "violation": self.violation,
            "track_id": self.track_id,
            "state": getattr(self.state, "value", self.state),
            "severity": self.severity,
            "opened_at": self.opened_at,
            "updated_at": self.updated_at
        }

@pytest.fixture(autouse=True)
def mock_incident_record():
    with patch("src.storage.repositories.IncidentRecord") as mock_record:
        mock_record.from_dict.side_effect = lambda d: DummyIncident(**d)
        yield mock_record

@pytest.fixture(params=["in_memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "in_memory":
        yield InMemoryIncidentRepository()
    else:
        db_path = tmp_path / "incidents.db"
        r = SQLiteIncidentRepository(db_path)
        yield r
        r.close()

def test_save_and_get(repo):
    inc = DummyIncident(id="inc-1", camera_id="cam2")
    repo.save(inc)
    
    fetched = repo.get("inc-1")
    assert fetched is not None
    assert fetched.id == "inc-1"
    assert fetched.camera_id == "cam2"

def test_get_nonexistent(repo):
    assert repo.get("missing") is None

def test_find_open(repo):
    inc = DummyIncident(id="inc-2", camera_id="cam3", zone_id="z3", violation="v3", track_id=42, state="new")
    # Patch OPEN_STATES to match the test data
    state_mock = MagicMock()
    state_mock.value = "new"
    
    with patch("src.storage.repositories.OPEN_STATES", [state_mock]):
        repo.save(inc)
        found = repo.find_open(("cam3", "z3", "v3", 42))
        assert found is not None
        assert found.id == "inc-2"

def test_find_open_not_found(repo):
    found = repo.find_open(("cam1", "z1", "v1", 1))
    assert found is None

def test_list_incidents(repo):
    repo.save(DummyIncident(id="inc-3", state="resolved", opened_at="2023-01-02T12:00:00Z"))
    repo.save(DummyIncident(id="inc-4", state="new", opened_at="2023-01-01T12:00:00Z"))
    
    # Test without states filter
    all_incidents = repo.list_incidents()
    assert len(all_incidents) == 2
    # Should be sorted by opened_at descending
    assert all_incidents[0].id == "inc-3"
    
    # Test with states filter
    state_mock = MagicMock()
    state_mock.value = "new"
    filtered = repo.list_incidents(states=frozenset([state_mock]))
    assert len(filtered) == 1
    assert filtered[0].id == "inc-4"

def test_sqlite_ping(tmp_path):
    db_path = tmp_path / "ping.db"
    repo = SQLiteIncidentRepository(db_path)
    assert repo.ping() is True
    repo.close()
    assert repo.ping() is False
