"""Optional operator gate for shared / network deployments.

Default is open (single-operator on-prem workstation). Setting
``SAFE_SIGHT_AUTH_REQUIRED=true`` plus ``SAFE_SIGHT_OPERATOR_PASSWORD_SHA256``
enables a password gate. Secrets are never stored in code — only the SHA-256
hex digest is compared, with ``hmac.compare_digest`` to avoid timing leaks.
"""
from __future__ import annotations

import hashlib
import hmac


def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, expected_sha256: str) -> bool:
    if not plain or not expected_sha256:
        return False
    candidate = hash_password(plain)
    return hmac.compare_digest(candidate, expected_sha256.strip().lower())


def is_auth_configured(auth_required: bool, password_sha256: str) -> bool:
    return bool(auth_required and (password_sha256 or "").strip())


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "operator": {"view", "inspect", "export-own"},
    "supervisor": {"view", "inspect", "export-own", "acknowledge", "resolve", "export-all"},
    "admin": {"view", "inspect", "export-own", "acknowledge", "resolve", "export-all", "configure", "purge"},
}


def can(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get((role or "operator").lower(), set())
