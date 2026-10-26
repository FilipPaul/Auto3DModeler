// Assembly joints: how a placed part is held against another one. Plain geometry (three.js maths), no UI.
//   touch    — a flat face on a flat face, facing each other (gap: mm apart; the first joint also centres them)
//   flush    — two flat faces in one plane, facing the same way (gap: offset along the normal)
//   axis     — concentric: a round face on a round face, on one axis (a pin in a hole); it can still slide along it
//   parallel — two flat faces parallel (turns only)
//   perp     — two flat faces at right angles (turns only)
//   angle    — two flat faces at an angle (`value` degrees between their directions; turns only)
//   tangent  — a round face touching a flat face (the cylinder's side on the plane)
// A part's joints are applied in order: the first one places it freely; the later ones only turn it about the
// direction fixed before, and only move it along their own direction — so "pin in hole" + "touch" = the pin in
// the hole, down to the face. A flat face put onto another one is centred on it once (when the joint is made); then
// it may slide on it.
import * as THREE from 'three';

export const JOINT_TYPES = {
  touch: { icon: '⧉', name: 'Touch', faces: 'plane', hint: 'a flat face onto a flat face (facing each other)' },
  gap: { icon: '↔', name: 'Gap', faces: 'plane', hint: 'a flat face facing another one, a distance apart' },
  flush: { icon: '▭', name: 'Flush', faces: 'plane', hint: 'two flat faces in one plane, facing the same way' },
  axis: { icon: '◎', name: 'Concentric', faces: 'cylinder', hint: 'two round faces on one axis (a pin in a hole, a shaft in a bearing)' },
  parallel: { icon: '∥', name: 'Parallel', faces: 'plane', hint: 'two flat faces parallel (it only turns)' },
  perp: { icon: '⟂', name: 'Perpendicular', faces: 'plane', hint: 'two flat faces at right angles (it only turns)' },
  angle: { icon: '∠', name: 'Angle', faces: 'plane', hint: 'two flat faces at an angle you set (it only turns)' },
  tangent: { icon: '⌒', name: 'Tangent', faces: 'mixed', hint: 'a round face touching a flat face (a roller on a plate)' },
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

/** How far (degrees) the moving part is turned about a joint's direction, from the other part: the angle between
 *  their own x directions (or y, when x runs along it) seen along `dir`. */
export function spinOf(fB, fA, dir) {
  const d = V(dir).normalize();
  const pick = (f) => { const x = V(f.xdir).projectOnPlane(d); return x.length() > 1e-6 ? x.normalize() : V(f.ydir).projectOnPlane(d).normalize(); };
  const a = pick(fA), b = pick(fB);
  return (Math.atan2(new THREE.Vector3().crossVectors(a, b).dot(d), a.dot(b)) * 180) / Math.PI;
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

/** One joint: the moving part's matrix M (THREE.Matrix4) and its face fB (world, as placed by M) against the other
 *  part's face fA. faceAt(M) gives fB again for a new M. fixed: what an earlier joint fixed ({dir, flippable}).
 *  -> {M, fixed} (what this joint fixes). */
export function applyJoint(M, j, faceAt, fA, first, fixed, centre = first) {
  let fB = faceAt(M);
  const type = j.type || 'touch';
  if (type === 'axis') {
    if (fA.type !== 'cylinder' || fB.type !== 'cylinder') throw new Error('Pin in hole joins two round faces.');
    const dA = V(fA.axis.d).normalize(), dB = V(fB.axis.d).normalize();
    const target = (j.flip ? -1 : 1) * Math.sign(dB.dot(dA) || 1) > 0 ? dA : dA.clone().negate();
    M = turnAbout(M, V(fB.axis.o), turnFor(dB, target, first ? null : fixed));
    fB = faceAt(M);
    const v = V(fB.axis.o).sub(V(fA.axis.o)), perp = v.clone().sub(dA.clone().multiplyScalar(v.dot(dA)));
    M = shift(M, perp.negate());
    const ends = axialEnds(faceAt(M), fA);
    if (Number.isFinite(j.dist) && ends) { // a distance along the axis: between the round faces' facing ends
      const { a, b } = ends, side = j.side || (b[0] + b[1] >= a[0] + a[1] ? 1 : -1);
      M = shift(M, dA.clone().multiplyScalar(side > 0 ? a[1] + j.dist - b[0] : a[0] - j.dist - b[1]));
    }
    if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, fA.axis.o, dA, j.angle); // turned about the axis
    return { M, fixed: { dir: dA, flippable: true } };
  }
  if (type === 'tangent') {
    const cyl = fB.type === 'cylinder' ? fB : fA, pl = fB.type === 'cylinder' ? fA : fB;
    if (cyl.type !== 'cylinder' || pl.type !== 'plane' || !cyl.radius) throw new Error('Tangent joins a round face and a flat face.');
    const side = j.flip ? -1 : 1;
    if (fB.type === 'cylinder') { // a roller onto a plate: its axis along the plate, r out from it
      const nA = V(fA.normal).normalize();
      M = turnAbout(M, V(fB.axis.o), turnToAngle(V(fB.axis.d), nA, 90, first ? null : fixed));
      fB = faceAt(M);
      const s = V(fB.axis.o).sub(V(fA.centroid)).dot(nA);
      M = shift(M, nA.clone().multiplyScalar(side * fB.radius - s));
      if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle);
      return { M, fixed: { dir: nA } };
    }
    // a plate onto a roller: the plate along the axis, the axis r out from its face
    const dA = V(fA.axis.d).normalize();
    M = turnAbout(M, V(fB.centroid), turnToAngle(V(fB.normal), dA, 90, first ? null : fixed));
    fB = faceAt(M);
    const nB = V(fB.normal).normalize(), s = V(fA.axis.o).sub(V(fB.centroid)).dot(nB);
    M = shift(M, nB.clone().multiplyScalar(s - side * fA.radius));
    return { M, fixed: { dir: dA, flippable: true } };
  }
  if (fA.type !== 'plane' || fB.type !== 'plane') throw new Error(`${JOINT_TYPES[type]?.name || type} joins two flat faces.`);
  if (type === 'perp' || type === 'angle') { // turns only: the faces' directions at the angle
    const nA = V(fA.normal).normalize(), deg = type === 'perp' ? 90 : j.flip ? 180 - (+j.value || 0) : +j.value || 0;
    M = turnAbout(M, V(fB.centroid), turnToAngle(V(fB.normal), nA, deg, first ? null : fixed));
    if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle);
    return { M, fixed: { dir: nA } };
  }
  const nA = V(fA.normal).normalize(), cA = V(fA.centroid);
  const target = type === 'touch' || type === 'gap' ? nA.clone().negate() : j.flip ? nA.clone().negate() : nA.clone();
  M = turnAbout(M, V(fB.centroid), turnFor(V(fB.normal), target, first ? null : fixed));
  if (type === 'parallel') return { M, fixed: { dir: nA } };
  fB = faceAt(M);
  const cB = V(fB.centroid), goal = cA.clone().addScaledVector(nA, +j.gap || 0);
  // a new first touch centres the faces on each other; otherwise only the distance along the normal is set
  const d = centre && (type === 'touch' || type === 'gap') ? goal.sub(cB) : nA.clone().multiplyScalar(goal.sub(cB).dot(nA));
  M = shift(M, d);
  if (Number.isFinite(j.angle)) M = spinTo(M, faceAt, fA, faceAt(M).centroid, nA, j.angle); // turned on the face
  return { M, fixed: { dir: nA } };
}
