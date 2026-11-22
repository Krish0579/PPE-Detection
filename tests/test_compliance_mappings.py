from __future__ import annotations

import pytest

from src.compliance.mappings import (
    COMPLIANCE_DISCLAIMER,
    CitationRegistry,
    RequirementReference,
    canonical_item,
    default_registry,
)


def test_canonical_item():
    assert canonical_item("hardhat") == "helmet"
    assert canonical_item("hard_hat") == "helmet"
    assert canonical_item("missing_hardhat") == "helmet"
    assert canonical_item("no_shoes") == "boots"
    assert canonical_item("Glove") == "gloves"
    assert canonical_item("Safety Vest") == "vest"
    assert canonical_item("Unknown-Item") == "unknown_item"
    assert canonical_item("") == ""

def test_requirement_reference():
    ref = RequirementReference(
        ppe_item="helmet",
        standard="OSHA",
        citation="29 CFR",
        title="Head Protection"
    )
    assert ref.jurisdiction == "US"
    assert ref.notes == ""

def test_citation_registry_init_and_lookup():
    ref = RequirementReference("helmet", "OSHA", "123", "Title")
    registry = CitationRegistry([ref])
    
    # Specific match
    refs = registry.references_for("helmet")
    assert len(refs) == 1
    assert refs[0].citation == "123"

def test_citation_registry_wildcard():
    ref_spec = RequirementReference("helmet", "OSHA", "123", "Title")
    ref_wild = RequirementReference("*", "OSHA", "456", "General")
    
    registry = CitationRegistry([ref_spec, ref_wild])
    
    refs = registry.references_for("helmet")
    assert len(refs) == 2
    assert {r.citation for r in refs} == {"123", "456"}
    
    refs2 = registry.references_for("unknown")
    assert len(refs2) == 1
    assert refs2[0].citation == "456"

def test_citation_registry_update():
    registry = CitationRegistry()
    assert registry.version == 1
    
    ref = RequirementReference("boots", "OSHA", "999", "Foot")
    v = registry.update([ref], actor="admin")
    
    assert v == 2
    assert registry.version == 2
    assert registry.updated_by == "admin"
    assert len(registry.references_for("boots")) == 1

def test_citation_registry_update_missing_actor():
    registry = CitationRegistry()
    with pytest.raises(ValueError):
        registry.update([], actor="")

def test_citation_registry_describe():
    ref = RequirementReference("helmet", "OSHA", "123", "Title")
    registry = CitationRegistry([ref])
    
    desc = registry.describe("missing_hardhat")
    
    assert desc["detected_condition"] == "missing_hardhat"
    assert desc["configured_requirement"] == "helmet"
    assert len(desc["references"]) == 1
    assert desc["mapping_version"] == registry.version
    assert desc["human_review_required"] is True
    assert desc["disclaimer"] == COMPLIANCE_DISCLAIMER

def test_save_and_load_registry(tmp_path):
    p = tmp_path / "mappings.json"
    
    ref = RequirementReference("gloves", "OSHA", "555", "Hand")
    registry = CitationRegistry([ref], version=4, updated_by="user1")
    
    registry.save(p)
    assert p.exists()
    
    loaded = CitationRegistry.load(p)
    assert loaded.version == 4
    assert loaded.updated_by == "user1"
    
    refs = loaded.references_for("gloves")
    assert len(refs) == 1
    assert refs[0].standard == "OSHA"
    assert refs[0].citation == "555"

def test_default_registry():
    registry = default_registry()
    refs = registry.references_for("hardhat")
    assert len(refs) >= 1  # Should include at least 'helmet' and '*'
