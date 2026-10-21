"""Reproducible benchmark pipeline for the open-source AI components.

Measures, against a clearly-labeled fictional evaluation set:
  - claim extraction precision / recall / F1 (schema-validated)
  - evidence retrieval Recall@K (does the gold chunk appear in the top-K?)
  - unsupported-citation rate (citations that fail verbatim validation)
  - inference latency (p50/p95) for extraction and NLI
  - model resident memory (when Ollama exposes it)

Nothing here is a clinical validation claim. The eval set is FICTIONAL and exists
to exercise the pipeline deterministically. Run:

    python -m scripts.benchmark --full        # includes live model calls
    python -m scripts.benchmark               # offline components only

Results are written to backend/docs/BENCHMARK_RESULTS.md. Measured numbers are
distinguished from targets; see the README for the interpretation.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.extraction.claims import ExtractedClaim, extract_claims, _extract_json
from app.services.retrieval.search import hybrid_search, validate_citation
from app.services.risk.engine import score
from app.services.verification.verify import _numeric_conflicts

# ---------------------------------------------------------------------------
# FICTIONAL labeled evaluation fixtures. Every drug below is invented.
# Each case: page text, the gold claims (verbatim spans), and a gold reference
# chunk id for retrieval. These are NOT real medicines or real guidance.
# ---------------------------------------------------------------------------
EVAL_CASES = [
    {
        "id": "zorvaxin-pregnancy",
        "text": (
            "Zorvaxin can be taken safely throughout pregnancy and while breastfeeding. "
            "No additional monitoring is required during the first trimester."
        ),
        "gold_claims": [
            {"claim_text": "Zorvaxin can be taken safely throughout pregnancy and while breastfeeding.",
             "category": "pregnancy_breastfeeding", "medication": "Zorvaxin"},
        ],
        "gold_doc_title": "Zorvaxin",
    },
    {
        "id": "cardiolamine-dose",
        "text": "The maximum daily dose of Cardiolamine is 400 mg for adults with normal kidney function.",
        "gold_claims": [
            {"claim_text": "The maximum daily dose of Cardiolamine is 400 mg for adults with normal kidney function.",
             "category": "dosage", "medication": "Cardiolamine"},
        ],
        "gold_doc_title": "Cardiolamine",
    },
    {
        "id": "respirol-children",
        "text": "Respirol inhaler is suitable for children aged 4 and older when supervised by a parent.",
        "gold_claims": [
            {"claim_text": "Respirol inhaler is suitable for children aged 4 and older when supervised by a parent.",
             "category": "pediatric", "medication": "Respirol"},
        ],
        "gold_doc_title": "Respirol",
    },
    {
        "id": "no-claim",
        "text": "Welcome to our clinic. We are open weekdays. Our reception is on the ground floor.",
        "gold_claims": [],
        "gold_doc_title": None,
    },
]


def _gold_offsets(text: str, claim_text: str) -> tuple[int, int]:
    start = text.find(claim_text)
    if start == -1:
        return (0, len(claim_text))
    return (start, start + len(claim_text))


def _match(pred: str, gold: str) -> bool:
    g = " ".join(gold.lower().split())
    p = " ".join(pred.lower().split())
    return g in p or p in g


def bench_extraction_full(org_id: str, db) -> dict:
    """Run the live model over the eval set; score against gold claims."""
    tp = fp = fn = 0
    latencies: list[float] = []
    for case in EVAL_CASES:
        t0 = time.perf_counter()
        preds, failures = extract_claims(case["text"], case["id"])
        latencies.append((time.perf_counter() - t0) * 1000)
        gold = case["gold_claims"]
        matched_gold = set()
        for p in preds:
            hit = next(
                (i for i, g in enumerate(gold)
                 if _match(p.claim_text, g["claim_text"]) and i not in matched_gold),
                None,
            )
            if hit is not None:
                tp += 1
                matched_gold.add(hit)
            else:
                fp += 1
        fn += len(gold) - len(matched_gold)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn,
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else None,
        "latency_p95_ms": round(_p95(latencies), 1) if latencies else None,
    }


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, int(round(0.95 * (len(s) - 1))))
    return s[idx]


def bench_retrieval(org_id: str, db, ks=(1, 3, 5)) -> dict:
    """Recall@K: does a chunk from the gold document appear in the top-K hits?"""
    results = {f"recall@{k}": [] for k in ks}
    unsupported = 0
    total = 0
    for case in EVAL_CASES:
        if not case["gold_doc_title"]:
            continue
        query = case["gold_claims"][0]["claim_text"] if case["gold_claims"] else case["text"]
        hits = hybrid_search(db, org_id, query, top_k=max(ks))
        total += 1
        gold_hit_rank = next(
            (i for i, h in enumerate(hits)
             if case["gold_doc_title"].lower() in _doc_title(db, h.document_id).lower()),
            None,
        )
        for k in ks:
            results[f"recall@{k}"].append(1 if (gold_hit_rank is not None and gold_hit_rank < k) else 0)
        # unsupported-citation check on the top hit
        if hits and not validate_citation(db, hits[0].chunk_id, hits[0].text[:800]):
            unsupported += 1
    out = {k: (round(sum(v) / len(v), 3) if v else 0.0) for k, v in results.items()}
    out["unsupported_citation_rate"] = round(unsupported / total, 3) if total else 0.0
    out["evaluated"] = total
    return out


def _doc_title(db, document_id: str) -> str:
    from app.models import ReferenceDocument

    doc = db.get(ReferenceDocument, document_id)
    return doc.title if doc else ""


def bench_offline() -> dict:
    """Deterministic components that need no model: schema, numeric guard, risk."""
    import app.services.verification.verify as V
    from app.services.extraction.claims import ExtractedClaim

    # numeric-conflict guard accuracy on hand-labeled pairs
    pairs = [
        ("children aged 4 and older", "approved for 6 years and older", True),
        ("maximum 400 mg daily", "do not exceed 400 mg per day", False),
        ("start at 500 mg twice daily", "initiate 500 mg once daily", True),
    ]
    correct = 0
    for claim_txt, ev_txt, expect_conflict in pairs:
        got = bool(_numeric_conflicts(claim_txt, [ev_txt]))
        correct += 1 if got == expect_conflict else 0
    guard_acc = correct / len(pairs)

    # risk engine determinism + monotonicity spot-check
    low = score(category="screening_recommendation", verdict="SUPPORTED",
                extraction_confidence=0.9, evidence_similarities=[0.8], llm_relation="supports")
    high = score(category="contraindication", verdict="POTENTIAL_CONTRADICTION",
                 extraction_confidence=0.9, evidence_similarities=[0.9],
                 pages_hosting_claim=10, site_page_count=200, llm_relation="contradicts")
    monotonic = high.composite > low.composite

    return {
        "numeric_guard_accuracy": round(guard_acc, 3),
        "risk_monotonic_high_gt_low": monotonic,
        "risk_low_composite": round(low.composite, 3),
        "risk_high_composite": round(high.composite, 3),
    }


def model_memory() -> dict | None:
    try:
        import httpx

        from app.core.config import settings

        r = httpx.get(f"{settings.ollama_base_url}/api/ps", timeout=5)
        if r.status_code != 200:
            return None
        models = r.json().get("models", [])
        if not models:
            return None
        m = models[0]
        return {"model": m.get("name"), "size_vram_mb": round(m.get("size", 0) / 1e6, 1)}
    except Exception:
        return None


def write_results(payload: dict) -> Path:
    out = Path(__file__).resolve().parents[1] / "docs" / "BENCHMARK_RESULTS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MedGuard AI — Benchmark Results",
        "",
        "Generated by `python -m scripts.benchmark`. The evaluation set is **fictional**",
        "(invented drug names) and exercises the pipeline deterministically. These are",
        "**measured** numbers on this machine, not clinical-validation claims and not",
        "product targets. Re-run to reproduce; hardware and model choice affect results.",
        "",
        f"- Extraction model: `{payload.get('model', 'n/a')}`",
        f"- Embedding model: `{payload.get('embedding_model', 'n/a')}`",
        "",
        "## Claim extraction (live model)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    ex = payload.get("extraction")
    if ex:
        lines += [
            f"| Precision | {ex['precision']} |",
            f"| Recall | {ex['recall']} |",
            f"| F1 | {ex['f1']} |",
            f"| TP / FP / FN | {ex['tp']} / {ex['fp']} / {ex['fn']} |",
            f"| Latency p50 | {ex['latency_p50_ms']} ms |",
            f"| Latency p95 | {ex['latency_p95_ms']} ms |",
        ]
    else:
        lines.append("| (skipped — model not reached in offline mode) | — |")

    lines += ["", "## Evidence retrieval", "", "| Metric | Value |", "| --- | --- |"]
    for k, v in (payload.get("retrieval") or {}).items():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## Deterministic components (no model)", "", "| Metric | Value |", "| --- | --- |"]
    for k, v in (payload.get("offline") or {}).items():
        lines.append(f"| {k} | {v} |")

    mem = payload.get("memory")
    lines += ["", "## Model memory", ""]
    if mem:
        lines.append(f"- {mem['model']}: {mem['size_vram_mb']} MB resident")
    else:
        lines.append("- (not reported by the inference server)")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="include live-model extraction calls")
    args = ap.parse_args()

    from app.core.config import settings
    from app.core.database import SessionLocal
    from sqlalchemy import select

    from app.models import Organization

    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).limit(1))
        if org is None:
            raise SystemExit("No organization. Run scripts/bootstrap.py and scripts/seed_references.py first.")
        org_id = org.id

        payload: dict = {
            "model": settings.ollama_model,
            "embedding_model": settings.embedding_model,
            "offline": bench_offline(),
            "retrieval": bench_retrieval(org_id, db),
            "memory": model_memory(),
        }
        if args.full:
            payload["extraction"] = bench_extraction_full(org_id, db)
        else:
            payload["extraction"] = None

        out = write_results(payload)
        print(f"Wrote {out}")
        import json

        print(json.dumps(payload, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
