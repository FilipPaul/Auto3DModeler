// "One joint is missing": parts that almost make a closed loop — a chain from the base through a crank and a rod to a
// slider that is held elsewhere — where one more pin in a hole would close it. Found by geometry: a free hole of one
// part and a free pin of another with a matching Ø (the pin as big as the hole, or up to 0.6 mm smaller), their axes
// parallel and near (within the moving part's size), both parts already joined and still able to move, and not in
// one loop together. ⚙ Mechanism (or the part panel) shows one quiet line and ➕ Add joint. Plain geometry, no UI.
import * as THREE from 'three';

const b64 = (s, T) => { // (a binary answer's arrays come as typed arrays already: modeler/packed.js)
  if (typeof s !== 'string') return s;
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};

/** Is a round face of a body a pin (the material inside it) rather than a hole? From its triangles' facing: outward
 *  from the axis = a pin. Kept on the body. */
export function isPin(body, name) {
  body._pins = body._pins || {};
  if (name in body._pins) return body._pins[name];
  body._P = body._P || b64(body.positions, Float32Array);
  body._F = body._F || b64(body.face_ids, Uint32Array);
  const f = body.faces.find((x) => x.name === name && x.axis);
  if (!f) return (body._pins[name] = null);
  const ids = new Set(body.faces.filter((x) => x.name === name).map((x) => x.id)), o = new THREE.Vector3(...f.axis.o), d = new THREE.Vector3(...f.axis.d).normalize();
  const P = body._P, a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3(), r = new THREE.Vector3();
  let out = 0;
  for (let tr = 0; tr < body._F.length; tr++) {
    if (!ids.has(body._F[tr])) continue;
    const k = tr * 9;
    a.set(P[k], P[k + 1], P[k + 2]);
    b.set(P[k + 3], P[k + 4], P[k + 5]);
    c.set(P[k + 6], P[k + 7], P[k + 8]);
    n.subVectors(b, a).cross(c.clone().sub(a)); // (the triangle's outward side: counter-clockwise)
    r.copy(a).add(b).add(c).divideScalar(3).sub(o).projectOnPlane(d); // (from the axis to the triangle)
    out += Math.sign(n.dot(r));
  }
  return (body._pins[name] = out === 0 ? null : out > 0);
}

/** The joint that would close a loop in assembly `asm`, or null: {move: {inst, face}, onto: {inst, face}, hole: {inst,
 *  name, d}, pin: {inst, name, d}} — move/onto as the joint goes (world faces), hole/pin to name them. */
export function missingJoint(asm) {
  const mates = (asm.doc.mates || []).filter((m) => !asm.insideMate(m));
  if (mates.length < 2) return null;
  const used = new Set(mates.filter((m) => m.type === 'axis').flatMap((m) => [`${m.move}|${m.face}`, `${m.onto}|${m.ontoFace}`]));
  const moves = (id) => { const it = asm.inst(id); if (!it || it.fixed || it.fastener) return false; try { const d = asm.motionsOf(id); return !!d?.count || !!asm.mechanismOf(id); } catch { return false; } };
  const holes = [], pins = [];
  for (const it of asm.doc.instances) {
    if (it.fastener || !mates.some((m) => m.move === it.id) || !moves(it.id)) continue; // (joined and still free to move)
    const body = asm.bodyOf(it)?.body;
    for (const name of new Set((body?.faces || []).filter((f) => f.type === 'cylinder' && f.radius && f.axis).map((f) => f.name))) {
      if (used.has(`${it.id}|${name}`)) continue;
      const pin = isPin(body, name);
      if (pin === null) continue;
      let w;
      try { w = asm.worldFace(it.id, name); } catch { continue; }
      (pin ? pins : holes).push({ inst: it.id, name, face: w, d: 2 * w.radius, size: body.bbox ? Math.hypot(body.bbox[3] - body.bbox[0], body.bbox[4] - body.bbox[1], body.bbox[5] - body.bbox[2]) : 100 });
    }
  }
  const hangsOn = (x, y) => { // does part x hang on part y (through others)?
    const seen = new Set(), stack = [x];
    while (stack.length) {
      const z = stack.pop();
      if (z === y) return true;
      if (seen.has(z)) continue;
      seen.add(z);
      stack.push(...mates.filter((m) => m.move === z).map((m) => m.onto));
    }
    return false;
  };
  const loopOf = (x) => (asm.loops || []).find((l) => l.parts.includes(x))?.parts.join(',') || x;
  let best = null;
  for (const h of holes) {
    for (const p of pins) {
      if (h.inst === p.inst || loopOf(h.inst) === loopOf(p.inst) || p.d > h.d + 1e-3 || h.d - p.d > 0.6) continue;
      const dh = h.face.axis.d, dp = p.face.axis.d;
      if (Math.abs(dh.dot(dp)) < 0.995) continue;
      const apart = p.face.axis.o.clone().sub(h.face.axis.o).projectOnPlane(dh).length();
      // the joint goes from the hole's part (the rod: its first eye joined already) unless the pin's part may not hang on it
      const [mv, on] = !hangsOn(p.inst, h.inst) ? [h, p] : !hangsOn(h.inst, p.inst) ? [p, h] : [null, null];
      if (!mv || apart > Math.max(mv.size, on.size)) continue;
      if (!best || apart < best.apart) best = { apart, move: { inst: mv.inst, face: mv.face }, onto: { inst: on.inst, face: on.face }, hole: h, pin: p };
    }
  }
  return best;
}
