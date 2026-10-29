// ⚙ Mechanism: the assembly's mechanisms, each driven by one slider — a closed loop (a crank – rod – slider) by one of
// its parts' free motions (the crank's turn by default: the others follow, the loop solver of loops.js), or a part's
// own turn / slide on its own (a hinge, a wheel, a slide with limits). ▶ plays it on and on: a full turn round and
// round, else to and fro — back at a dead point (a slider pushing a crank). ⋯: another driver, the speed, ⚠ the travel
// checked for collisions, 📈 a trace (how a follower moves over the driver's travel) and 🎬 an animation saved (anim.js).
// A widget of the left column (leftdock.js: docked or floating), there only while the assembly has a mechanism; ✕
// closes it, ⚙ Mechanism in the toolbar opens it again. Parts coupled by gears, a belt or a rack (couplings.js) are one
// mechanism: its driver turns them all. A ⚙ moving sub-assembly's own mechanisms are listed too ("Crank (in Drive)"),
// driven in the assembly's flat engine (Assembly.flatAsm: its parts "I3/I2" with both levels' joints) — the parts
// here joined to them follow, a loop through both levels is solved together.
//   Assembly JSON: "mechs": [{"parts": ["I2", "I3", …], "name": "the user's", "drive": {"part": "I3", "key": "J3:turn"},
//   "speed": 2}] — found again by the parts they share; a free motion's own name: an instance's
//   "moveNames": {"J3:turn": "crank"} (Assembly.nameMotion; shown wherever the motion is).
import { t } from '../i18n.js';
import { renameInPlace } from '../rename.js';
import { leftDock } from '../leftdock.js';
import { missingJoint } from './missing.js';
import { animHtml, bindAnim } from './anim.js';

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

/** A driver's travel: its limits; a turn without them a full turn (0 … 360°); a slide without them its size each way. */
function rangeOf(asm, d) {
  const lim = asm.limitsOf(asm.inst(d.part), d.mo), turn = d.mo.kind === 'turn';
  if (lim) return { min: lim.min, max: lim.max, full: turn && lim.max - lim.min >= FULL, turn, lim };
  if (turn) return { min: 0, max: 360, full: true, turn };
  let p = 0;
  try { p = asm.motionPos(d.part, d.mo); } catch { p = 0; }
  const span = Math.max(10, Math.round(asm.loopPart(d.part).L));
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
    this.more = new Set(); // the mechanisms whose ⋯ is open
    this.box = leftDock.addWidget('mech', 'assembly', { title: '⚙ Mechanism', h: 230, close: () => this.close() });
  }

  /** The mechanisms found again and the widget drawn (or hidden: none, or closed). */
  render() {
    try { this.list = this.asm.active === false ? [] : mechanisms(this.asm); } catch { this.list = []; }
    if (!this.playing) try { this.missing = this.asm.active === false ? null : missingJoint(this.asm); } catch { this.missing = null; } // (▶: the joints stay as they are)
    if (!this.missing && this.asm.hoverMissing) { this.asm.hoverMissing = null; this.asm.drawMarks(); }
    if (this.playing && !this.list.some((m) => m.key === this.playing.key)) this.stop(false);
    const on = this.list.length > 0 && !this.closed;
    leftDock.show('mech', on);
    if (on) this.draw();
  }

  open(part = null) {
    this.closed = false;
    const of = (x) => x.parts.includes(part) || x.inside === part; // (a sub-assembly: the mechanisms inside it)
    if (part) { const m = this.list.find(of); if (m) this.more.add(m.key); }
    this.render();
    this.asm.renderBar();
    if (this.missing) this.asm.renderProps(); // (the "missing joint" line: here now, not in the part panel)
    const row = part && this.box.querySelector(`[data-mckey="${CSS.escape(this.list.find(of)?.key || '')}"]`);
    row?.scrollIntoView({ block: 'nearest' });
  }

  close() { this.stop(); this.closed = true; leftDock.show('mech', false); this.asm.renderBar(); if (this.missing) this.asm.renderProps(); }
  toggle() { if (this.closed || !this.list.length) this.open(); else this.close(); }

  rowHtml(m, k) {
    const e = engOf(this.asm, m), dbl = esc(t('Double-click: give it your own name')), dblM = esc(t('Double-click: give this motion your own name'));
    const head = `<label><span class="mc-name ${m.own ? 'own' : ''}" data-mcname="${k}" title="${dbl}" data-no-i18n>⚙ ${esc(m.name)}</span>${m.driver
      ? ` <span class="mc-what" ${m.flat ? '' : `data-mcmo="${k}" title="${dblM}"`} data-no-i18n>· ${m.turn ? '↻' : '↔'} ${esc(m.driver.mo.label)}</span>` : ''}</label>`;
    if (!m.closed) return `<div class="as-dof mc-row bad" data-mckey="${esc(m.key)}">${head}<p class="mp-count bad">${esc(t2('⚠ The closed loop {parts} cannot close here — a part is too short or too long for this place.', { parts: m.parts.join('–') }))}</p></div>`;
    let at = 0;
    try { at = posOf(this.asm, m); } catch { at = 0; }
    const u = m.turn ? '°' : 'mm', play = this.playing?.key === m.key, note = this.notes[m.key], open = this.more.has(m.key), tr = this.traces[m.key];
    return `<div class="as-dof mc-row ${play ? 'on' : ''}" data-mckey="${esc(m.key)}">${head}
      <div class="as-dofrow"><input type="range" data-mcv="${k}" min="${m.min}" max="${m.max}" step="${m.turn ? 1 : 0.5}" value="${fmt(at)}" aria-label="${esc(m.name)}">
        <input type="number" step="any" data-mcn="${k}" value="${fmt(at)}"><span class="unit">${u}</span>
        <button class="mini mc-play ${play ? 'on' : ''}" data-mcplay="${k}" title="${esc(t(play ? 'Pause: it stays where it is' : 'Play: the whole mechanism moves, on and on'))}">${play ? '⏸' : '▶'}</button>
        <button class="mini mc-moreb ${open ? 'on' : ''}" data-mcmore="${k}" title="${esc(t('More: what drives it, how fast, ⚠ check the travel, 📈 trace'))}">⋯</button></div>
      ${open ? `<div class="mc-more">
        ${m.drivers.length > 1 ? `<label class="mc-drv">${esc(t('Driven by'))} <select data-mcdrv="${k}">${m.drivers.map((d, i) => `<option value="${i}" ${d === m.driver ? 'selected' : ''} data-no-i18n>${esc(e.partName(e.inst(d.part)?.part))} ${d.part} · ${d.mo.kind === 'turn' ? '↻' : '↔'} ${esc(d.mo.label)}</option>`).join('')}</select></label>` : ''}
        <div class="mc-acts"><select class="as-dspeed" data-mcspeed="${k}" title="${esc(t('How fast ▶ plays'))}">${SPEEDS.map(([v, l]) => `<option value="${v}" ${m.speed === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
          <button class="btn small" data-mccheck="${k}" title="${esc(t('Move it over its whole travel in small steps and check for collisions on the way'))}">${esc(t('⚠ Check the travel'))}</button>
          ${m.parts.length > 1 ? `<button class="btn small ${tr ? 'on' : ''}" data-mctrace="${k}" title="${esc(t('How another part of it moves over the travel: a curve'))}">📈 ${esc(t('Trace'))}</button>` : ''}</div>
        ${animHtml(this, m, k)}
        ${note ? `<p class="mp-count as-dofnote ${note.bad ? 'bad' : ''}" data-no-i18n>${esc(note.text)}</p>` : ''}
        ${tr ? this.traceSvg(m, tr, at) : ''}</div>` : ''}</div>`;
  }

  /** 📈 The trace as a small curve: the driver across, the follower up; a line where the driver is now. */
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
      sl.addEventListener('input', () => { this.stop(false); num.value = fmt(+sl.value); driveTo(asm, m, +sl.value); this.mark(m); });
      sl.addEventListener('change', () => { driveTo(asm, m, +sl.value, true); });
    }
    for (const num of this.box.querySelectorAll('[data-mcn]')) {
      num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
      num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) { this.stop(false); driveTo(asm, row(num, 'mcn'), v, true); } });
    }
    for (const b of this.box.querySelectorAll('[data-mcplay]')) b.addEventListener('click', () => { const m = row(b, 'mcplay'); if (this.playing?.key === m.key) this.stop(); else this.play(m); });
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
    const p = this.playing = { key: m.key, dir: 1, v: at, last: performance.now(), speed: m.speed };
    this.draw();
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
      const e = engOf(this.asm, m), r = await e.checkTravel(m.driver.part, m.driver.mo, 24, { min: m.full ? 0 : m.min, max: m.full ? 360 : m.max });
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
          drivers: m.drivers.map((d) => `${d.part} motion ${idx(d)}: ${d.mo.label}`) } : {}) };
    });
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

