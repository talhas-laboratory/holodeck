const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = { health: {}, config: {}, workspaces: [], current: null, tasks: [], runs: [], claims: [], view: 'overview' };
const viewCopy = {
  overview: ['LOCAL AUTHORITY / COMPLETE STATE', 'Workspace overview', 'Intent, motion, and boundaries in one place.'],
  work: ['TASKS / SCOPE / JUDGMENT', 'Work', 'Plan and inspect every bounded work item.'],
  runs: ['AGENTS / INTENT / PATH CLAIMS', 'Runs & claims', 'See exactly who is moving through which surface.'],
  configuration: ['RUNTIME / MANIFEST / POLICY', 'Configuration', 'The effective settings and honest product boundary.'],
};
const lanes = [
  ['backlog', 'Backlog'], ['ready', 'Ready'], ['in-progress', 'In motion'],
  ['review', 'Review'], ['blocked', 'Blocked'], ['closed', 'Closed'],
];

function esc(value = '') { return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function lines(value = '') { return String(value).split('\n').map(item => item.trim()).filter(Boolean); }
function time(value) { if (!value) return '—'; return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
function laneFor(status) { return ['done', 'cancelled', 'completed'].includes(status) ? 'closed' : lanes.some(([key]) => key === status) ? status : 'backlog'; }
function taskName(id) { return state.tasks.find(task => task.task_id === id)?.title || id; }
function empty(message) { return `<div class="empty-state"><span>○</span><p>${esc(message)}</p></div>`; }
function toast(message, kind = 'ok') { const node = $('#toast'); node.textContent = message; node.dataset.kind = kind; node.classList.add('is-visible'); clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('is-visible'), 2600); }

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function showView(name) {
  state.view = name;
  $$('.nav-item').forEach(item => item.classList.toggle('is-active', item.dataset.view === name));
  $$('.view').forEach(view => view.classList.toggle('is-active', view.dataset.page === name));
  const [kicker, title, note] = viewCopy[name];
  $('#view-kicker').textContent = kicker; $('#view-title').textContent = title; $('#view-note').textContent = note;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderHeader() {
  const workspace = state.current;
  $('#health-dot').classList.toggle('is-live', state.health.status === 'ok');
  $('#health-label').textContent = state.health.status === 'ok' ? 'healthy' : 'unavailable';
  $('#rail-workspace').textContent = workspace?.label || 'No workspace';
  $('#rail-roots').textContent = workspace?.artifact_roots?.join(' · ') || 'No roots declared';
  const select = $('#workspace-select');
  select.innerHTML = state.workspaces.length
    ? state.workspaces.map(item => `<option value="${esc(item.workspace_id)}">${esc(item.label || item.workspace_id)}</option>`).join('')
    : '<option value="">No workspaces</option>';
  select.value = workspace?.workspace_id || '';
}

function renderOverview() {
  const workspace = state.current || {};
  const activeRuns = state.runs.filter(run => run.status === 'active');
  const activeClaims = state.claims.filter(claim => claim.status === 'active');
  $('#metric-open').textContent = state.tasks.filter(task => !['done', 'cancelled'].includes(task.status)).length;
  $('#metric-runs').textContent = activeRuns.length;
  $('#metric-claims').textContent = activeClaims.length;
  $('#metric-done').textContent = state.tasks.filter(task => task.status === 'done').length;
  $('#workspace-goal').textContent = workspace.goal || 'No goal recorded yet';
  $('#workspace-purpose').textContent = workspace.purpose || 'Add a purpose in Configuration to make the operating intent explicit.';
  $('#workspace-state').textContent = workspace.status || 'empty';
  $('#workspace-meta').innerHTML = [
    ['Identity', workspace.workspace_id],
    ['Artifact roots', workspace.artifact_roots?.join(' · ') || 'Not declared'],
    ['Out of scope', workspace.scope_out?.join(' · ') || 'Not declared'],
    ['Last updated', time(workspace.updated_at)],
  ].map(([term, value]) => `<div><dt>${term}</dt><dd>${esc(value || '—')}</dd></div>`).join('');
  $('#recent-runs').innerHTML = state.runs.length ? state.runs.slice(0, 4).map(run => `<article class="stack-row"><span class="status-mark status--${esc(run.status)}"></span><div><strong>${esc(run.agent_id)}</strong><p>${esc(run.intent || taskName(run.task_id))}</p></div><small>${time(run.created_at)}</small></article>`).join('') : empty('No agent runs have been recorded.');
  const actions = state.config.onboarding_policy?.actions || {};
  const policyCounts = Object.values(actions).reduce((acc, value) => ({ ...acc, [value]: (acc[value] || 0) + 1 }), {});
  $('#policy-summary').innerHTML = [['automatic', 'Automatic'], ['approval_required', 'Approval'], ['denied', 'Denied']].map(([key, label]) => `<div><span class="policy-orb policy-orb--${key}">${policyCounts[key] || 0}</span><p><strong>${label}</strong><small>${key === 'automatic' ? 'ambiently allowed' : key === 'denied' ? 'never ambient' : 'requires judgment'}</small></p></div>`).join('');
  const capabilities = state.config.capabilities || [];
  const available = capabilities.filter(item => item.status === 'available').length;
  $('#capability-count').textContent = `${available}/${capabilities.length}`;
  $('#capability-summary').innerHTML = capabilities.map(item => `<span class="${item.status}" title="${esc(item.label)}"></span>`).join('');
}

function renderWork() {
  $('#task-board').innerHTML = lanes.map(([key, label]) => {
    const tasks = state.tasks.filter(task => laneFor(task.status) === key);
    return `<section class="lane lane--${key}"><header><span>${label}</span><b>${tasks.length}</b></header><div class="lane-cards">${tasks.length ? tasks.map(task => `<button class="task-card" data-task="${esc(task.task_id)}"><span>${esc(task.task_id)}</span><h3>${esc(task.title)}</h3><div><small>${task.acceptance_criteria?.length || 0} criteria</small><em>${esc(task.status)}</em></div></button>`).join('') : empty('Nothing rests here.')}</div></section>`;
  }).join('');
  $('#run-task').innerHTML = state.tasks.length ? state.tasks.filter(task => !['done', 'cancelled'].includes(task.status)).map(task => `<option value="${esc(task.task_id)}">${esc(task.task_id)} · ${esc(task.title)}</option>`).join('') : '<option value="">No open tasks</option>';
}

function renderRuns() {
  $('#run-count').textContent = state.runs.length;
  const activeClaims = state.claims.filter(claim => claim.status === 'active');
  $('#claim-count').textContent = `${activeClaims.length} active`;
  $('#run-list').innerHTML = state.runs.length ? state.runs.map(run => `<article class="run-row"><div class="run-main"><span class="status-mark status--${esc(run.status)}"></span><div><p class="record-id">${esc(run.run_id)}</p><h3>${esc(run.intent || taskName(run.task_id))}</h3><p>${esc(run.agent_id)} · ${esc(taskName(run.task_id))}</p></div></div><div class="run-paths">${(run.claimed_paths || []).map(path => `<code>${esc(path)}</code>`).join('') || '<small>No paths claimed</small>'}</div><div class="run-end"><small>${time(run.created_at)}</small>${run.summary ? `<p>${esc(run.summary)}</p>` : ''}${run.status === 'active' ? `<button class="button button--tiny" data-complete-run="${esc(run.run_id)}">Complete</button>` : `<span class="state-tag">${esc(run.status)}</span>`}</div></article>`).join('') : empty('Begin a run to coordinate an agent and claim its working paths.');
  $('#claim-list').innerHTML = state.claims.length ? state.claims.map(claim => `<article class="claim-row ${claim.status === 'released' ? 'is-released' : ''}"><span>${claim.status === 'active' ? '◆' : '◇'}</span><div><code>${esc(claim.path)}</code><p>${esc(claim.agent_id)} · ${esc(taskName(claim.task_id))}</p><small>${claim.status === 'active' ? `claimed ${time(claim.created_at)}` : `released ${time(claim.released_at || claim.updated_at)}`}</small></div></article>`).join('') : empty('No paths have been claimed.');
}

function renderConfiguration() {
  const workspace = state.current || {};
  const form = $('#workspace-form');
  for (const field of ['label', 'goal', 'purpose']) form.elements[field].value = workspace[field] || '';
  form.elements.artifact_roots.value = (workspace.artifact_roots || []).join('\n');
  form.elements.scope_out.value = (workspace.scope_out || []).join('\n');
  $('#workspace-times').innerHTML = `<span>Created ${time(workspace.created_at)}</span><span>Updated ${time(workspace.updated_at)}</span>`;
  const runtime = state.config.runtime || {};
  $('#runtime-config').innerHTML = Object.entries(runtime).map(([key, value]) => `<div><dt>${esc(key.replaceAll('_', ' '))}</dt><dd>${esc(value)}</dd></div>`).join('');
  const manifest = state.config.project_manifest || {};
  $('#manifest-config').innerHTML = Object.entries(manifest).map(([key, value]) => `<div><dt>${esc(key.replaceAll('_', ' '))}</dt><dd>${esc(Array.isArray(value) ? value.join(' · ') : value)}</dd></div>`).join('');
  const actions = state.config.onboarding_policy?.actions || {};
  $('#policy-table').innerHTML = Object.entries(actions).map(([action, decision]) => `<div><code>${esc(action)}</code><span class="decision decision--${esc(decision)}">${esc(decision.replace('_', ' '))}</span></div>`).join('');
  $('#capability-ledger').innerHTML = (state.config.capabilities || []).map(item => `<article><span class="cap-dot cap-dot--${esc(item.status)}"></span><div><strong>${esc(item.label)}</strong><small>${esc(item.id)}</small></div><em>${esc(item.status)}</em></article>`).join('');
}

function render() { renderHeader(); renderOverview(); renderWork(); renderRuns(); renderConfiguration(); }

async function selectWorkspace(id) {
  state.current = state.workspaces.find(item => item.workspace_id === id) || null;
  if (!state.current) { state.tasks = []; state.runs = []; state.claims = []; render(); return; }
  const base = `/api/workspaces/${encodeURIComponent(id)}`;
  const [tasks, runs, claims] = await Promise.all([api(`${base}/tasks`), api(`${base}/runs`), api(`${base}/claims`)]);
  state.tasks = tasks.tasks || []; state.runs = runs.runs || []; state.claims = claims.claims || [];
  render();
}

async function load({ quiet = false } = {}) {
  try {
    const previous = state.current?.workspace_id;
    const [health, config, catalog] = await Promise.all([api('/health'), api('/api/config'), api('/api/workspaces')]);
    state.health = health; state.config = config; state.workspaces = catalog.workspaces || [];
    const id = state.workspaces.some(item => item.workspace_id === previous) ? previous : state.workspaces[0]?.workspace_id;
    await selectWorkspace(id);
    if (!quiet) toast('Authoritative state refreshed');
  } catch (error) { state.health = { status: 'unavailable' }; renderHeader(); toast(error.message, 'error'); }
}

function payloadFrom(form, listFields = []) {
  const data = Object.fromEntries(new FormData(form).entries());
  for (const field of listFields) data[field] = lines(data[field]);
  return data;
}

$$('[data-open]').forEach(button => button.addEventListener('click', () => {
  if (button.dataset.open !== 'workspace-dialog' && !state.current) return toast('Create a workspace first', 'error');
  document.getElementById(button.dataset.open).showModal();
}));
$$('.dialog-close, .dialog-actions [value="cancel"]').forEach(button => button.addEventListener('click', event => {
  event.preventDefault();
  button.closest('dialog').close();
}));
$$('.nav-item').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
$$('[data-go]').forEach(button => button.addEventListener('click', () => showView(button.dataset.go)));
$('#workspace-select').addEventListener('change', event => selectWorkspace(event.target.value).catch(error => toast(error.message, 'error')));
$('#refresh').addEventListener('click', () => load());

$('#create-workspace-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const payload = payloadFrom(event.currentTarget, ['artifact_roots', 'scope_out']);
    const workspace = await api('/api/workspaces', { method: 'POST', body: JSON.stringify(payload) });
    event.currentTarget.closest('dialog').close(); event.currentTarget.reset(); await load({ quiet: true }); await selectWorkspace(workspace.workspace_id); toast('Workspace created');
  } catch (error) { toast(error.message, 'error'); }
});

$('#create-task-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const payload = payloadFrom(event.currentTarget, ['acceptance_criteria', 'constraints']);
    if (!payload.task_id) delete payload.task_id;
    await api(`/api/workspaces/${encodeURIComponent(state.current.workspace_id)}/tasks`, { method: 'POST', body: JSON.stringify(payload) });
    event.currentTarget.closest('dialog').close(); event.currentTarget.reset(); await selectWorkspace(state.current.workspace_id); toast('Task created');
  } catch (error) { toast(error.message, 'error'); }
});

$('#create-run-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const payload = payloadFrom(event.currentTarget, ['claimed_paths']);
    await api(`/api/workspaces/${encodeURIComponent(state.current.workspace_id)}/runs`, { method: 'POST', body: JSON.stringify(payload) });
    event.currentTarget.closest('dialog').close(); event.currentTarget.reset(); await selectWorkspace(state.current.workspace_id); showView('runs'); toast('Run started and paths claimed');
  } catch (error) { toast(error.message, 'error'); }
});

$('#workspace-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.current) return toast('Create a workspace first', 'error');
  try {
    const payload = payloadFrom(event.currentTarget, ['artifact_roots', 'scope_out']);
    await api(`/api/workspaces/${encodeURIComponent(state.current.workspace_id)}`, { method: 'PATCH', body: JSON.stringify(payload) });
    await load({ quiet: true }); toast('Workspace settings saved');
  } catch (error) { toast(error.message, 'error'); }
});

$('#task-detail-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const payload = payloadFrom(event.currentTarget, ['acceptance_criteria', 'constraints']);
    const taskId = payload.task_id; delete payload.task_id;
    await api(`/api/workspaces/${encodeURIComponent(state.current.workspace_id)}/tasks/${encodeURIComponent(taskId)}`, { method: 'PATCH', body: JSON.stringify(payload) });
    event.currentTarget.closest('dialog').close(); await selectWorkspace(state.current.workspace_id); toast('Task record saved');
  } catch (error) { toast(error.message, 'error'); }
});

document.addEventListener('click', async event => {
  const taskButton = event.target.closest('[data-task]');
  if (taskButton) {
    const task = state.tasks.find(item => item.task_id === taskButton.dataset.task); if (!task) return;
    const form = $('#task-detail-form'); form.elements.task_id.value = task.task_id; form.elements.title.value = task.title; form.elements.status.value = task.status; form.elements.acceptance_criteria.value = (task.acceptance_criteria || []).join('\n'); form.elements.constraints.value = (task.constraints || []).join('\n');
    $('#detail-task-id').textContent = task.task_id; $('#task-times').innerHTML = `<span>Created ${time(task.created_at)}</span><span>Updated ${time(task.updated_at)}</span>`; $('#task-detail-dialog').showModal();
  }
  const runButton = event.target.closest('[data-complete-run]');
  if (runButton) {
    const summary = window.prompt('Completion summary (optional)') ?? null; if (summary === null) return;
    try { await api(`/api/workspaces/${encodeURIComponent(state.current.workspace_id)}/runs/${encodeURIComponent(runButton.dataset.completeRun)}/complete`, { method: 'POST', body: JSON.stringify({ summary }) }); await selectWorkspace(state.current.workspace_id); toast('Run completed; claims released'); } catch (error) { toast(error.message, 'error'); }
  }
});

load();
