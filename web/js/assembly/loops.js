// Closed loops of joints: a part joined onto two parts that move (a rod on a crank's pin and on a slider's pin) — its
// joints cannot be applied one after the other, the parts of the loop are placed together. Plain maths (three.js),
// no UI.
//   findLoops: the loops in a set of joints -> the parts that move in each
//   solveLoop: the free parts of a loop moved (a damped least-squares, from where they are: the nearest way) until
//              all its joints hold (jointResidual 0) — or it cannot close (a rod too short for that place)
//   loopFreedom: how many ways a loop's parts can still move together (a crank – rod – slider: 1)
//   screwBetween: a part's move from one place to another, in steps (a crank's turn about its own axis), so a big move
//              of a part in a loop is followed step by step and the loop stays the way it was put together
import * as THREE from 'three';
import { jointResidual } from './joints.js';

/** The closed loops among joints [{move, onto}] -> [[part ids that move in it]]. A part joined onto two or more parts
 *  closes a loop with the parts between them, down to the parts all of those hang on (they stay). moves(id): may the
 *  part move (it has joints of its own and is not 📌 fixed). Loops that share a part are one. */
export function findLoops(mates, moves) {
  const on = (x) => [...new Set(mates.filter((m) => m.move === x).map((m) => m.onto))];
  const below = (x) => { // the part and every part it hangs on, through others
    const seen = new Set(), stack = [x];
    while (stack.length) { const y = stack.pop(); if (!seen.has(y)) { seen.add(y); stack.push(...on(y)); } }
    return seen;
  };
  const loops = [];
  for (const id of new Set(mates.map((m) => m.move))) {
    const sup = on(id);
    if (sup.length < 2 || !moves(id)) continue;
    const chains = sup.map(below), common = chains.reduce((a, b) => new Set([...a].filter((x) => b.has(x))));
    const parts = new Set([id, ...chains.flatMap((c) => [...c]).filter((x) => !common.has(x) && moves(x))]);
    if (parts.size < 2) continue; // (onto parts that stay: its joints one after another, as any part's)
    for (const l of loops.filter((l) => [...l].some((x) => parts.has(x)))) { l.forEach((x) => parts.add(x)); loops.splice(loops.indexOf(l), 1); }
    loops.push(parts);
  }
  return loops.map((l) => [...l].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true })));
}

const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);

/** Solve A x = b (n × n, rows of numbers) -> x, or null when it has no single answer. */
function solve(A, b) {
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-14) return null;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = c + 1; r < n; r++) {
      const f = M[r][c] / M[c][c];
      if (f) for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  const x = new Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) x[r] = (M[r][n] - M[r].slice(r + 1, n).reduce((s, v, k) => s + v * x[r + 1 + k], 0)) / M[r][r];
  return x;
}

/** A small move of a part: x = [dx, dy, dz (mm), rx, ry, rz (radians × L)] about its centre c (where M puts it). */
function nudge(M, c, L, x) {
  const p = c.clone().applyMatrix4(M), r = new THREE.Vector3(x[3], x[4], x[5]).divideScalar(L), a = r.length();
  const R = a < 1e-15 ? new THREE.Matrix4() : new THREE.Matrix4().makeRotationAxis(r.normalize(), a);
  return new THREE.Matrix4().makeTranslation(p.x + x[0], p.y + x[1], p.z + x[2]).multiply(R).multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z)).multiply(M);
}

/** The joints' misses with the parts at P (id -> Matrix4): one list of numbers. faceAt(id, face, M) -> the face in the
 *  world (as Assembly.worldFace). */
function misses(mates, P, faceAt) {
  const out = [];
  for (const m of mates) {
    try { out.push(...jointResidual(m, faceAt(m.move, m.face, P.get(m.move)), faceAt(m.onto, m.ontoFace, P.get(m.onto)))); } catch { /* not built */ }
  }
  return out;
}

/** The largest miss of the joints with the parts at P (mm; 0: they all hold exactly). */
export function worstMiss(mates, P, faceAt) { return misses(mates, P, faceAt).reduce((s, x) => Math.max(s, Math.abs(x)), 0); }

/** How each miss changes as each free part moves a little (by its six small moves) -> columns. */
function jacobian(free, mates, P, faceAt, r0, h = 1e-5) {
  const cols = [];
  for (const f of free) {
    for (let k = 0; k < 6; k++) {
      const x = [0, 0, 0, 0, 0, 0];
      x[k] = h;
      const Q = new Map(P).set(f.id, nudge(P.get(f.id), f.c, f.L, x)), r = misses(mates, Q, faceAt);
      cols.push(r.map((v, i) => (v - r0[i]) / h));
    }
  }
  return cols;
}

/** Move the free parts [{id, c (its centre, own), L (its size)}] from P (id -> Matrix4, every part the joints touch)
 *  until all the joints hold -> {ok, P (the new places), miss (the largest miss left, mm)}. The parts move as little
 *  as they can (damped: a way the joints leave free is not taken). tol: mm. */
export function solveLoop(free, mates, P, faceAt, { tol = 1e-6, steps = 80 } = {}) {
  P = new Map(P);
  if (!free.length) { const r0 = misses(mates, P, faceAt); return { ok: r0.every((v) => Math.abs(v) <= Math.max(tol, 1e-4)), P, miss: Math.max(0, ...r0.map(Math.abs)) }; }
  let r = misses(mates, P, faceAt), cost = dot(r, r), lambda = 1e-3;
  const worst = (v) => v.reduce((s, x) => Math.max(s, Math.abs(x)), 0);
  for (let it = 0; it < steps && worst(r) > tol; it++) {
    const J = jacobian(free, mates, P, faceAt, r), n = J.length;
    const A = J.map((ci) => J.map((cj) => dot(ci, cj))), g = J.map((c) => -dot(c, r));
    let moved = false;
    while (lambda < 1e10) {
      const x = solve(A.map((row, i) => row.map((v, k) => (i === k ? v + lambda * (v + 1) : v))), g);
      if (!x) { lambda *= 10; continue; }
      const Q = new Map(P);
      free.forEach((f, q) => Q.set(f.id, nudge(P.get(f.id), f.c, f.L, x.slice(6 * q, 6 * q + 6))));
      const r2 = misses(mates, Q, faceAt), c2 = dot(r2, r2);
      if (c2 < cost) { P = Q; r = r2; cost = c2; lambda = Math.max(lambda / 4, 1e-12); moved = true; break; }
      lambda *= 6;
    }
    if (!moved || n === 0) break;
  }
  return { ok: worst(r) <= Math.max(tol, 1e-4), P, miss: worst(r) };
}

/** How many ways the parts [{id, c, L}] can still move together, their joints holding (the moves the joints'
 *  misses do not see). */
export function loopFreedom(free, mates, P, faceAt) {
  const r0 = misses(mates, P, faceAt), h = 1e-4, J = [];
  for (const f of free) {
    for (let k = 0; k < 6; k++) { // (both ways: a miss that is 0 at both ends of a turn does not count it as held)
      const a = [0, 0, 0, 0, 0, 0], b = [0, 0, 0, 0, 0, 0];
      a[k] = h;
      b[k] = -h;
      const ra = misses(mates, new Map(P).set(f.id, nudge(P.get(f.id), f.c, f.L, a)), faceAt);
      const rb = misses(mates, new Map(P).set(f.id, nudge(P.get(f.id), f.c, f.L, b)), faceAt);
      J.push(ra.map((v, i) => (v - rb[i]) / (2 * h)));
    }
  }
  if (!r0.length) return J.length;
  // the rank of J (its columns: the parts' moves): Gram–Schmidt, a column that adds less than 1e-4 of itself is not new
  const basis = [];
  for (const col of J) {
    const n0 = Math.sqrt(dot(col, col));
    let v = [...col];
    for (const b of basis) { const k = dot(v, b); v = v.map((x, i) => x - k * b[i]); }
    const n = Math.sqrt(dot(v, v));
    if (n > 1e-4 * Math.max(1, n0)) basis.push(v.map((x) => x / n));
  }
  return J.length - basis.length;
}

/** A part's move from matrix A to B as a screw: a turn about one line and a slide along it -> (s: 0 … 1) -> the
 *  matrix part of the way (a crank turned 90° about its shaft goes round its shaft, not across). */
export function screwBetween(A, B) {
  const D = B.clone().multiply(A.clone().invert()), q = new THREE.Quaternion().setFromRotationMatrix(D);
  if (q.w < 0) q.set(-q.x, -q.y, -q.z, -q.w);
  const t = new THREE.Vector3().setFromMatrixPosition(D), phi = 2 * Math.acos(Math.min(1, q.w));
  if (phi < 1e-9) return (s) => new THREE.Matrix4().makeTranslation(t.x * s, t.y * s, t.z * s).multiply(A);
  const a = new THREE.Vector3(q.x, q.y, q.z).normalize(), along = a.clone().multiplyScalar(t.dot(a)), across = t.clone().sub(along);
  const p = across.clone().add(new THREE.Vector3().crossVectors(a, across).multiplyScalar(1 / Math.tan(phi / 2))).multiplyScalar(0.5); // a point on its line
  return (s) => new THREE.Matrix4().makeTranslation(p.x + along.x * s, p.y + along.y * s, p.z + along.z * s).multiply(new THREE.Matrix4().makeRotationAxis(a, phi * s))
    .multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z)).multiply(A);
}

/** How many steps a move from A to B is followed in: one per 10° of turn and per a tenth of the part's size L. */
export function stepsBetween(A, B, L) {
  const D = B.clone().multiply(A.clone().invert()), q = new THREE.Quaternion().setFromRotationMatrix(D);
  const phi = 2 * Math.acos(Math.min(1, Math.abs(q.w))), t = new THREE.Vector3().setFromMatrixPosition(D).length();
  return Math.min(72, Math.max(1, Math.ceil((phi * 180) / Math.PI / 10), Math.ceil(t / Math.max(1, L / 10))));
}
