"""Configurable safety rule engine with temporal confirmation (blueprint §6-§7).

PPE decisions are *not* hard-coded in the detector. A :class:`SafetyRule`
declares which PPE a zone requires, the severity, how long a condition must
persist before it is confirmed, and how it escalates. The engine evaluates
:class:`~src.core.models.DetectionResult` objects and emits
:class:`~src.core.models.SafetyEvent` only for confirmed, persistent breaches,
so a single noisy frame never creates an incident.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.models import DetectionResult, PersonObservation, SafetyEvent, Severity


@dataclass(frozen=True)
class SafetyRule:
    rule_id: str
    zone_id: str
    required_ppe: frozenset[str] = field(default_factory=frozenset)
    severity: Severity = Severity.WARNING
    confirm_seconds: float = 2.0
    clear_seconds: float = 3.0
    min_confidence: float = 0.35
    treat_unknown_as_missing: bool = False
    escalate_after_seconds: float | None = None
    max_dwell_seconds: float | None = None
    enabled: bool = True
    version: int = 1

    def __post_init__(self) -> None:
        if not self.rule_id or not self.zone_id:
            raise ValueError("rule_id and zone_id are required")
        if self.confirm_seconds < 0 or self.clear_seconds < 0:
            raise ValueError("confirmation windows must be non-negative")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0, 1]")


@dataclass
class _ConditionTrack:
    first_seen: float
    last_seen: float
    confirmed: bool = False
    escalated: bool = False


class TemporalConfirmer:
    """Tracks how long each (rule, camera, track, violation) condition has persisted."""

    def __init__(self) -> None:
        self._tracks: dict[tuple[str, str, int | None, str], _ConditionTrack] = {}

    def observe(self, key: tuple[str, str, int | None, str], now: float) -> _ConditionTrack:
        track = self._tracks.get(key)
        if track is None:
            track = _ConditionTrack(first_seen=now, last_seen=now)
            self._tracks[key] = track
        track.last_seen = now
        return track

    def expire(self, now: float, clear_after: dict[str, float]) -> list[tuple[str, str, int | None, str]]:
        """Drop conditions not observed within their rule's clear window."""
        cleared = []
        for key, track in list(self._tracks.items()):
            if now - track.last_seen >= clear_after.get(key[0], 3.0):
                cleared.append(key)
                del self._tracks[key]
        return cleared

    def __len__(self) -> int:
        return len(self._tracks)


class RuleEngine:
    def __init__(self, rules: list[SafetyRule] | tuple[SafetyRule, ...] = ()) -> None:
        self._rules: dict[str, SafetyRule] = {}
        self._confirmer = TemporalConfirmer()
        for rule in rules:
            self.upsert(rule)

    # --- administration -------------------------------------------------
    def upsert(self, rule: SafetyRule) -> None:
        self._rules[rule.rule_id] = rule

    def remove(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def rules_for_zone(self, zone_id: str) -> list[SafetyRule]:
        return [r for r in self._rules.values() if r.enabled and r.zone_id in (zone_id, "*")]

    @property
    def rules(self) -> tuple[SafetyRule, ...]:
        return tuple(self._rules.values())

    # --- evaluation -----------------------------------------------------
    def _violations(self, rule: SafetyRule, person: PersonObservation) -> list[str]:
        if person.confidence < rule.min_confidence:
            return []
        missing = []
        for item in sorted(rule.required_ppe):
            state = person.ppe_state(item)
            if state == "MISSING" or (state == "UNKNOWN" and rule.treat_unknown_as_missing):
                missing.append(f"missing_{item}")
        return missing

    def evaluate(self, result: DetectionResult, now: float | None = None) -> list[SafetyEvent]:
        now = result.timestamp if now is None else now
        events: list[SafetyEvent] = []
        for person in result.persons:
            for rule in self.rules_for_zone(person.zone_id):
                for violation in self._violations(rule, person):
                    key = (rule.rule_id, result.camera_id, person.track_id, violation)
                    track = self._confirmer.observe(key, now)
                    persisted = now - track.first_seen
                    event = self._maybe_emit(rule, result, person, violation, track, persisted)
                    if event is not None:
                        events.append(event)
        self._confirmer.expire(now, {r.rule_id: r.clear_seconds for r in self._rules.values()})
        return events

    def _maybe_emit(
        self,
        rule: SafetyRule,
        result: DetectionResult,
        person: PersonObservation,
        violation: str,
        track: _ConditionTrack,
        persisted: float,
    ) -> SafetyEvent | None:
        severity = rule.severity
        if not track.confirmed and persisted >= rule.confirm_seconds:
            track.confirmed = True
        elif (
            track.confirmed
            and not track.escalated
            and rule.escalate_after_seconds is not None
            and persisted >= rule.escalate_after_seconds
        ):
            track.escalated = True
            severity = rule.severity.escalate()
        else:
            return None
        return SafetyEvent(
            rule_id=rule.rule_id,
            camera_id=result.camera_id,
            zone_id=person.zone_id,
            violation=violation,
            severity=severity,
            track_id=person.track_id,
            first_seen=track.first_seen,
            confirmed_at=result.timestamp,
            confidence=person.confidence,
            details={"persisted_seconds": round(persisted, 3), "rule_version": rule.version},
        )

    @property
    def pending_conditions(self) -> int:
        return len(self._confirmer)
