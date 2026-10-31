'use strict';

// The page talks to ui/app.py's Api through window.pywebview.api. Every call
// returns a promise; a result carrying "error" is a problem to show the user.

let api = null;

const state = {
  projects: [],
  slug: null,
  project: null,
  tab: 'cuts',
  which: 'final',        // which cut list the Cuts and Check tabs show
  filter: '',
  flaggedOnly: false,
  cache: {},             // "cuts:final", "check:final", "sheet:research" ... for this project
  job: { id: null, next: 0, running: false, info: null, exitCode: null, cancelled: false },
  log: [],
  drafts: {},            // unsent feedback, by "slug:short number"
  editor: null,          // the open shorts editor (ui/web/editor.js)
  renders: 0,
};

const STAGES = [
  { action: 'convert', name: 'Convert', desc: 'An .mkv movie becomes a .mov Resolve reads, in stereo.',
    done: (p) => p.has.converted, notNeeded: (p) => p.has.converted === null },
  { action: 'transcribe', name: 'Transcribe', desc: 'Word-level transcripts of both clips.',
    done: (p) => p.has.transcripts },
  { action: 'research', name: 'Research', desc: 'The film\'s beat sheet, from the web and the transcript.',
    done: (p) => p.has.research },
  { action: 'select', name: 'Select cuts', desc: 'The cut list, from the beat sheet and both transcripts.',
    done: (p) => p.has.cuts },
  { action: 'review', name: 'Review', desc: 'Checks the cut list against the rules and fixes it.',
    done: (p) => p.has.review },
  { action: 'tighten', name: 'Tighten', desc: 'Cuts dead air out of the hosts-only segments, from the waveform.',
    done: (p) => p.has.tightened },
];

const TABS = [['cuts', 'Cuts'], ['check', 'Check'], ['research', 'Research'], ['review', 'Review'],
  ['shorts', 'Shorts'], ['log', 'Log']];

// Asked before a step that replaces something or touches Resolve.
const CONFIRM = {
  convert: (p) => p.has.converted && {
    text: 'Convert the movie again?\nThe existing .mov will be replaced.', ok: 'Convert again' },
  transcribe: (p) => p.has.transcripts && {
    text: 'Both clips are already transcribed. Transcribe them again?\nA feature film takes a long time.',
    ok: 'Transcribe again' },
  research: (p) => p.has.research && { text: 'Replace the existing research sheet?', ok: 'Research again' },
  select: (p) => p.has.cuts && {
    text: 'Replace the existing cut list?\nAny changes made to it by hand will be lost.', ok: 'Select again' },
  review: (p) => p.has.review && {
    text: 'Review again?\nThe review revises the cut list and keeps the version before it as the draft.',
    ok: 'Review again' },
  make_cuts: (p) => (p.has.cuts || p.has.research) && {
    text: 'Run research, select and review in one go?' +
      (p.has.cuts ? '\nThe existing cut list will be replaced.' : ''),
    ok: 'Run all',
    option: p.has.research ? 'Redo the research sheet too' : null },
  tighten: (p) => p.has.tightened && {
    text: 'Tighten again?\nThe cut list is rewritten; the version before is kept as <slug>.pretighten.json.',
    ok: 'Tighten again' },
  build: () => ({ text: 'Build a new timeline in the Resolve project that is open now?', ok: 'Build' }),
  select_shorts: (p) => p.has.shorts && {
    text: 'Select the shorts again?\nThe existing shorts file will be replaced, including any revisions.',
    ok: 'Select again' },
};

// --- helpers ------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'style') node.style.cssText = value;
    else if (value === true) node.setAttribute(key, '');
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function call(method, ...args) {
  const result = await api[method](...args);
  if (result && result.error) {
    toast(result.error);
    throw new Error(result.error);
  }
  return result;
}

let toastTimer = null;
function toast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 6000);
}

// Resolves to { checked } on OK, null on Cancel.
function ask(text, okLabel, option) {
  $('modal-text').textContent = text;
  $('modal-ok').textContent = okLabel || 'OK';
  $('modal-option').hidden = !option;
  $('modal-option-text').textContent = option || '';
  $('modal-check').checked = false;
  $('modal').hidden = false;
  $('modal-ok').focus();
  return new Promise((resolve) => {
    const finish = (value) => {
      $('modal').hidden = true;
      $('modal-ok').onclick = $('modal-cancel').onclick = null;
      resolve(value);
    };
    $('modal-ok').onclick = () => finish({ checked: $('modal-check').checked });
    $('modal-cancel').onclick = () => finish(null);
  });
}

function clock(seconds) {
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = (seconds - hours * 3600 - minutes * 60).toFixed(2).padStart(5, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

function runtime(seconds) {
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, '0')}s`;
}

function showView(name) {
  for (const view of ['empty', 'new', 'project']) $('view-' + view).hidden = view !== name;
}

// --- sidebar --------------------------------------------------------------------

async function refreshProjects() {
  state.projects = (await call('list_projects')).projects;
  renderSidebar();
}

function renderSidebar() {
  const list = $('project-list');
  list.replaceChildren(...state.projects.map((p) => {
    const running = state.job.running && state.job.info && state.job.info.slug === p.slug;
    const has = p.has || {};
    return h('li', { class: p.slug === state.slug ? 'selected' : '', onclick: () => selectProject(p.slug) },
      h('div', { class: 'project-name' }, running && h('span', { class: 'spinner' }), p.title),
      h('div', { class: 'dots', title: 'Transcribed, researched, cut, reviewed' },
        ['transcripts', 'research', 'cuts', 'review'].map((key) =>
          h('span', { class: 'dot' + (has[key] ? ' on' : '') }))));
  }));
}

async function selectProject(slug) {
  state.slug = slug;
  state.which = 'final';
  state.filter = '';
  state.flaggedOnly = false;
  if (state.tab === 'log' && !(state.job.info && state.job.info.slug === slug)) state.tab = 'cuts';
  showView('project');
  renderSidebar();
  await refreshProject();
}

async function refreshProject() {
  if (!state.slug) return;
  const slug = state.slug;
  const project = await call('project', slug);
  if (slug !== state.slug) return;
  state.project = project;
  state.cache = {};
  if (!project.has.draft) state.which = 'final';
  renderProject();
  renderPanel();
  if (project.has.cuts) loadCached('check', state.which).then(renderTabs, () => {});
}

// --- project header, stages, tabs -------------------------------------------------

function renderProject() {
  renderHeader();
  renderStages();
  renderTabs();
}

function renderHeader() {
  const p = state.project;
  const offset = h('input', { type: 'number', step: 'any', min: '0', id: 'offset-input',
    value: p.offset === null ? '' : p.offset, placeholder: 'seconds' });
  $('project-header').replaceChildren(
    h('h1', {}, p.title),
    h('div', { class: 'clips' }, p.clips.map((clip) =>
      h('div', {}, clip.label + ': ',
        h('span', { class: 'path' }, clip.path || '(not set)'),
        !clip.exists && h('span', { class: 'missing' }, '  not found')))),
    h('div', { class: 'offset-row' + (p.offset === null ? ' needed' : '') },
      'Movie offset', offset, 'seconds',
      h('button', { class: 'btn small', onclick: saveOffset }, 'Save'),
      p.offset === null && h('span', { class: 'blocked' },
        'How far into the reaction recording the movie starts. Needed before research.')));
}

async function saveOffset() {
  await call('set_offset', state.slug, $('offset-input').value);
  await refreshProject();
  refreshProjects();
}

function runButton(action, label, primary) {
  const p = state.project;
  const reason = p.blocked[action];
  const busy = state.job.running;
  return h('button', {
    class: 'btn small' + (primary ? ' primary' : ''),
    disabled: Boolean(reason) || busy,
    title: reason || (busy ? 'Another step is running.' : null),
    onclick: () => run(action),
  }, label);
}

function isRunning(action) {
  const info = state.job.info;
  return state.job.running && info && info.slug === state.slug && info.action === action;
}

function renderStages() {
  const p = state.project;
  const cards = STAGES.map((stage) => {
    const done = stage.done(p);
    const running = isRunning(stage.action);
    const skip = stage.notNeeded && stage.notNeeded(p);
    return h('div', { class: 'stage' },
      h('div', { class: 'stage-top' },
        h('span', { class: 'stage-name' }, stage.name),
        h('span', { class: 'pill ' + (running ? 'running' : done ? 'done' : 'todo') },
          running ? 'Running' : done ? 'Done' : skip ? 'Not needed' : 'Not done')),
      h('div', { class: 'stage-desc' }, stage.desc),
      !skip && p.blocked[stage.action] && h('div', { class: 'blocked' }, p.blocked[stage.action]),
      !skip && h('div', { class: 'stage-actions' },
        runButton(stage.action, done ? 'Run again' : 'Run', !done)));
  });
  const building = isRunning('build') || isRunning('dry_run');
  cards.push(h('div', { class: 'stage' },
    h('div', { class: 'stage-top' },
      h('span', { class: 'stage-name' }, 'Build'),
      building && h('span', { class: 'pill running' }, 'Running')),
    h('div', { class: 'stage-desc' }, 'Lay the cut list down as a timeline in Resolve.'),
    p.blocked.build && h('div', { class: 'blocked' }, p.blocked.build),
    h('div', { class: 'stage-actions' },
      runButton('dry_run', 'Dry run', false), runButton('build', 'Build in Resolve', true))));
  $('stages').replaceChildren(...cards);

  $('run-all').replaceChildren(
    runButton('make_cuts', 'Run research, select and review', false),
    isRunning('make_cuts')
      ? h('span', { class: 'pill running' }, 'Running')
      : h('span', {}, p.blocked.make_cuts || 'Runs the three cut stages back to back.'));
}

function renderTabs() {
  const check = state.cache['check:' + state.which];
  $('tabs').replaceChildren(...TABS.map(([key, label]) => {
    let badge = null;
    if (key === 'check' && check && !check.invalid) {
      if (check.fails.length) badge = h('span', { class: 'count bad' }, check.fails.length);
      else if (check.warns.length) badge = h('span', { class: 'count warn' }, check.warns.length);
    } else if (key === 'check' && check && check.invalid) {
      badge = h('span', { class: 'count bad' }, '!');
    }
    return h('button', { class: 'tab' + (state.tab === key ? ' active' : ''), onclick: () => setTab(key) },
      label, badge);
  }));
}

function setTab(key) {
  state.tab = key;
  renderTabs();
  renderPanel();
}

// --- running a step ---------------------------------------------------------------

async function run(action, extra) {
  const question = CONFIRM[action] && CONFIRM[action](state.project);
  let options = extra || {};
  if (question) {
    const answer = await ask(question.text, question.ok, question.option);
    if (!answer) return;
    options = { ...options, redo_research: answer.checked };
  }
  await call('start', state.slug, action, options);
  state.tab = 'log';
  await poll();
}

// One poll at a time: two in flight would both fetch, and append, the same lines.
let polling = null;
function poll() {
  if (!polling) polling = pollOnce().finally(() => { polling = null; });
  return polling;
}

async function pollOnce() {
  const result = await api.job_poll(state.job.next, state.job.id);
  if (!result.job) return;

  const fresh = result.job.id !== state.job.id;
  if (fresh) state.log = [];
  const changed = fresh || result.running !== state.job.running;
  state.job = { id: result.job.id, next: result.next, running: result.running, info: result.job,
    exitCode: result.exit_code, cancelled: result.cancelled };
  if (result.lines.length) {
    state.log.push(...result.lines);
    appendLog(result.lines);
  }
  if (changed) await jobChanged();
}

async function jobChanged() {
  const job = state.job;
  $('jobbar').hidden = !job.running;
  $('jobbar-label').textContent = job.running ? job.info.label : '';
  await refreshProjects();
  if (state.slug) await refreshProject();
}

async function pollForever() {
  try { await poll(); } catch (error) { /* the window is closing */ }
  setTimeout(pollForever, 500);
}

window.confirmQuit = async function () {
  if (await ask('A step is still running. Stop it and quit?', 'Stop and quit')) api.quit();
};

// --- panels -------------------------------------------------------------------------

function loadCached(kind, variant) {
  const key = kind + ':' + variant;
  if (state.cache[key]) return Promise.resolve(state.cache[key]);
  const cache = state.cache;
  const request = kind === 'sheet' ? call('sheet', state.slug, variant)
    : kind === 'shorts' ? call('shorts', state.slug) : call(kind, state.slug, variant);
  return request.then((data) => { cache[key] = data; return data; });
}

function setPanel(...nodes) {
  $('panel').replaceChildren(...nodes.filter(Boolean));
}

function panelEmpty(text) {
  setPanel(h('div', { class: 'panel-empty' }, text));
}

async function renderPanel() {
  const p = state.project;
  const token = ++state.renders;
  const current = () => token === state.renders;

  if (state.tab === 'log') return renderLog();
  if (state.tab === 'shorts') {
    try {
      const data = await loadCached('shorts', 'all');
      if (current()) renderShorts(data);
    } catch (error) {
      if (current()) panelEmpty(error.message);
    }
    return;
  }
  if ((state.tab === 'cuts' || state.tab === 'check') && !p.has.cuts) {
    return panelEmpty('No cut list yet. Run Select cuts to make one.');
  }
  if (state.tab === 'research' && !p.has.research) return panelEmpty('No research sheet yet. Run Research.');
  if (state.tab === 'review' && !p.has.review) return panelEmpty('No review yet. Run Review.');

  try {
    if (state.tab === 'cuts') {
      const data = await loadCached('cuts', state.which);
      if (current()) renderCuts(data);
    } else if (state.tab === 'check') {
      const data = await loadCached('check', state.which);
      if (current()) { renderCheck(data); renderTabs(); }
    } else {
      const data = await loadCached('sheet', state.tab);
      if (current()) renderSheet(data);
    }
  } catch (error) {
    if (current()) panelEmpty(error.message);
  }
}

function whichSelect() {
  if (!state.project.has.draft) return null;
  const select = h('select', { onchange: (event) => {
    state.which = event.target.value;
    renderPanel();
    loadCached('check', state.which).then(renderTabs, () => {});
  } },
    h('option', { value: 'final', selected: state.which === 'final' }, 'Reviewed cut list'),
    h('option', { value: 'draft', selected: state.which === 'draft' }, 'Draft (before review)'));
  return h('label', {}, 'Showing ', select);
}

function stat(value, label) {
  return h('div', {}, h('div', { class: 'stat-value' }, value), h('div', { class: 'stat-label' }, label));
}

function renderCuts(data) {
  const body = h('tbody', {});
  const shown = h('span', { class: 'hint' });

  const fill = () => {
    const needle = state.filter.trim().toLowerCase();
    const rows = data.segments.filter((s) =>
      (!state.flaggedOnly || s.fix) &&
      (!needle || [s.layout, s.film_beat, s.reason, s.fix].some((t) => t && t.toLowerCase().includes(needle))));
    body.replaceChildren(...rows.map((s) =>
      h('tr', { class: s.fix ? 'flagged' : '' },
        h('td', { class: 'num' }, s.n),
        h('td', { class: 'num' }, clock(s.at)),
        h('td', { class: 'num' }, clock(s.start)),
        h('td', { class: 'num' }, clock(s.end)),
        h('td', { class: 'num' }, (s.end - s.start).toFixed(2)),
        h('td', {}, h('span', { class: 'chip', style: 'background:' + s.color }, s.layout)),
        h('td', { class: 'beat' }, s.iconic && h('span', { class: 'star', title: 'Iconic' }, '★ '), s.film_beat || ''),
        h('td', {}, s.reason, s.fix && h('div', { class: 'fix' }, 'Fix: ' + s.fix)))));
    shown.textContent = rows.length === data.segments.length ? '' : `${rows.length} of ${data.segments.length} shown`;
  };

  const hook = data.hook && (typeof data.hook === 'string' ? data.hook
    : data.hook.line || data.hook.text || data.hook.reason || JSON.stringify(data.hook));

  setPanel(
    h('div', { class: 'stats' },
      stat(runtime(data.total), 'runtime'),
      stat(data.count, 'segments'),
      stat(data.flagged, 'flagged to fix'),
      stat(data.offset === null || data.offset === undefined ? '-' : data.offset + 's', 'movie offset')),
    h('div', { class: 'mixbar' }, data.mix.map((m) =>
      h('span', { style: `background:${m.color};width:${m.share}%`, title: `${m.layout} ${m.share.toFixed(1)}%` }))),
    h('div', { class: 'legend' }, data.mix.map((m) =>
      h('span', { class: 'legend-item' }, h('span', { class: 'swatch', style: 'background:' + m.color }),
        `${m.layout} ${m.share.toFixed(1)}% (${runtime(m.seconds)})`))),
    hook && h('div', { class: 'hook' }, h('b', {}, 'HOOK'), hook),
    h('div', { class: 'toolbar' },
      h('input', { type: 'search', placeholder: 'Filter by beat, reason or layout', value: state.filter,
        oninput: (event) => { state.filter = event.target.value; fill(); } }),
      h('label', {}, h('input', { type: 'checkbox', checked: state.flaggedOnly,
        onchange: (event) => { state.flaggedOnly = event.target.checked; fill(); } }), ' Flagged only'),
      whichSelect(), shown, h('span', { class: 'spacer' }), h('span', { class: 'hint' }, 'cuts/' + data.file)),
    h('table', {},
      h('thead', {}, h('tr', {},
        h('th', { class: 'num' }, '#'), h('th', { class: 'num' }, 'Timeline'), h('th', { class: 'num' }, 'In'),
        h('th', { class: 'num' }, 'Out'), h('th', { class: 'num' }, 'Secs'), h('th', {}, 'Layout'),
        h('th', {}, 'Film beat'), h('th', {}, 'Reason'))),
      body));
  fill();
}

function renderCheck(data) {
  const toolbar = h('div', { class: 'toolbar' }, whichSelect());
  if (data.invalid) {
    setPanel(
      h('div', { class: 'verdict bad' }, 'The cut list is not valid, so nothing else was measured.'),
      toolbar,
      h('div', { class: 'findings' }, finding('fail', 'FAIL', data.invalid)));
    return;
  }
  setPanel(
    h('div', { class: 'verdict ' + (data.fails.length ? 'bad' : 'ok') },
      `${data.fails.length} hard failure(s), ${data.warns.length} warning(s)`),
    h('div', { class: 'hint' }, `cuts/${data.file}: ${data.count} segments, ${(data.total / 60).toFixed(1)} min`),
    toolbar,
    h('table', { class: 'check-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Layout mix'), h('th', { class: 'num' }, 'Share of runtime'),
        h('th', {}, 'Target'))),
      h('tbody', {}, data.mix.map((row) =>
        h('tr', {}, h('td', {}, row.name), h('td', { class: 'num' }, row.share.toFixed(1) + '%'),
          h('td', {}, row.target))))),
    h('div', { class: 'findings' },
      data.fails.map((line) => finding('fail', 'FAIL', line)),
      data.warns.map((line) => finding('warn', 'WARN', line)),
      data.notes.map((line) => finding('note', 'NOTE', line))));
}

function finding(kind, tag, text) {
  return h('div', { class: 'finding ' + kind }, h('span', { class: 'tag' }, tag), h('span', { class: 'body' }, text));
}

function renderSheet(data) {
  const sheet = h('div', { class: 'sheet' });
  sheet.innerHTML = data.html;   // rendered by ui/projects.py with raw HTML stripped
  setPanel(sheet);
}

// --- shorts -----------------------------------------------------------------------------

function actionButton(action, label, primary, extra, why) {
  const reason = why || state.project.blocked[action];
  const busy = state.job.running;
  return h('button', {
    class: 'btn small' + (primary ? ' primary' : ''),
    disabled: Boolean(reason) || busy,
    title: reason || (busy ? 'Another step is running.' : null),
    onclick: () => run(action, extra),
  }, label);
}

function renderShorts(data) {
  mountEditor();
  const selectButton = actionButton('select_shorts', data.exists ? 'Select again' : 'Select shorts', !data.exists);
  if (!data.exists) {
    setPanel(
      h('div', { class: 'toolbar' }, selectButton,
        h('span', { class: 'hint' }, state.project.blocked.select_shorts ||
          'Picks the film\'s best moments with your reactions and writes the shorts file.')),
      h('div', { class: 'panel-empty' }, 'No shorts yet.'));
    return;
  }

  const crop = h('input', { type: 'number', min: '0', max: '100', step: '1', id: 'shorts-crop',
    value: Math.round(data.crop_x * 100) });
  const nudge = h('input', { type: 'number', step: '0.01', id: 'shorts-nudge', value: data.nudge });
  setPanel(
    h('div', { class: 'toolbar' },
      selectButton,
      actionButton('tighten_shorts', 'Tighten', false),
      !state.project.has.proxies && actionButton('make_proxies', 'Make proxies', false),
      actionButton('preview_shorts', 'Preview stills', false),
      actionButton('render_shorts', 'Render all', true),
      h('button', { class: 'btn small', onclick: () => call('open_shorts_folder', state.slug).catch(() => {}) },
        'Open folder'),
      h('span', { class: 'spacer' }),
      h('label', { title: 'Which part of the camera frame the bottom half shows: 0 is the left edge, 100 the right.' },
        'Hosts crop ', crop, ' %'),
      h('label', { title: 'Seconds to play the film later (+) or earlier (-) against your reactions.' },
        'Film nudge ', nudge, ' s'),
      h('button', { class: 'btn small', onclick: saveShortsOptions }, 'Save')),
    h('div', { class: 'shorts' }, data.shorts.map((short) => shortCard(short, data))));
}

async function saveShortsOptions() {
  await call('set_shorts_options', state.slug, $('shorts-crop').value, $('shorts-nudge').value);
  await refreshProject();
}

function shortCard(short, data) {
  const failed = short.fails.length > 0;
  const base = `${data.media_url}/${short.number}`;
  let media;
  if (short.video) {
    media = h('video', { controls: true, preload: 'metadata', playsinline: true,
      poster: short.preview ? `${base}/preview?v=${short.preview}` : null,
      src: `${base}/video?v=${short.video}` });
  } else if (short.preview) {
    media = h('img', { src: `${base}/preview?v=${short.preview}`, alt: 'Preview still' });
  } else {
    media = h('div', { class: 'short-blank' }, 'Not rendered');
  }

  // Kept outside the DOM: the panel is redrawn whenever a step starts or finishes.
  const draftKey = `${state.slug}:${short.number}`;
  const feedback = h('textarea', { rows: '3',
    placeholder: 'What should change? e.g. "Open on Theresa\'s scream instead" or "the setup line is too long".',
    oninput: (event) => { state.drafts[draftKey] = event.target.value; } });
  feedback.value = state.drafts[draftKey] || '';
  const number = { number: short.number };
  const state_ = failed ? ['bad', 'Breaks a limit']
    : !short.video ? ['todo', 'Not rendered']
    : short.stale ? ['warn', 'Changed since render'] : ['done', 'Rendered'];

  return h('div', { class: 'short' },
    h('div', { class: 'short-media' }, media),
    h('div', { class: 'short-body' },
      h('div', { class: 'short-head' },
        h('span', { class: 'short-name' }, `${short.number}. ${short.name}`),
        h('span', { class: 'pill ' + state_[0] }, state_[1]),
        h('span', { class: 'hint' }, [runtime(short.runtime),
          short.type, short.score === null ? null : `score ${short.score}`].filter(Boolean).join(' · '))),
      short.yt_title && h('div', { class: 'short-title' }, short.yt_title),
      short.hook_text && h('div', { class: 'hint' }, 'Top text: ' + short.hook_text),
      (short.fails.length || short.warns.length) ? h('div', { class: 'findings' },
        short.fails.map((line) => finding('fail', 'FAIL', line)),
        short.warns.map((line) => finding('warn', 'WARN', line))) : null,
      h('table', { class: 'short-segments' }, h('tbody', {}, short.segments.map((segment, index) =>
        h('tr', {},
          h('td', { class: 'num' }, index + 1),
          h('td', { class: 'num' }, (segment.end - segment.start).toFixed(1) + 's'),
          h('td', {}, segment.layout === 'panel' ? 'film + us' : 'us only'),
          h('td', {}, segment.reason,
            segment.captions && segment.captions.length ? h('div', { class: 'caption-line' },
              segment.captions.map((c) => h('span', { class: 'who-' + (c.who === 'film' ? 'film' : 'us') },
                c.text + ' '))) : null))))),
      h('div', { class: 'stage-actions' },
        h('button', {
          class: 'btn small',
          disabled: !state.project.has.proxies,
          title: state.project.has.proxies ? 'Cut, trim and caption this short on a timeline.'
            : 'Make proxies first (toolbar above): the editor plays small copies of both recordings.',
          onclick: () => openEditor(short.number).catch(() => {}),
        }, 'Edit'),
        actionButton('render_shorts', short.video ? 'Render again' : 'Render', !short.video || short.stale,
          number, failed ? 'Fix the failure first: send feedback below.' : null),
        actionButton('preview_shorts', 'Preview still', false, number,
          failed ? 'Fix the failure first: send feedback below.' : null)),
      h('div', { class: 'short-feedback' },
        feedback,
        h('button', {
          class: 'btn small',
          disabled: state.job.running || Boolean(state.project.blocked.short_feedback),
          title: state.project.blocked.short_feedback || (state.job.running ? 'Another step is running.' : null),
          onclick: () => {
            if (!feedback.value.trim()) return toast('Write the feedback first.');
            const text = feedback.value;
            delete state.drafts[draftKey];
            run('short_feedback', { number: short.number, feedback: text })
              .catch(() => { state.drafts[draftKey] = text; });
          },
        }, 'Send feedback to Claude'))));
}

function renderLog() {
  const job = state.job;
  let stateText = 'Nothing has run yet.';
  if (job.info) {
    stateText = job.running ? 'Running' : job.cancelled ? 'Cancelled'
      : job.exitCode === 0 ? 'Finished' : `Failed (exit code ${job.exitCode})`;
  }
  const log = h('pre', { id: 'log' }, state.log.join('\n') + (state.log.length ? '\n' : ''));
  setPanel(
    h('div', { class: 'log-head' },
      h('h2', { style: 'margin:0' }, job.info ? job.info.label : 'Log'),
      h('span', { class: 'log-state' }, stateText),
      h('span', { class: 'spacer' }),
      job.running && h('button', { class: 'btn small danger', onclick: cancelJob }, 'Cancel')),
    log);
  log.scrollTop = log.scrollHeight;
}

function appendLog(lines) {
  const log = $('log');
  if (!log || state.tab !== 'log') return;
  const pinned = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  log.append(lines.join('\n') + '\n');
  if (pinned) log.scrollTop = log.scrollHeight;
}

async function cancelJob() {
  if (await ask('Stop ' + state.job.info.label + '?', 'Stop it')) api.job_cancel();
}

// --- new project ----------------------------------------------------------------------

function openNewProject() {
  state.slug = null;
  renderSidebar();
  $('new-form').reset();
  showView('new');
  $('new-title').focus();
}

async function submitNewProject(event) {
  event.preventDefault();
  const fields = [$('new-title').value, $('new-reaction').value, $('new-movie').value, $('new-offset').value];
  let result = await call('create_project', ...fields, false);
  if (result.exists) {
    if (!await ask(`A project called "${fields[0].trim()}" already exists. Replace its settings?`, 'Replace')) return;
    result = await call('create_project', ...fields, true);
  }
  await refreshProjects();
  await selectProject(result.slug);
}

// --- start -----------------------------------------------------------------------------

function start() {
  api = window.pywebview.api;

  $('new-project').addEventListener('click', openNewProject);
  $('new-form').addEventListener('submit', submitNewProject);
  $('new-cancel').addEventListener('click', () => showView('empty'));
  for (const button of document.querySelectorAll('[data-browse]')) {
    button.addEventListener('click', async () => {
      const picked = await call('pick_file');
      if (picked.path) $(button.dataset.browse).value = picked.path;
    });
  }
  $('jobbar-cancel').addEventListener('click', cancelJob);
  $('jobbar-log').addEventListener('click', () => {
    const slug = state.job.info.slug;
    state.tab = 'log';
    if (slug && slug !== state.slug) selectProject(slug);
    else if (state.slug) setTab('log');
  });
  // Links in the sheets open in the real browser, not in this window.
  document.addEventListener('click', (event) => {
    const link = event.target.closest && event.target.closest('a[href]');
    if (!link) return;
    event.preventDefault();
    api.open_external(link.href);
  });

  refreshProjects().catch(() => {});
  pollForever();
}

if (window.pywebview && window.pywebview.api) start();
else window.addEventListener('pywebviewready', start);
