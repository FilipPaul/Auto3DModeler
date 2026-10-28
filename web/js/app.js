import { initI18n, t } from './i18n.js';
import { Viewer } from './viewer.js';
import { DrawingView } from './drawing.js';
import { LayersPanel, newLayer, maskRings, hitMask, nice } from './layers.js';
import { DimensionTool, addDimension, deleteDimension, promoteDimension, planDimension, evalNumber } from './dimtool.js';
import { PrintPanel } from './printers.js';
import { BendsPanel } from './bends.js';
import { OutlineWizard } from './outline.js';
import { OutlinePanel, shapeRings, hitShape } from './outlinepanel.js';
import { openLightbox } from './lightbox.js';
import { ChatPanel, startBridge, bridgeStats } from './agent.js';
import { AiHistory } from './aihistory.js';
import { LibraryBrowser, saveToLibrary, libraryItems, matchScore, itemFromModel } from './library/browser.js';
import { repaint } from './modeler/paint.js';
import { moreHandlers, colouredGroups } from './agent_more.js';
import { buildPart, sizesOf, lengthsOf } from './library/build.js';
import { Project } from './parts.js';
import { Modeler } from './modeler/modeler.js';
import { modelHandlers } from './modeler/agent_model.js';
import { Assembly } from './assembly/assembly.js';
import { askHowToOpen, addTree, treeSize } from './assembly/stepfile.js';
import { DrawingEditor, drawingToSketch } from './drawing2d/editor.js';
import { SheetEditor, partHash } from './sheet/sheet.js';
import { isStandard } from './assembly/fasteners.js';
import { initSplitters } from './splitters.js';
import { Autosave } from './autosave.js';
import { Windows } from './windows.js';
import { actionDock } from './actiondock.js';
import * as THREE from 'three';
import { bodyOf, picture, svgPicture } from './thumbs.js';
import { setAskAI } from './suggest.js';
import { changed as projectChanged } from './history.js';
import { trackProgress, newRid } from './progressbox.js'; // (slow requests: the busy box with Cancel)
import { initJobs } from './jobs.js';

initI18n();  // Czech / English: translates the page as it is built
initJobs(() => project.current?.name); // ⚙ N in the top bar: what is working now, with ✕ Stop

const $ = (id) => document.getElementById(id);
const UNIT_TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254 };
const STEP = { mm: 1, cm: 0.1, m: 0.001, in: 0.05 };
const RESOLVABLE = new Set(['missing_dimension', 'invalid_dimension', 'missing_thickness', 'assumed_alignment']);

const state = {
  model: null, preview: null, solution: null, values: {}, userSet: new Set(), lastError: null,
  flatView: false, // show the part unbent (bends ignored) to edit masks / dimensions
  // outline models: the editor state behind the outline (painted mask, detection hints) — saved with
  // the project, kept out of the model so it is not sent with every rebuild
  outlineEditor: null,
  // design layers whose mask was traced with the outline editor: {pictureId: {image, source, polygons, img_w, img_h, editor}}
  layerPictures: {},
  // an imported 3D file (STL / STEP …): {name, data} — saved with the project, the server keeps the triangles
  importFile: null,
};
const viewer = new Viewer($('viewport'));

// ------------------------------------------------------------------ undo / redo (Ctrl+Z / Ctrl+Y)
// One history for every edit (dimensions, objects, shapes, layers, bends, outline edits, the AI): a step is
// recorded when a rebuild has settled (so a drag or a scrub is one step), by comparing the part with the
// last recorded state.
const clone = (x) => (x === undefined || x === null ? x : structuredClone(x));
const history = {
  undo: [], redo: [], base: null, baseKey: '', timer: null, restoring: false,
  capture() {
    return { model: clone(state.model), values: { ...state.values }, layers: clone(layers.layers), bends: clone(bends.bends),
      userSet: [...state.userSet], outlineEditor: state.outlineEditor, layerPictures: clone(state.layerPictures) };
  },
  key(c) { return JSON.stringify([c.model, c.values, c.layers, c.bends]); },
  reset() {
    clearTimeout(this.timer);
    this.undo = []; this.redo = []; this.base = null; this.baseKey = '';
    this.updateUI();
  },
  /** Record the current state as a step if it differs from the last one. */
  commit() {
    if (!state.model || !state.solution || this.restoring) return false;
    const cur = this.capture(), k = this.key(cur);
    if (!this.base) { this.base = cur; this.baseKey = k; return false; }
    if (k === this.baseKey) return false;
    this.undo.push(this.base);
    if (this.undo.length > 80) this.undo.shift();
    this.redo = [];
    this.base = cur;
    this.baseKey = k;
    this.updateUI();
    projectChanged();
    return true;
  },
  schedule() { clearTimeout(this.timer); this.timer = setTimeout(() => this.commit(), 600); },
  flush() { clearTimeout(this.timer); return this.commit(); },
  canUndo() { return this.undo.length > 0 || (!!this.base && !!state.model && this.key(this.capture()) !== this.baseKey); },
  async go(dir) {
    this.flush();
    const from = dir < 0 ? this.undo : this.redo, to = dir < 0 ? this.redo : this.undo;
    const snap = from.pop();
    if (!snap) return false;
    to.push(this.base);
    await this.restore(snap);
    return true;
  },
  /** Back to the last recorded state without a new step (a cancelled rebuild). */
  async revert() {
    clearTimeout(this.timer);
    if (this.base) await this.restore(this.base, { solve: false });
  },
  async restore(snap, { solve = true } = {}) {
    this.restoring = true;
    try {
      state.model = clone(snap.model);
      state.userSet = new Set(snap.userSet);
      state.outlineEditor = snap.outlineEditor;
      state.layerPictures = clone(snap.layerPictures) || {};
      layers.set(clone(snap.layers));
      bends.set(clone(snap.bends));
      outlinePanel.set(state.model);
      updateFlatToggle();
      if (solve) await applyValues({ ...snap.values }, { quiet: true });
      else state.values = { ...snap.values };
      renderAll();
    } finally {
      this.base = snap;
      this.baseKey = this.key(this.capture());
      this.restoring = false;
      this.updateUI();
    }
  },
  updateUI() {
    const u = document.getElementById('undoBtn'), r = document.getElementById('redoBtn');
    if (u) u.disabled = !this.canUndo();
    if (r) r.disabled = !this.redo.length;
    window.__chat?.updateUndo();
  },
};
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
  outline: 'part size', drawing: 'from drawing', estimated: 'estimated', default: 'default', user: 'set by you', added: 'added by you',
  reference: 'reference', aligned: 'assumed', conflict: 'conflict',
};

function toast(msg, kind = 'info', ms = 4500) {
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.textContent = msg;
  $('toasts').appendChild(t);
  setTimeout(() => t.remove(), ms);
  return t;
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

const SAVE_TYPES = {
  json: ['Auto3DModeler project', 'application/json'], stl: ['STL 3D model', 'model/stl'], step: ['STEP CAD model', 'model/step'],
  glb: ['GLB 3D preview', 'model/gltf-binary'], zip: ['ZIP of pieces', 'application/zip'], pdf: ['PDF drawing', 'application/pdf'],
  igs: ['IGES CAD model', 'model/iges'], dxf: ['DXF drawing', 'image/vnd.dxf'], obj: ['OBJ 3D mesh', 'model/obj'],
  csv: ['CSV table', 'text/csv'], xlsx: ['Excel workbook', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
};
/** Save a file where the user chooses (name + folder: the browser's Save dialog, Edge / Chrome), else as a
 *  download. Resolves to the chosen file name, or null when the dialog was cancelled. */
async function download(blob, name, { id = 'auto3d-export' } = {}) {
  if (window.showSaveFilePicker) {
    const ext = name.split('.').pop().toLowerCase();
    const [description, mime] = SAVE_TYPES[ext] || ['File', blob.type || 'application/octet-stream'];
    try {
      const handle = await window.showSaveFilePicker({ suggestedName: name, id, types: [{ description: t(description), accept: { [mime]: [`.${ext}`] } }] });
      const w = await handle.createWritable();
      await w.write(blob);
      await w.close();
      return handle.name;
    } catch (e) {
      if (e.name === 'AbortError') return null; // the user closed the dialog
      // not allowed here (e.g. no user gesture left): fall back to a normal download
    }
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return name;
}

const layers = new LayersPanel($('layerList'), {
  onChange: () => scheduleRebuild(),
  onSelect: (L) => viewer.setSelection(L ? maskRings(L) : null, L?.face),
  unit: 'mm',
  canEditOutline: (L) => !!state.layerPictures[L.mask?.picture],
  onEditOutline: (L) => editLayerOutline(L),
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

const wizard = new OutlineWizard({ api, toast });
const outlinePanel = new OutlinePanel($('rtab-outline'), {
  onChange: (renderParamsToo) => { scheduleRebuild(); if (renderParamsToo) renderParams(); },
  onSelect: (rings) => {
    const r = rings || regionOf(outlinePanel.selected)?.rings || null;
    if (r) { layers.selected = null; layers.render(); }
    viewer.setSelection(r, 'over');
  },
  pick: (opts, onPick) => startPick(opts, onPick),
  canEditOutline: () => hasPicture(),
  onChangeOutline: () => editOutline(),
  getSolution: () => state.solution,
  api, toast,
});
const isOutline = () => state.model?.kind === 'outline';
const isMesh = () => state.model?.kind === 'mesh';
const isDrawing = () => !!state.model && !state.model.kind; // a PDF drawing (parametric)
/** The outline came from a picture (it can be reopened in the outline editor). */
const hasPicture = () => isOutline() && !!state.preview?.image;

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
/** Open a part (a parsed drawing, picture outline or import): it becomes its own part tab. */
async function loadParsed(data) {
  if (data.error) throw new Error(data.error);
  project.beginOpen();
  setWorkspace('quick');
  try {
    await loadPart(data);
  } catch (e) {
    await project.cancelOpen();
    throw e;
  }
  project.endOpen(partNameOf(data));
}

const partNameOf = (data) => (data.model?.source || 'part').replace(/\.(pdf|png|jpe?g|webp|gif|bmp|svg|dxf|dwg|stl|obj|3mf|step|stp|igs|iges)$/i, '');

/** Put a part on screen. `switching`: an existing part tab is shown again (no messages, no new tab). */
async function loadPart(data, { switching = false } = {}) {
  history.reset();
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
  // the project is named after its first part; later parts keep the name
  state.projectName = data.project_name || state.projectName || partNameOf(data);
  showProjectName();
  viewer.hasFitted = false;
  state.outlineEditor = data.outline_editor || null;
  state.layerPictures = data.layer_pictures || {};
  state.importFile = data.import_file || null;
  if (isMesh() && state.importFile) {
    // the server may not have the file (restarted / other machine): register it again (same id)
    try { state.model.mesh_id = (await (await api('/api/import/register', state.importFile)).json()).mesh_id; } catch (e) { toast(e.message, 'error'); }
  }
  state.model.point_dims = state.model.point_dims || [];
  outlinePanel.set(data.model);
  // the same tabs and tools for every kind of part; only the "source" section of the Part tab differs
  document.querySelector('.rtab[data-rtab="outline"]').hidden = false;
  $('editOutlineBtn').hidden = !hasPicture();
  $('drawingTools').hidden = false;
  $('drawingEdit').hidden = !hasPicture();
  if (!isDrawing()) switchRTab('outline');
  if (isDrawing() && !data.model.loops.length) {
    renderAll();
    if (switching) return;
    toast('No part outline could be recognised in this PDF — see Checks.', 'error', 8000);
    switchTab('issues');
    return;
  }
  await applyValues(state.values, { initial: true });
  if (!state.solution) { renderAll(); return; }
  const h = state.solution.bbox[3] - state.solution.bbox[1];
  $('snapStep').value = data.snap ?? nice(h / 20);
  renderAll();
  if (switching) return;
  const errs = data.model.issues.filter((i) => i.severity === 'error').length;
  const warns = data.model.issues.filter((i) => i.severity === 'warning').length;
  if (isOutline()) toast('Outline loaded — choose what to make in the Part tab, set the real size in Dimensions.', 'ok', 6000);
  else if (isMesh()) toast('3D file imported — orientation, scale and added objects are in the Part tab.', 'ok', 6000);
  else if (errs || warns) {
    toast(`Drawing read with ${errs ? `${errs} error(s)` : ''}${errs && warns ? ' and ' : ''}${warns ? `${warns} warning(s)` : ''} — review the highlighted dimensions.`, errs ? 'error' : 'warning', 7000);
    const unsure = data.model.issues.find((i) => i.code === 'unsure_outline'); // (a sheet of several views: maybe not the part)
    if (unsure) toast(unsure.message, 'warning', 12000);
  } else toast('All dimensions read successfully.', 'ok');
}

async function openPdf(file) {
  const fd = new FormData();
  fd.append('file', file);
  try {
    await loadParsed(await (await api('/api/parse', fd)).json());
  } catch (e) { toast(e.message, 'error', 8000); }
}

/** Picture -> outline wizard -> new outline model. */
async function openImage(file) {
  const res = await wizard.open(file);
  if (!res) return;
  try {
    await loadParsed(await (await api('/api/outline/model', res)).json());
    state.outlineEditor = res.editor;
  } catch (e) { toast(e.message, 'error', 8000); }
}

/** Reopen the outline editor on the outline the part is made from (with its edit and hints), and
 *  apply the result to the part, keeping size, shapes and objects. */
async function editOutline() {
  if (!isOutline() || !state.preview?.image) return;
  // the part's scale: mm per picture pixel of the outline in use
  const usedXs = state.model.outline.polygons.flatMap((p) => p[0].map((q) => q[0]));
  const mmPerPx = state.values.width / (Math.max(...usedXs) - Math.min(...usedXs));
  const res = await wizard.open({ url: state.preview.image, source: state.model.source }, {
    replace: true, size: { width: state.values.width, mmPerPx },
    current: { polygons: state.model.outline.polygons, ...(state.outlineEditor || {}) },
  });
  if (!res) return;
  state.outlineEditor = res.editor;
  const o = state.model.outline;
  const backup = { ...o };
  Object.assign(o, { polygons: res.polygons, img_w: res.img_w, img_h: res.img_h });
  const pts = res.polygons.flatMap((p) => p[0]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  o.aspect = (Math.max(...xs) - Math.min(...xs)) / (Math.max(...ys) - Math.min(...ys));
  let rejected = false;
  // set both sizes directly (the aspect ratio changed with the outline)
  const lock = o.lock;
  o.lock = false;
  await applyValues({ ...state.values, width: res.width, height: res.height }, { onReject: () => { rejected = true; } });
  o.lock = lock;
  if (rejected) { Object.assign(o, backup); await applyValues({ ...state.values }, { quiet: true }); } else toast('Outline applied to the part.', 'ok');
  renderAll();
}

$('editOutlineBtn').addEventListener('click', () => editOutline());

/** Picture-pixel polygons (y down) -> a mask in a unit box centred at 0 (y up), as image masks use. */
function unitPolygons(polys) {
  const pts = polys.flatMap((p) => p[0]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const bw = x1 - x0, bh = y1 - y0, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return {
    polygons: polys.map((poly) => poly.map((ring) => ring.map(([x, y]) => [+((x - cx) / bw).toFixed(6), +(-(y - cy) / bh).toFixed(6)]))),
    aspect: bw / bh, bw,
  };
}

/** 3D design: trace an object in a picture with the outline editor and use it as a layer mask. */
async function addOutlineLayer(file) {
  if (!state.solution) { toast('Open a drawing or a picture first — the outline is added to that part.', 'warning'); return; }
  const [x0, y0, x1, y1] = state.solution.bbox;
  const res = await wizard.open(file, { purpose: 'layer', size: { width: nice(Math.min(x1 - x0, y1 - y0) * 0.5) } });
  if (!res) return;
  const u = unitPolygons(res.polygons);
  const id = `P${Date.now().toString(36)}`;
  state.layerPictures[id] = { image: res.image, source: res.source, polygons: res.polygons, img_w: res.img_w, img_h: res.img_h, editor: res.editor };
  const L = newLayer('image', state.solution, { polygons: u.polygons, aspect: u.aspect, name: res.source.replace(/\.[^.]+$/, '') });
  Object.assign(L.mask, { w: res.width, h: res.height, picture: id });
  layers.add(L);
  switchRTab('design');
  toast('Outline added as a design layer — click where it goes, then choose emboss / engrave / cut through.', 'ok', 6000);
  placeLayer(L);
}

/** Reopen the outline editor for a traced layer mask; keeps the mask's scale and place. */
async function editLayerOutline(L) {
  const pic = state.layerPictures[L.mask.picture];
  if (!pic) return;
  const xs = pic.polygons.flatMap((p) => p[0].map((q) => q[0]));
  const mmPerPx = L.mask.w / (Math.max(...xs) - Math.min(...xs));
  const res = await wizard.open({ url: pic.image, source: pic.source }, {
    purpose: 'layer', replace: true, size: { width: L.mask.w, mmPerPx }, current: { polygons: pic.polygons, ...(pic.editor || {}) },
  });
  if (!res) return;
  const u = unitPolygons(res.polygons);
  Object.assign(pic, { polygons: res.polygons, editor: res.editor });
  Object.assign(L.mask, { polygons: u.polygons, aspect: u.aspect, w: res.width, h: res.height });
  layers.render();
  viewer.setSelection(maskRings(L), L.face);
  scheduleRebuild();
  toast('Layer outline updated.', 'ok');
}
$('outlineLayerInput').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) addOutlineLayer(f); });
$('drawingWrap').addEventListener('click', () => { if (state.model) enlargeDrawing(); });
$('drawingEdit').addEventListener('click', () => editOutline());
$('drawingEnlarge').addEventListener('click', () => enlargeDrawing());

/** mm across the full width of the Drawing tab's view (picture: the whole image; DXF: the padded drawing). */
function drawingWidthMM() {
  const o = state.model.outline;
  const xs = o.polygons.flatMap((p) => p[0].map((q) => q[0]));
  const bw = Math.max(...xs) - Math.min(...xs);
  const mmPerUnit = state.values.width / bw;
  if (o.space === 'mm') {
    const ys = o.polygons.flatMap((p) => p[0].map((q) => q[1]));
    const pad = Math.max(bw, Math.max(...ys) - Math.min(...ys)) * 0.04;
    return (bw + 2 * pad) * mmPerUnit;
  }
  return o.img_w * mmPerUnit;
}

/** The Drawing tab, large, with zoom and pan (and the way into the outline editor for pictures). */
function enlargeDrawing() {
  if (!state.model) return;
  openLightbox($('drawingWrap'), {
    title: state.model.source || 'Drawing',
    actions: hasPicture() ? [['✎ Edit outline', () => editOutline(), 'primary']] : [],
    mmAcross: isOutline() ? drawingWidthMM() : null,
  });
}

$('imgInput').addEventListener('change', (e) => { if (e.target.files[0]) openImage(e.target.files[0]); e.target.value = ''; });

const IMPORT_RE = /\.(dxf|dwg|stl|obj|3mf|step|stp)$/i;
/** DXF / DWG drawings (-> an outline in real mm) and STL / OBJ / 3MF / STEP 3D files (-> a sliced part). */
async function openImport(file) {
  const fd = new FormData();
  const rid = newRid();
  fd.append('rid', rid);
  fd.append('file', file);
  const stop = trackProgress(rid, `Uploading ${file.name}…`);
  let data;
  try {
    data = await (await api('/api/import', fd)).json();
  } catch (e) {
    stop();
    toast(e.message, /cancel/i.test(e.message) ? 'info' : 'error', 9000);
    return;
  }
  stop();
  try { await loadParsed(data); } catch (e) { toast(e.message, 'error', 9000); }
}
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
// CAD data (STEP, IGES) opens as a 3D model with its exact solid; a mesh (STL / OBJ / 3MF, mostly for printing) as a quick part
const OPEN_SOLID_RE = /\.(step|stp|igs|iges)$/i;
/** A STEP / IGES / STL / OBJ file made a solid by the kernel (kept on the server by its hash) -> {blob, name, faces,
 *  bbox, volume, op?, warning?} — an IGES of surfaces that do not close: op "ref" (a reference body) and why. */
async function importSolid(file, more = []) {
  const fd = new FormData(), rid = newRid();
  fd.append('rid', rid);
  for (const f of [file, ...more]) fd.append('file', f); // (more: the part files an assembly STEP refers to)
  const stop = trackProgress(rid, `Reading ${file.name}…`);
  try { return await (await api('/api/model/import', fd)).json(); } finally { stop(); }
}
/** The step of a 3D model that is that solid: joined (add), cut out of the part (cut), or a reference (ref). */
const solidStep = (r, id = 'F1', op = r.op || 'add') => ({ id, type: 'solid', name: r.name.replace(/\.[^.]+$/, ''), blob: r.blob, file: r.name, op });
/** Open a 3D file as a 3D model part: the exact solid, then sketches, holes … on it (a big mesh: a sliced quick part). */
async function openSolid(file, more = []) {
  let r;
  try { r = await importSolid(file, more); } catch (e) {
    if (/MESH_TOO_BIG/.test(e.message)) {
      toast(t('This mesh is too big to become an exact solid — it opens as a quick part (sliced), as before.'), 'info', 7000);
      await openImport(file);
    } else toast(e.message.replace(/^MESH_TOO_BIG /, ''), /cancel/i.test(e.message) ? 'info' : 'error', 9000);
    return;
  }
  const how = await askHowToOpen(r); // a STEP assembly (SolidWorks, CATIA, Solid Edge …): as an assembly, or one body
  if (!how) return;
  if (how === 'assembly') { await openStepAssembly(r); return; }
  await project.newModel({ features: [solidStep(r)] }, r.name.replace(/\.[^.]+$/, ''));
  toast(t2('{name} is open as a 3D model ({faces} faces) — sketch on its faces, add holes, or ask the AI to build on it.', { name: r.name, faces: r.faces }), 'ok', 7000);
  if (r.warning) toast(t(r.warning), r.op === 'ref' ? 'warning' : 'info', 10000); // (an IGES: sewn, or only a reference body)
  return r;
}
/** A STEP's assembly tree (r: importSolid's answer, or {blob, name}) -> its parts and sub-assemblies added to the
 *  project (closed) -> {tree, top: {name, data}} of the top assembly (not added). */
async function importTree(r) {
  const rid = newRid(), stop = trackProgress(rid, t2('Reading the assembly of {name}…', { name: r.name }));
  try {
    const tree = await (await api('/api/model/import/assembly', { blob: r.blob, name: r.name, rid })).json();
    const top = addTree(tree, { addModelPart: (n, d) => project.addBackground(n, d), addAssembly: (n, d) => project.addBackground(n, d, 'assembly') },
      r.name.replace(/\.[^.]+$/, ''));
    return { tree, top };
  } finally { stop(); }
}
/** A STEP assembly opened as an assembly of the project (its own tab). */
async function openStepAssembly(r) {
  let res;
  try { res = await importTree(r); } catch (e) { toast(e.message, /cancel/i.test(e.message) ? 'info' : 'error', 9000); return null; }
  await project.newAssembly(res.top.name, res.top.data);
  const n = treeSize(res.tree);
  toast(t2('{name} is open as an assembly: {parts} parts, {subs} sub-assemblies — each part a 3D model of the project.', { name: r.name, ...n }), 'ok', 8000);
  return { ...res, ...n };
}
// drawings: DXF / DWG, and PCB data — a Gerber set or an ODB++ job (a .zip / .tgz, or the Gerber / drill files)
const DRAWING_RE = /\.(dxf|dwg|zip|tgz|tar|gbr|ger|gtl|gbl|gto|gbo|gts|gbs|gtp|gbp|gko|gm\d*|gml|g\d+|cmp|sol|plc|pls|stc|sts|art|pho|drl|xln|drd|exc|ncd)$|\.tar\.gz$/i;
/** A DXF / DWG opens as it is (layers, lines, circles …) in the 2D drawing workspace — what to make of it comes later. */
async function openDrawing(file, more = []) {
  const fd = new FormData();
  for (const f of [file, ...more]) fd.append('file', f);
  try {
    const d = await (await api('/api/drawing/import', fd)).json();
    await project.newDrawing(d, file.name.replace(/\.(tar\.gz|[^.]+)$/i, ''));
    toast(d.pcb ? t2('{name}: a board of {k} layers ({n} shapes) — the copper on top, its outline and holes are shown; 👁 shows the others. ⬇ DXF saves the shown layers.', { name: file.name, n: d.entities.length, k: d.layers.length })
      : t2('{name}: {n} shapes on {k} layers — look, measure, tidy it up; Use ▾ makes a sketch or a quick part of it.', { name: file.name, n: d.entities.length, k: d.layers.length }), 'ok', 8000);
    for (const msg of d.issues || []) toast(msg, 'info', 8000);
  } catch (e) { toast(e.message, 'error', 9000); }
}
$('cadInput').addEventListener('change', (e) => {
  const all = [...e.target.files], f = all[0];
  e.target.value = '';
  // several Gerber / drill files picked together: one board (a drill file may be a .txt)
  if (all.length > 1 && all.every((x) => DRAWING_RE.test(x.name) || /\.txt$/i.test(x.name))) openDrawing(f, all.slice(1));
  // several STEP files: an assembly and the part files it refers to (CATIA) — the server opens the top one with them
  else if (all.length > 1 && all.every((x) => /\.(step|stp)$/i.test(x.name))) openSolid(f, all.slice(1));
  else if (f) (DRAWING_RE.test(f.name) ? openDrawing : OPEN_SOLID_RE.test(f.name) ? openSolid : openImport)(f);
});
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
  const f = e.dataTransfer.files[0], all = [...e.dataTransfer.files];
  if (!f) return;
  if (all.length > 1 && all.every((x) => /\.(step|stp)$/i.test(x.name))) { openSolid(f, all.slice(1)); return; } // (an assembly and its part files)
  if (/\.json$/i.test(f.name)) openProject(f);
  else if (/\.pdf$/i.test(f.name) || f.type === 'application/pdf') openPdf(f);
  else if (OPEN_SOLID_RE.test(f.name) && !e.shiftKey) openSolid(f); // Shift: a sliced quick part, as before
  else if (DRAWING_RE.test(f.name) && !e.shiftKey) openDrawing(f); // Shift: straight to a quick part, as before
  else if (IMPORT_RE.test(f.name)) openImport(f);
  else if (f.type.startsWith('image/')) {
    // with a part loaded a picture becomes a design layer; Shift+drop (or no part) traces its outline
    if (state.solution && !e.shiftKey) addImageLayer(f);
    else openImage(f);
  } else toast('Please drop a PDF, DXF / DWG, STL / OBJ / 3MF / STEP or a picture.', 'warning');
});

// ------------------------------------------------------------------ solving
let inflight = null, queued = null;

/** Rebuild with new parameter values; invalid results are rejected and the last valid model is kept. */
function applyValues(values, opts = {}) {
  values = lockAspect(scaleByDims(values));
  queued = { values, ...opts };
  if (!inflight) inflight = pump();
  return inflight;
}

/** Outline models: with the aspect ratio locked, a changed width drives the height and vice versa. */
function lockAspect(values) {
  if (!isOutline() || state.model.outline.lock === false) return values;
  const a = state.model.outline.aspect, prev = state.values;
  if (!(a > 0) || values.width === undefined) return values;
  if (values.width !== prev.width) return { ...values, height: +(values.width / a).toFixed(6) };
  if (values.height !== prev.height) return { ...values, width: +(values.height * a).toFixed(6) };
  return values;
}

// ------------------------------------------------------------------ point-to-point dimensions
// model.point_dims = [{id, a: [x, y, z], b: [x, y, z], axis: 'd' | 'x' | 'y' | 'z'}], each also a param
// (kind 'point'). On picture / DXF / 3D-file parts a changed value scales the part to fit (picture and
// DXF parts in x / y — heights stay; 3D files uniformly); on PDF drawings they are reference values
// (the drawing's dimensions drive the part).
const AXIS_NAME = { d: '', x: ' (X)', y: ' (Y)', z: ' (Z)' };
function measureOf(a, b, axis) {
  const d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  if (axis === 'x') return Math.abs(d[0]);
  if (axis === 'y') return Math.abs(d[1]);
  if (axis === 'z') return Math.abs(d[2]);
  return Math.hypot(...d);
}
const canScale = (axis) => isMesh() || (isOutline() && axis !== 'z');

function addPointDim(a, b, axis) {
  const m = state.model;
  const n = (m.point_dims?.length || 0) + 1;
  const id = `pd${Date.now().toString(36)}${n}`;
  const value = +measureOf(a, b, axis).toFixed(6);
  if (!(value > 0)) { toast('The two points are the same along that direction.', 'warning'); return; }
  m.point_dims = [...(m.point_dims || []), { id, a, b, axis }];
  m.params.push({ id, name: `Dimension ${n}${AXIS_NAME[axis]}`, kind: 'point', axis, value, unit: m.unit,
    role: canScale(axis) ? 'driving' : 'reference', source: 'added' });
  state.values = { ...state.values, [id]: value };
  renderParams();
  renderSolution();
  history.schedule();
  toast(canScale(axis) ? 'Dimension added — type a value to scale the part to it.' : 'Dimension added (reference — the drawing drives the part).', 'ok');
}

function removePointDim(id) {
  const m = state.model;
  m.point_dims = (m.point_dims || []).filter((d) => d.id !== id);
  m.params = m.params.filter((p) => p.id !== id);
  const { [id]: _, ...rest } = state.values;
  state.values = rest;
  renderParams();
  renderSolution();
  history.schedule();
}

/** A changed point dimension scales the part: values (sizes / scale) + everything placed in mm. */
function scaleByDims(values) {
  const m = state.model;
  if (!m?.point_dims?.length) return values;
  const changed = m.point_dims.find((d) => values[d.id] !== undefined && state.values[d.id] !== undefined
    && Math.abs(values[d.id] - state.values[d.id]) > 1e-9);
  if (!changed) return values;
  const k = values[changed.id] / state.values[changed.id];
  if (!canScale(changed.axis) || !(k > 0)) return { ...values, [changed.id]: state.values[changed.id] };
  const out = { ...values };
  const sz = isMesh(); // 3D files scale uniformly, picture / DXF parts only in x / y
  if (isMesh()) out.scale = +(values.scale * k).toFixed(6);
  else { out.width = +(values.width * k).toFixed(6); out.height = +(values.height * k).toFixed(6); }
  const scaleItem = (it) => {
    for (const key of ['x', 'y', 'x2', 'y2', 'w', 'h', 'width', 'stroke']) if (typeof it[key] === 'number') it[key] = +(it[key] * k).toFixed(6);
    if (sz) for (const key of ['z0', 'z1']) if (typeof it[key] === 'number') it[key] = +(it[key] * k).toFixed(6);
  };
  for (const it of [...(m.shapes || []), ...(m.extras || []), ...(m.preset === 'custom' ? (m.objects || []).filter((o) => o.source !== 'outline') : [])]) scaleItem(it);
  for (const d of m.point_dims) {
    for (const p of [d.a, d.b]) { p[0] *= k; p[1] *= k; if (sz) p[2] *= k; }
    out[d.id] = +measureOf(d.a, d.b, d.axis).toFixed(6);
  }
  outlinePanel.refreshOpen();
  return out;
}

/** 3D annotations of the point dimensions (an axis dimension runs along its axis from point a). */
function pointDimAnnotations() {
  return (state.model?.point_dims || []).filter((d) => param(d.id)).map((d) => {
    const { a, b, axis } = d;
    const p2 = axis === 'x' ? [b[0], a[1], a[2]] : axis === 'y' ? [a[0], b[1], a[2]] : axis === 'z' ? [a[0], a[1], b[2]] : b;
    return { param: d.id, p1_3d: a, p2_3d: p2, ext: axis === 'd' ? [] : [[p2, b]] };
  });
}

async function pump() {
  let cancelled = false;
  while (queued) {
    const job = queued;
    queued = null;
    const rid = newRid(), stop = trackProgress(rid, 'Building 3D…');
    try {
      const sol = await (await api('/api/solve', { model: state.model, values: job.values, layers: layers.layers, bends: activeBends(), rid })).json();
      if (sol.cancelled) {
        cancelled = true;
        queued = null; // drop what was waiting too
      } else if (sol.ok) {
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
    } finally {
      stop();
    }
  }
  inflight = null;
  if (cancelled) {
    // the part (e.g. a new slice height) was changed but not built: go back to the last good state
    await history.revert();
    toast('Cancelled — the part is back to its last state.', 'info');
    return;
  }
  history.schedule();
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
  showDrawing();
}

// ------------------------------------------------------------------ rendering
function renderAll() {
  const has = !!state.model;
  updateTopButtons();
  $('toModelBtn').hidden = !state.solution;
  $('paramsEmpty').hidden = has;
  $('paramHint').hidden = !has;
  renderParams();
  renderIssues();
  if (has) showDrawing();
  if (state.solution) renderSolution();
}

/** The Drawing tab: the PDF page, or for outline models the picture with the chosen outline. */
function showDrawing() {
  $('drawingWrap').classList.toggle('clickable', !!state.model);
  if (isMesh()) {
    $('drawingWrap').innerHTML = '<div class="empty">A 3D file has no drawing — see the 3D view.</div>';
    $('drawingWrap').style.aspectRatio = '';
    $('drawingWrap').classList.remove('clickable');
    return;
  }
  if (!isOutline()) { drawing.show(state.preview, state.model, statusOf); return; }
  const wrap = $('drawingWrap'), o = state.model.outline;
  if (o.space === 'mm') {
    // a DXF / DWG drawing: the closed regions in mm (y up)
    const pts = o.polygons.flatMap((p) => p[0]);
    const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const pad = Math.max(x1 - x0, y1 - y0) * 0.04;
    const d = o.polygons.map((poly) => poly.map((r) => `M${r.map(([x, y]) => `${x},${-y}`).join('L')}Z`).join('')).join('');
    wrap.style.aspectRatio = `${x1 - x0 + 2 * pad} / ${y1 - y0 + 2 * pad}`;
    wrap.innerHTML = `<svg viewBox="${x0 - pad} ${-y1 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}" preserveAspectRatio="none" style="position:static;display:block;width:100%;height:100%">
      <path d="${d}" fill="#3fb95022" fill-rule="evenodd" stroke="#1f6feb" stroke-width="${Math.max(x1 - x0, y1 - y0) / 400}"/></svg>`;
    wrap.classList.add('clickable');
    wrap.title = 'Click to enlarge';
    return;
  }
  wrap.style.aspectRatio = `${o.img_w} / ${o.img_h}`;
  const d = o.polygons.map((poly) => poly.map((r) => `M${r.map((p) => p.join(',')).join('L')}Z`).join('')).join('');
  const lw = Math.max(o.img_w, o.img_h) / 300;
  wrap.innerHTML = `<img alt=""><svg viewBox="0 0 ${o.img_w} ${o.img_h}" preserveAspectRatio="none">
    <path d="${d}" fill="#3fb95022" fill-rule="evenodd" stroke="#3fb950" stroke-width="${lw * 1.6}"/></svg>`;
  wrap.querySelector('img').src = state.preview?.image || '';
  wrap.classList.add('clickable');
  wrap.title = 'Click to enlarge';
}

function renderSolution() {
  const sol = state.solution;
  viewer.setSolution(sol);
  const [x0, y0, x1] = sol.bbox;
  const gap = Math.max(x1 - x0, sol.bbox[3] - y0) * 0.035;
  const thk = sol.thickness_3d
    ? { param: 'thickness', axis: 'z', p1_3d: sol.thickness_3d[0], p2_3d: sol.thickness_3d[1] }
    : { param: 'thickness', axis: 'z', p1: [x1 + gap, y0], p2: [x1 + gap, y0], z: 0, z2: sol.thickness };
  const anns = [...(param('thickness') ? [...sol.annotations, thk] : sol.annotations), ...(sol.bent ? [] : pointDimAnnotations())]
    .filter((a) => !param(a.param)?.hidden);
  bends.setInfo(sol.bends_info);
  outlinePanel.refreshInfo();
  const lf = sol.layer_faces, tgt = $('designTarget');
  tgt.hidden = !lf;
  if (lf) {
    tgt.innerHTML = `On this part, layers go on <b></b>: <i>front</i> = its top (z ${fmt(+lf.top.toFixed(3))} mm), <i>back</i> = its bottom (z ${fmt(+lf.bottom.toFixed(3))} mm).
      ${state.model.preset === 'custom' ? 'Move another object to the top of the list in the Part tab to decorate that one.' : 'Use <i>Edit as 3D objects</i> in the Part tab to choose another object.'}`;
    tgt.querySelector('b').textContent = `“${lf.object}”`;
  }
  viewer.setAnnotations(anns, makeLabel, statusOf);
  const sel = layers.layers.find((l) => l.id === layers.selected);
  const shapeSel = shapeRings(outlinePanel.selectedItem()) || regionOf(outlinePanel.selected)?.rings || null;
  viewer.setSelection(sel ? maskRings(sel) : shapeSel, sel ? sel.face : 'over');
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
    <span>${isOutline() ? `${(sol.objects || []).filter((o) => o.visible !== false).length} object(s)` : `${sol.loops.length - 1} cutout(s)`}</span><span>${layers.layers.filter((l) => l.visible).length} design layer(s)</span>
    <span>volume ${fmt(+(sol.volume ?? 0).toFixed(3))} ${u}³</span><span>${sol.mesh?.count ?? 0} triangles</span>`;
}

function groupOf(p) {
  if (p.hidden) return 'hidden';
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
    reference: 'Reference (driven by others)', hidden: 'Hidden (still used)',
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
        ${p.hidden ? '<button class="mini show-dim" title="Show this dimension in the view again">Show</button>'
    : !canDeleteDim(p) ? '<button class="mini hide-dim" title="Hide this dimension from the view (the drawing still sets it)">Hide</button>' : ''}
      </span></div>`;
  const name = row.querySelector('.name');
  name.textContent = p.name;
  row.querySelector('.src').textContent = src;
  name.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); name.blur(); } });
  name.addEventListener('blur', () => {
    const n = name.textContent.trim();
    if (n && n !== p.name && n !== t(p.name)) { p.name = n; showDrawing(); }  // a translated name is not a rename
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
  row.querySelector('.show-dim')?.addEventListener('click', () => { delete p.hidden; renderParams(); renderSolution(); history.schedule(); });
  row.querySelector('.hide-dim')?.addEventListener('click', () => deleteDim(p.id));
  row.querySelector('.remove')?.addEventListener('click', () => (p.kind === 'point' ? removePointDim(p.id)
    : structuralChange(() => deleteDimension(state.model, state, p.id), `${p.name} removed.`)));
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

/** Dimensions you added (and point dimensions) can be deleted; the drawing's own ones drive the part. */
const canDeleteDim = (p) => !!p && (p.kind === 'point' || p.source === 'added');
let hoveredDim = null;
function deleteDim(id) {
  const p = param(id);
  if (!p) return;
  if (!canDeleteDim(p)) {
    // a size the drawing needs: hidden from the view (it still sets the part), back with Show in Dimensions
    p.hidden = true;
    renderParams();
    renderSolution();
    history.schedule();
    toast(`${p.name} hidden — the drawing still sets this size. Show it again in Dimensions (Hidden).`, 'ok', 5000);
    return;
  }
  if (p.kind === 'point') removePointDim(id);
  else structuralChange(() => deleteDimension(state.model, state, id), `${p.name} removed.`);
}

// 3D labels: click to type, drag to scrub, wheel to nudge
function makeLabel(a) {
  const p = param(a.param);
  const el = document.createElement('div');
  const st = statusOf(a.param);
  el.className = `dim-label ${st}`;
  const v = state.solution.values[a.param] ?? state.values[a.param];
  el.textContent = st === 'reference' ? `(${fmt(v)})` : `${fmt(v)}${a.param === 'thickness' ? ` ${p.unit} thk` : ''}`;
  el.title = `${p.name} — ${STATUS_LABEL[st]}${p.role === 'driving' ? '\nClick to edit · drag ↔ or scroll to change' : ''}${canDeleteDim(p) ? '\n✕ or Delete (while pointing at it) removes it' : '\n✕ or Delete (while pointing at it) hides it'}`;
  el.addEventListener('mouseenter', () => { highlightRow(a.param, true); hoveredDim = a.param; });
  el.addEventListener('mouseleave', () => { highlightRow(a.param, false); if (hoveredDim === a.param) hoveredDim = null; });
  {
    const x = document.createElement('span');
    x.className = 'dim-x';
    x.textContent = '✕';
    x.title = canDeleteDim(p) ? 'Delete this dimension' : 'Hide this dimension (the drawing still sets it)';
    x.addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); hoveredDim = null; deleteDim(a.param); });
    el.appendChild(x);
  }
  if (p.role !== 'driving') return el;

  el.addEventListener('wheel', (e) => {
    e.preventDefault();
    e.stopPropagation();
    nudgeLive(a.param, e.deltaY < 0 ? 1 : -1, e);
  }, { passive: false });

  el.addEventListener('pointerdown', (e) => {
    if (el.querySelector('input') || e.target.closest('.dim-x')) return;
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
  const design = [...(state.solution?.design_issues || []), ...(isOutline() ? state.solution?.issues || [] : [])].map((i) => ({ ...i, design: true }));
  const open = [...issues.filter((i) => !i.resolved), ...design];
  const errs = open.filter((i) => i.severity === 'error').length;
  const warns = open.filter((i) => i.severity === 'warning').length;
  const c = $('issueCount');
  c.textContent = errs + warns || '';
  c.className = `count ${errs ? 'err' : warns ? 'warn' : ''}`;

  const dimCount = state.model.params.filter((p) => p.source === 'drawing').length;
  const sum = document.createElement('div');
  sum.className = 'summary';
  const intro = isOutline() ? 'Outline traced from a picture — set its real size in Dimensions.'
    : `Read <b>${dimCount}</b> dimension(s) from the drawing; outline with <b>${Math.max(0, state.model.loops.length - 1)}</b> cutout(s).`;
  sum.innerHTML = `<span class="intro">${intro}</span><br>
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
$('measureBtn').addEventListener('click', () => startMeasure(false));

/** What is under a picked point: a round hole / boss (cylinder) or a flat face (from the server's features). */
function featureAt(h) {
  const F = state.solution?.features;
  if (!h || !F) return null;
  const tol = (viewer.size || 1) * 0.004;
  const onWall = Math.abs(h.normal[2]) < 0.5;
  let best = null;
  for (const c of F.circles) {
    if (h.z < c.z0 - tol || h.z > c.z1 + tol) continue;
    const d = Math.abs(Math.hypot(h.x - c.x, h.y - c.y) - c.r);
    // on its wall — or on a face, its rim (a click right at the edge of a hole)
    if ((onWall && d < tol * 2) || (!onWall && d < tol) || (!onWall && c.hole === false && Math.abs(h.z - c.z1) < tol && Math.hypot(h.x - c.x, h.y - c.y) < c.r)) {
      if (!best || d < best.d) best = { kind: 'circle', ...c, d };
    }
  }
  if (best) return best;
  if (!onWall) {
    const face = F.faces.find((f) => Math.abs(f.z - h.z) < tol && (f.up === h.normal[2] > 0) && inRings(f.rings, h.x, h.y));
    if (face) return { kind: 'face', ...face };
  }
  return null;
}

function featureText(ft) {
  const u = state.model.unit, f = (v) => `${fmt(+v.toFixed(3))} ${u}`;
  if (!ft) return '';
  if (ft.kind === 'circle') return `${ft.hole ? 'hole' : 'cylinder'} Ø ${f(2 * ft.r)}`;
  return `${ft.up ? 'top' : 'bottom'} face ${fmt(+ft.area.toFixed(2))} ${u}²`;
}

/** Measure on the part: click a feature (hole, cylinder, face) for its size; a second click measures the
 *  distance — centre to centre when circles were picked. Results can be kept as dimensions. */
function startMeasure(asDimension) {
  if (!state.solution) return;
  if (state.solution.bent) { toast('Switch to Flat view to measure.', 'warning'); return; }
  $('measureBox').hidden = true;
  viewer.setMeasure(null);
  const what = asDimension ? 'the dimension' : 'the measurement';
  startPick({ hint: `Click a point, hole, cylinder or face — the first point of ${what}` }, (a) => {
    const fa = featureAt(a);
    viewer.setMeasure([pointOf(a, fa)]);
    showMeasure(a, null, asDimension);
    startPick({ hint: `Click the second point of ${what} (Esc = keep just the first)` }, (b) => showMeasure(a, b, asDimension));
  });
}

/** The point a pick stands for: a circle's centre (at the pick height), else the pick itself. */
function pointOf(h, ft) {
  return ft?.kind === 'circle' ? { x: ft.x, y: ft.y, z: Math.min(Math.max(h.z, ft.z0), ft.z1) } : h;
}

function showMeasure(a, b, asDimension) {
  const u = state.model.unit, f = (v) => `${fmt(+v.toFixed(3))} ${u}`;
  const fa = featureAt(a), fb = b ? featureAt(b) : null;
  const box = $('measureBox');
  box.hidden = false;
  const featRows = (ft, label) => {
    if (!ft) return '';
    if (ft.kind === 'circle') {
      return `<span>${label}</span><b>${ft.hole ? 'Hole' : 'Cylinder / boss'}</b><span>Ø</span><b>${f(2 * ft.r)}</b><span>radius</span><b>${f(ft.r)}</b>
        <span>centre</span><b>${fmt(+ft.x.toFixed(3))}, ${fmt(+ft.y.toFixed(3))}</b><span>${ft.hole ? 'depth' : 'height'}</span><b>${f(ft.z1 - ft.z0)} (z ${fmt(+ft.z0.toFixed(3))}–${fmt(+ft.z1.toFixed(3))})</b>`;
    }
    return `<span>${label}</span><b>${ft.up ? 'Top' : 'Bottom'} face at z ${fmt(+ft.z.toFixed(3))}</b><span>area</span><b>${fmt(+ft.area.toFixed(3))} ${u}²</b>
      <span>perimeter</span><b>${f(ft.perimeter)}</b>`;
  };
  let rows = featRows(fa, b ? 'First' : 'Picked');
  let keep = '';
  let A = null, B = null;
  if (b) {
    const pa = pointOf(a, fa), pb = pointOf(b, fb);
    A = [pa.x, pa.y, pa.z];
    B = [pb.x, pb.y, pb.z];
    const centres = fa?.kind === 'circle' || fb?.kind === 'circle';
    const dist = measureOf(A, B, 'd');
    viewer.setMeasure([pa, pb], f(dist));
    rows += featRows(fb, 'Second');
    rows += `<span>${centres ? 'Distance (centres)' : 'Distance'}</span><b>${f(dist)}</b><span>Δx</span><b>${f(Math.abs(B[0] - A[0]))}</b>
      <span>Δy</span><b>${f(Math.abs(B[1] - A[1]))}</b><span>Δz</span><b>${f(Math.abs(B[2] - A[2]))}</b>`;
    keep = `<div class="mb-keep">${asDimension ? 'Add as' : 'Keep as dimension'}:
      <button class="btn small" data-axis="d">Distance</button><button class="btn small" data-axis="x">X</button><button class="btn small" data-axis="y">Y</button><button class="btn small" data-axis="z">Z</button></div>`;
  } else if (!fa) {
    rows += `<span>Point</span><b>${fmt(+a.x.toFixed(3))}, ${fmt(+a.y.toFixed(3))}, ${fmt(+a.z.toFixed(3))}</b>`;
  }
  const circle = fa?.kind === 'circle' ? fa : fb?.kind === 'circle' ? fb : null;
  if (circle) keep += `<div class="mb-keep">Keep the Ø ${f(2 * circle.r)} as a dimension: <button class="btn small" data-dia="1">Ø</button></div>`;
  box.innerHTML = `<div class="mb-head"><b>${asDimension ? 'New dimension' : 'Measure'}</b><button class="icon-btn mb-x" title="Close">✕</button></div>
    <div class="mb-rows">${rows}</div>${keep}
    ${b ? '' : '<p class="hint">Click a second point to measure a distance (centre to centre with holes / cylinders).</p>'}
    <div class="row-actions"><button class="btn small mb-again">📏 ${asDimension ? 'Another dimension' : 'Measure again'}</button></div>`;
  const close = () => { box.hidden = true; viewer.setMeasure(null); stopPick(); };
  box.querySelector('.mb-x').addEventListener('click', close);
  box.querySelector('.mb-again').addEventListener('click', () => startMeasure(asDimension));
  for (const btn of box.querySelectorAll('[data-axis]')) {
    btn.addEventListener('click', () => { addPointDim(A, B, btn.dataset.axis); close(); if (asDimension) startMeasure(true); });
  }
  box.querySelector('[data-dia]')?.addEventListener('click', () => {
    // a diameter = the distance between two opposite points of the circle, through its centre (along x)
    const z = circle.z1;
    addPointDim([circle.x - circle.r, circle.y, z], [circle.x + circle.r, circle.y, z], 'd');
    close();
  });
}

$('dimToolBtn').addEventListener('click', async () => {
  if (!state.solution) return;
  // picture / DXF / 3D-file parts: dimensions between two picked points (as many as you like)
  if (!isDrawing()) { startMeasure(true); return; }
  if (state.solution.bent) { await setFlatView(true); toast('Switched to Flat view to pick edges.', 'info', 3000); }
  if (printPanel.pieces) printPanel.exitSplit();
  if (dimTool.active) dimTool.stop(); else dimTool.start();
});
$('undoBtn').addEventListener('click', () => history.go(-1));
$('redoBtn').addEventListener('click', () => history.go(1));
window.addEventListener('keydown', (e) => {
  if (state.workspace !== 'quick') return; // the 3D model and assembly workspaces have their own keys
  if (e.target.closest?.('input,select,textarea,[contenteditable]')) return;
  if (document.querySelector('.wizard, .lightbox')) return; // they have their own keys
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')) {
    e.preventDefault();
    history.go(k === 'y' || e.shiftKey ? 1 : -1);
    return;
  }
  if (e.key === 'Escape' && outlinePanel.selected) { outlinePanel.selected = null; outlinePanel.render(); viewer.setSelection(null); }
  if (e.key === 'Delete' && hoveredDim) { deleteDim(hoveredDim); hoveredDim = null; return; }
  if ((e.key === 'd' || e.key === 'D') && state.solution && !dimTool.active) $('dimToolBtn').click();
  if ((e.key === 'm' || e.key === 'M') && state.solution) startMeasure(false);
  if (e.key === 'Delete' && outlinePanel.selected && !layers.selected) {
    const m = state.model;
    m.shapes = (m.shapes || []).filter((s) => s.id !== outlinePanel.selected);
    m.objects = (m.objects || []).filter((o) => o.id !== outlinePanel.selected);
    m.extras = (m.extras || []).filter((o) => o.id !== outlinePanel.selected);
    outlinePanel.selected = null;
    outlinePanel.render();
    viewer.setSelection(null);
    scheduleRebuild();
  }
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
$('addShape').addEventListener('click', () => {
  if (!state.solution) return;
  const L = newLayer('shape', state.solution);
  layers.add(L);
  placeLayer(L);
});

/** Click where a new layer's mask goes (its centre); a click on the back face puts it on the back.
 *  Esc keeps it in the middle of the part. */
function placeLayer(L) {
  if (!L || !state.solution || state.solution.bent) return;
  startPick({ hint: `Click on the part where “${L.name}” goes` }, (h) => {
    Object.assign(L.mask, { x: h.x, y: h.y });
    if (h.normal[2] < -0.5) L.face = 'bottom';
    else if (h.normal[2] > 0.5) L.face = 'top';
    layers.render();
    viewer.setSelection(maskRings(L), L.face);
    scheduleRebuild();
  });
}
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
    toast('Image traced — click where it goes on the part, then choose emboss / engrave / cut.', 'ok');
    placeLayer(layers.layers.at(-1));
  } catch (e) { toast(`Could not use that image: ${e.message || e}`, 'error'); }
}

// drag masks on the part
const canvas = viewer.renderer.domElement;
let drag = null;

// ------------------------------------------------------------------ picking points / faces on the part
// startPick({hint}, onPick): the next click on the part calls onPick({x, y, z, normal, snap});
// the camera can still be orbited (only a click without dragging picks). Esc cancels.
let picking = null;
const SNAP_LABEL = { corner: 'corner', edge: 'edge', 'top face': 'top face', 'bottom face': 'bottom face', wall: 'wall', surface: '' };
function startPick({ hint }, onPick) {
  if (!state.solution) return;
  if (state.solution.bent) { toast('Switch to Flat view to pick on the part.', 'warning'); return; }
  stopPick();
  picking = { onPick, down: null };
  $('toolHint').textContent = `${hint} — Esc cancels`;
  $('toolHint').hidden = false;
  canvas.style.cursor = 'crosshair';
  vp.classList.add('picking'); // dimension labels let clicks through to the part
}
function stopPick() {
  picking = null;
  $('toolHint').hidden = true;
  canvas.style.cursor = '';
  vp.classList.remove('picking');
  viewer.setMarker(null);
}
const fmtMM = (v) => (+v.toFixed(2)).toString();
canvas.addEventListener('pointermove', (e) => {
  if (!picking) return;
  const h = viewer.pickSurface(e.clientX, e.clientY);
  const ft = h && featureAt(h);
  viewer.setMarker(h, h && (ft ? `${featureText(ft)} · ` : SNAP_LABEL[h.snap] ? `${SNAP_LABEL[h.snap]} · ` : '') + `x ${fmtMM(h.x)}  y ${fmtMM(h.y)}  z ${fmtMM(h.z)}`);
});
canvas.addEventListener('pointerdown', (e) => {
  if (picking && e.button === 0) picking.down = [e.clientX, e.clientY];
}, true);
canvas.addEventListener('pointerup', (e) => {
  if (!picking || e.button !== 0 || !picking.down) return;
  const moved = Math.hypot(e.clientX - picking.down[0], e.clientY - picking.down[1]) > 4;
  picking.down = null;
  if (moved) return; // that was an orbit
  const h = viewer.pickSurface(e.clientX, e.clientY);
  if (!h) { toast('Click on the part.', 'warning', 2000); return; }
  const cb = picking.onPick;
  stopPick();
  cb(h);
});
window.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || state.workspace !== 'quick') return;
  if (picking) stopPick();
  else if (!$('measureBox').hidden) { $('measureBox').hidden = true; viewer.setMeasure(null); }
});

canvas.addEventListener('pointerdown', (e) => {
  if (!state.solution || e.button !== 0 || dimTool.active || printPanel.pieces || bends.placing || state.solution.bent || picking) return;
  // hit-test on the surface under the cursor (its height too: a click on a band next to a post is the band);
  // dragging then moves the primitive on a plane above the part
  const pt0 = viewer.pickFace(e.clientX, e.clientY, 'over');
  const surf = viewer.pickSurface(e.clientX, e.clientY);
  const tolZ = (viewer.size || 1) * 1e-3; // pickSurface puts a flat face at its exact height: a box 3 mm under it is not it
  const shapes = outlinePanel.draggables().sort((a, b) => (b.id === outlinePanel.selected) - (a.id === outlinePanel.selected));
  const at = surf || pt0;
  const hitS = at && shapes.find((s) => hitShape(s, at.x, at.y)
    && (!surf || s.z0 === undefined || (surf.z >= s.z0 - tolZ && surf.z <= s.z1 + tolZ)));
  if (hitS && pt0) {
    if (outlinePanel.selected !== hitS.id) outlinePanel.select(hitS.id);
    drag = { S: hitS, last: pt0 };
    clickAt = null;
    viewer.controls.enabled = false;
    canvas.setPointerCapture(e.pointerId);
    e.stopPropagation();
    return;
  }
  const ordered = [...layers.layers].reverse().sort((a, b) => (b.id === layers.selected) - (a.id === layers.selected));
  for (const L of ordered) {
    if (!L.visible) continue;
    const pt = viewer.pickFace(e.clientX, e.clientY, L.face);
    if (pt && hitMask(L, pt.x, pt.y)) {
      if (layers.selected !== L.id) { layers.selected = null; layers.select(L.id); }
      drag = { L, dx: L.mask.x - pt.x, dy: L.mask.y - pt.y };
      clickAt = null;
      viewer.controls.enabled = false;
      canvas.setPointerCapture(e.pointerId);
      e.stopPropagation();
      return;
    }
  }
}, true);
canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  if (drag.S) {
    const pt = viewer.pickFace(e.clientX, e.clientY, 'over');
    if (!pt) return;
    const S = drag.S, step = parseFloat($('snapStep').value);
    let dx = pt.x - drag.last.x, dy = pt.y - drag.last.y;
    if ($('snapToggle').checked && step > 0) {
      dx = Math.round(dx / step) * step;
      dy = Math.round(dy / step) * step;
      if (!dx && !dy) return;
    }
    drag.last = { x: drag.last.x + dx, y: drag.last.y + dy };
    for (const k of ['x', 'x2']) if (S[k] !== undefined) S[k] = +(S[k] + dx).toFixed(6);
    for (const k of ['y', 'y2']) if (S[k] !== undefined) S[k] = +(S[k] + dy).toFixed(6);
    viewer.setSelection(shapeRings(S), 'over');
    drag.moved = true;
    return;
  }
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
/** The footprint (from the server) of an object by id. */
function regionOf(id) { return id ? (state.solution?.object_regions || []).find((r) => r.id === id) : null; }

function inRings(rings, x, y) {
  let c = false;
  for (const r of rings) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
    }
  }
  return c;
}
function nearRings(rings, x, y, tol) {
  for (const r of rings) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [ax, ay] = r[j], [bx, by] = r[i], dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L));
      if (Math.hypot(ax + t * dx - x, ay + t * dy - y) < tol) return true;
    }
  }
  return false;
}

/** Select the object under a click on the part (the last one built there wins: holes, posts on top …). */
function selectAt(clientX, clientY) {
  const h = viewer.pickSurface(clientX, clientY);
  const regions = state.solution?.object_regions || [];
  const tol = (viewer.size || 1) * 0.006, tolZ = (viewer.size || 1) * 1e-3;
  const hit = h && [...regions].reverse().find((r) => h.z >= r.z0 - tolZ && h.z <= r.z1 + tolZ
    && (inRings(r.rings, h.x, h.y) || nearRings(r.rings, h.x, h.y, tol)));
  if (!hit) {
    if (outlinePanel.selected) { outlinePanel.selected = null; outlinePanel.render(); viewer.setSelection(null); }
    return;
  }
  if (hit.preset) {
    viewer.setSelection(hit.rings, 'over');
    toast(`“${hit.name}” is part of the ${state.model.preset === 'cutter' ? 'cookie cutter' : state.model.preset} preset — use “Edit as 3D objects →” in the Part tab to change or delete it.`, 'info', 5000);
    return;
  }
  outlinePanel.selected = hit.id;
  outlinePanel.render();
  outlinePanel.onSelect(null);
  switchRTab('outline');
  toast(`Selected “${hit.name}” — Delete removes it, Esc deselects.`, 'info', 2500);
}
let clickAt = null;
// (a click that places / picks something is not also a selection)
canvas.addEventListener('pointerdown', (e) => { clickAt = e.button === 0 && !picking ? [e.clientX, e.clientY] : null; });
canvas.addEventListener('pointerup', (e) => {
  const c = clickAt;
  clickAt = null;
  if (!c || drag || picking || dimTool.active || printPanel.pieces || bends.placing || !state.solution || state.solution.bent) return;
  if (Math.hypot(e.clientX - c[0], e.clientY - c[1]) > 4) return; // that was an orbit
  selectAt(e.clientX, e.clientY);
});

const endDrag = () => {
  if (!drag) return;
  const moved = drag.moved, wasShape = !!drag.S;
  drag = null;
  viewer.controls.enabled = true;
  if (moved) { if (wasShape) outlinePanel.refreshOpen(); else layers.refreshOpen(); scheduleRebuild(); }
};
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);

// ------------------------------------------------------------------ export / projects
$('exportBtn').addEventListener('click', (e) => { e.stopPropagation(); $('exportBtn').parentElement.classList.toggle('open'); });
$('openBtn').addEventListener('click', (e) => { e.stopPropagation(); $('openMenuWrap').classList.toggle('open'); });
// a choice closes the menu (the file dialog opens from the label)
$('openMenu').addEventListener('click', (e) => { if (e.target.closest('.menu-item, button')) setTimeout(() => $('openMenuWrap').classList.remove('open'), 0); });
document.addEventListener('click', (e) => { if (!e.target.closest('#openMenuWrap')) $('openMenuWrap').classList.remove('open'); });
document.addEventListener('click', () => $('exportBtn').parentElement.classList.remove('open'));
$('exportMenu').addEventListener('click', async (e) => {
  const fmtName = e.target.dataset.fmt;
  if (fmtName === '3mf' && (state.workspace === 'model' || state.workspace === 'assembly')) { $('exportBtn').parentElement.classList.remove('open'); export3mf(); return; }
  if (fmtName && state.workspace === 'model') { $('exportBtn').parentElement.classList.remove('open'); modeler.export(fmtName); return; }
  if (fmtName && state.workspace === 'assembly') { $('exportBtn').parentElement.classList.remove('open'); assembly.export(fmtName); return; }
  if (!fmtName || !state.solution) return;
  const base = safeName();
  const open = state.model.issues.filter((i) => (i.severity !== 'info') && !(RESOLVABLE.has(i.code) && i.params.every((p) => state.userSet.has(p) || !param(p))));
  try {
    if (fmtName === 'glb') {
      const buf = await viewer.exportGLB(UNIT_TO_M[state.model.unit]);
      if (!(await download(new Blob([buf], { type: 'model/gltf-binary' }), `${base}.glb`))) return;
    } else {
      const res = await api(`/api/export/${fmtName}`, { model: state.model, values: state.values, layers: layers.layers, bends: bends.bends });
      if (!(await download(await res.blob(), `${base}.${fmtName}`))) return;
    }
    toast(open.length ? `Exported ${fmtName.toUpperCase()} (in mm). Note: ${open.length} unresolved check(s) — estimated values may be wrong.`
      : `Exported ${fmtName.toUpperCase()} (in mm).`, open.length ? 'warning' : 'ok', 6000);
  } catch (err) { toast(`Export failed: ${err.message}`, 'error'); }
});

/** ⬇ 3MF in colours: the model, or the whole assembly — an object per colour (each gets its filament in the slicer). */
async function export3mf() {
  try {
    const r = await agentHandlers.export_data({ format: '3mf' });
    const res = await fetch('/api/export/3mf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(r.data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
    if (await download(await res.blob(), `${safeName()}.3mf`)) toast(t2('Exported 3MF: {n} coloured object(s) — give each its filament in the slicer.', { n: r.data.groups.length }), 'ok', 6000);
  } catch (e) { toast(`Export failed: ${e.message}`, 'error'); }
}

function showProjectName() {
  const el = $('fileName');
  el.toggleAttribute('data-no-i18n', !!state.projectName);  // the user's own name
  el.textContent = state.projectName || 'No drawing loaded';
  el.title = state.model ? `Project “${state.projectName}” from ${state.model.source} — click to rename` : state.projectName ? 'Click to rename the project' : '';
  el.classList.toggle('editable', !!(state.model || state.projectName));
}
$('fileName').addEventListener('click', () => {
  const el = $('fileName');
  if (!(state.model || state.projectName) || el.isContentEditable) return;
  el.contentEditable = 'true';
  el.focus();
  document.getSelection().selectAllChildren(el);
});
$('fileName').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
  if (e.key === 'Escape') { e.target.textContent = state.projectName; e.target.blur(); }
});
$('fileName').addEventListener('blur', (e) => {
  e.target.contentEditable = 'false';
  const n = e.target.textContent.trim().replace(/[\\/:*?"<>|]+/g, '_');
  if (n && n !== state.projectName) { state.projectName = n; toast(`Project renamed to “${n}”.`, 'ok', 2500); }
  showProjectName();
});
const safeName = () => (state.projectName || 'part').replace(/[\\/:*?"<>|]+/g, '_').trim() || 'part';
/** File names for a model / an assembly: the tab's name (the project may hold several). */
const tabName = () => (project.current?.name || '').replace(/[\/:*?"<>|]+/g, '_').trim() || safeName();

/** The part on screen as saved in the project (a version-2 file held exactly this). */
function partPayload() {
  return {
    model: state.model, preview: state.preview, values: state.values,
    userSet: [...state.userSet], layers: layers.layers, bends: bends.bends, snap: parseFloat($('snapStep').value), original: state.original,
    outline_editor: state.outlineEditor,
    import_file: state.importFile,
    layer_pictures: Object.fromEntries(Object.entries(state.layerPictures).filter(([id]) => layers.layers.some((L) => L.mask?.picture === id))),
  };
}

// the parts of the project: tabs in the top bar
const project = new Project($('partTabs'), {
  payload: (kind) => (kind === 'model' ? modeler.payload() : kind === 'assembly' ? assembly.payload() : kind === 'drawing' ? drawing2d.payload() : kind === 'sheet' ? sheet.payload() : structuredClone(partPayload())),
  async load(data, opts) {
    setWorkspace(['model', 'assembly', 'drawing', 'sheet'].includes(opts.kind) ? opts.kind : 'quick');
    if (opts.kind === 'model') modeler.load(data, { then: opts.then });
    else if (opts.kind === 'assembly') await assembly.load(data);
    else if (opts.kind === 'drawing') drawing2d.load(data);
    else if (opts.kind === 'sheet') await sheet.load(data);
    else await loadPart(data, opts);
    if (!state.projectName) { state.projectName = project.current?.name || 'Project'; showProjectName(); }
  },
  async settle() {
    clearTimeout(rebuildTimer);
    while (inflight) await inflight;
    while (modeler.inflight) await modeler.inflight;
    history.flush();
  },
  getHistory: (kind) => (kind === 'model' ? modeler.history.state : kind === 'assembly' ? assembly.history.state : kind === 'drawing' ? drawing2d.history.state : kind === 'sheet' ? sheet.history.state
    : { undo: history.undo, redo: history.redo, base: history.base, baseKey: history.baseKey }),
  setHistory(h, kind) {
    if (kind === 'model') modeler.history.state = h;
    else if (kind === 'assembly') assembly.history.state = h;
    else if (kind === 'drawing') drawing2d.history.state = h;
    else if (kind === 'sheet') sheet.history.state = h;
    else { Object.assign(history, h); history.updateUI(); }
  },
  openWindow: (id) => windows.open(id).catch((e) => toast(e.message, 'warning', 7000)),
  showNone: (on) => document.body.classList.toggle('none-open', on), // the last tab closed
  windowId: () => windows?.wid, // (tabs dragged between windows)
  async thumb(p) { // the tree's hover preview: what is in the part
    const data = project.dataOf(p);
    if (p.kind === 'sheet') return data?.built ? svgPicture(sheet.svgOf(data)) : null;
    if (p.kind === 'model') return data?.features?.length ? picture([{ body: await bodyOf(data.features), color: 0xa98be0 }], `m${JSON.stringify(data.features).length}:${p.id}:${JSON.stringify(data.features)}`) : null;
    if (p.kind !== 'assembly') return null;
    const list = [], walk = async (asm, M, depth, inner = null) => { // (sub-assemblies' parts too, placed — moved inside them: `inner`)
      for (const it of asm?.instances || []) {
        const q = project.parts.find((x) => x.id === it.part), d = q && project.dataOf(q), mi = inner?.[it.id] || it.matrix;
        const m = M ? new THREE.Matrix4().fromArray(M).multiply(new THREE.Matrix4().fromArray(mi)).toArray() : mi;
        if (q?.kind === 'assembly' && depth < 4) await walk(d, m, depth + 1, it.inner);
        else if (d?.features?.length) list.push({ body: await bodyOf(d.features), matrix: m, color: [0xa98be0, 0x7ee787, 0x58a6ff, 0xe3b341, 0xff9b7a][list.length % 5] });
      }
    };
    await walk(data, null, 0);
    return picture(list, `a${p.id}:${JSON.stringify(list.map((x) => x.matrix))}:${list.length}`);
  },
  projectId: () => autosave?.id,
  tookTab: (id, win) => windows?.tell({ took: id, win }), // (the window it came from lets it go)
  toast,
});

// ------------------------------------------------------------------ workspaces: Quick part | 3D model
// A classic part (drawing, picture, import) is edited in the Quick part workspace; a 3D model part
// (sketches -> extrude …) in the 3D model workspace. The part tab decides which one is on screen.
const modeler = new Modeler({ left: $('modelLeft'), viewport: $('modelViewport'), right: $('modelRight') }, {
  toast, download, safeName: () => tabName(),
  onChange: () => updateTopButtons(),
  pickOutline: () => pickOutlineFile(),
  importSolid: (file) => importSolid(file),
  backTo: (id) => id && project.switchTo(id),
  saveToLibrary: () => saveToLibrary(project.current?.name || safeName(), modeler.payload(), toast),
  saveBackToLibrary: () => saveBackToLibrary().catch((e) => toast(e.message, 'error', 7000)),
  duplicatePart: async () => { await project.duplicate(); toast(t2('{name} — a copy of its own (change it without changing the original).', { name: project.current?.name }), 'ok', 5000); },
  // ✂ Split's pieces as parts of their own: new tabs, the first one opened
  newParts: async (parts) => {
    const ids = parts.map((p) => project.addBackground(p.name, p.data));
    for (const p of project.parts) if (ids.includes(p.id)) delete p.closed;
    await project.switchTo(ids[0]);
    toast(t('Each piece is a part of its own now — the part you split keeps both.'), 'ok', 5000);
  },
  newSheet: () => { const p = project.current; if (p) project.newSheet(p.id, `${p.name} — ${t('drawing')}`); },
  // a printing copy of a model part: its STEP as a Quick part, on the 3D print tab (split exactly: printexact.py)
  async toPrint(blob) {
    const name = `${project.current?.name || safeName()} (print).step`;
    await openImport(new File([blob], name, { type: 'model/step' }));
    if (state.workspace === 'quick' && isMesh()) switchRTab('print');
  },
});

// ------------------------------------------------------------------ outlines of classic parts in 3D models
/** The outline of a part (picture, DXF / DWG, PDF, 3D file) in mm: {polygons, width, height, name}. */
async function outlineOfModel(model, values) {
  const res = await api('/api/model/profile', { model, values: values || Object.fromEntries(model.params.map((p) => [p.id, p.value])), layers: [] });
  return res.json();
}

/** 🖼 Outline in a sketch: choose a picture (traced in the outline editor), a DXF / DWG or a PDF drawing. */
function pickOutlineFile() {
  return new Promise((resolve) => {
    document.getElementById('outlinePickInput')?.remove();
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.id = 'outlinePickInput';
    inp.hidden = true;
    inp.accept = 'image/*,.pdf,.dxf,.dwg';
    document.body.appendChild(inp); // in the page while choosing (a browser test can hand it a file)
    inp.addEventListener('cancel', () => { inp.remove(); resolve(null); });
    inp.addEventListener('change', async () => {
      const file = inp.files[0];
      inp.remove();
      if (!file) { resolve(null); return; }
      try {
        let data;
        const ext = file.name.toLowerCase().split('.').pop();
        if (file.type.startsWith('image/')) {
          const res = await wizard.open(file);
          if (!res) { resolve(null); return; }
          data = await (await api('/api/outline/model', res)).json();
        } else {
          const fd = new FormData();
          fd.append('file', file);
          data = await (await api(ext === 'pdf' ? '/api/parse' : '/api/import', fd)).json();
        }
        if (data.error) throw new Error(data.error);
        resolve(await outlineOfModel(data.model, data.values));
      } catch (e) {
        toast(e.message, 'error', 7000);
        resolve(null);
      }
    });
    inp.click();
  });
}

/** ◆ To 3D model: the open part's outline as the first sketch of a new model, Extrude ready. */
$('toModelBtn').addEventListener('click', async () => {
  if (!state.model || !state.solution) return;
  try {
    history.flush();
    const o = await outlineOfModel(state.model, state.values);
    const sketch = { id: 'F1', type: 'sketch', name: `${t('Sketch')} 1`, plane: { datum: 'XY' }, points: {}, constraints: [], dims: [],
      entities: [{ id: 'b1', t: 'block', name: o.name, polys: o.polygons, w0: o.width, h0: o.height, scale: 1, at: [0, 0] }] };
    await project.newModel({ features: [sketch] }, `${project.current?.name || o.name} — 3D`, 'extrude');
    toast('A 3D model was made from the outline — give it a height (Extrude), then add holes, roundings…', 'ok', 6000);
  } catch (e) { toast(e.message, 'error', 7000); }
});
// 2D drawings (DXF / DWG): a viewer and editor; Use ▾ makes a 3D model sketch or a quick part of one
const drawing2d = new DrawingEditor({ left: $('dwgLeft'), viewport: $('dwgViewport'), right: $('dwgRight') }, {
  toast, download, safeName: () => tabName(), onChange: () => updateTopButtons(),
  async useAsSketch(d) {
    if (!d.entities.some((e) => e.t !== 'text')) { toast(t('Nothing to sketch on the shown layers.'), 'warning'); return; }
    if (d.entities.length > 3000) toast(t('A big sketch — hide the layers you do not need first, it is quicker to work with.'), 'info', 7000);
    const name = `${project.current?.name || t('Drawing')} (${t('3D model')})`;
    await project.newModel({ features: [drawingToSketch(d)] }, name, 'none');
    toast(t('The drawing is the sketch of a new 3D model — edit it, or ⬆ Extrude it.'), 'ok', 6000);
  },
  async useAsQuick(d) {
    try { await loadParsed(await (await api('/api/drawing/outline', d)).json()); } catch (e) { toast(e.message, 'error', 8000); }
  },
});

// drawing sheets (📄) of 3D model parts: views and dimensions, made again when the part changes
/** A part's data as it is now (the one on screen from its workspace). */
function partDataNow(id) {
  const p = project.parts.find((q) => q.id === id);
  if (!p) return null;
  if (p.id === project.active && p.data === 'live') return p.kind === 'model' ? modeler.payload() : p.kind === 'assembly' ? assembly.payload() : null;
  return typeof p.data === 'object' ? p.data : null;
}
const sheet = new SheetEditor({ left: $('shLeft'), viewport: $('shViewport'), right: $('shRight') }, {
  toast, download, safeName: () => tabName(), onChange: () => updateTopButtons(),
  progress: (rid, label) => trackProgress(rid, label), // (a sheet being made: the progress bar with Cancel)
  partData: (id) => partDataNow(id),
  partName: (id) => project.parts.find((q) => q.id === id)?.name || null,
  kindOf: (id) => project.parts.find((q) => q.id === id)?.kind,
  drawingCtx: () => drawingCtx(),
  parts: () => project.parts,
  openSheet: (id) => { const p = project.parts.find((q) => q.id === id); if (p) project.newSheet(id, `${p.name} — ${t('drawing')}`); },
  openPart: (id) => project.switchTo(id),
  // a title-block template on every sheet of a drawing set (ids: its pages' sources); the top assembly gets a sheet
  // when it has none (new sheets of the set take the template from it) -> how many sheets
  applyTemplate: (root, name, ids) => {
    let n = 0;
    for (const id of ids) {
      const p = project.parts.find((q) => q.kind === 'sheet' && (q.data === 'live' ? q.id === project.active && sheet.d?.source === id : q.data?.source === id));
      const d = !p ? null : p.data === 'live' ? sheet.d : p.data;
      if (d) { d.template = name; delete d.tb; delete d.frame; n++; continue; }
      if (id !== root) continue; // (a page without its own sheet: drawn with the set's template)
      const now = new Date().toISOString(), a = project.parts.find((q) => q.id === root);
      project.addBackground(`${a?.name || root} — ${t('drawing')}`, { source: root, preset: 'medium', created: now, changed: now, rev: 1, template: name }, 'sheet');
      n++;
    }
    updateTopButtons();
    return n;
  },
});
/** The drawing set of an assembly as one PDF -> the downloaded file's name (pages: the assembly, its sub-assemblies, the parts). */
/** What a drawing set needs to know of the project. */
function drawingCtx() {
  return {
    kindOf: (id) => project.parts.find((q) => q.id === id)?.kind,
    sheetOf: (id) => { // (the sheet on screen as it is now)
      const p = project.parts.find((q) => q.kind === 'sheet' && (q.data === 'live' ? q.id === project.active && sheet.d?.source === id : q.data?.source === id));
      return !p ? null : p.data === 'live' ? sheet.payload() : p.data;
    },
    bought: (data, name) => isStandard(data, name),
    massOf: (id) => assembly.massOf(id), // (g each, from the assembly's bodies when it has built that part)
  };
}
async function drawingSetPdf(aid, { quiet = false } = {}) {
  const ctx = drawingCtx();
  const busy = quiet ? null : toast(t('Making the drawings…'), 'info', 60000);
  try {
    const set = await sheet.drawingSet(aid, ctx);
    const res = await fetch('/api/sheet/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ svgs: set.svgs, name: tabName() }) });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    const blob = await res.blob();
    if (quiet) return { blob, set };
    await download(blob, `${tabName()} — drawings.pdf`);
    toast(t2('{n} pages: {pages}', { n: set.svgs.length, pages: set.pages.join(', ') }), 'ok', 7000);
    return { blob, set };
  } catch (e) { if (quiet) throw e; toast(e.message, 'error', 8000); return null; } finally { busy?.remove?.(); }
}

// a part changed: its sheets (closed ones too) get a new revision and the date — made again when opened
let sheetTimer = null;
window.addEventListener('a3d:changed', () => {
  clearTimeout(sheetTimer);
  sheetTimer = setTimeout(() => {
    for (const p of project.parts) {
      if (p.kind !== 'sheet' || typeof p.data !== 'object' || !p.data?.hash) continue;
      const h = sheet.sourceHash(p.data.source); // (an assembly's: its parts too)
      if (!h) continue;
      if (h === p.data.hash) continue;
      Object.assign(p.data, { hash: h, rev: (p.data.rev || 1) + 1, changed: new Date().toISOString() });
      if (p.data.built) p.data.built.stale = true;
    }
  }, 800);
});

// assemblies: 3D model parts of the project placed together
const assembly = new Assembly({ left: $('asmLeft'), viewport: $('asmViewport'), right: $('asmRight') }, {
  toast, download, safeName: () => tabName(),
  parts: () => project.parts,
  partData: (id) => { const p = project.parts.find((q) => q.id === id); return p && typeof p.data === 'object' ? p.data : null; },
  addModelPart: (name, data) => project.addBackground(name, data),
  // a STEP / STL / OBJ to insert: a solid step, or (a STEP assembly, if wanted) a new sub-assembly of the project
  importFile: async (file) => {
    const r = await importSolid(file), how = await askHowToOpen(r);
    if (r.warning) toast(t(r.warning), r.op === 'ref' ? 'warning' : 'info', 10000);
    if (how !== 'assembly') return how ? { step: solidStep(r) } : null;
    const { top } = await importTree(r);
    return { part: project.addBackground(top.name, top.data, 'assembly') };
  },
  duplicatePart: (id) => project.duplicate(id, false),
  renamePart: (id, name) => project.rename(id, name),
  editInPlace: async (id, ctx) => { await project.switchTo(id); if (project.active === id) modeler.setContext(ctx); },
  openPart: (id) => project.switchTo(id),
  drawingSet: () => drawingSetPdf(project.active),
  newSheet: () => { const p = project.current; if (p) project.newSheet(p.id, `${p.name} — ${t('drawing')}`); },
  selfId: () => project.active, // the assembly on screen (it may not go into itself)
  setRoot: (id) => sheet.rootOf(id), // the top assembly whose drawing set numbers its parts (the BOM's positions)
  onChange: () => updateTopButtons(),
});
state.workspace = 'quick';
function setWorkspace(ws) {
  state.workspace = ws;
  document.body.classList.toggle('ws-model', ws === 'model');
  document.body.classList.toggle('ws-assembly', ws === 'assembly');
  document.body.classList.toggle('ws-drawing', ws === 'drawing');
  document.body.classList.toggle('ws-sheet', ws === 'sheet');
  sheet.active = ws === 'sheet';
  modeler.active = ws === 'model';
  assembly.active = ws === 'assembly';
  drawing2d.active = ws === 'drawing';
  if (ws === 'drawing') { dimTool.stop(); requestAnimationFrame(() => drawing2d.resize()); }
  if (ws === 'model') { modeler.view.resize(); dimTool.stop(); }
  if (ws === 'assembly') { assembly.view.resize(); dimTool.stop(); }
  placeChat();
  updateTopButtons();
}

// the AI chat: a tab of the quick-part panel; in the 3D model and assembly workspaces the ✨ AI button opens it in a drawer
function placeChat() {
  const el = $('tab-ai'), drawer = $('aiDrawer'), quick = state.workspace === 'quick';
  if (quick && el.parentElement === drawer) document.querySelector('.panel.left.quick-only').insertBefore(el, $('tab-drawing'));
  if (!quick && el.parentElement !== drawer) drawer.appendChild(el);
  drawer.hidden = quick || !state.chatOpen;
  $('aiBtn').classList.toggle('on', !drawer.hidden);
  // the drawer takes its room from the layout (the panels stay usable), the 3D views fit the new size
  if (document.body.classList.toggle('chat-open', !drawer.hidden) !== !!placeChat.was) {
    placeChat.was = !drawer.hidden;
    requestAnimationFrame(() => { if (state.workspace === 'model') modeler.view.resize(); if (state.workspace === 'assembly') assembly.view.resize(); });
  }
}
function toggleChat(open = !state.chatOpen) {
  state.chatOpen = open;
  placeChat();
  if (open) $('aiDrawer').querySelector('textarea')?.focus();
}
$('aiBtn').addEventListener('click', () => toggleChat());
// ✨ in the Suggested table: what is selected goes into the chat (the AI's tools know these ids)
setAskAI((refs) => {
  toggleChat(true);
  const ta = $('tab-ai').querySelector('textarea');
  if (!ta) return;
  ta.value = `${ta.value.trim() ? `${ta.value.trimEnd()}\n` : ''}[${t('Selected')} ${refs}] `;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
});
$('aiClose').addEventListener('click', () => toggleChat(false));
function updateTopButtons() {
  if (state.workspace === 'sheet') {
    $('saveBtn').disabled = false;
    $('exportBtn').disabled = true;
  } else if (state.workspace === 'drawing') {
    $('saveBtn').disabled = false;
    $('exportBtn').disabled = true;
  } else if (state.workspace === 'assembly') {
    $('saveBtn').disabled = false;
    $('exportBtn').disabled = !assembly.hasBody();
  } else if (state.workspace === 'model') {
    $('saveBtn').disabled = false;
    $('exportBtn').disabled = !modeler.hasBody();
  } else {
    $('saveBtn').disabled = !state.model;
    $('exportBtn').disabled = !state.solution;
  }
}
$('newModelBtn').addEventListener('click', () => project.newModel());

/** The project file (every part; the imported files it uses are added on Save). */
function projectFile() {
  return { app: 'Auto3DModeler', version: 3, project_name: state.projectName, unit: state.model?.unit || 'mm', ...project.toJSON(), assets: {}, assemblies: [] };
}

$('saveBtn').addEventListener('click', async () => {
  const proj = projectFile();
  proj.blobs = await projectBlobs(proj);
  const saved = await download(new Blob([JSON.stringify(proj)], { type: 'application/json' }), `${safeName()}.a3d.json`, { id: 'auto3d-project' });
  if (!saved) return;
  // a name changed in the Save dialog becomes the project's name
  const n = saved.replace(/\.a3d\.json$|\.json$/i, '');
  if (n && n !== state.projectName) { state.projectName = n; showProjectName(); }
  toast(`Project saved as ${saved}.`, 'ok');
});

/** The imported files (by hash) the project's 3D models use, base64 — so the project opens on another computer. */
async function projectBlobs(proj) {
  const shas = new Set(proj.parts.flatMap((p) => (p.model?.features || []).filter((f) => f.type === 'solid' && f.blob).map((f) => f.blob)));
  const out = {};
  for (const sha of shas) {
    const res = await fetch(`/api/blob/${sha}`);
    if (!res.ok) continue;
    const u = new Uint8Array(await res.arrayBuffer());
    let s = '';
    for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
    out[sha] = btoa(s);
  }
  return out;
}

async function openProject(file) {
  try {
    const raw = JSON.parse(await file.text());
    // its imported files back to the server first (by their hash)
    for (const [sha, b] of Object.entries(raw.blobs || {})) {
      const bin = atob(b), u = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
      await fetch('/api/blob', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: u });
      void sha;
    }
    delete raw.blobs;
    const res = await api('/api/project/migrate', raw);
    const proj = await res.json();
    if (proj.error) throw new Error(proj.error);
    state.projectName = proj.project_name;
    await autosave?.saveNow(); // (the one on screen kept first)
    await project.loadAll(proj);
    autosave?.fresh();
    showProjectName();
    toast(proj.parts.length > 1 ? `Project loaded — ${proj.parts.length} parts (tabs in the top bar).` : 'Project loaded.', 'ok');
  } catch (e) { toast(e.message, 'error'); }
}
$('projectInput').addEventListener('change', (e) => { if (e.target.files[0]) openProject(e.target.files[0]); e.target.value = ''; });

// auto-load the sample when opened with ?sample
if (new URLSearchParams(location.search).has('sample')) $('sampleBtn').click();
// ------------------------------------------------------------------ AI agent (MCP tools)
// Each tool the AI calls through the app's MCP server arrives here and is applied like a user edit:
// visible at once, with an undo snapshot taken before every change.
// every AI change is its own step in the app's undo history: pending user edits are recorded first
function aiSnapshot() { history.flush(); }
async function aiUndo() {
  if (!(await history.go(-1))) return { text: 'Nothing to undo.', error: true };
  return { text: `Undone. ${partLine()}` };
}

const r3 = (v) => (typeof v === 'number' ? +v.toFixed(3) : v);
/** An item without bulky geometry (traced text / logo polygons). */
const lean = (it) => Object.fromEntries(Object.entries(it).filter(([k]) => k !== 'polygons' && k !== 'preset_opts_by').map(([k, v]) => [k, r3(v)]));

function partLine() {
  const sol = state.solution;
  if (!sol) return 'No valid part.';
  const [x0, y0, x1, y1] = sol.bbox3 ? sol.bbox3.slice(0, 4) : sol.bbox, [z0, z1] = sol.z_range || [0, sol.thickness];
  const errs = [...(sol.design_issues || []), ...(sol.issues || [])].filter((i) => i.severity === 'error' || i.severity === 'warning');
  return `Size ${r3(x1 - x0)} × ${r3(y1 - y0)} × ${r3(z1 - z0)} ${state.model.unit}, volume ${r3(sol.volume)} ${state.model.unit}³.`
    + (errs.length ? ` Issues: ${errs.map((i) => `[${i.severity}] ${i.message}`).join(' ')}` : '');
}

function partSummary() {
  const m = state.model, sol = state.solution;
  if (!m) return { open: false, hint: 'No part is open in the app. Ask the user what to open (a file, or a picture to trace) — do not open the sample unless they ask.' };
  const kind = isOutline() ? (m.outline.space === 'mm' ? 'outline (from a DXF drawing)' : 'outline (traced from a picture)') : isMesh() ? 'imported 3D file' : 'PDF drawing';
  const out = {
    source: m.source, kind, unit: m.unit,
    dimensions: m.params.map((p) => ({ id: p.id, name: p.name, value: r3(sol?.values?.[p.id] ?? state.values[p.id]), role: p.role, kind: p.kind })),
  };
  if (sol) {
    const [x0, y0, x1, y1] = sol.bbox, [z0, z1] = sol.z_range || [0, sol.thickness];
    Object.assign(out, { bbox: { x0: r3(x0), y0: r3(y0), x1: r3(x1), y1: r3(y1), z0: r3(z0), z1: r3(z1) }, z_levels: (sol.z_levels || []).map(r3), volume: r3(sol.volume) });
    if (sol.layer_faces) out.design_layers_go_on = sol.layer_faces;
    if (sol.outline_bbox) out.profile_bbox = sol.outline_bbox.map(r3);
  }
  if (isOutline()) {
    out.make = { preset: m.preset, options: m.preset_opts, lock_aspect: m.outline.lock !== false, mirror: !!m.outline.mirror, cleanup: m.outline.cleanup || {} };
    if (m.preset === 'custom') out.objects = (m.objects || []).map(lean);
    else if (sol?.objects) out.preset_objects = sol.objects.map(lean);
  }
  if (isMesh()) out.import_options = m.mesh_opts;
  out.added_objects = (m.extras || []).map(lean);
  if (!isMesh()) out.shapes = (m.shapes || []).map(lean);
  out.design_layers = layers.layers.map((L) => ({ id: L.id, name: L.name, op: L.op, depth: L.depth, face: L.face, visible: L.visible,
    mask: lean(L.mask || {}), fill: { pattern: L.fill?.pattern, sx: L.fill?.sx, sy: L.fill?.sy, width: L.fill?.width, use: L.fill?.use } }));
  out.point_dimensions = (m.point_dims || []).map((d) => ({ ...d, value: r3(state.values[d.id]) }));
  const issues = [...(sol?.design_issues || []), ...(sol?.issues || []), ...(m.issues || [])].filter((i) => i.severity !== 'info');
  out.issues = issues.map((i) => `[${i.severity}] ${i.message}`);
  out.printer = printPanel.printer()?.name;
  return out;
}

/** Apply the current model; reports the result (or why it was rejected). */
async function aiBuild(label) {
  state.lastError = null;
  await applyValues({ ...state.values }, { quiet: true });
  renderAll();
  history.flush();
  if (state.lastError) return { text: `${label} — but the model is invalid: ${state.lastError.join(' ')} (use undo to go back).`, error: true };
  return { text: `${label}. ${partLine()}` };
}

const OBJECT_KIND = { cylinder: 'circle', box: 'rect', bar: 'line', text: 'text', profile: 'fill', band: 'band' };
const ITEM_KEYS = ['name', 'op', 'x', 'y', 'w', 'h', 'rot', 'x2', 'y2', 'width', 'z0', 'z1', 'stroke', 'offset', 'inner', 'outer', 'text', 'font', 'bold', 'visible', 'mode', 'round'];
const pick = (args, keys) => Object.fromEntries(keys.filter((k) => args[k] !== undefined).map((k) => [k, args[k]]));
function findItem(id) {
  const m = state.model;
  for (const key of ['objects', 'extras', 'shapes']) {
    const arr = m[key] || [];
    const i = arr.findIndex((o) => o.id === id);
    if (i >= 0) return { arr, i, it: arr[i], key };
  }
  const i = layers.layers.findIndex((L) => L.id === id);
  if (i >= 0) return { arr: layers.layers, i, it: layers.layers[i], key: 'layers' };
  return null;
}

const needPart = () => { if (!state.model || !state.solution) throw new Error('No part is open in the app — ask the user what to open.'); };

const agentHandlers = {
  get_part: async () => ({ text: JSON.stringify(partSummary()) }),
  // (wrapped below: on a 3D model part only opening a file works for now)

  get_screenshot: async ({ view }) => {
    needPart();
    if (view) viewer.setView(view);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    viewer.renderer.render(viewer.scene, viewer.camera);
    const src = viewer.renderer.domElement, k = Math.min(1, 900 / Math.max(src.width, src.height));
    const c = document.createElement('canvas');
    c.width = Math.round(src.width * k);
    c.height = Math.round(src.height * k);
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#161b22';
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(src, 0, 0, c.width, c.height);
    return { text: `3D view (${view || 'current'}). ${partLine()}`, image: c.toDataURL('image/png').split(',')[1] };
  },

  ask_user: async ({ question, options, recommended = 0 }) => {
    if (!String(question || '').trim() || !Array.isArray(options) || options.length < 2) throw new Error('question, and 2–5 options [{label, description}] (recommended: the number of yours, 0 = the first).');
    const opts = options.slice(0, 5).map((o) => (typeof o === 'string' ? { label: o } : { label: String(o.label || ''), description: o.description ? String(o.description) : undefined }));
    if (opts.some((o) => !o.label)) throw new Error('Each option needs a label.');
    if (state.workspace === 'quick') document.querySelector('.tab[data-tab=ai]')?.click(); else if ($('aiDrawer').hidden) toggleChat(true); // (the chat in sight)
    window.__chat?.ask({ question: String(question), options: opts, recommended: Math.max(0, Math.min(opts.length - 1, Number.parseInt(recommended, 10) || 0)) });
    return { text: 'Shown in the app\'s chat as buttons (your recommended one first, marked ★). End your turn now and wait: the user\'s choice comes as their next message ("<question> → <option>"). Several questions: one ask_user each in this turn, then end it — the answers come together.' };
  },
  load_drawing: async ({ data, name }) => {
    await project.newDrawing(data, name);
    for (const msg of data.issues || []) toast(msg, 'info', 8000);
    return { text: `Opened ${name} as a 📐 drawing: ${data.entities.length} shapes on ${data.layers.length} layers${data.pcb ? ' (a board: the top copper, outline, holes and silkscreen shown)' : ''}${data.issues?.length ? `; notes: ${data.issues.join(' ')}` : ''}. get_drawing tells its layers and size.` };
  },
  load_solid: async ({ blob, name }) => { // an IGES from disk: a 3D model part with its solid (/api/model/import)
    const file = new File([await (await fetch(`/api/blob/${blob}`)).blob()], name);
    const r = await openSolid(file);
    if (!r) throw new Error(`${name} could not be opened.`);
    const bb = r.bbox ? ` ${r.bbox.slice(3).map((v, i) => +(v - r.bbox[i]).toFixed(2)).join(' × ')} mm,` : '';
    return { text: `Opened ${name} as the 3D model “${project.current?.name}”: one solid step F1 (op ${r.op || 'add'}),${bb} ${r.faces} faces${r.op === 'ref' ? '' : `, ${r.volume} mm³`}.${r.warning ? ` Note: ${r.warning}` : ''} get_model / find_refs give its faces.` };
  },
  load_step_assembly: async ({ blob, name }) => {
    const r = await openStepAssembly({ blob, name });
    if (!r) throw new Error(`${name} could not be opened as an assembly.`);
    const names = Object.values(r.tree.parts).map((p) => p.name);
    return { text: `Opened ${name} as the assembly “${r.top.name}”: ${r.parts} different parts (${names.slice(0, 12).join(', ')}${names.length > 12 ? ' …' : ''}), ${r.placements} placements, ${r.subs} sub-assemblies; each part is a 3D model of the project (a solid step). get_assembly lists the placed parts.` };
  },
  load: async ({ data, editor }) => {
    await loadParsed(data);
    if (editor) state.outlineEditor = editor;
    history.updateUI();
    return { text: `Opened ${state.model.source}. ${partLine()}` };
  },

  get_body: async () => {
    needPart();
    return { text: 'ok', body: { model: state.model, values: state.values, layers: layers.layers, bends: bends.bends } };
  },

  set_dimensions: async ({ values }) => {
    needPart();
    const next = { ...state.values }, done = [], skipped = [];
    for (const [k, v] of Object.entries(values || {})) {
      const p = state.model.params.find((q) => q.id === k) || state.model.params.find((q) => q.name.toLowerCase() === String(k).toLowerCase());
      if (!p) { skipped.push(`${k} (unknown)`); continue; }
      if (p.role !== 'driving') { skipped.push(`${p.name} (a reference value — it follows the others)`); continue; }
      if (!Number.isFinite(+v)) { skipped.push(`${p.name} (not a number)`); continue; }
      next[p.id] = +v;
      state.userSet.add(p.id);
      done.push(`${p.name} = ${+v}`);
    }
    if (!done.length) return { text: `Nothing set: ${skipped.join(', ')}`, error: true };
    aiSnapshot();
    state.lastError = null;
    await applyValues(next, { quiet: true });
    renderAll();
    if (state.lastError) return { text: `Rejected: ${state.lastError.join(' ')}`, error: true };
    history.flush();
    return { text: `Set ${done.join(', ')}${skipped.length ? `; skipped ${skipped.join(', ')}` : ''}. ${partLine()}` };
  },

  set_make: async ({ preset, options }) => {
    needPart();
    if (!isOutline()) return { text: 'Only outline parts (picture / DXF) have presets — use add_object for other parts.', error: true };
    aiSnapshot();
    const m = state.model;
    if (preset && preset !== m.preset) {
      if (preset === 'custom' && !(m.objects || []).length) m.objects = clone(state.solution.objects || []);
      m.preset = preset;
      if (preset !== 'custom') m.preset_opts = { ...outlinePanel.defaults(preset), ...(m.preset_opts_by?.[preset] || {}) };
    }
    if (options && m.preset !== 'custom') {
      m.preset_opts = { ...m.preset_opts, ...options };
      m.preset_opts_by = { ...(m.preset_opts_by || {}), [m.preset]: { ...m.preset_opts } };
    }
    outlinePanel.render();
    return aiBuild(`Making: ${m.preset}`);
  },

  set_part_options: async (a) => {
    needPart();
    aiSnapshot();
    const m = state.model;
    if (isOutline()) {
      if (a.lock_aspect !== undefined) m.outline.lock = !!a.lock_aspect;
      if (a.mirror !== undefined) m.outline.mirror = !!a.mirror;
      if (a.cleanup) m.outline.cleanup = { ...(m.outline.cleanup || {}), ...a.cleanup };
    } else if (isMesh()) {
      m.mesh_opts = { ...m.mesh_opts, ...pick(a, ['up', 'rot', 'mirror', 'layer']) };
    } else return { text: 'PDF parts have no such options — change their dimensions instead.', error: true };
    outlinePanel.render();
    return aiBuild('Options changed');
  },

  add_object: async (a) => {
    needPart();
    const kind = OBJECT_KIND[a.kind];
    if (!kind) return { text: `Unknown kind ${a.kind}.`, error: true };
    const m = state.model;
    const ob = outlinePanel.newObject(kind);
    Object.assign(ob, pick(a, ITEM_KEYS));
    if (ob.op === 'add') ob.op = 'union';
    if (kind === 'fill' || kind === 'band') ob.name = a.name || (kind === 'band' ? 'Profile band' : 'Profile');
    if (kind === 'text' && !(await outlinePanel.traceText(ob))) return { text: 'The text produced no outline.', error: true };
    aiSnapshot();
    const key = isOutline() && m.preset === 'custom' ? 'objects' : 'extras';
    m[key] = [...(m[key] || []), ob];
    outlinePanel.render();
    const res = await aiBuild(`Added ${ob.name} (id ${ob.id})`);
    return res;
  },

  add_shape: async (a) => {
    needPart();
    if (isMesh()) return { text: 'Imported 3D files have no 2D profile — use add_object.', error: true };
    const s = outlinePanel.newShape(a.kind === 'hole' ? 'hole' : a.kind === 'text' ? 'text' : a.kind);
    Object.assign(s, pick(a, ITEM_KEYS));
    if (s.op === 'union') s.op = 'add';
    if (a.kind === 'text' && !(await outlinePanel.traceText(s))) return { text: 'The text produced no outline.', error: true };
    aiSnapshot();
    state.model.shapes = [...(state.model.shapes || []), s];
    outlinePanel.render();
    return aiBuild(`Added 2D ${s.name} (id ${s.id})`);
  },

  add_design_layer: async (a) => {
    needPart();
    const L = newLayer(a.kind === 'grid' ? 'grid' : 'shape', state.solution);
    Object.assign(L, pick(a, ['name', 'op', 'depth', 'face', 'margin']));
    if (a.mask) Object.assign(L.mask, a.mask);
    if (a.fill) Object.assign(L.fill, a.fill);
    aiSnapshot();
    layers.layers.push(L);
    layers.render();
    return aiBuild(`Added design layer ${L.name} (id ${L.id})`);
  },

  update_item: async ({ id, fields }) => {
    needPart();
    const f = findItem(id);
    if (!f) return { text: `No item with id ${id}.`, error: true };
    aiSnapshot();
    const { mask, fill, ...rest } = fields || {};
    Object.assign(f.it, rest);
    if (mask && f.it.mask) Object.assign(f.it.mask, mask);
    if (fill && f.it.fill) Object.assign(f.it.fill, fill);
    if ((rest.text !== undefined || rest.font !== undefined || rest.bold !== undefined || rest.h !== undefined) && f.it.polygons) await outlinePanel.traceText(f.it);
    outlinePanel.render();
    layers.render();
    return aiBuild(`Changed ${f.it.name || id}`);
  },

  remove_item: async ({ id }) => {
    needPart();
    if ((state.model.point_dims || []).some((d) => d.id === id)) { aiSnapshot(); removePointDim(id); return aiBuild('Dimension removed'); }
    const f = findItem(id);
    if (!f) return { text: `No item with id ${id}.`, error: true };
    aiSnapshot();
    f.arr.splice(f.i, 1);
    if (f.key === 'layers') layers.render();
    outlinePanel.selected = null;
    outlinePanel.render();
    return aiBuild(`Removed ${f.it.name || id}`);
  },

  add_dimension: async ({ a, b, axis }) => {
    needPart();
    aiSnapshot();
    const before = new Set((state.model.point_dims || []).map((d) => d.id));
    addPointDim(a, b, axis || 'd');
    const d = (state.model.point_dims || []).find((x) => !before.has(x.id));
    if (!d) return { text: 'No dimension: the points coincide along that direction.', error: true };
    history.flush();
    return { text: `Added ${param(d.id).name} (id ${d.id}) = ${r3(state.values[d.id])} ${state.model.unit}, ${param(d.id).role === 'driving' ? 'set it with set_dimensions to scale the part' : 'reference value'}.` };
  },

  check_print: async ({ printer, split }) => {
    needPart();
    const p = printer || printPanel.selected;
    const res = await (await api('/api/print/plan', { model: state.model, values: state.values, layers: layers.layers, bends: activeBends(),
      printer: p, margin: printPanel.margin, split: !!split, joint: printPanel.jointRequest() })).json();
    const pr = printPanel.printers.find((q) => q.id === p);
    const pieces = (res.pieces || []).map((q) => `piece ${q.index}: ${(q.size_mm || []).map((v) => r3(v)).join(' × ')} mm${q.orientation === 'too big' ? ' (too big!)' : ''}`);
    return { text: JSON.stringify({ printer: pr?.name || p, part_mm: (res.size_mm || []).map(r3), usable_bed_mm: (res.usable_mm || []).map(r3), fits_whole: res.fits,
      pieces: split ? pieces.length : undefined, details: split ? pieces.slice(0, 12) : undefined, issues: (res.issues || []).map((i) => i.message),
      printers: printPanel.printers.map((q) => ({ id: q.id, name: q.name, x: q.x, y: q.y, z: q.z })) }) };
  },

  undo: async () => aiUndo(),
};

async function assemblyScreenshot({ view, fit = true } = {}) {
  if (view) assembly.view.setView({ side: 'right', back: 'front' }[view] || view);
  if (fit !== false) assembly.view.fit?.(); // (all of it in the picture)
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const v = assembly.view;
  v.renderer.render(v.scene, v.camera);
  const src = v.renderer.domElement, k = Math.min(1, 900 / Math.max(src.width, src.height));
  const c = document.createElement('canvas');
  c.width = Math.round(src.width * k);
  c.height = Math.round(src.height * k);
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#161b22';
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.drawImage(src, 0, 0, c.width, c.height);
  return { text: `Assembly view (${view || 'current'}).`, image: c.toDataURL('image/png').split(',')[1] };
}

/** A drawing sheet on screen, as a picture (its SVG drawn on white). */
async function sheetScreenshot() {
  await sheet.ensure();
  const svg = sheet.svgEl ? new XMLSerializer().serializeToString(sheet.svgEl) : null;
  if (!svg) throw new Error('The sheet is not drawn yet.');
  const img = new Image(), url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  await new Promise((ok, bad) => { img.onload = ok; img.onerror = () => bad(new Error('The sheet could not be drawn as a picture.')); img.src = url; });
  const w = 1400, h = Math.round(w * (img.height / img.width || 0.707)), c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(img, 0, 0, w, h);
  URL.revokeObjectURL(url);
  return { text: `Drawing sheet of ${project.current?.name || ''} (rev ${sheet.d?.rev || 1}).`, image: c.toDataURL('image/png').split(',')[1] };
}

// 3D model parts: their own tools; the shared ones (screenshot, export, undo, get_part) follow the part on screen
const MODEL = modelHandlers({ modeler, project, getWorkspace: () => state.workspace });
const SHARED = { get_screenshot: 'model_screenshot', get_body: 'model_body', undo: 'model_undo' };
const ANYWHERE = new Set(['load', 'load_drawing', 'load_solid', 'load_step_assembly', 'ask_user', 'sheet_open', 'get_sheet', 'sheet_edit', 'export_data', 'list_parts', 'open_part', 'duplicate_part', 'new_model', 'new_assembly']);
for (const [name, fn] of Object.entries(agentHandlers)) {
  if (ANYWHERE.has(name)) continue;
  agentHandlers[name] = async (...args) => {
    if (state.workspace === 'sheet' && name === 'get_screenshot') return sheetScreenshot();
    if (state.workspace === 'assembly') {
      if (name === 'get_screenshot') return assemblyScreenshot(...args);
      if (name === 'get_body') return { text: 'ok', body: { assembly: true, step_tree: assembly.stepTree(), name: tabName() } };
      if (name === 'undo') { const ok = await assembly.history.go(-1); return { text: ok ? 'Undone.' : 'Nothing to undo.' }; }
      throw new Error(`${name} is not for assemblies — use get_assembly, insert_part, snap_faces, place_part, or open_part a part.`);
    }
    if (state.workspace === 'model') {
      if (SHARED[name]) return MODEL[SHARED[name]](...args);
      if (name === 'get_part') {
        const r = await MODEL.get_model();
        return { text: `The part on screen is a 3D model (use get_model, find_refs, add_feature …): ${r.text}` };
      }
      throw new Error(`${name} is for quick parts (drawings, pictures, imports) — the part on screen is a 3D model: use add_feature / edit_feature / find_refs, or open_part another part.`);
    }
    return fn(...args);
  };
}
const BOTH = new Set(['check_print']); // a tool of both kinds: on a quick part (a printing copy) the quick part's
for (const [name, fn] of Object.entries(MODEL)) {
  if (SHARED[name] || Object.values(SHARED).includes(name)) continue;
  const quick = BOTH.has(name) ? agentHandlers[name] : null;
  agentHandlers[name] = async (...args) => {
    if (state.workspace === 'assembly' && !ANYWHERE.has(name)) {
      throw new Error(`${name}: an assembly is on screen — open_part the part to change it, or use get_assembly / insert_part / snap_faces / place_part.`);
    }
    if (quick && state.workspace !== 'model') return quick(...args);
    return fn(...args);
  };
}
Object.assign(agentHandlers, assembly.handlers(), {
  new_assembly: async ({ name }) => {
    await project.newAssembly(name || null);
    return { text: `New assembly “${project.current?.name}” (empty). Next: insert_part with a 3D model part (list_parts).` };
  },
});


// autosave: the project kept on the server a few seconds after each change; 🕘 Recent projects; the last one offered
var autosave = new Autosave({
  toast,
  project: () => (project.parts.length ? projectFile() : null),
  partCount: () => project.parts.length, // (only counted: building the file while a part loads would disturb it)
  status: () => $('autosaveState'),
  async restore(raw) {
    const proj = await (await api('/api/project/migrate', raw)).json();
    if (proj.error) throw new Error(proj.error);
    state.projectName = proj.project_name;
    await project.loadAll(proj);
    showProjectName();
  },
  onId: (id) => windows?.connect(id),
});

// OK / Cancel, ✓ Finish sketch, Done: in the bottom-right corner of each view
for (const [vp, right] of [['modelViewport', 'modelRight'], ['asmViewport', 'asmRight'], ['shViewport', 'shRight'], ['dwgViewport', 'dwgRight']]) actionDock($(vp), [$(vp), $(right)]);

// ⧉ a part in a window of its own (another monitor): every window has the project, a change in one goes to the others
var windows = new Windows({
  project, toast,
  live: () => project.hooks.payload(project.current.kind),
  async reloadLive(p) { // changed in another window: shown again here (its undo kept)
    const h = project.hooks.getHistory(p.kind);
    await project.show(p);
    project.hooks.setHistory(h, p.kind);
  },
  async rebuild() { // parts it uses changed in another window
    if (state.workspace === 'assembly') await assembly.refresh();
    else if (state.workspace === 'sheet') await sheet.ensure();
  },
  saveNow: () => autosave.saveNow(),
  gave: (id) => project.close(id), // (a tab of this window taken by another one)
});
windows.connect(autosave.id);
const opened = new URLSearchParams(location.search);
if (opened.has('project')) { // a window opened by ⧉: its project, its part on screen
  autosave.open(opened.get('project')).then(async () => {
    const id = opened.get('part');
    if (id && project.parts.some((p) => p.id === id)) {
      await project.switchTo(id);
      project.showOnly(id); // (only its tab here: the others stay in the project, ☰)
    }
    document.title = `${project.current?.name || ''} — Auto3DModeler`;
  }).catch((e) => toast(e.message, 'error', 8000));
}
$('recentBtn').addEventListener('click', () => { $('openMenuWrap').classList.remove('open'); autosave.showRecent(); });
if (!opened.has('sample') && !opened.has('project')) setTimeout(() => autosave.offerLast(), 600);

// 🕘 the project after each AI turn that ran tools here, kept by the server; loaded back like a project file
const aiHistory = new AiHistory({
  toast,
  project: () => (project.parts.length ? projectFile() : null),
  async restore(raw) {
    const proj = await (await api('/api/project/migrate', raw)).json();
    if (proj.error) throw new Error(proj.error);
    state.projectName = proj.project_name;
    await project.loadAll(proj);
    windows.connect(autosave.id, true); // (the same project, as it was: to its other windows too)
    windows.send();
    showProjectName();
  },
});
let savedCalls = 0;
const chat = new ChatPanel($('tab-ai'), { toast,
  onTurnDone: ({ prompt }) => {
    const n = bridgeStats.calls - savedCalls;
    if (n <= 0) return; // nothing ran here (e.g. the chat's past replayed on a reload)
    savedCalls = bridgeStats.calls;
    aiHistory.save(prompt, n);
  },
  onHistory: () => aiHistory.open(),
  onUndo: () => ({ model: modeler, assembly }[state.workspace]?.history || history).go(-1),
  canUndo: () => ({ model: modeler, assembly }[state.workspace]?.history || history).canUndo() });
window.__chat = chat;
startBridge(agentHandlers);
initSplitters(document.querySelector('main.layout'), $('aiDrawer'));

// 📚 the parts library: a part opens as a new 3D model, or goes into the assembly on screen (the same library part
// once in the project, placed as often as wanted)
const libKey = (d) => (d?.library ? JSON.stringify([d.library.id, d.library.size, d.library.length ?? null]) : null);
const library = new LibraryBrowser({
  toast,
  importSolid: (file) => importSolid(file),
  canInsert: () => state.workspace === 'assembly',
  async openAsModel(name, data) {
    await project.newModel(structuredClone(data), name);
    toast(t2('{name} — a 3D model of its own now (change it, or put it into an assembly).', { name }), 'ok', 5000);
  },
  /** ✎ Edit in the library: the own library part as a 3D model marked as its library edit (📚 Save back keeps it). */
  async editInLibrary(item) {
    const built = buildPart(item);
    const data = { ...structuredClone(built.data), libEdit: { id: item.id, name: item.name } };
    await project.newModel(data, `${item.name} (📚)`);
    toast(t2('{name} — your library part, to change. 📚 Save back to the library keeps the change.', { name: item.name }), 'ok', 6000);
  },
  async insertIntoAssembly(name, data) {
    const same = project.parts.find((p) => p.kind === 'model' && typeof p.data === 'object' && libKey(p.data) === libKey(data));
    const id = same?.id || project.addBackground(name, structuredClone(data));
    await assembly.insert(id);
    toast(t2('{name} is in the assembly — join it with 🔗 Joint.', { name }), 'ok', 5000);
  },
});
$('libBtn').addEventListener('click', () => library.open());

/** 📚 Save back to the library: the 3D model on screen (a library part being changed) becomes that library part again —
 *  its steps, colour, paint; its name, category, maker and part number as they were. -> the saved item. */
async function saveBackToLibrary() {
  const data = modeler.payload(), edit = data.libEdit;
  if (!edit) throw new Error(t('This 3D model is not a library part being changed.'));
  const was = (await libraryItems()).find((it) => it.id === edit.id && it.source === 'user');
  if (!was) throw new Error(t2('“{name}” is not in your library any more — 📚 Save to the library keeps it as a new part.', { name: edit.name }));
  const item = { ...was, features: structuredClone(data.features || []) };
  if (data.color) item.color = data.color; else delete item.color;
  if (data.paint?.length) item.paint = structuredClone(data.paint); else delete item.paint;
  const res = await fetch('/api/library', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item }) });
  const r = await res.json();
  if (!res.ok) throw new Error(r.error || res.statusText);
  toast(t2('“{name}” is saved in your library — new uses take it; parts already in projects stay as they were.', { name: r.name }), 'ok', 6000);
  return r;
}

// the AI and the library: find real parts first, put them in (a 3D model or the assembly on screen)
const libraryTools = {
  library_search: async ({ query = '', category = '' }) => {
    const items = (await libraryItems()).filter((it) => !category || it.category.toLowerCase().includes(String(category).toLowerCase()));
    const found = items.map((it) => ({ it, s: matchScore(it, query) })).filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 12);
    if (!found.length) return { text: `Nothing in the library for “${query}”${category ? ` in ${category}` : ''}. Categories: ${[...new Set(items.map((i) => i.category))].join('; ')}. Draw the part yourself (new_model) if it is not a bought part.` };
    return { text: JSON.stringify(found.map(({ it }) => {
      // the example in the size the query names ("M3 socket" -> M3, "cylinder 16" -> Ø16), else the first
      const sizes = sizesOf(it), words = String(query).toLowerCase().split(/\s+/), plain = (k) => String(k).toLowerCase().replace(/^ø/, '');
      const first = (sizes.find((s) => words.includes(plain(s.key))) || sizes[0])?.key, ls = lengthsOf(it, first), sample = buildPart(it, first, ls?.values[0]);
      return { item: it.id, name: it.name, category: it.category, maker: it.maker || undefined, standard: it.standard || undefined, outline_only: it.approx || undefined,
        sizes: sizes.map((s) => s.key).slice(0, 40), [ls ? (ls.name === 'Stroke' ? 'strokes' : 'lengths') : 'no_length']: ls ? (Array.isArray(it.lengths.values) ? ls.values : `per size, e.g. ${first}: ${ls.values.join(', ')}`) : true,
        example: { size: first, ...(ls ? { length: ls.values[0] } : {}), name: sample.name, pn: sample.data.library.pn, description: sample.data.library.description } };
    })) };
  },
  library_add: async ({ item, size, length, to }) => {
    const items = await libraryItems(), it = items.find((x) => x.id === item) || items.find((x) => x.name.toLowerCase() === String(item || '').toLowerCase());
    if (!it) throw new Error(`No library item “${item}” — library_search first (item = its "item" id).`);
    const sizes = sizesOf(it), key = size === undefined || size === null || size === '' ? sizes[0]?.key : String(size);
    if (!sizes.some((s) => s.key === key)) throw new Error(`${it.name}: size is one of ${sizes.map((s) => s.key).join(', ')}.`);
    const ls = lengthsOf(it, key);
    if (ls && length !== undefined && !ls.values.includes(+length)) throw new Error(`${it.name} ${key}: ${ls.name.toLowerCase()} is one of ${ls.values.join(', ')} mm.`);
    const built = buildPart(it, key, ls ? (length === undefined ? ls.values[0] : +length) : undefined), lib = built.data.library;
    const where = to || (state.workspace === 'assembly' ? 'assembly' : 'model');
    const facts = { name: built.name, pn: lib.pn || undefined, maker: lib.maker || undefined, outline_only: lib.approx || undefined };
    if (where === 'assembly') {
      if (state.workspace !== 'assembly') throw new Error('No assembly on screen — new_assembly or open_part an assembly first (or to: "model").');
      const before = new Set(assembly.doc.instances.map((i) => i.id));
      await library.hooks.insertIntoAssembly(built.name, built.data);
      const placed = assembly.doc.instances.find((i) => !before.has(i.id)), body = assembly.bodies[placed?.part]?.body;
      // its flat and round faces, the lowest first (the bottom it stands on is the first flat one facing down)
      const faces = [...new Map((body?.faces || []).filter((f) => f.type === 'plane' || f.type === 'cylinder').sort((a, b) => a.centroid[2] - b.centroid[2] || b.area - a.area)
        .map((f) => [f.name, { face: f.name, type: f.type === 'plane' ? 'flat' : 'round', ...(f.radius ? { d: +(2 * f.radius).toFixed(3) } : {}), ...(f.normal ? { normal: f.normal.map((v) => +v.toFixed(3)) } : {}), centre: f.centroid.map((v) => +v.toFixed(2)) }])).values()].slice(0, 14);
      const bottom = faces.find((f) => f.type === 'flat' && f.normal?.[2] < -0.9)?.face;
      return { text: JSON.stringify({ placed: placed?.id, part: placed?.part, ...facts, ...(bottom ? { bottom_face: bottom } : {}), faces,
        hint: 'Join it with snap_faces (move = {part: the placed id, face}); its round faces take "axis", bottom_face is the face it stands on (as drawn).' }) };
    }
    await library.hooks.openAsModel(built.name, built.data);
    return { text: JSON.stringify({ ...facts, part: project.current?.id, on_screen: true, hint: 'A 3D model of its own now: get_model / find_refs; insert_part it into an assembly.' }) };
  },
  check_collisions: async () => {
    if (state.workspace !== 'assembly') throw new Error('No assembly on screen.');
    await assembly.refresh();
    const res = await fetch('/api/assembly/clashes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances: assembly.flatParts() }) });
    const r = await res.json();
    if (!res.ok) throw new Error(r.error || res.statusText);
    const name = (id) => `${assembly.partName(assembly.inst(assembly.topOf(id))?.part)} ${id}`;
    return { text: r.clashes.length ? JSON.stringify(r.clashes.map((c) => ({ a: c.a, b: c.b, parts: `${name(c.a)} ↔ ${name(c.b)}`, overlap_mm3: c.volume, overlap_box: c.bbox })))
      : 'No parts overlap (touching faces are fine).' };
  },
};
Object.assign(agentHandlers, libraryTools);
Object.assign(agentHandlers, moreHandlers({ state, project, modeler, assembly, drawing2d, sheet, drawingSet: (aid) => sheet.drawingSet(aid, drawingCtx()), t2 }));

// the AI and the look of parts: the whole part's colour / see-through, single faces; a joined part moved its free ways;
// the model on screen kept in the library
const faceIdsNamed = (faces, names) => {
  const want = new Set(names.map(String));
  return faces.filter((f) => want.has(f.name) || (f.names || []).some((n) => want.has(n) || want.has(String(n).split(':')[0])) || want.has(String(f.name || '').split(':')[0])).map((f) => f.id);
};
const okColor = (c) => { if (c !== null && c !== undefined && !/^#[0-9a-f]{6}$/i.test(String(c))) throw new Error('color is "#rrggbb" (or null).'); return c; };
Object.assign(agentHandlers, {
  set_look: async ({ part, color, opacity, threads }) => {
    okColor(color);
    const op = opacity === undefined || opacity === null ? undefined : Math.min(1, Math.max(0.1, +opacity));
    if (threads !== undefined && state.workspace !== 'model') throw new Error('threads is a 3D model\'s own setting — open_part the model first (its placed parts show it too).');
    if (threads !== undefined && !['hidden', 'cosmetic', 'real', null].includes(threads)) throw new Error('threads is "hidden", "cosmetic" or "real".');
    if (state.workspace === 'assembly') {
      const it = assembly.inst(part);
      if (!it) throw new Error(`part is a placed id (${assembly.doc.instances.map((i) => i.id).join(', ')}) — see get_assembly.`);
      if (color !== undefined) { if (color) it.colour = color; else delete it.colour; }
      if (op !== undefined) it.opacity = op;
      assembly.commit();
      return { text: `${assembly.partName(it.part)} ${it.id}: ${it.colour || 'its own colour'}, ${Math.round((it.opacity ?? 1) * 100)} % solid (in this assembly).` };
    }
    if (state.workspace !== 'model') throw new Error('Open a 3D model or an assembly first.');
    const m = modeler;
    if (color !== undefined) { if (color) m.part.color = color; else delete m.part.color; }
    if (op !== undefined) m.part.opacity = op;
    m.view.setLook(m.part);
    m.history.commit();
    m.renderProps();
    if (threads !== undefined) await m.setThreads(threads || 'hidden');
    const real = m.part.threads === 'real' && m.result?.threads?.real;
    const thr = m.threadHoles().length ? `, ${m.threadHoles().length} threaded hole(s): threads ${m.part.threads || 'hidden'}${real ? (real.issue ? ` — ${real.issue}` : ` (${real.cut} cut in ${real.seconds} s, volume ${+m.result.body.volume.toFixed(3)} mm³${real.warning ? `; ${real.warning}` : ''})`) : ''}` : '';
    return { text: `The model: ${m.part.color || 'the usual colour'}, ${Math.round((m.part.opacity ?? 1) * 100)} % solid${thr}.` };
  },
  paint_faces: async ({ faces = [], color, part }) => {
    okColor(color);
    if (!faces.length) throw new Error('faces: the names of the faces (find_refs / get_model), or a step id for all its faces.');
    if (state.workspace === 'assembly') {
      const it = assembly.inst(part), body = assembly.bodies[it?.part]?.body;
      if (!it || !body) throw new Error('part is a placed id I… of the assembly (get_assembly).');
      const ids = faceIdsNamed(body.faces, faces);
      if (!ids.length) throw new Error(`No face named ${faces.join(', ')} in ${it.id}. Its faces: ${[...new Set(body.faces.map((f) => f.name))].join(', ')}.`);
      const p = repaint(body.faces, it.paint || [], ids, color || null);
      if (p.length) it.paint = p; else delete it.paint;
      assembly.commit();
      return { text: `${ids.length} face(s) of ${it.id} ${color ? `painted ${color}` : 'back to their own colour'} (in this assembly).` };
    }
    if (state.workspace !== 'model' || !modeler.result?.body) throw new Error('Open a 3D model (with a solid) or an assembly first.');
    const m = modeler, body = m.result.body, ids = faceIdsNamed(body.faces, faces);
    if (!ids.length) throw new Error(`No face named ${faces.join(', ')}. The faces: ${[...new Set(body.faces.map((f) => f.name))].join(', ')}.`);
    const p = repaint(body.faces, m.part.paint || [], ids, color || null);
    if (p.length) m.part.paint = p; else delete m.part.paint;
    m.view.setLook(m.part);
    m.history.commit();
    return { text: `${ids.length} face(s) ${color ? `painted ${color}` : 'back to the part\'s colour'}.` };
  },
  move_free: async ({ part, motion = 0, amount, to }) => {
    if (state.workspace !== 'assembly') throw new Error('No assembly on screen.');
    const { it, mo, eng } = assembly.motionFor(part, motion, true), p = eng.motionPos(it.id, mo), lim = eng.limitsOf(it, mo); // (eng: a sub-assembly's, for a part inside it)
    if (!Number.isFinite(+amount) && !Number.isFinite(+to)) throw new Error('amount (mm for a move, degrees for a turn) or to (where along it).');
    let goal = Number.isFinite(+to) && to !== null && to !== undefined ? +to : p + +amount;
    const stopped = lim && (goal < lim.min || goal > lim.max);
    if (lim) goal = Math.max(lim.min, Math.min(lim.max, goal));
    eng.moveFree(it.id, mo, eng.stepTo(mo, p, goal, lim), null, true);
    return { text: `${part} moved: ${mo.label}, now at ${+eng.motionPos(it.id, mo).toFixed(2)} ${mo.kind === 'turn' ? '°' : 'mm'}${stopped ? ` (stopped at its limit ${lim.min} … ${lim.max})` : ''}. ${JSON.stringify(assembly.summary().parts.find((x) => x.id === assembly.topOf(part)))}` };
  },
  save_to_library: async ({ name, category = 'My parts', maker = '', pn = '' }) => {
    if (state.workspace !== 'model' || !modeler.part.features.length) throw new Error('Open the 3D model to keep (it needs steps).');
    if (modeler.part.libEdit && !name) { const r = await saveBackToLibrary(); return { text: `“${r.name}” saved back to the library (item ${r.id}) — the library part being changed; new uses take it.` }; }
    const item = itemFromModel(name || project.current?.name || 'My part', modeler.payload(), { category, maker, pn });
    const res = await fetch('/api/library', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item }) });
    const r = await res.json();
    if (!res.ok) throw new Error(r.error || res.statusText);
    return { text: `“${r.name}” is in the library (item ${r.id}, ${r.category}) — library_add {item: "${r.id}"} puts it in.` };
  },
});

window.__app = { state, viewer, layers, printPanel, dimTool, bends, outlinePanel, wizard, chat, aiHistory, library, autosave, windows, agentHandlers, featureAt, history, modeler, project, assembly, drawing2d, sheet };
