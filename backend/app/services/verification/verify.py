"""Verification: structured compatibility checks, then LLM-assisted comparison.

Order matters: deterministic structured checks run first; the LLM is only used for
the semantic comparison step. Lack of evidence is never treated as contradiction.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.core.config import settings
from app.services.extraction.claims import ExtractedClaim, _extract_json, call_llm

log = logging.getLogger(__name__)

VERDICT_SUPPORTED = "SUPPORTED"
VERDICT_CONTRADICTION = "POTENTIAL_CONTRADICTION"
VERDICT_OUTDATED = "POSSIBLY_OUTDATED"
VERDICT_INCOMPLETE = "INCOMPLETE_INFORMATION"
VERDICT_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

VETERINARY_TERMS = re.compile(
    r"\b(vet|veterinary|dog|dogs|canine|cat|cats|feline|horse|equine|livestock|animal|animals|pet|pets)\b",
    re.I,
)


@dataclass
class StructuredCheck:
    name: str
    matched: bool
    detail: str


@dataclass
class VerificationOutcome:
    verdict: str
    rationale: str
    structured: list[StructuredCheck] = field(default_factory=list)
    llm_relation: str | None = None  # supports|contradicts|insufficient|outdated
    llm_confidence: float | None = None
    notes: list[str] = field(default_factory=list)


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


# matches quantities like "400 mg", "5 mg", "6 years", "aged 4", "2.5 mL"
_QTY_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|g|kg|ml|l|years?|months?|weeks?|days?|doses?|puffs?|%|times?)\b",
    re.I,
)
_AGE_RE = re.compile(r"\b(?:aged|age|years\s+of\s+age|above|over|under|below)\s+(?P<num>\d+)\b", re.I)
# spelled-out dosing frequency: "once daily", "twice a day", "three times daily", "2x/day"
_FREQ_WORDS = {"once": "1", "twice": "2", "single": "1"}
_FREQ_RE = re.compile(
    r"\b(?P<w>once|twice|three|four|five|six)\s*(?:a\s+|per\s+)?(?:day|daily|week|month)\b"
    r"|\b(?P<n>\d+)\s*(?:times|x)\s*(?:a\s+|per\s+)?(?:day|daily|week|month)\b",
    re.I,
)
_FREQ_NUMS = {"three": "3", "four": "4", "five": "5", "six": "6"}


def _quantities(text: str) -> dict[str, set[str]]:
    """Extract unit -> set of numeric values mentioned in a text.

    Units are singularized so "6 years" (regex) and "aged 6" (age regex) share the
    same "year" bucket and can be compared for conflicts. Dosing frequency words
    ("once daily" vs "twice daily") are normalized into a shared "frequency" bucket.
    """
    out: dict[str, set[str]] = {}
    for m in _QTY_RE.finditer(text):
        unit = m.group("unit").lower().rstrip("s")
        out.setdefault(unit, set()).add(m.group("num"))
    for m in _AGE_RE.finditer(text):
        out.setdefault("year", set()).add(m.group("num"))
    for m in _FREQ_RE.finditer(text):
        if m.group("w"):
            w = m.group("w").lower()
            val = _FREQ_WORDS.get(w, _FREQ_NUMS.get(w))
        else:
            val = m.group("n")
        if val:
            out.setdefault("frequency", set()).add(val)
    return out


def _numeric_conflicts(claim_text: str, evidence_texts: list[str]) -> list[str]:
    """Deterministic: same unit, different value, in claim vs evidence.

    Catches dose/age threshold mismatches the small semantic model can miss.
    Only reports units present on BOTH sides with non-overlapping value sets.
    """
    claim_q = _quantities(claim_text)
    ev_q: dict[str, set[str]] = {}
    for t in evidence_texts:
        for unit, vals in _quantities(t).items():
            ev_q.setdefault(unit, set()).update(vals)
    conflicts: list[str] = []
    for unit, cvals in claim_q.items():
        evals = ev_q.get(unit)
        if not evals:
            continue
        if cvals.isdisjoint(evals):
            conflicts.append(f"{unit}: claim {sorted(cvals)} vs evidence {sorted(evals)}")
    return conflicts


def structured_checks(claim: ExtractedClaim, evidence_texts: list[str], evidence_dates: list[date | None],
                      page_last_modified: datetime | None = None, jurisdiction: str | None = None,
                      evidence_jurisdictions: list[str | None] | None = None) -> list[StructuredCheck]:
    """Compare medication identity, formulation, dosage, population, species,
    jurisdiction and dates between claim and evidence. Deterministic."""
    checks: list[StructuredCheck] = []
    joined = " ".join(evidence_texts).lower()

    # medication identity
    if claim.medication:
        checks.append(StructuredCheck(
            "medication_identity",
            _norm(claim.medication) in joined,
            f"claim medication {claim.medication!r} present in evidence: {_norm(claim.medication) in joined}",
        ))
    # formulation
    if claim.formulation:
        checks.append(StructuredCheck(
            "formulation",
            _norm(claim.formulation) in joined,
            f"formulation {claim.formulation!r} mentioned in evidence",
        ))
    # species (veterinary must not be compared against human labeling automatically)
    claim_vet = bool(VETERINARY_TERMS.search(claim.claim_text)) or bool(
        claim.population and VETERINARY_TERMS.search(claim.population)
    )
    evidence_vet = any(VETERINARY_TERMS.search(t) for t in evidence_texts)
    checks.append(StructuredCheck(
        "species_alignment",
        claim_vet == evidence_vet or (not claim_vet and not evidence_vet),
        f"claim veterinary={claim_vet}, evidence veterinary={evidence_vet}",
    ))
    # population overlap
    if claim.population:
        pop_tokens = set(re.findall(r"[a-z]+", _norm(claim.population))) - {"and", "or", "the", "in", "with"}
        pop_hit = any(tok in joined for tok in pop_tokens) if pop_tokens else False
        checks.append(StructuredCheck("population", pop_hit, f"population {claim.population!r} tokens found in evidence: {pop_hit}"))
    # jurisdiction
    if jurisdiction:
        mismatched = [j for j in evidence_jurisdictions if j and j != jurisdiction]
        checks.append(StructuredCheck(
            "jurisdiction",
            len(mismatched) == 0,
            f"claim jurisdiction {jurisdiction}; mismatched evidence jurisdictions: {mismatched or 'none'}",
        ))
    # dates: evidence newer than the page suggests staleness
    newer = [d for d in evidence_dates if d and page_last_modified and d > page_last_modified.date()]
    checks.append(StructuredCheck(
        "recency",
        len(newer) == 0,
        f"{len(newer)} evidence document(s) published after the page was last modified",
    ))
    # dosage literal comparison when both sides state a dose
    if claim.dosage:
        dose_nums = re.findall(r"\d+(?:\.\d+)?", claim.dosage)
        if dose_nums:
            ev_nums = set(re.findall(r"\d+(?:\.\d+)?", joined))
            checks.append(StructuredCheck(
                "dosage",
                any(n in ev_nums for n in dose_nums),
                f"claim dose values {dose_nums} vs evidence values present: {any(n in ev_nums for n in dose_nums)}",
            ))
    return checks


NLI_PROMPT = """You are a pharmacovigilance assistant comparing a web-page medical claim against authoritative source excerpts.
Return ONLY JSON: {{"relation": "supports"|"contradicts"|"insufficient", "confidence": 0.0-1.0, "reason": "one sentence"}}

Rules:
- "contradicts" only if the source directly conflicts with the claim (different dose, opposite safety statement, different population limits).
- "insufficient" if the sources neither support nor refute the claim.
- Never infer contradiction from missing information.

CLAIM: {claim}
SOURCE EXCERPTS:
{evidence}
"""


def llm_relation(claim_text: str, evidence: list[str]) -> tuple[str | None, float | None, str | None]:
    """Semantic comparison via the configured open model. Returns (relation, confidence, reason)."""
    if not evidence:
        return None, None, None
    excerpts = "\n".join(f"- {e[:600]}" for e in evidence[:6])
    prompt = NLI_PROMPT.format(claim=claim_text[:1000], evidence=excerpts)
    try:
        raw = call_llm(prompt)
        data = _extract_json(raw)
        relation = str(data.get("relation", "")).lower()
        if relation not in ("supports", "contradicts", "insufficient"):
            relation = "insufficient"
        conf = float(data.get("confidence", 0.5))
        return relation, max(0.0, min(1.0, conf)), str(data.get("reason", ""))[:500]
    except Exception as exc:
        log.warning("NLI call failed: %s", exc)
        return None, None, None


def verify(
    claim: ExtractedClaim,
    evidence_texts: list[str],
    evidence_dates: list[date | None],
    *,
    page_last_modified: datetime | None = None,
    jurisdiction: str | None = None,
    evidence_jurisdictions: list[str | None] | None = None,
) -> VerificationOutcome:
    """Full verification: structured checks first, then semantic comparison."""
    evidence_jurisdictions = evidence_jurisdictions or [None] * len(evidence_texts)
    checks = structured_checks(claim, evidence_texts, evidence_dates, page_last_modified,
                              jurisdiction, evidence_jurisdictions)

    if not evidence_texts:
        return VerificationOutcome(
            verdict=VERDICT_INSUFFICIENT,
            rationale=(
                "No authoritative evidence matched this claim in the knowledge base. "
                "This is not evidence that the claim is wrong — a human reviewer should assess it."
            ),
            structured=checks,
            notes=["no_evidence"],
        )

    species = next((c for c in checks if c.name == "species_alignment"), None)
    if species and not species.matched:
        return VerificationOutcome(
            verdict=VERDICT_INCOMPLETE,
            rationale=(
                "The claim and the retrieved evidence refer to different species contexts "
                "(e.g. veterinary vs human), so the sources cannot be compared automatically. "
                "Human review required."
            ),
            structured=checks,
            notes=["species_mismatch"],
        )

    relation, conf, reason = llm_relation(claim.claim_text, evidence_texts)
    outcome = VerificationOutcome(
        verdict=VERDICT_INSUFFICIENT,
        rationale="",
        structured=checks,
        llm_relation=relation,
        llm_confidence=conf,
    )

    recency = next((c for c in checks if c.name == "recency"), None)
    # Deterministic quantity guard: a same-unit/different-value mismatch in the
    # claim vs authoritative evidence overrides an LLM "supports" verdict, since
    # small models frequently miss numeric threshold conflicts.
    num_conflicts = _numeric_conflicts(claim.claim_text, evidence_texts)
    med_match = next((c for c in checks if c.name == "medication_identity"), None)
    if relation == "contradicts":
        outcome.verdict = VERDICT_CONTRADICTION
        outcome.rationale = (
            f"The source material conflicts with the page claim. {reason} "
            "Structured checks confirm the medication/population context aligns; expert review is required "
            "before treating this as a confirmed error."
        )
    elif relation == "supports" and num_conflicts and (med_match is None or med_match.matched):
        outcome.verdict = VERDICT_CONTRADICTION
        outcome.notes.append("numeric_conflict")
        outcome.rationale = (
            f"A structured quantity check found a conflict the automated comparison glossed over: "
            f"{'; '.join(num_conflicts)}. The claim and the authoritative source state different values "
            "for the same unit. Expert review is required before treating this as a confirmed error."
        )
    elif relation == "supports":
        if recency and not recency.matched:
            outcome.verdict = VERDICT_OUTDATED
            outcome.rationale = (
                f"The claim matches older source material, but newer authoritative documents "
                f"post-date the page. {reason} Human review recommended."
            )
        else:
            outcome.verdict = VERDICT_SUPPORTED
            outcome.rationale = f"The claim is consistent with the retrieved authoritative sources. {reason}"
    else:  # insufficient or model unavailable
        matched_any = any(c.matched for c in checks if c.name in ("medication_identity", "formulation", "dosage", "population"))
        if matched_any and relation is None:
            outcome.verdict = VERDICT_INSUFFICIENT
            outcome.rationale = (
                "Related authoritative sources were found but the semantic comparison could not be completed "
                "(model unavailable or inconclusive). Marked for human review; no contradiction is implied."
            )
        elif matched_any:
            outcome.verdict = VERDICT_INCOMPLETE
            outcome.rationale = (
                f"Related sources exist but neither support nor refute the claim as stated. {reason} "
                "The page may be missing important qualifiers."
            )
        else:
            outcome.verdict = VERDICT_INSUFFICIENT
            outcome.rationale = (
                "Retrieved sources do not clearly relate to the specific claim. "
                "Human review required; absence of evidence is not evidence of error."
            )
    return outcome
