"""Zone-aware safety policy domain model and compliance evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViolationType(str, Enum):
    MISSING_PPE = "missing_ppe"
    RESTRICTED_ENTRY = "restricted_zone_entry"
    EXCESSIVE_DWELL = "excessive_dwell"
    UNKNOWN_ZONE = "unknown_zone"
    UNKNOWN_WORKER = "unknown_worker"
    LOW_CONFIDENCE = "insufficient_detection_confidence"


@dataclass(frozen=True)
class ZonePolicy:
    zone_id: str
    name: str
    zone_type: str
    required_ppe: frozenset[str] = field(default_factory=frozenset)
    max_dwell_seconds: float | None = None
    regulatory_reference: str = ""
    description: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class ComplianceViolation:
    type: ViolationType
    message: str
    severity: str = "WARNING"
    ppe: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ComplianceResult:
    compliant: bool
    violations: tuple[ComplianceViolation, ...]
    zone: ZonePolicy | None


DEFAULT_ZONE_POLICIES = (
    ZonePolicy("Z-01", "Assembly Line A", "Standard", frozenset({"helmet", "vest"}), description="Assembly operations"),
    ZonePolicy(
        "Z-02",
        "Heavy Machinery Bay",
        "Restricted",
        frozenset({"helmet", "vest", "boots", "gloves", "goggles"}),
        120.0,
        description="Restricted heavy machinery area",
    ),
    ZonePolicy(
        "Z-03",
        "Logistics & Forklift Corridor",
        "Standard",
        frozenset({"helmet", "vest", "boots"}),
        description="Forklift and logistics corridor",
    ),
)


class ZonePolicyEngine:
    """Pure domain service; UI and inference layers depend only on this contract."""

    def __init__(self, policies: tuple[ZonePolicy, ...] = DEFAULT_ZONE_POLICIES) -> None:
        self._policies = {policy.name: policy for policy in policies if policy.enabled}
        self._by_id = {policy.zone_id: policy for policy in policies if policy.enabled}

    def get_zone_policy(self, zone_name: str) -> ZonePolicy | None:
        return self._policies.get(zone_name)

    def get_policy(self, zone_name_or_id: str) -> ZonePolicy | None:
        return self._policies.get(zone_name_or_id) or self._by_id.get(zone_name_or_id)

    def get_by_id(self, zone_id: str) -> ZonePolicy | None:
        return self._by_id.get(zone_id)

    def evaluate_worker_zone_compliance(
        self,
        worker: Any,
        policy: ZonePolicy | None = None,
        *,
        min_confidence: float = 0.0,
    ) -> ComplianceResult:
        zone_name = getattr(worker, "zone", "")
        selected = policy or self.get_zone_policy(zone_name)
        violations: list[ComplianceViolation] = []
        if selected is None:
            violations.append(ComplianceViolation(ViolationType.UNKNOWN_ZONE, f"Unknown zone: {zone_name}"))
            return ComplianceResult(False, tuple(violations), None)

        if getattr(worker, "worker_id", None) is None:
            violations.append(ComplianceViolation(ViolationType.UNKNOWN_WORKER, "Worker identity is unavailable"))

        if selected.zone_type.lower() == "restricted" and getattr(worker, "is_restricted_zone", False):
            violations.append(
                ComplianceViolation(
                    ViolationType.RESTRICTED_ENTRY, "Restricted-zone entry requires authorization", "HIGH"
                )
            )

        dwell = float(getattr(worker, "dwell_seconds", 0.0) or 0.0)
        if selected.max_dwell_seconds is not None and dwell > selected.max_dwell_seconds:
            violations.append(
                ComplianceViolation(ViolationType.EXCESSIVE_DWELL, "Maximum configured dwell time exceeded", "HIGH")
            )

        gear = getattr(worker, "gear", {}) or {}
        for item in selected.required_ppe:
            status = str(gear.get(item, "UNKNOWN")).upper()
            if status == "VIOLATION":
                violations.append(
                    ComplianceViolation(ViolationType.MISSING_PPE, f"Required PPE missing: {item}", "HIGH", item)
                )
            elif status == "UNKNOWN":
                violations.append(
                    ComplianceViolation(
                        ViolationType.LOW_CONFIDENCE,
                        f"Required PPE not confidently observed: {item}",
                        "WARNING",
                        item,
                        min_confidence,
                    )
                )

        return ComplianceResult(not violations, tuple(violations), selected)


def get_zone_policy(zone_name: str) -> ZonePolicy | None:
    return ZonePolicyEngine().get_zone_policy(zone_name)


def evaluate_worker_zone_compliance(worker: Any, policy: ZonePolicy | None = None) -> ComplianceResult:
    return ZonePolicyEngine().evaluate_worker_zone_compliance(worker, policy)
