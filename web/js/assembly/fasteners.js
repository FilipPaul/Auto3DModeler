// Fasteners for assemblies: where screws, heat-set inserts and dowel pins fit (holes that line up across parts),
// and the standard parts themselves (simple 3D models: a socket-head screw, an insert, a pin). Plain data and maths.
import * as THREE from 'three';
import { sketchFromShapes } from '../modeler/agent_model.js';

/** Metric sizes: the screw's Ø, its clearance hole, the head (Ø × height), the hex key, the heat-set insert (its hole,
 *  its outside Ø and length). Holes are as 3D printed: a little bigger than the nominal. */
export const SIZES = {
  M2: { d: 2, clear: [2.15, 2.7], head: [3.8, 2], key: 1.5, insertHole: [3.0, 3.4], insert: [3.2, 3] },
  'M2.5': { d: 2.5, clear: [2.7, 3.15], head: [4.5, 2.5], key: 2, insertHole: [3.5, 3.9], insert: [3.7, 4] },
  M3: { d: 3, clear: [3.2, 3.7], head: [5.5, 3], key: 2.5, insertHole: [3.9, 4.4], insert: [4.2, 5] },
  M4: { d: 4, clear: [4.3, 4.9], head: [7, 4], key: 3, insertHole: [5.0, 5.8], insert: [5.6, 6] },
  M5: { d: 5, clear: [5.3, 5.9], head: [8.5, 5], key: 4, insertHole: [6.0, 6.8], insert: [6.4, 7] },
};
export const SCREW_LENGTHS = [3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40, 45, 50];
export const PIN_SIZES = [2, 2.5, 3, 4, 5, 6, 8];
export const PIN_LENGTHS = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 24, 30, 36, 40];

const fit = (x, [lo, hi]) => x >= lo - 1e-6 && x <= hi + 1e-6;
const hexagon = (s) => Array.from({ length: 6 }, (_, i) => [+(s / Math.sqrt(3) * Math.cos((i * Math.PI) / 3)).toFixed(4), +(s / Math.sqrt(3) * Math.sin((i * Math.PI) / 3)).toFixed(4)]);
const sk = (id, plane, shapes) => ({ id, type: 'sketch', name: `Sketch ${id.slice(1)}`, plane, ...sketchFromShapes(shapes, true) });
const ex = (id, sketch, d, op = 'add') => ({ id, type: 'extrude', name: `Extrude ${id.slice(1)}`, sketch, op, d, through: false, symmetric: false, flip: false });
const onTop = (name, z) => ({ face: { name }, frame: { o: [0, 0, z], x: [1, 0, 0], n: [0, 0, 1] } });

/** The model of a standard part, and the names of its faces that joints use:
 *  shaft (the round face that goes in the hole), seat (the face that sits on the part), top (the end face). */
export function fastenerModel(kind, size, length) {
  const S = SIZES[size];
  if (kind === 'screw') { // socket head cap screw (ISO 4762), the shaft up from 0, the head on top
    const [dk, k] = S.head;
    return {
      name: `${size}×${length} screw`,
      features: [sk('F1', { datum: 'XY' }, [{ circle: { x: 0, y: 0, d: S.d } }]), ex('F2', 'F1', length),
        sk('F3', onTop('F2:end', length), [{ circle: { x: 0, y: 0, d: dk } }]), ex('F4', 'F3', k),
        sk('F5', onTop('F4:end', length + k), [{ polyline: { points: hexagon(S.key) } }]), ex('F6', 'F5', +(k * 0.6).toFixed(2), 'cut')],
      faces: { shaft: 'F2:side:c1', seat: 'F4:start' },
      material: 'PA',
    };
  }
  if (kind === 'insert') { // heat-set insert: a ring, its thread inside
    const [od, len] = S.insert;
    return {
      name: `${size} insert`,
      features: [sk('F1', { datum: 'XY' }, [{ circle: { x: 0, y: 0, d: od } }, { circle: { x: 0, y: 0, d: S.d } }]), ex('F2', 'F1', length || len)],
      faces: { shaft: 'F2:side:c1', top: 'F2:end' },
      material: 'PA',
    };
  }
  // a dowel pin
  return {
    name: `Ø${size}×${length} pin`,
    features: [sk('F1', { datum: 'XY' }, [{ circle: { x: 0, y: 0, d: +size } }]), ex('F2', 'F1', length)],
    faces: { shaft: 'F2:side:c1', top: 'F2:end' },
    material: 'PA',
  };
}

/** The round faces of the placed parts in world coordinates: [{inst, name, r, o, d, t0, t1}] — t along d. */
function holes(asm) {
  const out = [];
  const fasteners = new Set((asm.doc.mates || []).filter((m) => m.type === 'axis').map((m) => m.move)); // pins / screws in holes
  for (const it of asm.doc.instances) {
    const b = asm.bodies[it.part]?.body;
    if (!b || fasteners.has(it.id)) continue;
    const M = new THREE.Matrix4().fromArray(it.matrix), N = new THREE.Matrix3().getNormalMatrix(M);
    for (const f of b.faces) {
      if (f.type !== 'cylinder' || !f.axis || !f.radius) continue;
      const d = new THREE.Vector3(...f.axis.d).applyMatrix3(N).normalize(), o = new THREE.Vector3(...f.axis.o).applyMatrix4(M);
      const c = new THREE.Vector3(...f.centroid).applyMatrix4(M), len = f.area / (2 * Math.PI * f.radius);
      // the centroid of a full cylinder is on its axis, halfway; of a half one (a split face) a little off it
      const tc = c.clone().sub(o).dot(d);
      const same = out.find((h) => h.inst === it.id && Math.abs(h.r - f.radius) < 1e-4 && h.o.clone().sub(o).cross(h.d).length() < 1e-3 && Math.abs(Math.abs(h.d.dot(d)) - 1) < 1e-6);
      if (same) continue; // the other half of a split cylinder
      out.push({ inst: it.id, name: f.name, r: f.radius, o, d, t0: tc - len / 2, t1: tc + len / 2, part: it.part });
    }
  }
  return out;
}

/** The flat face of a placed part across the axis at a point, its normal pointing `out`. */
function planeAt(asm, inst, point, out) {
  const it = asm.inst(inst), b = asm.bodies[it.part]?.body;
  const M = new THREE.Matrix4().fromArray(it.matrix), N = new THREE.Matrix3().getNormalMatrix(M);
  let best = null;
  for (const f of b.faces) {
    if (f.type !== 'plane') continue;
    const n = new THREE.Vector3(...f.normal).applyMatrix3(N).normalize();
    if (n.dot(out) < 0.999) continue;
    const c = new THREE.Vector3(...f.centroid).applyMatrix4(M);
    if (Math.abs(c.clone().sub(point).dot(n)) > 0.05) continue;
    const dist = c.distanceTo(point);
    if (!best || dist < best.dist) best = { name: f.name, dist };
  }
  return best?.name || null;
}

/** Where fasteners fit: holes on one axis through two or more parts. -> [{id, kind, size, length, text, ...}] */
export function findCandidates(asm) {
  const hs = holes(asm), lines = [];
  for (const h of hs) {
    const line = lines.find((l) => Math.abs(Math.abs(l.d.dot(h.d)) - 1) < 1e-4 && h.o.clone().sub(l.o).cross(l.d).length() < 0.05);
    if (line) {
      const t = h.o.clone().sub(line.o).dot(line.d), s = Math.sign(h.d.dot(line.d));
      line.holes.push({ ...h, t0: t + s * (s > 0 ? h.t0 : h.t1), t1: t + s * (s > 0 ? h.t1 : h.t0) });
    } else lines.push({ o: h.o.clone(), d: h.d.clone(), holes: [{ ...h }] });
  }
  const out = [];
  const filled = new Set((asm.doc.mates || []).filter((m) => m.type === 'axis').map((m) => `${m.onto}|${m.ontoFace}`));
  let full = 0;
  for (const line of lines) {
    const insts = [...new Set(line.holes.map((h) => h.inst))];
    if (insts.length < 2) continue;
    if (line.holes.some((h) => filled.has(`${h.inst}|${h.name}`))) { full++; continue; } // it has its fastener
    const lo = Math.min(...line.holes.map((h) => h.t0)), hi = Math.max(...line.holes.map((h) => h.t1));
    // try both ends as the side the fastener goes in from
    for (const end of [1, -1]) {
      const at = end > 0 ? hi : lo, inward = line.d.clone().multiplyScalar(-end), outward = line.d.clone().multiplyScalar(end);
      const entry = line.holes.filter((h) => Math.abs((end > 0 ? h.t1 : h.t0) - at) < 0.05).sort((a, b) => b.r - a.r)[0];
      if (!entry) continue;
      const entryPoint = line.o.clone().addScaledVector(line.d, at);
      const entryPlane = planeAt(asm, entry.inst, entryPoint, outward);
      if (!entryPlane) continue;
      const others = line.holes.filter((h) => h.inst !== entry.inst);
      const depth = hi - lo;
      const base = { axis: { o: entryPoint.toArray(), d: inward.toArray() }, entry: { inst: entry.inst, hole: entry.name, plane: entryPlane },
        holes: line.holes.map((h) => ({ inst: h.inst, name: h.name })) };
      for (const [size, S] of Object.entries(SIZES)) {
        if (!fit(2 * entry.r, S.clear)) continue;
        // the next part's hole for an insert: from the face where the parts meet
        const ins = others.find((h) => fit(2 * h.r, S.insertHole));
        if (ins) {
          const meet = end > 0 ? ins.t1 : ins.t0;
          const face = planeAt(asm, ins.inst, line.o.clone().addScaledVector(line.d, meet), outward);
          const insLen = Math.min(S.insert[1], ins.t1 - ins.t0);
          const screwLen = [...SCREW_LENGTHS].reverse().find((L) => L <= Math.abs(at - meet) + insLen - 0.3) || SCREW_LENGTHS[0];
          if (face) {
            out.push({ ...base, kind: 'screw-insert', size, length: screwLen, insert: { inst: ins.inst, hole: ins.name, plane: face, length: +insLen.toFixed(2) },
              text: `${size}×${screwLen} screw + ${size} insert` });
          }
        } else if (others.every((h) => fit(2 * h.r, S.clear) || fit(2 * h.r, S.insertHole))) {
          const L = [...SCREW_LENGTHS].reverse().find((x) => x <= depth - 0.3) || SCREW_LENGTHS[0];
          out.push({ ...base, kind: 'screw', size, length: L, text: `${size}×${L} screw` });
        }
      }
      // a pin: the same Ø all along
      const d0 = 2 * entry.r, pin = PIN_SIZES.find((p) => Math.abs(p - d0) < 0.25);
      if (pin && line.holes.every((h) => Math.abs(2 * h.r - d0) < 0.25) && end > 0) {
        const L = [...PIN_LENGTHS].reverse().find((x) => x <= depth) || PIN_LENGTHS[0];
        out.push({ ...base, kind: 'pin', size: String(pin), length: L, text: `Ø${pin}×${L} pin` });
      }
    }
  }
  // the best first: screw + insert, then screws, then pins; one suggestion per axis and end
  const rank = { 'screw-insert': 0, screw: 1, pin: 2 };
  out.sort((a, b) => rank[a.kind] - rank[b.kind]);
  const seen = new Set(), best = [];
  for (const c of out) {
    const key = `${c.axis.o.map((v) => v.toFixed(2))}`;
    if (seen.has(key)) continue;
    seen.add(key);
    best.push({ ...c, id: `C${best.length + 1}` });
  }
  best.filled = full;
  return best;
}
