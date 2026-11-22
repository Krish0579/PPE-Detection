from __future__ import annotations

import hashlib

import pytest

from src.security.passwords import (
    _ARGON2,
    active_scheme,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)


def test_validate_password_strength():
    assert len(validate_password_strength("short1!")) > 0  # < 12 chars
    assert len(validate_password_strength("alllowercaseonly")) > 0  # only 1 character class
    assert len(validate_password_strength("ValidPassword123!")) == 0
    assert len(validate_password_strength("")) > 0

def test_hash_and_verify_password():
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False
    assert verify_password(password, "") is False
    assert verify_password("", hashed) is False

def test_hash_empty_password_raises():
    with pytest.raises(ValueError, match="password must not be empty"):
        hash_password("")

def test_legacy_sha256_verification():
    password = "MySecretPassword123!"
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    
    assert verify_password(password, legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False
    assert needs_rehash(legacy_hash) is True

def test_needs_rehash():
    password = "MySecretPassword123!"
    hashed = hash_password(password)
    
    # The newly created hash shouldn't need a rehash (assuming default params haven't changed)
    assert needs_rehash(hashed) is False
    
    # Empty string should need rehash
    assert needs_rehash("") is True

def test_active_scheme():
    scheme = active_scheme()
    if _ARGON2 is not None:
        assert scheme == "argon2id"
    else:
        assert scheme == "scrypt"

def test_verify_invalid_encoded():
    assert verify_password("pass", "invalid_encoded_string_without_prefix") is False
    assert verify_password("pass", "$scrypt$invalid_params$salt$digest") is False
