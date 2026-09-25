"""Idempotently seed a clearly synthetic local walkthrough.

This script does not upload anything to Cloudinary or call an AI service.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import evidence_store as store


SITE_ID = 'demo-riverbank'
BEFORE_VISIT = 'demo-visit-before'
AFTER_VISIT = 'demo-visit-after'
BEFORE_ASSET = 'synthetic-river-before'
AFTER_ASSET = 'synthetic-river-after'
OBSERVATION_ID = 'synthetic-river-observation'


def seed():
    now = store.timestamp()
    with store.connection() as db:
        db.execute('''INSERT OR IGNORE INTO sites(id,name,location,description)
            VALUES (?,?,?,?)''',
            (SITE_ID, 'Riverbank cleanup · synthetic walkthrough',
             'Illustrative river bend',
             'A guided sample with two synthetic visits. No real field evidence or impact claim.'))
        db.execute('''UPDATE sites SET
            location=CASE WHEN location='' THEN ? ELSE location END,
            description=CASE WHEN description='' THEN ? ELSE description END
            WHERE id=?''',
            ('Illustrative river bend',
             'A guided sample with two synthetic visits. No real field evidence or impact claim.',
             SITE_ID))
        for visit in (
            (BEFORE_VISIT, SITE_ID, '2026-09-01', 'Visit 1 · before'),
            (AFTER_VISIT, SITE_ID, '2026-09-23', 'Visit 2 · after'),
        ):
            db.execute('''INSERT OR IGNORE INTO visits(id,site_id,visited_on,label)
                VALUES (?,?,?,?)''', visit)
        for asset in (
            (BEFORE_ASSET, BEFORE_VISIT, 'synthetic/river-before',
             '/demo/sample-media/river-before-synthetic.png',
             'Synthetic image generated for the LEX local demo · before'),
            (AFTER_ASSET, AFTER_VISIT, 'synthetic/river-after',
             '/demo/sample-media/river-after-synthetic.png',
             'Synthetic image generated for the LEX local demo · after'),
        ):
            db.execute('''INSERT OR IGNORE INTO assets
                (asset_id,visit_id,public_id,version,secure_url,source,width,height,format)
                VALUES (?,?,?,1,?,?,1536,1024,'png')''', asset)
        if not store.one(db, 'SELECT id FROM observations WHERE id=?', (OBSERVATION_ID,)):
            observation = {
                'id': OBSERVATION_ID, 'site_id': SITE_ID,
                'before_asset_id': BEFORE_ASSET, 'after_asset_id': AFTER_ASSET,
                'ai_draft': None,
                'working_text': 'The later synthetic image shows fewer visible pieces of litter on the photographed near bank.',
                'approved_text': None, 'review_status': 'pending',
                'reliability_reason': 'Synthetic walkthrough text, not an AI finding. Inspect both sample images before approving or editing it.',
                'reviewed_by': None, 'reviewed_at': None,
                'created_at': now, 'updated_at': now, 'version': 1,
            }
            db.execute('''INSERT INTO observations VALUES
                (:id,:site_id,:before_asset_id,:after_asset_id,:ai_draft,:working_text,
                 :approved_text,:review_status,:reliability_reason,:reviewed_by,
                 :reviewed_at,:created_at,:updated_at,:version)''', observation)
            store.revision(db, observation, 'synthetic_sample_created', 'demo setup',
                           observation['working_text'])
    print(f'Synthetic local sample is ready: site {SITE_ID}. No media was uploaded.')


if __name__ == '__main__':
    seed()
