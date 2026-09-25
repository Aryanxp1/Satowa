(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = { session: null, integrations: null, sites: [], site: '', siteRecord: null,
    visits: [], observations: [], measurements: [], report: null, nextTab: 'visits' };
  const tabs = new Set(['overview', 'visits', 'compare', 'review', 'report']);

  function element(tag, className = '', text = '') {
    const item = document.createElement(tag);
    if (className) item.className = className;
    item.textContent = text;
    return item;
  }

  function notice(message, isError = false) {
    const item = $('notice');
    item.textContent = message;
    item.classList.toggle('error', isError);
    item.hidden = !message;
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
      notice(error.message || 'The request could not be completed.', true);
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
    const approved = report.observations.length;
    const measured = report.recorded_measurements.length;
    $('report-count').textContent = `${approved} approved observation${approved === 1 ? '' : 's'} · ${measured} recorded measurement${measured === 1 ? '' : 's'}`;
    $('export').disabled = approved + measured === 0;
  }

  function renderNextStep() {
    const photos = state.visits.reduce((sum, visit) => sum + visit.assets.length, 0);
    const unreviewed = state.observations.some(item => ['pending', 'unreliable'].includes(item.review_status));
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
        const figure = element('figure');
        const image = element('img'); image.src = asset.secure_url; image.alt = `${visit.label}: ${asset.source}`; image.loading = 'lazy';
        figure.append(image, element('figcaption', '', asset.source));
        thumbnails.append(figure);
      }
      if (!visit.assets.length) thumbnails.append(element('p', 'empty-state', 'No photos yet.'));
      card.append(thumbnails);
      const form = element('form', 'upload-form');
      const sourceLabel = element('label', '', 'Source / permission reference');
      const source = element('input'); source.name = 'source'; source.required = true; source.maxLength = 200;
      source.placeholder = 'Photographer and consent record'; sourceLabel.append(source);
      const fileLabel = element('label', '', 'Upload a photo');
      const file = element('input'); file.type = 'file'; file.name = 'file'; file.accept = 'image/jpeg,image/png,image/webp'; file.required = true;
      fileLabel.append(file);
      const button = element('button', 'button secondary', 'Upload to Cloudinary');
      form.append(sourceLabel, fileLabel, button);
      form.addEventListener('submit', event => {
        event.preventDefault();
        run(async () => {
          button.disabled = true;
          try {
            const data = new FormData(form);
            data.set('project_id', state.site); data.set('visit_id', visit.id); data.set('visit_date', visit.visited_on);
            await request('/media/images', { method: 'POST', body: data });
            notice('Photo uploaded to this visit.');
            await refreshSite();
          } finally { button.disabled = false; }
        });
      });
      card.append(form);
      list.append(card);
    }
  }

  function assetsForSite() { return state.visits.flatMap(visit => visit.assets.map(asset => ({ ...asset, visit }))); }

  function renderPairChoices() {
    const assets = assetsForSite();
    for (const [id, before] of [['before-select', true], ['after-select', false]]) {
      const select = $(id); const previous = select.value;
      select.replaceChildren(new Option('Choose a photo', ''));
      for (const asset of assets) select.add(new Option(`${asset.visit.visited_on} · ${asset.visit.label} · ${asset.source}`, asset.asset_id));
      if (assets.some(asset => asset.asset_id === previous)) select.value = previous;
      else if (assets.length) select.value = (before ? assets[0] : assets[assets.length - 1]).asset_id;
    }
    $('compare').disabled = assets.length < 2;
    $('compare-hint').textContent = assets.length < 2 ? 'Add a photo from each of two visits first.' :
      state.site === 'demo-riverbank' ? 'Synthetic images demonstrate the comparison; AI will decline them.' :
        'AI drafts only visible, supportable change.';
    updatePreview();
  }

  function updatePreview() {
    const assets = assetsForSite();
    const before = assets.find(asset => asset.asset_id === $('before-select').value);
    const after = assets.find(asset => asset.asset_id === $('after-select').value);
    for (const [side, selected] of [['before', before], ['after', after]]) {
      const image = $(`${side}-preview`);
      image.hidden = !selected;
      if (selected) image.src = selected.secure_url;
      else image.removeAttribute('src');
    }
    $('comparison-stage').hidden = !before || !after || before.asset_id === after.asset_id;
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
    const list = $('observations'); list.replaceChildren();
    list.classList.toggle('empty', !state.observations.length);
    if (!state.observations.length) { list.textContent = 'No observations yet. Compare two photographs to draft one.'; return; }
    for (const observation of [...state.observations].reverse()) {
      const card = element('article', 'observation-card');
      const head = element('div', 'observation-head');
      head.append(element('span', `badge ${observation.review_status}`, observation.review_status),
        element('span', 'meta', `Revision ${observation.version}`));
      card.append(head, element('h3', '', observation.id === 'synthetic-river-observation' ?
        'Riverbank visual observation' : `Observation ${observation.id.slice(0, 8)}`));
      const evidence = element('div', 'evidence-grid');
      for (const [caption, id] of [['BEFORE', observation.before_asset_id], ['AFTER', observation.after_asset_id]]) {
        const asset = assetsForSite().find(item => item.asset_id === id);
        if (!asset) continue;
        const figure = element('figure');
        const image = element('img'); image.src = asset.secure_url; image.alt = `${caption}: ${asset.source}`; image.loading = 'lazy';
        figure.append(image, element('figcaption', '', `${caption} · ${asset.visit.visited_on}`));
        evidence.append(figure);
      }
      card.append(evidence);
      if (observation.reliability_reason) card.append(element('p', 'reason', observation.reliability_reason));
      if (observation.ai_draft) card.append(element('p', 'ai-draft', `AI suggestion: ${observation.ai_draft}`));
      const label = element('label', '', 'Your observation');
      const field = element('textarea'); field.value = observation.working_text || ''; field.maxLength = 600; field.rows = 3;
      field.placeholder = 'Describe only what you can support from the paired photos.'; label.append(field); card.append(label);
      if (observation.reviewed_by) card.append(element('p', 'meta', `Last reviewed by ${observation.reviewed_by}`));
      const actions = element('div', 'actions');
      const save = element('button', 'button secondary', 'Save edit');
      const approve = element('button', 'button primary', 'Approve');
      const reject = element('button', 'button quiet', 'Reject');
      const updateSave = () => { save.disabled = field.value.trim() === (observation.working_text || '').trim(); };
      updateSave(); field.addEventListener('input', updateSave);
      const act = (method, payload) => run(async () => {
        const buttons = [save, approve, reject]; buttons.forEach(button => { button.disabled = true; });
        try {
          await request(`/observations/${observation.id}${method === 'POST' ? '/review' : ''}`,
            { method, json: { expected_version: observation.version, ...payload } });
          notice(method === 'PATCH' ? 'Edit saved. Review it again before export.' : 'Review saved.');
          await refreshSite();
        } finally { buttons.forEach(button => { button.disabled = false; }); }
      });
      save.addEventListener('click', () => act('PATCH', { working_text: field.value }));
      approve.addEventListener('click', () => act('POST', { decision: 'approve', text: field.value }));
      reject.addEventListener('click', () => act('POST', { decision: 'reject' }));
      if (observation.review_status === 'approved') { approve.disabled = true; reject.disabled = true; }
      actions.append(save, approve, reject); card.append(actions); list.append(card);
    }
  }

  function renderMeasurements() {
    const select = $('measurement-visit');
    select.replaceChildren(new Option('Choose a visit', ''));
    for (const visit of state.visits) select.add(new Option(`${visit.visited_on} · ${visit.label}`, visit.id));
    const list = $('measurements'); list.replaceChildren();
    if (!state.measurements.length) { list.textContent = 'No measurements recorded.'; return; }
    for (const item of state.measurements) {
      const row = element('div', 'measurement-item');
      row.append(element('strong', '', `${item.quantity} ${item.unit} · ${item.label}`),
        element('span', '', `Source: ${item.source} · recorded by ${item.recorded_by}`));
      list.append(row);
    }
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    $('theme-toggle').textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
    $('theme-toggle').setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    localStorage.setItem('setowa-theme', theme);
  }

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
  $('compare').addEventListener('click', () => run(async () => {
    const before_asset_id = $('before-select').value; const after_asset_id = $('after-select').value;
    if (!before_asset_id || !after_asset_id) throw new Error('Choose two photographs first.');
    $('compare').disabled = true;
    try {
      const result = await request('/pairs', { method: 'POST', json: { before_asset_id, after_asset_id } });
      await refreshSite();
      notice(result.review_status === 'unreliable' ? result.reliability_reason : 'Draft ready for human review.',
        result.review_status === 'unreliable');
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

  window.addEventListener('hashchange', () => run(route));
  run(async () => { await getStatus(); await route(); });
})();
