// ⏺ Recording of moves: the user says "look what I'm doing", works, and the AI reads what they did. Switched on by the
// top bar's ⏺ (or the AI's start_recording), it runs until stopped — across workspaces, parts and a reload — and keeps
// a compact log (the browser session, the newest 2000 events): clicks with where they were and what was under them,
// drags as one event with their path (sampled), keys, values typed, suggestion rows run, picks (as the AI's tools name
// them), undo / redo, steps added / changed / deleted, joints added, workspace and part switches, and every toast —
// the errors and refusals with their text. No plain mouse movement. A few small screenshots at key moments (an error,
// a step done), at most one every 5 s, with the clicks / the drag that led to them marked. Hooked centrally: the
// document's pointer / click / key / change events, History (history.js watchers), the suggestions table
// (a3d:select) and the toast stack (a MutationObserver) — no calls sprinkled through the workspaces.
import { t } from './i18n.js';
import { History } from './history.js';

const KEY = 'a3d.rec', SHOTS_KEY = 'a3d.recShots';
const MAX = 2000, MAX_SHOTS = 12, SHOT_GAP_MS = 5000, SHOT_W = 800; // events kept; screenshots kept / how often / how wide
const PATH_MS = 50, PATH_PX = 8, DRAG_PX = 5;                       // a drag's samples: every 50 ms and 8 px; a click moves less than 5 px
const MODS = (e) => ['ctrl', 'shift', 'alt'].filter((m) => e[`${m}Key`] || (m === 'ctrl' && e.metaKey));
const OFF = '#aiDrawer, #tab-ai, .ai-drawer, .rec-pill, #recBtn'; // (the chat and the recording's own controls: not recorded)
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const r3 = (v) => +(+v).toFixed(3);
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const short = (v, n = 60) => { const s = typeof v === 'string' ? v : JSON.stringify(v); return s === undefined ? '—' : s.length > n ? `${s.slice(0, n - 1)}…` : s; };

/** The view on screen (the 3D view, the drawing, the sheet). */
const viewEl = () => [...document.querySelectorAll('section.viewport')].find((v) => v.offsetParent && v.getBoundingClientRect().width > 0);
/** A screen point -> {at: [x, y] 0 … 1 across and down the view (as gui_action's at) or none outside it, px: in the
 *  pixels of get_screenshot {ui: true} (the window, scaled to at most 1400 px wide)}. */
function placeOf(x, y) {
  const v = viewEl()?.getBoundingClientRect(), k = Math.min(1, 1400 / innerWidth);
  const inView = v && x >= v.left && x <= v.right && y >= v.top && y <= v.bottom;
  return { ...(inView ? { at: [r3((x - v.left) / v.width), r3((y - v.top) / v.height)] } : {}), px: [Math.round(x * k), Math.round(y * k)] };
}

/** A control's name as gui_state gives it (its text, its field's label, a step's id). */
function nameOf(el) {
  if (!el) return '';
  const item = el.closest('.mt-item');
  if (item) return `${(item.querySelector('.mt-name')?.textContent || '').trim()}${item.dataset.id ? ` [${item.dataset.id}]` : ''}`.slice(0, 80);
  const lab = el.closest('label'), row = el.closest('[data-jrow], .as-dof, .as-rot, .field');
  let s = el.matches('input, select, textarea') ? (lab?.textContent || el.placeholder || el.dataset.k || el.name || el.title || '') : (el.textContent || el.title || el.getAttribute('aria-label') || '');
  s = s.replace(/\s+/g, ' ').trim();
  if (el.matches('input, select, textarea') && row && row !== lab) {
    const n = (row.querySelector('label, .as-jt')?.textContent || '').replace(/\s+/g, ' ').trim();
    if (n && n !== s) s = `${n} › ${s}`.trim();
  }
  return (s || el.title || el.className || el.tagName.toLowerCase()).slice(0, 80);
}

class Recorder {
  constructor() {
    this.on = false;
    this.by = 'user';
    this.reason = '';
    this.t0 = 0;
    this.tEnd = 0;
    this.n = 0;            // the next event's index (kept going when the oldest are dropped)
    this.events = [];
    this.shots = [];       // [{id, i, t, data (PNG base64)}]
    this.nShot = 0;
    this.lastShot = {};    // when the last picture was taken: of a message, of a step done
    this.sent = -1;        // the last event index attached to a chat message
    this.listeners = new Set();
    this.ctx = null;
    this.where = '';
  }

  // ------------------------------------------------------------------ the session's copy (a reload goes on)
  load() {
    try {
      const s = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (s) Object.assign(this, { on: !!s.on, by: s.by || 'user', reason: s.reason || '', t0: s.t0 || 0, tEnd: s.tEnd || 0, n: s.n || 0, events: s.events || [], sent: s.sent ?? -1, nShot: s.nShot || 0 });
      this.shots = JSON.parse(sessionStorage.getItem(SHOTS_KEY) || '[]');
    } catch { /* private window, a broken copy: a fresh start */ }
  }

  save(now = false) {
    clearTimeout(this.saveTimer);
    const go = () => {
      try { sessionStorage.setItem(KEY, JSON.stringify({ on: this.on, by: this.by, reason: this.reason, t0: this.t0, tEnd: this.tEnd, n: this.n, events: this.events, sent: this.sent, nShot: this.nShot })); } catch { /* full */ }
      for (;;) { // (the pictures: the oldest go when they do not fit)
        try { sessionStorage.setItem(SHOTS_KEY, JSON.stringify(this.shots)); break; } catch { if (!this.shots.length) break; this.shots.shift(); }
      }
    };
    if (now) go(); else this.saveTimer = setTimeout(go, 400);
  }

  listen(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  changed() { for (const fn of this.listeners) fn(this); }

  // ------------------------------------------------------------------ start / stop
  start(by = 'user', reason = '') {
    if (this.on) return false;
    Object.assign(this, { on: true, by, reason, t0: Date.now(), tEnd: 0, n: 0, events: [], shots: [], nShot: 0, lastShot: {}, sent: -1, where: '' });
    this.push('start', { by, ...(reason ? { reason } : {}) });
    this.save(true);
    this.changed();
    return true;
  }

  stop(by = 'user') {
    if (!this.on) return false;
    this.endDrag();
    this.push('stop', { by });
    this.on = false;
    this.tEnd = Date.now();
    this.save(true);
    this.changed();
    return true;
  }

  get seconds() { return this.t0 ? ((this.on ? Date.now() : this.tEnd || Date.now()) - this.t0) / 1000 : 0; }

  /** Where the user is: {ws, part, step} (the workspace, the part on screen, the step being made / changed). */
  context() {
    const c = this.ctx;
    if (!c) return {};
    const ws = c.state.workspace, p = c.project.current, cmd = ws === 'model' ? c.modeler.cmd?.feature : null;
    return { ws, ...(p ? { part: `${p.name} (${p.id})` } : {}), ...(cmd ? { step: `${cmd.id} ${cmd.type}` } : ws === 'model' && c.modeler.selected ? { sel: c.modeler.selected } : {}) };
  }

  /** One event: its kind and data, with the time and where it happened; a workspace / part switch first, when there
   *  was one since the last event. -> the event (or null when not recording). */
  push(kind, data = {}) {
    if (!this.on) return null;
    if (this.typed && kind !== 'value') this.flushTyped(); // (a value typed before what follows it)
    return this.add(kind, data, this.noticeSwitch());
  }

  /** A workspace / part switch since the last event: a switch event. -> the context now. */
  noticeSwitch() {
    const cx = this.context(), where = `${cx.ws || ''}|${cx.part || ''}`;
    if (this.where && where !== this.where) this.add('switch', { to: [cx.ws, cx.part].filter(Boolean).join(' · ') }, cx);
    this.where = where;
    return cx;
  }

  add(kind, data, cx) {
    const e = { i: this.n++, t: +((Date.now() - this.t0) / 1000).toFixed(1), kind, ...data, ws: cx.ws, ...(cx.part ? { part: cx.part } : {}), ...(cx.step ? { step: cx.step } : {}) };
    this.events.push(e);
    if (this.events.length > MAX) this.events.splice(0, this.events.length - MAX);
    this.save();
    this.changed();
    return e;
  }

  // ------------------------------------------------------------------ hooks
  init(ctx) {
    this.ctx = ctx;
    this.load();
    if (this.on) { this.where = ''; this.push('reload', { note: 'the page was loaded again — the recording goes on' }); }
    this.pill = document.createElement('div');
    this.pill.className = 'rec-pill';
    this.pill.hidden = true;
    this.pill.dataset.noI18n = '';
    document.body.appendChild(this.pill);
    this.btn = document.getElementById('recBtn');
    this.btn?.addEventListener('click', () => (this.on ? this.stop('user') : this.start('user')));
    this.listen(() => this.draw());
    window.addEventListener('a3d:lang', () => this.draw(true));
    setInterval(() => { if (this.on) { this.noticeSwitch(); this.draw(); } }, 1000); // (the time; a switch with nothing done after it)
    this.draw(true);
    this.hookPointer();
    this.hookKeys();
    this.hookToasts();
    History.watchers.add((h, dir) => { try { this.onHistory(h, dir); } catch { /* the recording never breaks an undo */ } });
    window.addEventListener('a3d:select', (e) => this.onSelect(e.detail));
    window.addEventListener('pagehide', () => this.save(true));
    window.addEventListener('wheel', (e) => this.onWheel(e), { capture: true, passive: true });
  }

  /** The indicator at the top centre of the view (every workspace) and the top bar's ⏺. */
  draw(full = false) {
    this.btn?.classList.toggle('on', this.on);
    const tip = t(this.on ? 'Recording your moves for the AI — click to stop' : '⏺ Recording of moves: the AI sees what you do (clicks, commands, values, errors) — click to start, click again to stop');
    if (this.btn && this.btn.title !== tip) this.btn.title = tip; // (not set again every second)
    const p = this.pill;
    if (!p) return;
    p.hidden = !this.on;
    if (!this.on) return;
    if (full || !p.firstChild || p.dataset.lang !== t('Recording moves')) {
      p.dataset.lang = t('Recording moves');
      p.innerHTML = `<span class="rec-dot"></span><b>${esc(t('Recording moves'))}</b><span class="rec-time"></span><span class="rec-by"></span><button type="button" class="rec-stop" title="${esc(t('Stop the recording — the AI can read it then'))}">■ ${esc(t('Stop'))}</button>`;
      p.querySelector('.rec-stop').addEventListener('click', (e) => { e.stopPropagation(); this.stop('user'); });
      for (const ev of ['pointerdown', 'pointerup', 'dblclick']) p.addEventListener(ev, (x) => x.stopPropagation());
    }
    p.querySelector('.rec-time').textContent = `· ${clock(this.seconds)}`;
    p.querySelector('.rec-by').textContent = this.by === 'ai' ? `(${t('started by the AI')})` : '';
    p.title = this.reason ? `${t('Started by the AI')}: ${this.reason}` : t('Your clicks, commands, values and the app\'s messages are kept for the AI (not plain mouse movement)');
    const v = viewEl()?.getBoundingClientRect() || document.querySelector('main.layout')?.getBoundingClientRect();
    if (!v) return;
    // under the view's toolbar and its hint line (what to click next), not over them
    const below = [...(viewEl()?.querySelectorAll(':scope > .m-cmdbar, :scope > .m-hint:not([hidden])') || [])].map((el) => el.getBoundingClientRect()).filter((r) => r.height);
    const top = Math.max(v.top, ...below.map((r) => r.bottom));
    p.style.left = `${Math.round(v.left + v.width / 2)}px`;
    p.style.top = `${Math.round(top + 6)}px`;
  }

  /** What is under a screen point, as the AI's tools name it: a face ("F2:end"), an edge ("edge F2:end|F1:side:0"), a
   *  snap point, an assembly's part / face ("I2 F2:end"), a sheet's dimension / view / cell, a control. */
  underAt(x, y) {
    const el = document.elementFromPoint(x, y), c = this.ctx;
    if (!el || !c) return undefined;
    const d = el.closest('[data-dim]'), cell = el.closest('[data-tcell]'), view = el.closest('[data-view]'), ctl = el.closest('button, a, input, select, textarea, label, .chip, .mt-item');
    if (d) return `dimension ${d.dataset.dim}`;
    if (cell) return `title cell ${cell.dataset.tcell}`;
    if (view) return `view ${view.dataset.view}`;
    if (ctl) return `${ctl.tagName === 'INPUT' ? 'field' : 'button'} ${nameOf(ctl)}`;
    if (el.tagName !== 'CANVAS') return undefined;
    try {
      if (c.state.workspace === 'model' && el.closest('#modelViewport')) {
        const m = c.modeler, v = m.view;
        if (m.mode === 'sketch') {
          const uv = v.planePoint(x, y, m.frame());
          return uv ? `sketch point [${uv.map((q) => +q.toFixed(2)).join(', ')}]` : 'the sketch';
        }
        const s = v.measurePoint?.(x, y), ei = v.pickEdge(x, y, 6), h = v.pick(x, y);
        const snap = s?.snap && s.snap !== 'point' ? `${s.snap} ` : s?.id ? `point ${s.id} ` : '';
        if (ei >= 0) { const r = m.edgeRef(ei); return `${snap}edge ${r ? `${r.a}|${r.b}` : `#${ei}`}`; }
        if (h?.face) return `${snap}face ${h.face.name}`;
        return snap ? snap.trim() : 'empty space';
      }
      if (c.state.workspace === 'assembly' && el.closest('#asmViewport')) {
        const h = c.assembly.view.pickInst?.(x, y), inst = h?.inst?.id || h?.inst;
        return h ? `part ${inst}${h.face?.name ? ` face ${h.face.name}` : ''}` : 'empty space';
      }
    } catch { /* a view not built yet */ }
    return 'the view';
  }

  /** Is a view moved by this drag (orbit / pan) or a thing in it (a part, a dimension, a hole, a sketch shape)? */
  dragKind() {
    const c = this.ctx, v = c?.state.workspace === 'model' ? c.modeler.view : c?.state.workspace === 'assembly' ? c.assembly.view : null;
    if (!v?.controls) return 'drag';
    return v.controls.enabled ? 'view' : 'object';
  }

  hookPointer() {
    // a press: where, which button, the keys held, what is under it; held and moved: its path (sampled); let go: one
    // event — a click (or a double-click), or a drag with its points
    document.addEventListener('pointerdown', (e) => {
      if (!this.on || e.pointerType === 'touch' && !e.isPrimary) return;
      if (e.target.closest?.(OFF)) { this.down = null; return; }
      const p = placeOf(e.clientX, e.clientY);
      this.down = { x: e.clientX, y: e.clientY, x1: e.clientX, y1: e.clientY, tm: performance.now(), button: ['left', 'middle', 'right'][e.button] || `button ${e.button}`,
        mods: MODS(e), under: this.underAt(e.clientX, e.clientY), el: e.target, path: [p], far: false, of: null };
    }, true);
    document.addEventListener('pointermove', (e) => {
      const d = this.down;
      if (!d || !this.on || !e.buttons) return;
      const now = performance.now();
      if (!d.far && Math.hypot(e.clientX - d.x, e.clientY - d.y) >= DRAG_PX) d.far = true;
      if (d.far && now - d.tm >= PATH_MS && Math.hypot(e.clientX - d.x1, e.clientY - d.y1) >= PATH_PX) {
        d.path.push(placeOf(e.clientX, e.clientY));
        Object.assign(d, { x1: e.clientX, y1: e.clientY, tm: now });
        if (!d.of) d.of = this.dragKind();
      }
    }, true);
    const up = (e) => {
      const d = this.down;
      this.down = null;
      if (!d || !this.on) return;
      const p = placeOf(e.clientX, e.clientY), ctl = d.el?.closest?.('button, a, .chip, .mt-item, [data-sg], [data-sgc]');
      if (d.far) {
        d.path.push(p);
        this.push('drag', { button: d.button, ...(d.mods.length ? { keys: d.mods } : {}), of: d.of || this.dragKind(),
          from: d.under, to: this.underAt(e.clientX, e.clientY), path: d.path.map((q) => q.at || null), path_px: d.path.map((q) => q.px) });
        return;
      }
      const ev = { button: d.button, ...(d.mods.length ? { keys: d.mods } : {}), ...p, ...(d.under ? { on: d.under } : {}) };
      this.lastClick = { e: this.push('click', ev), el: ctl, tm: Date.now() };
    };
    document.addEventListener('pointerup', up, true);
    document.addEventListener('pointercancel', () => { this.down = null; }, true);
    // a click: a control pressed (with the mouse: added to its click event; with the keyboard: its own) — a suggestion
    // row run, a command, OK / Cancel …
    document.addEventListener('click', (e) => {
      if (!this.on || e.target.closest?.(OFF)) return;
      const el = e.target.closest?.('button, a, .chip, .mt-item, [role=menuitem], label.menu-item');
      if (!el) return;
      const row = el.closest('[data-sg], [data-sgc]'), box = el.closest('.view-suggest, .sg-menu');
      const what = row && box?.sg ? { kind: 'suggest', row: nameOf(row), table: box.sg.title, ...(box.sg.refs ? { about: box.sg.refs } : {}) } : { kind: 'press', control: nameOf(el) };
      const lc = this.lastClick;
      if (lc && Date.now() - lc.tm < 600 && lc.e && !lc.e.control && !lc.e.row && (lc.el === el || lc.el?.contains(el) || el.contains(lc.el))) {
        delete lc.e.on; // (the control names it)
        if (what.kind === 'suggest') Object.assign(lc.e, { kind: 'suggest', row: what.row, table: what.table, ...(what.about ? { about: what.about } : {}) });
        else lc.e.control = what.control;
        this.save();
        return;
      }
      const { kind, ...rest } = what;
      this.push(kind, { ...rest, ...(e.detail === 0 ? { via: 'keyboard' } : {}) });
    }, true);
    document.addEventListener('dblclick', (e) => {
      const lc = this.lastClick;
      if (this.on && lc?.e && Date.now() - lc.tm < 600 && !e.target.closest?.(OFF)) { lc.e.double = true; this.save(); }
    }, true);
    // a value typed / chosen in a field: when it is let go (its change), or typing stopped for a moment (a panel drawn
    // anew while typing never sends its change); the same value of the same field once
    const valueOf = (el) => (el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.type === 'file' ? [...(el.files || [])].map((f) => f.name).join(', ')
      : el.tagName === 'SELECT' ? (el.selectedOptions[0]?.textContent?.trim() || el.value) : el.value);
    const field = (e) => { const el = e.target; return this.on && el.matches?.('input, select, textarea') && !el.closest(OFF) ? el : null; };
    document.addEventListener('input', (e) => {
      const el = field(e);
      if (!el || el.type === 'checkbox' || el.type === 'radio' || el.type === 'file') return;
      this.typed = { field: nameOf(el), value: valueOf(el) };
      clearTimeout(this.typedTimer);
      this.typedTimer = setTimeout(() => this.flushTyped(), 900);
    }, true);
    document.addEventListener('change', (e) => {
      const el = field(e);
      if (!el) return;
      this.typed = { field: nameOf(el), value: valueOf(el) };
      this.flushTyped();
    }, true);
  }

  /** The value being typed, as an event (not twice). */
  flushTyped() {
    clearTimeout(this.typedTimer);
    const v = this.typed;
    this.typed = null;
    if (!v || !this.on) return;
    const last = [...this.events].reverse().find((e) => e.kind === 'value');
    if (last && last.field === v.field && last.value === v.value && this.events.length - this.events.indexOf(last) < 4) return;
    this.push('value', v);
  }

  hookKeys() {
    document.addEventListener('keydown', (e) => {
      if (!this.on || e.repeat || ['Control', 'Shift', 'Alt', 'Meta'].includes(e.key) || e.target.closest?.(OFF)) return;
      const typing = e.target.matches?.('input:not([type=checkbox]):not([type=range]), textarea, [contenteditable]');
      const named = ['Escape', 'Enter', 'Delete', 'Tab'].includes(e.key) || /^F\d+$/.test(e.key);
      if (typing && (!named || e.key === 'Tab')) return; // (letters, Ctrl+A … in a field: its value when it is set)
      const key = [...MODS(e).filter((m) => m !== 'shift' || e.key.length > 1), e.key === ' ' ? 'Space' : e.key.length === 1 ? e.key.toLowerCase() : e.key].join('+');
      this.push('key', { key, ...(typing ? { in: nameOf(e.target) } : {}) });
    }, true);
  }

  /** Every message of the app (toasts): its text, an error / a refusal with a screenshot. */
  hookToasts() {
    const stack = document.getElementById('toasts');
    if (!stack) return;
    new MutationObserver((muts) => {
      if (!this.on) return;
      for (const m of muts) for (const n of m.addedNodes) {
        if (n.nodeType !== 1 || !n.classList.contains('toast')) continue;
        const kind = ['error', 'warning', 'ok', 'success'].find((k) => n.classList.contains(k)) || 'info';
        const text = n.textContent.replace(/\s+/g, ' ').trim();
        const ev = this.push('toast', { level: kind, text: text.slice(0, 400) });
        if (ev && (kind === 'error' || kind === 'warning')) this.shoot(ev);
      }
    }).observe(stack, { childList: true });
  }

  /** What is selected (the suggestions table's refs, as the AI's tools name it), when it changed. */
  onSelect({ title, refs, n }) {
    if (!this.on) return;
    const key = n ? `${title}|${refs}` : '';
    if (key === this.selKey) return;
    this.selKey = key;
    this.push('select', n ? { what: refs || title, table: title, rows: n } : { what: null });
  }

  onWheel(e) {
    if (!this.on || !e.target.closest?.('section.viewport') || e.target.closest(OFF)) return;
    const last = this.events[this.events.length - 1];
    if (last?.kind === 'view' && Date.now() - (this.wheelAt || 0) < 1500) { last.zoom += e.deltaY < 0 ? 1 : -1; this.save(); } // (one event while it goes on)
    else this.push('view', { zoom: e.deltaY < 0 ? 1 : -1, ...placeOf(e.clientX, e.clientY) });
    this.wheelAt = Date.now();
  }

  /** A history step (dir 0: recorded; -1 undo; +1 redo): undo / redo said, and what changed — steps of a 3D model
   *  added / changed / deleted, an assembly's parts, joints, couplings. */
  onHistory(h, dir) {
    if (!this.on) return;
    if (dir) this.push(dir < 0 ? 'undo' : 'redo', {});
    const before = dir > 0 ? h.undo[h.undo.length - 1] : dir < 0 ? h.redo[h.redo.length - 1] : h.undo[h.undo.length - 1];
    const now = h.base;
    if (!before || !now) return;
    let done = false;
    for (const [key, word] of [['features', 'step'], ['instances', 'part'], ['mates', 'joint'], ['couplings', 'coupling'], ['harnesses', 'harness']]) {
      if (!Array.isArray(now[key]) && !Array.isArray(before[key])) continue;
      const a = new Map((before[key] || []).map((x) => [x.id, x])), b = new Map((now[key] || []).map((x) => [x.id, x]));
      const what = (x) => ({ id: x.id, ...(x.type ? { type: x.type } : {}), ...(x.name ? { name: x.name } : {}), ...(x.part ? { of: x.part } : {}), ...(x.move ? { move: x.move, onto: x.onto } : {}) });
      for (const [id, x] of b) {
        if (!a.has(id)) { this.push(`${word} added`, { ...what(x), ...(dir ? { by: dir < 0 ? 'undo' : 'redo' } : {}) }); done = true; continue; }
        const y = a.get(id);
        if (JSON.stringify(x) === JSON.stringify(y)) continue;
        const fields = [...new Set([...Object.keys(x), ...Object.keys(y)])].filter((k) => JSON.stringify(x[k]) !== JSON.stringify(y[k])).slice(0, 6);
        const changes = Object.fromEntries(fields.map((k) => [k, Array.isArray(x[k]) || Array.isArray(y[k]) ? `${(y[k] || []).length} → ${(x[k] || []).length} items` : `${short(y[k], 40)} → ${short(x[k], 40)}`]));
        this.push(`${word} changed`, { ...what(x), changes, ...(dir ? { by: dir < 0 ? 'undo' : 'redo' } : {}) });
        done = true;
      }
      for (const [id, y] of a) if (!b.has(id)) { this.push(`${word} deleted`, { ...what(y), ...(dir ? { by: dir < 0 ? 'undo' : 'redo' } : {}) }); done = true; }
    }
    if (done && !dir) this.shoot(this.events[this.events.length - 1]); // (a command finished: what it looks like)
  }

  // ------------------------------------------------------------------ screenshots
  /** A small picture of the window for event `ev` (at most one every 5 s): the clicks of the last 5 s and the drag that
   *  led to it marked in red. */
  async shoot(ev) {
    const why = ev?.kind === 'toast' ? 'msg' : 'step'; // (an error is not kept from its picture by a step done just before)
    if (!ev || Date.now() - (this.lastShot[why] || 0) < SHOT_GAP_MS || this.shooting) return;
    this.lastShot[why] = Date.now();
    this.shooting = true;
    try {
      const { screenshotUI } = await import('./agent_more.js');
      const r = await screenshotUI();
      const img = await new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = `data:image/png;base64,${r.image}`; });
      const k = Math.min(1, SHOT_W / img.width), c = document.createElement('canvas');
      c.width = Math.round(img.width * k);
      c.height = Math.round(img.height * k);
      const g = c.getContext('2d');
      g.drawImage(img, 0, 0, c.width, c.height);
      g.strokeStyle = '#ff3b30';
      g.fillStyle = '#ff3b30';
      g.lineWidth = 2;
      const since = Date.now() - SHOT_GAP_MS, recent = this.events.filter((x) => x.kind === 'click' || x.kind === 'suggest' || x.kind === 'drag').filter((x) => this.t0 + x.t * 1000 >= since);
      for (const x of recent) {
        if (x.kind === 'drag') {
          g.beginPath();
          x.path_px.forEach(([px, py], j) => (j ? g.lineTo(px * k, py * k) : g.moveTo(px * k, py * k)));
          g.stroke();
          const [ex, ey] = x.path_px[x.path_px.length - 1];
          g.beginPath(); g.arc(ex * k, ey * k, 4, 0, 7); g.fill();
        } else if (x.px) { g.beginPath(); g.arc(x.px[0] * k, x.px[1] * k, 7, 0, 7); g.stroke(); }
      }
      const id = `S${++this.nShot}`;
      this.shots.push({ id, i: ev.i, t: ev.t, data: c.toDataURL('image/png').split(',')[1] });
      if (this.shots.length > MAX_SHOTS) this.shots.shift();
      ev.shot = id;
      this.save();
    } catch { /* no picture this time */ }
    this.shooting = false;
  }

  endDrag() { this.down = null; }

  // ------------------------------------------------------------------ reading it
  /** The events from `since` (an event index) or the last `last`; paths false: the drags without their points.
   *  Where (workspace / part / step) is given when it differs from the event before it in the list. */
  read({ since, last, paths = true } = {}) {
    let list = this.events;
    if (Number.isFinite(+since) && since !== null && since !== undefined) list = list.filter((e) => e.i >= +since);
    if (Number.isFinite(+last) && last !== null && last !== undefined && +last > 0) list = list.slice(-Math.round(+last));
    let prev = '';
    return list.map(({ ws, part, step, ...e }) => {
      const where = [ws, part, step].filter(Boolean).join(' · '), out = { ...e };
      if (where !== prev) out.where = where;
      prev = where;
      if (!paths && e.kind === 'drag') { out.points = e.path.length; out.from_px = e.path_px[0]; out.to_px = e.path_px[e.path_px.length - 1]; delete out.path; delete out.path_px; }
      return out;
    });
  }

  /** One event as a line of text (the chat's attachment). */
  line(e) {
    const { i, t: s, kind, where, ...rest } = e;
    delete rest.path; delete rest.path_px;
    const bits = Object.entries(rest).map(([k, v]) => `${k}: ${short(v, 120)}`).join(', ');
    return `${clock(s)}${where ? ` [${where}]` : ''} ${kind}${bits ? ` — ${bits}` : ''}`;
  }

  /** The stopped recording for a chat message: what it is, then its last events as lines. */
  forChat(max = 60) {
    const list = this.read({ paths: false }), cut = list.slice(-max);
    this.sent = this.n - 1;
    this.save(true);
    this.changed();
    return `[⏺ Recording of my moves: ${list.length} events over ${clock(this.seconds)}${cut.length < list.length ? ` — the last ${cut.length} below; get_recording for all` : ''}${this.shots.length ? `; screenshots ${this.shots.map((x) => x.id).join(', ')} (get_recording_screenshot)` : ''}]\n${cut.map((e) => this.line(e)).join('\n')}`;
  }

  /** A stopped recording not attached to a message yet: how many events it has (else 0). */
  attachable() { return !this.on && this.events.length > 2 && this.sent < this.n - 1 ? this.events.length : 0; }
}

export const recorder = new Recorder();

/** The AI's tools: start / stop the recording, read it, a screenshot of it. */
export function recordHandlers() {
  const state = () => ({ running: recorder.on, started_by: recorder.by, ...(recorder.reason ? { reason: recorder.reason } : {}), seconds: Math.round(recorder.seconds), count: recorder.events.length, next: recorder.n });
  return {
    start_recording: async ({ reason = '' } = {}) => {
      if (recorder.on) return { text: `The recording already runs (started by ${recorder.by === 'ai' ? 'you' : 'the user'}, ${Math.round(recorder.seconds)} s, ${recorder.events.length} events). get_recording reads it.` };
      recorder.start('ai', String(reason || '').slice(0, 200));
      return { text: 'Recording the user\'s moves — the user sees “⏺ Recording moves (started by the AI)” at the top of the view and can stop it. Tell them to go ahead and say when they are done; then get_recording (and stop_recording when they did not stop it).' };
    },
    stop_recording: async () => {
      const was = recorder.stop('ai');
      return { text: `${was ? 'Stopped' : 'It was not running'}: ${JSON.stringify(state())}. get_recording reads it.` };
    },
    get_recording: async ({ since, last, paths = true } = {}) => {
      const events = recorder.read({ since, last, paths });
      if (!recorder.events.length) return { text: 'Nothing recorded — start_recording (when the user asks you to watch), or the user switches ⏺ on in the top bar.' };
      return { text: JSON.stringify({ ...state(), dropped: recorder.events[0].i, shots: recorder.shots.map(({ id, i, t: s }) => ({ id, event: i, t: s })), events }) };
    },
    get_recording_screenshot: async ({ id }) => {
      const s = recorder.shots.find((x) => x.id === String(id));
      if (!s) throw new Error(`No screenshot ${id} — get_recording lists them (shots: ${recorder.shots.map((x) => x.id).join(', ') || 'none'}).`);
      return { text: `Screenshot ${s.id} at ${s.t} s (event ${s.i}): the window as the user saw it, their clicks of the 5 s before as red rings, a drag as a red line ending in a dot.`, image: s.data };
    },
  };
}
