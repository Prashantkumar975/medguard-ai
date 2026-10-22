"""Risk engine determinism and priority-threshold tests (brief section 12)."""
from app.services.risk.engine import score


def test_high_harm_contradiction_is_critical():
    r = score(
        category="contraindication",
        verdict="POTENTIAL_CONTRADICTION",
        extraction_confidence=0.9,
        evidence_similarities=[0.85],
        pages_hosting_claim=5,
        site_page_count=50,
        llm_relation="contradicts",
    )
    assert r.harm >= 0.8
    assert r.composite >= 0.55
    assert r.priority in ("critical", "high")


def test_supported_claim_scores_low_priority():
    r = score(
        category="screening_recommendation",
        verdict="SUPPORTED",
        extraction_confidence=0.9,
        evidence_similarities=[0.8],
        llm_relation="supports",
    )
    assert r.priority in ("low", "medium")
    assert r.harm <= 0.2


def test_components_clamped_to_unit_interval():
    r = score(
        category="emergency_instruction",
        verdict="POTENTIAL_CONTRADICTION",
        extraction_confidence=1.0,
        evidence_similarities=[1.0, 1.0],
        pages_hosting_claim=1000,
        site_page_count=1000,
    )
    for v in (r.harm, r.exposure, r.evidence_strength, r.uncertainty):
        assert 0.0 <= v <= 1.0


def test_missing_model_raises_uncertainty():
    r_no_llm = score(
        category="dosage", verdict="INSUFFICIENT_EVIDENCE",
        extraction_confidence=0.8, evidence_similarities=[], llm_relation=None,
    )
    r_with_llm = score(
        category="dosage", verdict="INSUFFICIENT_EVIDENCE",
        extraction_confidence=0.8, evidence_similarities=[], llm_relation="insufficient",
    )
    assert r_no_llm.uncertainty > r_with_llm.uncertainty


def test_deterministic_for_same_inputs():
    kwargs = dict(
        category="dosage", verdict="POTENTIAL_CONTRADICTION",
        extraction_confidence=0.7, evidence_similarities=[0.6, 0.8],
        pages_hosting_claim=3, site_page_count=20,
    )
    assert score(**kwargs).composite == score(**kwargs).composite
