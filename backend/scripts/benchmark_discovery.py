"""Synthetic local FTS5 throughput only; not AI accuracy or hosted load evidence."""
import json
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.semantic_search import keyword_search

results = []
for size in (100, 1000, 10000):
    docs = [{'content': f'Synthetic shoreline litter observation record {i}', 'kind': 'media',
             'entity_id': str(i), 'site_id': 'synthetic', 'review_status': 'metadata_only',
             'evidence': []} for i in range(size)]
    timings = []
    for _ in range(20):
        start = time.perf_counter()
        keyword_search(docs, 'shoreline litter', 8, 0)
        timings.append((time.perf_counter() - start) * 1000)
    results.append({'records': size, 'runs': 20, 'p50_ms': round(statistics.median(timings), 2),
                    'p95_ms': round(sorted(timings)[18], 2)})
print(json.dumps({'scope': 'Synthetic local FTS5 build+query. Excludes database source collection, network, embeddings, and concurrency.',
                  'results': results}, indent=2))
