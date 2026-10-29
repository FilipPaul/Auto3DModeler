// 〰 Springs: a placed part that is a spring reaches from where it sits to a face of another part (a piston pressing a
// spring onto a body) — wherever that part goes, the spring is drawn that long: scaled along its axis, its far end on
// that face, its other end where it is. Only the view changes (the parts' places, animations, screenshots): its model
// and its joints stay as they are, the kernel has it at its free length — so collisions between it and the parts it
// is joined to are not counted. Its free length is its modelled length (between its two end faces); its row says free /
// now / compressed and, with a stiffness k (N/mm, one optional input), the force. Plain maths (three.js) and its rows.
//   Assembly JSON: "springs": [{"id": "S1", "part": "I4", "face": "F2:end" (its end that reaches), "onto": "I3",
//     "ontoFace": "F2:start" (the face it reaches), "k": 0.5 (N/mm, optional), "name": "the user's"}]
import * as THREE from 'three';
import { t } from '../i18n.js';

const fmt = (v) => (+(+v).toFixed(2)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

/** A spring part's end face and the end face across it (its own coordinates): {n (out of its end), end, base (points
 *  on the two), free (mm between them)} or null (the face is not flat, or nothing is across it). */
export function springEnds(body, face) {
  const flat = (body?.faces || []).filter((f) => f.type === 'plane' && f.normal);
  const e = flat.filter((f) => f.name === face || (f.names || []).includes(face)).sort((p, q) => q.area - p.area)[0];
  if (!e) return null;
  const n = new THREE.Vector3(...e.normal).normalize(), end = new THREE.Vector3(...e.centroid);
  let base = null, free = 0;
  for (const f of flat) {
    if (new THREE.Vector3(...f.normal).dot(n) > -0.999) continue;
    const d = end.clone().sub(new THREE.Vector3(...f.centroid)).dot(n);
    if (d > free) { free = d; base = new THREE.Vector3(...f.centroid); }
  }
  return base && free > 1e-6 ? { n, end, base, free } : null;
}

/** Where a spring is now -> {free, now (mm from its base to the face it reaches, along its axis), scale (now / free),
 *  compressed (free − now), force (N, with k)} or null (not built, or no end across). */
export function springState(asm, s) {
  const it = asm.inst(s.part), body = asm.bodyOf(it)?.body, ends = body && springEnds(body, s.face);
  if (!ends || !asm.inst(s.onto)) return null;
  let to;
  try { to = asm.worldFace(s.onto, s.ontoFace); } catch { return null; }
  const M = new THREE.Matrix4().fromArray(it.matrix), n = ends.n.clone().applyMatrix3(new THREE.Matrix3().getNormalMatrix(M)).normalize();
  const now = to.centroid.clone().sub(ends.base.clone().applyMatrix4(M)).dot(n), scale = Math.max(0.05, now / ends.free);
  return { free: ends.free, now, scale, compressed: ends.free - now, ...(Number.isFinite(s.k) && s.k > 0 ? { force: s.k * (ends.free - now) } : {}), ends };
}

/** The matrix the spring part `it` is drawn with: its place, scaled along its axis about its base (array of 16), or
 *  null when it is no spring. */
export function springMatrix(asm, it) {
  const s = (asm.doc.springs || []).find((x) => x.part === it.id), st = s && springState(asm, s);
  if (!st || Math.abs(st.scale - 1) < 1e-9) return null;
  const { n, base } = st.ends, k = st.scale - 1;
  const S = new THREE.Matrix4().set( // x + (s − 1)((x − base)·n) n
    1 + k * n.x * n.x, k * n.x * n.y, k * n.x * n.z, 0,
    k * n.y * n.x, 1 + k * n.y * n.y, k * n.y * n.z, 0,
    k * n.z * n.x, k * n.z * n.y, 1 + k * n.z * n.z, 0,
    0, 0, 0, 1);
  const L = new THREE.Matrix4().makeTranslation(base.x, base.y, base.z).multiply(S).multiply(new THREE.Matrix4().makeTranslation(-base.x, -base.y, -base.z));
  return new THREE.Matrix4().fromArray(it.matrix).multiply(L).toArray();
}

/** A spring made: part a's end face ({inst, face}) reaches part b's face — the spring is a's part (or b's, when only
 *  b's is called a spring / pružina). -> the record; throws when a's face has no end across it. */
export function addSpring(asm, a, b, k = null) {
  const looks = (q) => /spring|pru[žz]in/i.test(asm.partName(asm.inst(q.inst)?.part) || '');
  if (!looks(a) && looks(b)) [a, b] = [b, a];
  if (a.inst === b.inst) throw new Error(t('A spring reaches from one part to another.'));
  const name = a.face?.name || a.face;
  if (!springEnds(asm.bodyOf(asm.inst(a.inst))?.body, name)) throw new Error(t('A spring joins a flat end face of the spring (with its other end across it) to the face it pushes on.'));
  const list = asm.doc.springs || [], n = Math.max(0, ...list.map((x) => parseInt(String(x.id).slice(1), 10) || 0)) + 1;
  const old = list.find((x) => x.part === a.inst);
  const rec = { id: old?.id || `S${n}`, part: a.inst, face: name, onto: b.inst, ontoFace: b.face?.name || b.face, ...(Number.isFinite(+k) && +k > 0 ? { k: +k } : old?.k ? { k: old.k } : {}), ...(old?.name ? { name: old.name } : {}) };
  asm.doc.springs = [...list.filter((x) => x !== old), rec]; // (one spring per part: made again, it reaches the new face)
  return rec;
}

/** Do parts x and y overlap only because a spring between them is drawn compressed (a spring and a part it is joined
 *  to, or reaches)? Ids may be "I3/I1" (inside a sub-assembly: its top part counts). */
export function springIgnores(asm, x, y) {
  const top = (id) => String(id).split('/')[0], a = top(x), b = top(y);
  return (asm.doc.springs || []).some((s) => {
    if (s.part !== a && s.part !== b) return false;
    const other = s.part === a ? b : a;
    return other === s.onto || (asm.doc.mates || []).some((m) => (m.move === s.part && m.onto === other) || (m.onto === s.part && m.move === other));
  });
}

/** The springs' rows for a part's panel (or all, id null): free · now · compressed, k (one input) and the force, ✕. */
export function springsHtml(asm, id) {
  const list = (asm.doc.springs || []).filter((s) => asm.inst(s.part) && asm.inst(s.onto) && (id === null || s.part === id || s.onto === id));
  if (!list.length) return '';
  const dbl = esc(t('Double-click: give it your own name'));
  return `<h3>${esc(t('Springs'))}</h3><div class="as-joints">${list.map((s) => {
    const st = springState(asm, s), a = asm.inst(s.part), b = asm.inst(s.onto);
    const state = st ? t2('free {free} mm · now {now} mm · compressed {c} mm', { free: fmt(st.free), now: fmt(st.now), c: fmt(st.compressed) }) : t('its end face is gone');
    return `<div class="as-jrow as-srow ${st ? '' : 'bad'}" data-srow="${s.id}"><span class="as-jt">〰 <span class="as-jname ${s.name ? 'own' : ''}" data-sname="${s.id}" title="${dbl}" ${s.name ? 'data-no-i18n' : ''}>${esc(s.name || t('Spring'))}</span> <i>${s.id}</i></span>
      <span class="as-jw"><b data-no-i18n>${esc(asm.partName(a?.part))}</b> <i>${s.part}</i> → <b data-no-i18n>${esc(asm.partName(b?.part))}</b> <i>${s.onto}</i> · <span class="as-sstate" data-no-i18n>${esc(state)}${st?.force !== undefined ? ` · ${esc(t2('force {f} N', { f: fmt(st.force) }))}` : ''}</span></span>
      <label class="as-jv" title="${esc(t('Its stiffness: how many newtons per mm it is compressed — empty: no force shown'))}">k <input type="number" step="any" min="0" data-sk="${s.id}" value="${s.k ? fmt(s.k) : ''}" placeholder="—"> N/mm</label>
      <span class="as-jbtn"><button class="mini danger" data-sdel="${s.id}" title="${esc(t('Remove this spring (the part stays as it is modelled)'))}">✕</button></span></div>`;
  }).join('')}</div>`;
}

/** The springs' rows bound: k typed, ✕, the name by double-click, hover lights its two faces. */
export function bindSpringRows(asm, box, rename) {
  const rec = (id) => (asm.doc.springs || []).find((s) => s.id === id);
  for (const row of box.querySelectorAll('[data-srow]')) {
    row.addEventListener('mouseenter', () => { asm.hoverJoint = row.dataset.srow; asm.drawMarks(); });
    row.addEventListener('mouseleave', () => { asm.hoverJoint = null; asm.drawMarks(); });
  }
  for (const el of box.querySelectorAll('[data-sk]')) {
    el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
    el.addEventListener('change', () => {
      const s = rec(el.dataset.sk), raw = String(el.value).trim(), v = parseFloat(raw.replace(',', '.'));
      if (!s) return;
      if (!raw || !(v > 0)) delete s.k; else s.k = v;
      asm.commit();
    });
  }
  for (const el of box.querySelectorAll('[data-sdel]')) {
    el.addEventListener('click', () => { asm.doc.springs = (asm.doc.springs || []).filter((s) => s.id !== el.dataset.sdel); if (!asm.doc.springs.length) delete asm.doc.springs; asm.hoverJoint = null; asm.commit(); });
  }
  for (const el of box.querySelectorAll('[data-sname]')) {
    el.addEventListener('dblclick', (ev) => {
      ev.stopPropagation();
      const s = rec(el.dataset.sname);
      if (!s.name) el.textContent = '';
      rename(el, (n) => { const v = String(n || '').trim(); if (v) s.name = v; else delete s.name; asm.commit(); });
    });
  }
}

/** The springs' readouts brought up to date while the parts move (▶, a drag, a slider) — only their text. */
export function updateSpringRows(asm, box) {
  for (const el of box?.querySelectorAll('[data-srow]') || []) {
    const s = (asm.doc.springs || []).find((x) => x.id === el.dataset.srow), st = s && springState(asm, s), out = el.querySelector('.as-sstate');
    if (st && out) out.textContent = `${t2('free {free} mm · now {now} mm · compressed {c} mm', { free: fmt(st.free), now: fmt(st.now), c: fmt(st.compressed) })}${st.force !== undefined ? ` · ${t2('force {f} N', { f: fmt(st.force) })}` : ''}`;
  }
}

/** For the AI (get_assembly `springs`). */
export function springsSummary(asm) {
  return (asm.doc.springs || []).map((s) => {
    const st = springState(asm, s), r = (v) => +v.toFixed(3);
    return { id: s.id, ...(s.name ? { name: s.name } : {}), part: s.part, face: s.face, onto: s.onto, onto_face: s.ontoFace, ...(s.k ? { k_n_per_mm: s.k } : {}),
      ...(st ? { free_mm: r(st.free), now_mm: r(st.now), compressed_mm: r(st.compressed), scale: r(st.scale), ...(st.force !== undefined ? { force_n: r(st.force) } : {}) } : { broken: true }) };
  });
}
