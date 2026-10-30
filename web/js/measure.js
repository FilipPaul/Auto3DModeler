// 📏 Measure — one tool and one table for the 3D model and the assembly. What a click measures follows from what is
// clicked (no mode menu): a point (a snapped corner, an edge's middle, a centre), an edge (its length; a circle: Ø, an
// arc: R), a face (its area; a round one: Ø and its axis), a part (an assembly's 'Parts' chip: the clearance between
// two). The first click adds a row with what it is; a second click on something else turns that row into the
// measurement between the two (the distance, ΔX ΔY ΔZ; a point to a face: square to it; two flat faces: the gap
// when parallel, else the angle; two axes: how far apart, else the angle) — a click on empty space starts anew.
// The rows stay (in the doc: part.measures / assembly.measures — saved with it, small) with their marks in the view
// (thin lines, a small label each); the tool stays on until Esc. The table is a left-column widget (leftdock.js):
// one line a row — #, icon, what, the value bold, the rest muted (also its tooltip); hovering a row lights its marks,
// a click on it suggests copy / hide / delete; 👁 all marks, 📋 copy all (tab separated), 🗑 clear (↶ in the toast).
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { t } from './i18n.js';
import { leftDock } from './leftdock.js';
import { showSuggest } from './suggest.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const r3 = (v) => +(+v).toFixed(3);
/** A number as the table shows it: up to 3 decimals, no trailing zeros. */
export const fmtMm = (v) => (Number.isFinite(+v) ? String(r3(v)) : '—');
const V = (p) => (p?.isVector3 ? p.clone() : new THREE.Vector3(...p));
const arr = (p) => p.toArray().map((x) => +x.toFixed(4));
const PAR = 1 - 1e-4; // |cos| above this: parallel
const COL = { mark: 0xf2cc60, hot: 0x58a6ff };

// ---------------------------------------------------------------------------------------------- geometry
/** What a picked thing is, geometrically: {t: 'point', p} | {t: 'line', p, d, a, b, len} | {t: 'axis', p, d, r, ring?,
 *  len?} (a circle / arc edge: ring, p its centre; a round face: p on its axis) | {t: 'plane', p, n} | {t: 'curve', len}
 *  | {t: 'surf'} | {t: 'part'}. */
export function geoOf(ent) {
  if (ent.kind === 'point') return { t: 'point', p: V(ent.p) };
  if (ent.kind === 'part') return { t: 'part' };
  if (ent.kind === 'edge') return edgeGeo(ent.pts, ent.matrix);
  const f = ent.face;
  if (f.type === 'plane' && f.normal) return { t: 'plane', p: V(f.centroid), n: V(f.normal).normalize() };
  if (f.type === 'cylinder' && f.axis) return { t: 'axis', p: V(f.axis.o), d: V(f.axis.d).normalize(), r: f.radius || 0 };
  return { t: 'surf' };
}

/** An edge's points (flat [x, y, z, …], moved by matrix) -> a line, a circle / arc (by three of its points and all of
 *  them on that circle) or a curve, with its length. */
export function edgeGeo(flat, matrix = null) {
  const P = [];
  for (let k = 0; k + 2 < flat.length; k += 3) { const p = new THREE.Vector3(flat[k], flat[k + 1], flat[k + 2]); P.push(matrix ? p.applyMatrix4(matrix) : p); }
  let len = 0;
  for (let i = 1; i < P.length; i++) len += P[i].distanceTo(P[i - 1]);
  const closed = P.length > 2 && P[0].distanceTo(P[P.length - 1]) < 1e-6 * (1 + len);
  const a = P[0], b = P[P.length - 1], tol = 1e-4 * (1 + len);
  if (!closed && P.length >= 2) {
    const d = b.clone().sub(a), L = d.length();
    if (L > 1e-9 && P.every((p) => p.clone().sub(a).cross(d).length() / L < tol * 10) && Math.abs(L - len) < tol * 10) return { t: 'line', p: a.clone(), d: d.normalize(), a: a.clone(), b: b.clone(), len };
  }
  const Q = closed ? P.slice(0, -1) : P;
  if (Q.length >= 4) {
    const i1 = Math.floor(Q.length / 3), i2 = Math.floor((2 * Q.length) / 3), c = circumcentre(Q[0], Q[i1], Q[i2]);
    if (c) {
      const r = c.distanceTo(Q[0]), n = Q[i1].clone().sub(Q[0]).cross(Q[i2].clone().sub(Q[0])).normalize();
      if (r > 1e-6 && Q.every((p) => Math.abs(p.distanceTo(c) - r) < r * 0.01 + 1e-6 && Math.abs(p.clone().sub(c).dot(n)) < r * 0.01 + 1e-6)) {
        return { t: 'axis', ring: true, full: closed || Math.abs(len - 2 * Math.PI * r) < len * 0.02, p: c, d: n, r, len };
      }
    }
  }
  return { t: 'curve', len, mid: P[Math.floor(P.length / 2)] };
}

function circumcentre(a, b, c) {
  const ab = b.clone().sub(a), ac = c.clone().sub(a), n = ab.clone().cross(ac), n2 = n.lengthSq();
  if (n2 < 1e-18) return null;
  const x = n.clone().cross(ab).multiplyScalar(ac.lengthSq()).add(ac.clone().cross(n).multiplyScalar(ab.lengthSq())).multiplyScalar(1 / (2 * n2));
  return a.clone().add(x);
}

/** The foot of point p on the line (o, unit d). */
const footLine = (p, o, d) => o.clone().addScaledVector(d, p.clone().sub(o).dot(d));
/** The foot of point p on the plane (o, unit n). */
const footPlane = (p, o, n) => p.clone().addScaledVector(n, -p.clone().sub(o).dot(n));
const acute = (u, v) => { const c = Math.min(1, Math.abs(u.dot(v))); return (Math.acos(c) * 180) / Math.PI; };
/** The nearest points of two lines (o1, d1), (o2, d2) — not parallel. */
function nearestOfLines(o1, d1, o2, d2) {
  const w = o1.clone().sub(o2), a = d1.dot(d1), b = d1.dot(d2), c = d2.dot(d2), d = d1.dot(w), e = d2.dot(w), den = a * c - b * b;
  const s = (b * e - c * d) / den, u = (a * e - b * d) / den;
  return [o1.clone().addScaledVector(d1, s), o2.clone().addScaledVector(d2, u)];
}

/** The polyline of a picked thing (its mark): an edge's points, a face's / point's spot. */
function shapeOf(ent) {
  if (ent.kind === 'edge') { const g = edgeGeo(ent.pts, ent.matrix), P = []; for (let k = 0; k + 2 < ent.pts.length; k += 3) { const p = new THREE.Vector3(ent.pts[k], ent.pts[k + 1], ent.pts[k + 2]); P.push(ent.matrix ? p.applyMatrix4(ent.matrix) : p); } return { g, P }; }
  return { g: geoOf(ent), P: [] };
}

const at = (ent) => V(ent.at || ent.p || [0, 0, 0]);
const ptLabel = { corner: 'corner', midpoint: 'midpoint', centre: 'centre', quadrant: 'quadrant', point: 'point', origin: 'Origin' };

/** One thing's own measure -> a row (without id): icon, its name, the value (+ unit), details, its mark. */
export function single(ent) {
  const { g, P } = shapeOf(ent), here = at(ent);
  const half = P.length % 2 ? P[(P.length - 1) / 2] : P.length ? P[P.length / 2 - 1].clone().add(P[P.length / 2]).multiplyScalar(0.5) : here; // (an edge's middle)
  const mark = { lines: P.length ? [P.map(arr)] : [], dots: [arr(here)], at: arr(ent.kind === 'edge' ? half : here) };
  const row = { a: label(ent), mark };
  if (ent.kind === 'point') return { ...row, icon: '•', kind: 'point', text: `${fmtMm(here.x)}, ${fmtMm(here.y)}, ${fmtMm(here.z)}`, tail: 'X, Y, Z' };
  if (ent.kind === 'part') return { ...row, icon: '◆', kind: 'part', v: null, tail: 'Click a second part: the clearance' };
  if (ent.kind === 'edge') {
    if (g.t === 'line') return { ...row, icon: 'L', kind: 'len', v: r3(g.len), unit: 'mm' };
    if (g.t === 'axis' && g.full) return { ...row, icon: 'Ø', kind: 'dia', v: r3(2 * g.r), unit: 'mm', tail: `R ${fmtMm(g.r)} · L ${fmtMm(g.len)}`, mark: { ...mark, dots: [arr(g.p)] } };
    if (g.t === 'axis') return { ...row, icon: 'R', kind: 'rad', v: r3(g.r), unit: 'mm', tail: `Ø ${fmtMm(2 * g.r)} · L ${fmtMm(g.len)}`, mark: { ...mark, dots: [arr(g.p)] } };
    return { ...row, icon: 'L', kind: 'len', v: r3(g.len), unit: 'mm' };
  }
  const f = ent.face;
  if (g.t === 'axis') return { ...row, icon: 'Ø', kind: 'dia', v: r3(2 * g.r), unit: 'mm', tail: `R ${fmtMm(g.r)} · ${fmtMm(f.area)} mm² · axis ${dirText(g.d)}` };
  return { ...row, icon: '▭', kind: 'area', v: r3(f.area), unit: 'mm²' };
}

/** An axis' direction in words when it is along X / Y / Z, else its numbers. */
function dirText(d) {
  for (const [k, i] of [['X', 0], ['Y', 1], ['Z', 2]]) if (Math.abs(Math.abs(d.getComponent(i)) - 1) < 1e-4) return k;
  return `${fmtMm(d.x)}, ${fmtMm(d.y)}, ${fmtMm(d.z)}`;
}

/** The measurement between two picked things -> a row (without id). Parts: null (the kernel's clearance). */
export function pair(A, B) {
  const ga = geoOf(A), gb = geoOf(B);
  if (ga.t === 'part' || gb.t === 'part') return null;
  const row = { a: label(A), b: label(B) };
  const dist = (p, q, icon = '↔', extra = '') => {
    const d = q.clone().sub(p);
    return { ...row, icon, kind: 'dist', v: r3(d.length()), unit: 'mm', tail: `${extra}${extra ? ' · ' : ''}ΔX ${fmtMm(Math.abs(d.x))} · ΔY ${fmtMm(Math.abs(d.y))} · ΔZ ${fmtMm(Math.abs(d.z))}`,
      mark: { lines: [[arr(p), arr(q)]], dots: [arr(p), arr(q)], at: arr(p.clone().add(q).multiplyScalar(0.5)) } };
  };
  const angle = (u, v, p, q, extra = '') => {
    const a = acute(u, v);
    return { ...row, icon: '∠', kind: 'angle', v: r3(a), unit: '°', tail: `${extra}${extra ? ' · ' : ''}${fmtMm(180 - a)}°`, mark: { lines: [[arr(p), arr(q)]], dots: [arr(p), arr(q)], at: arr(p.clone().add(q).multiplyScalar(0.5)) } };
  };
  // (ordered so that the simpler one is first: point, line, axis, plane)
  const ORDER = { point: 0, line: 1, axis: 2, plane: 3, curve: 4, surf: 5 };
  let [x, y, X, Y] = [ga, gb, A, B];
  if (ORDER[x.t] > ORDER[y.t]) [x, y, X, Y] = [gb, ga, B, A];
  const pX = x.t === 'point' ? x.p : at(X), pY = y.t === 'point' ? y.p : at(Y);
  const both = (k) => x.t === k && y.t === k;
  if (both('point')) return dist(x.p, y.p);
  if (x.t === 'point' && y.t === 'plane') return { ...dist(x.p, footPlane(x.p, y.p, y.n), '⊥'), tail: 'square to the face' };
  if (x.t === 'point' && y.t === 'line') return { ...dist(x.p, footLine(x.p, y.p, y.d), '⊥'), tail: 'square to the edge' };
  if (x.t === 'point' && y.t === 'axis') return y.ring ? dist(x.p, y.p, '↔', 'to the centre') : { ...dist(x.p, footLine(x.p, y.p, y.d), '⊥'), tail: 'to the axis' };
  if ((x.t === 'line' || x.t === 'axis') && (y.t === 'line' || y.t === 'axis')) {
    if (Math.abs(x.d.dot(y.d)) > PAR) {
      const f = footLine(x.p, y.p, y.d), off = x.p.distanceTo(f);
      if (off < 1e-6 && x.ring && y.ring) return { ...dist(x.p, y.p), tail: 'centres, on one axis' }; // (coaxial circles: along the axis)
      // (the mark between the clicked spot of the first and its foot on the second)
      const p = footLine(pX, x.p, x.d), q = footLine(p, y.p, y.d);
      const out = { ...dist(p, q, '⫽'), v: r3(off), tail: x.t === 'axis' && y.t === 'axis' ? `between the axes · Ø ${fmtMm(2 * x.r)} / Ø ${fmtMm(2 * y.r)}` : 'parallel' };
      if (x.r && y.r) out.alt = r3(Math.max(0, off - x.r - y.r)); // (the gap between the two round surfaces)
      else if (x.r || y.r) out.alt = r3(Math.max(0, off - (x.r || y.r)));
      return out;
    }
    const [p, q] = nearestOfLines(x.p, x.d, y.p, y.d);
    return angle(x.d, y.d, pX, pY, `apart ${fmtMm(p.distanceTo(q))}`);
  }
  if ((x.t === 'line' || x.t === 'axis') && y.t === 'plane') {
    if (Math.abs(x.d.dot(y.n)) < 1 - PAR) {
      const p = footLine(pX, x.p, x.d), q = footPlane(p, y.p, y.n), out = { ...dist(p, q, '⫽'), tail: x.t === 'axis' ? `axis to the face · R ${fmtMm(x.r)}` : 'parallel to the face' };
      if (x.r && !x.ring) out.alt = r3(Math.max(0, p.distanceTo(q) - x.r));
      return out;
    }
    const a = 90 - acute(x.d, y.n);
    return { ...angle(x.d, y.n, pX, pY), v: r3(a), tail: `${fmtMm(180 - a)}°` };
  }
  if (both('plane')) {
    if (Math.abs(x.n.dot(y.n)) > PAR) return { ...dist(pX, footPlane(pX, y.p, y.n), '⫽'), tail: 'parallel faces' };
    return angle(x.n, y.n, pX, pY);
  }
  return { ...dist(pX, pY), tail: 'clicked spots' }; // (a curve or a free-form face: between the spots clicked)
}

/** A picked thing's short name: {w: a word (translated when shown), id: 'F3' / 'E7' / 'I2·F3' (none: a point)}. */
function label(ent) {
  if (ent.kind === 'point') { const p = V(ent.p); return { w: ptLabel[ent.snap] || 'point', id: ent.name || '', tip: ent.tip || `${fmtMm(p.x)}, ${fmtMm(p.y)}, ${fmtMm(p.z)}` }; }
  if (ent.kind === 'part') return { w: 'part', id: ent.id, tip: ent.tip || '' };
  if (ent.kind === 'edge') { const g = edgeGeo(ent.pts, ent.matrix); return { w: ent.hole && g.t === 'axis' ? 'hole' : g.t === 'axis' ? (g.full ? 'circle' : 'arc') : 'edge', id: ent.id, tip: ent.tip || '' }; }
  return { w: ent.hole ? 'hole' : ent.face.type === 'cylinder' ? 'round face' : 'face', id: ent.id, tip: ent.tip || '' };
}

/** A snap point (mp, from view.measurePoint) and an edge both under the mouse: does the point win? A corner or a
 *  reference point does; an edge's middle or a round edge's centre only when the mouse is right on it (6 px) — else the
 *  edge itself is measured (a small hole's rim is within the 10 px of its centre). */
export function snapWins(view, mp, e) {
  if (!mp?.snap) return false;
  if (mp.snap === 'corner' || mp.snap === 'point' || mp.snap === 'origin') return true;
  const [x, y] = view.toScreen(mp.point);
  return Math.hypot(x - e.clientX, y - e.clientY) <= 6;
}

// ---------------------------------------------------------------------------------------------- the tool
const SHOW_KEY = 'a3d.measureMarks';
const WORDS = { corner: 'corner', midpoint: 'midpoint', centre: 'centre', quadrant: 'quadrant', point: 'point', part: 'part', hole: 'hole', circle: 'circle', arc: 'arc', edge: 'edge', face: 'face', 'round face': 'round face' };

/** 📏 The measure tool of one workspace. o: {ws: 'model' | 'assembly', view(), viewport, list() -> the doc's rows
 *  (made when missing), pick(e, mode) -> a picked thing or null, hover(thing|null) (light its face), clearance(a, b)
 *  -> Promise {distance, pa, pb, overlap?} (the assembly), changed() (the doc changed: saved), stop() (Esc / ✕: the
 *  workspace turns the tool off), toast(text, kind, ms)}. */
export class MeasureTool {
  constructor(o) {
    this.o = { ...o, changed: () => { o.changed?.(); window.dispatchEvent(new Event('a3d:changed')); } }; // (a3d:changed: autosaved with its part)
    this.on = false;
    this.pend = null; // the first thing picked: {ent, id (its row)}
    this.hot = null; // the row under the mouse (its marks lit)
    this.sel = null; // the row clicked
    this.mode = 'items'; // 'items' | 'parts' (the assembly: whole parts, for their clearance)
    this.cc = 'centre'; // two round things: 'centre' (their axes apart) | 'min' (the gap between their surfaces)
    try { this.marks = localStorage.getItem(SHOW_KEY) !== '0'; } catch { this.marks = true; }
    this.w = `measure-${o.ws}`;
    this.box = leftDock.addWidget(this.w, o.ws, { title: '📏 Measurements', h: 220, close: () => { if (this.on) o.stop(); this.closed = true; this.render(); } });
    this.box.classList.add('ms-box');
    this.headButtons();
    window.addEventListener('a3d:lang', () => this.render());
  }

  /** The doc's rows (make: made when it has none yet — a part never measured keeps no empty list). */
  rows(make = false) { return this.o.list(make) || []; }
  view() { return this.o.view(); }

  headButtons() {
    const head = this.box.parentElement.querySelector(':scope > .lw-head'), x = head.querySelector('.lw-close');
    const mk = (a, text, title) => { const b = document.createElement('button'); b.className = 'mini ms-act'; b.dataset.msa = a; b.textContent = text; b.title = title; head.insertBefore(b, head.querySelector('.lw-fold')); return b; };
    this.eye = mk('eye', '👁️', 'Show or hide all the measurements\' marks in the view');
    mk('copy', '📋', 'Copy all the measurements (as a table: paste into a spreadsheet or a text)');
    mk('clear', '🗑️', 'Delete all the measurements');
    head.addEventListener('click', (e) => {
      const b = e.target.closest('[data-msa]');
      if (!b) return;
      e.stopPropagation();
      if (b.dataset.msa === 'eye') { this.marks = !this.marks; try { localStorage.setItem(SHOW_KEY, this.marks ? '1' : '0'); } catch { /* private */ } this.render(); }
      if (b.dataset.msa === 'copy') this.copy(this.text());
      if (b.dataset.msa === 'clear') this.clear();
    });
    if (x) head.appendChild(x);
  }

  // ------------------------------------------------------------------ on / off
  start() {
    this.on = true;
    this.closed = false;
    this.pend = null;
    this.render();
  }

  stop() {
    this.on = false;
    this.endPend();
    this.tip(null);
    this.o.hover?.(null);
    const v = this.view();
    v.setSnapMark(null);
    v.setHoverEdges([]);
    v.setMeasure([]);
    this.render();
  }

  /** The thing a click picked becomes the first of a measurement (Measure from here). */
  from(ent) {
    if (!this.on) this.start();
    this.pick(ent);
  }

  // ------------------------------------------------------------------ the mouse
  /** A click in the view while the tool is on. */
  click(e) {
    const ent = this.o.pick(e, this.mode);
    if (!ent) { this.endPend(); this.render(); return; } // (empty space: the next click starts anew)
    this.pick(ent);
  }

  /** No first pick waiting any more (a part alone measures nothing: its row goes). */
  endPend() {
    const p = this.pend;
    this.pend = null;
    this.view().setMeasure([]);
    if (p?.ent.kind !== 'part') return;
    const list = this.rows(), i = list.findIndex((r) => r.id === p.id);
    if (i >= 0 && list[i].kind === 'part') { list.splice(i, 1); this.o.changed?.(); }
  }

  pick(ent) {
    const list = this.rows(), v = this.view();
    if (this.pend && !same(this.pend.ent, ent)) {
      const A = this.pend.ent, i = list.findIndex((r) => r.id === this.pend.id);
      this.pend = null;
      v.setMeasure([]);
      if (A.kind === 'part' || ent.kind === 'part') {
        if (A.kind !== 'part' || ent.kind !== 'part') { this.add(single(ent)); return; }
        this.clearance(A, ent, i);
        return;
      }
      const row = pair(A, ent);
      if (i >= 0) { list[i] = { ...row, id: list[i].id }; this.saved(list[i].id); } else this.add(row);
      return;
    }
    if (this.pend && same(this.pend.ent, ent)) { this.endPend(); this.render(); return; } // (the same again: just it)
    const id = this.add(single(ent));
    this.pend = { ent, id };
    v.setMeasure([at(ent)]);
    this.render();
  }

  async clearance(A, B, i) {
    const list = this.rows(), id = i >= 0 ? list[i].id : this.add({ icon: '⇹', kind: 'clear', v: null, a: label(A), b: label(B), mark: { lines: [], dots: [], at: arr(at(A)) } });
    const put = (row) => { const k = this.rows().findIndex((r) => r.id === id); if (k >= 0) { this.rows()[k] = { ...row, id }; this.saved(id); } };
    put({ icon: '⇹', kind: 'clear', v: null, a: label(A), b: label(B), tail: 'measuring…', mark: { lines: [], dots: [], at: arr(at(A)) } });
    try {
      const r = await this.o.clearance(A, B);
      const p = V(r.pa), q = V(r.pb);
      put({ icon: '⇹', kind: 'clear', v: r3(r.distance), unit: 'mm', a: label(A), b: label(B), tail: r.overlap ? 'they go into each other' : r.distance < 1e-6 ? 'touching' : 'clearance (the least distance)',
        mark: { lines: [[arr(p), arr(q)]], dots: [arr(p), arr(q)], at: arr(p.clone().add(q).multiplyScalar(0.5)) } });
    } catch (err) {
      put({ icon: '⇹', kind: 'clear', v: null, a: label(A), b: label(B), tail: `⚠ ${err.message}`, mark: { lines: [], dots: [], at: arr(at(A)) } });
      this.o.toast?.(err.message, 'warning', 6000);
    }
  }

  /** The mouse over the view while the tool is on: what a click takes — a snap point, an edge lit, its name and size. */
  hover(e) {
    const v = this.view();
    if (!e) { this.tip(null); v.setSnapMark(null); v.setHoverEdges([]); this.o.hover?.(null); return; }
    const ent = this.o.pick(e, this.mode);
    v.setSnapMark(ent?.kind === 'point' ? { point: V(ent.p), snap: ent.snap, name: ent.name } : null);
    v.setHoverEdges(ent?.kind === 'edge' ? [{ pts: ent.pts, matrix: ent.matrix || null }] : [], ent?.kind === 'edge' ? `ms:${ent.id}` : '');
    this.o.hover?.(ent);
    if (!ent) { this.tip(null); return; }
    const s = single(ent), name = `${cap(t(WORDS[s.a.w] || s.a.w))}${s.a.id ? ` ${s.a.id}` : ''}${ent.kind === 'part' && ent.tip ? ` ${ent.tip}` : ''}`;
    const val = s.text || (s.v != null ? `${s.icon === 'Ø' ? 'Ø' : s.icon === 'R' ? 'R' : ''}${fmtMm(s.v)} ${s.unit}` : '');
    this.tip({ x: e.clientX, y: e.clientY, text: `${name}${val ? ` · ${val}` : ''}${this.pend ? ` — ${t('click: measure to it')}` : ''}` });
  }

  tip(p) {
    const vp = this.o.viewport;
    let el = vp.querySelector(':scope > .ms-tip');
    if (!p) { if (el) el.hidden = true; return; }
    if (!el) { el = document.createElement('div'); el.className = 'm-tip ms-tip'; el.dataset.noI18n = ''; vp.appendChild(el); }
    const r = vp.getBoundingClientRect();
    el.hidden = false;
    el.textContent = p.text;
    Object.assign(el.style, { left: `${p.x - r.left + 14}px`, top: `${p.y - r.top + 14}px` });
  }

  // ------------------------------------------------------------------ rows
  add(row) {
    const list = this.rows(true), id = (list.reduce((m, r) => Math.max(m, r.id || 0), 0) || 0) + 1;
    list.push({ ...row, id });
    this.saved(id);
    return id;
  }

  saved(id = null) {
    if (id) { this.sel = null; this.lastId = id; }
    this.render();
    this.o.changed?.();
  }

  remove(id) {
    const list = this.rows(), i = list.findIndex((r) => r.id === id);
    if (i < 0) return;
    const [gone] = list.splice(i, 1);
    if (this.pend?.id === id) { this.pend = null; this.view().setMeasure([]); }
    if (this.sel === id) { this.sel = null; showSuggest(this.o.viewport, '', []); }
    if (this.hot === id) this.hot = null;
    this.render();
    this.o.changed?.();
    this.undoToast(t('Measurement deleted.'), () => { this.rows(true).splice(Math.min(i, this.rows().length), 0, gone); this.render(); this.o.changed?.(); });
  }

  clear() {
    const list = this.rows();
    if (!list.length) return;
    const was = list.splice(0, list.length);
    this.pend = null;
    this.sel = null;
    this.hot = null;
    this.view().setMeasure([]);
    showSuggest(this.o.viewport, '', []);
    this.render();
    this.o.changed?.();
    this.undoToast(t('Measurements cleared.'), () => { this.rows(true).push(...was); this.render(); this.o.changed?.(); });
  }

  undoToast(text, undo) {
    const el = this.o.toast?.(text, 'info', 6000);
    if (!el?.appendChild) return;
    const b = document.createElement('button');
    b.className = 'btn small';
    b.textContent = `↶ ${t('Undo')}`;
    b.title = t('Bring it back');
    b.style.marginLeft = '8px';
    b.addEventListener('click', () => { undo(); el.remove(); });
    el.appendChild(b);
  }

  /** A row's value as the table shows it (the chip's min / centre for two round things). */
  value(r) {
    if (r.text) return r.text;
    const v = this.cc === 'min' && r.alt != null ? r.alt : r.v;
    if (v == null) return '…';
    const pre = r.kind === 'dia' ? 'Ø' : r.kind === 'rad' ? 'R' : '';
    return `${pre}${fmtMm(v)}${r.unit === '°' ? '°' : r.unit === 'mm²' ? ' mm²' : ''}`;
  }

  /** The value with a unit other than mm small after it (mm is the header's). */
  valueHtml(r) {
    const v = esc(this.value(r));
    return r.unit === 'mm²' ? v.replace(/ mm²$/, '<small>mm²</small>') : v;
  }

  what(r) {
    const w = (x) => cap(t(WORDS[x.w] || x.w));
    if (!r.b) return `${w(r.a)}${r.a.id ? ` ${r.a.id}` : ''}`;
    const s = (x) => x.id || t(WORDS[x.w] || x.w);
    return `${s(r.a)} ↔ ${s(r.b)}`;
  }

  tail(r) {
    const parts = [];
    if (r.alt != null) parts.push(this.cc === 'min' ? `${t('centre–centre')} ${fmtMm(r.v)}` : `${t('min')} ${fmtMm(r.alt)}`);
    if (r.tail) parts.push(trTail(r.tail));
    return parts.join(' · ');
  }

  text() {
    const lines = [['#', t('What'), t('Value'), t('Unit'), t('Details')].join('\t')];
    this.rows().forEach((r, i) => lines.push([i + 1, this.what(r), this.value(r).replace(/ mm²$|°$/, ''), r.unit || '', this.tail(r)].join('\t')));
    return lines.join('\n');
  }

  copy(text) {
    navigator.clipboard?.writeText(text).then(() => this.o.toast?.(t('Copied'), 'ok', 1500), () => this.o.toast?.(text, 'info', 8000));
    this.copied = text; // (for the tests: a headless browser may not grant the clipboard)
  }

  // ------------------------------------------------------------------ drawing
  render() {
    const list = this.rows() || [], show = (this.on || list.length > 0) && !this.closed;
    leftDock.show(this.w, show);
    this.eye.classList.toggle('on', this.marks);
    this.eye.style.opacity = this.marks ? '' : '0.45';
    this.table(list); // (hidden too: no rows left behind in it)
    if (this.on) {
      this.o.hint?.(t(this.pend ? 'Click another item: the distance or angle to it — or empty space for a new measurement. Esc ends.'
        : this.mode === 'parts' ? 'Click two parts: the clearance between them. Esc ends.' : 'Click an edge, a face or a corner — then another one for the distance or angle. Esc ends.'));
    }
    this.draw();
  }

  table(list) {
    const anyAlt = list.some((r) => r.alt != null), asm = this.o.ws === 'assembly';
    const bar = (asm || anyAlt) ? `<div class="ms-bar">${asm ? `<div class="seg ms-seg" title="${esc(t('What a click picks: an edge, a face or a point — or a whole part (the clearance between two parts)'))}">
        <button data-msm="items" class="${this.mode === 'items' ? 'on' : ''}">${esc(t('Items'))}</button><button data-msm="parts" class="${this.mode === 'parts' ? 'on' : ''}">${esc(t('Parts'))}</button></div>` : ''}
      ${anyAlt ? `<div class="seg ms-seg" title="${esc(t('Two round things (holes, pins): how far apart their axes are, or the least gap between their surfaces'))}">
        <button data-mcc="centre" class="${this.cc === 'centre' ? 'on' : ''}">${esc(t('centre–centre'))}</button><button data-mcc="min" class="${this.cc === 'min' ? 'on' : ''}">${esc(t('min'))}</button></div>` : ''}</div>` : '';
    this.box.innerHTML = `${bar}${list.length ? `<div class="ms-th"><span>#</span><span></span><span>${esc(t('What'))}</span><span class="ms-u">mm</span><span></span><span></span></div>` : ''}
      <div class="ms-list">${list.map((r, i) => `<div class="ms-row${r.id === this.sel ? ' sel' : ''}${r.id === this.hot ? ' hot' : ''}${this.pend?.id === r.id ? ' pend' : ''}${r.hide ? ' off' : ''}" data-ms="${r.id}" data-no-i18n
          title="${esc(this.rowTip(r, i))}"><span class="ms-n">${i + 1}</span><span class="ms-i">${esc(r.icon || '')}</span><span class="ms-what">${esc(this.what(r))}</span><b class="ms-v">${this.valueHtml(r)}</b><span class="ms-tail">${esc(this.tail(r))}</span><button class="ms-x" data-msx="${r.id}" title="${esc(t('Delete this measurement'))}">✕</button></div>`).join('')}</div>
      ${list.length ? '' : `<p class="hint ms-empty">${esc(t(this.mode === 'parts' ? 'Nothing measured yet — click two parts.' : 'Nothing measured yet — click an edge, a face or a corner of the part.'))}</p>`}`;
    for (const b of this.box.querySelectorAll('[data-msm]')) b.addEventListener('click', () => { this.mode = b.dataset.msm; this.endPend(); this.render(); });
    for (const b of this.box.querySelectorAll('[data-mcc]')) b.addEventListener('click', () => { this.cc = b.dataset.mcc; this.render(); });
    for (const row of this.box.querySelectorAll('[data-ms]')) {
      const id = +row.dataset.ms;
      row.addEventListener('mouseenter', () => { this.hot = id; row.classList.add('hot'); this.draw(); });
      row.addEventListener('mouseleave', () => { if (this.hot === id) { this.hot = null; row.classList.remove('hot'); this.draw(); } });
      row.addEventListener('click', (e) => { if (e.target.closest('[data-msx]')) return; this.choose(id); });
    }
    for (const b of this.box.querySelectorAll('[data-msx]')) b.addEventListener('click', (e) => { e.stopPropagation(); this.remove(+b.dataset.msx); });
    const last = this.lastId && this.box.querySelector(`[data-ms="${this.lastId}"]`);
    if (last) { last.scrollIntoView({ block: 'nearest' }); this.lastId = null; }
  }

  rowTip(r, i) {
    const whole = (x) => `${cap(t(WORDS[x.w] || x.w))}${x.id ? ` ${x.id}` : ''}${x.tip ? ` (${t(x.tip)})` : ''}`;
    return `#${i + 1} ${r.b ? `${whole(r.a)} ↔ ${whole(r.b)}` : whole(r.a)}\n${this.value(r)}${r.unit === 'mm' ? ' mm' : ''}${this.tail(r) ? ` · ${this.tail(r)}` : ''}\n${t('Click: copy, hide or delete it')}`;
  }

  /** A row clicked: chosen (its marks lit) and what to do with it suggested. */
  choose(id) {
    const list = this.rows(), i = list.findIndex((r) => r.id === id), r = list[i];
    if (!r) return;
    this.sel = this.sel === id ? null : id;
    this.render();
    if (!this.sel) { showSuggest(this.o.viewport, '', []); return; }
    const val = this.value(r);
    showSuggest(this.o.viewport, `📏 #${i + 1} ${this.what(r)} = ${val}`, [
      { icon: '📋', label: t('Copy the value'), title: val, run: () => this.copy(val.replace(/^[ØR]/, '').replace(/ mm²$|°$/, '')) },
      { icon: '📋', label: t('Copy the row'), run: () => this.copy(`${this.what(r)}\t${val}${r.unit === 'mm' ? ' mm' : ''}\t${this.tail(r)}`) },
      { icon: r.hide ? '👁' : '◌', label: t(r.hide ? 'Show its mark' : 'Hide its mark'), run: () => { r.hide = !r.hide; this.render(); this.o.changed?.(); this.choose(id); this.choose(id); } },
      { icon: '✕', label: t('Delete the measurement'), danger: true, run: () => this.remove(id) },
    ]);
  }

  /** The rows' marks in the view: a thin line, dots and a small label each (the hovered / chosen one lit). */
  draw() {
    const v = this.view();
    if (!v?.scene) return;
    if (!v.msGroup) { v.msGroup = new THREE.Group(); v.scene.add(v.msGroup); }
    v.clear(v.msGroup);
    v.invalidate();
    if (!this.marks || this.closed) return;
    this.rows().forEach((r, i) => {
      const lit = r.id === this.hot || r.id === this.sel;
      if (r.hide && !lit) return;
      const col = lit ? COL.hot : COL.mark, m = r.mark || {};
      for (const pl of m.lines || []) {
        if (pl.length < 2) continue;
        const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pl.map(V)), new THREE.LineBasicMaterial({ color: col, depthTest: false, transparent: true, opacity: lit ? 1 : 0.8 }));
        l.renderOrder = 13;
        v.msGroup.add(l);
      }
      if (m.dots?.length) {
        const d = new THREE.Points(new THREE.BufferGeometry().setFromPoints(m.dots.map(V)), new THREE.PointsMaterial({ color: col, size: lit ? 8 : 6, sizeAttenuation: false, depthTest: false }));
        d.renderOrder = 13;
        v.msGroup.add(d);
      }
      if (m.at) {
        const el = document.createElement('div');
        el.className = `ms-mark${lit ? ' on' : ''}`;
        el.dataset.noI18n = '';
        el.dataset.ms = r.id;
        el.innerHTML = `<i>${i + 1}</i>${this.valueHtml(r)}`;
        const lab = new CSS2DObject(el);
        lab.position.copy(V(m.at));
        v.msGroup.add(lab);
      }
    });
  }

  /** For the AI: the rows as data. */
  summary() {
    return this.rows().map((r, i) => ({ n: i + 1, what: this.what(r), value: r.text || r.v, unit: r.unit || undefined, ...(r.alt != null ? { min_gap: r.alt } : {}), details: this.tail(r) || undefined }));
  }

  /** The AI's measure: a row added between two things (or of one), the row returned. */
  addPair(A, B = null) {
    const row = B ? pair(A, B) : single(A);
    const id = this.add(row);
    return this.rows().find((r) => r.id === id);
  }

  /** Another doc on screen (a part / an assembly opened): its rows. */
  reset() { this.pend = null; this.sel = null; this.hot = null; this.closed = false; this.render(); }
}

function same(a, b) {
  if (a.kind !== b.kind) return false;
  if (a.kind === 'point') return V(a.p).distanceTo(V(b.p)) < 1e-6;
  return a.id === b.id;
}
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
/** The details: their words translated, the numbers kept. */
function trTail(s) { return s.split(' · ').map((x) => t(x)).join(' · '); }
