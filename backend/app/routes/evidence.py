"""Site visits, evidence selection, human review, and grounded exports."""
from datetime import date
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.routes.media import require_upload_token
from app.services import evidence_store as store
from app.services.image_comparison import compare_images

router = APIRouter(prefix='/api/v1', tags=['Evidence workflow'], dependencies=[Depends(require_upload_token)])
ID = r'^[a-z0-9][a-z0-9_-]{0,63}$'


class SiteInput(BaseModel):
    id: str = Field(pattern=ID)
    name: str = Field(min_length=1, max_length=120)


class VisitInput(BaseModel):
    visited_on: date
    label: str = Field(min_length=1, max_length=120)


class PairInput(BaseModel):
    before_asset_id: str = Field(min_length=1, max_length=128)
    after_asset_id: str = Field(min_length=1, max_length=128)


class EditInput(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    working_text: str | None = Field(default=None, max_length=600)
    before_asset_id: str | None = None
    after_asset_id: str | None = None


class ReviewInput(BaseModel):
    decision: Literal['approve', 'reject']
    reviewer: str = Field(min_length=1, max_length=100)
    text: str | None = Field(default=None, max_length=600)


def require_site(db, site_id):
    site = store.one(db, 'SELECT * FROM sites WHERE id=?', (site_id,))
    if not site:
        raise HTTPException(404, 'Site not found')
    return site


def require_observation(db, observation_id):
    observation = store.one(db, 'SELECT * FROM observations WHERE id=?', (observation_id,))
    if not observation:
        raise HTTPException(404, 'Observation not found')
    return observation


def validate_pair(db, before_id, after_id, site_id=None):
    if before_id == after_id:
        raise HTTPException(422, 'Before and after evidence must differ')
    sql = ('SELECT a.*, v.site_id, v.visited_on FROM assets a '
           'JOIN visits v ON v.id=a.visit_id WHERE a.asset_id=?')
    before, after = store.one(db, sql, (before_id,)), store.one(db, sql, (after_id,))
    if not before or not after:
        raise HTTPException(404, 'Evidence asset not found')
    if before['site_id'] != after['site_id'] or (site_id and before['site_id'] != site_id):
        raise HTTPException(422, 'Both images must belong to the same site')
    if before['visited_on'] >= after['visited_on']:
        raise HTTPException(422, 'The before visit must precede the after visit')
    return before, after


@router.post('/sites', status_code=201)
def create_site(payload: SiteInput):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, 'Site name must not be blank')
    with store.connection() as db:
        if store.one(db, 'SELECT id FROM sites WHERE id=?', (payload.id,)):
            raise HTTPException(409, 'Site already exists')
        db.execute('INSERT INTO sites(id,name) VALUES (?,?)', (payload.id, name))
    return {'id': payload.id, 'name': name}


@router.post('/sites/{site_id}/visits', status_code=201)
def create_visit(site_id: str, payload: VisitInput):
    label = payload.label.strip()
    if not label:
        raise HTTPException(422, 'Visit label must not be blank')
    with store.connection() as db:
        require_site(db, site_id)
        visit = {'id': store.new_id(), 'site_id': site_id,
                 'visited_on': payload.visited_on.isoformat(), 'label': label}
        db.execute('INSERT INTO visits(id,site_id,visited_on,label) VALUES (:id,:site_id,:visited_on,:label)', visit)
    return visit


@router.get('/sites/{site_id}/visits')
def list_visits(site_id: str):
    with store.connection() as db:
        require_site(db, site_id)
        visits = store.rows(db, 'SELECT * FROM visits WHERE site_id=? ORDER BY visited_on,id', (site_id,))
        for visit in visits:
            visit['assets'] = store.rows(db, 'SELECT * FROM assets WHERE visit_id=? ORDER BY asset_id', (visit['id'],))
        return visits


@router.post('/pairs', status_code=201)
async def select_pair(payload: PairInput):
    with store.connection() as db:
        before, after = validate_pair(db, payload.before_asset_id, payload.after_asset_id)
    comparison = await compare_images(before, after)
    now = store.timestamp()
    observation = {
        'id': store.new_id(), 'site_id': before['site_id'],
        'before_asset_id': before['asset_id'], 'after_asset_id': after['asset_id'],
        'ai_draft': comparison.observation if comparison.reliable else None,
        'working_text': comparison.observation if comparison.reliable else None,
        'approved_text': None,
        'review_status': 'pending' if comparison.reliable else 'unreliable',
        'reliability_reason': comparison.reason, 'reviewed_by': None,
        'reviewed_at': None, 'created_at': now, 'updated_at': now,
    }
    with store.connection() as db:
        # Recheck after the external AI call; the chosen records are immutable.
        validate_pair(db, payload.before_asset_id, payload.after_asset_id, before['site_id'])
        db.execute('''INSERT INTO observations VALUES
            (:id,:site_id,:before_asset_id,:after_asset_id,:ai_draft,:working_text,
             :approved_text,:review_status,:reliability_reason,:reviewed_by,
             :reviewed_at,:created_at,:updated_at)''', observation)
        store.revision(db, observation, 'drafted' if comparison.reliable else 'comparison_unreliable',
                       'system', observation['ai_draft'] or observation['reliability_reason'])
    return observation


@router.get('/sites/{site_id}/observations')
def list_observations(site_id: str):
    with store.connection() as db:
        require_site(db, site_id)
        return store.rows(db, 'SELECT * FROM observations WHERE site_id=? ORDER BY created_at,id', (site_id,))


@router.get('/observations/{observation_id}')
def get_observation(observation_id: str):
    with store.connection() as db:
        observation = require_observation(db, observation_id)
        observation['revisions'] = store.rows(
            db, 'SELECT * FROM observation_revisions WHERE observation_id=? ORDER BY id',
            (observation_id,))
        return observation


@router.patch('/observations/{observation_id}')
def edit_observation(observation_id: str, payload: EditInput):
    if not payload.actor.strip():
        raise HTTPException(422, 'Actor must not be blank')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        observation = require_observation(db, observation_id)
        before_id = payload.before_asset_id or observation['before_asset_id']
        after_id = payload.after_asset_id or observation['after_asset_id']
        validate_pair(db, before_id, after_id, observation['site_id'])
        text = payload.working_text.strip() if payload.working_text is not None else observation['working_text']
        evidence_changed = (before_id != observation['before_asset_id'] or
                            after_id != observation['after_asset_id'])
        changed = evidence_changed or text != observation['working_text']
        if not changed:
            return observation
        if evidence_changed and payload.working_text is None:
            text = None
        db.execute('''UPDATE observations SET before_asset_id=?,after_asset_id=?,ai_draft=?,
            working_text=?,approved_text=NULL,review_status='pending',reliability_reason=?,
            reviewed_by=NULL,reviewed_at=NULL,updated_at=? WHERE id=?''',
            (before_id, after_id, None if evidence_changed else observation['ai_draft'],
             text, 'Evidence changed; review the new pair manually.' if evidence_changed
             else observation['reliability_reason'],
             store.timestamp(), observation_id))
        updated = require_observation(db, observation_id)
        store.revision(db, updated, 'edited', payload.actor.strip(), text)
        return updated


@router.post('/observations/{observation_id}/review')
def review_observation(observation_id: str, payload: ReviewInput):
    reviewer = payload.reviewer.strip()
    if not reviewer:
        raise HTTPException(422, 'Reviewer must not be blank')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        observation = require_observation(db, observation_id)
        if observation['review_status'] == 'approved':
            raise HTTPException(409, 'Edit before reviewing an approved observation again')
        validate_pair(db, observation['before_asset_id'], observation['after_asset_id'], observation['site_id'])
        if payload.decision == 'approve':
            text = (payload.text if payload.text is not None else observation['working_text']) or ''
            text = text.strip()
            if not text:
                raise HTTPException(422, 'Approval requires a written observation')
            status, approved = 'approved', text
        else:
            status, approved = 'rejected', None
            text = payload.text.strip() if payload.text is not None else observation['working_text']
        now = store.timestamp()
        db.execute('''UPDATE observations SET working_text=?, approved_text=?,review_status=?,
            reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?''',
            (text, approved, status, reviewer, now, now, observation_id))
        updated = require_observation(db, observation_id)
        store.revision(db, updated, status, reviewer, text)
        return updated


def report_rows(db, site_id):
    return store.rows(db, '''SELECT o.id,o.approved_text,o.reviewed_by,o.reviewed_at,
        b.asset_id AS before_asset_id,b.secure_url AS before_url,b.version AS before_version,
        a.asset_id AS after_asset_id,a.secure_url AS after_url,a.version AS after_version,
        bv.visited_on AS before_date,av.visited_on AS after_date
        FROM observations o
        JOIN assets b ON b.asset_id=o.before_asset_id
        JOIN assets a ON a.asset_id=o.after_asset_id
        JOIN visits bv ON bv.id=b.visit_id
        JOIN visits av ON av.id=a.visit_id
        WHERE o.site_id=? AND o.review_status='approved' AND o.approved_text IS NOT NULL
        ORDER BY o.reviewed_at,o.id''', (site_id,))


@router.get('/sites/{site_id}/report')
def export_report(site_id: str, format: Literal['json','markdown'] = Query(default='json')):
    with store.connection() as db:
        site = require_site(db, site_id)
        observations = report_rows(db, site_id)
    if format == 'json':
        return {'site': site, 'generated_at': store.timestamp(), 'observations': observations,
                'recorded_measurements': []}
    lines = [f'# {escape(site["name"])} — Cleanup Evidence Report', '',
             'Only reviewed observations are included. No measurements were recorded.', '']
    for item in observations:
        lines += [f'## Observation {item["id"]}', '', escape(item['approved_text']), '',
                  f'Before ({item["before_date"]}): {item["before_url"]}',
                  f'After ({item["after_date"]}): {item["after_url"]}',
                  f'Approved by {escape(item["reviewed_by"])} at {item["reviewed_at"]}', '']
    return Response('\n'.join(lines), media_type='text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="lex-{site_id}-report.md"'})
