"""Versioned, administrator-maintained mapping from PPE requirements to standard citations."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.core.models import utc_now_iso

COMPLIANCE_DISCLAIMER = (
    "Automated detections indicate observed conditions against configured requirements. "
    "They are not legal certification and not a complete determination of facility compliance; "
    "human review is required."
)


@dataclass(frozen=True)
class RequirementReference:
    ppe_item: str
    standard: str
    citation: str
    title: str
    jurisdiction: str = "US"
    notes: str = ""


_DEFAULT_REFERENCES: tuple[RequirementReference, ...] = (
    RequirementReference("helmet", "OSHA", "29 CFR 1910.135", "Head Protection"),
    RequirementReference("vest", "ANSI/ISEA", "107-2020", "High-Visibility Safety Apparel"),
    RequirementReference("goggles", "OSHA", "29 CFR 1910.133", "Eye and Face Protection"),
    RequirementReference("gloves", "OSHA", "29 CFR 1910.138", "Hand Protection"),
    RequirementReference("boots", "OSHA", "29 CFR 1910.136", "Foot Protection"),
    RequirementReference("mask", "OSHA", "29 CFR 1910.134", "Respiratory Protection"),
    RequirementReference("*", "OSHA", "29 CFR 1910.132", "General Requirements (PPE hazard assessment)"),
)

# Detector vocabulary → canonical PPE item.
_ALIASES = {
    "hardhat": "helmet",
    "hard_hat": "helmet",
    "goggle": "goggles",
    "glasses": "goggles",
    "glass": "goggles",
    "glove": "gloves",
    "boot": "boots",
    "shoe": "boots",
    "shoes": "boots",
    "safety_vest": "vest",
    "respirator": "mask",
}


def canonical_item(raw: str) -> str:
    text = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = text.removeprefix("missing_")
    text = text.removeprefix("no_")
    return _ALIASES.get(text, text)


class CitationRegistry:
    def __init__(
        self,
        references: tuple[RequirementReference, ...] | list[RequirementReference] = (),
        *,
        version: int = 1,
        updated_by: str = "system",
        updated_at: str = "",
    ) -> None:
        self._refs: dict[str, list[RequirementReference]] = {}
        for ref in references:
            self._refs.setdefault(canonical_item(ref.ppe_item) if ref.ppe_item != "*" else "*", []).append(ref)
        self.version = version
        self.updated_by = updated_by
        self.updated_at = updated_at or utc_now_iso()
        self._lock = threading.Lock()

    def references_for(self, violation_or_item: str) -> list[RequirementReference]:
        item = canonical_item(violation_or_item)
        with self._lock:
            return list(self._refs.get(item, [])) + list(self._refs.get("*", []))

    def update(self, references: list[RequirementReference], *, actor: str) -> int:
        """Replace mappings atomically and bump the version (audited by the caller)."""
        if not actor:
            raise ValueError("actor is required to update compliance mappings")
        new: dict[str, list[RequirementReference]] = {}
        for ref in references:
            if not ref.citation or not ref.standard:
                raise ValueError(f"incomplete reference for {ref.ppe_item!r}")
            new.setdefault(canonical_item(ref.ppe_item) if ref.ppe_item != "*" else "*", []).append(ref)
        with self._lock:
            self._refs = new
            self.version += 1
            self.updated_by = actor
            self.updated_at = utc_now_iso()
            return self.version

    def describe(self, violation: str) -> dict[str, Any]:
        """Report-ready structure distinguishing detected condition, requirement and references."""
        return {
            "detected_condition": violation,
            "configured_requirement": canonical_item(violation),
            "references": [asdict(r) for r in self.references_for(violation)],
            "mapping_version": self.version,
            "human_review_required": True,
            "disclaimer": COMPLIANCE_DISCLAIMER,
        }

    # --- persistence ---------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            refs = [asdict(r) for items in self._refs.values() for r in items]
        return {"version": self.version, "updated_by": self.updated_by, "updated_at": self.updated_at, "refs": refs}

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)

    @classmethod
    def load(cls, path: str | Path) -> CitationRegistry:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        refs = [RequirementReference(**r) for r in data.get("refs", [])]
        return cls(
            refs,
            version=int(data.get("version", 1)),
            updated_by=str(data.get("updated_by", "system")),
            updated_at=str(data.get("updated_at", "")),
        )


def default_registry() -> CitationRegistry:
    return CitationRegistry(_DEFAULT_REFERENCES)
