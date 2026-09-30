"""HTTP tests for the persisted evidence and review workflow."""
import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import image_comparison, media

client = TestClient(app)
HEADERS = {'Authorization': 'Bearer reviewer-token'}


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path/'lex.sqlite3'))
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('demo-token'))
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Aryan":"reviewer-token"}'))
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', '')
    monkeypatch.setattr(settings, 'CLOUDINARY_CLOUD_NAME', 'demo-cloud')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_KEY', 'dummy')
    monkeypatch.setattr(settings, 'CLOUDINARY_API_SECRET', SecretStr('dummy'))
    counter = iter(range(100))
    def fake_upload(*args, **kwargs):
        n = next(counter)
        public = f'lex/river/image-{n}'
        return {'asset_id':f'asset-{n}', 'public_id':public, 'version':n+1,
                'resource_type':'image', 'format':'png', 'width':16, 'height':12,
                'secure_url':f'https://res.cloudinary.com/demo-cloud/image/upload/v{n+1}/{public}.png'}
    monkeypatch.setattr(media.cloudinary.uploader, 'upload', Mock(side_effect=fake_upload))


def image_bytes():
    out = io.BytesIO()
    Image.new('RGB', (16,12)).save(out, 'PNG')
    return out.getvalue()


def setup_site(site='river', before_date='2026-09-01', after_date='2026-09-23'):
    assert client.post('/api/v1/sites', json={'id':site,'name':'River Bend'}, headers=HEADERS).status_code == 201
    ids=[]
    for date in (before_date, after_date):
        visit=client.post(f'/api/v1/sites/{site}/visits', json={'visited_on':date,'label':date}, headers=HEADERS)
        assert visit.status_code==201
        visit_id=visit.json()['id']
        upload=client.post('/api/v1/media/images', headers=HEADERS,
            data={'project_id':site,'visit_date':date,'visit_id':visit_id,'source':'Team photo, consent recorded'},
            files={'file':('image.png',image_bytes(),'image/png')})
        assert upload.status_code==201,upload.text
        ids.append(upload.json()['asset_id'])
    return ids


def review(observation_id, decision, text=None, *, version=None, headers=HEADERS):
    if version is None:
        version = client.get(f'/api/v1/observations/{observation_id}', headers=HEADERS).json()['version']
    payload = {'decision': decision, 'expected_version': version}
    if text is not None:
        payload['text'] = text
    return client.post(f'/api/v1/observations/{observation_id}/review', headers=headers, json=payload)


def edit_observation(observation_id, **changes):
    version = client.get(f'/api/v1/observations/{observation_id}', headers=HEADERS).json()['version']
    return client.patch(f'/api/v1/observations/{observation_id}', headers=HEADERS,
                        json={'expected_version': version, **changes})


def fake_reliable(monkeypatch):
    async def compare(*args):
        return image_comparison.Comparison(reliable=True, observation='Less visible litter along the photographed bank.')
    monkeypatch.setattr('app.routes.evidence.compare_images', compare)


def test_full_review_reload_and_export(monkeypatch):
    fake_reliable(monkeypatch)
    before,after=setup_site()
    create=client.post('/api/v1/pairs',json={'before_asset_id':before,'after_asset_id':after},headers=HEADERS)
    assert create.status_code==201,create.text
    obs=create.json()
    assert obs['review_status']=='pending'
    assert obs['ai_draft'].startswith('Less visible')
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations']==[]
    approved=review(obs['id'], 'approve', 'Less visible litter in this section.')
    assert approved.status_code==200,approved.text
    reloaded=client.get(f"/api/v1/observations/{obs['id']}",headers=HEADERS).json()
    assert reloaded['ai_draft']==obs['ai_draft']
    assert [r['action'] for r in reloaded['revisions']]==['drafted','approved']
    report=client.get('/api/v1/sites/river/report',headers=HEADERS).json()
    assert len(report['observations'])==1
    item=report['observations'][0]
    assert item['approved_text']=='Less visible litter in this section.'
    assert item['before_asset_id']==before and item['after_asset_id']==after
    assert item['before_url'].startswith('https://res.cloudinary.com/')
    assert report['recorded_measurements']==[]
    md=client.get('/api/v1/sites/river/report?format=markdown',headers=HEADERS)
    assert md.status_code==200
    assert 'attachment;' in md.headers['content-disposition']
    assert item['approved_text'] in md.text
    assert item['before_url'] in md.text and item['after_url'] in md.text
    edited=edit_observation(obs['id'], working_text='Edited observation').json()
    assert edited['review_status']=='pending' and edited['approved_text'] is None
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations']==[]
    assert review(obs['id'], 'approve').status_code==200
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations'][0]['approved_text']=='Edited observation'


def test_unreliable_does_not_invent_text_and_human_can_override():
    before,after=setup_site()
    response=client.post('/api/v1/pairs',json={'before_asset_id':before,'after_asset_id':after},headers=HEADERS)
    assert response.status_code==201
    observation=response.json()
    assert observation['review_status']=='pending'
    assert observation['ai_draft'] is None
    assert observation['reliability_reason']
    oid=observation['id']
    assert review(oid, 'approve').status_code==422
    assert review(oid, 'approve', 'Manually verified change.').status_code==200
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations'][0]['approved_text']=='Manually verified change.'


def test_reject_and_evidence_edit_revoke_approval(monkeypatch):
    fake_reliable(monkeypatch)
    before,after=setup_site()
    third=client.post('/api/v1/sites/river/visits',headers=HEADERS,
        json={'visited_on':'2026-09-24','label':'Follow-up'}).json()
    another=client.post('/api/v1/media/images',headers=HEADERS,
        data={'project_id':'river','visit_date':'2026-09-24','visit_id':third['id'],'source':'Team'},
        files={'file':('image.png',image_bytes(),'image/png')}).json()['asset_id']
    oid=client.post('/api/v1/pairs',headers=HEADERS,
        json={'before_asset_id':before,'after_asset_id':after}).json()['id']
    assert review(oid, 'reject').status_code==200
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations']==[]
    assert review(oid, 'approve').status_code==200
    edit=edit_observation(oid, after_asset_id=another)
    assert edit.status_code==200
    assert edit.json()['review_status']=='pending'
    assert edit.json()['approved_text'] is None
    assert edit.json()['ai_draft'] is None
    assert edit.json()['working_text'] is None
    assert 'Evidence changed' in edit.json()['reliability_reason']
    assert client.get('/api/v1/sites/river/report',headers=HEADERS).json()['observations']==[]
    assert client.get(f'/api/v1/observations/{oid}',headers=HEADERS).json()['revisions'][-1]['after_asset_id']==another


def test_pair_rejects_cross_site_and_wrong_order(monkeypatch):
    fake_reliable(monkeypatch)
    before,after=setup_site()
    other,_=setup_site('other')
    for a,b in ((after,before),(before,other),(before,before)):
        r=client.post('/api/v1/pairs',json={'before_asset_id':a,'after_asset_id':b},headers=HEADERS)
        assert r.status_code==422
    assert client.get('/api/v1/sites/river/observations',headers=HEADERS).json()==[]


def test_upload_visit_mismatch_never_calls_cloudinary():
    setup_site()
    visit=client.get('/api/v1/sites/river/visits',headers=HEADERS).json()[0]
    mock=media.cloudinary.uploader.upload
    n=mock.call_count
    response=client.post('/api/v1/media/images',headers=HEADERS,
        data={'project_id':'river','visit_date':'2026-09-24','visit_id':visit['id'],'source':'Team'},
        files={'file':('image.png',image_bytes(),'image/png')})
    assert response.status_code==422
    assert mock.call_count==n

@pytest.mark.parametrize('path,method', [('/api/v1/sites','post'),('/api/v1/sites/river/report','get')])
def test_workflow_requires_token(path,method):
    response=getattr(client,method)(path)
    assert response.status_code==401


def test_stale_review_rejected_and_actor_comes_from_token(monkeypatch):
    fake_reliable(monkeypatch)
    before, after = setup_site()
    observation = client.post('/api/v1/pairs', headers=HEADERS,
        json={'before_asset_id': before, 'after_asset_id': after}).json()
    old_version = observation['version']
    changed = edit_observation(observation['id'], working_text='Reviewer edited this description.')
    assert changed.status_code == 200
    assert changed.json()['version'] == old_version + 1
    stale = review(observation['id'], 'approve', version=old_version)
    assert stale.status_code == 409
    assert client.get('/api/v1/sites/river/report', headers=HEADERS).json()['observations'] == []
    master = review(observation['id'], 'approve', headers={'Authorization': 'Bearer demo-token'})
    assert master.status_code == 403
    current = review(observation['id'], 'approve')
    assert current.status_code == 200
    assert current.json()['reviewed_by'] == 'Aryan'
    assert current.json()['version'] == old_version + 2
    assert client.get(f"/api/v1/observations/{observation['id']}", headers=HEADERS).json()['revisions'][-1]['actor'] == 'Aryan'
    stale_edit = client.patch(f"/api/v1/observations/{observation['id']}", headers=HEADERS,
                              json={'expected_version': old_version, 'working_text': 'Old edit'})
    assert stale_edit.status_code == 409


def test_request_cannot_impersonate_reviewer(monkeypatch):
    fake_reliable(monkeypatch)
    before, after = setup_site()
    observation = client.post('/api/v1/pairs', headers=HEADERS,
        json={'before_asset_id': before, 'after_asset_id': after}).json()
    response = client.post(f"/api/v1/observations/{observation['id']}/review", headers=HEADERS,
        json={'decision': 'approve', 'expected_version': observation['version'],
              'reviewer': 'Attacker'})
    assert response.status_code == 200
    assert response.json()['reviewed_by'] == 'Aryan'


def test_existing_database_adds_version_column(tmp_path, monkeypatch):
    import sqlite3
    from app.services import evidence_store as store
    path = tmp_path / 'legacy.sqlite3'
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(path))
    with sqlite3.connect(path) as db:
        legacy = store.SCHEMA.replace(',\n version INTEGER NOT NULL DEFAULT 1', '')
        legacy = legacy.replace(",\n location TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT ''", '')
        db.executescript(legacy)
    with store.connection() as db:
        columns = {row['name'] for row in db.execute('PRAGMA table_info(observations)')}
        site_columns = {row['name'] for row in db.execute('PRAGMA table_info(sites)')}
    assert 'version' in columns
    assert {'location', 'description'} <= site_columns


def test_demo_served_by_backend():
    assert client.get('/', headers={'Accept': 'text/html'},
                      follow_redirects=False).headers['location'] == '/demo/'
    html = client.get('/demo/')
    assert html.status_code == 200
    assert 'See the change.' in html.text
    assert client.get('/demo/app.js').status_code == 200


def test_synthetic_walkthrough_is_idempotent_and_labeled():
    from scripts.seed_local_demo import seed
    seed()
    seed()
    sites = client.get('/api/v1/sites', headers=HEADERS).json()
    assert [site['id'] for site in sites] == ['demo-riverbank']
    visits = client.get('/api/v1/sites/demo-riverbank/visits', headers=HEADERS).json()
    assert len(visits) == 2
    assert len(visits[0]['assets']) == len(visits[1]['assets']) == 1
    observation = client.get('/api/v1/sites/demo-riverbank/observations', headers=HEADERS).json()[0]
    assert observation['ai_draft'] is None
    assert observation['review_status'] == 'pending'
    assert 'Synthetic' in observation['reliability_reason']
    assert client.get('/demo/sample-media/river-before-synthetic.png').status_code == 200
    approved = review(observation['id'], 'approve')
    assert approved.status_code == 200
    report = client.get('/api/v1/sites/demo-riverbank/report', headers=HEADERS).json()
    assert report['synthetic_demo'] is True
    assert len(report['observations']) == 1
    markdown = client.get('/api/v1/sites/demo-riverbank/report?format=markdown', headers=HEADERS)
    assert 'SYNTHETIC DEMO' in markdown.text
    assert client.get('/showcase/').status_code == 200


def test_measurements_need_named_reviewer_and_explicit_source():
    setup_site()
    visit = client.get('/api/v1/sites/river/visits', headers=HEADERS).json()[1]
    payload = {'visit_id': visit['id'], 'label': 'Collected litter',
               'quantity': 12.5, 'unit': 'kg', 'source': 'Signed scale sheet'}
    master = client.post('/api/v1/sites/river/measurements',
                         headers={'Authorization': 'Bearer demo-token'}, json=payload)
    assert master.status_code == 403
    missing_source = client.post('/api/v1/sites/river/measurements', headers=HEADERS,
                                 json={**payload, 'source': '  '})
    assert missing_source.status_code == 422
    negative = client.post('/api/v1/sites/river/measurements', headers=HEADERS,
                           json={**payload, 'quantity': -5})
    assert negative.status_code == 422
    saved = client.post('/api/v1/sites/river/measurements', headers=HEADERS, json=payload)
    assert saved.status_code == 201
    assert saved.json()['recorded_by'] == 'Aryan'
    report = client.get('/api/v1/sites/river/report', headers=HEADERS).json()
    assert report['observations'] == []
    assert report['recorded_measurements'][0]['quantity'] == 12.5
    assert report['synthetic_demo'] is False
    markdown = client.get('/api/v1/sites/river/report?format=markdown', headers=HEADERS)
    assert '12.5 kg' in markdown.text and 'Signed scale sheet' in markdown.text


def test_migration_adds_permission_status_and_thumbnail_url(tmp_path, monkeypatch):
    import sqlite3
    from app.services import evidence_store as store
    path = tmp_path / 'legacy_assets.sqlite3'
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(path))
    with sqlite3.connect(path) as db:
        legacy = store.SCHEMA.replace(',\n permission_status TEXT NOT NULL DEFAULT \'granted\',\n thumbnail_url TEXT', '')
        legacy = legacy.replace("CHECK(review_status IN ('pending','approved','rejected'))",
                                "CHECK(review_status IN ('pending','approved','rejected','unreliable'))")
        db.executescript(legacy)
        db.execute("INSERT INTO sites(id,name,location,description) VALUES ('s1','Site 1','','')")
        db.execute("INSERT INTO visits(id,site_id,visited_on,label) VALUES ('v1','s1','2026-09-01','V1')")
        db.execute("INSERT INTO visits(id,site_id,visited_on,label) VALUES ('v2','s1','2026-09-02','V2')")
        db.execute("""INSERT INTO assets (asset_id,visit_id,public_id,version,secure_url,source,width,height,format)
                      VALUES ('a1','v1','pub1',1,'https://res.cloudinary.com/demo/image/upload/v1/a1.png','Source',100,100,'png')""")
        db.execute("""INSERT INTO assets (asset_id,visit_id,public_id,version,secure_url,source,width,height,format)
                      VALUES ('a2','v2','pub2',1,'https://res.cloudinary.com/demo/image/upload/v1/a2.png','Source',100,100,'png')""")
        now = store.timestamp()
        db.execute("""INSERT INTO observations (id,site_id,before_asset_id,after_asset_id,ai_draft,working_text,
                      approved_text,review_status,reliability_reason,reviewed_by,reviewed_at,created_at,updated_at,version)
                      VALUES ('o1','s1','a1','a2',NULL,NULL,NULL,'unreliable','Test reason',NULL,NULL,?,?,1)""",
                   (now, now))
    # Connect via store.connection(), which triggers non-destructive migration
    with store.connection() as db:
        asset_columns = {row['name'] for row in db.execute('PRAGMA table_info(assets)')}
        asset_row = dict(db.execute("SELECT * FROM assets WHERE asset_id='a1'").fetchone())
        obs_row = dict(db.execute("SELECT * FROM observations WHERE id='o1'").fetchone())

    assert 'permission_status' in asset_columns
    assert 'thumbnail_url' in asset_columns
    assert asset_row['permission_status'] == 'granted'
    assert asset_row['thumbnail_url'] is None
    assert obs_row['review_status'] == 'pending'
    assert obs_row['reliability_reason'] == 'Test reason'


def test_asset_permission_status_and_thumbnail_persistence():
    setup_site()
    visit = client.get('/api/v1/sites/river/visits', headers=HEADERS).json()[0]

    # Explicit permission status upload
    upload = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'river', 'visit_date': visit['visited_on'], 'visit_id': visit['id'],
              'source': 'Field surveyor consent note', 'permission_status': 'pending_verification'},
        files={'file': ('perm.png', image_bytes(), 'image/png')})
    assert upload.status_code == 201
    asset_data = upload.json()
    assert asset_data['permission_status'] == 'pending_verification'
    assert asset_data.get('thumbnail_url') is not None

    # Retrieve visits and verify assets retain permission_status and thumbnail_url
    visits = client.get('/api/v1/sites/river/visits', headers=HEADERS).json()
    target_visit = [v for v in visits if v['id'] == visit['id']][0]
    saved_asset = [a for a in target_visit['assets'] if a['asset_id'] == asset_data['asset_id']][0]
    assert saved_asset['permission_status'] == 'pending_verification'
    assert saved_asset['thumbnail_url'] == asset_data['thumbnail_url']

    # Default permission status upload
    default_upload = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'river', 'visit_date': visit['visited_on'], 'visit_id': visit['id'],
              'source': 'Standard team photo'},
        files={'file': ('def.png', image_bytes(), 'image/png')})
    assert default_upload.status_code == 201
    assert default_upload.json()['permission_status'] == 'granted'

    # Direct DB test verifying nullable thumbnail_url
    from app.services import evidence_store as store
    with store.connection() as db:
        null_asset_id = store.new_id()
        db.execute("""INSERT INTO assets
            (asset_id,visit_id,public_id,version,secure_url,source,width,height,format,permission_status,thumbnail_url)
            VALUES (?,?,?,1,?,?,100,100,'png','granted',NULL)""",
            (null_asset_id, visit['id'], 'null_thumb', 'https://example.org/null.png', 'Test source'))
        retrieved = store.one(db, "SELECT * FROM assets WHERE asset_id=?", (null_asset_id,))
        assert retrieved['thumbnail_url'] is None
        assert retrieved['permission_status'] == 'granted'


def test_pair_validation_matrix_valid_pair_accepted(monkeypatch):
    """Test A: same site + chronological visits + valid assets -> accepted."""
    fake_reliable(monkeypatch)
    before, after = setup_site('site-a', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS)
    assert res.status_code == 201
    data = res.json()
    assert data['site_id'] == 'site-a'
    assert data['before_asset_id'] == before
    assert data['after_asset_id'] == after
    assert data['review_status'] == 'pending'
    assert data['version'] == 1


def test_pair_validation_matrix_different_sites_rejected():
    """Test B: different sites -> rejected."""
    before, _ = setup_site('site-b1', '2026-09-01', '2026-09-10')
    _, after = setup_site('site-b2', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS)
    assert res.status_code == 422
    assert 'Both images must belong to the same site' in res.text


def test_pair_validation_matrix_visit_order_rejected():
    """Test C: after visit earlier than or equal to before visit -> rejected."""
    before, after = setup_site('site-c', '2026-09-01', '2026-09-10')
    # Inverted order
    res = client.post('/api/v1/pairs', json={'before_asset_id': after, 'after_asset_id': before}, headers=HEADERS)
    assert res.status_code == 422
    assert 'The before visit must precede the after visit' in res.text

    # Same visit / same date upload
    visit = client.get('/api/v1/sites/site-c/visits', headers=HEADERS).json()[0]
    upload2 = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'site-c', 'visit_date': '2026-09-01', 'visit_id': visit['id'], 'source': 'Photo 2'},
        files={'file': ('img.png', image_bytes(), 'image/png')}).json()
    res_same = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': upload2['asset_id']}, headers=HEADERS)
    assert res_same.status_code == 422
    assert 'The before visit must precede the after visit' in res_same.text


def test_pair_validation_matrix_nonexistent_before_asset_rejected():
    """Test D: nonexistent before asset -> rejected (404)."""
    _, after = setup_site('site-d', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={'before_asset_id': 'nonexistent-before-id', 'after_asset_id': after}, headers=HEADERS)
    assert res.status_code == 404
    assert 'before asset' in res.text.lower()


def test_pair_validation_matrix_nonexistent_after_asset_rejected():
    """Test E: nonexistent after asset -> rejected (404)."""
    before, _ = setup_site('site-e', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': 'nonexistent-after-id'}, headers=HEADERS)
    assert res.status_code == 404
    assert 'after asset' in res.text.lower()


def test_pair_validation_matrix_asset_visit_mismatch_rejected():
    """Test F: asset belongs to different visit than claimed -> rejected."""
    before, after = setup_site('site-f', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={
        'before_asset_id': before,
        'after_asset_id': after,
        'before_visit_id': 'mismatched-visit-id'
    }, headers=HEADERS)
    assert res.status_code == 422
    assert 'claimed visit' in res.text.lower()


def test_pair_validation_matrix_visit_site_mismatch_rejected():
    """Test G: visit belongs to different site -> rejected."""
    before, after = setup_site('site-g', '2026-09-01', '2026-09-10')
    res = client.post('/api/v1/pairs', json={
        'before_asset_id': before,
        'after_asset_id': after,
        'site_id': 'other-site'
    }, headers=HEADERS)
    assert res.status_code == 422
    assert 'Both images must belong to the same site' in res.text


def test_pair_validation_matrix_permission_status_rejected():
    """Test H: permission_status not acceptable -> rejected."""
    setup_site('site-h', '2026-09-01', '2026-09-10')
    visits = client.get('/api/v1/sites/site-h/visits', headers=HEADERS).json()
    v1_id, v2_id = visits[0]['id'], visits[1]['id']

    # Upload asset with 'revoked' permission
    up_revoked = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'site-h', 'visit_date': '2026-09-01', 'visit_id': v1_id,
              'source': 'Revoked contributor photo', 'permission_status': 'revoked'},
        files={'file': ('rev.png', image_bytes(), 'image/png')}).json()['asset_id']

    # Upload valid after asset with 'granted'
    up_valid = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'site-h', 'visit_date': '2026-09-10', 'visit_id': v2_id,
              'source': 'Team photo', 'permission_status': 'granted'},
        files={'file': ('val.png', image_bytes(), 'image/png')}).json()['asset_id']

    res = client.post('/api/v1/pairs', json={'before_asset_id': up_revoked, 'after_asset_id': up_valid}, headers=HEADERS)
    assert res.status_code == 422
    assert 'must be \'granted\'' in res.text or 'permission' in res.text.lower()

    # Upload asset with 'pending_verification'
    up_pending = client.post('/api/v1/media/images', headers=HEADERS,
        data={'project_id': 'site-h', 'visit_date': '2026-09-01', 'visit_id': v1_id,
              'source': 'Pending consent photo', 'permission_status': 'pending_verification'},
        files={'file': ('pend.png', image_bytes(), 'image/png')}).json()['asset_id']

    res_pending = client.post('/api/v1/pairs', json={'before_asset_id': up_pending, 'after_asset_id': up_valid}, headers=HEADERS)
    assert res_pending.status_code == 422
    assert 'must be \'granted\'' in res_pending.text or 'permission' in res_pending.text.lower()


def test_pair_validation_matrix_deleted_missing_asset_rejected():
    """Test I: deleted/missing asset cannot form a pair or be reviewed."""
    before, after = setup_site('site-i', '2026-09-01', '2026-09-10')
    from app.services import evidence_store as store

    with store.connection() as db:
        db.execute('DELETE FROM assets WHERE asset_id=?', (before,))

    res = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS)
    assert res.status_code == 404
    assert 'Evidence asset not found' in res.text


def test_pair_validation_matrix_manually_tampered_ids_rejected(monkeypatch):
    """Test J: manually tampered asset/site IDs cannot be injected."""
    fake_reliable(monkeypatch)
    before_a, after_a = setup_site('site-j1', '2026-09-01', '2026-09-10')
    _, after_b = setup_site('site-j2', '2026-09-01', '2026-09-10')

    obs = client.post('/api/v1/pairs', json={'before_asset_id': before_a, 'after_asset_id': after_a}, headers=HEADERS).json()

    # Attempt to tamper: patch observation with an asset from site-j2
    tampered_edit = edit_observation(obs['id'], after_asset_id=after_b)
    assert tampered_edit.status_code == 422
    assert 'Both images must belong to the same site' in tampered_edit.text

    # Attempt to change site_id of observation via edit payload
    version = client.get(f"/api/v1/observations/{obs['id']}", headers=HEADERS).json()['version']
    site_tamper = client.patch(f"/api/v1/observations/{obs['id']}", headers=HEADERS,
                               json={'expected_version': version, 'site_id': 'site-j2'})
    assert site_tamper.status_code == 422
    assert 'Cannot change the site of an observation' in site_tamper.text


def test_pair_validation_matrix_review_integrity_mutation_invalidates_approval(monkeypatch):
    """Test K: existing approved observation + pair mutation -> approval invalidated / returns to pending."""
    fake_reliable(monkeypatch)
    before, after = setup_site('site-k', '2026-09-01', '2026-09-10')
    obs = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS).json()
    
    app_res = review(obs['id'], 'approve', 'Initial verified clean observation.')
    assert app_res.status_code == 200
    assert app_res.json()['review_status'] == 'approved'
    assert app_res.json()['approved_text'] == 'Initial verified clean observation.'

    v3 = client.post('/api/v1/sites/site-k/visits', headers=HEADERS,
                     json={'visited_on': '2026-09-20', 'label': 'Visit 3'}).json()
    asset3 = client.post('/api/v1/media/images', headers=HEADERS,
                         data={'project_id': 'site-k', 'visit_date': '2026-09-20', 'visit_id': v3['id'], 'source': 'Surveyor 3'},
                         files={'file': ('img3.png', image_bytes(), 'image/png')}).json()['asset_id']

    edit_res = edit_observation(obs['id'], after_asset_id=asset3)
    assert edit_res.status_code == 200
    data = edit_res.json()
    assert data['review_status'] == 'pending'
    assert data['approved_text'] is None
    assert data['reviewed_by'] is None
    assert data['reviewed_at'] is None
    assert data['after_asset_id'] == asset3
    assert 'Evidence changed' in data['reliability_reason']


def test_pair_validation_matrix_review_integrity_report_exclusion_on_evidence_change(monkeypatch):
    """Test L: existing approved observation + evidence changed -> approval invalidated and excluded from report."""
    fake_reliable(monkeypatch)
    before, after = setup_site('site-l', '2026-09-01', '2026-09-10')
    obs = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS).json()
    review(obs['id'], 'approve', 'Verified clean bank.')

    rep_before = client.get('/api/v1/sites/site-l/report', headers=HEADERS).json()
    assert len(rep_before['observations']) == 1
    assert rep_before['observations'][0]['approved_text'] == 'Verified clean bank.'

    v3 = client.post('/api/v1/sites/site-l/visits', headers=HEADERS,
                     json={'visited_on': '2026-09-25', 'label': 'Visit 3'}).json()
    asset3 = client.post('/api/v1/media/images', headers=HEADERS,
                         data={'project_id': 'site-l', 'visit_date': '2026-09-25', 'visit_id': v3['id'], 'source': 'Surveyor'},
                         files={'file': ('img.png', image_bytes(), 'image/png')}).json()['asset_id']
    edit_observation(obs['id'], after_asset_id=asset3)

    rep_after = client.get('/api/v1/sites/site-l/report', headers=HEADERS).json()
    assert len(rep_after['observations']) == 0

    reloaded = client.get(f"/api/v1/observations/{obs['id']}", headers=HEADERS).json()
    last_rev = reloaded['revisions'][-1]
    assert last_rev['action'] == 'edited'
    assert last_rev['after_asset_id'] == asset3


def test_pair_validation_matrix_metadata_update_preserves_contract(monkeypatch):
    """Test M: existing approved observation + same evidence:
    - no-op update preserves approved status and version
    - text edit resets to pending per trust model contract
    """
    fake_reliable(monkeypatch)
    before, after = setup_site('site-m', '2026-09-01', '2026-09-10')
    obs = client.post('/api/v1/pairs', json={'before_asset_id': before, 'after_asset_id': after}, headers=HEADERS).json()
    approved = review(obs['id'], 'approve', 'Stable verified observation.').json()
    original_version = approved['version']

    # 1. No-op edit with unchanged text and same evidence
    noop = client.patch(f"/api/v1/observations/{obs['id']}", headers=HEADERS,
                        json={'expected_version': original_version, 'working_text': 'Stable verified observation.'}).json()
    assert noop['review_status'] == 'approved'
    assert noop['version'] == original_version
    assert noop['approved_text'] == 'Stable verified observation.'

    # 2. Text update resets to pending per human verification invariant
    edited = client.patch(f"/api/v1/observations/{obs['id']}", headers=HEADERS,
                          json={'expected_version': original_version, 'working_text': 'Updated observation draft.'}).json()
    assert edited['review_status'] == 'pending'
    assert edited['approved_text'] is None
    assert edited['working_text'] == 'Updated observation draft.'
    assert edited['version'] == original_version + 1


def test_matrix_n_ai_result_always_pending_until_human_review(monkeypatch):
    """Test N: AI result is strictly a proposal engine and cannot auto-approve.
    - 'changed', 'uncertain', and 'insufficient_evidence' all create 'pending' observations.
    - unapproved observations never appear in final reports.
    - human reviewer approval is mandatory to graduate to 'approved'.
    """
    # 1. Structured 'changed' result
    async def compare_changed(*args):
        return image_comparison.Comparison(
            status=image_comparison.ComparisonStatus.CHANGED,
            summary='Visible reduction in trash on ground.',
            confidence=0.89,
            reliable=True,
            observation='Visible reduction in trash on ground.'
        )
    monkeypatch.setattr('app.routes.evidence.compare_images', compare_changed)
    b1, a1 = setup_site('site-n1', '2026-09-01', '2026-09-10')
    obs1 = client.post('/api/v1/pairs', json={'before_asset_id': b1, 'after_asset_id': a1}, headers=HEADERS).json()
    assert obs1['review_status'] == 'pending'
    assert obs1['approved_text'] is None
    assert obs1['ai_draft'] == 'Visible reduction in trash on ground.'
    rep1 = client.get('/api/v1/sites/site-n1/report', headers=HEADERS).json()
    assert len(rep1['observations']) == 0, "AI proposal must not appear in report prior to human review"

    # 2. Structured 'uncertain' result
    async def compare_uncertain(*args):
        return image_comparison.Comparison(
            status=image_comparison.ComparisonStatus.UNCERTAIN,
            confidence=0.3,
            uncertainty_reason='camera_angle_mismatch',
            reliable=False,
            reason='camera_angle_mismatch'
        )
    monkeypatch.setattr('app.routes.evidence.compare_images', compare_uncertain)
    b2, a2 = setup_site('site-n2', '2026-09-01', '2026-09-10')
    obs2 = client.post('/api/v1/pairs', json={'before_asset_id': b2, 'after_asset_id': a2}, headers=HEADERS).json()
    assert obs2['review_status'] == 'pending'
    assert obs2['approved_text'] is None
    assert obs2['ai_draft'] is None
    assert obs2['reliability_reason'] == 'camera_angle_mismatch'
    rep2 = client.get('/api/v1/sites/site-n2/report', headers=HEADERS).json()
    assert len(rep2['observations']) == 0

    # 3. Structured 'insufficient_evidence' result
    async def compare_insufficient(*args):
        return image_comparison.Comparison(
            status=image_comparison.ComparisonStatus.INSUFFICIENT_EVIDENCE,
            confidence=0.05,
            uncertainty_reason='poor_image_quality',
            reliable=False,
            reason='poor_image_quality'
        )
    monkeypatch.setattr('app.routes.evidence.compare_images', compare_insufficient)
    b3, a3 = setup_site('site-n3', '2026-09-01', '2026-09-10')
    obs3 = client.post('/api/v1/pairs', json={'before_asset_id': b3, 'after_asset_id': a3}, headers=HEADERS).json()
    assert obs3['review_status'] == 'pending'
    assert obs3['approved_text'] is None
    assert obs3['ai_draft'] is None
    assert obs3['reliability_reason'] == 'poor_image_quality'

    # Human reviewer inspects and provides human-verified observation
    approved = review(obs3['id'], 'approve', 'Human reviewer manually confirmed bank cleanup despite blur.', headers=HEADERS)
    assert approved.status_code == 200
    assert approved.json()['review_status'] == 'approved'
    assert approved.json()['approved_text'] == 'Human reviewer manually confirmed bank cleanup despite blur.'

    rep3 = client.get('/api/v1/sites/site-n3/report', headers=HEADERS).json()
    assert len(rep3['observations']) == 1
    assert rep3['observations'][0]['approved_text'] == 'Human reviewer manually confirmed bank cleanup despite blur.'





@pytest.fixture(autouse=True)
def optional_gemini_provider_contract(monkeypatch):
    """These legacy contract tests deliberately exercise the optional Gemini adapter."""
    from app.config import settings
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
