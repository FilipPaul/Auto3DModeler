// ⚙ Mechanism: the assembly's mechanisms, each driven by one slider — a closed loop (a crank – rod – slider) by one of
// its parts' free motions (the crank's turn by default: the others follow, the loop solver of loops.js), or a part's
// own turn / slide on its own (a hinge, a wheel, a slide with limits). ▶ plays it on and on: a full turn round and
// round, else to and fro — back at a dead point (a slider pushing a crank); under the slider the driver's limits
// (⇤ min … max ⇥ typed in place, ⇤⇥ Limits / ✕: Assembly.setTravel) — ▶ keeps to them. ⋯: ⇤ / ⇥ set here, another driver, the speed, ⚠ the travel
// checked for collisions, 📈 a trace (how a follower moves over the driver's travel) and 🎬 an animation saved (anim.js).
// The row's ⚠ (off by default): collisions shown while it moves — red parts, a note in the view, red bands under the
// slider; ⋯ Stop at a collision (mechclash.js). A joint of its parts that lost its face (a feature edit took it — the
// part then moves freely there) says so in its row, with 🔧 Fix the joint (Assembly.repairJoint); driving it warns once.
// A widget of the left column (leftdock.js: docked or floating), there only while the assembly has a mechanism; ✕
// closes it, ⚙ Mechanism in the toolbar opens it again. Parts coupled by gears, a belt or a rack (couplings.js) are one
// mechanism: its driver turns them all. A ⚙ moving sub-assembly's own mechanisms are listed too ("Crank (in Drive)"),
// driven in the assembly's flat engine (Assembly.flatAsm: its parts "I3/I2" with both levels' joints) — the parts
// here joined to them follow, a loop through both levels is solved together.
//   Assembly JSON: "mechs": [{"parts": ["I2", "I3", …], "name": "the user's", "drive": {"part": "I3", "key": "J3:turn"},
//   "speed": 2}] — found again by the parts they share; a free motion's own name: an instance's
//   "moveNames": {"J3:turn": "crank"} (Assembly.nameMotion; shown wherever the motion is).
import { t, getLang } from '../i18n.js';
import { renameInPlace } from '../rename.js';
import { leftDock } from '../leftdock.js';
import { missingJoint } from './missing.js';
import { animHtml, bindAnim } from './anim.js';
import { travelOf } from './dof.js';
import { clashOn, clashBarHtml, clashesNow, refreshScans, setClash, bandsOf } from './mechclash.js';
import { pointAt } from '../pointat.js';

const fmt = (v) => (+(+v).toFixed(2)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const FULL = 359.5; // (limits this wide: a full turn, round and round)
const SPEEDS = [[0.5, '½×'], [1, '1×'], [2, '2×']];
const wrap = (a) => ((((a + 180) % 360) + 360) % 360) - 180; // (a turn the short way round)

/** The mechanisms of assembly `asm` -> [{id: "M1", key, parts, closed, drivers: [{part, mo}], driver, rec, name, min, max,
 *  full (round and round), turn, flat, inside}]. A closed loop with free motions is one (its closing part — joined onto
 *  two of its parts — does not drive it); a part outside loops that turns about an axis, slides along one, or has
 *  limits set on a motion is one on its own (fasteners and 📌 fixed parts are not); parts tied by a coupling (⚙ gears,
 *  ⛓ a belt, ▤ a rack — couplings.js) are one together (`train`). Those with parts inside a ⚙ moving sub-assembly
 *  ("I3/I2") come from its flat engine (`flat`; all inside one: `inside` — its placement, "(in <it>)" after the name). */
export function mechanisms(asm) {
  let out = listOf(asm);
  const fl = asm.flatAsm?.();
  if (fl) {
    const deep = listOf(fl).filter((m) => m.parts.some((x) => String(x).includes('/')));
    for (const m of deep) {
      const tops = [...new Set(m.parts.map((x) => String(x).split('/')[0]))];
      m.flat = true;
      if (tops.length === 1 && m.parts.every((x) => String(x).includes('/'))) {
        m.inside = tops[0];
        if (!m.rec?.name || m.rec._sub || m.rec.of) m.name = t2('{name} (in {sub})', { name: m.name, sub: asm.partName(asm.inst(tops[0])?.part) }); // (its name here: as given here)
      }
    }
    const taken = new Set(deep.flatMap((m) => m.parts));
    out = [...out.filter((m) => !m.parts.some((x) => taken.has(x))), ...deep];
  }
  return out.map((m, k) => ({ ...m, id: `M${k + 1}` }));
}

/** What the mechanisms (and the missing joint) are found from: the placed parts (where they are, their limits), the
 *  joints, couplings, loops, the parts' bodies and names — the same key: the same mechanisms. */
function foundKey(asm) {
  return JSON.stringify([asm.doc.instances, asm.doc.mates || null, asm.doc.couplings || null, asm.doc.mechs || null, asm.doc.springs || null,
    (asm.loops || []).map((l) => [l.id, l.parts, l.closed, l.stopped]), Object.entries(asm.bodies || {}).map(([k, b]) => [k, b?.key]),
    asm.hooks.parts().map((p) => [p.id, p.name]), getLang()]);
}

/** The engine a mechanism moves in: with parts inside a sub-assembly, the assembly's flat one (Assembly.flatAsm). */
export const engOf = (asm, m) => (m?.flat && !asm.flatOf ? asm.flatAsm() || asm : asm);

/** The mechanisms of one engine (mechanisms). */
function listOf(asm) {
  const out = [], seen = new Set();
  const own = (x) => { let d = null; try { d = asm.motionsOf(x, true); } catch { d = null; } return d?.count ? d.motions.map((mo) => ({ part: x, mo })) : []; };
  for (const l of asm.loops || []) {
    if (seen.has(l.parts[0]) || !asm.mechanismOf(l.parts[0])) continue;
    l.parts.forEach((x) => seen.add(x));
    const mates = (asm.doc.mates || []).filter((m) => l.parts.includes(m.move) && !asm.insideMate(m));
    const closing = new Set(l.parts.filter((x) => new Set(mates.filter((m) => m.move === x).map((m) => m.onto)).size >= 2));
    const onClosing = new Set(mates.filter((m) => closing.has(m.move)).map((m) => m.onto)); // (the crank and the slider the rod is on)
    out.push({ parts: l.parts, closed: l.closed, drivers: l.parts.filter((x) => !closing.has(x)).flatMap(own), onClosing });
  }
  const follows = (it) => Object.values(it.travel || {}).find((l) => l?.follow && asm.inst(l.follow.part)); // (↕ by a driver's direction: part of the driver's mechanism)
  for (const it of asm.doc.instances) {
    if (seen.has(it.id) || it.fastener || it.fixed || follows(it)) continue;
    const ds = own(it.id).filter(({ mo }) => /:(turn|along)$/.test(mo.key || '') || asm.limitsOf(it, mo));
    if (ds.length) out.push({ parts: [it.id], closed: true, drivers: ds, onClosing: new Set() });
  }
  for (const c of asm.doc.couplings || []) { // ⚙ coupled parts (gears, a belt, a rack): one mechanism, moved by one value
    const ensure = (x) => {
      const on = (asm.doc.mates || []).filter((j) => j.move === x).map((j) => j.onto); // (a gear keyed on a shaft: the shaft's)
      let m = out.find((q) => q.parts.includes(x)) || out.find((q) => on.some((y) => q.parts.includes(y)));
      if (!m && asm.inst(x) && !asm.inst(x).fixed) { m = { parts: [x], closed: true, drivers: own(x), onClosing: new Set() }; out.push(m); }
      return m;
    };
    const A = ensure(c.a), B = ensure(c.b);
    if (!A || !B || A === B) continue;
    A.parts.push(...B.parts.filter((x) => !A.parts.includes(x)));
    A.drivers.push(...B.drivers);
    A.closed = A.closed && B.closed;
    B.onClosing.forEach((x) => A.onClosing.add(x));
    A.train = true;
    out.splice(out.indexOf(B), 1);
  }
  for (const it of asm.doc.instances) { // ↕ a part going by a driver's direction moves with its mechanism
    const f = follows(it), m = f && out.find((q) => q.parts.includes(f.follow.part));
    if (m && !m.parts.includes(it.id)) m.parts.push(it.id);
  }
  return out.filter((m) => m.drivers.length || !m.closed).map((m, k) => {
    const rec = recOf(asm, m.parts), rank = (d) => {
      const lim = asm.limitsOf(asm.inst(d.part), d.mo), turn = d.mo.kind === 'turn', axis = /:turn$/.test(d.mo.key || '');
      const grounded = (asm.doc.mates || []).some((j) => j.move === d.part && j.type === 'axis' && (asm.inst(j.onto)?.fixed || String(d.part).startsWith(`${j.onto}/`))); // (a crank: on a pin of the fixed base — inside a sub-assembly: of its base)
      return lim && turn && lim.max - lim.min >= FULL ? 0 : turn && axis && grounded ? 1 : turn && axis && m.onClosing.has(d.part) ? 1.5 : turn && axis ? 2 : lim ? 3 : 4;
    };
    const best = [...m.drivers].sort((a, b) => rank(a) - rank(b))[0];
    const driver = (rec?.drive && m.drivers.find((d) => d.part === rec.drive.part && d.mo.key === rec.drive.key)) || best;
    const one = m.parts.length === 1, name = rec?.name || (driver ? (one ? asm.partName(asm.inst(driver.part)?.part)
      : t2('{part} and {n} more', { part: asm.partName(asm.inst(driver.part)?.part), n: m.parts.length - 1 })) : m.parts.join('–'));
    return { id: `M${k + 1}`, key: m.parts.join(','), parts: m.parts, closed: m.closed, drivers: m.drivers, driver, rec, name, train: !!m.train, own: !!rec?.name, speed: rec?.speed || 1, ...(driver ? rangeOf(asm, driver) : {}) };
  });
}

/** The record of a mechanism with these parts in doc.mechs (the one sharing most of them) — made when `make` (a
 *  sub-assembly's own one, `_sub`, taken over as this assembly's). */
function recOf(asm, parts, make = false) {
  const list = asm.doc.mechs || [], share = (r) => (r.parts || []).filter((x) => parts.includes(x)).length;
  let rec = list.filter((r) => share(r) > 0).sort((a, b) => share(b) - share(a))[0] || null;
  if (rec?._sub && make) { const { _sub, ...mine } = rec; rec = { ...mine, of: _sub }; asm.doc.mechs = [...list, rec]; } // (`of`: its name still the sub-assembly's)
  if (!rec && make) { rec = { parts: [...parts] }; asm.doc.mechs = [...list, rec]; }
  if (rec && make) rec.parts = [...parts];
  return rec;
}

/** A driver's travel: its limits; a turn without them a full turn (0 … 360°); a slide without them its size each way;
 *  one side open (dof.travelOf): a turn a full turn from the other (round to its stop), a slide its size that way. */
function rangeOf(asm, d) {
  const lim = asm.limitsOf(asm.inst(d.part), d.mo), turn = d.mo.kind === 'turn';
  if (lim && Number.isFinite(lim.min) && Number.isFinite(lim.max)) return { min: lim.min, max: lim.max, full: turn && lim.max - lim.min >= FULL, turn, lim };
  if (turn && !lim) return { min: 0, max: 360, full: true, turn };
  let p = 0;
  try { p = asm.motionPos(d.part, d.mo); } catch { p = 0; }
  const span = Math.max(10, Math.round(asm.loopPart(d.part).L));
  if (lim) return { ...travelOf(lim, turn, p, span), full: false, turn, lim };
  return { min: Math.floor(p - span), max: Math.ceil(p + span), full: false, turn };
}

/** Where a mechanism's driver is (degrees 0 … 360 for a full turn without limits; mm). */
export function posOf(asm, m) {
  asm = engOf(asm, m);
  let p = asm.motionPos(m.driver.part, m.driver.mo);
  if (m.full && !m.lim) p = ((p % 360) + 360) % 360;
  return p;
}

/** A mechanism's driver moved to v (the others follow) -> {at: where it got, stopped: a dead point / its end held it}.
 *  final: an undo step; quiet: not drawn (a sweep). */
export function driveTo(asm, m, v, final = false, quiet = false) {
  asm = engOf(asm, m);
  if (!m.full) v = Math.max(m.min, Math.min(m.max, v));
  const p = posOf(asm, m), a = m.full ? wrap(v - p) : v - p;
  asm.moveFree(m.driver.part, m.driver.mo, a, null, final, quiet);
  const at = posOf(asm, m), lp = (asm.loops || []).find((l) => l.parts.includes(m.driver.part));
  const off = m.full ? Math.abs(wrap(at - v)) : Math.abs(at - v);
  return { at, stopped: !!lp?.stopped || off > (m.turn ? 0.5 : 0.05) };
}

/** 📈 How the mechanism's followers move over the driver's travel: the first other part with a slide (else a turn),
 *  its place at n + 1 steps -> {label, unit, xs, ys} or null. The parts end where they were. */
export function traceOf(asm, m, n = 36) {
  if (m.parts.length < 2 || !m.closed) return null;
  asm = engOf(asm, m);
  let f = null;
  for (const kind of ['move', 'turn']) {
    for (const x of m.parts.filter((y) => y !== m.driver.part)) {
      let d = null;
      try { d = asm.motionsOf(x, true); } catch { d = null; }
      const mo = d?.motions.find((q) => q.kind === kind);
      if (mo) { f = { part: x, mo }; break; }
    }
    if (f) break;
  }
  if (!f) return null;
  const snap = asm.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]), xs = [], ys = [];
  const back = !m.full && Object.values(asm.inst(f.part)?.travel || {}).some((l) => l?.follow); // (↕ it goes by the direction: there and back, both stops)
  try {
    const p0 = posOf(asm, m);
    if (back) driveTo(asm, m, m.min - 1, false, true); // (it comes to min going back)
    for (let k = 0; k <= (back ? 2 * n : n); k++) {
      const q = back && k > n ? 2 * n - k : k, v = m.full ? p0 + (360 * k) / n : m.min + ((m.max - m.min) * q) / n;
      const r = driveTo(asm, m, m.full ? ((v % 360) + 360) % 360 : v, false, true);
      if (r.stopped && !m.full) continue;
      xs.push(m.full ? ((v % 360) + 360) % 360 : r.at);
      ys.push(asm.motionPos(f.part, f.mo));
    }
  } finally {
    for (const [iid, mat, hang] of snap) { const x = asm.inst(iid); if (x) { x.matrix = mat; x.hang = hang; } }
    asm.checkJoints();
    asm.draw();
  }
  return xs.length > 1 ? { label: `${asm.partName(asm.inst(f.part)?.part)} — ${f.mo.label}`, unit: f.mo.kind === 'turn' ? '°' : 'mm', xs, ys, ...(back ? { back: true } : {}) } : null;
}

/** The ⚙ Mechanism widget of assembly `asm` (its hooks: render() from Assembly.render, open(), summary() for the AI). */
export class MechanismPanel {
  constructor(asm) {
    this.asm = asm;
    this.list = [];
    this.closed = false; // (✕: until ⚙ Mechanism opens it again)
    this.notes = {}; // mechanism key -> {text, bad} (⚠ the travel)
    this.traces = {}; // mechanism key -> a trace (📈)
    this.checked = {}; // mechanism key -> ⚠ the travel checked: {min, max, n, hits} (⇤⇥ Limits start where it was free)
    this.more = new Set(); // the mechanisms whose ⋯ is open
    this.scans = {}; // mechanism key -> its travel scanned for ⚠ collisions while it moves (mechclash.js)
    this.warned = new Set(); // the broken joints driving has warned about (once each)
    this.box = leftDock.addWidget('mech', 'assembly', { title: '⚙ Mechanism', h: 270, close: () => this.close() });
  }

  /** The mechanisms found again and the widget drawn (or hidden: none, or closed). */
  render() {
    // found again only when the assembly changed (a part chosen redraws everything: 500 parts' motions were worked out
    // on every click)
    const key = this.asm.active === false || this.playing ? null : foundKey(this.asm);
    if (key === null || key !== this.found) {
      try { this.list = this.asm.active === false ? [] : mechanisms(this.asm); } catch { this.list = []; }
      if (!this.playing) try { this.missing = this.asm.active === false ? null : missingJoint(this.asm); } catch { this.missing = null; } // (▶: the joints stay as they are)
      this.found = key;
    }
    if (!this.missing && this.asm.hoverMissing) { this.asm.hoverMissing = null; this.asm.drawMarks(); }
    if (this.playing && !this.list.some((m) => m.key === this.playing.key)) this.stop(false);
    for (const id of this.warned) if (!(this.asm.doc.mates || []).some((j) => j.id === id && j.broken)) this.warned.delete(id); // (fixed: broken again later, said again)
    const on = this.list.length > 0 && !this.closed;
    leftDock.show('mech', on);
    if (on) this.draw();
    refreshScans(this);
  }

  open(part = null) {
    this.closed = false;
    const of = (x) => x.parts.includes(part) || x.inside === part; // (a sub-assembly: the mechanisms inside it)
    if (part) { const m = this.list.find(of); if (m) this.more.add(m.key); }
    this.render();
    this.asm.renderBar();
    if (this.missing) this.asm.renderProps(); // (the "missing joint" line: here now, not in the part panel)
    // brought to the user — open low in the column, folded, behind another box: unfolded, raised, scrolled to, a ring
    // on it, its slider focused (⚙ Drive the mechanism looked like it did nothing when the widget was open already)
    const row = (part && this.box.querySelector(`[data-mckey="${CSS.escape(this.list.find(of)?.key || '')}"]`)) || this.box.querySelector('.mc-row');
    const w = this.box.closest('.lw-widget');
    if (!w || w.hidden) return;
    pointAt(row || w, { again: true });
    row?.querySelector('input[type=range]')?.focus({ preventScroll: true });
  }

  /** The joints of mechanism m's parts whose face is gone -> [{j: the joint, inst, face, side}] (Assembly.goneFace). */
  broken(m) {
    const e = engOf(this.asm, m);
    return (e.doc.mates || []).filter((j) => j.broken && (m.parts.includes(j.move) || m.parts.includes(j.onto))).map((j) => ({ j, ...e.goneFace?.(j) })).filter((x) => x.face);
  }

  /** ⚠ A row's broken joints: what is gone, 🔧 Fix the joint. */
  brokenHtml(m) {
    return this.broken(m).map(({ j, face }) => `<p class="mp-count bad mc-broken" data-no-i18n>${esc(t2('⚠ joint {id} is broken — face {face} is gone', { id: `${j.id}${j.name ? ` “${j.name}”` : ''}`, face }))}
      ${m.flat ? '' : `<button class="btn small" data-mcfix="${esc(j.id)}" title="${esc(t('Click the face that takes its place — the joint holds again'))}">🔧 ${esc(t('Fix the joint'))}</button>`}</p>`).join('');
  }

  /** Driven with a broken joint: said once (each joint), the row's 🔧 Fix the joint pointed at. */
  warnBroken(m) {
    const b = this.broken(m).filter(({ j }) => !this.warned.has(j.id));
    if (!b.length) return;
    b.forEach(({ j }) => this.warned.add(j.id));
    const { j, face } = b[0], fix = m.flat ? null : { label: `🔧 ${t('Fix the joint')}`, run: () => this.asm.repairJoint(j.id) };
    this.asm.hooks.toast(t2('{name} moves with joint {id} broken (face {face} is gone) — its part is not held there.', { name: m.name, id: j.id, face }), 'warning', 8000,
      { point: `[data-mcfix="${CSS.escape(j.id)}"]`, ...(fix ? { action: fix } : {}) });
  }

  close() { this.stop(); this.closed = true; leftDock.show('mech', false); this.asm.renderBar(); if (this.missing) this.asm.renderProps(); }
  toggle() { if (this.closed || !this.list.length) this.open(); else this.close(); }

  rowHtml(m, k) {
    const e = engOf(this.asm, m), dbl = esc(t('Double-click: give it your own name')), dblM = esc(t('Double-click: give this motion your own name'));
    const head = `<label><span class="mc-name ${m.own ? 'own' : ''}" data-mcname="${k}" title="${dbl}" data-no-i18n>⚙ ${esc(m.name)}</span>${m.driver
      ? ` <span class="mc-what" ${m.flat ? '' : `data-mcmo="${k}" title="${dblM}"`} data-no-i18n>· ${m.turn ? '↻' : '↔'} ${esc(m.driver.mo.label)}</span>` : ''}</label>`;
    if (!m.closed) return `<div class="as-dof mc-row bad" data-mckey="${esc(m.key)}">${head}${this.brokenHtml(m)}<p class="mp-count bad">${esc(t2('⚠ The closed loop {parts} cannot close here — a part is too short or too long for this place.', { parts: m.parts.join('–') }))}</p></div>`;
    let at = 0;
    try { at = posOf(this.asm, m); } catch { at = 0; }
    const u = m.turn ? '°' : 'mm', play = this.playing?.key === m.key, note = this.notes[m.key], open = this.more.has(m.key), tr = this.traces[m.key];
    const broken = this.brokenHtml(m);
    return `<div class="as-dof mc-row ${play ? 'on' : ''} ${broken ? 'bad' : ''}" data-mckey="${esc(m.key)}">${head}${broken}
      <div class="as-dofrow"><span class="mc-slw"><input type="range" data-mcv="${k}" min="${m.min}" max="${m.max}" step="${m.turn ? 1 : 0.5}" value="${fmt(at)}" aria-label="${esc(m.name)}">${clashBarHtml(this, m)}</span>
        <input type="number" step="any" data-mcn="${k}" value="${fmt(at)}"><span class="unit">${u}</span>
        <button class="mini mc-play ${play ? 'on' : ''}" data-mcplay="${k}" title="${esc(t(play ? 'Pause: it stays where it is' : 'Play: the whole mechanism moves, on and on'))}">${play ? '⏸' : '▶'}</button>
        <button class="mini mc-clashb ${clashOn(m) ? 'on' : ''}" data-mcclash="${k}" title="${esc(t(clashOn(m) ? 'Collisions shown while it moves — click: off' : 'Collisions: show where parts hit while it moves (▶, the slider, a drag) — red parts, red bands under the slider'))}">⚠</button>
        <button class="mini mc-moreb ${open ? 'on' : ''}" data-mcmore="${k}" title="${esc(t('More: what drives it, how fast, ⚠ check the travel, 📈 trace'))}">⋯</button></div>
      ${this.limHtml(m, k, u)}
      ${open ? `<div class="mc-more">
        ${this.limEditable(m) ? `<div class="mc-acts mc-here"><button class="btn small" data-mchere="${k}:min" title="${esc(t('Min where it is now: move it there first (the slider, or drag it), then click'))}">${esc(t('⇤ Set min here'))}</button>
          <button class="btn small" data-mchere="${k}:max" title="${esc(t('Max where it is now: move it there first (the slider, or drag it), then click'))}">${esc(t('Set max here ⇥'))}</button></div>` : ''}
        ${m.drivers.length > 1 ? `<label class="mc-drv">${esc(t('Driven by'))} <select data-mcdrv="${k}">${m.drivers.map((d, i) => `<option value="${i}" ${d === m.driver ? 'selected' : ''} data-no-i18n>${esc(e.partName(e.inst(d.part)?.part))} ${d.part} · ${d.mo.kind === 'turn' ? '↻' : '↔'} ${esc(d.mo.label)}</option>`).join('')}</select></label>` : ''}
        <div class="mc-acts"><select class="as-dspeed" data-mcspeed="${k}" title="${esc(t('How fast ▶ plays'))}">${SPEEDS.map(([v, l]) => `<option value="${v}" ${m.speed === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
          <button class="btn small" data-mccheck="${k}" title="${esc(t('Move it over its whole travel in small steps and check for collisions on the way'))}">${esc(t('⚠ Check the travel'))}</button>
          ${m.parts.length > 1 ? `<button class="btn small ${tr ? 'on' : ''}" data-mctrace="${k}" title="${esc(t('How another part of it moves over the travel: a curve'))}">📈 ${esc(t('Trace'))}</button>` : ''}</div>
        ${clashOn(m) ? `<label class="mc-cstop" title="${esc(t('▶ pauses where a collision starts'))}"><input type="checkbox" data-mcstop="${k}" ${m.rec?.clashStop ? 'checked' : ''}> ${esc(t('Stop at a collision'))}</label>` : ''}
        ${animHtml(this, m, k)}
        ${note ? `<p class="mp-count as-dofnote ${note.bad ? 'bad' : ''}" data-no-i18n>${esc(note.text)}</p>` : ''}
        ${tr ? this.traceSvg(m, tr, at) : ''}</div>` : ''}</div>`;
  }

  /** Its driver's limits can be set here (not one inside a ⚙ moving sub-assembly: its own assembly has them). */
  limEditable(m) { return !!m.driver?.mo.key && !m.flat; }

  /** ⇤⇥ The driver's range under its slider: "⇤ −45 … 90 ° ⇥" (a value clicked: typed in place; ✕ takes them off), a full
   *  turn's "Full turn", or "No limits" with ⇤⇥ Limits to switch them on. */
  limHtml(m, k, u) {
    if (!m.driver) return '';
    const ed = this.limEditable(m);
    if (!m.lim) return `<div class="mc-lim"><span class="mc-limtxt">${esc(t('no limits'))}</span>${ed ? `<button class="mini mc-limadd" data-mclimadd="${k}" title="${esc(t('Limits: how far it may go each way — they start around where it is (where ⚠ Check the travel found it free), then type them'))}">${esc(t('⇤⇥ Limits'))}</button>` : ''}</div>`;
    const v = (end) => (!Number.isFinite(m.lim[end]) // (that side open: ∞ — a click sets it where it is now)
      ? (ed ? `<button class="mini mc-limopen" data-mclimset="${k}:${end}" title="${esc(t(end === 'min' ? 'No min: it goes freely that way — click: min where it is now' : 'No max: it goes freely that way — click: max where it is now'))}">∞</button>` : '<span>∞</span>')
      : ed ? `<input type="number" step="any" class="mc-limv" data-mclim="${k}:${end}" value="${fmt(m.lim[end])}" aria-label="${end}" title="${esc(t('Click to type it — ▶ and the slider keep to it'))}"><button class="mini mc-limoff" data-mclimoff="${k}:${end}" title="${esc(t(end === 'min' ? 'Take the min off: it goes freely that way' : 'Take the max off: it goes freely that way'))}">✕</button>`
        : `<span data-no-i18n>${fmt(m.lim[end])}</span>`);
    return `<div class="mc-lim on">${m.full ? `<span class="mc-limtxt">${esc(t('full turn'))}</span>` : ''}<span class="mc-limr">⇤ ${v('min')} … ${v('max')} <span class="unit">${u}</span> ⇥</span></div>`;
  }

  /** ⇤⇥ The limits a driver starts with: the stretch around where it is that ⚠ Check the travel found free (when it found
   *  a collision), else Assembly.firstLimits (a turn ±90°, a slide ±10 mm). */
  firstLimits(m) {
    const e = engOf(this.asm, m), c = this.checked[m.key], d = m.driver;
    if (c?.hits?.length) {
      const span = c.max - c.min, step = span / c.n, round = span >= 360;
      let p = e.motionPos(d.part, d.mo);
      if (round) p = ((p - c.min) % 360 + 360) % 360 + c.min;
      if (!c.hits.some((h) => p >= h.from - 1e-6 && p <= h.to + 1e-6)) {
        const below = c.hits.filter((h) => h.to < p), above = c.hits.filter((h) => h.from > p);
        const lo = below.length ? Math.max(...below.map((h) => h.to)) + step : round ? Math.max(...c.hits.map((h) => h.to)) + step - 360 : c.min; // (a full turn: past 0 round to the last one)
        const hi = above.length ? Math.min(...above.map((h) => h.from)) - step : round ? Math.min(...c.hits.map((h) => h.from)) - step + 360 : c.max;
        if (hi > lo) return { min: +lo.toFixed(2), max: +hi.toFixed(2) };
      }
    }
    return e.firstLimits(d.part, d.mo);
  }

  /** 📈 The trace as a small curve:the driver across, the follower up; a line where the driver is now. */
  traceSvg(m, tr, at) {
    const W = 240, Hh = 64, x0 = Math.min(...tr.xs), x1 = Math.max(...tr.xs), y0 = Math.min(...tr.ys), y1 = Math.max(...tr.ys);
    const X = (v) => 4 + ((v - x0) / (x1 - x0 || 1)) * (W - 8), Y = (v) => Hh - 4 - ((v - y0) / (y1 - y0 || 1)) * (Hh - 8);
    const pts = tr.xs.map((x, i) => [x, tr.ys[i]]).sort((a, b) => (tr.back ? 0 : a[0] - b[0])).map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(' ');
    return `<div class="mc-trace"><div class="mc-tlabel" data-no-i18n>${esc(tr.label)}: ${fmt(y0)} … ${fmt(y1)} ${tr.unit}</div>
      <svg viewBox="0 0 ${W} ${Hh}" preserveAspectRatio="none"><polyline points="${pts}"/><line class="mc-now" x1="${X(at).toFixed(1)}" x2="${X(at).toFixed(1)}" y1="0" y2="${Hh}"/></svg></div>`;
  }

  /** The quiet line "One joint is missing …" with ➕ Add joint (here, or in the part panel when this widget is not
   *  shown) — '' when nothing is near-closed. */
  missingHtml() {
    const x = this.missing;
    if (!x) return '';
    const name = (q, what) => t2(what, { d: fmt(+q.d.toFixed(2)), part: this.asm.partName(this.asm.inst(q.inst)?.part) });
    return `<div class="hint mc-miss" data-no-i18n>${esc(t2('One joint is missing to close the mechanism: {a} ↔ {b}', { a: name(x.hole, 'hole Ø{d} ({part})'), b: name(x.pin, 'pin Ø{d} ({part})') }))}
      <button class="btn small" data-mcadd title="${esc(t('Add ◎ Concentric between them — the loop closes (Ctrl+Z: back)'))}">${esc(t('➕ Add joint'))}</button></div>`;
  }

  /** ➕ Add joint: the missing pin in its hole (◎ Concentric) — one undo step. */
  addMissing() {
    const x = this.missing;
    if (!x) return;
    this.stop(false);
    this.asm.hoverMissing = null;
    this.asm.joinRound([x.move, x.onto], false);
  }

  bindMissing(box) {
    box.querySelector('[data-mcadd]')?.addEventListener('click', () => this.addMissing());
    for (const el of box.querySelectorAll('.mc-miss')) {
      el.addEventListener('mouseenter', () => { this.asm.hoverMissing = this.missing; this.asm.drawMarks(); });
      el.addEventListener('mouseleave', () => { this.asm.hoverMissing = null; this.asm.drawMarks(); });
    }
  }

  draw() {
    this.box.innerHTML = `${this.missingHtml()}<div class="mc-list">${this.list.map((m, k) => this.rowHtml(m, k)).join('')}</div>`;
    this.bindMissing(this.box);
    bindAnim(this);
    const asm = this.asm, row = (el, a) => this.list[+el.dataset[a]];
    for (const sl of this.box.querySelectorAll('[data-mcv]')) {
      const m = row(sl, 'mcv'), num = this.box.querySelector(`[data-mcn="${sl.dataset.mcv}"]`);
      sl.addEventListener('input', () => { this.stop(false); num.value = fmt(+sl.value); driveTo(asm, m, +sl.value); this.mark(m); this.warnBroken(m); });
      sl.addEventListener('change', () => { driveTo(asm, m, +sl.value, true); });
    }
    for (const num of this.box.querySelectorAll('[data-mcn]')) {
      num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
      num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) { this.stop(false); driveTo(asm, row(num, 'mcn'), v, true); this.warnBroken(row(num, 'mcn')); } });
    }
    for (const b of this.box.querySelectorAll('[data-mcplay]')) b.addEventListener('click', () => { const m = row(b, 'mcplay'); if (this.playing?.key === m.key) this.stop(); else this.play(m); });
    for (const b of this.box.querySelectorAll('[data-mcfix]')) b.addEventListener('click', () => { this.stop(false); asm.repairJoint(b.dataset.mcfix); });
    for (const b of this.box.querySelectorAll('[data-mcclash]')) b.addEventListener('click', () => { const m = row(b, 'mcclash'); setClash(this, m, !clashOn(m)); });
    for (const c of this.box.querySelectorAll('[data-mcstop]')) c.addEventListener('change', () => setClash(this, row(c, 'mcstop'), true, c.checked));
    for (const b of this.box.querySelectorAll('[data-mcmore]')) b.addEventListener('click', () => { const m = row(b, 'mcmore'); if (this.more.has(m.key)) this.more.delete(m.key); else this.more.add(m.key); this.draw(); });
    for (const s of this.box.querySelectorAll('[data-mcdrv]')) {
      s.addEventListener('change', () => {
        const m = row(s, 'mcdrv'), d = m.drivers[+s.value], rec = recOf(engOf(asm, m), m.parts, true);
        this.stop(false);
        rec.drive = { part: d.part, key: d.mo.key };
        delete this.traces[m.key];
        asm.commit();
      });
    }
    for (const s of this.box.querySelectorAll('[data-mcspeed]')) {
      s.addEventListener('change', () => { const m = row(s, 'mcspeed'), rec = recOf(engOf(asm, m), m.parts, true), v = +s.value; if (v === 1) delete rec.speed; else rec.speed = v; if (this.playing?.key === m.key) this.playing.speed = v; asm.history.commit(); this.render(); });
    }
    this.bindLimits(row);
    for (const b of this.box.querySelectorAll('[data-mccheck]')) b.addEventListener('click', () => this.check(row(b, 'mccheck')).catch(() => {}));
    for (const b of this.box.querySelectorAll('[data-mctrace]')) {
      b.addEventListener('click', () => { const m = row(b, 'mctrace'); this.stop(); if (this.traces[m.key]) delete this.traces[m.key]; else this.traces[m.key] = traceOf(asm, m) || null; this.draw(); });
    }
    for (const el of this.box.querySelectorAll('[data-mcname]')) {
      el.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        const m = row(el, 'mcname');
        el.textContent = m.own ? m.name : '';
        renameInPlace(el, (n) => this.rename(m, n));
        el.addEventListener('blur', () => { if (!el.textContent.trim()) this.draw(); }, { once: true }); // (left empty: as it was)
      });
    }
    for (const el of this.box.querySelectorAll('[data-mcmo]')) {
      el.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        const m = row(el, 'mcmo');
        el.textContent = m.driver.mo.name || '';
        renameInPlace(el, (n) => asm.nameMotion(m.driver.part, m.driver.mo, n));
        el.addEventListener('blur', () => { if (!el.textContent.trim()) this.draw(); }, { once: true });
      });
    }
  }

  /** ⇤⇥ The limits' controls: a value typed (Enter or away: set, Esc: as it was), ⇤⇥ Limits, ✕, ⇤ / ⇥ here. */
  bindLimits(row) {
    const asm = this.asm, set = (m, lim) => { this.stop(false); asm.setTravel(m.driver.part, m.driver.mo, lim); };
    for (const el of this.box.querySelectorAll('[data-mclim]')) {
      const [k, end] = el.dataset.mclim.split(':'), m = this.list[+k], was = el.value;
      el.addEventListener('focus', () => el.select());
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); if (ev.key === 'Escape') { el.value = was; el.blur(); } });
      el.addEventListener('change', () => {
        const v = parseFloat(String(el.value).replace(',', '.').replace('−', '-'));
        if (!Number.isFinite(v) || !m.lim) { el.value = was; return; }
        setTimeout(() => { // (Tab to the other value: it is there again, focused, after the row is drawn anew)
          const to = document.activeElement?.dataset?.mclim;
          set(m, { min: m.lim.min, max: m.lim.max, [end]: v });
          if (to) this.box.querySelector(`[data-mclim="${to}"]`)?.focus();
        });
      });
    }
    for (const b of this.box.querySelectorAll('[data-mclimadd]')) {
      b.addEventListener('click', () => {
        const m = row(b, 'mclimadd');
        set(m, this.firstLimits(m));
        this.box.querySelector(`[data-mckey="${CSS.escape(m.key)}"] [data-mclim$=":min"]`)?.focus(); // (type them next)
      });
    }
    for (const b of this.box.querySelectorAll('[data-mclimoff]')) { // ✕ by a value: that side open
      b.addEventListener('click', () => { const [k, end] = b.dataset.mclimoff.split(':'), m = this.list[+k]; this.stop(false); asm.clearEnd(m.driver.part, m.driver.mo, end); });
    }
    for (const b of this.box.querySelectorAll('[data-mclimset]')) { // ∞: that side set where it is now
      b.addEventListener('click', () => { const [k, end] = b.dataset.mclimset.split(':'), m = this.list[+k]; this.stop(false); asm.limitHere(m.driver.part, m.driver.mo, end); });
    }
    for (const b of this.box.querySelectorAll('[data-mchere]')) {
      b.addEventListener('click', () => { const [k, end] = b.dataset.mchere.split(':'), m = this.list[+k]; this.stop(false); asm.limitHere(m.driver.part, m.driver.mo, end); });
    }
  }

  /** A mechanism's record in the assembly (doc.mechs: its name, driver, speed) — made when it has none (one inside a
   *  sub-assembly: its own record taken over, its name kept). */
  recFor(m) { return recOf(engOf(this.asm, m), m.parts, true); }

  /** A mechanism's own name (empty: its default again). */
  rename(m, name) {
    const rec = recOf(engOf(this.asm, m), m.parts, true), v = String(name || '').trim();
    if (v) rec.name = v; else delete rec.name;
    delete rec.of; // (a name given here: as it is)
    this.asm.commit();
  }

  /** The slider, the number and the trace's line where the driver is now (while it plays). */
  mark(m, at = null) {
    const k = this.list.indexOf(m);
    if (k < 0) return;
    try { at = at ?? posOf(this.asm, m); } catch { return; }
    const sl = this.box.querySelector(`[data-mcv="${k}"]`), num = this.box.querySelector(`[data-mcn="${k}"]`), ln = this.box.querySelector(`[data-mckey="${CSS.escape(m.key)}"] .mc-now`);
    if (sl) sl.value = at;
    if (num && document.activeElement !== num) num.value = fmt(at);
    const tr = this.traces[m.key];
    if (ln && tr) { const x0 = Math.min(...tr.xs), x1 = Math.max(...tr.xs), x = 4 + ((at - x0) / (x1 - x0 || 1)) * 232; ln.setAttribute('x1', x.toFixed(1)); ln.setAttribute('x2', x.toFixed(1)); }
  }

  /** ▶ The mechanism on and on: a full turn round and round (4 s a turn at 1×), else to and fro over its travel (2 s
   *  each way); back where it cannot go on (a dead point, an end). */
  play(m) {
    this.stop(false);
    let at;
    try { at = posOf(this.asm, m); } catch { return; }
    const p = this.playing = { key: m.key, dir: 1, v: at, last: performance.now(), speed: m.speed, hit: clashesNow(this, m).length > 0 };
    this.draw();
    this.warnBroken(m);
    const frame = (now) => {
      if (this.playing !== p) return;
      const mm = this.list.find((x) => x.key === p.key);
      if (!mm || !document.body.classList.contains('ws-assembly') || this.asm.active === false) { this.stop(); return; }
      const dt = Math.min(0.1, (now - p.last) / 1000), rate = (mm.full ? 90 : (mm.max - mm.min) / 2) * p.speed;
      p.last = now;
      let v = p.v + p.dir * rate * dt;
      if (mm.full) v = ((v % 360) + 360) % 360;
      else if (v >= mm.max) { v = mm.max; p.dir = -1; } else if (v <= mm.min) { v = mm.min; p.dir = 1; }
      const r = driveTo(this.asm, mm, v);
      if (r.stopped) { p.dir = -p.dir; p.v = r.at; } else p.v = v;
      this.mark(mm, r.at);
      const hit = mm.rec?.clashStop && clashesNow(this, mm).length > 0; // (⋯ Stop at a collision: where one starts, not while in it)
      if (hit && !p.hit) { this.stop(); return; }
      p.hit = hit;
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  /** ⏸ It stays where it is (an undo step: commit). */
  stop(commit = true) {
    if (!this.playing) return;
    this.playing = null;
    if (commit) this.asm.commit(); else this.draw();
  }

  /** ⚠ The mechanism over its whole travel checked for collisions (Assembly.checkTravel) -> its result; the note in the row. */
  async check(m) {
    this.stop();
    const name = m.name;
    this.notes[m.key] = { text: t('Checking the travel…') };
    this.more.add(m.key);
    this.draw();
    try {
      const range = { min: m.full ? 0 : m.min, max: m.full ? 360 : m.max }, e = engOf(this.asm, m), r = await e.checkTravel(m.driver.part, m.driver.mo, 24, range);
      this.checked[m.key] = { ...range, n: 24, hits: r.hits || [] };
      const note = e.travelNote;
      this.notes[m.key] = { text: `${name}: ${note?.text || (r.free ? '✓' : '⚠')}`, bad: !r.free };
      this.render();
      return r;
    } catch (e) {
      this.notes[m.key] = { text: e.message, bad: true };
      this.render();
      throw e;
    }
  }

  /** For the AI (get_assembly `mechanisms`): each with its name, parts, driver, where it is and its travel. */
  summary() {
    return this.list.map((m) => {
      let at = null;
      try { at = m.driver ? +posOf(this.asm, m).toFixed(2) : null; } catch { at = null; }
      const e = engOf(this.asm, m), idx = (d) => { let x = null; try { x = e.motionsOf(d.part, true)?.motions.findIndex((q) => q.key === d.mo.key); } catch { x = null; } return x; };
      return { id: m.id, name: m.name, parts: m.parts, ...(m.inside ? { inside: m.inside } : {}), ...(m.closed ? {} : { closed: false }),
        ...(m.driver ? { driver: { part: m.driver.part, motion: idx(m.driver), label: m.driver.mo.label }, at, min: m.min, max: m.max, unit: m.turn ? 'deg' : 'mm', ...(m.full ? { full_turn: true } : {}),
          drivers: m.drivers.map((d) => `${d.part} motion ${idx(d)}: ${d.mo.label}`) } : {}), ...this.clashSummary(m),
        ...(this.broken(m).length ? { broken_joints: this.broken(m).map(({ j, face }) => ({ id: j.id, gone_face: face })) } : {}) };
    });
  }

  /** ⚠ on: {collisions: true, stop_at_collision?, collision_bands: [{from, to, with}] (once scanned), collisions_now}. */
  clashSummary(m) {
    if (!clashOn(m)) return {};
    const sc = this.scans[m.key], now = clashesNow(this, m);
    return { collisions: true, ...(m.rec?.clashStop ? { stop_at_collision: true } : {}), collision_bands: sc?.steps ? bandsOf(sc) : 'being checked',
      ...(now.length ? { collisions_now: now.map((c) => ({ a: c.a, b: c.b, volume: +c.volume.toFixed(2), depth: +c.depth.toFixed(2) })) } : {}) };
  }

  /** The mechanism the AI means: its id (M1), name or a part of it; none: the first. */
  find(which) {
    if (!this.list.length) throw new Error('This assembly has no mechanism: no closed loop of joints that moves, no part turning or sliding on an axis.');
    if (which === undefined || which === null || which === '') return this.list[0];
    const w = String(which).toLowerCase(), m = this.list.find((x) => x.id.toLowerCase() === w || x.name.toLowerCase() === w || x.parts.includes(String(which)))
      || this.list.find((x) => x.inside === String(which)) || this.list.find((x) => x.name.toLowerCase().includes(w)); // (a sub-assembly: the first inside it)
    if (!m) throw new Error(`No mechanism “${which}” — get_assembly lists them (mechanisms): ${this.list.map((x) => `${x.id} “${x.name}”`).join(', ')}.`);
    return m;
  }
}

