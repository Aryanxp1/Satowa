(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { token: '', site: '', visits: [], observations: [], measurements: [] };
  const notice = (message, error = false) => {
    $('notice').textContent = message;
    $('notice').classList.toggle('error', error);
  };
  const node = (tag, className = '', text = '') => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
  };
  const api = async (path, options = {}) => {
    const headers = { Authorization: `Bearer ${state.token}`, ...options.headers };
    if (options.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(`/api/v1${path}`, { ...options, headers, cache: 'no-store' });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch (_) { /* Keep the HTTP status text. */ }
      throw new Error(`${response.status}: ${detail}`);
    }
    return response.headers.get('content-type')?.includes('application/json') ? response.json() : response;
  };
  const run = async (action) => {
    try { await action(); } catch (error) {
      notice(error.message || 'Request failed.', true);
      if (error.message?.startsWith('409:') && state.site) await refreshSite();
    }
  };

  async function loadSites(preferred = '') {
    const [sites, integrations] = await Promise.all([api('/sites'), api('/integrations')]);
    const select = $('site-select');
    select.replaceChildren(new Option('Choose a site', ''));
    sites.forEach(site => select.add(new Option(`${site.name} (${site.id})`, site.id)));
    if (preferred && sites.some(site => site.id === preferred)) select.value = preferred;
    $('integration-status').textContent = `Media: ${integrations.cloudinary_ready ? 'Cloudinary configured' : 'local sample only; Cloudinary credentials needed for uploads'} · Image comparison: ${integrations.gemini_ready ? 'Gemini configured' : 'manual review; Gemini key needed for AI drafts'}`;
    $('workspace').hidden = false;
    return sites;
  }

  async function refreshSite() {
    if (!state.site) return;
    const [visits, observations, measurements, report] = await Promise.all([
      api(`/sites/${encodeURIComponent(state.site)}/visits`),
      api(`/sites/${encodeURIComponent(state.site)}/observations`),
      api(`/sites/${encodeURIComponent(state.site)}/measurements`),
      api(`/sites/${encodeURIComponent(state.site)}/report`),
    ]);
    state.visits = visits;
    state.observations = observations;
    state.measurements = measurements;
    $('site-workspace').hidden = false;
    $('synthetic-banner').hidden = state.site !== 'demo-riverbank';
    $('visit-count').textContent = visits.length;
    $('photo-count').textContent = visits.reduce((total, visit) => total + visit.assets.length, 0);
    $('observation-count').textContent = observations.length;
    $('approved-count').textContent = report.observations.length;
    renderVisits();
    renderPairChoices();
    renderObservations();
    renderMeasurements();
    const count = report.observations.length;
    const measureCount = report.recorded_measurements.length;
    $('report-count').textContent = `${count} approved observation${count === 1 ? '' : 's'} and ${measureCount} recorded measurement${measureCount === 1 ? '' : 's'} ready to export.`;
    $('export').disabled = count + measureCount === 0;
  }

  function renderVisits() {
    const container = $('visits');
    container.replaceChildren();
    const filter = $('media-filter').value.trim().toLowerCase();
    const visible = state.visits.filter(visit => !filter || visit.label.toLowerCase().includes(filter) ||
      visit.visited_on.includes(filter) || visit.assets.some(asset => asset.source.toLowerCase().includes(filter)));
    container.classList.toggle('empty', visible.length === 0);
    if (!visible.length) { container.textContent = filter ? 'No visits or photo sources match this search.' : 'No visits yet.'; return; }
    visible.forEach(visit => {
      const card = node('article', 'visit-card');
      card.append(node('h3', '', visit.label), node('div', 'date', visit.visited_on));
      const thumbs = node('div', 'thumb-grid');
      visit.assets.filter(asset => !filter || visit.label.toLowerCase().includes(filter) ||
        visit.visited_on.includes(filter) || asset.source.toLowerCase().includes(filter)).forEach(asset => {
        const image = node('img');
        image.src = asset.secure_url;
        image.alt = `${visit.label}: ${asset.source}`;
        image.loading = 'lazy';
        thumbs.append(image);
      });
      card.append(thumbs);
      const form = node('form', 'upload-form');
      const source = node('input');
      source.name = 'source'; source.placeholder = 'Source or permission reference';
      source.required = true; source.maxLength = 200;
      const file = node('input');
      file.type = 'file'; file.name = 'file'; file.accept = 'image/jpeg,image/png,image/webp'; file.required = true;
      const button = node('button', 'secondary', 'Upload photo');
      form.append(source, file, button);
      form.addEventListener('submit', event => {
        event.preventDefault();
        run(async () => {
          button.disabled = true;
          try {
            const data = new FormData(form);
            data.set('project_id', state.site);
            data.set('visit_id', visit.id);
            data.set('visit_date', visit.visited_on);
            await api('/media/images', { method: 'POST', body: data });
            notice('Photo uploaded to this visit.');
            await refreshSite();
          } finally { button.disabled = false; }
        });
      });
      card.append(form);
      container.append(card);
    });
  }

  function renderPairChoices() {
    const assets = state.visits.flatMap(visit => visit.assets.map(asset => ({ ...asset, visit })));
    for (const [id, first] of [['before-select', true], ['after-select', false]]) {
      const select = $(id);
      const previous = select.value;
      select.replaceChildren(new Option('Choose a photo', ''));
      assets.forEach(asset => select.add(new Option(
        `${asset.visit.visited_on} · ${asset.visit.label} · ${asset.source}`, asset.asset_id)));
      if (assets.some(asset => asset.asset_id === previous)) select.value = previous;
      else if (assets.length) select.value = (first ? assets[0] : assets[assets.length - 1]).asset_id;
    }
    updatePreview();
    $('compare').disabled = assets.length < 2;
  }

  function updatePreview() {
    const assets = state.visits.flatMap(visit => visit.assets);
    for (const side of ['before', 'after']) {
      const selected = assets.find(asset => asset.asset_id === $(`${side}-select`).value);
      const image = $(`${side}-preview`);
      image.hidden = !selected;
      if (selected) image.src = selected.secure_url;
      else image.removeAttribute('src');
    }
    const before = assets.find(asset => asset.asset_id === $('before-select').value);
    const after = assets.find(asset => asset.asset_id === $('after-select').value);
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

  function renderMeasurements() {
    const select = $('measurement-visit');
    select.replaceChildren(new Option('Choose a visit', ''));
    state.visits.forEach(visit => select.add(new Option(`${visit.visited_on} · ${visit.label}`, visit.id)));
    const container = $('measurements');
    container.replaceChildren();
    if (!state.measurements.length) {
      container.textContent = 'No measurements recorded. Photos alone do not establish weight or impact.';
      return;
    }
    state.measurements.forEach(item => {
      const row = node('div', 'measurement-item');
      row.append(node('strong', '', `${item.quantity} ${item.unit} · ${item.label}`),
        node('span', '', `Source: ${item.source} · ${item.recorded_by}`));
      container.append(row);
    });
  }

  function renderObservations() {
    const container = $('observations');
    container.replaceChildren();
    container.classList.toggle('empty', state.observations.length === 0);
    if (!state.observations.length) { container.textContent = 'No observations yet.'; return; }
    state.observations.forEach(observation => {
      const card = node('article', 'observation-card');
      const badge = node('span', `badge ${observation.review_status}`, observation.review_status);
      const title = node('h3', '', observation.id === 'synthetic-river-observation'
        ? 'Sample observation' : `Observation ${observation.id.slice(0, 8)}`);
      const meta = node('p', 'meta', `Version ${observation.version} · ${observation.before_asset_id.slice(0, 9)} → ${observation.after_asset_id.slice(0, 9)}`);
      card.append(badge, title, meta);
      const evidence = node('div', 'evidence-grid');
      for (const [labelText, assetId] of [['Before', observation.before_asset_id], ['After', observation.after_asset_id]]) {
        const asset = state.visits.flatMap(visit => visit.assets).find(item => item.asset_id === assetId);
        if (!asset) continue;
        const figure = node('figure');
        const image = node('img');
        image.src = asset.secure_url;
        image.alt = `${labelText} evidence: ${asset.source}`;
        image.loading = 'lazy';
        const caption = node('figcaption', '', `${labelText} · ${asset.source}`);
        figure.append(image, caption);
        evidence.append(figure);
      }
      card.append(evidence);
      if (observation.reliability_reason) card.append(node('p', 'reason', observation.reliability_reason));
      if (observation.ai_draft) card.append(node('p', 'meta', `AI draft: ${observation.ai_draft}`));
      const label = node('label', '', 'Review text');
      const field = node('textarea');
      field.value = observation.working_text || '';
      field.maxLength = 600;
      label.append(field);
      card.append(label);
      if (observation.reviewed_by) card.append(node('p', 'meta', `Last reviewed by ${observation.reviewed_by}`));
      const actions = node('div', 'actions');
      const save = node('button', 'secondary', 'Save edit');
      const approve = node('button', 'primary', 'Approve');
      const reject = node('button', 'secondary', 'Reject');
      save.disabled = field.value.trim() === (observation.working_text || '').trim();
      field.addEventListener('input', () => { save.disabled = field.value.trim() === (observation.working_text || '').trim(); });
      const act = (method, payload) => run(async () => {
        const buttons = [...actions.querySelectorAll('button')];
        const disabledBefore = buttons.map(button => button.disabled);
        buttons.forEach(button => { button.disabled = true; });
        try {
          await api(`/observations/${observation.id}${method === 'POST' ? '/review' : ''}`,
            { method, json: { expected_version: observation.version, ...payload } });
          notice(method === 'PATCH' ? 'Edit saved. Approval is required again.' : 'Review saved.');
          await refreshSite();
        } finally {
          buttons.forEach((button, index) => { button.disabled = disabledBefore[index]; });
        }
      });
      save.addEventListener('click', () => act('PATCH', { working_text: field.value }));
      approve.addEventListener('click', () => act('POST', { decision: 'approve', text: field.value }));
      reject.addEventListener('click', () => act('POST', { decision: 'reject' }));
      if (observation.review_status === 'approved') {
        approve.disabled = true;
        reject.disabled = true;
      }
      actions.append(save, approve, reject);
      card.append(actions);
      container.append(card);
    });
  }

  $('connect').addEventListener('click', () => run(async () => {
    const token = $('token').value.trim();
    if (!token) throw new Error('Enter a reviewer token.');
    state.token = token;
    await loadSites();
    $('token').value = '';
    notice('Connected. Choose or create a site.');
  }));
  $('load-site').addEventListener('click', () => run(async () => {
    state.site = $('site-select').value;
    if (!state.site) throw new Error('Choose a site first.');
    await refreshSite();
    notice(`Opened ${state.site}.`);
  }));
  $('site-form').addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form));
      await api('/sites', { method: 'POST', json: data });
      state.site = data.id;
      await loadSites(data.id);
      await refreshSite();
      form.reset();
      notice('Site created. Add its first visit.');
    });
  });
  $('visit-form').addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form));
      await api(`/sites/${encodeURIComponent(state.site)}/visits`, { method: 'POST', json: data });
      form.reset();
      await refreshSite();
      notice('Visit added. Upload a photo to it.');
    });
  });
  $('before-select').addEventListener('change', updatePreview);
  $('after-select').addEventListener('change', updatePreview);
  $('comparison-range').addEventListener('input', updateComparisonRange);
  $('media-filter').addEventListener('input', renderVisits);
  $('measurement-form').addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    run(async () => {
      const data = Object.fromEntries(new FormData(form));
      data.quantity = Number(data.quantity);
      await api(`/sites/${encodeURIComponent(state.site)}/measurements`, { method: 'POST', json: data });
      form.reset();
      await refreshSite();
      notice('Measured outcome saved with its source.');
    });
  });
  $('compare').addEventListener('click', () => run(async () => {
    const before_asset_id = $('before-select').value;
    const after_asset_id = $('after-select').value;
    if (!before_asset_id || !after_asset_id) throw new Error('Select two photos.');
    $('compare').disabled = true;
    try {
      const result = await api('/pairs', { method: 'POST', json: { before_asset_id, after_asset_id } });
      await refreshSite();
      notice(result.review_status === 'unreliable' ? result.reliability_reason : 'Draft ready for human review.',
        result.review_status === 'unreliable');
    } finally { $('compare').disabled = false; }
  }));
  $('export').addEventListener('click', () => run(async () => {
    const response = await api(`/sites/${encodeURIComponent(state.site)}/report?format=markdown`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = node('a');
    link.href = url; link.download = `lex-${state.site}-report.md`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice('Approved report downloaded.');
  }));
})();
