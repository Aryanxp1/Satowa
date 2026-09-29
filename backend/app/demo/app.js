(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = {
    session: null,
    integrations: null,
    sites: [],
    projects: [],
    projectFilter: '',
    site: '',
    siteRecord: null,
    visits: [],
    observations: [],
    measurements: [],
    report: null,
    nextTab: 'visits',
    comparisons: {},
    stageMode: 'slider', // 'slider' | 'side-by-side'
    mediaItems: [],
    mediaIntelligence: {},
    skills: [],
    activeTestSkill: null,
    workflows: [],
    currentWorkflow: null,
    selectedNodeId: null,
    workflowExecution: null,
    impactStory: null,
  };
  const tabs = new Set(['overview', 'visits', 'media-library', 'skills', 'workflows', 'compare', 'review', 'report', 'impact', 'discovery', 'campaign', 'media', 'evidence']);


  function element(tag, className = '', text = '') {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text) item.textContent = text;
    return item;
  }

  let noticeTimer = null;
  function notice(message, type = 'info') {
    const item = $('notice');
    if (!item) return;
    if (noticeTimer) {
      clearTimeout(noticeTimer);
      noticeTimer = null;
    }
    if (!message) {
      item.hidden = true;
      item.replaceChildren();
      return;
    }

    const isError = type === true || type === 'error';
    const isSuccess = type === 'success';
    const isWarn = type === 'warn' || type === 'warning';

    item.className = `notice-banner ${isError ? 'error' : (isSuccess ? 'success' : (isWarn ? 'warn' : 'info'))}`;
    item.hidden = false;

    item.replaceChildren();
    const textSpan = element('span', 'notice-text', message);
    const closeBtn = element('button', 'notice-close-btn', '✕');
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', 'Dismiss notification');
    closeBtn.addEventListener('click', () => {
      item.hidden = true;
      item.replaceChildren();
    });
    item.append(textSpan, closeBtn);

    // Auto-dismiss success and info notices after 5 seconds, errors stay until dismissed or tab switch
    if (isSuccess || type === 'info') {
      noticeTimer = setTimeout(() => {
        item.hidden = true;
        item.replaceChildren();
      }, 5000);
    }
  }

  function sanitizeErrorMessage(msg) {
    if (!msg) return 'The request could not be completed.';
    if (msg.includes('503:')) return 'Service or credentials unavailable. Please check Cloudinary / Gemini configuration.';
    if (msg.includes('502:')) return 'Media or AI provider communication error. No partial or corrupt data was recorded.';
    if (msg.includes('409:')) return 'Observation version conflict. The record was modified and has been refreshed.';
    if (msg.includes('404:')) return 'Requested item not found. Please refresh the page.';
    if (msg.includes('403:')) return 'Action restricted or permission denied.';
    if (msg.includes('415:')) return 'Unsupported media format. Please upload JPEG, PNG, or WebP images.';
    if (msg.includes('413:')) return 'Upload or payload is too large.';
    if (msg.includes('422:')) {
      const match = msg.match(/422:\s*(.*)/);
      return match ? match[1].replace(/^[\[{].*[\]}]$/, 'Validation failed.') : 'Validation failed. Check visit dates, site consistency, and permissions.';
    }
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Network connection')) {
      return 'Network connection failed. Verify the Setowa backend server is running on http://127.0.0.1:8000.';
    }
    const cleaned = msg.replace(/^\d{3}:\s*/, '').split('\n')[0].trim();
    return cleaned || 'The request could not be completed.';
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

  function openLightbox(src, title, details, badgeText = 'Granted', badgeClass = 'granted', mediaType = 'image', videoUrl = null) {
    const modal = $('lightbox-modal');
    const img = $('lightbox-img');
    const video = $('lightbox-video');
    const typeBadge = $('lightbox-type-badge');

    if (mediaType === 'video' && videoUrl) {
      if (img) img.style.display = 'none';
      if (video) {
        video.style.display = 'block';
        video.src = videoUrl;
        if (src) video.poster = src;
      }
      if (typeBadge) {
        typeBadge.textContent = 'VIDEO';
        typeBadge.className = 'badge';
        typeBadge.style.display = 'inline-block';
      }
    } else {
      if (video) {
        video.pause();
        video.style.display = 'none';
        video.removeAttribute('src');
      }
      if (img) {
        img.style.display = 'block';
        img.src = src;
      }
      if (typeBadge) {
        typeBadge.textContent = 'IMAGE';
        typeBadge.className = 'badge';
        typeBadge.style.display = 'inline-block';
      }
    }

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
    const video = $('lightbox-video');
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.style.display = 'none';
    }
    const img = $('lightbox-img');
    if (img) img.removeAttribute('src');
    if (typeof modal.close === 'function') modal.close();
    else modal.removeAttribute('open');
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
    notice('');
    let active = name;
    if (active === 'media') active = 'media-library';
    if (active === 'evidence') active = 'review';
    if (!tabs.has(active)) active = 'media-library';
    state.activeTab = active;

    for (const tab of ['overview', 'visits', 'media-library', 'skills', 'workflows', 'compare', 'review', 'report', 'impact', 'discovery', 'campaign']) {
      const el = $(`tab-${tab}`);
      if (el) el.hidden = tab !== active;
    }

    let stage = active;
    if (active === 'media-library' || active === 'visits') stage = 'media-library';
    else if (['compare', 'review', 'report'].includes(active)) stage = 'review';

    document.querySelectorAll('.tab-button').forEach(button => {
      const btnTab = button.dataset.tab;
      const selected = btnTab === active || btnTab === stage;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-current', selected ? 'page' : 'false');
    });

    document.querySelectorAll('.evidence-subnav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.sub === active);
    });

    if (active === 'media-library') {
      renderMediaLibrary();
    } else if (active === 'skills') {
      loadSkills();
    } else if (active === 'workflows') {
      loadWorkflowsStudio();
    } else if (active === 'impact') {
      loadImpactStoryTab();
    } else if (active === 'campaign') {
      loadCampaignDrafts();
    } else if (active === 'compare') {
      renderPairChoices();
    } else if (active === 'review') {
      renderObservations();
    } else if (active === 'report') {
      renderReportPreview();
      renderMeasurements();
    }
  }

  function projectHash(siteId, tab = 'media-library') {
    return `#project/${encodeURIComponent(siteId)}/${tab}`;
  }

  function goToTab(tab) { location.hash = projectHash(state.site, tab); }

  async function loadProjects() {
    [state.projects, state.sites] = await Promise.all([request('/projects'), request('/sites')]);
    const projectFilter = $('library-project-select');
    projectFilter.replaceChildren(new Option('All projects', ''));
    for (const project of state.projects) {
      projectFilter.add(new Option(project.name, project.project_id));
    }
    if (state.projectFilter && !state.projects.some(p => p.project_id === state.projectFilter)) state.projectFilter = '';
    projectFilter.value = state.projectFilter;
    const parentSelect = $('site-project-select');
    parentSelect.replaceChildren();
    for (const project of state.projects) parentSelect.add(new Option(project.name, project.project_id));
    if (state.projectFilter) parentSelect.value = state.projectFilter;
    const list = $('project-list');
    list.replaceChildren();
    const visibleSites = state.sites.filter(site => !state.projectFilter || site.project_id === state.projectFilter);
    if (!visibleSites.length) list.append(element('p', 'empty-state', 'No sites in this project yet. Create a site to begin.'));
    const projects = await Promise.all(visibleSites.map(async site => {
      const [visits, observations] = await Promise.all([
        request(`/sites/${encodeURIComponent(site.id)}/visits`),
        request(`/sites/${encodeURIComponent(site.id)}/observations`),
      ]);
      return { site, visits, observations };
    }));
    projects.sort((a, b) => {
      if (a.site.id === 'site_nyali_creek') return -1;
      if (b.site.id === 'site_nyali_creek') return 1;
      if (a.site.id === 'demo-riverbank') return 1;
      if (b.site.id === 'demo-riverbank') return -1;
      return a.site.name.localeCompare(b.site.name);
    });

    for (const select of [$('topbar-site-select'), $('site-select')]) {
      if (!select) continue;
      select.replaceChildren();
      for (const site of state.sites) {
        const opt = document.createElement('option');
        opt.value = site.id;
        const tag = site.id === 'site_nyali_creek' ? ' (Unverified scenario)' : (site.id === 'demo-riverbank' ? ' (Synthetic sample)' : '');
        opt.textContent = `${site.name}${tag}`;
        select.appendChild(opt);
      }
      if (state.site) select.value = state.site;
    }

    for (const { site, visits, observations } of projects) {
      const isMombasa = site.id === 'site_nyali_creek';
      const sample = site.id === 'demo-riverbank';
      const card = element('article', `project-card ${isMombasa ? 'showcase-card' : ''} ${sample ? 'sample-card' : ''}`);
      if (sample) {
        const photo = element('div', 'project-card-photo');
        const image = element('img');
        image.src = '/demo/sample-media/river-after-synthetic.png';
        image.alt = 'Synthetic riverbank sample';
        photo.append(image, element('span', '', 'GUIDED SAMPLE / SYNTHETIC'));
        card.append(photo);
      }
      const body = element('div', 'project-card-body');
      const kickerText = isMombasa ? 'ILLUSTRATIVE SCENARIO · UNVERIFIED' : (sample ? 'GUIDED SAMPLE · SYNTHETIC' : 'CLEANUP SITE');
      const parent = state.projects.find(p => p.project_id === site.project_id);
      body.append(element('p', 'kicker', kickerText),
        element('h2', '', site.name),
        element('p', 'meta', `Project: ${parent ? parent.name : 'Unassigned'}`),
        element('p', 'project-description', site.description || 'A new site ready for visits and evidence.'));
      const meta = element('div', 'project-meta');
      meta.append(element('span', '', site.location || site.id),
        element('span', '', `${visits.length} visit${visits.length === 1 ? '' : 's'} · ${observations.length} observation${observations.length === 1 ? '' : 's'}`));
      const link = element('a', 'button primary', isMombasa ? 'Open scenario →' : (sample ? 'Try guided demo →' : 'Open site →'));
      link.href = projectHash(site.id, 'media-library');
      body.append(meta, link);
      card.append(body);
      list.append(card);
    }
  }

  async function refreshSite() {
    if (!state.site) return;
    const id = encodeURIComponent(state.site);
    const [visits, observations, measurements, report, mediaItems] = await Promise.all([
      request(`/sites/${id}/visits`),
      request(`/sites/${id}/observations`),
      request(`/sites/${id}/measurements`),
      request(`/sites/${id}/report`),
      request(`/media?site_id=${id}`).catch(() => []),
    ]);
    state.visits = visits;
    state.observations = observations;
    state.measurements = measurements;
    state.report = report;
    state.mediaItems = Array.isArray(mediaItems) ? mediaItems : [];
    $('visit-count').textContent = visits.length;
    $('photo-count').textContent = visits.reduce((sum, visit) => sum + visit.assets.length, 0);
    $('observation-count').textContent = observations.length;
    $('approved-count').textContent = report.observations.length;
    $('synthetic-banner').hidden = !report.synthetic_demo;
    renderVisits();
    renderMediaLibrary();
    if (state.mediaItems && state.mediaItems.length) {
      Promise.all(state.mediaItems.map(item =>
        request(`/media/${item.asset_id}/intelligence`)
          .then(intel => { if (intel) state.mediaIntelligence[item.asset_id] = intel; })
          .catch(() => {})
      )).then(() => { renderMediaLibrary(); });
    }
    loadSkills();
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

  async function openProject(id, tab = 'media-library') {
    if (!state.sites.length) await loadProjects();
    let site = state.sites.find(item => item.id === id);
    if (!site) {
      await loadProjects();
      site = state.sites.find(item => item.id === id);
    }
    if (!site) { location.hash = '#projects'; throw new Error('Project not found.'); }
    state.site = id;
    state.siteRecord = site;
    for (const select of [$('topbar-site-select'), $('site-select')]) {
      if (select) select.value = id;
    }
    const parent = state.projects.find(p => p.project_id === site.project_id);
    $('project-kicker').textContent = parent ? `${parent.name} / SITE WORKSPACE` : 'SITE WORKSPACE';
    $('project-title').textContent = site.name;
    $('project-subtitle').textContent = site.location || 'Location not yet recorded';
    $('overview-description').textContent = site.description || 'Add a description to explain what this site is documenting.';
    $('project-badge').textContent = id === 'demo-riverbank' ? 'SYNTHETIC SAMPLE' : (id === 'site_nyali_creek' ? 'UNVERIFIED SCENARIO' : 'EVIDENCE RECORD');
    for (const key of ['name', 'location', 'description']) {
      const field = $('site-edit-form').elements.namedItem(key);
      if (field) field.value = site[key] || '';
    }
    if ($('bulk-date-input') && !$('bulk-date-input').value) {
      $('bulk-date-input').value = new Date().toISOString().slice(0, 10);
    }
    await refreshSite();
    selectTab(tab);
    showPage('project');
  }

  async function route() {
    const hash = location.hash.replace(/^#/, '');
    const parts = hash.split('/');
    if (parts[0] === 'setup') { showPage('setup'); return; }
    await connectLocal();
    if (!hash || hash === '/') {
      if (!state.sites.length) await loadProjects();
      const defaultSite = state.sites.find(s => s.id === 'demo-riverbank') || state.sites[0];
      if (defaultSite) {
        location.hash = `#project/${encodeURIComponent(defaultSite.id)}/media-library`;
        return;
      }
      location.hash = '#projects';
      return;
    }
    if (parts[0] === 'projects') { await loadProjects(); showPage('projects'); return; }
    if (parts[0] === 'project' && parts[1]) {
      const siteId = decodeURIComponent(parts[1]);
      let tab = parts[2] || 'media-library';
      if (tab === 'media') tab = 'media-library';
      await openProject(siteId, tab);
      return;
    }
    location.hash = '#projects';
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
          const originalText = button.textContent;
          button.disabled = true;
          button.textContent = 'Uploading to Cloudinary...';
          try {
            const data = new FormData(form);
            data.set('project_id', state.siteRecord.project_id);
            data.set('site_id', state.site);
            data.set('visit_id', visit.id);
            data.set('visit_date', visit.visited_on);
            await request('/media/images', { method: 'POST', body: data });
            notice('Photo uploaded. Check permission and provenance before using it as evidence.');
            await refreshSite();
          } finally {
            button.disabled = false;
            button.textContent = originalText;
          }
        });
      });
      card.append(form);
      list.append(card);
    }
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  }

  function renderMediaLibrary() {
    const grid = $('media-library-grid');
    if (!grid) return;
    grid.replaceChildren();

    const typeFilter = $('media-type-filter') ? $('media-type-filter').value.trim().toLowerCase() : '';
    const permFilter = $('media-perm-filter') ? $('media-perm-filter').value.trim().toLowerCase() : '';
    const aiFilter = $('media-ai-status-filter') ? $('media-ai-status-filter').value.trim().toLowerCase() : '';
    const searchFilter = $('media-search-input') ? $('media-search-input').value.trim().toLowerCase() : '';
    const tagFilter = $('media-tag-input') ? $('media-tag-input').value.trim().toLowerCase() : '';

    const items = (state.mediaItems || []).filter(item => {
      if (typeFilter && (item.media_type || 'image').toLowerCase() !== typeFilter) return false;
      if (permFilter && (item.permission_status || 'granted').toLowerCase() !== permFilter) return false;
      
      const intel = state.mediaIntelligence ? state.mediaIntelligence[item.asset_id] : null;

      if (aiFilter) {
        if (aiFilter === 'unanalyzed') {
          if (intel && ['analyzed', 'uncertain', 'insufficient_evidence'].includes(intel.status)) return false;
        } else {
          if (!intel || intel.status !== aiFilter) return false;
        }
      }

      if (tagFilter) {
        const tf = tagFilter.replace('-', '_');
        const inTags = intel && (intel.tags || []).some(t => t.toLowerCase().includes(tf));
        const inSignals = intel && (intel.signals || []).some(s => s.toLowerCase().includes(tf));
        const inDesc = intel && (intel.description || '').toLowerCase().includes(tf);
        if (!inTags && !inSignals && !inDesc) return false;
      }

      if (searchFilter) {
        const query = searchFilter;
        const matchesFilename = (item.original_filename || '').toLowerCase().includes(query);
        const matchesSource = (item.source || '').toLowerCase().includes(query);
        const matchesId = (item.asset_id || '').toLowerCase().includes(query);
        if (!matchesFilename && !matchesSource && !matchesId) return false;
      }
      return true;
    });

    grid.classList.toggle('empty', !items.length);
    if (!items.length) {
      grid.textContent = (state.mediaItems && state.mediaItems.length)
        ? 'No media assets match the current filter selection.'
        : 'No media assets in library yet. Use the bulk uploader above to ingest photos or videos.';
      return;
    }

    for (const item of items) {
      const isVideo = item.media_type === 'video';
      const card = element('article', `media-card ${isVideo ? 'media-video-card' : 'media-image-card'}`);

      // Media thumbnail preview
      const thumb = element('div', 'media-card-thumb');
      const img = element('img');
      img.src = item.thumbnail_url || item.preview_url || item.secure_url;
      img.alt = item.original_filename || item.asset_id;
      img.loading = 'lazy';
      thumb.append(img);

      const typeBadge = element('span', `media-type-badge ${isVideo ? 'video' : ''}`, (item.media_type || 'image').toUpperCase());
      thumb.append(typeBadge);

      if (isVideo && item.duration) {
        const durationBadge = element('span', 'media-duration-badge', formatDuration(item.duration));
        thumb.append(durationBadge);
      }

      const previewBtn = element('button', 'zoom-btn', isVideo ? '▶ Play Video' : '⤢ Enlarge');
      previewBtn.type = 'button';
      previewBtn.addEventListener('click', () => {
        const title = item.original_filename || (isVideo ? 'Video Evidence' : 'Photo Evidence');
        const details = `ID: ${item.asset_id} · Source: ${item.source} · ${item.width || '?'}x${item.height || '?'} ${item.format.toUpperCase()}${item.duration ? ` · Duration: ${formatDuration(item.duration)}` : ''}`;
        const permStatus = item.permission_status || 'granted';
        openLightbox(
          item.preview_url || item.secure_url,
          title,
          details,
          permStatus.replace('_', ' ').toUpperCase(),
          permStatus,
          item.media_type || 'image',
          isVideo ? item.secure_url : null
        );
      });
      thumb.append(previewBtn);
      card.append(thumb);

      // Card Body
      const body = element('div', 'media-card-body');
      const filename = element('h4', '', item.original_filename || item.asset_id.slice(0, 16));
      filename.title = item.original_filename || item.asset_id;

      const tags = element('div', 'media-card-tags');
      const permBadge = element('span', `badge ${item.permission_status || 'granted'}`, (item.permission_status || 'granted').replace('_', ' '));
      const autoPill = element('span', 'delivery-pill', '⚡ f_auto,q_auto');
      const cloudPill = element('span', 'delivery-pill', item.secure_url.includes('cloudinary.com') ? '☁ Cloudinary' : 'Local');
      tags.append(permBadge, autoPill, cloudPill);

      // Structured AI Intelligence Summary
      const intel = state.mediaIntelligence ? state.mediaIntelligence[item.asset_id] : null;
      const intelSection = element('div', 'media-card-intel');
      const intelHeader = element('div', 'intel-header-row');
      const intelStatus = intel ? intel.status : 'unanalyzed';
      const intelStatusBadge = element('span', `badge ${intelStatus === 'analyzed' ? 'success' : (intelStatus === 'uncertain' ? 'uncertain' : (intelStatus === 'unanalyzed' ? 'neutral' : 'danger'))}`, intel ? `🧠 ${intelStatus.toUpperCase()}` : '⚪ UNANALYZED');
      intelHeader.append(intelStatusBadge);
      if (intel && intel.model_name) {
        intelHeader.append(element('span', 'meta', intel.model_name));
      }
      intelSection.append(intelHeader);

      if (intel && intel.description) {
        const desc = element('p', 'intel-desc', intel.description);
        intelSection.append(desc);
      }

      if (intel && intel.tags && intel.tags.length) {
        const tagWrap = element('div', 'intel-tags-row');
        for (const t of intel.tags.slice(0, 4)) {
          tagWrap.append(element('span', 'delivery-pill', `#${t}`));
        }
        if (intel.tags.length > 4) {
          tagWrap.append(element('span', 'meta', `+${intel.tags.length - 4}`));
        }
        intelSection.append(tagWrap);
      }

      if (intel && intel.warnings && intel.warnings.length) {
        const warnPill = element('span', 'badge warn', `⚠ ${intel.warnings[0]}`);
        intelSection.append(warnPill);
      }

      const meta = element('p', 'meta');
      const dim = item.width && item.height ? `${item.width}×${item.height}` : '';
      const parts = [dim, item.format?.toUpperCase(), item.created_at ? item.created_at.slice(0, 10) : ''].filter(Boolean);
      meta.textContent = `${parts.join(' · ')} · Source: ${item.source || 'Unspecified'}`;

      const actions = element('div', 'media-card-actions');
      const copyBtn = element('button', 'button secondary button-small', 'Copy URL');
      copyBtn.type = 'button';
      copyBtn.addEventListener('click', () => {
        navigator.clipboard?.writeText(item.secure_url).then(() => {
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy URL'; }, 1500);
        }).catch(() => {
          notice(`Asset URL: ${item.secure_url}`);
        });
      });

      const openLink = element('a', 'button quiet button-small', 'Open ↗');
      openLink.href = item.secure_url;
      openLink.target = '_blank';
      openLink.rel = 'noopener noreferrer';

      actions.append(copyBtn, openLink);

      // AI Analysis Action
      const intelBtn = element('button', 'button secondary button-small', intel ? '🧠 Intelligence' : '🧠 Analyze');
      intelBtn.type = 'button';
      intelBtn.addEventListener('click', () => {
        if (intel) {
          openIntelligenceModal(item, intel);
        } else {
          triggerAnalyzeMedia(item.asset_id, false);
        }
      });
      actions.append(intelBtn);

      if (isVideo) {
        const frameBtn = element('button', 'button primary button-small', '🎬 Frame Analytics');
        frameBtn.type = 'button';
        frameBtn.addEventListener('click', () => {
          openVideoFramesModal(item);
        });
        actions.append(frameBtn);
      }

      body.append(filename, tags, intelSection, meta, actions);
      card.append(body);

      grid.append(card);
    }
  }

  async function loadSkills() {
    try {
      const skills = await request('/skills');
      state.skills = Array.isArray(skills) ? skills : [];
      renderSkills();
    } catch (e) {
      console.warn('Could not load skills:', e);
    }
  }

  function renderSkills() {
    const grid = $('skills-list-grid');
    if (!grid) return;
    grid.replaceChildren();

    const badge = $('skills-count-badge');
    if (badge) {
      badge.textContent = `${state.skills.length} Skill${state.skills.length === 1 ? '' : 's'} Registered`;
    }

    if (!state.skills.length) {
      grid.className = 'skills-grid empty';
      grid.textContent = 'No skills registered yet.';
      return;
    }

    grid.className = 'skills-grid';

    for (const skill of state.skills) {
      const card = element('article', 'skill-card paper-card');

      const header = element('div', 'skill-card-header');
      const titleWrap = element('div');
      const title = element('h3', 'skill-name', skill.name);
      const badges = element('div', 'skill-badges');
      badges.append(
        element('span', 'badge version-badge', `v${skill.version}`),
        element('span', `badge kind-badge ${skill.kind}`, skill.kind)
      );
      if (skill.model?.provider) {
        badges.append(element('span', 'badge model-badge', `AI: ${skill.model.provider}`));
      }
      titleWrap.append(title, badges);
      header.append(titleWrap);

      const desc = element('p', 'skill-desc', skill.description);
      const metaGrid = element('div', 'skill-meta-grid');

      // Permissions
      const permsWrap = element('div', 'skill-meta-item');
      permsWrap.append(element('strong', '', 'Permissions: '));
      if (skill.permissions && skill.permissions.length) {
        const permsList = element('span', 'skill-tags-list');
        for (const p of skill.permissions) {
          permsList.append(element('span', 'skill-tag perm-tag', p));
        }
        permsWrap.append(permsList);
      } else {
        permsWrap.append(element('span', 'meta', 'None'));
      }

      // Inputs
      const inputsWrap = element('div', 'skill-meta-item');
      inputsWrap.append(element('strong', '', 'Inputs: '));
      const inputsList = element('span', 'skill-tags-list');
      for (const inp of (skill.inputs || [])) {
        inputsList.append(element('span', `skill-tag ${inp.required ? 'required-tag' : 'optional-tag'}`, `${inp.name} (${inp.type})`));
      }
      inputsWrap.append(inputsList);

      // Outputs
      const outputsWrap = element('div', 'skill-meta-item');
      outputsWrap.append(element('strong', '', 'Outputs: '));
      const outputsList = element('span', 'skill-tags-list');
      for (const out of (skill.outputs || [])) {
        outputsList.append(element('span', 'skill-tag output-tag', `${out.name} (${out.type})`));
      }
      outputsWrap.append(outputsList);

      metaGrid.append(permsWrap, inputsWrap, outputsWrap);

      const actions = element('div', 'skill-actions');
      const testBtn = element('button', 'button secondary button-small', 'Test Skill ⚡');
      testBtn.type = 'button';
      testBtn.addEventListener('click', () => openSkillTester(skill));
      actions.append(testBtn);

      card.append(header, desc, metaGrid, actions);
      grid.append(card);
    }
  }

  function openSkillTester(skill) {
    state.activeTestSkill = skill;
    const panel = $('skill-tester-panel');
    if (!panel) return;
    $('tester-skill-title').textContent = `Test Skill: ${skill.name}@${skill.version}`;
    $('tester-skill-desc').textContent = skill.description;

    const container = $('tester-inputs-container');
    container.replaceChildren();

    for (const inp of (skill.inputs || [])) {
      const label = element('label');
      label.textContent = `${inp.name} (${inp.type}) ${inp.required ? '*' : '(optional)'}:`;
      const input = element('input');
      input.name = inp.name;
      input.placeholder = inp.description || inp.name;
      if (inp.required) input.required = true;

      // Provide helpful test defaults for the built-in skills
      if (skill.name === 'media-metadata' && inp.name === 'url') {
        input.value = state.mediaItems.length > 0 ? state.mediaItems[0].secure_url : 'https://res.cloudinary.com/demo/image/upload/sample.jpg';
      } else if (skill.name === 'evidence-comparison') {
        if (inp.name === 'before_url') input.value = 'https://res.cloudinary.com/demo/image/upload/sample.jpg';
        if (inp.name === 'after_url') input.value = 'https://res.cloudinary.com/demo/image/upload/sample.jpg';
      }

      label.append(input);
      container.append(label);
    }

    $('skill-run-output').hidden = true;
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth' });
  }

  // ---------------------------------------------------------------------------
  // T013 Setowa Workflow Studio & Builder
  // ---------------------------------------------------------------------------

  async function loadWorkflowsStudio() {
    try {
      if (!state.skills.length) {
        const skills = await request('/skills');
        state.skills = Array.isArray(skills) ? skills : [];
      }
      renderWorkflowPalette();

      const wfList = await request('/workflows');
      state.workflows = Array.isArray(wfList) ? wfList : [];
      renderWorkflowSelector();

      if (!state.currentWorkflow && state.workflows.length > 0) {
        await loadWorkflow(state.workflows[0].id);
      } else if (!state.currentWorkflow) {
        initNewWorkflow();
      }
    } catch (e) {
      console.warn('Could not load workflows:', e);
    }
  }

  function renderWorkflowSelector() {
    const sel = $('wf-selector');
    if (!sel) return;
    const currentId = state.currentWorkflow?.id;
    sel.replaceChildren();
    for (const wf of state.workflows) {
      const opt = new Option(`${wf.name} (v${wf.version})`, wf.id);
      if (wf.id === currentId) opt.selected = true;
      sel.add(opt);
    }
  }

  async function loadWorkflow(wfId) {
    try {
      const wf = await request(`/workflows/${encodeURIComponent(wfId)}`);
      state.currentWorkflow = wf;
      state.selectedNodeId = wf.nodes.length > 0 ? wf.nodes[0].id : null;
      renderWorkflowCanvas();
      renderNodeInspector();
      setWorkflowStatusBadge('Ready', 'granted');
    } catch (e) {
      notice(`Failed to load workflow: ${e.message}`, true);
    }
  }

  function initNewWorkflow() {
    state.currentWorkflow = {
      id: 'wf_' + Math.random().toString(36).substring(2, 9),
      name: 'Custom Impact Workflow',
      version: '1.0.0',
      description: 'Declarative DAG pipeline composed in Setowa Workflow Builder.',
      inputs: [
        { name: 'media_url', type: 'string', description: 'Primary media URL for analysis', required: true }
      ],
      nodes: [],
      edges: [],
      metadata: { created_in_builder: true }
    };
    state.selectedNodeId = null;
    renderWorkflowCanvas();
    renderNodeInspector();
    setWorkflowStatusBadge('Draft', '');
  }

  function setWorkflowStatusBadge(text, badgeClass) {
    const badge = $('wf-status-badge');
    if (!badge) return;
    badge.textContent = text;
    badge.className = `badge ${badgeClass}`;
  }

  function renderWorkflowPalette() {
    const list = $('wf-palette-list');
    if (!list) return;
    list.replaceChildren();

    if (!state.skills.length) {
      list.textContent = 'No skills available.';
      return;
    }

    for (const skill of state.skills) {
      const card = element('div', 'wf-palette-card');
      const title = element('div', 'wf-palette-title');
      title.append(
        element('span', '', skill.name),
        element('span', `badge kind-badge ${skill.kind}`, `v${skill.version}`)
      );
      const desc = element('p', 'wf-palette-desc', skill.description);

      const addBtn = element('button', 'button secondary button-small', '+ Add Node');
      addBtn.type = 'button';
      addBtn.addEventListener('click', () => addNodeToWorkflow(skill));

      card.append(title, desc, addBtn);
      list.append(card);
    }
  }

  function addNodeToWorkflow(skill) {
    if (!state.currentWorkflow) initNewWorkflow();
    const count = state.currentWorkflow.nodes.length;
    const baseId = skill.name.replace(/[^a-z0-9]/gi, '_');
    const nodeId = `${baseId}_${count + 1}`;

    const x = 30 + ((count * 30) % 180);
    const y = 30 + ((count * 60) % 220);

    const defaultInputs = {};
    for (const inp of (skill.inputs || [])) {
      if (inp.default !== undefined && inp.default !== null) {
        defaultInputs[inp.name] = inp.default;
      }
    }

    const newNode = {
      id: nodeId,
      skill: skill.name,
      skill_version: skill.version,
      inputs: defaultInputs,
      position: { x, y },
      metadata: { label: skill.name }
    };

    state.currentWorkflow.nodes.push(newNode);
    state.selectedNodeId = nodeId;
    renderWorkflowCanvas();
    renderNodeInspector();
    setWorkflowStatusBadge('Draft (Unsaved)', '');
  }

  function renderWorkflowCanvas() {
    const wf = state.currentWorkflow;
    if (!wf) return;

    $('wf-name-input').value = wf.name || '';
    $('wf-version-input').value = wf.version || '1.0.0';
    $('wf-canvas-meta').textContent = `${wf.nodes.length} node${wf.nodes.length === 1 ? '' : 's'}, ${wf.edges.length} edge${wf.edges.length === 1 ? '' : 's'}`;

    const emptyMsg = $('wf-canvas-empty');
    if (emptyMsg) emptyMsg.hidden = wf.nodes.length > 0;

    const container = $('wf-canvas-nodes');
    container.querySelectorAll('.wf-node').forEach(el => el.remove());

    const svg = $('wf-canvas-svg');
    if (svg) svg.replaceChildren();

    for (const node of wf.nodes) {
      const nodeEl = element('div', `wf-node ${node.id === state.selectedNodeId ? 'selected' : ''}`);
      nodeEl.id = `wf-node-${node.id}`;
      nodeEl.style.left = `${node.position?.x ?? 50}px`;
      nodeEl.style.top = `${node.position?.y ?? 50}px`;

      // Header
      const header = element('div', 'wf-node-header');
      const title = element('span', 'wf-node-title', node.skill);
      title.title = `${node.skill}@${node.skill_version}`;

      const delBtn = element('button', 'wf-node-delete-btn', '✕');
      delBtn.title = 'Delete Node';
      delBtn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        deleteNode(node.id);
      });

      header.append(title, delBtn);

      // Body
      const body = element('div', 'wf-node-body');
      const idLabel = element('div', 'wf-node-id', `#${node.id}`);

      // Ports preview
      const ports = element('div', 'wf-node-ports');
      const skillInst = state.skills.find(s => s.name === node.skill);
      const inputs = skillInst?.inputs || Object.keys(node.inputs).map(k => ({ name: k, type: '' }));
      const outputs = skillInst?.outputs || [];

      const inPortRow = element('div', 'wf-port-row');
      inPortRow.append(
        element('span', 'wf-port-in', `▶ In: ${inputs.map(i => i.name).slice(0, 2).join(', ')}${inputs.length > 2 ? '…' : ''}`)
      );
      const outPortRow = element('div', 'wf-port-row');
      outPortRow.append(
        element('span', 'wf-port-out', `◀ Out: ${outputs.map(o => o.name).slice(0, 2).join(', ')}${outputs.length > 2 ? '…' : ''}`)
      );
      ports.append(inPortRow, outPortRow);

      body.append(idLabel, ports);
      nodeEl.append(header, body);

      // Click to select
      nodeEl.addEventListener('click', () => {
        state.selectedNodeId = node.id;
        container.querySelectorAll('.wf-node').forEach(el => el.classList.remove('selected'));
        nodeEl.classList.add('selected');
        renderNodeInspector();
      });

      // Draggable logic
      setupNodeDragging(nodeEl, node);

      container.append(nodeEl);
    }

    // Draw SVG connections
    requestAnimationFrame(() => drawWorkflowEdges());
  }

  function setupNodeDragging(nodeEl, node) {
    let startX = 0, startY = 0;
    let initialLeft = 0, initialTop = 0;

    nodeEl.addEventListener('pointerdown', (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      startX = e.clientX;
      startY = e.clientY;
      initialLeft = node.position?.x ?? (parseInt(nodeEl.style.left, 10) || 0);
      initialTop = node.position?.y ?? (parseInt(nodeEl.style.top, 10) || 0);

      nodeEl.setPointerCapture(e.pointerId);

      const onPointerMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        const newX = Math.max(0, initialLeft + dx);
        const newY = Math.max(0, initialTop + dy);
        nodeEl.style.left = `${newX}px`;
        nodeEl.style.top = `${newY}px`;
        node.position = { x: newX, y: newY };
        drawWorkflowEdges();
      };

      const onPointerUp = (ev) => {
        nodeEl.releasePointerCapture(ev.pointerId);
        nodeEl.removeEventListener('pointermove', onPointerMove);
        nodeEl.removeEventListener('pointerup', onPointerUp);
      };

      nodeEl.addEventListener('pointermove', onPointerMove);
      nodeEl.addEventListener('pointerup', onPointerUp);
    });
  }

  function drawWorkflowEdges() {
    const svg = $('wf-canvas-svg');
    const container = $('wf-canvas-container');
    if (!svg || !container || !state.currentWorkflow) return;

    svg.replaceChildren();
    const containerRect = container.getBoundingClientRect();

    // Arrow marker def
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'wf-arrow');
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M 0 1 L 10 5 L 0 9 z');
    path.setAttribute('fill', '#2563eb');
    marker.append(path);
    defs.append(marker);
    svg.append(defs);

    for (const edge of state.currentWorkflow.edges) {
      const srcEl = $(`wf-node-${edge.source_node}`);
      const tgtEl = $(`wf-node-${edge.target_node}`);
      if (!srcEl || !tgtEl) continue;

      const srcRect = srcEl.getBoundingClientRect();
      const tgtRect = tgtEl.getBoundingClientRect();

      const x1 = srcRect.right - containerRect.left;
      const y1 = srcRect.top + srcRect.height / 2 - containerRect.top;
      const x2 = tgtRect.left - containerRect.left;
      const y2 = tgtRect.top + tgtRect.height / 2 - containerRect.top;

      const dx = Math.max(30, Math.abs(x2 - x1) * 0.5);
      const cx1 = x1 + dx;
      const cx2 = x2 - dx;

      const edgePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      edgePath.setAttribute('d', `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`);
      edgePath.setAttribute('stroke', '#2563eb');
      edgePath.setAttribute('stroke-width', '2');
      edgePath.setAttribute('fill', 'none');
      edgePath.setAttribute('marker-end', 'url(#wf-arrow)');

      svg.append(edgePath);
    }
  }

  function deleteNode(nodeId) {
    if (!state.currentWorkflow) return;
    state.currentWorkflow.nodes = state.currentWorkflow.nodes.filter(n => n.id !== nodeId);
    state.currentWorkflow.edges = state.currentWorkflow.edges.filter(
      e => e.source_node !== nodeId && e.target_node !== nodeId
    );
    if (state.selectedNodeId === nodeId) {
      state.selectedNodeId = state.currentWorkflow.nodes[0]?.id || null;
    }
    renderWorkflowCanvas();
    renderNodeInspector();
    setWorkflowStatusBadge('Draft (Unsaved)', '');
  }

  function renderNodeInspector() {
    const container = $('wf-inspector-content');
    if (!container) return;
    container.replaceChildren();

    const wf = state.currentWorkflow;
    if (!wf || !state.selectedNodeId) {
      container.append(element('p', 'muted', 'Select a node on the canvas to configure its inputs and connections.'));
      return;
    }

    const node = wf.nodes.find(n => n.id === state.selectedNodeId);
    if (!node) {
      container.append(element('p', 'muted', 'Node not found.'));
      return;
    }

    const skill = state.skills.find(s => s.name === node.skill);

    // Node Metadata Section
    const infoSection = element('div', 'wf-inspector-section');
    infoSection.append(
      element('div', 'wf-inspector-label', 'Node Identity'),
      element('strong', '', node.id),
      element('div', 'meta', `Skill: ${node.skill}@${node.skill_version}`)
    );

    // Inputs Mapping Section
    const inputsSection = element('div', 'wf-inspector-section');
    inputsSection.append(element('div', 'wf-inspector-label', 'Input Mappings'));

    const declaredInputs = skill?.inputs || Object.keys(node.inputs).map(k => ({ name: k, type: 'string', required: true }));

    for (const inp of declaredInputs) {
      const row = element('div', 'wf-input-mapping-row');
      const label = element('strong', '', `${inp.name} ${inp.required ? '*' : ''}`);
      row.append(label);

      const currentVal = node.inputs[inp.name] || '';

      const sel = element('select');
      sel.add(new Option('Custom Literal Value', 'literal'));
      // Workflow inputs
      for (const wfIn of (wf.inputs || [])) {
        sel.add(new Option(`Workflow Input ($input.${wfIn.name})`, `$input.${wfIn.name}`));
      }
      // Upstream outputs
      for (const otherNode of wf.nodes) {
        if (otherNode.id === node.id) continue;
        const otherSkill = state.skills.find(s => s.name === otherNode.skill);
        for (const out of (otherSkill?.outputs || [])) {
          sel.add(new Option(`Node [${otherNode.id}] → ${out.name}`, `$node.${otherNode.id}.${out.name}`));
        }
      }

      const inputVal = element('input');
      inputVal.placeholder = inp.description || 'Value';

      if (typeof currentVal === 'string' && (currentVal.startsWith('$input.') || currentVal.startsWith('$node.'))) {
        sel.value = currentVal;
        inputVal.hidden = true;
      } else {
        sel.value = 'literal';
        inputVal.value = currentVal;
        inputVal.hidden = false;
      }

      sel.addEventListener('change', () => {
        if (sel.value === 'literal') {
          inputVal.hidden = false;
          node.inputs[inp.name] = inputVal.value;
          wf.edges = wf.edges.filter(e => !(e.target_node === node.id && e.target_input === inp.name));
        } else {
          inputVal.hidden = true;
          node.inputs[inp.name] = sel.value;
          if (sel.value.startsWith('$node.')) {
            const parts = sel.value.substring(6).split('.');
            const srcNode = parts[0];
            const srcOut = parts[1];
            wf.edges = wf.edges.filter(e => !(e.target_node === node.id && e.target_input === inp.name));
            wf.edges.push({
              source_node: srcNode,
              source_output: srcOut,
              target_node: node.id,
              target_input: inp.name
            });
          } else {
            wf.edges = wf.edges.filter(e => !(e.target_node === node.id && e.target_input === inp.name));
          }
        }
        drawWorkflowEdges();
        setWorkflowStatusBadge('Draft (Unsaved)', '');
      });

      inputVal.addEventListener('input', () => {
        node.inputs[inp.name] = inputVal.value;
        setWorkflowStatusBadge('Draft (Unsaved)', '');
      });

      row.append(sel, inputVal);
      inputsSection.append(row);
    }

    container.append(infoSection, inputsSection);
  }

  async function validateCurrentWorkflow() {
    const wf = state.currentWorkflow;
    if (!wf) return;
    wf.name = $('wf-name-input').value.trim() || 'Untitled Workflow';
    wf.version = $('wf-version-input').value.trim() || '1.0.0';

    const alertBox = $('wf-validation-alert');
    try {
      const res = await request('/workflows/validate-draft', {
        method: 'POST',
        json: wf
      });

      if (res.is_valid) {
        setWorkflowStatusBadge('DAG Valid', 'granted');
        if (alertBox) alertBox.hidden = true;
        notice(`Workflow DAG is valid! Execution order: ${res.execution_order.join(' → ')}`);
      } else {
        setWorkflowStatusBadge('Invalid DAG', 'revoked');
        if (alertBox) {
          alertBox.hidden = false;
          alertBox.textContent = `Validation failed: ${res.errors.join('; ')}`;
        }
        notice('Workflow validation failed.', true);
      }
    } catch (e) {
      notice(`Validation error: ${e.message}`, true);
    }
  }

  async function saveCurrentWorkflow() {
    const wf = state.currentWorkflow;
    if (!wf) return;
    wf.name = $('wf-name-input').value.trim() || 'Untitled Workflow';
    wf.version = $('wf-version-input').value.trim() || '1.0.0';

    try {
      let saved;
      const existing = state.workflows.find(w => w.id === wf.id);
      if (existing) {
        saved = await request(`/workflows/${encodeURIComponent(wf.id)}`, {
          method: 'PUT',
          json: wf
        });
      } else {
        saved = await request('/workflows', {
          method: 'POST',
          json: wf
        });
      }
      state.currentWorkflow = saved;
      setWorkflowStatusBadge('Saved', 'granted');
      notice(`Workflow '${saved.name}' saved successfully.`);

      const wfList = await request('/workflows');
      state.workflows = Array.isArray(wfList) ? wfList : [];
      renderWorkflowSelector();
    } catch (e) {
      notice(`Failed to save workflow: ${e.message}`, true);
    }
  }

  function prepareRunWorkflow() {
    const wf = state.currentWorkflow;
    if (!wf) return;
    const formContainer = $('wf-exec-inputs');
    if (!formContainer) return;
    formContainer.replaceChildren();

    for (const inp of (wf.inputs || [])) {
      const label = element('label');
      label.textContent = `${inp.name} (${inp.type}) ${inp.required ? '*' : ''}:`;
      const input = element('input');
      input.name = inp.name;
      input.placeholder = inp.description || inp.name;
      if (inp.required) input.required = true;

      // Smart pre-fill for demo before/after comparisons
      if (inp.name === 'before_asset_id' && state.visits.length > 0 && state.visits[0].assets.length > 0) {
        input.value = state.visits[0].assets[0].asset_id;
      } else if (inp.name === 'after_asset_id' && state.visits.length > 1 && state.visits[1].assets.length > 0) {
        input.value = state.visits[1].assets[0].asset_id;
      }

      label.append(input);
      formContainer.append(label);
    }

    $('wf-execution-panel').scrollIntoView({ behavior: 'smooth' });
  }

  async function executeCurrentWorkflow(form) {
    const wf = state.currentWorkflow;
    if (!wf) return;

    const submitBtn = $('wf-exec-submit-btn');
    const statusText = $('wf-exec-status-text');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Running DAG...';
    if (statusText) statusText.textContent = 'Executing workflow steps in topological order...';

    try {
      const rawInputs = Object.fromEntries(new FormData(form));
      const result = await request(`/workflows/${encodeURIComponent(wf.id)}/execute`, {
        method: 'POST',
        json: {
          inputs: rawInputs,
          execution_context: { user_id: state.session || 'analyst' }
        }
      });

      state.workflowExecution = result;
      renderWorkflowExecutionResults(result);
      notice(`Workflow execution completed: ${result.status.toUpperCase()}`);
    } catch (e) {
      notice(`Execution failed: ${e.message}`, true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
      if (statusText) statusText.textContent = '';
    }
  }

  function renderWorkflowExecutionResults(result) {
    const resultsBox = $('wf-exec-results');
    if (!resultsBox) return;

    resultsBox.hidden = false;
    $('wf-res-status').textContent = result.status.toUpperCase();
    $('wf-res-duration').textContent = `${result.duration_ms} ms`;
    $('wf-res-id').textContent = result.execution_id;

    const statusBadge = $('wf-exec-status-badge');
    if (statusBadge) {
      statusBadge.textContent = result.status.toUpperCase();
      statusBadge.className = `badge ${result.status === 'success' ? 'granted' : 'revoked'}`;
    }

    const stepsContainer = $('wf-res-steps');
    stepsContainer.replaceChildren();

    for (const nodeId of result.execution_order) {
      const nodeRes = result.node_results[nodeId] || {};
      const chip = element('div', 'wf-step-chip');
      const info = element('div');
      info.append(
        element('strong', '', nodeId),
        element('div', 'meta', `${nodeRes.skill || 'step'} · ${nodeRes.latency_ms ?? 0}ms`)
      );
      const badge = element('span', `badge ${nodeRes.status || 'pending'}`, (nodeRes.status || 'pending').toUpperCase());
      chip.append(info, badge);

      chip.addEventListener('click', () => {
        stepsContainer.querySelectorAll('.wf-step-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        $('wf-step-detail-json').textContent = JSON.stringify(nodeRes, null, 2);
      });

      stepsContainer.append(chip);
    }

    $('wf-step-detail-json').textContent = JSON.stringify(result, null, 2);
  }

  function assetsForSite() {
    return state.visits.flatMap(visit => visit.assets.map(asset => ({ ...asset, visit })));
  }

  function renderPairChoices() {
    const allAssets = assetsForSite();
    const photoAssets = allAssets.filter(asset => (asset.media_type || 'image') !== 'video');
    photoAssets.sort((a, b) => (a.visit.visited_on || '').localeCompare(b.visit.visited_on || ''));

    for (const [id, isBefore] of [['before-select', true], ['after-select', false]]) {
      const select = $(id);
      if (!select) continue;
      const previous = select.value;
      select.replaceChildren(new Option('Choose a photo', ''));
      for (const asset of photoAssets) {
        const permNote = asset.permission_status !== 'granted' ? ` [${asset.permission_status}]` : '';
        select.add(new Option(`${asset.visit.visited_on} · ${asset.visit.label} · ${asset.source}${permNote}`, asset.asset_id));
      }
      if (photoAssets.some(asset => asset.asset_id === previous)) {
        select.value = previous;
      } else if (photoAssets.length >= 2) {
        select.value = (isBefore ? photoAssets[0] : photoAssets[photoAssets.length - 1]).asset_id;
      } else if (photoAssets.length === 1 && isBefore) {
        select.value = photoAssets[0].asset_id;
      }
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
          element('span', 'banner-badge', '✓ HUMAN-APPROVED RECORD'),
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
          element('h4', '', 'APPROVED OBSERVATION'),
          element('p', 'verified-text', observation.approved_text || observation.working_text),
          element('p', 'verification-trail',
            `✓ Approved by ${observation.reviewed_by || 'Human Reviewer'} on ${observation.reviewed_at ? observation.reviewed_at.slice(0, 16).replace('T', ' ') : 'recently'} UTC`
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
        const originalTexts = { save: save.textContent, approve: approve.textContent, reject: reject.textContent };
        buttons.forEach(button => { button.disabled = true; });
        if (method === 'PATCH') save.textContent = 'Saving...';
        else if (payload.decision === 'approve') approve.textContent = 'Approving...';
        else if (payload.decision === 'reject') reject.textContent = 'Rejecting...';
        try {
          await request(`/observations/${observation.id}${method === 'POST' ? '/review' : ''}`,
            { method, json: { expected_version: observation.version, ...payload } });
          notice(
            method === 'PATCH' ? 'Edit saved. Approval invalidated; observation returned to pending.' :
            payload.decision === 'approve' ? 'Observation approved. It is now eligible for the evidence report.' :
            'Observation rejected and excluded from report.'
          );
          await refreshSite();
        } finally {
          buttons.forEach(button => { button.disabled = false; });
          save.textContent = originalTexts.save;
          approve.textContent = originalTexts.approve;
          reject.textContent = originalTexts.reject;
        }
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
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        const values = Object.fromEntries(new FormData(form));
        const status = await request('/local/credentials', { method: 'PUT', json: {
          cloudinary: { cloud_name: values.cloud_name, api_key: values.cloudinary_api_key,
            api_secret: values.cloudinary_api_secret },
          gemini: { api_key: values.gemini_api_key },
        } });
        form.reset(); renderStatus(status);
        notice('Saved locally. The readiness indicators have been updated.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  $('new-project-button').addEventListener('click', () => {
    $('new-project-panel').hidden = !$('new-project-panel').hidden;
    if (!$('new-project-panel').hidden) $('site-form').elements.namedItem('name').focus();
  });
  $('new-parent-project-button').addEventListener('click', () => {
    $('new-parent-project-panel').hidden = !$('new-parent-project-panel').hidden;
    if (!$('new-parent-project-panel').hidden) $('parent-project-form').elements.namedItem('name').focus();
  });
  $('library-project-select').addEventListener('change', event => {
    state.projectFilter = event.target.value;
    run(loadProjects);
  });
  $('parent-project-form').addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form));
      await request('/projects', { method: 'POST', json: data });
      state.projectFilter = data.id;
      form.reset();
      $('new-parent-project-panel').hidden = true;
      await loadProjects();
      $('new-project-panel').hidden = false;
      notice('Project created. Add its first site.', 'success');
    });
  });

  $('site-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        const data = Object.fromEntries(new FormData(form));
        await request('/sites', { method: 'POST', json: data });
        form.reset(); notice('Site created. Add its first visit.');
        await loadProjects(); location.hash = projectHash(data.id);
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  $('site-edit-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        const site = await request(`/sites/${encodeURIComponent(state.site)}`, {
          method: 'PATCH', json: Object.fromEntries(new FormData(form)),
        });
        state.siteRecord = site;
        state.sites = state.sites.map(item => item.id === site.id ? site : item);
        $('project-title').textContent = site.name;
        $('project-subtitle').textContent = site.location || 'Location not yet recorded';
        $('overview-description').textContent = site.description || 'Add a description to explain what this site is documenting.';
        notice('Project details saved.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  document.querySelectorAll('.tab-button').forEach(button => button.addEventListener('click', () => goToTab(button.dataset.tab)));
  $('next-step-button').addEventListener('click', () => goToTab(state.nextTab));

  $('visit-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        await request(`/sites/${encodeURIComponent(state.site)}/visits`, {
          method: 'POST', json: Object.fromEntries(new FormData(form)),
        });
        form.reset(); await refreshSite(); notice('Visit recorded. Add a photo below.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  $('media-filter').addEventListener('input', renderVisits);
  if ($('media-type-filter')) $('media-type-filter').addEventListener('change', renderMediaLibrary);
  if ($('media-perm-filter')) $('media-perm-filter').addEventListener('change', renderMediaLibrary);
  if ($('media-search-input')) $('media-search-input').addEventListener('input', renderMediaLibrary);

  const bulkForm = $('bulk-upload-form');
  if (bulkForm) {
    bulkForm.addEventListener('submit', event => {
      event.preventDefault();
      run(async () => {
        const filesInput = $('bulk-files-input');
        const files = filesInput?.files;
        if (!files || !files.length) {
          throw new Error('Please select at least one media file.');
        }

        const dateInput = $('bulk-date-input');
        const visitDate = dateInput?.value || new Date().toISOString().slice(0, 10);

        const permSelect = $('bulk-perm-select');
        const permStatus = permSelect?.value || 'granted';

        const sourceInput = $('bulk-source-input');
        const source = sourceInput?.value.trim() || '';
        if (!source) {
          throw new Error('Please provide source attribution / consent record.');
        }

        const submitBtn = $('bulk-submit-btn');
        const statusText = $('bulk-upload-status');
        const resultsBox = $('bulk-results-box');

        const originalBtnText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = `Ingesting ${files.length} file${files.length === 1 ? '' : 's'}...`;
        if (statusText) statusText.textContent = 'Uploading and processing collection via Cloudinary...';
        if (resultsBox) resultsBox.hidden = true;

        try {
          const formData = new FormData();
          for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
          }
          formData.set('project_id', state.site);
          formData.set('visit_date', visitDate);
          formData.set('permission_status', permStatus);
          formData.set('source', source);

          const result = await request('/media/bulk', {
            method: 'POST',
            body: formData,
          });

          notice(`Bulk ingestion complete: ${result.successful} successful, ${result.failed} failed.`);

          if (resultsBox) {
            resultsBox.replaceChildren();
            const summary = element('div', 'bulk-summary-line',
              `Processed ${result.total_files} file${result.total_files === 1 ? '' : 's'}: ${result.successful} succeeded, ${result.failed} failed.`
            );
            resultsBox.append(summary);

            if (result.results && result.results.length) {
              const resList = element('ul', 'bulk-results-list');
              for (const r of result.results) {
                const li = element('li', r.status === 'success' ? 'bulk-item-success' : 'bulk-item-failed');
                li.textContent = `${r.filename}: ${r.status === 'success' ? '✓ Ingested' : `✕ ${r.error || 'Failed'}`}`;
                resList.append(li);
              }
              resultsBox.append(resList);
            }
            resultsBox.hidden = false;
          }

          if (result.successful > 0) {
            filesInput.value = '';
            await refreshSite();
          }
        } finally {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
          if (statusText) statusText.textContent = '';
        }
      });
    });
  }

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
    const compareBtn = $('compare');
    const originalText = compareBtn.textContent;
    compareBtn.disabled = true;
    compareBtn.textContent = 'Comparing with Gemini...';
    notice('Analyzing evidence pair with Gemini vision model...');
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
    } finally {
      compareBtn.disabled = false;
      compareBtn.textContent = originalText;
    }
  }));

  $('measurement-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(async () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        const data = Object.fromEntries(new FormData(form)); data.quantity = Number(data.quantity);
        await request(`/sites/${encodeURIComponent(state.site)}/measurements`, { method: 'POST', json: data });
        form.reset(); await refreshSite(); notice('Measurement saved with its source.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  $('export').addEventListener('click', () => run(async () => {
    const exportBtn = $('export');
    const originalText = exportBtn.textContent;
    exportBtn.disabled = true;
    exportBtn.textContent = 'Generating report...';
    try {
      const response = await request(`/sites/${encodeURIComponent(state.site)}/report?format=markdown`);
      const blob = await response.blob(); const url = URL.createObjectURL(blob);
      const link = element('a'); link.href = url; link.download = `setowa-${state.site}-report.md`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notice('Reviewed report downloaded.');
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = originalText;
    }
  }));

  $('toggle-json-report').addEventListener('click', () => {
    const view = $('report-json-view');
    view.hidden = !view.hidden;
    $('toggle-json-report').textContent = view.hidden ? 'View Raw JSON' : 'Hide Raw JSON';
  });

  const skillForm = $('skill-test-form');
  if (skillForm) {
    skillForm.addEventListener('submit', event => {
      event.preventDefault();
      run(async () => {
        if (!state.activeTestSkill) return;
        const skill = state.activeTestSkill;
        const form = event.currentTarget;
        const runBtn = $('run-skill-btn');
        const statusText = $('skill-run-status');
        const originalText = runBtn.textContent;
        runBtn.disabled = true;
        runBtn.textContent = 'Executing...';
        if (statusText) statusText.textContent = `Running ${skill.name}...`;

        try {
          const rawInputs = Object.fromEntries(new FormData(form));
          const inputs = {};
          for (const [k, v] of Object.entries(rawInputs)) {
            if (v !== '') inputs[k] = v;
          }

          const result = await request(`/skills/${encodeURIComponent(skill.name)}/execute`, {
            method: 'POST',
            json: {
              skill_name: skill.name,
              skill_version: skill.version,
              inputs: inputs,
              execution_context: { user_id: state.session || 'analyst' }
            }
          });

          const outputBox = $('skill-run-output');
          const metaBox = $('skill-result-meta');
          const jsonBox = $('skill-result-json');

          if (metaBox) {
            metaBox.replaceChildren();
            const statusBadge = element('span', `badge ${result.status === 'success' ? 'granted' : 'revoked'}`, result.status.toUpperCase());
            const latency = element('span', 'meta', `Latency: ${result.metadata?.latency_ms ?? 0}ms · Version: ${result.skill_version}`);
            metaBox.append(statusBadge, latency);
          }

          if (jsonBox) {
            jsonBox.textContent = JSON.stringify(result, null, 2);
          }

          if (outputBox) outputBox.hidden = false;
          notice(`Skill ${skill.name} executed: ${result.status.toUpperCase()}`);
        } finally {
          runBtn.disabled = false;
          runBtn.textContent = originalText;
          if (statusText) statusText.textContent = '';
        }
      });
    });
  }

  const closeTesterBtn = $('close-tester-btn');
  if (closeTesterBtn) {
    closeTesterBtn.addEventListener('click', () => {
      $('skill-tester-panel').hidden = true;
    });
  }

  // Workflow Studio Listeners
  const wfSelector = $('wf-selector');
  if (wfSelector) {
    wfSelector.addEventListener('change', (e) => {
      if (e.target.value) run(() => loadWorkflow(e.target.value));
    });
  }

  const wfNewBtn = $('wf-new-btn');
  if (wfNewBtn) {
    wfNewBtn.addEventListener('click', () => initNewWorkflow());
  }

  const wfValidateBtn = $('wf-validate-btn');
  if (wfValidateBtn) {
    wfValidateBtn.addEventListener('click', () => run(validateCurrentWorkflow));
  }

  const wfSaveBtn = $('wf-save-btn');
  if (wfSaveBtn) {
    wfSaveBtn.addEventListener('click', () => run(saveCurrentWorkflow));
  }

  const wfRunBtn = $('wf-run-btn');
  if (wfRunBtn) {
    wfRunBtn.addEventListener('click', () => prepareRunWorkflow());
  }

  const wfClearBtn = $('wf-clear-btn');
  if (wfClearBtn) {
    wfClearBtn.addEventListener('click', () => {
      if (state.currentWorkflow) {
        state.currentWorkflow.nodes = [];
        state.currentWorkflow.edges = [];
        state.selectedNodeId = null;
        renderWorkflowCanvas();
        renderNodeInspector();
        setWorkflowStatusBadge('Draft (Cleared)', '');
      }
    });
  }

  const wfExecForm = $('wf-exec-form');
  if (wfExecForm) {
    wfExecForm.addEventListener('submit', (e) => {
      e.preventDefault();
      run(() => executeCurrentWorkflow(e.currentTarget));
    });
  }

  // =========================================================================
  // T014 Setowa Field Video Ingestion & Frame Analytics
  // =========================================================================
  let activeVideoAsset = null;
  let activeVideoFrames = [];
  let activeVideoAnalysis = null;

  async function openVideoFramesModal(asset) {
    activeVideoAsset = asset;
    const modal = $('frames-modal');
    if (!modal) return;

    $('frames-modal-title').textContent = `Field Video: ${asset.original_filename || asset.asset_id}`;
    $('frames-modal-subtitle').textContent = `ID: ${asset.asset_id} · ${asset.width || '?'}×${asset.height || '?'} · Duration: ${formatDuration(asset.duration || 0)}`;

    const player = $('frames-video-player');
    if (player) {
      player.src = asset.secure_url;
      player.load();
    }

    $('extract-status-text').textContent = '';
    $('extract-status-text').className = 'status-indicator';
    $('analyze-status-text').textContent = '';
    $('analyze-status-text').className = 'status-indicator';

    if (typeof modal.showModal === 'function') modal.showModal();
    else modal.setAttribute('open', '');

    await loadVideoFramesAndAnalysis(asset.asset_id);
  }

  function closeVideoFramesModal() {
    const modal = $('frames-modal');
    const player = $('frames-video-player');
    if (player) {
      player.pause();
      player.removeAttribute('src');
    }
    if (typeof modal.close === 'function') modal.close();
    else modal.removeAttribute('open');
    activeVideoAsset = null;
    activeVideoFrames = [];
    activeVideoAnalysis = null;
  }

  async function loadVideoFramesAndAnalysis(assetId) {
    try {
      const [frames, analysis] = await Promise.all([
        request(`/media/${assetId}/frames`).catch(() => []),
        request(`/media/${assetId}/frame-analysis`).catch(() => null),
      ]);
      activeVideoFrames = Array.isArray(frames) ? frames : [];
      activeVideoAnalysis = analysis;
      renderVideoFramesTimeline(activeVideoFrames, activeVideoAnalysis);
    } catch (err) {
      console.warn('Could not load frame data:', err);
    }
  }

  function renderVideoFramesTimeline(frames, analysis) {
    const container = $('frames-timeline-container');
    const countBadge = $('frames-count-badge');
    const summaryCard = $('frames-summary-card');

    if (!container) return;
    container.replaceChildren();

    if (countBadge) {
      countBadge.textContent = `${frames.length} frame${frames.length === 1 ? '' : 's'}`;
    }

    // Render aggregated analysis summary if available
    if (analysis && analysis.total_analyzed > 0) {
      summaryCard.hidden = false;
      const statusBadge = $('summary-status-badge');
      statusBadge.textContent = (analysis.status || 'analyzed').toUpperCase();
      statusBadge.className = `badge ${analysis.status === 'analyzed' ? 'success' : 'uncertain'}`;

      $('summary-text').textContent = analysis.summary || 'Frame observation completed.';

      const signalsBox = $('summary-signals-tags');
      signalsBox.replaceChildren();
      for (const sig of (analysis.aggregated_signals || [])) {
        signalsBox.append(element('span', 'signal-pill', `#${sig}`));
      }

      const warnBox = $('summary-warnings-box');
      if (analysis.warnings && analysis.warnings.length) {
        warnBox.hidden = false;
        warnBox.textContent = `⚠ ${analysis.warnings.join(' · ')}`;
      } else {
        warnBox.hidden = true;
      }
    } else {
      if (summaryCard) summaryCard.hidden = true;
    }

    if (!frames.length) {
      container.className = 'frames-timeline-container empty';
      container.textContent = 'No frames extracted yet. Choose a sampling strategy and click "Extract Frames".';
      return;
    }

    container.className = 'frames-timeline-container';

    // Map frame analysis by frame_id
    const analysisByFrame = {};
    if (analysis && analysis.frames) {
      for (const f of analysis.frames) {
        analysisByFrame[f.frame_id] = f;
      }
    }

    for (const frame of frames) {
      const card = element('div', 'frame-timeline-card');

      // Left: Thumbnail with timestamp
      const thumbCol = element('div', 'frame-thumb-col');
      const img = element('img');
      img.src = frame.thumbnail_url || frame.frame_url;
      img.alt = `Frame at ${frame.timestamp_seconds}s`;
      img.loading = 'lazy';
      thumbCol.append(img);

      const tsPill = element('span', 'frame-ts-pill', `@ ${frame.timestamp_seconds.toFixed(2)}s`);
      thumbCol.append(tsPill);

      thumbCol.addEventListener('click', () => {
        openLightbox(
          frame.frame_url,
          `Video Frame @ ${frame.timestamp_seconds.toFixed(2)}s`,
          `Frame ID: ${frame.frame_id} · Source: ${frame.source_video_url}`,
          'FRAME',
          'granted',
          'image'
        );
      });
      card.append(thumbCol);

      // Right: Body with provenance and analysis details
      const bodyCol = element('div', 'frame-body-col');

      const bodyTop = element('div', 'frame-body-top');
      const fid = element('span', 'frame-id-text', frame.frame_id);
      const badgesWrap = element('div', 'frame-badges-wrap');

      const frameAnl = analysisByFrame[frame.frame_id];
      if (frameAnl) {
        const anlBadge = element('span', `badge ${frameAnl.status === 'analyzed' ? 'success' : 'uncertain'}`, (frameAnl.status || 'analyzed').toUpperCase());
        badgesWrap.append(anlBadge);
        if (frameAnl.confidence !== null && frameAnl.confidence !== undefined) {
          const confBadge = element('span', 'delivery-pill', `${Math.round(frameAnl.confidence * 100)}% cert.`);
          badgesWrap.append(confBadge);
        }
      } else {
        badgesWrap.append(element('span', 'badge pending', 'PENDING ANALYSIS'));
      }
      bodyTop.append(fid, badgesWrap);
      bodyCol.append(bodyTop);

      // Signals & Observations
      if (frameAnl) {
        if (frameAnl.detected_signals && frameAnl.detected_signals.length) {
          const sigsRow = element('div', 'frame-signals-row');
          for (const s of frameAnl.detected_signals) {
            sigsRow.append(element('span', 'signal-pill', `#${s}`));
          }
          bodyCol.append(sigsRow);
        }

        if (frameAnl.observations && frameAnl.observations.length) {
          const obsList = element('ul', 'frame-obs-list');
          for (const o of frameAnl.observations) {
            obsList.append(element('li', '', o));
          }
          bodyCol.append(obsList);
        }

        if (frameAnl.warnings && frameAnl.warnings.length) {
          const warnText = element('p', 'frame-warnings-list', `⚠ ${frameAnl.warnings.join(' · ')}`);
          bodyCol.append(warnText);
        }
      } else {
        const pendingNote = element('p', 'meta', 'Extracted via Cloudinary offset transform. Ready for visual AI observation.');
        bodyCol.append(pendingNote);
      }

      // Single frame analyze action
      const actionRow = element('div', 'frame-action-row');
      const singleAnalyzeBtn = element('button', 'button quiet button-small', 'Analyze This Frame');
      singleAnalyzeBtn.type = 'button';
      singleAnalyzeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        run(() => analyzeFramesForActiveVideo([frame.frame_id]));
      });
      actionRow.append(singleAnalyzeBtn);
      bodyCol.append(actionRow);

      card.append(bodyCol);
      container.append(card);
    }
  }

  async function extractFramesForActiveVideo() {
    if (!activeVideoAsset) return;
    const statusText = $('extract-status-text');
    const strat = $('frame-strategy-select').value;
    const paramVal = parseFloat($('frame-param-input').value) || 2.0;
    const maxVal = parseInt($('frame-max-input').value, 10) || 20;

    statusText.textContent = 'Extracting frames via Cloudinary...';
    statusText.className = 'status-indicator loading';

    const payload = {
      strategy: strat,
      max_frames: maxVal,
    };
    if (strat === 'interval') {
      payload.interval_seconds = paramVal;
    } else {
      payload.frame_count = parseInt(paramVal, 10) || 5;
    }

    try {
      const resp = await request(`/media/${activeVideoAsset.asset_id}/frames/extract`, {
        method: 'POST',
        json: payload,
      });
      statusText.textContent = `✓ Extracted ${resp.total_frames} frames`;
      statusText.className = 'status-indicator success';
      activeVideoFrames = resp.frames || [];
      renderVideoFramesTimeline(activeVideoFrames, activeVideoAnalysis);
      notice(`Successfully extracted ${resp.total_frames} frames from video.`);
    } catch (err) {
      statusText.textContent = 'Extraction failed';
      statusText.className = 'status-indicator error';
      throw err;
    }
  }

  async function analyzeFramesForActiveVideo(frameIds = null) {
    if (!activeVideoAsset) return;
    const statusText = $('analyze-status-text');
    statusText.textContent = 'Analyzing frames via SkillRuntime...';
    statusText.className = 'status-indicator loading';

    const payload = {};
    if (frameIds && frameIds.length) {
      payload.frame_ids = frameIds;
    }

    try {
      const report = await request(`/media/${activeVideoAsset.asset_id}/frames/analyze`, {
        method: 'POST',
        json: payload,
      });
      statusText.textContent = `✓ Analyzed ${report.total_analyzed} frames`;
      statusText.className = 'status-indicator success';
      activeVideoAnalysis = report;
      renderVideoFramesTimeline(activeVideoFrames, activeVideoAnalysis);
      notice(`Analyzed ${report.total_analyzed} frames with field-frame-observation skill.`);
    } catch (err) {
      statusText.textContent = 'Analysis failed';
      statusText.className = 'status-indicator error';
      throw err;
    }
  }

  // Frame Analytics Listeners
  const frameStratSelect = $('frame-strategy-select');
  if (frameStratSelect) {
    frameStratSelect.addEventListener('change', (e) => {
      const lbl = $('frame-param-label');
      const inp = $('frame-param-input');
      if (e.target.value === 'interval') {
        if (lbl) lbl.childNodes[0].textContent = 'Interval (Seconds)';
        if (inp) { inp.min = '0.5'; inp.max = '30'; inp.step = '0.5'; inp.value = '2.0'; }
      } else {
        if (lbl) lbl.childNodes[0].textContent = 'Frame Count';
        if (inp) { inp.min = '1'; inp.max = '60'; inp.step = '1'; inp.value = '5'; }
      }
    });
  }

  const btnExtractFrames = $('btn-extract-frames');
  if (btnExtractFrames) {
    btnExtractFrames.addEventListener('click', () => run(extractFramesForActiveVideo));
  }

  const btnAnalyzeFrames = $('btn-analyze-frames');
  if (btnAnalyzeFrames) {
    btnAnalyzeFrames.addEventListener('click', () => run(() => analyzeFramesForActiveVideo()));
  }

  const framesCloseBtn = $('frames-close-btn');
  if (framesCloseBtn) {
    framesCloseBtn.addEventListener('click', () => closeVideoFramesModal());
  }

  // =========================================================================
  // T016 AI Media Intelligence & Discovery Foundation
  // =========================================================================
  let activeIntelAsset = null;
  let activeIntelRecord = null;

  async function openIntelligenceModal(asset, intelRecord) {
    activeIntelAsset = asset;
    activeIntelRecord = intelRecord;
    const modal = $('intelligence-modal');
    if (!modal) return;

    $('intel-modal-title').textContent = `Media Intelligence: ${asset.original_filename || asset.asset_id}`;
    const img = $('intel-preview-img');
    if (img) {
      img.src = asset.preview_url || asset.thumbnail_url || asset.secure_url;
      img.alt = asset.original_filename || asset.asset_id;
    }

    renderIntelligenceModalContent(asset, intelRecord);

    if (typeof modal.showModal === 'function') modal.showModal();
    else modal.setAttribute('open', '');

    try {
      const [latest, history] = await Promise.all([
        request(`/media/${asset.asset_id}/intelligence`).catch(() => intelRecord),
        request(`/media/${asset.asset_id}/intelligence/history`).catch(() => []),
      ]);
      if (latest) {
        state.mediaIntelligence[asset.asset_id] = latest;
        activeIntelRecord = latest;
        renderIntelligenceModalContent(asset, latest);
      }
      renderIntelligenceHistory(history);
    } catch (e) {
      console.warn('Could not refresh intelligence data:', e);
    }
  }

  function renderIntelligenceModalContent(asset, intel) {
    const provInfo = $('intel-provenance-info');
    if (provInfo) {
      provInfo.innerHTML = `
        <strong>Asset ID:</strong> ${asset.asset_id}<br>
        <strong>Media Type:</strong> ${(asset.media_type || 'image').toUpperCase()}<br>
        <strong>Dimensions:</strong> ${asset.width || '?'}×${asset.height || '?'} · ${asset.format ? asset.format.toUpperCase() : ''}<br>
        <strong>Source:</strong> ${asset.source || 'Unspecified'}<br>
        <strong>Model:</strong> ${intel ? (intel.model_name || 'Gemini Vision') : 'Pending Analysis'}<br>
        <strong>Analyzed At:</strong> ${intel ? (intel.created_at || '').slice(0, 19).replace('T', ' ') : 'Not yet analyzed'}
      `;
    }

    const badge = $('intel-status-badge');
    const status = intel ? (intel.status || 'analyzed') : 'pending';
    badge.textContent = status.toUpperCase();
    badge.className = `badge ${status === 'analyzed' ? 'success' : (status === 'uncertain' ? 'uncertain' : 'danger')}`;

    $('intel-description-text').textContent = intel ? (intel.description || 'No description provided.') : 'Asset has not been analyzed with AI visual intelligence yet.';

    const obsList = $('intel-observations-list');
    obsList.replaceChildren();
    if (intel && intel.observations && intel.observations.length) {
      for (const obs of intel.observations) {
        const li = element('li', '', obs);
        obsList.append(li);
      }
    } else {
      obsList.append(element('li', 'meta', 'No specific observations recorded.'));
    }

    const tagsContainer = $('intel-tags-container');
    tagsContainer.replaceChildren();
    if (intel && intel.tags && intel.tags.length) {
      for (const t of intel.tags) {
        tagsContainer.append(element('span', 'delivery-pill', `#${t}`));
      }
    } else {
      tagsContainer.append(element('span', 'meta', 'No tags detected.'));
    }

    const sigsContainer = $('intel-signals-container');
    sigsContainer.replaceChildren();
    if (intel && intel.signals && intel.signals.length) {
      for (const s of intel.signals) {
        sigsContainer.append(element('span', 'signal-pill', s));
      }
    } else {
      sigsContainer.append(element('span', 'meta', 'No visual signals detected.'));
    }

    const actWrap = $('intel-activity-wrap');
    if (intel && intel.activity) {
      actWrap.hidden = false;
      $('intel-activity-pill').textContent = intel.activity;
    } else {
      actWrap.hidden = true;
    }

    const uncBox = $('intel-uncertainty-box');
    if (intel && intel.uncertainty) {
      uncBox.hidden = false;
      $('intel-uncertainty-text').textContent = intel.uncertainty;
    } else {
      uncBox.hidden = true;
    }

    const warnBox = $('intel-warnings-box');
    const warnList = $('intel-warnings-list');
    warnList.replaceChildren();
    if (intel && intel.warnings && intel.warnings.length) {
      warnBox.hidden = false;
      for (const w of intel.warnings) {
        warnList.append(element('li', '', w));
      }
    } else {
      warnBox.hidden = true;
    }
  }

  function renderIntelligenceHistory(history) {
    const histContainer = $('intel-history-container');
    if (!histContainer) return;
    histContainer.replaceChildren();

    if (!history || !history.length) {
      histContainer.textContent = 'No previous revisions for this asset.';
      return;
    }

    const list = element('div', 'intel-history-list');
    for (const h of history) {
      const item = element('div', 'intel-history-item', `
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <strong>${(h.status || 'analyzed').toUpperCase()}</strong>
          <span class="meta">${(h.created_at || '').slice(0, 19).replace('T', ' ')}</span>
        </div>
        <p style="margin:2px 0;">${h.description || ''}</p>
        <span class="meta">Model: ${h.model_name || 'gemini'} · Tags: ${(h.tags || []).join(', ') || 'none'}</span>
      `);
      list.append(item);
    }
    histContainer.append(list);
  }

  function closeIntelligenceModal() {
    const modal = $('intelligence-modal');
    if (!modal) return;
    if (typeof modal.close === 'function') modal.close();
    else modal.removeAttribute('open');
    activeIntelAsset = null;
    activeIntelRecord = null;
  }

  async function triggerAnalyzeMedia(assetId, forceReanalyze = false) {
    const statusIndicator = $('reanalyze-status-text');
    if (statusIndicator) {
      statusIndicator.textContent = forceReanalyze ? 'Re-analyzing...' : 'Analyzing...';
      statusIndicator.className = 'status-indicator loading';
    }
    notice(forceReanalyze ? 'Re-analyzing media with Gemini vision intelligence...' : 'Analyzing media with Gemini vision intelligence...');

    try {
      const endpoint = forceReanalyze ? `/media/${assetId}/reanalyze` : `/media/${assetId}/analyze`;
      const result = await request(endpoint, {
        method: 'POST',
        json: { force_reanalyze: forceReanalyze },
      });
      state.mediaIntelligence[assetId] = result;
      if (result.status === 'analyzed') {
        notice(`Intelligence analysis complete: ${result.tags?.length || 0} tags / ${(result.signals || []).length} signals detected`, 'success');
        if (statusIndicator) {
          statusIndicator.textContent = `Completed (${result.status})`;
          statusIndicator.className = 'status-indicator success';
        }
      } else if (result.status === 'uncertain') {
        notice(`Intelligence analysis uncertain: ${result.uncertainty || 'Inconclusive visual evidence'}`, 'warn');
        if (statusIndicator) {
          statusIndicator.textContent = 'Uncertain';
          statusIndicator.className = 'status-indicator warn';
        }
      } else if (result.status === 'insufficient_evidence') {
        notice('Intelligence analysis: Insufficient visual evidence to confirm cleanup', 'warn');
        if (statusIndicator) {
          statusIndicator.textContent = 'Insufficient Evidence';
          statusIndicator.className = 'status-indicator warn';
        }
      } else {
        notice(`Intelligence analysis failed: ${result.uncertainty || (result.warnings && result.warnings[0]) || 'Analysis failed'}`, 'error');
        if (statusIndicator) {
          statusIndicator.textContent = 'Failed';
          statusIndicator.className = 'status-indicator error';
        }
      }
      renderMediaLibrary();
      if (activeIntelAsset && activeIntelAsset.asset_id === assetId) {
        activeIntelRecord = result;
        renderIntelligenceModalContent(activeIntelAsset, result);
        const history = await request(`/media/${assetId}/intelligence/history`).catch(() => []);
        renderIntelligenceHistory(history);
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      const msg = sanitizeErrorMessage(err.message || String(err));
      notice(`Analysis failed: ${msg}`, 'error');
      if (statusIndicator) {
        statusIndicator.textContent = `Failed: ${msg}`;
        statusIndicator.className = 'status-indicator error';
      }
    }
  }

  // T016 Filter and Modal Listeners
  if ($('media-ai-status-filter')) $('media-ai-status-filter').addEventListener('change', renderMediaLibrary);
  if ($('media-tag-input')) $('media-tag-input').addEventListener('input', renderMediaLibrary);
  const closeIntelBtn = $('close-intel-modal');
  if (closeIntelBtn) closeIntelBtn.addEventListener('click', closeIntelligenceModal);
  const reanalyzeBtn = $('btn-reanalyze-asset');
  if (reanalyzeBtn) {
    reanalyzeBtn.addEventListener('click', () => {
      if (activeIntelAsset) triggerAnalyzeMedia(activeIntelAsset.asset_id, true);
    });
  }

  // ==========================================================================
  // Milestone T017: Sustainability Timeline & Impact Story
  // ==========================================================================

  async function loadImpactStoryTab() {
    if (!state.site) return;
    const projectId = (state.siteRecord && state.siteRecord.project_id) || state.site;

    if ($('impact-project-name')) {
      $('impact-project-name').textContent = (state.siteRecord && state.siteRecord.name) || state.site;
    }

    notice('Loading impact story and sustainability timeline...');

    try {
      const story = await request(`/projects/${encodeURIComponent(projectId)}/impact-story`);
      state.impactStory = story;
      renderImpactStory(story);
      notice('');
    } catch (err) {
      if (err.message && err.message.includes('404')) {
        state.impactStory = null;
        renderEmptyImpactStory(projectId);
        notice('');
      } else {
        console.error('Failed to load impact story:', err);
        notice(`Failed to load impact story: ${sanitizeErrorMessage(err.message || String(err))}`, 'error');
      }
    }
  }

  function renderEmptyImpactStory(projectId) {
    if ($('impact-metric-events')) $('impact-metric-events').textContent = '0';
    if ($('impact-metric-media')) $('impact-metric-media').textContent = '0';
    if ($('impact-metric-verified')) $('impact-metric-verified').textContent = '0';
    if ($('impact-metric-measurements')) $('impact-metric-measurements').textContent = '0';
    if ($('impact-date-range')) $('impact-date-range').textContent = 'Date range: Not generated yet';

    if ($('impact-narrative-text')) {
      $('impact-narrative-text').innerHTML = `
        <p class="muted">No impact story generated for this project yet. Click <strong>Generate Story</strong> above to synthesize your persisted field media, before/after evidence comparisons, and human-approved observations.</p>
      `;
    }
    if ($('impact-uncertainty-callout')) $('impact-uncertainty-callout').hidden = true;

    const cardsContainer = $('impact-cards-container');
    if (cardsContainer) {
      cardsContainer.className = 'impact-cards-grid empty';
      cardsContainer.textContent = 'No before/after cards generated yet. Click Generate Story above.';
    }

    const timelineContainer = $('impact-timeline-container');
    if (timelineContainer) {
      timelineContainer.innerHTML = '<div class="empty-state">No timeline events generated yet. Click Generate Story above.</div>';
    }

    renderShareControls(null);
  }

  function renderImpactStory(story) {
    if (!story) return;

    if ($('impact-project-name')) $('impact-project-name').textContent = story.title || (state.siteRecord && state.siteRecord.name) || state.site;
    const dateRange = story.date_range && (story.date_range.start || story.date_range.start_date || story.date_range.end || story.date_range.end_date)
      ? `${story.date_range.start || story.date_range.start_date || 'date unknown'} → ${story.date_range.end || story.date_range.end_date || 'date unknown'}`
      : 'dates not recorded';
    if ($('impact-date-range')) $('impact-date-range').textContent = `Evidence Period: ${dateRange}`;

    const metrics = story.metrics || {};
    const events = story.events || [];
    const cards = story.before_after_cards || [];
    const eventCount = metrics.event_count ?? events.length;
    const mediaCount = metrics.media_count ?? (new Set(events.flatMap(e => e.asset_ids || []))).size;
    const verifiedCount = metrics.approved_findings_count ?? cards.filter(c => c.verification_status === 'approved').length;
    const measurementCount = metrics.measurement_count ?? events.filter(e => e.event_type === 'measurement').length;

    if ($('impact-metric-events')) $('impact-metric-events').textContent = String(eventCount);
    if ($('impact-metric-media')) $('impact-metric-media').textContent = String(mediaCount);
    if ($('impact-metric-verified')) $('impact-metric-verified').textContent = String(verifiedCount);
    if ($('impact-metric-measurements')) $('impact-metric-measurements').textContent = String(measurementCount);

    if ($('impact-status-pill')) {
      $('impact-status-pill').textContent = (story.status || 'draft').toUpperCase();
      $('impact-status-pill').className = `badge ${story.status === 'published' ? 'approved' : 'pending'}`;
    }
    if ($('impact-status-select')) {
      $('impact-status-select').value = story.status || 'draft';
    }

    if ($('impact-narrative-text')) {
      if (story.summary_narrative) {
        const paras = story.summary_narrative.split('\n\n').filter(p => p.trim());
        $('impact-narrative-text').replaceChildren();
        for (const p of paras) {
          $('impact-narrative-text').appendChild(element('p', '', p.trim()));
        }
      } else {
        $('impact-narrative-text').innerHTML = '<p class="muted">No narrative text generated.</p>';
      }
    }

    if ($('impact-uncertainty-callout') && $('impact-uncertainty-text')) {
      if (story.uncertainty_note && story.uncertainty_note.trim()) {
        $('impact-uncertainty-text').textContent = story.uncertainty_note;
        $('impact-uncertainty-callout').hidden = false;
      } else {
        $('impact-uncertainty-callout').hidden = true;
      }
    }

    renderShareControls(story);
    renderBeforeAfterCards(story.before_after_cards || []);
    renderTimelineEvents(story.events || []);
  }

  function renderBeforeAfterCards(cards) {
    const container = $('impact-cards-container');
    if (!container) return;
    container.replaceChildren();

    if (!cards || !cards.length) {
      container.className = 'impact-cards-grid empty';
      container.textContent = 'No before/after comparison records available for this project.';
      return;
    }

    container.className = 'impact-cards-grid';

    for (const card of cards) {
      const cardEl = element('article', 'impact-card');

      const header = element('div', 'impact-card-header');
      const titleSpan = element('strong', '', card.site_name || card.site_id || 'Restoration Site');
      const badge = element('span', `badge ${card.verification_status === 'approved' ? 'approved' : card.verification_status === 'rejected' ? 'rejected' : 'pending'}`);
      badge.textContent = card.verification_status === 'approved' ? 'Approved Finding' : card.verification_status === 'rejected' ? 'Rejected' : 'Pending Review';
      header.append(titleSpan, badge);

      const mediaRow = element('div', 'impact-card-media-row');

      const beforePhoto = element('div', 'impact-card-photo');
      const beforeImg = element('img');
      beforeImg.src = card.before_thumbnail_url || card.before_media_url;
      beforeImg.alt = 'Before restoration state';
      beforeImg.loading = 'lazy';
      beforePhoto.append(beforeImg, element('span', '', 'BEFORE'));
      beforePhoto.addEventListener('click', () => {
        openLightbox(card.before_media_url, `Before: ${card.site_name || card.site_id}`, 'Baseline field evidence');
      });

      const afterPhoto = element('div', 'impact-card-photo');
      const afterImg = element('img');
      afterImg.src = card.after_thumbnail_url || card.after_media_url;
      afterImg.alt = 'After restoration state';
      afterImg.loading = 'lazy';
      afterPhoto.append(afterImg, element('span', '', 'AFTER'));
      afterPhoto.addEventListener('click', () => {
        openLightbox(card.after_media_url, `After: ${card.site_name || card.site_id}`, 'Subsequent field evidence');
      });

      mediaRow.append(beforePhoto, afterPhoto);

      const details = element('div', 'impact-card-details');
      const textP = element('p', 'impact-card-text', card.approved_text || card.working_text || card.ai_draft || 'Comparison recorded.');
      details.append(textP);

      if (card.uncertainty) {
        const uBox = element('div', 'warning-callout', `⚠️ Caveat: ${card.uncertainty}`);
        details.append(uBox);
      }

      const footer = element('div', 'impact-card-footer');
      const reviewer = card.reviewed_by ? `Approved by ${card.reviewed_by}` : 'AI Proposal (Unverified)';
      const dateStr = (card.reviewed_at || card.updated_at || '').slice(0, 10);
      footer.append(element('span', '', reviewer), element('span', '', dateStr));

      cardEl.append(header, mediaRow, details, footer);
      container.append(cardEl);
    }
  }

  function renderTimelineEvents(events) {
    const container = $('impact-timeline-container');
    if (!container) return;
    container.replaceChildren();

    if (!events || !events.length) {
      container.innerHTML = '<div class="empty-state">No timeline events recorded yet.</div>';
      return;
    }

    for (const ev of events) {
      const item = element('div', 'timeline-event-item');

      const marker = element('div', `timeline-event-marker ${ev.event_type || 'milestone'}`);
      item.append(marker);

      const top = element('div', 'timeline-event-top');
      const titleRow = element('div', 'timeline-event-title-row');
      const typeBadge = element('span', `event-type-badge ${ev.event_type || 'milestone'}`, (ev.event_type || 'event').replace('_', ' '));
      const h4 = element('h4', '', ev.title || 'Timeline Event');
      titleRow.append(typeBadge, h4);

      const dateMeta = element('span', 'meta', ev.timestamp_date || 'Undated');
      top.append(titleRow, dateMeta);
      item.append(top);

      const body = element('div', 'timeline-event-body');

      if (ev.primary_media_url) {
        const thumbWrap = element('div', 'timeline-media-thumb');
        const img = element('img');
        img.src = ev.thumbnail_url || ev.primary_media_url;
        img.alt = ev.title || 'Timeline evidence photo';
        img.loading = 'lazy';
        thumbWrap.append(img);

        const isVideo = ev.media_type === 'video' || (ev.primary_media_url && ev.primary_media_url.endsWith('.mp4'));
        if (isVideo) {
          const icon = element('div', 'vid-icon', '▶');
          thumbWrap.append(icon);
          thumbWrap.addEventListener('click', () => {
            openLightbox(ev.thumbnail_url, ev.title, ev.description, 'Granted', 'granted', 'video', ev.primary_media_url);
          });
        } else {
          thumbWrap.addEventListener('click', () => {
            openLightbox(ev.primary_media_url, ev.title, ev.description, 'Granted', 'granted', 'image');
          });
        }
        body.append(thumbWrap);
      }

      const descCol = element('div', 'timeline-event-desc');
      if (ev.description) {
        descCol.append(element('p', '', ev.description));
      }

      if (ev.observations && ev.observations.length) {
        const obsList = element('ul', 'timeline-event-observations');
        for (const obs of ev.observations) {
          const cleanObs = obs.replace(/^OBSERVED:\s*/i, '');
          obsList.append(element('li', '', `• ${cleanObs}`));
        }
        descCol.append(obsList);
      }

      body.append(descCol);
      item.append(body);

      const footer = element('div', 'timeline-event-footer');
      const siteText = ev.site_name || ev.site_id ? `Site: ${ev.site_name || ev.site_id}` : 'Project Scope';
      const verifStatus = ev.verification_status ? `Status: ${ev.verification_status}` : '';
      footer.append(element('span', '', siteText), element('span', '', verifStatus));

      item.append(footer);
      container.append(item);
    }
  }

  async function generateImpactStoryAction() {
    if (!state.site) return;
    const projectId = (state.siteRecord && state.siteRecord.project_id) || state.site;
    const btn = $('btn-generate-impact');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Generating...';
    }
    notice('Synthesizing project timeline, media intelligence, and verified evidence...');

    try {
      const story = await request(`/projects/${encodeURIComponent(projectId)}/impact-story/generate`, {
        method: 'POST',
        json: { force_regenerate: true },
      });
      state.impactStory = story;
      renderImpactStory(story);
      notice('Impact story generated. Review evidence and approval states before sharing.', 'success');
    } catch (err) {
      console.error('Failed to generate impact story:', err);
      notice(`Story generation failed: ${sanitizeErrorMessage(err.message || String(err))}`, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Generate Story →';
      }
    }
  }

  async function updateStoryStatusAction(newStatus) {
    if (!state.impactStory || !state.impactStory.id) return;
    try {
      const updated = await request(`/impact-stories/${encodeURIComponent(state.impactStory.id)}`, {
        method: 'PUT',
        json: { status: newStatus },
      });
      state.impactStory = updated;
      renderImpactStory(updated);
      notice(`Story status updated to ${newStatus}`);
    } catch (err) {
      console.error('Failed to update story status:', err);
      notice(`Failed to update status: ${sanitizeErrorMessage(err)}`, true);
    }
  }

  // ==========================================================================
  // Milestone T018: Public Share Experience Controls
  // ==========================================================================

  function renderShareControls(story) {
    const isPublished = story && story.status === 'published';
    const shareToken = story ? story.share_token : null;
    const sharePath = story && story.share_url ? story.share_url : (shareToken ? `/share/${shareToken}` : null);
    const fullShareUrl = sharePath ? `${window.location.origin}${sharePath}` : null;

    const icon = $('share-status-icon');
    const label = $('share-status-label');
    const display = $('share-url-display');
    const openBtn = $('btn-open-public-story');
    const copyBtn = $('btn-copy-share-link');
    const rotateBtn = $('btn-rotate-share-link');
    const revokeBtn = $('btn-revoke-share-link');
    const topOpenBtn = $('btn-top-open-public');

    if (!story) {
      if (icon) icon.textContent = '🔒';
      if (label) label.textContent = 'Private';
      if (display) display.textContent = 'Story must be generated and published to share publicly.';
      if (openBtn) openBtn.disabled = true;
      if (copyBtn) copyBtn.disabled = true;
      if (rotateBtn) rotateBtn.disabled = true;
      if (revokeBtn) revokeBtn.disabled = true;
      if (topOpenBtn) topOpenBtn.hidden = true;
      return;
    }

    if (isPublished && shareToken) {
      if (icon) icon.textContent = '🌐';
      if (label) label.textContent = 'Published & Public';
      if (display) {
        display.innerHTML = `<a href="/share/${encodeURIComponent(shareToken)}" target="_blank" rel="noopener" style="color:var(--brand-primary,#0284c7); text-decoration:underline;">${fullShareUrl}</a>`;
      }
      if (openBtn) {
        openBtn.disabled = false;
        openBtn.onclick = () => window.open(`/share/${encodeURIComponent(shareToken)}`, '_blank', 'noopener');
      }
      if (copyBtn) {
        copyBtn.disabled = false;
        copyBtn.onclick = async () => {
          try {
            await navigator.clipboard.writeText(fullShareUrl);
            notice('Public share link copied to clipboard!');
          } catch {
            prompt('Public Share Link:', fullShareUrl);
          }
        };
      }
      if (rotateBtn) {
        rotateBtn.disabled = false;
        rotateBtn.onclick = rotateShareLinkAction;
      }
      if (revokeBtn) {
        revokeBtn.disabled = false;
        revokeBtn.onclick = revokeShareLinkAction;
      }
      if (topOpenBtn) {
        topOpenBtn.hidden = false;
        topOpenBtn.onclick = () => window.open(`/share/${encodeURIComponent(shareToken)}`, '_blank', 'noopener');
      }
    } else {
      if (icon) icon.textContent = '🔒';
      const statusLabel = (story.status || 'draft').replace('_', ' ').toUpperCase();
      if (label) label.textContent = `Private (${statusLabel})`;
      if (display) {
        display.textContent = 'Public sharing is gated. Change status to "Published" above to enable public access.';
      }
      if (openBtn) openBtn.disabled = true;
      if (copyBtn) copyBtn.disabled = true;
      if (rotateBtn) rotateBtn.disabled = true;
      if (revokeBtn) revokeBtn.disabled = true;
      if (topOpenBtn) topOpenBtn.hidden = true;
    }
  }

  async function rotateShareLinkAction() {
    if (!state.impactStory || !state.impactStory.id) return;
    if (!confirm('Rotate share link? The current link will immediately stop working.')) return;
    try {
      const res = await request(`/impact-stories/${encodeURIComponent(state.impactStory.id)}/share/rotate`, {
        method: 'POST',
      });
      state.impactStory.share_token = res.share_token;
      state.impactStory.share_url = res.share_url;
      renderShareControls(state.impactStory);
      notice('Share link rotated successfully! Old links are now invalid.');
    } catch (err) {
      console.error('Failed to rotate share link:', err);
      notice(`Failed to rotate link: ${sanitizeErrorMessage(err)}`, true);
    }
  }

  async function revokeShareLinkAction() {
    if (!state.impactStory || !state.impactStory.id) return;
    if (!confirm('Revoke public access? The story will no longer be accessible via any public link.')) return;
    try {
      const res = await request(`/impact-stories/${encodeURIComponent(state.impactStory.id)}/share/revoke`, {
        method: 'POST',
      });
      state.impactStory.share_token = null;
      state.impactStory.share_url = null;
      renderShareControls(state.impactStory);
      notice('Public access revoked. The story is now private.');
    } catch (err) {
      console.error('Failed to revoke share link:', err);
      notice(`Failed to revoke link: ${sanitizeErrorMessage(err)}`, true);
    }
  }

  function activeProjectId() {
    return (state.siteRecord && state.siteRecord.project_id) || state.site;
  }

  function appendEvidenceLinks(container, evidence) {
    for (const item of evidence || []) {
      if (!item.url) continue;
      let url;
      try { url = new URL(item.url, location.origin); } catch (_) { continue; }
      if (!['https:', 'http:'].includes(url.protocol)) continue;
      const link = element('a', '', item.role ? `${item.role} photo` : 'View source media');
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      container.append(link, document.createTextNode('  '));
    }
  }

  $('semantic-search-form').addEventListener('submit', (event) => run(async () => {
    event.preventDefault();
    const query = $('semantic-query').value.trim();
    if (query.length < 3) return;
    const button = $('semantic-search-form').querySelector('button');
    button.disabled = true;
    $('semantic-search-status').textContent = 'Embedding current project records and searching…';
    try {
      const result = await request(`/projects/${encodeURIComponent(activeProjectId())}/semantic-search`,
        { method: 'POST', json: { query, limit: 8 } });
      const box = $('semantic-search-results');
      box.replaceChildren();
      $('semantic-search-status').textContent = result.results.length
        ? `${result.results.length} result(s) · ${result.indexed} record(s) newly embedded${result.truncated ? ` · collection limit reached (${result.max_documents} records)` : ''}`
        : 'No searchable records in this project yet.';
      for (const hit of result.results) {
        const card = element('article', 'paper-card discovery-result');
        const heading = element('h3', '', `${hit.kind.replaceAll('_', ' ')} · ${hit.site_id || 'project'}`);
        const status = element('p', 'meta', `Status: ${hit.review_status.replaceAll('_', ' ')} · similarity ${hit.score.toFixed(2)}`);
        const body = element('p', '', hit.text);
        card.append(heading, status, body);
        appendEvidenceLinks(card, hit.evidence);
        box.append(card);
      }
    } catch (error) {
      $('semantic-search-status').textContent = sanitizeErrorMessage(error.message);
      throw error;
    } finally { button.disabled = false; }
  }));

  function renderCampaignDrafts(drafts) {
    const box = $('campaign-drafts');
    box.replaceChildren();
    if (!drafts.length) {
      box.append(element('p', 'meta', 'No drafts yet. Approve an observation or record a sourced measurement first.'));
      return;
    }
    for (const draft of drafts) {
      const card = element('article', 'paper-card discovery-result');
      card.append(element('h3', '', draft.title));
      card.append(element('p', 'meta',
        `${draft.channel.replaceAll('_', ' ')} · DRAFT${draft.demo_only ? ' · SYNTHETIC DEMO' : ''}${draft.stale ? ' · STALE: source records changed' : ''}`));
      const copy = element('div', 'campaign-copy', draft.body);
      const button = element('button', 'button secondary', 'Copy draft');
      button.type = 'button';
      button.addEventListener('click', () => run(async () => {
        await navigator.clipboard.writeText(draft.body);
        notice('Draft copied. Check evidence before sharing.', 'success');
      }));
      card.append(copy, button);
      box.append(card);
    }
  }

  async function loadCampaignDrafts() {
    if (!state.site) return;
    try {
      const drafts = await request(`/projects/${encodeURIComponent(activeProjectId())}/campaign-drafts`);
      $('campaign-status').textContent = `${drafts.length} saved local draft(s). Nothing is published automatically.`;
      renderCampaignDrafts(drafts);
    } catch (error) {
      $('campaign-status').textContent = sanitizeErrorMessage(error.message);
    }
  }

  $('campaign-form').addEventListener('submit', (event) => run(async () => {
    event.preventDefault();
    const button = $('campaign-form').querySelector('button');
    button.disabled = true;
    $('campaign-status').textContent = 'Building a draft from approved and sourced records…';
    try {
      await request(`/projects/${encodeURIComponent(activeProjectId())}/campaign-drafts`,
        { method: 'POST', json: { channel: $('campaign-channel').value } });
      await loadCampaignDrafts();
      notice('Grounded local draft saved. Review before sharing.', 'success');
    } catch (error) {
      $('campaign-status').textContent = sanitizeErrorMessage(error.message);
      throw error;
    } finally { button.disabled = false; }
  }));

  // T017 / T018 Impact Story Event Listeners
  const generateImpactBtn = $('btn-generate-impact');
  if (generateImpactBtn) generateImpactBtn.addEventListener('click', generateImpactStoryAction);
  const refreshImpactBtn = $('btn-refresh-impact');
  if (refreshImpactBtn) refreshImpactBtn.addEventListener('click', loadImpactStoryTab);
  const statusSelect = $('impact-status-select');
  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      updateStoryStatusAction(e.target.value);
    });
  }

  for (const siteSelect of [$('topbar-site-select'), $('site-select')]) {
    if (!siteSelect) continue;
    siteSelect.addEventListener('change', (e) => {
      const selectedId = e.target.value;
      if (selectedId && selectedId !== state.site) {
        location.hash = `#project/${encodeURIComponent(selectedId)}/${state.activeTab || 'media-library'}`;
      }
    });
  }

  window.addEventListener('hashchange', () => run(route));
  run(async () => { await getStatus(); await route(); });
})();
