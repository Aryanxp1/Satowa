"""Run the real two-image comparison on permissioned assets already in LEX.

From backend/: python scripts/evaluate_pairs.py path/to/private-pairs.json
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.routes.evidence import validate_pair
from app.services.evidence_store import connection
from app.services.image_comparison import compare_images


async def evaluate(manifest):
    results = []
    for index, pair in enumerate(manifest, start=1):
        with connection() as db:
            before, after = validate_pair(db, pair['before_asset_id'], pair['after_asset_id'])
        result = await compare_images(before, after)
        expected = pair['expected_reliable']
        results.append({
            'pair': index, 'expected_reliable': expected,
            'actual_reliable': result.reliable,
            'matches_expectation': expected == result.reliable,
            'observation': result.observation, 'reason': result.reason,
        })
    return results


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/evaluate_pairs.py private-pairs.json')
    if not settings.GEMINI_API_KEY:
        raise SystemExit('GEMINI_API_KEY is required for a live comparison evaluation')
    manifest = json.loads(Path(sys.argv[1]).read_text())
    if not isinstance(manifest, list) or not manifest or any(
        not isinstance(pair, dict) or
        not isinstance(pair.get('before_asset_id'), str) or
        not isinstance(pair.get('after_asset_id'), str) or
        type(pair.get('expected_reliable')) is not bool
        for pair in manifest
    ):
        raise SystemExit('Manifest must be a nonempty list of evidence ID pairs with expected_reliable booleans')
    results = asyncio.run(evaluate(manifest))
    print(json.dumps({'tested': len(results),
                      'matched': sum(item['matches_expectation'] for item in results),
                      'results': results}, indent=2))
    if not all(item['matches_expectation'] for item in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
