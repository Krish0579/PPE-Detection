"""Modern password hashing (blueprint §11).

Uses Argon2id via ``argon2-cffi`` when installed; otherwise falls back to the
standard-library memory-hard ``scrypt`` KDF. Both produce self-describing
encoded hashes so the scheme can be upgraded later (see :func:`needs_rehash`).
Legacy unsalted SHA-256 digests used by ``src.security.auth`` are verified
only for migration and always report ``needs_rehash``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

try:  # pragma: no cover - optional dependency
    from argon2 import PasswordHasher as _Argon2Hasher
    from argon2 import exceptions as _argon2_exceptions

    _ARGON2 = _Argon2Hasher()
except ImportError:  # pragma: no cover - environment dependent
    _ARGON2 = None
    _argon2_exceptions = None

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_PREFIX = "$scrypt$"
_MIN_PASSWORD_LENGTH = 12


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text + "=" * (-len(text) % 4))


def validate_password_strength(password: str) -> list[str]:
    problems = []
    password = password or ""
    if len(password) < _MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {_MIN_PASSWORD_LENGTH} characters")
    classes = sum(
        (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
    )
    if classes < 2:
        problems.append("must mix at least two of: lowercase, uppercase, digits, symbols")
    return problems


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    if _ARGON2 is not None:
        return _ARGON2.hash(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=128 * 1024 * 1024, dklen=32
    )
    return f"{_SCRYPT_PREFIX}n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def _verify_scrypt(password: str, encoded: str) -> bool:
    try:
        params, salt_b64, digest_b64 = encoded[len(_SCRYPT_PREFIX) :].split("$")
        values = dict(item.split("=") for item in params.split(","))
        n, r, p = int(values["n"]), int(values["r"]), int(values["p"])
        expected = _unb64(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_unb64(salt_b64), n=n, r=r, p=p, maxmem=128 * 1024 * 1024, dklen=len(expected)
        )
    except (ValueError, KeyError):
        return False
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, encoded: str) -> bool:
    if not password or not encoded:
        return False
    encoded = encoded.strip()
    if encoded.startswith(_SCRYPT_PREFIX):
        return _verify_scrypt(password, encoded)
    if encoded.startswith("$argon2"):
        if _ARGON2 is None:
            return False
        try:
            return bool(_ARGON2.verify(encoded, password))
        except _argon2_exceptions.VerificationError:  # type: ignore[union-attr]
            return False
        except _argon2_exceptions.InvalidHashError:  # type: ignore[union-attr]
            return False
    if len(encoded) == 64 and all(c in "0123456789abcdefABCDEF" for c in encoded):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, encoded.lower())
    return False


def needs_rehash(encoded: str) -> bool:
    encoded = (encoded or "").strip()
    if encoded.startswith("$argon2"):
        return _ARGON2 is None or bool(_ARGON2.check_needs_rehash(encoded))
    if encoded.startswith(_SCRYPT_PREFIX):
        return _ARGON2 is not None or f"n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}" not in encoded
    return True


def active_scheme() -> str:
    return "argon2id" if _ARGON2 is not None else "scrypt"
