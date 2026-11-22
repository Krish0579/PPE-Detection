from __future__ import annotations

import pytest

from src.security.rbac import Role
from src.security.sessions import SessionStore


def test_session_create_and_validate():
    store = SessionStore(ttl_sec=3600, idle_sec=1800)
    
    now = 1000.0
    token = store.create("user1", "operator", now=now)
    assert token is not None
    
    session = store.validate(token, now=now)
    assert session is not None
    assert session.user == "user1"
    assert session.role == Role.OPERATOR
    assert session.created_at == now
    assert session.last_seen == now

def test_session_validate_expired_idle():
    store = SessionStore(ttl_sec=3600, idle_sec=1800)
    token = store.create("user1", Role.OPERATOR, now=1000.0)
    
    # Advance past idle_sec
    assert store.validate(token, now=1000.0 + 1801.0) is None
    # Token should be removed
    assert len(store) == 0

def test_session_validate_expired_ttl():
    store = SessionStore(ttl_sec=3600, idle_sec=1800)
    token = store.create("user1", Role.OPERATOR, now=1000.0)
    
    # Advance past ttl_sec (with activity inside idle time, but total ttl exceeded)
    # wait, validate checks if now - created_at >= ttl_sec
    assert store.validate(token, now=1000.0 + 3601.0) is None

def test_session_revoke():
    store = SessionStore()
    token = store.create("user1", Role.OPERATOR)
    
    assert store.revoke(token) is True
    assert store.validate(token) is None
    assert store.revoke("invalid") is False

def test_session_revoke_user():
    store = SessionStore()
    token1 = store.create("user1", Role.OPERATOR)
    token2 = store.create("user1", Role.ADMINISTRATOR)
    token3 = store.create("user2", Role.OPERATOR)
    
    assert store.revoke_user("user1") == 2
    assert store.validate(token1) is None
    assert store.validate(token2) is None
    assert store.validate(token3) is not None

def test_session_purge_expired():
    store = SessionStore(ttl_sec=3600, idle_sec=1800)
    store.create("user1", Role.OPERATOR, now=1000.0)
    store.create("user2", Role.OPERATOR, now=2000.0)
    
    # At time 3000, user1 (idle for 2000 > 1800) should be purged, user2 (idle for 1000) kept
    purged = store.purge_expired(now=3000.0)
    assert purged == 1
    assert len(store) == 1

def test_session_max_sessions():
    store = SessionStore(max_sessions=2)
    store.create("user1", Role.OPERATOR, now=1000.0)
    store.create("user2", Role.OPERATOR, now=1001.0)
    store.create("user3", Role.OPERATOR, now=1002.0)
    
    # user1 should have been evicted
    assert len(store) == 2
    assert store.revoke_user("user1") == 0
    assert store.revoke_user("user2") == 1

def test_invalid_create():
    store = SessionStore()
    with pytest.raises(ValueError):
        store.create("", Role.OPERATOR)
    with pytest.raises(ValueError):
        store.create("user1", "unknown_role")
