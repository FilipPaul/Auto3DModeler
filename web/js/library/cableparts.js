// 📎 Cable clips and ⛓ energy chains from the parts library (library/cableparts.json): the clips that hold a bundle of
// a given Ø, a clip put on a point of a part (its mounting face on that face, the cable along the cable's way), and an
// energy chain (igus e-chain) laid out as a U — its centre line, its fixed and moving ends — for the assembly
// (assembly/chains.js draws it) and the cable harness (a cable routed through the chain follows that path).
// auto3d/cableparts.py has the same math (the tests).
//
// A clip item carries, in its own coordinates (numbers or formulas of the size's values; `dc`: the cable's Ø):
//   "cable": {"axis": {"o", "d", "d2" (a second way: a 4-way tie mount)}, "dmin", "dmax", "tie": true (tied down)}
//   "mount": {"kind": "screw" | "adhesive" | "tie", "o", "n" (out of the part into the face it is fixed on), "screw":
//             "M4", "hole": Ø, "seat": z (the screw head's), "holes": [[x, y]…]}
// A chain item: "chain": {"pitch", "Bi", "Ba", "hi", "ha", "R", "dmax"}; a link spans x 0…pitch on the centre line.
//
// The API (for the harness: 📎 Clip here on a point, ⛓ Route through an energy chain on a span):
//   useLibrary({items, addPart})                      the library's items and how a part gets into the project (app.js)
//   clipsFor(d, items?) -> [{item, size, dmin, dmax, kind, mount, label}]     the clips for a bundle Ø d, snug first
//   placeClip(asm, choice, point, normal, cableDir, {d}) -> {inst, part, size, axis: {o, d} (world)}
//   chainPath(chain, moving) -> {points, segs, length, lower, upper, travel, ok, fixed, moving, links, pointAt(s)}
//   chainOf(item, size, R, links) -> the chain's numbers; travelRange(chain) -> {min, max}
import * as THREE from 'three';
import { evaluate, varsOf, sizesOf, lengthsOf, buildPart } from './build.js';

const CLIP_KINDS = ['clip', 'tie mount'];
let lib = { items: [], addPart: null };

/** The library's items (the app's cache) and its hook to put a library part into the project: addPart(name, data) ->
 *  the part's id (the same choice again: the part that is there). */
export function useLibrary({ items, addPart } = {}) {
  if (items) lib.items = items;
  if (addPart) lib.addPart = addPart;
}

const num = (v, vars) => (typeof v === 'number' ? v : evaluate(v, vars));
/** A mount's word (a screw size): a value's name gives that value, else the word itself. */
const word = (v, vars) => (typeof v === 'string' && v in vars ? vars[v] : v);

// ------------------------------------------------------------------ clips
/** {dmin, dmax} of the cable a clip of this size holds: its own, or (a P-clamp gives only its largest Ø) from the
 *  next smaller size's largest — below it the smaller size holds it. */
export function cableRange(item, sizeKey) {
  const keys = sizesOf(item).map((s) => s.key), cab = item.cable || {}, k = keys.indexOf(sizeKey);
  const dmax = num(cab.dmax, varsOf(item, sizeKey));
  if (cab.dmin !== undefined) return { dmin: num(cab.dmin, varsOf(item, sizeKey)), dmax };
  return { dmin: k > 0 ? num(cab.dmax, varsOf(item, keys[k - 1])) : 0, dmax };
}

/** A clip's frames for a size, in its own coordinates: {axis: {o, d, d2?}, mount: {kind, o, n, screw, hole, seat?,
 *  holes?}, dmin, dmax}; dc: the cable's Ø (a tie mount: the cable lies on top) — not said: the largest it holds. */
export function clipFrames(item, sizeKey, dc) {
  const { dmin, dmax } = cableRange(item, sizeKey), vars = { ...varsOf(item, sizeKey), dc: dc ?? dmax };
  const cab = item.cable || {}, mo = item.mount || {}, vec = (a) => a.map((x) => num(x, vars));
  const out = { dmin, dmax, mount: { kind: mo.kind || 'screw' } };
  if (cab.axis) out.axis = Object.fromEntries(['o', 'd', 'd2'].filter((k) => cab.axis[k]).map((k) => [k, vec(cab.axis[k])]));
  for (const k of ['o', 'n']) if (mo[k]) out.mount[k] = vec(mo[k]);
  if (mo.screw) out.mount.screw = word(mo.screw, vars);
  for (const k of ['hole', 'seat']) if (mo[k] !== undefined) out.mount[k] = num(mo[k], vars);
  if (mo.holes) out.mount.holes = mo.holes.map(vec);
  return out;
}

/** The clips that hold a bundle of Ø d: per clip item its smallest size that holds it -> [{item, size, dmin, dmax,
 *  kind, mount (its kind), label}], the snug ones first (a P-clamp of that Ø before a tie mount that takes 1.5–35). */
export function clipsFor(d, items = lib.items) {
  const out = [];
  if (!(d > 0)) return out;
  for (const it of items || []) {
    if (!CLIP_KINDS.includes(it.kind) || !it.cable) continue;
    for (const s of sizesOf(it)) {
      const r = cableRange(it, s.key);
      if (d < r.dmin - 1e-9 || d > r.dmax + 1e-9) continue;
      out.push({ item: it, size: s.key, ...r, kind: it.kind, mount: it.mount?.kind || 'screw', label: buildPart(it, s.key).name });
      break; // (the sizes in order: the smallest that holds it)
    }
  }
  return out.sort((a, b) => (a.dmax - a.dmin) - (b.dmax - b.dmin) || (a.dmax - d) - (b.dmax - d));
}

/** Where a clip goes (its own frames -> the world): its mount point on `point`, its mount normal into the face
 *  (against the face's outward `normal`), its cable axis along `cableDir` (laid onto the face) -> THREE.Matrix4. */
export function clipMatrix(frames, point, normal, cableDir) {
  const V = (a) => (a?.isVector3 ? a.clone() : new THREE.Vector3(...a));
  const mn = V(frames.mount.n).normalize(), md = V(frames.axis?.d || [0, 1, 0]).normalize();
  const wn = V(normal).normalize().negate();
  let wd = V(cableDir || [1, 0, 0]);
  wd.sub(wn.clone().multiplyScalar(wd.dot(wn))); // (along the face)
  if (wd.lengthSq() < 1e-12) wd = Math.abs(wn.x) < 0.9 ? new THREE.Vector3(1, 0, 0).cross(wn) : new THREE.Vector3(0, 1, 0).cross(wn);
  wd.normalize();
  const P = new THREE.Matrix4().makeBasis(mn, md, mn.clone().cross(md)), W = new THREE.Matrix4().makeBasis(wn, wd, wn.clone().cross(wd));
  const R = W.multiply(P.transpose()); // (the part's mount normal -> the world's, its cable way -> the cable's)
  const o = V(frames.mount.o || [0, 0, 0]).applyMatrix4(R);
  return R.setPosition(V(point).sub(o));
}

/** 📎 A clip put on a part: its mounting face on `point` (a face with the outward `normal`), the cable along
 *  `cableDir`. choice: {item, size} (from clipsFor) or an item (its size chosen by opts.d, the bundle Ø).
 *  -> {inst, part, size, axis: {o, d} (where the cable runs through it, in the world)}. */
export async function placeClip(asm, choice, point, normal, cableDir, opts = {}) {
  const item = choice.item || choice, size = choice.size || clipsFor(opts.d, [item])[0]?.size || sizesOf(item)[0]?.key;
  if (!lib.addPart) throw new Error('The library is not ready (useLibrary).');
  const frames = clipFrames(item, size, opts.d), M = clipMatrix(frames, point, normal, cableDir);
  const built = buildPart(item, size), pid = lib.addPart(built.name, built.data);
  const before = new Set(asm.doc.instances.map((i) => i.id));
  await asm.insert(pid);
  const it = asm.doc.instances.find((i) => !before.has(i.id));
  if (!it) throw new Error('It could not be put in.');
  it.matrix = M.toArray();
  if (asm.doc.instances.length > 1) delete it.fixed; // (held where it is put; the first part of all stays fixed)
  asm.applyMates?.();
  asm.commit();
  const axis = frames.axis ? { o: new THREE.Vector3(...frames.axis.o).applyMatrix4(M).toArray(), d: new THREE.Vector3(...frames.axis.d).transformDirection(M).toArray() } : null;
  return { inst: it.id, part: pid, size, axis };
}

// ------------------------------------------------------------------ energy chains
/** A chain item's choice -> its numbers {series, pn, pitch, Bi, Ba, hi, ha, R, dmax, links}. */
export function chainOf(item, sizeKey = sizesOf(item)[0]?.key, R, links) {
  const ls = lengthsOf(item, sizeKey), vars = varsOf(item, sizeKey, R ?? ls?.values[0]), c = { series: item.series || '', item: item.id, size: sizeKey };
  for (const k of ['pitch', 'Bi', 'Ba', 'hi', 'ha', 'R', 'dmax']) c[k] = num(item.chain[k], vars);
  c.pn = buildPart(item, sizeKey, c.R).data.library.pn;
  c.links = links || defaultLinks(c);
  return c;
}

/** Links for a travel (the fixed end in the middle of it): half the travel + the bend + two links, whole links. */
export const defaultLinks = (c, travel = 500) => Math.ceil((travel / 2 + Math.PI * c.R + 2 * c.pitch) / c.pitch);

/** How far the moving end may go from above the fixed end, either way: ±(L − πR) -> {min, max}. */
export function travelRange(c) {
  const m = c.links * c.pitch - Math.PI * c.R;
  return m > 0 ? { min: -m, max: m } : { min: 0, max: 0 };
}

/** ⛓ A chain laid out as a U — its own frame: the fixed end at the origin, the lower run along +x, the bend above it,
 *  the moving end on the upper run (2R up). moving: the travel (mm along x from above the fixed end), or a point
 *  (world, with chain.matrix; it is taken along x). -> {length (always links × pitch), lower, upper (the runs), travel
 *  (clamped to the range), ok (in range), segs [{t: 'line', a, b} | {t: 'arc', c, r, from, to, axis}], points (a
 *  polyline, the bend every 5°), pointAt(s) -> {p, d}, links [{a, b}] (each link's two pins), fixed / moving {o, d
 *  (along the path), n (out of the chain at its bracket)}} — in the world when chain.matrix (array of 16) is given. */
export function chainPath(c, moving = 0) {
  const M = c.matrix ? new THREE.Matrix4().fromArray(c.matrix) : null, R = c.R, L = c.links * c.pitch;
  let travel = moving;
  if (typeof moving !== 'number') { // a point: how far along x it is
    const p = moving?.isVector3 ? moving.clone() : new THREE.Vector3(...moving);
    if (M) p.applyMatrix4(M.clone().invert());
    travel = p.x;
  }
  const r = travelRange(c), m = Math.min(Math.max(travel, r.min), r.max);
  const a = (L - Math.PI * R + m) / 2, u = a - m;
  const local = (s) => { // the point and direction s along the centre line
    if (s <= a) return { p: new THREE.Vector3(s, 0, 0), d: new THREE.Vector3(1, 0, 0) };
    if (s <= a + Math.PI * R) { const t = (s - a) / R; return { p: new THREE.Vector3(a + R * Math.sin(t), 0, R - R * Math.cos(t)), d: new THREE.Vector3(Math.cos(t), 0, Math.sin(t)) }; }
    return { p: new THREE.Vector3(a - (s - a - Math.PI * R), 0, 2 * R), d: new THREE.Vector3(-1, 0, 0) };
  };
  const W = (v) => (M ? v.clone().applyMatrix4(M) : v.clone()), Wd = (v) => (M ? v.clone().transformDirection(M) : v.clone());
  const pointAt = (s) => { const q = local(Math.min(Math.max(s, 0), L)); return { p: W(q.p), d: Wd(q.d) }; };
  const n = 36, pts = [new THREE.Vector3(0, 0, 0), ...Array.from({ length: n + 1 }, (_, i) => new THREE.Vector3(a + R * Math.sin((Math.PI * i) / n), 0, R - R * Math.cos((Math.PI * i) / n))), new THREE.Vector3(m, 0, 2 * R)];
  const end = (o, d, nn) => ({ o: W(o).toArray(), d: Wd(d).toArray(), n: Wd(nn).toArray() });
  return {
    length: a + Math.PI * R + u, lower: a, upper: u, travel: m, ok: travel >= r.min - 1e-9 && travel <= r.max + 1e-9,
    segs: [{ t: 'line', a: W(new THREE.Vector3(0, 0, 0)).toArray(), b: W(new THREE.Vector3(a, 0, 0)).toArray() },
      { t: 'arc', c: W(new THREE.Vector3(a, 0, R)).toArray(), r: R, from: W(new THREE.Vector3(a, 0, 0)).toArray(), to: W(new THREE.Vector3(a, 0, 2 * R)).toArray(), axis: Wd(new THREE.Vector3(0, -1, 0)).toArray() },
      { t: 'line', a: W(new THREE.Vector3(a, 0, 2 * R)).toArray(), b: W(new THREE.Vector3(m, 0, 2 * R)).toArray() }],
    points: pts.map((p) => W(p).toArray()),
    pointAt,
    links: Array.from({ length: c.links }, (_, i) => ({ a: pointAt(i * c.pitch).p.toArray(), b: pointAt((i + 1) * c.pitch).p.toArray() })),
    fixed: end(new THREE.Vector3(0, 0, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, -1)),
    moving: end(new THREE.Vector3(m, 0, 2 * R), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1)),
  };
}

/** How many links a placed part counts in the parts list: a chain's link instance (assembly/chains.js) is the whole
 *  chain — doc: the assembly's data, it: the instance. */
export function linksOf(doc, it) {
  const ch = (doc?.chains || []).find((c) => c.part === it.id);
  return ch ? Math.max(1, ch.links | 0) : 1;
}
