"""Class semantics, token analysis, and alias mappings for SAFE SIGHT AI.

Maps model output labels to semantic concepts: compliance, violation, person,
and assigns consistent safety-standard colors.
"""

from __future__ import annotations

from src.config.settings import BGR_AMBER, BGR_BLUE, BGR_GREEN, BGR_RED, THEME_LIGHT

PPE_CONFIG_ALIASES = {
    "person": ["person", "worker", "people", "human"],
    "helmet": ["helmet", "hardhat", "hard-hat"],
    "vest": ["vest", "safety_vest", "safety-vest"],
    "boots": ["boots", "safety_boots", "safety-boots", "shoes"],
    "gloves": ["gloves", "glove", "safety_gloves"],
    "goggles": ["goggles", "goggle", "safety_glasses", "eye_protection", "glasses"],
    "no_helmet": ["no_helmet", "no-helmet", "no-hardhat", "without-helmet", "without_helmet"],
    "no_vest": ["no_vest", "no-vest", "without-vest", "without_vest"],
    "no_boots": ["no_boots", "no-boots", "without-boots", "without_boots"],
    "no_gloves": ["no_gloves", "no-gloves", "without-gloves", "without_gloves"],
    "no_goggles": ["no_goggle", "no-goggle", "no_goggles", "no-goggles", "without-goggles", "without_goggles"],
}

VIOLATION_TOKENS = ("no-", "no_", "no ", "without", "missing", "off-", "violation", "unprotected")

COMPLIANCE_TOKENS = (
    "helmet",
    "hardhat",
    "hard-hat",
    "vest",
    "mask",
    "gloves",
    "goggles",
    "boots",
    "shoes",
    "glasses",
    "shield",
    "harness",
    "ear-protection",
)

PERSON_TOKENS = ("person", "worker", "people", "human")


def normalize(label: str) -> str:
    """Normalize label for consistent substring and dictionary lookups."""
    return label.strip().lower().replace("_", "-").replace("  ", " ")


def is_violation(label: str) -> bool:
    """True when the class explicitly represents missing PPE or a safety violation."""
    n = normalize(label)
    return any(n.startswith(t.replace("_", "-")) or t in n for t in VIOLATION_TOKENS)


def is_person(label: str) -> bool:
    """True when the label represents a human worker."""
    n = normalize(label)
    return any(t in n for t in PERSON_TOKENS) and not is_violation(n)


def is_compliance(label: str) -> bool:
    """True when the label represents worn, compliant protective equipment."""
    n = normalize(label)
    return (not is_violation(n)) and any(t in n for t in COMPLIANCE_TOKENS)


def is_helmet(label: str) -> bool:
    """True when the class represents head protection (present or missing)."""
    n = normalize(label)
    return any(t in n for t in ("helmet", "hardhat", "hard-hat"))


def is_vest(label: str) -> bool:
    """True when the class represents torso protection (present or missing)."""
    n = normalize(label)
    return "vest" in n


def is_boots(label: str) -> bool:
    """True when the class represents foot protection (present or missing)."""
    n = normalize(label)
    return any(t in n for t in ("boot", "shoe"))


def is_gloves(label: str) -> bool:
    """True when the class represents hand protection (present or missing)."""
    n = normalize(label)
    return "glove" in n


def is_goggles(label: str) -> bool:
    """True when the class represents eye protection (present or missing)."""
    n = normalize(label)
    return any(t in n for t in ("goggle", "glass", "eye"))


def get_category(label: str) -> str:
    """High-level semantic categorization."""
    if is_violation(label):
        return "VIOLATION"
    if is_compliance(label):
        return "COMPLIANCE"
    if is_person(label):
        return "PERSON"
    return "NEUTRAL"


def bgr_for(label: str) -> tuple[int, int, int]:
    """Return OpenCV BGR color for this label."""
    if is_violation(label):
        return BGR_RED
    if is_compliance(label):
        return BGR_GREEN
    if is_person(label):
        return BGR_BLUE
    return BGR_AMBER


def hex_for(label: str, theme: dict | None = None) -> str:
    """Return CSS Hex color for UI components."""
    T = theme if theme is not None else THEME_LIGHT
    if is_violation(label):
        return T["red"]
    if is_compliance(label):
        return T["green"]
    if is_person(label):
        return T["blue"]
    return T["amber"]


LABEL_DISPLAY_NAMES = {
    "helmet": "Helmet",
    "vest": "Vest",
    "boots": "Boots",
    "gloves": "Gloves",
    "goggles": "Goggles",
    "person": "Worker",
    "no-helmet": "No Helmet",
    "no_helmet": "No Helmet",
    "no-vest": "No Vest",
    "no_vest": "No Vest",
    "no-boots": "No Boots",
    "no_boots": "No Boots",
    "no-gloves": "No Gloves",
    "no_gloves": "No Gloves",
    "no-goggle": "No Goggles",
    "no_goggle": "No Goggles",
    "no-goggles": "No Goggles",
    "no_goggles": "No Goggles",
    "none": "Background",
}


def format_label(label: str) -> str:
    """Format label string for human-readable display."""
    n = normalize(label)
    if n in LABEL_DISPLAY_NAMES:
        return LABEL_DISPLAY_NAMES[n]
    clean = n.replace("-", " ")
    return clean.title()
