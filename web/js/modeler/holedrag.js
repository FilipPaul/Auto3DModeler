// A made hole dragged on its face (no tool on): grabbed with the left button, it follows the mouse, snapped like the
// Hole tool places one (facesnap.js: corners, edge middles, centres, the face's centre, other holes …, the snap
// filters; Shift / Alt = free); a light ring where it goes, the snap marked, its distances live. Let go: its place and
// what it is measured from change in one undo step. Esc while dragging: it stays where it was. A distance locked 🔒
// (typed, or the 🔒 in the hole's panel) holds: the hole moves only along the free one — both locked, not at all.
import { snapOnFace, snapDrawing } from './facesnap.js';
import { t } from '../i18n.js';

const GHOST = 0x7ee787, DIM = 0xd2a8ff;
const fmt = (v) => String(+(+v).toFixed(3));
const AXES = [['x', 0], ['y', 1]];

/** Is hole i's distance along axis ('x' / 'y') locked 🔒? */
export const holeLocked = (f, i, axis) => !!f.lock?.[i]?.[axis];

/** Lock (or free) hole i's distance along axis. */
export function setHoleLock(f, i, axis, on) {
  if (on) {
    f.lock = f.lock || [];
    while (f.lock.length < f.points.length) f.lock.push(null);
    f.lock[i] = { ...(f.lock[i] || {}), [axis]: true };
    return;
  }
  if (!f.lock?.[i]) return;
  delete f.lock[i][axis];
  if (!Object.keys(f.lock[i]).length) f.lock[i] = null;
  if (f.lock.every((x) => !x)) delete f.lock;
}

/** The hole of a Hole step under the mouse (on its face, seen from the front, not behind the part) -> {f, i, fr, p0,
 *  free: {x, y}} — free: which way it may move (its distance not locked) — or null. */
export function holeUnder(m, clientX, clientY) {
  const body = m.result?.body;
  if (!body || m.mode !== 'part' || m.cmd) return null;
  const ray = m.view.ray(clientX, clientY).ray, hit = m.view.pick(clientX, clientY);
  const far = hit ? ray.origin.distanceTo(hit.point) : Infinity, tol = Math.max(m.view.size * 2e-3, 1e-3);
  let best = null;
  for (const f of m.builtSteps()) {
    if (f.type !== 'hole' || f.suppressed || !f.plane?.frame || !f.points?.length) continue;
    const fr = m.holeFrame(f);
    if (!fr || ray.direction.x * fr.n[0] + ray.direction.y * fr.n[1] + ray.direction.z * fr.n[2] > -1e-6) continue; // (its face seen from behind)
    const uv = m.view.planePoint(clientX, clientY, fr);
    if (!uv) continue;
    const y = [fr.n[1] * fr.x[2] - fr.n[2] * fr.x[1], fr.n[2] * fr.x[0] - fr.n[0] * fr.x[2], fr.n[0] * fr.x[1] - fr.n[1] * fr.x[0]];
    const P = [0, 1, 2].map((k) => fr.o[k] + uv[0] * fr.x[k] + uv[1] * y[k]);
    const dist = Math.hypot(P[0] - ray.origin.x, P[1] - ray.origin.y, P[2] - ray.origin.z);
    if (dist > far + tol && !String(hit?.face?.name || '').startsWith(`${f.id}:`)) continue; // (behind something)
    const r = Math.max(Math.max(f.d || 5, f.head ? f.head_d || 0 : 0) / 2, m.view.mmPerPixel(fr) * 6);
    f.points.forEach((p, i) => {
      const d = Math.hypot(uv[0] - p[0], uv[1] - p[1]);
      if (d <= r && (!best || d < best.d)) best = { d, f, i, fr, p0: [...p], free: { x: !holeLocked(f, i, 'x'), y: !holeLocked(f, i, 'y') } };
    });
  }
  return best;
}

/** What the mouse says over a hole (the cursor hint): how it can be moved, or that it cannot. */
export function holeHint(g) {
  if (g.free.x && g.free.y) return `${g.f.name} — ${t('✥ drag to move the hole')}`;
  if (g.free.x) return `${g.f.name} — ${t('↔ drag to move the hole (↕ locked)')}`;
  if (g.free.y) return `${g.f.name} — ${t('↕ drag to move the hole (↔ locked)')}`;
  return `${g.f.name} — ${t('🔒 dimension locked')}`;
}

/** The face the hole step is on (the body's), for snapping. */
function holeFace(m, f, fr) {
  const name = f.plane.face?.name, tol = Math.max(m.view.size * 1e-5, 1e-4);
  const on = (x) => x.type === 'plane' && x.normal.every((v, k) => Math.abs(v - fr.n[k]) < 1e-6)
    && Math.abs((x.centroid[0] - fr.o[0]) * fr.n[0] + (x.centroid[1] - fr.o[1]) * fr.n[1] + (x.centroid[2] - fr.o[2]) * fr.n[2]) < tol;
  const fs = (m.view.body?.faces || []).filter(on);
  return fs.find((x) => name && (x.name === name || (x.names || []).includes(name))) || fs[0] || null;
}

/** The spot the dragged hole goes to under the mouse: snapped, a locked coordinate kept -> {uv, s} or null. */
function dragSpot(m, g, e) {
  const raw = m.view.planePoint(e.clientX, e.clientY, g.fr);
  if (!raw) return null;
  for (const [axis, k] of AXES) if (!g.free[axis]) raw[k] = g.p0[k];
  // the other holes of this step (not one measured from this one: it would go round in a circle)
  const extra = g.f.points.map((p, j) => ({ uv: p, kind: 'hole', hole: j }))
    .filter((x) => x.hole !== g.i && !AXES.some(([axis]) => g.f.from?.[x.hole]?.[axis]?.hole === g.i));
  let s = g.face ? snapOnFace(m.view, { face: g.face, fr: g.fr, uv: raw, mpp: m.view.mmPerPixel(g.fr), skip: `${g.f.id}:`, extra, free: !!(e.shiftKey || e.altKey) })
    : { uv: raw.map((v) => +v.toFixed(6)), kind: null, guides: [], keys: {} };
  if (AXES.some(([axis, k]) => !g.free[axis] && Math.abs(s.uv[k] - g.p0[k]) > 1e-6)) { // (a snap off the free line: only along it, on the grid)
    const uv = AXES.map(([axis, k]) => (g.free[axis] && !(e.shiftKey || e.altKey) ? Math.round(raw[k] / 0.5) * 0.5 : raw[k]));
    s = { uv: uv.map((v) => +v.toFixed(6)), kind: null, guides: [], keys: {} };
  }
  return { uv: s.uv, s };
}

/** Hole i of f moved to uv (s: the snap it came from): its new place and what each moved distance is measured from —
 *  onto the face's centre / a middle line: kept in the middle; onto another hole or a round edge: from it; else from
 *  what it was measured from (a middle, or an edge it went past: from the nearest edge now). Changes f. */
export function moveHole(m, f, i, uv, s) {
  const p0 = f.points[i], moved = AXES.filter(([, k]) => Math.abs(uv[k] - p0[k]) > 1e-9);
  f.points[i] = [...uv];
  if (!moved.length) return;
  const spec = f.from?.[i];
  if (spec) {
    const near = m.nearestEdges(f, uv);
    for (const [axis, k] of moved) {
      const r = spec[axis];
      if (!r) continue;
      if (r.mid) { if (near[axis]) spec[axis] = near[axis]; else delete spec[axis]; continue; }
      const c = m.refCoord(f, r, k), d = c === null || c === undefined ? null : +(uv[k] - c).toFixed(6);
      if (d === null) { if (near[axis]) spec[axis] = near[axis]; continue; }
      if (r.edge && !r.round && Math.sign(d) !== Math.sign(r.d) && Math.abs(d) > 1e-9 && near[axis]) spec[axis] = near[axis]; // (gone past its edge)
      else r.d = d;
    }
  }
  m.holeKeyRefs(f, i, s, moved.map(([axis]) => axis));
}

/** A hole drag: started once the mouse went a few pixels with the button down on a hole (holeUnder's g). */
export class HoleDrag {
  constructor(m, g) {
    Object.assign(this, { m, g, at: null, cancelled: false });
    g.face = holeFace(m, g.f, g.fr);
  }

  /** The mouse moved: the hole's new spot, its ring, the snap, the distances (and in the tip). */
  move(e) {
    const m = this.m, g = this.g, at = dragSpot(m, g, e);
    if (!at) return;
    this.at = at;
    const key = JSON.stringify([at.uv, at.s.kind, at.s.guides]);
    if (key === this.key) { m.tip({ x: e.clientX, y: e.clientY, text: this.text }); return; }
    this.key = key;
    const f = structuredClone(g.f), mpp = m.view.mmPerPixel(g.fr);
    moveHole(m, f, g.i, at.uv, at.s);
    const lines = [], labels = [], p = at.uv, draw = snapDrawing(at.s, mpp), said = [];
    const circles = [[p, (g.f.d || 5) / 2, GHOST], ...(g.f.head && g.f.head_d ? [[p, g.f.head_d / 2, GHOST]] : [])];
    for (const [axis, k] of AXES) {
      const r = f.from?.[g.i]?.[axis];
      const cs = r ? (r.mid ? r.mid.map((x) => m.edgeCoord(f, x, k)) : [m.refCoord(f, r, k)]) : [null];
      cs.forEach((c, j) => {
        const v = c === null || c === undefined ? p[k] : Math.abs(p[k] - c); // (no edge: from the face's 0, 0)
        const a = c === null || c === undefined ? null : k === 0 ? [c, p[1]] : [p[0], c];
        if (a) lines.push([a, p, DIM]);
        const el = document.createElement('div');
        el.className = 'sk-label hole-dim live';
        el.textContent = fmt(v);
        const mid = a || p;
        labels.push({ el, u: (mid[0] + p[0]) / 2 + (k === 1 ? mpp * 12 : 0), v: (mid[1] + p[1]) / 2 + (k === 0 ? mpp * 10 : 0) });
        if (!j) said.push(`${k ? '↕' : '↔'} ${fmt(v)}`); // (in the middle: one number per way at the mouse)
      });
    }
    this.text = said.join('  ');
    m.tip({ x: e.clientX, y: e.clientY, text: this.text });
    m.view.setSketch(g.fr, { lines: [...lines, ...draw.lines], circles: [...circles, ...draw.circles], dots: [[p, GHOST], ...draw.dots], labels: [...labels, ...draw.labels], grid: 0 });
  }

  /** Let go: the hole goes there (one undo step), its step chosen with its new numbers. */
  drop() {
    const m = this.m, g = this.g, at = this.at;
    this.end();
    if (this.cancelled || !at || AXES.every(([, k]) => Math.abs(at.uv[k] - g.p0[k]) < 1e-9)) return false;
    moveHole(m, g.f, g.i, at.uv, at.s);
    m.selectStep(g.f.id);
    m.commit();
    return true;
  }

  /** Esc: the hole stays where it was. */
  cancel() { this.cancelled = true; this.end(); }

  end() {
    const m = this.m;
    m.view.setSketch(null);
    m.tip(null);
    m.view.controls.enabled = true;
    if (m.holeDrag === this) m.holeDrag = null;
  }
}
