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
/** Hex nuts (ISO 4032): across the flats, height. */
export const NUTS = { M2: [4, 1.6], 'M2.5': [5, 2], M3: [5.5, 2.4], M4: [7, 3.2], M5: [8, 4.7] };
export const SCREW_LENGTHS = [3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80];
/** What goes through the parts: a screw and a nut below, a screw into a heat-set insert in the last part, or a pin. */
export const BOLT_KINDS = { nut: 'Screw + nut', insert: 'Screw + heat-set insert', pin: 'Pin' };
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
  if (kind === 'nut') { // a hex nut: its hole the screw's Ø
    const [s, m] = NUTS[size];
    return {
      name: `${size} nut`,
      features: [sk('F1', { datum: 'XY' }, [{ polyline: { points: hexagon(s) } }, { circle: { x: 0, y: 0, d: S.d } }]), ex('F2', 'F1', m)],
      faces: { shaft: 'F2:side:c1', seat: 'F2:start' },
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

// ------------------------------------------------------------------ a new bolt: drilled through the parts

const b64 = (s, T) => {
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};
const SIDE = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });

/** Is this part a standard part (a screw, nut, insert or pin put in by the assembly)? */
export const isStandard = (data, name = '') => !!data?.standard || /^(M[\d.]+(×\d+)? (screw|nut|insert)|Ø[\d.]+×\d+ pin)$/.test(name);

/** Where the line (point o, direction d) runs through the placed parts: [{inst, part, tin, tout, inFace, outFace}],
 *  t in mm from o along d (a part the line goes in and out of twice gives two pieces). */
export function partsAlong(asm, o, d, skip = () => false) {
  const dir = d.clone().normalize(), from = o.clone().addScaledVector(dir, -1);
  const ray = new THREE.Raycaster(from, dir, 0, 1e5), out = [];
  for (const it of asm.doc.instances) {
    const b = asm.bodies[it.part]?.body;
    if (!b || skip(it)) continue;
    if (!b._geo) {
      b._geo = new THREE.BufferGeometry();
      b._geo.setAttribute('position', new THREE.BufferAttribute(b64(b.positions, Float32Array), 3));
      b._ids = b64(b.face_ids, Uint32Array);
    }
    const mesh = new THREE.Mesh(b._geo, SIDE);
    mesh.matrixAutoUpdate = false;
    mesh.matrix.fromArray(it.matrix);
    mesh.matrixWorld.copy(mesh.matrix);
    const N = new THREE.Matrix3().getNormalMatrix(mesh.matrix);
    const hits = [];
    for (const h of ray.intersectObject(mesh, false)) {
      const into = h.face.normal.clone().applyMatrix3(N).dot(dir) < 0, t = h.distance - 1;
      if (hits.some((x) => x.into === into && Math.abs(x.t - t) < 1e-4)) continue; // the same point on two triangles
      hits.push({ t, into, face: b.faces.find((f) => f.id === b._ids[h.faceIndex])?.name });
    }
    hits.sort((p, q) => p.t - q.t);
    let depth = 0, start = null;
    for (const h of hits) {
      if (h.into) { if (!depth++) start = h; } else if (depth > 0 && !--depth) {
        out.push({ inst: it.id, part: it.part, tin: start.t, tout: h.t, inFace: start.face, outFace: h.face });
      }
    }
  }
  return out.sort((p, q) => p.tin - q.tin);
}

/** A reason it does not fit: the English text, and its template + values (for the translation). */
const E = (key, vars = {}, stack = []) => ({ error: key.replace(/\{(\w+)\}/g, (_, k) => vars[k]), errorKey: key, errorVars: vars, stack });

const STD = (list, need, up) => (up ? list.find((x) => x >= need - 1e-6) : [...list].reverse().find((x) => x <= need + 1e-6));

/** A screw (+ nut / insert) or a pin in at point `o` (world) of a flat face, along `d` (into the parts):
 *  the parts it goes through (those touching one after another, at most `upto` of them), what fits and the holes it
 *  needs in each. -> {kind, size, length, text, holes: [{inst, part, tin, tout, d, through, depth, inFace, outFace}],
 *  ghost: [{o, d, len, r, sides}]} or {error, stack} */
export function planBolt(asm, { o, d, kind = 'nut', size = 'M3', upto = null, drillable = () => true }) {
  const S = SIZES[size];
  if (!S) return E('Size is one of {list}.', { list: Object.keys(SIZES).join(', ') });
  const skip = (it) => isStandard(asm.hooks.partData(it.part), asm.partName(it.part));
  const all = partsAlong(asm, o, d, skip).filter((p) => p.tout > 0.01);
  const stack = [];
  for (const p of all) {
    const prev = stack[stack.length - 1];
    if (!prev ? p.tin > 0.05 : p.tin - prev.tout > 0.6) break; // the first starts at the point; the next touch
    stack.push(p);
  }
  if (!stack.length) return E('There is no part at this point.');
  const bad = stack.findIndex((p) => !drillable(p.part));
  let use = bad < 0 ? stack : stack.slice(0, bad);
  if (upto) use = use.slice(0, upto);
  if (use.length < 2 || new Set(use.map((p) => p.inst)).size < 2) {
    if (bad >= 0 && bad < (upto || stack.length)) return E('{part} is not a 3D model, so it cannot be drilled — make it a 3D model to put a screw through it.', { part: asm.partName(stack[bad].part) }, stack);
    return E('Under this point there is only {part} — join the parts first (they have to touch), then put the screw through them.', { part: asm.partName(use[0].part) }, stack);
  }
  const last = use[use.length - 1], total = last.tout, D = d.clone().normalize();
  const at = (t) => o.clone().addScaledVector(D, t).toArray();
  const ghost = [];
  const isLast = (p) => !all.some((q) => q.inst === p.inst && q.tin > p.tout + 0.01); // no more of that part beyond
  const hole = (p, dia, depth = null) => ({ ...p, d: dia, through: depth === null && isLast(p), depth: depth ?? +(p.tout - p.tin + 0.5).toFixed(2) });
  const clear = +(S.d + 0.4).toFixed(2);
  let plan;
  if (kind === 'pin') {
    const pd = S.d, L = STD(PIN_LENGTHS, total);
    if (!L) return E('The parts are only {t} mm thick — too thin for a pin.', { t: fmt(total) }, stack);
    plan = { kind, size, pin: String(pd), length: L, text: `Ø${pd}×${L} pin`, holes: use.map((p) => hole(p, +(pd + 0.1).toFixed(2))) };
    ghost.push({ o: at(0), d: D.toArray(), len: L, r: pd / 2 });
  } else if (kind === 'insert') {
    const [od, insLen] = S.insert, top = last.tin, thick = last.tout - last.tin;
    if (thick < insLen + 1) return E('{part} is {t} mm thick here — an {size} insert needs {need} mm. Use a screw + nut.', { part: asm.partName(last.part), t: fmt(thick), size, need: fmt(insLen + 1) }, stack);
    const L = STD(SCREW_LENGTHS, top + insLen - 0.3);
    if (!L || L < top + 1.5) return E('No standard {size} screw ends in the insert here ({t} mm to it) — use a screw + nut.', { size, t: fmt(top) }, stack);
    plan = { kind, size, length: L, text: `${size}×${L} screw + ${size} insert`, insert: { length: insLen },
      holes: [...use.slice(0, -1).map((p) => hole(p, clear)), hole(last, +(S.insertHole[0] + 0.1).toFixed(2), +(insLen + 0.5).toFixed(2))] };
    ghost.push({ o: at(top), d: D.toArray(), len: insLen, r: od / 2, color: 0xd29922 });
  } else {
    const [s, m] = NUTS[size], need = total + m + 1, L = STD(SCREW_LENGTHS, need, true);
    if (!L) return E('The parts are {t} mm thick — more than the longest {size} screw ({max} mm) holds with its nut.', { t: fmt(total), size, max: SCREW_LENGTHS[SCREW_LENGTHS.length - 1] }, stack);
    plan = { kind: 'nut', size, length: L, text: `${size}×${L} screw + ${size} nut`, nut: { s, m }, holes: use.map((p) => hole(p, clear)) };
    ghost.push({ o: at(total), d: D.toArray(), len: m, r: s / Math.sqrt(3), sides: 6, color: 0xd29922 });
  }
  if (kind !== 'pin') {
    const [dk, k] = S.head;
    ghost.push({ o: at(0), d: D.toArray(), len: plan.length, r: S.d / 2 }, { o: at(0), d: D.clone().negate().toArray(), len: k, r: dk / 2 });
  }
  return { ...plan, stack, total, ghost, o: o.toArray(), d: D.toArray() };
}

const fmt = (v) => (+(+v).toFixed(2)).toString();
