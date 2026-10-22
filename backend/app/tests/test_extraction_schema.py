"""Claim extraction schema validation and offset checks (brief sections 8 and 20).

These tests exercise the deterministic validation layer (JSON parsing, Pydantic
schema, offset anchoring) with crafted model outputs. They do not invoke or mock
the live model for production inference — they test the validation plumbing.
"""
import pytest
from pydantic import ValidationError

from app.services.extraction.claims import ExtractedClaim, _extract_json


def test_valid_claim_passes():
    c = ExtractedClaim(
        claim_text="Take two tablets daily",
        category="Dosage",
        medication="Zorvaxin",
        source_offsets=(10, 32),
        extraction_confidence=0.9,
    )
    assert c.category == "dosage"  # normalized to lowercase
    assert c.source_offsets == (10, 32)


def test_category_alias_normalized():
    c = ExtractedClaim(
        claim_text="Avoid in pregnancy due to fetal harm",
        category="pregnancy",
        source_offsets=(0, 35),
        extraction_confidence=0.8,
    )
    assert c.category == "pregnancy_breastfeeding"


def test_unknown_category_rejected():
    with pytest.raises(ValidationError):
        ExtractedClaim(
            claim_text="some medical statement here for testing",
            category="astrology",
            source_offsets=(0, 10),
            extraction_confidence=0.5,
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ExtractedClaim(
            claim_text="some medical statement here for testing",
            category="dosage",
            source_offsets=(0, 10),
            extraction_confidence=1.5,
        )


def test_offsets_must_be_ordered():
    with pytest.raises(ValidationError):
        ExtractedClaim(
            claim_text="some medical statement here for testing",
            category="dosage",
            source_offsets=(50, 10),
            extraction_confidence=0.5,
        )


def test_extract_json_handles_fences_and_prose():
    raw = 'Sure! Here is the JSON:\n```json\n{"claims": [{"a": 1}]}\n```'
    assert _extract_json(raw) == {"claims": [{"a": 1}]}
    assert _extract_json('{"claims": []}') == {"claims": []}


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        _extract_json("no json here at all")


def test_too_short_claim_rejected():
    with pytest.raises(ValidationError):
        ExtractedClaim(
            claim_text="short",
            category="dosage",
            source_offsets=(0, 5),
            extraction_confidence=0.5,
        )
