// ⛓ Energy chains in the assembly: a chain from the library (igus e-chain) goes in as its first link — a placed part
// like any other, at the chain's fixed end (move it, join it to the machine's frame) — and the rest of its links are
// drawn on from there as a U (library/cableparts.js chainPath): the lower run, the 180° bend of radius R, the upper run
// to the moving end. The moving end goes by its travel (a slider), or with a part it is fixed to (a carriage): as
// that part moves along the chain's runs (dragged, its slide, ▶ a mechanism), the moving end goes along and the U
// rolls. The parts list counts the chain's links (igus orders by the link). Only the view draws the other links (one
// instanced mesh): the kernel, collisions and exports have the first link.
//   Assembly JSON: "chains": [{"id": "C1", "part": "I4" (its first link, at the fixed end), "links": 26,
//     "dims": {"pitch", "Bi", "Ba", "hi", "ha", "R", "dmax", "pn", "series"} (as the library gives them),
//     "travel": 0 (mm along the runs from above the fixed end), "follow": {"inst": "I3", "base": [x, y, z] (that
//     part's place when joined), "at": the travel then} (it moves with I3), "name": "the user's"}]
import * as THREE from 'three';
import { t } from '../i18n.js';
import { chainPath, travelRange, defaultLinks, chainOf as chainNumbers } from '../library/cableparts.js';

const fmt = (v) => (+(+v).toFixed(1)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

/** The chain whose first link is placed part `id` (or whose id is `id`). */
export const chainOf = (asm, id) => (asm.doc.chains || []).find((c) => c.part === id || c.id === id) || null;

/** ⛓ A chain made of placed part `inst` (its first link) -> the record. dims: the library's numbers (chainOf). */
export function addChain(asm, inst, dims, links = null) {
  const list = asm.doc.chains || [], n = Math.max(0, ...list.map((x) => parseInt(String(x.id).slice(1), 10) || 0)) + 1;
  const { links: n0, matrix, ...d } = dims; // (its own place is its first link's)
  const rec = { id: `C${n}`, part: inst, links: Math.max(2, links || n0 || defaultLinks(d)), dims: d, travel: 0 };
  asm.doc.chains = [...list.filter((x) => x.part !== inst), rec];
  return rec;
}

/** A library part just put in (placed part `inst`, its data with `library`): an energy chain of the library (kind
 *  "chain") becomes a chain, laid out from there -> the record, or null (not a chain). One undo step with the insert. */
export function libraryChain(asm, inst, data, items) {
  const lib = data?.library, item = lib && (items || []).find((x) => x.id === lib.id);
  if (!item || item.kind !== 'chain' || !item.chain || !asm.inst(inst)) return null;
  const rec = addChain(asm, inst, chainNumbers(item, lib.size, lib.length));
  asm.commit();
  drawChains(asm);
  asm.view?.fit(); // (the whole U in the view, not only its first link)
  return rec;
}

/** The chain's numbers now: its dims, its links and its first link's place (the fixed end). */
const numbers = (asm, rec) => ({ ...rec.dims, links: rec.links, matrix: asm.inst(rec.part)?.matrix });

/** Where its moving end is (mm along the runs from above the fixed end): its own travel, or — moving with a part —
 *  the travel when joined plus how far that part has gone along the runs since. */
export function travelOf(asm, rec) {
  const f = rec.follow, it = f && asm.inst(f.inst), me = asm.inst(rec.part);
  if (!it || !me) return +rec.travel || 0;
  const x = new THREE.Vector3(1, 0, 0).transformDirection(new THREE.Matrix4().fromArray(me.matrix));
  const now = new THREE.Vector3().setFromMatrixPosition(new THREE.Matrix4().fromArray(it.matrix));
  return (+f.at || 0) + now.sub(new THREE.Vector3(...f.base)).dot(x);
}

/** A chain laid out now, in the world (chainPath) -> its path or null (its first link is gone). */
export function chainNow(asm, rec) {
  if (!asm.inst(rec.part)) return null;
  return chainPath(numbers(asm, rec), travelOf(asm, rec));
}

/** For the harness (a cable routed through the chain): the chain `id` (C… or its first link's I…) laid out now ->
 *  {points (world), length, fixed, moving, pointAt(s)} or null. */
export const chainRoute = (asm, id) => { const rec = chainOf(asm, id); return rec ? chainNow(asm, rec) : null; };

/** Its moving end goes with part `inst` from now on (null: by its own travel again — kept where it is). */
export function followPart(asm, rec, inst) {
  const at = travelOf(asm, rec), it = inst && asm.inst(inst);
  if (!it) { delete rec.follow; rec.travel = +at.toFixed(3); return; }
  rec.follow = { inst, base: new THREE.Vector3().setFromMatrixPosition(new THREE.Matrix4().fromArray(it.matrix)).toArray().map((v) => +v.toFixed(4)), at: +at.toFixed(3) };
}

// ------------------------------------------------------------------ drawing
/** A link as the view draws it: its outer box Ba × ha with the Bi × hi opening through it, x 0…pitch. */
function linkGeometry(d) {
  const L = d.pitch - Math.min(0.4, d.pitch * 0.02), wall = (d.Ba - d.Bi) / 2, deck = (d.ha - d.hi) / 2; // (a hair apart: the links read as links)
  const parts = [[L, d.Ba, deck, 0, d.hi / 2 + deck / 2], [L, d.Ba, deck, 0, -d.hi / 2 - deck / 2], [L, wall, d.hi, d.Bi / 2 + wall / 2, 0], [L, wall, d.hi, -d.Bi / 2 - wall / 2, 0]];
  const pos = [], nor = [];
  for (const [x, y, z, cy, cz] of parts) {
    const g = new THREE.BoxGeometry(x, y, z).translate(L / 2, cy, cz).toNonIndexed();
    pos.push(...g.attributes.position.array);
    nor.push(...g.attributes.normal.array);
    g.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  return g;
}

/** Every chain drawn: its links from the second on, as laid out now (made again only when something changed). */
export function drawChains(asm) {
  const v = asm.view;
  if (!v) return;
  if (!asm.chainGroup) { asm.chainGroup = new THREE.Group(); asm.chainGroup.name = 'chains'; v.scene.add(asm.chainGroup); asm.chainBuilt = new Map(); }
  const seen = new Set();
  for (const rec of asm.doc.chains || []) {
    const it = asm.inst(rec.part);
    if (!it) continue;
    seen.add(rec.id);
    const travel = travelOf(asm, rec), sel = asm.sel === rec.part;
    const key = JSON.stringify([rec.dims, rec.links, it.matrix, +travel.toFixed(3), sel, v.clip?.length || 0]);
    const was = asm.chainBuilt.get(rec.id);
    if (was?.key === key) continue;
    if (was) { asm.chainGroup.remove(was.mesh); was.mesh.geometry.dispose(); was.mesh.material.dispose(); }
    const path = chainPath(numbers(asm, rec), travel), n = Math.max(0, rec.links - 1);
    const mat = new THREE.MeshStandardMaterial({ color: path.ok ? 0x3a3d42 : 0x8a2b2b, roughness: 0.6, metalness: 0.05, emissive: sel ? 0x0e2a4a : 0x000000, clippingPlanes: v.clip || [] });
    const mesh = new THREE.InstancedMesh(linkGeometry(rec.dims), mat, Math.max(1, n));
    mesh.count = n;
    const y = new THREE.Vector3(0, 1, 0).transformDirection(new THREE.Matrix4().fromArray(it.matrix)); // (across the chain: the same in the bend)
    path.links.slice(1).forEach((l, k) => {
      const a = new THREE.Vector3(...l.a), x = new THREE.Vector3(...l.b).sub(a).normalize(); // (a link from pin to pin)
      mesh.setMatrixAt(k, new THREE.Matrix4().makeBasis(x, y, x.clone().cross(y)).setPosition(a));
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.userData.chain = rec.id;
    asm.chainGroup.add(mesh);
    asm.chainBuilt.set(rec.id, { key, mesh });
  }
  for (const [id, b] of asm.chainBuilt) {
    if (seen.has(id)) continue;
    asm.chainGroup.remove(b.mesh); b.mesh.geometry.dispose(); b.mesh.material.dispose();
    asm.chainBuilt.delete(id);
  }
  v.invalidate();
}

// ------------------------------------------------------------------ the panel
/** The chain's rows in its first link's panel: links (= its length), the travel of the moving end (a slider within
 *  its range), the part it moves with, ✕ (a plain link again). */
export function chainsHtml(asm, id) {
  const rec = (asm.doc.chains || []).find((c) => c.part === id);
  if (!rec) return '';
  const d = rec.dims, r = travelRange({ ...d, links: rec.links }), travel = travelOf(asm, rec), path = chainNow(asm, rec);
  const others = asm.doc.instances.filter((i) => i.id !== rec.part);
  return `<h3>⛓ ${esc(t('Energy chain'))}</h3><div class="as-joints as-chain" data-chain="${rec.id}">
    <p class="hint" data-no-i18n>${esc(t2('{pn}: {n} links = {L} mm · Bi {Bi} × hi {hi} · R {R} · cables up to Ø{dmax}', { pn: d.pn || d.series, n: rec.links, L: fmt(rec.links * d.pitch), Bi: fmt(d.Bi), hi: fmt(d.hi), R: fmt(d.R), dmax: fmt(d.dmax) }))}</p>
    <label class="as-jv" title="${esc(t('How many links: the chain\'s length (igus orders by the link)'))}">${esc(t('Links'))} <input type="number" min="2" step="1" data-chlinks value="${rec.links}"></label>
    <label class="as-jv as-chtravel" title="${esc(t('Where the moving end is: mm along the runs from above the fixed end'))}">${esc(t('Travel'))}
      <input type="range" data-chtravel min="${Math.ceil(r.min)}" max="${Math.floor(r.max)}" step="1" value="${fmt(travel)}" ${rec.follow ? 'disabled' : ''}>
      <span class="as-chtv" data-no-i18n>${fmt(travel)} mm</span></label>
    <label class="as-jv" title="${esc(t('The part its moving end is fixed to: as it moves, the chain rolls along'))}">${esc(t('Moves with'))}
      <select data-chfollow><option value="">${esc(t('— its own travel'))}</option>${others.map((i) => `<option value="${i.id}" ${rec.follow?.inst === i.id ? 'selected' : ''} data-no-i18n>${esc(asm.partName(i.part))} ${i.id}</option>`).join('')}</select></label>
    ${path && !path.ok ? `<p class="hint bad">${esc(t('⚠ The moving end is past the chain\'s reach — add links.'))}</p>` : ''}
    <span class="as-jbtn"><button class="mini danger" data-chdel title="${esc(t('Not a chain any more: only this link stays'))}">✕</button></span></div>`;
}

/** The chain's rows bound: links typed, the travel slid (drawn as it goes), the part it moves with, ✕. */
export function bindChainRows(asm, box) {
  const row = box.querySelector('[data-chain]'), rec = row && chainOf(asm, row.dataset.chain);
  if (!rec) return;
  const links = row.querySelector('[data-chlinks]'), slider = row.querySelector('[data-chtravel]'), out = row.querySelector('.as-chtv');
  links.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') links.blur(); });
  links.addEventListener('change', () => { const n = parseInt(links.value, 10); if (n >= 2) { rec.links = n; asm.commit(); } });
  slider.addEventListener('input', () => { rec.travel = +slider.value; out.textContent = `${fmt(rec.travel)} mm`; drawChains(asm); });
  slider.addEventListener('change', () => { rec.travel = +slider.value; asm.commit(); });
  row.querySelector('[data-chfollow]').addEventListener('change', (ev) => { followPart(asm, rec, ev.target.value || null); asm.commit(); });
  row.querySelector('[data-chdel]').addEventListener('click', () => { asm.doc.chains = asm.doc.chains.filter((c) => c !== rec); if (!asm.doc.chains.length) delete asm.doc.chains; asm.commit(); });
}

/** The chains whose first link is gone are dropped (a part taken out). */
export function tidyChains(asm) {
  if (!asm.doc.chains) return;
  asm.doc.chains = asm.doc.chains.filter((c) => asm.inst(c.part));
  for (const c of asm.doc.chains) if (c.follow && !asm.inst(c.follow.inst)) followPart(asm, c, null);
  if (!asm.doc.chains.length) delete asm.doc.chains;
}

/** For the AI (get_assembly `chains`). */
export function chainsSummary(asm) {
  return (asm.doc.chains || []).map((c) => {
    const p = chainNow(asm, c), r3 = (v) => +(+v).toFixed(3), d = c.dims;
    return { id: c.id, ...(c.name ? { name: c.name } : {}), first_link: c.part, pn: d.pn, links: c.links, length_mm: r3(c.links * d.pitch), pitch_mm: d.pitch, inner_mm: [d.Bi, d.hi], outer_mm: [d.Ba, d.ha], bend_radius_mm: d.R, max_cable_d_mm: d.dmax,
      travel_mm: r3(travelOf(asm, c)), ...(c.follow ? { moves_with: c.follow.inst } : {}),
      ...(p ? { reach_ok: p.ok, fixed_end: p.fixed.o.map(r3), moving_end: p.moving.o.map(r3), lower_run_mm: r3(p.lower), upper_run_mm: r3(p.upper) } : { broken: true }) };
  });
}

// ------------------------------------------------------------------ for the AI
/** edit_chain (the assembly on screen): a chain's links, the travel of its moving end, the part it moves with, its
 *  name, or not a chain any more — what its panel does, one undo step. */
export function chainHandlers(asm) {
  return {
    edit_chain: async ({ id, links, travel, moves_with, name, remove } = {}) => {
      if (!asm.active) throw new Error('No assembly is on screen — new_assembly, or open_part an assembly.');
      const rec = chainOf(asm, id) || (asm.doc.chains || []).find((c) => c.name === id);
      if (!rec) throw new Error(`No energy chain “${id}” — get_assembly lists them (\`chains\`, ids C…); library_search "chain" + library_add put one in.`);
      if (remove) {
        asm.doc.chains = asm.doc.chains.filter((c) => c !== rec);
        if (!asm.doc.chains.length) delete asm.doc.chains;
        asm.commit();
        return { text: `${rec.id} is not a chain any more: only its first link ${rec.part} stays (a plain part).` };
      }
      const keep = structuredClone(rec);
      try {
        if (links !== undefined) { const n = Math.round(+links); if (!(n >= 2)) throw new Error('links: how many links, 2 or more (igus orders by the link).'); rec.links = n; }
        if (moves_with !== undefined) {
          if (moves_with && (!asm.inst(moves_with) || moves_with === rec.part)) throw new Error(`moves_with: a placed part (I…) other than its first link ${rec.part} — get_assembly lists them; null: its own travel.`);
          followPart(asm, rec, moves_with || null);
        }
        if (travel !== undefined) {
          if (rec.follow) throw new Error(`${rec.id} moves with ${rec.follow.inst} — its travel follows that part (move it: move_free / drive_mechanism), or moves_with: null first.`);
          if (!Number.isFinite(+travel)) throw new Error('travel: mm along the runs from above the fixed end.');
          const r = travelRange({ ...rec.dims, links: rec.links });
          rec.travel = Math.trunc(Math.max(r.min, Math.min(r.max, +travel)) * 1000) / 1000; // (held in its reach: 3 decimals, toward 0 — never a hair past it)
        }
        if (name !== undefined) { if (String(name ?? '').trim()) rec.name = String(name).trim(); else delete rec.name; }
      } catch (e) { Object.assign(rec, keep); if (!keep.follow) delete rec.follow; if (!keep.name) delete rec.name; throw e; }
      asm.commit();
      drawChains(asm);
      const s = chainsSummary(asm).find((c) => c.id === rec.id), r = travelRange({ ...rec.dims, links: rec.links });
      return { text: `${rec.id}: ${s.links} links (${s.length_mm} mm), travel ${s.travel_mm} mm (it reaches ${+r.min.toFixed(1)} … ${+r.max.toFixed(1)})${s.moves_with ? `, moves with ${s.moves_with}` : ''}${s.reach_ok === false ? ' — ⚠ the moving end is past its reach: add links' : ''}. ${JSON.stringify(s)}` };
    },
  };
}
