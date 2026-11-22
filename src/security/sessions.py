"""Server-side session store with absolute and idle expiry (blueprint §11).

Tokens are 256-bit random values; only their SHA-256 digest is held in memory
so a memory dump does not directly leak live session tokens.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field

from src.security.rbac import Role, parse_role


@dataclass
class Session:
    user: str
    role: Role
    created_at: float
    last_seen: float
    attributes: dict[str, str] = field(default_factory=dict)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionStore:
    def __init__(self, ttl_sec: float = 8 * 3600, idle_sec: float = 30 * 60, max_sessions: int = 1000) -> None:
        if ttl_sec <= 0 or idle_sec <= 0:
            raise ValueError("ttl_sec and idle_sec must be positive")
        self.ttl_sec = ttl_sec
        self.idle_sec = idle_sec
        self.max_sessions = max_sessions
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, user: str, role: str | Role, now: float | None = None) -> str:
        parsed = parse_role(role)
        if not user or parsed is None:
            raise ValueError("a user and a known role are required")
        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_locked(now)
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions, key=lambda k: self._sessions[k].last_seen)
                del self._sessions[oldest]
            self._sessions[_digest(token)] = Session(user=user, role=parsed, created_at=now, last_seen=now)
        return token

    def validate(self, token: str, now: float | None = None) -> Session | None:
        """Return the live session (refreshing idle time) or ``None`` if expired/unknown."""
        if not token:
            return None
        now = time.time() if now is None else now
        key = _digest(token)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if now - session.created_at >= self.ttl_sec or now - session.last_seen >= self.idle_sec:
                del self._sessions[key]
                return None
            session.last_seen = now
            return session

    def revoke(self, token: str) -> bool:
        with self._lock:
            return self._sessions.pop(_digest(token or ""), None) is not None

    def revoke_user(self, user: str) -> int:
        with self._lock:
            keys = [k for k, s in self._sessions.items() if s.user == user]
            for key in keys:
                del self._sessions[key]
            return len(keys)

    def purge_expired(self, now: float | None = None) -> int:
        with self._lock:
            return self._purge_locked(time.time() if now is None else now)

    def _purge_locked(self, now: float) -> int:
        expired = [
            k
            for k, s in self._sessions.items()
            if now - s.created_at >= self.ttl_sec or now - s.last_seen >= self.idle_sec
        ]
        for key in expired:
            del self._sessions[key]
        return len(expired)

    def __len__(self) -> int:
        return len(self._sessions)
