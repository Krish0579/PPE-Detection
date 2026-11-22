from __future__ import annotations

import pytest

from src.security.rbac import Permission, PermissionDenied, Role, has_permission, parse_role, permissions_for, require


def test_role_enum():
    assert Role.OPERATOR == "operator"
    assert Role.SAFETY_OFFICER == "safety_officer"
    assert Role.ADMINISTRATOR == "administrator"

@pytest.mark.parametrize("raw, expected", [
    (Role.OPERATOR, Role.OPERATOR),
    ("operator", Role.OPERATOR),
    ("OPERATOR", Role.OPERATOR),
    ("  operator  ", Role.OPERATOR),
    ("supervisor", Role.SAFETY_OFFICER),
    ("admin", Role.ADMINISTRATOR),
    ("officer", Role.SAFETY_OFFICER),
    ("unknown", None),
    (None, None),
    ("", None),
])
def test_parse_role(raw, expected):
    assert parse_role(raw) == expected

def test_permissions_for():
    operator_perms = permissions_for(Role.OPERATOR)
    assert Permission.MONITOR_VIEW in operator_perms
    assert Permission.SYSTEM_CONFIGURE not in operator_perms
    
    admin_perms = permissions_for(Role.ADMINISTRATOR)
    assert Permission.SYSTEM_CONFIGURE in admin_perms
    assert Permission.MONITOR_VIEW in admin_perms
    
    assert permissions_for("unknown") == frozenset()
    assert permissions_for(None) == frozenset()

def test_has_permission():
    assert has_permission(Role.OPERATOR, Permission.MONITOR_VIEW) is True
    assert has_permission("admin", Permission.USER_MANAGE) is True
    assert has_permission(Role.OPERATOR, Permission.SYSTEM_CONFIGURE) is False
    assert has_permission("unknown", Permission.MONITOR_VIEW) is False
    assert has_permission(None, Permission.MONITOR_VIEW) is False

def test_require():
    # Should not raise
    require(Role.ADMINISTRATOR, Permission.SYSTEM_CONFIGURE)
    
    # Should raise
    with pytest.raises(PermissionDenied) as exc:
        require(Role.OPERATOR, Permission.SYSTEM_CONFIGURE)
    
    assert exc.value.role == Role.OPERATOR
    assert exc.value.permission == Permission.SYSTEM_CONFIGURE
    assert "lacks permission" in str(exc.value)
