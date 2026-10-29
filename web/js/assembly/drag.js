// A part dragged in the assembly's view: the chosen part moves the way its joints leave free — a turn follows the
// mouse round its axis, a slide along its line — and every part joined to it follows (Assembly.moveFree: the parts on
// it go along, a closed loop is solved). A part of a closed loop drives the loop's driver (mechanism.js).
import * as THREE from 'three';

/** The chosen part dragged in the view the way it can move: a turn follows the mouse round its axis, a slide along
 *  its line; a part of a closed loop drives the loop's driver (the crank turns, wherever on the loop it was grabbed),
 *  the rest follows (Assembly.moveFree). e: the press -> {move(e), end() -> moved?} or null (it cannot move: the view
 *  turns as usual). */
export function startDrag(asm, id, e) {
  const hit = asm.view.ray(e.clientX, e.clientY).intersectObjects(asm.view.meshes || [], false)[0];
  if (!hit || hit.object.userData.inst !== id) return null;
  let part = id, mo = null;
  const m = (asm.mech?.list || []).find((x) => x.parts.includes(id) && x.closed && x.driver && x.parts.length > 1);
  if (m) ({ part, mo } = m.driver);
  else {
    let d = null;
    try { d = asm.motionsOf(id); } catch { d = null; }
    if (d?.count) mo = d.motions.find((q) => q.kind === 'turn' && /:turn$/.test(q.key || '')) || d.motions.find((q) => /:along$/.test(q.key || '')) || d.motions[0];
  }
  if (!mo) return null;
  const P0 = hit.point.clone(), n = mo.dir.clone().normalize(), o = mo.point ? mo.point.clone() : null;
  const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(n, P0), a0 = o ? P0.clone().sub(o).projectOnPlane(n) : new THREE.Vector3();
  let done = 0, prev = 0, turns = 0, moved = false;
  const amountAt = (ev) => {
    const ray = asm.view.ray(ev.clientX, ev.clientY).ray;
    if (mo.kind === 'turn') {
      const q = ray.intersectPlane(plane, new THREE.Vector3());
      if (!q || a0.length() < 1e-6) return null;
      const v = q.sub(o).projectOnPlane(n), raw = (Math.atan2(n.dot(new THREE.Vector3().crossVectors(a0, v)), a0.dot(v)) * 180) / Math.PI;
      if (raw - prev > 180) turns--; else if (raw - prev < -180) turns++; // (round and round: on past ±180°)
      prev = raw;
      return raw + 360 * turns;
    }
    // a slide: where along its line (through the grabbed point) the mouse's ray comes nearest
    const w = ray.origin.clone().sub(P0), b = ray.direction.dot(n), den = 1 - b * b;
    if (den < 1e-6) return null;
    return (n.dot(w) - b * ray.direction.dot(w)) / den;
  };
  return {
    part, mo,
    move(ev) {
      const a = amountAt(ev);
      if (a === null || Math.abs(a - done) < 1e-3) return;
      const lim = asm.limitsOf(asm.inst(mo.via || part), mo);
      let step = a - done;
      if (lim) { const p = asm.motionPos(part, mo); step = Math.max(lim.min, Math.min(lim.max, p + step)) - p; }
      asm.moveFree(part, mo, step, null, false);
      done = a;
      moved = true;
      if (m) asm.mech.mark(asm.mech.list.find((x) => x.key === m.key) || m);
    },
    end() { if (moved) asm.commit(); return moved; },
  };
}
