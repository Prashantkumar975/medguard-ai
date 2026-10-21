# MedGuard AI — Risk Engine

Deterministic, configurable risk scoring. Implemented in
`app/services/risk/engine.py`. These scores **triage human review**; they are not
validated clinical risk estimates and never certify a statement as safe/unsafe.

## Formula

```
composite = w_harm·H + w_exposure·E + w_evidence·S + w_uncertainty·(1 − U)
```

Weights (configurable in `engine.WEIGHTS`):

| Component | Weight |
| --- | --- |
| harm (H) | 0.40 |
| exposure (E) | 0.20 |
| evidence strength (S) | 0.25 |
| uncertainty (U) | 0.15 |

Priority thresholds (on `composite`):

| Priority | composite |
| --- | --- |
| critical | ≥ 0.75 |
| high | ≥ 0.55 |
| medium | ≥ 0.35 |
| low | < 0.35 |

## Components

### Harm (H)
Base harm by claim **category** (deterministic table), scaled by a **verdict
multiplier**. Contraindications, emergencies and drug interactions carry the
highest base harm; screening/treatment recommendations the lowest. The multiplier
down-weights SUPPORTED (0.15) and up-weights POTENTIAL_CONTRADICTION (1.0).

### Exposure (E)
Two factors: the **fraction of the site** repeating the claim and the **site size**:

```
fraction     = pages_hosting_claim / site_page_count
size_factor  = log(1 + site_page_count) / log(51)      # saturates near 50 pages
E            = 0.25 + 0.75 · fraction · size_factor
```

The size factor prevents a claim on the only page of a 1-page demo site from being
treated as maximum reach. A single-page site tops out near `E ≈ 0.36`.

### Evidence strength (S)
Mean cosine similarity of the retrieved evidence chunks. `0.0` when nothing was
retrieved (which pairs with high uncertainty and an INSUFFICIENT_EVIDENCE verdict).

### Uncertainty (U)
Starts at `1 − extraction_confidence`, then is inflated when the semantic
comparison is missing (`+0.3`) or inconclusive (`+0.2`), and when the verdict is
INSUFFICIENT_EVIDENCE (`+0.15`). Clamped to `[0, 1]`.

## Assumptions and limitations

- The category→harm table and thresholds are **heuristic defaults**, tunable per
  deployment. They are not derived from clinical outcome data.
- Exposure approximates reach from page counts; it does not use traffic analytics.
- LLM-derived inputs (extraction confidence, semantic relation) are recorded but
  re-derived scores are **not** treated as clinical ground truth.
- Priority orders the **review queue**. A human reviewer confirms every finding
  before it is described as an error.
