// 🔌 Cable harnesses in the assembly: choose what runs (one cable, loose wires, a ribbon cable, a sleeve), its Ø and
// the minimum bend radius, then click the points it passes — on a part's face (it lies on it: Ø/2 + 0.5 mm off), a
// hole's centre (it goes through), or in space. A point on a part sticks to it (the placed part + its own
// coordinates): it follows when the part moves (mechanisms, dragging, explode). The route is shaped to the minimum
// bend radius: every corner an arc of it (straight lines + arcs), two corners too close for that moved apart along
// their outer legs; only a corner nothing makes fit gets the largest radius that does and a quiet ⚠ note. Drawn as tubes (wires twisted round the centre line, a sleeve corrugated, a
// ribbon flat), listed in the assembly tree, in the BOM (a line per wire / cable, its length + a reserve, rounded up),
// exported to STEP / GLB / the drawing as a "harness" step of its own part (auto3d/modeler/harness.py: the same math).
//
// Assembly JSON: "harnesses": [{"id": "H1", "kind": "cable" | "wires" | "ribbon" | "sleeve", "d": 6 (cable / sleeve Ø),
//   "color": "black", "wires": [{"d": 1.5, "color": "brown"}] (loose wires, a ribbon's count), "pitch": 1.27,
//   "r_min": 30 (not said: the rule of thumb, autoRmin), "reserve": 5 (%), "name": "…", "length_locked": 400 (🔒 mm),
//   "spans": [{"from": 2, "length": 140}] (➰ the cable between points from and from + 1 (0-based) that long: a loop of
//   slack there; they win over length_locked; "chain": "C1" — ⛓ the span routed through that energy chain: the cable
//   runs along the chain's path as it is laid out now; "enter": "fixed" | "moving" — the chain's end it goes in at,
//   the one nearer its first point when it was routed (an older file's: when loaded), kept as the chain moves),
//   "points": [{"inst": "I2", "at": [x, y, z] (in the part), "n": [x, y, z] (its face's normal: the cable lies on it;
//   none: right there, a hole's centre), "face": "F2:end" (its name, for the list)} (🔒 locked on the part: it moves with
//   it) | {"xyz": [x, y, z]} (in space) | {"xyz", "on": {inst, at, n, face}} (🔓 a point of a part unlocked: it stays in
//   space; 🔒 again: it sticks to the part where it is then) | {"inst": "I7", "at": …, "clip": "I7"} (📎 on the axis of
//   the clip placed there, locked to it)], with "conn": true | false on any of them (🔌 a connection point: the cable
//   plugs into that part there — a connector, a probe's tail, a gland; not said: an end of the harness on a part is
//   one) — the cable may enter that part near it: no collision, no lead-out note for it}]. A loaded point in space that lies on a face (Ø/2 + 0.5 off it) is taken as
//   locked to it (adopt).
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { t, getLang } from '../i18n.js';
import { clipsFor, clipChoices, clipFrames, clipItem, placeClip, chainsFor, placeChain } from '../library/cableparts.js';
import { chainRoute, chainOf as chainRec, addChain, drawChains } from './chains.js';
import { ClipPick } from './clippick.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const V = (a) => new THREE.Vector3(...a);
const CLEAR = 0.5; // mm between a face and the cable lying on it

export const KINDS = {
  cable: { icon: '⚫', name: 'Cable', hint: 'One round cable: its Ø and colour' },
  wires: { icon: '≋', name: 'Loose wires', hint: 'Single wires laid together: how many, each one\'s Ø and colour — the bundle\'s Ø from how they pack' },
  ribbon: { icon: '▬', name: 'Ribbon cable', hint: 'A flat cable: its width = wires × pitch' },
  sleeve: { icon: '〰', name: 'Sleeve', hint: 'A corrugated hose round the wires: its Ø' },
};
// IEC 60757 wire colours: [code, hex, English, Czech (as a colour), Czech (of a wire / cable)]
export const COLOURS = {
  black: ['BK', 0x262626, 'black', 'černá', 'černý'], brown: ['BN', 0x7b4a24, 'brown', 'hnědá', 'hnědý'], red: ['RD', 0xd0312d, 'red', 'červená', 'červený'],
  orange: ['OG', 0xf08c1a, 'orange', 'oranžová', 'oranžový'], yellow: ['YE', 0xf2d22e, 'yellow', 'žlutá', 'žlutý'], green: ['GN', 0x2e9d48, 'green', 'zelená', 'zelený'],
  blue: ['BU', 0x2f6fd0, 'blue', 'modrá', 'modrý'], violet: ['VT', 0x8a4fc4, 'violet', 'fialová', 'fialový'], grey: ['GY', 0x8c9096, 'grey', 'šedá', 'šedý'],
  white: ['WH', 0xf2f2f0, 'white', 'bílá', 'bílý'], pink: ['PK', 0xf29bb8, 'pink', 'růžová', 'růžový'], 'green-yellow': ['GNYE', 0x9cc23a, 'green-yellow', 'zelenožlutá', 'zelenožlutý'],
};
const ORDER = ['red', 'black', 'blue', 'brown', 'green-yellow', 'white', 'grey', 'orange', 'yellow', 'violet', 'pink', 'green'];
const colourOf = (c) => COLOURS[c] || COLOURS.black;
export const colourName = (c) => (getLang() === 'cs' ? colourOf(c)[3] : colourOf(c)[2]);
const hexOf = (c) => `#${colourOf(c)[1].toString(16).padStart(6, '0')}`;

/** A length in whole mm, thousands apart ("1 284"). */
export const mmText = (v) => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const num = (v) => { const s = String(+(+v).toFixed(2)); return getLang() === 'cs' ? s.replace('.', ',') : s; };

// ------------------------------------------------------------------ the math (as auto3d/modeler/harness.py)
const PACKING = { 1: 1, 2: 2, 3: 1 + 2 / Math.sqrt(3), 4: 1 + Math.SQRT2, 5: 1 + 1 / Math.sin(Math.PI / 5), 6: 3, 7: 3, 8: 1 + 1 / Math.sin(Math.PI / 7), 9: 1 + 1 / Math.sin(Math.PI / 8) };

/** n wires of Ø d in a round bundle -> their centres [[x, y]] in its cross-section. */
export function wireLayout(n, d) {
  n = Math.max(1, n | 0);
  const ring = (k, r, a0 = 0) => Array.from({ length: k }, (_, i) => [r * Math.cos(a0 + (2 * Math.PI * i) / k), r * Math.sin(a0 + (2 * Math.PI * i) / k)]);
  if (n === 1) return [[0, 0]];
  if (n === 2) return [[-d / 2, 0], [d / 2, 0]];
  if (n <= 6) return ring(n, d / (2 * Math.sin(Math.PI / n)));
  if (n <= 9) return [[0, 0], ...ring(n - 1, Math.max(d, d / (2 * Math.sin(Math.PI / (n - 1)))))];
  const m = Math.max(3, Math.round(n / 3.2)), ri = d / (2 * Math.sin(Math.PI / m)), ro = Math.max(ri + d, d / (2 * Math.sin(Math.PI / (n - m))));
  return [...ring(m, ri), ...ring(n - m, ro, Math.PI / (n - m))];
}

/** The outer Ø of n wires of Ø d laid in a round bundle (1, 3, 7 wires: 1, 2.155, 3 × d). */
export function bundleD(n, d) {
  n = Math.max(1, n | 0);
  return PACKING[n] ? PACKING[n] * d : 2 * Math.max(...wireLayout(n, d).map(([x, y]) => Math.hypot(x, y))) + d;
}

const wireD = (h) => Math.max(...(h.wires || []).map((w) => +w.d || 1.5), 0) || 1.5;
/** A harness's outer size: a cable's / sleeve's Ø, a bundle's Ø, a ribbon's width. */
export function outerD(h) {
  if (h.kind === 'wires') return bundleD((h.wires || []).length || 1, wireD(h));
  if (h.kind === 'ribbon') return Math.max(1, (h.wires || []).length) * (+h.pitch || 1.27);
  return +h.d || 6;
}
/** How far its centre line keeps off a face it lies on (a ribbon: lying flat). */
const lift = (h) => (h.kind === 'ribbon' ? (+h.d || 1) / 2 : outerD(h) / 2) + CLEAR;
/** The rule of thumb when none is given: 5 × Ø (a cable, a bundle), 3 × Ø (a corrugated sleeve), 10 mm (a ribbon). */
export const autoRmin = (h) => (h.kind === 'ribbon' ? 10 : Math.ceil((h.kind === 'sleeve' ? 3 : 5) * outerD(h)));
export const rMinOf = (h) => (Number.isFinite(+h.r_min) && h.r_min !== null && h.r_min !== '' ? +h.r_min : autoRmin(h));

/** The corners of the polyline P rounded with rMin where its legs leave room, else with the largest radius that fits
 *  (a leg shared by two corners split by what each wants) -> {L, U, turn, want, T (how far each arc reaches along its
 *  legs), R (its radius)}. */
function fit(P, rMin) {
  const L = [], U = [];
  for (let k = 0; k + 1 < P.length; k++) { const v = P[k + 1].clone().sub(P[k]); L.push(v.length()); U.push(v.divideScalar(L[k])); }
  const turn = P.map((_, i) => (i === 0 || i === P.length - 1 ? 0 : Math.acos(Math.max(-1, Math.min(1, U[i - 1].dot(U[i]))))));
  const want = turn.map((a) => (a > 1e-9 && a < Math.PI - 1e-9 ? rMin * Math.tan(a / 2) : a >= Math.PI - 1e-9 ? Infinity : 0));
  const room = (i, k) => { // how much of leg k corner i may take (the room split by what the corners at its two ends want)
    const j = i === k ? k + 1 : k, a = want[i], b = want[j];
    if (b <= 0 || a + b <= L[k]) return b <= 0 ? L[k] : Math.min(a, L[k]);
    if (Number.isFinite(a + b)) return L[k] * (a / (a + b));
    return a === Infinity && b === Infinity ? L[k] / 2 : a === Infinity ? L[k] : 0;
  };
  const T = P.map(() => 0), R = P.map(() => 0);
  for (let i = 1; i + 1 < P.length; i++) {
    if (turn[i] <= 1e-9) continue;
    T[i] = Math.min(want[i], room(i, i - 1), room(i, i));
    R[i] = turn[i] < Math.PI - 1e-9 ? T[i] / Math.tan(turn[i] / 2) : 0;
  }
  return { L, U, turn, want, T, R };
}

/** Two corners too close for rMin (the leg between them too short for both arcs: an S or a double bend) moved apart
 *  along their outer legs — the middle leg longer, both arcs rMin — as little as that needs and as far as the corners
 *  beyond leave room; when no move makes them fit, the move that bends them least tight (a U turn: none). The ends
 *  stay. As harness.py's _spread. -> the points the arcs are fitted to. */
function spread(P0, rMin) {
  const P = P0.map((p) => p.clone()), tight = rMin * (1 - 1e-6), ok = (a) => a > 1e-9 && a < Math.PI - 1e-9;
  for (let i = 1; i + 2 < P.length; i++) {
    const { L, U, turn, want, T, R } = fit(P, rMin);
    if (!ok(turn[i]) || !ok(turn[i + 1]) || Math.min(R[i], R[i + 1]) >= tight) continue;
    if (T[i] + T[i + 1] < L[i] * (1 - 1e-9)) continue; // (not the leg between them that is short)
    const smax = Math.min(L[i - 1] - (i > 1 ? want[i - 1] : 0), L[i + 1] - (i + 2 < P.length - 1 ? want[i + 2] : 0)) * (1 - 1e-9);
    if (!(smax > 1e-9)) continue;
    const a0 = P[i].clone(), b0 = P[i + 1].clone(), ua = U[i - 1], ub = U[i + 1];
    const moved = (s) => { const Q = P.slice(); Q[i] = a0.clone().addScaledVector(ua, -s); Q[i + 1] = b0.clone().addScaledVector(ub, s); return Q; };
    const worst = (s) => { const R2 = fit(moved(s), rMin).R; return Math.min(R2[i], R2[i + 1]); };
    const n = 32, f = [];
    for (let k = 0; k <= n; k++) f.push(worst((smax * k) / n));
    let k = f.findIndex((x, j) => j > 0 && x >= tight), s = 0;
    if (k > 0) { // the least move that fits, bisected (to where both arcs are rMin to the last digits)
      let lo = (smax * (k - 1)) / n, hi = (smax * k) / n;
      for (let it = 0; it < 60; it++) { const mid = (lo + hi) / 2; if (worst(mid) >= rMin * (1 - 1e-13)) hi = mid; else lo = mid; }
      s = hi;
    } else {
      k = f.reduce((b, x, j) => (x > f[b] ? j : b), 0);
      s = f[k] > f[0] * (1 + 1e-3) ? (smax * k) / n : 0;
    }
    const Q = moved(s);
    P[i] = Q[i]; P[i + 1] = Q[i + 1];
  }
  return P;
}

/** A harness's locked length (🔒, mm) or null. */
export const lockedOf = (h) => (+h.length_locked > 0 ? +h.length_locked : null);
/** ➰ A harness's spans with their own length -> {from: length} (from: 0-based, the span to the next point). */
export const spansOf = (h) => Object.fromEntries((h.spans || []).filter((s) => +s.length > 0 && Number.isInteger(+s.from)).map((s) => [+s.from, +s.length]));
/** How far an end of the cable on a face (at p, its normal n) goes straight out of it before it bends towards nxt:
 *  room for that bend at the radius (r · tan of half its turn, the turn at most 160°; at least a right angle's), + Ø.
 *  As harness.py's lead_of. */
export function leadOf(h, p = null, n = null, nxt = null) {
  const r = rMinOf(h), d = outerD(h);
  let L = Math.max(r, d) + d;
  if (!p || !nxt) return L;
  for (let i = 0; i < 3; i++) { // (further out, the turn towards nxt changes a little: again)
    const v = nxt.clone().sub(p.clone().addScaledVector(n, L));
    if (v.length() < 1e-9) break;
    const turn = Math.acos(Math.max(-1, Math.min(1, n.dot(v) / v.length())));
    L = Math.max(Math.max(r, d), r * Math.tan(Math.min(turn, (160 * Math.PI) / 180) / 2)) + d;
  }
  return L;
}

/** An end of the cable on a face leaves it square: a point out along that face's normal (n0 / n1: the first / last
 *  point's, or null) put in after the first point / before the last, as far out as its bend needs (leadOf) ->
 *  {E, where (where each point went)}. As harness.py's leads. */
export function leads(h, pts, n0, n1) {
  const E = pts.map((p) => p.clone()), where = pts.map((_, i) => i), m = pts.length;
  if (m < 2) return { E, where };
  if (n1) { const n = n1.clone().normalize(); E.splice(E.length - 1, 0, pts[m - 1].clone().addScaledVector(n, leadOf(h, pts[m - 1], n, pts[m - 2]))); where[m - 1]++; }
  if (n0) { const n = n0.clone().normalize(); E.splice(1, 0, pts[0].clone().addScaledVector(n, leadOf(h, pts[0], n, pts[1]))); for (let i = 1; i < m; i++) where[i]++; }
  return { E, where };
}

/** The points the cable runs through before its detours: the given points, the leads at its ends on faces, and the
 *  paths of its spans routed through an energy chain (chains: {k: [Vector3], from span k's first point's side}) ->
 *  {E, where (where each given point went), tag: per point 'p' | 'lead' | 'chain'}. */
function expandE(h, pts, n0, n1, chains = {}) {
  const { E, where } = leads(h, pts, n0, n1), tag = E.map((_, i) => (where.includes(i) ? 'p' : 'lead'));
  for (const k of Object.keys(chains).map(Number).sort((a, b) => b - a)) {
    if (!chains[k]?.length || k + 1 >= where.length) continue;
    const at = where[k + 1] - (k + 1 === where.length - 1 && tag[where[k + 1] - 1] === 'lead' ? 1 : 0); // (before the point after it, or its lead)
    const path = chains[k].filter((p, i, all) => p.distanceTo(E[at - 1]) > 1e-6 && p.distanceTo(E[at]) > 1e-6 && (!i || p.distanceTo(all[i - 1]) > 1e-6)); // (a point twice: once — the route counts each once)
    if (!path.length) continue;
    E.splice(at, 0, ...path.map((p) => p.clone()));
    tag.splice(at, 0, ...path.map(() => 'chain'));
    for (let i = 0; i < where.length; i++) if (where[i] >= at) where[i] += path.length;
  }
  return { E, where, tag };
}

/** The legs of E the slack and the detours leave as they are: a lead, a leg inside an energy chain. */
const stillOf = (tag) => tag.slice(1).map((_, k) => k).filter((k) => (tag[k] === 'chain' && tag[k + 1] === 'chain') || (k === 0 && tag[1] === 'lead') || (k === tag.length - 2 && tag[k] === 'lead'));

// harness -> {key, E, where, tag, clashes}: the detours round the parts worked out last (avoid), for the points they
// were worked out for (key) — the route uses them while its points are those, else only its leads (a drag: no waiting)
const AVOID = new WeakMap();
const keyOf = (h, pts, n0, n1, chains = {}) => JSON.stringify([pts.map((p) => p.toArray().map((x) => +x.toFixed(2))), n0?.toArray().map((x) => +x.toFixed(3)), n1?.toArray().map((x) => +x.toFixed(3)), rMinOf(h), outerD(h), lockedOf(h), h.spans || null,
  Object.entries(chains).map(([k, P]) => [k, P[0].toArray().map((x) => +x.toFixed(2)), P[P.length - 1].toArray().map((x) => +x.toFixed(2))])]);

/** A harness's route through its world points (pts; n0 / n1: its ends' face normals): its leads, the detours worked
 *  out for these points, shaped to its radius with its spans' and its locked length's slack -> shape(…) with its
 *  bends, spans and taut spans told by the given points + {points (the points it runs through), where, dropped
 *  (spans whose own length a detour broke), clashes, short (points too close to the end on a face: shortLeads)}. */
export function routeOf(h, pts, n0 = null, n1 = null, chains = {}) {
  const c = AVOID.get(h), hit = c && c.key === keyOf(h, pts, n0, n1, chains);
  const { E, where, tag } = hit ? { E: c.E.map((p) => p.clone()), where: c.where.slice(), tag: c.tag.slice() } : expandE(h, pts, n0, n1, chains);
  const r = routeE(h, E, where, hit ? c.clashes : [], stillOf(tag));
  r.detours = hit ? c.detours : 0;
  r.short = shortLeads(h, pts, n0, n1, E, tag);
  return r;
}

/** The route through E (the given points at `where`), told by the given points. */
function routeE(h, E, where, clashes = [], still = []) {
  const sp = spansOf(h), legOf = {}, own = {};
  for (const [k, v] of Object.entries(sp)) { // (a span of several legs — a lead in it: its slack on its longest other leg)
    const a = where[+k], b = where[+k + 1];
    let j = -1;
    if (b !== undefined) for (let i = a; i < b; i++) if (!still.includes(i) && (j < 0 || E[i + 1].distanceTo(E[i]) > E[j + 1].distanceTo(E[j]))) j = i;
    if (j >= 0) { legOf[k] = j; own[j] = v; }
  }
  let r = shape(E, rMinOf(h), own, lockedOf(h), still); // (its leads stay straight)
  for (let it = 0; it < 4; it++) { // (that leg's length set so that the whole span is its length: its other legs' share taken off)
    let off = 0;
    for (const [k, j] of Object.entries(legOf)) {
      const S = (r.spans || []).slice(where[+k], where[+k + 1]).reduce((s, x) => s + x, 0), d = sp[k] - S;
      if (Math.abs(d) > 0.05 && own[j] + d > 0 && !r.taut.some((x) => x.span === j)) { own[j] += d; off++; }
    }
    if (!off) break;
    r = shape(E, rMinOf(h), own, lockedOf(h), still);
  }
  const back = (i) => { let k = 0; where.forEach((w, j) => { if (w <= i) k = j; }); return k; }; // (a point of E -> the given point before it)
  r.bends = r.bends.map((b) => ({ ...b, at: back(b.at) }));
  r.taut = r.taut.map((x) => ({ ...x, span: x.span === null ? null : back(x.span) }));
  r.spansE = r.spans;
  r.spans = where.slice(1).map((w, k) => (r.spans || []).slice(where[k], w).reduce((s, x) => s + x, 0));
  r.points = E;
  r.where = where;
  r.own = own;
  r.still = still;
  r.dropped = Object.keys(sp).map(Number).filter((k) => k + 1 < where.length && !(k in legOf));
  r.clashes = clashes;
  return r;
}

/** ➰ How long each span (from point k to k + 1) is at its tightest: the route through the same points (its leads and
 *  detours) with no span's own length and no locked length — straight legs and r_min arcs (r: routeAt's) -> [mm]. */
export function tightSpans(h, r) {
  if (!r?.points?.length || !r.where) return r?.spans || [];
  const h0 = { ...h, spans: (h.spans || []).filter((x) => x.chain).map((x) => ({ from: x.from, chain: x.chain })) };
  delete h0.length_locked;
  return routeE(h0, r.points.map((p) => p.clone()), r.where.slice(), [], r.still || []).spans;
}
export const spanTight = (h, r, k) => tightSpans(h, r)[k] ?? r?.spans?.[k] ?? 0;

/** A point's face normal in the world (a point lying on a part's face) -> Vector3 or null. */
function normalAt(asm, p, M = null) {
  if (!p?.inst || !p.n) return null;
  M = M || (asm ? matrixOf(asm, p.inst) : null);
  return M ? V(p.n).applyMatrix3(new THREE.Matrix3().getNormalMatrix(M)).normalize() : null;
}

/** A harness's route as its parts are drawn (extra: the point under the mouse, after its last). */
export function routeAt(asm, h, extra = []) {
  const { ok, n0, n1, chains } = inputsAt(asm, h, extra);
  return routeOf(h, [...ok, ...extra], n0, n1, chains);
}

/** What a harness's route is worked out from, as its parts are drawn: its points, its ends' face normals, the paths of
 *  its spans through an energy chain (read now: the chain's moving end where it is). */
function inputsAt(asm, h, extra = []) {
  const P = h.points || [], pts = P.map((p) => pointAt(asm, h, p)), ok = pts.filter(Boolean);
  return { ok, n0: pts[0] ? normalAt(asm, P[0]) : null, n1: !extra.length && pts.length > 1 && pts[pts.length - 1] ? normalAt(asm, P[P.length - 1]) : null, chains: ok.length === pts.length ? spanChains(asm, h, pts) : {} };
}

/** ⛓ The spans routed through an energy chain -> {k: [Vector3]}: the chain's centre line as it is laid out now, from
 *  the end the span enters (its `enter`; none: the nearer one to its first point). */
function spanChains(asm, h, pts) {
  const out = {};
  for (const s of h.spans || []) {
    const a = pts[+s.from], r = s.chain && a && pts[+s.from + 1] ? chainRoute(asm, s.chain) : null;
    if (!r?.points?.length) continue;
    const P = r.points.map((p) => V(p));
    out[+s.from] = (s.enter || nearerEnd(a, P)) === 'fixed' ? P : P.reverse();
  }
  return out;
}

/** ⛓ The end of a chain's path P (fixed end first) nearer point a: 'fixed' | 'moving'. */
const nearerEnd = (a, P) => (a.distanceTo(P[0]) <= a.distanceTo(P[P.length - 1]) ? 'fixed' : 'moving');

/** ⛓ The end of chain `chain` span k of harness h enters, as they are placed now (the nearer one to its first point)
 *  -> 'fixed' | 'moving' | null (the chain or the point is gone). */
function enterNow(asm, h, k, chain) {
  const p = h.points?.[k], it = p?.inst && asm.inst(p.inst); // (as placed, as the chain is: not as drawn — a view still showing the last assembly)
  const a = p && (p.xyz || it) && pointAt(asm, h, p, it ? new THREE.Matrix4().fromArray(it.matrix) : null), r = chainRoute(asm, chain);
  return a && r?.points?.length ? nearerEnd(a, r.points.map((q) => V(q))) : null;
}

/** ⛓ An opened assembly's spans through a chain with no `enter` (an older file): the end decided once, as the parts
 *  stand when loaded, and kept from then on (the chain moving does not flip the cable's way through it). */
export function settleEntries(asm) {
  for (const h of asm.doc.harnesses || []) {
    for (const s of h.spans || []) {
      if (!s.chain || s.enter) continue;
      const e = enterNow(asm, h, +s.from, s.chain);
      if (e) s.enter = e;
    }
  }
}

/** 🔌 Is point i of harness h a connection point (the cable plugs into its part there)? Said on the point (conn), else
 *  an end of the harness that sits on a part (not on a clip). */
export function connOf(h, i) {
  const P = h.points || [], p = P[i];
  if (!p) return false;
  if (p.conn !== undefined) return !!p.conn;
  return (i === 0 || i === P.length - 1) && !!(p.inst || p.on?.inst) && !p.clip;
}

/** 🔌 The parts a harness may enter at its connection points: (inst, w) -> excused? — that point's part, within a lead
 *  and a few Ø of it (pts: its world points, one per point; else nothing is excused). */
export function excuser(h, pts) {
  const P = h.points || [], reach = Math.max(leadOf(h), 5 * outerD(h)) + outerD(h), near = [];
  if (pts.length === P.length) P.forEach((p, i) => { const on = p.inst || p.on?.inst; if (on && pts[i] && connOf(h, i)) near.push([on, pts[i]]); });
  return (inst, w) => near.some(([on, q]) => on === inst && q.distanceTo(w) <= reach);
}

/** A cable leaving a face goes straight out of it (leadOf, at least max(r_min, Ø) + Ø) before it bends: the points
 *  closer than that to the end they follow (pts: its given points, E / tag: the route's points) -> [{p (that point,
 *  world), need (mm)}] — a quiet note there, not a kink. */
export function shortLeads(h, pts, n0, n1, E, tag) {
  const out = [], need = leadOf(h), m = pts.length, all = m === (h.points || []).length; // (🔌 a connection end: no note)
  if (m < 2) return out;
  const near = (a, i) => { if (i >= 0 && i < E.length && a.distanceTo(E[i]) < need - 1e-6) out.push({ p: E[i].clone(), need }); };
  if (n0 && !(all && connOf(h, 0))) near(pts[0], tag.findIndex((x, i) => i > 0 && x !== 'lead'));
  if (n1 && !(all && connOf(h, m - 1))) near(pts[m - 1], tag.map((x, i) => (i < tag.length - 1 && x !== 'lead' ? i : -1)).reduce((a, b) => Math.max(a, b), -1));
  return out;
}

/** A harness's route as its placed parts stand in the assembly document (the BOM, the export). */
export function docRoute(doc, h) {
  const mats = new Map((doc.instances || []).map((it) => [it.id, new THREE.Matrix4().fromArray(it.matrix)]));
  const P = h.points || [], M = (p) => (p?.inst ? mats.get(p.inst) || null : null), pts = docPoints(doc, h);
  const asDoc = { doc, inst: (id) => (doc.instances || []).find((i) => i.id === id) || null }; // (chains.js reads only these)
  return routeOf(h, pts, normalAt(null, P[0], M(P[0]) || undefined), P.length > 1 ? normalAt(null, P[P.length - 1], M(P[P.length - 1]) || undefined) : null,
    pts.length === P.length ? spanChains(asDoc, h, pts) : {});
}

/** Every direction a sample looks for the parts round it (to the faces, the edges and the corners of a cube: 26). */
const DIRS = [-1, 0, 1].flatMap((x) => [-1, 0, 1].flatMap((y) => [-1, 0, 1].map((z) => [x, y, z]))).filter((d) => d.some(Boolean)).map((d) => V(d).normalize());

/** The parts round a point: how far and which way to move p so a tube of radius rad there clears them -> {push, inst}
 *  or null. Inside a part: out through its nearest side; outside but nearer than rad: away from it. boxes: the
 *  parts' world boxes (grown by rad). */
function probe(meshes, boxes, p, rad, skip = null) {
  const ray = new THREE.Raycaster(), up = V([0.3017, 0.2081, 0.9304]).normalize();
  let best = null;
  meshes.forEach((m, i) => {
    if (!boxes[i].containsPoint(p) || skip?.(m.userData.inst, p)) return; // (🔌 a part it plugs into, near that point)
    ray.far = Infinity;
    ray.set(p, up);
    if (ray.intersectObject(m, false).length % 2) { // (inside it)
      let out = null;
      for (const d of DIRS) { ray.set(p, d); const h = ray.intersectObject(m, false)[0]; if (h && (!out || h.distance < out.dist)) out = { dist: h.distance, d }; }
      if (out) { const push = out.d.clone().multiplyScalar(out.dist + rad); if (!best || push.length() > best.push.length()) best = { push, inst: m.userData.inst }; }
      return;
    }
    ray.far = rad;
    for (const d of DIRS) {
      ray.set(p, d);
      const h = ray.intersectObject(m, false)[0];
      if (!h) continue;
      const push = d.clone().multiplyScalar(-(rad - h.distance));
      if (!best || push.length() > best.push.length()) best = { push, inst: m.userData.inst };
    }
  });
  return best;
}

/** Points every ~step mm along a route's segments -> [Vector3]. */
function sampleRoute(r, step) {
  const out = [];
  for (const g of r.segs) {
    const n = Math.max(g.t === 'arc' ? 2 : 1, Math.ceil(g.len / step)), c = new RouteCurve([g], g.len);
    for (let k = 0; k < n; k++) out.push(c.getPoint(k / n));
  }
  const last = r.segs[r.segs.length - 1];
  if (last) out.push(last.b.clone());
  return out;
}

/** The leg of the polyline E nearest to p (its index: from E[k] to E[k + 1]). */
function legOfE(E, p) {
  const ln = new THREE.Line3(), q = new THREE.Vector3();
  let best = 0, bd = Infinity;
  for (let k = 0; k + 1 < E.length; k++) { const d = ln.set(E[k], E[k + 1]).closestPointToPoint(p, true, q).distanceTo(p); if (d < bd) { bd = d; best = k; } }
  return best;
}

/** The route kept clear of the parts (as harness.py's avoid): its leads, then the shaped route sampled and every
 *  sample too near a part pushed out — for each leg the deepest one becomes a point of its own, shaped again, a few
 *  rounds. The clicked points stay (anchors). -> {E, where, clashes: [{at, inst}] still too near}. */
function avoidRoute(h, pts, n0, n1, meshes, chains = {}, rounds = 6) {
  const rad = outerD(h) / 2 + CLEAR, boxes = meshes.map((m) => new THREE.Box3().setFromObject(m).expandByScalar(rad));
  let { E, where, tag } = expandE(h, pts, n0, n1, chains);
  const detour = E.map(() => false), r0 = rMinOf(h), own = spansOf(h); // (the points put in round a part: they may move further out)
  const skip = excuser(h, pts), hits = (r) => sampleRoute(r, Math.max(0.5, rad / 3)).map((p) => ({ p, x: probe(meshes, boxes, p, outerD(h) / 2 + CLEAR / 2, skip) })).filter((s) => s.x && s.x.push.length() > 1e-9);
  const kept = (k) => (tag[k] === 'chain' && tag[k + 1] === 'chain') || Object.keys(own).some((j) => where[+j] <= k && k < where[+j + 1]); // (a leg in a chain, or of a span with its own length: that length wins, a hit there is told)
  for (let i = 0; i < rounds; i++) {
    const best = new Map();
    for (const s of hits(shape(E, rMinOf(h)))) { const k = legOfE(E, s.p); if (!kept(k) && (!best.has(k) || s.x.push.length() > best.get(k).x.push.length())) best.set(k, s); }
    if (!best.size) break;
    for (const k of [...best.keys()].sort((a, b) => b - a)) {
      const s = best.get(k), out = s.x.push.clone().setLength(s.x.push.length() + rad / 2); // (half a radius to spare: the arcs cut in)
      const near = [k, k + 1].filter((j) => detour[j] && E[j].distanceTo(s.p) < 2 * r0 + rad);
      if (near.length) { const j = near.reduce((a, b) => (E[a].distanceTo(s.p) <= E[b].distanceTo(s.p) ? a : b)); E[j] = E[j].clone().add(out); continue; } // (its own detour point further out: one corner round the part)
      E.splice(k + 1, 0, s.p.clone().add(out));
      detour.splice(k + 1, 0, true);
      tag.splice(k + 1, 0, 'det');
      where = where.map((w) => (w > k ? w + 1 : w));
    }
  }
  return { E, where, tag, detours: detour.filter(Boolean).length, clashes: hits(routeE(h, E, where, [], stillOf(tag))).filter((s) => !kept(legOfE(E, s.p)) || !(tag[legOfE(E, s.p)] === 'chain')).map((s) => ({ at: s.p.toArray().map((x) => +x.toFixed(1)), inst: s.x.inst })) };
}

/** The route through world points (THREE.Vector3), shaped to the minimum bend radius: each corner an arc of rMin
 *  tangent to both legs; two corners too close for that moved apart along their outer legs until they fit (spread);
 *  only where nothing fits (a short end leg, a U turn narrower than 2 × rMin) the largest radius that does, ok false
 *  -> {segs: [{t: 'line' | 'arc', a, b, len, (arc) c, r, ang, axis}], length, bends: [{at (the point's number in
 *  pts), r, ok, angle (deg), p}]}. The same math as auto3d/modeler/harness.py. */
export function route(pts, rMin) {
  let P = [];
  const idx = [];
  pts.forEach((p, k) => { if (!P.length || p.distanceTo(P[P.length - 1]) > 1e-6) { P.push(p.clone()); idx.push(k); } });
  if (P.length < 2) return { segs: [], length: 0, bends: [] };
  rMin = Math.max(0, +rMin || 0);
  const clicked = P;
  if (rMin > 0) P = spread(P, rMin);
  const { U, turn, T: Ts, R: Rs } = fit(P, rMin);
  const segs = [], bends = [], station = P.map(() => 0);
  let at = P[0], length = 0;
  for (let i = 1; i + 1 < P.length; i++) {
    const a = turn[i];
    if (a <= 1e-9) { station[i] = length + P[i].distanceTo(at); continue; }
    const T = Ts[i], r = Rs[i];
    bends.push({ at: idx[i], r, ok: r >= rMin * 0.97, angle: (a * 180) / Math.PI, p: clicked[i] });
    const A = P[i].clone().addScaledVector(U[i - 1], -T), B = P[i].clone().addScaledVector(U[i], T);
    if (A.distanceTo(at) > 1e-9) { segs.push({ t: 'line', a: at, b: A, len: A.distanceTo(at) }); length += A.distanceTo(at); }
    station[i] = length + (r * a) / 2; // (a corner's place along the cable: its arc's middle)
    if (r > 1e-9) {
      const w = U[i].clone().sub(U[i - 1]).normalize(), c = P[i].clone().addScaledVector(w, r / Math.cos(a / 2));
      const axis = A.clone().sub(c).cross(B.clone().sub(c)).normalize();
      segs.push({ t: 'arc', a: A, b: B, c, r, ang: a, axis, len: r * a, bend: bends.length - 1 });
      length += r * a;
    }
    at = B;
  }
  if (P[P.length - 1].distanceTo(at) > 1e-9) { segs.push({ t: 'line', a: at, b: P[P.length - 1], len: P[P.length - 1].distanceTo(at) }); length += P[P.length - 1].distanceTo(at); }
  station[P.length - 1] = length;
  return { segs, length, bends, station };
}

/** Which way a span's slack bows (square to it): out of the corners at its ends — the way the cable comes in
 *  (before: the leg before it), away from where it goes on (after) —, so the bow leaves its ends without a sharp
 *  turn; its corners turning opposite ways (an S: out of one is into the other), square to their plane, the downward
 *  side; with little of that (an end span, a straight run), down (−z) as it hangs; a vertical span with nothing to go
 *  by: along x. As harness.py's _sag. */
function sag(a, b, before = null, after = null) {
  const u = b.clone().sub(a).normalize(), sq = (g) => g.clone().addScaledVector(u, -g.dot(u));
  const n = new THREE.Vector3();
  if (before) n.add(sq(before.clone().normalize()));
  if (after) n.sub(sq(after.clone().normalize()));
  if (before && after && n.length() < 0.5 && sq(before.clone().normalize()).length() > 0.5) {
    const side = u.clone().cross(sq(before.clone().normalize()));
    if (side.length() > 1e-6) { side.normalize(); return side.z > 0 ? side.negate() : side; }
  }
  n.addScaledVector(sq(V([0, 0, -1])), 0.25);
  if (n.length() > 0.05) return n.normalize();
  for (const g of [[0, 0, -1], [1, 0, 0], [0, 1, 0]]) {
    const m = sq(V(g));
    if (m.length() > 1e-3) return m.normalize();
  }
  return null;
}

/** The points with each span k bowed h[k] mm (0: straight): two points put in, in the middle of its straight part
 *  (between the arcs of its end corners) ± a quarter of that + h / 2 (no more than rMin: a deep loop on a short span
 *  reaches out past it) and h off it the way it hangs (sag) — a flat-bottomed bow the corners round at rMin; a
 *  shallow bow leaves the end corners as they were -> {Q, where (where each point of P went)}. As harness.py's _bowed. */
function bowed(P, h, rMin) {
  const Q = [P[0]], where = [0], T = rMin > 0 && P.length > 2 ? fit(P, rMin).T : P.map(() => 0);
  for (let k = 0; k + 1 < P.length; k++) {
    const a = P[k], b = P[k + 1];
    if (h[k] > 1e-9) {
      const L = a.distanceTo(b), n = sag(a, b, k > 0 ? a.clone().sub(P[k - 1]) : null, k + 2 < P.length ? P[k + 2].clone().sub(b) : null), u = b.clone().sub(a).divideScalar(L);
      const [s0, s1] = L - T[k] - T[k + 1] > 1e-6 ? [T[k], L - T[k + 1]] : [0, L], m = (s0 + s1) / 2, f = s1 - s0; // (its straight part)
      const w = rMin > 0 ? Math.min(rMin, f / 4 + h[k] / 2) : f / 4;
      Q.push(a.clone().addScaledVector(u, m - w).addScaledVector(n, h[k]), a.clone().addScaledVector(u, m + w).addScaledVector(n, h[k]));
    }
    Q.push(b);
    where.push(Q.length - 1);
  }
  return { Q, where };
}

/** The x ≥ 0 that makes f(x) = target (f growing from f(0) ≤ target): doubled until past it, then bisected. */
function solve(f, target, scale) {
  let lo = 0, hi = Math.max(scale, 1e-3) * 0.05;
  for (let i = 0; i < 60 && f(hi) < target; i++) { lo = hi; hi *= 2; }
  for (let i = 0; i < 50 && hi - lo >= 1e-6 * scale; i++) { const mid = (lo + hi) / 2; if (f(mid) < target) lo = mid; else hi = mid; }
  return (lo + hi) / 2;
}

/** The route with slack (as harness.py's shape): a span (the cable between points k and k + 1) given its own length
 *  gets a bow that hangs the way gravity pulls, as deep as makes it that long (from corner to corner, each corner's
 *  place the middle of its arc — they add up to the whole); the whole cable given a length (total) bows all its spans
 *  alike — the spans' own lengths win when both are given. Too short for its ends: straight, taut, reported with how
 *  much it is short. spans: {k: length} -> route(…) + {spans: [each span's length], taut: [{span: k | null, short}],
 *  totalIgnored}. */
export function shape(pts, rMin, spans = null, total = null, still = []) {
  const P = [], keep = [];
  pts.forEach((p, k) => { if (!P.length || p.distanceTo(P[P.length - 1]) > 1e-6) { P.push(p.clone()); keep.push(k); } });
  rMin = Math.max(0, +rMin || 0);
  if (P.length < 2) return { ...route(P, rMin), spans: [], taut: [], totalIgnored: false };
  const want = new Map();
  for (const [k, v] of Object.entries(spans || {})) { const i = keep.indexOf(+k); if (i >= 0 && i + 1 < P.length && +v > 0) want.set(i, +v); }
  const run = (h) => {
    const { Q, where } = bowed(P, h, rMin), r = route(Q, rMin), st = r.station || Q.map(() => 0);
    r.spans = P.length > 1 ? P.slice(1).map((_, k) => st[where[k + 1]] - st[where[k]]) : [];
    r.where = where;
    return r;
  };
  let h = P.slice(1).map(() => 0);
  const taut = [];
  if (P.length >= 2 && want.size) {
    const base = run(h).spans;
    for (const [k, v] of want) if (base[k] > v + 0.5) taut.push({ span: keep[k], short: base[k] - v });
    for (let pass = 0; pass < 4; pass++) { // (a span's bow turns its ends' corners, the next span's length with them: again)
      for (const [k, v] of want) {
        if (base[k] > v + 0.5) continue;
        const x = solve((s) => run([...h.slice(0, k), s, ...h.slice(k + 1)]).spans[k], v, P[k].distanceTo(P[k + 1]));
        h = [...h.slice(0, k), x, ...h.slice(k + 1)];
      }
    }
  } else if (P.length >= 2 && +total > 0) {
    const legs = P.slice(1).map((p, k) => (still.includes(k) ? 0 : p.distanceTo(P[k]))), L0 = run(h).length;
    if (L0 > +total + 0.5) taut.push({ span: null, short: L0 - +total });
    else { const lam = solve((x) => run(legs.map((g) => x * g)).length, +total, 1); h = legs.map((g) => lam * g); }
  }
  const r = run(h);
  r.bends = r.bends.map((b) => { let k = 0; r.where.forEach((w, i) => { if (w <= b.at) k = i; }); return { ...b, at: keep[k] ?? b.at }; });
  r.taut = taut;
  r.totalIgnored = !!(want.size && +total > 0);
  return r;
}

/** The route as a three.js curve, parametrised by its length (TubeGeometry samples it evenly). */
class RouteCurve extends THREE.Curve {
  constructor(segs, length) { super(); this.segs = segs; this.length = length || 1; }

  getPoint(u, out = new THREE.Vector3()) {
    let s = Math.max(0, Math.min(1, u)) * this.length;
    for (const g of this.segs) {
      if (s <= g.len + 1e-9 || g === this.segs[this.segs.length - 1]) {
        const k = g.len ? Math.min(1, s / g.len) : 0;
        if (g.t === 'line') return out.copy(g.a).lerp(g.b, k);
        return out.copy(g.a).sub(g.c).applyAxisAngle(g.axis, g.ang * k).add(g.c);
      }
      s -= g.len;
    }
    return out.copy(this.segs[0]?.a || new THREE.Vector3());
  }

  getUtoTmapping(u) { return u; } // (already by length)
  getLength() { return this.length; }
}

/** A polyline as a curve by its length (a wire's offset line). */
class PolyCurve extends THREE.Curve {
  constructor(pts) {
    super();
    this.pts = pts;
    this.acc = [0];
    for (let i = 1; i < pts.length; i++) this.acc.push(this.acc[i - 1] + pts[i].distanceTo(pts[i - 1]));
  }

  getPoint(u, out = new THREE.Vector3()) {
    const L = this.acc[this.acc.length - 1], s = Math.max(0, Math.min(1, u)) * L;
    let i = 1;
    while (i < this.acc.length - 1 && this.acc[i] < s) i++;
    const span = this.acc[i] - this.acc[i - 1] || 1;
    return out.copy(this.pts[i - 1]).lerp(this.pts[i], (s - this.acc[i - 1]) / span);
  }

  getUtoTmapping(u) { return u; }
}

// ------------------------------------------------------------------ where its points are
/** A placed part's matrix as drawn (exploded too: the points stay on it), else as placed. */
function matrixOf(asm, id) {
  const mesh = (asm.view?.meshes || []).find((m) => m.userData.inst === id);
  if (mesh) return mesh.matrix;
  const it = asm.inst(id);
  return it ? new THREE.Matrix4().fromArray(it.matrix) : null;
}

/** A point of a harness in the world (a point on a part: off its face by Ø/2 + clearance) -> Vector3 or null (its
 *  part is gone). M: a placed part's matrix (default: as drawn). */
export function pointAt(asm, h, p, M = null) {
  if (p.xyz) return V(p.xyz);
  M = M || matrixOf(asm, p.inst);
  if (!M) return null;
  const w = V(p.at).applyMatrix4(M);
  if (p.n) w.addScaledVector(V(p.n).applyMatrix3(new THREE.Matrix3().getNormalMatrix(M)).normalize(), lift(h));
  return w;
}

/** A click on a round flat face — a pin's top, a ring round a hole: a cylinder of the part stands square on it round
 *  its centre and the click is within that cylinder's radius — -> its centre (on the axis, part coordinates) or null.
 *  f: the body's face, at: the click (part coordinates). */
function axisOf(body, f, at) {
  if (f.type !== 'plane' || !f.normal) return null;
  const o = V(f.frame?.o || f.centroid), n = V(f.normal).normalize();
  let R = 0;
  for (const c of body.faces || []) {
    if (c.type !== 'cylinder' || !c.axis) continue;
    const d = V(c.axis.d).normalize(), off = o.clone().sub(V(c.axis.o));
    if (Math.abs(d.dot(n)) < 0.999 || off.addScaledVector(d, -off.dot(d)).length() > 0.01) continue;
    R = Math.max(R, c.radius || 0);
  }
  const r = at.clone().sub(o);
  return R > 0 && r.addScaledVector(n, -r.dot(n)).length() <= R + 1e-6 ? o : null;
}

/** A world spot in a placed part's own coordinates (as drawn) -> [x, y, z] or null. */
function localOf(asm, inst, w) { const M = matrixOf(asm, inst); return M ? w.clone().applyMatrix4(M.clone().invert()).toArray().map((x) => +x.toFixed(4)) : null; }

/** A point of a part 🔓 unlocked (it stays where it is now, in space; it remembers its part) or 🔒 locked again (it
 *  sticks to its part where it is now) -> the new point. */
export function lockPoint(asm, h, p, lock) {
  if (lock) {
    const on = p.on || (p.inst ? p : null);
    if (!on?.inst || !p.xyz) return p;
    const M = matrixOf(asm, on.inst);
    if (!M) return p;
    const w = V(p.xyz);
    if (on.n) w.addScaledVector(V(on.n).applyMatrix3(new THREE.Matrix3().getNormalMatrix(M)).normalize(), -lift(h)); // (back onto its face)
    return { inst: on.inst, at: localOf(asm, on.inst, w), ...(on.n ? { n: on.n } : {}), ...(on.face ? { face: on.face } : {}), ...(p.conn !== undefined ? { conn: p.conn } : {}) };
  }
  if (!p.inst) return p;
  const w = pointAt(asm, h, p);
  return w ? { xyz: w.toArray().map((x) => +x.toFixed(3)), on: { inst: p.inst, at: p.at, ...(p.n ? { n: p.n } : {}), ...(p.face ? { face: p.face } : {}) }, ...(p.conn !== undefined ? { conn: p.conn } : {}) } : p;
}

/** The world points of a harness (its placed parts' matrices from the assembly document: the BOM, the export). */
export function docPoints(doc, h) {
  const mats = new Map((doc.instances || []).map((it) => [it.id, new THREE.Matrix4().fromArray(it.matrix)]));
  return (h.points || []).map((p) => pointAt({ inst: () => null }, h, p, p.inst ? mats.get(p.inst) || null : null)).filter(Boolean);
}

/** A harness as the kernel's step (auto3d/modeler/harness.py), its points in the assembly's frame. */
export function harnessStep(doc, h) {
  const r = docRoute(doc, h); // (its leads and detours: the points it runs through, its spans on those)
  return { id: h.id, type: 'harness', kind: h.kind, points: r.points.map((p) => p.toArray().map((v) => +v.toFixed(4))), d: +h.d || (h.kind === 'ribbon' ? 1 : 6),
    wires: (h.wires || []).map((w) => ({ d: +w.d || 1.5, color: w.color })), pitch: +h.pitch || 1.27, r_min: rMinOf(h), ...(lockedOf(h) ? { length: lockedOf(h) } : {}),
    ...(r.still.length && (lockedOf(h) || Object.keys(r.own).length) ? { still: r.still } : {}), ...(Object.keys(r.own).length ? { spans: Object.entries(r.own).map(([k, v]) => ({ from: +k, length: v })) } : {}) };
}

/** Each harness of an assembly as a part placed where it is, for the drawing sheet: [{id, part: {features}, matrix}]. */
export function harnessSolids(doc, matrix) {
  return (doc?.harnesses || []).filter((h) => (h.points || []).length > 1).map((h) => ({ id: h.id, part: { features: [harnessStep(doc, h)] }, matrix }));
}

/** The assembly's STEP / GLB tree with its harnesses: a part each ("Harness 1"), in its colour(s), placed as is. */
export function withHarnesses(asm, tree) {
  const root = tree.assemblies[tree.root];
  for (const h of asm.doc.harnesses || []) {
    if ((h.points || []).length < 2) continue;
    const key = `${tree.root}:${h.id}`, wires = h.kind === 'wires' ? h.wires || [] : [];
    tree.parts[key] = { name: nameOf(h), features: [harnessStep(asm.doc, h)], colour: hexOf(h.kind === 'wires' ? wires[0]?.color : h.kind === 'ribbon' ? 'grey' : h.color),
      ...(wires.length > 1 ? { paint: wires.map((w, k) => ({ feature: `${h.id}:w${k}`, color: hexOf(w.color) })) } : {}) };
    root.instances.push({ ref: key, matrix: new THREE.Matrix4().identity().toArray() });
  }
  return tree;
}

/** "The cable is taut — 12 mm short" / "Span 2–3 is taut — 12 mm short" (a shape's taut entry). */
const tautText = (x) => (x.span === null || x.span === undefined ? t2('The cable is taut — {x} mm short', { x: num(Math.round(x.short * 10) / 10) })
  : t2('Span {a}–{b} is taut — {x} mm short', { a: x.span + 1, b: x.span + 2, x: num(Math.round(x.short * 10) / 10) }));

/** A span's own entry changed: {length: mm | null, chain: C… | null} (null: taken off; an entry with nothing left goes). */
function spanSet(h, from, change) {
  const list = h.spans || [], s = { ...(list.find((x) => +x.from === from) || { from }) };
  for (const [k, v] of Object.entries(change)) { if (v === null || v === undefined) delete s[k]; else s[k] = v; }
  h.spans = [...list.filter((x) => +x.from !== from), ...(s.length > 0 || s.chain ? [s] : [])].sort((a, b) => a.from - b.from);
  if (!h.spans.length) delete h.spans;
}

/** ⛓ The chain span k of a harness is routed through (its id) or null. */
const chainOfSpan = (h, k) => (h.spans || []).find((s) => +s.from === k)?.chain || null;

/** "Harness 1" (its own name when it has one). */
export const nameOf = (h) => h.name || t2('Harness {n}', { n: String(h.id).replace(/\D/g, '') || h.id });
/** What it is in short: "4 × Ø1.5", "Ø6", "10 × 1.27". */
export const specOf = (h) => (h.kind === 'wires' ? `${(h.wires || []).length} × Ø${num(wireD(h))}` : h.kind === 'ribbon' ? `${(h.wires || []).length} × ${num(+h.pitch || 1.27)}` : `Ø${num(outerD(h))}`);

/** The BOM lines of an assembly's harnesses: a line per wire (a cable, ribbon, sleeve: one), its length with the
 *  reserve, rounded up to 10 mm -> [{key, name, qty, length_mm, colour, harness}]. */
export function harnessBom(doc) {
  const cs = getLang() === 'cs', out = new Map();
  for (const h of doc?.harnesses || []) {
    const pts = docPoints(doc, h);
    if (pts.length < 2) continue;
    const L = Math.ceil((docRoute(doc, h).length * (1 + (Number.isFinite(+h.reserve) ? +h.reserve : 5) / 100)) / 10) * 10;
    const line = (what, colour) => {
      const name = `${what}${colour ? ` ${cs ? colourOf(colour)[4] : colourOf(colour)[2]}` : ''} — ${mmText(L)} mm`, key = `${h.id}|${name}`;
      const r = out.get(key) || { key, name, qty: 0, length_mm: L, colour: colour || null, harness: h.id, harness_name: nameOf(h) };
      r.qty++;
      out.set(key, r);
    };
    if (h.kind === 'wires') for (const w of h.wires || []) line(`${cs ? 'Vodič' : 'Wire'} Ø${num(+w.d || 1.5)} mm`, w.color || 'black');
    else if (h.kind === 'ribbon') line(`${cs ? 'Plochý kabel' : 'Ribbon cable'} ${(h.wires || []).length} × ${num(+h.pitch || 1.27)} mm`, null);
    else if (h.kind === 'sleeve') line(`${cs ? 'Chránička' : 'Sleeve'} Ø${num(outerD(h))} mm`, null);
    else line(`${cs ? 'Kabel' : 'Cable'} Ø${num(outerD(h))} mm`, h.color || 'black');
  }
  return [...out.values()];
}

/** For the AI and the tree: a harness's facts as the parts stand now. */
export function harnessFacts(asm, h) {
  const r = routeAt(asm, h), tool = asm.harnessTool;
  const list = (h.points || []).map((p, i) => { const w = pointAt(asm, h, p), on = p.inst ? p : p.on;
    return { n: i + 1, ...(on?.inst ? { part: on.inst, locked: !!p.inst } : { part: null }), ...(on?.face ? { face: on.face } : {}), ...(p.clip ? { clip: p.clip } : {}), ...(connOf(h, i) ? { connection: true } : {}), xyz: w ? w.toArray().map((x) => +x.toFixed(2)) : null }; });
  return { id: h.id, name: nameOf(h), type: h.kind, d_mm: +outerD(h).toFixed(3), r_min_mm: rMinOf(h), points: (h.points || []).length, point_list: list, length_mm: +r.length.toFixed(1),
    ...(h.kind === 'wires' || h.kind === 'ribbon' ? { wires: (h.wires || []).map((w) => ({ d: +w.d || 1.5, color: w.color })) } : { color: h.color || 'black' }),
    ...(lockedOf(h) ? { length_locked_mm: lockedOf(h) } : {}), ...(r.taut.length ? { taut: { short_mm: +r.taut[0].short.toFixed(1), ...(r.taut[0].span !== null ? { span: `${r.taut[0].span + 1}–${r.taut[0].span + 2}` } : {}) } } : {}),
    ...(h.spans?.length ? { spans: h.spans.map((s) => ({ from: +s.from + 1, to: +s.from + 2, ...(+s.length > 0 ? { length_mm: +s.length } : {}), ...(s.chain ? { chain: s.chain } : {}), now_mm: +(r.spans[s.from] ?? 0).toFixed(1) })) } : {}),
    ...(r.totalIgnored ? { note: 'the spans\' own lengths win over length_locked' } : {}),
    ...(r.detours ? { detour_points: r.detours } : {}), ...(r.dropped.length ? { spans_not_kept: r.dropped.map((k) => `${k + 1}–${k + 2}`) } : {}),
    ...(r.clashes.length ? { still_hits: [...new Set(r.clashes.map((c) => c.inst))] } : {}),
    ...(r.bends.some((b) => !b.ok) ? { bends_too_tight: r.bends.filter((b) => !b.ok).map((b) => ({ point: b.at + 1, r_mm: +b.r.toFixed(1), min_mm: rMinOf(h) })) } : {}),
    ...(r.short.length ? { too_close: r.short.map((x) => ({ xyz: x.p.toArray().map((v) => +v.toFixed(2)), lead_mm: +x.need.toFixed(1) })) } : {}),
    ...(tool?.through.get(h.id)?.length ? { through_parts: tool.through.get(h.id), through_at: (tool.throughAt?.get(h.id) || []).map((c) => ({ part: c.inst, span: `${c.span}–${c.span + 1}`, xyz: c.at })) } : {}) };
}

const defaults = () => {
  let s = {};
  try { s = JSON.parse(localStorage.getItem('a3d.harness') || '{}') || {}; } catch { s = {}; }
  return { kind: KINDS[s.kind] ? s.kind : 'wires', n: s.n > 0 ? s.n : 4, wd: s.wd > 0 ? s.wd : 1.5, d: s.d > 0 ? s.d : 6 };
};
const wiresOf = (n, d, had = []) => Array.from({ length: Math.max(1, Math.min(60, n | 0)) }, (_, k) => had[k] || { d, color: ORDER[k % ORDER.length] });

// ------------------------------------------------------------------ the tool
export class HarnessTool {
  constructor(asm) {
    this.asm = asm;
    this.edit = null; // the harness whose points are being clicked
    this.sel = null; // the harness chosen
    this.pt = null; // its point chosen (Delete removes it)
    this.hover = null; // where a click would put the next point
    this.through = new Map(); // harness id -> the parts its centre line goes through
    this.built = new Map(); // harness id -> {key, objs}
    this.taut = new Set(); // the harnesses pulled taut (🔒 their length too short for their ends)
    this.hl = null; // its point under the mouse in the panel's list (lit in the view)
    this.span = null; // its span chosen (the cable clicked between two points, or its row): ➰ a loop there
    this.spanEdit = null; // the span whose length is being typed
    this.spanHl = null; // its span row under the mouse (lit in the view)
    this.altDepth = 0; // Alt + click: how many faces behind the front one (again at the same spot: one further)
    this.adopted = new WeakSet(); // the harnesses whose points in space were looked at: one lying on a face is locked to it
    this.clips = new ClipPick(this); // 📎 a clip's ghost where it would go, the pick list
    asm.els.viewport.addEventListener('pointerleave', () => { if (this.hover) { this.hover = null; this.drawNow(); } }); // (no preview with the mouse elsewhere)
    asm.els.viewport.addEventListener('pointerdown', (e) => this.down(e), true); // (before the part's drag and the view's turning)
  }

  list() { return this.asm.doc.harnesses || []; }
  get(id) { return this.list().find((h) => h.id === id) || null; }
  get busy() { return !!this.edit; }

  /** 🔌 A new harness (the last one's kind and sizes), its points clicked next; from: its first point. */
  start(from = null) {
    const a = this.asm, s = defaults();
    a.measuring && a.toggleMeasure();
    a.painting && a.togglePaint();
    if (a.mode !== 'idle') a.cancelJoint();
    if (a.bolt) a.cancelBolt();
    a.clashPanel = false;
    a.fastenerPanel = false;
    this.finish(false);
    const n = Math.max(0, ...this.list().map((h) => parseInt(String(h.id).replace(/\D/g, ''), 10) || 0)) + 1;
    const h = { id: `H${n}`, kind: s.kind, d: s.d, color: 'black', wires: wiresOf(s.kind === 'ribbon' ? 10 : s.n, s.wd), pitch: 1.27, reserve: 5, points: from ? [from] : [] };
    if (h.kind === 'ribbon') h.d = 1;
    (a.doc.harnesses ||= []).push(h);
    this.edit = h.id;
    this.sel = h.id;
    this.pt = null;
    a.sel = null;
    a.sel2 = null;
    a.facePicks = [];
    a.snapPick = null;
    a.view.setMeasure([]);
    if (from) a.history.commit();
    a.hint(t('🔌 Click the points the harness passes: a face of a part, a hole\'s centre, or in space — Esc / Enter / ✓ Done keeps them.'));
    a.render();
    a.draw();
    return h;
  }

  /** ✎ Click more points of a harness (drag them, click the cable to add one between, Delete). */
  editPoints(id) {
    if (!this.get(id)) return;
    this.edit = id;
    this.sel = id;
    this.pt = null;
    this.hover = null; // (no next point shown until the mouse is over the view again)
    this.asm.sel = null;
    this.asm.hint(t('🔌 Click the points the harness passes: a face of a part, a hole\'s centre, or in space — Esc / Enter / ✓ Done keeps them.'));
    this.asm.render();
    this.asm.draw();
  }

  /** Its points changed by fn(points) — one undo step (the spans' own lengths keep to their points). */
  editPts(h, fn) {
    const before = (h.points || []).slice(), n = before.length;
    fn(h.points);
    if (h.points.length !== n) keepSpans(h, before);
    const gone = before.map((p) => p.clip).filter((c) => c && !h.points.some((p) => p.clip === c) && this.asm.inst(c)); // (📎 its point taken away: the clip stays — offered to go too)
    this.orphans = [...new Set([...(this.orphans || []).filter((c) => this.asm.inst(c)), ...gone])];
    this.span = null;
    this.spanEdit = null;
    this.asm.commit();
  }

  /** ➰ Span `from` (to the next point) given its own length (null: none) — one undo step. */
  setSpan(id, from, length) { this.set(id, (x) => spanSet(x, from, { length: length > 0 ? +(+length).toFixed(1) : null })); }

  /** ⛓ Span `from` routed through chain `chain` (its id C…; null: not any more) — one undo step. It enters the chain at
   *  the end nearer its first point now, and keeps that end as the chain moves (`enter`). */
  setSpanChain(id, from, chain) {
    const h = this.get(id), enter = chain && h ? enterNow(this.asm, h, from, chain) : null;
    this.set(id, (x) => spanSet(x, from, { chain: chain || null, enter }));
  }

  /** The part a point of a harness sits on (a clip's point: the part that clip is fixed to) or null (in space). */
  hostOf(p) {
    if (!p?.inst) return null;
    return (p.clip && (this.asm.doc.mates || []).find((m) => m.move === p.clip && m.type === 'rigid')?.onto) || p.inst;
  }

  /** 🔗 A clip or a chain's first link just put in on part `host`, fixed to it (it goes with it — a carriage, an arm);
   *  nothing when there is none. */
  fixOn(inst, host) {
    if (!host || host === inst || !this.asm.inst(host)) return;
    try { this.asm.fixTogether(inst, host); } catch { /* (held where it is put) */ }
  }

  /** 🔌 Point i of harness h a connection point or not (on: the other way round) — one undo step. */
  setConn(h, i, on = !connOf(h, i)) {
    if (!h.points?.[i]) return;
    this.editPts(h, (P) => { P[i] = { ...P[i], conn: !!on }; });
  }

  /** 📎 Where a clip on point i of harness h goes -> {face (the point on the face, world), n (its outward normal), dir
   *  (the cable's way there: from the point before to the one after, or null), D (the bundle's Ø), host (the part it is
   *  fixed to), old / current (a point with a clip already: that clip I… and its {item, size} — it is swapped)} or null
   *  (a point in space or in a hole: no clip there). */
  clipPose(h, i) {
    const a = this.asm, p = h.points?.[i], D = outerD(h);
    if (!p?.inst) return null;
    const pts = h.points.map((q) => pointAt(a, h, q)), w = pts[i];
    if (!w) return null;
    const dir = (pts[i + 1] || w).clone().sub(pts[i - 1] || w), out = { D, dir: dir.lengthSq() > 1e-9 ? dir : null };
    if (p.clip) { // (its mounting face and normal from the clip that is there)
      const it = a.inst(p.clip), lib = it && a.hooks.partData(it.part)?.library, item = lib && clipItem(lib.id);
      if (!item) return null;
      const f = clipFrames(item, lib.size, D), M = new THREE.Matrix4().fromArray(it.matrix);
      return { ...out, face: V(f.mount.o || [0, 0, 0]).applyMatrix4(M), n: V(f.mount.n || [0, 0, -1]).transformDirection(M).negate(),
        host: (a.doc.mates || []).find((m) => m.move === p.clip && m.type === 'rigid')?.onto || null, old: p.clip, current: { item: lib.id, size: lib.size } };
    }
    if (!p.n) return null;
    const n = normalAt(a, p);
    return { ...out, face: w.clone().addScaledVector(n, -lift(h)), n, host: this.hostOf(p) };
  }

  /** 📎 A clip on point i of harness h (it lies on a part's face): choice (clipsFor's; default the snuggest for its
   *  bundle) placed there with the cable along its way, 🔗 fixed to that part (it goes with it), the point then on the
   *  clip's axis, locked to the clip — one undo step. A point with a clip already: that one swapped for it (taken out),
   *  the point kept. -> the clip's placed part (I…). */
  async clipAt(h, i, choice = null) {
    const a = this.asm, pose = this.clipPose(h, i);
    if (!pose) throw new Error(t('A clip goes on a point lying on a part\'s face.'));
    const c = choice || clipsFor(pose.D)[0];
    if (!c) throw new Error(t2('No clip in the library holds a bundle of Ø{d} mm.', { d: num(pose.D) }));
    this.clips.close();
    const mark = a.history.mark(), r = await placeClip(a, c, pose.face, pose.n, pose.dir, { d: pose.D });
    this.fixOn(r.inst, pose.host);
    const o = r.axis ? V(r.axis.o) : pose.face;
    this.editPts(h, (P) => { P[i] = { inst: r.inst, at: localOf(a, r.inst, o), clip: r.inst }; });
    if (pose.old && a.inst(pose.old) && !h.points.some((q) => q.clip === pose.old)) { // (🔁 swapped: the old clip goes)
      this.orphans = (this.orphans || []).filter((x) => x !== pose.old);
      a.removeInst(pose.old);
    }
    a.history.squash(mark);
    return r.inst;
  }

  /** 📎 The same clip on every point of harness h that lies on a face and has none yet — one undo step -> how many. */
  async clipAll(h, choice) {
    const a = this.asm, mark = a.history.mark();
    let n = 0;
    for (let i = 0; i < (h.points || []).length; i++) {
      const p = h.points[i];
      if (!p.inst || !p.n || p.clip) continue;
      await this.clipAt(h, i, choice);
      n++;
    }
    a.history.squash(mark);
    return n;
  }

  /** ⛓ Span k of harness h routed through chain `id` (C… or its first link I…); none given: one from the library put in,
   *  sized for its bundle (its opening, its bend ≥ the harness's radius), its fixed end at the span's first point and
   *  🔗 fixed to the part that point is on — one undo step -> the chain's id. */
  async chainSpan(h, k, id = undefined) {
    const a = this.asm, P = h.points || [];
    if (!(k >= 0 && k + 1 < P.length)) throw new Error(t2('A span runs from a point to the next: 1 … {n}.', { n: P.length - 1 }));
    if (id === null) { this.setSpanChain(h.id, k, null); return null; }
    let rec = id ? chainRec(a, id) : null;
    if (id && !rec) throw new Error(t2('No energy chain “{id}” in the assembly.', { id }));
    const mark = a.history.mark();
    if (!rec) {
      const c = chainsFor(outerD(h), rMinOf(h))[0];
      if (!c) throw new Error(t2('No energy chain in the library takes a bundle of Ø{d} mm bent at R {r} mm or more.', { d: num(outerD(h)), r: num(rMinOf(h)) }));
      const A = pointAt(a, h, P[k]), B = pointAt(a, h, P[k + 1]), placed = await placeChain(a, c, A, B.clone().sub(A));
      rec = addChain(a, placed.inst, placed.dims);
      this.fixOn(placed.inst, this.hostOf(P[k]));
      drawChains(a);
    }
    this.setSpanChain(h.id, k, rec.id);
    a.history.squash(mark);
    return rec.id;
  }

  /** ✓ Done (Esc, Enter): the points so far are kept; fewer than two — nothing is kept. */
  finish(redraw = true) {
    const h = this.get(this.edit);
    this.edit = null;
    this.hover = null;
    this.pt = null;
    if (!h) return;
    if ((h.points || []).length < 2) {
      this.asm.doc.harnesses = this.list().filter((x) => x !== h);
      this.sel = null;
      if ((h.points || []).length) this.asm.history.commit();
      this.asm.hooks.toast(t('A harness needs at least two points — none was kept.'), 'info', 4000);
    }
    this.asm.hint('');
    if (redraw) { this.asm.render(); this.asm.draw(); }
  }

  remove(id) {
    this.asm.doc.harnesses = this.list().filter((h) => h.id !== id);
    if (this.sel === id) this.sel = null;
    if (this.edit === id) { this.edit = null; this.hover = null; this.asm.hint(''); }
    this.asm.commit();
  }

  /** A setting of a harness changed (one undo step): its kind, Ø, count, R, colours. */
  set(id, change) {
    const h = this.get(id);
    if (!h) return;
    change(h);
    if (!h.wires?.length) h.wires = wiresOf(4, 1.5);
    try { localStorage.setItem('a3d.harness', JSON.stringify({ kind: h.kind, n: h.wires.length, wd: wireD(h), d: +h.d || 6 })); } catch { /* private window */ }
    this.asm.commit();
  }

  /** 🔒 Its length locked as it is now (on: off again) — one undo step. */
  lockLength(id) {
    const h = this.get(id);
    if (!h) return;
    if (lockedOf(h)) { this.set(id, (x) => { delete x.length_locked; }); return; }
    const L = routeAt(this.asm, h).length;
    this.set(id, (x) => { x.length_locked = +L.toFixed(1); });
  }

  /** Where a click puts a point: a hole's centre (snapped), a face of a part (lying on it), else in space — on the
   *  plane through `ref` (the last point) facing the camera -> a point of the harness's JSON + its world spot. */
  candidate(e, ref = null) {
    const v = this.asm.view, sp = v.measurePoint(e.clientX, e.clientY, 8);
    const local = (inst, w) => { const M = matrixOf(this.asm, inst); return M ? w.clone().applyMatrix4(M.clone().invert()) : null; };
    const centre = () => { // (a hole's centre snapped: right there, the cable goes through)
      const at = sp?.snap === 'centre' && sp.inst ? local(sp.inst, sp.point) : null;
      return at ? { p: { inst: sp.inst, at: at.toArray().map((x) => +x.toFixed(4)) }, w: sp.point.clone(), what: 'centre' } : null;
    };
    const ray = v.ray(e.clientX, e.clientY), hits = ray.intersectObjects(v.meshes || [], false);
    const depth = e.altKey ? Math.min(this.altDepth, hits.length - 1) : 0, hit = hits[Math.max(0, depth)]; // (Alt: a face behind the front one)
    if (!hit?.face) return centre() || this.inSpace(ray, ref);
    if (hit.face) {
      const inst = hit.object.userData.inst, at = local(inst, hit.point), n = hit.face.normal.clone();
      const nw = n.clone().applyMatrix3(new THREE.Matrix3().getNormalMatrix(hit.object.matrix)).normalize();
      if (!depth && nw.dot(ray.ray.direction) > 0) n.negate(); // (the side seen: the cable lies on it; a face behind: its outside)
      const { faceIds, body } = hit.object.userData, fid = faceIds?.[hit.faceIndex];
      const f = body?.faces?.[fid]?.id === fid ? body.faces[fid] : body?.faces?.find((x) => x.id === fid);
      const ax = f && axisOf(body, f, at); // (a round face — a pin's top, a ring round a hole —: its centre, on its axis)
      if (ax) return { p: { inst, at: ax.toArray().map((x) => +x.toFixed(4)), n: n.normalize().toArray().map((x) => +x.toFixed(6)), face: f.name }, w: ax.clone().applyMatrix4(hit.object.matrix), what: 'axis', depth };
      if (!depth) { const c = centre(); if (c) return c; } // (a pin's top first: lying on it, on its axis)
      return { p: { inst, at: at.toArray().map((x) => +x.toFixed(4)), n: n.normalize().toArray().map((x) => +x.toFixed(6)), ...(f?.name ? { face: f.name } : {}) }, w: hit.point.clone(), what: 'face', depth };
    }
  }

  /** A point in space under the mouse: on the plane through ref (else the view's centre) facing the camera. */
  inSpace(ray, ref) {
    const v = this.asm.view, o = ref || v.controls.target.clone(), dir = v.camera.getWorldDirection(new THREE.Vector3()), w = new THREE.Vector3();
    if (!ray.ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(dir, o), w)) return null;
    return { p: { xyz: w.toArray().map((x) => +x.toFixed(3)) }, w, what: 'space' };
  }

  /** The harness's points on the screen -> the one within px of the mouse (its index) or -1. */
  pointNear(h, e, px = 10) {
    let best = -1, bd = px;
    (h.points || []).forEach((p, i) => {
      const w = pointAt(this.asm, h, p);
      if (!w) return;
      const [x, y] = this.asm.view.toScreen(w), d = Math.hypot(x - e.clientX, y - e.clientY);
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }

  /** The cable near the mouse (within px on the screen) -> {leg (insert after this point), w (the spot)} or null. */
  cableNear(h, e, px = 7) {
    const pts = (h.points || []).map((p) => pointAt(this.asm, h, p)), ok = pts.filter(Boolean);
    const r = routeAt(this.asm, h);
    if (!r.segs.length) return null;
    const curve = new RouteCurve(r.segs, r.length), n = Math.min(400, Math.max(40, Math.ceil(r.length / 2)));
    let best = null;
    for (let i = 0; i <= n; i++) {
      const w = curve.getPoint(i / n), [x, y] = this.asm.view.toScreen(w), d = Math.hypot(x - e.clientX, y - e.clientY);
      if (d < px && (!best || d < best.d)) best = { d, w };
    }
    if (!best) return null;
    let leg = 0, ld = Infinity; // (the leg of the clicked points it is nearest)
    const ln = new THREE.Line3(), q = new THREE.Vector3();
    for (let k = 0; k + 1 < ok.length; k++) {
      ln.set(ok[k], ok[k + 1]);
      const dd = ln.closestPointToPoint(best.w, true, q).distanceTo(best.w);
      if (dd < ld) { ld = dd; leg = k; }
    }
    return { leg: pts.indexOf(ok[leg]), w: best.w };
  }

  /** A press on a point of the harness being edited (or chosen): it is dragged — on a face it lies on, in space it
   *  moves in the plane facing the camera. Before the view turns (capture). */
  down(e) {
    const a = this.asm, h = this.get(this.edit || this.sel);
    if (e.button !== 0 || !h || !a.active || e.target !== a.view.renderer.domElement || a.measuring || a.painting || a.mode !== 'idle') return;
    const i = this.pointNear(h, e);
    if (i < 0) return;
    e.stopPropagation(); // (no view turning, no part dragged)
    this.pt = i;
    const start = { x: e.clientX, y: e.clientY }, cv = a.view.renderer.domElement;
    let moved = false;
    const was = JSON.stringify(h.points[i]);
    const move = (ev) => {
      if (!moved && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 4) return;
      moved = true;
      cv.style.cursor = 'grabbing';
      const c = this.candidate(ev, pointAt(a, h, h.points[i]));
      if (c) { h.points[i] = c.p; this.drawNow(); }
    };
    const up = () => {
      window.removeEventListener('pointermove', move, true);
      window.removeEventListener('pointerup', up, true);
      cv.style.cursor = '';
      if (moved && JSON.stringify(h.points[i]) !== was) a.commit();
      else { a.render(); a.draw(); } // (a click on a point: it is chosen — Delete removes it)
    };
    window.addEventListener('pointermove', move, true);
    window.addEventListener('pointerup', up, true);
  }

  /** The mouse over the view while clicking points: the next point and the route to it shown (live length). */
  hoverAt(e) {
    const a = this.asm;
    if (!this.edit || a.measuring || a.painting || a.mode !== 'idle' || a.bolt) return false;
    const h = this.get(this.edit), v = this.asm.view, cv = v.renderer.domElement;
    if (!h) return false;
    v.clearHoverMarks();
    if (this.pointNear(h, e) >= 0) { this.hover = null; cv.style.cursor = 'grab'; this.drawNow(); return true; }
    if (this.cableNear(h, e)) { this.hover = null; cv.style.cursor = 'copy'; this.drawNow(); return true; }
    const last = h.points.length ? pointAt(this.asm, h, h.points[h.points.length - 1]) : null;
    this.hover = this.candidate(e, last);
    cv.style.cursor = 'crosshair';
    v.setSnapMark(this.hover?.what === 'centre' || this.hover?.what === 'axis' ? { snap: 'centre', point: this.hover.w } : null);
    this.drawNow();
    return true;
  }

  /** A click: while editing — a point (chosen), the cable (a point added there), else a new last point; with no tool
   *  on — a harness clicked is chosen. -> handled? */
  click(e) {
    const a = this.asm;
    if (this.edit && (a.measuring || a.painting || a.mode !== 'idle' || a.bolt)) this.finish(false); // (another tool started meanwhile: it takes the click)
    if (this.edit) {
      const h = this.get(this.edit);
      if (!h) { this.edit = null; return false; }
      const i = this.pointNear(h, e);
      if (i >= 0) { this.pt = i; a.render(); a.draw(); return true; }
      const on = this.cableNear(h, e);
      if (on) {
        const p0 = h.points[on.leg], p1 = h.points[on.leg + 1], M = p0?.inst && p0.inst === p1?.inst ? matrixOf(a, p0.inst) : null; // (between two points of one part: on it too)
        this.pt = on.leg + 1;
        this.editPts(h, (P) => P.splice(on.leg + 1, 0, M ? { inst: p0.inst, at: on.w.clone().applyMatrix4(M.clone().invert()).toArray().map((x) => +x.toFixed(4)) } : { xyz: on.w.toArray().map((x) => +x.toFixed(3)) }));
        return true;
      }
      if (e.altKey) { // (Alt + click: the face behind; again at the same spot: the next one behind, in place of it)
        const again = this.altAt && Math.hypot(e.clientX - this.altAt.x, e.clientY - this.altAt.y) < 4 && this.altAt.n === h.points.length;
        if (again) h.points.pop();
        this.altDepth = again ? this.altDepth + 1 : 1;
      } else this.altDepth = 0;
      const last = h.points.length ? pointAt(a, h, h.points[h.points.length - 1]) : null, c = this.candidate(e, last);
      if (!c) return true;
      if (e.altKey && c.depth < this.altDepth) this.altDepth = 0; // (past the last face: round to the front again)
      h.points.push(c.p);
      this.altAt = e.altKey ? { x: e.clientX, y: e.clientY, n: h.points.length } : null;
      this.pt = null;
      this.hover = null;
      a.commit();
      return true;
    }
    if (a.measuring || a.painting || a.mode !== 'idle' || a.bolt) return false;
    const hit = this.pick(e);
    if (!hit) { if (this.sel) { this.sel = null; this.pt = null; this.span = null; } return false; }
    const near = hit === this.sel ? this.cableNear(this.get(hit), e, 14) : null; // (the chosen one clicked again: the span there)
    this.span = near ? near.leg : null;
    this.spanEdit = null;
    this.sel = hit;
    this.pt = null;
    a.sel = null;
    a.sel2 = null;
    a.facePicks = [];
    a.snapPick = null;
    a.view.setMeasure([]);
    a.render();
    a.draw();
    return true;
  }

  /** The harness under the mouse (in front of the parts) -> its id or null. */
  pick(e) {
    const v = this.asm.view, ray = v.ray(e.clientX, e.clientY), objs = [];
    for (const [, b] of this.built) objs.push(...b.objs.filter((o) => o.isMesh && o.userData.harness));
    const hh = ray.intersectObjects(objs, false)[0];
    if (!hh) return null;
    const part = ray.intersectObjects(v.meshes || [], false)[0];
    return !part || hh.distance <= part.distance + 1e-6 ? hh.object.userData.harness : null;
  }

  /** Keys: Esc / Enter — done; Delete — the chosen point (or the chosen harness). -> handled? */
  key(e) {
    if (this.edit) {
      if (e.key === 'Escape' || e.key === 'Enter') { e.preventDefault(); this.finish(); return true; }
      if ((e.key === 'Delete' || e.key === 'Backspace') && this.pt !== null) {
        const h = this.get(this.edit), i = this.pt;
        this.pt = null;
        this.editPts(h, (P) => P.splice(i, 1));
        return true;
      }
      return e.key === 'Delete';
    }
    if (!this.sel) return false;
    if (e.key === 'Escape' && this.clips.box) { this.clips.close(); return true; } // (📎 the pick list first)
    if (e.key === 'Escape') { this.sel = null; this.pt = null; this.asm.render(); this.asm.draw(); return true; }
    if (e.key === 'Delete') {
      const h = this.get(this.sel);
      if (this.pt !== null && h?.points.length > 2) { const i = this.pt; this.pt = null; this.editPts(h, (P) => P.splice(i, 1)); } else this.remove(this.sel);
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------- drawing
  /** Each harness drawn (made again only when its points or settings changed); the one chosen lit, its points shown
   *  while chosen or edited, a quiet ⚠ note on a corner with no room for the radius, the next point's preview while
   *  clicking. */
  draw() {
    const v = this.asm.view;
    if (!v) return;
    if (!this.group) { this.group = new THREE.Group(); v.scene.add(this.group); }
    const seen = new Set();
    for (const h of this.list()) {
      seen.add(h.id);
      this.adopt(h);
      const pts = (h.points || []).map((p) => pointAt(this.asm, h, p));
      const extra = this.hoverWorld(h);
      const key = JSON.stringify([h.kind, h.d, h.color, h.wires, h.pitch, h.r_min, h.length_locked, [...pts, ...extra].map((p) => p && p.toArray().map((x) => x.toFixed(3))), this.sel === h.id, this.edit === h.id, this.pt, this.hl, this.litSpan(h), JSON.stringify(this.throughAt?.get(h.id) || []), AVOID.get(h)?.key || '', (h.points || []).map((p, i) => +connOf(h, i)).join(''), JSON.stringify((h.spans || []).filter((s) => s.chain).map((s) => chainRoute(this.asm, s.chain)?.moving.o || null)), this.asm.view.clip?.length || 0]);
      const was = this.built.get(h.id);
      if (was?.key === key) continue;
      if (was) for (const o of was.objs) { this.group.remove(o); o.geometry?.dispose(); if (o.isCSS2DObject) o.element.remove(); }
      this.built.set(h.id, { key, objs: this.make(h, pts, extra) });
    }
    for (const [id, b] of this.built) {
      if (seen.has(id)) continue;
      for (const o of b.objs) { this.group.remove(o); o.geometry?.dispose(); if (o.isCSS2DObject) o.element.remove(); }
      this.built.delete(id);
    }
    v.invalidate();
    clearTimeout(this.clashTimer);
    this.clashTimer = setTimeout(() => { this.avoidAll(); this.checkThrough(); }, 400);
  }

  /** ➰ The span lit in the view (its row under the mouse, its length being typed, or the span chosen) or null. */
  litSpan(h) {
    if (this.sel !== h.id && this.edit !== h.id) return null;
    const k = this.spanHl ?? this.spanEdit ?? this.span;
    return k !== null && k !== undefined && k + 1 < (h.points || []).length ? k : null;
  }

  drawNow() { this.draw(); const el = this.asm.$('.hn-len'); if (el) el.textContent = this.lengthText(this.get(this.edit || this.sel)); }

  /** The tubes, marks and labels of one harness. */
  make(h, pts, extra) {
    const v = this.asm.view, objs = [], on = this.sel === h.id || this.edit === h.id, clip = v.clip || [];
    const all = [...pts.filter(Boolean), ...extra], r = routeAt(this.asm, h, extra), D = outerD(h);
    const add = (o) => { o.userData.harness = h.id; this.group.add(o); objs.push(o); return o; };
    const taut = r.taut.length ? r.taut[0] : null; // (🔒 too short for its ends: straight, drawn red)
    if (taut && !this.taut.has(h.id) && !extra.length) this.asm.hooks.toast(`🔌 ${nameOf(h)}: ${tautText(taut)}`, 'warning', 4000); // (a limit, as a collision: said once)
    if (taut) this.taut.add(h.id); else this.taut.delete(h.id);
    const mat = (hex, extraOpts = {}) => new THREE.MeshStandardMaterial({ color: taut ? 0xd0312d : hex, roughness: 0.5, metalness: 0.05, emissive: taut ? 0x3a0808 : on ? 0x0e2a4a : 0x000000, clippingPlanes: clip, ...extraOpts });
    if (r.segs.length && r.length > 1e-6) {
      const curve = new RouteCurve(r.segs, r.length), n = Math.min(1200, Math.max(24, Math.ceil(r.length / Math.max(0.6, D / 2))));
      if (h.kind === 'wires') {
        const fr = curve.computeFrenetFrames(n, false), wd = wireD(h), lay = Math.max(20 * D, 30); // (one turn of the twist every lay mm)
        wireLayout((h.wires || []).length, wd).forEach(([x, y], k) => {
          const rho = Math.hypot(x, y), phi = Math.atan2(y, x), line = [];
          for (let i = 0; i <= n; i++) {
            const a = phi + (2 * Math.PI * (i / n) * r.length) / lay;
            line.push(curve.getPoint(i / n).addScaledVector(fr.normals[i], rho * Math.cos(a)).addScaledVector(fr.binormals[i], rho * Math.sin(a)));
          }
          add(new THREE.Mesh(new THREE.TubeGeometry(rho ? new PolyCurve(line) : curve, n, (+(h.wires[k]?.d) || wd) / 2, 8, false), mat(colourOf(h.wires[k]?.color)[1])));
        });
      } else if (h.kind === 'ribbon') {
        // flat at its start: its width level (across the route and the up axis), as the kernel's (harness.py)
        const w = D, th = +h.d || 1, fr = curve.computeFrenetFrames(n, false), t0 = curve.getTangent(0);
        let x0 = t0.clone().cross(new THREE.Vector3(0, 0, 1));
        if (x0.length() < 1e-6) x0 = t0.clone().cross(new THREE.Vector3(1, 0, 0));
        x0.normalize();
        const a = Math.atan2(x0.dot(fr.binormals[0]), x0.dot(fr.normals[0])), c = Math.cos(a), s = Math.sin(a);
        const at = (u, v) => new THREE.Vector2(u * c - v * s, u * s + v * c); // (x along the frame's normal, y its binormal)
        add(new THREE.Mesh(new THREE.ExtrudeGeometry(new THREE.Shape([at(-w / 2, -th / 2), at(w / 2, -th / 2), at(w / 2, th / 2), at(-w / 2, th / 2)]), { steps: n, extrudePath: curve, bevelEnabled: false }), mat(0xa9adb3)));
        const edge = [], e = at(-(w / 2 - (+h.pitch || 1.27) / 2), th * 0.3); // (the first wire marked red, as on a real one)
        for (let i = 0; i <= n; i++) edge.push(curve.getPoint(i / n).addScaledVector(fr.normals[i], e.x).addScaledVector(fr.binormals[i], e.y));
        add(new THREE.Mesh(new THREE.TubeGeometry(new PolyCurve(edge), n, Math.min(th, +h.pitch || 1.27) * 0.32, 6, false), mat(0xd0312d)));
      } else {
        const sleeve = h.kind === 'sleeve', segs = sleeve ? Math.min(2400, Math.ceil(r.length / (D / 12))) : n, rad = sleeve ? 16 : 14;
        const geo = new THREE.TubeGeometry(curve, segs, D / 2, rad, false);
        if (sleeve) { // corrugated: its radius in and out every D/3
          const pos = geo.attributes.position, c = new THREE.Vector3(), q = new THREE.Vector3();
          for (let i = 0; i <= segs; i++) {
            curve.getPoint(i / segs, c);
            const k = 1 + 0.09 * Math.cos((2 * Math.PI * (i / segs) * r.length) / (D / 3));
            for (let j = 0; j <= rad; j++) { const ix = i * (rad + 1) + j; q.fromBufferAttribute(pos, ix).sub(c).multiplyScalar(k).add(c); pos.setXYZ(ix, q.x, q.y, q.z); }
          }
          geo.computeVertexNormals();
        }
        add(new THREE.Mesh(geo, mat(colourOf(sleeve ? 'black' : h.color)[1], extra.length ? { transparent: true, opacity: 0.85 } : {})));
      }
      const lit = this.litSpan(h);
      if (lit !== null && !extra.length && r.spans?.[lit] > 0) { // ➰ that span lit (a brighter, thicker tube over it), the rest of the cable dimmed
        for (const o of objs) if (o.material) Object.assign(o.material, { transparent: true, opacity: 0.35, depthWrite: false });
        const s0 = r.spans.slice(0, lit).reduce((a, b) => a + b, 0), s1 = s0 + r.spans[lit], m = Math.max(8, Math.min(240, Math.ceil(r.spans[lit] / 2)));
        const seg = Array.from({ length: m + 1 }, (_, k) => curve.getPoint((s0 + ((s1 - s0) * k) / m) / r.length));
        const o = add(new THREE.Mesh(new THREE.TubeGeometry(new PolyCurve(seg), m, D * 0.65, 12, false), new THREE.MeshStandardMaterial({ color: 0x58a6ff, emissive: 0x1d4f8f, roughness: 0.4, transparent: true, opacity: 0.9, clippingPlanes: clip })));
        o.userData.litSpan = lit;
      }
      const label = (cls, text, at) => { // (a label just above its spot: CSS2D places the outer box, the inner one is lifted)
        const el = document.createElement('div'), sp = document.createElement('span');
        el.style.pointerEvents = 'none';
        sp.className = cls;
        sp.textContent = text;
        el.appendChild(sp);
        const o = new CSS2DObject(el);
        o.position.copy(at);
        return add(o);
      };
      const real = all.length - extra.length;
      r.bends.forEach((b, k) => { // (none while the corner hangs on the point under the mouse: it is not clicked yet)
        if (b.ok || (extra.length && b.at >= real - 1)) return;
        const g = r.segs.find((x) => x.bend === k); // (on its arc's middle; a sharp turn back: at its point)
        label('hn-warn', `⚠ ${t2('R {r} mm — no room for {min}', { r: num(b.r), min: num(rMinOf(h)) })}`, g ? new RouteCurve([g], g.len).getPoint(0.5) : b.p);
      });
      if (taut) label('hn-warn hn-taut', `⚠ ${tautText(taut)}`, curve.getPoint(0.5));
      if (!extra.length) for (const x of r.short) label('hn-note', t2('too close — the cable needs a straight lead-out of {x} mm', { x: num(Math.round(x.need)) }), x.p); // (quiet: where the next point is)
      const marks = [...(this.throughAt?.get(h.id) || []).map((c) => ({ at: c.at, name: c.name })), ...r.clashes.filter((c, i, all) => all.findIndex((x) => x.inst === c.inst) === i && !(this.throughAt?.get(h.id) || []).some((x) => x.inst === c.inst)).map((c) => ({ at: c.at, name: `${this.asm.partName(this.asm.inst(c.inst)?.part)} ${c.inst}` }))];
      for (const c of marks) label('hn-clash', `⚠ ${t2('the cable hits {part}', { part: c.name })}`, V(c.at)); // (where it could not get clear of a part)
      const own = extra.length ? routeAt(this.asm, h).length : r.length; // (its own length: not to the point under the mouse)
      if (on) label('hn-tag', `🔌 ${lockedOf(h) ? '🔒 ' : ''}${mmText(own)} mm`, curve.getPoint(taut ? 0.3 : 0.5)); // its length at its middle
    }
    if (on) { // its points: drag them; the chosen one yellow
      const P = pts.map((p, i) => [p, i]).filter(([p]) => p);
      const dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(P.map(([p]) => p)), new THREE.PointsMaterial({ color: 0x7ee787, size: 11, sizeAttenuation: false, depthTest: false }));
      dots.renderOrder = 15;
      add(dots);
      const ch = P.find(([, i]) => i === this.pt) || P.find(([, i]) => i === this.hl);
      if (ch) {
        const o = new THREE.Points(new THREE.BufferGeometry().setFromPoints([ch[0]]), new THREE.PointsMaterial({ color: 0xf2cc60, size: 16, sizeAttenuation: false, depthTest: false }));
        o.renderOrder = 16;
        add(o);
      }
      if (extra.length) {
        const o = new THREE.Points(new THREE.BufferGeometry().setFromPoints(extra), new THREE.PointsMaterial({ color: 0x58a6ff, size: 9, sizeAttenuation: false, depthTest: false }));
        o.renderOrder = 15;
        add(o);
      }
    }
    return objs;
  }

  /** The detours round the parts for every harness whose points changed (a moment after a change, not while
   *  dragging): avoidRoute, kept in AVOID for these points; drawn again when they changed. */
  avoidAll() {
    const v = this.asm.view, meshes = (v?.meshes || []).filter((m) => m.visible !== false);
    let changed = false;
    for (const h of this.list()) changed = this.avoidOne(h, meshes) || changed;
    if (changed) { this.draw(); if ((this.sel || this.edit) && !this.sliding) this.asm.renderProps(); }
  }

  /** The detours of one harness worked out for its points now (kept: unchanged) -> worked out again? */
  avoidOne(h, meshes = (this.asm.view?.meshes || []).filter((m) => m.visible !== false)) {
    const { ok, n0, n1, chains } = inputsAt(this.asm, h);
    if (ok.length < 2) return false;
    const key = keyOf(h, ok, n0, n1, chains);
    if (AVOID.get(h)?.key === key) return false;
    const own = new Set([...(h.points || []).map((p) => p.clip).filter(Boolean), ...(h.spans || []).map((s) => chainRec(this.asm, s.chain || '')?.part).filter(Boolean)]); // (its clips and chains: it runs through them)
    AVOID.set(h, { key, ...avoidRoute(h, ok, n0, n1, meshes.filter((m) => !own.has(m.userData.inst)), chains) });
    return true;
  }

  /** ⚠ Where a harness's centre line goes through a part (a ray from the spot crosses the part's faces an odd
   *  number of times) -> this.through: id -> [part names]; checked a moment after a change. */
  checkThrough() {
    const v = this.asm.view, was = JSON.stringify([...this.through]), wasAt = JSON.stringify([...(this.throughAt || [])]);
    this.through = new Map();
    this.throughAt = new Map(); // harness id -> [{inst, name, span (1: between points 1 and 2), at}]
    for (const h of this.list()) {
      const at = this.throughOf(h);
      if (!at.length) continue;
      this.through.set(h.id, at.map((c) => c.name));
      this.throughAt.set(h.id, at);
    }
    if (JSON.stringify([...this.throughAt]) !== wasAt) this.draw(); // (its ⚠ spots)
    if (JSON.stringify([...this.through]) !== was && (this.sel || this.edit) && !this.sliding) this.asm.renderProps();
  }

  /** ⚠ Where harness h's centre line goes through a part -> [{inst, name, span (1: between points 1 and 2), at}]. */
  throughOf(h) {
    const v = this.asm.view, ray = new THREE.Raycaster(), dir = new THREE.Vector3(0.3017, 0.2081, 0.9304).normalize();
    {
      const pts = (h.points || []).map((p) => pointAt(this.asm, h, p)).filter(Boolean), r = routeAt(this.asm, h);
      if (!r.segs.length) return [];
      const curve = new RouteCurve(r.segs, r.length), n = Math.min(240, Math.max(8, Math.ceil(r.length / 3))), hit = new Map();
      const skip = excuser(h, (h.points || []).map((p) => pointAt(this.asm, h, p))); // (🔌 the parts it plugs into, there)
      for (let i = 1; i < n; i++) {
        const w = curve.getPoint(i / n);
        ray.set(w, dir);
        for (const m of v.meshes || []) {
          if (hit.has(m.userData.inst) || skip(m.userData.inst, w)) continue;
          if (ray.intersectObject(m, false).length % 2) hit.set(m.userData.inst, w.clone()); // (its first spot inside)
        }
      }
      if (!hit.size) return [];
      const ln = new THREE.Line3(), q = new THREE.Vector3(), legOf = (w) => { // (the span of the clicked points it is nearest)
        let leg = 0, ld = Infinity;
        for (let k = 0; k + 1 < pts.length; k++) { const dd = ln.set(pts[k], pts[k + 1]).closestPointToPoint(w, true, q).distanceTo(w); if (dd < ld) { ld = dd; leg = k; } }
        return leg;
      };
      return [...hit].map(([id, w]) => ({ inst: id, name: `${this.asm.partName(this.asm.inst(id)?.part)} ${id}`, span: legOf(w) + 1, at: w.toArray().map((x) => +x.toFixed(1)) }));
    }
  }

  // ---------------------------------------------------------------- 🪄 auto-fix
  /** The warnings of harness h as its parts stand (its detours worked out first) -> {r, taut, bends, hits (parts),
   *  short, n (all of them)}. */
  warnings(h) {
    this.avoidOne(h);
    const r = routeAt(this.asm, h), hits = new Set([...r.clashes.map((c) => c.inst), ...this.throughOf(h).map((c) => c.inst)]);
    const w = { r, taut: r.taut.length, bends: r.bends.filter((b) => !b.ok).length, hits: hits.size, hitList: [...hits], short: r.short.length };
    return { ...w, n: w.taut + w.bends + w.hits + w.short };
  }

  /** Any ⚠ on harness h now (from what was worked out last: no new work)? */
  warned(h) {
    const r = routeAt(this.asm, h);
    return !!(r.taut.length || r.bends.some((b) => !b.ok) || r.clashes.length || r.short.length || this.through.get(h.id)?.length);
  }

  /** 🪄 Fix harness h by itself: tries, in turn, what clears warnings without moving its locked or connection points —
   *  a taut cable: its locked length / the span's own length longer by what it is short + 5 mm; a bend too tight: a
   *  free point dropped or moved apart; through a part: a free point moved off it or a point put in round it; a point
   *  too close to an end: moved out — keeping each change that leaves fewer warnings. One undo step -> {before, after,
   *  left: {taut, bends, hits, short}}. */
  autoFix(id) {
    const h = this.get(id);
    if (!h) return null;
    const a = this.asm, w0 = this.warnings(h);
    let cur = w0;
    if (!w0.n) return { before: 0, after: 0, left: w0 };
    const margin = 5;
    const snap = () => structuredClone({ points: h.points, spans: h.spans, length_locked: h.length_locked });
    const put = (x) => { for (const k of ['points', 'spans', 'length_locked']) { if (x[k] === undefined) delete h[k]; else h[k] = structuredClone(x[k]); } };
    const free = (i) => { const p = h.points[i]; return !!p && !p.inst && !p.clip && !connOf(h, i); }; // (in space: not 🔒 on a part, not a clip's, not 🔌)
    const world = () => h.points.map((p) => pointAt(a, h, p));
    const move = (i, w) => { const before = h.points.slice(); h.points[i] = { xyz: w.toArray().map((x) => +x.toFixed(3)), ...(h.points[i].conn !== undefined ? { conn: h.points[i].conn } : {}) }; keepSpans(h, before); };
    const drop = (i) => { const before = h.points.slice(); h.points.splice(i, 1); keepSpans(h, before); };
    const insert = (i, w) => { const before = h.points.slice(); h.points.splice(i, 0, { xyz: w.toArray().map((x) => +x.toFixed(3)) }); keepSpans(h, before); };
    const lengthen = (r) => { // (taut: its locked length / its span's own length longer by what it is short + a margin)
      let any = false;
      for (const x of r.taut) {
        if (x.span === null || x.span === undefined) { if (lockedOf(h)) { h.length_locked = +(lockedOf(h) + x.short + margin).toFixed(1); any = true; } } else if (spansOf(h)[x.span]) { spanSet(h, x.span, { length: +(spansOf(h)[x.span] + x.short + margin).toFixed(1) }); any = true; }
      }
      return any;
    };
    const best = (tries0) => { // (each change weighed — a cable it pulls taut lengthened as well —, the best kept if it leaves fewer warnings)
      const keep = snap(), taut0 = cur.taut;
      const tries = tries0.map((fn) => () => { fn(); const w = this.warnings(h); if (w.taut > taut0) lengthen(w.r); });
      let win = null;
      for (const fn of tries) {
        try { fn(); } catch { put(keep); continue; }
        const w = this.warnings(h);
        if (w.n < (win?.w.n ?? cur.n)) win = { fn, w };
        put(keep);
      }
      if (!win) { this.warnings(h); return false; }
      win.fn();
      cur = this.warnings(h);
      return true;
    };
    const D = outerD(h), R = rMinOf(h);
    for (let round = 0; round < 8 && cur.n; round++) {
      const P = world(), cats = [[], [], [], []]; // (taut, bends, through a part, lead-outs: the first kind whose change helps)
      let tries = cats[0];
      for (const x of cur.r.taut) { // taut: longer by what it is short (+ a margin), or not locked any more
        if (x.span === null || x.span === undefined) { if (lockedOf(h)) { tries.push(() => { h.length_locked = +(lockedOf(h) + x.short + margin).toFixed(1); }); tries.push(() => { delete h.length_locked; }); } } else {
          const k = x.span, L = spansOf(h)[k];
          if (L) { tries.push(() => spanSet(h, k, { length: +(L + x.short + margin).toFixed(1) })); tries.push(() => spanSet(h, k, { length: null })); }
        }
      }
      tries = cats[1];
      for (const b of cur.r.bends.filter((x) => !x.ok)) { // a bend too tight: a free point dropped, or it / its neighbours moved apart
        const k = b.at;
        if (free(k) && h.points.length > 2 && k > 0 && k < h.points.length - 1) tries.push(() => drop(k));
        for (const j of [k - 1, k, k + 1]) {
          if (!free(j) || !P[j]) continue;
          const mid = (P[j - 1] && P[j + 1] ? P[j - 1].clone().add(P[j + 1]).multiplyScalar(0.5) : null);
          for (const f of [1.5, 2.5]) if (mid && mid.distanceTo(P[j]) > 1e-6) tries.push(() => move(j, mid.clone().lerp(P[j], f)));
          for (const nb of [j - 1, j + 1]) if (P[nb] && P[nb].distanceTo(P[j]) > 1e-6) tries.push(() => move(j, P[j].clone().add(P[j].clone().sub(P[nb]).setLength(2 * R))));
        }
      }
      tries = cats[2];
      if (cur.hits) { // through a part: a free point moved off it to a side of its box, or a point put in round it
        const meshes = (a.view?.meshes || []).filter((m) => cur.hitList.includes(m.userData.inst));
        const spots = [...(this.throughOf(h) || []).map((c) => ({ inst: c.inst, at: V(c.at), span: c.span - 1 })), ...cur.r.clashes.map((c) => ({ inst: c.inst, at: V(c.at), span: null }))];
        const sides = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]].map(V);
        const outOf = (box, w, d) => { const q = w.clone(), k = d.x ? 'x' : d.y ? 'y' : 'z'; q[k] = (d[k] > 0 ? box.max[k] : box.min[k]) + d[k] * (D / 2 + CLEAR + 2); return q; };
        for (const m of meshes) {
          const box = new THREE.Box3().setFromObject(m);
          P.forEach((w, i) => { if (w && free(i) && box.clone().expandByScalar(D).containsPoint(w)) for (const d of sides) tries.push(() => move(i, outOf(box, w, d))); });
          for (const c of spots.filter((x) => x.inst === m.userData.inst).slice(0, 3)) {
            let k = c.span;
            if (k === null) { let bd = Infinity; const ln = new THREE.Line3(), q = new THREE.Vector3(); for (let j = 0; j + 1 < P.length; j++) if (P[j] && P[j + 1]) { const dd = ln.set(P[j], P[j + 1]).closestPointToPoint(c.at, true, q).distanceTo(c.at); if (dd < bd) { bd = dd; k = j; } } }
            if (k !== null && k >= 0) for (const d of sides) tries.push(() => insert(k + 1, outOf(box, c.at, d)));
          }
        }
      }
      tries = cats[3];
      if (cur.short) { // a point too close to an end on a face: moved out along that face's normal
        const need = leadOf(h), ends = [[0, 1], [h.points.length - 1, h.points.length - 2]];
        for (const [e, j] of ends) {
          const n = normalAt(a, h.points[e]);
          if (!n || !free(j) || !P[e] || !P[j]) continue;
          tries.push(() => move(j, P[j].clone().addScaledVector(n, need + D)));
          tries.push(() => move(j, P[e].clone().addScaledVector(n, need + D)));
        }
      }
      if (!cats.some((x) => x.length && best(x))) break;
    }
    const fixed = w0.n - cur.n;
    if (fixed > 0) { a.commit(); this.draw(); } else put(snap());
    return { before: w0.n, after: cur.n, left: { taut: cur.taut, bends: cur.bends, hits: cur.hits, short: cur.short } };
  }

  /** 🪄 Run it and say how it went: "Fixed 3 of 4 — left: 1 × through a part". */
  autoFixSay(id) {
    const x = this.autoFix(id);
    if (!x) return null;
    const left = [['taut', 'taut'], ['bends', 'too tight a bend'], ['hits', 'through a part'], ['short', 'too close to an end']].filter(([k]) => x.left[k]).map(([k, w]) => `${x.left[k]} × ${t(w)}`).join(', ');
    const text = !x.before ? t('Nothing to fix') : `🪄 ${t2('Fixed {a} of {b}', { a: x.before - x.after, b: x.before })}${left ? ` — ${t('left')}: ${left}` : ''}`;
    this.asm.hooks.toast(text, x.after ? 'warning' : 'ok', 6000);
    return { ...x, text };
  }

  lengthText(h) {
    if (!h) return '';
    const pts = (h.points || []).map((p) => pointAt(this.asm, h, p)).filter(Boolean), extra = this.hoverWorld(h);
    const own = t2('Length {l} mm', { l: mmText(routeAt(this.asm, h).length) });
    return extra.length ? `${own} · ${t2('with the next point {l} mm', { l: mmText(routeAt(this.asm, h, extra).length) })}` : own;
  }

  /** The next point under the mouse while clicking a harness's points (lying on its face) -> [Vector3] or []. */
  hoverWorld(h) {
    return this.edit === h.id && this.hover ? [pointAt(this.asm, h, this.hover.p) || this.hover.w] : [];
  }

  // ---------------------------------------------------------------- the panel, the tree, the suggestions
  /** The right panel of the harness being edited or chosen -> drawn? */
  panel(box) {
    const id = this.edit || this.sel, h = this.get(id);
    if (!h) { this.sel = null; this.edit = null; return false; }
    const r = routeAt(this.asm, h), bad = r.bends.filter((b) => !b.ok);
    const field = (k, label, value, unit, title, extra = '') => `<div class="field" title="${esc(t(title))}"><label>${esc(t(label))}</label><input type="number" step="any" data-hn="${k}" value="${value}" ${extra}><span class="unit">${unit}</span></div>`;
    const colours = (k, c) => `<select data-hc="${k}" title="${esc(t('Its colour'))}" style="border-left: 14px solid ${hexOf(c)}">${Object.keys(COLOURS).map((x) => `<option value="${x}" ${x === c ? 'selected' : ''}>${esc(colourName(x))}</option>`).join('')}</select>`;
    const first = h.kind === 'wires' || h.kind === 'ribbon' ? field('n', 'Wires', (h.wires || []).length, '×', 'How many wires', 'min="1" max="60" step="1"')
      : field('d', 'Ø', +h.d || 6, 'mm', h.kind === 'sleeve' ? 'The sleeve\'s outer Ø' : 'The cable\'s Ø', 'min="0.1"');
    const more = h.kind === 'wires' ? `${field('wd', 'Wire Ø', wireD(h), 'mm', 'Each wire\'s Ø (with its insulation)', 'min="0.1"')}<div class="hn-cols">${(h.wires || []).map((w, k) => colours(k, w.color)).join('')}</div>`
      : h.kind === 'ribbon' ? field('pitch', 'Pitch', +h.pitch || 1.27, 'mm', 'The spacing of its wires: the width = wires × pitch', 'min="0.1"')
        : h.kind === 'cable' ? `<div class="hn-cols">${colours('c', h.color || 'black')}</div>` : '';
    const thr = this.through.get(h.id) || [];
    box.innerHTML = `<h2>🔌 <span data-no-i18n>${esc(nameOf(h))}</span></h2>
      <div class="hn-kinds">${Object.entries(KINDS).map(([k, x]) => `<button class="chip ${k === h.kind ? 'on' : ''}" data-kind="${k}" title="${esc(t(x.hint))}">${x.icon} ${esc(t(x.name))}</button>`).join('')}</div>
      ${first}
      ${field('r', 'Min. bend R', rMinOf(h), 'mm', 'The smallest radius it may bend round — every corner is rounded at least this much (rule of thumb: 5 × Ø)', `min="0" placeholder="${autoRmin(h)}"`)}
      <div class="mp-facts hn-facts"><span>Ø</span><b data-no-i18n>${num(outerD(h))} mm</b><span>${esc(t('Points'))}</span><b>${(h.points || []).length}</b></div>
      <div class="hn-lenrow"><p class="mp-count hn-len">${esc(this.lengthText(h))}</p><button class="mini hn-lock ${lockedOf(h) ? 'on' : ''}" data-hx="lock" title="${esc(t(lockedOf(h) ? 'Unlock its length: it follows its points again' : 'Lock its length as it is now: when its ends move, the cable keeps it — slack sags, too far pulls it taut'))}">${lockedOf(h) ? '🔒' : '🔓'}</button></div>
      ${r.taut.map((x) => `<p class="hint hn-taut">⚠ ${esc(tautText(x))}</p>`).join('')}
      ${r.totalIgnored ? `<p class="hint">${esc(t('The spans\' own lengths win over the locked length'))}</p>` : ''}
      ${bad.map((b) => `<p class="hint hn-bad">⚠ ${esc(t2('Point {p}: no room for R {min} mm, bent R {r} mm', { p: b.at + 1, r: num(b.r), min: num(rMinOf(h)) }))}</p>`).join('')}
      ${thr.length ? `<p class="hint bad hn-thr">⚠ ${esc(t2('Goes through {parts}', { parts: (this.throughAt.get(h.id) || []).map((c) => `${c.name} (${t2('span {a}–{b}', { a: c.span, b: c.span + 1 })})`).join(', ') || thr.join(', ') }))}</p>` : ''}
      ${this.warned(h) ? `<button class="btn small hn-fix" data-hx="fix" title="${esc(t('Tries by itself what clears the warnings — a longer locked length, free points moved off the parts or apart — without moving locked or connection points; one undo step'))}">🪄 ${esc(t('Fix the cable automatically'))}</button>` : ''}
      ${this.pointsList(h)}
      <details class="hn-more" ${this.moreOpen ? 'open' : ''}><summary>${esc(t('More'))}</summary>${more}
        ${field('reserve', 'Reserve', Number.isFinite(+h.reserve) ? +h.reserve : 5, '%', 'Added to its length in the BOM (cut longer), rounded up to 10 mm', 'min="0" max="100"')}</details>
      ${this.edit ? `<p class="hint">${esc(t('Click the points it passes: a face of a part (it lies on it), a hole\'s centre (it goes through), or in space. Drag a point to move it, click the cable to add one between, Delete removes the chosen one.'))}</p>` : ''}
      <div class="mp-actions">${this.edit ? `<button class="btn small" data-hx="undoPt" ${(h.points || []).length ? '' : 'disabled'} title="${esc(t('Take the last point away'))}">↶ ${esc(t('Last point'))}</button><button class="btn small primary" data-hx="done" title="${esc(t('Keep the points (Esc, Enter)'))}">✓ ${esc(t('Done'))}</button>`
        : `<button class="btn small danger" data-hx="del" title="${esc(t('Delete the harness (Delete)'))}">✕ ${esc(t('Delete'))}</button><button class="btn small primary" data-hx="edit" title="${esc(t('Click more points, drag them, add one on the cable'))}">✎ ${esc(t('Edit points'))}</button>`}</div>`;
    for (const b of box.querySelectorAll('[data-kind]')) b.addEventListener('click', () => this.set(h.id, (x) => {
      x.kind = b.dataset.kind;
      if (x.kind === 'ribbon') { x.wires = wiresOf(Math.max(x.wires?.length || 0, 10), 1.5); x.d = 1; } else if (x.d <= 2) x.d = x.kind === 'sleeve' ? 10 : 6;
      if (x.kind === 'sleeve' && x.d < 8) x.d = 10;
    }));
    for (const inp of box.querySelectorAll('input[data-hn]')) {
      inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); });
      inp.addEventListener('change', () => {
        const raw = String(inp.value).replace(',', '.').trim(), val = parseFloat(raw), k = inp.dataset.hn;
        if (k === 'r' && raw === '') { this.set(h.id, (x) => { delete x.r_min; }); return; } // (empty: the rule of thumb)
        if (!Number.isFinite(val) || val < 0 || (val === 0 && k !== 'reserve' && k !== 'r')) { this.asm.render(); return; }
        this.set(h.id, (x) => {
          if (k === 'n') x.wires = wiresOf(val, wireD(x), x.wires);
          else if (k === 'wd') x.wires = (x.wires || []).map((w) => ({ ...w, d: val }));
          else if (k === 'r') x.r_min = val;
          else if (k === 'd') x.d = val;
          else x[k] = val;
        });
      });
    }
    for (const s of box.querySelectorAll('select[data-hc]')) s.addEventListener('change', () => this.set(h.id, (x) => { if (s.dataset.hc === 'c') x.color = s.value; else x.wires[+s.dataset.hc].color = s.value; }));
    box.querySelector('.hn-more').addEventListener('toggle', (e) => { this.moreOpen = e.target.open; });
    box.querySelector('[data-hx=done]')?.addEventListener('click', () => this.finish());
    box.querySelector('[data-hx=undoPt]')?.addEventListener('click', () => this.editPts(h, (P) => P.pop()));
    box.querySelector('[data-hx=edit]')?.addEventListener('click', () => this.editPoints(h.id));
    box.querySelector('[data-hx=lock]')?.addEventListener('click', () => this.lockLength(h.id));
    box.querySelector('[data-hx=fix]')?.addEventListener('click', () => this.autoFixSay(h.id));
    box.querySelector('[data-hx=del]')?.addEventListener('click', () => this.remove(h.id));
    this.pointsHandlers(h, box);
    return true;
  }

  /** The panel's list of its points, in order: number, the part and face it sits on (or "free point"), x / y / z (type
   *  to move it), 🔒 / 🔓 (a point of a part: moves with it, or stays in space), ↑ ↓ ✕, ＋ between two (a point in the
   *  middle), and 🗑 all points. */
  pointsList(h) {
    const P = h.points || [], n = P.length;
    const row = (p, i) => {
      const w = pointAt(this.asm, h, p), on = p.inst ? p : p.on, part = on?.inst ? `${this.asm.partName(this.asm.inst(on.inst)?.part)} ${on.inst}` : '';
      const where = p.clip ? `📎 ${part}` : part ? `${part}${on.face ? ` · ${on.face}` : on.n ? '' : ` · ${t('centre')}`}` : t('free point');
      const xyz = (w || V([0, 0, 0])).toArray().map((x, k) => `<input type="number" step="any" data-pxyz="${i}:${k}" value="${+x.toFixed(2)}" title="${'xyz'[k]} (mm)">`).join('');
      return `<div class="hn-pt ${i === this.pt ? 'on' : ''}" data-pt="${i}">
        <div class="hn-pt1"><b>${i + 1}</b><span class="hn-pw" data-no-i18n title="${esc(where)}">${esc(where)}</span>
          ${on?.inst ? `<button class="mini hn-plock ${p.inst ? 'on' : ''}" data-plock="${i}" title="${esc(t(p.inst ? 'Locked on its part: it moves with it — click: it stays in space' : 'Stays in space — click: lock it on its part, it moves with it'))}">${p.inst ? '🔒' : '🔓'}</button>` : ''}
          ${on?.inst ? `<button class="mini hn-pconn ${connOf(h, i) ? 'on' : ''}" data-pconn="${i}" title="${esc(t(connOf(h, i) ? '🔌 Connection point: the cable plugs into this part here — it may enter it (no collision, no lead-out note for it) — click: an ordinary point' : '🔌 Make it a connection point: the cable plugs into this part here (a connector, a probe\'s tail, a gland)'))}">🔌</button>` : ''}
          ${p.inst && (p.n || p.clip) ? `<button class="mini${p.clip ? ' on' : ''}" data-pclip="${i}" title="${esc(t(p.clip ? '📎 Swap the clip: pick another from the list — the point stays' : '📎 A clip here: pick one from the list (point at a row: preview) — the point then on its axis'))}">📎</button>` : ''}
          <button class="mini" data-pmove="${i}:-1" ${i ? '' : 'disabled'} title="${esc(t('Earlier'))}">↑</button><button class="mini" data-pmove="${i}:1" ${i < n - 1 ? '' : 'disabled'} title="${esc(t('Later'))}">↓</button><button class="mini danger" data-pdel="${i}" title="${esc(t('Delete the point'))}">✕</button></div>
        <div class="hn-pt2">${xyz}</div></div>`;
    };
    const r = routeAt(this.asm, h), own = spansOf(h);
    const ins = (i) => `<div class="hn-span ${i === this.span ? 'on' : ''}" data-span="${i}"><button class="hn-ins" data-pins="${i}" title="${esc(t2('A point between {a} and {b}', { a: i + 1, b: i + 2 }))}">＋</button>
      ${this.spanEdit === i ? `<input type="number" step="any" min="0" data-slen="${i}" value="${+(own[i] ?? r.spans?.[i] ?? 0).toFixed(1)}" title="${esc(t('The cable\'s length between these two points: longer than now makes a loop of slack (empty: as it is now)'))}"><span class="unit">mm</span>${this.slider(h, i, r)}${own[i] ? `<button class="mini" data-sclear="${i}" title="${esc(t('No length of its own'))}">✕</button>` : ''}`
        : `<button class="hn-slen" data-sloop="${i}" title="${esc(t('➰ A loop / slack here: type this span\'s length'))}">${own[i] ? '➰ ' : ''}${mmText(r.spans?.[i] ?? 0)} mm${own[i] ? ' 🔒' : ''}</button>`}
      ${chainOfSpan(h, i) ? `<span class="hn-chain" data-no-i18n title="${esc(t('Routed through this energy chain: it follows its moving end'))}">⛓ ${esc(chainOfSpan(h, i))}</span><button class="mini" data-snochain="${i}" title="${esc(t('Not through the chain any more'))}">✕</button>` : ''}</div>`;
    return `<details class="hn-pts" ${this.ptsOpen === false ? '' : 'open'}><summary>${esc(t('Points'))} (${n})</summary>
      ${P.map((p, i) => row(p, i) + (i < n - 1 ? ins(i) : '')).join('')}
      ${n ? `<button class="btn small danger hn-clear" data-hx="clearPts" title="${esc(t('Delete all its points and click new ones'))}">🗑 ${esc(t('Delete all points'))}</button>` : ''}</details>
      ${(this.orphans || []).filter((c) => this.asm.inst(c)).map((c) => `<p class="hint hn-orphan">📎 ${esc(t2('The clip {id} stays in the assembly', { id: `${this.asm.partName(this.asm.inst(c).part)} ${c}` }))} <button class="mini danger" data-rmclip="${c}">✕ ${esc(t('Remove it too'))}</button></p>`).join('')}`;
  }

  /** ➰ A slider for span i's length: from the tightest it can be (its shape with no slack) to 3 × the distance between
   *  its points or that + 300 mm, whichever is longer. */
  slider(h, i, r) {
    const a = pointAt(this.asm, h, h.points[i]), b = pointAt(this.asm, h, h.points[i + 1]);
    if (!a || !b) return '';
    const chord = a.distanceTo(b), lo = Math.ceil(spanTight(h, r, i) * 10) / 10, hi = Math.max(lo + 10, 3 * chord, chord + 300), v = spansOf(h)[i] ?? r.spans?.[i] ?? lo;
    return `<input type="range" class="hn-sslide" data-sslide="${i}" min="${lo.toFixed(1)}" max="${hi.toFixed(1)}" step="0.5" value="${Math.min(hi, Math.max(lo, v)).toFixed(1)}" title="${esc(t('Drag: the span\'s length, live — from the tightest it can be'))}">`;
  }

  pointsHandlers(h, box) {
    const P = () => h.points;
    for (const el of box.querySelectorAll('.hn-span')) { // (a span's row under the mouse: lit in the view)
      el.addEventListener('pointerenter', () => { this.spanHl = +el.dataset.span; this.draw(); });
      el.addEventListener('pointerleave', () => { if (this.spanHl === +el.dataset.span) { this.spanHl = null; this.draw(); } });
    }
    for (const sl of box.querySelectorAll('input[data-sslide]')) { // ➰ dragged: the length live (a frame at most), let go: one undo step
      const i = +sl.dataset.sslide, num0 = box.querySelector(`input[data-slen="${i}"]`);
      let raf = 0;
      sl.addEventListener('keydown', (ev) => ev.stopPropagation());
      sl.addEventListener('input', () => {
        this.sliding = true; // (the panel not drawn again under the mouse meanwhile)
        if (num0) num0.value = (+sl.value).toFixed(1);
        if (raf) return;
        raf = requestAnimationFrame(() => { raf = 0; spanSet(h, i, { length: +(+sl.value).toFixed(1) }); this.drawNow(); });
      });
      sl.addEventListener('change', () => { cancelAnimationFrame(raf); raf = 0; this.sliding = false; this.setSpan(h.id, i, +sl.value); });
    }
    box.querySelector('.hn-pts')?.addEventListener('toggle', (e) => { this.ptsOpen = e.target.open; });
    for (const el of box.querySelectorAll('.hn-pt')) {
      el.addEventListener('pointerenter', () => { this.hl = +el.dataset.pt; this.draw(); });
      el.addEventListener('pointerleave', () => { if (this.hl === +el.dataset.pt) { this.hl = null; this.draw(); } });
    }
    for (const b of box.querySelectorAll('[data-pconn]')) b.addEventListener('click', () => this.setConn(h, +b.dataset.pconn));
    for (const b of box.querySelectorAll('[data-pclip]')) b.addEventListener('click', () => { this.pt = +b.dataset.pclip; this.asm.render(); this.asm.draw(); this.clips.open(h, this.pt); }); // (📎 the pick list)
    for (const b of box.querySelectorAll('[data-snochain]')) b.addEventListener('click', () => this.setSpanChain(h.id, +b.dataset.snochain, null));
    for (const b of box.querySelectorAll('[data-rmclip]')) b.addEventListener('click', () => { this.orphans = (this.orphans || []).filter((c) => c !== b.dataset.rmclip); this.asm.removeInst(b.dataset.rmclip); });
    for (const b of box.querySelectorAll('[data-sloop]')) b.addEventListener('click', () => { this.span = +b.dataset.sloop; this.spanEdit = this.span; this.asm.render(); this.asm.draw(); this.asm.$('#asmRight input[data-slen]')?.focus(); });
    for (const b of box.querySelectorAll('[data-sclear]')) b.addEventListener('click', () => this.setSpan(h.id, +b.dataset.sclear, null));
    for (const inp of box.querySelectorAll('input[data-slen]')) {
      inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); if (ev.key === 'Escape') { this.spanEdit = null; this.asm.render(); } });
      inp.addEventListener('change', () => { // (empty: its length as it is now, locked)
        const i = +inp.dataset.slen, raw = String(inp.value).replace(',', '.').trim(), v = raw === '' ? routeAt(this.asm, h).spans[i] : parseFloat(raw);
        this.spanEdit = null;
        if (!(v > 0)) { this.asm.render(); return; }
        this.setSpan(h.id, i, v);
      });
    }
    for (const b of box.querySelectorAll('[data-pdel]')) b.addEventListener('click', () => { this.pt = null; this.hl = null; this.editPts(h, (Q) => Q.splice(+b.dataset.pdel, 1)); });
    for (const b of box.querySelectorAll('[data-pmove]')) b.addEventListener('click', () => {
      const [i, d] = b.dataset.pmove.split(':').map(Number), j = i + d;
      if (j < 0 || j >= P().length) return;
      this.pt = j;
      this.editPts(h, (Q) => { [Q[i], Q[j]] = [Q[j], Q[i]]; });
    });
    for (const b of box.querySelectorAll('[data-plock]')) b.addEventListener('click', () => { const i = +b.dataset.plock; this.editPts(h, (Q) => { Q[i] = lockPoint(this.asm, h, Q[i], !Q[i].inst); }); });
    for (const b of box.querySelectorAll('[data-pins]')) b.addEventListener('click', () => {
      const i = +b.dataset.pins, a = pointAt(this.asm, h, P()[i]), c = pointAt(this.asm, h, P()[i + 1]);
      if (!a || !c) return;
      const m = a.clone().lerp(c, 0.5), p0 = P()[i], p1 = P()[i + 1], same = p0.inst && p0.inst === p1.inst; // (between two points of one part: on it too)
      this.pt = i + 1;
      this.editPts(h, (Q) => Q.splice(i + 1, 0, same ? { inst: p0.inst, at: localOf(this.asm, p0.inst, m) } : { xyz: m.toArray().map((x) => +x.toFixed(3)) }));
    });
    for (const inp of box.querySelectorAll('input[data-pxyz]')) {
      inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); });
      inp.addEventListener('change', () => { // (typed: the point moves there; on a part it stays on it, at that spot)
        const [i, k] = inp.dataset.pxyz.split(':').map(Number), v = parseFloat(String(inp.value).replace(',', '.'));
        const p = P()[i], w = pointAt(this.asm, h, p);
        if (!Number.isFinite(v) || !w) { this.asm.render(); return; }
        w.setComponent(k, v);
        this.editPts(h, (Q) => {
          if (!p.inst) { Q[i] = { ...p, xyz: w.toArray().map((x) => +x.toFixed(3)) }; return; }
          Q[i] = lockPoint(this.asm, h, { xyz: w.toArray(), on: p }, true);
        });
      });
    }
    box.querySelector('[data-hx=clearPts]')?.addEventListener('click', () => {
      this.pt = null;
      this.hl = null;
      h.points = [];
      if (!this.edit) { this.edit = h.id; this.asm.hint(t('🔌 Click the points the harness passes: a face of a part, a hole\'s centre, or in space — Esc / Enter / ✓ Done keeps them.')); }
      this.asm.commit();
    });
  }

  /** Points in space of a loaded harness that lie on a part's face (Ø/2 + 0.5 off it, or on it) taken as 🔒 locked to
   *  it — once per harness, when the parts are drawn (an older file's points stuck where they were clicked). */
  adopt(h) {
    const v = this.asm.view;
    if (this.adopted.has(h) || !v?.meshes?.length || v.meshes.length < (this.asm.doc.instances || []).length) return;
    this.adopted.add(h);
    const ray = new THREE.Raycaster(), L = lift(h);
    (h.points || []).forEach((p, i) => {
      if (!p.xyz || p.on) return;
      const w = V(p.xyz);
      let best = null;
      for (const d of [[0, 0, -1], [0, 0, 1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]]) {
        ray.set(w, V(d));
        const hit = ray.intersectObjects(v.meshes, false)[0];
        if (hit && (Math.abs(hit.distance - L) < 0.75 || hit.distance < 0.75) && (!best || hit.distance < best.hit.distance)) best = { hit, d };
      }
      if (!best) return;
      const { hit, d } = best, inst = hit.object.userData.inst, M = hit.object.matrix;
      const nl = V(d).negate().applyMatrix3(new THREE.Matrix3().getNormalMatrix(M.clone().invert())).normalize();
      const on = hit.distance >= 0.75; // (lying on it: Ø/2 + 0.5 off; else right on it, a point the cable passes)
      h.points[i] = { inst, at: localOf(this.asm, inst, on ? hit.point : w), ...(on ? { n: nl.toArray().map((x) => +x.toFixed(6)) } : {}) };
    });
  }

  /** The harnesses under the parts in the assembly tree: "🔌 Harness 1 · 4 × Ø1.5 · 1 284 mm". */
  rows(list) {
    for (const h of this.list()) {
      const r = routeAt(this.asm, h), row = document.createElement('div');
      row.className = `mt-item hn-row${h.id === this.sel ? ' on' : ''}`;
      row.dataset.harness = h.id;
      row.innerHTML = `<span class="mt-icon">🔌</span><span class="mt-name" data-no-i18n></span><span class="mt-what" data-no-i18n></span>${r.taut.length ? `<span class="mt-warn" title="${esc(t2('The cable is taut — {x} mm short', { x: num(Math.round(r.taut[0].short * 10) / 10) }))}">⚠</span>` : r.bends.some((b) => !b.ok) ? `<span class="mt-warn soft" title="${esc(t('A corner has no room for the minimum bend radius'))}">⚠</span>` : ''}${lockedOf(h) ? `<span class="mt-what" title="${esc(t('Its length is locked'))}">🔒</span>` : ''}
        <span class="mt-acts"><button class="mini" data-a="edit" title="${esc(t('Edit points'))}">✎</button><button class="mini danger" data-a="del" title="${esc(t('Delete the harness (Delete)'))}">✕</button></span>`;
      row.querySelector('.mt-name').textContent = nameOf(h);
      row.querySelector('.mt-what').textContent = `${specOf(h)} · ${mmText(r.length)} mm`;
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'del') { this.remove(h.id); return; }
        if (a === 'edit') { this.editPoints(h.id); return; }
        if (this.edit && this.edit !== h.id) this.finish(false);
        this.sel = h.id;
        this.pt = null;
        this.asm.sel = null;
        this.asm.sel2 = null;
        this.asm.render();
        this.asm.draw();
      });
      list.appendChild(row);
    }
  }

  /** The Suggested table while a harness is edited or chosen -> shown? */
  suggest(vp, show) {
    const h = this.get(this.edit || this.sel);
    if (this.clips.at && (this.clips.at.h !== h?.id || this.clips.at.i !== this.pt)) this.clips.close(); // (📎 its list: for the point chosen only)
    if (!h) return false;
    if (this.edit) {
      show(vp, `🔌 ${nameOf(h)}`, [
        { icon: '✓', label: t('Done'), title: t('Keep the points (Esc, Enter)'), run: () => this.finish() },
        ...((h.points || []).length ? [{ icon: '↶', label: t('Take the last point away'), run: () => this.editPts(h, (P) => P.pop()) }] : []),
        ...(this.pt !== null ? [{ icon: '✕', label: t2('Delete point {n}', { n: this.pt + 1 }), danger: true, title: 'Delete', run: () => { const i = this.pt; this.pt = null; this.editPts(h, (P) => P.splice(i, 1)); } }] : []),
        ...this.centreItem(h),
        ...this.clipItems(h),
      ], t('Click a face, a hole\'s centre or in space: the next point'));
      return true;
    }
    const len = this.lengthText(h);
    show(vp, `🔌 ${nameOf(h)}`, [
      ...(this.span !== null && this.span + 1 < (h.points || []).length ? [{ icon: '➰', label: t('Loop / slack'), rank: -1, title: t2('Span {a}–{b}: type its length — longer makes a loop of slack that keeps the bend radius', { a: this.span + 1, b: this.span + 2 }),
        run: () => { this.spanEdit = this.span; this.asm.render(); this.asm.draw(); this.asm.$('#asmRight input[data-slen]')?.focus(); this.asm.$('#asmRight input[data-slen]')?.select(); } }] : []),
      ...(this.warned(h) ? [{ icon: '🪄', label: t('Fix the cable automatically'), rank: -0.5, title: t('Tries by itself what clears the warnings — a longer locked length, free points moved off the parts or apart — without moving locked or connection points; one undo step'), run: () => this.autoFixSay(h.id) }] : []),
      ...this.clipItems(h),
      ...this.connItems(h),
      ...this.chainItems(h),
      { icon: '✎', label: t('Edit points'), rank: 0, title: t('Click more points, drag them, add one on the cable'), run: () => this.editPoints(h.id) },
      { icon: '📏', label: len, rank: 1, title: t('Copy its length'), run: () => { navigator.clipboard?.writeText(String(Math.round(routeAt(this.asm, h).length))).catch(() => {}); this.asm.hooks.toast(len, 'info', 2500); } },
      ...Object.entries(KINDS).filter(([k]) => k !== h.kind).map(([k, x], i) => ({ icon: x.icon, label: t2('Make it: {kind}', { kind: t(x.name) }), rank: 3 + i, title: t(x.hint), run: () => this.set(h.id, (y) => { y.kind = k; if (k === 'ribbon') { y.wires = wiresOf(Math.max(y.wires?.length || 0, 10), 1.5); y.d = 1; } else if (y.d <= 2 || (k === 'sleeve' && y.d < 8)) y.d = k === 'sleeve' ? 10 : 6; }) })),
      { icon: lockedOf(h) ? '🔓' : '🔒', label: t(lockedOf(h) ? 'Unlock its length' : 'Lock its length'), rank: 1.5, title: t(lockedOf(h) ? 'Unlock its length: it follows its points again' : 'Lock its length as it is now: when its ends move, the cable keeps it — slack sags, too far pulls it taut'), run: () => this.lockLength(h.id) },
      { icon: '📋', label: t('Bill of materials'), rank: 6, title: t('Every part with its quantity, material and mass'), run: () => this.asm.openBom() },
      { icon: '✕', label: t('Delete the harness'), rank: 2, danger: true, title: 'Delete', run: () => this.remove(h.id) },
    ], t('Ø, bend radius and colours: in the panel on the right'));
    return true;
  }

  /** 📎 Clip here (the chosen point, lying on a part's face): the clips for its bundle, the snuggest first — two or
   *  three in the table, the rest under Show all —, each previewed in the view while pointed at, and ⋯ Choose from the
   *  list; a point with a clip: 📎 Swap the clip (the list). -> [suggestions]. */
  clipItems(h) {
    const i = this.pt, p = i !== null ? h.points?.[i] : null;
    if (!p?.inst || !(p.n || p.clip)) return [];
    const err = (e) => this.asm.hooks.toast(e.message, 'warning', 6000), list = () => this.clips.open(h, i);
    if (p.clip) return [{ icon: '📎', label: t('Swap the clip…'), rank: 0.45, title: t('Pick another clip from the list (point at a row: preview) — the point stays'), run: list }];
    const fit = clipsFor(outerD(h));
    return [...fit.map((c, k) => ({ icon: '📎', label: `${t('Clip here')}: ${c.label}`, rank: k < 3 ? 0.4 + k * 0.05 : 20 + k,
      title: t2('Holds Ø{a}–{b} mm — put on the face at point {n}, the cable along it; the point then on its axis', { a: num(c.dmin), b: num(c.dmax), n: i + 1 }),
      hover: (on) => (on ? this.clips.ghost(h, i, c) : this.clips.hide()), run: () => this.clipAt(h, i, c).catch(err) })),
    ...(clipChoices(outerD(h)).length ? [{ icon: '⋯', label: t('Choose from the list…'), rank: 0.56, title: t('Every clip, tie mount and tie — the ones that hold the bundle first; point at a row: preview'), run: list }] : [])];
  }

  /** 🔌 Connection point (the chosen point, on a part): on / off. -> [suggestions]. */
  connItems(h) {
    const i = this.pt, p = i !== null ? h.points?.[i] : null;
    if (!(p?.inst || p?.on?.inst)) return [];
    return [{ icon: '🔌', label: t('Connection point'), rank: 0.6, on: connOf(h, i), title: t('The cable plugs into this part here (a connector, a probe\'s tail, a gland): it may enter it — no collision, no lead-out note for it'), run: () => this.setConn(h, i) }];
  }

  /** ⛓ Route through an energy chain (the chosen span): each chain of the assembly, or one from the library sized for
   *  the bundle put in; through one already: not any more. -> [suggestions]. */
  chainItems(h) {
    const k = this.span;
    if (k === null || k + 1 >= (h.points || []).length) return [];
    const err = (e) => this.asm.hooks.toast(e.message, 'warning', 6000), now = chainOfSpan(h, k);
    if (now) return [{ icon: '⛓', label: t2('Not through chain {id} any more', { id: now }), rank: 0.5, run: () => this.setSpanChain(h.id, k, null) }];
    const fit = chainsFor(outerD(h), rMinOf(h)).slice(0, 2);
    return [...(this.asm.doc.chains || []).map((c, j) => ({ icon: '⛓', label: `${t('Route through an energy chain')}: ${c.id}`, rank: 0.45 + j * 0.01, title: t2('Span {a}–{b} along chain {id}: the cable follows its moving end', { a: k + 1, b: k + 2, id: c.id }), run: () => this.chainSpan(h, k, c.id).catch(err) })),
      ...fit.map((c, j) => ({ icon: '⛓', label: `${t('Route through an energy chain')}: ${c.label}`, rank: (this.asm.doc.chains || []).length ? 3 + j : 0.45 + j * 0.05, title: t2('Put a chain from the library in (opening {Bi} mm, bend R {R}) at the span\'s first point and route the cable through it', { Bi: num(c.Bi), R: num(c.R) }), run: () => this.chainSpan(h, k).catch(err) }))];
  }

  /** ◎ The chosen point (else the last one) to the centre of the face it sits on — a pin's top, a ring round a
   *  hole: on its axis, so the length stays as a joint turns about it; a hole's side: on its axis there. -> [] or
   *  [a suggestion]. */
  centreItem(h) {
    const i = this.pt ?? (h.points || []).length - 1, p = h.points?.[i];
    if (!p?.inst || !p.face) return [];
    const body = this.asm.bodyOf(this.asm.inst(p.inst))?.body, f = body?.faces?.find((x) => x.name === p.face);
    if (!f || !(f.type === 'plane' || (f.type === 'cylinder' && f.axis))) return [];
    let at;
    if (f.type === 'plane') at = V(f.frame?.o || f.centroid);
    else { const o = V(f.axis.o), d = V(f.axis.d).normalize(); at = o.addScaledVector(d, V(p.at).sub(V(f.axis.o)).dot(d)); }
    if (at.distanceTo(V(p.at)) < 1e-3) return [];
    return [{ icon: '◎', label: t('Point to the centre of this face / hole'), rank: 0.5, title: t('On its axis: the length stays the same as a joint turns about it'),
      run: () => this.editPts(h, (Q) => { Q[i] = { inst: p.inst, at: at.toArray().map((x) => +x.toFixed(4)), ...(f.type === 'plane' && p.n ? { n: p.n } : {}), face: p.face }; }) }];
  }

  /** 🔌 Route a cable from a picked spot -> a suggestion, or null. q: a click's candidate {p} (on a face: lying on
   *  it), or a snap point {inst, point} (a corner, a centre: right there). */
  fromHere(q, rank = 2.5) {
    let p = q?.p || null;
    if (!p && q?.inst && q.point) {
      const M = matrixOf(this.asm, q.inst);
      if (M) p = { inst: q.inst, at: q.point.clone().applyMatrix4(M.clone().invert()).toArray().map((x) => +x.toFixed(4)) };
    }
    if (!p?.inst) return null;
    return { icon: '🔌', label: t('Route a cable from here'), rank, title: t('A cable harness: its first point here, then click the next ones'), run: () => this.start(p) };
  }
}

/** Harness h's points changed from `before` (the same point objects, some put in, taken out or moved): a span keeps
 *  its length / chain while its two points are still neighbours, else it goes. */
function keepSpans(h, before) {
  if (!h.spans?.length) return;
  h.spans = h.spans.map((s) => { const i = h.points.indexOf(before[s.from]); return i >= 0 && h.points[i + 1] === before[s.from + 1] ? { ...s, from: i } : null; }).filter(Boolean);
  if (!h.spans.length) delete h.spans;
}

// ------------------------------------------------------------------ for the AI
/** add_harness / edit_harness (the assembly on screen). */
export function harnessHandlers(asm) {
  const need = () => { if (!asm.active) throw new Error('No assembly is on screen — new_assembly, or open_part an assembly.'); };
  const toPoint = (q, k) => { // {part, face} (on its face's middle, or through a hole's centre) | {part, point: [x, y, z] in the part} | {xyz} | [x, y, z]
    if (Array.isArray(q)) q = { xyz: q };
    if (q.xyz) { if (q.xyz.length !== 3) throw new Error(`points[${k}].xyz: [x, y, z] in mm.`); return { xyz: q.xyz.map(Number) }; }
    const it = asm.inst(q.part);
    if (!it) throw new Error(`points[${k}]: no placed part “${q.part}” — get_assembly lists them (I…), or give xyz.`);
    if (q.point) { if (q.point.length !== 3) throw new Error(`points[${k}].point: [x, y, z] in the part's own coordinates.`); return { inst: it.id, at: q.point.map(Number) }; }
    const inv = matrixOf(asm, it.id).clone().invert();
    if (!q.face) throw new Error(`points[${k}]: give face (its name, as find_refs names it), point ([x, y, z] in the part) or xyz.`);
    const f = asm.worldFace(it.id, q.face);
    if (f.type === 'cylinder') return { inst: it.id, at: f.centroid.clone().applyMatrix4(inv).toArray().map((x) => +x.toFixed(4)) }; // (a hole: through its centre)
    if (!f.normal) throw new Error(`points[${k}]: ${q.face} is neither flat nor round — give point or xyz.`);
    return { inst: it.id, at: (f.frame?.o ? V(f.frame.o) : f.centroid.clone().applyMatrix4(inv)).toArray().map((x) => +x.toFixed(4)), n: f.normal.clone().transformDirection(inv).toArray().map((x) => +x.toFixed(6)), face: q.face }; // (a flat face's centre: a pin's top on its axis)
  };
  const apply = (h, a) => {
    if (a.type !== undefined) { if (!KINDS[a.type]) throw new Error(`type is ${Object.keys(KINDS).join(', ')}.`); h.kind = a.type; }
    if (a.wires !== undefined) {
      if (!Array.isArray(a.wires) || !a.wires.length) throw new Error('wires: [{color, d}, …] — one per wire.');
      h.wires = a.wires.map((w, k) => ({ d: +w.d > 0 ? +w.d : +a.wire_d || 1.5, color: COLOURS[w.color] ? w.color : ORDER[k % ORDER.length] }));
      for (const w of a.wires) if (w.color && !COLOURS[w.color]) throw new Error(`colour “${w.color}”: one of ${Object.keys(COLOURS).join(', ')}.`);
    } else if (a.count !== undefined) h.wires = wiresOf(+a.count, +a.wire_d || wireD(h), h.wires);
    else if (a.wire_d !== undefined) h.wires = (h.wires || []).map((w) => ({ ...w, d: +a.wire_d }));
    if (a.d !== undefined) { if (!(+a.d > 0)) throw new Error('d: the Ø in mm (> 0).'); h.d = +a.d; }
    if (a.color !== undefined) { if (!COLOURS[a.color]) throw new Error(`color: one of ${Object.keys(COLOURS).join(', ')}.`); h.color = a.color; }
    if (a.r_min !== undefined) { if (a.r_min === null) delete h.r_min; else if (+a.r_min >= 0) h.r_min = +a.r_min; else throw new Error('r_min: mm, 0 or more (null: the rule of thumb).'); }
    if (a.pitch !== undefined) h.pitch = +a.pitch || 1.27;
    if (a.reserve !== undefined) h.reserve = Math.max(0, +a.reserve || 0);
    if (a.length !== undefined) { if (a.length === null || a.length === false) delete h.length_locked; else if (+a.length > 0) h.length_locked = +a.length; else throw new Error('length: the cable\'s locked length in mm (> 0; null: not locked).'); }
    if (a.length_locked !== undefined && a.length === undefined) {
      if (!a.length_locked) delete h.length_locked;
      else if (!lockedOf(h)) h.length_locked = +routeAt(asm, h).length.toFixed(1);
    }
    if (a.name !== undefined) { if (String(a.name).trim()) h.name = String(a.name).trim(); else delete h.name; }
    if (a.points !== undefined) h.points = a.points.map(toPoint);
    if (a.add_points !== undefined) h.points.push(...a.add_points.map((q, k) => toPoint(q, h.points.length + k)));
    // one point by its number: put somewhere else / taken out / put in after one / all in another order (as the panel's
    // points list: x y z typed, ✕, ＋ between, ↑ ↓) — the spans' own lengths keep to their points
    const at = (k, key, n = h.points.length) => { const i = Math.round(+k) - 1; if (!(i >= 0 && i < n)) throw new Error(`${key}: point ${k} — it has ${n} (1 … ${n}).`); return i; };
    for (const q of [].concat(a.set_points || [])) { const i = at(q?.n, 'set_points'); h.points[i] = toPoint(q, i); }
    const before = h.points.slice();
    if (a.remove_points !== undefined) {
      const gone = new Set([].concat(a.remove_points).map((k) => at(k, 'remove_points')));
      h.points = h.points.filter((_, i) => !gone.has(i));
    }
    if (a.insert_points !== undefined) {
      const { after, points } = a.insert_points || {};
      if (!Array.isArray(points) || !points.length) throw new Error('insert_points: {after: a point number (0 = before the first), points: [{part, face} | {part, point} | {xyz}, …]}.');
      const i = after === 0 ? 0 : at(after, 'insert_points.after') + 1;
      h.points.splice(i, 0, ...points.map((q, k) => toPoint(q, i + k)));
    }
    if (a.order !== undefined) {
      const o = [].concat(a.order).map((k) => at(k, 'order'));
      if (o.length !== h.points.length || new Set(o).size !== o.length) throw new Error(`order: every point number once, in the new order (1 … ${h.points.length}).`);
      const P = h.points.slice();
      h.points = o.map((i) => P[i]);
    }
    if (a.remove_points !== undefined || a.insert_points !== undefined || a.order !== undefined) keepSpans(h, before);
    for (const s of a.spans || []) { // ➰ {from: point number (1 = the first), length: mm | null}
      const i = +s.from - 1;
      if (!(i >= 0 && i + 1 < h.points.length)) throw new Error(`spans: from ${s.from} — a span runs from a point to the next: 1 … ${h.points.length - 1}.`);
      const L = s.length === undefined ? routeAt(asm, h).spans[i] : s.length;
      if (L !== null && !(+L > 0)) throw new Error('spans: length in mm (> 0; null: none of its own).');
      spanSet(h, i, { length: L === null ? null : +(+L).toFixed(1) });
    }
    for (const [key, on] of [['connect_points', true], ['disconnect_points', false]]) { // 🔌 connection points
      for (const k of a[key] || []) {
        if (!h.points[+k - 1]) throw new Error(`${key}: point ${k} — it has ${h.points.length} (1 … ${h.points.length}).`);
        h.points[+k - 1] = { ...h.points[+k - 1], conn: on };
      }
    }
    for (const [key, lock] of [['lock_points', true], ['unlock_points', false]]) {
      for (const k of a[key] || []) {
        const p = h.points[+k - 1];
        if (!p) throw new Error(`${key}: point ${k} — it has ${h.points.length} (1 … ${h.points.length}).`);
        if (!(p.inst || p.on?.inst)) throw new Error(`${key}: point ${k} is in space, on no part — nothing to lock it to.`);
        h.points[+k - 1] = lockPoint(asm, h, p, lock);
      }
    }
    if (h.kind === 'ribbon' && !(+h.d > 0 && +h.d < 3)) h.d = 1;
  };
  const answer = (h) => {
    asm.harnessTool.checkThrough();
    const f = harnessFacts(asm, h);
    return { text: `${f.id} ${f.type}, Ø${f.d_mm} mm, ${f.length_mm} mm long through ${f.points} points${f.bends_too_tight ? ` — ⚠ bends tighter than R ${f.r_min_mm}: ${f.bends_too_tight.map((b) => `point ${b.point} R ${b.r_mm}`).join(', ')} (spread the points out or lower r_min)` : ''}${f.through_parts ? ` — ⚠ goes through ${f.through_parts.join(', ')}` : ''}${f.taut ? ` — ⚠ 🔒 taut${f.taut.span ? ` (span ${f.taut.span})` : ''}: ${f.taut.short_mm} mm short` : ''}. ${JSON.stringify(f)}` };
  };
  return {
    add_harness: async (a = {}) => {
      need();
      await asm.refresh();
      if (!Array.isArray(a.points) || a.points.length < 2) throw new Error('points: at least two — [{part, face} | {part, point} | {xyz}, …].');
      const h = { id: '', kind: 'wires', d: 6, color: 'black', wires: wiresOf(a.type === 'ribbon' ? 10 : 4, 1.5), pitch: 1.27, reserve: 5, points: [] };
      apply(h, a);
      h.id = `H${Math.max(0, ...asm.harnessTool.list().map((x) => parseInt(String(x.id).replace(/\D/g, ''), 10) || 0)) + 1}`;
      if (asm.harnessTool.edit) asm.harnessTool.finish(false);
      (asm.doc.harnesses ||= []).push(h);
      asm.harnessTool.sel = h.id;
      asm.sel = null;
      asm.commit();
      return answer(h);
    },
    edit_harness: async (a = {}) => {
      need();
      const h = asm.harnessTool.get(a.id) || asm.harnessTool.list().find((x) => nameOf(x) === a.id);
      if (!h) throw new Error(`No harness “${a.id}” — get_assembly lists them (\`harnesses\`, ids H…).`);
      if (a.remove) { asm.harnessTool.remove(h.id); return { text: `${h.id} removed.` }; }
      const keep = structuredClone(h);
      try { apply(h, a); } catch (e) { Object.assign(h, keep); throw e; }
      if ((h.points || []).length < 2) { Object.assign(h, keep); throw new Error('A harness keeps at least two points.'); }
      asm.harnessTool.sel = h.id;
      asm.commit();
      if (a.clip) { // 📎 {point: number, item?, size?}: a clip there (the snuggest for its bundle)
        const i = +a.clip.point - 1, c = a.clip.item ? (a.clip.size ? clipChoices(outerD(h)).filter((x) => x.fits) : clipsFor(outerD(h))).find((x) => x.item.id === a.clip.item && (!a.clip.size || x.size === a.clip.size)) : null;
        if (a.clip.item && !c) throw new Error(`clip: “${a.clip.item}” does not hold a bundle of Ø${num(outerD(h))} mm — clipsFor lists: ${clipsFor(outerD(h)).map((x) => `${x.item.id} ${x.size}`).join(', ')}.`);
        await asm.harnessTool.clipAt(h, i, c);
      }
      if (a.auto_fix) { const x = asm.harnessTool.autoFixSay(h.id); const ans = answer(h); return { text: `🪄 ${x.text}. ${ans.text}` }; } // 🪄
      if (a.chain) await asm.harnessTool.chainSpan(h, +a.chain.span - 1, a.chain.id === undefined ? undefined : a.chain.id); // ⛓ {span: number, id: C… | null}
      return answer(h);
    },
  };
}
