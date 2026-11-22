"""Compliance mapping layer (blueprint §9).

Regulatory references are kept separate from detection logic and are
versioned and administrator-maintained. Automated detection is never
represented as legal certification or a complete determination of facility
compliance — every mapping output carries :data:`COMPLIANCE_DISCLAIMER`.
"""

from src.compliance.mappings import (
    COMPLIANCE_DISCLAIMER,
    CitationRegistry,
    RequirementReference,
    default_registry,
)

__all__ = ["COMPLIANCE_DISCLAIMER", "CitationRegistry", "RequirementReference", "default_registry"]
