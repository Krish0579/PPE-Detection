"""Explicit permission-based RBAC (blueprint §11).

UI and services ask ``has_permission(role, "incident.resolve")`` instead of
scattering role-name checks. The legacy coarse-grained ``src.security.auth.can``
remains for existing callers.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    OPERATOR = "operator"
    SAFETY_OFFICER = "safety_officer"
    ADMINISTRATOR = "administrator"


class Permission:
    MONITOR_VIEW = "monitor.view"
    CAMERA_SWITCH = "camera.switch"
    CAMERA_CONFIGURE = "camera.configure"
    ALERT_ACKNOWLEDGE = "alert.acknowledge"
    INCIDENT_VIEW = "incident.view"
    INCIDENT_ACKNOWLEDGE = "incident.acknowledge"
    INCIDENT_INTERVENE = "incident.intervene"
    INCIDENT_RESOLVE = "incident.resolve"
    INCIDENT_REOPEN = "incident.reopen"
    INCIDENT_DISMISS = "incident.dismiss"
    EVIDENCE_VIEW = "evidence.view"
    REPORT_VIEW = "report.view"
    REPORT_EXPORT = "report.export"
    RULE_MODIFY = "rule.modify"
    THRESHOLD_MODIFY = "threshold.modify"
    USER_MANAGE = "user.manage"
    INTEGRATION_MANAGE = "integration.manage"
    SYSTEM_CONFIGURE = "system.configure"
    SYSTEM_HEALTH_VIEW = "system.health.view"
    AUDIT_VIEW = "audit.view"


_OPERATOR = frozenset(
    {
        Permission.MONITOR_VIEW,
        Permission.CAMERA_SWITCH,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.INCIDENT_VIEW,
        Permission.INCIDENT_ACKNOWLEDGE,
        Permission.SYSTEM_HEALTH_VIEW,
    }
)
_SAFETY_OFFICER = _OPERATOR | frozenset(
    {
        Permission.INCIDENT_INTERVENE,
        Permission.INCIDENT_RESOLVE,
        Permission.INCIDENT_REOPEN,
        Permission.INCIDENT_DISMISS,
        Permission.EVIDENCE_VIEW,
        Permission.REPORT_VIEW,
        Permission.REPORT_EXPORT,
        Permission.AUDIT_VIEW,
    }
)
_ADMINISTRATOR = _SAFETY_OFFICER | frozenset(
    {
        Permission.CAMERA_CONFIGURE,
        Permission.RULE_MODIFY,
        Permission.THRESHOLD_MODIFY,
        Permission.USER_MANAGE,
        Permission.INTEGRATION_MANAGE,
        Permission.SYSTEM_CONFIGURE,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.OPERATOR: _OPERATOR,
    Role.SAFETY_OFFICER: _SAFETY_OFFICER,
    Role.ADMINISTRATOR: _ADMINISTRATOR,
}

# Legacy role names used by src.security.auth map onto the blueprint roles.
_ALIASES = {"supervisor": Role.SAFETY_OFFICER, "admin": Role.ADMINISTRATOR, "officer": Role.SAFETY_OFFICER}


def parse_role(raw: str | Role | None) -> Role | None:
    if isinstance(raw, Role):
        return raw
    text = str(raw or "").strip().lower()
    if text in _ALIASES:
        return _ALIASES[text]
    try:
        return Role(text)
    except ValueError:
        return None


def permissions_for(role: str | Role | None) -> frozenset[str]:
    parsed = parse_role(role)
    return ROLE_PERMISSIONS.get(parsed, frozenset()) if parsed else frozenset()


def has_permission(role: str | Role | None, permission: str) -> bool:
    """Deny by default: unknown roles and unknown permissions are refused."""
    return permission in permissions_for(role)


class PermissionDenied(PermissionError):
    def __init__(self, role: str | Role | None, permission: str) -> None:
        super().__init__(f"role '{role}' lacks permission '{permission}'")
        self.role = role
        self.permission = permission


def require(role: str | Role | None, permission: str) -> None:
    if not has_permission(role, permission):
        raise PermissionDenied(role, permission)
