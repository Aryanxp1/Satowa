"""Site visits, evidence selection, human review, and grounded exports."""
from datetime import date
from html import escape
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.routes.media import require_upload_token
from app.services import evidence_store as store
from app.services.image_comparison import compare_images
from app.services.reviewer_auth import authorization_or_local_cookie, reviewer_for_authorization

router = APIRouter(prefix='/api/v1', tags=['Evidence workflow'], dependencies=[Depends(require_upload_token)])
ID = r'^[a-z0-9][a-z0-9_-]{0,63}$'


class SiteInput(BaseModel):
    id: str = Field(pattern=ID)
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=600)
    project_id: Optional[str] = Field(default=None, pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SiteUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=600)
    project_id: Optional[str] = Field(default=None, pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class VisitInput(BaseModel):
    visited_on: date
    label: str = Field(min_length=1, max_length=120)


class PairInput(BaseModel):
    before_asset_id: str = Field(min_length=1, max_length=128)
    after_asset_id: str = Field(min_length=1, max_length=128)
    site_id: str | None = None
    before_visit_id: str | None = None
    after_visit_id: str | None = None


class EditInput(BaseModel):
    expected_version: int = Field(ge=1)
    working_text: str | None = Field(default=None, max_length=600)
    before_asset_id: str | None = None
    after_asset_id: str | None = None
    site_id: str | None = None
    before_visit_id: str | None = None
    after_visit_id: str | None = None


class ReviewInput(BaseModel):
    decision: Literal['approve', 'reject']
    expected_version: int = Field(ge=1)
    text: str | None = Field(default=None, max_length=600)


class MeasurementInput(BaseModel):
    visit_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=10_000_000, allow_inf_nan=False)
    unit: Literal['kg', 'bags', 'items']
    source: str = Field(min_length=1, max_length=200)


def require_reviewer(request: Request, authorization: str | None = Header(default=None)):
    return reviewer_for_authorization(authorization_or_local_cookie(authorization, request))


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


VALID_IMAGE_FORMATS = {'jpeg', 'jpg', 'png', 'webp'}


def validate_pair(
    db,
    before_id: str,
    after_id: str,
    site_id: str | None = None,
    before_visit_id: str | None = None,
    after_visit_id: str | None = None,
):
    """Authoritative server-side evidence pair validation.

    Enforces invariants:
    - Non-empty, distinct before and after asset IDs
    - Both assets exist in the persistent store
    - Both assets have valid media formats, secure URLs, and positive dimensions
    - Both assets have acceptable permission_status ('granted')
    - Both assets reference existing visits and match any claimed visits
    - Both visits reference existing sites and match any claimed site
    - Both visits belong to the same site
    - The before visit strictly precedes the after visit chronologically
    """
    if not before_id or not after_id:
        raise HTTPException(422, 'Both before and after evidence asset IDs must be provided')
    if before_id == after_id:
        raise HTTPException(422, 'Before and after evidence must differ')

    # 1. Existence check on persistent assets table
    before_asset = store.one(db, 'SELECT * FROM assets WHERE asset_id=?', (before_id,))
    if not before_asset:
        raise HTTPException(404, f'Evidence asset not found: before asset {before_id}')

    after_asset = store.one(db, 'SELECT * FROM assets WHERE asset_id=?', (after_id,))
    if not after_asset:
        raise HTTPException(404, f'Evidence asset not found: after asset {after_id}')

    # 2. Media validity (format, dimensions, secure URL)
    before_fmt = (before_asset.get('format') or '').lower()
    after_fmt = (after_asset.get('format') or '').lower()
    if before_fmt not in VALID_IMAGE_FORMATS or not before_asset.get('secure_url'):
        raise HTTPException(422, f'Before asset is not valid image evidence ({before_fmt})')
    if after_fmt not in VALID_IMAGE_FORMATS or not after_asset.get('secure_url'):
        raise HTTPException(422, f'After asset is not valid image evidence ({after_fmt})')
    if (before_asset.get('width') or 0) <= 0 or (before_asset.get('height') or 0) <= 0:
        raise HTTPException(422, 'Before asset has invalid dimensions')
    if (after_asset.get('width') or 0) <= 0 or (after_asset.get('height') or 0) <= 0:
        raise HTTPException(422, 'After asset has invalid dimensions')

    # 3. Permission status check (only 'granted' permitted for evidence pairs)
    if before_asset.get('permission_status') != 'granted':
        raise HTTPException(
            422,
            f"Before asset permission is '{before_asset.get('permission_status')}', must be 'granted'"
        )
    if after_asset.get('permission_status') != 'granted':
        raise HTTPException(
            422,
            f"After asset permission is '{after_asset.get('permission_status')}', must be 'granted'"
        )

    # 4. Visit existence and claimed visit verification
    before_visit = store.one(db, 'SELECT * FROM visits WHERE id=?', (before_asset['visit_id'],))
    if not before_visit:
        raise HTTPException(422, f"Before asset references nonexistent visit: {before_asset['visit_id']}")

    after_visit = store.one(db, 'SELECT * FROM visits WHERE id=?', (after_asset['visit_id'],))
    if not after_visit:
        raise HTTPException(422, f"After asset references nonexistent visit: {after_asset['visit_id']}")

    if before_visit_id and before_asset['visit_id'] != before_visit_id:
        raise HTTPException(422, 'Before asset does not belong to the claimed visit')
    if after_visit_id and after_asset['visit_id'] != after_visit_id:
        raise HTTPException(422, 'After asset does not belong to the claimed visit')

    # 5. Site existence
    before_site = store.one(db, 'SELECT * FROM sites WHERE id=?', (before_visit['site_id'],))
    if not before_site:
        raise HTTPException(422, f"Before visit references nonexistent site: {before_visit['site_id']}")

    after_site = store.one(db, 'SELECT * FROM sites WHERE id=?', (after_visit['site_id'],))
    if not after_site:
        raise HTTPException(422, f"After visit references nonexistent site: {after_visit['site_id']}")

    # 6. Site consistency: both belong to same site and match any claimed site
    if before_visit['site_id'] != after_visit['site_id']:
        raise HTTPException(422, 'Both images must belong to the same site')

    if site_id and (before_visit['site_id'] != site_id or after_visit['site_id'] != site_id):
        raise HTTPException(422, 'Both images must belong to the same site')

    # 7. Chronological ordering
    if before_visit['visited_on'] >= after_visit['visited_on']:
        raise HTTPException(422, 'The before visit must precede the after visit')

    before_dict = dict(before_asset)
    before_dict['site_id'] = before_visit['site_id']
    before_dict['visited_on'] = before_visit['visited_on']

    after_dict = dict(after_asset)
    after_dict['site_id'] = after_visit['site_id']
    after_dict['visited_on'] = after_visit['visited_on']

    return before_dict, after_dict


@router.post('/sites', status_code=201)
def create_site(payload: SiteInput):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, 'Site name must not be blank')
    now = store.timestamp()
    # Use supplied project_id or fall back to default project
    project_id = (payload.project_id or '').strip() or 'proj_default'
    with store.connection() as db:
        if store.one(db, 'SELECT id FROM sites WHERE id=?', (payload.id,)):
            raise HTTPException(409, 'Site already exists')
        # Verify project exists
        if not store.get_project(db, project_id):
            raise HTTPException(404, f"Project '{project_id}' not found")
        db.execute(
            'INSERT INTO sites(id,name,location,description,project_id,latitude,longitude,created_at) VALUES (?,?,?,?,?,?,?,?)',
            (payload.id, name, payload.location.strip(), payload.description.strip(),
             project_id, payload.latitude, payload.longitude, now)
        )
    return {
        'id': payload.id, 'name': name, 'location': payload.location.strip(),
        'description': payload.description.strip(), 'project_id': project_id,
        'latitude': payload.latitude, 'longitude': payload.longitude, 'created_at': now,
    }


@router.get('/sites')
def list_sites(project_id: Optional[str] = Query(default=None)):
    with store.connection() as db:
        if project_id:
            return store.rows(db, 'SELECT * FROM sites WHERE project_id=? ORDER BY name,id', (project_id,))
        return store.rows(db, 'SELECT * FROM sites ORDER BY name,id')


@router.get('/sites/{site_id}/detail')
def get_site_detail(site_id: str):
    """Retrieve site record with aggregate media metrics."""
    from app.services.media_query import get_site_summary
    with store.connection() as db:
        return get_site_summary(db, site_id)


@router.get('/sites/{site_id}/media')
def get_site_media(
    site_id: str,
    media_type: Optional[Literal['image', 'video']] = None,
    permission_status: Optional[Literal['granted', 'pending_verification', 'revoked']] = None,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    sort: Literal['desc', 'asc'] = 'desc',
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Retrieve paginated media assets for a specific site."""
    from app.services.media_query import MediaQueryFilters, query_media_assets, validate_date_string
    validated_from = validate_date_string(date_from, 'date_from')
    validated_to = validate_date_string(date_to, 'date_to')
    with store.connection() as db:
        require_site(db, site_id)
        filters = MediaQueryFilters(
            site_id=site_id,
            media_type=media_type,
            permission_status=permission_status,
            date_from=validated_from,
            date_to=validated_to,
            sort=sort,
            page=page,
            limit=limit,
        )
        return query_media_assets(db, filters)


@router.patch('/sites/{site_id}')
def update_site(site_id: str, payload: SiteUpdate, reviewer: str = Depends(require_reviewer)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, 'Site name must not be blank')
    with store.connection() as db:
        require_site(db, site_id)
        db.execute(
            'UPDATE sites SET name=?,location=?,description=?,latitude=?,longitude=? WHERE id=?',
            (name, payload.location.strip(), payload.description.strip(),
             payload.latitude, payload.longitude, site_id)
        )
        return require_site(db, site_id)


@router.get('/integrations')
def integration_status():
    return {
        'cloudinary_ready': all((settings.CLOUDINARY_CLOUD_NAME,
                                 settings.CLOUDINARY_API_KEY,
                                 settings.CLOUDINARY_API_SECRET.get_secret_value())),
        'gemini_ready': bool(settings.GEMINI_API_KEY),
    }


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
        before, after = validate_pair(
            db,
            payload.before_asset_id,
            payload.after_asset_id,
            site_id=payload.site_id,
            before_visit_id=payload.before_visit_id,
            after_visit_id=payload.after_visit_id,
        )
    comparison = await compare_images(before, after)
    now = store.timestamp()
    observation = {
        'id': store.new_id(), 'site_id': before['site_id'],
        'before_asset_id': before['asset_id'], 'after_asset_id': after['asset_id'],
        'ai_draft': comparison.observation if comparison.reliable else None,
        'working_text': comparison.observation if comparison.reliable else None,
        'approved_text': None,
        'review_status': 'pending',
        'reliability_reason': comparison.reason, 'reviewed_by': None,
        'reviewed_at': None, 'created_at': now, 'updated_at': now, 'version': 1,
    }
    with store.connection() as db:
        # Recheck after the external AI call; the chosen records are immutable.
        validate_pair(
            db,
            payload.before_asset_id,
            payload.after_asset_id,
            site_id=payload.site_id or before['site_id'],
            before_visit_id=payload.before_visit_id,
            after_visit_id=payload.after_visit_id,
        )
        db.execute('''INSERT INTO observations VALUES
            (:id,:site_id,:before_asset_id,:after_asset_id,:ai_draft,:working_text,
             :approved_text,:review_status,:reliability_reason,:reviewed_by,
             :reviewed_at,:created_at,:updated_at,:version)''', observation)
        store.revision(db, observation, 'drafted' if comparison.reliable else 'comparison_unreliable',
                       'system', observation['ai_draft'] or observation['reliability_reason'])
    obs_response = dict(observation)
    obs_response['comparison'] = comparison.model_dump()
    return obs_response


@router.get('/sites/{site_id}/observations')
def list_observations(site_id: str):
    with store.connection() as db:
        require_site(db, site_id)
        return store.rows(db, 'SELECT * FROM observations WHERE site_id=? ORDER BY created_at,id', (site_id,))


@router.post('/sites/{site_id}/measurements', status_code=201)
def record_measurement(site_id: str, payload: MeasurementInput,
                       reviewer: str = Depends(require_reviewer)):
    label, source = payload.label.strip(), payload.source.strip()
    if not label or not source:
        raise HTTPException(422, 'Measurement label and source must not be blank')
    with store.connection() as db:
        require_site(db, site_id)
        visit = store.one(db, 'SELECT * FROM visits WHERE id=?', (payload.visit_id,))
        if not visit or visit['site_id'] != site_id:
            raise HTTPException(422, 'Measurement visit must belong to this site')
        measurement = {
            'id': store.new_id(), 'site_id': site_id, 'visit_id': visit['id'],
            'label': label, 'quantity': payload.quantity, 'unit': payload.unit,
            'source': source, 'recorded_by': reviewer, 'recorded_at': store.timestamp(),
        }
        db.execute('''INSERT INTO measurements
            (id,site_id,visit_id,label,quantity,unit,source,recorded_by,recorded_at)
            VALUES (:id,:site_id,:visit_id,:label,:quantity,:unit,:source,:recorded_by,:recorded_at)''',
            measurement)
    return measurement


@router.get('/sites/{site_id}/measurements')
def list_measurements(site_id: str):
    with store.connection() as db:
        require_site(db, site_id)
        return store.rows(db, '''SELECT * FROM measurements WHERE site_id=?
            ORDER BY recorded_at,id''', (site_id,))


@router.get('/observations/{observation_id}')
def get_observation(observation_id: str):
    with store.connection() as db:
        observation = require_observation(db, observation_id)
        observation['revisions'] = store.rows(
            db, 'SELECT * FROM observation_revisions WHERE observation_id=? ORDER BY id',
            (observation_id,))
        return observation


@router.patch('/observations/{observation_id}')
def edit_observation(observation_id: str, payload: EditInput,
                     reviewer: str = Depends(require_reviewer)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        observation = require_observation(db, observation_id)
        if payload.expected_version != observation['version']:
            raise HTTPException(409, 'Observation changed; reload before editing')
        if payload.site_id and payload.site_id != observation['site_id']:
            raise HTTPException(422, 'Cannot change the site of an observation')
        before_id = payload.before_asset_id or observation['before_asset_id']
        after_id = payload.after_asset_id or observation['after_asset_id']
        validate_pair(
            db,
            before_id,
            after_id,
            site_id=observation['site_id'],
            before_visit_id=payload.before_visit_id,
            after_visit_id=payload.after_visit_id,
        )
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
            reviewed_by=NULL,reviewed_at=NULL,updated_at=?,version=version+1 WHERE id=?''',
            (before_id, after_id, None if evidence_changed else observation['ai_draft'],
             text, 'Evidence changed; review the new pair manually.' if evidence_changed
             else observation['reliability_reason'],
             store.timestamp(), observation_id))
        updated = require_observation(db, observation_id)
        store.revision(db, updated, 'edited', reviewer, text)
        return updated


@router.post('/observations/{observation_id}/review')
def review_observation(observation_id: str, payload: ReviewInput,
                       reviewer: str = Depends(require_reviewer)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        observation = require_observation(db, observation_id)
        if payload.expected_version != observation['version']:
            raise HTTPException(409, 'Observation changed; reload before reviewing')
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
            reviewed_by=?,reviewed_at=?,updated_at=?,version=version+1 WHERE id=?''',
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
          AND b.permission_status='granted' AND a.permission_status='granted'
        ORDER BY o.reviewed_at,o.id''', (site_id,))


@router.get('/sites/{site_id}/report')
def export_report(site_id: str, format: Literal['json','markdown'] = Query(default='json')):
    with store.connection() as db:
        site = require_site(db, site_id)
        observations = report_rows(db, site_id)
        measurements = store.rows(db, '''SELECT m.*,v.visited_on FROM measurements m
            JOIN visits v ON v.id=m.visit_id WHERE m.site_id=? ORDER BY m.recorded_at,m.id''',
            (site_id,))
    demo_only = site_id == 'demo-riverbank' or any(
        item['before_url'].startswith('/demo/sample-media/') or
        item['after_url'].startswith('/demo/sample-media/') for item in observations)
    if format == 'json':
        return {'site': site, 'generated_at': store.timestamp(), 'observations': observations,
                'recorded_measurements': measurements, 'synthetic_demo': demo_only}
    lines = [f'# {escape(site["name"])} — Setowa Evidence Report', '',
             'Only reviewed observations and explicitly recorded measurements are included.', '']
    if demo_only:
        lines += ['**SYNTHETIC DEMO — NOT FIELD EVIDENCE**', '']
    for item in observations:
        lines += [f'## Observation {item["id"]}', '', escape(item['approved_text']), '',
                  f'Before ({item["before_date"]}): {item["before_url"]}',
                  f'After ({item["after_date"]}): {item["after_url"]}',
                  f'Approved by {escape(item["reviewed_by"])} at {item["reviewed_at"]}', '']
    if measurements:
        lines += ['## Recorded measurements', '']
        for item in measurements:
            lines += [f'- {escape(item["label"])}: {item["quantity"]:g} {item["unit"]} '
                      f'({item["visited_on"]}; source: {escape(item["source"])}; '
                      f'recorded by {escape(item["recorded_by"])})']
        lines.append('')
    else:
        lines += ['No measurements were recorded.', '']
    return Response('\n'.join(lines), media_type='text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="setowa-{site_id}-report.md"'})
