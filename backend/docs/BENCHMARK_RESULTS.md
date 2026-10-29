# MedGuard AI — Small Synthetic Benchmark (Historical)

The figures below come from a historical run of `python -m scripts.benchmark` using invented drug names and three extraction/retrieval examples. They are retained only as a smoke-check record. **They are too limited to estimate real-world model accuracy or support a performance claim.** An F1 score of 1.0 on three examples is not evidence of reliable clinical performance.

The historical run used `qwen2.5:1.5b` and `BAAI/bge-small-en-v1.5`; the current application defaults to a Nebius-hosted model. Latency and memory figures therefore do not describe the current default configuration.

| Measure from the historical run | Recorded result | Scope |
| --- | ---: | --- |
| Extraction precision / recall / F1 | 1.0 / 1.0 / 1.0 | 3 synthetic examples |
| Extraction TP / FP / FN | 3 / 0 / 0 | 3 synthetic examples |
| Extraction latency p50 / p95 | 1928.7 / 2001.3 ms | Old local model and machine |
| Retrieval recall@1 / @3 / @5 | 1.0 / 1.0 / 1.0 | 3 synthetic examples |
| Unsupported-citation rate | 0.0 | 3 synthetic examples |
| Numeric guard accuracy | 1.0 | Synthetic cases only |
| Historical model memory | 1367.1 MB | `qwen2.5:1.5b` |

Before reporting performance, evaluate a substantially larger, independently reviewed dataset with representative positive, negative, ambiguous, and out-of-scope cases. Report confidence intervals and model/version details. Clinical use would require a separately designed validation and expert oversight.
