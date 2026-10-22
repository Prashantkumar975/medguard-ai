"""Deterministic, configurable risk scoring.

Formula (documented in backend/docs/RISK_ENGINE.md):
    composite = w_harm*H + w_exposure*E + w_evidence*S + w_uncertainty*(1-U)
    priority thresholds: composite >= 0.75 critical, >= 0.55 high, >= 0.35 medium, else low

Harm base weights are per claim category (deterministic table). These are
triage weights for organizing human review — NOT validated clinical risk estimates.
"""
from __future__ import annotations

from dataclasses import dataclass

# Base harm by claim category (0-1). Deterministic table, documented assumption.
CATEGORY_HARM = {
    "emergency_instruction": 0.95,
    "contraindication": 0.9,
    "drug_interaction": 0.85,
    "dosage": 0.8,
    "pregnancy_breastfeeding": 0.8,
    "medication_safety_warning": 0.7,
    "pediatric": 0.7,
    "treatment_recommendation": 0.55,
    "screening_recommendation": 0.45,
}

# Multiplier applied when the verdict indicates a direct conflict.
VERDICT_MULTIPLIER = {
    "POTENTIAL_CONTRADICTION": 1.0,
    "POSSIBLY_OUTDATED": 0.85,
    "INCOMPLETE_INFORMATION": 0.6,
    "INSUFFICIENT_EVIDENCE": 0.5,
    "SUPPORTED": 0.15,
}

WEIGHTS = {"harm": 0.4, "exposure": 0.2, "evidence": 0.25, "uncertainty": 0.15}
THRESHOLDS = [("critical", 0.75), ("high", 0.55), ("medium", 0.35)]


@dataclass
class RiskComponents:
    harm: float
    exposure: float
    evidence_strength: float
    uncertainty: float

    @property
    def composite(self) -> float:
        return (
            WEIGHTS["harm"] * self.harm
            + WEIGHTS["exposure"] * self.exposure
            + WEIGHTS["evidence"] * self.evidence_strength
            + WEIGHTS["uncertainty"] * (1.0 - self.uncertainty)
        )

    @property
    def priority(self) -> str:
        c = self.composite
        for label, cut in THRESHOLDS:
            if c >= cut:
                return label
        return "low"


def score(
    *,
    category: str | None,
    verdict: str,
    extraction_confidence: float | None,
    evidence_similarities: list[float],
    pages_hosting_claim: int = 1,
    site_page_count: int = 1,
    llm_relation: str | None = None,
) -> RiskComponents:
    """Compute risk components deterministically from observable inputs.

    - harm: category base harm x verdict multiplier (clamped 0-1)
    - exposure: log-scaled share of site pages hosting the claim pattern
    - evidence_strength: mean vector similarity of supporting/ conflicting evidence
    - uncertainty: 1 - extraction confidence, inflated when the LLM relation is
      missing/insufficient or structured checks disagree
    """
    base = CATEGORY_HARM.get(category or "", 0.5)
    harm = min(1.0, base * VERDICT_MULTIPLIER.get(verdict, 0.6))

    import math

    # Two factors: what fraction of the site repeats the claim, and how large the
    # site is. A claim on every page of a 1-page demo site is not maximum reach.
    fraction = min(1.0, pages_hosting_claim / max(site_page_count, 1))
    size_factor = min(1.0, math.log1p(max(site_page_count, 1)) / math.log1p(50))
    exposure = round(0.25 + 0.75 * fraction * size_factor, 4)

    evidence_strength = round(sum(evidence_similarities) / len(evidence_similarities), 4) if evidence_similarities else 0.0

    conf = extraction_confidence if extraction_confidence is not None else 0.5
    uncertainty = 1.0 - conf
    if llm_relation is None:
        uncertainty = min(1.0, uncertainty + 0.3)
    elif llm_relation == "insufficient":
        uncertainty = min(1.0, uncertainty + 0.2)
    if verdict == "INSUFFICIENT_EVIDENCE":
        uncertainty = min(1.0, uncertainty + 0.15)

    return RiskComponents(
        harm=round(harm, 4),
        exposure=exposure,
        evidence_strength=evidence_strength,
        uncertainty=round(uncertainty, 4),
    )
