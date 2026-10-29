// Couplings between motions: ⚙ a gear pair, ⛓ a belt / chain, ▤ a rack and pinion — each one joint with one number
// (the ratio, "převod"). Two parts that each turn (or slide) by their own joints are tied: turning one turns the other
// (applyMates -> followCouplings: the other part is moved by the coupled amount, the parts on it and a closed loop it is
// in follow). A coupling takes one free motion away: the two parts move as one mechanism (mechanism.js).
//   Assembly JSON: "couplings": [{"id": "G1", "type": "gear" | "belt" | "rack", "a": "I2", "aFace": "F2:side:c1",
//     "b": "I3", "bFace": "F2:side:c1", "ratio": 2, "inner": true (a ring gear: the same way round), "flip": true (the
//     other way round), "name": "the user's"}]
//   gear / belt: ratio = turns of a per one turn of b (Ø b / Ø a: "i = 2:1" — b turns half as fast); a gear pair turns
//   opposite ways (an internal gear the same way), a belt the same way
//   rack: a = the pinion (its round face), b = the rack (its flat face); ratio = mm the rack moves per turn (π·Ø)
import * as THREE from 'three';
import { t } from '../i18n.js';
import { motionMatrix } from './dof.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

export const COUPLING_TYPES = {
  gear: { icon: '⚙', name: 'Gear pair', hint: 'Two round faces of two turning parts: turning one turns the other by the ratio (gears in mesh turn opposite ways, a ring gear the same way)' },
  belt: { icon: '⛓', name: 'Belt / chain', hint: 'Two pulleys or sprockets: both turn the same way, by the ratio of their Ø' },
  rack: { icon: '▤', name: 'Rack and pinion', hint: 'A round face of a turning part and a flat face of a sliding part: one turn moves the rack π·Ø' },
};

/** A ratio as "2:1" / "1:2" / "1.5:1" (turns of a per one turn of b). */
export function ratioText(c) {
  if (c.type === 'rack') return t2('{mm} mm per turn', { mm: fmt(c.ratio) });
  const r = +c.ratio || 1;
  return r >= 1 ? `i = ${fmt(r)}:1` : `i = 1:${fmt(1 / r)}`;
}

/** What two picked faces can be coupled by -> [{type, ratio, inner, rank}] (lower rank first): two round faces on
 *  parallel axes apart — a gear pair when they touch (Ø a + Ø b apart, or one inside the other: a ring gear), a belt
 *  when they are further; a round face and a flat face along its axis — a rack and pinion. [] when none fits (a pin in
 *  its hole: one axis). pins: [is a's round face a pin (its material inside), b's] when known — a hole and a pin are a
 *  joint to make (a rod's eye onto a pin), not wheels, unless the hole is a ring gear round the pin. */
export function couplingOptions(fa, fb, pins = null) {
  if (fa.type === 'cylinder' && fb.type === 'cylinder' && fa.axis && fb.axis && fa.radius && fb.radius) {
    const da = fa.axis.d.clone().normalize();
    if (Math.abs(da.dot(fb.axis.d.clone().normalize())) < 0.999) return [];
    const apart = fb.axis.o.clone().sub(fa.axis.o).projectOnPlane(da).length(), ra = fa.radius, rb = fb.radius;
    if (apart < 0.5) return []; // (one axis: concentric, not a pair)
    const tol = Math.max(0.5, 0.05 * (ra + rb)), ratio = +(rb / ra).toFixed(4);
    const outer = Math.abs(apart - (ra + rb)) <= tol, inner = Math.abs(apart - Math.abs(ra - rb)) <= tol && apart < Math.max(ra, rb);
    if (pins && (pins[0] === false || pins[1] === false)) { // (a hole: only a ring gear round the other wheel)
      const ring = pins[ra > rb ? 0 : 1] === false && pins[ra > rb ? 1 : 0] !== false;
      return inner && ring ? [{ type: 'gear', ratio, inner, rank: 0 }] : [];
    }
    if (outer || inner) return [{ type: 'gear', ratio, inner, rank: 0 }, { type: 'belt', ratio, rank: 2 }];
    if (apart > ra + rb) return [{ type: 'belt', ratio, rank: 0 }, { type: 'gear', ratio, rank: 2 }];
    return [{ type: 'gear', ratio, rank: 1 }, { type: 'belt', ratio, rank: 2 }];
  }
  const cyl = fa.type === 'cylinder' ? fa : fb.type === 'cylinder' ? fb : null, pl = cyl === fa ? fb : fa;
  if (!cyl?.axis || !cyl.radius || pl.type !== 'plane' || !pl.normal || (pins && pins[cyl === fa ? 0 : 1] === false)) return []; // (a pinion: a pin, not a hole)
  if (Math.abs(pl.normal.dot(cyl.axis.d.clone().normalize())) > 0.01) return []; // (the flat face must run along the axis)
  const off = Math.abs(cyl.axis.o.clone().sub(pl.centroid).dot(pl.normal));
  return [{ type: 'rack', ratio: +(2 * Math.PI * cyl.radius).toFixed(6), rank: Math.abs(off - cyl.radius) <= Math.max(0.5, 0.05 * cyl.radius) ? 0 : 1 }];
}

/** A coupling made between two picked faces ({inst, face (world)}) of two parts (a rack: the round face is the pinion,
 *  whichever was picked first) -> the record (in asm.doc.couplings; the same two parts coupled already: that one
 *  changed). ratio: its number (default: from the faces' Ø). Throws when the faces do not fit. */
export function addCoupling(asm, qa, qb, type, ratio = null) {
  if (!COUPLING_TYPES[type]) throw new Error(`type is ${Object.keys(COUPLING_TYPES).join(', ')}.`);
  if (type === 'rack' && qa.face.type !== 'cylinder') [qa, qb] = [qb, qa];
  if (qa.inst === qb.inst) throw new Error(t('Couple two different parts.'));
  if (type === 'rack' ? qa.face.type !== 'cylinder' || qb.face.type !== 'plane' : qa.face.type !== 'cylinder' || qb.face.type !== 'cylinder') {
    throw new Error(t(type === 'rack' ? 'A rack and pinion couples a round face (the pinion) and a flat face (the rack).' : 'A gear pair or a belt couples two round faces.'));
  }
  const opt = couplingOptions(qa.face, qb.face).find((o) => o.type === type);
  if (!opt) throw new Error(t(type === 'rack' ? 'The rack\'s flat face must run along the pinion\'s axis.' : 'The two round faces must be on parallel axes, apart.'));
  const r = ratio === null || ratio === undefined || ratio === '' ? opt.ratio : +ratio;
  if (!Number.isFinite(r) || r <= 0) throw new Error(t('The ratio is a number above 0.'));
  const list = asm.doc.couplings || [], same = list.find((c) => (c.a === qa.inst && c.b === qb.inst) || (c.a === qb.inst && c.b === qa.inst));
  const rec = { type, a: qa.inst, aFace: qa.face.name, b: qb.inst, bFace: qb.face.name, ratio: r, ...(opt.inner ? { inner: true } : {}) };
  if (same) {
    for (const k of ['inner', 'flip']) delete same[k];
    return Object.assign(same, rec);
  }
  const n = Math.max(0, ...list.map((c) => parseInt(String(c.id || '').slice(1), 10) || 0)) + 1;
  const c = { id: `G${n}`, ...rec };
  asm.doc.couplings = [...list, c];
  return c;
}

/** The two sides of a coupling as they are placed: {a: {inst, mo}, b: {inst, mo}, ab} — mo: the turn about the round
 *  face's axis (a rack: the slide along it, across the pinion), ab: how much b moves per unit of a (degrees -> degrees,
 *  a rack: degrees -> mm), its sign the way round. Throws when a face is gone. */
export function sidesOf(asm, c) {
  const fa = asm.worldFace(c.a, c.aFace), fb = asm.worldFace(c.b, c.bFace), s = c.flip ? -1 : 1;
  if (!fa.axis) throw new Error(`${c.id}: ${c.aFace} is not round.`);
  const da = fa.axis.d.clone().normalize(), a = { inst: c.a, mo: { kind: 'turn', dir: da, point: fa.axis.o.clone() } };
  if (c.type === 'rack') {
    if (!fb.normal) throw new Error(`${c.id}: ${c.bFace} is not flat.`);
    const n = fb.normal.clone().normalize();
    if (fa.axis.o.clone().sub(fb.centroid).dot(n) < 0) n.negate(); // (from the rack towards the pinion)
    const dir = new THREE.Vector3().crossVectors(da, n.negate()); // (where the pinion's rim goes where it meets the rack)
    if (dir.length() < 1e-6) throw new Error(`${c.id}: the rack runs along the pinion's axis.`);
    return { a, b: { inst: c.b, mo: { kind: 'move', dir: dir.normalize() } }, ab: (s * (+c.ratio || 0)) / 360 };
  }
  if (!fb.axis) throw new Error(`${c.id}: ${c.bFace} is not round.`);
  const db = fb.axis.d.clone().normalize(), same = c.type === 'belt' || c.inner;
  return { a, b: { inst: c.b, mo: { kind: 'turn', dir: db, point: fb.axis.o.clone() } }, ab: ((same ? 1 : -1) * Math.sign(da.dot(db) || 1) * s) / (+c.ratio || 1) };
}

/** How far a part moved from matrix A to B along a motion: a turn about its direction (degrees, −180 … 180), a slide
 *  along it (mm). */
export function deltaOf(mo, A, B) {
  const D = B.clone().multiply(A.clone().invert()), d = mo.dir;
  if (mo.kind === 'move') return new THREE.Vector3().setFromMatrixPosition(B).sub(new THREE.Vector3().setFromMatrixPosition(A)).dot(d);
  const q = new THREE.Quaternion().setFromRotationMatrix(D), deg = (2 * Math.atan2(q.x * d.x + q.y * d.y + q.z * d.z, q.w) * 180) / Math.PI;
  return ((((deg + 180) % 360) + 360) % 360) - 180;
}

/** The part that really moves when part `id` turns / slides by `mo`: itself, or a part it is fixed on (a gear keyed to
 *  a shaft: the shaft) -> its id, or null (held: it cannot move that way). */
export function moverOf(asm, id, mo) {
  for (let k = 0; k < 4 && id; k++) {
    const it = asm.inst(id);
    if (!it || it.fixed) return null;
    const mine = (asm.doc.mates || []).filter((m) => m.move === id && asm.inst(m.onto) && !asm.insideMate(m));
    if (!mine.length) return id; // (not joined: it turns where it is)
    const M = new THREE.Matrix4().fromArray(it.matrix), amt = mo.kind === 'turn' ? 0.02 : 0.05;
    let H;
    try { H = asm.holdPart(id, motionMatrix(mo, amt).multiply(M.clone()), true); } catch { H = M; }
    const want = mo.kind === 'turn' ? (amt * 180) / Math.PI : amt;
    if (Math.abs(deltaOf(mo, M, H) - want) < want * 0.02) return id;
    const on = [...new Set(mine.map((m) => m.onto))];
    if (on.length !== 1) return null;
    id = on[0];
  }
  return null;
}

/** After the parts were placed (applyMates): each coupling whose one side moved moves its other side by the coupled
 *  amount (the parts on it go along, a closed loop it is in follows) — through a whole train, each part once.
 *  before: id -> matrix before; drive: {id, was, mo, amount} (the part moved by hand / a slider: by how much exactly,
 *  so a turn past 180° counts). -> true when a part was moved. */
export function followCouplings(asm, before, drive) {
  const list = (asm.doc.couplings || []).filter((c) => asm.inst(c.a) && asm.inst(c.b));
  if (!list.length) return false;
  const mates = (asm.doc.mates || []).filter((m) => asm.inst(m.move) && asm.inst(m.onto)), Mat = (a) => new THREE.Matrix4().fromArray(a);
  const was = new Map(before);
  if (drive?.was) was.set(drive.id, drive.was);
  const known = new Map(), done = new Set(), stopped = (asm.loops || []).filter((l) => l.stopped).map((l) => l.parts[0]);
  const amountOf = (side) => {
    if (known.has(side.inst)) return known.get(side.inst);
    const mo = drive?.mo;
    if (drive?.id === side.inst && mo && Number.isFinite(drive.amount) && mo.kind === side.mo.kind && Math.abs(mo.dir.clone().normalize().dot(side.mo.dir)) > 0.999) {
      return drive.amount * Math.sign(mo.dir.dot(side.mo.dir)); // (exactly as driven: a turn past 180° too)
    }
    return was.has(side.inst) ? deltaOf(side.mo, Mat(was.get(side.inst)), Mat(asm.inst(side.inst).matrix)) : 0;
  };
  let moved = false;
  for (let pass = 0; pass <= list.length; pass++) {
    let any = false;
    for (const c of list) {
      let S;
      try { S = sidesOf(asm, c); } catch { continue; }
      for (const [p, q, k] of [[S.a, S.b, S.ab], [S.b, S.a, S.ab ? 1 / S.ab : 0]]) {
        if (done.has(q.inst) || !k) continue;
        const dp = amountOf(p);
        if (Math.abs(dp) < 1e-7) continue;
        const want = dp * k, amt = want - amountOf(q);
        done.add(p.inst);
        done.add(q.inst);
        known.set(p.inst, dp);
        known.set(q.inst, want);
        any = true;
        if (Math.abs(amt) < 1e-7) continue;
        const id = moverOf(asm, q.inst, q.mo), it = id && asm.inst(id);
        if (!it) continue;
        const prev = [...it.matrix], snap = new Map(asm.doc.instances.map((x) => [x.id, [...x.matrix]]));
        it.matrix = asm.holdPart(id, motionMatrix(q.mo, q.mo.kind === 'turn' ? (amt * Math.PI) / 180 : amt).multiply(Mat(prev))).toArray();
        asm.placeAll(mates);
        if (asm.closeLoops(snap, { id, was: prev })) asm.placeAll(mates);
        moved = true;
      }
    }
    if (!any) break;
  }
  for (const x of stopped) { const lp = (asm.loops || []).find((l) => l.parts.includes(x)); if (lp) lp.stopped = true; } // (a dead point met before stays known)
  return moved;
}

/** The parts coupled with part `id` (through the whole train) — ids, not itself. */
export function coupledWith(asm, id) {
  const list = asm.doc.couplings || [], seen = new Set([id]), stack = [id];
  while (stack.length) {
    const x = stack.pop();
    for (const c of list) for (const [p, q] of [[c.a, c.b], [c.b, c.a]]) if (p === x && !seen.has(q)) { seen.add(q); stack.push(q); }
  }
  seen.delete(id);
  return [...seen];
}

/** The couplings' rows for a part's panel (or all, id null): its type and name, the two parts, the ratio (one input),
 *  ⇄ the other way round, ✕. */
export function couplingsHtml(asm, id) {
  const list = (asm.doc.couplings || []).filter((c) => id === null || c.a === id || c.b === id);
  if (!list.length) return '';
  const dbl = esc(t('Double-click: give it your own name'));
  return `<h3>${esc(t('Couplings'))}</h3><div class="as-joints">${list.map((c) => {
    const ct = COUPLING_TYPES[c.type] || COUPLING_TYPES.gear, a = asm.inst(c.a), b = asm.inst(c.b), rack = c.type === 'rack';
    return `<div class="as-jrow as-crow" data-crow="${c.id}"><span class="as-jt">${ct.icon} <span class="as-jname ${c.name ? 'own' : ''}" data-cname="${c.id}" title="${dbl}" ${c.name ? 'data-no-i18n' : ''}>${esc(c.name || t(ct.name))}</span> <i>${c.id}</i></span>
      <span class="as-jw"><b data-no-i18n>${esc(asm.partName(a?.part))}</b> <i>${c.a}</i> ↔ <b data-no-i18n>${esc(asm.partName(b?.part))}</b> <i>${c.b}</i> · ${esc(t(rack ? 'it slides as the pinion turns' : c.type === 'belt' || c.inner ? (c.flip ? 'opposite ways' : 'the same way') : c.flip ? 'the same way' : 'opposite ways'))}</span>
      <label class="as-jv" title="${esc(t(rack ? 'How far the rack moves per one turn of the pinion (π·Ø)' : 'Turns of the first part per one turn of the second (Ø second / Ø first) — 2: the second turns half as fast'))}">${esc(t('Ratio'))} <input type="number" step="any" min="0" data-cratio="${c.id}" value="${fmt(c.ratio)}"> ${esc(rack ? t('mm per turn') : ': 1')}</label>
      <span class="as-jbtn"><button class="mini" data-cflip="${c.id}" title="${esc(t('The other way round'))}">⇄</button><button class="mini danger" data-cdel="${c.id}" title="${esc(t('Remove this coupling (the parts stay where they are)'))}">✕</button></span></div>`;
  }).join('')}</div>`;
}

/** The couplings' rows bound: the ratio typed, ⇄, ✕, the name by double-click, hover lights the two faces. */
export function bindCouplingRows(asm, box, rename) {
  const rec = (id) => (asm.doc.couplings || []).find((c) => c.id === id);
  for (const row of box.querySelectorAll('[data-crow]')) {
    row.addEventListener('mouseenter', () => { asm.hoverJoint = row.dataset.crow; asm.drawMarks(); });
    row.addEventListener('mouseleave', () => { asm.hoverJoint = null; asm.drawMarks(); });
  }
  for (const el of box.querySelectorAll('[data-cratio]')) {
    el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
    el.addEventListener('change', () => {
      const c = rec(el.dataset.cratio), v = parseFloat(String(el.value).replace(',', '.'));
      if (!c || !Number.isFinite(v) || v <= 0) { el.value = fmt(c?.ratio || 1); return; }
      c.ratio = v;
      asm.commit();
    });
  }
  for (const el of box.querySelectorAll('[data-cflip]')) el.addEventListener('click', () => { const c = rec(el.dataset.cflip); if (c.flip) delete c.flip; else c.flip = true; asm.commit(); });
  for (const el of box.querySelectorAll('[data-cdel]')) {
    el.addEventListener('click', () => { asm.doc.couplings = (asm.doc.couplings || []).filter((c) => c.id !== el.dataset.cdel); asm.hoverJoint = null; asm.commit(); });
  }
  for (const el of box.querySelectorAll('[data-cname]')) {
    el.addEventListener('dblclick', (ev) => {
      ev.stopPropagation();
      const c = rec(el.dataset.cname);
      if (!c.name) el.textContent = '';
      rename(el, (n) => { const v = String(n || '').trim(); if (v) c.name = v; else delete c.name; asm.commit(); });
    });
  }
}

/** For the AI (get_assembly `couplings`). */
export function couplingsSummary(asm) {
  return (asm.doc.couplings || []).map((c) => ({ id: c.id, type: c.type, ...(c.name ? { name: c.name } : {}), part: c.a, face: c.aFace, onto: c.b, onto_face: c.bFace,
    ratio: c.ratio, ...(c.type === 'rack' ? { unit: 'mm per turn' } : { means: `${c.a} turns ${fmt(c.ratio)}× per turn of ${c.b}` }),
    way: c.type === 'rack' ? undefined : (c.type === 'belt' || !!c.inner) !== !!c.flip ? 'same' : 'opposite' }));
}
