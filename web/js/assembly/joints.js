// Assembly joints: how a placed part is held against another one. Plain geometry (three.js maths), no UI.
//   touch    — a flat face on a flat face, facing each other (gap: mm apart; the first joint also centres them)
//   flush    — two flat faces in one plane, facing the same way (gap: offset along the normal)
//   axis     — concentric: a round face on a round face, on one axis (a pin in a hole); it can still slide along it
//   axis_distance — two round faces with their axes parallel, `dist` mm apart (two probes side by side); it turns about
//              its own axis and slides along it; its swing round the other axis is kept (`angle`, from the other part's
//              x direction) unless freed. A round face and a flat face: the axis parallel to the face, `dist` mm from it
//              on the `side` it stood (+1: the way the face looks)
//   parallel — two flat faces parallel (turns only)
//   perp     — two flat faces at right angles (turns only)
//   angle    — two flat faces at an angle (`value` degrees between their directions; turns only)
//   tangent  — a round face touching a flat face (the cylinder's side on the plane)
//   ball     — a ball's centre (a spherical face's) on another part's axis (a hole, a cone: it slides along it) or on
//              another ball's centre (a ball joint: it only turns, three ways)
//   seat     — a ball sitting in a seat: in a cone, or on the edge of a hole smaller than it — on the axis, touching it
//   rigid    — 🔗 fixed together: the part goes with the other one as they were when joined (its `rot` and `pos`; the
//              faces only anchor it: each part's biggest one)
// Any joint may also hold motions its type leaves free, where they were when locked (lockMotion): `slides` — a move
// along a direction of the other part kept at a distance, `rot` — the part's turn against the other part kept (a ball's
// three turns at once); with `pos` too that is a 🔗 rigid joint: the part fixed to the other one as they were.
// A part's joints are applied in order: the first one places it freely; the later ones only turn it about the
// direction fixed before (about the axis itself, when an axis fixed it: the pin stays in its hole), and only move it
// along their own direction — so "pin in hole" + "touch" = the pin in the hole, down to the face. A flat face put onto another one is centred on it once (when the joint is made); then
// it may slide on it. jointMiss tells how far a joint is from holding (another joint of the part may hold it elsewhere).
// A part joined onto two parts that move closes a loop (a rod on a crank and on a slider): loops.js places those parts
// together, bringing their joints' jointResidual to 0.
import * as THREE from 'three';

export const JOINT_TYPES = {
  touch: { icon: '⧉', name: 'Touch', faces: 'plane', hint: 'a flat face onto a flat face (facing each other)' },
  gap: { icon: '↔', name: 'Gap', faces: 'plane', hint: 'a flat face facing another one, a distance apart' },
  flush: { icon: '▭', name: 'Flush', faces: 'plane', hint: 'two flat faces in one plane, facing the same way' },
  axis: { icon: '◎', name: 'Concentric', faces: 'cylinder', hint: 'two round faces on one axis (a pin in a hole, a shaft in a bearing)' },
  axis_distance: { icon: '↔', name: 'Axis distance', faces: 'axisd', hint: 'two round faces with their axes parallel, a distance apart (two probes side by side) — or an axis along a flat face. The same height: add ▭ Flush on their ends' },
  parallel: { icon: '∥', name: 'Parallel', faces: 'plane', hint: 'two flat faces parallel (it only turns)' },
  perp: { icon: '⟂', name: 'Perpendicular', faces: 'plane', hint: 'two flat faces at right angles (it only turns)' },
  angle: { icon: '∠', name: 'Angle', faces: 'plane', hint: 'two flat faces at an angle you set (it only turns)' },
  tangent: { icon: '⌒', name: 'Tangent', faces: 'mixed', hint: 'a round face touching a flat face (a roller on a plate)' },
  ball: { icon: '●', name: 'Ball joint', faces: 'ball', hint: "a ball's centre on an axis (a hole, a cone: it slides along it and turns any way) or on another ball's centre (it only turns)" },
  seat: { icon: '◉', name: 'Ball in seat', faces: 'ball', hint: 'a ball sitting in a conical seat or on the edge of a hole — on its axis, touching it' },
  rigid: { icon: '🔗', name: 'Fixed together', faces: 'part', hint: 'the first part goes with the other one as they are now — it has no motion of its own' },
  // not a joint that holds: a spring part reaching to another part's face, drawn as long as it is (springs.js)
  spring: { icon: '〰', name: 'Spring', faces: 'plane', hint: "a spring's end face to the face it pushes on: it is drawn as long as the distance (compressed, stretched)" },
  // not a joint of its own: a screw (+ nut / insert) or pin through the parts — the holes drilled for it, or ones there
  fastener: { icon: '🔩', name: 'Screw / pin', faces: 'any', hint: 'click where it goes in: a flat face (the holes are drilled for it, through the parts below) or a hole that is there', pick: true },
};

const V = (a) => (a instanceof THREE.Vector3 ? a.clone() : new THREE.Vector3(...a));

/** Turn `from` onto `to`; with a direction already fixed (`fixed.dir`) only about that direction — or, when that
 *  direction came from an axis (a pin in a hole: either way round is fine), also flipped over end to end. */
function turnFor(from, to, fixed) {
  const q = new THREE.Quaternion();
  if (!fixed) return q.setFromUnitVectors(from.clone().normalize(), to.clone().normalize());
  const a = fixed.dir.clone().normalize(), p = from.clone().projectOnPlane(a), r = to.clone().projectOnPlane(a);
  if (p.length() < 1e-9 || r.length() < 1e-9) {
    if (fixed.flippable && from.dot(to) < 0) { // along the axis, but the wrong way: over end to end
      const side = Math.abs(a.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
      return q.setFromAxisAngle(side.projectOnPlane(a).normalize(), Math.PI);
    }
    return q; // already along the fixed direction: nothing to turn
  }
  p.normalize();
  r.normalize();
  const ang = Math.atan2(new THREE.Vector3().crossVectors(p, r).dot(a), p.dot(r));
  return q.setFromAxisAngle(a, ang);
}

/** Turn direction `from` (about `fixed.dir`, else about the axis across both) so it makes `deg` degrees with `to`
 *  — the smallest turn that does it. */
function turnToAngle(from, to, deg, fixed) {
  const q = new THREE.Quaternion(), f = from.clone().normalize(), t = to.clone().normalize();
  let a = fixed ? fixed.dir.clone() : new THREE.Vector3().crossVectors(f, t);
  if (a.length() < 1e-9) a = Math.abs(t.x) < 0.9 ? new THREE.Vector3(1, 0, 0).cross(t) : new THREE.Vector3(0, 1, 0).cross(t);
  a.normalize();
  // f turned by φ about a: p·cosφ + (a×p)·sinφ + a(a·f), p = f across a
  const p = f.clone().addScaledVector(a, -a.dot(f)), ap = new THREE.Vector3().crossVectors(a, p);
  const A = p.dot(t), B = ap.dot(t), C = a.dot(f) * a.dot(t), R = Math.hypot(A, B);
  if (R < 1e-9) return q;
  const x = Math.max(-1, Math.min(1, (Math.cos((deg * Math.PI) / 180) - C) / R)), base = Math.atan2(B, A), w = Math.acos(x);
  const wrap = (v) => Math.atan2(Math.sin(v), Math.cos(v));
  const phi = [wrap(base + w), wrap(base - w)].sort((u, v) => Math.abs(u) - Math.abs(v))[0];
  return q.setFromAxisAngle(a, phi);
}

function turnAbout(M, centre, q) {
  return new THREE.Matrix4().makeTranslation(centre.x, centre.y, centre.z).multiply(new THREE.Matrix4().makeRotationFromQuaternion(q))
    .multiply(new THREE.Matrix4().makeTranslation(-centre.x, -centre.y, -centre.z)).multiply(M);
}

const shift = (M, d) => new THREE.Matrix4().makeTranslation(d.x, d.y, d.z).multiply(M);

/** The point a later joint turns the part about: on the axis an earlier joint put it on (a pin in a hole: turned about
 *  that axis it stays in the hole), else `p` (its own face's). */
const pivotOf = (fixed, first, p) => (!first && fixed?.o ? V(fixed.o) : p);

/** How far (degrees) the moving part is turned about a joint's direction, from the other part: the angle between
 *  their own x directions (or y, when x runs along it) seen along `dir`. */
export function spinOf(fB, fA, dir) {
  const d = V(dir).normalize(), a = across(fA, d), b = across(fB, d);
  return (Math.atan2(new THREE.Vector3().crossVectors(a, b).dot(d), a.dot(b)) * 180) / Math.PI;
}

/** A part's own x direction (or y, when x runs along d) across the direction d, from a face of it (world). */
function across(f, d) {
  const x = V(f.xdir).projectOnPlane(d);
  return x.length() > 1e-6 ? x.normalize() : V(f.ydir).projectOnPlane(d).normalize();
}

/** ↔ Two round faces: the shortest way from fA's axis to fB's, across fA's axis (world). */
const axisOffset = (fB, fA) => V(fB.axis.o).sub(V(fA.axis.o)).projectOnPlane(V(fA.axis.d).normalize());

/** ↔ Where fB's axis stands round fA's: degrees about fA's axis from the other part's x direction (what an axis
 *  distance's 🔒 keeps); 0 when the axes are one. */
export function orbitOf(fB, fA) {
  const dA = V(fA.axis.d).normalize(), p = axisOffset(fB, fA), a = across(fA, dA);
  if (p.length() < 1e-9) return 0;
  p.normalize();
  return (Math.atan2(new THREE.Vector3().crossVectors(a, p).dot(dA), a.dot(p)) * 180) / Math.PI;
}

/** ↔ The direction across fA's axis `deg` round it (orbitOf's way). */
function orbitDir(fA, deg) {
  const dA = V(fA.axis.d).normalize();
  return across(fA, dA).applyAxisAngle(dA, (deg * Math.PI) / 180);
}

/** ↔ The distance an axis distance joint measures now, its faces as placed: between the two axes, or (a round face and
 *  a flat one) of the axis from the face, signed (+: the way the face looks) -> mm, or null when the faces do not fit. */
export function axisDistanceNow(fB, fA) {
  if (fA.axis && fB.axis) return axisOffset(fB, fA).length();
  const cyl = fB.axis ? fB : fA, pl = cyl === fB ? fA : fB;
  if (!cyl.axis || !pl.normal) return null;
  return V(cyl.axis.o).sub(V(pl.centroid)).dot(V(pl.normal).normalize());
}

/** ↔ How far an axis distance joint is from holding -> {deg (the axes askew / the axis off the face's plane), mm (off
 *  the distance; with the swing 🔒, off where it is kept), res (jointResidual's numbers)}, or null. */
function axisDistanceMiss(j, fB, fA, S) {
  const d = Math.max(0, +j.dist || 0), ang = (a, b) => (V(a).normalize().angleTo(V(b).normalize()) * 180) / Math.PI;
  if (fA.axis && fB.axis) {
    const dA = V(fA.axis.d).normalize(), p = axisOffset(fB, fA), a = ang(fB.axis.d, dA), x = new THREE.Vector3().crossVectors(V(fB.axis.d).normalize(), dA);
    const res = [x.x * S, x.y * S, x.z * S]; // (askew; either way along is fine)
    let mm;
    if (Number.isFinite(j.angle)) { // its swing kept: the axis right there
      const e = p.clone().sub(orbitDir(fA, j.angle).multiplyScalar(d));
      mm = e.length();
      res.push(e.x, e.y, e.z);
    } else {
      mm = Math.abs(p.length() - d);
      res.push(p.length() - d);
    }
    return { deg: Math.min(a, 180 - a), mm, res };
  }
  const cyl = fB.axis ? fB : fA, pl = cyl === fB ? fA : fB;
  if (!cyl.axis || !pl.normal) return null;
  const n = V(pl.normal).normalize(), off = axisDistanceNow(fB, fA) - (j.side || 1) * d;
  return { deg: Math.abs(90 - ang(cyl.axis.d, n)), mm: Math.abs(off), res: [off, V(cyl.axis.d).normalize().dot(n) * S] };
}

/** Turn M about the line (point, dir) so that the spin is `deg`. */
function spinTo(M, faceAt, fA, point, dir, deg) {
  const now = spinOf(faceAt(M), fA, dir);
  return turnAbout(M, V(point), new THREE.Quaternion().setFromAxisAngle(V(dir).normalize(), ((deg - now) * Math.PI) / 180));
}

/** Two round faces on one axis: where each reaches along the other one's axis (fA's: from its origin, along its
 *  direction) -> {a: [lo, hi], b: [lo, hi]}, or null when a face's length is not known (its `span`). */
export function axialEnds(fB, fA) {
  if (!fA.span || !fB.span) return null;
  const oA = V(fA.axis.o), dA = V(fA.axis.d).normalize(), oB = V(fB.axis.o), dB = V(fB.axis.d).normalize();
  const t = (s) => oB.clone().addScaledVector(dB, s).sub(oA).dot(dA);
  const b = [t(fB.span[0]), t(fB.span[1])].sort((p, q) => p - q);
  return { a: [...fA.span].sort((p, q) => p - q), b };
}

/** The distance along the axis between two concentric round faces now: {dist, side} (side +1: B beyond A's far end). */
export function axialGap(fB, fA) {
  const e = axialEnds(fB, fA);
  if (!e) return null;
  const dz = V(fA.axis.d).normalize().z, overlap = e.b[0] < e.a[1] - 1e-6 && e.b[1] > e.a[0] + 1e-6;
  // one inside the other (e.g. both still on the bed): the moving part goes on top (up the axis, else its + way)
  const side = overlap ? (dz < -1e-9 ? -1 : 1) : e.b[0] + e.b[1] >= e.a[0] + e.a[1] ? 1 : -1;
  return { side, dist: side > 0 ? e.b[0] - e.a[1] : e.a[0] - e.b[1] };
}

/** How far a joint is from holding, its faces as they are placed (fB: the moving part's, fA: the other one's)
 *  -> {mm, deg, ok} (ok: it holds), or null when the faces are not of its kind. */
export function jointMiss(j, fB, fA) {
  const type = j.type || 'touch', ang = (a, b) => (V(a).normalize().angleTo(V(b).normalize()) * 180) / Math.PI;
  const wrap = (d) => Math.abs(((((d + 180) % 360) + 360) % 360) - 180);
  let mm = 0, deg = 0, dir = null;
  if (type === 'rigid') {
    // (only its locks)
  } else if (type === 'ball' || type === 'seat') {
    const v = ballShift(type, fB, fA);
    if (!v) return null;
    mm = v.length();
  } else if (type === 'axis') {
    if (!fA.axis || !fB.axis) return null;
    const dA = V(fA.axis.d).normalize(), a = ang(fB.axis.d, dA);
    deg = Math.min(a, 180 - a);
    mm = V(fB.axis.o).sub(V(fA.axis.o)).projectOnPlane(dA).length();
    const e = Number.isFinite(j.dist) ? axialEnds(fB, fA) : null;
    if (e) {
      const side = j.side || (e.b[0] + e.b[1] >= e.a[0] + e.a[1] ? 1 : -1), now = side > 0 ? e.b[0] - e.a[1] : e.a[0] - e.b[1];
      mm = Math.max(mm, Math.abs(now - j.dist));
    }
    dir = dA;
  } else if (type === 'axis_distance') {
    const r = axisDistanceMiss(j, fB, fA, 1);
    if (!r) return null;
    ({ mm, deg } = r);
  } else if (type === 'tangent') {
    const cyl = fB.type === 'cylinder' ? fB : fA, pl = cyl === fB ? fA : fB;
    if (!cyl.axis || !pl.normal || !cyl.radius) return null;
    const n = V(pl.normal).normalize();
    deg = Math.abs(90 - ang(cyl.axis.d, n));
    mm = Math.abs(Math.abs(V(cyl.axis.o).sub(V(pl.centroid)).dot(n)) - cyl.radius);
  } else {
    if (!fA.normal || !fB.normal) return null;
    const nA = V(fA.normal).normalize(), a = ang(fB.normal, nA);
    if (type === 'perp') deg = Math.abs(a - 90);
    else if (type === 'angle') deg = Math.abs(a - (j.flip ? 180 - (+j.value || 0) : +j.value || 0));
    else if (type === 'touch' || type === 'gap') deg = 180 - a;
    else deg = j.flip ? 180 - a : a; // flush, parallel
    if (type === 'touch' || type === 'gap' || type === 'flush') mm = Math.abs(V(fB.centroid).sub(V(fA.centroid)).dot(nA) - (+j.gap || 0));
    dir = nA;
  }
  if (Number.isFinite(j.angle) && dir && deg < 0.1) deg = Math.max(deg, wrap(spinOf(fB, fA, dir) - j.angle)); // its turn locked
  const [lm, ld] = lockMiss(j, fB, fA);
  mm = Math.max(mm, lm);
  deg = Math.max(deg, ld);
  return { mm, deg, ok: mm < 0.05 && deg < 0.1 };
}

/** How far a joint is from holding, as numbers that are all 0 when it holds and change smoothly as the parts move
 *  (mm; a direction's miss times S mm) — what the closed-loop solve (loops.js) brings to 0 for several joints at
 *  once. The same faces as jointMiss; [] when the faces are not of its kind. */
export function jointResidual(j, fB, fA, S = 50) {
  const type = j.type || 'touch', out = [], vec = (v, k = 1) => out.push(v.x * k, v.y * k, v.z * k);
  const cross = (a, b) => new THREE.Vector3().crossVectors(V(a).normalize(), V(b).normalize());
  let dir = null;
  if (type === 'rigid') {
    // (only its locks)
  } else if (type === 'ball' || type === 'seat') {
    const v = ballShift(type, fB, fA);
    if (!v) return out;
    vec(v);
  } else if (type === 'axis') {
    if (!fA.axis || !fB.axis) return out;
    const dA = V(fA.axis.d).normalize();
    vec(V(fB.axis.o).sub(V(fA.axis.o)).projectOnPlane(dA)); // the axes apart
    vec(cross(fB.axis.d, dA), S); // … and askew (either way along is fine)
    const e = Number.isFinite(j.dist) ? axialEnds(fB, fA) : null;
    if (e) { const side = j.side || (e.b[0] + e.b[1] >= e.a[0] + e.a[1] ? 1 : -1); out.push((side > 0 ? e.b[0] - e.a[1] : e.a[0] - e.b[1]) - j.dist); }
    dir = dA;
  } else if (type === 'axis_distance') {
    out.push(...(axisDistanceMiss(j, fB, fA, S)?.res || []));
  } else if (type === 'tangent') {
    const cyl = fB.type === 'cylinder' ? fB : fA, pl = cyl === fB ? fA : fB;
    if (!cyl.axis || !pl.normal || !cyl.radius) return out;
    const n = V(pl.normal).normalize();
    out.push(Math.abs(V(cyl.axis.o).sub(V(pl.centroid)).dot(n)) - cyl.radius, V(cyl.axis.d).normalize().dot(n) * S);
  } else {
    if (!fA.normal || !fB.normal) return out;
    const nA = V(fA.normal).normalize(), nB = V(fB.normal).normalize();
    if (type === 'perp' || type === 'angle') {
      const deg = type === 'perp' ? 90 : j.flip ? 180 - (+j.value || 0) : +j.value || 0;
      out.push((nB.dot(nA) - Math.cos((deg * Math.PI) / 180)) * S);
    } else vec(nB.clone().addScaledVector(nA, type === 'touch' || type === 'gap' || j.flip ? 1 : -1), S); // facing / the same way
    if (type === 'touch' || type === 'gap' || type === 'flush') out.push(V(fB.centroid).sub(V(fA.centroid)).dot(nA) - (+j.gap || 0));
    dir = nA;
  }
  if (Number.isFinite(j.angle) && dir) { // its turn locked
    const w = ((((spinOf(fB, fA, dir) - j.angle + 180) % 360) + 360) % 360) - 180;
    out.push(((w * Math.PI) / 180) * S);
  }
  if (j.rot || j.pos || j.slides?.length) { // its locks
    const F = frameOf(fA), off = anchorOf(fB).sub(V(fA.centroid));
    for (const s of j.slides || []) out.push(off.dot(toWorld(s.d, F).normalize()) - s.at);
    if (j.pos) vec(off.clone().sub(toWorld(j.pos, F)));
    if (j.rot) { const B = frameOf(fB); vec(B[0].sub(toWorld(j.rot.x, F)), S); vec(B[1].sub(toWorld(j.rot.y, F)), S); }
  }
  return out;
}

/** A round face's axis as a line (a cylinder's; a cone's from its apex the way it opens) -> {o, d} or null. */
function lineOf(f) {
  if (f.cone) return { o: V(f.cone.apex), d: V(f.cone.d).normalize() };
  return f.axis ? { o: V(f.axis.o), d: V(f.axis.d).normalize() } : null;
}

/** Where a ball's centre goes for a ● ball joint / ◉ seat on `seat` (another ball, a hole, a cone; world), the ball r
 *  and its centre now c -> {p, d?} (d: a line through p — the centre may slide along it), or null. In a cone it touches
 *  the cone r / sin(half) from the apex; on a hole smaller than it, √(R² − r²) out of the hole's end on its side. */
export function ballTarget(type, seat, r, c) {
  if (seat.type === 'sphere' && seat.centre) return { p: V(seat.centre) };
  const ax = lineOf(seat);
  if (!ax) return null;
  if (type !== 'seat') return { p: ax.o, d: ax.d };
  if (seat.cone) {
    const s = Math.sin((seat.cone.half * Math.PI) / 180);
    return s > 1e-6 ? { p: ax.o.clone().addScaledVector(ax.d, r / s) } : { p: ax.o, d: ax.d };
  }
  if (!seat.span || !(seat.radius < r)) return { p: ax.o, d: ax.d }; // (a ball in a bore as big: anywhere along it)
  const h = Math.sqrt(r * r - seat.radius * seat.radius), at = V(c).sub(ax.o).dot(ax.d), [s0, s1] = [...seat.span].sort((a, b) => a - b);
  return { p: ax.o.clone().addScaledVector(ax.d, at >= (s0 + s1) / 2 ? s1 + h : s0 - h) };
}

/** A ● ball joint / ◉ seat: how far the moving part has to shift for it to hold (fB: its face, fA: the other's; either
 *  may be the ball) -> THREE.Vector3, or null when neither is a ball. */
function ballShift(type, fB, fA) {
  const mine = fB.type === 'sphere', ball = mine ? fB : fA, seat = mine ? fA : fB;
  if (ball.type !== 'sphere' || !ball.centre) return null;
  const c = V(ball.centre), tg = ballTarget(type, seat, ball.radius, c);
  if (!tg) return null;
  const v = tg.p.clone().sub(c);
  if (tg.d) v.projectOnPlane(tg.d); // (on a line: only across it)
  return mine ? v : v.negate();
}

/** The point of a face a lock measures from: a ball's centre, else its centroid. */
export const anchorOf = (f) => V(f.type === 'sphere' && f.centre ? f.centre : f.centroid);

/** A part's own directions in the world (from a face of it: its xdir / ydir) -> [x, y, z]. */
const frameOf = (f) => { const x = V(f.xdir).normalize(), y = V(f.ydir).normalize(); return [x, y, new THREE.Vector3().crossVectors(x, y).normalize()]; };
const toLocal = (v, F) => F.map((a) => +a.dot(v).toFixed(9));
const toWorld = (a, F) => F[0].clone().multiplyScalar(a[0]).addScaledVector(F[1], a[1]).addScaledVector(F[2], a[2]);

/** The moving part as it is against the other one, in the other part's own frame (fB, fA: faces of the two, world):
 *  {rot: {x, y} (its own directions), pos (its face's anchor from the other face's centroid)} — what a 🔗 rigid
 *  joint and a lock of a ball's turns keep. */
export function frameNow(fB, fA) {
  const F = frameOf(fA), B = frameOf(fB);
  return { rot: { x: toLocal(B[0], F), y: toLocal(B[1], F) }, pos: toLocal(anchorOf(fB).sub(V(fA.centroid)), F) };
}

/** A move along `dir` (world) locked where it is: {d (in the other part's frame), at (mm)}. */
export function slideNow(fB, fA, dir) {
  const F = frameOf(fA), d = V(dir).normalize();
  return { d: toLocal(d, F), at: +anchorOf(fB).sub(V(fA.centroid)).dot(d).toFixed(4) };
}

/** What a joint's locks (slides, rot, pos) miss: [mm off each slide / the position, the turn off (degrees)]. */
function lockMiss(j, fB, fA) {
  if (!j.rot && !j.pos && !j.slides?.length) return [0, 0];
  const F = frameOf(fA), off = anchorOf(fB).sub(V(fA.centroid));
  let mm = 0, deg = 0;
  for (const s of j.slides || []) mm = Math.max(mm, Math.abs(off.dot(toWorld(s.d, F).normalize()) - s.at));
  if (j.pos) mm = Math.max(mm, off.distanceTo(toWorld(j.pos, F)));
  if (j.rot) { const B = frameOf(fB); deg = (Math.max(B[0].angleTo(toWorld(j.rot.x, F)), B[1].angleTo(toWorld(j.rot.y, F))) * 180) / Math.PI; }
  return [mm, deg];
}

/** The locks applied: the part turned about its anchor to `rot`, moved to `pos`, along each slide to its distance. */
function holdLocks(M, j, faceAt, fA) {
  if (!j.rot && !j.pos && !j.slides?.length) return M;
  const F = frameOf(fA);
  let fB = faceAt(M);
  if (j.rot) {
    const B = frameOf(fB), x = toWorld(j.rot.x, F).normalize(), y = toWorld(j.rot.y, F).normalize();
    const T = new THREE.Matrix4().makeBasis(x, y, new THREE.Vector3().crossVectors(x, y).normalize()), Bm = new THREE.Matrix4().makeBasis(...B);
    const p = anchorOf(fB);
    M = new THREE.Matrix4().makeTranslation(p.x, p.y, p.z).multiply(T.multiply(Bm.transpose())).multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z)).multiply(M);
    fB = faceAt(M);
  }
  if (j.pos) M = shift(M, toWorld(j.pos, F).sub(anchorOf(fB).sub(V(fA.centroid))));
  for (const s of j.slides || []) {
    const d = toWorld(s.d, F).normalize(), now = anchorOf(faceAt(M)).sub(V(fA.centroid)).dot(d);
    M = shift(M, d.multiplyScalar(s.at - now));
  }
  return M;
}

/** One joint: the moving part's matrix M (THREE.Matrix4) and its face fB (world, as placed by M) against the other
 *  part's face fA. faceAt(M) gives fB again for a new M. fixed: what an earlier joint fixed ({dir, flippable}).
 *  -> {M, fixed} (what this joint fixes). Its locks (slides, rot, pos) after its own kind. */
export function applyJoint(M, j, faceAt, fA, first, fixed, centre = first) {
  const r = placeJoint(M, j, faceAt, fA, first, fixed, centre);
  return { M: holdLocks(r.M, j, faceAt, fA), fixed: r.fixed };
}

function placeJoint(M, j, faceAt, fA, first, fixed, centre = first) {
  let fB = faceAt(M);
  const type = j.type || 'touch';
  if (type === 'rigid') return { M, fixed: null }; // (its rot and pos hold it: holdLocks)
  if (type === 'ball' || type === 'seat') {
    const v = ballShift(type, fB, fA);
    if (!v) throw new Error('A ball joint joins a ball (a spherical face) and a hole, a cone or another ball.');
    return { M: shift(M, v), fixed: null };
  }
  if (type === 'axis') {
    if (fA.type !== 'cylinder' || fB.type !== 'cylinder') throw new Error('Pin in hole joins two round faces.');
    const dA = V(fA.axis.d).normalize(), dB = V(fB.axis.d).normalize();
    const target = Math.sign(dB.dot(dA) || 1) > 0 ? dA : dA.clone().negate(); // the way round it is (⇅ turns it over once)
    M = turnAbout(M, pivotOf(fixed, first, V(fB.axis.o)), turnFor(dB, target, first ? null : fixed));
    fB = faceAt(M);
    const v = V(fB.axis.o).sub(V(fA.axis.o)), perp = v.clone().sub(dA.clone().multiplyScalar(v.dot(dA)));
    M = shift(M, perp.negate());
    const ends = axialEnds(faceAt(M), fA);
    if (Number.isFinite(j.dist) && ends) { // a distance along the axis: between the round faces' facing ends
      const { a, b } = ends, side = j.side || (b[0] + b[1] >= a[0] + a[1] ? 1 : -1);
      M = shift(M, dA.clone().multiplyScalar(side > 0 ? a[1] + j.dist - b[0] : a[0] - j.dist - b[1]));
    }
    if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, fA.axis.o, dA, j.angle); // turned about the axis
    return { M, fixed: { dir: dA, flippable: true, o: V(fA.axis.o) } }; // (o: a later joint turns it about this axis)
  }
  if (type === 'axis_distance') {
    const d = Math.max(0, +j.dist || 0), side = j.side || 1;
    if (fA.axis && fB.axis) { // the axes parallel (the way round they are), d apart: where its swing is kept, else the least move
      const dA = V(fA.axis.d).normalize(), dB = V(fB.axis.d).normalize();
      M = turnAbout(M, pivotOf(fixed, first, V(fB.axis.o)), turnFor(dB, dB.dot(dA) >= 0 ? dA : dA.clone().negate(), first ? null : fixed));
      const p = axisOffset(faceAt(M), fA), u = Number.isFinite(j.angle) ? orbitDir(fA, j.angle) : p.length() > 1e-9 ? p.clone().normalize() : across(fA, dA);
      M = shift(M, u.multiplyScalar(d).sub(p));
      return { M, fixed: { dir: dA, flippable: true, o: V(faceAt(M).axis.o) } }; // (a later joint turns it about its own axis: it stays d away)
    }
    if (!(fA.axis && fB.normal) && !(fB.axis && fA.normal)) throw new Error('Axis distance joins two round faces, or a round face and a flat face.');
    if (fB.axis) { // its axis along the other part's flat face, d from it
      const nA = V(fA.normal).normalize();
      M = turnAbout(M, pivotOf(fixed, first, V(fB.axis.o)), turnToAngle(V(fB.axis.d), nA, 90, first ? null : fixed));
      M = shift(M, nA.clone().multiplyScalar(side * d - axisDistanceNow(faceAt(M), fA)));
      return { M, fixed: { dir: nA } };
    }
    // its flat face along the other part's axis, the axis d from it
    const dA = V(fA.axis.d).normalize();
    M = turnAbout(M, pivotOf(fixed, first, V(fB.centroid)), turnToAngle(V(fB.normal), dA, 90, first ? null : fixed));
    M = shift(M, V(faceAt(M).normal).normalize().multiplyScalar(axisDistanceNow(faceAt(M), fA) - side * d));
    return { M, fixed: { dir: dA, flippable: true } };
  }
  if (type === 'tangent') {
    const cyl = fB.type === 'cylinder' ? fB : fA, pl = fB.type === 'cylinder' ? fA : fB;
    if (cyl.type !== 'cylinder' || pl.type !== 'plane' || !cyl.radius) throw new Error('Tangent joins a round face and a flat face.');
    const side = j.flip ? -1 : 1;
    if (fB.type === 'cylinder') { // a roller onto a plate: its axis along the plate, r out from it
      const nA = V(fA.normal).normalize();
      M = turnAbout(M, pivotOf(fixed, first, V(fB.axis.o)), turnToAngle(V(fB.axis.d), nA, 90, first ? null : fixed));
      fB = faceAt(M);
      const s = V(fB.axis.o).sub(V(fA.centroid)).dot(nA);
      M = shift(M, nA.clone().multiplyScalar(side * fB.radius - s));
      if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle);
      return { M, fixed: { dir: nA } };
    }
    // a plate onto a roller: the plate along the axis, the axis r out from its face
    const dA = V(fA.axis.d).normalize();
    M = turnAbout(M, pivotOf(fixed, first, V(fB.centroid)), turnToAngle(V(fB.normal), dA, 90, first ? null : fixed));
    fB = faceAt(M);
    const nB = V(fB.normal).normalize(), s = V(fA.axis.o).sub(V(fB.centroid)).dot(nB);
    M = shift(M, nB.clone().multiplyScalar(s - side * fA.radius));
    return { M, fixed: { dir: dA, flippable: true } };
  }
  if (fA.type !== 'plane' || fB.type !== 'plane') throw new Error(`${JOINT_TYPES[type]?.name || type} joins two flat faces.`);
  if (type === 'perp' || type === 'angle') { // turns only: the faces' directions at the angle
    const nA = V(fA.normal).normalize(), deg = type === 'perp' ? 90 : j.flip ? 180 - (+j.value || 0) : +j.value || 0;
    M = turnAbout(M, pivotOf(fixed, first, V(fB.centroid)), turnToAngle(V(fB.normal), nA, deg, first ? null : fixed));
    if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle);
    return { M, fixed: { dir: nA } };
  }
  const nA = V(fA.normal).normalize(), cA = V(fA.centroid);
  const target = type === 'touch' || type === 'gap' ? nA.clone().negate() : j.flip ? nA.clone().negate() : nA.clone();
  M = turnAbout(M, pivotOf(fixed, first, V(fB.centroid)), turnFor(V(fB.normal), target, first ? null : fixed));
  if (type === 'parallel') return { M, fixed: { dir: nA } };
  fB = faceAt(M);
  const cB = V(fB.centroid), goal = cA.clone().addScaledVector(nA, +j.gap || 0);
  // a new first touch centres the faces on each other; otherwise only the distance along the normal is set
  const d = centre && (type === 'touch' || type === 'gap') ? goal.sub(cB) : nA.clone().multiplyScalar(goal.sub(cB).dot(nA));
  M = shift(M, d);
  if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle); // turned on the face
  return { M, fixed: { dir: nA } };
}
