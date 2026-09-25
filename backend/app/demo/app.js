(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = {
    session: null,
    integrations: null,
    sites: [],
    site: '',
    siteRecord: null,
    visits: [],
    observations: [],
    measurements: [],
    report: null,
    nextTab: 'visits',
    comparisons: {},
    stageMode: 'slider', // 'slider' | 'side-by-side'
  };
  const tabs = new Set(['overview', 'visits', 'compare', 'review', 'report']);

  function element(tag, className = '', text = '') {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text) item.textContent = text;
    return item;
  }

  function notice(message, isError = false) {
    const item = $('notice');
    item.textContent = message;
    item.classList.toggle('error', isError);
    item.hidden = !message;
  }

  function sanitizeErrorMessage(msg) {
    if (!msg) return 'The request could not be completed.';
    if (msg.includes('503:')) return 'Cloudinary or service is not configured. Please check provider settings.';
    if (msg.includes('502:')) return 'Media/AI provider communication error. No partial data was recorded.';
    if (msg.includes('409:')) return 'Observation version conflict. The record was modified and has been refreshed.';
    if (msg.includes('422:')) {
      const match = msg.match(/422:\s*(.*)/);
      return match ? match[1] : 'Validation failed. Check visit dates, site consistency, and permissions.';
    }
    return msg;
  }

  function formatReason(reason) {
    if (!reason) return 'Viewpoint, framing, or evidence quality is insufficient for a reliable comparison.';
    const map = {
      camera_angle_mismatch: 'Camera angle mismatch — Before and after viewpoints differ significantly.',
      lighting_difference: 'Lighting difference — Substantial lighting or shadow disparity.',
      partial_occlusion: 'Partial occlusion — Key portions of the cleanup area are obstructed.',
      insufficient_visual_overlap: 'Insufficient visual overlap — The two images do not share enough common reference landmarks.',
      poor_image_quality: 'Poor image quality — Resolution, blur, or compression prevents reliable visual inspection.',
      relevant_area_not_visible: 'Relevant area not visible — The target cleanup zone is outside the camera frame.',
      incompatible_framing: 'Incompatible framing — The framing or zoom level prevents reliable comparison.',
      synthetic_walkthrough_evidence: 'Synthetic walkthrough evidence — Demo media for local walkthrough only.',
      provider_unavailable: 'AI comparison provider not configured (GEMINI_API_KEY required).',
      provider_error: 'AI provider error or timeout during comparison.',
      unverified_quantitative_claim: 'Unverified numerical impact claim was rejected.',
    };
    return map[reason] || reason;
  }

  function openLightbox(src, title, details, badgeText = 'Granted', badgeClass = 'granted') {
    const modal = $('lightbox-modal');
    $('lightbox-img').src = src;
    $('lightbox-title').textContent = title || 'Field Evidence';
    $('lightbox-details').textContent = details || '';
    const badge = $('lightbox-badge');
    badge.textContent = badgeText;
    badge.className = `badge ${badgeClass}`;
    if (typeof modal.showModal === 'function') modal.showModal();
    else modal.setAttribute('open', '');
  }

  function closeLightbox() {
    const modal = $('lightbox-modal');
    if (typeof modal.close === 'function') modal.close();
    else modal.removeAttribute('open');
    $('lightbox-img').removeAttribute('src');
  }

  async function request(path, options = {}) {
    const headers = { ...options.headers };
    if (options.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(`/api/v1${path}`, { ...options, headers, cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === 'string' ? body.detail : 'Request could not be completed';
      } catch (_) { /* Preserve the HTTP status text. */ }
      throw new Error(`${response.status}: ${detail}`);
    }
    return response.headers.get('content-type')?.includes('application/json') ? response.json() : response;
  }

  async function run(action) {
    try { await action(); }
    catch (error) {
      notice(sanitizeErrorMessage(error.message || 'The request could not be completed.'), true);
      if (error.message?.startsWith('409:') && state.site) await refreshSite();
    }
  }

  function renderStatus(status) {
    state.integrations = status;
    for (const [name, ready, message] of [
      ['cloudinary', status.cloudinary_ready, status.cloudinary_ready ? 'Ready for uploads' : 'Add keys for uploads'],
      ['gemini', status.gemini_ready, status.gemini_ready ? 'Key present' : 'Optional for AI comparison'],
      ['reviewer', status.reviewer_ready, status.reviewer_ready ? 'Local access ready' : 'Run ./run_local.sh'],
    ]) {
      $(`${name}-dot`).classList.toggle('ready', ready);
      $(`${name}-status`).textContent = message;
    }
    $('session-label').textContent = status.reviewer ? `${status.reviewer} / local` : 'Local workspace';
    $('integration-status').textContent = `Cloudinary ${status.cloudinary_ready ? 'ready' : 'not configured'} · Gemini ${status.gemini_ready ? 'ready' : 'optional'}`;
    $('nav-projects').hidden = !status.reviewer;
  }

  async function getStatus() {
    const status = await request('/local/status');
    renderStatus(status);
    state.session = status.reviewer;
    return status;
  }

  async function connectLocal() {
    if (state.session) return;
    const session = await request('/local/session', { method: 'POST' });
    state.session = session.reviewer;
    await getStatus();
  }

  function showPage(name) {
    for (const page of ['setup', 'projects', 'project']) $(`${page}-page`).hidden = page !== name;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function selectTab(name) {
    const active = tabs.has(name) ? name : 'overview';
    for (const tab of tabs) $(`tab-${tab}`).hidden = tab !== active;
    document.querySelectorAll('.tab-button').forEach(button => {
      const selected = button.dataset.tab === active;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-current', selected ? 'page' : 'false');
    });
  }

  function projectHash(siteId, tab = 'overview') {
    return `#project/${encodeURIComponent(siteId)}/${tab}`;
  }

  function goToTab(tab) { location.hash = projectHash(state.site, tab); }

  async function loadProjects() {
    state.sites = await request('/sites');
    const list = $('project-list');
    list.replaceChildren();
    if (!state.sites.length) list.append(element('p', 'empty-state', 'No projects yet. Create a site to begin.'));
    const projects = await Promise.all(state.sites.map(async site => {
      const [visits, observations] = await Promise.all([
        request(`/sites/${encodeURIComponent(site.id)}/visits`),
        request(`/sites/${encodeURIComponent(site.id)}/observations`),
      ]);
      return { site, visits, observations };
    }));
    projects.sort((a, b) => (a.site.id === 'demo-riverbank' ? -1 : b.site.id === 'demo-riverbank' ? 1 : a.site.name.localeCompare(b.site.name)));
    for (const { site, visits, observations } of projects) {
      const sample = site.id === 'demo-riverbank';
      const card = element('article', `project-card ${sample ? 'sample-card' : ''}`);
      if (sample) {
        const photo = element('div', 'project-card-photo');
        const image = element('img');
        image.src = '/demo/sample-media/river-after-synthetic.png';
        image.alt = 'Synthetic riverbank sample';
        photo.append(image, element('span', '', 'GUIDED SAMPLE / SYNTHETIC'));
        card.append(photo);
      }
      const body = element('div', 'project-card-body');
      body.append(element('p', 'kicker', sample ? 'START HERE' : 'CLEANUP PROJECT'),
        element('h2', '', site.name),
        element('p', 'project-description', site.description || 'A new site ready for visits and evidence.'));
      const meta = element('div', 'project-meta');
      meta.append(element('span', '', site.location || site.id),
        element('span', '', `${visits.length} visit${visits.length === 1 ? '' : 's'} · ${observations.length} observation${observations.length === 1 ? '' : 's'}`));
      const link = element('a', 'button primary', sample ? 'Try guided demo →' : 'Open project →');
      link.href = projectHash(site.id);
      body.append(meta, link);
      card.append(body);
      list.append(card);
    }
  }

  async function refreshSite() {
    if (!state.site) return;
    const id = encodeURIComponent(state.site);
    const [visits, observations, measurements, report] = await Promise.all([
      request(`/sites/${id}/visits`), request(`/sites/${id}/observations`),
      request(`/sites/${id}/measurements`), request(`/sites/${id}/report`),
    ]);
    state.visits = visits;
    state.observations = observations;
    state.measurements = measurements;
    state.report = report;
    $('visit-count').textContent = visits.length;
    $('photo-count').textContent = visits.reduce((sum, visit) => sum + visit.assets.length, 0);
    $('observation-count').textContent = observations.length;
    $('approved-count').textContent = report.observations.length;
    $('synthetic-banner').hidden = !report.synthetic_demo;
    renderVisits();
    renderPairChoices();
    renderObservations();
    renderMeasurements();
    renderNextStep();
    renderReportPreview();
  }

  function renderNextStep() {
    const photos = state.visits.reduce((sum, visit) => sum + visit.assets.length, 0);
    const unreviewed = state.observations.some(item => item.review_status === 'pending');
    let title, copy, tab;
    if (unreviewed) {
      [title, copy, tab] = ['Review the observation', 'Inspect the two photographs, edit the text if needed, then approve or reject it.', 'review'];
    } else if (state.report.observations.length) {
      [title, copy, tab] = ['Export your report', 'The approved observation is ready with its evidence links.', 'report'];
    } else if (state.visits.length < 2 || photos < 2) {
      [title, copy, tab] = ['Record your visits', 'Add two dated visits with a photograph from each visit.', 'visits'];
    } else {
      [title, copy, tab] = ['Compare your photographs', 'Choose a before and an after image of the same location.', 'compare'];
    }
    state.nextTab = tab;
    $('next-step-title').textContent = title;
    $('next-step-copy').textContent = copy;
  }

  async function openProject(id, tab) {
    if (!state.sites.length) await loadProjects();
    let site = state.sites.find(item => item.id === id);
    if (!site) {
      await loadProjects();
      site = state.sites.find(item => item.id === id);
    }
    if (!site) { location.hash = '#projects'; throw new Error('Project not found.'); }
    state.site = id;
    state.siteRecord = site;
    $('project-title').textContent = site.name;
    $('project-subtitle').textContent = site.location || 'Location not yet recorded';
    $('overview-description').textContent = site.description || 'Add a description to explain what this site is documenting.';
    $('project-badge').textContent = id === 'demo-riverbank' ? 'SYNTHETIC SAMPLE' : 'EVIDENCE RECORD';
    for (const key of ['name', 'location', 'description']) $('site-edit-form').elements.namedItem(key).value = site[key] || '';
    await refreshSite();
    selectTab(tab);
    showPage('project');
  }

  async function route() {
    const parts = location.hash.replace(/^#/, '').split('/');
    if (!parts[0] || parts[0] === 'setup') { showPage('setup'); return; }
    await connectLocal();
    if (parts[0] === 'projects') { await loadProjects(); showPage('projects'); return; }
    if (parts[0] === 'project' && parts[1]) {
      await openProject(decodeURIComponent(parts[1]), parts[2]); return;
    }
    location.hash = '#setup';
  }

  function renderVisits() {
    const list = $('visits');
    list.replaceChildren();
    const filter = $('media-filter').value.trim().toLowerCase();
    const visible = state.visits.filter(visit => !filter || visit.label.toLowerCase().includes(filter) ||
      visit.visited_on.includes(filter) || visit.assets.some(asset => asset.source.toLowerCase().includes(filter)));
    list.classList.toggle('empty', !visible.length);
    if (!visible.length) { list.textContent = filter ? 'No matching visits or photo sources.' : 'No visits yet. Add the first one above.'; return; }
    for (const visit of visible) {
      const card = element('article', 'visit-card');
      card.append(element('p', 'kicker', visit.visited_on), element('h3', '', visit.label));
      const thumbnails = element('div', 'thumb-grid');
      for (const asset of visit.assets.filter(asset => !filter || visit.label.toLowerCase().includes(filter) ||
        visit.visited_on.includes(filter) || asset.source.toLowerCase().includes(filter))) {
        const figure = element('figure', 'visit-asset-figure');
        const imgWrap = element('div', 'provenance-img-wrap');
        const image = element('img');
        image.src = asset.secure_url;
        image.alt = `${visit.label}: ${asset.source}`;
        image.loading = 'lazy';
        const zoomBtn = element('button', 'zoom-btn', '⤢ Enlarge');
        zoomBtn.type = 'button';
        zoomBtn.addEventListener('click', () => {
          openLightbox(
            asset.secure_url,
            `${visit.label} (${visit.visited_on})`,
            `Source: ${asset.source} · Format: ${asset.width}x${asset.height} ${asset.format.toUpperCase()} · ID: ${asset.asset_id}`,
            asset.permission_status.replace('_', ' ').toUpperCase(),
            asset.permission_status
          );
        });
        imgWrap.append(image, zoomBtn);

        const permStatus = asset.permission_status || 'granted';
        const figcaption = element('figcaption', '', `${asset.source} · `);
        const permBadge = element('span', `badge ${permStatus}`, permStatus.replace('_', ' '));
        const cloudBadge = element('span', 'cloudinary-tag', asset.secure_url.includes('cloudinary.com') ? '☁ Cloudinary' : 'Local sample');
        figcaption.append(permBadge, element('br'), cloudBadge);

        figure.append(imgWrap, figcaption);
        thumbnails.append(figure);
      }
      if (!visit.assets.length) thumbnails.append(element('p', 'empty-state', 'No photos yet.'));
      card.append(thumbnails);

      const form = element('form', 'upload-form');
      const sourceLabel = element('label', '', 'Source / consent record');
      const source = element('input');
      source.name = 'source';
      source.required = true;
      source.maxLength = 200;
      source.placeholder = 'e.g. Ranger team photo / signed consent on file';
      sourceLabel.append(source);

      const permLabel = element('label', '', 'Permission status');
      const permSelect = element('select');
      permSelect.name = 'permission_status';
      permSelect.add(new Option('Granted (Consent on file)', 'granted'));
      permSelect.add(new Option('Pending verification', 'pending_verification'));
      permSelect.add(new Option('Revoked', 'revoked'));
      permLabel.append(permSelect);

      const fileLabel = element('label', '', 'Upload a photo (JPEG, PNG, WebP)');
      const file = element('input');
      file.type = 'file';
      file.name = 'file';
      file.accept = 'image/jpeg,image/png,image/webp';
      file.required = true;
      fileLabel.append(file);

      const button = element('button', 'button secondary', 'Upload to Cloudinary');
      form.append(sourceLabel, permLabel, fileLabel, button);
      form.addEventListener('submit', event => {
        event.preventDefault();
        run(async () => {
          button.disabled = true;
          try {
            const data = new FormData(form);
            data.set('project_id', state.site);
            data.set('visit_id', visit.id);
            data.set('visit_date', visit.visited_on);
            await request('/media/images', { method: 'POST', body: data });
            notice('Photo uploaded and verified.');
            await refreshSite();
          } finally { button.disabled = false; }
        });
      });
      card.append(form);
      list.append(card);
    }
  }

  function assetsForSite() {
    return state.visits.flatMap(visit => visit.assets.map(asset => ({ ...asset, visit })));
  }

  function renderPairChoices() {
    const assets = assetsForSite();
    for (const [id, before] of [['before-select', true], ['after-select', false]]) {
      const select = $(id);
      const previous = select.value;
      select.replaceChildren(new Option('Choose a photo', ''));
      for (const asset of assets) {
        const permNote = asset.permission_status !== 'granted' ? ` [${asset.permission_status}]` : '';
        select.add(new Option(`${asset.visit.visited_on} · ${asset.visit.label} · ${asset.source}${permNote}`, asset.asset_id));
      }
      if (assets.some(asset => asset.asset_id === previous)) select.value = previous;
      else if (assets.length) select.value = (before ? assets[0] : assets[assets.length - 1]).asset_id;
    }
    updatePreview();
  }

  function updatePreview() {
    const assets = assetsForSite();
    const before = assets.find(asset => asset.asset_id === $('before-select').value);
    const after = assets.find(asset => asset.asset_id === $('after-select').value);

    // Update Before Card
    const beforeCard = $('before-card');
    if (before) {
      beforeCard.hidden = false;
      $('before-preview').src = before.secure_url;
      $('before-perm-badge').textContent = (before.permission_status || 'granted').replace('_', ' ');
      $('before-perm-badge').className = `badge ${before.permission_status || 'granted'}`;
      $('before-visit-info').textContent = `${before.visit.visited_on} — ${before.visit.label}`;
      $('before-source-info').textContent = `Source: ${before.source} · ID: ${before.asset_id.slice(0, 10)}…`;
    } else {
      beforeCard.hidden = true;
    }

    // Update After Card
    const afterCard = $('after-card');
    if (after) {
      afterCard.hidden = false;
      $('after-preview').src = after.secure_url;
      $('after-perm-badge').textContent = (after.permission_status || 'granted').replace('_', ' ');
      $('after-perm-badge').className = `badge ${after.permission_status || 'granted'}`;
      $('after-visit-info').textContent = `${after.visit.visited_on} — ${after.visit.label}`;
      $('after-source-info').textContent = `Source: ${after.source} · ID: ${after.asset_id.slice(0, 10)}…`;
    } else {
      afterCard.hidden = true;
    }

    // Validation Invariants Check
    const warning = $('pair-validation-warning');
    let validationError = null;
    if (before && after) {
      if (before.asset_id === after.asset_id) {
        validationError = 'Select two different photographs for comparison.';
      } else if (before.visit.visited_on >= after.visit.visited_on) {
        validationError = `Chronological order violation: Before visit (${before.visit.visited_on}) must precede After visit (${after.visit.visited_on}).`;
      } else if (before.permission_status !== 'granted') {
        validationError = `Permission restriction: Before photo permission is '${before.permission_status}'. Only 'granted' evidence can be compared.`;
      } else if (after.permission_status !== 'granted') {
        validationError = `Permission restriction: After photo permission is '${after.permission_status}'. Only 'granted' evidence can be compared.`;
      }
    }

    if (validationError) {
      warning.textContent = `⚠ Invariant check: ${validationError}`;
      warning.hidden = false;
      $('compare').disabled = true;
    } else {
      warning.hidden = true;
      $('compare').disabled = !before || !after;
    }

    // Comparison Stage (slider)
    const canCompare = before && after && !validationError;
    $('comparison-stage').hidden = !canCompare || state.stageMode !== 'slider';
    if (before && after) {
      $('comparison-before').src = before.secure_url;
      $('comparison-after').src = after.secure_url;
      updateComparisonRange();
    }
  }

  function updateComparisonRange() {
    $('comparison-before').style.clipPath = `inset(0 ${100 - Number($('comparison-range').value)}% 0 0)`;
  }

  function renderObservations() {
    const list = $('observations');
    list.replaceChildren();
    list.classList.toggle('empty', !state.observations.length);
    if (!state.observations.length) {
      list.textContent = 'No observations yet. Compare two dated photographs on the Compare tab to propose an observation.';
      return;
    }

    for (const observation of [...state.observations].reverse()) {
      const isApproved = observation.review_status === 'approved';
      const isRejected = observation.review_status === 'rejected';
      const isPending = observation.review_status === 'pending';

      const card = element('article', `observation-card ${isApproved ? 'verified' : isRejected ? 'rejected' : 'ai-proposal'}`);

      // Top Status Banner
      const banner = element('div', 'card-banner');
      if (isApproved) {
        banner.append(
          element('span', 'banner-badge', '✓ HUMAN VERIFIED RECORD'),
          element('span', '', 'INCLUDED IN OFFICIAL REPORT'),
          element('span', '', `Revision ${observation.version}`)
        );
      } else if (isRejected) {
        banner.append(
          element('span', 'banner-badge', '✕ REJECTED BY REVIEWER'),
          element('span', '', 'EXCLUDED FROM REPORT'),
          element('span', '', `Revision ${observation.version}`)
        );
      } else {
        banner.append(
          element('span', 'banner-badge', '🤖 AI PROPOSAL'),
          element('span', '', '⚠ HUMAN VERIFICATION REQUIRED'),
          element('span', '', 'NOT IN OFFICIAL REPORT')
        );
      }
      card.append(banner);

      // Title & Observation ID
      card.append(element('h3', '', observation.id === 'synthetic-river-observation' ?
        'Riverbank Visual Observation' : `Observation ${observation.id.slice(0, 8)}`));

      // Side-by-side Evidence provenance thumbnails
      const evidence = element('div', 'evidence-grid');
      for (const [caption, id] of [['BEFORE', observation.before_asset_id], ['AFTER', observation.after_asset_id]]) {
        const asset = assetsForSite().find(item => item.asset_id === id);
        if (!asset) continue;
        const figure = element('figure');
        const imgWrap = element('div', 'provenance-img-wrap');
        imgWrap.style.width = '100%';
        imgWrap.style.height = '180px';
        const image = element('img');
        image.src = asset.secure_url;
        image.alt = `${caption}: ${asset.source}`;
        image.loading = 'lazy';
        const zoomBtn = element('button', 'zoom-btn', '⤢ Enlarge');
        zoomBtn.type = 'button';
        zoomBtn.addEventListener('click', () => {
          openLightbox(
            asset.secure_url,
            `${caption} (${asset.visit.visited_on})`,
            `Visit: ${asset.visit.label} · Source: ${asset.source} · ID: ${asset.asset_id}`,
            (asset.permission_status || 'granted').toUpperCase(),
            asset.permission_status || 'granted'
          );
        });
        imgWrap.append(image, zoomBtn);
        figure.append(
          imgWrap,
          element('figcaption', '', `${caption} · ${asset.visit.visited_on} · ${asset.source}`)
        );
        evidence.append(figure);
      }
      card.append(evidence);

      // Cached or Synthesized Structured AI Result
      const comp = state.comparisons[observation.id] || {};
      const status = comp.status || (
        observation.reliability_reason && !observation.ai_draft ?
          (observation.reliability_reason.includes('poor_image_quality') ? 'insufficient_evidence' : 'uncertain') :
          'changed'
      );
      const confidence = comp.confidence !== undefined ? comp.confidence : (status === 'changed' ? 0.85 : 0.20);
      const isUncertain = status === 'uncertain' || status === 'insufficient_evidence';

      // Structured AI Box (rendered for all pending observations)
      if (isPending) {
        const aiBox = element('div', 'structured-ai-box');
        const aiHeader = element('div', 'structured-header');

        const statusLabel = status.replace('_', ' ').toUpperCase();
        const pillClass = status === 'insufficient_evidence' ? 'insufficient' : status;
        const pill = element('span', `status-pill ${pillClass}`, `● ${statusLabel}`);

        const gauge = element('div', 'confidence-gauge');
        gauge.append(
          element('strong', '', `MODEL CONFIDENCE: ${confidence.toFixed(2)}`),
          element('small', '', 'Model certainty score — NOT factual accuracy')
        );
        aiHeader.append(pill, gauge);
        aiBox.append(aiHeader);

        // AI Proposal Summary (if provided)
        if (observation.ai_draft) {
          aiBox.append(
            element('p', 'kicker', 'AI SUGGESTED OBSERVATION'),
            element('blockquote', 'ai-quote', `“${observation.ai_draft}”`)
          );
        }

        // Structured Visible Changes List
        if (comp.changes && comp.changes.length) {
          aiBox.append(element('p', 'kicker', 'STRUCTURED VISIBLE CHANGES'));
          const changesList = element('ul', 'changes-list');
          for (const change of comp.changes) {
            const li = element('li');
            li.append(
              element('span', 'change-badge', change.type || 'visual_change'),
              element('span', '', change.description + (change.evidence ? ` (Evidence: ${change.evidence})` : ''))
            );
            changesList.append(li);
          }
          aiBox.append(changesList);
        }

        // Prominent Uncertainty UX
        if (isUncertain) {
          const reasonText = comp.uncertainty_reason || observation.reliability_reason || 'insufficient_visual_overlap';
          const callout = element('div', `uncertainty-callout ${status === 'insufficient_evidence' ? 'danger' : 'warning'}`);
          if (status === 'insufficient_evidence') {
            callout.append(
              element('strong', '', '🚫 Insufficient evidence for a reliable comparison.'),
              element('p', '', `Reason: ${formatReason(reasonText)}`)
            );
          } else {
            callout.append(
              element('strong', '', '⚠️ AI could not determine the outcome with sufficient confidence.'),
              element('p', '', `Reason: ${formatReason(reasonText)}`)
            );
          }
          aiBox.append(callout);
        }

        // Evidence Notes
        if (comp.evidence_notes) {
          aiBox.append(
            element('div', 'evidence-notes-box', `Supporting visual notes: ${comp.evidence_notes}`)
          );
        }

        card.append(aiBox);
      }

      // If Approved: Display Verified Record Box
      if (isApproved) {
        const verifiedDisplay = element('div', 'verified-display');
        verifiedDisplay.append(
          element('h4', '', 'OFFICIAL VERIFIED OBSERVATION'),
          element('p', 'verified-text', observation.approved_text || observation.working_text),
          element('p', 'verification-trail',
            `✓ Verified by ${observation.reviewed_by || 'Human Reviewer'} on ${observation.reviewed_at ? observation.reviewed_at.slice(0, 16).replace('T', ' ') : 'recently'} UTC`
          ),
          element('p', 'invalidation-note',
            'ℹ Any subsequent edit to this text or change of paired evidence will immediately invalidate this approval.'
          )
        );
        card.append(verifiedDisplay);
      }

      // Review Actions Section
      const reviewBox = element('div', 'human-review-box');
      if (isPending) {
        reviewBox.append(
          element('p', 'review-guidance',
            '⚠ AI suggestion — A human reviewer must inspect the evidence, confirm or edit the observation, and make the final approval decision.'
          )
        );
      }

      const label = element('label', '', isApproved ? 'Revise observation (Invalidates current approval):' : 'Reviewer written observation:');
      const field = element('textarea');
      field.value = observation.working_text || observation.ai_draft || '';
      field.maxLength = 600;
      field.rows = 3;
      field.placeholder = 'Describe only what you can support from the paired photos.';
      label.append(field);
      reviewBox.append(label);

      const actions = element('div', 'actions');
      const save = element('button', 'button secondary', isApproved ? 'Save revised text' : 'Save draft');
      const approve = element('button', 'button primary', '✓ Approve observation');
      const reject = element('button', 'button quiet', '✕ Reject');

      const updateSave = () => {
        save.disabled = field.value.trim() === (observation.working_text || '').trim();
      };
      updateSave();
      field.addEventListener('input', updateSave);

      const act = (method, payload) => run(async () => {
        const buttons = [save, approve, reject];
        buttons.forEach(button => { button.disabled = true; });
        try {
          await request(`/observations/${observation.id}${method === 'POST' ? '/review' : ''}`,
            { method, json: { expected_version: observation.version, ...payload } });
          notice(
            method === 'PATCH' ? 'Edit saved. Approval invalidated; observation returned to pending.' :
            payload.decision === 'approve' ? 'Observation approved and verified. Now included in official report.' :
            'Observation rejected and excluded from report.'
          );
          await refreshSite();
        } finally { buttons.forEach(button => { button.disabled = false; }); }
      });

      save.addEventListener('click', () => act('PATCH', { working_text: field.value }));
      approve.addEventListener('click', () => act('POST', { decision: 'approve', text: field.value }));
      reject.addEventListener('click', () => act('POST', { decision: 'reject' }));

      if (isApproved) {
        approve.disabled = true;
        reject.disabled = true;
      }

      actions.append(approve, save, reject);
      reviewBox.append(actions);
      card.append(reviewBox);

      list.append(card);
    }
  }

  function renderMeasurements() {
    const select = $('measurement-visit');
    select.replaceChildren(new Option('Choose a visit', ''));
    for (const visit of state.visits) select.add(new Option(`${visit.visited_on} · ${visit.label}`, visit.id));
    const list = $('measurements');
    list.replaceChildren();
    if (!state.measurements.length) { list.textContent = 'No measurements recorded.'; return; }
    for (const item of state.measurements) {
      const row = element('div', 'measurement-item');
      row.append(element('strong', '', `${item.quantity} ${item.unit} · ${item.label}`),
        element('span', '', `Source: ${item.source} · recorded by ${item.recorded_by}`));
      list.append(row);
    }
  }

  function renderReportPreview() {
    const report = state.report;
    const approved = report ? report.observations.length : 0;
    const measured = report ? report.recorded_measurements.length : 0;

    $('report-count').textContent = `${approved} approved observation${approved === 1 ? '' : 's'} · ${measured} recorded measurement${measured === 1 ? '' : 's'}`;
    $('export').disabled = approved + measured === 0;

    const preview = $('report-live-preview');
    preview.replaceChildren();

    if (!report) return;

    preview.append(
      element('h3', '', `${state.siteRecord ? state.siteRecord.name : state.site} — Setowa Evidence Report`),
      element('p', 'report-meta-sub', `Generated: ${report.generated_at ? report.generated_at.slice(0, 19).replace('T', ' ') : 'Live'} UTC · Location: ${state.siteRecord?.location || 'Unspecified'}`)
    );

    if (report.synthetic_demo) {
      const demoAlert = element('div', 'synthetic-banner');
      demoAlert.append(
        element('strong', '', '⚠️ SYNTHETIC DEMO — NOT FIELD EVIDENCE'),
        element('span', '', 'This report contains synthetic media used for demonstration only.')
      );
      preview.append(demoAlert);
    }

    // Section 1: Observations
    const obsSection = element('section', 'report-observations-section');
    obsSection.append(element('h4', 'kicker', '01 / REVIEWED & APPROVED OBSERVATIONS'));
    if (!report.observations.length) {
      obsSection.append(
        element('p', 'empty-state', 'No approved observations. Unapproved AI suggestions remain in pending status and are strictly excluded from this report.')
      );
    } else {
      for (const item of report.observations) {
        const obsCard = element('article', 'report-obs-item');
        obsCard.append(
          element('h4', '', `Verified Finding: ${item.approved_text}`),
          element('p', 'meta', `Reviewed by ${item.reviewed_by} · Approved at ${item.reviewed_at ? item.reviewed_at.slice(0, 16).replace('T', ' ') : ''} UTC`)
        );
        const thumbs = element('div', 'report-evidence-thumbs');
        for (const [label, url, date, id] of [
          ['Before Visit', item.before_url, item.before_date, item.before_asset_id],
          ['After Visit', item.after_url, item.after_date, item.after_asset_id]
        ]) {
          const thumbCard = element('figure', 'report-thumb-card');
          const img = element('img');
          img.src = url;
          img.alt = label;
          thumbCard.append(img, element('figcaption', '', `${label} (${date})`));
          thumbs.append(thumbCard);
        }
        obsCard.append(thumbs);
        obsSection.append(obsCard);
      }
    }
    preview.append(obsSection);

    // Section 2: Measurements
    const measSection = element('section', 'report-measurements-section');
    measSection.append(element('h4', 'kicker', '02 / RECORDED QUANTITATIVE MEASUREMENTS'));
    if (!report.recorded_measurements.length) {
      measSection.append(element('p', 'empty-state', 'No quantitative measurements explicitly recorded for this site.'));
    } else {
      for (const m of report.recorded_measurements) {
        const item = element('div', 'measurement-item');
        item.append(
          element('strong', '', `${m.quantity} ${m.unit} — ${m.label}`),
          element('span', '', `Source: ${m.source} · Recorded on ${m.recorded_at ? m.recorded_at.slice(0, 10) : ''} by ${m.recorded_by}`)
        );
        measSection.append(item);
      }
    }
    preview.append(measSection);

    // JSON view update
    $('report-json-view').textContent = JSON.stringify(report, null, 2);
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    $('theme-toggle').textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
    $('theme-toggle').setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    localStorage.setItem('setowa-theme', theme);
  }

  // Event Listeners
  $('theme-toggle').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  applyTheme((localStorage.getItem('setowa-theme') || localStorage.getItem('lex-theme')) === 'dark' ? 'dark' : 'light');

  $('enter-workspace').addEventListener('click', () => run(async () => { await connectLocal(); location.hash = '#projects'; }));

  $('credential-form').addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    run(async () => {
      const values = Object.fromEntries(new FormData(form));
      const status = await request('/local/credentials', { method: 'PUT', json: {
        cloudinary: { cloud_name: values.cloud_name, api_key: values.cloudinary_api_key,
          api_secret: values.cloudinary_api_secret },
        gemini: { api_key: values.gemini_api_key },
      } });
      form.reset(); renderStatus(status);
      notice('Saved locally. The readiness indicators have been updated.');
    });
  });

  $('new-project-button').addEventListener('click', () => {
    $('new-project-panel').hidden = !$('new-project-panel').hidden;
    if (!$('new-project-panel').hidden) $('site-form').elements.namedItem('name').focus();
  });

  $('site-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form));
      await request('/sites', { method: 'POST', json: data });
      form.reset(); notice('Project created. Add its first visit.');
      await loadProjects(); location.hash = projectHash(data.id);
    });
  });

  $('site-edit-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const site = await request(`/sites/${encodeURIComponent(state.site)}`, {
        method: 'PATCH', json: Object.fromEntries(new FormData(form)),
      });
      state.siteRecord = site;
      state.sites = state.sites.map(item => item.id === site.id ? site : item);
      $('project-title').textContent = site.name;
      $('project-subtitle').textContent = site.location || 'Location not yet recorded';
      $('overview-description').textContent = site.description || 'Add a description to explain what this site is documenting.';
      notice('Project details saved.');
    });
  });

  document.querySelectorAll('.tab-button').forEach(button => button.addEventListener('click', () => goToTab(button.dataset.tab)));
  $('next-step-button').addEventListener('click', () => goToTab(state.nextTab));

  $('visit-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      await request(`/sites/${encodeURIComponent(state.site)}/visits`, {
        method: 'POST', json: Object.fromEntries(new FormData(form)),
      });
      form.reset(); await refreshSite(); notice('Visit recorded. Add a photo below.');
    });
  });

  $('media-filter').addEventListener('input', renderVisits);
  $('before-select').addEventListener('change', updatePreview);
  $('after-select').addEventListener('change', updatePreview);
  $('comparison-range').addEventListener('input', updateComparisonRange);

  $('toggle-stage-view').addEventListener('click', () => {
    state.stageMode = state.stageMode === 'slider' ? 'side-by-side' : 'slider';
    $('toggle-stage-view').textContent = state.stageMode === 'slider' ? 'Switch to Side-by-Side' : 'Switch to Reveal Slider';
    $('comparison-stage').hidden = state.stageMode !== 'slider';
  });

  // Lightbox bindings
  $('lightbox-close').addEventListener('click', closeLightbox);
  $('lightbox-modal').addEventListener('click', (e) => {
    if (e.target === $('lightbox-modal')) closeLightbox();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('lightbox-modal').hasAttribute('open')) closeLightbox();
  });

  document.querySelectorAll('.zoom-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetId = btn.dataset.target;
      const img = $(targetId);
      if (img && img.src) {
        openLightbox(img.src, 'Evidence Preview', 'Field photograph inspection');
      }
    });
  });

  $('compare').addEventListener('click', () => run(async () => {
    const before_asset_id = $('before-select').value;
    const after_asset_id = $('after-select').value;
    if (!before_asset_id || !after_asset_id) throw new Error('Choose two photographs first.');
    $('compare').disabled = true;
    try {
      const result = await request('/pairs', { method: 'POST', json: { before_asset_id, after_asset_id } });
      if (result.comparison) {
        state.comparisons[result.id] = result.comparison;
      }
      await refreshSite();
      const isUncertain = result.comparison?.status === 'uncertain' || result.comparison?.status === 'insufficient_evidence';
      notice(
        isUncertain ? `Comparison result: ${result.comparison.status.toUpperCase()} — Check reason on Review tab.` :
        'AI comparison completed. Review and approve the proposal below.',
        isUncertain
      );
      goToTab('review');
    } finally { $('compare').disabled = false; }
  }));

  $('measurement-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form)); data.quantity = Number(data.quantity);
      await request(`/sites/${encodeURIComponent(state.site)}/measurements`, { method: 'POST', json: data });
      form.reset(); await refreshSite(); notice('Measurement saved with its source.');
    });
  });

  $('export').addEventListener('click', () => run(async () => {
    const response = await request(`/sites/${encodeURIComponent(state.site)}/report?format=markdown`);
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = element('a'); link.href = url; link.download = `setowa-${state.site}-report.md`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice('Reviewed report downloaded.');
  }));

  $('toggle-json-report').addEventListener('click', () => {
    const view = $('report-json-view');
    view.hidden = !view.hidden;
    $('toggle-json-report').textContent = view.hidden ? 'View Raw JSON' : 'Hide Raw JSON';
  });

  window.addEventListener('hashchange', () => run(route));
  run(async () => { await getStatus(); await route(); });
})();
