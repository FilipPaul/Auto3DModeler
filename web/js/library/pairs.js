// 🔗 Library parts that go with each other: a screw and its nut / washer / heat-set insert, a standoff and its screw,
// a test probe and its receptacle, a cylinder and its auto switch. An item's `pairs` ([{ref, role, back, size, qty}],
// both ways — auto3d/library.py link_pairs mirrors them) say which; here: the companions of a chosen size, the
// suggestions for a placed part, and putting a companion in — on the part's axis, where it goes (a nut at the screw's
// end or under the parts it holds, a washer under the head, a probe seated in its receptacle with its stroke as the
// limits of its slide), joined Concentric so it stays on the axis.
//   A placed companion remembers it: instance "pair": {"host": "I3", "role": "nut", "slot": "nut" | "head" | "under"}.
import * as THREE from 'three';
import { t, getLang } from '../i18n.js';
import { buildPart, sizesOf, lengthsOf, varsOf, evaluate } from './build.js';
import { partsAlong, isStandard } from '../assembly/fasteners.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
/** What a companion is to the part it goes with (the words of the suggestions). */
export const ROLE_NAMES = { nut: 'Nut', washer: 'Washer', insert: 'Insert', screw: 'Screw', standoff: 'Standoff', receptacle: 'Receptacle', probe: 'Probe',
  'auto switch': 'Auto switch', cylinder: 'Cylinder', part: 'Part' };
const roleName = (r) => t(ROLE_NAMES[r] || r);
const itemName = (it) => (getLang() === 'cs' && it.name_cs) || t(it.name);

/** The parts that go with item `item` in size `sizeKey`: [{item, size, role, back, qty}] — a size the companion does
 *  not have is left out (an M1 screw: no washer). */
export function companions(items, item, sizeKey) {
  const out = [];
  for (const p of item?.pairs || []) {
    const it = items.find((x) => x.id === p.ref);
    if (!it || (p.from_size && p.from_size !== sizeKey)) continue; // (only that size of this one goes with it)
    const keys = sizesOf(it).map((s) => s.key), size = p.size === 'same' ? sizeKey : p.size || keys[0];
    if (!keys.includes(size)) continue;
    out.push({ item: it, size, role: p.role, back: p.back, qty: p.qty || 1 });
  }
  return out;
}

/** "Goes with" for the library window: [{item, size, role, label}] (the first of each role named by its role). */
export function goesWith(items, item, sizeKey) {
  const seen = new Set();
  return companions(items, item, sizeKey).map((c) => {
    const first = !seen.has(c.role);
    seen.add(c.role);
    return { ...c, label: `${roleName(c.role)} ${c.size}`, first };
  });
}

// ------------------------------------------------------------------ geometry (a library part is built along +Z from 0)
const bodyOf = (asm, it) => asm.bodyOf(it)?.body;
const topOf = (body) => body?.bbox?.[5] ?? 0;
/** The round faces about the part's own Z axis: [{name, r}] (the ones a companion's axis is joined on). */
function axisFaces(body) {
  return (body?.faces || []).filter((f) => f.type === 'cylinder' && f.axis && Math.abs(Math.abs(f.axis.d[2]) - 1) < 1e-6
    && Math.hypot(f.axis.o[0], f.axis.o[1]) < 1e-6).map((f) => ({ name: f.name, r: f.radius }));
}
/** The two round faces to join on the axis: the closest radii (a screw's shaft in the nut's hole; a probe's barrel in
 *  the receptacle's bore), the smaller ones first. -> [faceA, faceB] or null. */
function axisPair(a, b) {
  let best = null;
  for (const x of axisFaces(a)) for (const y of axisFaces(b)) {
    const s = Math.abs(x.r - y.r) * 1000 + Math.min(x.r, y.r);
    if (!best || s < best.s) best = { s, x, y };
  }
  return best ? [best.x.name, best.y.name] : null;
}

/** The library item and choice of a placed part -> {item, size, length, vars} or null. */
export function libOf(items, data) {
  const lib = data?.library, item = lib && items.find((x) => x.id === lib.id);
  return item ? { item, size: lib.size, length: lib.length, vars: varsOf(item, lib.size, lib.length) } : null;
}

const num = (v, vars, d = 0) => { try { return v === undefined ? d : evaluate(v, vars); } catch { return d; } };

/** The companion's own length (a screw put through a nut: the shortest that comes out of it) or undefined. */
function lengthFor(comp, hostTop) {
  const ls = lengthsOf(comp.item, comp.size);
  if (!ls) return undefined;
  const d = num('d', varsOf(comp.item, comp.size), 3);
  const need = comp.back === 'standoff' ? Math.max(1.5 * d, 4) : hostTop + 1; // (into a standoff's thread: 1.5 d; else through it)
  return ls.values.find((v) => v >= need - 1e-6) ?? ls.values[ls.values.length - 1];
}

/** Where along the host's own Z the companion's origin goes, and its slot (screws: head / nut / under). The parts a
 *  screw holds are found along its axis (the first one touching the head and the ones touching it). */
function placeOf(asm, hostIt, host, comp, compTop, length) {
  const hv = host.vars, top = topOf(bodyOf(asm, hostIt));
  if (host.item.kind === 'receptacle' && comp.role === 'probe') return { z: num('zp', hv), slot: 'probe' };
  if (host.item.kind === 'probe' && comp.role === 'receptacle') return { z: -num('zp', varsOf(comp.item, comp.size)), slot: 'receptacle' };
  if (comp.role === 'screw') return { z: top - (length ?? compTop), slot: 'screw' }; // (its head on the part's top)
  if (comp.role === 'auto switch' || comp.role === 'cylinder') return null; // (no place on an axis: beside it)
  if (host.item.kind === 'standoff' || host.item.id.startsWith('standoff')) return { z: -compTop, slot: 'nut' }; // (a nut on its male end, below)
  // a screw: its seat (under the head) at z = L; washer under the head, the nut at the end of what it holds
  const L = num('L', hv, top), pairs = asm.doc.instances.filter((i) => i.pair?.host === hostIt.id);
  const headWasher = pairs.find((i) => i.pair.slot === 'head'), hw = headWasher ? topOf(bodyOf(asm, headWasher)) : 0;
  if (comp.role === 'washer' && !headWasher) return { z: L - compTop, slot: 'head' };
  // what it holds: parts along its axis from under the head (and its washer) down, touching one after another
  const M = new THREE.Matrix4().fromArray(hostIt.matrix), seat = new THREE.Vector3(0, 0, L - hw).applyMatrix4(M);
  const down = new THREE.Vector3(0, 0, -1).transformDirection(M);
  const skip = (it) => it.id === hostIt.id || !!it.pair || !!it.fastener || isStandard(asm.hooks.partData(it.part), asm.partName(it.part));
  let thick = 0;
  try {
    for (const p of partsAlong(asm, seat, down, skip)) {
      if (p.tin - thick > 0.6) break;
      thick = Math.max(thick, p.tout);
    }
  } catch { thick = 0; }
  // (the underside of what it holds; nothing held: right under the head — slide it along its axis to where it goes)
  const under = pairs.find((i) => i.pair.slot === 'under'), bottom = L - hw - thick;
  if (comp.role === 'washer') return { z: bottom - compTop, slot: 'under' }; // the second washer: under what it holds
  if (comp.role === 'nut') return { z: bottom - (under ? topOf(bodyOf(asm, under)) : 0) - compTop, slot: 'nut' };
  if (comp.role === 'insert') return { z: 0, slot: 'insert' }; // (where the screw ends)
  return { z: 0, slot: comp.role };
}

/** Put companion `comp` ({item, size, role, back}) of the placed part `hostId` into the assembly, on its axis where it
 *  goes. hooks: {addPart(name, data) -> part id (a part of the project, the same one again when it is there)}.
 *  -> {inst, joint, travel} (travel: a probe's stroke as its slide's limits). */
export async function addCompanion(asm, items, hostId, comp, hooks) {
  const hostIt = asm.inst(hostId), host = libOf(items, asm.hooks.partData(hostIt?.part));
  if (!hostIt || !host) throw new Error(t('That part is not a library part.'));
  await asm.refresh();
  const length = lengthFor(comp, topOf(bodyOf(asm, hostIt)));
  const built = buildPart(comp.item, comp.size, length);
  const pid = hooks.addPart(built.name, built.data);
  const before = new Set(asm.doc.instances.map((i) => i.id));
  await asm.insert(pid);
  const it = asm.doc.instances.find((i) => !before.has(i.id));
  if (!it) throw new Error(t('It could not be put in.'));
  asm.sel = hostId; // (the part it goes with stays chosen: its table offers the next one)
  const place = placeOf(asm, hostIt, host, comp, topOf(bodyOf(asm, it)), length);
  if (!place) { asm.commit(); return { inst: it.id }; } // (beside it: no place on its axis)
  it.matrix = new THREE.Matrix4().fromArray(hostIt.matrix).multiply(new THREE.Matrix4().makeTranslation(0, 0, place.z)).toArray();
  it.pair = { host: hostIt.id, role: comp.role, slot: place.slot };
  delete it.fixed;
  const faces = axisPair(bodyOf(asm, it), bodyOf(asm, hostIt));
  // a receptacle put to a probe that hangs on nothing: the receptacle holds the probe (it is the one mounted in the
  // plate — fixed in its place when the probe was), the probe slides in it
  const flip = comp.role === 'receptacle' && !(asm.doc.mates || []).some((m) => m.move === hostIt.id);
  if (flip && hostIt.fixed) { delete hostIt.fixed; it.fixed = true; }
  const joint = !faces ? null : flip ? asm.addJoint({ inst: hostIt.id, face: { name: faces[1] } }, { inst: it.id, face: { name: faces[0] } }, 'axis')
    : asm.addJoint({ inst: it.id, face: { name: faces[0] } }, { inst: hostIt.id, face: { name: faces[1] } }, 'axis');
  if (place.slot === 'head') { // a washer under the head: the screw sits on it now (its seat's touch joint lifted by it)
    const h = topOf(bodyOf(asm, it));
    for (const m of (asm.doc.mates || []).filter((x) => x.move === hostIt.id && x.type === 'touch')) m.gap = +((+m.gap || 0) + h).toFixed(4);
  }
  asm.applyMates();
  asm.commit();
  let travel = null;
  const probe = comp.role === 'probe' ? it : comp.role === 'receptacle' ? hostIt : null, pv = probe && libOf(items, asm.hooks.partData(probe.part))?.vars;
  if (joint && probe && pv?.ms) travel = strokeLimits(asm, probe.id, joint.id, pv.ms, probe === it ? hostIt : it);
  return { inst: it.id, joint: joint?.id, travel };
}

/** A probe in its receptacle: its slide along the axis limited to its stroke (pushed in up to the max. stroke), named
 *  Stroke — the mechanism tools then show it compressing. -> the limits or null. */
function strokeLimits(asm, probeId, jointId, stroke, rec) {
  if (!asm.inst(probeId) || !rec) return null;
  let d = null;
  try { d = asm.motionsOf(probeId, true); } catch { d = null; }
  const mo = d?.motions?.find((m) => m.key === `${jointId}:along`);
  if (!mo) return null;
  const p = asm.motionPos(probeId, mo), up = new THREE.Vector3(0, 0, 1).transformDirection(new THREE.Matrix4().fromArray((asm.inst(probeId)).matrix));
  const lim = mo.dir.dot(up) > 0 ? { min: +(p - stroke).toFixed(4), max: +p.toFixed(4) } : { min: +p.toFixed(4), max: +(p + stroke).toFixed(4) };
  asm.setTravel(probeId, mo, lim);
  try { asm.nameMotion(probeId, mo, t('Stroke')); } catch { /* (no name: its own words) */ }
  return { key: mo.key, ...lim };
}

/** The suggestions for a placed library part (the assembly's table): ＋ each companion, the first of each role on
 *  top; a screw with a nut and a washer: ＋ Set (nut + 2 washers). run(c) puts it in. -> rows for showSuggest. */
export function pairRows(items, data, run) {
  const host = libOf(items, data);
  if (!host) return [];
  const list = goesWith(items, host.item, host.size);
  const rows = list.map((c, k) => ({ icon: '＋', rank: c.first ? -1.5 + k * 0.01 : 2.5 + k * 0.01,
    label: c.first ? `${roleName(c.role)} ${c.size}` : `${itemName(c.item)} ${c.size}`,
    title: t2('{what} — on its axis, where it goes (Concentric)', { what: buildPart(c.item, c.size).name }), run: () => run([c]) }));
  const nut = list.find((c) => c.role === 'nut'), washer = list.find((c) => c.role === 'washer');
  if (nut && washer && host.item.category?.startsWith('Fasteners / Screws')) {
    rows.push({ icon: '＋', rank: -1.4, label: t('Set: nut + 2 washers'), title: t2('{nut} and two {washer}: a washer under the head, one under the nut', { nut: buildPart(nut.item, nut.size).name, washer: buildPart(washer.item, washer.size).name }),
      run: () => run([washer, washer, nut]) });
  }
  return rows;
}
