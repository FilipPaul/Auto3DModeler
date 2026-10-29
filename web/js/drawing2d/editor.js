// The 2D drawing workspace: a DXF / DWG as it is — its layers (show / hide, colour, the one new lines go on), every
// line, circle, arc, polyline and text in real mm — to look at, measure and touch up (select, delete, draw lines and
// circles, snapping to ends, middles and centres). What to make of it is chosen later: Use ▾ as a sketch of a new 3D
// model, or as a quick part (its closed outlines). Drawing JSON: see auto3d/drawing2d.py.
import { History } from '../history.js';
import { t } from '../i18n.js';
import { choose } from '../choose.js';
import { showSuggest } from '../suggest.js';
import { drawingSuggest } from './drawsuggest.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const TAU = Math.PI * 2, rad = (d) => (d * Math.PI) / 180;
const SNAP_PX = 10, HIT_PX = 6;
const UNIT_MM = { mm: 1, cm: 10, m: 1000, in: 25.4 }; // what one unit of the file is, in mm
const SHAPES = { line: 'Line', circle: 'Circle', arc: 'Arc', poly: 'Polyline', text: 'Text' };

/** A shape's length: a line's, a polyline's all along, an arc's along its curve, a circle's round (mm). */
const lengthOf = (e) => {
  if (e.t === 'line') return Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]);
  if (e.t === 'circle') return TAU * e.r;
  if (e.t === 'arc') return sweepOf(e) * e.r;
  if (e.t === 'poly') { const q = e.closed ? [...e.pts, e.pts[0]] : e.pts; let L = 0; for (let i = 0; i + 1 < q.length; i++) L += Math.hypot(q[i + 1][0] - q[i][0], q[i + 1][1] - q[i][1]); return L; }
  return null;
};

/** What a filter can look at: enum (a choice), num (mm), str (text). */
const FIELDS = {
  shape: { label: 'Shape', kind: 'enum', get: (e) => e.t },
  layer: { label: 'Layer', kind: 'enum', get: (e) => e.layer },
  dia: { label: 'Ø', kind: 'num', get: (e) => (e.t === 'circle' || e.t === 'arc' ? 2 * e.r : null) },
  r: { label: 'Radius', kind: 'num', get: (e) => (e.t === 'circle' || e.t === 'arc' ? e.r : null) },
  len: { label: 'Length', kind: 'num', get: lengthOf },
  w: { label: 'Width', kind: 'num', get: (e) => (e.w ? e.w : null) }, // a trace's width (Gerber / ODB++)
  color: { label: 'Colour', kind: 'enum', get: null }, // (the colour it is drawn in: set by the editor)
  text: { label: 'Text', kind: 'str', get: (e) => (e.t === 'text' ? String(e.text) : null) },
};
const OPS = { enum: ['is', 'is not', 'is any of'], num: ['=', '≠', '<', '>', '≤', '≥'], str: ['contains', 'is'] };
const sameNum = (a, b) => Math.abs(a - b) <= 0.0005 + Math.abs(b) * 1e-9;
const passes = (v, op, want, kind) => {
  if (v === null || v === undefined) return false;
  if (kind === 'num') {
    const w = parseFloat(String(want).replace(',', '.'));
    if (!Number.isFinite(w)) return true; // no value typed yet: it does not narrow
    return { '=': sameNum(v, w), '≠': !sameNum(v, w), '<': v < w && !sameNum(v, w), '>': v > w && !sameNum(v, w), '≤': v <= w || sameNum(v, w), '≥': v >= w || sameNum(v, w) }[op];
  }
  if (kind === 'str') return op === 'is' ? v === want : v.toLowerCase().includes(String(want || '').toLowerCase());
  if (op === 'is any of') return [].concat(want ?? []).includes(v);
  return op === 'is not' ? v !== want : v === want;
};

/** An arc's sweep from a0 to a1 (degrees, counter-clockwise) in radians, > 0. */
const sweepOf = (e) => { let s = rad(e.a1 - e.a0) % TAU; if (s <= 1e-12) s += TAU; return s; };
/** Is point p inside polygon pts (even-odd)? */
const inside = (p, pts) => {
  let c = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    if ((pts[i][1] > p[1]) !== (pts[j][1] > p[1]) && p[0] < ((pts[j][0] - pts[i][0]) * (p[1] - pts[i][1])) / (pts[j][1] - pts[i][1]) + pts[i][0]) c = !c;
  }
  return c;
};
const segDist = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
  const k = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L));
  return Math.hypot(a[0] + k * dx - p[0], a[1] + k * dy - p[1]);
};

export class DrawingEditor {
  /** els: {left, viewport, right}; hooks: {toast, onChange, useAsSketch(drawing), useAsQuick(drawing)} */
  constructor(els, hooks) {
    this.els = els;
    this.hooks = hooks;
    this.d = { entities: [], layers: [] };
    this.tool = 'select';
    this.sel = new Set();
    this.rev = 0; // the drawing's revision: the caches (batches, the grid) are kept for one
    this.filters = []; // 🔍 [{field, op, value}] — all of them must hold
    this.layerSel = new Set(); // layers picked in the list (Ctrl / Shift + click: several)
    this.view = { cx: 0, cy: 0, k: 4 };
    this.history = new History({
      capture: () => ({ entities: this.d.entities, layers: this.d.layers, units: this.d.file_units }),
      restore: (s) => {
        const rescaled = (this.d.file_units || 'mm') !== (s.units || 'mm');
        Object.assign(this.d, { entities: s.entities, layers: s.layers, file_units: s.units });
        this.rev = (this.rev || 0) + 1;
        this.sel.clear();
        this.renderPanels();
        if (rescaled) this.fit(); else this.draw();
      },
      onChange: () => this.updateUndo(),
    });
    this.build();
    this.bind();
    window.addEventListener('a3d:lang', () => this.renderPanels()); // (texts built with t(): in the new language)
  }

  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = '<div class="mt-head"><b>Layers</b><span class="mt-sub">click 👁 to show / hide</span></div><div class="dw-layers"></div>';
    viewport.innerHTML = `<div class="m-cmdbar dw-bar"></div><div class="m-hint" hidden></div><canvas class="dw-canvas"></canvas>
      <div class="dw-measure" hidden></div><div class="m-status dw-status"></div>`;
    right.innerHTML = '<div class="mp-body"></div>';
    this.cv = viewport.querySelector('canvas');
    this.ctx = this.cv.getContext('2d');
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
    new ResizeObserver(() => this.resize()).observe(viewport);
  }

  // ------------------------------------------------------------------ the drawing as a project part
  load(data) {
    this.d = structuredClone(data || { entities: [], layers: [] });
    this.rev = (this.rev || 0) + 1;
    this.d.entities = this.d.entities || [];
    this.d.layers = this.d.layers || [];
    if (!this.d.layers.length) this.d.layers.push({ name: '0', color: '#ffffff', visible: true });
    this.d.active = this.d.layers.some((l) => l.name === this.d.active) ? this.d.active : this.d.layers[0].name;
    this.tool = 'select';
    this.sel.clear();
    this.pending = null;
    this.measure = null;
    this.history.reset();
    this.resize();
    this.fit();
    this.renderPanels();
    // a file that does not say its units and comes out tiny is most likely in inches (PCB tools)
    const b = this.bbox();
    if (b && !this.d.units_declared && !this.d.units_checked && Math.max(b[2] - b[0], b[3] - b[1]) < 5) {
      this.hooks.toast(t('The file does not say its units and is only a few mm big — if it is in inches, set File units to inch (in the panel).'), 'info', 9000);
    }
    this.d.units_checked = true;
  }

  payload() { return structuredClone(this.d); }
  layer(name) { return this.d.layers.find((l) => l.name === name); }
  shown(e) { return this.layer(e.layer)?.visible !== false; }
  commit() { this.rev = (this.rev || 0) + 1; this.history.commit(); this.renderPanels(); this.draw(); this.hooks.onChange?.(); }
  newId() {
    let n = this.d.entities.length;
    const used = new Set(this.d.entities.map((e) => e.id));
    while (used.has(`e${++n}`));
    return `e${n}`;
  }

  // ------------------------------------------------------------------ view: mm <-> screen
  resize() {
    const r = this.cv.parentElement.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    this.w = Math.max(1, r.width);
    this.h = Math.max(1, r.height);
    this.cv.width = this.w * dpr;
    this.cv.height = this.h * dpr;
    Object.assign(this.cv.style, { width: `${this.w}px`, height: `${this.h}px` });
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.draw();
  }

  toScreen([x, y]) { return [(x - this.view.cx) * this.view.k + this.w / 2, this.h / 2 - (y - this.view.cy) * this.view.k]; }
  toWorld(sx, sy) { return [(sx - this.w / 2) / this.view.k + this.view.cx, (this.h / 2 - sy) / this.view.k + this.view.cy]; }

  /** The box of the shown entities (mm): [x0, y0, x1, y1] or null. */
  bbox(list = this.d.entities.filter((e) => this.shown(e))) {
    let b = null;
    const add = (x, y) => { b = b ? [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)] : [x, y, x, y]; };
    for (const e of list) {
      if (e.t === 'line') { add(...e.a); add(...e.b); } else if (e.t === 'circle') { add(e.c[0] - e.r, e.c[1] - e.r); add(e.c[0] + e.r, e.c[1] + e.r); }
      else if (e.t === 'arc') { const a0 = rad(e.a0), sw = sweepOf(e); for (let i = 0; i <= 32; i++) { const a = a0 + (sw * i) / 32; add(e.c[0] + e.r * Math.cos(a), e.c[1] + e.r * Math.sin(a)); } } else if (e.t === 'poly') for (const p of e.pts) add(...p);
      else if (e.t === 'text') { add(...e.at); add(e.at[0] + e.h * 0.6 * String(e.text).length, e.at[1] + e.h); }
    }
    return b;
  }

  fit() {
    const b = this.bbox();
    if (!b) { this.view = { cx: 0, cy: 0, k: 4 }; this.draw(); return; }
    const w = Math.max(b[2] - b[0], 1e-3), h = Math.max(b[3] - b[1], 1e-3);
    this.view = { cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2, k: Math.min((this.w - 60) / w, (this.h - 90) / h) };
    this.draw();
  }

  // ------------------------------------------------------------------ drawing
  colourOf(e) {
    const c = e.color || this.layer(e.layer)?.color || '#ffffff';
    return /^#0{6}$/i.test(c) ? '#c9d1d9' : c; // black lines would vanish on the dark sheet
  }

  draw() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = null; this.paint(); });
  }

  paint() {
    const c = this.ctx, k = this.view.k;
    c.clearRect(0, 0, this.w, this.h);
    c.fillStyle = '#0e1115';
    c.fillRect(0, 0, this.w, this.h);
    // a light grid: 1, 10, 100 … mm, whatever is ~ 20 px or more
    const step = 10 ** Math.ceil(Math.log10(20 / k));
    const [x0, y1] = this.toWorld(0, 0), [x1, y0] = this.toWorld(this.w, this.h);
    c.strokeStyle = '#1b222c';
    c.lineWidth = 1;
    c.beginPath();
    for (let x = Math.floor(x0 / step) * step; x <= x1; x += step) { const [sx] = this.toScreen([x, 0]); c.moveTo(sx, 0); c.lineTo(sx, this.h); }
    for (let y = Math.floor(y0 / step) * step; y <= y1; y += step) { const [, sy] = this.toScreen([0, y]); c.moveTo(0, sy); c.lineTo(this.w, sy); }
    c.stroke();
    const path = (e) => {
      c.beginPath();
      if (e.t === 'line') { c.moveTo(...this.toScreen(e.a)); c.lineTo(...this.toScreen(e.b)); } else if (e.t === 'circle') { const [sx, sy] = this.toScreen(e.c); c.arc(sx, sy, e.r * k, 0, TAU); } else if (e.t === 'arc') { const [sx, sy] = this.toScreen(e.c); c.arc(sx, sy, e.r * k, -rad(e.a0), -rad(e.a0) - sweepOf(e), true); } else if (e.t === 'poly') {
        e.pts.forEach((p, i) => (i ? c.lineTo(...this.toScreen(p)) : c.moveTo(...this.toScreen(p))));
        if (e.closed) c.closePath();
      }
    };
    // everything, batched: one path per layer and look, drawn in mm (half a million shapes stay quick)
    const dpr = window.devicePixelRatio || 1;
    c.save();
    c.setTransform(dpr * k, 0, 0, -dpr * k, dpr * (this.w / 2 - this.view.cx * k), dpr * (this.h / 2 + this.view.cy * k));
    c.lineCap = c.lineJoin = 'round';
    for (const g of this.batches()) {
      if (this.layer(g.layer)?.visible === false) continue;
      const col = g.clear ? '#0e1115' : this.colourOf({ layer: g.layer, color: g.color });
      if (g.fill) { c.fillStyle = col; c.fill(g.path); } else { c.strokeStyle = col; c.lineWidth = g.w || 1 / k; c.stroke(g.path); }
    }
    c.restore();
    const special = [...this.sel, ...(this.matchSet || []), ...(this.hover ? [this.hover] : [])];
    const byId = this.byId(), texts = this.texts();
    for (const e of [...texts, ...special.map((id) => byId.get(id)).filter(Boolean)]) {
      if (!this.shown(e)) continue;
      const on = this.sel.has(e.id), hov = this.hover === e.id, hit = !on && this.matchSet?.has(e.id);
      if (e.t !== 'text' && !on && !hov && !hit) continue;
      c.strokeStyle = on ? '#f2cc60' : hov ? '#6cb6ff' : hit ? '#39d0d8' : e.clear ? '#0e1115' : this.colourOf(e);
      c.fillStyle = c.strokeStyle;
      c.lineWidth = e.w ? Math.max(1, e.w * k) : on || hov || hit ? 2 : 1; // a trace: as wide as it is
      c.lineCap = c.lineJoin = 'round';
      if (e.t === 'text') {
        c.save();
        const [sx, sy] = this.toScreen(e.at);
        c.translate(sx, sy);
        c.rotate(-rad(e.rot || 0));
        c.font = `${Math.max(1, e.h * k)}px sans-serif`;
        c.fillText(e.text, 0, 0);
        c.restore();
        continue;
      }
      path(e);
      if (e.fill) { c.fill(); if (on || hov || hit) { c.lineWidth = 2; c.stroke(); } } else c.stroke();
    }
    // the shape being drawn, the measure, the snap point
    const live = this.pending && this.cursor ? this.pendingShape() : null;
    if (live) { c.strokeStyle = '#7ee787'; c.lineWidth = 1.5; c.setLineDash([5, 4]); path(live); c.stroke(); c.setLineDash([]); }
    if (this.measure?.a) {
      const b = this.measure.b || this.cursor?.p;
      if (b) {
        c.strokeStyle = '#f2cc60';
        c.lineWidth = 1.5;
        c.beginPath(); c.moveTo(...this.toScreen(this.measure.a)); c.lineTo(...this.toScreen(b)); c.stroke();
      }
    }
    if (this.cursor?.snap) {
      const [sx, sy] = this.toScreen(this.cursor.p);
      c.strokeStyle = '#7ee787';
      c.lineWidth = 2;
      c.strokeRect(sx - 5, sy - 5, 10, 10);
    }
  }

  /** The shapes as batches: [{layer, fill, clear, w, color, path (Path2D in mm)}], the list's top layer last; kept for
   *  this revision of the drawing. */
  batches() {
    if (this._bat && this._bat.rev === this.rev && this._bat.n === this.d.entities.length) return this._bat.list;
    const rank = new Map(this.d.layers.map((l, i) => [l.name, i])), groups = new Map();
    for (const e of this.d.entities) {
      if (e.t === 'text') continue;
      const fill = !!e.fill, key = `${e.layer}\u0001${fill}\u0001${e.clear ? 1 : 0}\u0001${fill ? 0 : e.w || 0}\u0001${e.color || ''}`;
      let g = groups.get(key);
      if (!g) groups.set(key, (g = { layer: e.layer, rank: rank.get(e.layer) ?? 0, fill, clear: !!e.clear, w: fill ? 0 : e.w || 0, color: e.color || null, path: new Path2D() }));
      const P = g.path;
      if (e.t === 'line') { P.moveTo(e.a[0], e.a[1]); P.lineTo(e.b[0], e.b[1]); } else if (e.t === 'circle') { P.moveTo(e.c[0] + e.r, e.c[1]); P.arc(e.c[0], e.c[1], e.r, 0, TAU); } else if (e.t === 'arc') {
        const a0 = rad(e.a0), sw = sweepOf(e);
        P.moveTo(e.c[0] + e.r * Math.cos(a0), e.c[1] + e.r * Math.sin(a0));
        P.arc(e.c[0], e.c[1], e.r, a0, a0 + sw, false);
      } else if (e.t === 'poly' && e.pts.length) {
        P.moveTo(e.pts[0][0], e.pts[0][1]);
        for (let i = 1; i < e.pts.length; i++) P.lineTo(e.pts[i][0], e.pts[i][1]);
        if (e.closed) P.closePath();
      }
    }
    // a layer's clear (cut-out) parts after its others
    const list = [...groups.values()].sort((a, b) => a.rank - b.rank || a.clear - b.clear);
    this._bat = { rev: this.rev, n: this.d.entities.length, list };
    return list;
  }

  byId() {
    if (!this._ids || this._ids.rev !== this.rev || this._ids.n !== this.d.entities.length) this._ids = { rev: this.rev, n: this.d.entities.length, map: new Map(this.d.entities.map((e) => [e.id, e])) };
    return this._ids.map;
  }

  texts() {
    if (!this._txt || this._txt.rev !== this.rev || this._txt.n !== this.d.entities.length) this._txt = { rev: this.rev, n: this.d.entities.length, list: this.d.entities.filter((e) => e.t === 'text') };
    return this._txt.list;
  }

  /** A grid over the drawing: which shapes are near a point (picking and snapping look only there). */
  near(p, reach) {
    if (!this._grid || this._grid.rev !== this.rev || this._grid.n !== this.d.entities.length) {
      const b = this.bbox(this.d.entities) || [0, 0, 1, 1], size = Math.max(b[2] - b[0], b[3] - b[1], 1e-3);
      const cell = size / 256, cells = new Map(), big = [];
      const boxOf = (e) => {
        const h = (e.w || 0) / 2;
        if (e.t === 'line') return [Math.min(e.a[0], e.b[0]) - h, Math.min(e.a[1], e.b[1]) - h, Math.max(e.a[0], e.b[0]) + h, Math.max(e.a[1], e.b[1]) + h];
        if (e.t === 'circle' || e.t === 'arc') return [e.c[0] - e.r - h, e.c[1] - e.r - h, e.c[0] + e.r + h, e.c[1] + e.r + h];
        if (e.t === 'text') return [e.at[0], e.at[1], e.at[0] + e.h * 0.6 * String(e.text).length, e.at[1] + e.h];
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const q of e.pts || []) { x0 = Math.min(x0, q[0]); y0 = Math.min(y0, q[1]); x1 = Math.max(x1, q[0]); y1 = Math.max(y1, q[1]); }
        return [x0 - h, y0 - h, x1 + h, y1 + h];
      };
      for (const e of this.d.entities) {
        const q = boxOf(e), i0 = Math.floor((q[0] - b[0]) / cell), i1 = Math.floor((q[2] - b[0]) / cell), j0 = Math.floor((q[1] - b[1]) / cell), j1 = Math.floor((q[3] - b[1]) / cell);
        if ((i1 - i0 + 1) * (j1 - j0 + 1) > 256) { big.push(e); continue; } // a long one (an outline): always looked at
        for (let i = i0; i <= i1; i++) for (let j = j0; j <= j1; j++) { const kk = i * 100003 + j; (cells.get(kk) || cells.set(kk, []).get(kk)).push(e); }
      }
      this._grid = { rev: this.rev, n: this.d.entities.length, b, cell, cells, big };
    }
    const g = this._grid, out = new Set(g.big);
    const i0 = Math.floor((p[0] - reach - g.b[0]) / g.cell), i1 = Math.floor((p[0] + reach - g.b[0]) / g.cell);
    const j0 = Math.floor((p[1] - reach - g.b[1]) / g.cell), j1 = Math.floor((p[1] + reach - g.b[1]) / g.cell);
    if ((i1 - i0 + 1) * (j1 - j0 + 1) > 40000) return this.d.entities; // zoomed far out: all of them
    for (let i = i0; i <= i1; i++) for (let j = j0; j <= j1; j++) for (const e of g.cells.get(i * 100003 + j) || []) out.add(e);
    return out;
  }

  /** The entities in the order of their layers (the list's top drawn last, on top), kept until the entities change. */
  ordered() {
    const key = this.d.entities, lk = this.d.layers.map((l) => l.name).join('\u0001');
    if (this._ord?.key === key && this._ord.lk === lk) return this._ord.list;
    const rank = new Map(this.d.layers.map((l, i) => [l.name, i]));
    const list = [...this.d.entities].sort((a, b) => (rank.get(a.layer) ?? 0) - (rank.get(b.layer) ?? 0));
    this._ord = { key, lk, list };
    return list;
  }

  // ------------------------------------------------------------------ picking, snapping
  /** The spot under the mouse: an end, a middle or a centre within reach, else the plain point. */
  snapAt(sx, sy) {
    const p = this.toWorld(sx, sy), tol = SNAP_PX / this.view.k;
    let best = null;
    const near = (q, kind) => { const d = Math.hypot(q[0] - p[0], q[1] - p[1]); if (d < tol && (!best || d < best.d)) best = { d, p: q, snap: kind }; };
    for (const e of this.near(p, tol)) {
      if (!this.shown(e)) continue;
      if (e.t === 'line') { near(e.a, 'end'); near(e.b, 'end'); near([(e.a[0] + e.b[0]) / 2, (e.a[1] + e.b[1]) / 2], 'middle'); } else if (e.t === 'circle') near(e.c, 'centre');
      else if (e.t === 'arc') { near(e.c, 'centre'); for (const a of [rad(e.a0), rad(e.a0) + sweepOf(e)]) near([e.c[0] + e.r * Math.cos(a), e.c[1] + e.r * Math.sin(a)], 'end'); } else if (e.t === 'poly') {
        if (e.fill && e.pts.length <= 64) near([e.pts.reduce((s, q) => s + q[0], 0) / e.pts.length, e.pts.reduce((s, q) => s + q[1], 0) / e.pts.length], 'centre'); // a pad
        else for (const q of e.pts) near(q, 'end');
      }
    }
    return best ? { p: [...best.p], snap: best.snap } : { p };
  }

  /** The entity under the mouse (its id) or null. */
  hitAt(sx, sy) {
    const p = this.toWorld(sx, sy), tol = HIT_PX / this.view.k;
    let best = null;
    const consider = (e, d) => { if (d < tol && (!best || d < best.d)) best = { d, id: e.id }; };
    for (const e of this.near(p, tol)) {
      if (!this.shown(e)) continue;
      const half = (e.w || 0) / 2;
      if (e.t === 'line') consider(e, Math.max(0, segDist(p, e.a, e.b) - half));
      else if (e.t === 'circle') { const dc = Math.hypot(p[0] - e.c[0], p[1] - e.c[1]); consider(e, e.fill && dc <= e.r ? 0 : Math.max(0, Math.abs(dc - e.r) - half)); }
      else if (e.t === 'arc') {
        const a = (Math.atan2(p[1] - e.c[1], p[0] - e.c[0]) - rad(e.a0) + 2 * TAU) % TAU;
        if (a <= sweepOf(e)) consider(e, Math.abs(Math.hypot(p[0] - e.c[0], p[1] - e.c[1]) - e.r));
      } else if (e.t === 'poly') {
        const q = e.closed ? [...e.pts, e.pts[0]] : e.pts;
        if (e.fill && inside(p, e.pts)) consider(e, 0);
        for (let i = 0; i + 1 < q.length; i++) consider(e, Math.max(0, segDist(p, q[i], q[i + 1]) - half));
      } else if (e.t === 'text') {
        const w = e.h * 0.6 * String(e.text).length;
        if (p[0] >= e.at[0] && p[0] <= e.at[0] + w && p[1] >= e.at[1] && p[1] <= e.at[1] + e.h) consider(e, 0);
      }
    }
    return best?.id || null;
  }

  // ------------------------------------------------------------------ the mouse and the keys
  bind() {
    const cv = this.cv;
    let pan = null;
    cv.addEventListener('contextmenu', (e) => e.preventDefault());
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = cv.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top, before = this.toWorld(sx, sy);
      this.view.k *= Math.exp(-e.deltaY * 0.0015);
      const after = this.toWorld(sx, sy);
      this.view.cx += before[0] - after[0];
      this.view.cy += before[1] - after[1];
      this.draw();
    }, { passive: false });
    cv.addEventListener('pointerdown', (e) => {
      const r = cv.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
      // pan: the right / middle button, or the left one on empty paper with Select
      if (e.button !== 0 || (this.tool === 'select' && !this.hitAt(sx, sy))) { pan = { x: e.clientX, y: e.clientY, cx: this.view.cx, cy: this.view.cy, moved: false, button: e.button, sx, sy, add: e.ctrlKey || e.shiftKey }; cv.setPointerCapture(e.pointerId); }
    });
    cv.addEventListener('pointermove', (e) => {
      const r = cv.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
      if (pan) {
        const dx = e.clientX - pan.x, dy = e.clientY - pan.y;
        if (Math.hypot(dx, dy) > 3) pan.moved = true;
        this.view.cx = pan.cx - dx / this.view.k;
        this.view.cy = pan.cy + dy / this.view.k;
        this.draw();
        return;
      }
      this.cursor = this.tool === 'select' ? null : this.snapAt(sx, sy);
      const hv = this.tool === 'select' ? this.hitAt(sx, sy) : null;
      if (hv !== this.hover) this.hover = hv;
      cv.style.cursor = this.tool === 'select' ? (hv ? 'pointer' : 'grab') : 'crosshair';
      const p = this.cursor?.p || this.toWorld(sx, sy);
      this.$('.dw-status').textContent = `x ${fmt(p[0])}  y ${fmt(p[1])} mm${this.cursor?.snap ? `  · ${t(this.cursor.snap)}` : ''}`;
      this.draw();
    });
    cv.addEventListener('pointerup', (e) => {
      const r = cv.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
      if (pan) {
        const was = pan;
        pan = null;
        if (!was.moved && was.button === 0) { if (!was.add) this.sel.clear(); this.renderPanels(); this.draw(); } // a click on empty paper
        return;
      }
      if (e.button !== 0) return;
      this.click(sx, sy, e);
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')) { e.preventDefault(); this.history.go(k === 'y' || e.shiftKey ? 1 : -1); return; }
    if (e.key === 'Escape' && this.picking) { this.picking = false; this.hint(''); this.renderProps(); return; }
    if (e.key === 'Escape' && this.tool === 'select' && this.sel.size && !this.pending) { this.sel.clear(); this.renderProps(); this.draw(); return; }
    if (e.key === 'Escape') { if (this.pending || this.measure) { this.pending = null; this.measure = null; this.$('.dw-measure').hidden = true; this.draw(); } else this.setTool('select'); return; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel.size) { this.removeSel(); return; }
    if (e.ctrlKey || e.metaKey) return;
    if (k === 'l') this.setTool('line');
    if (k === 'c') this.setTool('circle');
    if (k === 'm') this.setTool('measure');
    if (k === 'f') this.fit();
  }

  setTool(tool) {
    this.tool = tool;
    this.pending = null;
    this.measure = null;
    this.$('.dw-measure').hidden = true;
    this.hint({ line: 'Line: click where it starts, then where it ends (it goes on from there; Esc = stop).', circle: 'Circle: click the centre, then a point on it.',
      measure: 'Measure: click two spots (ends, middles and centres snap) — or a circle for its Ø.', select: '' }[tool] || '');
    this.renderBar();
    this.renderSuggest();
    this.draw();
  }

  /** The suggestions table (bottom left of the view) for the chosen shapes — or the drawing's next steps. */
  renderSuggest() {
    const s = drawingSuggest(this);
    showSuggest(this.els.viewport, s?.title || '', s?.items || [], s?.hint || '', s?.refs || '');
  }

  hint(text) { const h = this.$('.m-hint'); h.hidden = !text; h.textContent = t(text); }

  click(sx, sy, e) {
    if (this.picking) { // 💧 the filters from the shape clicked
      const id = this.hitAt(sx, sy), hit = id && this.d.entities.find((x) => x.id === id);
      if (!hit) { this.hooks.toast?.(t('Click right on a shape.'), 'info', 2500); return; }
      this.picking = false;
      this.hint('');
      this.likeThis(hit, false);
      this.hooks.toast?.(tv('{n} shapes like it — Select them, or remove a filter to find more.', { n: this.matchSet.size }), 'ok', 4000);
      return;
    }
    if (this.tool === 'select') {
      const id = this.hitAt(sx, sy);
      if (e.ctrlKey || e.shiftKey) { if (id) (this.sel.has(id) ? this.sel.delete(id) : this.sel.add(id)); } else this.sel = new Set(id ? [id] : []);
      this.renderPanels();
      this.draw();
      return;
    }
    const s = this.snapAt(sx, sy);
    if (this.tool === 'measure') return this.measureClick(s, sx, sy);
    if (!this.pending) { this.pending = { a: s.p }; this.draw(); return; }
    const sh = this.pendingShape(s);
    if (sh && (sh.t !== 'circle' || sh.r > 1e-9) && (sh.t !== 'line' || Math.hypot(sh.b[0] - sh.a[0], sh.b[1] - sh.a[1]) > 1e-9)) {
      this.d.entities = [...this.d.entities, { id: this.newId(), layer: this.d.active, ...sh }];
      this.commit();
    }
    this.pending = this.tool === 'line' ? { a: s.p } : null; // a line goes on from its end
  }

  pendingShape(s = this.cursor) {
    if (!this.pending || !s) return null;
    const a = this.pending.a, b = s.p;
    if (this.tool === 'line') return { t: 'line', a: a.map((v) => +v.toFixed(6)), b: b.map((v) => +v.toFixed(6)) };
    if (this.tool === 'circle') return { t: 'circle', c: a.map((v) => +v.toFixed(6)), r: +Math.hypot(b[0] - a[0], b[1] - a[1]).toFixed(6) };
    return null;
  }

  measureClick(s, sx, sy) {
    const box = this.$('.dw-measure');
    if (!this.measure?.a || this.measure.b) {
      // a click right on a circle / arc (no point to snap to): its size
      const id = !s.snap ? this.hitAt(sx, sy) : null, e = id ? this.d.entities.find((x) => x.id === id) : null;
      if (e && (e.t === 'circle' || e.t === 'arc')) {
        box.hidden = false;
        box.innerHTML = `<b>${e.t === 'circle' ? t('Circle') : t('Arc')}</b> Ø ${fmt(2 * e.r)} mm · R ${fmt(e.r)} · ${t('centre')} ${fmt(e.c[0])}, ${fmt(e.c[1])}`;
        this.measure = null;
        return;
      }
      this.measure = { a: s.p };
      box.hidden = false;
      box.innerHTML = `${t('From')} ${fmt(s.p[0])}, ${fmt(s.p[1])} — ${t('click the second spot.')}`;
      this.draw();
      return;
    }
    this.measure.b = s.p;
    const [a, b] = [this.measure.a, s.p];
    box.innerHTML = `<b>${fmt(Math.hypot(b[0] - a[0], b[1] - a[1]))} mm</b> · Δx ${fmt(Math.abs(b[0] - a[0]))} · Δy ${fmt(Math.abs(b[1] - a[1]))} · ${fmt((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI)}°`;
    this.draw();
  }

  /** The file's units were not what it was read as: rescale everything (one file unit = UNIT_MM[u] mm). */
  setUnits(u) {
    const f = UNIT_MM[u] / UNIT_MM[this.d.file_units || 'mm'];
    if (!f || f === 1) return;
    const P = (p) => p.map((v) => +(v * f).toFixed(6));
    this.d.entities = this.d.entities.map((e) => ({ ...e, ...(e.a ? { a: P(e.a) } : {}), ...(e.b ? { b: P(e.b) } : {}), ...(e.c ? { c: P(e.c) } : {}),
      ...(e.r ? { r: +(e.r * f).toFixed(6) } : {}), ...(e.pts ? { pts: e.pts.map(P) } : {}), ...(e.at ? { at: P(e.at) } : {}), ...(e.h ? { h: +(e.h * f).toFixed(4) } : {}) }));
    this.d.file_units = u;
    this.commit();
    this.fit();
  }

  // ------------------------------------------------------------------ 🔍 select by filter
  fieldValue(field, e) { return field === 'color' ? this.colourOf(e) : FIELDS[field].get(e); }

  /** The shapes (shown) every filter holds for. */
  matches() {
    const fs = this.filters.filter((f) => FIELDS[f.field]);
    if (!fs.length) return [];
    return this.d.entities.filter((e) => this.shown(e) && fs.every((f) => passes(this.fieldValue(f.field, e), f.op, f.value, FIELDS[f.field].kind)));
  }

  /** The choices for an enum field (the drawing's layers, the shapes and colours it has). */
  choices(field) {
    if (field === 'layer') return this.d.layers.map((l) => [l.name, l.name]);
    if (field === 'shape') return Object.entries(SHAPES).filter(([k]) => this.d.entities.some((e) => e.t === k)).map(([k, v]) => [k, t(v)]);
    if (field === 'color') return [...new Set(this.d.entities.map((e) => this.colourOf(e)))].map((c) => [c, c]);
    return [];
  }

  filterHtml() {
    const rows = this.filters.map((f, i) => {
      const F = FIELDS[f.field], ops = OPS[F.kind];
      const many = f.op === 'is any of', vals = [].concat(f.value ?? []);
      const val = F.kind === 'enum'
        ? `<select data-fv="${i}" ${many ? `multiple size="${Math.min(5, Math.max(2, this.choices(f.field).length))}"` : ''}>${this.choices(f.field).map(([v, label]) => `<option value="${esc(v)}" ${(many ? vals.includes(v) : v === f.value) ? 'selected' : ''} data-no-i18n>${esc(label)}</option>`).join('')}</select>`
        : `<input data-fv="${i}" type="${F.kind === 'num' ? 'text' : 'text'}" inputmode="${F.kind === 'num' ? 'decimal' : 'text'}" value="${esc(f.value ?? '')}" placeholder="${F.kind === 'num' ? 'mm' : ''}">`;
      return `<div class="dw-filter"><select data-ff="${i}">${Object.entries(FIELDS).map(([k, x]) => `<option value="${k}" ${k === f.field ? 'selected' : ''}>${esc(t(x.label))}</option>`).join('')}</select>
        <select data-fo="${i}">${ops.map((o) => `<option ${o === f.op ? 'selected' : ''}>${esc(t(o))}</option>`).join('')}</select>${val}
        <button class="mini danger" data-fx="${i}" title="${esc(t('Remove this filter'))}">✕</button></div>`;
    }).join('');
    const n = this.filters.length ? this.matches().length : null;
    return `<h3>🔍 ${esc(t('Select by filter'))}</h3>${rows}
      <div class="row-actions wrap"><button class="btn small" data-a="addFilter" title="${esc(t('Add a filter: all of them must hold'))}">＋ ${esc(t('Filter'))}</button>
        <button class="btn small ${this.picking ? 'on' : ''}" data-a="dropper" title="${esc(t('Eyedropper: click a shape in the drawing — the filters become what it is (shape, layer, size); remove one to find more'))}">💧 ${esc(t('From a shape'))}</button>
        ${n !== null ? `<span class="mp-count dw-fcount">${esc(tv('{n} match', { n }))}</span>` : ''}</div>
      ${n ? `<div class="row-actions wrap"><button class="btn small primary" data-a="selMatches">${esc(t('Select them'))}</button><button class="btn small" data-a="addMatches">＋ ${esc(t('Add to the selection'))}</button></div>` : ''}`;
  }

  bindFilter(box) {
    const set = (i, patch) => {
      this.filters[i] = { ...this.filters[i], ...patch };
      this.updateMatches();
      this.renderProps();
    };
    for (const el of box.querySelectorAll('[data-ff]')) {
      el.addEventListener('change', () => {
        const field = el.value, F = FIELDS[field];
        set(+el.dataset.ff, { field, op: OPS[F.kind][0], value: F.kind === 'enum' ? this.choices(field)[0]?.[0] : '' });
      });
    }
    for (const el of box.querySelectorAll('[data-fo]')) {
      el.addEventListener('change', () => {
        const i = +el.dataset.fo, f = this.filters[i], op = OPS[FIELDS[f.field].kind][el.selectedIndex];
        set(i, { op, value: op === 'is any of' ? [].concat(f.value ?? []) : Array.isArray(f.value) ? f.value[0] : f.value });
      });
    }
    for (const el of box.querySelectorAll('[data-fv]')) {
      const i = +el.dataset.fv;
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      if (el.tagName === 'SELECT') el.addEventListener('change', () => set(i, { value: el.multiple ? [...el.selectedOptions].map((o) => o.value) : el.value }));
      else {
        el.addEventListener('input', () => { this.filters[i].value = el.value; this.updateMatches(); const c = box.querySelector('.dw-fcount'); if (c) c.textContent = tv('{n} match', { n: this.matchSet.size }); });
        el.addEventListener('change', () => set(i, { value: el.value }));
      }
    }
    for (const el of box.querySelectorAll('[data-fx]')) el.addEventListener('click', () => { this.filters.splice(+el.dataset.fx, 1); this.updateMatches(); this.renderProps(); });
    box.querySelector('[data-a=addFilter]').addEventListener('click', () => {
      // the next filter: the shape first, then the layer, then a size
      const used = new Set(this.filters.map((f) => f.field)), field = ['shape', 'layer', 'dia', 'len', 'color', 'text', 'r'].find((k) => !used.has(k)) || 'shape';
      this.filters.push({ field, op: OPS[FIELDS[field].kind][0], value: FIELDS[field].kind === 'enum' ? this.choices(field)[0]?.[0] : '' });
      this.updateMatches();
      this.renderProps();
    });
    box.querySelector('[data-a=dropper]').addEventListener('click', () => {
      this.picking = !this.picking;
      if (this.picking && this.tool !== 'select') this.setTool('select');
      this.hint(this.picking ? 'Eyedropper: click a shape — the filters become what it is. Esc = stop.' : '');
      this.renderProps();
    });
    box.querySelector('[data-a=selMatches]')?.addEventListener('click', () => { this.sel = new Set(this.matches().map((e) => e.id)); this.renderProps(); this.draw(); });
    box.querySelector('[data-a=addMatches]')?.addEventListener('click', () => { for (const e of this.matches()) this.sel.add(e.id); this.renderProps(); this.draw(); });
  }

  updateMatches() { this.matchSet = new Set(this.matches().map((e) => e.id)); this.draw(); }

  /** Filters that pick shapes like this one (its shape, layer and size), and those selected. */
  likeThis(e, select = true) {
    this.filters = [{ field: 'shape', op: 'is', value: e.t }, { field: 'layer', op: 'is', value: e.layer }];
    if (e.t === 'circle' || e.t === 'arc') this.filters.push({ field: 'dia', op: '=', value: fmt(2 * e.r) });
    else if (e.t === 'line' || e.t === 'poly') this.filters.push({ field: 'len', op: '=', value: fmt(lengthOf(e)) });
    if (select) this.sel = new Set(this.matches().map((x) => x.id));
    this.updateMatches();
    this.renderProps();
  }

  /** The selected shapes' size set at once: circles' Ø (centres stay), arcs' / circles' radius, lines' length (from
   *  their start, along them). */
  setSize(kind, value) {
    const v = parseFloat(String(value).replace(',', '.'));
    if (!(v > 0)) { this.hooks.toast?.(t('The size must be greater than zero.'), 'warning'); return; }
    this.d.entities = this.d.entities.map((e) => {
      if (!this.sel.has(e.id)) return e;
      if (kind === 'dia' && (e.t === 'circle' || e.t === 'arc')) return { ...e, r: +(v / 2).toFixed(6) };
      if (kind === 'r' && (e.t === 'circle' || e.t === 'arc')) return { ...e, r: +v.toFixed(6) };
      if (kind === 'len' && e.t === 'line') {
        const L = Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]) || 1;
        return { ...e, b: [e.a[0] + ((e.b[0] - e.a[0]) * v) / L, e.a[1] + ((e.b[1] - e.a[1]) * v) / L].map((x) => +x.toFixed(6)) };
      }
      return e;
    });
    this.commit();
  }

  /** Use ▾ (kind: 'sketch' | 'quick'): of the selected shapes, the ones the filter finds, or all the shown ones —
   *  asked when there is a selection or a filter; the selection first. */
  async use(kind) {
    const shown = this.d.entities.filter((x) => this.shown(x)), sel = shown.filter((x) => this.sel.has(x.id)), found = this.filters.length ? this.matches() : [];
    let pick = shown;
    if (sel.length || found.length) {
      const opts = [];
      if (sel.length) opts.push({ value: 'sel', primary: true, label: tv('The {n} selected shapes', { n: sel.length }) });
      if (found.length && !(sel.length === found.length && found.every((x) => this.sel.has(x.id)))) opts.push({ value: 'found', primary: !sel.length, label: tv('The {n} shapes the filter finds', { n: found.length }) });
      opts.push({ value: 'all', label: tv('All the shown layers ({n} shapes)', { n: shown.length }) }, { value: null, label: 'Cancel' });
      const what = opts.length > 2 ? await choose(t(kind === 'sketch' ? 'What goes into the sketch?' : 'What goes into the quick part?'), opts) : 'all';
      if (!what) return;
      pick = what === 'sel' ? sel : what === 'found' ? found : shown;
    }
    const d = { ...this.payload(), entities: structuredClone(pick) };
    if (kind === 'sketch') this.hooks.useAsSketch?.(d);
    else this.hooks.useAsQuick?.(d);
  }

  /** Only these shapes (the chosen ones) as a sketch / a quick part — no question asked. */
  useShapes(kind, shapes) {
    const d = { ...this.payload(), entities: structuredClone(shapes) };
    if (kind === 'sketch') this.hooks.useAsSketch?.(d);
    else this.hooks.useAsQuick?.(d);
  }

  /** ⬇ the shown layers as a DXF. */
  async exportDxf() {
    const shown = { ...this.d, layers: this.d.layers, entities: this.d.entities.filter((e) => this.shown(e)) };
    if (!shown.entities.length) { this.hooks.toast?.(t('Nothing to export on the shown layers.'), 'warning'); return; }
    const res = await fetch('/api/drawing/dxf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(shown) });
    if (!res.ok) { this.hooks.toast?.((await res.json().catch(() => ({}))).error || res.statusText, 'error'); return; }
    const name = `${(this.hooks.safeName?.() || this.d.source || 'drawing').replace(/\.[^.]+$/, '')}.dxf`;
    if (await this.hooks.download?.(await res.blob(), name)) this.hooks.toast?.(tv('Saved {name} ({n} shapes on {k} layers).', { name, n: shown.entities.length, k: this.d.layers.filter((l) => l.visible !== false).length }), 'ok', 5000);
  }

  removeSel() {
    this.d.entities = this.d.entities.filter((e) => !this.sel.has(e.id));
    this.sel.clear();
    this.commit();
  }

  // ------------------------------------------------------------------ panels
  updateUndo() {
    const u = this.$('.dw-bar [data-a=undo]'), r = this.$('.dw-bar [data-a=redo]');
    if (u) u.disabled = !this.history.canUndo();
    if (r) r.disabled = !this.history.canRedo();
  }

  renderBar() {
    const bar = this.$('.dw-bar'), btn = (a, label, title) => `<button class="chip ${this.tool === a ? 'on' : ''}" data-a="${a}" title="${esc(title)}">${label}</button>`;
    bar.innerHTML = `${btn('select', '⬚ Select', 'Click a shape (Ctrl+click: more), Delete removes it; drag the paper to move it, the wheel zooms')}
      ${btn('line', '／ Line', 'Draw lines (L) — ends, middles and centres snap')}${btn('circle', '◯ Circle', 'Draw a circle: its centre, then a point on it (C)')}
      ${btn('measure', '📏 Measure', 'Measure: two spots, or a circle for its Ø (M)')}
      <span class="sep"></span><button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
      <button class="chip" data-a="fit" title="Show all of it (F)">⤢ Fit</button>
      <button class="chip" data-a="dxf" title="Save the shown layers as a DXF (in mm, its layers and colours; traces keep their width, pads and areas filled)">⬇ DXF</button>
      <span class="sep"></span>
      <div class="menu dw-use"><button class="chip tool" data-a="use" title="What to make of the drawing (its shown layers)">Use ▾</button>
        <div class="menu-list"><button data-use="sketch">✏ As a sketch of a new 3D model</button><button data-use="quick">▤ As a quick part (its closed outlines)</button></div></div>`;
    for (const b of bar.querySelectorAll('[data-a]')) {
      b.addEventListener('click', (e) => {
        const a = b.dataset.a;
        if (a === 'undo') return this.history.go(-1);
        if (a === 'redo') return this.history.go(1);
        if (a === 'fit') return this.fit();
        if (a === 'dxf') return this.exportDxf();
        if (a === 'use') { e.stopPropagation(); bar.querySelector('.dw-use').classList.toggle('open'); return null; }
        return this.setTool(a);
      });
    }
    for (const b of bar.querySelectorAll('[data-use]')) {
      b.addEventListener('click', () => { bar.querySelector('.dw-use').classList.remove('open'); this.use(b.dataset.use); });
    }
    this.updateUndo();
  }

  renderPanels() {
    this.renderBar();
    this.renderLayers();
    this.renderProps();
  }

  renderLayers() {
    const box = this.$('.dw-layers'), count = {};
    for (const e of this.d.entities) count[e.layer] = (count[e.layer] || 0) + 1;
    this.layerSel = new Set([...this.layerSel].filter((n) => this.layer(n)));
    const many = this.layerSel.size > 1;
    box.innerHTML = `${this.d.layers.map((l, i) => `<div class="dw-layer ${l.name === this.d.active ? 'on' : ''} ${this.layerSel.has(l.name) ? 'picked' : ''} ${l.visible === false ? 'off' : ''}" data-i="${i}">
        <button class="mini" data-a="eye" title="${l.visible === false ? 'Show this layer' : 'Hide this layer'}">${l.visible === false ? '◌' : '👁'}</button>
        <input type="color" data-a="col" value="${/^#[0-9a-f]{6}$/i.test(l.color) ? l.color : '#ffffff'}" title="The layer's colour">
        <span class="dw-lname" data-no-i18n title="${esc(t('Click: new lines go on this layer'))}">${esc(l.name)}</span><span class="mt-what">${count[l.name] || 0}</span></div>`).join('')}
      ${many ? `<div class="dw-lsel"><b>${esc(tv('{n} layers', { n: this.layerSel.size }))}</b>
        <div class="row-actions wrap"><button class="btn small" data-a="selOn">👁 ${esc(t('Show'))}</button><button class="btn small" data-a="selOff">◌ ${esc(t('Hide'))}</button>
        <button class="btn small" data-a="selShapes">⬚ ${esc(t('Select their shapes'))}</button><button class="btn small" data-a="selFilter">🔍 ${esc(t('As a filter'))}</button></div></div>` : ''}
      <div class="row-actions wrap"><button class="btn small" data-a="allOn">👁 ${esc(t('All'))}</button><button class="btn small" data-a="allOff">◌ ${esc(t('None'))}</button><button class="btn small" data-a="newLayer">＋ ${esc(t('Layer'))}</button></div>`;
    // a row of the picked layers changes them all
    const group = (l) => (this.layerSel.has(l.name) && this.layerSel.size > 1 ? this.layerSel : new Set([l.name]));
    for (const row of box.querySelectorAll('.dw-layer')) {
      const i = +row.dataset.i, l = this.d.layers[i];
      row.querySelector('[data-a=eye]').addEventListener('click', () => {
        const g = group(l), vis = l.visible === false;
        this.d.layers = this.d.layers.map((x) => (g.has(x.name) ? { ...x, visible: vis } : x));
        this.commit();
      });
      const col = row.querySelector('[data-a=col]');
      col.addEventListener('input', () => { for (const x of this.d.layers) if (group(l).has(x.name)) x.color = col.value; this.draw(); });
      col.addEventListener('change', () => { const g = group(l); this.d.layers = this.d.layers.map((x) => (g.has(x.name) ? { ...x, color: col.value } : x)); this.commit(); });
      row.querySelector('.dw-lname').addEventListener('click', (e) => {
        if (e.shiftKey && this.layerAnchor !== undefined) { // all from the last one clicked to this one
          const [a, b] = [Math.min(this.layerAnchor, i), Math.max(this.layerAnchor, i)];
          if (!(e.ctrlKey || e.metaKey)) this.layerSel.clear();
          for (let k = a; k <= b; k++) this.layerSel.add(this.d.layers[k].name);
        } else if (e.ctrlKey || e.metaKey) {
          if (this.layerSel.has(l.name)) this.layerSel.delete(l.name); else this.layerSel.add(l.name);
          this.layerAnchor = i;
        } else {
          this.layerSel = new Set([l.name]);
          this.layerAnchor = i;
          this.d.active = l.name; // new lines go here
        }
        this.renderLayers();
      });
    }
    const setVis = (v) => { this.d.layers = this.d.layers.map((x) => (this.layerSel.has(x.name) ? { ...x, visible: v } : x)); this.commit(); };
    box.querySelector('[data-a=selOn]')?.addEventListener('click', () => setVis(true));
    box.querySelector('[data-a=selOff]')?.addEventListener('click', () => setVis(false));
    box.querySelector('[data-a=selShapes]')?.addEventListener('click', () => {
      this.sel = new Set(this.d.entities.filter((e) => this.layerSel.has(e.layer) && this.shown(e)).map((e) => e.id));
      this.renderProps();
      this.draw();
    });
    box.querySelector('[data-a=selFilter]')?.addEventListener('click', () => {
      this.filters = [...this.filters.filter((f) => f.field !== 'layer'), { field: 'layer', op: 'is any of', value: [...this.layerSel] }];
      this.updateMatches();
      this.renderProps();
    });
    box.querySelector('[data-a=allOn]').addEventListener('click', () => { this.d.layers = this.d.layers.map((x) => ({ ...x, visible: true })); this.commit(); });
    box.querySelector('[data-a=allOff]').addEventListener('click', () => { this.d.layers = this.d.layers.map((x) => ({ ...x, visible: false })); this.commit(); });
    box.querySelector('[data-a=newLayer]').addEventListener('click', () => {
      let n = 1;
      while (this.layer(`${t('Layer')} ${n}`)) n++;
      const name = `${t('Layer')} ${n}`;
      this.d.layers = [...this.d.layers, { name, color: '#7ee787', visible: true }];
      this.d.active = name;
      this.commit();
    });
  }

  renderProps() {
    const box = this.$('.mp-body'), sel = this.d.entities.filter((e) => this.sel.has(e.id));
    this.matchSet = new Set(this.matches().map((e) => e.id));
    if (sel.length) {
      const e = sel[0], one = sel.length === 1;
      const all = (...ts) => sel.every((x) => ts.includes(x.t)), same = (f) => sel.every((x) => sameNum(f(x), f(e)));
      // one size for all of them (circles: Ø; circles and arcs: R; lines: length) — the value shown when they agree
      const sizeField = all('circle') ? ['dia', 'Ø', same((x) => x.r) ? fmt(2 * e.r) : '']
        : all('circle', 'arc') ? ['r', 'R', same((x) => x.r) ? fmt(e.r) : '']
        : all('line') ? ['len', t('Length'), same(lengthOf) ? fmt(lengthOf(e)) : ''] : null;
      const size = !one ? '' : e.t === 'line' ? `${t('Length')} ${fmt(Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]))} mm` : e.t === 'circle' ? `Ø ${fmt(2 * e.r)} mm · ${t('centre')} ${fmt(e.c[0])}, ${fmt(e.c[1])}`
        : e.t === 'arc' ? `R ${fmt(e.r)} mm · ${fmt(sweepOf(e) * 180 / Math.PI)}°` : e.t === 'poly' ? tv('{n} points', { n: e.pts.length }) + (e.closed ? ` · ${t('closed')}` : '') : e.t === 'text' ? `“${esc(e.text)}”` : '';
      box.innerHTML = `<h2>${one ? esc(t({ line: 'Line', circle: 'Circle', arc: 'Arc', poly: 'Polyline', text: 'Text' }[e.t] || e.t)) : tv('{n} shapes', { n: sel.length })}</h2>
        ${size ? `<p class="hint" data-no-i18n>${size}</p>` : ''}
        ${sizeField ? `<div class="field"><label data-no-i18n>${esc(sizeField[1])}</label><input data-k="size" inputmode="decimal" value="${sizeField[2]}" placeholder="${esc(t('different'))}"><span class="unit">mm</span></div>
          <p class="hint">${esc(sel.length > 1 ? tv('Type it: all {n} change.', { n: sel.length }) : t('Type it: it changes.'))}</p>` : ''}
        <div class="field"><label>Layer</label><select data-k="layer">${this.d.layers.map((l) => `<option ${l.name === e.layer ? 'selected' : ''} data-no-i18n>${esc(l.name)}</option>`).join('')}</select></div>
        <div class="row-actions wrap">${one ? `<button class="btn small" data-a="like" title="${esc(t('Filters for shapes like this one (its shape, layer and size) — and select them all'))}">≡ ${esc(t('All like this'))}</button>` : ''}
          <button class="btn small danger" data-a="del">✕ ${esc(t('Delete'))} (Del)</button></div>
        <div class="dw-fbox">${this.filterHtml()}</div>`;
      this.bindFilter(box.querySelector('.dw-fbox'));
      const sz = box.querySelector('[data-k=size]');
      sz?.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') sz.blur(); });
      sz?.addEventListener('change', () => { if (sz.value.trim()) this.setSize(sizeField[0], sz.value); });
      box.querySelector('[data-a=like]')?.addEventListener('click', () => this.likeThis(e));
      box.querySelector('[data-k=layer]').addEventListener('change', (ev) => { for (const x of sel) x.layer = ev.target.value; this.d.entities = [...this.d.entities]; this.commit(); });
      box.querySelector('[data-a=del]').addEventListener('click', () => this.removeSel());
      this.renderSuggest();
      return;
    }
    const b = this.bbox(), n = this.d.entities.length, shown = this.d.entities.filter((e) => this.shown(e)).length;
    box.innerHTML = `<h2>${esc(t('Drawing'))}</h2><p class="hint" data-no-i18n>${esc(this.d.source || '')}</p>
      <div class="field"><label>${esc(t('File units'))}</label><select data-k="units" title="${esc(t('What one unit of the file is — the file may not say (or say it wrong): change it and the drawing is rescaled'))}">
        ${Object.keys(UNIT_MM).map((u) => `<option value="${u}" ${u === (this.d.file_units || 'mm') ? 'selected' : ''}>${u === 'in' ? 'inch' : u}</option>`).join('')}</select></div>
      <div class="mp-facts">${b ? `<span>${esc(t('Size'))}</span><b>${fmt(b[2] - b[0])} × ${fmt(b[3] - b[1])} mm</b>` : ''}
        <span>${esc(t('Shapes'))}</span><b>${shown} / ${n}</b><span>${esc(t('Layers'))}</span><b>${this.d.layers.filter((l) => l.visible !== false).length} / ${this.d.layers.length}</b></div>
      <div class="dw-fbox">${this.filterHtml()}</div>
      <h3>${esc(t('What next'))}</h3><p class="hint">${esc(t('Look, measure, tidy it up — then Use ▾ makes something of the shown layers:'))}</p>
      <div class="row-actions"><button class="btn small primary" data-use="sketch">✏ ${esc(t('As a sketch of a new 3D model'))}</button></div>
      <div class="row-actions"><button class="btn small" data-use="quick">▤ ${esc(t('As a quick part (its closed outlines)'))}</button></div>`;
    box.querySelector('[data-k=units]').addEventListener('change', (ev) => this.setUnits(ev.target.value));
    this.bindFilter(box.querySelector('.dw-fbox'));
    for (const el of box.querySelectorAll('[data-use]')) {
      el.addEventListener('click', () => this.use(el.dataset.use));
    }
    this.renderSuggest();
  }
}

/** A drawing's shapes as a clean sketch (on the XY plane) of a 3D model — the server's /api/drawing/sketch: ends that
 *  nearly meet welded into one point, an exporter's crumbs absorbed, collinear lines and arcs on one circle joined, a
 *  flattened smooth curve one arc or spline again. -> {feature, report: {before, after}}; offline: as drawingToSketch. */
export async function drawingToCleanSketch(drawing) {
  try {
    const res = await fetch('/api/drawing/sketch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(drawing) });
    const j = await res.json();
    if (!res.ok || j.error) throw new Error(j.error || res.statusText);
    return { feature: { id: 'F1', type: 'sketch', name: `${t('Sketch')} 1`, plane: { datum: 'XY' }, ...j.sketch }, report: j.report };
  } catch (e) {
    console.warn('clean sketch:', e);
    return { feature: drawingToSketch(drawing), report: null };
  }
}

/** A drawing's shapes as a sketch (on the XY plane) of a 3D model: lines, circles, arcs and polylines become sketch
 *  lines, circles and arcs (ends that meet are joined); texts are left out. -> the sketch feature */
export function drawingToSketch(drawing) {
  const points = {}, entities = [], key = new Map();
  let np = 0, ne = 0;
  const pt = (p) => {
    const k = `${p[0].toFixed(5)},${p[1].toFixed(5)}`;
    if (!key.has(k)) { const id = `p${++np}`; points[id] = [+p[0].toFixed(6), +p[1].toFixed(6)]; key.set(k, id); }
    return key.get(k);
  };
  for (const e of drawing.entities || []) {
    if (e.t === 'line') { const a = pt(e.a), b = pt(e.b); if (a !== b) entities.push({ id: `l${++ne}`, t: 'line', a, b }); } else if (e.t === 'circle') entities.push({ id: `c${++ne}`, t: 'circle', c: pt(e.c), r: e.r });
    else if (e.t === 'arc') {
      const a0 = rad(e.a0), a1 = a0 + sweepOf(e);
      entities.push({ id: `a${++ne}`, t: 'arc', c: pt(e.c), a: pt([e.c[0] + e.r * Math.cos(a0), e.c[1] + e.r * Math.sin(a0)]), b: pt([e.c[0] + e.r * Math.cos(a1), e.c[1] + e.r * Math.sin(a1)]) });
    } else if (e.t === 'poly') {
      const q = e.closed ? [...e.pts, e.pts[0]] : e.pts;
      for (let i = 0; i + 1 < q.length; i++) { const a = pt(q[i]), b = pt(q[i + 1]); if (a !== b) entities.push({ id: `l${++ne}`, t: 'line', a, b }); }
    }
  }
  return { id: 'F1', type: 'sketch', name: `${t('Sketch')} 1`, plane: { datum: 'XY' }, points, entities, constraints: [], dims: [] };
}
