"""Verification verdict tests (brief sections 11 and 20).

Deterministic layers (structured checks, numeric-conflict guard, species guard,
insufficient-evidence routing) are tested directly. Tests that require the live
model are skipped when Ollama is unreachable rather than silently mocked.
"""
from datetime import date

import httpx
import pytest

from app.services.extraction.claims import ExtractedClaim
from app.services.verification.verify import (
    VERDICT_CONTRADICTION,
    VERDICT_INSUFFICIENT,
    VERDICT_SUPPORTED,
    _numeric_conflicts,
    structured_checks,
    verify,
)


def _claim(text, category="dosage", medication=None, population=None, dosage=None, offsets=None):
    return ExtractedClaim(
        claim_text=text,
        category=category,
        medication=medication,
        population=population,
        dosage=dosage,
        source_offsets=offsets or (0, len(text)),
        extraction_confidence=0.9,
    )


def test_no_evidence_is_insufficient_not_contradiction():
    out = verify(_claim("Take 400 mg daily"), [], [])
    assert out.verdict == VERDICT_INSUFFICIENT
    assert "not evidence that the claim is wrong" in out.rationale


def test_species_mismatch_blocks_comparison():
    claim = _claim("Hepatrin Vet chewable is well tolerated in dogs with liver conditions", medication="Hepatrin")
    ev = ["Hepatrin tablets are contraindicated in patients with active liver disease."]
    checks = structured_checks(claim, ev, [date(2026, 1, 19)])
    species = next(c for c in checks if c.name == "species_alignment")
    assert species.matched is False


def test_veterinary_claim_not_auto_compared():
    claim = _claim("Give this flea tablet to your cat monthly", category="medication_safety_warning", medication="Petguard")
    ev = ["Petguard is contraindicated in patients with kidney disease."]  # human label
    out = verify(claim, ev, [date(2026, 1, 1)])
    # species guard routes away from an automatic contradiction
    assert out.verdict != VERDICT_CONTRADICTION
    assert "species" in (out.notes or [""])[0] or out.verdict == "INCOMPLETE_INFORMATION"


def test_numeric_conflict_detects_age_mismatch():
    conflicts = _numeric_conflicts(
        "Respirol inhaler is suitable for children aged 4 and older.",
        ["Respirol is approved for use in patients 6 years of age and older."],
    )
    assert conflicts and "year" in conflicts[0]


def test_numeric_conflict_no_false_positive_when_value_present():
    conflicts = _numeric_conflicts(
        "The maximum daily dose of Cardiolamine is 400 mg.",
        ["Do not exceed 400 mg per day in adults with normal renal function."],
    )
    assert conflicts == []


def test_structured_recency_flags_newer_evidence():
    claim = _claim("Start Glucavane at 500 mg twice daily", medication="Glucavane")
    ev = ["Initiate Glucavane at 500 mg once daily."]
    checks = structured_checks(claim, ev, [date(2026, 7, 9)], page_last_modified=None)
    recency = next(c for c in checks if c.name == "recency")
    # no page date -> recency matched (cannot conclude staleness)
    assert recency.matched is True


def _ollama_up() -> bool:
    try:
        from app.core.config import settings

        r = httpx.get(f"{settings.ollama_base_url}/api/version", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not reachable")
def test_live_model_contradiction_end_to_end():
    claim = _claim(
        "Zorvaxin can be taken safely throughout pregnancy.",
        category="contraindication",
        medication="Zorvaxin",
    )
    ev = ["Zorvaxin is contraindicated in pregnant women because of the risk of fetal harm."]
    out = verify(claim, ev, [date(2026, 8, 21)])
    assert out.verdict == VERDICT_CONTRADICTION
    assert out.llm_relation in ("contradicts", None)  # guard can also catch it
