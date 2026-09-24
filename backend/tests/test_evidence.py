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
    monkeypatch.setattr(settings, 'REVIEWER_TOKENS', SecretStr('{"Farhan":"reviewer-token"}'))
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
    assert observation['review_status']=='unreliable'
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
    assert current.json()['reviewed_by'] == 'Farhan'
    assert current.json()['version'] == old_version + 2
    assert client.get(f"/api/v1/observations/{observation['id']}", headers=HEADERS).json()['revisions'][-1]['actor'] == 'Farhan'
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
              'reviewer': 'Aryan'})
    assert response.status_code == 200
    assert response.json()['reviewed_by'] == 'Farhan'


def test_existing_database_adds_version_column(tmp_path, monkeypatch):
    import sqlite3
    from app.services import evidence_store as store
    path = tmp_path / 'legacy.sqlite3'
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(path))
    with sqlite3.connect(path) as db:
        db.executescript(store.SCHEMA.replace(',\n version INTEGER NOT NULL DEFAULT 1', ''))
    with store.connection() as db:
        columns = {row['name'] for row in db.execute('PRAGMA table_info(observations)')}
    assert 'version' in columns


def test_demo_served_by_backend():
    html = client.get('/demo/')
    assert html.status_code == 200
    assert 'Show the evidence.' in html.text
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
    assert saved.json()['recorded_by'] == 'Farhan'
    report = client.get('/api/v1/sites/river/report', headers=HEADERS).json()
    assert report['observations'] == []
    assert report['recorded_measurements'][0]['quantity'] == 12.5
    assert report['synthetic_demo'] is False
    markdown = client.get('/api/v1/sites/river/report?format=markdown', headers=HEADERS)
    assert '12.5 kg' in markdown.text and 'Signed scale sheet' in markdown.text
