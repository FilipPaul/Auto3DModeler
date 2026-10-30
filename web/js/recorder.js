// ⏺ Recording of moves: the user says "look what I'm doing", works, and the AI reads what they did. Switched on by the
// top bar's ⏺ (or the AI's start_recording), it runs until stopped — across workspaces, parts and a reload — and keeps
// a compact log (the browser session, the newest 2000 events): clicks with where they were and what was under them,
// drags as one event with their path (sampled), keys, values typed, suggestion rows run, picks (as the AI's tools name
// them), undo / redo, steps added / changed / deleted, joints added, workspace and part switches, and every toast —
// the errors and refusals with their text. No plain mouse movement. A few small screenshots at key moments (an error,
// a step done), at most one every 5 s, with the clicks / the drag that led to them marked. Hooked centrally: the
// document's pointer / click / key / change events, History (history.js watchers), the suggestions table
// (a3d:select) and the toast stack (a MutationObserver) — no calls sprinkled through the workspaces.
// Cheap while the user works (it once made the app lag): an event costs well under a millisecond — what is under the
// cursor only on a press / a release, a drag's samples kept as plain numbers, the session's copy written at most once a
// second when the browser is idle and only its newest chunk of events (never the whole log, never the pictures again),
// a screenshot taken when idle, the page walked in slices, encoded off the main thread.
// 📋 Copy the recording (the pill, the chat's 📎): the recording as plain text for the clipboard — a header (the app's
// version and commit, date, workspace, project, part, window, length) and one line per event — to paste into a chat
// with a developer; a blocked clipboard: the text in a panel to copy by hand.
import { t } from './i18n.js';
import { History } from './history.js';
import { pageBuild } from './stale.js';

const KEY = 'a3d.rec', SHOTS_KEY = 'a3d.recShots', PART = 'a3d.rec.'; // the header; (old copies: the pictures); its chunks / pictures
const PAST_KEY = 'a3d.recPast', MAX_PAST = 2;                       // the recordings before the last one, as the chat's text (the last 3 in all)
const MAX = 2000, MAX_SHOTS = 12, SHOT_GAP_MS = 5000, SHOT_W = 800; // events kept; screenshots kept / how often / how wide
const PATH_MS = 50, PATH_PX = 8, DRAG_PX = 5;                       // a drag's samples: every 50 ms and 8 px; a click moves less than 5 px
const CHUNK = 100, SAVE_MS = 1000;                                  // events per stored chunk; the copy written at most once a second
const COPY_MAX = 90000, COPY_HEAD = 0.3;                            // 📋 the copied text's bytes at most; its first events' share of them
const chunkKey = (c) => `${PART}c${c}`, shotKey = (id) => `${PART}s${id}`;
const PASSIVE = { capture: true, passive: true }; // (the page's events heard first, never held up or stopped)
const idle = (fn, timeout = 1000) => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout }) : setTimeout(fn, 1));
const MODS = (e) => ['ctrl', 'shift', 'alt'].filter((m) => e[`${m}Key`] || (m === 'ctrl' && e.metaKey));
const ZOOMS = 'canvas, .sh-stage'; // (what the wheel zooms: a view's canvas, the drawing sheet's stage)
const OFF = '#aiDrawer, #tab-ai, .ai-drawer, .rec-pill, #recBtn, .rec-copy'; // (the chat and the recording's own controls: not recorded)
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const r3 = (v) => +(+v).toFixed(3);
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const short = (v, n = 60) => { const s = typeof v === 'string' ? v : JSON.stringify(v); return s === undefined ? '—' : s.length > n ? `${s.slice(0, n - 1)}…` : s; };
const bytes = (s) => new TextEncoder().encode(s).length;
const two = (v) => String(v).padStart(2, '0');
/** A time as "2026-10-30 11:24:05 (UTC+01:00)". */
const stamp = (ms) => {
  const d = new Date(ms), o = -d.getTimezoneOffset();
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())} (UTC${o < 0 ? '-' : '+'}${two(Math.floor(Math.abs(o) / 60))}:${two(Math.abs(o) % 60)})`;
};

/** The view on screen (the 3D view, the drawing, the sheet). */
const viewEl = () => [...document.querySelectorAll('section.viewport')].find((v) => v.offsetParent && v.getBoundingClientRect().width > 0);
/** A screen point -> {at: [x, y] 0 … 1 across and down the view (as gui_action's at) or none outside it, px: in the
 *  pixels of get_screenshot {ui: true} (the window, scaled to at most 1400 px wide)}. */
function placeOf(x, y, v = viewEl()?.getBoundingClientRect()) {
  const k = Math.min(1, 1400 / innerWidth);
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
    this.past = [];        // the recordings before this one, newest first: [{id, t0, seconds, count, sent, text}] (the chat's 📎 ▾)
    this.listeners = new Set();
    this.ctx = null;
    this.where = '';
    this.dirty = new Set(); // the chunks of events changed since the last write
    this.stored = new Set(); // the chunks / the pictures in the session's copy
    this.cost = { ms: 0, max: 0, n: 0 }; // the time the recording took from the page (its handlers): the e2e test reads it
    this.meta = {};        // 📋 the project and the window when it started / stopped: {project, w, h, dpr}
    this.version = '';     // 📋 the app's version and commit (/api/version), for the copied text's header
  }

  /** fn timed into this.cost (a handler of the page's events). */
  timed(fn) {
    return (...a) => {
      if (!this.on) return fn(...a);
      const t0 = performance.now();
      try { return fn(...a); } finally { const ms = performance.now() - t0; this.cost.ms += ms; this.cost.n++; if (ms > this.cost.max) this.cost.max = ms; }
    };
  }

  // ------------------------------------------------------------------ the session's copy (a reload goes on)
  // a3d.rec: the header (state, its chunks, its pictures' ids); a3d.rec.c<k>: events k·100 … k·100+99; a3d.rec.s<id>: a picture
  load() {
    try {
      this.past = JSON.parse(sessionStorage.getItem(PAST_KEY) || '[]');
      const s = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (!s) return;
      Object.assign(this, { on: !!s.on, by: s.by || 'user', reason: s.reason || '', t0: s.t0 || 0, tEnd: s.tEnd || 0, n: s.n || 0, sent: s.sent ?? -1, nShot: s.nShot || 0, meta: s.meta || {} });
      const chunks = s.chunks || [];
      this.events = s.events || chunks.flatMap((c) => JSON.parse(sessionStorage.getItem(chunkKey(c)) || '[]')).filter((e) => e.i >= (s.first || 0)); // (the oldest chunk: from the first kept)
      this.shots = s.shots ? s.shots.map((x) => ({ ...x, data: sessionStorage.getItem(shotKey(x.id)) })).filter((x) => x.data)
        : JSON.parse(sessionStorage.getItem(SHOTS_KEY) || '[]'); // (a copy of before the chunks)
      this.stored = new Set([...chunks.map(chunkKey), ...this.shots.map((x) => shotKey(x.id))]);
      if (!s.chunks) for (const e of this.events) this.dirty.add(Math.floor(e.i / CHUNK));
    } catch { /* private window, a broken copy: a fresh start */ }
  }

  /** The session's copy: at most once a second, when the browser is idle (now: at once — a stop, leaving the page). */
  save(now = false) {
    if (now) { clearTimeout(this.saveTimer); this.saveTimer = 0; this.write(); return; }
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => idle(() => { this.saveTimer = 0; this.write(); }), SAVE_MS);
  }

  /** An event changed after it was added (a click named by its control, a picture of it): its chunk written again. */
  touch(e) {
    if (e) this.dirty.add(Math.floor(e.i / CHUNK));
    this.save();
  }

  /** Write the changed chunks, the new pictures and the header; drop what is no longer kept (the oldest pictures go when
   *  the session's storage is full). */
  write() {
    const put = (key, val) => {
      for (;;) {
        try { sessionStorage.setItem(key, val); this.stored.add(key); return true; } catch {
          const old = this.shots.find((x) => this.stored.has(shotKey(x.id)) && shotKey(x.id) !== key);
          if (!old) return false;
          this.shots.splice(this.shots.indexOf(old), 1);
          this.drop(shotKey(old.id));
        }
      }
    };
    const first = this.events[0]?.i ?? this.n, c0 = Math.floor(first / CHUNK);
    const chunks = this.events.length ? Array.from({ length: Math.floor((this.n - 1) / CHUNK) - c0 + 1 }, (_, j) => c0 + j) : [];
    for (const c of [...this.dirty].sort((a, b) => a - b)) {
      if (c < c0) continue;
      put(chunkKey(c), JSON.stringify(this.events.slice(Math.max(0, c * CHUNK - first), Math.max(0, (c + 1) * CHUNK - first))));
    }
    this.dirty.clear();
    for (const x of [...this.shots]) if (!this.stored.has(shotKey(x.id)) && !put(shotKey(x.id), x.data)) this.shots.splice(this.shots.indexOf(x), 1); // (not even alone: not kept)
    const keep = new Set([...chunks.map(chunkKey), ...this.shots.map((x) => shotKey(x.id))]);
    for (const key of [...this.stored]) if (!keep.has(key) && key !== KEY) this.drop(key);
    put(KEY, JSON.stringify({ on: this.on, by: this.by, reason: this.reason, t0: this.t0, tEnd: this.tEnd, n: this.n, sent: this.sent, nShot: this.nShot, first, meta: this.meta,
      chunks, shots: this.shots.filter((x) => this.stored.has(shotKey(x.id))).map(({ id, i, t: s }) => ({ id, i, t: s })) }));
  }

  drop(key) { try { sessionStorage.removeItem(key); } catch { /* gone */ } this.stored.delete(key); }

  /** A new recording: the old one's chunks and pictures out of the session's copy. */
  clear() {
    try {
      for (const key of Object.keys(sessionStorage)) if (key.startsWith(PART)) sessionStorage.removeItem(key);
      sessionStorage.removeItem(SHOTS_KEY);
    } catch { /* none */ }
    this.stored.clear();
    this.dirty.clear();
  }

  listen(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  changed() { for (const fn of this.listeners) fn(this); }

  // ------------------------------------------------------------------ start / stop
  start(by = 'user', reason = '') {
    if (this.on) return false;
    if (this.events.length > 2) { // the one before: kept for the chat's 📎 ▾ (as its text — the events themselves go)
      this.past = [{ id: this.t0, t0: this.t0, seconds: this.seconds, count: this.events.length, sent: this.sent >= this.n - 1, text: this.chatText(), copy: this.copyText() }, ...this.past].slice(0, MAX_PAST);
      try { sessionStorage.setItem(PAST_KEY, JSON.stringify(this.past)); } catch { // full: kept without their 📋 texts (then the chat's text is copied)
        try { sessionStorage.setItem(PAST_KEY, JSON.stringify(this.past.map(({ copy, ...r }) => r))); } catch { /* not kept */ }
      }
    }
    Object.assign(this, { on: true, by, reason, t0: Date.now(), tEnd: 0, n: 0, events: [], shots: [], nShot: 0, lastShot: {}, sent: -1, where: '', meta: this.metaNow() });
    this.clear();
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
    this.meta = { ...this.meta, ...this.metaNow() };
    this.save(true);
    this.changed();
    return true;
  }

  /** The project and the window now (the 📋 header). */
  metaNow() {
    return { project: this.ctx?.state?.projectName || '', w: innerWidth, h: innerHeight, dpr: +(devicePixelRatio || 1).toFixed(2) };
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
    this.touch(e);
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
    setInterval(this.timed(() => { if (this.on) { this.noticeSwitch(); this.draw(); } }), 1000); // (the time; a switch with nothing done after it)
    this.draw(true);
    this.hookPointer();
    this.hookKeys();
    this.hookToasts();
    History.watchers.add(this.timed((h, dir) => { try { this.onHistory(h, dir); } catch { /* the recording never breaks an undo */ } }));
    window.addEventListener('a3d:select', this.timed((e) => this.onSelect(e.detail)));
    window.addEventListener('pagehide', () => this.save(true));
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.save(true); });
    window.addEventListener('wheel', this.timed((e) => this.onWheel(e)), PASSIVE);
    idle(() => this.appVersion(), 3000); // (the 📋 header's version: asked once, before a copy needs it)
    this.changed(); // (a recording kept over a reload: the chat offers its 📎)
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
      p.innerHTML = `<span class="rec-dot"></span><b>${esc(t('Recording moves'))}</b><span class="rec-time"></span><span class="rec-by"></span><button type="button" class="rec-stop" title="${esc(t('Stop the recording — the AI can read it then'))}">■ ${esc(t('Stop'))}</button><button type="button" class="rec-stop rec-send" title="${esc(t('Stop the recording and send it to the AI chat now'))}">➤ ${esc(t('Stop and send to the AI'))}</button><button type="button" class="rec-stop rec-copy-btn" title="${esc(t('Stop the recording and copy it as text — paste it (Ctrl+V) into a chat with a developer or another AI'))}">📋 ${esc(t('Copy the recording'))}</button>`;
      p.querySelector('.rec-stop').addEventListener('click', (e) => { e.stopPropagation(); this.stop('user'); });
      // (the chat hears it: opens, attaches this recording and sends — agent.js)
      p.querySelector('.rec-send').addEventListener('click', (e) => { e.stopPropagation(); if (this.stop('user')) window.dispatchEvent(new CustomEvent('a3d:rec-send', { detail: { id: this.t0 } })); });
      // (📋 stopped, then copied — in the click itself: the clipboard needs the user's gesture)
      p.querySelector('.rec-copy-btn').addEventListener('click', (e) => { e.stopPropagation(); this.stop('user'); this.copy(); });
      for (const ev of ['pointerdown', 'pointerup', 'dblclick']) p.addEventListener(ev, (x) => x.stopPropagation());
    }
    const set = (el, k, v) => { if (el[k] !== v) el[k] = v; }; // (the page not touched when nothing changed — every event draws)
    set(p.querySelector('.rec-time'), 'textContent', `· ${clock(this.seconds)}`);
    set(p.querySelector('.rec-by'), 'textContent', this.by === 'ai' ? `(${t('started by the AI')})` : '');
    set(p, 'title', this.reason ? `${t('Started by the AI')}: ${this.reason}` : t('Your clicks, commands, values and the app\'s messages are kept for the AI (not plain mouse movement)'));
    if (!this.placing) this.placing = requestAnimationFrame(() => { this.placing = 0; this.place(); });
  }

  /** The indicator's place: at the top centre of the view on screen. */
  place() {
    const p = this.pill;
    if (!p || !this.on) return;
    const v = viewEl()?.getBoundingClientRect() || document.querySelector('main.layout')?.getBoundingClientRect();
    if (!v) return;
    // under the view's toolbar and its hint line (what to click next), not over them
    const below = [...(viewEl()?.querySelectorAll(':scope > .m-cmdbar, :scope > .m-hint:not([hidden])') || [])].map((el) => el.getBoundingClientRect()).filter((r) => r.height);
    const top = Math.max(v.top, ...below.map((r) => r.bottom));
    const left = `${Math.round(v.left + v.width / 2)}px`, tp = `${Math.round(top + 6)}px`;
    if (p.style.left !== left) p.style.left = left;
    if (p.style.top !== tp) p.style.top = tp;
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
    // event — a click (or a double-click), or a drag with its points. What is under the cursor: only on the press and the
    // release; the samples: plain numbers (the view's box read once, on the press), made into places on the release
    document.addEventListener('pointerdown', this.timed((e) => {
      if (!this.on || e.pointerType === 'touch' && !e.isPrimary) return;
      if (e.target.closest?.(OFF)) { this.down = null; return; }
      this.down = { x: e.clientX, y: e.clientY, x1: e.clientX, y1: e.clientY, tm: performance.now(), button: ['left', 'middle', 'right'][e.button] || `button ${e.button}`,
        mods: MODS(e), under: this.underAt(e.clientX, e.clientY), el: e.target, box: viewEl()?.getBoundingClientRect(), pts: [e.clientX, e.clientY], far: false, of: null };
    }), PASSIVE);
    document.addEventListener('pointermove', (e) => { // (not timed: a few comparisons per move)
      const d = this.down;
      if (!d || !e.buttons) return;
      const x = e.clientX, y = e.clientY;
      if (!d.far && Math.hypot(x - d.x, y - d.y) >= DRAG_PX) d.far = true;
      if (d.far && Math.hypot(x - d.x1, y - d.y1) >= PATH_PX && e.timeStamp - d.tm >= PATH_MS) {
        d.pts.push(x, y);
        d.x1 = x; d.y1 = y; d.tm = e.timeStamp;
        if (!d.of) d.of = this.dragKind();
      }
    }, PASSIVE);
    const up = this.timed((e) => {
      const d = this.down;
      this.down = null;
      if (!d || !this.on) return;
      const p = placeOf(e.clientX, e.clientY, d.box), ctl = d.el?.closest?.('button, a, .chip, .mt-item, [data-sg], [data-sgc]');
      if (d.far) {
        const path = [];
        for (let j = 0; j < d.pts.length; j += 2) path.push(placeOf(d.pts[j], d.pts[j + 1], d.box));
        path.push(p);
        this.push('drag', { button: d.button, ...(d.mods.length ? { keys: d.mods } : {}), of: d.of || this.dragKind(),
          from: d.under, to: this.underAt(e.clientX, e.clientY), path: path.map((q) => q.at || null), path_px: path.map((q) => q.px) });
        return;
      }
      const ev = { button: d.button, ...(d.mods.length ? { keys: d.mods } : {}), ...p, ...(d.under ? { on: d.under } : {}) };
      this.lastClick = { e: this.push('click', ev), el: ctl, tm: Date.now() };
    });
    document.addEventListener('pointerup', up, PASSIVE);
    document.addEventListener('pointercancel', () => { this.down = null; }, PASSIVE);
    // a click: a control pressed (with the mouse: added to its click event; with the keyboard: its own) — a suggestion
    // row run, a command, OK / Cancel …
    document.addEventListener('click', this.timed((e) => {
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
        this.touch(lc.e);
        return;
      }
      const { kind, ...rest } = what;
      this.push(kind, { ...rest, ...(e.detail === 0 ? { via: 'keyboard' } : {}) });
    }), PASSIVE);
    document.addEventListener('dblclick', (e) => {
      const lc = this.lastClick;
      if (this.on && lc?.e && Date.now() - lc.tm < 600 && !e.target.closest?.(OFF)) { lc.e.double = true; this.touch(lc.e); }
    }, PASSIVE);
    // a value typed / chosen in a field: when it is let go (its change), or typing stopped for a moment (a panel drawn
    // anew while typing never sends its change); the same value of the same field once
    const valueOf = (el) => (el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.type === 'file' ? [...(el.files || [])].map((f) => f.name).join(', ')
      : el.tagName === 'SELECT' ? (el.selectedOptions[0]?.textContent?.trim() || el.value) : el.value);
    const field = (e) => { const el = e.target; return this.on && el.matches?.('input, select, textarea') && !el.closest(OFF) ? el : null; };
    document.addEventListener('input', this.timed((e) => {
      const el = field(e);
      if (!el || el.type === 'checkbox' || el.type === 'radio' || el.type === 'file') return;
      this.typed = { field: nameOf(el), value: valueOf(el) };
      clearTimeout(this.typedTimer);
      this.typedTimer = setTimeout(this.timed(() => this.flushTyped()), 900);
    }), PASSIVE);
    document.addEventListener('change', this.timed((e) => {
      const el = field(e);
      if (!el) return;
      this.typed = { field: nameOf(el), value: valueOf(el) };
      this.flushTyped();
    }), PASSIVE);
  }

  /** The value being typed, as an event (not twice). */
  flushTyped() {
    clearTimeout(this.typedTimer);
    const v = this.typed;
    this.typed = null;
    if (!v || !this.on) return;
    const ev = this.events, last = [ev[ev.length - 1], ev[ev.length - 2], ev[ev.length - 3]].find((e) => e?.kind === 'value'); // (the last value of the last three events)
    if (last && last.field === v.field && last.value === v.value) return;
    this.push('value', v);
  }

  hookKeys() {
    document.addEventListener('keydown', this.timed((e) => {
      if (!this.on || e.repeat || ['Control', 'Shift', 'Alt', 'Meta'].includes(e.key) || e.target.closest?.(OFF)) return;
      const typing = e.target.matches?.('input:not([type=checkbox]):not([type=range]), textarea, [contenteditable]');
      const named = ['Escape', 'Enter', 'Delete', 'Tab'].includes(e.key) || /^F\d+$/.test(e.key);
      if (typing && (!named || e.key === 'Tab')) return; // (letters, Ctrl+A … in a field: its value when it is set)
      const key = [...MODS(e).filter((m) => m !== 'shift' || e.key.length > 1), e.key === ' ' ? 'Space' : e.key.length === 1 ? e.key.toLowerCase() : e.key].join('+');
      this.push('key', { key, ...(typing ? { in: nameOf(e.target) } : {}) });
    }), PASSIVE);
  }

  /** Every message of the app (toasts): its text, an error / a refusal with a screenshot. */
  hookToasts() {
    const stack = document.getElementById('toasts');
    if (!stack) return;
    new MutationObserver(this.timed((muts) => {
      if (!this.on) return;
      for (const m of muts) for (const n of m.addedNodes) {
        if (n.nodeType !== 1 || !n.classList.contains('toast')) continue;
        const kind = ['error', 'warning', 'ok', 'success'].find((k) => n.classList.contains(k)) || 'info';
        const text = n.textContent.replace(/\s+/g, ' ').trim();
        const ev = this.push('toast', { level: kind, text: text.slice(0, 400) });
        if (ev && (kind === 'error' || kind === 'warning')) this.shoot(ev);
      }
    })).observe(stack, { childList: true });
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
    const last = this.events[this.events.length - 1], box = e.target.closest('.fb-box, .lw-widget, .sg-menu, .view-suggest');
    if (box) { // (over a box floating on the view — the suggestions, a widget: its list scrolled, not the view zoomed)
      const name = (box.querySelector('.vs-head > b, .lw-head > b, .mpc-head') || box).textContent.replace(/\s+/g, ' ').trim().slice(0, 60);
      if (last?.kind === 'scroll' && last.in === name && Date.now() - (this.wheelAt || 0) < 1500) { last.by += e.deltaY > 0 ? 1 : -1; this.touch(last); }
      else this.push('scroll', { in: name, by: e.deltaY > 0 ? 1 : -1, ...placeOf(e.clientX, e.clientY) });
      this.wheelAt = Date.now();
      return;
    }
    if (!e.target.closest(ZOOMS)) return; // (a label, a button over the view: not a zoom of it)
    if (last?.kind === 'view' && Date.now() - (this.wheelAt || 0) < 1500) { last.zoom += e.deltaY < 0 ? 1 : -1; this.touch(last); } // (one event while it goes on)
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
   *  led to it marked in red. Taken when the browser is idle, the page walked in slices, encoded off the main thread. */
  shoot(ev) {
    const why = ev?.kind === 'toast' ? 'msg' : 'step'; // (an error is not kept from its picture by a step done just before)
    if (!ev || Date.now() - (this.lastShot[why] || 0) < SHOT_GAP_MS || this.shooting) return;
    this.lastShot[why] = Date.now();
    this.shooting = true;
    idle(() => this.snap(ev).catch(() => { /* no picture this time */ }).finally(() => { this.shooting = false; }));
  }

  async snap(ev) {
    const { screenshotUI } = await import('./agent_more.js');
    const { canvas: c, k } = await screenshotUI({ canvas: true, width: SHOT_W, slice: 8 });
    const f = k / Math.min(1, 1400 / innerWidth), g = c.getContext('2d'); // (the events' px: of a picture at most 1400 px wide)
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.strokeStyle = '#ff3b30';
    g.fillStyle = '#ff3b30';
    g.lineWidth = 2;
    const since = (Date.now() - SHOT_GAP_MS - this.t0) / 1000, recent = [];
    for (let j = this.events.length - 1; j >= 0 && this.events[j].t >= since; j--) if (['click', 'suggest', 'drag'].includes(this.events[j].kind)) recent.push(this.events[j]);
    for (const x of recent) {
      if (x.kind === 'drag') {
        g.beginPath();
        x.path_px.forEach(([px, py], j) => (j ? g.lineTo(px * f, py * f) : g.moveTo(px * f, py * f)));
        g.stroke();
        const [ex, ey] = x.path_px[x.path_px.length - 1];
        g.beginPath(); g.arc(ex * f, ey * f, 4, 0, 7); g.fill();
      } else if (x.px) { g.beginPath(); g.arc(x.px[0] * f, x.px[1] * f, 7, 0, 7); g.stroke(); }
    }
    const blob = await new Promise((ok) => c.toBlob(ok, 'image/png'));
    const data = await new Promise((ok, fail) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1]); r.onerror = fail; r.readAsDataURL(blob); });
    if (!this.events.includes(ev)) return; // (a new recording meanwhile)
    const id = `S${++this.nShot}`;
    this.shots.push({ id, i: ev.i, t: ev.t, data });
    if (this.shots.length > MAX_SHOTS) this.shots.shift();
    ev.shot = id;
    this.touch(ev);
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

  /** A stopped recording for a chat message (id: one of recordings(); none: the last one) — marked sent. */
  forChat(max = 60, id = null) {
    const old = id !== null && id !== this.t0 ? this.past.find((r) => r.id === id) : null;
    if (old) {
      old.sent = true;
      try { sessionStorage.setItem(PAST_KEY, JSON.stringify(this.past)); } catch { /* full */ }
      this.changed();
      return old.text;
    }
    const text = this.chatText(max);
    this.sent = this.n - 1;
    this.save(true);
    this.changed();
    return text;
  }

  /** The recording as the chat's text: what it is, then its last events as lines. */
  chatText(max = 60) {
    const list = this.read({ paths: false }), cut = list.slice(-max);
    return `[⏺ Recording of my moves: ${list.length} events over ${clock(this.seconds)}${cut.length < list.length ? ` — the last ${cut.length} below; get_recording for all` : ''}${this.shots.length ? `; screenshots ${this.shots.map((x) => x.id).join(', ')} (get_recording_screenshot)` : ''}]\n${cut.map((e) => this.line(e)).join('\n')}`;
  }

  /** The recording for the AI's problem report (the events, without the screenshots): one running or stopped in the
   *  last `recentMin` minutes, else null. */
  forReport(recentMin = 30) {
    if (!this.events.length || (!this.on && !(this.tEnd && Date.now() - this.tEnd < recentMin * 60000))) return null;
    return { running: this.on, started_by: this.by, ...(this.reason ? { reason: this.reason } : {}), started: new Date(this.t0).toISOString(),
      seconds: Math.round(this.seconds), count: this.events.length, dropped: this.events[0].i, screenshots: this.shots.length, events: this.read() };
  }

  /** A stopped recording not attached to a message yet: how many events it has (else 0). */
  attachable() { return !this.on && this.events.length > 2 && this.sent < this.n - 1 ? this.events.length : 0; }

  /** The stopped recordings the chat can attach, newest first (the last 3): [{id, t0, seconds, count, sent}]. */
  recordings() {
    const now = !this.on && this.events.length > 2 ? [{ id: this.t0, t0: this.t0, seconds: this.seconds, count: this.events.length, sent: this.sent >= this.n - 1 }] : [];
    return [...now, ...this.past];
  }

  // ------------------------------------------------------------------ 📋 copied as text (for a developer's chat)
  /** The app's version and commit as the problem reports write them ("0.9.0 (main @ 2900fde, 2026-10-27)"), asked once. */
  async appVersion() {
    if (this.version) return this.version;
    try {
      const v = await (await fetch('/api/version')).json(), page = pageBuild();
      this.version = `${v.text || v.version}${page && v.commit && page !== v.commit ? `; page loaded at ${page} — reload it` : ''}`;
    } catch { /* the server restarting: said unknown */ }
    return this.version;
  }

  /** One event as a compact line for a developer: a mark (‼ an error, ! a warning), time, kind, what, where, value. */
  devLine(e) {
    const { i, t: s, kind, where, shot, ...r } = e;
    const tm = `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`;
    const pt = (q) => (q ? `[${q.join(', ')}]` : '—');
    const place = (x) => [x.at ? `at ${pt(x.at)}` : '', x.px ? `px ${pt(x.px)}` : ''].filter(Boolean).join(' ');
    const q = (v) => `"${short(v, 160)}"`;
    const btn = `${r.button || ''}${r.keys ? `+${r.keys.join('+')}` : ''}`;
    let mark = ' ', body;
    if (kind === 'click' || kind === 'suggest') {
      body = [`${btn}${r.double ? ' double' : ''}`, kind === 'suggest' ? `row ${q(r.row)} in ${q(r.table)}${r.about ? ` about ${r.about}` : ''}` : '',
        r.control ? `on button ${q(r.control)}` : r.on ? `on ${r.on}` : '', place(r)].filter(Boolean).join(' ');
    } else if (kind === 'drag') { // (the path shortened: its start, three points on the way, its end)
      const path = r.path || [], px = r.path_px || [], n = Math.max(path.length, px.length);
      const pick = [...new Set([0, Math.round((n - 1) / 4), Math.round((n - 1) / 2), Math.round(3 * (n - 1) / 4), n - 1])].filter((j) => j >= 0 && j < n);
      const way = pick.map((j) => (path[j] ? pt(path[j]) : `px ${pt(px[j])}`)).join(' → ');
      body = `${btn} of the ${r.of || 'view'}: from ${r.from || '?'} to ${r.to || '?'}; path (${n} points) ${way}${px.length ? `; px ${pt(px[0])} → ${pt(px[px.length - 1])}` : ''}`;
    } else if (kind === 'toast') {
      mark = r.level === 'error' ? '‼' : r.level === 'warning' ? '!' : ' ';
      body = `${r.level === 'error' ? 'ERROR' : r.level === 'warning' ? 'WARNING' : r.level || 'info'}: ${q(r.text)}`;
    } else if (kind === 'value') body = `${q(r.field)} = ${q(r.value)}`;
    else if (kind === 'key') body = `${r.key}${r.in ? ` in ${q(r.in)}` : ''}`;
    else if (kind === 'press') body = `button ${q(r.control)}${r.via ? ` (${r.via})` : ''}`;
    else if (kind === 'view') body = `zoom ${r.zoom > 0 ? '+' : ''}${r.zoom} ${place(r)}`;
    else if (kind === 'scroll') body = `${q(r.in)} ${r.by > 0 ? 'down' : 'up'} ${Math.abs(r.by)} ${place(r)}`;
    else body = Object.entries(r).map(([k, v]) => `${k}: ${short(v, 160)}`).join(', ');
    return `${mark} ${tm.padStart(6)}  ${kind.padEnd(13)} ${body}${shot ? ` [screenshot ${shot} left out]` : ''}`;
  }

  /** The recording as self-contained text for a developer: its header, then a line per event (a "── in" line when the
   *  workspace / part / step changes); longer than COPY_MAX bytes: its first and last events, the middle summed up. */
  copyText() {
    const list = this.read(), m = this.meta || {}, last = this.events[this.events.length - 1] || {};
    const ws = [...new Set(this.events.map((e) => e.ws).filter(Boolean))], parts = [...new Set(this.events.map((e) => e.part).filter(Boolean))];
    const head = [
      '# Auto3DModeler — recording of the user\'s moves (⏺)',
      `App version: ${this.version || 'unknown'}`,
      `Recorded: ${stamp(this.t0)}, ${clock(this.seconds)} long, ${list.length} events${this.on ? ' (still running)' : ''}; started by ${this.by === 'ai' ? 'the AI' : 'the user'}${this.reason ? ` — ${this.reason}` : ''}`,
      `Workspace: ${last.ws || '—'}${ws.length > 1 ? ` (visited: ${ws.join(', ')})` : ''} · Project: ${m.project ? `"${m.project}"` : '—'} · Part: ${last.part || '—'}${parts.length > 1 ? ` (also: ${parts.filter((x) => x !== last.part).join(', ')})` : ''}`,
      `Window: ${m.w || innerWidth} × ${m.h || innerHeight} px (device pixel ratio ${m.dpr || 1}); "at [x, y]" = 0…1 across / down the view, "px [x, y]" = window pixels scaled to at most 1400 px wide`,
      ...(this.events[0]?.i ? [`Not kept: the oldest ${this.events[0].i} events (the recording keeps the newest ${MAX})`] : []),
      `Screenshots: ${this.shots.length ? `${this.shots.length} taken (${this.shots.map((x) => x.id).join(', ')}) — left out of this text` : 'none'}`,
      'Lines: mark (‼ error, ! warning) · time m:ss.s · event · what (button, under the cursor, place, value)',
      '',
    ].join('\n');
    const lines = [];
    let at = '';
    for (const e of list) {
      if (e.where !== undefined) { at = e.where; lines.push({ e, at, s: `── in ${at || '—'}` }); }
      lines.push({ e, at, s: this.devLine(e) });
    }
    const size = lines.reduce((a, l) => a + bytes(l.s) + 1, 0), room = COPY_MAX - bytes(head) - 4000; // (4000: the summary)
    let body = lines;
    if (size > room) { // the first and the last events, the middle summed up (its errors and warnings kept)
      let a = 0, b = 0, h = 0, k = lines.length;
      while (h < lines.length && a + bytes(lines[h].s) + 1 <= room * COPY_HEAD) a += bytes(lines[h++].s) + 1;
      while (k > h && b + bytes(lines[k - 1].s) + 1 <= room * (1 - COPY_HEAD)) b += bytes(lines[--k].s) + 1;
      const mid = lines.slice(h, k).filter((l) => !l.s.startsWith('──')).map((l) => l.e), count = {};
      for (const e of mid) count[e.kind] = (count[e.kind] || 0) + 1;
      const errs = mid.filter((e) => e.kind === 'toast' && (e.level === 'error' || e.level === 'warning')).slice(-20);
      body = [...lines.slice(0, h),
        { s: `… ${mid.length} events left out (${Object.entries(count).map(([x, n]) => `${n}× ${x}`).join(', ')})${errs.length ? ` — their last ${errs.length} errors / warnings:` : ''} …` },
        ...errs.map((e) => ({ s: this.devLine(e) })), ...(errs.length ? [{ s: '… (end of the left-out part) …' }] : []),
        ...(k < lines.length && !lines[k].s.startsWith('──') ? [{ s: `── in ${lines[k].at || '—'}` }] : []), // (where the kept end starts)
        ...lines.slice(k)];
    }
    return `${head}${body.map((l) => l.s).join('\n')}\n`;
  }

  /** 📋 Copy a recording (id: one of recordings(); none: this one) to the clipboard as copyText(); the clipboard
   *  blocked: the text in a panel to copy by hand. Called in the click (the user's gesture). -> true when copied. */
  async copy(id = null) {
    const old = id !== null && id !== this.t0 ? this.past.find((r) => r.id === id) : null;
    if (!old && !this.version) await Promise.race([this.appVersion(), new Promise((ok) => setTimeout(ok, 1500))]);
    const text = old ? old.copy || old.text : this.copyText(), count = old ? old.count : this.events.length;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('no clipboard');
      await navigator.clipboard.writeText(text);
    } catch {
      this.copyPanel(text);
      return false;
    }
    const kb = Math.max(1, Math.round(bytes(text) / 1024));
    this.ctx?.toast?.(t('Recording copied ({n} events, {kb} kB) — paste it with Ctrl+V').replace('{n}', count).replace('{kb}', kb), 'ok');
    return true;
  }

  /** The clipboard blocked: the text in a panel — Select all, then Ctrl+C. */
  copyPanel(text) {
    document.querySelector('.rec-copy')?.remove();
    const el = document.createElement('div');
    el.className = 'rec-copy';
    el.dataset.noI18n = '';
    el.innerHTML = `<div class="rec-copy-head"><b>📋 ${esc(t('Copy the recording'))}</b><button type="button" class="btn small rec-copy-x" title="${esc(t('Close'))}">✕</button></div>
      <p class="hint">${esc(t('The browser did not let the app write to the clipboard — select all, press Ctrl+C, then paste it (Ctrl+V) into the chat.'))}</p>
      <textarea readonly spellcheck="false"></textarea>
      <div class="rec-copy-acts"><span class="hint">${Math.max(1, Math.round(bytes(text) / 1024))} kB</span><button type="button" class="btn small primary rec-copy-all">${esc(t('Select all'))}</button></div>`;
    const ta = el.querySelector('textarea');
    ta.value = text;
    el.querySelector('.rec-copy-all').addEventListener('click', () => { ta.focus(); ta.select(); });
    el.querySelector('.rec-copy-x').addEventListener('click', () => el.remove());
    el.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); el.remove(); } });
    document.body.appendChild(el);
    ta.focus();
    ta.select();
    return el;
  }

  /** A recording in a few words: "11:24 · 0:22 · 22 events". */
  describe(r) {
    const at = new Date(r.t0).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    return `${at} · ${clock(r.seconds)} · ${t('{n} events').replace('{n}', r.count)}`;
  }
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
