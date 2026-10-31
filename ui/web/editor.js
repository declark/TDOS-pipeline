'use strict';

// The shorts editor: a small timeline over one short, with a live preview.
//
// It plays the proxies src/make_proxies.py writes (the originals are too big
// for the window's player), lays the short out as the renderer will - title
// band, film, us, captions on the seam - and edits a draft of the short that
// is only written to cuts/<slug>.shorts.json on Save. The checks and caption
// groups shown are ui/shorts_edit.py's, so they match check_cuts and the
// renderer exactly.
//
// The editor covers the whole window while it's open. Its DOM is built once
// and lives outside the panel, which is redrawn whenever a job ticks:
// rebuilding it would reload both videos.

const SNAP_PX = 8;
const MIN_CLIP = 0.1;           // seconds
const UNDO_LIMIT = 100;
const TIMELINE_ROOM = 300;      // px kept below the monitor for the timeline
const SHORTS_WRITERS = ['select_shorts', 'short_feedback', 'tighten_shorts'];

// --- opening and closing ------------------------------------------------------------

async function openEditor(number) {
  const view = await call('short_editor', state.slug, number);
  const ed = {
    slug: state.slug,
    number,
    view,
    draft: clone(view.short),
    saved: JSON.stringify(view.short),
    version: view.version,
    undo: [],
    redo: [],
    selected: { clip: 0, caption: null, bleep: null },
    playhead: 0,
    playing: false,
    pps: 60,                 // timeline pixels per second
    snap: true,
    checks: null,
    peaks: { us: [], film: [] },  // loaded windows of loudness, each {start, rate, db}
    words: { us: [], film: [] },
    root: null,
  };
  state.editor = ed;
  buildEditor(ed);
  document.body.append(ed.root);
  refreshLock(ed);
  fitZoom(ed);
  await loadWaveforms(ed);
  refreshEditor(ed);
  seek(ed, 0);
  scheduleCheck(ed, 0);
}

async function closeEditor() {
  const ed = state.editor;
  if (!ed) return;
  if (isDirty(ed) && !await ask('Close the editor and lose the unsaved changes?', 'Discard')) return;
  pause(ed);
  if (ed.tone) ed.tone.context.close();
  ed.root.remove();
  state.editor = null;
  delete state.cache['shorts:all'];
  renderPanel();
}

// Called whenever the shorts panel redraws: keeps the editor's lock up to date.
function mountEditor() {
  if (state.editor) refreshLock(state.editor);
  return false;
}

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function isDirty(ed) { return JSON.stringify(ed.draft) !== ed.saved; }

// --- the program: clips laid end to end --------------------------------------------------

function clips(ed) { return ed.draft.segments; }
function clipLength(clip) { return clip.end - clip.start; }
function programLength(ed) { return clips(ed).reduce((sum, c) => sum + clipLength(c), 0); }

function clipStarts(ed) {
  const starts = [];
  let at = 0;
  for (const clip of clips(ed)) { starts.push(at); at += clipLength(clip); }
  return starts;
}

// Program seconds -> { index, source } (source = recording time).
function locate(ed, t) {
  const list = clips(ed);
  let at = 0;
  for (let i = 0; i < list.length; i++) {
    const length = clipLength(list[i]);
    if (t < at + length || i === list.length - 1) {
      return { index: i, source: list[i].start + Math.min(Math.max(t - at, 0), length) };
    }
    at += length;
  }
  return { index: 0, source: list[0].start };
}

function frame(ed) { return 1 / ed.view.fps; }
function onFrame(ed, seconds) { return Math.round(seconds * ed.view.fps) / ed.view.fps; }

// --- building the DOM -------------------------------------------------------------------

function buildEditor(ed) {
  const v = ed.view;
  // As tall as the window allows with the timeline still in view.
  const monitorHeight = Math.max(420, Math.min(820, window.innerHeight - TIMELINE_ROOM));
  const scale = monitorHeight / v.frame.height;
  const MONITOR_WIDTH = Math.round(v.frame.width * scale);
  const px = (n) => `${Math.round(n * scale)}px`;

  const hosts = h('video', { class: 'ed-video', preload: 'auto', playsinline: true, src: v.proxy_urls.us });
  const film = h('video', { class: 'ed-video', preload: 'auto', playsinline: true, src: v.proxy_urls.film });
  hosts.style.objectPosition = `${v.hosts_crop_x * 100}% 50%`;
  hosts.volume = Math.min(1, v.hosts_gain);
  film.volume = Math.min(1, v.film_gain);
  ed.hosts = hosts;
  ed.film = film;

  const safe = v.frame.safe;
  const band = h('div', { class: 'ed-band', style: `height:${px(v.frame.band)};` +
      `padding-top:${px(safe.top)};color:${v.frame.title_color}` },
    v.band_lines.map((line, i) => h('div', {
      style: `font-size:${px(line.size)};font-weight:${i === 0 ? 600 : 700}` }, line.text)));
  ed.caption = h('div', { class: 'ed-caption', style: `top:${px(v.frame.band + v.frame.film)};` +
      `font-size:${px(v.caption_style.size)};` +
      `-webkit-text-stroke:${px(v.caption_style.stroke_width * 2)} ${v.caption_style.stroke}` });
  const monitor = h('div', { class: 'ed-monitor', style: `width:${MONITOR_WIDTH}px;` +
      `height:${px(v.frame.height)};background:${v.frame.background}` },
    band,
    h('div', { class: 'ed-film', style: `height:${px(v.frame.film)}` }, film),
    h('div', { class: 'ed-hosts', style: `height:${px(v.frame.hosts)}` }, hosts),
    ed.caption);

  ed.timeReadout = h('span', { class: 'ed-time' });
  ed.playButton = h('button', { class: 'btn small', onclick: () => togglePlay(ed) }, 'Play');
  const transport = h('div', { class: 'ed-transport' },
    h('button', { class: 'btn small', title: 'Start (Home)', onclick: () => seek(ed, 0) }, '|<'),
    h('button', { class: 'btn small', title: 'Back a frame (Left)', onclick: () => step(ed, -frame(ed)) }, '<'),
    ed.playButton,
    h('button', { class: 'btn small', title: 'On a frame (Right)', onclick: () => step(ed, frame(ed)) }, '>'),
    ed.timeReadout);

  ed.inspector = h('div', { class: 'ed-inspector' });
  ed.checksBox = h('div', { class: 'ed-checks' });
  ed.lockBanner = h('div', { class: 'ed-lock', hidden: true });
  ed.saveButton = h('button', { class: 'btn small', onclick: () => saveEditor(ed, false) }, 'Save');
  ed.renderButton = h('button', { class: 'btn small primary', onclick: () => saveEditor(ed, true) },
    'Save & render');
  ed.title = h('span', { class: 'ed-title' });
  ed.runtimeBadge = h('span', { class: 'pill' });
  const header = h('div', { class: 'toolbar ed-header' },
    h('button', { class: 'btn small', onclick: closeEditor }, '< Shorts'),
    ed.title, ed.runtimeBadge,
    h('span', { class: 'spacer' }),
    h('button', { class: 'btn small', title: 'Undo (Ctrl+Z)', onclick: () => undo(ed) }, 'Undo'),
    h('button', { class: 'btn small', title: 'Redo (Ctrl+Shift+Z)', onclick: () => redo(ed) }, 'Redo'),
    h('button', { class: 'btn small', onclick: () => discard(ed) }, 'Discard changes'),
    ed.saveButton, ed.renderButton);

  // Timeline: ruler canvas, the clip track, the caption track, the playhead.
  ed.ruler = h('canvas', { class: 'ed-ruler', height: 22 });
  ed.clipTrack = h('div', { class: 'ed-track ed-clips' });
  ed.captionTrack = h('div', { class: 'ed-track ed-captions' });
  ed.bleepTrack = h('div', { class: 'ed-track ed-bleeps' });
  ed.playheadLine = h('div', { class: 'ed-playhead' });
  ed.dropMarker = h('div', { class: 'ed-drop', hidden: true });
  ed.lane = h('div', { class: 'ed-lane' }, ed.ruler, ed.clipTrack, ed.captionTrack, ed.bleepTrack,
    ed.playheadLine, ed.dropMarker);
  ed.scroller = h('div', { class: 'ed-scroller' }, ed.lane);
  ed.snapBox = h('input', { type: 'checkbox', checked: true,
    onchange: (event) => { ed.snap = event.target.checked; } });
  const timelineBar = h('div', { class: 'toolbar ed-timeline-bar' },
    h('button', { class: 'btn small', title: 'Split the clip at the playhead (S)', onclick: () => split(ed) },
      'Split'),
    h('button', { class: 'btn small', title: 'Copy the selected clip after itself', onclick: () => duplicate(ed) },
      'Duplicate'),
    h('button', { class: 'btn small', title: 'Ripple delete (Delete)', onclick: () => removeSelected(ed) },
      'Delete'),
    h('button', { class: 'btn small', title: 'Film + us / us only (L)', onclick: () => toggleLayout(ed) },
      'Toggle film audio'),
    h('button', { class: 'btn small', title: 'A caption at the playhead', onclick: () => addCaption(ed) },
      'Add caption'),
    h('button', { class: 'btn small', title: 'Bleep the word under the playhead (B)', onclick: () => bleepWord(ed) },
      'Bleep'),
    h('button', { class: 'btn small', title: 'Bleep every swear the transcripts hear in this short',
      onclick: () => findSwears(ed) }, 'Find swears'),
    h('span', { class: 'spacer' }),
    h('label', { title: 'Edges snap to words, the playhead and the frame grid. Hold Alt to drag freely.' },
      ed.snapBox, ' Snap'),
    h('button', { class: 'btn small', onclick: () => zoom(ed, 1 / 1.5) }, '-'),
    h('button', { class: 'btn small', onclick: () => fitZoom(ed, true) }, 'Fit'),
    h('button', { class: 'btn small', onclick: () => zoom(ed, 1.5) }, '+'));

  ed.root = h('div', { class: 'editor', tabindex: '-1' },
    header, ed.lockBanner,
    h('div', { class: 'ed-main' },
      h('div', { class: 'ed-left' }, monitor, transport),
      h('div', { class: 'ed-right' }, ed.inspector, ed.checksBox)),
    timelineBar, ed.scroller);

  // Scrub on the ruler or an empty bit of the lane.
  ed.lane.addEventListener('pointerdown', (event) => {
    if (event.target !== ed.ruler && event.target !== ed.lane && event.target !== ed.playheadLine) return;
    scrubFrom(ed, event);
  });
  film.addEventListener('loadeddata', () => seek(ed, ed.playhead));
  hosts.addEventListener('loadeddata', () => seek(ed, ed.playhead));
}

// --- drawing ---------------------------------------------------------------------------------

function refreshEditor(ed) {
  const list = clips(ed);
  if (ed.selected.clip >= list.length) ed.selected = { clip: list.length - 1, caption: null };
  ed.title.textContent = `Short ${ed.number}: ${ed.draft.name || ''}` + (isDirty(ed) ? '  (unsaved)' : '');
  drawTimeline(ed);
  drawInspector(ed);
  drawChecks(ed);
  updatePlayhead(ed);
}

function drawTimeline(ed) {
  const starts = clipStarts(ed);
  const total = programLength(ed);
  const width = Math.max(ed.scroller.clientWidth, Math.ceil((total + 2) * ed.pps));
  ed.lane.style.width = `${width}px`;

  // Ruler: a tick every second, labelled every few depending on zoom.
  const ruler = ed.ruler;
  ruler.width = width;
  const ctx = ruler.getContext('2d');
  const styles = getComputedStyle(document.documentElement);
  ctx.clearRect(0, 0, width, ruler.height);
  ctx.fillStyle = styles.getPropertyValue('--muted');
  ctx.font = '11px sans-serif';
  const every = ed.pps >= 80 ? 1 : ed.pps >= 30 ? 2 : 5;
  for (let s = 0; s <= total + 2; s++) {
    const x = Math.round(s * ed.pps) + 0.5;
    ctx.fillRect(x, s % every === 0 ? 10 : 16, 1, 22);
    if (s % every === 0) ctx.fillText(`${s}s`, x + 3, 10);
  }

  ed.clipTrack.replaceChildren(...clips(ed).map((clip, i) => clipBlock(ed, clip, i, starts[i])));
  const captionBlocks = [];
  clips(ed).forEach((clip, i) => {
    (clip.captions || []).forEach((caption, j) => {
      const from = Math.max(caption.start, clip.start);
      const to = Math.min(caption.end, clip.end);
      if (to <= from) return;
      captionBlocks.push(captionBlock(ed, caption, i, j, starts[i] + from - clip.start, to - from));
    });
  });
  ed.captionTrack.replaceChildren(...captionBlocks);

  const bleepBlocks = [];
  clips(ed).forEach((clip, i) => {
    (clip.bleeps || []).forEach((bleep, j) => {
      const from = Math.max(bleep.start, clip.start);
      const to = Math.min(bleep.end, clip.end);
      if (to <= from) return;
      bleepBlocks.push(bleepBlock(ed, bleep, i, j, starts[i] + from - clip.start, to - from));
    });
  });
  ed.bleepTrack.replaceChildren(...bleepBlocks);
}

function bleepBlock(ed, bleep, clipIndex, bleepIndex, at, length) {
  const selected = ed.selected.clip === clipIndex && ed.selected.bleep === bleepIndex;
  const block = h('div', {
    class: 'ed-cap bleep ' + (bleep.who === 'film' ? 'film' : 'us') + (selected ? ' selected' : ''),
    style: `left:${at * ed.pps}px;width:${Math.max(4, length * ed.pps)}px`,
    title: `Bleep (${bleep.who === 'film' ? 'film' : 'us'}) ${bleep.start.toFixed(2)}-${bleep.end.toFixed(2)}`,
  }, h('span', {}, bleep.who === 'film' ? 'BLEEP film' : 'BLEEP'),
  h('div', { class: 'ed-handle left' }), h('div', { class: 'ed-handle right' }));
  block.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    const handle = event.target.classList.contains('ed-handle')
      ? (event.target.classList.contains('left') ? 'start' : 'end') : 'move';
    captionDrag(ed, event, clipIndex, bleepIndex, handle, 'bleeps');
  });
  return block;
}

function clipBlock(ed, clip, index, at) {
  const selected = ed.selected.clip === index && ed.selected.caption === null && ed.selected.bleep == null;
  const block = h('div', {
    class: 'ed-clip ' + (clip.layout === 'panel' ? 'film' : 'us') + (selected ? ' selected' : ''),
    style: `left:${at * ed.pps}px;width:${Math.max(2, clipLength(clip) * ed.pps)}px`,
    title: `${clip.start.toFixed(2)}-${clip.end.toFixed(2)}  ${clip.reason || ''}`,
  });
  const canvas = h('canvas', { class: 'ed-wave' });
  block.append(canvas,
    h('span', { class: 'ed-clip-label' }, `${index + 1} · ${clipLength(clip).toFixed(1)}s`),
    h('div', { class: 'ed-handle left' }), h('div', { class: 'ed-handle right' }));
  requestAnimationFrame(() => drawWave(ed, canvas, clip, index));

  block.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    const handle = event.target.classList.contains('ed-handle')
      ? (event.target.classList.contains('left') ? 'start' : 'end') : null;
    if (handle) trimFrom(ed, event, index, handle);
    else clipPointer(ed, event, index, at);
  });
  return block;
}

function drawWave(ed, canvas, clip, index) {
  const width = Math.max(2, Math.round(clipLength(clip) * ed.pps));
  const height = canvas.clientHeight || 46;
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  const sources = clip.layout === 'panel' ? [['us', 'rgba(255,230,0,0.8)'], ['film', 'rgba(92,214,255,0.85)']]
    : [['us', 'rgba(255,230,0,0.75)']];
  // Ours rises from the middle line, the film's hangs below it, so both read.
  const middle = Math.round(height / 2);
  for (const [who, color] of sources) {
    const peaks = peaksFor(ed, who, clip);
    if (!peaks || !peaks.db.length) continue;
    const up = who === 'us' || sources.length === 1;
    const room = sources.length === 1 ? middle - 2 : middle - 3;
    ctx.fillStyle = color;
    for (let x = 0; x < width; x++) {
      const t = clip.start + x / ed.pps;
      const k = Math.floor((t - peaks.start) * peaks.rate);
      if (k < 0 || k >= peaks.db.length) continue;
      const level = Math.max(0, (peaks.db[k] + 60) / 60);      // -60..0 dB -> 0..1
      const bar = Math.max(1, level * room);
      if (sources.length === 1) ctx.fillRect(x, middle - bar, 1, 2 * bar);
      else if (up) ctx.fillRect(x, middle - bar, 1, bar);
      else ctx.fillRect(x, middle, 1, bar);
    }
  }
  // Word ticks: ours along the top, the film's along the bottom.
  for (const [who, y, color] of [['us', 0, '#ffe600'], ['film', height - 3, '#5cd6ff']]) {
    ctx.fillStyle = color;
    for (const [start, end] of ed.words[who]) {
      if (end < clip.start || start > clip.end) continue;
      const x0 = (start - clip.start) * ed.pps;
      const x1 = (end - clip.start) * ed.pps;
      ctx.fillRect(Math.max(0, x0), y, Math.max(1, x1 - x0 - 1), 3);
    }
  }
}

function captionBlock(ed, caption, clipIndex, captionIndex, at, length) {
  const selected = ed.selected.clip === clipIndex && ed.selected.caption === captionIndex;
  const block = h('div', {
    class: 'ed-cap ' + (caption.who === 'film' ? 'film' : 'us') + (selected ? ' selected' : ''),
    style: `left:${at * ed.pps}px;width:${Math.max(4, length * ed.pps)}px`,
    title: caption.text,
  }, h('span', {}, caption.text), h('div', { class: 'ed-handle left' }), h('div', { class: 'ed-handle right' }));
  block.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    const handle = event.target.classList.contains('ed-handle')
      ? (event.target.classList.contains('left') ? 'start' : 'end') : 'move';
    captionDrag(ed, event, clipIndex, captionIndex, handle);
  });
  block.addEventListener('dblclick', () => {
    const input = ed.inspector.querySelector('.ed-caption-text');
    if (input) { input.focus(); input.select(); }
  });
  return block;
}

function drawInspector(ed) {
  const clip = clips(ed)[ed.selected.clip];
  const parts = [];
  if (clip) {
    const caption = ed.selected.caption === null ? null : (clip.captions || [])[ed.selected.caption];
    const bleep = ed.selected.bleep == null ? null : (clip.bleeps || [])[ed.selected.bleep];
    if (bleep) {
      parts.push(h('h3', {}, `Bleep in clip ${ed.selected.clip + 1}`),
        h('div', { class: 'ed-row' },
          h('label', {}, 'Who ',
            h('select', { onchange: (event) => edit(ed, () => { bleep.who = event.target.value; }) },
              h('option', { value: 'us', selected: bleep.who !== 'film' }, 'us'),
              h('option', { value: 'film', selected: bleep.who === 'film' }, 'film'))),
          timeField(ed, 'Start', bleep.start, (value) => { bleep.start = value; }),
          timeField(ed, 'End', bleep.end, (value) => { bleep.end = value; })),
        bleep.who === 'film' && clip.layout !== 'panel'
          ? h('div', { class: 'hint' }, 'The film isn\'t heard in this clip, so this bleep does nothing.') : null,
        h('button', { class: 'btn small danger', onclick: () => removeSelected(ed) }, 'Delete bleep'));
    } else if (caption) {
      parts.push(h('h3', {}, `Caption in clip ${ed.selected.clip + 1}`),
        h('label', { class: 'ed-field' }, 'Text',
          h('input', { type: 'text', class: 'ed-caption-text', value: caption.text,
            onchange: (event) => edit(ed, () => { caption.text = event.target.value; }) })),
        h('div', { class: 'ed-row' },
          h('label', {}, 'Who ',
            h('select', { onchange: (event) => edit(ed, () => { caption.who = event.target.value; }) },
              h('option', { value: 'us', selected: caption.who !== 'film' }, 'us'),
              h('option', { value: 'film', selected: caption.who === 'film' }, 'film'))),
          timeField(ed, 'Start', caption.start, (value) => { caption.start = value; }),
          timeField(ed, 'End', caption.end, (value) => { caption.end = value; })),
        h('button', { class: 'btn small danger', onclick: () => removeSelected(ed) }, 'Delete caption'));
    } else {
      parts.push(h('h3', {}, `Clip ${ed.selected.clip + 1} of ${clips(ed).length}`),
        h('div', { class: 'ed-row' },
          timeField(ed, 'In', clip.start, (value) => { clip.start = value; delete clip.trimmed_from; }),
          timeField(ed, 'Out', clip.end, (value) => { clip.end = value; delete clip.trimmed_from; })),
        h('div', { class: 'ed-row' },
          h('label', {}, h('input', { type: 'radio', name: 'ed-layout', checked: clip.layout === 'panel',
            onchange: () => edit(ed, () => { clip.layout = 'panel'; }) }), ' Film + us'),
          h('label', {}, h('input', { type: 'radio', name: 'ed-layout', checked: clip.layout !== 'panel',
            onchange: () => edit(ed, () => { clip.layout = 'panel_hosts_only'; }) }), ' Us only')),
        clip.reason ? h('div', { class: 'hint' }, clip.reason) : null);
    }
  }
  const short = ed.draft;
  const field = (label, key, multiline) => h('label', { class: 'ed-field' }, label,
    h(multiline ? 'textarea' : 'input', { type: 'text', rows: multiline ? '2' : null,
      onchange: (event) => edit(ed, () => { short[key] = event.target.value; }) },
    multiline ? (short[key] || '') : null));
  const fields = [field('Name', 'name'), field('YouTube title', 'yt_title'),
    field('Hook text', 'hook_text'), field('Description', 'description', true)];
  for (const [node, key] of [[fields[0], 'name'], [fields[1], 'yt_title'], [fields[2], 'hook_text']]) {
    node.querySelector('input').value = short[key] || '';
  }
  parts.push(h('details', { class: 'ed-short-fields' }, h('summary', {}, 'Title and description'), fields));
  ed.inspector.replaceChildren(...parts.filter(Boolean));
}

function timeField(ed, label, value, set) {
  const input = h('input', { type: 'number', step: '0.01', value: value.toFixed(2),
    onchange: (event) => edit(ed, () => set(onFrame(ed, Number(event.target.value)))) });
  const nudge = (delta) => edit(ed, () => set(onFrame(ed, value + delta)));
  return h('span', { class: 'ed-time-field' }, label + ' ', input,
    h('button', { class: 'btn tiny', title: '-0.1s', onclick: () => nudge(-0.1) }, '«'),
    h('button', { class: 'btn tiny', title: '-1 frame', onclick: () => nudge(-frame(ed)) }, '‹'),
    h('button', { class: 'btn tiny', title: '+1 frame', onclick: () => nudge(frame(ed)) }, '›'),
    h('button', { class: 'btn tiny', title: '+0.1s', onclick: () => nudge(0.1) }, '»'));
}

function drawChecks(ed) {
  const checks = ed.checks;
  const total = programLength(ed);
  const limits = ed.view.limits;
  ed.runtimeBadge.textContent = `${total.toFixed(1)}s`;
  ed.runtimeBadge.className = 'pill ' + (total > limits.max ? 'bad'
    : total < limits.target[0] || total > limits.target[1] ? 'warn' : 'done');
  if (!checks) { ed.checksBox.replaceChildren(); return; }
  ed.checksBox.replaceChildren(...[
    h('h3', {}, 'Checks'),
    !checks.fails.length && !checks.warns.length ? h('div', { class: 'hint' }, 'No problems.') : null,
    ...checks.fails.map((line) => finding('fail', 'FAIL', line)),
    ...checks.warns.map((line) => finding('warn', 'WARN', line))].filter(Boolean));
}

function refreshLock(ed) {
  const info = state.job.info;
  const locked = state.job.running && info && info.slug === ed.slug && SHORTS_WRITERS.includes(info.action);
  // The editor covers the job bar, so say what's running here.
  ed.lockBanner.hidden = !state.job.running;
  ed.lockBanner.classList.toggle('busy', Boolean(state.job.running && !locked));
  ed.lockBanner.textContent = !state.job.running ? ''
    : locked ? `${info.label} is rewriting the shorts file. Save once it's finished.`
    : `Running: ${info.label}`;
  ed.saveButton.disabled = ed.renderButton.disabled = Boolean(locked);
}

// --- edits, undo, checks --------------------------------------------------------------------

// Every change to the draft goes through here, so it can be undone.
function edit(ed, change, before) {
  ed.undo.push(before || JSON.stringify(ed.draft));
  if (ed.undo.length > UNDO_LIMIT) ed.undo.shift();
  ed.redo = [];
  change();
  tidy(ed);
  refreshEditor(ed);
  seek(ed, Math.min(ed.playhead, programLength(ed)));
  scheduleCheck(ed);
}

// Keep every clip and caption sane after an edit.
function tidy(ed) {
  const length = ed.view.durations.us || Infinity;
  for (const clip of clips(ed)) {
    clip.start = Math.max(0, clip.start);
    clip.end = Math.min(length, Math.max(clip.end, clip.start + MIN_CLIP));
    for (const caption of clip.captions || []) {
      caption.end = Math.max(caption.end, caption.start + 0.05);
    }
    for (const bleep of clip.bleeps || []) {
      bleep.end = Math.max(bleep.end, bleep.start + 0.05);
    }
  }
}

function undo(ed) {
  if (!ed.undo.length) return;
  ed.redo.push(JSON.stringify(ed.draft));
  ed.draft = JSON.parse(ed.undo.pop());
  afterHistory(ed);
}

function redo(ed) {
  if (!ed.redo.length) return;
  ed.undo.push(JSON.stringify(ed.draft));
  ed.draft = JSON.parse(ed.redo.pop());
  afterHistory(ed);
}

async function afterHistory(ed) {
  ed.selected = { clip: Math.min(ed.selected.clip, clips(ed).length - 1), caption: null };
  await loadWaveforms(ed);
  refreshEditor(ed);
  seek(ed, Math.min(ed.playhead, programLength(ed)));
  scheduleCheck(ed);
}

async function discard(ed) {
  if (!isDirty(ed)) return;
  if (!await ask('Throw away every change since the last save?', 'Discard')) return;
  ed.undo.push(JSON.stringify(ed.draft));
  ed.draft = JSON.parse(ed.saved);
  afterHistory(ed);
}

let checkTimer = null;
function scheduleCheck(ed, delay = 300) {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(async () => {
    const draft = clone(ed.draft);
    try {
      const result = await call('short_draft_state', ed.slug, ed.number, draft);
      if (state.editor !== ed) return;
      ed.checks = result;
      drawChecks(ed);
      showCaption(ed);
    } catch (error) { /* shown as a toast */ }
  }, delay);
}

async function saveEditor(ed, render) {
  pause(ed);
  try {
    const result = await call('save_short', ed.slug, ed.number, clone(ed.draft), ed.version, render);
    ed.version = result.version;
    ed.saved = JSON.stringify(ed.draft);
    delete state.cache['shorts:all'];
    refreshEditor(ed);
    toast(render ? 'Saved. Rendering the short - it shows on its card when it\'s done.' : 'Saved.');
    if (render) poll();
  } catch (error) {
    if (/changed since the editor opened/.test(error.message)
        && await ask('The shorts file was changed by another step. Reload it? Your unsaved edits will be lost.',
          'Reload')) {
      state.editor = null;
      openEditor(ed.number);
    }
  }
}

// --- clip operations -----------------------------------------------------------------------

function split(ed) {
  const { index, source } = locate(ed, ed.playhead);
  const clip = clips(ed)[index];
  const at = onFrame(ed, source);
  if (at - clip.start < frame(ed) || clip.end - at < frame(ed)) return toast('Move the playhead inside a clip.');
  edit(ed, () => {
    const second = clone(clip);
    clip.end = at;
    second.start = at;
    delete clip.trimmed_from;
    delete second.trimmed_from;
    if (clip.captions) {
      clip.captions = clip.captions.filter((c) => c.start < at);
      second.captions = second.captions.filter((c) => c.end > at);
    }
    if (clip.bleeps) {
      // A bleep across the cut goes on in both halves, so the word stays covered.
      clip.bleeps = clip.bleeps.filter((b) => b.start < at).map((b) => ({ ...b, end: Math.min(b.end, at) }));
      second.bleeps = second.bleeps.filter((b) => b.end > at).map((b) => ({ ...b, start: Math.max(b.start, at) }));
    }
    clips(ed).splice(index + 1, 0, second);
    ed.selected = { clip: index + 1, caption: null };
  });
}

function duplicate(ed) {
  const index = ed.selected.clip;
  edit(ed, () => {
    clips(ed).splice(index + 1, 0, clone(clips(ed)[index]));
    ed.selected = { clip: index + 1, caption: null };
  });
  loadWaveforms(ed).then(() => drawTimeline(ed));
}

function removeSelected(ed) {
  const clip = clips(ed)[ed.selected.clip];
  if (ed.selected.bleep != null) {
    edit(ed, () => {
      clip.bleeps.splice(ed.selected.bleep, 1);
      if (!clip.bleeps.length) delete clip.bleeps;
      ed.selected = { clip: ed.selected.clip, caption: null };
    });
    return;
  }
  if (ed.selected.caption !== null) {
    edit(ed, () => {
      clip.captions.splice(ed.selected.caption, 1);
      ed.selected = { clip: ed.selected.clip, caption: null };
    });
    return;
  }
  if (clips(ed).length === 1) return toast('A short needs at least one clip.');
  edit(ed, () => {
    clips(ed).splice(ed.selected.clip, 1);
    ed.selected = { clip: Math.max(0, ed.selected.clip - 1), caption: null };
  });
  loadWaveforms(ed).then(() => drawTimeline(ed));
}

function toggleLayout(ed) {
  const clip = clips(ed)[ed.selected.clip];
  edit(ed, () => { clip.layout = clip.layout === 'panel' ? 'panel_hosts_only' : 'panel'; });
}

function addCaption(ed) {
  const { index, source } = locate(ed, ed.playhead);
  const clip = clips(ed)[index];
  const start = onFrame(ed, Math.min(source, clip.end - 0.3));
  edit(ed, () => {
    clip.captions = clip.captions || [];
    clip.captions.push({ who: 'us', start,
      end: Math.min(clip.end, start + 1.0), text: 'New caption' });
    clip.captions.sort((a, b) => a.start - b.start);
    ed.selected = { clip: index, caption: clip.captions.findIndex((c) => c.start === start) };
  });
  const input = ed.inspector.querySelector('.ed-caption-text');
  if (input) { input.focus(); input.select(); }
}

// Bleep the transcript word under the playhead (ours first, then the film's
// where it's heard), or half a second from the playhead if no word is there.
function bleepWord(ed) {
  const { index, source } = locate(ed, ed.playhead);
  const clip = clips(ed)[index];
  const pad = ed.view.bleep.pad;
  const sides = clip.layout === 'panel' ? ['us', 'film'] : ['us'];
  let bleep = null;
  for (const who of sides) {
    const word = ed.words[who].find(([start, end]) => start - pad <= source && source <= end + pad);
    if (word) { bleep = { who, start: word[0] - pad, end: word[1] + pad }; break; }
  }
  if (!bleep) bleep = { who: 'us', start: source, end: source + 0.5 };
  bleep.start = onFrame(ed, Math.max(clip.start, bleep.start));
  bleep.end = onFrame(ed, Math.min(clip.end, bleep.end));
  if (bleep.end - bleep.start < 0.05) return toast('Move the playhead inside a clip.');
  edit(ed, () => {
    clip.bleeps = clip.bleeps || [];
    clip.bleeps.push(bleep);
    clip.bleeps.sort((a, b) => a.start - b.start);
    ed.selected = { clip: index, caption: null, bleep: clip.bleeps.indexOf(bleep) };
  });
}

async function findSwears(ed) {
  let found;
  try { found = await call('short_find_swears', ed.slug, ed.number, clone(ed.draft)); } catch (error) { return; }
  if (state.editor !== ed) return;
  const fresh = [];
  for (const [index, bleeps] of Object.entries(found)) {
    const clip = clips(ed)[Number(index)];
    for (const bleep of bleeps) {
      const covered = (clip.bleeps || []).some((b) => b.who === bleep.who
        && b.start <= bleep.end && bleep.start <= b.end);
      if (!covered) fresh.push([clip, bleep]);
    }
  }
  if (!fresh.length) return toast('No swears found that aren\'t bleeped already.');
  edit(ed, () => {
    for (const [clip, bleep] of fresh) {
      clip.bleeps = clip.bleeps || [];
      clip.bleeps.push(bleep);
      clip.bleeps.sort((a, b) => a.start - b.start);
    }
  });
  toast(`Bleeped ${fresh.length} word${fresh.length === 1 ? '' : 's'}. Play it through to check them.`);
}

// --- dragging ----------------------------------------------------------------------------------

// Follow a drag on the window, not the element: trims redraw the timeline as
// they go, which replaces the element the drag started on.
function dragging(event, move, done) {
  const id = event.pointerId;
  const onMove = (e) => { if (e.pointerId === id) move(e); };
  const onUp = (e) => {
    if (e.pointerId !== id) return;
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', onUp);
    done(e);
  };
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);
}

function laneX(ed, event) {
  return event.clientX - ed.lane.getBoundingClientRect().left;
}

// Snap a recording time: to word edges, the playhead (in this clip), the frame grid.
function snapTime(ed, t, clipIndex, event) {
  if (!ed.snap || event.altKey) return onFrame(ed, t);
  const reach = SNAP_PX / ed.pps;
  let best = null;
  const consider = (candidate) => {
    if (Math.abs(candidate - t) <= reach && (best === null || Math.abs(candidate - t) < Math.abs(best - t))) {
      best = candidate;
    }
  };
  const clip = clips(ed)[clipIndex];
  const sides = clip.layout === 'panel' ? ['us', 'film'] : ['us'];
  for (const who of sides) for (const [start, end] of ed.words[who]) { consider(start); consider(end); }
  const here = locate(ed, ed.playhead);
  if (here.index === clipIndex) consider(here.source);
  return onFrame(ed, best === null ? t : best);
}

function trimFrom(ed, event, index, edge) {
  const before = JSON.stringify(ed.draft);
  const clip = clips(ed)[index];
  const original = { start: clip.start, end: clip.end };
  const x0 = event.clientX;
  ed.selected = { clip: index, caption: null };
  pause(ed);
  dragging(event, (e) => {
    const delta = (e.clientX - x0) / ed.pps;
    if (edge === 'start') {
      clip.start = Math.min(snapTime(ed, original.start + delta, index, e), clip.end - MIN_CLIP);
    } else {
      clip.end = Math.max(snapTime(ed, original.end + delta, index, e), clip.start + MIN_CLIP);
    }
    tidy(ed);
    drawTimeline(ed);
    // Show the frame at the edge being dragged.
    const starts = clipStarts(ed);
    seek(ed, edge === 'start' ? starts[index] : starts[index] + clipLength(clip) - frame(ed) / 2);
  }, () => {
    if (clip.start === original.start && clip.end === original.end) { refreshEditor(ed); return; }
    delete clip.trimmed_from;
    const after = JSON.stringify(ed.draft);
    ed.draft = JSON.parse(before);
    edit(ed, () => { ed.draft = JSON.parse(after); }, before);
    loadWaveforms(ed).then(() => drawTimeline(ed));
  });
}

function clipPointer(ed, event, index, at) {
  const x0 = event.clientX;
  let moved = false;
  dragging(event, (e) => {
    if (!moved && Math.abs(e.clientX - x0) < 5) return;
    moved = true;
    const target = dropIndex(ed, laneX(ed, e));
    const starts = clipStarts(ed);
    const x = target < starts.length ? starts[target] : programLength(ed);
    ed.dropMarker.hidden = false;
    ed.dropMarker.style.left = `${x * ed.pps - 1}px`;
  }, (e) => {
    ed.dropMarker.hidden = true;
    if (!moved) {
      // A click: select the clip and put the playhead where it was clicked.
      ed.selected = { clip: index, caption: null };
      refreshEditor(ed);
      seek(ed, Math.max(0, laneX(ed, e) / ed.pps));
      return;
    }
    let target = dropIndex(ed, laneX(ed, e));
    if (target === index || target === index + 1) return;
    edit(ed, () => {
      const [clip] = clips(ed).splice(index, 1);
      if (target > index) target -= 1;
      clips(ed).splice(target, 0, clip);
      ed.selected = { clip: target, caption: null };
    });
    loadWaveforms(ed).then(() => drawTimeline(ed));
  });
}

// Where a dragged clip would land: before the clip whose middle is right of x.
function dropIndex(ed, x) {
  const starts = clipStarts(ed);
  const t = x / ed.pps;
  for (let i = 0; i < starts.length; i++) {
    if (t < starts[i] + clipLength(clips(ed)[i]) / 2) return i;
  }
  return starts.length;
}

// Drags a caption, or a bleep with kind 'bleeps': both are spans inside a clip.
function captionDrag(ed, event, clipIndex, captionIndex, mode, kind = 'captions') {
  const before = JSON.stringify(ed.draft);
  const clip = clips(ed)[clipIndex];
  const caption = clip[kind][captionIndex];
  const original = { start: caption.start, end: caption.end };
  const x0 = event.clientX;
  const selection = kind === 'bleeps' ? { clip: clipIndex, caption: null, bleep: captionIndex }
    : { clip: clipIndex, caption: captionIndex };
  ed.selected = selection;
  drawInspector(ed);
  let moved = false;
  dragging(event, (e) => {
    const delta = (e.clientX - x0) / ed.pps;
    if (!moved && Math.abs(e.clientX - x0) < 3) return;
    moved = true;
    if (mode === 'move') {
      const length = original.end - original.start;
      const start = Math.min(Math.max(snapTime(ed, original.start + delta, clipIndex, e), clip.start),
        clip.end - length);
      caption.start = start;
      caption.end = start + length;
    } else if (mode === 'start') {
      caption.start = Math.min(Math.max(snapTime(ed, original.start + delta, clipIndex, e), clip.start),
        caption.end - 0.05);
    } else {
      caption.end = Math.max(Math.min(snapTime(ed, original.end + delta, clipIndex, e), clip.end),
        caption.start + 0.05);
    }
    drawTimeline(ed);
  }, () => {
    if (!moved) {
      // A plain click: mark it selected without rebuilding, so a double-click lands.
      for (const node of ed.root.querySelectorAll('.ed-clip.selected, .ed-cap.selected')) {
        node.classList.remove('selected');
      }
      event.target.closest('.ed-cap').classList.add('selected');
      return;
    }
    const after = JSON.stringify(ed.draft);
    ed.draft = JSON.parse(before);
    edit(ed, () => {
      ed.draft = JSON.parse(after);
      ed.selected = selection;
    }, before);
  });
}

function scrubFrom(ed, event) {
  pause(ed);
  const go = (e) => seek(ed, Math.min(Math.max(0, laneX(ed, e) / ed.pps), programLength(ed)));
  go(event);
  dragging(event, go, () => {});
}

// --- zoom ------------------------------------------------------------------------------------

function zoom(ed, factor) {
  ed.pps = Math.min(600, Math.max(8, ed.pps * factor));
  drawTimeline(ed);
  updatePlayhead(ed);
}

function fitZoom(ed, redraw) {
  const width = ed.scroller.clientWidth || 900;
  ed.pps = Math.max(8, (width - 20) / Math.max(1, programLength(ed) + 1));
  if (redraw) { drawTimeline(ed); updatePlayhead(ed); }
}

// --- waveforms and words ---------------------------------------------------------------------

// The loaded window of loudness that covers a whole clip, if there is one.
function peaksFor(ed, who, clip) {
  return ed.peaks[who].find((p) => p.start <= clip.start + 0.05
    && p.start + p.db.length / p.rate >= clip.end - 0.05) || null;
}

async function loadWaveforms(ed) {
  const pad = 15;
  const list = clips(ed);
  const jobs = [];
  for (const clip of list) {
    for (const who of ['us', 'film']) {
      if (peaksFor(ed, who, clip)) continue;
      jobs.push(call('short_peaks', ed.slug, who, Math.max(0, clip.start - pad), clip.end + pad)
        .then((peaks) => { ed.peaks[who].push(peaks); }));
    }
  }
  const low = Math.min(...list.map((c) => c.start)) - 60;
  const high = Math.max(...list.map((c) => c.end)) + 60;
  if (!ed.wordsRange || ed.wordsRange[0] > low + 50 || ed.wordsRange[1] < high - 50) {
    jobs.push(call('short_words', ed.slug, low, high).then((words) => {
      ed.words = words;
      ed.wordsRange = [low, high];
    }));
  }
  try { await Promise.all(jobs); } catch (error) { /* shown as a toast */ }
}

// --- playback ---------------------------------------------------------------------------------

function seek(ed, t) {
  ed.playhead = Math.min(Math.max(0, t), programLength(ed));
  const { index, source } = locate(ed, Math.min(ed.playhead, programLength(ed) - frame(ed) / 2));
  ed.current = index;
  cue(ed, index, source);
  updatePlayhead(ed);
}

// Point both videos at a recording time, the film muted unless the clip is heard with it.
function cue(ed, index, source) {
  const clip = clips(ed)[index];
  if (ed.hosts.readyState >= 1) ed.hosts.currentTime = source;
  const filmTime = source - ed.view.film_offset;
  if (ed.film.readyState >= 1) ed.film.currentTime = Math.max(0, filmTime);
  applyBleeps(ed, clip, source);
}

// Mute whichever side a bleep covers at this moment and sound the tone over it,
// as the render will.
// The players' sound runs a little behind their clocks, so the preview mutes
// and sounds a touch early to land where the render does.
const BLEEP_LEAD = 0.08;        // seconds

function applyBleeps(ed, clip, source) {
  const filmHeard = clip.layout === 'panel' && source - ed.view.film_offset >= 0;
  const ahead = ed.playing ? source + BLEEP_LEAD : source;
  const on = (who) => (clip.bleeps || []).some((b) => b.who === who && b.start <= ahead && source < b.end);
  const us = on('us');
  const film = filmHeard && on('film');
  ed.hosts.muted = us;
  ed.film.muted = !filmHeard || film;
  setTone(ed, ed.playing && (us || film));
}

// Made on Play, a click, so the window lets it sound. With a bleep sound in
// config/shorts.json it's that sound, trimmed and levelled as the render does
// it; until it has loaded (or if it can't), the tone.
function makeTone(ed) {
  if (ed.tone) {
    if (ed.tone.context.state === 'suspended') ed.tone.context.resume();
    return;
  }
  const context = new AudioContext();
  const gain = context.createGain();
  gain.gain.value = 0;
  gain.connect(context.destination);
  const oscillator = context.createOscillator();
  oscillator.frequency.value = ed.view.bleep.tone_hz;
  oscillator.connect(gain);
  oscillator.start();
  ed.tone = { context, gain, oscillator, sound: null, playing: null, on: false };
  if (ed.view.bleep.sound_url) {
    fetch(ed.view.bleep.sound_url)
      .then((response) => response.arrayBuffer())
      .then((data) => context.decodeAudioData(data))
      .then((buffer) => {
        ed.tone.sound = trimmedSound(context, buffer);
        oscillator.disconnect();
        oscillator.stop();
      })
      .catch(() => toast('Could not load the bleep sound; previewing with the tone.'));
  }
}

// The sound with its near-silent ends cut off and its peak at 1, so a repeat
// comes straight back in and the level matches the render.
function trimmedSound(context, buffer) {
  const channels = [...Array(buffer.numberOfChannels).keys()].map((c) => buffer.getChannelData(c));
  const loud = (i) => Math.max(...channels.map((data) => Math.abs(data[i])));
  let peak = 0;
  for (let i = 0; i < buffer.length; i++) peak = Math.max(peak, loud(i));
  if (!peak) return null;
  const floor = peak * 10 ** (-50 / 20);
  let first = 0, last = buffer.length - 1;
  while (first < last && loud(first) <= floor) first++;
  while (last > first && loud(last) <= floor) last--;
  const out = context.createBuffer(channels.length, last - first + 1, buffer.sampleRate);
  channels.forEach((data, c) => out.getChannelData(c).set(data.subarray(first, last + 1).map((v) => v / peak)));
  return out;
}

function setTone(ed, on) {
  const tone = ed.tone;
  if (!tone || tone.on === on) return;
  tone.on = on;
  const now = tone.context.currentTime;
  if (tone.sound) {
    if (tone.playing) { tone.playing.stop(now + 0.01); tone.playing = null; }
    if (on) {
      // From its start each time, over again for a long bleep.
      tone.playing = tone.context.createBufferSource();
      tone.playing.buffer = tone.sound;
      tone.playing.loop = true;
      tone.playing.connect(tone.gain);
      tone.playing.start(now);
    }
  }
  tone.gain.gain.setTargetAtTime(on ? ed.view.bleep.level : 0, now, 0.003);
}

function togglePlay(ed) {
  if (ed.playing) pause(ed); else play(ed);
}

function play(ed) {
  if (!ed.view.proxies) return toast('Make the proxies first.');
  if (ed.playhead >= programLength(ed) - frame(ed)) seek(ed, 0);
  makeTone(ed);
  ed.playing = true;
  ed.playButton.textContent = 'Pause';
  const { index, source } = locate(ed, ed.playhead);
  ed.current = index;
  cue(ed, index, source);
  Promise.all([ed.hosts.play(), ed.film.play()]).catch(() => {});
  requestAnimationFrame(() => tick(ed));
}

function pause(ed) {
  ed.playing = false;
  if (ed.playButton) ed.playButton.textContent = 'Play';
  if (ed.hosts) { ed.hosts.pause(); ed.film.pause(); }
  if (ed.tone) setTone(ed, false);
}

function tick(ed) {
  if (!ed.playing || state.editor !== ed || !ed.root.isConnected) { pause(ed); return; }
  const list = clips(ed);
  const clip = list[ed.current];
  const source = ed.hosts.currentTime;
  if (source >= clip.end - frame(ed) / 2 || source < clip.start - 0.5) {
    // Cut to the next clip, or stop at the end of the short.
    if (ed.current + 1 >= list.length) {
      pause(ed);
      ed.playhead = programLength(ed);
      updatePlayhead(ed);
      return;
    }
    ed.current += 1;
    cue(ed, ed.current, list[ed.current].start);
    ed.playhead = clipStarts(ed)[ed.current];
  } else {
    ed.playhead = clipStarts(ed)[ed.current] + (source - clip.start);
    // Keep the film on the recording's clock.
    const filmTime = source - ed.view.film_offset;
    if (filmTime >= 0 && Math.abs(ed.film.currentTime - filmTime) > 0.12) ed.film.currentTime = filmTime;
    applyBleeps(ed, clip, source);
  }
  updatePlayhead(ed);
  requestAnimationFrame(() => tick(ed));
}

function step(ed, delta) {
  pause(ed);
  seek(ed, ed.playhead + delta);
}

function updatePlayhead(ed) {
  ed.playheadLine.style.left = `${ed.playhead * ed.pps}px`;
  const { index, source } = locate(ed, ed.playhead);
  ed.timeReadout.textContent = `${ed.playhead.toFixed(2)}s / ${programLength(ed).toFixed(2)}s` +
    `  ·  clip ${index + 1} @ ${clock(source)}`;
  // Keep the playhead in view while playing.
  if (ed.playing) {
    const x = ed.playhead * ed.pps;
    const view = ed.scroller;
    if (x < view.scrollLeft || x > view.scrollLeft + view.clientWidth - 40) view.scrollLeft = x - 40;
  }
  showCaption(ed);
}

function showCaption(ed) {
  const groups = (ed.checks && ed.checks.groups) || [];
  const t = ed.playhead;
  const group = groups.find((g) => g.start - 1e-6 <= t && t < g.end);
  if (!group) { ed.caption.replaceChildren(); return; }
  let active = 0;
  group.words.forEach(([at], i) => { if (at <= t + 1e-6) active = i; });
  const style = ed.view.caption_style;
  ed.caption.replaceChildren(...group.words.map(([, text], i) => h('span', {
    style: `color:${i === active ? style.highlight[group.who === 'film' ? 'film' : 'us'] : style.color}`,
  }, text + (i < group.words.length - 1 ? ' ' : ''))));
}

// --- keys -------------------------------------------------------------------------------------

document.addEventListener('keydown', (event) => {
  const ed = state.editor;
  if (!ed || !ed.root || !ed.root.isConnected) return;
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
  const key = event.key;
  if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 's') {
    event.preventDefault();
    saveEditor(ed, false);
    return;
  }
  if (typing) return;
  if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 'z') {
    event.preventDefault();
    if (event.shiftKey) redo(ed); else undo(ed);
  } else if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 'y') {
    event.preventDefault();
    redo(ed);
  } else if (key === ' ') {
    event.preventDefault();
    togglePlay(ed);
  } else if (key === 'ArrowLeft' || key === 'ArrowRight') {
    event.preventDefault();
    step(ed, (key === 'ArrowLeft' ? -1 : 1) * (event.shiftKey ? 1 : frame(ed)));
  } else if (key === 'Home') {
    seek(ed, 0);
  } else if (key === 's' || key === 'S') {
    split(ed);
  } else if (key === 'Delete' || key === 'Backspace') {
    event.preventDefault();
    removeSelected(ed);
  } else if (key === 'l' || key === 'L') {
    toggleLayout(ed);
  } else if (key === 'b' || key === 'B') {
    bleepWord(ed);
  }
});
