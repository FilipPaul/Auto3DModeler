// Smart suggestions: what a placed part most likely goes onto, found by geometry so one click in the Suggested table
// does it — ◎ a pin into a hole of the same Ø in another part (or a hole onto a pin), ⧉ a part put down on the top of
// the fixed part (its underside onto it). Plain geometry over the assembly's bodies, no UI (assembly.js shows them).
import { isPin, facesOf } from './missing.js';

/** A body's round faces with an axis, once per body (kept on it): [{name, d, pin}] — pin null (neither) left out. */
function roundsOf(body) {
  if (body._rounds) return body._rounds;
  const out = [], { own } = facesOf(body);
  for (const name of new Set(body.faces.filter((f) => f.type === 'cylinder' && f.radius && f.axis).map((f) => f.name))) {
    const pin = isPin(body, name);
    if (pin !== null) out.push({ name, d: 2 * own.get(name).find((f) => f.radius).radius, pin });
  }
  return (body._rounds = out);
}

/** The round faces used by concentric joints: a set of "inst|face". */
const usedRounds = (asm) => new Set((asm.doc.mates || []).filter((m) => m.type === 'axis').flatMap((m) => [`${m.move}|${m.face}`, `${m.onto}|${m.ontoFace}`]));

/** A placed part's round faces not used by a concentric joint yet: [{inst, name, face (world), d, pin}]. used: the
 *  used ones (usedRounds), when known; want(d, pin): only those (its world face is the costly part — a base plate
 *  with 160 holes, 500 placed parts). */
export function freeRounds(asm, it, used = usedRounds(asm), want = null) {
  const body = asm.bodyOf(it)?.body;
  if (!body?.faces || it.fastener) return [];
  const out = [];
  for (const r of roundsOf(body)) {
    if (used.has(`${it.id}|${r.name}`) || (want && !want(r.d, r.pin))) continue;
    let face;
    try { face = asm.worldFace(it.id, r.name); } catch { continue; }
    out.push({ inst: it.id, name: r.name, face, d: 2 * face.radius, pin: r.pin });
  }
  return out;
}

/** Does a pin of Ø `p` fit a hole of Ø `h`? As big as the hole, or up to 0.6 mm smaller (a print's play). */
const fits = (p, h) => p <= h + 1e-3 && h - p <= 0.6;

/** Pin-in-hole joints part `id` can make with the other parts, the best first: [{move: {inst, face}, onto: {inst,
 *  face}, d, hole: inst id, pin: inst id}] (`move`: the chosen part, unless it is 📌 fixed). At most one per other
 *  part (its nearest fitting hole / pin), at most `max`. */
export function pinFits(asm, id, max = 2) {
  const a = asm.inst(id);
  if (!a || a.fastener) return [];
  const used = usedRounds(asm), mine = freeRounds(asm, a, used);
  if (!mine.length) return [];
  const moving = new Set((asm.doc.mates || []).map((m) => m.move)), joined = (x) => moving.has(x);
  // its pins and holes by Ø: a round face of another part meets only those of a fitting Ø (a merged sub-assembly has
  // thousands of round faces — not each against each)
  const byD = (pin) => mine.filter((p) => p.pin === pin).sort((x, y) => x.d - y.d), pins = byD(true), holes = byD(false);
  const near = (d, pin) => { // (mine that may fit a round face of Ø d: its holes for a pin, its pins for a hole)
    const list = pin ? holes : pins, lo = pin ? d - 2e-3 : d - 0.601, hi = pin ? d + 0.601 : d + 2e-3;
    let a = 0, b = list.length;
    while (a < b) { const m = (a + b) >> 1; if (list[m].d < lo) a = m + 1; else b = m; }
    const out = [];
    for (let k = a; k < list.length && list[k].d <= hi; k++) out.push(list[k]);
    return out;
  };
  const fitsMine = (d, pin) => near(d, pin).some((p) => fits(p.pin ? p.d : d, p.pin ? d : p.d)); // (by Ø first: only those placed)
  const best = new Map();
  for (const b of asm.doc.instances) {
    if (b.id === id || b.fastener) continue;
    for (const q of freeRounds(asm, b, used, fitsMine)) {
      for (const p of near(q.d, q.pin)) {
        if (p.pin === q.pin || !fits(p.pin ? p.d : q.d, p.pin ? q.d : p.d)) continue;
        const apart = p.face.axis.o.distanceTo(q.face.axis.o);
        // the better target: a fixed part, or one already in place (joined); then the nearer one
        const score = (b.fixed ? 0 : joined(b.id) ? 1e5 : 2e5) + apart;
        const old = best.get(b.id);
        if (!old || score < old.score) {
          const [mv, on] = a.fixed ? [q, p] : [p, q];
          best.set(b.id, { score, move: { inst: mv.inst, face: mv.face }, onto: { inst: on.inst, face: on.face }, d: p.pin ? q.d : p.d, hole: (p.pin ? q : p).inst, pin: (p.pin ? p : q).inst });
        }
      }
    }
  }
  return [...best.values()].sort((x, y) => x.score - y.score).slice(0, max);
}

/** ⧉ Put part `id` down on another part: its underside (the lowest face looking down) onto the top of part `ontoId`
 *  (none: the 📌 fixed part, else the biggest other part) — {move: {inst, face}, onto: {inst, face}} or null (it is
 *  joined or fixed already, or not standing upright). */
export function restOn(asm, id, ontoId = null) {
  const a = asm.inst(id);
  if (!a || a.fixed || a.fastener || (asm.doc.mates || []).some((m) => m.move === id)) return null;
  const others = asm.doc.instances.filter((b) => b.id !== id && !b.fastener && asm.bodyOf(b)?.body);
  const size = (b) => { const bb = asm.bodyOf(b).body.bbox || [0, 0, 0, 0, 0, 0]; return (bb[3] - bb[0]) * (bb[4] - bb[1]); };
  const base = ontoId ? others.find((b) => b.id === ontoId) : others.find((b) => b.fixed) || others.sort((p, q) => size(q) - size(p))[0];
  if (!base) return null;
  const flat = (it, up) => {
    let best = null;
    for (const name of new Set((asm.bodyOf(it)?.body?.faces || []).filter((f) => f.type === 'plane').map((f) => f.name))) {
      let f;
      try { f = asm.worldFace(it.id, name); } catch { continue; }
      if ((up ? f.normal.z : -f.normal.z) < 0.999) continue;
      const key = (up ? -f.centroid.z : f.centroid.z) - f.area * 1e-9; // (the top: the highest; the underside: the lowest; the larger of two)
      if (!best || key < best.key) best = { key, face: f };
    }
    return best?.face || null;
  };
  const under = flat(a, false), top = flat(base, true);
  return under && top ? { move: { inst: id, face: under }, onto: { inst: base.id, face: top } } : null;
}
