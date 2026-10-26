// Assembly joints: how a placed part is held against another one. Plain geometry (three.js maths), no UI.
//   touch    — a flat face on a flat face, facing each other (gap: mm apart; the first joint also centres them)
//   flush    — two flat faces in one plane, facing the same way (gap: offset along the normal)
//   axis     — a round face on a round face, on one axis (a pin in a hole); it can still slide along the axis
//   parallel — two flat faces parallel (turns only)
// A part's joints are applied in order: the first one places it freely; the later ones only turn it about the
// direction fixed before, and only move it along their own direction — so "pin in hole" + "touch" = the pin in
// the hole, down to the face.
import * as THREE from 'three';

export const JOINT_TYPES = {
  touch: { icon: '⧉', name: 'Touch', faces: 'plane', hint: 'a flat face onto a flat face (facing each other)' },
  gap: { icon: '↔', name: 'Gap', faces: 'plane', hint: 'a flat face facing another one, a distance apart' },
  flush: { icon: '▭', name: 'Flush', faces: 'plane', hint: 'two flat faces in one plane, facing the same way' },
  axis: { icon: '◎', name: 'Pin in hole', faces: 'cylinder', hint: 'two round faces on one axis (a pin in a hole, a shaft in a bearing)' },
  parallel: { icon: '∥', name: 'Parallel', faces: 'plane', hint: 'two flat faces parallel (it only turns)' },
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

function turnAbout(M, centre, q) {
  return new THREE.Matrix4().makeTranslation(centre.x, centre.y, centre.z).multiply(new THREE.Matrix4().makeRotationFromQuaternion(q))
    .multiply(new THREE.Matrix4().makeTranslation(-centre.x, -centre.y, -centre.z)).multiply(M);
}

const shift = (M, d) => new THREE.Matrix4().makeTranslation(d.x, d.y, d.z).multiply(M);

/** One joint: the moving part's matrix M (THREE.Matrix4) and its face fB (world, as placed by M) against the other
 *  part's face fA. faceAt(M) gives fB again for a new M. fixed: what an earlier joint fixed ({dir, flippable}).
 *  -> {M, fixed} (what this joint fixes). */
export function applyJoint(M, j, faceAt, fA, first, fixed) {
  let fB = faceAt(M);
  const type = j.type || 'touch';
  if (type === 'axis') {
    if (fA.type !== 'cylinder' || fB.type !== 'cylinder') throw new Error('Pin in hole joins two round faces.');
    const dA = V(fA.axis.d).normalize(), dB = V(fB.axis.d).normalize();
    const target = (j.flip ? -1 : 1) * Math.sign(dB.dot(dA) || 1) > 0 ? dA : dA.clone().negate();
    M = turnAbout(M, V(fB.axis.o), turnFor(dB, target, first ? null : fixed));
    fB = faceAt(M);
    const v = V(fB.axis.o).sub(V(fA.axis.o)), perp = v.clone().sub(dA.clone().multiplyScalar(v.dot(dA)));
    return { M: shift(M, perp.negate()), fixed: { dir: dA, flippable: true } };
  }
  if (fA.type !== 'plane' || fB.type !== 'plane') throw new Error(`${JOINT_TYPES[type]?.name || type} joins two flat faces.`);
  const nA = V(fA.normal).normalize(), cA = V(fA.centroid);
  const target = type === 'touch' || type === 'gap' ? nA.clone().negate() : j.flip ? nA.clone().negate() : nA.clone();
  M = turnAbout(M, V(fB.centroid), turnFor(V(fB.normal), target, first ? null : fixed));
  if (type === 'parallel') return { M, fixed: { dir: nA } };
  fB = faceAt(M);
  const cB = V(fB.centroid), goal = cA.clone().addScaledVector(nA, +j.gap || 0);
  // the first touch centres the faces on each other; otherwise only the distance along the normal is set
  const d = first && (type === 'touch' || type === 'gap') ? goal.sub(cB) : nA.clone().multiplyScalar(goal.sub(cB).dot(nA));
  return { M: shift(M, d), fixed: { dir: nA } };
}
