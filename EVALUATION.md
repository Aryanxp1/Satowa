# Evaluation evidence

No real-world AI accuracy score is claimed. Existing synthetic walkthrough media and mocked provider tests are functional fixtures, not evidence of environmental impact or real-model accuracy.

## Local lexical benchmark (2026-09-29)

`scripts/benchmark_discovery.py`, 20 repetitions per size, this development Mac:

| Synthetic records | p50 ms | p95 ms |
|---:|---:|---:|
| 100 | 0.21 | 0.27 |
| 1,000 | 1.09 | 1.21 |
| 10,000 | 10.58 | 12.39 |

These times include temporary FTS5 build and query only. They exclude source database reads, network, external embeddings, browser rendering, and concurrency. They are not an end-to-end collection benchmark or a hosted SLA.

## Required field evaluation

Obtain permissioned media before running a real benchmark. Record source URL, creator, license/permission evidence, attribution, capture-date provenance, site, before/after relationship, viewpoint comparability, and independent human labels. Unknown dates remain unknown. Never pair unrelated images or turn synthetic assets into verified impact.

Measure unsupported claim frequency, abstention on incomparable pairs, groundedness, retrieval relevance, latency, and failure rates separately. Report actual sample counts and model/version. `scripts/evaluate_pairs.py` and `scripts/evaluation.example.json` are starting tools, not completed evaluation results.
