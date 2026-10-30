// How a joined part can still move: its joints are applied to the part nudged each way (the six small moves / turns),
// and the nudges they keep are its free motions. Plain maths (three.js), no UI.
//   hold(M) -> M again, held by the part's joints (the parts it hangs on stay)
// The free motions come back as moves along a direction and turns about a line, the simplest ones first (along
// X / Y / Z, along an axis or a face, about an axis) — a slider each.
import * as THREE from 'three';

const V = (a) => (a instanceof THREE.Vector3 ? a.clone() : new THREE.Vector3(...a));
const has = (v) => Number.isFinite(v);

/** v kept within a motion's limits ({min?, max?}: a side without one is open — it goes freely that way). */
export const clampLim = (lim, v) => (lim ? Math.max(has(lim.min) ? lim.min : -Infinity, Math.min(has(lim.max) ? lim.max : Infinity, v)) : v);

/** A motion's travel with both ends ({min, max}) from its limits: both set — as they are; one side open — a turn up to a
 *  full turn from the other (round to the stop again), a slide `reach` past where it is (p), as one without limits;
 *  none: null. */
export function travelOf(lim, turn, p = 0, reach = 10) {
  const lo = has(lim?.min), hi = has(lim?.max);
  if (lo && hi) return { min: lim.min, max: lim.max };
  if (!lo && !hi) return null;
  if (turn) return lo ? { min: lim.min, max: lim.min + 360 } : { min: lim.max - 360, max: lim.max };
  return lo ? { min: lim.min, max: Math.ceil(Math.max(p, lim.min) + reach) } : { min: Math.floor(Math.min(p, lim.max) - reach), max: lim.max };
}

/** A move along d (mm) or a turn about the line (p, d) (radians) -> the matrix that does it. */
export function motionMatrix(mo, amount) {
  if (mo.kind === 'move') { const t = V(mo.dir).normalize().multiplyScalar(amount); return new THREE.Matrix4().makeTranslation(t.x, t.y, t.z); }
  const p = V(mo.point), q = new THREE.Quaternion().setFromAxisAngle(V(mo.dir).normalize(), amount);
  return new THREE.Matrix4().makeTranslation(p.x, p.y, p.z).multiply(new THREE.Matrix4().makeRotationFromQuaternion(q)).multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z));
}

/** The small motion from M to M2, seen at the point c: [dx, dy, dz (/ L), rx, ry, rz] (L: the part's size). */
function twistBetween(M2, M, c, L) {
  const D = M2.clone().multiply(M.clone().invert());
  const q = new THREE.Quaternion().setFromRotationMatrix(D);
  if (q.w < 0) { q.x = -q.x; q.y = -q.y; q.z = -q.z; q.w = -q.w; }
  const s = Math.sqrt(1 - Math.min(1, q.w * q.w)), ang = 2 * Math.acos(Math.min(1, q.w));
  const r = s < 1e-12 ? [0, 0, 0] : [q.x / s * ang, q.y / s * ang, q.z / s * ang];
  const t = c.clone().applyMatrix4(D).sub(c);
  return [t.x / L, t.y / L, t.z / L, ...r];
}

/** A motion as the same kind of small twist at c (a unit amount: 1 L of move, 1 radian of turn). */
function twistOf(mo, c, L) {
  const d = V(mo.dir).normalize();
  if (mo.kind === 'move') return [d.x, d.y, d.z, 0, 0, 0];
  const t = new THREE.Vector3().crossVectors(d, c.clone().sub(V(mo.point)));
  return [t.x / L, t.y / L, t.z / L, d.x, d.y, d.z];
}

const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);
const norm = (a) => Math.sqrt(dot(a, a));
const minus = (a, b, k = 1) => a.map((v, i) => v - k * b[i]);

/** The free motions of a part placed by M (THREE.Matrix4) and held by hold(M): candidates are tried in order
 *  [{kind: 'move' | 'turn', dir, point, label}]; -> {count (how many ways it can move), motions: the chosen ones}. */
export function freeMotions(M, hold, c, L, candidates) {
  const eps = 1e-3, cols = [];
  const unit = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  // the joints' answer to the six small nudges (three moves, three turns at c)
  for (let i = 0; i < 6; i++) {
    const mo = i < 3 ? { kind: 'move', dir: unit[i] } : { kind: 'turn', dir: unit[i - 3], point: c };
    const amount = i < 3 ? eps * L : eps;
    let after;
    try { after = hold(motionMatrix(mo, amount).multiply(M.clone())); } catch { after = M.clone(); }
    cols.push(twistBetween(after, M, c, L).map((v) => v / eps));
  }
  const apply = (x) => [0, 1, 2, 3, 4, 5].map((r) => cols.reduce((s, col, j) => s + col[r] * x[j], 0));
  // how many independent ways it can move: the rank of the answer
  const basis = [];
  const residual = (x, B) => B.reduce((v, b) => minus(v, b, dot(v, b)), x);
  for (const col of cols) {
    const r = residual(col, basis);
    if (norm(r) > 0.2) basis.push(r.map((v) => v / norm(r)));
  }
  const count = basis.length, picked = [], chosen = [];
  for (const mo of candidates) {
    if (picked.length >= count) break;
    const x = twistOf(mo, c, L), n = norm(x);
    if (n < 1e-9) continue;
    const xu = x.map((v) => v / n);
    if (norm(minus(apply(xu), xu)) > 0.05) continue; // the joints undo it: not free
    const r = residual(xu, picked);
    if (norm(r) < 0.3) continue; // the same as one already chosen
    picked.push(r.map((v) => v / norm(r)));
    chosen.push(mo);
  }
  return { count, motions: chosen, unexplained: count - chosen.length };
}
