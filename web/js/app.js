import { Viewer } from './viewer.js';
import { DrawingView } from './drawing.js';
import { LayersPanel, newLayer, maskRings, hitMask, nice } from './layers.js';
import { DimensionTool, addDimension, deleteDimension, promoteDimension, planDimension, evalNumber } from './dimtool.js';
import { PrintPanel } from './printers.js';
import { BendsPanel } from './bends.js';

const $ = (id) => document.getElementById(id);
const UNIT_TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254 };
const STEP = { mm: 1, cm: 0.1, m: 0.001, in: 0.05 };
const RESOLVABLE = new Set(['missing_dimension', 'invalid_dimension', 'missing_thickness', 'assumed_alignment']);

const state = {
  model: null, preview: null, solution: null, values: {}, userSet: new Set(), lastError: null,
  flatView: false, // show the part unbent (bends ignored) to edit masks / dimensions
};
const viewer = new Viewer($('viewport'));
const drawing = new DrawingView($('drawingWrap'));

// ------------------------------------------------------------------ helpers
const fmt = (v) => (v === undefined || v === null || Number.isNaN(v) ? '—' : (+(+v).toFixed(4)).toString());
const param = (id) => state.model.params.find((p) => p.id === id);

function statusOf(id) {
  const p = param(id);
  if (!p) return 'drawing';
  if (p.role === 'conflict') return 'conflict';
  if (p.role === 'reference') return 'reference';
  if (p.source === 'added') return 'added';
  if (state.userSet.has(id)) return 'user';
  return p.source;
}

const STATUS_LABEL = {
  drawing: 'from drawing', estimated: 'estimated', default: 'default', user: 'set by you', added: 'added by you',
  reference: 'reference', aligned: 'assumed', conflict: 'conflict',
};

function toast(msg, kind = 'info', ms = 4500) {
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.textContent = msg;
  $('toasts').appendChild(t);
  setTimeout(() => t.remove(), ms);
}

async function api(path, body, method) {
  const opts = method ? { method } : body instanceof FormData ? { method: 'POST', body }
    : body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { msg = (await res.json()).error || msg; } catch { /* binary */ }
    throw new Error(msg);
  }
  return res;
}

function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

const layers = new LayersPanel($('layerList'), {
  onChange: () => scheduleRebuild(),
  onSelect: (L) => viewer.setSelection(L ? maskRings(L) : null, L?.face),
  unit: 'mm',
});

const printPanel = new PrintPanel($('rtab-print'), {
  api, viewer, toast, download,
  getBody: () => (state.model && state.solution ? { model: state.model, values: state.values, layers: layers.layers, bends: activeBends(), solution: state.solution } : null),
});
printPanel.load().catch((e) => toast(e.message, 'error'));

const bends = new BendsPanel($('bendList'), {
  viewer, toast,
  getSolution: () => state.solution,
  onChange: (added) => {
    updateFlatToggle();
    if (added && state.flatView) setFlatView(false);
    else scheduleRebuild();
  },
  ensureFlat: async () => {
    if (!state.flatView && bends.bends.some((b) => b.visible)) {
      await setFlatView(true);
      toast('Switched to Flat view to place the fold line.', 'info', 3000);
    }
  },
});

/** Bends sent to the server (none while editing in Flat view). */
function activeBends() { return state.flatView ? [] : bends.bends; }

function updateFlatToggle() {
  const any = bends.bends.some((b) => b.visible);
  $('flatToggle').hidden = !any;
  $('flatToggle').classList.toggle('on', state.flatView && any);
  if (!any) state.flatView = false;
}

async function setFlatView(on) {
  state.flatView = on;
  updateFlatToggle();
  await applyValues({ ...state.values }, { quiet: true });
}
$('flatToggle').addEventListener('click', () => setFlatView(!state.flatView));
$('addFold').addEventListener('click', () => bends.startPlacing());
$('addRoll').addEventListener('click', () => { if (state.solution) bends.addRoll(); });

// ------------------------------------------------------------------ loading
async function loadParsed(data) {
  if (data.error) throw new Error(data.error);
  state.model = data.model;
  state.preview = data.preview;
  state.userSet = new Set(data.userSet || []);
  state.values = data.values || Object.fromEntries(data.model.params.map((p) => [p.id, p.value]));
  // what the drawing defined (values + structure), for "restore defaults"; projects carry it along
  state.original = data.original || {
    params: structuredClone(data.model.params),
    values: Object.fromEntries(data.model.params.map((p) => [p.id, p.value])),
  };
  state.solution = null;
  layers.unit = data.model.unit;
  layers.selected = null;
  layers.set(data.layers || []);
  bends.unit = data.model.unit;
  state.flatView = false;
  bends.set(data.bends || []);
  updateFlatToggle();
  viewer.setSelection(null);
  dimTool.stop();
  $('fileName').textContent = data.model.source || 'drawing.pdf';
  viewer.hasFitted = false;
  if (!data.model.loops.length) {
    renderAll();
    toast('No part outline could be recognised in this PDF — see Checks.', 'error', 8000);
    switchTab('issues');
    return;
  }
  await applyValues(state.values, { initial: true });
  if (!state.solution) { renderAll(); return; }
  const h = state.solution.bbox[3] - state.solution.bbox[1];
  $('snapStep').value = data.snap ?? nice(h / 20);
  renderAll();
  const errs = data.model.issues.filter((i) => i.severity === 'error').length;
  const warns = data.model.issues.filter((i) => i.severity === 'warning').length;
  if (data.app) toast('Project loaded.', 'ok');
  else if (errs || warns) {
    toast(`Drawing read with ${errs ? `${errs} error(s)` : ''}${errs && warns ? ' and ' : ''}${warns ? `${warns} warning(s)` : ''} — review the highlighted dimensions.`, errs ? 'error' : 'warning', 7000);
  } else toast('All dimensions read successfully.', 'ok');
}

async function openPdf(file) {
  const fd = new FormData();
  fd.append('file', file);
  try {
    await loadParsed(await (await api('/api/parse', fd)).json());
  } catch (e) { toast(e.message, 'error', 8000); }
}

$('pdfInput').addEventListener('change', (e) => { if (e.target.files[0]) openPdf(e.target.files[0]); e.target.value = ''; });
$('sampleBtn').addEventListener('click', async () => {
  try { await loadParsed(await (await api('/api/sample')).json()); } catch (e) { toast(e.message, 'error'); }
});

const vp = $('viewport');
vp.addEventListener('dragover', (e) => { e.preventDefault(); vp.classList.add('drag-over'); });
vp.addEventListener('dragleave', () => vp.classList.remove('drag-over'));
vp.addEventListener('drop', (e) => {
  e.preventDefault();
  vp.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  if (/\.json$/i.test(f.name)) openProject(f);
  else if (/\.pdf$/i.test(f.name) || f.type === 'application/pdf') openPdf(f);
  else if (f.type.startsWith('image/')) addImageLayer(f);
  else toast('Please drop a PDF drawing (or an image to add as a design layer).', 'warning');
});

// ------------------------------------------------------------------ solving
let inflight = null, queued = null;

/** Rebuild with new parameter values; invalid results are rejected and the last valid model is kept. */
function applyValues(values, opts = {}) {
  queued = { values, ...opts };
  if (!inflight) inflight = pump();
  return inflight;
}

async function pump() {
  $('busy').hidden = false;
  while (queued) {
    const job = queued;
    queued = null;
    try {
      const sol = await (await api('/api/solve', { model: state.model, values: job.values, layers: layers.layers, bends: activeBends() })).json();
      if (sol.ok) {
        state.values = job.values;
        state.solution = sol;
        state.lastError = null;
        renderSolution();
        const dErr = (sol.design_issues || []).filter((i) => i.severity === 'error');
        if (dErr.length && !job.quiet) toast(dErr.map((i) => i.message).join(' '), 'error', 6000);
      } else {
        const msgs = sol.issues.filter((i) => i.severity === 'error').map((i) => i.message);
        state.lastError = msgs;
        if (!job.quiet) toast(`Change not applied: ${msgs.join(' ')}`, 'error', 6000);
        job.onReject?.(sol);
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  }
  $('busy').hidden = true;
  inflight = null;
}

let rebuildTimer = null;
function scheduleRebuild() {
  clearTimeout(rebuildTimer);
  rebuildTimer = setTimeout(() => { if (state.model) applyValues(state.values, { quiet: true }).then(() => { renderIssues(); notifyDesignIssues(); }); }, 180);
}

let lastDesignMsg = '';
function notifyDesignIssues() {
  const msg = (state.solution?.design_issues || []).filter((i) => i.severity !== 'info').map((i) => i.message).join(' ');
  if (msg && msg !== lastDesignMsg) toast(msg, (state.solution.design_issues || []).some((i) => i.severity === 'error') ? 'error' : 'warning', 6000);
  lastDesignMsg = msg;
}

function setParam(id, v, opts = {}) {
  if (!Number.isFinite(v)) {
    toast('Please enter a number.', 'warning');
    renderParams();
    return Promise.resolve();
  }
  state.userSet.add(id);
  return applyValues({ ...state.values, [id]: v }, {
    ...opts,
    onReject: () => {
      if (!opts.wasUser) state.userSet.delete(id);
      renderParams();
      flashParam(id);
    },
  });
}

/** Structural model change (dimension added/removed/promoted): rebuild, roll back if invalid. */
async function structuralChange(mutate, okMsg) {
  const backup = { params: structuredClone(state.model.params), values: { ...state.values }, userSet: new Set(state.userSet) };
  mutate();
  let rejected = false;
  await applyValues({ ...state.values }, { onReject: () => { rejected = true; } });
  if (rejected) {
    state.model.params = backup.params;
    state.values = backup.values;
    state.userSet = backup.userSet;
    await applyValues({ ...state.values }, { quiet: true });
  } else if (okMsg) toast(okMsg, 'ok');
  renderParams();
  renderIssues();
  drawing.show(state.preview, state.model, statusOf);
}

// ------------------------------------------------------------------ rendering
function renderAll() {
  const has = !!state.model;
  $('saveBtn').disabled = !has;
  $('exportBtn').disabled = !state.solution;
  $('paramsEmpty').hidden = has;
  $('paramHint').hidden = !has;
  renderParams();
  renderIssues();
  if (has) drawing.show(state.preview, state.model, statusOf);
  if (state.solution) renderSolution();
}

function renderSolution() {
  const sol = state.solution;
  viewer.setSolution(sol);
  const [x0, y0, x1] = sol.bbox;
  const gap = Math.max(x1 - x0, sol.bbox[3] - y0) * 0.035;
  const thk = sol.thickness_3d
    ? { param: 'thickness', axis: 'z', p1_3d: sol.thickness_3d[0], p2_3d: sol.thickness_3d[1] }
    : { param: 'thickness', axis: 'z', p1: [x1 + gap, y0], p2: [x1 + gap, y0], z: 0, z2: sol.thickness };
  const anns = [...sol.annotations, thk];
  bends.setInfo(sol.bends_info);
  viewer.setAnnotations(anns, makeLabel, statusOf);
  const sel = layers.layers.find((l) => l.id === layers.selected);
  viewer.setSelection(sel ? maskRings(sel) : null, sel?.face);
  renderParamValues();
  renderIssues();
  renderStatus();
  printPanel.refresh();
}

function renderStatus() {
  const sol = state.solution, u = state.model.unit;
  const [x0, y0, x1, y1] = sol.bbox3 ? sol.bbox3.slice(0, 4) : sol.bbox;
  const [z0, z1] = sol.z_range || [0, sol.thickness];
  const size = (v) => fmt(+v.toFixed(2));
  $('statusBar').innerHTML = `<span>${size(x1 - x0)} × ${size(y1 - y0)} × ${size(z1 - z0)} ${u}${sol.bent ? ' (bent)' : ''}</span>
    <span>${sol.loops.length - 1} cutout(s)</span><span>${layers.layers.filter((l) => l.visible).length} design layer(s)</span>
    <span>volume ${fmt(+(sol.volume ?? 0).toFixed(3))} ${u}³</span><span>${sol.mesh?.count ?? 0} triangles</span>`;
}

function groupOf(p) {
  const st = statusOf(p.id);
  if (st === 'conflict' || st === 'estimated' || st === 'default') return 'attention';
  if (st === 'reference') return 'reference';
  if (st === 'aligned') return 'assumed';
  if (st === 'added') return 'added';
  return 'main';
}

// ------------------------------------------------------------------ restore defaults
const defaultOf = (id) => state.original?.values[id];
const isChanged = (id) => {
  const d = defaultOf(id);
  return d !== undefined && param(id)?.role === 'driving' && Math.abs((state.values[id] ?? d) - d) > 1e-9;
};

/** Number of differences from the drawing: edited values plus structural edits (added / promoted). */
function changeCount() {
  if (!state.original) return 0;
  const orig = new Map(state.original.params.map((p) => [p.id, p]));
  let n = state.model.params.filter((p) => isChanged(p.id)).length;
  n += state.model.params.filter((p) => !orig.has(p.id) || orig.get(p.id).role !== p.role).length;
  n += state.original.params.filter((p) => !state.model.params.some((q) => q.id === p.id)).length;
  return n;
}

function resetParam(id) {
  const d = defaultOf(id);
  const wasUser = state.userSet.has(id);
  state.userSet.delete(id);
  applyValues({ ...state.values, [id]: d }, {
    onReject: () => { if (wasUser) state.userSet.add(id); flashParam(id); },
  }).then(() => { renderParams(); renderIssues(); });
}

$('resetAll').addEventListener('click', () => {
  const n = changeCount();
  if (!n || !confirm(`Restore all dimensions to the drawing? This undoes ${n} change(s), including dimensions you added.`)) return;
  structuralChange(() => {
    state.model.params = structuredClone(state.original.params);
    state.values = { ...state.original.values };
    state.userSet = new Set();
  }, 'Dimensions restored to the drawing defaults.');
});

function renderParams() {
  const list = $('paramList');
  list.innerHTML = '';
  $('paramsToolbar').hidden = !state.model;
  if (!state.model) return;
  const n = changeCount();
  $('changeCount').textContent = n ? `${n} change(s) from the drawing` : 'Matches the drawing';
  $('resetAll').disabled = !n;
  const groups = {
    attention: 'Needs your attention', main: 'Dimensions', added: 'Added by you', assumed: 'Assumptions',
    reference: 'Reference (driven by others)',
  };
  const ordered = [...state.model.params].sort((a, b) => (a.kind === 'thickness' ? -1 : b.kind === 'thickness' ? 1 : 0));
  for (const [g, title] of Object.entries(groups)) {
    const items = ordered.filter((p) => groupOf(p) === g);
    if (!items.length) continue;
    const h = document.createElement('div');
    h.className = 'param-group';
    h.textContent = title;
    list.appendChild(h);
    for (const p of items) list.appendChild(paramRow(p));
  }
  renderParamValues();
}

function paramRow(p) {
  const st = statusOf(p.id);
  const row = document.createElement('div');
  row.className = 'param';
  row.dataset.param = p.id;
  const editable = p.role === 'driving';
  const src = p.text ? `drawing: “${p.text}”` : p.invalid_text ? `invalid label “${p.invalid_text}”` : p.source === 'estimated' ? 'not in drawing' : '';
  const canPromote = (p.role === 'reference' || p.role === 'conflict') && p.kind === 'linear';
  row.innerHTML = `
    <div class="name" contenteditable="true" spellcheck="false" title="Click to rename"></div>
    <div class="val">
      ${editable ? '<button class="step" data-d="-1" title="Decrease">−</button>' : ''}
      <input type="text" inputmode="decimal" ${editable ? '' : 'disabled'}>
      ${editable ? '<button class="step" data-d="1" title="Increase">+</button>' : ''}
      <span class="unit">${p.unit}</span>
    </div>
    <div class="meta"><span class="badge ${st}">${STATUS_LABEL[st]}</span><span class="src"></span>
      <span class="acts">
        ${isChanged(p.id) ? `<button class="mini reset" title="Restore ${fmt(defaultOf(p.id))} ${p.unit} (${p.source === 'drawing' ? 'from the drawing' : 'original value'})">↺ ${fmt(defaultOf(p.id))}</button>` : ''}
        ${canPromote ? `<button class="mini promote" title="Make this dimension drive the geometry">${p.role === 'conflict' ? 'Use this value' : 'Make driving'}</button>` : ''}
        ${p.source === 'added' ? '<button class="mini danger remove" title="Remove this dimension">Remove</button>' : ''}
      </span></div>`;
  const name = row.querySelector('.name');
  name.textContent = p.name;
  row.querySelector('.src').textContent = src;
  name.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); name.blur(); } });
  name.addEventListener('blur', () => {
    const n = name.textContent.trim();
    if (n && n !== p.name) { p.name = n; drawing.show(state.preview, state.model, statusOf); }
    else name.textContent = p.name;
  });
  const input = row.querySelector('input');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') input.blur();
    if (e.key === 'Escape') { input.value = fmt(state.values[p.id]); input.blur(); }
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      nudge(p.id, e.key === 'ArrowUp' ? 1 : -1, e);
    }
  });
  input.addEventListener('change', () => {
    const v = evalNumber(input.value);
    if (v === state.values[p.id]) return;
    const wasUser = state.userSet.has(p.id);
    setParam(p.id, v, { wasUser }).then(() => { renderParams(); renderIssues(); });
  });
  row.querySelectorAll('.step').forEach((b) => b.addEventListener('click', (e) => nudge(p.id, +b.dataset.d, e)));
  row.querySelector('.remove')?.addEventListener('click', () => structuralChange(() => deleteDimension(state.model, state, p.id), `${p.name} removed.`));
  row.querySelector('.promote')?.addEventListener('click', () => promote(p, row));
  row.querySelector('.reset')?.addEventListener('click', () => resetParam(p.id));
  row.addEventListener('mouseenter', () => { viewer.highlight(p.id, true); drawing.highlight(p.id, true); });
  row.addEventListener('mouseleave', () => { viewer.highlight(p.id, false); drawing.highlight(p.id, false); });
  return row;
}

/** Make a reference / conflicting dimension driving, choosing what it replaces. */
function promote(p, row) {
  const plan = planDimension(state.model, state.userSet, p.axis, p.lo, p.hi, p.id);
  const value = p.role === 'conflict' ? p.value : state.solution.values[p.id];
  const run = (replace) => structuralChange(() => {
    promoteDimension(state.model, state, p.id, replace);
    state.values[p.id] = value;
    if (p.role === 'driving' && p.source !== 'drawing') state.userSet.add(p.id);
  }, `${p.name} now drives the geometry.`);
  if (plan.auto) return run(plan.auto.id);
  if (!plan.path.length) return run(null);
  const box = document.createElement('div');
  box.className = 'promote-box';
  box.innerHTML = `<p class="hint">Choose which dimension becomes a reference instead:</p>
    <select>${plan.path.map((q) => `<option value="${q.id}">${q.name} = ${fmt(state.solution.values[q.id])}</option>`).join('')}</select>
    <div class="row-actions"><button class="btn small" data-a="c">Cancel</button><button class="btn small primary" data-a="ok">Apply</button></div>`;
  row.appendChild(box);
  box.querySelector('[data-a=c]').addEventListener('click', () => box.remove());
  box.querySelector('[data-a=ok]').addEventListener('click', () => run(box.querySelector('select').value));
}

function renderParamValues() {
  for (const row of document.querySelectorAll('.param')) {
    const id = row.dataset.param;
    const input = row.querySelector('input');
    if (document.activeElement !== input) input.value = fmt(state.solution?.values?.[id] ?? state.values[id]);
  }
}

function stepFor(e) {
  const base = STEP[state.model.unit] ?? 1;
  return base * (e?.shiftKey ? 10 : 1) * (e?.altKey ? 0.1 : 1);
}

function nudge(id, dir, e) {
  const p = param(id);
  if (p.role !== 'driving') return;
  const step = stepFor(e);
  const v = +(Math.round(((state.values[id] ?? 0) + dir * step) / step) * step).toFixed(6);
  const wasUser = state.userSet.has(id);
  setParam(id, v, { wasUser }).then(() => { renderParams(); renderIssues(); });
}

function flashParam(id) {
  const row = document.querySelector(`.param[data-param="${id}"]`);
  if (row) { row.classList.remove('flash'); void row.offsetWidth; row.classList.add('flash'); }
}

// 3D labels: click to type, drag to scrub, wheel to nudge
function makeLabel(a) {
  const p = param(a.param);
  const el = document.createElement('div');
  const st = statusOf(a.param);
  el.className = `dim-label ${st}`;
  const v = state.solution.values[a.param] ?? state.values[a.param];
  el.textContent = st === 'reference' ? `(${fmt(v)})` : `${fmt(v)}${a.param === 'thickness' ? ` ${p.unit} thk` : ''}`;
  el.title = `${p.name} — ${STATUS_LABEL[st]}${p.role === 'driving' ? '\nClick to edit · drag ↔ or scroll to change' : ''}`;
  el.addEventListener('mouseenter', () => highlightRow(a.param, true));
  el.addEventListener('mouseleave', () => highlightRow(a.param, false));
  if (p.role !== 'driving') return el;

  el.addEventListener('wheel', (e) => {
    e.preventDefault();
    e.stopPropagation();
    nudgeLive(a.param, e.deltaY < 0 ? 1 : -1, e);
  }, { passive: false });

  el.addEventListener('pointerdown', (e) => {
    if (el.querySelector('input')) return;
    e.preventDefault();
    e.stopPropagation();
    el.setPointerCapture(e.pointerId);
    const startX = e.clientX, start = state.values[a.param];
    let scrubbing = false;
    const move = (ev) => {
      const dx = ev.clientX - startX;
      if (!scrubbing && Math.abs(dx) < 4) return;
      scrubbing = true;
      const step = stepFor(ev);
      const nv = +(Math.round((start + Math.round(dx / 6) * step) / step) * step).toFixed(6);
      if (nv !== state.values[a.param]) {
        if (p.source !== 'added') state.userSet.add(a.param);
        applyValues({ ...state.values, [a.param]: nv }, { quiet: true });
      }
    };
    const up = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      if (!scrubbing) editLabel(el, a.param);
      else {
        (inflight || Promise.resolve()).then(() => {
          if (state.lastError) toast(`Limit reached: ${state.lastError.join(' ')}`, 'warning');
          renderParams(); renderIssues();
        });
      }
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
  });
  return el;
}

let wheelTimer = null;
function nudgeLive(id, dir, e) {
  const step = stepFor(e);
  const v = +(Math.round(((state.values[id] ?? 0) + dir * step) / step) * step).toFixed(6);
  state.userSet.add(id);
  applyValues({ ...state.values, [id]: v }, { quiet: true });
  clearTimeout(wheelTimer);
  wheelTimer = setTimeout(() => {
    (inflight || Promise.resolve()).then(() => {
      if (state.lastError) toast(`Limit reached: ${state.lastError.join(' ')}`, 'warning');
      renderParams(); renderIssues();
    });
  }, 300);
}

function editLabel(el, id) {
  const input = document.createElement('input');
  input.value = fmt(state.values[id]);
  el.textContent = '';
  el.appendChild(input);
  input.focus();
  input.select();
  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    if (commit) {
      const v = evalNumber(input.value);
      if (v !== state.values[id]) {
        const wasUser = state.userSet.has(id);
        setParam(id, v, { wasUser }).then(() => { renderParams(); renderIssues(); renderSolution(); });
        return;
      }
    }
    renderSolution();
  };
  input.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') finish(true);
    if (e.key === 'Escape') finish(false);
  });
  input.addEventListener('blur', () => finish(true));
}

function highlightRow(id, on) {
  document.querySelector(`.param[data-param="${id}"]`)?.classList.toggle('hl', on);
  viewer.highlight(id, on);
}

// ------------------------------------------------------------------ issues
function renderIssues() {
  const list = $('issueList');
  list.innerHTML = '';
  if (!state.model) { $('issueCount').textContent = ''; return; }
  const issues = state.model.issues.map((i, idx) => ({ ...i, idx, resolved: RESOLVABLE.has(i.code) && i.params.length && i.params.every((p) => state.userSet.has(p) || !param(p)) }));
  const design = (state.solution?.design_issues || []).map((i) => ({ ...i, design: true }));
  const open = [...issues.filter((i) => !i.resolved), ...design];
  const errs = open.filter((i) => i.severity === 'error').length;
  const warns = open.filter((i) => i.severity === 'warning').length;
  const c = $('issueCount');
  c.textContent = errs + warns || '';
  c.className = `count ${errs ? 'err' : warns ? 'warn' : ''}`;

  const dimCount = state.model.params.filter((p) => p.source === 'drawing').length;
  const sum = document.createElement('div');
  sum.className = 'summary';
  sum.innerHTML = `Read <b>${dimCount}</b> dimension(s) from the drawing; outline with <b>${Math.max(0, state.model.loops.length - 1)}</b> cutout(s).<br>
    ${errs ? `<b class="err">${errs} error(s)</b> ` : ''}${warns ? `<b class="warn">${warns} warning(s)</b> ` : ''}${!errs && !warns ? '<b class="ok">No open problems.</b>' : 'Set the flagged values to resolve them.'}`;
  list.appendChild(sum);

  const icon = { error: '✕', warning: '!', info: 'i' };
  for (const i of [...design, ...issues]) {
    const d = document.createElement('div');
    d.className = `issue ${i.severity}${i.resolved ? ' resolved' : ''}`;
    d.innerHTML = `<span class="ic">${icon[i.severity]}</span><span></span>`;
    d.lastChild.textContent = i.design ? `3D design — ${i.message}` : i.message;
    d.addEventListener('click', () => {
      if (i.design && i.layer) {
        switchRTab('design');
        layers.selected = null;
        layers.select(i.layer);
      } else if (i.params.length) {
        switchTab('params');
        for (const pid of i.params) {
          flashParam(pid);
          viewer.highlight(pid, true);
          setTimeout(() => viewer.highlight(pid, false), 1400);
        }
        document.querySelector(`.param[data-param="${i.params[0]}"] input:not(:disabled)`)?.focus();
      } else if (i.draw) {
        switchTab('drawing');
        drawing.flashIssue(i.idx);
      }
    });
    list.appendChild(d);
  }
}

// ------------------------------------------------------------------ tabs & view tools
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-body').forEach((b) => b.classList.toggle('active', b.id === `tab-${name}`));
}
function switchRTab(name) {
  document.querySelectorAll('.rtab').forEach((t) => t.classList.toggle('active', t.dataset.rtab === name));
  document.querySelectorAll('.rtab-body').forEach((b) => b.classList.toggle('active', b.id === `rtab-${name}`));
}
document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => switchTab(t.dataset.tab)));
document.querySelectorAll('.rtab').forEach((t) => t.addEventListener('click', () => switchRTab(t.dataset.rtab)));
document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => viewer.setView(b.dataset.view)));
$('dimsToggle').addEventListener('click', (e) => { e.target.classList.toggle('on'); viewer.setDimsVisible(e.target.classList.contains('on')); });
$('wireToggle').addEventListener('click', (e) => { e.target.classList.toggle('on'); viewer.setWire(e.target.classList.contains('on')); });

// ------------------------------------------------------------------ dimension tool
const dimTool = new DimensionTool({
  viewer, toast,
  getState: () => state,
  onAdd: (spec) => structuralChange(() => addDimension(state.model, state, spec), 'Dimension added — edit it like any other.'),
});
$('dimToolBtn').addEventListener('click', async () => {
  if (!state.solution) return;
  if (state.solution.bent) { await setFlatView(true); toast('Switched to Flat view to pick edges.', 'info', 3000); }
  if (printPanel.pieces) printPanel.exitSplit();
  if (dimTool.active) dimTool.stop(); else dimTool.start();
});
window.addEventListener('keydown', (e) => {
  if (e.target.closest?.('input,select,textarea,[contenteditable]')) return;
  if ((e.key === 'd' || e.key === 'D') && state.solution && !dimTool.active) $('dimToolBtn').click();
  if ((e.key === 'Delete') && layers.selected) {
    layers.layers = layers.layers.filter((l) => l.id !== layers.selected);
    layers.selected = null;
    layers.render();
    viewer.setSelection(null);
    scheduleRebuild();
  }
});

// ------------------------------------------------------------------ design layers
$('addGrid').addEventListener('click', () => { if (state.solution) layers.add(newLayer('grid', state.solution)); });
$('addShape').addEventListener('click', () => { if (state.solution) layers.add(newLayer('shape', state.solution)); });
$('imageInput').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) addImageLayer(f); });
$('baseColor').addEventListener('input', () => viewer.setColors($('baseColor').value, $('featureColor').value));
$('featureColor').addEventListener('input', () => viewer.setColors($('baseColor').value, $('featureColor').value));

/** Rasterise any image (incl. SVG) in the browser, then trace its silhouette on the server. */
async function addImageLayer(file) {
  if (!state.solution) { toast('Load a drawing first.', 'warning'); return; }
  try {
    const url = URL.createObjectURL(file);
    const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = url; });
    const scale = 512 / Math.max(img.naturalWidth || 512, img.naturalHeight || 512);
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round((img.naturalWidth || 512) * scale));
    c.height = Math.max(1, Math.round((img.naturalHeight || 512) * scale));
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    URL.revokeObjectURL(url);
    const traced = await (await api('/api/trace', { image: c.toDataURL('image/png') })).json();
    if (!traced.polygons.length) { toast('No shape found in the image (use a dark logo on a light or transparent background).', 'warning', 6000); return; }
    layers.add(newLayer('image', state.solution, { ...traced, name: file.name.replace(/\.[^.]+$/, '') }));
    switchRTab('design');
    toast('Image traced — drag it on the part, then choose emboss / engrave / cut.', 'ok');
  } catch (e) { toast(`Could not use that image: ${e.message || e}`, 'error'); }
}

// drag masks on the part
const canvas = viewer.renderer.domElement;
let drag = null;
canvas.addEventListener('pointerdown', (e) => {
  if (!state.solution || e.button !== 0 || dimTool.active || printPanel.pieces || bends.placing || state.solution.bent) return;
  const ordered = [...layers.layers].reverse().sort((a, b) => (b.id === layers.selected) - (a.id === layers.selected));
  for (const L of ordered) {
    if (!L.visible) continue;
    const pt = viewer.pickFace(e.clientX, e.clientY, L.face);
    if (pt && hitMask(L, pt.x, pt.y)) {
      if (layers.selected !== L.id) { layers.selected = null; layers.select(L.id); }
      drag = { L, dx: L.mask.x - pt.x, dy: L.mask.y - pt.y };
      viewer.controls.enabled = false;
      canvas.setPointerCapture(e.pointerId);
      e.stopPropagation();
      return;
    }
  }
}, true);
canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const pt = viewer.pickFace(e.clientX, e.clientY, drag.L.face);
  if (!pt) return;
  let x = pt.x + drag.dx, y = pt.y + drag.dy;
  const step = parseFloat($('snapStep').value);
  if ($('snapToggle').checked && step > 0) {
    const [bx, by] = state.solution.bbox;
    x = bx + Math.round((x - bx) / step) * step;
    y = by + Math.round((y - by) / step) * step;
  }
  if (x === drag.L.mask.x && y === drag.L.mask.y) return;
  drag.L.mask.x = +x.toFixed(6);
  drag.L.mask.y = +y.toFixed(6);
  viewer.setSelection(maskRings(drag.L), drag.L.face);
  drag.moved = true;
});
const endDrag = () => {
  if (!drag) return;
  const moved = drag.moved;
  drag = null;
  viewer.controls.enabled = true;
  if (moved) { layers.refreshOpen(); scheduleRebuild(); }
};
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);

// ------------------------------------------------------------------ export / projects
$('exportBtn').addEventListener('click', (e) => { e.stopPropagation(); $('exportBtn').parentElement.classList.toggle('open'); });
document.addEventListener('click', () => $('exportBtn').parentElement.classList.remove('open'));
$('exportMenu').addEventListener('click', async (e) => {
  const fmtName = e.target.dataset.fmt;
  if (!fmtName || !state.solution) return;
  const base = (state.model.source || 'part').replace(/\.pdf$/i, '').replace(/[^\w-]+/g, '_');
  const open = state.model.issues.filter((i) => (i.severity !== 'info') && !(RESOLVABLE.has(i.code) && i.params.every((p) => state.userSet.has(p) || !param(p))));
  try {
    if (fmtName === 'glb') {
      const buf = await viewer.exportGLB(UNIT_TO_M[state.model.unit]);
      download(new Blob([buf], { type: 'model/gltf-binary' }), `${base}.glb`);
    } else {
      const res = await api(`/api/export/${fmtName}`, { model: state.model, values: state.values, layers: layers.layers, bends: bends.bends });
      download(await res.blob(), `${base}.${fmtName}`);
    }
    toast(open.length ? `Exported ${fmtName.toUpperCase()} (in mm). Note: ${open.length} unresolved check(s) — estimated values may be wrong.`
      : `Exported ${fmtName.toUpperCase()} (in mm).`, open.length ? 'warning' : 'ok', 6000);
  } catch (err) { toast(`Export failed: ${err.message}`, 'error'); }
});

$('saveBtn').addEventListener('click', () => {
  const proj = {
    app: 'Auto3DModeler', version: 2, model: state.model, preview: state.preview, values: state.values,
    userSet: [...state.userSet], layers: layers.layers, bends: bends.bends, snap: parseFloat($('snapStep').value), original: state.original,
  };
  const base = (state.model.source || 'part').replace(/\.pdf$/i, '');
  download(new Blob([JSON.stringify(proj)], { type: 'application/json' }), `${base}.a3d.json`);
});

async function openProject(file) {
  try {
    const proj = JSON.parse(await file.text());
    if (proj.app !== 'Auto3DModeler') throw new Error('Not an Auto3DModeler project file.');
    await loadParsed(proj);
  } catch (e) { toast(e.message, 'error'); }
}
$('projectInput').addEventListener('change', (e) => { if (e.target.files[0]) openProject(e.target.files[0]); e.target.value = ''; });

// auto-load the sample when opened with ?sample
if (new URLSearchParams(location.search).has('sample')) $('sampleBtn').click();
window.__app = { state, viewer, layers, printPanel, dimTool, bends };
