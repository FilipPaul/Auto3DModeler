// Sketch mode of the 3D model workspace: draw rectangles, lines and circles on a plane; every size shows a
// label — type a number to lock it 🔒 (it then holds while you drag or change other sizes), click 🔒 to free
// it again. The server's sketch solver (planegcs, /api/model/sketch/solve) keeps the locks and the drawn
// horizontal / vertical rules; everything else stays free and follows the mouse.
//
// Sketch JSON (see auto3d/modeler/constraints.py): points {id: [u, v]}, entities (line a-b, circle c r,
// g = drawn together), constraints (h / v of a line), dims (locked sizes: len, dia, dx, dy, dist; an end of a
// distance can be a fixed reference {ref: [u, v]} on an edge of the part the sketch is on). A block is an
// outline taken from a picture / DXF / PDF part {t: 'block', polys, w0, h0, at, scale}: rigid, moved by
// dragging, sized by its width.
import { t } from '../i18n.js';
import { showSuggest, fitFilterRow, snapKinds as partSnapKinds, setSnapKind } from '../suggest.js';
import { floatBox } from '../floatbox.js';
import { roundAxes } from './axes.js';
import { nextFrames } from '../frames.js';
import { nearRelations, shapeName, roundValue, standardShapes } from './sketchauto.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const nice = (x) => { const p = 10 ** Math.floor(Math.log10(x)); return [1, 2, 5, 10].map((k) => k * p).find((s) => s >= x); };
const ORIGIN = 'O';
const HV_DEG = 3; // a line drawn within 3° of horizontal / vertical becomes exactly that
const SOLVE_WAIT_MS = 20000; // a sketch solve that takes longer is given up (the editor stays usable)
const UNION_MAX = 400; // ∪ Union: the most pieces it trims (each a solve)
const AUTO_DIM_MS = 30000; // 🪄 Auto-dimension's most time (each size it tries is a solve)

/** An arc (centre c, from a counter-clockwise to b, radius |a - c|) as points from a to b. */
export function arcPts(c, a, b, stepDeg = 5) {
  const r = Math.hypot(a[0] - c[0], a[1] - c[1]), t0 = Math.atan2(a[1] - c[1], a[0] - c[0]);
  let sweep = (Math.atan2(b[1] - c[1], b[0] - c[0]) - t0) % (2 * Math.PI);
  if (sweep <= 1e-12) sweep += 2 * Math.PI;
  const n = Math.max(2, Math.ceil((sweep * 180) / Math.PI / stepDeg)), out = [];
  for (let i = 0; i <= n; i++) out.push([c[0] + r * Math.cos(t0 + (sweep * i) / n), c[1] + r * Math.sin(t0 + (sweep * i) / n)]);
  out[0] = [...a];
  out[n] = [...b];
  return out;
}

/** The arc through three points: start s, end e, and m on it -> {c, a, b} (counter-clockwise a -> b), or null. */
export function arcThrough(s, e, m) {
  const d = 2 * (s[0] * (e[1] - m[1]) + e[0] * (m[1] - s[1]) + m[0] * (s[1] - e[1]));
  if (Math.abs(d) < 1e-9) return null; // in a line
  const q = (p) => p[0] * p[0] + p[1] * p[1];
  const c = [(q(s) * (e[1] - m[1]) + q(e) * (m[1] - s[1]) + q(m) * (s[1] - e[1])) / d,
    (q(s) * (m[0] - e[0]) + q(e) * (s[0] - m[0]) + q(m) * (e[0] - s[0])) / d];
  const ang = (p) => Math.atan2(p[1] - c[1], p[0] - c[0]), tau = 2 * Math.PI, norm = (x) => ((x % tau) + tau) % tau;
  const ccw = norm(ang(m) - ang(s)) < norm(ang(e) - ang(s)); // going counter-clockwise from s, m comes before e
  return ccw ? { c, a: s, b: e, swap: false } : { c, a: e, b: s, swap: true };
}

/** The two lines meeting at a sketch point (a corner that can be rounded), or null. */
export function cornerLines(f, pid) {
  const ls = f.entities.filter((e) => e.t === 'line' && (e.a === pid || e.b === pid));
  if (ls.length !== 2 || f.entities.some((e) => e.t !== 'line' && (e.a === pid || e.b === pid || e.c === pid))) return null;
  const P = (id) => (id === 'O' ? [0, 0] : f.points[id]);
  const [u1, u2] = ls.map((l) => { const q = P(l.a === pid ? l.b : l.a), p = P(pid), L = Math.hypot(q[0] - p[0], q[1] - p[1]); return L ? [(q[0] - p[0]) / L, (q[1] - p[1]) / L, L] : null; });
  if (!u1 || !u2 || Math.abs(u1[0] * u2[1] - u1[1] * u2[0]) < 1e-6) return null; // in a straight line: no corner
  return { lines: ls, u1, u2 };
}

/** Round the corner at point pid with radius r: the two lines get shorter and an arc joins them, tangent to both.
 *  The sharp corner stays as a point on both lines (sizes measured to it still hold — a rectangle keeps its width;
 *  dimensions can still start from it). newId(prefix) gives free ids. -> the arc's id, or throws. */
export function roundCorner(f, pid, r, newId) {
  const c = cornerLines(f, pid);
  if (!c) throw new Error('Round a corner where exactly two lines meet.');
  const { lines: [l1, l2], u1, u2 } = c;
  const p = pid === 'O' ? [0, 0] : f.points[pid];
  const half = Math.acos(Math.max(-1, Math.min(1, u1[0] * u2[0] + u1[1] * u2[1]))) / 2;
  const t = r / Math.tan(half);
  if (!(r > 0) || t >= u1[2] - 1e-9 || t >= u2[2] - 1e-9) throw new Error('That radius is too big for these lines.');
  const T1 = [p[0] + u1[0] * t, p[1] + u1[1] * t], T2 = [p[0] + u2[0] * t, p[1] + u2[1] * t];
  const bx = u1[0] + u2[0], by = u1[1] + u2[1], bl = Math.hypot(bx, by), k = r / Math.sin(half);
  const C = [p[0] + (bx / bl) * k, p[1] + (by / bl) * k], mid = [C[0] - (bx / bl) * r, C[1] - (by / bl) * r];
  const geo = arcThrough(T1, T2, mid);
  const r6 = (q) => q.map((v) => +v.toFixed(9));
  const t1 = newId('p'); f.points[t1] = r6(T1);
  const t2 = newId('p'); f.points[t2] = r6(T2);
  const cc = newId('p'); f.points[cc] = r6(C);
  for (const [l, tp] of [[l1, t1], [l2, t2]]) {
    // a locked length of a line now runs to the sharp corner (not to the shortened end)
    // (the line's own size label goes — it is shorter now; a rectangle shows its size on the opposite side)
    const len = f.dims.find((d) => d.t === 'len' && d.e === l.id);
    if (len) Object.assign(len, { t: 'dist', a: pid, b: l.a === pid ? l.b : l.a, e: undefined });
    if (l.a === pid) l.a = tp; else l.b = tp;
    f.hidden = [...new Set([...(f.hidden || []), `len:${l.id}`])];
  }
  f.dims.forEach((d) => { if (d.e === undefined) delete d.e; });
  const id = newId('a');
  f.entities.push({ id, t: 'arc', c: cc, a: geo.swap ? t2 : t1, b: geo.swap ? t1 : t2 });
  f.constraints.push({ id: newId('k'), t: 'tan', e: l1.id, arc: id, p: t1 }, { id: newId('k'), t: 'tan', e: l2.id, arc: id, p: t2 },
    { id: newId('k'), t: 'corner', p: pid, lines: [l1.id, l2.id] });
  return id;
}

/** The arc that leaves s along direction d (unit) and ends at e (tangent to d at s) -> {c, a, b, swap}, or null when
 *  e is straight ahead / behind (no arc). */
export function tangentArc(s, d, e) {
  const n = [-d[1], d[0]], w = [e[0] - s[0], e[1] - s[1]], nw = n[0] * w[0] + n[1] * w[1];
  if (Math.abs(nw) < 1e-9 * (1 + Math.hypot(...w))) return null;
  const t = (w[0] * w[0] + w[1] * w[1]) / (2 * nw), c = [s[0] + n[0] * t, s[1] + n[1] * t];
  // the centre on the left of the way it goes: counter-clockwise from s to e
  return t > 0 ? { c, a: s, b: e, swap: false } : { c, a: e, b: s, swap: true };
}

// ------------------------------------------------------------------ pattern
export const PATTERN_MAX = 100; // copies in one ⁂ pattern
const entPts = (e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : e.t === 'spline' ? [...e.pts] : e.t === 'circle' ? [e.c] : []);

/** ⁂ Pattern: copies of the shapes `src` (entity ids: lines, circles, arcs, curves) in a row — {kind: 'row', n, d, e?}
 *  d apart along line e (else the sketch's X) — or around a point — {kind: 'around', n, c (a point id, 'O' the
 *  origin)}, spread evenly over 360°. A ⁂ Pattern relation (constraints.py `pat`) holds them: the same size and step,
 *  they follow the original. newId(prefix) gives free ids (kid: the relation's own). -> the relation; throws. */
export function makePattern(f, src, o, newId, kid = newId) {
  const P = (id) => (id === 'O' ? [0, 0] : f.points[id]);
  const ents = src.map((id) => f.entities.find((e) => e.id === id)).filter((e) => e && ['line', 'arc', 'circle', 'spline'].includes(e.t));
  if (!ents.length) throw new Error('Pick the shapes to repeat: lines, circles or arcs.');
  const n = Math.round(+o.n), around = o.kind === 'around';
  if (!(n >= 2 && n <= PATTERN_MAX)) throw new Error(`The count is 2 … ${PATTERN_MAX}.`);
  const pts = [...new Set(ents.flatMap(entPts))];
  let move, extra;
  if (around) {
    const c = o.c && P(o.c) ? o.c : 'O', C = P(c);
    if (pts.every((p) => Math.hypot(P(p)[0] - C[0], P(p)[1] - C[1]) < 1e-9)) throw new Error('Those shapes sit on the centre — choose another centre.');
    move = (q, i) => { const a = (2 * Math.PI * i) / n, x = q[0] - C[0], y = q[1] - C[1]; return [C[0] + x * Math.cos(a) - y * Math.sin(a), C[1] + x * Math.sin(a) + y * Math.cos(a)]; };
    extra = { c };
  } else {
    const d = +o.d, ln = o.e && f.entities.find((x) => x.id === o.e && x.t === 'line');
    if (!Number.isFinite(d) || !d) throw new Error('The spacing must not be zero.');
    let u = [1, 0];
    if (ln) { const a = P(ln.a), b = P(ln.b), L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (L > 1e-9) u = [(b[0] - a[0]) / L, (b[1] - a[1]) / L]; }
    move = (q, i) => [q[0] + u[0] * d * i, q[1] + u[1] * d * i];
    extra = { d, ...(ln ? { e: ln.id } : {}) };
  }
  const pairs = pts.map((p) => [p, []]), circles = ents.filter((e) => e.t === 'circle').map((e) => [e.id, []]), copies = [];
  for (let i = 1; i < n; i++) {
    const map = {};
    for (const [p, qs] of pairs) {
      if (around && p === extra.c) { map[p] = p; qs.push(p); continue; } // (the centre itself stays)
      map[p] = newId('p');
      f.points[map[p]] = move(P(p), i).map((v) => +v.toFixed(6));
      qs.push(map[p]);
    }
    const groups = {};
    for (const e of ents) {
      const id = newId(e.t === 'circle' ? 'c' : e.t === 'arc' ? 'a' : e.t === 'spline' ? 's' : 'l');
      const c = { ...e, id };
      if (e.g) c.g = groups[e.g] || (groups[e.g] = newId('r'));
      for (const k of ['a', 'b', 'c']) if (typeof e[k] === 'string') c[k] = map[e[k]];
      if (e.pts) c.pts = e.pts.map((q) => map[q]);
      f.entities.push(c);
      copies.push(id);
      if (e.t === 'circle') circles.find(([x]) => x === e.id)[1].push(id);
    }
  }
  const k = { id: kid('k'), t: 'pat', user: true, kind: around ? 'around' : 'row', n, ...extra, src: ents.map((e) => e.id), pairs, circles, copies };
  f.constraints.push(k);
  return k;
}

/** Take a ⁂ pattern's copies away (and its relation): their shapes, the points only they used, what held them. */
export function unmakePattern(f, k) {
  const gone = new Set(k.copies || []);
  f.entities = f.entities.filter((e) => !gone.has(e.id));
  const mine = new Set((k.pairs || []).flatMap(([p, qs]) => qs.filter((q) => q !== p)));
  const used = new Set(f.entities.flatMap(entPts));
  const lost = new Set([...mine].filter((q) => !used.has(q)));
  for (const q of lost) delete f.points[q];
  f.constraints = f.constraints.filter((c) => c.id !== k.id && ![c.e, c.e2, c.arc, ...(c.lines || [])].some((x) => gone.has(x)) && ![c.p, c.p2].some((x) => lost.has(x)));
  f.dims = f.dims.filter((d) => !gone.has(d.e) && !gone.has(d.e2) && !lost.has(d.a) && !lost.has(d.b));
}

// ------------------------------------------------------------------ smooth curves
/** A smooth curve (a spline) exactly through points in their order -> points along it (per = between two of them).
 *  A cubic spline over the distance along the points, as the kernel makes it (B-spline through the points). */
export function splinePts(P, per = 16) {
  if (P.length < 3) return P.map((p) => [...p]);
  const n = P.length, t = [0];
  for (let i = 1; i < n; i++) t.push(t[i - 1] + (Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]) || 1e-9));
  const coef = (k) => { // a natural cubic spline of coordinate k over t -> its second derivatives
    const y = P.map((p) => p[k]), m = new Array(n).fill(0), u = new Array(n).fill(0);
    for (let i = 1; i < n - 1; i++) {
      const sig = (t[i] - t[i - 1]) / (t[i + 1] - t[i - 1]), q = sig * m[i - 1] + 2;
      m[i] = (sig - 1) / q;
      u[i] = ((6 * ((y[i + 1] - y[i]) / (t[i + 1] - t[i]) - (y[i] - y[i - 1]) / (t[i] - t[i - 1]))) / (t[i + 1] - t[i - 1]) - sig * u[i - 1]) / q;
    }
    for (let i = n - 2; i >= 0; i--) m[i] = m[i] * m[i + 1] + u[i];
    return { y, m };
  };
  const cs = [coef(0), coef(1)], out = [];
  for (let i = 0; i < n - 1; i++) {
    const h = t[i + 1] - t[i];
    for (let s = 0; s < per; s++) {
      const a = 1 - s / per, b = s / per;
      out.push(cs.map(({ y, m }) => a * y[i] + b * y[i + 1] + ((a ** 3 - a) * m[i] + (b ** 3 - b) * m[i + 1]) * (h * h) / 6));
    }
  }
  out.push([...P[n - 1]]);
  return out;
}

// ------------------------------------------------------------------ trimming: where shapes cross
const TAU = 2 * Math.PI;
const angNorm = (x) => ((x % TAU) + TAU) % TAU;

/** A line / circle / arc of a sketch as plain geometry (P: point id -> [u, v]). */
function geomOf(e, P) {
  if (e.t === 'line') return { kind: 'line', a: P(e.a), b: P(e.b) };
  if (e.t === 'circle') return { kind: 'circle', c: P(e.c), r: e.r };
  if (e.t === 'arc') {
    const c = P(e.c), a = P(e.a), b = P(e.b), t0 = Math.atan2(a[1] - c[1], a[0] - c[0]);
    return { kind: 'arc', c, r: Math.hypot(a[0] - c[0], a[1] - c[1]), t0, sweep: angNorm(Math.atan2(b[1] - c[1], b[0] - c[0]) - t0) || TAU };
  }
  return null;
}

/** Where along a shape a point is: a line 0..1 from a to b, a circle 0..2π, an arc 0..its sweep from a. */
function paramOf(g, p) {
  if (g.kind === 'line') {
    const dx = g.b[0] - g.a[0], dy = g.b[1] - g.a[1];
    return ((p[0] - g.a[0]) * dx + (p[1] - g.a[1]) * dy) / (dx * dx + dy * dy || 1);
  }
  const t = angNorm(Math.atan2(p[1] - g.c[1], p[0] - g.c[0]) - (g.kind === 'arc' ? g.t0 : 0));
  return t;
}

function onShape(g, p, eps = 1e-7) {
  const t = paramOf(g, p);
  if (g.kind === 'line') return t > -eps && t < 1 + eps;
  if (g.kind === 'arc') return t < g.sweep + eps || t > TAU - eps;
  return true;
}

/** The points where two shapes cross. */
function crossings(g, h) {
  const out = [];
  const lineCircle = (L, C) => {
    const dx = L.b[0] - L.a[0], dy = L.b[1] - L.a[1], fx = L.a[0] - C.c[0], fy = L.a[1] - C.c[1];
    const A = dx * dx + dy * dy, B = 2 * (fx * dx + fy * dy), D = B * B - 4 * A * (fx * fx + fy * fy - C.r * C.r);
    if (A < 1e-18 || D < 0) return [];
    return [(-B - Math.sqrt(D)) / (2 * A), (-B + Math.sqrt(D)) / (2 * A)].filter((t, i, arr) => i === 0 || Math.abs(t - arr[0]) > 1e-12)
      .map((t) => [L.a[0] + t * dx, L.a[1] + t * dy]);
  };
  if (g.kind === 'line' && h.kind === 'line') {
    const r = [g.b[0] - g.a[0], g.b[1] - g.a[1]], s = [h.b[0] - h.a[0], h.b[1] - h.a[1]], den = r[0] * s[1] - r[1] * s[0];
    if (Math.abs(den) > 1e-12) {
      const q = [h.a[0] - g.a[0], h.a[1] - g.a[1]], t = (q[0] * s[1] - q[1] * s[0]) / den;
      out.push([g.a[0] + t * r[0], g.a[1] + t * r[1]]);
    }
  } else if (g.kind === 'line' || h.kind === 'line') {
    out.push(...(g.kind === 'line' ? lineCircle(g, h) : lineCircle(h, g)));
  } else {
    const d = Math.hypot(h.c[0] - g.c[0], h.c[1] - g.c[1]);
    if (d > 1e-12 && d <= g.r + h.r + 1e-12 && d >= Math.abs(g.r - h.r) - 1e-12) {
      const a = (g.r * g.r - h.r * h.r + d * d) / (2 * d), hh = Math.sqrt(Math.max(0, g.r * g.r - a * a));
      const m = [g.c[0] + (a * (h.c[0] - g.c[0])) / d, g.c[1] + (a * (h.c[1] - g.c[1])) / d];
      const ox = (-(h.c[1] - g.c[1]) * hh) / d, oy = ((h.c[0] - g.c[0]) * hh) / d;
      out.push([m[0] + ox, m[1] + oy]);
      if (hh > 1e-12) out.push([m[0] - ox, m[1] - oy]);
    }
  }
  return out.filter((p) => onShape(g, p) && onShape(h, p));
}

/** Relations the user sets between shapes: what each one needs picked (in order), its symbol and name. */
export const RELATIONS = {
  h: { icon: '─', name: 'Horizontal', picks: ['line'] },
  v: { icon: '│', name: 'Vertical', picks: ['line'] },
  par: { icon: '∥', name: 'Parallel', picks: ['line', 'line'] },
  perp: { icon: '⟂', name: 'Perpendicular', picks: ['line', 'line'] },
  eq: { icon: '=', name: 'Equal', picks: ['shape', 'shape'], hint: 'two lines (same length) or two circles / arcs (same size)' },
  conc: { icon: '◎', name: 'Concentric', picks: ['round', 'round'] },
  coin: { icon: '•', name: 'Coincident', picks: ['point', 'any'], hint: 'a point, then another point, a line or a circle it lies on' },
  tang: { icon: '⌒', name: 'Tangent', picks: ['shape', 'round'], hint: 'a line or a circle / arc, then a circle / arc it touches' },
  fix: { icon: '📌', name: 'Fix', picks: ['point'], hint: 'a point that stays where it is' },
  // made by the ⇋ Mirror tool (not in the Relations menu): the copy stays the mirror image of the original
  mir: { icon: '⇋', name: 'Mirrored', picks: [], tool: true },
  // made by the ⁂ Pattern tool: the copies keep the original's size and step (its symbol opens the count / spacing)
  pat: { icon: '⁂', name: 'Pattern', picks: [], tool: true },
  // made by the ⧈ Offset tool: the copy stays the distance away from its original (its ⧈ size label types it)
  off: { icon: '⧈', name: 'Offset', picks: [], tool: true },
};

const segDist = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L));
  return Math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]);
};

/** First-version sketches (rect / circle with their own size and centre) -> points, lines and circles. */
export function upgradeSketch(f) {
  const out = { ...f, points: { ...(f.points || {}) }, entities: [], constraints: [...(f.constraints || [])], dims: [...(f.dims || [])] };
  let n = 0;
  const pid = () => { while (out.points[`p${++n}`]); return `p${n}`; };
  let k = 0;
  const kid = (pre) => { while (out.entities.some((e) => e.id === `${pre}${++k}`) || out.constraints.some((c) => c.id === `${pre}${k}`)); return `${pre}${k}`; };
  for (const e of f.entities || []) {
    if (e.t === 'rect') {
      const hw = e.w / 2, hh = e.h / 2, g = kid('r');
      const ids = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => { const p = pid(); out.points[p] = [e.cx + a * hw, e.cy + b * hh]; return p; });
      ids.forEach((a, i) => {
        const id = kid('l');
        out.entities.push({ id, t: 'line', a, b: ids[(i + 1) % 4], g });
        out.constraints.push({ id: kid('k'), t: i % 2 ? 'v' : 'h', e: id });
      });
    } else if (e.t === 'circle' && !('c' in e)) {
      const p = pid();
      out.points[p] = [e.cx, e.cy];
      out.entities.push({ id: kid('c'), t: 'circle', c: p, r: e.d / 2 });
    } else out.entities.push(e);
  }
  // ids used twice (older versions gave the dx / dy locks of a point on the origin, or a slot's two sides, one id):
  // the later one gets a free id (what refers to that id keeps meaning the first, as it did)
  const all = new Set([...Object.keys(out.points), ...out.entities.flatMap((e) => [e.id, e.g]), ...out.constraints.map((c) => c.id), ...out.dims.map((d) => d.id)]);
  const seen = new Set();
  for (const key of ['entities', 'constraints', 'dims']) {
    out[key] = out[key].map((x) => {
      if (!seen.has(x.id)) { seen.add(x.id); return x; }
      const pre = String(x.id).replace(/\d+$/, '') || key[0];
      let i = 0;
      while (all.has(`${pre}${++i}`));
      all.add(`${pre}${i}`); seen.add(`${pre}${i}`);
      return { ...x, id: `${pre}${i}` };
    });
  }
  return out;
}

/** The circle through three points in 3D -> {c, r, n (unit normal)} or null (in a line). */
function circleOf(a, b, c) {
  const sub = (p, q) => [p[0] - q[0], p[1] - q[1], p[2] - q[2]], dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
  const cross = (p, q) => [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]];
  const ab = sub(b, a), ac = sub(c, a), n = cross(ab, ac), den = 2 * dot(n, n);
  if (den < 1e-18) return null;
  const t1 = cross(n, ab), t2 = cross(ac, n), kac = dot(ac, ac), kab = dot(ab, ab);
  const u = [0, 1, 2].map((i) => (kac * t1[i] + kab * t2[i]) / den), L = Math.sqrt(dot(n, n));
  return { c: [a[0] + u[0], a[1] + u[1], a[2] + u[2]], r: Math.sqrt(dot(u, u)), n: n.map((v) => v / L) };
}

/** A translated text with {name} values filled in. */
export const BIG_SKETCH = 200;
const DRAWING = new Set(['line', 'rect', 'circle', 'slot', 'spline', 'arc']); // (the tools that draw: points snap, the Snap groups are the ones in use)
const PART_SNAP = 0x4e9a5c; // the part's snap points near the mouse while drawing (the one caught: bright green) // a sketch of more shapes (e.g. from a PCB) labels only its locked sizes
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

export class Sketcher {
  /** m: the Modeler (view, frame(), toast, hint …) */
  constructor(m, feature, isNew) {
    this.m = m;
    this.f = upgradeSketch(feature);
    this.isNew = isNew;
    this.tool = isNew ? 'rect' : 'select';
    this.sel = null;     // {kind: 'point' | 'entity' | 'group', id}
    this.chain = null;   // line tool: the last point of the chain {id}, and the first one
    this.start = null;   // rect / circle: the first click {uv, id}
    this.cursor = null;  // snapped mouse position {uv, id}
    this.undo = [];
    this.solver = true;  // false when the sketch solver is not installed (sizes are then just set)
    this.dof = null;
  }

  get view() { return this.m.view; }
  frame() { return this.m.frame(); }
  P(id) { return id === ORIGIN ? [0, 0] : this.f.points[id]; }
  ent(id) { return this.f.entities.find((e) => e.id === id); }
  /** A free id. It also skips the ids it gave out before: several are often asked for before any is added to the
   *  sketch (the dx and dy locks of a point on the origin, a slot's two sides), and must differ. */
  newId(pre) {
    const used = new Set([...Object.keys(this.f.points), ...this.f.entities.flatMap((e) => [e.id, e.g]), ...this.f.constraints.map((c) => c.id), ...this.f.dims.map((d) => d.id)]);
    const given = this.givenIds || (this.givenIds = new Set());
    let n = 0;
    while (used.has(`${pre}${++n}`) || given.has(`${pre}${n}`));
    given.add(`${pre}${n}`);
    return `${pre}${n}`;
  }
  /** The sketch as it is (for undo / redo; on a face also its plane — its origin can move). */
  snapshot() { return structuredClone({ points: this.f.points, entities: this.f.entities, constraints: this.f.constraints, dims: this.f.dims, place: this.f.place || {}, rd: this.f.rd || {}, ...(this.f.plane?.face ? { plane: this.f.plane } : {}) }); }

  step() { this.undo.push(this.snapshot()); this.redo = []; } // (a new change: what was undone is gone)

  /** A size label the mouse can drag (as on a drawing sheet): its place is f.place[key] = at(uv) — an offset from the
   *  shape (mm) or an angle round a circle; `what` (lines, circles, points) lights up while the mouse is on it. */
  movable(lab, key, at, what, segs = []) {
    for (const [a, b] of segs) (this.dimHits || (this.dimHits = [])).push({ a, b, key, at, what }); // (its lines can be dragged too)
    const el = lab.el;
    el.classList.add('movable');
    el.addEventListener('mouseenter', () => { this.hoverSize = { key, what }; this.drawHighlight(); });
    el.addEventListener('mouseleave', () => { if (this.hoverSize?.key === key && !this.sizeDrag) { this.hoverSize = null; this.drawHighlight(); } });
    el.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0 || ev.target.closest('button, input')) return;
      ev.preventDefault();
      const x0 = ev.clientX, y0 = ev.clientY;
      let moved = false;
      const move = (e) => {
        if (!moved && Math.hypot(e.clientX - x0, e.clientY - y0) < 3) return;
        if (!moved) { moved = true; this.step(); this.sizeDrag = key; this.hoverSize = { key, what }; }
        const uv = this.m.view.planePoint(e.clientX, e.clientY, this.frame());
        if (!uv) return;
        const v = at(uv);
        this.f.place = { ...(this.f.place || {}), [key]: Array.isArray(v) ? v : +v.toFixed(4) };
        this.draw();
      };
      const up = () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        if (!moved) return;
        this.sizeDrag = null;
        this.noClickUntil = performance.now() + 300; // (the click that ends a drag does not open the value)
        this.changed();
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    });
    return lab;
  }
  back() {
    const s = this.undo.pop();
    if (!s) return;
    (this.redo || (this.redo = [])).push(this.snapshot());
    Object.assign(this.f, s);
    this.sel = null;
    this.chain = null;
    this.changed();
  }

  changed() {
    this.renderSuggest();
    if (this.isNew && this.f.entities.length && this.f.plane?.datum && this.m.$('.m-cmdbar [data-a^=plane-]')) this.m.renderCmdBar();
    this.m.renderProps();
    this.m.hint(this.hint());
    this.draw();
    this.refreshDof();
  }

  /** How many sizes are still free (after any change; asks the solver, nothing moves). */
  refreshDof() {
    clearTimeout(this.dofTimer);
    this.dofTimer = setTimeout(async () => {
      if (!this.solver || !this.f.entities.length) { if (this.dof !== null && !this.f.entities.length) { this.dof = null; this.m.renderProps(); } return; }
      const r = await this.solve();
      if (this.m.sk !== this) return;
      const { colours, dof } = this.takeState(r);
      if (colours) this.draw();
      if (dof) this.m.renderProps();
    }, 120);
  }

  /** The solver's word on the sketch as it is: the free count, which points / radii are free, and the locks and
   *  relations that do not fit (their shapes red) -> {colours, dof}: what changed (to draw / list again). */
  takeState(r) {
    const key = () => JSON.stringify([this.free ? [[...this.free.points], [...this.free.radii], [...(this.free.unknown || [])]] : null, [...(this.bad || [])]]);
    const was = key(), dofWas = this.dof, consWas = JSON.stringify(this.conflicts || []);
    if (r.free) this.free = { points: new Set(r.free.points), radii: new Set(r.free.radii), unknown: new Set(r.free.unknown || []) };
    if (r.conflicts) { this.conflicts = r.conflicts; this.conflicting = r.conflicting || r.conflicts; this.bad = this.badOf(r.conflicts); }
    if (r.dof !== undefined) this.dof = r.dof;
    return { colours: key() !== was, dof: this.dof !== dofWas || JSON.stringify(this.conflicts || []) !== consWas };
  }

  /** The shapes a list of lock / relation ids holds (drawn red when those do not fit). */
  badOf(ids) {
    const want = new Set(ids), out = new Set(), f = this.f;
    const byPoint = (p) => f.entities.filter((e) => [e.a, e.b, e.c, ...(e.pts || [])].includes(p)).map((e) => e.id);
    const ends = (x) => (typeof x === 'string' ? byPoint(x) : x?.mid ? [x.mid] : []);
    for (const d of f.dims) if (want.has(d.id)) [d.id, d.e, d.e2, ...ends(d.a), ...ends(d.b)].forEach((e) => e && out.add(e));
    for (const k of f.constraints) {
      if (!want.has(k.id)) continue;
      [k.e, k.e2, k.arc, ...(k.lines || [])].forEach((e) => e && out.add(e));
      for (const p of [k.p, k.p2]) if (p) byPoint(p).forEach((e) => out.add(e));
    }
    return out;
  }

  hint() {
    if (this.tool === 'rect') return this.start ? 'Click the second corner (Esc = stop drawing).' : 'Click the first corner of a rectangle.';
    if (this.tool === 'circle') return this.start ? 'Click to set the size (Esc = stop drawing).' : 'Click the centre of a circle.';
    if (this.tool === 'slot') return !this.start ? 'Click the centre of one round end of the slot.' : !this.slotEnd ? 'Click the centre of the other end.' : 'Move out to its width and click (Esc = stop drawing).';
    if (this.tool === 'round') return 'Round corner: click a corner where two lines meet, then type the radius.';
    if (this.tool === 'offset') return 'Offset: click a closed shape — a circle, an outline of lines / arcs, or a picture outline — then type the distance (negative = inside). The copy follows its original (a picture outline: a one-off copy).';
    if (this.tool === 'relate') {
      const r = RELATIONS[this.relType] || RELATIONS.par, k = (this.relPicks || []).length, want = r.picks[k];
      const what = { line: 'a line', round: 'a circle or an arc', shape: 'a line, a circle or an arc', point: 'a point', any: 'a point, a line or a circle' }[want];
      return `${r.icon} ${r.name}: click ${what}${k ? ' (the second)' : ''}${r.hint && !k ? ` — ${r.hint}` : ''}. Esc = stop.`;
    }
    if (this.tool === 'mirror' && this.mirSrc && !this.mirLine) return 'Mirror the picked shapes: click the line to mirror across — or choose the X / Y axis in the box.';
    if (this.tool === 'mirror') return this.mirLine ? 'Mirror: click the shapes to mirror (a rectangle or a joined outline goes whole). Esc = done.'
      : 'Mirror: click the line to mirror across — or choose the X / Y axis in the box.';
    if (this.tool === 'pattern') return 'Pattern: type the count and the spacing (Enter = done) — click a line to go along it, or a point / circle to go around it.';
    if (this.tool === 'extend') return 'Extend: click a line near the end to lengthen — up to the next shape it meets.';
    if (this.tool === 'trim') return 'Trim: click the piece of a line, circle or arc to cut away — up to where other shapes cross it.';
    if (this.tool === 'arc' && this.tan) return 'Tangent arc: it continues the line — click where it ends (Shift-click: a free arc; Esc = stop drawing).';
    if (this.tool === 'arc') return !this.start ? 'Click where the arc starts (at the end of a line: it continues the line smoothly).' : !this.arcEnd ? 'Click where the arc ends.' : 'Move the mouse to bend the arc, click to place it (Esc = stop drawing).';
    if (this.tool === 'spline') return this.spl ? 'Click the next point the curve goes through — click its first point to close it, double-click or Enter to finish, Esc to stop.' : 'Click where the smooth curve starts (a point or a line end joins it there).';
    if (this.tool === 'line') return this.chain ? 'Click the next point — click the first point to close the shape, double-click or Esc to stop.' : 'Click where the line starts.';
    if (this.tool === 'dim') return this.dimA ? 'Type its size and Enter — or click a second one for the distance between them (Esc = start again).' : 'Dimension: click a line or a circle for its size — or a point, a line or an edge of the part, then a second one for a distance.';
    if (this.tool === 'select' && this.merging) return 'Merge: click or drag a box over the shapes (each click adds one) — then ⛓ Join into one curve, 🧹 Simplify or ◆ One outline in the table. Esc = done.';
    if (this.tool === 'select' && (this.picks || []).length > 1) return 'Drag one of the picked shapes: they all move together · the table offers what fits them · Delete removes them.';
    return this.sel ? 'Drag to move it · click a size to type it and lock it 🔒 · Delete removes it.' : 'Click a shape or a corner to select it — or pick a drawing tool.';
  }

  setTool(t) {
    this.tool = t;
    this.merging = false; // (⛓ Merge ends with another tool, or Esc)
    this.picks = []; // (Esc, another tool: the suggestions go)
    this.relPicks = [];
    this.start = null;
    this.slotEnd = null;
    this.arcEnd = null;
    this.tan = null;
    this.chain = null;
    this.spl = null;
    this.dimA = null;
    this.closeChooser();
    this.mirLine = null;
    this.mirSrc = null;
    this.pat = null;
    if (t === 'mirror') { this.mirMove = false; this.mirrorChooser(); } // a copy unless asked (each time)
    if (t !== 'select') this.sel = null;
    this.m.renderCmdBar();
    this.changed();
  }

  // ------------------------------------------------------------------ geometry helpers
  mpp() { return this.view.mmPerPixel(this.frame()); }

  /** Snap (what the Snap filters at the bottom allow — snapKinds, and for the part under the sketch the 3D view's
   *  own Snap filters, shared: partSnapKinds): existing points / ends (they get connected), centres and the origin, a
   *  line's middle, the part's corners / edge middles / centres / quadrants, then a place on a sketch line / circle /
   *  arc (the new point stays on it) or on an edge of the part, then the guides, then the grid (off: just where the
   *  mouse is). Alt = no snapping. skip: a point (or a Set of points: a selection dragged together) not snapped to. */
  snap(uv, free = false, skip = null) {
    if (free) return { uv };
    const tol = this.mpp() * 9, S = this.snapKinds, out = skip instanceof Set ? (id) => skip.has(id) : (id) => id === skip;
    const centres = new Set(this.f.entities.filter((e) => e.t === 'circle' || e.t === 'arc').map((e) => e.c));
    let best = null;
    // a sketch point on the origin wins over the origin itself (so the new line joins it)
    for (const [id, p] of [...Object.entries(this.f.points).filter(([id]) => (centres.has(id) ? S.centre : S.ends)), ...(S.origin ? [[ORIGIN, [0, 0]]] : [])]) {
      if (out(id)) continue;
      const d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol && (!best || d < best.d)) best = { id, d, uv: [...p] };
    }
    if (best) return best;
    const lines = this.f.entities.filter((e) => e.t === 'line' && !out(e.a) && !out(e.b)); // (not the line being drawn from)
    if (S.mid) {
      for (const e of lines) {
        const a = this.P(e.a), b = this.P(e.b), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], d = Math.hypot(m[0] - uv[0], m[1] - uv[1]);
        if (d < tol && (!best || d < best.d)) best = { d, uv: m.map((v) => +v.toFixed(6)), on: e.id, mid: e.id };
      }
    }
    if (best) return best;
    for (const q of this.partSnaps()) { // (the part's corners, edge middles, centres, quadrants — what its filters allow)
      const d = Math.hypot(q.uv[0] - uv[0], q.uv[1] - uv[1]);
      if (d < tol && (!best || d < best.d)) best = { d, uv: [...q.uv], ref: true, refKind: q.kind };
    }
    if (best) return best;
    const R = S.edges ? this.refs() : { circles: [], lines: [] };
    const foot = (a, b) => { // the nearest place on a segment
      const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1, k = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
      return [a[0] + k * dx, a[1] + k * dy];
    };
    if (S.on) {
      for (const e of lines) { // on a line of the sketch: the point stays on it
        const p = foot(this.P(e.a), this.P(e.b)), d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
        if (d < tol * 0.8 && (!best || d < best.d)) best = { d, uv: p.map((v) => +v.toFixed(6)), on: e.id };
      }
    }
    if (S.on) {
      for (const e of this.f.entities) { // on a circle / arc of the sketch
        if (e.t !== 'circle' && e.t !== 'arc') continue;
        const c = this.P(e.c), r = e.t === 'circle' ? e.r : this.arcR(e), d0 = Math.hypot(uv[0] - c[0], uv[1] - c[1]);
        if (d0 < 1e-9 || Math.abs(d0 - r) >= tol * 0.8 || (best && Math.abs(d0 - r) >= best.d)) continue;
        const p = [c[0] + ((uv[0] - c[0]) * r) / d0, c[1] + ((uv[1] - c[1]) * r) / d0];
        if (e.t === 'arc' && this.arcDist(e, p) > tol * 0.5) continue; // (off the arc's own piece)
        best = { d: Math.abs(d0 - r), uv: p.map((v) => +v.toFixed(6)), on: e.id };
      }
    }
    if (best) return best;
    for (const [a, b] of R.lines) { // on a straight edge of the part
      const p = foot(a, b), d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol * 0.8 && (!best || d < best.d)) best = { d, uv: p.map((v) => +v.toFixed(6)), ref: true, edge: true };
    }
    if (best) return best;
    for (const q of R.circles) { // on a round edge of the part: the nearest point of it
      const d = Math.hypot(uv[0] - q.c[0], uv[1] - q.c[1]);
      if (d > 1e-9 && Math.abs(d - q.r) < tol && (!best || Math.abs(d - q.r) < best.d)) {
        best = { d: Math.abs(d - q.r), uv: [q.c[0] + ((uv[0] - q.c[0]) * q.r) / d, q.c[1] + ((uv[1] - q.c[1]) * q.r) / d].map((v) => +v.toFixed(6)), ref: true, onCircle: q };
      }
    }
    if (best) return best;
    const g = this.gridStep(), grid = S.grid ? [Math.round(uv[0] / g) * g, Math.round(uv[1] / g) * g] : [...uv]; // (Grid off: just where the mouse is)
    // guides: in line with a point (its x or its y — a corner, a line's middle, the origin) or on the extension of a
    // line; shown as dashed lines from what it lines up with while the mouse is there
    const keys = !S.guides ? [] : [...Object.entries(this.f.points).filter(([id]) => !out(id)).map(([, p]) => p), [0, 0],
      ...lines.map((e) => { const a = this.P(e.a), b = this.P(e.b); return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; })];
    let gx = null, gy = null;
    for (const p of keys) {
      const dx = Math.abs(p[0] - uv[0]), dy = Math.abs(p[1] - uv[1]);
      if (dx < tol && dy > tol && (!gx || dx < gx.d)) gx = { d: dx, v: p[0], from: p };
      if (dy < tol && dx > tol && (!gy || dy < gy.d)) gy = { d: dy, v: p[1], from: p };
    }
    let ext = null;
    if (S.guides) {
      for (const e of lines) { // beyond a line's end, along it
        const a = this.P(e.a), b = this.P(e.b), dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy;
        if (L2 < 1e-12) continue;
        const k = ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L2;
        if (k >= 0 && k <= 1) continue; // (on the line itself: snapped above)
        const p = [a[0] + k * dx, a[1] + k * dy], d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
        if (d < tol * 0.8 && (!ext || d < ext.d)) ext = { d, a, dir: [dx, dy], from: k < 0 ? a : b, p };
      }
    }
    const cut = (x, y) => { // where a line's extension meets x = … or y = …
      if (x !== null && Math.abs(ext.dir[0]) > 1e-9) { const k = (x - ext.a[0]) / ext.dir[0]; return [x, ext.a[1] + k * ext.dir[1]]; }
      if (y !== null && Math.abs(ext.dir[1]) > 1e-9) { const k = (y - ext.a[1]) / ext.dir[1]; return [ext.a[0] + k * ext.dir[0], y]; }
      return null;
    };
    let at = null, guides = [];
    if (gx && gy) { at = [gx.v, gy.v]; guides = [gx.from, gy.from]; }
    else if (ext && (gx || gy)) { at = cut(gx ? gx.v : null, gy ? gy.v : null) || ext.p; guides = [ext.from, (gx || gy).from]; }
    else if (ext) { at = ext.p; guides = [ext.from]; }
    else if (gx) { at = [gx.v, grid[1]]; guides = [gx.from]; }
    else if (gy) { at = [grid[0], gy.v]; guides = [gy.from]; }
    if (at) { const p = at.map((x) => +x.toFixed(6)); return { uv: p, guides: guides.map((q) => [[...q], p]) }; }
    return { uv: grid.map((x) => +x.toFixed(6)) };
  }

  gridStep() { return nice(this.mpp() * 12); }

  /** The part's points a drawn point can snap to, as the part's Snap filters allow (shared with the 3D view: turned
   *  off there, off here too): [{uv, kind: corner | midpoint | centre | quadrant}]. */
  partSnaps(K = partSnapKinds()) {
    const R = this.refs(), key = `${this._refsKey}|${K.corner}${K.midpoint}${K.centre}${K.quadrant}`;
    if (this._partSnapsKey === key) return this._partSnaps;
    const out = [];
    if (K.corner) for (const p of R.points) out.push({ uv: p, kind: 'corner' });
    if (K.midpoint) for (const [a, b] of R.lines) out.push({ uv: [+((a[0] + b[0]) / 2).toFixed(6), +((a[1] + b[1]) / 2).toFixed(6)], kind: 'midpoint' });
    if (K.centre) for (const q of [...R.circles, ...R.arcs]) out.push({ uv: q.c, kind: 'centre' });
    if (K.quadrant) for (const q of R.circles) for (const [x, y] of [[1, 0], [0, 1], [-1, 0], [0, -1]]) out.push({ uv: [+(q.c[0] + x * q.r).toFixed(6), +(q.c[1] + y * q.r).toFixed(6)], kind: 'quadrant' });
    this._partSnapsKey = key;
    this._partSnaps = out;
    return out;
  }

  /** A new point at a snapped place; on the origin it is locked there (shown as x 0 / y 0 🔒, can be freed). */
  pointAt(s) {
    if (s.id && s.id !== ORIGIN) return s.id;
    const id = this.newId('p');
    this.f.points[id] = [...s.uv];
    if (s.on && this.ent(s.on)) this.f.constraints.push({ id: this.newId('k'), t: s.mid ? 'mid' : 'on', p: id, e: s.on }); // (snapped onto a line / circle, or a line's middle: it stays there)
    if (s.id === ORIGIN) {
      this.f.dims.push({ id: this.newId('d'), t: 'dx', a: ORIGIN, b: id, v: 0 }, { id: this.newId('d'), t: 'dy', a: ORIGIN, b: id, v: 0 });
    }
    return id;
  }

  groupOf(e) { return e?.g ? this.f.entities.filter((x) => x.g === e.g) : e ? [e] : []; }

  pointsOfSel(sel = this.sel) {
    if (!sel) return [];
    if (sel.kind === 'point') return [sel.id];
    if (sel.kind === 'entity' && ['block', 'outline'].includes(this.ent(sel.id)?.t)) return [];
    const es = sel.kind === 'group' ? this.f.entities.filter((e) => e.g === sel.id) : [this.ent(sel.id)].filter(Boolean);
    return [...new Set(es.flatMap((e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : e.t === 'spline' ? e.pts : [e.c])))].filter((p) => p !== ORIGIN);
  }

  /** A smooth curve of the sketch -> points along it (sketch coordinates). */
  splineOf(e) { return splinePts((e.pts || []).map((id) => this.P(id)).filter(Boolean)); }

  /** What is under the mouse: a point, a line, a circle (edge or inside) or a rectangle (inside). */
  hit(uv) {
    const tol = this.mpp() * 7;
    let best = null;
    const consider = (d, sel) => { if (d < tol && (!best || d < best.d)) best = { d, sel }; };
    for (const [id, p] of Object.entries(this.f.points)) consider(Math.hypot(p[0] - uv[0], p[1] - uv[1]) * 0.6, { kind: 'point', id });
    for (const e of this.f.entities) {
      if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
        const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
        consider(Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]), e.g ? { kind: 'group', id: e.g } : { kind: 'entity', id: e.id });
      } else if (e.t === 'circle') {
        const c = this.P(e.c), d = Math.hypot(c[0] - uv[0], c[1] - uv[1]);
        consider(Math.abs(d - e.r), { kind: 'entity', id: e.id });
        if (d < e.r) consider(tol * 0.9, { kind: 'entity', id: e.id });
      } else if (e.t === 'arc') {
        consider(this.arcDist(e, uv), { kind: 'entity', id: e.id });
      } else if (e.t === 'spline') {
        const ps = this.splineOf(e);
        for (let i = 0; i + 1 < ps.length; i++) consider(segDist(uv, ps[i], ps[i + 1]), { kind: 'entity', id: e.id });
      }
    }
    for (const e of this.f.entities) {
      if (e.t !== 'block' && e.t !== 'outline') continue;
      for (const r of e.t === 'outline' ? this.outlineRings(e) : this.blockRings(e)) {
        for (let i = 0; i < r.length; i++) {
          const a = r[i], b = r[(i + 1) % r.length], dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
          const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
          consider(Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]), { kind: 'entity', id: e.id });
        }
      }
    }
    if (best) return best.sel;
    const blk = this.f.entities.find((e) => e.t === 'block' && this.inBlock(e, uv));
    if (blk) return { kind: 'entity', id: blk.id };
    // inside a rectangle (the smallest one)
    const groups = [...new Set(this.f.entities.filter((e) => e.g).map((e) => e.g))];
    let inside = null;
    for (const g of groups) {
      const ps = this.pointsOfSel({ kind: 'group', id: g }).map((p) => this.P(p));
      const xs = ps.map((p) => p[0]), ys = ps.map((p) => p[1]);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      if (uv[0] > x0 && uv[0] < x1 && uv[1] > y0 && uv[1] < y1) {
        const area = (x1 - x0) * (y1 - y0);
        if (!inside || area < inside.area) inside = { area, sel: { kind: 'group', id: g } };
      }
    }
    return inside?.sel || null;
  }

  arcOf(e) { return arcPts(this.P(e.c), this.P(e.a), this.P(e.b)); }
  arcR(e) { const c = this.P(e.c), a = this.P(e.a); return Math.hypot(a[0] - c[0], a[1] - c[1]); }
  arcDist(e, uv) {
    const ps = this.arcOf(e);
    let d = Infinity;
    for (let i = 0; i + 1 < ps.length; i++) d = Math.min(d, segDist(uv, ps[i], ps[i + 1]));
    return d;
  }

  // ------------------------------------------------------------------ solving
  /** detail: also which points are still free (for the colours) — a check per point, left out where only the
   *  count matters (🪄 tries many sizes one by one). */
  async solve(drag = null, keep = null, detail = !drag) {
    if (!this.solver) return { ok: true };
    let res, r;
    try { // (never waits for ever: a solve that does not come back is an error the caller shows)
      res = await fetch('/api/model/sketch/solve', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sketch: this.f, drag, keep, detail }), signal: AbortSignal.timeout(SOLVE_WAIT_MS) });
    } catch { return { ok: false, error: t('The sketch solver did not answer in time — try again, or undo the last change.') }; }
    try { r = await res.json(); } catch { return { ok: false, error: `The sketch could not be solved (server error ${res.status}).` }; }
    if (res.status === 501) { this.solver = false; this.m.toast(r.error, 'warning', 8000); return { ok: true }; }
    if (!res.ok) return { ok: false, error: r.error };
    return r;
  }

  apply(r) {
    if (r.points) for (const [k, v] of Object.entries(r.points)) if (this.f.points[k]) this.f.points[k] = v;
    if (r.radii) for (const [k, v] of Object.entries(r.radii)) { const e = this.ent(k); if (e) e.r = v; }
    this.takeState(r); // (the free count, the colours)
    for (const d of this.f.dims) if (d.free) d.v = +this.measure(d).toFixed(6);
  }

  /** Change the locks (dims) and solve; when the result contradicts other locks, go back and say which. exact: the
   *  held points must get where they are asked (a selection moved / turned / scaled as a whole), else it is refused. */
  async relock(mutate, hold = null, keep = null, { quiet = false, exact = false } = {}) {
    const before = structuredClone(this.f);
    this.step();
    mutate();
    const r = await this.solve(hold, keep);
    if (exact && hold && r.ok && r.held && !r.held.ok) {
      r.ok = false;
      r.conflicts = r.held.conflicts;
      const names = r.conflicts.map((id) => this.dimName(this.f.dims.find((d) => d.id === id))
        || ((k) => k && RELATIONS[k.t] ? `${RELATIONS[k.t].icon} ${t(RELATIONS[k.t].name)}` : '')(this.f.constraints.find((k) => k.id === id))).filter(Boolean);
      r.error = names.length ? tv('Locked sizes hold the selection where it is ({names}) — unlock one of them first.', { names: names.join(', ') })
        : t('Locked sizes hold the selection where it is — unlock them first.');
    }
    // a "solution" that shrinks a line or a circle to nothing means the rules contradict each other
    if (r.ok && r.points) {
      const P = (id) => (id === ORIGIN ? [0, 0] : r.points[id] || this.f.points[id]);
      const gone = this.f.entities.some((e) => (e.t === 'line' && Math.hypot(P(e.a)[0] - P(e.b)[0], P(e.a)[1] - P(e.b)[1]) < 0.01)
        || (e.t === 'circle' && (r.radii?.[e.id] ?? e.r) < 0.005));
      if (gone) {
        r.ok = false;
        const rel = this.f.constraints.filter((k) => k.user && !before.constraints.some((x) => x.id === k.id));
        r.error = t('These relations contradict each other (a line or circle would shrink to nothing) — remove one of them first.')
          + (rel.length ? ` (${rel.map((k) => `${RELATIONS[k.t]?.icon} ${t(RELATIONS[k.t]?.name || k.t)}`).join(', ')})` : '');
      }
    }
    if (!r.ok) {
      Object.assign(this.f, before);
      this.undo.pop();
      const names = (r.conflicts || []).map((id) => this.dimName(this.f.dims.find((d) => d.id === id))
        || ((k) => k && RELATIONS[k.t] ? `${RELATIONS[k.t].icon} ${t(RELATIONS[k.t].name)}` : '')(before.constraints.find((k) => k.id === id))).filter(Boolean);
      if (!quiet) {
        this.m.toast(r.error || (names.length ? `That does not fit the other locked sizes (${names.join(', ')}) — unlock one of them first.`
          : 'That does not fit the other locked sizes — unlock one of them first.'), 'error', 7000);
      }
    } else this.apply(r);
    this.changed();
    return !!r.ok;
  }

  dimName(d) {
    if (!d) return '';
    if (d.t === 'dia') return `Ø${fmt(d.v)}`;
    if (d.t === 'rad') return `R${fmt(d.v)}`;
    if (d.t === 'dx') return `x ${fmt(d.v)}`;
    if (d.t === 'dy') return `y ${fmt(d.v)}`;
    if (d.t === 'ang') return `${fmt(d.v)}°`;
    return fmt(d.v);
  }

  /** The value a size has now (locked or not). */
  measure(spec) {
    if (spec.t === 'bw') { const e = this.ent(spec.e); return e.w0 * (e.scale || 1); }
    if (spec.t === 'len') { const e = this.ent(spec.e), a = this.P(e.a), b = this.P(e.b); return Math.hypot(b[0] - a[0], b[1] - a[1]); }
    if (spec.t === 'dia') return 2 * this.ent(spec.e).r;
    if (spec.t === 'rad') return this.arcR(this.ent(spec.e));
    if (spec.t === 'ang') return Math.abs(this.signedAngle(spec));
    if (spec.t === 'pl') {
      const e = this.ent(spec.e), p = this.endUV(spec.a), a = this.P(e.a), b = this.P(e.b), L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      return Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / L;
    }
    const a = this.endUV(spec.a), b = this.endUV(spec.b);
    if (spec.t === 'dist') return Math.hypot(b[0] - a[0], b[1] - a[1]);
    return spec.t === 'dx' ? b[0] - a[0] : b[1] - a[1];
  }

  /** A line as a ray (rev: from b to a) -> its direction [du, dv]. */
  rayDir(id, rev) { const e = this.ent(id), a = this.P(e.a), b = this.P(e.b); return rev ? [a[0] - b[0], a[1] - b[1]] : [b[0] - a[0], b[1] - a[1]]; }

  /** The turn from an angle's first ray to its second (degrees, −180 … 180). */
  signedAngle(spec) {
    const p = this.rayDir(spec.e, spec.r1), q = this.rayDir(spec.e2, spec.r2);
    return (Math.atan2(p[0] * q[1] - p[1] * q[0], p[0] * q[0] + p[1] * q[1]) * 180) / Math.PI;
  }

  /** Where two lines (as infinite lines) cross -> [u, v], or null when they are parallel. */
  crossing(l1, l2) {
    const A = this.ent(l1), B = this.ent(l2), a = this.P(A.a), b = this.P(A.b), c = this.P(B.a), d = this.P(B.b);
    const r = [b[0] - a[0], b[1] - a[1]], s = [d[0] - c[0], d[1] - c[1]], den = r[0] * s[1] - r[1] * s[0];
    if (Math.abs(den) < 1e-9 * Math.hypot(...r) * Math.hypot(...s)) return null;
    const k = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den;
    return [a[0] + k * r[0], a[1] + k * r[1]];
  }

  /** The angle between two clicked lines: each taken from their crossing toward where it was clicked. */
  angleSpec(A, B) {
    const X = this.crossing(A.line, B.line);
    if (!X) return null;
    const rev = (id, at) => {
      const e = this.ent(id), a = this.P(e.a), b = this.P(e.b), d = [b[0] - a[0], b[1] - a[1]];
      let toward = at ? [at[0] - X[0], at[1] - X[1]] : null;
      if (!toward || Math.hypot(...toward) < 1e-6) { // (clicked at the crossing: its far end)
        const far = Math.hypot(a[0] - X[0], a[1] - X[1]) > Math.hypot(b[0] - X[0], b[1] - X[1]) ? a : b;
        toward = [far[0] - X[0], far[1] - X[1]];
      }
      return toward[0] * d[0] + toward[1] * d[1] < 0 ? 1 : 0;
    };
    const spec = { t: 'ang', e: A.line, e2: B.line, r1: rev(A.line, A.at), r2: rev(B.line, B.at) };
    spec.sg = this.signedAngle(spec) < 0 ? -1 : 1;
    return spec;
  }

  /** An end of a distance: a sketch point id, the origin, or a fixed reference {ref: [u, v]}. */
  endUV(x) {
    if (x && typeof x === 'object' && x.mid) { const e = this.ent(x.mid); if (!e) return null; const a = this.P(e.a), b = this.P(e.b); return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; }
    return x && typeof x === 'object' ? x.ref : this.P(x);
  }

  /** A circle / arc's size shown as its radius ('r') or diameter ('d') — f.rd, by default Ø for a circle, R for an arc. */
  roundAs(id) { const e = this.ent(id); return this.f.rd?.[id] || (e?.t === 'arc' ? 'r' : 'd'); }

  /** What a typed value of `spec` is times the size it locks (a circle shown as R: ½; an arc shown as Ø: 2). */
  shownFactor(spec) {
    if (spec?.t === 'dia' && this.roundAs(spec.e) === 'r') return 0.5;
    if (spec?.t === 'rad' && this.roundAs(spec.e) === 'd') return 2;
    return 1;
  }

  /** Show a circle / arc's size the other way (R ⇄ Ø). */
  flipRound(id) {
    this.f.rd = { ...(this.f.rd || {}), [id]: this.roundAs(id) === 'r' ? 'd' : 'r' };
    this.changed();
  }

  /** Ctrl+Y: what Ctrl+Z took back, again. */
  forward() {
    const s = this.redo?.pop();
    if (!s) return;
    this.undo.push(this.snapshot());
    Object.assign(this.f, s);
    this.sel = null;
    this.chain = null;
    this.changed();
  }

  /** What a click may take in ⬚ Select, ↔ Dimension, ⟂ Relations (the Select filters at the bottom; remembered). */
  get pickable() {
    if (!this._pickable) {
      let saved = null;
      try { saved = JSON.parse(localStorage.getItem('a3d.skpick') || 'null'); } catch { saved = null; }
      this._pickable = { points: true, mid: true, origin: true, lines: true, round: true, edges: true, ...(saved || {}) };
    }
    return this._pickable;
  }

  /** Where a drawn (or dragged) point may land (the Snap filters at the bottom; remembered): points / ends, midpoints,
   *  centres, the origin, on lines / curves, the part's edges / corners, guides, the grid. */
  get snapKinds() {
    if (!this._snapKinds) {
      let saved = null;
      try { saved = JSON.parse(localStorage.getItem('a3d.sksnap') || 'null'); } catch { saved = null; }
      this._snapKinds = { ends: true, mid: true, centre: true, origin: true, on: true, edges: true, guides: true, grid: true, ...(saved || {}) };
      delete this._snapKinds.part; // (one toggle for the whole part before: now the part's own kinds)
    }
    return this._snapKinds;
  }

  /** The filter row at the bottom of the view: Snap (where a drawn point lands) and Select (what a click takes) —
   *  toggles, remembered; fitted to the view (suggest.js fitFilterRow). */
  renderFilters() {
    const vp = this.m.els.viewport;
    let bar = vp.querySelector(':scope > .sk-filters:not(.snap-filters)'); // (not the 3D view's row: it goes when a sketch opens)
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'sk-filters';
      for (const ev of ['pointerdown', 'pointerup', 'click']) bar.addEventListener(ev, (x) => x.stopPropagation());
      vp.appendChild(bar);
    }
    const SN = [['ends', '•', 'Points', "Snap to the sketch's points: line ends, corners (a new line joins them). Click to switch"],
      ['mid', '⊹', 'Midpoints', 'Snap to the middle of a line (the point stays there). Click to switch'],
      ['centre', '◎', 'Centres', 'Snap to the centre of a circle or arc of the sketch. Click to switch'],
      ['origin', '⊕', 'Origin', 'Snap to the origin (0, 0). Click to switch'],
      ['on', '⟋', 'On shapes', 'Snap anywhere on a line, circle or arc of the sketch (the point stays on it). Click to switch'],
      ['guides', '┆', 'Guides', "Catch in line with a point or on a line's extension (dashed green lines). Click to switch"],
      ['grid', '▦', 'Grid', 'Snap to the grid; off: a point lands exactly where you click. Click to switch']];
    const PK = partSnapKinds(), PT = [['corner', '⌜', 'Corners', "Snap to the part's corners"],
      ['midpoint', '⊹', 'Edge midpoints', "Snap to the middle of the part's straight edges"],
      ['centre', '◎', 'Centres', "Snap to the centres of the part's holes, round edges and arcs"],
      ['quadrant', '◔', 'Quadrants', "Snap to the 4 quadrant points of the part's round edges (right, top, left, bottom)"],
      ['edges', '⟋', 'Edges', 'Snap anywhere on an edge of the part (the point lands on it)']];
    const onPart = !!this.m.result?.body, alt = t('hold Alt for no snapping');
    const F = [['points', '•', 'Points'], ['mid', '⊹', 'Midpoints'], ['origin', '⊕', 'Origin'], ['lines', '╱', 'Lines'], ['round', '◯', 'Circles / arcs'], ['edges', '┅', 'Part edges']];
    const drawing = DRAWING.has(this.tool);
    bar.innerHTML = `<span class="skf-g skf-snap${drawing ? ' active' : ''}"><span class="skf-t" title="${t('Where a point you draw lands — hold Alt for no snapping at all')}">${t('Snap')}:</span>${SN.map(([k, i, l, w]) => `<button class="${this.snapKinds[k] ? 'on' : ''}" data-sksnap="${k}" title="${t(l)}: ${t(w)} (${alt})">${i} <span class="skf-l">${t(l)}</span></button>`).join('')}</span>
      ${onPart ? `<span class="sep"></span><span class="skf-g skf-part${drawing ? ' active' : ''}"><span class="skf-t" title="${t("The part under the sketch: what a drawn point snaps to on it — the same choice as the 3D view's Snap row")}">${t('On the part')}:</span>${PT.map(([k, i, l, w]) => {
    const on = k === 'edges' ? this.snapKinds.edges : PK[k];
    return `<button class="${on ? 'on' : ''}" data-skpart="${k}" title="${t(l)}: ${t(w)} — ${t('click to switch')} (${alt})">${i} <span class="skf-l">${t(l)}</span></button>`;
  }).join('')}</span>` : ''}
      <span class="sep"></span><span class="skf-g skf-pick${drawing ? '' : ' active'}"><span class="skf-t" title="${t('What a click takes in ⬚ Select, ↔ Dimension and ⟂ Relations')}">${t('Select')}:</span>${F.map(([k, i, l]) => `<button class="${this.pickable[k] ? 'on' : ''}" data-f="${k}" title="${t(l)}: ${t('Click to pick these — or not')}">${i} <span class="skf-l">${t(l)}</span></button>`).join('')}</span>`;
    for (const b of bar.querySelectorAll('[data-f]')) {
      b.addEventListener('click', () => {
        this.pickable[b.dataset.f] = !this.pickable[b.dataset.f];
        try { localStorage.setItem('a3d.skpick', JSON.stringify(this.pickable)); } catch { /* private window */ }
        this.hover = null;
        this.renderFilters();
        this.draw();
      });
    }
    for (const b of bar.querySelectorAll('[data-skpart]')) {
      b.addEventListener('click', () => {
        const k = b.dataset.skpart;
        if (k === 'edges') {
          this.snapKinds.edges = !this.snapKinds.edges;
          try { localStorage.setItem('a3d.sksnap', JSON.stringify(this.snapKinds)); } catch { /* private window */ }
        } else setSnapKind(k, !partSnapKinds()[k]); // (the 3D view's choice too)
        this.cursor = null;
        this.renderFilters();
        this.draw();
      });
    }
    for (const b of bar.querySelectorAll('[data-sksnap]')) {
      b.addEventListener('click', () => {
        this.snapKinds[b.dataset.sksnap] = !this.snapKinds[b.dataset.sksnap];
        try { localStorage.setItem('a3d.sksnap', JSON.stringify(this.snapKinds)); } catch { /* private window */ }
        this.cursor = null;
        this.renderFilters();
        this.draw();
      });
    }
    fitFilterRow(bar);
    if (!vp.skFit && window.ResizeObserver) (vp.skFit = new ResizeObserver(() => fitFilterRow(vp.querySelector(':scope > .sk-filters:not(.snap-filters)')))).observe(vp);
  }

  // ------------------------------------------------------------------ 🪄 auto-dimension
  /** The sizes worth locking, best first: each shape's own sizes, then where it is — from the nearest edges of the
   *  part (a hole from the outer edges closest to it), else from the origin — then anything left from the origin. */
  autoDimCandidates() {
    const f = this.f, R = this.refs(), P = (id) => this.P(id), out = [];
    const hv = (e, t) => f.constraints.some((k) => k.e === e.id && k.t === t);
    // shapes joined by their points (a rectangle, an outline) are placed once
    const ends = (e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : e.t === 'circle' ? [e.c] : []);
    const left = new Set(f.entities.filter((e) => e.t !== 'block').map((e) => e.id)), clusters = [];
    while (left.size) {
      const first = f.entities.find((e) => left.has(e.id)), group = [first], pts = new Set(ends(first));
      left.delete(first.id);
      for (let grew = true; grew;) {
        grew = false;
        for (const e of f.entities) {
          if (!left.has(e.id) || !ends(e).some((p) => pts.has(p) && p !== ORIGIN)) continue;
          group.push(e);
          ends(e).forEach((p) => pts.add(p));
          left.delete(e.id);
          grew = true;
        }
      }
      clusters.push({ ents: group, pts: [...pts].filter((p) => p !== ORIGIN) });
    }
    // of a shape's points and the part's vertical / horizontal edges, the closest pair (else that point from the origin)
    const nearest = (pts, dir) => {
      let best = null;
      R.lines.forEach(([a, b], i) => {
        const isV = Math.abs(a[0] - b[0]) < 1e-7, isH = Math.abs(a[1] - b[1]) < 1e-7;
        if (dir === 'x' ? !isV : !isH) return;
        for (const p of pts) {
          const d = dir === 'x' ? Math.abs(a[0] - P(p)[0]) : Math.abs(a[1] - P(p)[1]);
          if (!best || d < best.d - 1e-9) best = { d, p, end: { ref: a, ...(R.lineIds[i] ? { edge: R.lineIds[i] } : {}) } };
        }
      });
      return best ? { t: dir === 'x' ? 'dx' : 'dy', a: best.end, b: best.p } : { t: dir === 'x' ? 'dx' : 'dy', a: ORIGIN, b: pts[0] };
    };
    for (const c of clusters) {
      // its sizes
      for (const e of c.ents) {
        if (e.t === 'circle') out.push({ t: 'dia', e: e.id });
        else if (e.t === 'arc') out.push({ t: 'rad', e: e.id });
      }
      const lines = c.ents.filter((e) => e.t === 'line'), mid = (e, k) => (P(e.a)[k] + P(e.b)[k]) / 2;
      const hs = lines.filter((e) => hv(e, 'h')).sort((p, q) => mid(p, 1) - mid(q, 1)), vs = lines.filter((e) => hv(e, 'v')).sort((p, q) => mid(p, 0) - mid(q, 0));
      // a side that runs into an arc is as long as the arc lets it: the arc's centre is the size worth locking
      const arcEnds = new Set(c.ents.filter((e) => e.t === 'arc').flatMap((e) => [e.a, e.b]));
      const plain = (e) => !arcEnds.has(e.a) && !arcEnds.has(e.b);
      for (const e of [...hs, ...vs].filter(plain)) out.push({ t: 'len', e: e.id }); // the bottom and left first: a rectangle's width and height
      // an arc of its own (not a rounded corner) is placed by its centre, from the part's nearest edges or the origin
      const corner = new Set(f.constraints.filter((k) => k.t === 'corner').flatMap((k) => k.lines || []));
      for (const e of c.ents.filter((x) => x.t === 'arc' && c.ents.length > 1)) {
        if (f.constraints.some((k) => k.t === 'tan' && k.arc === e.id && corner.has(k.e))) continue;
        out.push(nearest([e.c], 'x'), nearest([e.c], 'y'));
      }
      // where it is: a circle / arc by its centre, other shapes by their corner nearest each edge of the part
      const circle = c.ents.find((e) => e.t === 'circle' || e.t === 'arc');
      const pts = circle && c.ents.length === 1 ? [circle.c] : [...c.pts].sort((p, q) => P(p)[0] + P(p)[1] - P(q)[0] - P(q)[1]);
      if (pts.length) out.push(nearest(pts, 'x'), nearest(pts, 'y'));
      for (const e of [...hs, ...vs].filter((x) => !plain(x))) out.push({ t: 'len', e: e.id });
      for (const e of lines.filter((x) => !hv(x, 'h') && !hv(x, 'v'))) out.push({ t: 'dx', a: e.a, b: e.b }, { t: 'dy', a: e.a, b: e.b }, { t: 'len', e: e.id });
    }
    // anything still free: its points from the origin
    for (const c of clusters) for (const p of c.pts) out.push({ t: 'dx', a: ORIGIN, b: p }, { t: 'dy', a: ORIGIN, b: p });
    return out;
  }

  /** 🪄 Lock the sizes the sketch still needs to be fully defined. First the relations it nearly has already (H / V,
   *  tangent, equal radius — sketchauto.nearRelations), then sizes (autoDimCandidates); each tried and kept only when
   *  it fixes something and fits the others, so no lock is held twice. round: each size locked at a nice value (whole
   *  mm) — the shapes move to it, listed in the panel to keep or take back. Never silent: a toast says what was locked,
   *  which shapes are still free, or which locks do not fit. -> {added: [names], dof, free: [shape names], error?}. */
  async autoDimension({ round = false } = {}) {
    const say = (text, kind, ms = 6000) => { this.m.toast(text, kind, ms); return text; };
    if (!this.solver) return { added: [], dof: null, free: [], error: say(t('Auto-dimension needs the sketch solver.'), 'warning') };
    let r = await this.solve(null, null, false), notes = [];
    // a lock held twice at the value it has (the others fix it already) is not an error: it becomes a reference
    const twice = r.ok || r.conflicting?.length ? [] : this.f.dims.filter((d) => !d.free && (r.redundant || []).includes(d.id));
    if (twice.length) {
      this.step();
      twice.forEach((d) => { d.free = true; });
      r = await this.solve(null, null, false);
      if (r.ok) notes = twice.map((d) => this.dimName(d)); else { this.undo.pop(); twice.forEach((d) => { delete d.free; }); }
    }
    if (!r.ok) {
      const names = this.ruleNames(r.conflicting?.length ? r.conflicting : r.conflicts || []);
      return { added: [], dof: r.dof ?? null, free: [], error: say(r.error || (names.length ? tv('The sketch does not solve as it is: {names} do not fit together — remove or change one of them first.', { names: names.join(', ') })
        : t('The sketch does not solve as it is — fix it first.')), 'error', 8000) };
    }
    if (notes.length) say(tv('{names}: held twice (the other sizes fix it already) — now a reference dimension, it only measures.', { names: notes.join(', ') }), 'info', 8000);
    let dof = r.dof ?? 0;
    if (dof <= 0) {
      if (notes.length) { this.apply(r); this.changed(); return { added: [], references: notes, dof, free: [] }; }
      return { added: [], dof, free: [], error: say(t('The sketch is fully defined already.'), 'info', 3000) };
    }
    if (!notes.length) this.step(); // (one undo step with the references made above)
    const added = [], rels = [], rounded = [], P = (id) => this.P(id), drawn = structuredClone(this.f.points);
    /** A size as it was drawn (before 🪄 rounded others and the shapes moved): what the rounded list says it was. */
    const asDrawn = (c) => { const now = this.f.points; this.f.points = drawn; try { return this.measure(c); } finally { this.f.points = now; } };
    let late = false;
    const until = performance.now() + AUTO_DIM_MS; // (a big sketch: what is done by then stays, the rest is said)
    /** Put x into list, solve: kept when it lowers the free count, fits, and moves no point more than `most`. */
    const tryOne = async (list, x, most = Infinity) => {
      list.push(x);
      const res = await this.solve(null, null, false);
      const moved = res.ok && res.points ? Math.max(0, ...Object.entries(res.points).map(([k, v]) => (this.f.points[k] ? Math.hypot(v[0] - this.f.points[k][0], v[1] - this.f.points[k][1]) : 0))) : 0;
      if (!res.ok || (res.dof ?? dof) >= dof || moved > most) { list.pop(); return false; }
      dof = res.dof;
      this.apply(res);
      return true;
    };
    try {
      // the relations it nearly has (a hair off): before any size, so no size locks what a relation means
      for (const k of nearRelations(this.f, P)) {
        if (dof <= 0) break;
        if (performance.now() > until) { late = true; break; }
        const rule = { id: this.newId('k'), ...k };
        if (await tryOne(this.f.constraints, rule, 0.05)) rels.push(...this.ruleNames([rule.id]));
      }
      for (const c of this.autoDimCandidates()) {
        if (dof <= 0) break;
        if (performance.now() > until) { late = true; break; }
        const had = this.findDim(c);
        if (had && !had.free) continue;
        const now = +this.measure(c).toFixed(6);
        if (!Number.isFinite(now) || (['len', 'dia', 'rad', 'dist'].includes(c.t) && !(now > 1e-9))) continue;
        const v = round ? roundValue(now, c.t) : now;
        if (had) { // a reference dimension: it drives now
          delete had.free;
          had.v = v;
          const res = await this.solve(null, null, false);
          if (!res.ok || (res.dof ?? dof) >= dof) { had.free = true; had.v = now; continue; }
          dof = res.dof;
          this.apply(res);
        } else if (!(await tryOne(this.f.dims, { id: this.newId('d'), ...c, v }))) continue;
        added.push(this.dimName({ ...c, v }));
        const was = round ? asDrawn(c) : v;
        if (round && Math.abs(v - was) > 1e-6) rounded.push({ name: this.dimName({ ...c, v }), from: this.dimName({ ...c, v: was }) });
      }
    } catch (e) { // (never silent: say what stopped it)
      say(tv('🪄 Auto-dimension stopped: {why}', { why: e.message || e }), 'error', 8000);
    }
    if (!added.length && !rels.length && !notes.length) this.undo.pop();
    r = await this.solve();
    if (r.ok) this.apply(r);
    this.rounded = round && rounded.length ? rounded : null; // (the panel lists them: keep, or take back)
    this.changed();
    // what is still free, by name (the solver's free points)
    const free = dof > 0 ? this.f.entities.filter((e) => this.stateOf(e) === 'free').map((e) => shapeName(e, P)) : [];
    if (rels.length) say(tv('Relations the sketch nearly had, added: {names}', { names: rels.join(', ') }), 'info', 8000);
    if (late) say(t('🪄 Auto-dimension took too long on this sketch — the sizes locked so far stay; click it again to go on.'), 'warning', 8000);
    else if (dof <= 0) say(tv('{n} size(s) locked — the sketch is fully defined.', { n: added.length }), 'ok');
    else if (free.length) say(tv('{n} size(s) locked — still free: {names}. Lock their sizes by hand, or add relations.', { n: added.length, names: free.slice(0, 3).join('; ') + (free.length > 3 ? ' …' : '') }), 'warning', 9000);
    else say(tv('{n} size(s) locked — {k} still free (lock them by hand, or add relations).', { n: added.length, k: dof }), 'warning', 9000);
    return { added, ...(rels.length ? { relations: rels } : {}), ...(notes.length ? { references: notes } : {}), dof, free, ...(late ? { error: 'it took too long — the sizes locked so far stay' } : {}) };
  }

  /** Locks and relations by id -> their names as the panel shows them ("R23", "⌒ Tangent", "Horizontal"). */
  ruleNames(ids, cons = this.f.constraints) {
    const own = { on: 'On a shape', corner: 'Corner', mid: 'Midpoint' };
    return ids.map((id) => {
      const d = this.f.dims.find((x) => x.id === id);
      if (d) return this.dimName(d);
      const k = cons.find((x) => x.id === id);
      if (!k) return '';
      const rel = RELATIONS[k.t === 'tan' ? 'tang' : k.t]; // (a tangent arc's own tangent is the same relation)
      return rel ? `${rel.icon} ${t(rel.name)}` : t(own[k.t] || k.t);
    }).filter(Boolean);
  }

  findDim(spec) {
    const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
    return this.f.dims.find((d) => d.t === spec.t && (spec.e ? d.e === spec.e && (d.e2 ?? null) === (spec.e2 ?? null) && (spec.a === undefined || same(d.a, spec.a))
      : same(d.a, spec.a) && same(d.b, spec.b)));
  }

  /** Type a value: the size is locked at it. Holds the point it is measured from, so it grows from there. */
  async setSize(spec, value) {
    if (spec.t === 'bw') { this.sel = { kind: 'entity', id: spec.e }; this.setBlock('w', value); return; }
    let v = parseFloat(String(value).replace(',', '.'));
    if (!Number.isFinite(v) || (['len', 'dia', 'rad', 'dist', 'pl', 'ang'].includes(spec.t) && v <= 0)) {
      this.m.toast('A size must be greater than zero.', 'error');
      return;
    }
    if (spec.t === 'ang' && v >= 180) { this.m.toast('An angle is between 0 and 180°.', 'error'); return; }
    let hold = null;
    if (spec.t === 'dx' || spec.t === 'dy') {
      const cur = this.measure(spec);
      if (v > 0 && cur < 0) v = -v; // "12 to the left" stays to the left
    }
    // a distance is measured from a (it stays) to b (it moves): hold a when it is a sketch point
    if (['dx', 'dy', 'dist'].includes(spec.t) && typeof spec.a === 'string' && spec.a !== ORIGIN && this.f.points[spec.a]) hold = { [spec.a]: this.P(spec.a) };
    if (spec.t === 'len') { const e = this.ent(spec.e); if (e.a !== ORIGIN) hold = { [e.a]: this.P(e.a) }; }
    if (spec.t === 'ang' || spec.t === 'pl') { const e = this.ent(spec.e); hold = { [e.a]: this.P(e.a), [e.b]: this.P(e.b) }; } // its (first) line stays
    if (spec.t === 'dia' || spec.t === 'rad') {
      // a radius changes only its own circle / arc: everything else stays (a rounded corner's sharp corner too, so
      // the rounding slides along its lines); a circle keeps its centre
      const e = this.ent(spec.e), tangent = this.f.constraints.some((k) => k.t === 'tan' && k.arc === e.id);
      const own = new Set(e.t === 'circle' ? [] : tangent ? [e.a, e.b, e.c] : [e.a, e.b]); // a tangent arc's centre moves
      hold = Object.fromEntries(Object.keys(this.f.points).filter((k) => !own.has(k)).map((k) => [k, this.P(k)]));
    }
    if (!this.solver) { this.setDirect(spec, v); return; }
    await this.relock(() => {
      const d = this.findDim(spec);
      if (d) { d.v = v; delete d.free; } else this.f.dims.push({ id: this.newId('d'), ...spec, v });
      this.unhide(spec);
    }, hold, this.keepFor(spec));
  }

  /** A typed size along x keeps every point's y (and the other way round), when the sketch allows it. */
  keepFor(spec) {
    if (spec.t === 'dx') return 'v';
    if (spec.t === 'dy') return 'u';
    const a = spec.t === 'len' ? this.ent(spec.e) : spec.t === 'dist' ? spec : null;
    if (!a) return null;
    const p = this.endUV(a.a), q = this.endUV(a.b);
    if (!p || !q) return null;
    return Math.abs(p[1] - q[1]) < 1e-7 ? 'v' : Math.abs(p[0] - q[0]) < 1e-7 ? 'u' : null;
  }

  /** Without the solver: set the size directly (no locks). */
  setDirect(spec, v) {
    this.step();
    if (spec.t === 'dia') this.ent(spec.e).r = v / 2;
    else if (spec.t === 'rad') {
      const e = this.ent(spec.e), c = this.P(e.c);
      for (const k of [e.a, e.b]) {
        const p = this.P(k), L = Math.hypot(p[0] - c[0], p[1] - c[1]) || 1;
        if (this.f.points[k]) this.f.points[k] = [c[0] + ((p[0] - c[0]) / L) * v, c[1] + ((p[1] - c[1]) / L) * v];
      }
    } else if (spec.t === 'len') {
      const e = this.ent(spec.e), a = this.P(e.a), b = this.P(e.b), L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      this.f.points[e.b] = [a[0] + ((b[0] - a[0]) / L) * v, a[1] + ((b[1] - a[1]) / L) * v];
    } else {
      const p = this.f.points[spec.b], a = this.P(spec.a);
      if (p) p[spec.t === 'dx' ? 0 : 1] = a[spec.t === 'dx' ? 0 : 1] + v;
    }
    this.changed();
  }

  async toggleLock(spec) {
    const d = this.findDim(spec);
    // a shape's own size: unlocked = no dimension; a dimension you added: unlocked = it only measures (🔓)
    if (d && (d.t === 'len' || d.t === 'dia' || d.t === 'rad')) await this.relock(() => { this.f.dims = this.f.dims.filter((x) => x !== d); });
    else if (d && !d.free) await this.relock(() => { d.free = true; });
    else if (d) await this.relock(() => { delete d.free; d.v = +this.measure(d).toFixed(6); });
    else await this.relock(() => this.f.dims.push({ id: this.newId('d'), ...spec, v: +this.measure(spec).toFixed(6) }));
  }

  // ------------------------------------------------------------------ hiding a shape's own sizes
  sizeKey(spec) { return `${spec.t}:${spec.e}`; }
  isHidden(spec) { return (this.f.hidden || []).includes(this.sizeKey(spec)); }
  unhide(spec) { if (spec.e) this.f.hidden = (this.f.hidden || []).filter((k) => k !== this.sizeKey(spec)); }

  /** ✕ on a shape's size: no lock on it any more, and its label is not shown (↔ Dimension on it brings it back). */
  async hideSize(spec) {
    await this.relock(() => {
      this.f.dims = this.f.dims.filter((d) => !(d.t === spec.t && d.e === spec.e));
      this.f.hidden = [...new Set([...(this.f.hidden || []), this.sizeKey(spec)])];
    });
  }

  /** The sizes ✕ hid (not the lengths of lines shortened by a rounded corner — those stay hidden). */
  userHidden() {
    const rounded = new Set(this.f.constraints.filter((c) => c.t === 'corner').flatMap((c) => c.lines.map((l) => `len:${l}`)));
    return (this.f.hidden || []).filter((k) => !rounded.has(k));
  }

  async showAllSizes() { const keep = new Set(this.userHidden()); await this.relock(() => { this.f.hidden = this.f.hidden.filter((k) => !keep.has(k)); }); }

  deleteSel() {
    const many = (this.picks || []).filter((q) => ['line', 'circle', 'arc', 'spline'].includes(q.kind));
    if (!this.sel && !many.length) return;
    this.step();
    const s = many.length > 1 || !this.sel ? { kind: 'many' } : this.sel;
    let gone;
    if (s.kind === 'many') gone = new Set(many.map((q) => q.id)); // (picked by a box or Ctrl+click)
    else if (s.kind === 'point') {
      gone = new Set(this.f.entities.filter((e) => e.a === s.id || e.b === s.id || e.c === s.id).map((e) => e.id));
      for (const e of this.f.entities) if (e.t === 'spline' && e.pts.includes(s.id)) { e.pts = e.pts.filter((p) => p !== s.id); if (e.pts.length < 2) gone.add(e.id); }
    }
    else gone = new Set(s.kind === 'group' ? this.f.entities.filter((e) => e.g === s.id).map((e) => e.id) : [s.id]);
    this.f.entities = this.f.entities.filter((e) => !gone.has(e.id));
    this.f.constraints = this.f.constraints.filter((c) => !gone.has(c.e) && !gone.has(c.arc) && !(c.lines || []).some((l) => gone.has(l))
      && !(s.kind === 'point' && c.p === s.id && c.t === 'corner') && !(c.t === 'off' && !c.pairs.some(([o, q]) => !gone.has(o) && !gone.has(q))));
    const used = new Set([...this.f.entities.flatMap((e) => [e.a, e.b, e.c, ...(e.pts || [])]), ...this.f.constraints.filter((c) => c.t === 'corner').map((c) => c.p)]);
    for (const p of Object.keys(this.f.points)) if (!used.has(p)) delete this.f.points[p];
    this.f.dims = this.f.dims.filter((d) => !gone.has(d.e) && (!d.a || d.a === ORIGIN || this.f.points[d.a]) && (!d.b || this.f.points[d.b]));
    this.sel = null;
    this.picks = [];
    this.changed();
  }

  /** A shape as a pick of the suggestions (what a click on it would give). */
  pickOf(e) {
    if (e.t === 'line') {
      const a = this.P(e.a), b = this.P(e.b);
      return { kind: 'line', id: e.id, t: { kind: 'line', line: e.id, a: e.a, b: e.b, uvA: a, uvB: b, dir: Math.abs(a[1] - b[1]) < 1e-7 ? 'h' : Math.abs(a[0] - b[0]) < 1e-7 ? 'v' : 's', at: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] } };
    }
    if (e.t === 'circle' || e.t === 'arc') return { kind: e.t, id: e.id, t: { kind: 'point', end: e.c, uv: this.P(e.c), [e.t]: e.id } };
    if (e.t === 'spline') { const ps = this.splineOf(e); return { kind: 'spline', id: e.id, t: { kind: 'spline', spline: e.id, at: ps[Math.floor(ps.length / 2)] } }; }
    return null;
  }

  /** The smooth curve (spline) within reach of uv -> {e, d} or null. */
  splineAt(uv) {
    let best = null;
    for (const e of this.f.entities) {
      if (e.t !== 'spline') continue;
      const ps = this.splineOf(e);
      for (let i = 0; i + 1 < ps.length; i++) { const d = segDist(uv, ps[i], ps[i + 1]); if (d < this.mpp() * 8 && (!best || d < best.d)) best = { e, d }; }
    }
    return best;
  }

  /** The points of joined curves (⛓ Join, 🧹 Simplify: `fit` splines, often hundreds of points) not shown or caught
   *  unless their curve is selected — the curve is one shape. */
  hiddenPts() {
    const shown = this.sel?.kind === 'entity' && !this.mg ? this.sel.id : null, out = new Set(); // (one clicked: its points, to drag)
    for (const e of this.f.entities) if (e.t === 'spline' && e.fit && e.id !== shown) for (const q of e.pts.slice(1, -1)) out.add(q);
    return out;
  }

  /** The shapes a selection box takes (screen corners): dragged right to left — every shape it touches; left to
   *  right — only the shapes wholly inside it. */
  boxPicks(x0, y0, x1, y1) {
    const L = Math.min(x0, x1), R = Math.max(x0, x1), T = Math.min(y0, y1), B = Math.max(y0, y1), crossing = x1 < x0;
    const fr = this.frame(), scr = (p) => this.view.uvToScreen(fr, p), inside = ([x, y]) => x >= L && x <= R && y >= T && y <= B;
    const pts = (e) => { // its points along it (dense enough to find a crossing)
      const along = (ps) => ps.flatMap((p, i) => (i ? Array.from({ length: 8 }, (_, k) => [ps[i - 1][0] + (p[0] - ps[i - 1][0]) * (k + 1) / 8, ps[i - 1][1] + (p[1] - ps[i - 1][1]) * (k + 1) / 8]) : [p]));
      if (e.t === 'line') return along([this.P(e.a), this.P(e.b)]);
      if (e.t === 'circle') { const c = this.P(e.c); return Array.from({ length: 64 }, (_, k) => [c[0] + e.r * Math.cos((k / 64) * 2 * Math.PI), c[1] + e.r * Math.sin((k / 64) * 2 * Math.PI)]); }
      if (e.t === 'arc') return along(this.arcOf(e));
      if (e.t === 'spline') return this.splineOf(e);
      return [];
    };
    const out = [];
    for (const e of this.f.entities) {
      const s = pts(e).map(scr);
      if (!s.length) continue;
      if (crossing ? s.some(inside) : s.every(inside)) { const q = this.pickOf(e); if (q) out.push(q); }
    }
    return out;
  }

  // ------------------------------------------------------------------ mouse
  down(e) {
    if (this.tool !== 'select' && this.tool !== 'dim') return null;
    const uv = this.view.planePoint(e.clientX, e.clientY, this.frame());
    const grab = uv && this.dimHitAt(uv);
    if (grab) return { size: grab, x0: e.clientX, y0: e.clientY, moved: false }; // a dimension by its line
    if (this.tool !== 'select') return null;
    const h = uv && this.hit(uv);
    if (!h) return { box: true, x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY, add: e.ctrlKey || e.metaKey || this.merging, moved: false }; // a selection box (⛓ Merge: adds)
    if ((this.picks || []).length > 1 && this.inPicks(h)) { // one of several picked: they all go together, the grabbed point snaps
      const ids = this.pickPoints(), own = h.kind === 'point' ? [h.id] : this.pointsOfSel(h).filter((id) => ids.includes(id));
      const grab = own.sort((a, b) => Math.hypot(this.P(a)[0] - uv[0], this.P(a)[1] - uv[1]) - Math.hypot(this.P(b)[0] - uv[0], this.P(b)[1] - uv[1]))[0];
      if (ids.length) return { uv0: uv, ids, grab, from: Object.fromEntries(ids.map((id) => [id, [...this.P(id)]])), moved: false, group: true };
    }
    this.sel = h;
    this.changed();
    const blk = h.kind === 'entity' && this.ent(h.id)?.t === 'block' ? this.ent(h.id) : null;
    if (blk) return { uv0: uv, block: blk, from: [...blk.at], moved: false };
    const ids = this.pointsOfSel(h);
    return { uv0: uv, ids, from: Object.fromEntries(ids.map((id) => [id, [...this.P(id)]])), moved: false, snapshot: structuredClone(this.f), unpick: !(e.ctrlKey || e.metaKey) };
  }

  async move(e, drag) {
    if (drag?.box) { // the selection box follows the mouse: right to left touching (green, dashed), left to right inside (blue)
      Object.assign(drag, { x1: e.clientX, y1: e.clientY });
      if (!drag.moved && Math.hypot(drag.x1 - drag.x0, drag.y1 - drag.y0) < 4) return;
      drag.moved = true;
      const vp = this.m.els.viewport, vr = vp.getBoundingClientRect();
      let el = vp.querySelector(':scope > .sk-box');
      if (!el) { el = document.createElement('div'); el.className = 'sk-box'; vp.appendChild(el); }
      el.classList.toggle('crossing', drag.x1 < drag.x0);
      Object.assign(el.style, { left: `${Math.min(drag.x0, drag.x1) - vr.left}px`, top: `${Math.min(drag.y0, drag.y1) - vr.top}px`,
        width: `${Math.abs(drag.x1 - drag.x0)}px`, height: `${Math.abs(drag.y1 - drag.y0)}px` });
      return;
    }
    const uv = this.view.planePoint(e.clientX, e.clientY, this.frame());
    if (!uv) return;
    if (drag?.size) { // a dimension dragged by its line: its place, as when its label is dragged
      if (!drag.moved && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 3) return;
      if (!drag.moved) { drag.moved = true; this.step(); this.sizeDrag = drag.size.key; this.hoverSize = { key: drag.size.key, what: drag.size.what }; }
      const v = drag.size.at(uv);
      this.f.place = { ...(this.f.place || {}), [drag.size.key]: Array.isArray(v) ? v : +v.toFixed(4) };
      this.draw();
      return;
    }
    if (drag?.block) {
      const g = e.altKey || !this.snapKinds.grid ? 0 : this.gridStep();
      let du = uv[0] - drag.uv0[0], dv = uv[1] - drag.uv0[1];
      if (g) { du = Math.round(du / g) * g; dv = Math.round(dv / g) * g; }
      if (!drag.moved && (du || dv)) { drag.moved = true; this.step(); }
      drag.block.at = [+(drag.from[0] + du).toFixed(6), +(drag.from[1] + dv).toFixed(6)];
      this.draw();
      return;
    }
    if (drag) {
      let du = uv[0] - drag.uv0[0], dv = uv[1] - drag.uv0[1];
      if (drag.group && drag.grab && !e.altKey) { // a picked group: its grabbed point snaps (what the Snap row allows), the rest follow
        const g = drag.from[drag.grab], s = this.snap([g[0] + du, g[1] + dv], false, new Set(drag.ids));
        du = s.uv[0] - g[0];
        dv = s.uv[1] - g[1];
        this.dragGuides = s.guides || null;
      } else if (drag.ids.length === 1 && !e.altKey) { // a single point snaps to the grid / other points
        const s = this.snap([drag.from[drag.ids[0]][0] + du, drag.from[drag.ids[0]][1] + dv], false, drag.ids[0]);
        du = s.uv[0] - drag.from[drag.ids[0]][0];
        dv = s.uv[1] - drag.from[drag.ids[0]][1];
      } else if (!e.altKey && this.snapKinds.grid) { const g = this.gridStep(); du = Math.round(du / g) * g; dv = Math.round(dv / g) * g; }
      const target = Object.fromEntries(drag.ids.map((id) => [id, [drag.from[id][0] + du, drag.from[id][1] + dv]]));
      if (!drag.moved && (du || dv)) { drag.moved = true; this.step(); if (drag.unpick && this.picks?.length) { this.picks = []; this.renderSuggest(); } } // (an unpicked shape dragged: the picks go)
      if (!drag.moved) return;
      drag.pending = target;
      if (drag.busy) return; // one solve at a time; the last position wins
      drag.busy = true;
      while (drag.pending) {
        const t = drag.pending;
        drag.pending = null;
        if (this.solver) {
          const r = await this.solve(t);
          if (r.ok || r.points) this.apply(r);
        } else for (const [k, v] of Object.entries(t)) this.f.points[k] = v;
        this.draw();
      }
      drag.busy = false;
      return;
    }
    this.cursor = this.snap(uv, e.altKey);
    const hv = this.tool === 'offset' ? ((l) => l && { kind: 'entity', id: l.ids[0], loop: l.ids, key: `off:${l.ids.join(',')}` })(this.loopAt(uv))
      : this.tool === 'trim' ? ((p) => p && { kind: 'piece', pts: p.pts, key: `${p.e.id}:${p.lo}:${p.hi}` })(this.pieceAt(uv))
      : this.tool === 'extend' ? ((x) => x && { kind: 'piece', grow: true, pts: [x.from, x.to], key: `ext:${x.e.id}:${x.end}` })(this.extensionAt(uv))
      : this.tool === 'round' ? this.cornerAt(uv)
      : this.tool === 'dim' || this.tool === 'relate' ? this.pickTarget(uv)
      : this.tool === 'select' ? ((h) => (h?.kind === 'point' ? { kind: 'point', end: h.id, uv: this.P(h.id) } : h))(this.hit(uv))
      : this.cursor.id || this.cursor.ref || this.cursor.on ? { kind: 'point', end: this.cursor.ref ? { ref: this.cursor.uv } : this.cursor.id || null, uv: this.cursor.uv,
        ...(this.cursor.mid ? { mid: this.cursor.mid } : this.cursor.on ? { onShape: this.ent(this.cursor.on)?.t } : this.cursor.edge || this.cursor.onCircle ? { onShape: 'edge' } : this.cursor.refKind ? { refKind: this.cursor.refKind } : {}) } : null;
    const key = hv?.key || JSON.stringify(hv && { ...hv, d: undefined });
    const changed = key !== this.hoverKey;
    this.hover = hv;
    this.hoverKey = key;
    if (this.tool !== 'select' || changed) this.draw();
    this.view.renderer.domElement.style.cursor = this.tool === 'select' ? (this.hit(uv) ? 'move' : '') : 'crosshair';
  }

  /** The dimension whose line is under the mouse (its dimension line, leader or arc) -> {key, at, what} or null. */
  dimHitAt(uv) {
    const tol = this.mpp() * 5;
    let best = null;
    for (const h of this.dimHits || []) {
      const d = segDist(uv, h.a, h.b);
      if (d < tol && (!best || d < best.d)) best = { d, ...h };
    }
    return best;
  }

  async up(drag) {
    if (drag?.box) {
      this.m.els.viewport.querySelector(':scope > .sk-box')?.remove();
      if (!drag.moved) return;
      const got = this.boxPicks(drag.x0, drag.y0, drag.x1, drag.y1), had = drag.add ? this.picks || [] : [];
      this.picks = [...had, ...got.filter((q) => !had.some((x) => x.kind === q.kind && x.id === q.id))]; // (Ctrl: added to what is picked)
      this.sel = null;
      this.sgMore = null; // (a new pick: the short list)
      this.changed();
      return;
    }
    if (drag?.size) { this.sizeDrag = null; if (drag.moved) { this.hoverSize = null; this.changed(); } return; }
    if (!drag) return;
    while (drag.busy) await new Promise((r) => setTimeout(r, 15));
    if (!drag.moved) return;
    if (drag.group) { this.dragGuides = null; this.refreshPicks(); }
    this.changed();
  }

  click(e) {
    const uv0 = this.view.planePoint(e.clientX, e.clientY, this.frame());
    if (!uv0) return;
    if (this.tool === 'select') {
      const item = this.pickItem(uv0);
      if ((e.ctrlKey || e.metaKey || this.merging) && item) { // Ctrl+click (⛓ Merge: any click): one more (or one less)
        const i = (this.picks || []).findIndex((q) => q.kind === item.kind && q.id === item.id);
        this.picks = i >= 0 ? this.picks.filter((_, k) => k !== i) : [...(this.picks || []), item];
      } else { this.sel = this.hit(uv0); this.picks = item ? [item] : []; }
      this.sgMore = null; // (a new pick: the short list)
      this.changed();
      return;
    }
    if (this.tool === 'dim') { this.dimClick(uv0, e); return; }
    const s = this.snap(uv0, e.altKey);
    if (this.tool === 'line') { this.linePoint(s, e.detail >= 2); return; }
    if (this.tool === 'spline') { this.splinePoint(s, e.detail >= 2); return; }
    if (this.tool === 'arc') { this.arcPoint(s, e.shiftKey); return; }
    if (this.tool === 'round') { this.roundAt(uv0); return; }
    if (this.tool === 'trim') { this.trimAt(uv0); return; }
    if (this.tool === 'extend') { this.extendAt(uv0); return; }
    if (this.tool === 'relate') { this.relateClick(uv0); return; }
    if (this.tool === 'offset') { this.offsetAt(uv0, e); return; }
    if (this.tool === 'mirror') { this.mirrorClick(uv0); return; }
    if (this.tool === 'pattern') { this.patternClick(uv0); return; }
    if (this.tool === 'slot') { this.slotPoint(s); return; }
    if (!this.start) { this.start = s; this.m.hint(this.hint()); this.draw(); return; }
    const a = this.start;
    this.start = null;
    if (this.tool === 'rect') this.addRect(a, s);
    else this.addCircle(a, s);
  }

  addRect(a, b) {
    const [u0, v0] = a.uv, [u1, v1] = b.uv;
    if (Math.abs(u1 - u0) < 1e-9 || Math.abs(v1 - v0) < 1e-9) { this.changed(); return; }
    this.step();
    const g = this.newId('r');
    // corners in order from the first click; the first corner may be an existing point (connected)
    const p1 = this.pointAt(a);
    const ids = [p1];
    for (const uv of [[u1, v0], [u1, v1], [u0, v1]]) { const id = this.newId('p'); this.f.points[id] = uv; ids.push(id); }
    if (b.id && b.id !== ORIGIN) { delete this.f.points[ids[2]]; ids[2] = b.id; }
    ids.forEach((p, i) => {
      const id = this.newId('l');
      this.f.entities.push({ id, t: 'line', a: p, b: ids[(i + 1) % 4], g, ...this.consFlag() });
      this.f.constraints.push({ id: this.newId('k'), t: i % 2 ? 'v' : 'h', e: id });
    });
    this.sel = { kind: 'group', id: g };
    this.changed();
  }

  /** ⊂⊃ Slot: the centre of one end, of the other, then its width (the mouse's distance from the middle line × 2). */
  slotPoint(s) {
    if (!this.start) { this.start = s; this.m.hint(this.hint()); this.draw(); return; }
    if (!this.slotEnd) {
      if (Math.hypot(s.uv[0] - this.start.uv[0], s.uv[1] - this.start.uv[1]) < 1e-6) return;
      this.slotEnd = s;
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const a = this.start, b = this.slotEnd, r = this.slotHalf(a.uv, b.uv, s.uv);
    this.start = this.slotEnd = null;
    if (r > 1e-6) this.addSlot(a, b, r);
    else this.changed();
  }

  /** Half a slot's width: how far p is from the line through its two centres. */
  slotHalf(a, b, p) {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    return Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / L;
  }

  /** A slot of half width r round centres a, b (snapped points): two straight sides and two half circles, kept a slot
   *  (the sides tangent to the ends, the ends the same size) — its width and length then sized like any shape. */
  addSlot(a, b, r) {
    this.step();
    const g = this.newId('r'), c1 = this.pointAt(a), c2 = this.pointAt(b), A1 = this.P(c1), A2 = this.P(c2);
    const L = Math.hypot(A2[0] - A1[0], A2[1] - A1[1]), n = [-(A2[1] - A1[1]) / L * r, (A2[0] - A1[0]) / L * r];
    const pt = (p) => { const id = this.newId('p'); this.f.points[id] = [+p[0].toFixed(6), +p[1].toFixed(6)]; return id; };
    const P1 = pt([A1[0] - n[0], A1[1] - n[1]]), P2 = pt([A2[0] - n[0], A2[1] - n[1]]), P3 = pt([A2[0] + n[0], A2[1] + n[1]]), P4 = pt([A1[0] + n[0], A1[1] + n[1]]);
    const l1 = this.newId('l'), e2 = this.newId('a'), l2 = this.newId('l'), e1 = this.newId('a'), cf = this.consFlag();
    this.f.entities.push({ id: l1, t: 'line', a: P1, b: P2, g, ...cf }, { id: e2, t: 'arc', c: c2, a: P2, b: P3, g, ...cf },
      { id: l2, t: 'line', a: P3, b: P4, g, ...cf }, { id: e1, t: 'arc', c: c1, a: P4, b: P1, g, ...cf });
    const k = (o) => this.f.constraints.push({ id: this.newId('k'), ...o });
    k({ t: 'tan', e: l1, arc: e2, p: P2 });
    k({ t: 'tan', e: l2, arc: e2, p: P3 });
    k({ t: 'tan', e: l2, arc: e1, p: P4 });
    k({ t: 'tan', e: l1, arc: e1, p: P1 });
    k({ t: 'eq', e: e1, e2 });
    if (Math.abs(A2[1] - A1[1]) < 1e-9) k({ t: 'h', e: l1 }); else if (Math.abs(A2[0] - A1[0]) < 1e-9) k({ t: 'v', e: l1 }); // (drawn level / upright: kept so)
    this.sel = { kind: 'group', id: g };
    this.changed();
  }

  addCircle(a, b) {
    const r = Math.hypot(b.uv[0] - a.uv[0], b.uv[1] - a.uv[1]);
    if (r < 1e-9) { this.changed(); return; }
    this.step();
    const c = this.pointAt(a);
    const id = this.newId('c');
    this.f.entities.push({ id, t: 'circle', c, r: +r.toFixed(6), ...this.consFlag() });
    this.sel = { kind: 'entity', id };
    this.changed();
  }

  // ------------------------------------------------------------------ relations
  /** What a click picks for a relation: {kind: 'line' | 'circle' | 'arc' | 'point', id}, fitting `want`, or null. */
  relPick(uv, want) {
    const t = this.pickTarget(uv);
    if (!t) return null;
    if (t.mid && want !== 'point') return ['line', 'shape', 'any'].includes(want) ? { kind: 'line', id: t.mid } : null; // (a line's middle: that line)
    if (t.kind === 'point' && (want === 'point' || want === 'any') && !t.circle && !t.arc && typeof t.end === 'string') return { kind: 'point', id: t.end };
    if (t.circle) return want !== 'point' && want !== 'line' ? { kind: 'circle', id: t.circle } : want === 'point' ? { kind: 'point', id: t.end } : null;
    if (t.arc) return want !== 'point' && want !== 'line' ? { kind: 'arc', id: t.arc } : want === 'point' ? { kind: 'point', id: t.end } : null;
    if (t.kind === 'line' && t.line && ['line', 'shape', 'any'].includes(want)) return { kind: 'line', id: t.line };
    return null;
  }

  async relateClick(uv) {
    const type = this.relType || 'par', r = RELATIONS[type], picks = this.relPicks || (this.relPicks = []);
    const p = this.relPick(uv, r.picks[picks.length]);
    if (!p) { this.m.toast(this.hint(), 'info', 3000); return; }
    if (picks.some((q) => q.id === p.id)) return;
    picks.push(p);
    if (picks.length < r.picks.length) { this.m.hint(this.hint()); this.draw(); return; }
    this.relPicks = [];
    await this.addRelation(type, picks);
  }

  /** A relation between picks ({kind, id}: the second may be missing for h / v / fix). */
  async addRelation(type, picks) {
    const [a, b] = picks, k = this.relationOf(type, picks);
    if (type === 'eq' && (a.kind === 'line') !== (b.kind === 'line')) { this.m.toast('Equal: two lines, or two circles / arcs.', 'warning'); this.changed(); return; }
    await this.relock(() => this.f.constraints.push(k));
  }

  /** The relation for these picks, as the sketch keeps it. */
  relationOf(type, picks) {
    const [a, b] = picks, k = { id: this.newId('k'), t: type, user: true };
    if (type === 'h' || type === 'v') k.e = a.id;
    else if (type === 'fix') Object.assign(k, { p: a.id, at: [...this.P(a.id)] });
    else if (type === 'coin') Object.assign(k, b.kind === 'point' || b.kind === 'origin' ? { p: a.id, p2: b.id } : { p: a.id, e: b.id });
    else Object.assign(k, { e: a.id, e2: b.id });
    return k;
  }

  // ------------------------------------------------------------------ mirror
  /** The little box of the ⇋ Mirror tool: across the X / Y axis (or a clicked line), move instead of copy, done. */
  mirrorChooser() {
    this.closeChooser();
    const box = document.createElement('div');
    box.className = 'sk-choose sk-mirror';
    Object.assign(box.style, { left: '12px', top: '56px' });
    const ax = this.mirLine?.axis;
    box.innerHTML = `<div class="sk-choose-t">⇋ ${t('Mirror')}</div>
      <p class="hint">${t(this.mirLine ? (ax ? (ax === 'y' ? 'Across the Y axis (left ↔ right).' : 'Across the X axis (up ↔ down).') : 'Across the line you clicked.') : 'Across:')}</p>
      <div class="seg"><button data-ax="y" class="${ax === 'y' ? 'on' : ''}" title="${t('left ↔ right')}">${t('Y axis')}</button><button data-ax="x" class="${ax === 'x' ? 'on' : ''}" title="${t('up ↔ down')}">${t('X axis')}</button></div>
      <p class="hint">${t('or click a line of the sketch.')}</p>
      <label class="sk-off"><input type="checkbox" data-move ${this.mirMove ? 'checked' : ''}> ${t('Move (do not keep the original)')}</label>
      <button class="btn small primary" data-done>${t('Done')}</button>`;
    for (const ev of ['pointerdown', 'pointerup']) box.addEventListener(ev, (x) => x.stopPropagation());
    for (const b of box.querySelectorAll('[data-ax]')) b.addEventListener('click', () => { this.mirLine = { axis: b.dataset.ax }; if (this.mirSrc) { this.mirrorPicked(this.mirLine); return; } this.mirrorChooser(); this.changed(); });
    box.querySelector('[data-move]').addEventListener('change', (x) => { this.mirMove = x.target.checked; });
    box.querySelector('[data-done]').addEventListener('click', () => this.setTool('select'));
    this.m.els.viewport.appendChild(box);
    floatBox(box, this.m.els.viewport, { kind: 'sk-mirror', handle: '.sk-choose-t' });
    this.chooser = box;
  }

  async mirrorClick(uv) {
    if (!this.mirLine) {
      const p = this.relPick(uv, 'line');
      if (!p) { this.m.toast('Click a line to mirror across — or choose the X / Y axis.', 'info', 3000); return; }
      this.mirLine = { e: p.id };
      if (this.mirSrc) { this.mirrorPicked(this.mirLine); return; }
      this.mirrorChooser();
      this.changed();
      return;
    }
    const p = this.relPick(uv, 'shape');
    if (!p || p.id === this.mirLine.e) { this.m.toast('Click a line, circle or arc to mirror.', 'info', 3000); return; }
    const ents = this.wholeShape(this.ent(p.id), this.mirLine.e);
    if (ents.some((e) => e.t === 'block')) { this.m.toast('A picture outline cannot be mirrored yet.', 'warning'); return; }
    await this.mirror(ents, this.mirLine, this.mirMove);
  }

  /** The whole shape a line / circle / arc belongs to: its rectangle (slot …), or everything joined to it — not
   *  `skip` (a mirror line, a pattern's direction). */
  wholeShape(e0, skip = null) {
    if (!e0) return [];
    if (e0.g) return this.f.entities.filter((e) => e.g === e0.g && e.id !== skip);
    const ends = (e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b] : []);
    const seen = new Set([e0.id]), todo = [e0];
    while (todo.length) {
      const e = todo.pop();
      for (const o of this.f.entities) {
        if (seen.has(o.id) || o.id === skip || !['line', 'arc'].includes(o.t)) continue;
        if (ends(o).some((q) => q !== ORIGIN && ends(e).includes(q))) { seen.add(o.id); todo.push(o); }
      }
    }
    return this.f.entities.filter((e) => seen.has(e.id) && e.id !== skip);
  }

  /** Mirror these shapes across `line` ({e} a sketch line, or {axis: 'x' | 'y'}): a copy held by a ⇋ Mirrored
   *  relation (it follows the original), or (move) the shapes themselves turned over. Points on the line are shared. */
  async mirror(ents, line, move = false) {
    const ln = line.e ? this.ent(line.e) : null;
    const A = ln ? this.P(ln.a) : [0, 0], B = ln ? this.P(ln.b) : line.axis === 'x' ? [1, 0] : [0, 1];
    const L = Math.hypot(B[0] - A[0], B[1] - A[1]) || 1, d = [(B[0] - A[0]) / L, (B[1] - A[1]) / L];
    const refl = (p) => { const w = [p[0] - A[0], p[1] - A[1]], s = w[0] * d[0] + w[1] * d[1]; return [2 * (A[0] + s * d[0]) - p[0], 2 * (A[1] + s * d[1]) - p[1]].map((v) => +v.toFixed(6)); };
    const onLine = (p) => Math.abs((p[0] - A[0]) * d[1] - (p[1] - A[1]) * d[0]) < 1e-6;
    const square = Math.abs(d[0]) < 1e-9 || Math.abs(d[1]) < 1e-9; // across a horizontal / vertical line: H stays H, V stays V
    const pts = [...new Set(ents.flatMap((e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : [e.c])))];
    await this.relock(() => {
      const f = this.f;
      if (move) {
        for (const id of pts) if (id !== ORIGIN && !onLine(this.P(id))) f.points[id] = refl(this.P(id));
        for (const e of ents) if (e.t === 'arc') [e.a, e.b] = [e.b, e.a]; // turned over: it runs the other way round
        const ids = new Set(ents.map((e) => e.id));
        if (!square) f.constraints = f.constraints.filter((k) => !(ids.has(k.e) && (k.t === 'h' || k.t === 'v')));
        // their mirror copies (⇋ Mirrored) go along, so the solver has nothing to pull back
        for (const k of f.constraints.filter((x) => x.t === 'mir')) {
          const kl = k.e ? this.ent(k.e) : null, a0 = kl ? this.P(kl.a) : [0, 0], b0 = kl ? this.P(kl.b) : k.axis === 'x' ? [1, 0] : [0, 1];
          const n0 = Math.hypot(b0[0] - a0[0], b0[1] - a0[1]) || 1, u = [(b0[0] - a0[0]) / n0, (b0[1] - a0[1]) / n0];
          const rk = (p) => { const w = [p[0] - a0[0], p[1] - a0[1]], s = w[0] * u[0] + w[1] * u[1]; return [2 * (a0[0] + s * u[0]) - p[0], 2 * (a0[1] + s * u[1]) - p[1]].map((v) => +v.toFixed(6)); };
          for (const [p, q] of k.pairs || []) {
            if (p === q) continue;
            if (pts.includes(p) && !pts.includes(q)) f.points[q] = rk(this.P(p));
            else if (pts.includes(q) && !pts.includes(p)) f.points[p] = rk(this.P(q));
          }
        }
        for (const dm of f.dims) if (['dx', 'dy', 'dist'].includes(dm.t)) dm.v = +this.measure(dm).toFixed(6);
        return;
      }
      const map = {};
      for (const id of pts) {
        const p = this.P(id);
        if (id === ORIGIN || onLine(p)) { map[id] = id; continue; }
        map[id] = this.newId('p');
        f.points[map[id]] = refl(p);
      }
      const groups = {}, circles = [];
      for (const e of ents) {
        const id = this.newId(e.t === 'circle' ? 'c' : e.t === 'arc' ? 'a' : 'l'), g = e.g ? (groups[e.g] = groups[e.g] || this.newId('r')) : undefined;
        if (e.t === 'line') f.entities.push({ id, t: 'line', a: map[e.a], b: map[e.b], ...(g ? { g } : {}) });
        else if (e.t === 'arc') f.entities.push({ id, t: 'arc', c: map[e.c], a: map[e.b], b: map[e.a], ...(g ? { g } : {}) });
        else { f.entities.push({ id, t: 'circle', c: map[e.c], r: e.r }); circles.push([e.id, id]); }
      } // (no H / V of its own: the mirror keeps the copy's lines as the original's)
      f.constraints.push({ id: this.newId('k'), t: 'mir', user: true, pairs: pts.filter((p) => p !== ORIGIN).map((p) => [p, map[p]]), circles,
        ...(line.e ? { e: line.e } : { axis: line.axis }) });
    });
  }

  // ------------------------------------------------------------------ pattern
  /** ⁂ Pattern (the bar): the picked shapes (⬚ Select: a click, Ctrl+click, a box) repeated at once — 3 in a row along
   *  the sketch's X (a picked construction line: along it), or 6 around a picked point — then the quick box (count,
   *  spacing) re-makes them live; a click on a line / a point or circle chooses the direction / the centre. */
  async startPattern() {
    const P = this.picks?.length ? this.picks : this.sel?.kind === 'group' ? this.f.entities.filter((e) => e.g === this.sel.id).map((e) => ({ kind: e.t, id: e.id }))
      : this.sel?.kind === 'entity' ? [{ kind: this.ent(this.sel.id)?.t, id: this.sel.id }] : [];
    const shapes = P.filter((q) => ['line', 'circle', 'arc', 'spline', 'block'].includes(q.kind)).map((q) => this.ent(q.id)).filter(Boolean);
    const along = shapes.some((e) => !e.construction) ? shapes.find((e) => e.t === 'line' && e.construction)?.id : undefined;
    const src = [...new Set(shapes.filter((e) => e.id !== along).flatMap((e) => this.wholeShape(e, along)).map((e) => e.id))];
    if (!src.length) { this.m.toast('Select the shapes to repeat first (⬚ Select: click, Ctrl+click or drag a box), then ⁂ Pattern.', 'info', 5000); this.setTool('select'); return; }
    if (src.some((id) => this.ent(id)?.t === 'block')) { this.m.toast('A picture outline cannot be repeated yet.', 'warning'); return; }
    const centre = P.find((q) => q.kind === 'point' || q.kind === 'origin')?.id;
    const o = centre ? { kind: 'around', n: 6, c: centre } : { kind: 'row', n: 3, d: this.patGap(src, along), ...(along ? { e: along } : {}) };
    try { makePattern(structuredClone(this.f), src, o, (x) => `${x}?`); } catch (err) { this.m.toast(t(err.message), 'warning'); return; }
    let k;
    if (!(await this.relock(() => { k = makePattern(this.f, src, o, (x) => this.newId(x)); }))) return;
    this.picks = [];
    this.sel = null;
    this.editPattern(k.id, this.undo.length);
  }

  /** A row's first spacing: the shapes' length along the way they go and half again (rounded), so the copies do not touch. */
  patGap(src, along) {
    const ln = along && this.ent(along), a = ln ? this.P(ln.a) : [0, 0], b = ln ? this.P(ln.b) : [1, 0], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const u = [(b[0] - a[0]) / L, (b[1] - a[1]) / L], at = [];
    for (const e of src.map((id) => this.ent(id)).filter(Boolean)) {
      if (e.t === 'circle') { const c = this.P(e.c), s = c[0] * u[0] + c[1] * u[1]; at.push(s - e.r, s + e.r); }
      else if (e.t === 'arc') { const c = this.P(e.c), s = c[0] * u[0] + c[1] * u[1], r = this.arcR(e); at.push(s - r, s + r); }
      else for (const q of entPts(e)) at.push(this.P(q)[0] * u[0] + this.P(q)[1] * u[1]);
    }
    const w = at.length ? Math.max(...at) - Math.min(...at) : 0;
    return w > 1e-6 ? +(w * 1.5).toPrecision(2) : 10;
  }

  /** The ⁂ pattern's quick box (bottom left): in a row / around, the count and the spacing; typing re-makes the copies
   *  (one undo step for all of it — `base`: the undo depth it keeps), Enter = done. */
  editPattern(id, base = null) {
    const k = this.f.constraints.find((x) => x.id === id && x.t === 'pat');
    if (!k) return;
    this.closeChooser();
    if (this.tool !== 'pattern') { this.tool = 'pattern'; this.m.renderCmdBar(); }
    this.pat = { k: id, base };
    const row = k.kind !== 'around', box = document.createElement('div');
    box.className = 'sk-choose sk-quick sk-pattern';
    box.innerHTML = `<div class="sk-choose-t">⁂ ${t('Pattern')}</div>
      <div class="seg"><button data-kind="row" class="${row ? 'on' : ''}">${t('In a row')}</button><button data-kind="around" class="${row ? '' : 'on'}">${t('Around')}</button></div>
      <label>${t('Count')} <input type="text" data-pk="n" value="${k.n}"></label>
      ${row ? `<label>${t('Spacing')} <input type="text" data-pk="d" value="${fmt(k.d)}"> mm</label>` : ''}
      <p class="hint">${t(row ? (k.e ? 'Along the line you clicked — or click another line.' : 'Along X — or click a line to go along it.')
        : (k.c && k.c !== ORIGIN ? 'Around the point you clicked — or click another point or circle.' : 'Around the origin — or click a point or a circle for the centre.'))}
        ${t('Enter = done')}</p>
      <button class="btn small primary" data-done>${t('Done')}</button>`;
    for (const ev of ['pointerdown', 'pointerup']) box.addEventListener(ev, (x) => x.stopPropagation());
    const typed = () => Object.fromEntries([...box.querySelectorAll('[data-pk]')].map((i) => [i.dataset.pk, parseFloat(i.value.replace(',', '.'))]));
    for (const inp of box.querySelectorAll('[data-pk]')) {
      inp.addEventListener('input', () => { clearTimeout(this.patTimer); this.patTimer = setTimeout(() => this.repattern(typed(), true), 350); });
      inp.addEventListener('keydown', async (ev) => {
        ev.stopPropagation();
        if (ev.key === 'Escape') this.setTool('select');
        if (ev.key !== 'Enter') return;
        clearTimeout(this.patTimer);
        if (await this.repattern(typed())) this.setTool('select');
      });
    }
    for (const b of box.querySelectorAll('[data-kind]')) b.addEventListener('click', () => this.repattern({ kind: b.dataset.kind }));
    box.querySelector('[data-done]').addEventListener('click', async () => { clearTimeout(this.patTimer); if (await this.repattern(typed())) this.setTool('select'); });
    this.m.els.viewport.appendChild(box);
    floatBox(box, this.m.els.viewport, { kind: 'sk-pattern', handle: '.sk-choose-t' });
    this.chooser = box;
    this.m.hint(this.hint());
    setTimeout(() => { const i = box.querySelector('[data-pk=n]'); if (i && this.chooser === box) { i.focus(); i.select(); } }, 0);
  }

  /** The pattern re-made with these changes ({n, d, kind, e, c}; the same: nothing done). quiet: a half-typed value
   *  says nothing. -> true when it is (now) as asked. One at a time (typing and Enter may overlap). */
  repattern(ch, quiet = false) {
    const run = async () => {
      const k = this.f.constraints.find((x) => x.id === this.pat?.k);
      if (!k) return false;
      const o = { ...k, ...Object.fromEntries(Object.entries(ch).filter(([, v]) => v !== undefined && !Number.isNaN(v))) };
      if (o.kind === 'around') delete o.e; else delete o.c;
      if (o.kind === 'row' && !Number.isFinite(o.d)) o.d = this.patGap(k.src, o.e);
      if (['kind', 'n', 'd', 'e', 'c'].every((x) => o[x] === k[x])) return true;
      try { const g = structuredClone(this.f); unmakePattern(g, g.constraints.find((x) => x.id === k.id)); makePattern(g, k.src, o, (x) => `${x}?`); } catch (err) {
        if (!quiet) this.m.toast(t(err.message), 'warning');
        return false;
      }
      const ok = await this.relock(() => { unmakePattern(this.f, k); makePattern(this.f, k.src, o, (x) => this.newId(x), () => k.id); });
      if (ok && this.pat) {
        if (this.pat.base === null) this.pat.base = this.undo.length; // (the first change of this edit: its own undo step)
        else this.undo.length = this.pat.base; // (later ones: the same step)
      }
      if (this.pat && this.tool === 'pattern' && !quiet) this.editPattern(k.id, this.pat.base); // (in a row / around: its fields)
      return ok;
    };
    this.patBusy = (this.patBusy || Promise.resolve()).then(run, run);
    return this.patBusy;
  }

  /** A click while the pattern's box is open: a line -> along it (in a row); a point, a circle or an arc -> around
   *  its centre. */
  patternClick(uv) {
    if (!this.f.constraints.some((x) => x.id === this.pat?.k)) { this.setTool('select'); return; }
    const p = this.pickTarget(uv);
    if (!p) return;
    if (p.kind === 'line' && typeof p.line === 'string' && !p.mid) { this.repattern({ kind: 'row', e: p.line }); return; }
    const c = p.circle || p.arc ? this.ent(p.circle || p.arc)?.c : p.kind === 'point' && typeof p.end === 'string' ? p.end : null;
    if (c) this.repattern({ kind: 'around', c });
  }

  /** A relation's place in the sketch (for its symbol): the middle of its first shape, or its point. */
  relAt(k) {
    if (k.t === 'off') return null; // (its ⧈ size label shows it)
    if (k.t === 'pat') { // between the original and its first copy
      const pr = (k.pairs || []).find(([p, qs]) => qs[0] && qs[0] !== p && this.P(p) && this.P(qs[0]));
      return pr ? [(this.P(pr[0])[0] + this.P(pr[1][0])[0]) / 2, (this.P(pr[0])[1] + this.P(pr[1][0])[1]) / 2] : null;
    }
    if (k.t === 'mir') { // by the mirror line, or between the first pair across an axis
      if (k.e && this.ent(k.e)) { const a = this.P(this.ent(k.e).a), b = this.P(this.ent(k.e).b); return [a[0] + (b[0] - a[0]) * 0.75, a[1] + (b[1] - a[1]) * 0.75]; }
      const pr = (k.pairs || []).find(([p, q]) => p !== q && this.P(p) && this.P(q));
      return pr ? [(this.P(pr[0])[0] + this.P(pr[1])[0]) / 2, (this.P(pr[0])[1] + this.P(pr[1])[1]) / 2] : null;
    }
    if (k.p) return this.P(k.p);
    const e = this.ent(k.e);
    if (!e) return null;
    // a quarter along the line (its middle has the length label), a little beside it
    if (e.t === 'line') { const a = this.P(e.a), b = this.P(e.b); return [a[0] + (b[0] - a[0]) * 0.25, a[1] + (b[1] - a[1]) * 0.25]; }
    if (e.t === 'circle') { const c = this.P(e.c); return [c[0] - e.r * 0.7, c[1] + e.r * 0.7]; }
    if (e.t === 'arc') { const ps = this.arcOf(e); return ps[Math.floor(ps.length / 2)]; }
    return null;
  }

  userRelations() { return this.f.constraints.filter((k) => k.user || (RELATIONS[k.t] && !['h', 'v'].includes(k.t))); }

  async delRelation(id) {
    if (this.f.constraints.find((k) => k.id === id)?.t === 'off') { await this.unlinkOffset(id); return; } // (a one-off copy again)
    await this.relock(() => { this.f.constraints = this.f.constraints.filter((k) => k.id !== id); });
  }

  /** Trim: the piece of the shape under the mouse between the crossings next to it -> {e, g, lo, hi, cuts, pts}. */
  pieceAt(uv) {
    const tol = this.mpp() * 8, P = (id) => this.P(id);
    let best = null;
    for (const e of this.f.entities) {
      if (!['line', 'circle', 'arc'].includes(e.t)) continue;
      const g = geomOf(e, P);
      const d = g.kind === 'line' ? segDist(uv, g.a, g.b) : g.kind === 'circle' ? Math.abs(Math.hypot(uv[0] - g.c[0], uv[1] - g.c[1]) - g.r) : this.arcDist(e, uv);
      if (d < tol && (!best || d < best.d)) best = { d, e, g };
    }
    if (!best) return null;
    const { e, g } = best, closed = g.kind === 'circle', end = g.kind === 'line' ? 1 : g.kind === 'arc' ? g.sweep : TAU;
    const cuts = [];
    for (const o of this.f.entities) {
      if (o === e || !['line', 'circle', 'arc'].includes(o.t)) continue;
      for (const p of crossings(g, geomOf(o, P))) {
        let t = paramOf(g, p);
        if (g.kind === 'arc' && t > g.sweep + 1e-9) t = 0;
        if (!closed && (t < 1e-7 * end || t > end * (1 - 1e-7))) continue; // at its own ends: not a cut
        if (!cuts.some((c) => Math.abs(c.t - t) < 1e-7 * end)) cuts.push({ t, p, by: o.id });
      }
    }
    cuts.sort((x, y) => x.t - y.t);
    const at = paramOf(g, uv);
    let lo, hi;
    if (closed) {
      if (cuts.length < 2) { lo = { t: 0 }; hi = { t: TAU }; } else {
        const i = cuts.findIndex((c) => c.t > at);
        lo = i <= 0 ? cuts[cuts.length - 1] : cuts[i - 1];
        hi = i < 0 ? cuts[0] : cuts[i];
      }
    } else {
      const t = Math.max(0, Math.min(end, g.kind === 'arc' && at > g.sweep ? (at - g.sweep < TAU - at ? g.sweep : 0) : at));
      lo = [...cuts].reverse().find((c) => c.t < t) || { t: 0 };
      hi = cuts.find((c) => c.t > t) || { t: end };
    }
    // the piece as points, for the highlight
    const pts = [];
    if (g.kind === 'line') pts.push([g.a[0] + lo.t * (g.b[0] - g.a[0]), g.a[1] + lo.t * (g.b[1] - g.a[1])], [g.a[0] + hi.t * (g.b[0] - g.a[0]), g.a[1] + hi.t * (g.b[1] - g.a[1])]);
    else {
      const t0 = (g.kind === 'arc' ? g.t0 : 0) + lo.t, span = angNorm(hi.t - lo.t) || (closed && cuts.length < 2 ? TAU : hi.t - lo.t);
      const n = Math.max(2, Math.ceil(span / (Math.PI / 36)));
      for (let k = 0; k <= n; k++) pts.push([g.c[0] + g.r * Math.cos(t0 + (span * k) / n), g.c[1] + g.r * Math.sin(t0 + (span * k) / n)]);
    }
    return { e, g, lo, hi, cuts, pts, whole: lo.t === 0 && (hi.t === end) && !(closed && cuts.length >= 2) };
  }

  /** ✂ Trim: cut the piece away. A line keeps its other part(s), a circle becomes the arc that is left, an arc is split.
   *  The new ends stay on the shape that cut them ("on" constraints) when sizes change later. */
  async trimAt(uv, { quiet = false } = {}) {
    const pc = this.pieceAt(uv);
    if (!pc) { if (!quiet) this.m.toast('Click a line, circle or arc to trim.', 'info', 3000); return false; }
    const { e, lo, hi } = pc;
    const done = await this.relock(() => {
      const f = this.f;
      const newPt = (c) => {
        // on an end of the shape that cuts it: join there; else a new end that stays on that shape
        const by = f.entities.find((x) => x.id === c.by), tol = 1e-6 * (1 + Math.hypot(...c.p));
        const join = by && [by.a, by.b].find((q) => q && this.P(q) && Math.hypot(this.P(q)[0] - c.p[0], this.P(q)[1] - c.p[1]) < tol);
        if (join) return join;
        const id = this.newId('p');
        f.points[id] = c.p.map((v) => +v.toFixed(9));
        f.constraints.push({ id: this.newId('k'), t: 'on', p: id, e: c.by });
        return id;
      };
      const forget = (id) => {
        f.constraints = f.constraints.filter((k) => !((k.e === id || k.arc === id || (k.lines || []).includes(id)) && k.t !== 'h' && k.t !== 'v'));
        f.dims = f.dims.filter((d) => !(d.e === id && d.t === 'len'));
      };
      if (pc.whole) {
        f.entities = f.entities.filter((x) => x !== e);
        f.constraints = f.constraints.filter((k) => k.e !== e.id && k.arc !== e.id && !(k.lines || []).includes(e.id));
        f.dims = f.dims.filter((d) => d.e !== e.id);
      } else if (e.t === 'circle') {
        // what is left: the arc from the piece's far end round to its near end
        const a = newPt(hi), b = newPt(lo);
        const dia = f.dims.find((d) => d.e === e.id && d.t === 'dia');
        if (dia) Object.assign(dia, { t: 'rad', v: dia.v / 2 });
        Object.assign(e, { t: 'arc', a, b });
        delete e.r;
      } else {
        // relations of the shape as a whole (equal, parallel, tangent to a circle …) still hold for what is left of
        // it; a tangent at an end that stays stays too (a trimmed slot keeps its smooth joins)
        const whole = f.constraints.filter((k) => ['eq', 'tang', 'par', 'perp', 'conc'].includes(k.t) && (k.e === e.id || k.e2 === e.id));
        const tans = f.constraints.filter((k) => k.t === 'tan' && (k.e === e.id || k.arc === e.id));
        forget(e.id);
        const keepA = lo.t > 0, keepB = !(hi.t >= (e.t === 'line' ? 1 : pc.g.sweep) - 1e-12);
        const oldB = e.b;
        let piece = null;
        if (keepA && keepB) {
          // the middle goes: two pieces
          const p1 = newPt(lo), p2 = newPt(hi);
          e.b = p1;
          piece = { ...e, id: this.newId(e.t === 'line' ? 'l' : 'a'), a: p2, b: oldB, g: undefined };
          f.entities.push(piece);
          for (const k of f.constraints.filter((k) => k.e === e.id && (k.t === 'h' || k.t === 'v'))) f.constraints.push({ ...k, id: this.newId('k'), e: piece.id });
        } else if (keepA) e.b = newPt(lo);
        else e.a = newPt(hi);
        delete e.g;
        f.constraints = [...f.constraints.filter((k) => !whole.includes(k)), ...whole]; // (once each)
        for (const k of tans) {
          const on = [e, piece].find((x) => x && (x.a === k.p || x.b === k.p));
          if (on) f.constraints.push(on === e ? k : { ...k, id: this.newId('k'), [k.e === e.id ? 'e' : 'arc']: piece.id });
        }
      }
      const used = new Set([...f.entities.flatMap((x) => [x.a, x.b, x.c, ...(x.pts || [])]), ...f.constraints.filter((k) => k.t === 'corner').map((k) => k.p)]);
      for (const p of Object.keys(f.points)) if (!used.has(p)) delete f.points[p];
      f.constraints = f.constraints.filter((k) => !k.p || f.points[k.p] || k.p === ORIGIN);
      // a point kept on a shape that now ends there is on it already (held twice, the solver would refuse it)
      f.constraints = f.constraints.filter((k) => !(k.t === 'on' && f.entities.some((x) => x.id === k.e && (x.a === k.p || x.b === k.p))));
      f.dims = f.dims.filter((d) => (!d.a || typeof d.a !== 'string' || d.a === ORIGIN || f.points[d.a]) && (!d.b || typeof d.b !== 'string' || d.b === ORIGIN || f.points[d.b]));
    }, null, null, { quiet });
    this.sel = null;
    this.changed();
    return done;
  }

  /** ∪ Union: closed shapes that overlap become one outline — every piece of a line, circle or arc that lies inside
   *  another closed shape is trimmed away (✂ Trim's way: the new ends stay on the shape that cut them; equal radii and
   *  tangents that still apply stay). One undo step. -> {trimmed, before, after} or null (nothing overlaps). */
  async unionShapes() {
    const f = this.f, regions = this.unionRegions();
    if (regions.length < 2) return null;
    const before = f.entities.length, undo0 = this.undo.length;
    let trimmed = 0;
    for (let m = this.innerPiece(regions); m && trimmed < UNION_MAX; m = this.innerPiece(regions)) {
      if (!(await this.trimAt(m, { quiet: true }))) break; // (a trim the locks do not let through: stop there)
      trimmed++;
    }
    if (trimmed) this.undo.splice(undo0 + 1); // (one undo step for all of it)
    this.changed();
    return trimmed ? { trimmed, before, after: f.entities.length } : null;
  }

  /** The closed regions of the sketch as they are (loops of lines / arcs, circles): a polygon each, and its shapes. */
  unionRegions() {
    const P = (id) => this.P(id), f = this.f;
    const regions = [], seen = new Set();
    for (const e of f.entities) {
      if (seen.has(e.id) || e.construction || !['line', 'arc', 'circle'].includes(e.t)) continue;
      const l = this.loopFrom(e);
      if (!l) continue;
      l.ids.forEach((id) => seen.add(id));
      const ring = [];
      if (l.kind === 'circle') for (let i = 0; i < 180; i++) ring.push([P(e.c)[0] + e.r * Math.cos((i * TAU) / 180), P(e.c)[1] + e.r * Math.sin((i * TAU) / 180)]);
      else for (const o of l.order) {
        const ps = o.e.t === 'line' ? [P(o.from), P(o.to)] : arcPts(P(o.e.c), P(o.e.a), P(o.e.b), 2);
        ring.push(...(o.from === o.e.a ? ps : [...ps].reverse()).slice(0, -1));
      }
      regions.push({ ring, ids: new Set(l.ids), geos: l.ids.map((id) => geomOf(this.ent(id), P)) });
    }
    // a region no other one crosses (a hole inside a plate, a shape on its own) is left as it is
    for (const r of regions) r.crosses = regions.some((o) => o !== r && r.geos.some((g) => o.geos.some((h) => crossings(g, h).length)));
    return regions;
  }

  /** The middle of the first piece (between crossings) of a shape that lies inside a region it is not part of, or null. */
  innerPiece(regions) {
    const P = (id) => this.P(id), f = this.f;
    const inside = (ring, p) => {
      let c = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j];
        if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
      }
      return c;
    };
    const onBorder = (r, p) => r.geos.some((g) => (g.kind === 'line' ? segDist(p, g.a, g.b) : Math.abs(Math.hypot(p[0] - g.c[0], p[1] - g.c[1]) - g.r)) < 1e-6 && onShape(g, p, 1e-6));
    const alone = regions.filter((r) => !r.crosses);
    for (const e of f.entities) {
      if (e.construction || !['line', 'arc', 'circle'].includes(e.t) || alone.some((r) => r.ids.has(e.id))) continue;
      const g = geomOf(e, P), end = g.kind === 'line' ? 1 : g.kind === 'arc' ? g.sweep : TAU;
      const ts = [0, end];
      for (const o of f.entities) {
        if (o === e || !['line', 'circle', 'arc'].includes(o.t)) continue;
        for (const p of crossings(g, geomOf(o, P))) { const t = paramOf(g, p); if (t > 1e-7 * end && t < end * (1 - 1e-7)) ts.push(t); }
      }
      ts.sort((a, b) => a - b);
      for (let i = 0; i + 1 < ts.length; i++) {
        if (ts[i + 1] - ts[i] < 1e-6 * end) continue;
        const tm = (ts[i] + ts[i + 1]) / 2;
        const m = g.kind === 'line' ? [g.a[0] + tm * (g.b[0] - g.a[0]), g.a[1] + tm * (g.b[1] - g.a[1])]
          : [g.c[0] + g.r * Math.cos((g.kind === 'arc' ? g.t0 : 0) + tm), g.c[1] + g.r * Math.sin((g.kind === 'arc' ? g.t0 : 0) + tm)];
        if (regions.some((r) => !onBorder(r, m) && inside(r.ring, m))) return m;
      }
    }
    return null;
  }

  /** ⟷ Extend: the line under the mouse, its end nearer the mouse and where that end would go — the first shape the
   *  line meets beyond it -> {e, end ('a' | 'b'), from, to, by (the shape met)} or null. */
  extensionAt(uv) {
    const tol = this.mpp() * 8;
    let best = null;
    for (const e of this.f.entities) {
      if (e.t !== 'line') continue;
      const d = segDist(uv, this.P(e.a), this.P(e.b));
      if (d < tol && (!best || d < best.d)) best = { d, e };
    }
    if (!best) return null;
    const e = best.e, A = this.P(e.a), B = this.P(e.b), L = Math.hypot(B[0] - A[0], B[1] - A[1]);
    if (L < 1e-9) return null;
    const end = paramOf({ kind: 'line', a: A, b: B }, uv) < 0.5 ? 'a' : 'b';
    const from = end === 'a' ? A : B, other = end === 'a' ? B : A, dir = [(from[0] - other[0]) / L, (from[1] - other[1]) / L];
    const far = 1e6 * (1 + Math.hypot(...from));
    const ray = { kind: 'line', a: from, b: [from[0] + dir[0] * far, from[1] + dir[1] * far] };
    let hit = null;
    for (const x of this.f.entities) {
      if (x === e) continue;
      const g = geomOf(x, (id) => this.P(id));
      if (!g) continue;
      for (const p of crossings(ray, g)) {
        const s = (p[0] - from[0]) * dir[0] + (p[1] - from[1]) * dir[1];
        if (s > 1e-6 * (1 + L) && (!hit || s < hit.s)) hit = { s, p, by: x.id };
      }
    }
    return hit && { e, end, from, to: hit.p, by: hit.by };
  }

  /** ⟷ Extend: the end moves out to the shape it meets and stays on it (joined if it lands on that shape's end). */
  async extendAt(uv) {
    const x = this.extensionAt(uv);
    if (!x) { this.m.toast('Click a line near the end to lengthen — it needs a shape further along to reach.', 'info', 4000); return; }
    const f = this.f, pid = x.e[x.end];
    if (pid === ORIGIN || f.entities.some((o) => o !== x.e && [o.a, o.b, o.c].includes(pid))) {
      this.m.toast('That end is joined to another shape — it cannot move on its own.', 'info', 4000);
      return;
    }
    await this.relock(() => {
      const by = f.entities.find((o) => o.id === x.by), tol = 1e-6 * (1 + Math.hypot(...x.to));
      const join = [by.a, by.b].find((q) => q && q !== ORIGIN && this.P(q) && Math.hypot(this.P(q)[0] - x.to[0], this.P(q)[1] - x.to[1]) < tol);
      // its length and the end's place now follow the shape it meets
      f.dims = f.dims.filter((d) => !(d.e === x.e.id && d.t === 'len') && d.a !== pid && d.b !== pid);
      if (join) {
        x.e[x.end] = join;
        delete f.points[pid];
        f.constraints = f.constraints.filter((k) => k.p !== pid);
      } else {
        f.points[pid] = x.to.map((v) => +v.toFixed(9));
        f.constraints = f.constraints.filter((k) => !((k.t === 'on' || k.t === 'fix') && k.p === pid));
        f.constraints.push({ id: this.newId('k'), t: 'on', p: pid, e: by.id });
      }
    });
    this.sel = null;
    this.changed();
  }

  /** ⧈ Offset: the closed shape under the mouse -> {kind: 'circle' | 'block' | 'loop', ids, …}, or null. A loop is
   *  lines / arcs joined end to end all the way round (each corner joins exactly two). */
  loopAt(uv) {
    const tol = this.mpp() * 8;
    let best = null;
    for (const e of this.f.entities) {
      let d = Infinity;
      if (e.t === 'line') d = segDist(uv, this.P(e.a), this.P(e.b));
      else if (e.t === 'arc') d = this.arcDist(e, uv);
      else if (e.t === 'circle') d = Math.abs(Math.hypot(uv[0] - this.P(e.c)[0], uv[1] - this.P(e.c)[1]) - e.r);
      else if (e.t === 'block') d = this.inBlock(e, uv) ? tol * 0.9 : Infinity;
      if (d < tol && (!best || d < best.d)) best = { d, e };
    }
    return best ? this.loopFrom(best.e) : null;
  }

  /** The closed shape `e` is part of: a circle, a picture outline, or lines / arcs joined all round (not open, not
   *  branching) -> {kind, ids, order?, e?} or null. */
  loopFrom(e) {
    if (e.t === 'circle' || e.t === 'block') return { kind: e.t, ids: [e.id], e };
    if (e.t !== 'line' && e.t !== 'arc') return null;
    // walk round from e
    const segs = this.f.entities.filter((x) => x.t === 'line' || x.t === 'arc');
    const order = [{ e, from: e.a, to: e.b }];
    let at = e.b;
    while (at !== e.a) {
      const next = segs.filter((x) => x !== order[order.length - 1].e && (x.a === at || x.b === at));
      if (next.length !== 1 || order.some((o) => o.e === next[0])) return null; // open, or branching
      const x = next[0];
      order.push({ e: x, from: at, to: x.a === at ? x.b : x.a });
      at = order[order.length - 1].to;
      if (order.length > 500) return null;
    }
    return { kind: 'loop', ids: order.map((o) => o.e.id), order };
  }

  /** The offset copy of a loop of lines / arcs: each line moved d outwards, each arc concentric; corners where two
   *  moved lines meet; joins with arcs must be smooth (tangent). -> {pts: [[u, v]], segs: [{t, …}]} or throws. */
  offsetLoop(order, d) {
    // which way round: the signed area of the outline (arcs by their points)
    const ring = [];
    for (const o of order) {
      if (o.e.t === 'line') ring.push(this.P(o.from));
      else {
        const ps = this.arcOf(o.e);
        ring.push(...(o.from === o.e.a ? ps : [...ps].reverse()).slice(0, -1));
      }
    }
    let area = 0;
    for (let i = 0; i < ring.length; i++) { const p = ring[i], q = ring[(i + 1) % ring.length]; area += p[0] * q[1] - q[0] * p[1]; }
    const side = area > 0 ? 1 : -1; // outwards = to the right of the way round (counter-clockwise outline)
    const pieces = order.map((o) => {
      const a = this.P(o.from), b = this.P(o.to);
      if (o.e.t === 'line') {
        const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, n = [side * (b[1] - a[1]) / L, -side * (b[0] - a[0]) / L];
        return { t: 'line', a: [a[0] + n[0] * d, a[1] + n[1] * d], b: [b[0] + n[0] * d, b[1] + n[1] * d], src: o.e, w: o.from === o.e.a ? -side : side };
      }
      const c = this.P(o.e.c), r = this.arcR(o.e), ccw = o.from === o.e.a, r2 = r + d * side * (ccw ? 1 : -1);
      if (!(r2 > 1e-9)) throw new Error('That distance is bigger than a rounding of the outline.');
      const at = (p) => [c[0] + ((p[0] - c[0]) / r) * r2, c[1] + ((p[1] - c[1]) / r) * r2];
      return { t: 'arc', a: at(a), b: at(b), c: o.e.c, ccw, r: r2, src: o.e, w: ccw ? side : -side };
    });
    // the corners: where piece k ends and k + 1 starts
    const corners = pieces.map((p, k) => {
      const q = pieces[(k + 1) % pieces.length], tol = 1e-6 * (1 + Math.abs(d));
      if (Math.hypot(p.b[0] - q.a[0], p.b[1] - q.a[1]) < tol) return p.b;
      if (p.t === 'line' && q.t === 'line') {
        const g = crossings({ kind: 'line', a: p.a, b: p.b }, { kind: 'line', a: q.a, b: q.b });
        // the full lines (not just the pieces) meet at the mitre corner
        const r1 = [p.b[0] - p.a[0], p.b[1] - p.a[1]], r2 = [q.b[0] - q.a[0], q.b[1] - q.a[1]], den = r1[0] * r2[1] - r1[1] * r2[0];
        if (Math.abs(den) < 1e-12) return p.b;
        const w = [q.a[0] - p.a[0], q.a[1] - p.a[1]], t = (w[0] * r2[1] - w[1] * r2[0]) / den;
        return g.length ? g[0] : [p.a[0] + t * r1[0], p.a[1] + t * r1[1]];
      }
      throw new Error('This outline has a sharp corner next to an arc — round it (◜) or offset its pieces one by one.');
    });
    return { pieces, corners };
  }

  /** ⧈ Offset: pick the shape (or `l`: the picks' loop), then type the distance in a small box by the mouse. */
  offsetAt(uv, ev, l = this.loopAt(uv)) {
    if (!l) { this.m.toast('Click a closed shape: a circle, an outline of lines / arcs joined all round, or a picture outline.', 'info', 4000); return; }
    this.closeChooser();
    const box = document.createElement('div');
    box.className = 'sk-choose';
    const vr = this.m.els.viewport.getBoundingClientRect();
    Object.assign(box.style, { left: `${ev.clientX - vr.left + 12}px`, top: `${ev.clientY - vr.top + 12}px` });
    box.innerHTML = `<div class="sk-choose-t">Offset by</div><label class="sk-off"><input type="number" step="any" value="${fmt(this.lastOffset || 2)}"> mm</label>
      <p class="hint">Negative = inside.</p>${l.kind === 'block' ? '<p class="hint">A picture outline: a one-off copy (it does not follow).</p>' : ''}<button class="btn small primary">OK</button>`;
    for (const t of ['pointerdown', 'pointerup']) box.addEventListener(t, (x) => x.stopPropagation());
    this.m.els.viewport.appendChild(box);
    floatBox(box, this.m.els.viewport, { kind: 'sk-offset', handle: '.sk-choose-t', remember: 'size' }); // (opens by the mouse)
    this.chooser = box;
    const inp = box.querySelector('input');
    const go = () => {
      const d = parseFloat(String(inp.value).replace(',', '.'));
      if (!Number.isFinite(d) || !d) { this.m.toast('Type a distance (not 0).', 'warning'); return; }
      this.lastOffset = d;
      this.closeChooser();
      this.makeOffset(l, d);
    };
    inp.addEventListener('keydown', (x) => { x.stopPropagation(); if (x.key === 'Enter') go(); if (x.key === 'Escape') this.closeChooser(); });
    box.querySelector('button').addEventListener('click', go);
    setTimeout(() => { inp.focus(); inp.select(); }, 0);
  }

  async makeOffset(l, d) {
    const f = this.f;
    if (l.kind === 'block') {
      const e = l.e, k = e.scale || 1;
      const res = await fetch('/api/model/sketch/offset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ polys: e.polys, d: d / k }) });
      const r = await res.json();
      if (!res.ok) { this.m.toast(r.error, 'error'); return; }
      const xs = r.polys.flatMap((p) => p[0].map((q) => q[0])), ys = r.polys.flatMap((p) => p[0].map((q) => q[1]));
      this.step();
      const id = this.newId('b');
      f.entities.push({ ...e, id, name: `${e.name || 'outline'} (offset ${fmt(d)})`, polys: r.polys, w0: Math.max(...xs) - Math.min(...xs), h0: Math.max(...ys) - Math.min(...ys) });
      this.sel = { kind: 'entity', id };
      this.changed();
      return;
    }
    // a circle / a loop: the copy is held by a ⧈ Offset relation (constraints.py `off`) — it follows its original
    if (l.kind === 'circle') {
      const r = l.e.r + d;
      if (!(r > 0)) { this.m.toast('That distance is bigger than the circle.', 'error'); return; }
      await this.relock(() => {
        const id = this.newId('c');
        f.entities.push({ id, t: 'circle', c: l.e.c, r: +r.toFixed(6) });
        f.constraints.push({ id: this.newId('k'), t: 'off', user: true, d, pairs: [[l.e.id, id, 1]], src: [l.e.id], copies: [id] });
      });
      this.changed();
      return;
    }
    let geo;
    try { geo = this.offsetLoop(l.order, d); } catch (err) { this.m.toast(err.message, 'error', 6000); return; }
    await this.relock(() => {
      const ids = geo.corners.map((p) => { const id = this.newId('p'); f.points[id] = p.map((v) => +v.toFixed(9)); return id; });
      const pairs = [];
      geo.pieces.forEach((pc, k) => {
        const a = ids[(k - 1 + ids.length) % ids.length], b = ids[k], fwd = pc.t === 'line' ? l.order[k].from === pc.src.a : pc.ccw;
        const id = this.newId(pc.t === 'line' ? 'l' : 'a'); // (its ends as its original's: a <-> a)
        f.entities.push(pc.t === 'line' ? { id, t: 'line', a: fwd ? a : b, b: fwd ? b : a } : { id, t: 'arc', c: pc.c, a: fwd ? a : b, b: fwd ? b : a });
        pairs.push([pc.src.id, id, pc.w]);
      });
      f.constraints.push({ id: this.newId('k'), t: 'off', user: true, d, pairs, src: pairs.map((x) => x[0]), copies: pairs.map((x) => x[1]) });
    });
    this.changed();
  }

  /** The ⧈ linked offset a shape is the copy (or the original) of -> its relation, or null. */
  offsetOf(id, copy = true) { return this.f.constraints.find((k) => k.t === 'off' && (copy ? k.copies : k.src)?.includes(id)) || null; }

  /** ⧈ The offset's distance typed: the copy moves (its original stays); a negative number puts it on the other side. */
  async setOffset(id, value) {
    const k = this.f.constraints.find((x) => x.id === id && x.t === 'off'), v = parseFloat(String(value).replace(',', '.'));
    if (!k) return;
    if (!Number.isFinite(v) || !v) { this.m.toast('Type a distance (not 0).', 'warning'); return; }
    const orig = new Set(k.src.flatMap((c) => entPts(this.ent(c) || {}))); // (a copy arc shares its original's centre)
    const own = new Set(k.copies.flatMap((c) => entPts(this.ent(c) || {})).filter((p) => !orig.has(p)));
    const hold = Object.fromEntries(Object.keys(this.f.points).filter((p) => !own.has(p)).map((p) => [p, this.P(p)]));
    await this.relock(() => { k.d = Math.sign(k.d || 1) * v; }, hold);
  }

  /** ⛓ Unlink: the copy stays where it is as a one-off copy (its lines keep their original's horizontal / vertical). */
  async unlinkOffset(id) {
    await this.relock(() => {
      const k = this.f.constraints.find((x) => x.id === id);
      if (!k) return;
      this.f.constraints = this.f.constraints.filter((x) => x !== k);
      for (const [o, c] of k.pairs || []) {
        if (!this.ent(c)) continue;
        for (const x of this.f.constraints.filter((x) => x.e === o && (x.t === 'h' || x.t === 'v'))) this.f.constraints.push({ id: this.newId('k'), t: x.t, e: c });
      }
    });
  }

  /** A ⧈ offset's distance label: ⧈ and the value (click = type a new one). */
  offLabel(k, u, v) {
    const el = document.createElement('div');
    el.className = 'sk-label edit dist locked';
    el.dataset.off = k.id;
    el.innerHTML = '<span class="sk-val"></span>';
    el.querySelector('.sk-val').textContent = `⧈ ${fmt(Math.abs(k.d))}`;
    el.querySelector('.sk-val').title = t('Offset distance — click to type a new one (the copy follows its original)');
    el.querySelector('.sk-val').addEventListener('click', (ev) => {
      ev.stopPropagation();
      const inp = document.createElement('input');
      inp.className = 'sk-input';
      inp.value = fmt(Math.abs(k.d));
      const r = el.getBoundingClientRect(), vr = this.m.els.viewport.getBoundingClientRect();
      Object.assign(inp.style, { left: `${r.left - vr.left}px`, top: `${r.top - vr.top - 2}px` });
      this.m.els.viewport.appendChild(inp);
      inp.focus();
      inp.select();
      let done = false;
      const finish = (ok) => { if (done) return; done = true; inp.remove(); if (ok && inp.value.trim() !== '') this.setOffset(k.id, inp.value); };
      inp.addEventListener('keydown', (x) => { x.stopPropagation(); if (x.key === 'Enter') finish(true); if (x.key === 'Escape') finish(false); });
      inp.addEventListener('blur', () => finish(true));
    });
    for (const ev of ['pointerdown', 'pointerup']) el.addEventListener(ev, (x) => x.stopPropagation());
    return { el, u, v };
  }

  /** A corner under the mouse that can be rounded (two lines meet there) -> a hover target, or null. */
  cornerAt(uv) {
    const tol = this.mpp() * 10;
    let best = null;
    for (const [id, p] of Object.entries(this.f.points)) {
      const d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol && (!best || d < best.d) && cornerLines(this.f, id)) best = { d, kind: 'point', end: id, uv: p, corner: true };
    }
    return best;
  }

  /** ◜ Round corner: the corner gets an arc (radius: a fifth of the shorter line, locked), then type the radius. */
  async roundAt(uv) {
    const h = this.cornerAt(uv);
    if (!h) { this.m.toast('Click a corner where two lines meet.', 'info', 3000); return; }
    const { u1, u2 } = cornerLines(this.f, h.end), r0 = Math.min(u1[2], u2[2]) / 5;
    const r = r0 >= 1 ? Math.round(r0) : +r0.toFixed(1);
    let arc = null;
    await this.relock(() => {
      arc = roundCorner(this.f, h.end, r, (pre) => this.newId(pre));
      this.f.dims.push({ id: this.newId('d'), t: 'rad', e: arc, v: r });
    });
    if (!arc || !this.ent(arc)) return;
    this.sel = { kind: 'entity', id: arc };
    this.changed();
    await nextFrames();
    const d = this.findDim({ t: 'rad', e: arc });
    const el = d && this.m.els.viewport.querySelector(`.sk-label[data-dim="${d.id}"]`);
    if (el) this.editLabel(el, { t: 'rad', e: arc });
  }

  /** Arc tool: start, end, then a point it goes through (the bend). */
  /** An arc started at the loose end of a line continues it: that line and its direction (pointing out of the end). */
  tangentStart(s) {
    if (!s?.id || s.id === ORIGIN) return null;
    const ents = this.f.entities.filter((e) => [e.a, e.b, e.c].includes(s.id));
    if (ents.length !== 1 || ents[0].t !== 'line') return null;
    const l = ents[0], o = this.P(l.a === s.id ? l.b : l.a), p = this.P(s.id), L = Math.hypot(p[0] - o[0], p[1] - o[1]);
    return L > 1e-9 ? { line: l.id, d: [(p[0] - o[0]) / L, (p[1] - o[1]) / L] } : null;
  }

  arcPoint(s, free = false) {
    if (!this.start) { this.start = s; this.tan = free ? null : this.tangentStart(s); this.m.hint(this.hint()); this.draw(); return; }
    // tangent: unless Shift, or the end is straight along the line (then it is a free arc: end, then bend)
    if (this.tan && !free && tangentArc(this.start.uv, this.tan.d, s.uv)) { this.tangentArcTo(s); return; }
    this.tan = null;
    if (!this.arcEnd) {
      if (Math.hypot(s.uv[0] - this.start.uv[0], s.uv[1] - this.start.uv[1]) < 1e-9) return;
      this.arcEnd = s;
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const geo = arcThrough(this.start.uv, this.arcEnd.uv, s.uv);
    if (!geo) { this.m.toast('Move the mouse to one side to bend the arc.', 'info', 3000); return; }
    this.step();
    const [p, q] = geo.swap ? [this.arcEnd, this.start] : [this.start, this.arcEnd];
    const a = this.pointAt(p), b = this.pointAt(q), c = this.newId('p');
    this.f.points[c] = geo.c.map((x) => +x.toFixed(6));
    const id = this.newId('a');
    this.f.entities.push({ id, t: 'arc', c, a, b, ...this.consFlag() });
    this.start = null;
    this.arcEnd = null;
    this.sel = { kind: 'entity', id };
    this.changed();
  }

  /** The second click of a tangent arc: where it ends. */
  tangentArcTo(s) {
    const geo = tangentArc(this.start.uv, this.tan.d, s.uv);
    if (!geo) { this.m.toast('Click beside the line\'s direction to bend the arc.', 'info', 3000); return; }
    this.step();
    const a0 = this.start.id, b0 = this.pointAt(s), c = this.newId('p');
    this.f.points[c] = geo.c.map((x) => +x.toFixed(6));
    const id = this.newId('a');
    this.f.entities.push({ id, t: 'arc', c, a: geo.swap ? b0 : a0, b: geo.swap ? a0 : b0, ...this.consFlag() });
    this.f.constraints.push({ id: this.newId('k'), t: 'tan', e: this.tan.line, arc: id, p: a0 });
    this.start = null;
    this.tan = null;
    this.sel = { kind: 'entity', id };
    this.changed();
  }

  /** 〰 Spline: click points — one smooth curve through them (each click an undo step). Its first point again closes
   *  it; a point that is the end of another shape joins it there and ends the curve; double-click / Enter ends it. */
  splinePoint(s, dbl) {
    if (dbl) { this.finishSpline(); return; }
    if (!this.spl) {
      this.step();
      this.spl = { id: null, pts: [this.pointAt(s)] };
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const pts = this.spl.pts, last = pts[pts.length - 1];
    if (s.id && s.id === last) return;
    const a = this.P(last), b0 = s.id ? this.P(s.id) : s.uv;
    if (Math.hypot(b0[0] - a[0], b0[1] - a[1]) < 1e-9) return;
    this.step();
    const closing = s.id && s.id === pts[0] && pts.length > 2;
    const p = closing ? pts[0] : this.pointAt(s);
    pts.push(p);
    if (!this.spl.id) {
      this.spl.id = this.newId('s');
      this.f.entities.push({ id: this.spl.id, t: 'spline', pts });
    } else this.ent(this.spl.id).pts = [...pts];
    const joins = s.id && s.id !== ORIGIN && this.f.entities.some((e) => e.id !== this.spl.id && (e.a === s.id || e.b === s.id || (e.pts || []).includes(s.id)));
    if (closing || joins) this.finishSpline();
    else this.changed();
  }

  finishSpline() {
    const sp = this.spl;
    this.spl = null;
    if (sp?.id) this.sel = { kind: 'entity', id: sp.id };
    else if (sp) { // one point only: no curve
      const used = new Set(this.f.entities.flatMap((e) => [e.a, e.b, e.c, ...(e.pts || [])]));
      for (const p of sp.pts) if (!used.has(p)) delete this.f.points[p];
    }
    this.m.hint(this.hint());
    this.changed();
  }

  linePoint(s, dbl) {
    if (dbl) { this.chain = null; this.changed(); return; }
    if (!this.chain) {
      this.step();
      this.chain = { last: this.pointAt(s), first: null };
      this.chain.first = this.chain.last;
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const prev = this.chain.last;
    const closing = s.id && s.id === this.chain.first;
    if (s.id === prev) return;
    const a = this.P(prev), b0 = s.id ? this.P(s.id) : s.uv;
    if (Math.hypot(b0[0] - a[0], b0[1] - a[1]) < 1e-9) return;
    this.step(); // every line is its own undo step
    const p = closing ? this.chain.first : this.pointAt(s);
    const b = this.P(p);
    const id = this.newId('l');
    this.f.entities.push({ id, t: 'line', a: prev, b: p, ...this.consFlag() });
    // nearly horizontal / vertical -> exactly
    const ang = Math.abs((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI);
    if (Math.min(ang, 180 - ang) < HV_DEG) { this.f.constraints.push({ id: this.newId('k'), t: 'h', e: id }); this.f.points[p] = [b[0], a[1]]; }
    else if (Math.abs(ang - 90) < HV_DEG) { this.f.constraints.push({ id: this.newId('k'), t: 'v', e: id }); this.f.points[p] = [a[0], b[1]]; }
    if (closing || (s.id && s.id !== ORIGIN && s.id !== prev && this.f.entities.some((e) => e.id !== id && (e.a === s.id || e.b === s.id)))) {
      this.chain = null; // closed, or joined onto another shape: this line is done
      this.sel = { kind: 'entity', id };
    } else this.chain.last = p;
    this.changed();
  }

  key(e) {
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && (k === 'y' || (k === 'z' && e.shiftKey))) { e.preventDefault(); this.forward(); return true; } // redo
    if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); this.back(); return true; }
    if (e.key === 'Escape') {
      if (this.tool === 'mirror' || this.tool === 'pattern') this.setTool('select');
      else if (this.mg) this.mergeCancel();
      else if (this.chooser) this.closeChooser();
      else if (this.spl) this.finishSpline();
      else if (this.start || this.chain || this.dimA || this.relPicks?.length) { this.relPicks = []; this.start = null; this.tan = null; this.arcEnd = null; this.chain = null; this.dimA = null; this.changed(); } else this.setTool('select');
      return true;
    }
    if (e.key === 'Enter' && this.spl) { this.finishSpline(); return true; }
    if (e.key === 'Delete' || e.key === 'Backspace') { this.deleteSel(); return true; }
    if (k === 'r') this.setTool('rect');
    if (k === 'l') this.setTool('line');
    if (k === 's') this.setTool('spline');
    if (k === 'c') this.setTool('circle');
    if (k === 'a') this.setTool('arc');
    if (k === 'f') this.setTool('round');
    if (k === 't') this.setTool('trim');
    if (k === 'e') this.setTool('extend');
    if (k === 'o') this.setTool('offset');
    if (k === 'd') this.setTool('dim');
    return false;
  }



  /** ⬆ A face's outline (its edges, found again each rebuild): its rings in sketch coordinates, as the last rebuild
   *  that built this sketch found them. */
  outlineRings(e) { return this.m.faceOutlines?.[this.f.id]?.[e.id] || []; }

  // ------------------------------------------------------------------ blocks (outlines from other parts)
  /** The rings of a block in sketch coordinates. */
  blockRings(e) {
    const k = e.scale || 1, [au, av] = e.at || [0, 0];
    return (e.polys || []).flatMap((poly) => poly.map((r) => r.map(([x, y]) => [au + k * x, av + k * y])));
  }

  /** Is uv inside the block's outline (even-odd over all its rings)? */
  inBlock(e, uv) {
    let inside = false;
    for (const r of this.blockRings(e)) {
      for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
        const [xi, yi] = r[i], [xj, yj] = r[j];
        if ((yi > uv[1]) !== (yj > uv[1]) && uv[0] < ((xj - xi) * (uv[1] - yi)) / (yj - yi) + xi) inside = !inside;
      }
    }
    return inside;
  }

  /** Add an outline as a block: on a face it is centred on the face's centre, on a plane its corner is at the origin. */
  addBlock(o, extra = {}) {
    this.step();
    const id = this.newId('b');
    const onFace = !this.f.plane?.datum;
    this.f.entities.push({ id, t: 'block', name: o.name, polys: o.polygons, w0: o.width, h0: o.height, scale: 1,
      at: onFace ? [-o.width / 2, -o.height / 2] : [0, 0], ...extra });
    this.sel = { kind: 'entity', id };
    this.setTool('select');
    this.m.view.lookAt(this.frame(), this.m.sketchSpan());
    this.changed();
  }

  setBlock(k, value) {
    const e = this.ent(this.sel?.id);
    const v = parseFloat(String(value).replace(',', '.'));
    if (!e || e.t !== 'block' || !Number.isFinite(v)) return;
    if (k === 'w' && v <= 0) { this.m.toast('A size must be greater than zero.', 'error'); return; }
    this.step();
    if (k === 'h' && v <= 0) { this.m.toast('A size must be greater than zero.', 'error'); return; }
    if (k === 'w') e.scale = v / e.w0;
    else if (k === 'h') e.scale = v / e.h0;
    else if (k === 'x') e.at = [v, e.at[1]];
    else if (k === 'y') e.at = [e.at[0], v];
    this.changed();
  }

  // ------------------------------------------------------------------ the dimension tool and the part's edges
  /** The edges of the part lying in the sketch plane (the outline of the face sketched on), as fixed
   *  references: dashed lines to snap to and to dimension from. */
  refs() {
    const body = this.m.result?.body, fr = this.frame();
    const marks = this.m.result?.points || {}, key = `${body?.volume}|${JSON.stringify(fr)}|${JSON.stringify(marks)}`;
    if (this._refsKey === key) return this._refs;
    // lines / points: [u, v] in the sketch; lineIds / pointIds: which edge / corner of the part they are (by the
    // names of its faces), so a dimension from them follows the part when earlier steps change
    const out = { lines: [], curves: [], points: [], lineIds: [], pointIds: [], circles: [], arcs: [], axes: [] };
    if (body) {
      const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
      const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      const tol = Math.max(this.view.size * 1e-5, 1e-4), seen = new Set();
      const fname = (i) => body.faces[i]?.name;
      const k3 = (p) => p.map((v) => v.toFixed(4)).join(',');
      const corner = new Map(); // a corner (3D) -> the names of the faces meeting there
      for (const e of body.edges) {
        const pl = e.pts;
        for (const p of [[pl[0], pl[1], pl[2]], [pl[pl.length - 3], pl[pl.length - 2], pl[pl.length - 1]]]) {
          const s = corner.get(k3(p)) || new Set();
          for (const fi of e.faces) if (fname(fi)) s.add(fname(fi));
          corner.set(k3(p), s);
        }
      }
      for (const { pts: pl, faces: efs, mid } of body.edges) {
        const uv = [];
        let on = true;
        for (let i = 0; i < pl.length; i += 3) {
          const d = [pl[i] - o[0], pl[i + 1] - o[1], pl[i + 2] - o[2]];
          if (Math.abs(dot(d, n)) > tol) { on = false; break; }
          uv.push([+dot(d, x).toFixed(5), +dot(d, y).toFixed(5)]);
        }
        if (!on || uv.length < 2) continue;
        if (uv.length === 2) {
          out.lines.push(uv);
          out.lineIds.push(efs.length === 2 && fname(efs[0]) && fname(efs[1]) ? { a: fname(efs[0]), b: fname(efs[1]), fp: mid } : null);
        } else out.curves.push(uv);
        const ends = [[pl[0], pl[1], pl[2]], [pl[pl.length - 3], pl[pl.length - 2], pl[pl.length - 1]]];
        [uv[0], uv[uv.length - 1]].forEach((p, j) => {
          const k = p.join(',');
          if (seen.has(k)) return;
          seen.add(k);
          out.points.push(p);
          const faces = [...(corner.get(k3(ends[j])) || [])];
          out.pointIds.push(faces.length ? { faces, fp: ends[j].map((v) => +v.toFixed(6)) } : null);
        });
      }
    }
    // the part's round edges (hole rims, bosses — on any level) seen square onto the sketch: their circles and centres
    if (body) {
      const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
      const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      for (const { pts: pl } of body.edges) {
        const m = pl.length / 3;
        if (m < 8 || Math.hypot(pl[0] - pl[pl.length - 3], pl[1] - pl[pl.length - 2], pl[2] - pl[pl.length - 1]) > 1e-6) continue; // closed only
        const P = (i) => [pl[3 * i], pl[3 * i + 1], pl[3 * i + 2]];
        const c3 = circleOf(P(0), P(Math.floor(m / 3)), P(Math.floor((2 * m) / 3)));
        if (!c3 || Math.abs(dot(c3.n, n)) < 0.999) continue;
        let round = true;
        for (let i = 0; i < m && round; i++) round = Math.abs(Math.hypot(...P(i).map((v, k) => v - c3.c[k])) - c3.r) < c3.r * 0.01 + 1e-6;
        if (!round) continue;
        const d = [c3.c[0] - o[0], c3.c[1] - o[1], c3.c[2] - o[2]], c = [+dot(d, x).toFixed(5), +dot(d, y).toFixed(5)], r = +c3.r.toFixed(5);
        if (!out.circles.some((q) => Math.hypot(q.c[0] - c[0], q.c[1] - c[1]) < 1e-4 && Math.abs(q.r - r) < 1e-4)) out.circles.push({ c, r });
      }
      // the part's arcs in the plane (a rounded corner, a slot's end): their centres, to snap to
      for (const uv of out.curves) {
        const m = uv.length;
        if (m < 4) continue;
        const g = circleOf([...uv[0], 0], [...uv[Math.floor(m / 2)], 0], [...uv[m - 1], 0]);
        if (!g || !uv.every((p) => Math.abs(Math.hypot(p[0] - g.c[0], p[1] - g.c[1]) - g.r) < g.r * 0.01 + 1e-6)) continue;
        const c = [+g.c[0].toFixed(5), +g.c[1].toFixed(5)];
        if (!out.arcs.some((q) => Math.hypot(q.c[0] - c[0], q.c[1] - c[1]) < 1e-4) && !out.circles.some((q) => Math.hypot(q.c[0] - c[0], q.c[1] - c[1]) < 1e-4)) out.arcs.push({ c, r: +g.r.toFixed(5) });
      }
      // the round faces' axes: square to the sketch they name the circles' centres there (a size from one follows
      // it), else a line to measure from (a shaft lying along the plane, a cross hole under it)
      for (const q of roundAxes(body, fr)) {
        if (q.dir) { out.axes.push(q); continue; }
        const on = out.circles.filter((k) => Math.hypot(k.c[0] - q.c[0], k.c[1] - q.c[1]) < 1e-4);
        for (const k of on) k.axis = k.axis || q.ref;
        if (!on.length) out.circles.push({ c: q.c, r: q.r, axis: q.ref });
      }
    }
    // the reference points (• point steps) seen square onto the sketch: snapped to, a size to one follows it
    const y = [fr.n[1] * fr.x[2] - fr.n[2] * fr.x[1], fr.n[2] * fr.x[0] - fr.n[0] * fr.x[2], fr.n[0] * fr.x[1] - fr.n[1] * fr.x[0]];
    for (const g of this.m.part.features) {
      const p = g.type === 'point' && !g.suppressed && marks[g.id];
      if (!p || g.id === this.f.id) continue;
      const d = [p[0] - fr.o[0], p[1] - fr.o[1], p[2] - fr.o[2]];
      out.points.push([+(d[0] * fr.x[0] + d[1] * fr.x[1] + d[2] * fr.x[2]).toFixed(5), +(d[0] * y[0] + d[1] * y[1] + d[2] * y[2]).toFixed(5)]);
      out.pointIds.push({ point: g.id });
    }
    this._refsKey = key;
    this._refs = out;
    return out;
  }

  /** What the dimension tool can use under the mouse: a point (a sketch point, a circle's centre, the origin,
   *  a corner of the part) or a straight line (of the sketch or an edge of the part). */
  pickTarget(uv) {
    const tol = this.mpp() * 8;
    let best = null, bestPoint = null;
    // a point (corner, centre) within reach always beats a line through it
    const near = (d, t) => {
      if (d >= tol) return;
      if (t.kind === 'point') { if (!bestPoint || d < bestPoint.d) bestPoint = { d, ...t }; } else if (!best || d < best.d) best = { d, ...t };
    };
    const segD = (a, b) => {
      const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
      return Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]);
    };
    const dirOf = (a, b) => (Math.abs(a[1] - b[1]) < 1e-7 ? 'h' : Math.abs(a[0] - b[0]) < 1e-7 ? 'v' : 's');
    const F = this.pickable;
    if (F.origin) near(Math.hypot(uv[0], uv[1]), { kind: 'point', end: ORIGIN, uv: [0, 0] });
    const hidden = this.hiddenPts();
    if (F.points) for (const [id, p] of Object.entries(this.f.points)) if (!hidden.has(id)) near(Math.hypot(p[0] - uv[0], p[1] - uv[1]), { kind: 'point', end: id, uv: p });
    if (F.mid) { // a line's middle (a little less near than a real point)
      for (const e of this.f.entities) {
        if (e.t !== 'line') continue;
        const a = this.P(e.a), b = this.P(e.b), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        near(Math.hypot(m[0] - uv[0], m[1] - uv[1]) * 1.15, { kind: 'point', end: { mid: e.id }, uv: m, mid: e.id });
      }
    }
    const R = F.edges ? this.refs() : { points: [], pointIds: [], circles: [], lines: [], lineIds: [], axes: [] };
    R.points.forEach((r, i) => near(Math.hypot(r[0] - uv[0], r[1] - uv[1]), { kind: 'point', end: R.pointIds[i]?.point ? { ref: r, point: R.pointIds[i].point } : R.pointIds[i] ? { ref: r, vertex: R.pointIds[i] } : { ref: r }, uv: r }));
    for (const q of R.circles) { // a round edge of the part: its centre (on the rim or inside it)
      const d = Math.hypot(q.c[0] - uv[0], q.c[1] - uv[1]);
      near(Math.min(d, Math.abs(d - q.r) < tol ? tol * 0.9 : Infinity), { kind: 'point', end: q.axis ? { ref: q.c, axis: q.axis } : { ref: q.c }, uv: q.c });
    }
    for (const q of R.axes) { // a round face's axis (a shaft along the plane): on the axis, or anywhere over the face
      const d = segD(q.a, q.b), end = (p) => ({ ref: p, axis: q.ref });
      near(d < tol ? d : d < q.r ? tol * 0.95 : Infinity, { kind: 'line', a: end(q.a), b: end(q.b), uvA: q.a, uvB: q.b, dir: dirOf(q.a, q.b), axis: q.ref });
    }
    for (const e of this.f.entities) {
      if ((e.t === 'circle' || e.t === 'arc') && !F.round) continue;
      if (e.t === 'line' && !F.lines) continue;
      if (e.t === 'circle') {
        const c = this.P(e.c), d = Math.hypot(c[0] - uv[0], c[1] - uv[1]);
        near(Math.min(Math.abs(d - e.r), d < e.r ? tol * 0.8 : Infinity), { kind: 'point', end: e.c, uv: c, circle: e.id });
      } else if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        near(segD(a, b), { kind: 'line', a: e.a, b: e.b, uvA: a, uvB: b, dir: dirOf(a, b), line: e.id });
      } else if (e.t === 'arc') {
        near(this.arcDist(e, uv), { kind: 'point', end: e.c, uv: this.P(e.c), arc: e.id });
      }
    }
    R.lines.forEach(([a, b], i) => {
      const id = R.lineIds[i] ? { edge: R.lineIds[i] } : {};
      near(segD(a, b), { kind: 'line', a: { ref: a, ...id }, b: { ref: b, ...id }, uvA: a, uvB: b, dir: dirOf(a, b) });
    });
    return bestPoint || best;
  }

  /** The dimensions possible between two picks: along x, along y, straight. The sketch point is the end that moves. */
  dimOptions(A, B) {
    const sketchy = (x) => typeof x === 'string' && x !== ORIGIN;
    const order = (a, b) => (sketchy(a) || !sketchy(b) ? [b, a] : [a, b]); // [fixed-ish, moving] -> dims are b - a
    const opts = [];
    const add = (t, a, b) => {
      const [p, q] = order(a, b), spec = { t, a: p, b: q }, v = this.measure(spec);
      if (Math.abs(v) > 1e-7) opts.push({ spec, v });
    };
    if (A.kind === 'point' && B.kind === 'point') {
      if (JSON.stringify(A.end) === JSON.stringify(B.end)) return [];
      add('dx', A.end, B.end);
      add('dy', A.end, B.end);
      if (Math.abs(A.uv[0] - B.uv[0]) > 1e-7 && Math.abs(A.uv[1] - B.uv[1]) > 1e-7) add('dist', A.end, B.end);
    } else if (A.kind !== B.kind) {
      const [P, L] = A.kind === 'point' ? [A, B] : [B, A];
      if (L.dir === 'h') add('dy', P.end, L.a);
      else if (L.dir === 'v') add('dx', P.end, L.a);
      else if (sketchy(L.line)) { // a slanted line of the sketch: the point's distance from it
        const spec = { t: 'pl', a: P.end, e: L.line }, v = this.measure(spec);
        if (v > 1e-7) opts.push({ spec, v });
      }
    } else if (A.line && B.line && sketchy(A.line) && sketchy(B.line) && A.line !== B.line && this.crossing(A.line, B.line)) { // two lines that cross: their angle
      const spec = this.angleSpec(A, B);
      if (spec) opts.push({ spec, v: this.measure(spec) });
    } else if (A.dir === B.dir && A.dir !== 's' && (A.line || A.a) !== (B.line || B.a)) add(A.dir === 'h' ? 'dy' : 'dx', A.a, B.a);
    return opts;
  }

  dimClick(uv, e) {
    this.closeChooser();
    const t = this.pickTarget(uv);
    if (!t) { this.m.toast('Click a point, a circle, a line or an edge of the part.', 'info', 3000); return; }
    if (!this.dimA) { this.dimA = { ...t, at: uv }; this.m.hint(this.hint()); this.draw(); this.quickSize(t, e); return; }
    const A = this.dimA;
    t.at = uv;
    this.dimA = null;
    this.m.hint(this.hint());
    this.dimBetween(A, t, e);
  }

  /** The dimension that fits two picks (what dimClick gives for a first and a second click). */
  dimBetween(A, t, e) {
    let opts;
    if (A.line && t.line === A.line) opts = [{ spec: { t: 'len', e: A.line }, v: this.measure({ t: 'len', e: A.line }) }];
    else if (A.circle && t.circle === A.circle) opts = [{ spec: { t: 'dia', e: A.circle }, v: this.measure({ t: 'dia', e: A.circle }) }];
    else if (A.arc && t.arc === A.arc) opts = [{ spec: { t: 'rad', e: A.arc }, v: this.measure({ t: 'rad', e: A.arc }) }];
    else opts = this.dimOptions(A, t);
    if (!opts.length) { this.m.toast('Those two cannot be dimensioned — pick points, or a point and a straight horizontal / vertical edge.', 'warning', 5000); this.draw(); return; }
    if (opts.length === 1) { this.addDim(opts[0]); return; }
    this.showChooser(opts, e);
  }

  /** The first click of ↔ Dimension on a line, circle or arc: its own size in a box (bottom left), ready to type
   *  (Enter locks it); a click on a second shape instead gives the distance between them. */
  quickSize(A, e) {
    const ent = this.f.entities.find((x) => x.id === (A.line || A.circle || A.arc) && typeof (A.line || A.circle || A.arc) === 'string');
    if (!ent) return;
    const spec = ent.t === 'line' ? { t: 'len', e: ent.id } : ent.t === 'circle' ? { t: 'dia', e: ent.id } : ent.t === 'arc' ? { t: 'rad', e: ent.id } : null;
    if (!spec) return;
    let v;
    try { v = this.measure(spec); } catch { return; }
    const box = document.createElement('div');
    box.className = 'sk-choose sk-quick';
    // in the view's bottom-left corner: over no shape (a second click on any of them stays free)
    const k = this.shownFactor(spec), round = spec.t !== 'len';
    box.innerHTML = `<label>${spec.t === 'len' ? t('Length') : (spec.t === 'dia') === (k === 1) ? 'Ø' : 'R'} <input type="text" value="${fmt(Math.abs(v) * k)}"> mm
      ${round ? `<button class="mini" data-rd title="${t('Radius or diameter')}">R ⇄ Ø</button>` : ''}</label>
      <p class="hint">${t('Enter: this size — or click a second shape for a distance')}</p>`;
    const inp = box.querySelector('input');
    box.querySelector('[data-rd]')?.addEventListener('click', () => { this.flipRound(ent.id); this.quickSize(A, e); });
    inp.addEventListener('keydown', async (ev) => {
      ev.stopPropagation();
      if (ev.key === 'Escape') { this.closeChooser(); this.dimA = null; this.m.hint(this.hint()); this.draw(); }
      if (ev.key !== 'Enter') return;
      const typed = inp.value.trim();
      this.closeChooser();
      this.dimA = null;
      this.m.hint(this.hint());
      await this.addDim({ spec, v }, { edit: false });
      const typedV = parseFloat(typed.replace(',', '.')) / k;
      if (typed && Number.isFinite(typedV) && Math.abs(typedV - Math.abs(v)) > 1e-9) this.setSize(spec, String(typedV));
    });
    for (const ev of ['pointerdown', 'pointerup']) box.addEventListener(ev, (x) => x.stopPropagation());
    this.m.els.viewport.appendChild(box);
    floatBox(box, this.m.els.viewport, { kind: 'sk-quick' }); // (a ⠿ strip on top moves it)
    this.chooser = box;
    setTimeout(() => { inp.focus(); inp.select(); }, 0);
  }

  showChooser(opts, e) {
    const box = document.createElement('div');
    box.className = 'sk-choose';
    const vr = this.m.els.viewport.getBoundingClientRect();
    Object.assign(box.style, { left: `${e.clientX - vr.left + 12}px`, top: `${e.clientY - vr.top + 12}px` });
    const name = { dx: '↔ along x', dy: '↕ along y', dist: '⤢ straight', ang: '∠ angle', pl: '⊥ from the line' };
    box.innerHTML = '<div class="sk-choose-t">Which distance?</div>';
    for (const o of opts) {
      const b = document.createElement('button');
      b.className = 'btn small';
      b.textContent = `${name[o.spec.t]} — ${fmt(Math.abs(o.v))}`;
      b.addEventListener('click', (ev) => { ev.stopPropagation(); this.closeChooser(); this.addDim(o); });
      box.appendChild(b);
    }
    for (const t of ['pointerdown', 'pointerup']) box.addEventListener(t, (ev) => ev.stopPropagation());
    this.m.els.viewport.appendChild(box);
    floatBox(box, this.m.els.viewport, { kind: 'sk-which', handle: '.sk-choose-t', remember: 'size' }); // (opens by the mouse)
    this.chooser = box;
  }

  closeChooser() { this.chooser?.remove(); this.chooser = null; this.xf = null; this.mg = null; } // (a ✥ ⟳ ⤢ / ⛓ box: what it shows stays)

  /** Add a dimension (locked at the distance it has now), then let the user type the value right away. */
  async addDim(o, { edit = true } = {}) {
    const v = +o.v.toFixed(6);
    const held = await this.relock(() => {
      if (!this.findDim(o.spec)) this.f.dims.push({ id: this.newId('d'), ...o.spec, v });
      this.unhide(o.spec);
    }, null, null, { quiet: true });
    if (!held) { // (at the value it has, so it can only repeat what the other sizes fix)
      if (['len', 'dia', 'rad'].includes(o.spec.t)) {
        this.m.toast(t('Its size is fixed by the other sizes already — its label shows it as it is.'), 'info', 5000);
        return;
      }
      this.step();
      if (!this.findDim(o.spec)) this.f.dims.push({ id: this.newId('d'), ...o.spec, v, free: true });
      this.changed();
      this.m.toast(t('Fixed by the other sizes already — added as a reference dimension: it only measures (shown in brackets). 🔒 on it makes it drive instead of another.'), 'info', 7000);
      return;
    }
    const d = this.findDim(o.spec);
    if (!d || !edit) return;
    // labels reach the page with the next frame of the 3D view
    await nextFrames();
    const el = this.m.els.viewport.querySelector(`.sk-label[data-dim="${d.id}"]`);
    if (el) this.editLabel(el, o.spec);
  }

  async delDim(id) {
    await this.relock(() => { this.f.dims = this.f.dims.filter((d) => d.id !== id); });
  }

  // ------------------------------------------------------------------ drawing
  /** One size label: the value (click = type it and lock it) and a lock button (🔒 locked / 🔓 free). */
  label(spec, u, v, text, title) {
    const locked = !!this.findDim(spec), driven = !locked && this.driven(spec);
    const el = document.createElement('div');
    el.className = `sk-label edit${locked ? ' locked' : ''}${driven ? ' driven' : ''}`;
    // (a size the other sizes and relations set already is not "free": nothing to lock, shown with ＝)
    el.innerHTML = `<span class="sk-val"></span>${driven ? '<span class="sk-lock sk-driven">＝</span>' : '<button class="sk-lock"></button>'}`;
    el.querySelector('.sk-val').textContent = text;
    el.querySelector('.sk-val').title = `${title} — click to type it (that locks it)`;
    const lock = el.querySelector('.sk-lock');
    lock.textContent = locked ? '🔒' : driven ? '＝' : '🔓';
    lock.title = locked ? 'Locked — click to free this size' : driven ? 'Set by the other sizes and relations — nothing to lock' : 'Free — click to lock this size as it is';
    if (!driven) lock.addEventListener('click', (ev) => { ev.stopPropagation(); this.toggleLock(spec); });
    el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); if (performance.now() < (this.noClickUntil || 0)) return; this.editLabel(el, spec); });
    const dim = this.findDim(spec);
    if (dim) el.dataset.dim = dim.id;
    const x = document.createElement('button');
    x.className = 'sk-del';
    x.textContent = '✕';
    x.title = 'Hide this size (and unlock it) — ↔ Dimension on the shape shows it again';
    x.addEventListener('click', (ev) => { ev.stopPropagation(); this.hideSize(spec); });
    el.appendChild(x);
    for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
    return { el, u, v };
  }

  /** Is a size not locked but set already by the others (its shape / points fully defined)? */
  driven(spec) {
    if (!this.free) return false;
    const e = spec.e && this.ent(spec.e);
    if (e) return this.stateOf(e) === 'done';
    const pts = [spec.a, spec.b].filter((p) => typeof p === 'string' && p !== ORIGIN);
    return pts.length > 0 && pts.every((p) => !this.free.points.has(p) && !this.free.unknown?.has(p));
  }

  /** A distance label: the value (click = type a new one) and ✕ (delete the dimension). */
  distLabel(d, u, v) {
    const el = document.createElement('div');
    el.className = `sk-label edit dist${d.free ? '' : ' locked'}`;
    el.dataset.dim = d.id;
    el.innerHTML = '<span class="sk-val"></span><button class="sk-lock"></button><button class="sk-del" title="Delete this dimension">✕</button>';
    const shown = `${fmt(Math.abs(d.free ? this.measure(d) : d.v))}${d.t === 'ang' ? '°' : ''}`;
    el.querySelector('.sk-val').textContent = `${{ dx: '↔', dy: '↕', dist: '⤢', ang: '∠', pl: '⊥' }[d.t]} ${d.free ? `(${shown})` : shown}`;
    el.querySelector('.sk-val').title = d.free ? 'A reference dimension (it only measures: the other sizes drive it) — click to type a value and lock it' : 'Locked distance — click to type a new value';
    const lock = el.querySelector('.sk-lock');
    lock.textContent = d.free ? '🔓' : '🔒';
    lock.title = d.free ? 'A reference — it only measures. Click to lock it at this value (it then drives)' : 'Locked — click to make it a reference (it then only measures)';
    lock.addEventListener('click', (ev) => { ev.stopPropagation(); this.toggleLock(d); });
    el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); if (performance.now() < (this.noClickUntil || 0)) return; this.editLabel(el, d); });
    el.querySelector('.sk-del').addEventListener('click', (ev) => { ev.stopPropagation(); this.delDim(d.id); });
    for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
    return { el, u, v };
  }

  editLabel(el, spec) {
    const inp = document.createElement('input');
    inp.className = 'sk-input';
    const k = this.shownFactor(spec);
    inp.value = fmt(Math.abs(this.measure(spec)) * k);
    const r = el.getBoundingClientRect(), vr = this.m.els.viewport.getBoundingClientRect();
    Object.assign(inp.style, { left: `${r.left - vr.left}px`, top: `${r.top - vr.top - 2}px` });
    this.m.els.viewport.appendChild(inp);
    inp.focus();
    inp.select();
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      inp.remove();
      const v = parseFloat(String(inp.value).replace(',', '.'));
      if (ok && inp.value.trim() !== '') this.setSize(spec, Number.isFinite(v) && k !== 1 ? String(v / k) : inp.value);
    };
    inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') finish(true); if (ev.key === 'Escape') finish(false); });
    inp.addEventListener('blur', () => finish(true));
  }

  /** What a click with ⬚ Select picks for the suggestions: a point, a line, a circle or an arc of the sketch. */
  pickItem(uv) {
    const t = this.pickTarget(uv), own = (x) => typeof x === 'string' && x !== ORIGIN, sp = this.splineAt(uv);
    if (sp && (!t || (!(t.kind === 'point' && own(t.end) && !t.circle && !t.arc) && sp.d < t.d))) return this.pickOf(sp.e); // (a curve nearer than a line, not a point on it)
    if (!t) return null;
    const at = { ...t, at: uv };
    if (t.circle && own(t.circle)) return { kind: 'circle', id: t.circle, t: at };
    if (t.arc && own(t.arc)) return { kind: 'arc', id: t.arc, t: at };
    if (t.kind === 'line' && own(t.line)) return { kind: 'line', id: t.line, t: at };
    if (t.kind === 'point' && t.mid) return { kind: 'mid', id: t.mid, t: at };
    if (t.kind === 'point' && t.end === ORIGIN) return { kind: 'origin', id: ORIGIN, t: at };
    if (t.kind === 'point' && own(t.end)) return { kind: 'point', id: t.end, t: at };
    return null;
  }

  /** Make shapes construction (or, when they all are, part of the outline again). */
  setConstruction(ids) {
    const ents = ids.map((id) => this.ent(id)).filter(Boolean);
    if (!ents.length) return;
    this.step();
    const on = !ents.every((e) => e.construction);
    for (const e of ents) { if (on) e.construction = true; else delete e.construction; }
    this.changed();
  }

  /** What can be done with what is picked (one shape, several with Ctrl+click or a box) -> [{icon, label, title, run}]:
   *  a short list, the likeliest first — a dimension, the relation that is nearly true already, Delete —; the rest
   *  under ⋯ More… (in sections). */
  suggestions() {
    const P = this.picks || [], n = P.length;
    if (this.tool !== 'select' || this.xf || this.mg) return [];
    const MG = this.mergeItems(P);
    if (this.merging) return n ? [MG.join, MG.simplify, MG.outline].filter(Boolean) : [MG.whole]; // (⛓ Merge: what it does, nothing else)
    if (!n) return [];
    const round = (p) => p.kind === 'circle' || p.kind === 'arc';
    const rel = (type, ...ps) => ({ icon: RELATIONS[type].icon, label: t(RELATIONS[type].name), title: t(RELATIONS[type].hint || ''), run: () => this.addRelation(type, ps) });
    const at = () => { const b = this.m.els.viewport.querySelector('.view-suggest')?.getBoundingClientRect(); return { clientX: (b?.right || 300) + 8, clientY: b?.top || 300 }; };
    const between = (a, b, label) => ({ icon: '↔', label, run: () => this.dimBetween(a.t, b.t, at()) });
    const shapes = this.pickShapes(P), ids = shapes.map((e) => e.id), pts = this.pickPoints(P), loop = this.loopOfPicks(shapes);
    const kind = ids.length ? [{ icon: '┄', label: t(ids.every((id) => this.ent(id)?.construction) ? 'Part of the outline again' : 'Make it construction'), title: t('Construction shapes guide (an axis, a mirror line) but are not part of the outline'), run: () => this.setConstruction(ids) }] : [];
    const off = n === 1 && ids.length && this.offsetOf(ids[0]);
    if (off) kind.push({ icon: '⛓', label: t('Unlink the offset'), title: t('The copy stays where it is, but no longer follows its original'), run: () => this.unlinkOffset(off.id) });
    const del = ids.length ? [{ icon: '✕', label: t(ids.length > 1 ? 'Delete all' : 'Delete'), danger: true, run: () => { if (n > 1) this.sel = null; this.deleteSel(); } }] : []; // (several: the picked shapes, not the last one clicked)
    const ED = {
      move: { icon: '✥', label: t('Move…'), title: t('Type how far it goes (dx, dy) — or drag it'), run: () => this.xformBox('move') },
      rotate: { icon: '⟳', label: t('Rotate…'), title: t(this.pickPivot(P) ? 'Turn it about the picked point' : 'Turn it about its centre'), run: () => this.xformBox('rotate') },
      scale: { icon: '⤢', label: t('Scale…'), title: t('Make it bigger or smaller about its centre'), run: () => this.xformBox('scale') },
      copy: { icon: '⧉', label: t('Copy'), title: t('A copy beside it, picked — drag it where it goes'), run: () => this.copyPicks() },
      mirror: { icon: '⇋', label: t('Mirror'), title: t('Mirror it across a line or the X / Y axis'), run: () => this.mirrorPicks() },
      pattern: { icon: '⁂', label: t('Pattern'), title: t('Repeat it in a row or around a point'), run: () => this.startPattern() },
      offset: { icon: '⧈', label: t('Offset'), title: t('A copy of the closed outline a distance away — it follows its original'), run: () => this.offsetAt(null, at(), loop) },
    };
    const edit = !ids.length ? [] : [ED.move, ...(pts.length > 1 ? [ED.rotate, ED.scale] : []), ED.copy, ED.mirror, ED.pattern, ...(loop ? [ED.offset] : []), ...[MG.join, MG.simplify, MG.outline].filter(Boolean)];
    const lines = shapes.filter((e) => e.t === 'line'), hv = (id) => this.f.constraints.find((k) => (k.t === 'h' || k.t === 'v') && k.e === id)?.t;
    const rOf = (e) => (e.t === 'circle' ? e.r : this.arcR(e));
    // the relations that fit two shapes, the nearest to true first ([type, how far from true: < 1 = nearly]; of the
    // nearly true ones = Equal after ∥ / ⟂ / ◎), not those held already
    const ranked = (cands, a, b) => cands.filter(([ty]) => !this.hasRule(ty, a.id, b.id))
      .sort((x, y) => (x[1] >= 1) - (y[1] >= 1) || (x[1] < 1 && y[1] < 1 && (x[0] === 'eq') - (y[0] === 'eq')) || x[1] - y[1]);
    const lead = (cands) => (cands.filter((c) => c[1] < 1).length ? cands.filter((c) => c[1] < 1).slice(0, 2) : cands.slice(0, 1)); // (none nearly true: the nearest)
    let top = [], rels = [];
    if (n === 1) {
      const p = P[0], spec = p.kind === 'line' ? { t: 'len', e: p.id } : p.kind === 'circle' ? { t: 'dia', e: p.id } : p.kind === 'arc' ? { t: 'rad', e: p.id } : null;
      if (spec) {
        const asR = spec.t === 'len' ? null : this.shownFactor(spec) === 1 ? spec.t === 'rad' : spec.t === 'dia';
        top.push({ icon: spec.t === 'len' ? '↔' : asR ? 'R' : 'Ø', label: t(spec.t === 'len' ? 'Its length' : asR ? 'Its radius' : 'Its diameter'), run: () => this.addDim({ spec, v: this.measure(spec) }) });
        if (spec.t !== 'len') top.push({ icon: '⇄', label: t(asR ? 'Show it as a diameter' : 'Show it as a radius'), run: () => this.flipRound(p.id) });
      }
      if (off) top.push(kind.pop()); // (an offset's copy: its link first — it already follows its original's H / V)
      else if (p.kind === 'line' && !hv(p.id)) { // the nearer of horizontal / vertical first
        const a = this.P(this.ent(p.id).a), b = this.P(this.ent(p.id).b), flat = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]);
        top.push(rel(flat ? 'h' : 'v', p));
        rels.push(rel(flat ? 'v' : 'h', p));
      }
      if (p.kind === 'circle' && loop && !off) top.push(ED.offset);
      if (p.kind === 'point' && !this.f.constraints.some((k) => k.t === 'fix' && k.p === p.id)) top.push(rel('fix', p));
    } else if (n === 2 && !P.some((q) => q.kind === 'spline')) {
      const [a, b] = P, [ea, eb] = [this.ent(a.id), this.ent(b.id)];
      if (a.kind === 'line' && b.kind === 'line') {
        const dir = (e) => { const p = this.P(e.a), q = this.P(e.b), L = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1; return [(q[0] - p[0]) / L, (q[1] - p[1]) / L, L]; };
        const [u, w] = [dir(ea), dir(eb)], deg = (Math.acos(Math.min(1, Math.abs(u[0] * w[0] + u[1] * w[1]))) * 180) / Math.PI;
        const c = ranked([['par', deg / 10], ['perp', (90 - deg) / 10], ['eq', Math.abs(u[2] - w[2]) / Math.max(u[2], w[2]) / 0.1]], a, b), l = lead(c);
        top.push(between(a, b, t(this.crossing(a.id, b.id) ? 'The angle between them' : 'The distance between them')), ...l.map(([ty]) => rel(ty, a, b)));
        rels.push(...c.filter((x) => !l.includes(x)).map(([ty]) => rel(ty, a, b)));
      } else if (round(a) && round(b)) {
        const ca = this.P(ea.c), cb = this.P(eb.c), dc = Math.hypot(ca[0] - cb[0], ca[1] - cb[1]), ra = rOf(ea), rb = rOf(eb), big = Math.max(ra, rb);
        const c = ranked([['conc', dc / (0.15 * big)], ['eq', Math.abs(ra - rb) / big / 0.1], ['tang', Math.min(Math.abs(dc - ra - rb), Math.abs(dc - Math.abs(ra - rb))) / (0.1 * big) + 0.5]], a, b), l = lead(c);
        top.push(between(a, b, t('The distance between their centres')), ...l.map(([ty]) => rel(ty, a, b)));
        rels.push(...c.filter((x) => !l.includes(x)).map(([ty]) => rel(ty, a, b)));
      } else if (round(a) || round(b)) {
        const [c, o] = round(a) ? [a, b] : [b, a];
        if (o.kind === 'line') top.push(between(c, o, t('From its centre to the line')), ...(this.hasRule('tang', o.id, c.id) ? [] : [rel('tang', o, c)]));
        else top.push(...(o.kind === 'point' ? [rel('coin', o, c)] : []), between(c, o, t('The distance between them'))); // (a midpoint / the origin: a distance)
      } else if (['mid', 'origin'].includes(a.kind) || ['mid', 'origin'].includes(b.kind)) { // (a line's middle, the origin)
        const [x, y] = a.kind === 'point' ? [a, b] : [b, a];
        if (x.kind === 'point' && y.kind === 'origin') top.push({ ...rel('coin', x, y), label: t('Onto the origin') });
        top.push(between(a, b, t('The distance between them')));
      } else if (a.kind === 'point' && b.kind === 'point') {
        top.push(rel('coin', a, b), between(a, b, t('The distance between them')));
      } else {
        const [p, o] = a.kind === 'point' ? [a, b] : [b, a];
        top.push({ ...rel('coin', p, o), label: t('The point on the line') }, between(p, o, t('Its distance from the line')));
      }
    } else {
      const chain = (type, ps, label) => ({ icon: RELATIONS[type].icon, label: t(label), run: () => this.addRelations(ps.slice(1).map((q) => [type, [ps[0], q]])) });
      const L = P.filter((p) => p.kind === 'line'), R = P.filter(round);
      const eqL = L.length > 1 && chain('eq', L, 'Equal — all of them'), parL = L.length > 1 && chain('par', L, 'Parallel — all of them');
      const eqR = R.length > 1 && chain('eq', R, 'Equal — all of them'), conc = R.length > 1 && chain('conc', R, 'Concentric — all of them');
      if (MG.many) top.push(MG.join, MG.simplify, ...(MG.outline ? [MG.outline] : [])); // (a chain of many pieces — an import: one curve first)
      else if (MG.closed && !loop) top.push(MG.outline); // (closed outlines picked, holes and all: one rigid outline first)
      if (loop) top.push(ED.offset, ...(MG.outline && !MG.many ? [MG.outline] : []), ED.pattern, ED.move);
      else if (L.length === n) top.push(eqL, parL, ED.move);
      else if (R.length === n) top.push(eqR, conc, ED.move);
      else top.push(...(ids.length ? [ED.move, ED.copy, ED.mirror] : []));
      const loose = L.filter((p) => !hv(p.id));
      if (loose.length) rels.push({ icon: '─', label: t('Horizontal — all of them'), run: () => this.addRelations(loose.map((p) => ['h', [p]])) },
        { icon: '│', label: t('Vertical — all of them'), run: () => this.addRelations(loose.map((p) => ['v', [p]])) });
      rels.push(...[eqL, parL, eqR, conc].filter(Boolean));
    }
    const fix = pts.filter((id) => !this.f.constraints.some((k) => k.t === 'fix' && k.p === id));
    if (n > 1 && fix.length) rels.push({ icon: '📌', label: t('Fix — all their points'), run: () => this.addRelations(fix.map((id) => ['fix', [{ kind: 'point', id }]])) });
    // a slot / rectangle / circle drawn piece by piece: the real thing first; overlapping closed shapes: one outline
    const std = ids.length ? standardShapes(this.f, (p) => this.P(p)).find((sh) => ids.some((id) => sh.ids.includes(id))) : null;
    const STD = { slot: ['⊂⊃', 'Make it a slot', 'Its sides tangent to its round ends, the ends equal — one slot, sized by its centres and one radius'],
      rect: ['▭', 'Make it a rectangle', 'Its sides horizontal / vertical — one rectangle, sized by its width and height'],
      circle: ['◯', 'Make it a circle', 'The two arcs on one centre become one circle'] };
    if (std) top.unshift({ icon: STD[std.kind][0], label: t(STD[std.kind][1]), title: t(STD[std.kind][2]), run: () => this.convertShape(std) });
    if (ids.length > 1 && shapes.length <= 80 && this.overlapping()) top.unshift({ icon: '∪', label: t('Unite overlapping shapes'), title: t('Closed shapes overlap: trim the pieces inside each other — one outline of lines and arcs (tangents and equal radii stay)'), run: () => this.unite() });
    // ranked for the table (suggest.js shows the most relevant, the rest under ⋯ Show all): the likeliest four,
    // Delete, the rest of the likeliest; then two shapes — the other relations, the kind, the edits; more shapes —
    // the edits, the kind, the relations
    top = top.filter(Boolean);
    const first = [...top.map((x, k) => ({ ...x, rank: k < 4 ? k : k + 1 })), ...del.map((x) => ({ ...x, rank: Math.min(top.length, 4) }))];
    const order = n > 2 ? { Edit: 10, Kind: 20, Relations: 30 } : { Relations: 10, Kind: 20, Edit: 30 };
    const more = [['Edit', edit], ['Relations', rels], ['Kind', kind]].map(([s, its]) => [s, its.filter((x) => x && !top.includes(x)).map((x, k) => ({ ...x, rank: order[s] + k }))]).filter(([, its]) => its.length).sort((a, b) => order[a[0]] - order[b[0]]); // (the sections in that order too)
    return [...first, ...more.flatMap(([s, its]) => [{ section: t(s) }, ...its])];
  }

  /** The suggestions table (bottom left) for what is picked. */
  renderSuggest() {
    const items = this.suggestions(), P = this.picks || [], n = P.length, ns = this.pickShapes(P).length;
    const kind = { line: 'A line', circle: 'A circle', arc: 'An arc', spline: 'A smooth curve', point: 'A point', mid: "A line's midpoint", origin: 'The origin' }[P[0]?.kind];
    const what = P.map((q) => { // (as the AI's tools name them)
      const e = this.ent(q.id);
      if (q.kind === 'mid') return `${t('the middle of line')} ${q.id}`;
      if (q.kind === 'origin') return t('the origin');
      if (q.kind === 'point') return `${t('point')} ${q.id} (${(this.P(q.id) || []).map(fmt).join(', ')})`;
      return `${{ line: t('line'), circle: t('circle'), arc: t('arc'), spline: t('curve') }[q.kind] || q.kind} ${q.id}${e?.t === 'circle' ? ` (Ø${fmt(2 * e.r)})` : e?.t === 'line' ? ` (${fmt(this.measure({ t: 'len', e: e.id }))} mm)` : ''}`;
    });
    const count = (k, one, many) => (k === 1 ? t(one) : tv(many, { n: k }));
    const title = this.merging && !n ? `⛓ ${t('Merge')}` : n === 1 ? t(kind || 'Selected') : [ns && count(ns, '1 shape', '{n} shapes'), n - ns && count(n - ns, '1 point', '{n} points')].filter(Boolean).join(', ');
    const sg = showSuggest(this.m.els.viewport, title, items,
      this.merging ? t('Click or drag a box over the shapes to merge — each click adds one') : n === 1 ? t('Ctrl+click another shape: what fits the two') : ns ? t('Drag one of them: they all move together') : '', `${t('in the sketch')} ${this.f.id} “${this.f.name || ''}”: ${what.join(', ')}`);
    if (sg) sg.dataset.from = 'sketch';
  }

  // ------------------------------------------------------------------ the picks as a whole
  /** The picked lines, circles, arcs and smooth curves. */
  pickShapes(P = this.picks || []) { return P.filter((q) => ['line', 'circle', 'arc', 'spline'].includes(q.kind)).map((q) => this.ent(q.id)).filter(Boolean); }

  /** The points the picks move: their shapes' points and the picked points (not the origin). */
  pickPoints(P = this.picks || []) {
    return [...new Set([...this.pickShapes(P).flatMap(entPts), ...P.filter((q) => q.kind === 'point').map((q) => q.id)])].filter((id) => id !== ORIGIN && this.f.points[id]);
  }

  /** A picked point (or the origin) next to picked shapes: what they turn / scale about -> [u, v] or null. */
  pickPivot(P = this.picks || []) {
    const q = this.pickShapes(P).length && P.find((x) => x.kind === 'point' || x.kind === 'origin');
    return q ? [...this.P(q.id)] : null;
  }

  /** What the picks turn / scale about: a picked point, else the middle of their box (circles whole). */
  pickCentre(P = this.picks || []) {
    const piv = this.pickPivot(P);
    if (piv) return piv;
    const box = [];
    for (const id of this.pickPoints(P)) box.push(this.P(id));
    for (const e of this.pickShapes(P)) if (e.t === 'circle') { const c = this.P(e.c); box.push([c[0] - e.r, c[1] - e.r], [c[0] + e.r, c[1] + e.r]); }
    const xs = box.map((p) => p[0]), ys = box.map((p) => p[1]);
    return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  }

  /** Is this (what hit() found) among the picks: a picked shape, a point of one, a picked point, a picked side's rectangle. */
  inPicks(h) {
    const P = this.picks || [], shapes = this.pickShapes(P);
    if (h.kind === 'point') return P.some((q) => q.kind === 'point' && q.id === h.id) || shapes.some((e) => entPts(e).includes(h.id));
    if (h.kind === 'group') return shapes.some((e) => e.g === h.id);
    return shapes.some((e) => e.id === h.id);
  }

  /** The picks again where their shapes are now (after a move); gone ones dropped. */
  refreshPicks() {
    this.picks = (this.picks || []).map((q) => (['line', 'circle', 'arc', 'spline'].includes(q.kind) ? (this.ent(q.id) ? this.pickOf(this.ent(q.id)) : null)
      : q.kind === 'point' ? (this.f.points[q.id] ? { ...q, t: { ...q.t, uv: [...this.P(q.id)] } } : null) : q)).filter(Boolean);
  }

  /** The picked shapes as one closed outline (a circle, or lines / arcs joined all round, nothing else) -> loopFrom's
   *  {kind, ids, order} or null. */
  loopOfPicks(shapes = this.pickShapes()) {
    if (!shapes.length) return null;
    const l = this.loopFrom(shapes[0]), ids = new Set(shapes.map((e) => e.id));
    return l && l.ids.length === ids.size && l.ids.every((id) => ids.has(id)) ? l : null;
  }

  /** A relation already holds between these two (∥ / ⟂ also by their own H / V). */
  hasRule(type, a, b) {
    const hv = (id) => this.f.constraints.find((k) => (k.t === 'h' || k.t === 'v') && k.e === id)?.t;
    if (type === 'par' && hv(a) && hv(a) === hv(b)) return true;
    if (type === 'perp' && hv(a) && hv(b) && hv(a) !== hv(b)) return true;
    return this.f.constraints.some((k) => k.t === type && ((k.e === a && k.e2 === b) || (k.e === b && k.e2 === a)));
  }

  /** Several relations as one undo step ([[type, picks]]), each tried in turn: one the others hold already is left out. */
  async addRelations(list) {
    const base = this.undo.length;
    let made = 0;
    for (const [type, ps] of list) if (await this.relock(() => this.f.constraints.push(this.relationOf(type, ps)), null, null, { quiet: true })) made++;
    this.undo.length = Math.min(this.undo.length, base + 1);
    if (!made) this.m.toast(t('That does not fit the other locked sizes — unlock one of them first.'), 'warning', 5000);
  }

  /** ✥ ⟳ ⤢ The picked shapes moved by [dx, dy], turned by an angle (°) or scaled by a factor about pickCentre — their
   *  points held there while the solver keeps their relations; refused (a toast naming the locks) when a lock ties
   *  them to what does not go along. -> true when done. */
  async transformPicks(kind, v, P = this.picks || [], { quiet = false } = {}) {
    const ids = this.pickPoints(P), shapes = this.pickShapes(P);
    if (!ids.length) return false;
    const c = this.pickCentre(P), a = kind === 'rotate' ? (v * Math.PI) / 180 : 0, cos = Math.cos(a), sin = Math.sin(a);
    const to = (p) => (kind === 'move' ? [p[0] + v[0], p[1] + v[1]] : kind === 'rotate' ? [c[0] + (p[0] - c[0]) * cos - (p[1] - c[1]) * sin, c[1] + (p[0] - c[0]) * sin + (p[1] - c[1]) * cos]
      : [c[0] + (p[0] - c[0]) * v, c[1] + (p[1] - c[1]) * v]);
    const hold = Object.fromEntries(ids.map((id) => [id, to(this.P(id)).map((x) => +x.toFixed(9))]));
    if (kind === 'scale') { // (a circle's size is not a point: its lock is checked here)
      const d = this.f.dims.find((x) => x.t === 'dia' && !x.free && shapes.some((e) => e.id === x.e));
      if (d) { if (!quiet) this.m.toast(tv('Locked sizes hold the selection where it is ({names}) — unlock one of them first.', { names: this.dimName(d) }), 'error', 7000); return false; }
    }
    return this.relock(() => {
      for (const [id, p] of Object.entries(hold)) this.f.points[id] = p; // (they start there)
      if (kind === 'scale') for (const e of shapes) if (e.t === 'circle') e.r = +(e.r * v).toFixed(9);
      if (kind === 'rotate') this.turnRules(new Set(shapes.filter((e) => e.t === 'line').map((e) => e.id)), new Set(ids), v);
    }, hold, null, { quiet, exact: true });
  }

  /** The rules of turned lines: a quarter turn swaps H and V (and a dx / dy lock between two turned points), a half
   *  turn keeps them; any other angle puts ∥ / ⟂ in their place (a rectangle stays one). */
  turnRules(lines, pts, deg) {
    const f = this.f, q = Math.round(deg / 90), square = Math.abs(deg - q * 90) < 1e-9, n = ((q % 4) + 4) % 4;
    const hv = f.constraints.filter((k) => (k.t === 'h' || k.t === 'v') && lines.has(k.e));
    if (square) {
      if (n % 2) for (const k of hv) k.t = k.t === 'h' ? 'v' : 'h';
      for (const d of f.dims) {
        if ((d.t !== 'dx' && d.t !== 'dy') || !pts.has(d.a) || !pts.has(d.b)) continue;
        let w = d.t === 'dx' ? [d.v, 0] : [0, d.v];
        for (let i = 0; i < n; i++) w = [-w[1], w[0]];
        Object.assign(d, Math.abs(w[0]) > Math.abs(w[1]) ? { t: 'dx', v: w[0] } : { t: 'dy', v: w[1] });
      }
      return;
    }
    const H = hv.filter((k) => k.t === 'h').map((k) => k.e), V = hv.filter((k) => k.t === 'v').map((k) => k.e);
    f.constraints = f.constraints.filter((k) => !hv.includes(k));
    for (const [a, b] of [...H.slice(1).map((e) => [H[0], e]), ...V.slice(1).map((e) => [V[0], e])]) f.constraints.push({ id: this.newId('k'), t: 'par', user: true, e: a, e2: b });
    if (H.length && V.length) f.constraints.push({ id: this.newId('k'), t: 'perp', user: true, e: H[0], e2: V[0] });
  }

  /** ✥ Move / ⟳ Rotate / ⤢ Scale the picks: a small box (bottom left) — dx and dy, the angle or the factor — shown at
   *  once and as it is typed (one undo step for all of it); Enter = done, Esc = back as it was. */
  xformBox(kind) {
    const P = [...(this.picks || [])];
    if (!this.pickPoints(P).length) return;
    this.closeChooser();
    this.xf = { kind, picks: P, base: this.undo.length, orig: this.snapshot(), shown: false };
    const box = document.createElement('div');
    box.className = 'sk-choose sk-quick sk-xform';
    const field = (k, label, v, unit) => `<label>${label} <input type="text" data-xk="${k}" value="${v}"> ${unit}</label>`;
    box.innerHTML = `<div class="sk-choose-t">${{ move: '✥', rotate: '⟳', scale: '⤢' }[kind]} ${t({ move: 'Move', rotate: 'Rotate', scale: 'Scale' }[kind])}</div>
      ${kind === 'move' ? field('dx', 'dx', 0, 'mm') + field('dy', 'dy', 0, 'mm') : kind === 'rotate' ? field('a', t('Angle'), 90, '°') : field('k', t('Factor'), 2, '×')}
      <p class="hint">${t(kind === 'move' ? 'Or drag one of them.' : this.pickPivot(P) ? 'About the picked point.' : 'About their centre.')} ${t('Enter = done')}</p>
      <button class="btn small primary" data-done>${t('Done')}</button>`;
    for (const ev of ['pointerdown', 'pointerup']) box.addEventListener(ev, (x) => x.stopPropagation());
    const typed = () => {
      const v = Object.fromEntries([...box.querySelectorAll('[data-xk]')].map((i) => [i.dataset.xk, parseFloat(i.value.replace(',', '.'))]));
      return kind === 'move' ? [v.dx, v.dy] : kind === 'rotate' ? v.a : v.k;
    };
    const done = async () => { clearTimeout(this.xfTimer); if (await this.xformTo(typed()) && this.chooser === box) { this.closeChooser(); this.refreshPicks(); this.changed(); } };
    for (const inp of box.querySelectorAll('[data-xk]')) {
      inp.addEventListener('input', () => { clearTimeout(this.xfTimer); this.xfTimer = setTimeout(() => this.xformTo(typed(), true), 300); });
      inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Escape') this.xformCancel(); if (ev.key === 'Enter') done(); });
    }
    box.querySelector('[data-done]').addEventListener('click', done);
    this.m.els.viewport.appendChild(box);
    this.chooser = box;
    this.renderSuggest(); // (the table goes while the box is open)
    if (kind !== 'move') this.xformTo(typed(), true); // (shown at once: one click does it)
    setTimeout(() => { const i = box.querySelector('[data-xk]'); if (i && this.chooser === box) { i.focus(); i.select(); } }, 0);
  }

  /** The picks as the box asks (v: [dx, dy], an angle or a factor), from where they were when it opened. quiet: while
   *  typing (a refusal says nothing yet). One at a time. -> true when they are so. */
  xformTo(v, quiet = false) {
    const run = async () => {
      const xf = this.xf;
      if (!xf) return false;
      if (xf.shown) { Object.assign(this.f, structuredClone(xf.orig)); this.undo.length = xf.base; xf.shown = false; } // (back where it was, then anew)
      const bad = xf.kind === 'move' ? !v.every(Number.isFinite) : xf.kind === 'scale' ? !(v > 0) : !Number.isFinite(v);
      const none = !bad && (xf.kind === 'move' ? !v[0] && !v[1] : xf.kind === 'scale' ? v === 1 : v % 360 === 0);
      if (bad || none) {
        if (bad && !quiet) this.m.toast(t(xf.kind === 'scale' ? 'Type a factor greater than 0 (2 = twice as big).' : 'Type a number.'), 'warning');
        this.changed();
        return !bad;
      }
      const ok = await this.transformPicks(xf.kind, v, xf.picks, { quiet });
      if (ok && this.xf === xf) xf.shown = true;
      return ok;
    };
    this.xfBusy = (this.xfBusy || Promise.resolve()).then(run, run);
    return this.xfBusy;
  }

  /** Esc in the box: the picks back where they were, the box gone. */
  xformCancel() {
    clearTimeout(this.xfTimer);
    const run = async () => {
      const xf = this.xf;
      if (xf?.shown) { Object.assign(this.f, structuredClone(xf.orig)); this.undo.length = xf.base; }
      this.closeChooser();
      this.refreshPicks();
      this.changed();
    };
    this.xfBusy = (this.xfBusy || Promise.resolve()).then(run, run);
  }

  /** ⧉ Copy: the picked shapes again, a little beside them (their H / V, tangents and locked sizes along) — picked,
   *  ready to drag where they go. */
  async copyPicks() {
    const shapes = this.pickShapes();
    if (!shapes.length) return;
    const g = this.gridStep() * 2, picked = new Set(shapes.map((e) => e.id)), map = {}, emap = {}, groups = {};
    const ok = await this.relock(() => {
      const f = this.f;
      for (const id of [...new Set(shapes.flatMap(entPts))]) { const p = this.P(id); map[id] = this.newId('p'); f.points[map[id]] = [+(p[0] + g).toFixed(6), +(p[1] - g).toFixed(6)]; }
      for (const e of shapes) {
        const c = { ...structuredClone(e), id: (emap[e.id] = this.newId(e.t === 'circle' ? 'c' : e.t === 'arc' ? 'a' : e.t === 'spline' ? 's' : 'l')) };
        for (const k of ['a', 'b', 'c']) if (typeof e[k] === 'string') c[k] = map[e[k]];
        if (e.pts) c.pts = e.pts.map((q) => map[q]);
        delete c.g;
        if (e.g && f.entities.every((x) => x.g !== e.g || picked.has(x.id))) c.g = groups[e.g] || (groups[e.g] = this.newId('r')); // (a whole rectangle stays one)
        f.entities.push(c);
      }
      for (const k of [...f.constraints]) {
        if ((k.t === 'h' || k.t === 'v') && emap[k.e]) f.constraints.push({ id: this.newId('k'), t: k.t, e: emap[k.e] });
        if (k.t === 'tan' && emap[k.e] && emap[k.arc] && map[k.p]) f.constraints.push({ ...k, id: this.newId('k'), e: emap[k.e], arc: emap[k.arc], p: map[k.p] });
      }
      for (const d of [...f.dims]) if (!d.free && ['len', 'dia', 'rad'].includes(d.t) && emap[d.e]) f.dims.push({ ...d, id: this.newId('d'), e: emap[d.e] });
    });
    if (!ok) return;
    this.picks = Object.values(emap).map((id) => this.pickOf(this.ent(id))).filter(Boolean);
    this.sel = null;
    this.changed();
    this.m.toast(t('A copy — picked: drag it where it goes.'), 'info', 3500);
  }

  /** ⇋ Mirror the picked shapes: the Mirror box opens for them — the X / Y axis or a clicked line, and it is done. */
  mirrorPicks() {
    const ids = this.pickShapes().filter((e) => e.t !== 'spline').map((e) => e.id); // (a smooth curve is not mirrored yet)
    if (!ids.length) return;
    this.setTool('mirror');
    this.mirSrc = ids;
    this.m.hint(this.hint());
  }

  /** The picked shapes (mirrorPicks) mirrored across `line` at once. */
  async mirrorPicked(line) {
    const ents = (this.mirSrc || []).filter((id) => id !== line.e).map((id) => this.ent(id)).filter(Boolean);
    this.mirSrc = null;
    if (ents.length) await this.mirror(ents, line, this.mirMove);
    this.setTool('select');
  }

  // ------------------------------------------------------------------ ⛓ merge: many small shapes into few
  /** Are the picked curves connected (each shares an end with another one) / closed (every end shared by two)? */
  chainOf(curves) {
    // ends in one place (within 0.02 mm: a drawing's ends often miss each other by a hair) count as one
    const EPS = 0.02, cells = new Map(), key = (i, j) => `${i},${j}`, endsOf = (e) => (e.t === 'spline' ? [e.pts[0], e.pts[e.pts.length - 1]] : [e.a, e.b]);
    const at = curves.map((e) => endsOf(e).map((q) => this.P(q)).filter(Boolean));
    at.forEach((ps, k) => ps.forEach((p) => { const c = key(Math.floor(p[0] / EPS), Math.floor(p[1] / EPS)); cells.set(c, [...(cells.get(c) || []), [p, k]]); }));
    const near = (p) => { // how many ends are where p is
      const i = Math.floor(p[0] / EPS), j = Math.floor(p[1] / EPS);
      let n = 0;
      for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (const [q] of cells.get(key(i + a, j + b)) || []) if (Math.hypot(q[0] - p[0], q[1] - p[1]) <= EPS) n++;
      return n;
    };
    const counts = at.map((ps) => ps.map(near));
    const joined = curves.length > 1 && counts.every((cs) => cs.some((c) => c > 1));
    return { joined, closed: joined && counts.every((cs) => cs.every((c) => c % 2 === 0)) };
  }

  /** The ⛓ rows for these picks: join (a connected chain), simplify, outline (closed loops, circles), whole (nothing
   *  picked: the whole sketch); many: a chain of six pieces or more (they go first in the short list). */
  mergeItems(P) {
    const shapes = this.pickShapes(P).filter((e) => !e.construction), curves = shapes.filter((e) => e.t !== 'circle');
    const { joined, closed } = this.chainOf(curves);
    const row = (op, icon, label, title, whole = false) => ({ icon, label: t(label), title: t(title), run: () => this.mergeBox(op, whole) });
    return {
      many: joined && curves.length >= 6, closed,
      join: joined ? row('join', '⛓', 'Join into one curve', 'The connected lines, arcs and curves become one smooth curve (split only at sharp corners)') : null,
      simplify: curves.length > 1 ? row('simplify', '🧹', 'Simplify', 'Fewer shapes, the same outline: ends that nearly meet welded, tiny pieces absorbed, lines in line and arcs on one circle joined') : null,
      outline: (closed || (shapes.length && !curves.length)) && shapes.length ? row('outline', '◆', 'Make it one outline', 'The closed outline (with its holes) becomes one rigid shape: it moves, turns and scales as a whole') : null,
      whole: row('simplify', '🧹', 'Simplify the whole sketch', 'Fewer shapes, the same outline — for all the sketch', true),
    };
  }

  /** ⛓ Merge (the bar): with shapes picked, the table offers what merges them; with none, a mode — click or drag a box
   *  over shapes (each adds), then choose in the table. Again: off. */
  startMerge() {
    if (this.merging) { this.setTool('select'); return; }
    if (this.tool !== 'select') this.setTool('select');
    this.merging = true;
    this.sgMore = null;
    this.m.renderCmdBar();
    this.changed();
  }

  /** ⛓ Join / 🧹 Simplify / ◆ One outline of the picks (whole: the whole sketch) on the server — shown at once, one
   *  undo step; Join and Simplify open a small box: the tolerance (retyped: done again from where it was), the count
   *  before → after, Enter = done, Esc = back. */
  async mergeBox(op, whole = false) {
    const kinds = op === 'outline' ? ['line', 'arc', 'spline', 'circle'] : ['line', 'arc', 'spline'];
    const ids = whole ? null : this.pickShapes().filter((e) => kinds.includes(e.t) && !e.construction).map((e) => e.id);
    if (!whole && !ids.length) return;
    this.closeChooser();
    const mg = { op, ids, base: this.undo.length, orig: this.snapshot(), shown: false };
    this.mg = mg;
    if (op === 'outline') { // (nothing to type: done)
      const ok = await this.mergeTo(mg, null);
      if (this.mg === mg) this.mg = null;
      if (ok) { this.merging = false; this.m.renderCmdBar(); this.mergeSaid(mg); }
      this.changed();
      return;
    }
    const box = document.createElement('div');
    box.className = 'sk-choose sk-quick sk-xform sk-merge';
    box.innerHTML = `<div class="sk-choose-t">${op === 'join' ? `⛓ ${t('Join into one curve')}` : `🧹 ${t(whole ? 'Simplify the whole sketch' : 'Simplify')}`}</div>
      <label title="${t('How far the result may be from the shapes it replaces')}">${t('Tolerance')} <input type="text" data-mk="tol" value=""> mm</label>
      <p class="hint" data-mk="res">…</p>
      <p class="hint">${t('Enter = done, Esc = back')}</p>
      <button class="btn small primary" data-done>${t('Done')}</button>`;
    for (const ev of ['pointerdown', 'pointerup']) box.addEventListener(ev, (x) => x.stopPropagation());
    const inp = box.querySelector('[data-mk=tol]');
    const typed = () => parseFloat(inp.value.replace(',', '.'));
    const done = async () => { clearTimeout(this.mgTimer); await this.mgBusy; if (this.mg !== mg) return; if (Number.isFinite(typed()) && typed() !== mg.tol) await this.mergeTo(mg, typed()); if (this.chooser === box) { this.closeChooser(); this.merging = false; this.picks = []; this.m.renderCmdBar(); this.mergeSaid(mg); this.changed(); } }; // (done: the toast says what came of it)
    inp.addEventListener('input', () => { clearTimeout(this.mgTimer); this.mgTimer = setTimeout(() => { if (typed() > 0) this.mergeTo(mg, typed(), true); }, 350); });
    inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Escape') this.mergeCancel(); if (ev.key === 'Enter') done(); });
    box.querySelector('[data-done]').addEventListener('click', done);
    this.m.els.viewport.appendChild(box);
    this.chooser = box;
    this.mg = mg; // (closeChooser above cleared it — and the table goes while the box is open)
    this.renderSuggest();
    await this.mergeTo(mg, null);
    if (this.chooser === box && mg.report) { inp.value = fmt(mg.report.tol); setTimeout(() => { if (this.chooser === box) { inp.focus(); inp.select(); } }, 0); }
  }

  /** The merge done (again) from where the sketch was when the box opened, with this tolerance (null: the server's
   *  default for the sketch's size). One at a time. -> true when it is shown. */
  mergeTo(mg, tol, quiet = false) {
    const run = async () => {
      if (this.mg !== mg) return false;
      if (mg.shown) { Object.assign(this.f, structuredClone(mg.orig)); this.undo.length = mg.base; mg.shown = false; } // (back where it was, then anew)
      let j;
      try {
        const f = this.f, res = await fetch('/api/model/sketch/clean', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ op: mg.op, ids: mg.ids, tol, name: t('Outline'), sketch: { points: f.points, entities: f.entities, constraints: f.constraints, dims: f.dims } }) });
        j = await res.json();
        if (!res.ok || j.error) throw new Error(j.error || res.statusText);
      } catch (e) {
        if (!quiet) this.m.toast(t(e.message), 'warning', 5000);
        this.changed();
        return false;
      }
      if (this.mg !== mg) return false;
      this.step();
      Object.assign(this.f, { points: j.sketch.points, entities: j.sketch.entities, constraints: j.sketch.constraints, dims: j.sketch.dims });
      const had = new Set(mg.orig.entities.map((e) => e.id)), made = this.f.entities.filter((e) => !had.has(e.id));
      this.picks = made.map((e) => this.pickOf(e)).filter(Boolean);
      this.sel = made.length === 1 && made[0].t === 'block' ? { kind: 'entity', id: made[0].id } : null; // (an outline: its panel)
      Object.assign(mg, { shown: true, report: j.report, tol: j.report.tol });
      const res = this.chooser?.querySelector('[data-mk=res]');
      if (res) res.textContent = this.mergeText(j.report);
      this.changed();
      return true;
    };
    this.mgBusy = (this.mgBusy || Promise.resolve()).then(run, run);
    return this.mgBusy;
  }

  /** "688 → 1 shapes" (and the area, when it changed). */
  mergeText(r) {
    const moved = (r.issues || []).find((x) => x.code === 'area_changed');
    return `${tv('{a} → {b} shapes', { a: r.before.entities, b: r.after.entities })}${moved ? ` · ${t('the enclosed area changed — try a smaller tolerance')}` : ''}`;
  }

  mergeSaid(mg) { if (mg.report) this.m.toast(this.mergeText(mg.report), mg.report.issues?.length ? 'warning' : 'ok', 4000); }

  /** Esc in the ⛓ box: the sketch back as it was, the box gone. */
  mergeCancel() {
    clearTimeout(this.mgTimer);
    const mg = this.mg;
    const run = async () => {
      if (mg?.shown) { Object.assign(this.f, structuredClone(mg.orig)); this.undo.length = mg.base; this.picks = []; this.sel = null; }
      this.closeChooser();
      this.changed();
    };
    this.mgBusy = (this.mgBusy || Promise.resolve()).then(run, run);
  }

  /** {construction: true} while ┄ Construction is on (new shapes are helpers, not part of the outline). */
  consFlag() { return this.consMode ? { construction: true } : {}; }

  /** ┄ Construction: with ⬚ Select, the selected shape (or its rectangle) becomes a helper line / circle — or back;
   *  else new shapes are drawn as construction while it is on. Construction shapes guide (a revolve's axis, a
   *  mirror line, dimensions, relations) but are not part of the outline that is extruded. */
  toggleConstruction() {
    const pick = this.tool === 'select' ? this.sel : null; // (a shape just drawn is not what it means)
    const ids = pick?.kind === 'entity' ? [pick.id] : pick?.kind === 'group' ? this.f.entities.filter((e) => e.g === pick.id).map((e) => e.id) : [];
    const ents = ids.map((id) => this.ent(id)).filter((e) => e && ['line', 'circle', 'arc', 'spline'].includes(e.t));
    if (ents.length) {
      this.step();
      const on = !ents.every((e) => e.construction);
      for (const e of ents) { if (on) e.construction = true; else delete e.construction; }
      this.m.toast(t(on ? 'A construction shape now: it guides, but is not part of the outline.' : 'Part of the outline again.'), 'info', 3500);
      this.changed();
      return;
    }
    this.consMode = !this.consMode;
    this.m.renderCmdBar();
    this.m.toast(t(this.consMode ? '┄ Construction on: new lines and circles are helpers (an axis, a mirror line) — not part of the outline.' : '┄ Construction off.'), 'info', 4000);
  }

  /** What the size under the mouse measures, lit up (a layer of its own: the labels are not drawn again). */
  drawHighlight() {
    const hs = this.hoverSize?.what, mpp = this.mpp(), H = 0xf2cc60;
    if (!hs) { this.view.setSketchHighlight(null); return; }
    this.view.setSketchHighlight(this.frame(), {
      lines: (hs.lines || []).map(([a, b]) => [a, b, H]),
      circles: [...(hs.circles || []).map(([c, r]) => [c, r, H]), ...(hs.pts || []).map((p) => [p, mpp * 5, H])],
      dots: (hs.pts || []).map((p) => [p, H]),
    });
  }

  /** A shape's state for its colour: 'bad' (in a lock that does not fit), 'free' (some of it can still move),
   *  'done' (fully defined), or null (not known: no solver). */
  stateOf(e) {
    if (this.bad?.has(e.id)) return 'bad';
    if (!this.free) return null;
    const pts = e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : e.t === 'circle' ? [e.c] : e.t === 'spline' ? e.pts || [] : null;
    if (!pts) return null;
    if (pts.some((p) => this.free.points.has(p)) || this.free.radii.has(e.id)) return 'free';
    return pts.some((p) => this.free.unknown?.has(p)) || this.free.unknown?.has(e.id) ? null : 'done'; // (not checked in time)
  }

  draw() {
    const f = this.f, mpp = this.mpp(), labels = [], lines = [], circles = [], dots = [];
    const SEL = 0xf2cc60, LOCKED = 0xd2a8ff;
    // blue: can still move, green: fully defined, red: a lock that does not fit (cyan: not known)
    const CONS = 0xd29922; // construction shapes: dashed amber
    const DIM_ON = 0x8e7cc3, DIM_FREE = 0x4f5966; // dimension lines: a locked size (soft violet), a free one / a reference (faint)
    this.dimHits = []; // (filled by movable: the dimensions' lines, to drag them by)
    const STATE = { free: 0x58a6ff, done: 0x3fb950, bad: 0xff7b72 }, colourOf = (e) => STATE[this.stateOf(e)] ?? 0x39d0d8, NORM = 0x39d0d8;
    const place = f.place || {};
    // a dimension as on a drawing: extension lines, the dimension line with arrows at its ends
    const arrow = (p, d, col) => {
      const L = Math.hypot(d[0], d[1]) || 1, ux = d[0] / L, uy = d[1] / L, k = mpp * 7;
      for (const s of [0.42, -0.42]) lines.push([p, [p[0] - k * (ux * Math.cos(s) - uy * Math.sin(s)), p[1] - k * (ux * Math.sin(s) + uy * Math.cos(s))], col]);
    };
    // a round size: its label at an angle and a distance from the centre; as Ø a line across the circle (arrows on
    // both rims), as R a line from the centre (an arrow on the rim) — out to the label when it is outside
    const roundDim = (c, r, th, dist, dia, col) => {
      const u = [Math.cos(th), Math.sin(th)], rim = [c[0] + u[0] * r, c[1] + u[1] * r], at = [c[0] + u[0] * dist, c[1] + u[1] * dist];
      const out = dist > r ? at : rim, start = dia ? [c[0] - u[0] * r, c[1] - u[1] * r] : c;
      lines.push([start, out, col, true]);
      arrow(rim, u, col);
      if (dia) arrow(start, [-u[0], -u[1]], col);
      return { at, grab: [start, out] };
    };
    // dragging it: its angle and distance; dropped inside the circle it shows as Ø, outside as R
    const roundAt = (id, c, r) => (uv) => {
      const d = Math.hypot(uv[0] - c[0], uv[1] - c[1]);
      this.f.rd = { ...(this.f.rd || {}), [id]: d < r ? 'd' : 'r' };
      return [+Math.atan2(uv[1] - c[1], uv[0] - c[0]).toFixed(4), +Math.max(d, mpp * 4).toFixed(4)];
    };
    const dimLine = (a, b, a2, b2, col) => { // (dashed: they show what is measured without standing out)
      const over = (p, q) => { const d = [q[0] - p[0], q[1] - p[1]], L = Math.hypot(d[0], d[1]); return L < 1e-9 ? q : [q[0] + (d[0] / L) * mpp * 3, q[1] + (d[1] / L) * mpp * 3]; };
      if (Math.hypot(a2[0] - a[0], a2[1] - a[1]) > 1e-9) lines.push([a, over(a, a2), col, true]);
      if (Math.hypot(b2[0] - b[0], b2[1] - b[1]) > 1e-9) lines.push([b, over(b, b2), col, true]);
      lines.push([a2, b2, col, true]);
      arrow(a2, [a2[0] - b2[0], a2[1] - b2[1]], col);
      arrow(b2, [b2[0] - a2[0], b2[1] - a2[1]], col);
    };
    const selPts = new Set(this.pointsOfSel());
    const isSel = (e) => this.sel && ((this.sel.kind === 'entity' && this.sel.id === e.id) || (this.sel.kind === 'group' && this.sel.id === e.g));
    // 🏷 Sizes (the modeler's All / Locked / None; a big sketch labels only its locked sizes)
    const shows = (locked) => this.m.sizeShown?.(locked, f) ?? true;
    const freeShown = shows(false), anyShown = shows(true);
    const showSize = (spec) => anyShown && !this.isHidden(spec) && (freeShown || !!this.findDim(spec));
    const groupSide = {}; // a rectangle's width / height: the side that shows it
    for (const e of f.entities) {
      if (e.t !== 'line' || !e.g || this.isHidden({ t: 'len', e: e.id })) continue;
      const key = `${e.g}:${f.constraints.find((c) => c.e === e.id && (c.t === 'h' || c.t === 'v'))?.t}`;
      if (!groupSide[key] || (this.findDim({ t: 'len', e: e.id }) && !this.findDim({ t: 'len', e: groupSide[key] }))) groupSide[key] = e.id;
    }
    for (const e of f.entities) {
      if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        lines.push([a, b, isSel(e) ? SEL : e.construction ? CONS : colourOf(e), !!e.construction]);
        // a rectangle shows its width and height once; a free line its length
        if (e.g) { // the side with the lock shows it (a hidden side: the opposite one)
          const k = f.constraints.find((c) => c.e === e.id && (c.t === 'h' || c.t === 'v'))?.t;
          if (groupSide[`${e.g}:${k}`] !== e.id) continue;
        }
        const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (L < 1e-9 || !showSize({ t: 'len', e: e.id })) continue;
        const nx = -(b[1] - a[1]) / L, ny = (b[0] - a[0]) / L;
        // the label goes on the outside of a closed shape (away from its centre) — or where it was dragged
        const c = this.centreOf(e) || [a[0] + nx, a[1] + ny];
        const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        const side = (mid[0] - c[0]) * nx + (mid[1] - c[1]) * ny >= 0 ? 1 : -1;
        const key = `len:${e.id}`, off = place[key] ?? side * mpp * 16, spec = { t: 'len', e: e.id };
        const a2 = [a[0] + nx * off, a[1] + ny * off], b2 = [b[0] + nx * off, b[1] + ny * off];
        dimLine(a, b, a2, b2, this.findDim(spec) ? DIM_ON : DIM_FREE); // (a locked size stronger, a free one faint)
        labels.push(this.movable(this.label(spec, (a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2, fmt(L), 'Length'), key,
          (uv) => (uv[0] - a[0]) * nx + (uv[1] - a[1]) * ny, { lines: [[a, b]] }, [[a2, b2]]));
      } else if (e.t === 'outline') { // ⬆ a face's edges: fixed (they follow the face)
        for (const r of this.outlineRings(e)) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length], isSel(e) ? SEL : NORM]);
      } else if (e.t === 'block') {
        for (const r of this.blockRings(e)) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length], isSel(e) ? SEL : NORM]);
        const k = e.scale || 1, [au, av] = e.at;
        const el = document.createElement('div');
        el.className = 'sk-label edit block';
        el.innerHTML = '<span class="sk-val"></span>';
        el.querySelector('.sk-val').textContent = `↔ ${fmt(e.w0 * k)}`;
        el.querySelector('.sk-val').title = 'Width of the outline — click to type it (the height follows)';
        el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); this.editLabel(el, { t: 'bw', e: e.id }); });
        for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
        if (anyShown) labels.push({ el, u: au + (e.w0 * k) / 2, v: av - mpp * 14 });
      } else if (e.t === 'arc') {
        const ps = this.arcOf(e), col = isSel(e) ? SEL : e.construction ? CONS : colourOf(e);
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], col, !!e.construction]);
        const m = ps[Math.floor(ps.length / 2)], c = this.P(e.c), r = this.arcR(e) || 1;
        if (showSize({ t: 'rad', e: e.id })) {
          const key = `rad:${e.id}`, pl = place[key], col = this.findDim({ t: 'rad', e: e.id }) ? DIM_ON : DIM_FREE;
          const { at, grab } = roundDim(c, r, Array.isArray(pl) ? pl[0] : pl ?? Math.atan2(m[1] - c[1], m[0] - c[0]), Array.isArray(pl) ? pl[1] : r + mpp * 16, this.roundAs(e.id) === 'd', col);
          labels.push(this.movable(this.label({ t: 'rad', e: e.id }, at[0], at[1], this.roundAs(e.id) === 'd' ? `Ø${fmt(2 * r)}` : `R${fmt(r)}`, 'Radius'), key,
            roundAt(e.id, c, r), { lines: ps.slice(1).map((p, i) => [ps[i], p]), pts: [c] }, [grab]));
        }
      } else if (e.t === 'spline') {
        const ps = this.splineOf(e), col = isSel(e) ? SEL : colourOf(e);
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], col]);
      } else if (e.t === 'circle') {
        const c = this.P(e.c);
        if (e.construction) { // dashed: as 48 pieces
          for (let i = 0; i < 48; i++) {
            const a0 = (i / 48) * Math.PI * 2, a1 = ((i + 1) / 48) * Math.PI * 2;
            lines.push([[c[0] + e.r * Math.cos(a0), c[1] + e.r * Math.sin(a0)], [c[0] + e.r * Math.cos(a1), c[1] + e.r * Math.sin(a1)], isSel(e) ? SEL : CONS, true]);
          }
        } else circles.push([c, e.r, isSel(e) ? SEL : colourOf(e)]);
        if (showSize({ t: 'dia', e: e.id })) {
          const key = `dia:${e.id}`, pl = place[key], col = this.findDim({ t: 'dia', e: e.id }) ? DIM_ON : DIM_FREE;
          const { at, grab } = roundDim(c, e.r, Array.isArray(pl) ? pl[0] : pl ?? (this.offsetOf(e.id) ? (3 * Math.PI) / 4 : Math.PI / 4), // (an offset copy: not on its original's)
            Array.isArray(pl) ? pl[1] : e.r + mpp * 22, this.roundAs(e.id) !== 'r', col);
          labels.push(this.movable(this.label({ t: 'dia', e: e.id }, at[0], at[1], this.roundAs(e.id) === 'r' ? `R${fmt(e.r)}` : `Ø${fmt(2 * e.r)}`, 'Diameter'), key,
            roundAt(e.id, c, e.r), { circles: [[c, e.r]] }, [grab]));
        }
      }
    }
    for (const k of f.constraints.filter((c) => c.t === 'corner')) {
      const p = this.P(k.p);
      for (const l of k.lines.map((id) => this.ent(id)).filter(Boolean)) {
        const near = [l.a, l.b].map((q) => this.P(q)).sort((x, y) => Math.hypot(x[0] - p[0], x[1] - p[1]) - Math.hypot(y[0] - p[0], y[1] - p[1]))[0];
        if (p && near) lines.push([near, p, 0x8b95a3, true]);
      }
    }
    const hidden = this.hiddenPts();
    for (const [id, p] of Object.entries(f.points)) {
      if (hidden.has(id)) continue;
      const fixed = f.dims.some((d) => (d.t === 'dx' || d.t === 'dy') && d.b === id && d.a === ORIGIN);
      dots.push([p, selPts.has(id) ? SEL : this.free ? (this.free.points.has(id) ? STATE.free : STATE.done) : fixed ? LOCKED : NORM]);
    }
    // the part's edges in this plane (fixed references), dashed
    const refs = this.refs();
    for (const [a, b] of refs.lines) lines.push([a, b, 0x8b95a3, true]);
    for (const c of refs.curves) for (let i = 0; i + 1 < c.length; i++) lines.push([c[i], c[i + 1], 0x8b95a3, true]);
    for (const q of refs.circles) { // round edges of the part seen on the sketch: dashed, a ✛ at the centre
      for (let i = 0; i < 48; i++) {
        const a = (i / 48) * Math.PI * 2, b = ((i + 1) / 48) * Math.PI * 2;
        lines.push([[q.c[0] + q.r * Math.cos(a), q.c[1] + q.r * Math.sin(a)], [q.c[0] + q.r * Math.cos(b), q.c[1] + q.r * Math.sin(b)], 0x8b95a3, true]);
      }
      const k = mpp * 6;
      lines.push([[q.c[0] - k, q.c[1]], [q.c[0] + k, q.c[1]], 0x8b95a3], [[q.c[0], q.c[1] - k], [q.c[0], q.c[1] + k], 0x8b95a3]);
    }
    for (const q of refs.axes) { // round faces' axes along the sketch: a dashed centre line a little past the face
      const k = mpp * 10, a = q.a.map((v, i) => v - q.dir[i] * k), b = q.b.map((v, i) => v + q.dir[i] * k);
      lines.push([a, b, 0x6e9fd1, true]);
    }
    // distances (dimension tool): a dimension line from the moving end, an extension line to the other end
    for (const d of f.dims) {
      if (!shows(!d.free)) continue;
      const DC = d.free ? DIM_FREE : DIM_ON;
      if (d.t === 'ang' && this.ent(d.e) && this.ent(d.e2)) {
        const X = this.crossing(d.e, d.e2);
        if (!X) continue;
        const p = this.rayDir(d.e, d.r1), q = this.rayDir(d.e2, d.r2), a0 = Math.atan2(p[1], p[0]), sweep = (this.signedAngle(d) * Math.PI) / 180, R = place[d.id] ?? mpp * 34;
        const arc = Array.from({ length: 25 }, (_, i) => { const a = a0 + (sweep * i) / 24; return [X[0] + R * Math.cos(a), X[1] + R * Math.sin(a)]; });
        for (let i = 0; i + 1 < arc.length; i++) lines.push([arc[i], arc[i + 1], DC, i % 2 === 1]); // (dashed by turns)
        const am = a0 + sweep / 2, A1 = this.ent(d.e), A2 = this.ent(d.e2);
        arrow(arc[0], [arc[0][0] - arc[1][0], arc[0][1] - arc[1][1]], DC);
        arrow(arc[24], [arc[24][0] - arc[23][0], arc[24][1] - arc[23][1]], DC);
        labels.push(this.movable(this.distLabel(d, X[0] + (R + mpp * 14) * Math.cos(am), X[1] + (R + mpp * 14) * Math.sin(am)), d.id,
          (uv) => Math.max(mpp * 8, Math.hypot(uv[0] - X[0], uv[1] - X[1]) - mpp * 14), { lines: [[this.P(A1.a), this.P(A1.b)], [this.P(A2.a), this.P(A2.b)]] },
          arc.slice(1).map((q, i) => [arc[i], q])));
        continue;
      }
      if (d.t === 'pl' && this.ent(d.e)) {
        const e = this.ent(d.e), P = this.endUV(d.a), a = this.P(e.a), b = this.P(e.b), u = [b[0] - a[0], b[1] - a[1]], L2 = u[0] * u[0] + u[1] * u[1] || 1;
        const k = ((P[0] - a[0]) * u[0] + (P[1] - a[1]) * u[1]) / L2, foot = [a[0] + k * u[0], a[1] + k * u[1]];
        lines.push([P, foot, DC, true]);
        if (k < 0 || k > 1) lines.push([foot, k < 0 ? a : b, DC, true]); // (beyond the line's ends: on to it)
        labels.push(this.distLabel(d, (P[0] + foot[0]) / 2 + mpp * 10, (P[1] + foot[1]) / 2 + mpp * 10));
        continue;
      }
      if (!['dx', 'dy', 'dist'].includes(d.t)) continue;
      const A = this.endUV(d.a), B = this.endUV(d.b);
      if (!A || !B) continue;
      if ((d.a === ORIGIN || d.b === ORIGIN) && Math.abs(d.v) < 1e-9) continue; // "locked at the origin": the purple point says it
      // the dimension line where it was dragged (off: from the moving end, across the distance)
      const off = place[d.id] ?? 0;
      let mid, at, line, lineAt; // (lineAt: the place from the mouse on its dimension line)
      if (d.t === 'dx') {
        const y = B[1] + off, a2 = [A[0], y], b2 = [B[0], y];
        dimLine(A, B, a2, b2, DC);
        mid = [(A[0] + B[0]) / 2, y + mpp * 10];
        at = (uv) => uv[1] - B[1] - mpp * 10;
        line = [a2, b2];
        lineAt = (uv) => uv[1] - B[1];
      } else if (d.t === 'dy') {
        const x = B[0] + off, a2 = [x, A[1]], b2 = [x, B[1]];
        dimLine(A, B, a2, b2, DC);
        mid = [x + mpp * 22, (A[1] + B[1]) / 2];
        at = (uv) => uv[0] - B[0] - mpp * 22;
        line = [a2, b2];
        lineAt = (uv) => uv[0] - B[0];
      } else {
        const L = Math.hypot(B[0] - A[0], B[1] - A[1]) || 1, nx = -(B[1] - A[1]) / L, ny = (B[0] - A[0]) / L;
        const a2 = [A[0] + nx * off, A[1] + ny * off], b2 = [B[0] + nx * off, B[1] + ny * off];
        dimLine(A, B, a2, b2, DC);
        mid = [(a2[0] + b2[0]) / 2 + nx * mpp * 10, (a2[1] + b2[1]) / 2 + ny * mpp * 10];
        at = (uv) => (uv[0] - A[0]) * nx + (uv[1] - A[1]) * ny - mpp * 10;
        line = [a2, b2];
        lineAt = (uv) => (uv[0] - A[0]) * nx + (uv[1] - A[1]) * ny;
      }
      labels.push(this.movable(this.distLabel(d, mid[0], mid[1]), d.id, at, { pts: [A, B] }));
      if (Math.hypot(line[1][0] - line[0][0], line[1][1] - line[0][1]) > 1e-9) this.dimHits.push({ a: line[0], b: line[1], key: d.id, at: lineAt, what: { pts: [A, B] } });
    }
    // ⧈ linked offsets: the distance from the original to its copy (a third along a line, or across the rims)
    for (const k of shows(true) ? f.constraints.filter((c) => c.t === 'off') : []) {
      const [o, q] = (k.pairs || []).map(([a, b]) => [this.ent(a), this.ent(b)]).find(([a, b]) => a && b) || [];
      if (!o) continue;
      let A, B;
      if (o.t === 'line') {
        const a = this.P(o.a), b = this.P(o.b), qa = this.P(q.a), qb = this.P(q.b), u = [qb[0] - qa[0], qb[1] - qa[1]], L2 = u[0] * u[0] + u[1] * u[1] || 1;
        A = [a[0] + (b[0] - a[0]) / 5, a[1] + (b[1] - a[1]) / 5];
        const s = ((A[0] - qa[0]) * u[0] + (A[1] - qa[1]) * u[1]) / L2;
        B = [qa[0] + s * u[0], qa[1] + s * u[1]];
      } else {
        const c = this.P(o.c), ps = o.t === 'arc' ? this.arcOf(o) : null, m = ps ? ps[Math.floor(ps.length / 3)] : null;
        const th = m ? Math.atan2(m[1] - c[1], m[0] - c[0]) : (-3 * Math.PI) / 4, r = o.t === 'arc' ? this.arcR(o) : o.r, r2 = q.t === 'arc' ? this.arcR(q) : q.r;
        A = [c[0] + r * Math.cos(th), c[1] + r * Math.sin(th)];
        B = [c[0] + r2 * Math.cos(th), c[1] + r2 * Math.sin(th)];
      }
      if (Math.hypot(B[0] - A[0], B[1] - A[1]) < 1e-9) continue;
      lines.push([A, B, DIM_ON, true]);
      arrow(A, [A[0] - B[0], A[1] - B[1]], DIM_ON);
      arrow(B, [B[0] - A[0], B[1] - A[1]], DIM_ON);
      const L = Math.hypot(B[0] - A[0], B[1] - A[1]), u = [(B[0] - A[0]) / L, (B[1] - A[1]) / L], m = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2];
      const side = o.t === 'line' ? (((a, b) => ((a[0] - b[0]) * u[1] - (a[1] - b[1]) * u[0] < 0 ? 1 : -1))(this.P(o.a), this.P(o.b))) : 1;
      labels.push(this.offLabel(k, m[0] - side * u[1] * mpp * 26, m[1] + side * u[0] * mpp * 26)); // (beside it, toward the line's start)
    }
    this.drawHighlight();
    for (const q of this.picks || []) { // (what the suggestions are for)
      const e = this.ent(q.id);
      const qp = q.kind === 'mid' ? this.endUV({ mid: q.id }) : q.kind === 'point' || q.kind === 'origin' ? this.P(q.id) : null;
      if (qp) { dots.push([qp, SEL]); circles.push([qp, mpp * 5, SEL]); }
      else if (e?.t === 'line') lines.push([this.P(e.a), this.P(e.b), SEL]);
      else if (e?.t === 'circle') circles.push([this.P(e.c), e.r, SEL]);
      else if (e?.t === 'arc') { const ps = this.arcOf(e); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]); }
      else if (e?.t === 'spline') { const ps = this.splineOf(e); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]); }
    }
    // the guides of where the mouse is (in line with a point, on a line's extension): dashed, for the moment
    const guides = this.dragGuides || (!['select', 'dim', 'relate'].includes(this.tool) && this.cursor?.guides);
    if (guides) {
      for (const [p, q] of guides) { lines.push([p, q, 0x7ee787, true]); dots.push([p, 0x7ee787]); circles.push([p, mpp * 4, 0x7ee787]); }
    }
    // the dimension tool's first pick
    if (this.dimA) {
      if (this.dimA.kind === 'point') dots.push([this.dimA.uv, 0x7ee787]);
      else lines.push([this.dimA.uvA, this.dimA.uvB, 0x7ee787]);
    }
    // the relations the user set: a small symbol by their shape (click it to remove the relation)
    for (const k of this.userRelations()) {
      const at = this.relAt(k);
      if (!at) continue;
      const el = document.createElement('div');
      el.className = 'sk-label sk-rel';
      el.style.pointerEvents = 'auto'; // it takes clicks (the label layer lets them through to the view)
      el.textContent = RELATIONS[k.t]?.icon || '?';
      el.title = `${t(RELATIONS[k.t]?.name || k.t)} — ${t(k.t === 'pat' ? 'click to change the count / spacing' : 'click to remove it')}`;
      for (const ev of ['pointerdown', 'pointerup']) el.addEventListener(ev, (x) => x.stopPropagation());
      el.addEventListener('click', (x) => { x.stopPropagation(); if (k.t === 'pat') this.editPattern(k.id); else this.delRelation(k.id); });
      labels.push({ el, u: at[0] + mpp * 8, v: at[1] - mpp * 10 });
    }
    if (this.tool === 'mirror' && this.mirLine?.e && this.ent(this.mirLine.e)) { const e = this.ent(this.mirLine.e); lines.push([this.P(e.a), this.P(e.b), 0x7ee787]); }
    const pk = this.tool === 'pattern' && this.f.constraints.find((x) => x.id === this.pat?.k);
    if (pk?.e && this.ent(pk.e)) { const e = this.ent(pk.e); lines.push([this.P(e.a), this.P(e.b), 0x7ee787]); }
    if (pk?.kind === 'around' && this.P(pk.c || ORIGIN)) dots.push([this.P(pk.c || ORIGIN), 0x7ee787]);
    for (const q of this.tool === 'relate' ? this.relPicks || [] : []) {
      const e = q.kind === 'point' ? null : this.ent(q.id);
      if (q.kind === 'point') dots.push([this.P(q.id), 0x7ee787]);
      else if (e?.t === 'line') lines.push([this.P(e.a), this.P(e.b), 0x7ee787]);
      else if (e?.t === 'circle') circles.push([this.P(e.c), e.r, 0x7ee787]);
      else if (e?.t === 'arc') { const ps = this.arcOf(e); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], 0x7ee787]); }
    }
    // the origin, always: an orange point with short x / y arrows
    const ax = mpp * 26;
    lines.push([[0, 0], [ax, 0], 0xff7b72], [[0, 0], [0, ax], 0x7ee787]);
    dots.push([[0, 0], 0xffa657]);
    // what the mouse is on (what a dimension or a new point attaches to), highlighted with its name
    const HL = 0x7ee787, hv = this.hover;
    if (hv) {
      let name = '', at = null;
      if (hv.kind === 'point') {
        circles.push([hv.uv, mpp * 6, HL]);
        dots.push([hv.uv, HL]);
        if (hv.circle) { const c = this.ent(hv.circle); circles.push([this.P(c.c), c.r, HL]); name = 'circle (its centre)'; }
        else if (hv.arc) { const ps = this.arcOf(this.ent(hv.arc)); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], HL]); name = 'arc (its centre)'; }
        else name = hv.mid ? 'midpoint' : hv.onShape ? { line: 'on the line', circle: 'on the circle', arc: 'on the arc', edge: 'on the edge of the part' }[hv.onShape] || 'on it'
          : hv.refKind ? { corner: 'corner of the part', midpoint: "middle of the part's edge", centre: 'centre on the part', quadrant: 'quadrant on the part' }[hv.refKind]
          : hv.corner ? 'corner' : hv.end === ORIGIN ? 'origin' : hv.end?.axis ? 'axis of the round face' : hv.end && typeof hv.end === 'object' ? 'corner of the part' : 'point';
        at = hv.uv;
      } else if (hv.kind === 'piece') {
        for (let i = 0; i + 1 < hv.pts.length; i++) lines.push([hv.pts[i], hv.pts[i + 1], hv.grow ? 0x7ee787 : 0xff7b72]);
        name = hv.grow ? 'extend to here' : 'cut away';
        at = hv.pts[Math.floor(hv.pts.length / 2)];
      } else if (hv.kind === 'line') {
        lines.push([hv.uvA, hv.uvB, HL], [hv.uvA, hv.uvB, HL]);
        name = hv.line ? 'line' : hv.axis ? 'axis of the round face' : 'edge of the part';
        at = [(hv.uvA[0] + hv.uvB[0]) / 2, (hv.uvA[1] + hv.uvB[1]) / 2];
      } else if (hv.kind === 'entity' || hv.kind === 'group') {
        const ents = hv.loop ? hv.loop.map((id) => this.ent(id)).filter(Boolean) : hv.kind === 'group' ? this.f.entities.filter((x) => x.g === hv.id) : [this.ent(hv.id)].filter(Boolean);
        for (const x of ents) {
          if (x.t === 'line') lines.push([this.P(x.a), this.P(x.b), HL]);
          else if (x.t === 'circle') circles.push([this.P(x.c), x.r, HL]);
          else if (x.t === 'arc') { const ps = this.arcOf(x); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], HL]); }
          else if (x.t === 'block') for (const r of this.blockRings(x)) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length], HL]);
        }
      }
      if (name && at) {
        const el = document.createElement('div');
        el.className = 'sk-label hover';
        el.textContent = name;
        labels.push({ el, u: at[0] + mpp * 10, v: at[1] + mpp * 12 });
      }
    }
    // what is being drawn
    const cur = this.cursor?.uv;
    let live = null;
    if (cur && this.start && this.tool === 'rect') {
      const [u0, v0] = this.start.uv, [u1, v1] = cur;
      for (const [a, b] of [[[u0, v0], [u1, v0]], [[u1, v0], [u1, v1]], [[u1, v1], [u0, v1]], [[u0, v1], [u0, v0]]]) lines.push([a, b, SEL]);
      live = { text: `${fmt(Math.abs(u1 - u0))} × ${fmt(Math.abs(v1 - v0))}`, u: (u0 + u1) / 2, v: (v0 + v1) / 2 };
    } else if (cur && this.start && this.tool === 'slot') { // its middle line, then the slot at the mouse's width
      const a = this.start.uv, b = this.slotEnd?.uv;
      if (!b) { lines.push([a, cur, SEL, true]); live = { text: fmt(Math.hypot(cur[0] - a[0], cur[1] - a[1])), u: cur[0], v: cur[1] + mpp * 14 }; } else {
        const r = this.slotHalf(a, b, cur), L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, ang = Math.atan2(b[1] - a[1], b[0] - a[0]), n = [-(b[1] - a[1]) / L * r, (b[0] - a[0]) / L * r];
        lines.push([[a[0] - n[0], a[1] - n[1]], [b[0] - n[0], b[1] - n[1]], SEL], [[a[0] + n[0], a[1] + n[1]], [b[0] + n[0], b[1] + n[1]], SEL], [a, b, SEL, true]);
        for (const [c, a0] of [[b, ang - Math.PI / 2], [a, ang + Math.PI / 2]]) {
          const ps = Array.from({ length: 17 }, (_, i) => [c[0] + r * Math.cos(a0 + Math.PI * i / 16), c[1] + r * Math.sin(a0 + Math.PI * i / 16)]);
          for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]);
        }
        live = { text: `${fmt(L + 2 * r)} × ${fmt(2 * r)}`, u: (a[0] + b[0]) / 2, v: (a[1] + b[1]) / 2 };
      }
    } else if (cur && this.start && this.tool === 'circle') {
      const r = Math.hypot(cur[0] - this.start.uv[0], cur[1] - this.start.uv[1]);
      circles.push([this.start.uv, r, SEL]);
      live = { text: `Ø${fmt(2 * r)}`, u: this.start.uv[0], v: this.start.uv[1] };
    } else if (cur && this.start && this.tool === 'arc') {
      const geo = this.tan ? tangentArc(this.start.uv, this.tan.d, cur) : this.arcEnd && arcThrough(this.start.uv, this.arcEnd.uv, cur);
      if (geo) {
        const ps = arcPts(geo.c, geo.a, geo.b);
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]);
        live = { text: `R${fmt(Math.hypot(geo.a[0] - geo.c[0], geo.a[1] - geo.c[1]))}`, u: cur[0], v: cur[1] + mpp * 14 };
      } else lines.push([this.start.uv, this.arcEnd ? this.arcEnd.uv : cur, SEL, true]);
    } else if (cur && this.spl && this.tool === 'spline') { // the curve with the point under the mouse added
      const ps = splinePts([...this.spl.pts.map((id) => this.P(id)), cur]);
      for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]);
    } else if (cur && this.chain && this.tool === 'line') {
      const a = this.P(this.chain.last);
      lines.push([a, cur, SEL]);
      live = { text: fmt(Math.hypot(cur[0] - a[0], cur[1] - a[1])), u: (a[0] + cur[0]) / 2, v: (a[1] + cur[1]) / 2 };
    }
    if (live) {
      const el = document.createElement('div');
      el.className = 'sk-label live';
      el.textContent = live.text;
      labels.push({ el, u: live.u, v: live.v });
    }
    this.partMarks = 0; // (how many are shown: for the tests)
    if (cur && DRAWING.has(this.tool)) { // the part's snap points near the mouse (what its Snap filters allow): where a point can be caught
      const reach = mpp * 220;
      for (const q of this.partSnaps()) if (Math.abs(q.uv[0] - cur[0]) < reach && Math.abs(q.uv[1] - cur[1]) < reach) { dots.push([q.uv, PART_SNAP]); this.partMarks++; }
    }
    if (cur && this.tool !== 'select' && this.tool !== 'dim') dots.push([cur, this.cursor.id || this.cursor.ref ? 0x7ee787 : SEL]); // green = joins / snaps to that point
    this.view.setSketch(this.frame(), { lines, circles, dots, labels, grid: this.gridStep() });
  }

  centreOf(e) {
    if (!e.g) return null;
    const ps = this.pointsOfSel({ kind: 'group', id: e.g }).map((p) => this.P(p));
    return [ps.reduce((s, p) => s + p[0], 0) / ps.length, ps.reduce((s, p) => s + p[1], 0) / ps.length];
  }

  // ------------------------------------------------------------------ the property panel
  propsHtml() {
    const free = this.dof;
    const st = free === null ? '' : free === 0 ? '<p class="sk-dof ok">✓ Fully locked — every size is fixed.</p>'
      : `<p class="sk-dof">${free} free — those sizes follow when you drag. Type a size (or click 🔓) to lock it.</p>`;
    const s = this.sel;
    let what = '';
    const blk = s?.kind === 'entity' && this.ent(s.id)?.t === 'block' ? this.ent(s.id) : null;
    if (blk?.text !== undefined) { // 𝐓 Text: the text and its height
      const row = (k, label, v) => `<div class="field"><label>${label}</label><input type="number" step="any" data-bk="${k}" value="${fmt(v)}"><span class="unit">mm</span></div>`;
      what = `<h3>Text</h3>
        <div class="field"><label>Text</label><input type="text" data-bt="text" data-no-i18n value="${String(blk.text).replace(/[<>&"]/g, (c) => `&#${c.charCodeAt(0)};`)}"></div>
        ${row('h', 'Height', blk.h0 * (blk.scale || 1))}<p class="hint">Width ${fmt(blk.w0 * (blk.scale || 1))} mm (follows the text).</p>
        ${row('x', 'Corner x', blk.at[0])}${row('y', 'Corner y', blk.at[1])}
        <p class="hint">Drag it in the view to move it. Finish the sketch and ⬆ Extrude it — on the part it cuts the letters in.</p>
        <div class="row-actions"><button class="btn small danger" data-a="delSel" title="Delete it (Delete)">Delete</button></div>`;
    } else if (blk) {
      const row = (k, label, v) => `<div class="field"><label>${label}</label><input type="number" step="any" data-bk="${k}" value="${fmt(v)}"><span class="unit">mm</span></div>`;
      what = `<h3>Outline</h3><p class="hint" data-no-i18n>${(blk.name || '').replace(/[<>&]/g, '')}</p>
        ${row('w', 'Width', blk.w0 * (blk.scale || 1))}<p class="hint">Height ${fmt(blk.h0 * (blk.scale || 1))} mm (follows the width).</p>
        ${row('x', 'Corner x', blk.at[0])}${row('y', 'Corner y', blk.at[1])}
        <p class="hint">Drag it in the view to move it. The corner is its lower-left corner, from the sketch's origin.</p>
        <div class="row-actions"><button class="btn small danger" data-a="delSel" title="Delete it (Delete)">Delete</button></div>`;
    } else if (s) {
      const name = s.kind === 'point' ? 'Point' : s.kind === 'group' ? 'Rectangle' : ({ circle: 'Circle', arc: 'Arc' })[this.ent(s.id)?.t] || 'Line';
      what = `<h3>${name}</h3><p class="hint">Sizes and the position are shown in the view: click one to type it.</p>
        <div class="row-actions"><button class="btn small danger" data-a="delSel" title="Delete it (Delete)">Delete</button></div>`;
    }
    const name = (d) => {
      const v = fmt(Math.abs(d.v)), hv = this.f.constraints.find((k) => (k.t === 'h' || k.t === 'v') && k.e === d.e)?.t;
      if (d.t === 'len') return `${hv === 'h' ? t('Width') : hv === 'v' ? t('Height') : t('Length')} ${v}`;  // (a free distance shows its measured value)
      if (d.t === 'dia') return this.roundAs(d.e) === 'r' ? `R${fmt(Math.abs(d.v) / 2)}` : `Ø${v}`;
      if (d.t === 'rad') return this.roundAs(d.e) === 'd' ? `Ø${fmt(Math.abs(d.v) * 2)}` : `R${v}`;
      if (d.t === 'ang') return `∠ ${v}° (${t('angle')})`;
      if (d.t === 'pl') return `⊥ ${v} (${t('from a line')})`;
      const at = (x) => (x === ORIGIN ? 'origin' : typeof x === 'object' ? 'part edge' : 'point');
      if ((d.a === ORIGIN || d.b === ORIGIN) && Math.abs(d.v) < 1e-9) return `${d.t === 'dx' ? '↔' : '↕'} 0 (on the origin)`;
      return `${{ dx: '↔', dy: '↕', dist: '⤢' }[d.t]} ${v} (from the ${at(d.a)})`;
    };
    const hidden = this.userHidden().length;
    const rels = this.userRelations();
    const relList = rels.length ? `<h3>Relations</h3><div class="sk-dims">${rels.map((k) => `<div class="sk-dim"><span>${RELATIONS[k.t]?.icon || ''} ${RELATIONS[k.t]?.name || k.t}</span>
      <span class="sk-dim-acts"><button class="mini danger" data-delrel="${k.id}" title="${k.t === 'off' ? 'Unlink: the copy stays, but no longer follows its original' : 'Remove this relation'}">✕</button></span></div>`).join('')}</div>` : '';
    const fold = this.f.dims.length > 12; // a long list is folded
    const list = (this.f.dims.length ? `${fold ? `<details class="sk-fold"><summary>${tv('Dimensions ({n})', { n: this.f.dims.length })}</summary>` : '<h3>Dimensions</h3>'}<div class="sk-dims">${this.f.dims.map((d) =>
      `<div class="sk-dim${this.bad?.has(d.id) ? ' bad' : ''}" data-dimrow="${d.id}"><span>${d.free ? '🔓' : '🔒'} ${d.free ? `(${name({ ...d, v: this.measure(d) })})` : name(d)}</span>
        <span class="sk-dim-acts">${['len', 'dia', 'rad'].includes(d.t) ? '' : `<button class="mini" data-lock="${d.id}" title="${d.free ? 'Lock it at this value' : 'Free it (it then only measures)'}">${d.free ? '🔒' : '🔓'}</button>`}
        <button class="mini danger" data-del="${d.id}" title="Delete this dimension">✕</button></span></div>`).join('')}</div>${fold ? '</details>' : ''}` : '')
      + (hidden ? `<div class="row-actions"><button class="btn small" data-a="showSizes">Show ${hidden} hidden size(s)</button></div>` : '');
    const n = this.f.entities.length, big = n > BIG_SKETCH && this.m.sizeMode === 'all';
    const bigNote = big ? `<p class="hint sk-big">${this.m.bigAll?.has(this.f.id)
      ? `${tv('Every size of the {n} shapes is shown.', { n })} <button class="btn small" data-a="bigAll">Show only the locked ones</button>`
      : `${tv('A big sketch ({n} shapes): only the locked sizes are shown.', { n })} <button class="btn small" data-a="bigAll">Show them all anyway</button>`}</p>` : '';
    return `<h2>Sketch</h2><p class="hint">${this.hint()}</p>${st}${this.stateHtml()}${this.m.sizesHtml?.() || ''}${bigNote}${what}${list}${relList}
      <h3>Tips</h3><p class="hint">A shape inside another one becomes a hole. Lines that meet at a point are joined; click the
      first point again to close a shape. 🔒 = locked size (it stays when other sizes change). ↔ Dimension adds a distance
      between two points, circles or edges (also the part's edges, dashed). Right mouse button pans, wheel zooms, Ctrl+Z undoes.</p>`;
  }

  /** Under the free count: what does not fit and why (red on the shapes), 🪄 at rounded values while sizes are free
   *  (then what it rounded, to keep or take back), ∪ when closed shapes overlap. */
  stateHtml() {
    const out = [], con = this.conflicting || [], twice = (this.conflicts || []).filter((id) => !con.includes(id));
    if (con.length) out.push(`<p class="sk-why bad">⚠ ${tv('These do not fit together: {names} — remove or change one of them (their shapes are red).', { names: this.ruleNames(con).join(', ') })}</p>`);
    if (twice.length) out.push(`<p class="sk-why">${tv('Held twice: {names} — the other sizes fix it already; 🪄 makes it a reference dimension.', { names: this.ruleNames(twice).join(', ') })}</p>`);
    if (this.rounded) {
      out.push(`<div class="sk-rounded"><p class="hint">${t('Locked at rounded values (the shapes moved to them):')}</p><ul>${this.rounded.map((x) => `<li data-no-i18n>${x.from} → <b>${x.name}</b></li>`).join('')}</ul>
        <div class="row-actions"><button class="btn small primary" data-a="roundKeep">✓ ${t('Keep')}</button><button class="btn small" data-a="roundBack" title="${t('Back to the sketch as it was (Ctrl+Z)')}">↶ ${t('Take back')}</button></div></div>`);
    } else if (this.dof > 0 && this.solver) {
      out.push(`<div class="row-actions"><button class="btn small" data-a="autodimRound" title="${t('🪄 Auto-dimension, each size locked at a nice value (whole mm) — the shapes move to it; you see what changed and can take it back')}">🪄 ${t('Lock at rounded values')}</button></div>`);
    }
    if (this.f.entities.length <= 80 && this.overlapping()) {
      out.push(`<div class="row-actions"><button class="btn small" data-a="unite" title="${t('Closed shapes overlap: trim the pieces inside each other — one outline of lines and arcs (tangents and equal radii stay)')}">∪ ${t('Unite overlapping shapes')}</button></div>`);
    }
    return out.join('');
  }

  /** The panel's own buttons and rows (the modeler binds the rest): a row lights its dimension in the view. */
  bindProps(box) {
    for (const row of box.querySelectorAll('[data-dimrow]')) {
      const lab = () => this.m.els.viewport.querySelector(`.sk-label[data-dim="${row.dataset.dimrow}"]`);
      row.addEventListener('mouseenter', () => { const l = lab(); if (l) { l.classList.add('lit'); l.dispatchEvent(new MouseEvent('mouseenter')); } });
      row.addEventListener('mouseleave', () => { const l = lab(); if (l) { l.classList.remove('lit'); l.dispatchEvent(new MouseEvent('mouseleave')); } });
    }
    box.querySelector('[data-a=autodimRound]')?.addEventListener('click', () => this.autoDimension({ round: true }));
    box.querySelector('[data-a=roundKeep]')?.addEventListener('click', () => { this.rounded = null; this.m.renderProps(); });
    box.querySelector('[data-a=roundBack]')?.addEventListener('click', () => { this.rounded = null; this.back(); });
    box.querySelector('[data-a=unite]')?.addEventListener('click', () => this.unite());
  }

  /** ∪ from the panel / the suggestions: unite, and say what happened. */
  async unite() {
    const r = await this.unionShapes();
    this.m.toast(r ? tv('∪ One outline: {k} piece(s) inside other shapes trimmed — 🪄 Auto-dimension locks what is free now.', { k: r.trimmed }) : t('No closed shapes overlap — nothing to unite.'), r ? 'ok' : 'info', 6000);
  }

  /** Do closed shapes of the sketch overlap (they cross, a piece of one inside another — not a hole inside a plate)? */
  overlapping() {
    const regions = this.unionRegions();
    return regions.filter((r) => r.crosses).length > 1 && !!this.innerPiece(regions);
  }

  /** A standard shape drawn from single pieces made the real thing: a slot (its joins tangent, its ends equal, one
   *  shape), a rectangle (H / V sides, one shape), a circle (two half arcs -> one circle). */
  async convertShape(sh) {
    const f = this.f;
    await this.relock(() => {
      const ents = sh.ids.map((id) => this.ent(id)), g = this.newId('r');
      const has = (fn) => f.constraints.some(fn);
      if (sh.kind === 'slot') {
        const arcs = ents.filter((e) => e.t === 'arc'), lines = ents.filter((e) => e.t === 'line');
        for (const a of arcs) for (const p of [a.a, a.b]) {
          const l = lines.find((x) => x.a === p || x.b === p);
          if (l && !has((k) => k.t === 'tan' && k.e === l.id && k.arc === a.id && k.p === p)) f.constraints.push({ id: this.newId('k'), t: 'tan', e: l.id, arc: a.id, p });
        }
        if (!has((k) => k.t === 'eq' && [k.e, k.e2].includes(arcs[0].id) && [k.e, k.e2].includes(arcs[1].id))) f.constraints.push({ id: this.newId('k'), t: 'eq', e: arcs[0].id, e2: arcs[1].id });
        ents.forEach((e) => { e.g = g; });
      } else if (sh.kind === 'rect') {
        for (const l of ents) {
          if (has((k) => (k.t === 'h' || k.t === 'v') && k.e === l.id)) continue;
          const a = this.P(l.a), b = this.P(l.b);
          f.constraints.push({ id: this.newId('k'), t: Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v', e: l.id });
        }
        ents.forEach((e) => { e.g = g; });
      } else if (sh.kind === 'circle') {
        const gone = new Set(sh.ids);
        f.entities = f.entities.filter((e) => !gone.has(e.id));
        f.constraints = f.constraints.filter((k) => ![k.e, k.e2, k.arc].some((x) => gone.has(x)));
        const rad = f.dims.find((d) => d.t === 'rad' && gone.has(d.e));
        f.dims = f.dims.filter((d) => !gone.has(d.e));
        const id = this.newId('c');
        f.entities.push({ id, t: 'circle', c: sh.c, r: sh.r });
        if (rad) f.dims.push({ id: rad.id, t: 'dia', e: id, v: 2 * rad.v });
        const used = new Set(f.entities.flatMap((x) => [x.a, x.b, x.c, ...(x.pts || [])]));
        for (const p of Object.keys(f.points)) if (!used.has(p) && !f.dims.some((d) => d.a === p || d.b === p) && !f.constraints.some((k) => k.p === p || k.p2 === p)) delete f.points[p];
      }
    });
  }

  async init() {
    // a reopened sketch: ask the solver for the free degrees (nothing moves)
    if (this.f.entities.length) {
      const r = await this.solve();
      if (this.takeState(r).colours) this.draw(); // (its colours)
      this.m.renderProps();
    }
  }

  result() {
    const { points, entities, constraints, dims } = this.f;
    return { ...this.f, points, entities, constraints, dims };
  }
}
