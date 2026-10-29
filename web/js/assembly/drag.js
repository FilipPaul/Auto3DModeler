// A part dragged in the assembly's view: the chosen part moves the way its joints leave free — a turn follows the
// mouse round its axis, a slide along its line — and every part joined to it follows (Assembly.moveFree: the parts on
// it go along, a closed loop is solved, coupled gears turn). A part of a closed loop drives the loop's driver
// (mechanism.js); a gear of a train turns by its own axis. A part inside a ⚙ moving sub-assembly (the sub-assembly
// chosen, the part grabbed) moves by its own joints there, in the assembly's flat engine (Assembly.flatAsm). The cue:
// over the chosen part that can move, the cursor is the motion's symbol (↻ / ↔ / ⚙), the part and the parts that go
// with it glow; while dragging, the value at the cursor.
import * as THREE from 'three';
import { t } from '../i18n.js';
import { posOf } from './mechanism.js';

/** How the chosen part `id` moves when dragged -> {part, mo, mech} or null (it cannot move: a drag turns the view).
 *  A part of a closed loop drives the loop's driver; a gear of a train its own turn (mech: the mechanism it is in, the
 *  others follow); else its own free motion (an axis' turn first, then a slide along it). The press (startDrag) and
 *  the cursor's cue (dragCue) both ask this, so they never disagree. */
export function dragPlan(asm, id) {
  const it = asm.inst(id), key = it && `${id}|${it.matrix}|${JSON.stringify(asm.doc.mates || [])}|${JSON.stringify(asm.doc.couplings || [])}|${asm.mech?.list.map((x) => x.key).join(';')}`;
  if (key && asm._dragMemo?.key === key) return asm._dragMemo.plan; // (the cursor asks on every mouse move: once per change)
  const plan = planOf(asm, id);
  asm._dragMemo = key ? { key, plan } : null;
  return plan;
}

/** eng: the assembly, or its flat engine for a part inside a moving sub-assembly (Assembly.flatAsm). */
function planOf(asm, id, eng = asm) {
  const mk = (asm.mech?.list || []).find((x) => x.parts.includes(id) && x.closed && x.driver && x.parts.length > 1) || null;
  const m = mk && (!mk.train || (eng.loops || []).some((l) => l.parts.includes(id))) ? mk : null; // (⚙ a gear of a train: its own turn, the others follow)
  if (m) return { part: m.driver.part, mo: m.driver.mo, mech: mk, drives: true };
  let d = null;
  try { d = eng.motionsOf(id); } catch { d = null; }
  const mo = d?.count ? d.motions.find((q) => q.kind === 'turn' && /:turn$/.test(q.key || '')) || d.motions.find((q) => /:along$/.test(q.key || '')) || d.motions[0] : null;
  return mo ? { part: id, mo, mech: mk, drives: false } : null;
}

/** The chosen part dragged in the view the way it can move (dragPlan): a turn follows the mouse round its axis, a
 *  slide along its line (through the grabbed point); the rest follows (Assembly.moveFree). e: the press ->
 *  {part, mo, move(e), end() -> moved?} or null (it cannot move, or the press is not on it: the view turns). */
export function startDrag(asm, id, e) {
  const hit = asm.view.ray(e.clientX, e.clientY).intersectObjects(asm.view.meshes || [], false)[0];
  if (!hit || hit.object.userData.inst !== id) return null;
  const inner = asm.innerPartAt?.(id, hit), eng = inner?.eng || asm; // (a part moving inside a sub-assembly: "I3/I2", both levels' joints)
  const plan = inner ? planOf(asm, inner.id, eng) : dragPlan(asm, id);
  if (!plan) return null;
  const { part, mo, mech: mk } = plan;
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
    part, mo, plan,
    move(ev) {
      const a = amountAt(ev);
      if (a === null || Math.abs(a - done) < 1e-3) return;
      const lim = eng.limitsOf(eng.inst(mo.via || part), mo);
      let step = a - done;
      if (lim) { const p = eng.motionPos(part, mo); step = Math.max(lim.min, Math.min(lim.max, p + step)) - p; }
      eng.moveFree(part, mo, step, null, false);
      done = a;
      moved = true;
      if (mk) asm.mech.mark(asm.mech.list.find((x) => x.key === mk.key) || mk);
    },
    end() { if (moved) eng.commit(); return moved; },
  };
}

// ------------------------------------------------------------------ the cue: "a drag here moves the part"
// The cursor: the motion's symbol, 32 px — the accent colour on a white outline (it reads on the dark background and
// on light parts), ↻ a turn, ↔ a slide (turned along its line as seen on screen), ⚙ with an arrow a mechanism (the
// others follow); while dragging, white on an accent disc. `grab` where SVG cursors are not shown.
const ICON = {
  turn: '<path d="M18.4 8A7.5 7.5 0 1 0 19.5 13.5"/><path d="M19.5 3.5V8.5H14.5"/>',
  slide: '<path d="M3.5 12H20.5"/><path d="M7.5 7.5L3 12L7.5 16.5"/><path d="M16.5 7.5L21 12L16.5 16.5"/>',
  mech: '<circle cx="9.5" cy="9.5" r="3"/><path d="M9.5 2.5V4.5M9.5 14.5V16.5M2.5 9.5H4.5M14.5 9.5H16.5M4.6 4.6L6 6M13 13L14.4 14.4M4.6 14.4L6 13M13 6L14.4 4.6"/><path d="M21 13.5A7.5 7.5 0 0 1 13.5 21"/><path d="M21 18.5V13.5H16"/>',
};
const ACCENT = '#3b82f6', cache = new Map();

/** The CSS cursor for a drag of `kind` ('turn' | 'slide' | 'mech'), a slide's arrow turned `deg` on screen; on: while
 *  dragging. */
export function moveCursor(kind, deg = 0, on = false) {
  const key = `${kind}|${deg}|${on}`;
  if (!cache.has(key)) {
    const g = `<g transform="rotate(${deg} 12 12) translate(1.32 1.32) scale(.89)">${ICON[kind]}</g>`; // (its outline inside the 24 × 24)
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">${on
      ? `<circle cx="12" cy="12" r="11.3" fill="${ACCENT}" stroke="#fff" stroke-width="1.2"/><g stroke="#fff" stroke-width="2.2">${g}</g>`
      : `<g stroke="#0f1216" stroke-opacity=".6" stroke-width="6.4">${g}</g><g stroke="#fff" stroke-width="4.6">${g}</g><g stroke="${ACCENT}" stroke-width="2.4">${g}</g>`}</svg>`;
    cache.set(key, `url("data:image/svg+xml,${encodeURIComponent(svg)}") 16 16, ${on ? 'grabbing' : 'grab'}`);
  }
  return cache.get(key);
}

/** The parts a drag of the chosen part `id` moves (dragPlan): its mechanism's, else it and the parts joined onto it. */
export function movingParts(asm, id, plan = dragPlan(asm, id)) {
  if (!plan) return [];
  if (plan.mech) return [...plan.mech.parts];
  const out = new Set([plan.mo.via || id, id]);
  for (let grew = true; grew;) {
    grew = false;
    for (const m of asm.doc.mates || []) if (out.has(m.onto) && !out.has(m.move)) { out.add(m.move); grew = true; }
  }
  return [...out];
}

/** The cue over part `inst` (the mouse's) -> {cursor, kind, parts (the ones that move), plan} or null (it does not
 *  drag there: the normal cursor, the view turns). Only the chosen part drags (startDrag), so only it gets the cue. */
export function dragCue(asm, inst, on = false) {
  if (!inst || inst !== asm.sel || asm.sel2) return null;
  const plan = dragPlan(asm, inst);
  if (!plan) return null;
  const kind = plan.mech ? 'mech' : plan.mo.kind === 'turn' ? 'turn' : 'slide';
  let deg = 0;
  if (kind === 'slide') { // (the arrow along the slide as it looks on screen, in 15° steps)
    try {
      const it = asm.inst(inst), b = asm.bodyOf(it)?.body?.bbox, M = new THREE.Matrix4().fromArray(it.matrix);
      const c = b ? new THREE.Vector3((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2).applyMatrix4(M) : new THREE.Vector3();
      const [x0, y0] = asm.view.toScreen(c.clone()), [x1, y1] = asm.view.toScreen(c.clone().add(plan.mo.dir.clone().normalize().multiplyScalar(10)));
      deg = (((Math.round((Math.atan2(y1 - y0, x1 - x0) * 180) / Math.PI / 15) * 15) % 180) + 180) % 180;
    } catch { deg = 0; }
  }
  return { cursor: moveCursor(kind, deg, on), kind, parts: movingParts(asm, inst, plan), plan };
}

/** Where the dragged motion is, as the readout says it: "↻ 37°", "↔ 12.5 mm" (a mechanism: its driver, as its slider). */
export function dragValue(asm, plan) {
  let v;
  try {
    const m = plan.mech && plan.drives ? asm.mech.list.find((x) => x.key === plan.mech.key) || plan.mech : null;
    v = m ? posOf(asm, m) : asm.motionPos(plan.part, plan.mo);
  } catch { return ''; }
  const turn = plan.mo.kind === 'turn';
  return `${turn ? '↻' : '↔'} ${(+v.toFixed(turn ? 0 : 1)).toLocaleString(document.documentElement.lang || undefined)}${turn ? '°' : ' mm'}`;
}

const TIP_KEY = 'a3d.dragTip';
/** The small label at the cursor (`viewport`'s .as-dragtip): the readout while dragging, or — the first time the cue
 *  shows — what a drag does. text '' hides it. */
export function cueLabel(viewport, ev, text, strong = false) {
  let el = viewport.querySelector(':scope > .as-dragtip');
  if (!text) { el?.remove(); return; }
  if (!el) { el = document.createElement('div'); el.className = 'as-dragtip'; el.dataset.noI18n = ''; viewport.appendChild(el); }
  const r = viewport.getBoundingClientRect();
  el.classList.toggle('strong', strong);
  el.textContent = text;
  el.style.left = `${ev.clientX - r.left + 20}px`;
  el.style.top = `${ev.clientY - r.top + 20}px`;
}

/** The first-time hint for the cue ("Drag — moves the part / the mechanism") — until the user has dragged once. */
export function firstTip(cue) {
  try { if (localStorage.getItem(TIP_KEY)) return ''; } catch { return ''; }
  return t(cue.kind === 'mech' ? 'Drag — moves the mechanism' : 'Drag — moves the part');
}
export function tipSeen() { try { localStorage.setItem(TIP_KEY, '1'); } catch { /* private window */ } }
