"""Optional operator gate for shared / network deployments.

Default is open (single-operator on-prem workstation). Setting
``SAFE_SIGHT_AUTH_REQUIRED=true`` plus ``SAFE_SIGHT_OPERATOR_PASSWORD_SHA256``
enables a password gate. Secrets are never stored in code — only the SHA-256
hex digest is compared, with ``hmac.compare_digest`` to avoid timing leaks.

M1 Trust (plan W1.1/W1.2) adds:
- Multi-role resolution — optional ``SAFE_SIGHT_ADMIN_PASSWORD_SHA256`` and
  ``SAFE_SIGHT_SUPERVISOR_PASSWORD_SHA256`` upgrade a session to admin /
  supervisor. When neither is configured the deployment stays in *station
  mode*: the single operator keeps full access (backwards compatible).
- Login throttling — per-process exponential lockout after repeated failures.
- Session expiry helpers — absolute TTL and idle timeout, pure functions so
  the gate stays trivially testable.
"""

from __future__ import annotations

import hashlib
import hmac
import time

# --- Throttling (per-process; single-operator deployments get single-process) ---
_MAX_FAILURES = 5
_BASE_LOCK_SEC = 5.0
_MAX_LOCK_SEC = 900.0

_throttle_state: dict[str, float] = {"failures": 0.0, "locked_until": 0.0}


def reset_throttle_state() -> None:
    """Reset the login throttle (test seam + manual unlock via restart)."""
    _throttle_state["failures"] = 0.0
    _throttle_state["locked_until"] = 0.0


def lockout_remaining(now: float | None = None) -> float:
    """Seconds remaining in the current lockout (0 when not locked)."""
    now = time.time() if now is None else now
    return max(0.0, _throttle_state["locked_until"] - now)


def register_login_failure(now: float | None = None) -> float:
    """Record a failed attempt; returns the lockout duration just imposed."""
    now = time.time() if now is None else now
    _throttle_state["failures"] += 1.0
    if _throttle_state["failures"] >= _MAX_FAILURES:
        exponent = _throttle_state["failures"] - _MAX_FAILURES
        lock = min(_BASE_LOCK_SEC * (2.0**exponent), _MAX_LOCK_SEC)
        _throttle_state["locked_until"] = now + lock
        return lock
    return 0.0


def register_login_success() -> None:
    reset_throttle_state()


def throttled() -> bool:
    return lockout_remaining() > 0.0


# --- Password / role resolution -------------------------------------------------
def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, expected_sha256: str) -> bool:
    if not plain or not expected_sha256:
        return False
    candidate = hash_password(plain)
    return hmac.compare_digest(candidate, expected_sha256.strip().lower())


def is_auth_configured(auth_required: bool, password_sha256: str) -> bool:
    return bool(auth_required and (password_sha256 or "").strip())


def resolve_role(
    password: str,
    operator_sha256: str = "",
    supervisor_sha256: str = "",
    admin_sha256: str = "",
) -> str | None:
    """Map a submitted password to the highest-privilege role it unlocks.

    Returns ``None`` when the password matches no configured hash. The most
    privileged match wins so a shared password cannot accidentally downgrade
    an administrator.
    """
    if admin_sha256 and verify_password(password, admin_sha256):
        return "admin"
    if supervisor_sha256 and verify_password(password, supervisor_sha256):
        return "supervisor"
    if operator_sha256 and verify_password(password, operator_sha256):
        return "operator"
    return None


# --- RBAC -----------------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "operator": {"view", "inspect", "export-own"},
    "supervisor": {"view", "inspect", "export-own", "acknowledge", "resolve", "export-all"},
    "admin": {"view", "inspect", "export-own", "acknowledge", "resolve", "export-all", "configure", "purge"},
}


def can(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get((role or "operator").lower(), set())


def effective_role(session_role: str, *, admin_configured: bool, supervisor_configured: bool) -> str:
    """Station-mode degradation: when no elevated role is configured, the
    single operator keeps full access (W1.1 without breaking existing
    deployments). Elevated hashes must exist before the session role is
    actually constrained."""
    if not admin_configured and not supervisor_configured:
        return "admin"
    return (session_role or "operator").lower()


def session_expired(authenticated_at: float, now: float, ttl_sec: float) -> bool:
    """Absolute session TTL check."""
    return (now - authenticated_at) >= max(0.0, ttl_sec)


def session_idle_expired(last_seen: float, now: float, idle_sec: float) -> bool:
    """Idle re-auth check — measured between script runs."""
    return (now - last_seen) >= max(0.0, idle_sec)
