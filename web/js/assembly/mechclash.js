// ⚠ Collisions while a mechanism moves (⚙ Mechanism: the row's ⚠, off by default): its driver's travel is scanned once
// — the parts moved there in small steps here (driveTo, quiet), the kernel tells the collisions at each step
// (/api/assembly/sweep, as ⚠ Check the travel) — and scanned again after an edit. Then ▶, the slider and a drag only
// look up the step nearest to where the driver is: the parts in a collision glow red with the overlap boxed
// (Assembly.draw), a note in the view names them ("⚠ Collision: Arm × Post (−2.1 mm)"), red bands under the slider
// show where on its travel they happen; ⋯ "Stop at a collision" pauses ▶ where one starts. Two parts that both move
// are not checked against each other (they go along together), nor a 〰 spring against its parts.
//   Assembly JSON: the mechanism's record (doc.mechs) "clash": true, "clashStop": true — absent: off.
import { t, getLang } from '../i18n.js';
import { driveTo, posOf, engOf } from './mechanism.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const num = (v, d = 1) => { const s = String(+(+v).toFixed(d)); return getLang() === 'cs' ? s.replace('.', ',') : s; };
const ids = new WeakMap(); // a part's features (as built) -> a number: a part changed is scanned again
let idN = 0;
const idOf = (o) => { if (!o || typeof o !== 'object') return 0; if (!ids.has(o)) ids.set(o, ++idN); return ids.get(o); };

/** ⚠ on for this mechanism (its record's "clash"). */
export const clashOn = (m) => !!m?.rec?.clash;

/** How many steps the travel is scanned in: about every 2° of a turn, every 0.5 mm of a slide (24 … 180). */
function stepsOf(m) {
  const span = Math.abs(m.max - m.min) || 1;
  return Math.max(24, Math.min(180, Math.ceil(span / (m.turn ? 2 : 0.5))));
}

/** What a scan depends on: the parts that stand still (where, which shape), the joints and the driver's travel. */
function sigOf(asm, m, moving) {
  const e = engOf(asm, m);
  const still = e.flatParts().filter((f) => !moving?.has(f.id)).map((f) => [f.id, idOf(f.part.features), f.matrix.map((x) => +x.toFixed(4))]);
  return JSON.stringify([m.min, m.max, m.driver?.part, m.driver?.mo.key, still, e.doc.mates || [], e.doc.couplings || [], (moving && [...moving]) || []]);
}

/** The travel scanned: the driver moved over it (the parts end where they were), the kernel's collisions at each step
 *  -> {sig, min, max, full, n, h (a step), steps: [{at, clashes: [{a, b, volume, bbox, depth}]}], moving}. */
async function scan(panel, m) {
  const asm = panel.asm, e = engOf(asm, m), n = stepsOf(m), h = (m.max - m.min) / n;
  const snap = e.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]), base = e.flatParts(), steps = [];
  panel.scanning = true; // (the parts away from where they are: no live collisions drawn meanwhile)
  try {
    for (let k = 0; k <= n; k++) {
      const v = m.min + h * k, r = driveTo(e, m, m.full ? ((v % 360) + 360) % 360 : v, false, true);
      steps.push({ at: +v.toFixed(3), stopped: r.stopped && !m.full, matrices: Object.fromEntries(e.flatParts().map((f) => [f.id, f.matrix])) });
    }
  } finally {
    for (const [iid, mat, hang] of snap) { const x = e.inst(iid); if (x) { x.matrix = mat; x.hang = hang; } }
    e.checkJoints();
    panel.scanning = false;
  }
  const moving = new Set(steps.flatMap((s) => base.filter((f) => s.matrices[f.id].some((x, q) => Math.abs(x - f.matrix[q]) > 1e-7)).map((f) => f.id)));
  for (const s of steps) s.matrices = Object.fromEntries([...moving].map((k) => [k, s.matrices[k]]));
  const sig = sigOf(asm, m, moving); // (before the answer: an edit while it is computed scans again)
  const res = await fetch('/api/assembly/sweep', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances: base, steps: steps.map(({ at, matrices }) => ({ at, matrices })), quick: true }) });
  const r = await res.json();
  if (!res.ok) throw new Error(r.error || res.statusText);
  const out = r.steps.map((s, k) => ({ at: s.at, clashes: steps[k].stopped ? [] : s.clashes.filter((c) => !(moving.has(c.a) && moving.has(c.b)) && !e.springIgnores?.(c.a, c.b))
    .map((c) => ({ ...c, depth: depthOf(c, steps, k, moving.has(c.a) ? c.a : c.b) })) }));
  return { sig, min: m.min, max: m.max, full: !!m.full, n, h, steps: out, moving };
}

/** How deep a collision goes: the overlap's size along the way the moving part goes there (from this step to the
 *  next — a turn: across the arm, not its thickness), else its smallest size. */
function depthOf(c, steps, k, id) {
  const b = c.bbox, size = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], least = Math.min(...size);
  const M = steps[k]?.matrices[id], N = (steps[k + 1] || steps[k - 1])?.matrices[id];
  if (!M || !N) return least;
  const p = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], q = [p[0] - M[12], p[1] - M[13], p[2] - M[14]];
  const loc = [0, 1, 2].map((i) => M[4 * i] * q[0] + M[4 * i + 1] * q[1] + M[4 * i + 2] * q[2]); // (in the part's own frame: a rigid matrix's inverse)
  const to = [0, 1, 2].map((j) => N[j] * loc[0] + N[4 + j] * loc[1] + N[8 + j] * loc[2] + N[12 + j]);
  const v = to.map((x, j) => x - p[j]), len = Math.hypot(...v);
  if (len < 1e-9) return least;
  return Math.min(Math.max(...size), size.reduce((s, w, j) => s + (w * Math.abs(v[j])) / len, 0));
}

/** The scan's step nearest to v (a full turn: round) -> that step, or null (no scan, a pose it has not got). */
function stepAt(sc, v) {
  if (!sc?.steps || !Number.isFinite(v)) return null;
  let x = (v - sc.min) / (sc.h || 1);
  if (sc.full) x = ((x % sc.n) + sc.n) % sc.n;
  const k = Math.round(x);
  return k < 0 || k > sc.n ? null : sc.steps[k];
}

/** The stretches of the travel with a collision: [{from, to, with: [part ids]}] — a step's half each side of the steps
 *  that have one (as the live look-up shows them). */
export function bandsOf(sc) {
  const out = [];
  if (!sc?.steps) return out;
  let cur = null;
  sc.steps.forEach((s, k) => {
    if (s.clashes.length) {
      const w = s.clashes.flatMap((c) => [c.a, c.b]).filter((x) => !sc.moving.has(x));
      if (!cur) { cur = { from: Math.max(sc.min, s.at - sc.h / 2), to: s.at, with: new Set() }; out.push(cur); }
      cur.to = Math.min(sc.max, s.at + sc.h / 2);
      w.forEach((x) => cur.with.add(x));
    } else cur = null;
  });
  return out.map((b) => ({ from: +b.from.toFixed(2), to: +b.to.toFixed(2), with: [...b.with] }));
}

/** The collisions where mechanism m is now (its scan's nearest step) -> [{a, b, volume, bbox, depth}] (none: []). */
export function clashesNow(panel, m) {
  const sc = clashOn(m) && panel.scans[m.key];
  if (!sc?.steps) return [];
  let at;
  try { at = posOf(panel.asm, m); } catch { return []; }
  return stepAt(sc, at)?.clashes || [];
}

/** For Assembly.draw: the collisions now of every mechanism with ⚠ on (a sub-assembly's parts "I3/I2": as they are), and
 *  the note in the view shown or hidden. */
export function liveClashes(panel) {
  if (!panel || panel.scanning) return [];
  const out = [];
  for (const m of panel.list) if (clashOn(m)) out.push(...clashesNow(panel, m).map((c) => ({ ...c, mech: m })));
  showNote(panel, out);
  return out;
}

/** The note in the view: "⚠ Collision: Arm × Post (−2.1 mm)" (the deepest few), hidden when there is none. */
function showNote(panel, list) {
  const vp = panel.asm.els?.viewport;
  if (!vp) return;
  let el = vp.querySelector(':scope > .mc-clashnote');
  if (!list.length) { if (el) el.hidden = true; return; }
  if (!el) { el = document.createElement('div'); el.className = 'mc-clashnote'; el.dataset.noI18n = ''; vp.appendChild(el); }
  const name = (m, id) => { const e = engOf(panel.asm, m); return e.partName(e.inst(id)?.part) || panel.asm.partName(panel.asm.inst(panel.asm.topOf(id))?.part); };
  const pairs = [...list].sort((a, b) => b.depth - a.depth).slice(0, 3).map((c) => `${name(c.mech, c.a)} × ${name(c.mech, c.b)} (−${num(c.depth)} mm)`);
  const text = t2('⚠ Collision: {list}', { list: pairs.join(', ') + (list.length > 3 ? ' …' : '') });
  if (el.textContent !== text) el.textContent = text;
  el.hidden = false;
}

/** The red bands under the slider (where on its travel a collision is), or a faint line while it is scanned. */
export function clashBarHtml(panel, m) {
  if (!clashOn(m)) return '';
  const sc = panel.scans[m.key], span = m.max - m.min || 1;
  if (!sc?.steps || sc.min !== m.min || sc.max !== m.max) return `<span class="mc-clashbar busy" title="${esc(t('Checking the travel…'))}"></span>`;
  const bands = bandsOf(sc);
  return `<span class="mc-clashbar" data-mcbands="${bands.length}" title="${esc(bands.length ? t('Red: where on its travel parts collide') : t('✓ No collision over its travel'))}">${bands.map((b) =>
    `<i style="left:${(((b.from - m.min) / span) * 100).toFixed(2)}%;width:${Math.max(0.6, ((b.to - b.from) / span) * 100).toFixed(2)}%"></i>`).join('')}</span>`;
}

/** After the widget is drawn: each mechanism with ⚠ on is scanned (again) when it has no scan or a part / joint / its
 *  travel changed since — a moment later, not while ▶ plays. */
export function refreshScans(panel) {
  clearTimeout(panel.scanTimer);
  const due = panel.list.filter((m) => clashOn(m) && m.closed && m.driver && (() => { const sc = panel.scans[m.key]; return !sc || (!sc.busy && sc.sig !== sigOf(panel.asm, m, sc.moving)); })());
  for (const k of Object.keys(panel.scans)) if (!panel.list.some((m) => m.key === k && clashOn(m))) delete panel.scans[k];
  if (!due.length) return;
  panel.scanTimer = setTimeout(() => { if (!panel.playing) for (const m of due) rescan(panel, m).catch(() => {}); else refreshScans(panel); }, panel.playing ? 500 : 250);
}

/** One mechanism scanned now -> its scan (the widget and the view drawn again). */
export async function rescan(panel, m) {
  const run = (panel.scanRun = (panel.scanRun || 0) + 1), was = panel.scans[m.key];
  panel.scans[m.key] = { ...(was || {}), busy: true };
  let sc;
  try {
    sc = await scan(panel, m);
  } catch (e) {
    panel.scans[m.key] = { ...(was || {}), busy: false, sig: sigOf(panel.asm, m, was?.moving), error: e.message };
    panel.asm.hooks.toast?.(e.message, 'error', 6000);
    throw e;
  }
  if (!panel.list.some((x) => x.key === m.key && clashOn(x))) { delete panel.scans[m.key]; return null; } // (⚠ off meanwhile)
  panel.scans[m.key] = sc;
  if (run === panel.scanRun) { panel.draw(); panel.asm.draw(); }
  return sc;
}

/** ⚠ on / off for mechanism m (an undo step); on: its travel scanned. */
export function setClash(panel, m, on, stop = undefined) {
  const rec = panel.recFor(m);
  if (on) rec.clash = true; else { delete rec.clash; delete panel.scans[m.key]; }
  if (stop !== undefined) { if (stop) rec.clashStop = true; else delete rec.clashStop; }
  panel.asm.history.commit();
  panel.render();
  panel.asm.draw();
}

/** The scan of mechanism m once it is done (the AI waits for it) -> the scan or null. */
export async function scanDone(panel, m, wait = 120000) {
  const end = Date.now() + wait;
  while (Date.now() < end) {
    const sc = panel.scans[m.key];
    if (!sc?.busy) {
      if (sc?.steps && sc.sig === sigOf(panel.asm, m, sc.moving)) return sc;
      clearTimeout(panel.scanTimer);
      return rescan(panel, m);
    }
    await new Promise((ok) => setTimeout(ok, 100));
  }
  return null;
}
