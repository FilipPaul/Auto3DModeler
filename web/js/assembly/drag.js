// A part dragged in the assembly's view: the chosen part moves the way its joints leave free — a turn follows the
// mouse round its axis, a slide along its line — and every part joined to it follows (Assembly.moveFree: the parts on
// it go along, a closed loop is solved, coupled gears turn). Any part of a ⚙ mechanism (two parts or more: a loop, a
// train) drags too, chosen or not: by its own motion when the mechanism can be driven by it (the crank's turn, the
// slider's slide, the rocker's swing: the others follow), else (a rod, a coupler, a part fixed on one) the mechanism's
// driver goes where the grabbed point comes nearest the mouse (seekDrag). A part inside a ⚙ moving sub-assembly (the
// sub-assembly chosen, the part grabbed) moves by its own joints there, in the assembly's flat engine
// (Assembly.flatAsm). A drag starts past SLOP px (less: a click, it chooses) and is one undo step. The cue: over a part
// that drags, the arrow carries a badge with the motion (↻ / ↔ / ⚙), the part and the parts that go with it glow;
// while dragging, the value at the cursor.
import * as THREE from 'three';
import { t } from '../i18n.js';
import { posOf, driveTo, engOf } from './mechanism.js';
import { clampLim } from './dof.js';

const SLOP = 4; // (px the mouse goes before a press drags — as Assembly.bindPointer tells a click)

/** The ⚙ mechanism (two parts or more, driven) part `id` moves with: one of its parts, or a part fixed on one (a weight
 *  on the crank) — or null (a part moving on its own is a mechanism of its own: it drags when chosen, as any part). */
export function mechOf(asm, id, seen = new Set()) {
  if (!id || seen.has(id) || !asm.mech?.list.some((x) => x.parts.length > 1)) return null; // (no mechanism: asked on every hover)
  seen.add(id);
  const m = (asm.mech?.list || []).find((x) => x.parts.includes(id));
  if (m) return m.parts.length > 1 && m.closed && m.driver ? m : null;
  if (asm.inst(id)?.fixed) return null;
  for (const j of asm.doc.mates || []) if (j.move === id) { const on = mechOf(asm, j.onto, seen); if (on) return on; }
  return null;
}

/** How part `id` moves when dragged -> {part, mo, mech, drives, grab} or null (it cannot move: a drag turns the view).
 *  A part of a mechanism (mechOf): its own motion the mechanism can be driven by (drives: the driver's own), else the
 *  driver, sought after the mouse (grab: the part grabbed); else its own free motion (an axis' turn first, then a
 *  slide along it). The press (startDrag) and the cursor's cue (dragCue) both ask this, so they never disagree. */
export function dragPlan(asm, id) {
  const it = asm.inst(id), key = it && `${id}|${it.matrix}|${JSON.stringify(asm.doc.mates || [])}|${JSON.stringify(asm.doc.couplings || [])}|${asm.mech?.list.map((x) => x.key).join(';')}`;
  if (key && asm._dragMemo?.key === key) return asm._dragMemo.plan; // (the cursor asks on every mouse move: once per change)
  const plan = planOf(asm, id);
  asm._dragMemo = key ? { key, plan } : null;
  return plan;
}

/** eng: the assembly, or its flat engine for a part inside a moving sub-assembly (Assembly.flatAsm). */
function planOf(asm, id, eng = asm) {
  let d = null;
  try { d = eng.motionsOf(id); } catch { d = null; }
  const pick = (ms) => ms.find((q) => q.kind === 'turn' && /:turn$/.test(q.key || '')) || ms.find((q) => /:along$/.test(q.key || '')) || ms[0] || null;
  const mk = mechOf(asm, id);
  if (mk) { // (its own motion when the mechanism goes by it — fixed on a part: that one's — else the driver, sought)
    const own = pick((d?.motions || []).filter((q) => mk.drivers.some((x) => x.part === (q.via || id) && x.mo.key === q.key)));
    if (own) return { part: id, mo: own, mech: mk, drives: (own.via || id) === mk.driver.part && own.key === mk.driver.mo.key };
    return { part: mk.driver.part, mo: mk.driver.mo, mech: mk, drives: true, grab: id };
  }
  const mo = d?.count ? pick(d.motions) : null;
  return mo ? { part: id, mo, mech: null, drives: false } : null;
}

/** A press on the view (e) -> the drag of the part under it (startDrag) or null (the view turns): the chosen part, or
 *  any part of a ⚙ mechanism (mechOf). */
export function pressDrag(asm, e) {
  const hit = asm.view.ray(e.clientX, e.clientY).intersectObjects(asm.view.shown(), false)[0], id = hit?.object.userData.inst;
  if (!id || (id !== asm.sel && !mechOf(asm, id))) return null;
  return startDrag(asm, id, e, hit);
}

/** Part `id` dragged in the view the way it can move (dragPlan): a turn follows the mouse round its axis, a slide
 *  along its line (through the grabbed point); the rest follows (Assembly.moveFree; pushed by another part than its
 *  driver, a mechanism stops at the driver's limits); a part of a mechanism with no motion of its own seeks (seekDrag).
 *  Nothing moves until the mouse has gone SLOP px. e: the press (hit: what the ray hit there) ->
 *  {id, part, mo, plan, move(e), end() -> moved?} or null (it cannot move, or the press is not on it: the view turns). */
export function startDrag(asm, id, e, hit = null) {
  hit ||= asm.view.ray(e.clientX, e.clientY).intersectObjects(asm.view.shown(), false)[0];
  if (!hit || hit.object.userData.inst !== id) return null;
  const inner = asm.innerPartAt?.(id, hit), eng = inner?.eng || asm; // (a part moving inside a sub-assembly: "I3/I2", both levels' joints)
  const plan = inner ? planOf(asm, inner.id, eng) : dragPlan(asm, id);
  if (!plan) return null;
  const x0 = e.clientX, y0 = e.clientY;
  let live = false;
  const far = (ev) => live || (live = Math.hypot(ev.clientX - x0, ev.clientY - y0) > SLOP); // (a click is not a drag)
  if (plan.grab) {
    const s = seekDrag(asm, plan, hit.point, inner?.id || id);
    return { id, part: plan.part, mo: plan.mo, plan, move: (ev) => { if (far(ev)) s.move(ev); }, end: () => s.end() };
  }
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
    id, part, mo, plan,
    move(ev) {
      if (!far(ev)) return;
      const a = amountAt(ev);
      if (a === null || Math.abs(a - done) < 1e-3) return;
      const lim = eng.limitsOf(eng.inst(mo.via || part), mo);
      let step = a - done;
      if (lim) { const p = eng.motionPos(part, mo); step = clampLim(lim, p + step) - p; } // (one side open: free that way)
      const m = mk && (asm.mech.list.find((x) => x.key === mk.key) || mk), dl = m && !plan.drives && m.lim ? m.lim : null; // (the slider pushed: the crank's limits hold too)
      const e1 = dl && engOf(asm, m), was = dl && snapOf(e1);
      eng.moveFree(part, mo, step, null, false, !!dl);
      if (dl) {
        const p = posOf(asm, m), q = clampLim(dl, p);
        if (Math.abs(q - p) > 1e-6) { back(e1, was); driveTo(asm, m, q); } else asm.draw(); // (past its stop: the driver at its stop)
      }
      done = a;
      moved = true;
      if (m) asm.mech.mark(m);
    },
    end() { if (moved) eng.commit(); return moved; },
  };
}

/** Where the parts of engine `e` are, to put them back (back). */
const snapOf = (e) => e.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]);
function back(e, snap) { for (const [iid, mat, hang] of snap) { const x = e.inst(iid); if (x) { x.matrix = mat; x.hang = hang; } } }
const wrap = (a) => ((((a + 180) % 360) + 360) % 360) - 180; // (a turn the short way round)
const round360 = (a) => ((a % 360) + 360) % 360;

/** A part of mechanism plan.mech with no motion of its own (a rod, a coupler, a part fixed on one: `grab`) dragged:
 *  the driver goes where the grabbed point P0 (world) comes nearest the mouse. At the first move the driver's travel
 *  is swept once from where it is (quiet; the parts back after): the point's path on screen, a step about every 4° /
 *  1 mm, each way to its limits or a dead point (one branch, as ▶ goes). Each move then takes the mouse's nearest spot
 *  on that path — near where the driver is when that is about as near (the path may cross itself on screen) — and the
 *  driver goes there in steps no longer than the path's (the loop keeps its branch). -> {move(e), end() -> moved?} */
function seekDrag(asm, plan, P0, grab) {
  const key = plan.mech.key, cur = () => asm.mech.list.find((x) => x.key === key) || plan.mech;
  const e0 = engOf(asm, cur()), local = P0.clone().applyMatrix4(new THREE.Matrix4().fromArray(e0.inst(grab).matrix).invert());
  let path = null, at = 0, moved = false;
  const sweep = (m) => {
    const e = engOf(asm, m), snap = snapOf(e), p0 = posOf(asm, m), span = m.full ? 360 : m.max - m.min;
    const n = Math.max(24, Math.min(120, Math.ceil(span / (m.turn ? 4 : 1)))), h = span / n, pts = [];
    const look = (v, k) => { const [x, y] = asm.view.toScreen(local.clone().applyMatrix4(new THREE.Matrix4().fromArray(e.inst(grab).matrix))); pts.push({ v, k, x, y }); };
    try {
      if (m.full) { // (round from where it is: step k at p0 + k·h, the last one next to the first)
        for (let k = 0; k < n; k++) { if (!driveTo(asm, m, round360(p0 + k * h), false, true).stopped) look(p0 + k * h, k); }
      } else {
        for (const dir of [1, -1]) {
          back(e, snap);
          for (let k = dir > 0 ? 0 : 1; ; k++) {
            const v = Math.max(m.min, Math.min(m.max, p0 + dir * k * h)), r = driveTo(asm, m, v, false, true);
            if (r.stopped) break; // (a dead point: no further that way)
            look(r.at, dir * k);
            if (v <= m.min || v >= m.max) break;
          }
        }
        pts.sort((a, b) => a.k - b.k);
      }
    } finally { back(e, snap); e.checkJoints(); }
    return { pts, full: m.full, n, h };
  };
  const off = (v) => (path.full ? Math.abs(wrap(v - at)) : Math.abs(v - at));
  const seek = (cx, cy) => { // the driver's value whose point is nearest the mouse (cx, cy) — near `at` when about as near
    const P = path.pts, cand = P.length === 1 ? [{ v: P[0].v, d: 0 }] : [];
    for (let i = 0; i < P.length; i++) {
      const A = P[i], B = P[i + 1] || (path.full ? P[0] : null), next = B && (B === P[0] ? A.k === path.n - 1 && B.k === 0 : B.k - A.k === 1);
      if (!next) continue; // (a gap: a dead point between)
      const dx = B.x - A.x, dy = B.y - A.y, L = dx * dx + dy * dy, s = L > 1e-9 ? Math.max(0, Math.min(1, ((cx - A.x) * dx + (cy - A.y) * dy) / L)) : 0;
      const vb = B === P[0] ? A.v + path.h : B.v;
      cand.push({ v: A.v + s * (vb - A.v), d: Math.hypot(A.x + s * dx - cx, A.y + s * dy - cy) });
    }
    if (!cand.length) return null;
    const best = cand.reduce((a, b) => (b.d < a.d ? b : a)), here = cand.filter((c) => off(c.v) <= path.h * 6).reduce((a, b) => (!a || b.d < a.d ? b : a), null);
    return (here && here.d <= best.d + 12 ? here : best).v;
  };
  return {
    move(ev) {
      const m = cur();
      if (!path) { path = sweep(m); at = posOf(asm, m); }
      const v = seek(ev.clientX, ev.clientY);
      if (v === null || off(v) < 1e-3) return;
      const span = path.full ? wrap(v - at) : v - at, k = Math.max(1, Math.ceil(Math.abs(span) / path.h));
      for (let i = 1; i <= k; i++) { const w = at + (span * i) / k; driveTo(asm, m, path.full ? round360(w) : w, false, i < k); } // (drawn once, at the end)
      at = path.full ? round360(at + span) : at + span;
      moved = true;
      asm.mech.mark(m);
    },
    end() { if (moved) engOf(asm, cur()).commit(); return moved; },
  };
}

// ------------------------------------------------------------------ the cue: "a drag here moves the part"
// The cursor: the normal arrow (the user still sees where they point) with a round badge at its lower right — the
// panel's colour, an accent ring, a soft shadow — holding the motion's icon drawn like the app's 16 px icons (stroke,
// round joins): ↻ a turn, ↔ a slide (turned along its line as seen on screen), linked joints a mechanism (the others
// follow). While dragging the badge fills with the accent and the icon turns white. 32 px SVG, the hotspot at the
// arrow's tip, a 2× image through image-set (crisp on HiDPI) where the browser takes it; `grab` where SVG cursors are
// not shown. data-cue on the drawing names it (tests).
const ICON = { // (16 × 16, the app's icon grid)
  turn: '<path d="M13.2 8A5.2 5.2 0 1 1 11.6 4.2"/><path d="M12.3 1.3V4.8H8.8"/>',
  slide: '<path d="M2.2 8H13.8"/><path d="M5 5.2 2.2 8 5 10.8M11 5.2 13.8 8 11 10.8"/>',
  mech: '<path d="M3.6 12.2 6.4 4.4 12.6 10"/><circle cx="3.6" cy="12.2" r="1.6" fill="currentColor"/><circle cx="6.4" cy="4.4" r="1.6" fill="currentColor"/><circle cx="12.6" cy="10" r="1.6" fill="currentColor"/>',
};
const ACCENT = '#3b82f6', PANEL = '#1d222a', ICON_OFF = '#7fb2ff', BX = 22.4, BR = 8.8, HOT = '1 1', cache = new Map();
const ARROW = '<path d="M1.5 1.5V17.6L5.4 13.9L8.1 20.2L10.9 19L8.3 12.8H13.8Z" fill="#fff" stroke="#0f1216" stroke-width="1.2" stroke-linejoin="round"/>';
let imageSet; // (does the browser take image-set() in a cursor?)

/** The cursor's drawing (an SVG) for `kind`, the icon turned `deg`, `px` wide (32: 1×, 64: 2×); on: while dragging. */
export function cueSvg(kind, deg = 0, on = false, px = 32) {
  const k = 0.8, col = on ? '#fff' : ICON_OFF;
  const ico = `<g color="${col}" transform="rotate(${deg} ${BX} ${BX}) translate(${BX - 8 * k} ${BX - 8 * k}) scale(${k})" fill="none" stroke="${col}" stroke-width="${(1.5 / k).toFixed(3)}" stroke-linecap="round" stroke-linejoin="round">${ICON[kind]}</g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" data-cue="${kind}${on ? ' on' : ''}" width="${px}" height="${px}" viewBox="0 0 32 32">${ARROW}`
    + `<circle cx="${BX}" cy="${BX + 1}" r="${BR + 0.6}" fill="#000" opacity=".45"/>`
    + `<circle cx="${BX}" cy="${BX}" r="${BR}" fill="${on ? ACCENT : PANEL}" stroke="${on ? '#a9c9ff' : ACCENT}" stroke-width="1.2"/>${ico}</svg>`;
}

/** The CSS cursor for a drag of `kind` ('turn' | 'slide' | 'mech'), a slide's arrow turned `deg` on screen; on: while
 *  dragging. */
export function moveCursor(kind, deg = 0, on = false) {
  const key = `${kind}|${deg}|${on}`;
  if (!cache.has(key)) {
    const url = (px) => `url("data:image/svg+xml,${encodeURIComponent(cueSvg(kind, deg, on, px))}")`;
    imageSet ??= typeof CSS !== 'undefined' && CSS.supports('cursor', 'image-set(url("a.svg") 1x, url("b.svg") 2x) 1 1, grab');
    const img = imageSet ? `image-set(${url(32)} 1x, ${url(64)} 2x)` : url(32);
    cache.set(key, `${img} ${HOT}, ${on ? 'grabbing' : 'grab'}`);
  }
  return cache.get(key);
}

/** The parts a drag of part `id` moves (dragPlan): its mechanism's (and it), else it and the parts joined onto it. */
export function movingParts(asm, id, plan = dragPlan(asm, id)) {
  if (!plan) return [];
  if (plan.mech) return [...new Set([...plan.mech.parts, id])];
  const out = new Set([plan.mo.via || id, id]);
  for (let grew = true; grew;) {
    grew = false;
    for (const m of asm.doc.mates || []) if (out.has(m.onto) && !out.has(m.move)) { out.add(m.move); grew = true; }
  }
  return [...out];
}

/** The cue over part `inst` (the mouse's) -> {cursor, kind, parts (the ones that move), plan} or null (it does not
 *  drag there: the normal cursor, the view turns). The chosen part and any part of a ⚙ mechanism drag (pressDrag), so
 *  they get the cue. */
export function dragCue(asm, inst, on = false) {
  if (!inst || asm.sel2 || (inst !== asm.sel && !mechOf(asm, inst))) return null;
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
  el.style.left = `${ev.clientX - r.left + 34}px`; // (right of the cursor's badge)
  el.style.top = `${ev.clientY - r.top + 13}px`;
}

/** The first-time hint for the cue ("Drag — moves the part / the mechanism") — until the user has dragged once. */
export function firstTip(cue) {
  try { if (localStorage.getItem(TIP_KEY)) return ''; } catch { return ''; }
  return t(cue.kind === 'mech' ? 'Drag — moves the mechanism' : 'Drag — moves the part');
}
export function tipSeen() { try { localStorage.setItem(TIP_KEY, '1'); } catch { /* private window */ } }
