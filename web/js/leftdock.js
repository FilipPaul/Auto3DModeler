// Widgets: the ☰ project tree, the workspace's own panel (the step tree, the assembly's parts …) and the suggestions
// table. Each is docked in the left column (stacked, a splitter between two to share the height, ▾ folds one to its
// header) or floats over the view (moved / resized like the other floating boxes — floatbox.js — with its own
// opacity: Ctrl+wheel on its header or the slider in its ⋯ menu). Everything by dragging the header: into the left
// column (a line shows where it goes) to dock it, onto the view to float it. The project tree also stays behind the
// ☰ button (as it was) until it is docked; 📌 docks it at once. The column's width is the left splitter's
// (splitters.js); a column with nothing docked goes away (the view takes its room).
// Remembered (localStorage a3d.leftDock): where the project tree and the suggestions are (the same in every workspace —
// they belong to the project / the selection) and the order; per workspace (quick / model / assembly / drawing /
// sheet): where its panel is, the heights, the folded ones, the opacities (the floating places: floatbox.js, per
// workspace). ↺ Default layout in a widget's ⋯ menu puts it all back.
import { t } from './i18n.js';
import { resetWidth } from './splitters.js';
import { floatBox, setDockHook } from './floatbox.js';

const KEY = 'a3d.leftDock';
const WS = ['quick', 'model', 'assembly', 'drawing', 'sheet'];
const PANEL = { quick: '.panel.left.quick-only', model: '#modelLeft', assembly: '#asmLeft', drawing: '#dwgLeft', sheet: '#shLeft' };
const VIEW = { quick: '#viewport', model: '#modelViewport', assembly: '#asmViewport', drawing: '#dwgViewport', sheet: '#shViewport' };
const WS_CLASS = { quick: 'quick-only', model: 'model-only', assembly: 'asm-only', drawing: 'dwg-only', sheet: 'sheet-only' };
const TITLES = { quick: 'Quick part', model: '3D model', assembly: 'Assembly', drawing: '2D drawing', sheet: 'Drawing sheet' };
const MIN_H = 60; // a docked widget's least height (px, its header included)
const CONTROLS = 'button, input, select, textarea, a, label, [contenteditable]';
const OP_TIP = 'Drag: move it — into the left panel to dock it · Ctrl+wheel: opacity · double-click: back to its place';

const fresh = () => ({ project: 'popup', suggest: 'float', order: ['project', 'panel', 'suggest'], ws: {} });
function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (!s || typeof s !== 'object') return fresh();
    const f = fresh();
    return {
      project: ['popup', 'dock', 'float'].includes(s.project) ? s.project : f.project,
      suggest: ['dock', 'float'].includes(s.suggest) ? s.suggest : f.suggest,
      order: Array.isArray(s.order) && f.order.every((w) => s.order.includes(w)) ? s.order.filter((w) => f.order.includes(w)) : f.order,
      ws: s.ws && typeof s.ws === 'object' ? s.ws : {},
    };
  } catch { return fresh(); }
}
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

class LeftDock {
  constructor() {
    this.st = load();
    this.shown = false; // a project with parts: the project widget has something to show
    this.lastWs = null;
  }

  /** The workspace on screen (body.ws-*; none of them: the quick part). */
  ws() {
    const b = document.body.classList;
    return WS.slice(1).find((w) => b.contains(`ws-${w}`)) || 'quick';
  }

  /** The workspace's own record (its panel's place, heights, folded widgets, opacities). */
  my(ws = this.ws()) {
    const r = this.st.ws[ws] || (this.st.ws[ws] = {});
    r.h ||= {}; r.fold ||= {}; r.op ||= {};
    return r;
  }

  /** Where a widget is now: 'dock', 'float' (the project tree also 'popup': behind ☰). */
  mode(w, ws = this.ws()) { return w === 'panel' ? (this.my(ws).panel || 'dock') : this.st[w]; }
  get project() { return this.st.project; }
  get suggestDocked() { return this.st.suggest === 'dock'; }
  folded(w) { return !!this.my().fold[w]; }

  save() { try { localStorage.setItem(KEY, JSON.stringify(this.st)); } catch { /* private window: not remembered */ } }

  /** layout: main.layout (the grid). The workspace panels go into the left column, each in a widget. */
  init(layout) {
    if (this.layout || !layout) return;
    this.layout = layout;
    const col = this.col = document.createElement('div');
    col.className = 'left-col';
    col.id = 'leftCol';
    layout.insertBefore(col, layout.querySelector(':scope > .panel.left') || layout.firstChild);
    this.widgets = { project: this.widget('project'), suggest: this.widget('suggest'), panel: {} };
    col.append(this.widgets.project, this.widgets.suggest);
    for (const ws of WS) {
      const p = layout.querySelector(PANEL[ws]);
      if (!p) continue;
      const w = this.widget('panel', ws);
      w.appendChild(p);
      col.appendChild(w);
      this.widgets.panel[ws] = w;
    }
    const empty = document.createElement('p');
    empty.className = 'hint lw-empty-sg';
    empty.textContent = t('Nothing selected — click a face, an edge, a part or a step: what can be done with it shows here.');
    this.widgets.suggest.appendChild(empty);
    this.mark = document.createElement('div');
    this.mark.className = 'lw-mark';
    this.mark.hidden = true;
    layout.appendChild(this.mark);
    setDockHook({ move: (w, e) => this.dragOver(w, e), drop: (w, e) => this.dropFloating(w, e) });
    // the workspace changes (body class), the size changes, the language switches
    new MutationObserver(() => { if (this.ws() !== this.lastWs) this.apply(); }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => this.sync());
      ro.observe(layout);
      ro.observe(this.widgets.suggest);
    }
    window.addEventListener('resize', () => this.sync());
    window.addEventListener('a3d:lang', () => this.titles());
    // Ctrl+wheel on a floating widget's header: its opacity
    window.addEventListener('wheel', (e) => {
      if (!e.ctrlKey) return;
      const head = e.target.closest?.('.lw-widget.floating > .lw-head, .view-suggest:not(.docked) > .vs-head');
      if (!head) return;
      e.preventDefault();
      e.stopPropagation();
      const w = head.classList.contains('vs-head') ? 'suggest' : head.parentElement.dataset.w;
      this.setOpacity(w, this.opacity(w) + (e.deltaY < 0 ? 0.05 : -0.05), head);
    }, { passive: false, capture: true });
    document.addEventListener('pointerdown', (e) => { if (this.pop && !e.target.closest('.lw-pop, .lw-menu')) this.closeMenu(); }, true);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.pop) { e.stopPropagation(); this.closeMenu(); } }, true);
    this.apply();
  }

  /** A widget: its header (⠿ title … ▾ ⋯) and what is in it. */
  widget(w, ws) {
    const el = document.createElement('div');
    el.className = `lw-widget${ws ? ` ${WS_CLASS[ws]}` : ''}`;
    el.dataset.w = w;
    if (ws) el.dataset.ws = ws;
    el.innerHTML = `<div class="lw-head"><span class="lw-grip" aria-hidden="true">⠿</span><b></b><span class="lw-op" hidden></span>
      <button class="mini lw-fold" title="${t('Fold or unfold it (its header stays)')}">▾</button><button class="mini lw-menu" title="${t('Layout: dock it, float it over the view, its opacity, ↺ Default layout')}">⋯</button></div>`;
    const head = el.firstElementChild;
    head.querySelector('.lw-fold').addEventListener('click', (e) => { e.stopPropagation(); this.fold(w); });
    head.querySelector('.lw-menu').addEventListener('click', (e) => { e.stopPropagation(); this.menu(w, e.currentTarget); });
    head.addEventListener('pointerdown', (e) => { if (!el.classList.contains('floating')) this.dragStart(w, e, head); });
    // floating over a view: its clicks are its own (not a pick in the view)
    for (const ev of ['pointerdown', 'pointerup', 'pointermove', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu']) {
      el.addEventListener(ev, (e) => { if (el.classList.contains('floating')) e.stopPropagation(); });
    }
    return el;
  }

  /** The texts that follow the language. */
  titles() {
    if (!this.widgets) return;
    const set = (el, s) => { const b = el.querySelector(':scope > .lw-head > b'); if (b.textContent !== s) b.textContent = s; };
    set(this.widgets.project, `☰ ${t('Project')}`);
    set(this.widgets.suggest, `💡 ${t('Suggested')}`);
    for (const [ws, el] of Object.entries(this.widgets.panel)) set(el, t(TITLES[ws]));
    for (const el of this.col.querySelectorAll('.lw-widget')) this.headTip(el);
  }

  headTip(el) {
    const head = el.querySelector(':scope > .lw-head');
    const tip = t(el.classList.contains('floating') ? OP_TIP : 'Drag the header: up or down in the left panel, or onto the view to float it there');
    if (head.title !== tip) head.title = tip;
  }

  /** Is the project widget there to show (a project with parts)? (parts.js) */
  setShown(on) { if (this.shown !== on) { this.shown = on; this.apply(); } }

  // ---------------------------------------------------------------------------------------------- changes

  /** Dock widget `w` in the left column as its `at`-th one (default: the project tree on top, others at the end). */
  dock(w, at) {
    const ws = this.ws(), docked = this.docked(ws).filter((x) => x !== w);
    at = clamp(at ?? (w === 'project' ? 0 : docked.length), 0, docked.length);
    docked.splice(at, 0, w);
    this.st.order = [...docked, ...this.st.order.filter((x) => !docked.includes(x))];
    if (w === 'panel') this.my(ws).panel = 'dock'; else this.st[w] = 'dock';
    delete this.my(ws).fold[w];
    this.save();
    this.apply();
  }

  /** Float widget `w` over the view on screen (at x, y in it: its top left; none: where it was last). */
  float(w, x, y) {
    const ws = this.ws();
    if (x !== undefined) {
      const kind = w === 'suggest' ? 'suggest' : `lw-${w}-${ws}`;
      let old = null;
      try { old = JSON.parse(localStorage.getItem(`a3d.box.${kind}`) || 'null'); } catch { old = null; }
      try { localStorage.setItem(`a3d.box.${kind}`, JSON.stringify({ ...(old?.w ? { w: old.w, h: old.h } : {}), ax: 'l', dx: Math.round(Math.max(0, x)), ay: 't', dy: Math.round(Math.max(0, y)) })); } catch { /* private window */ }
    }
    if (w === 'panel') this.my(ws).panel = 'float'; else this.st[w] = 'float';
    this.save();
    if (w === 'panel' || w === 'project') this.widgetEl(w).dataset.place = ''; // (placed anew)
    this.apply();
    if (w === 'suggest') for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement, true);
  }

  /** The project tree back behind the ☰ button (open there: parts.js onUnpin). */
  unpin() { this.st.project = 'popup'; this.save(); this.onUnpin?.(); this.apply(); this.onProject?.(); }

  fold(w, on = !this.folded(w)) {
    const f = this.my().fold;
    if (on) f[w] = true; else delete f[w];
    this.save();
    this.apply();
  }

  opacity(w) { return this.my().op[w] ?? 1; }
  setOpacity(w, v, head) {
    v = Math.round(clamp(v, 0.3, 1) * 100) / 100;
    if (v >= 1) delete this.my().op[w]; else this.my().op[w] = v;
    this.save();
    this.applyOpacity();
    const badge = head?.querySelector('.lw-op');
    if (badge) { badge.textContent = `${Math.round(v * 100)} %`; badge.hidden = false; clearTimeout(badge.timer); badge.timer = setTimeout(() => { badge.hidden = true; }, 1200); }
    else if (head) { head.dataset.op = `${Math.round(v * 100)} %`; clearTimeout(head.opTimer); head.opTimer = setTimeout(() => { delete head.dataset.op; }, 1200); }
    const r = this.pop?.querySelector('input[type=range]');
    if (r && this.pop.dataset.w === w) { r.value = Math.round(v * 100); this.pop.querySelector('.lw-opv').textContent = `${r.value} %`; }
  }

  applyOpacity() {
    const s = document.body.style, op = this.my().op;
    for (const w of ['project', 'panel', 'suggest']) {
      const v = op[w] !== undefined ? String(op[w]) : '';
      if (s.getPropertyValue(`--op-${w}`) !== v) { if (v) s.setProperty(`--op-${w}`, v); else s.removeProperty(`--op-${w}`); }
    }
  }

  /** ↺ Default layout: the project tree behind ☰, the panels docked, the suggestions in their corner, the usual sizes. */
  reset() {
    this.st = fresh();
    this.save();
    try {
      for (const k of Object.keys(localStorage)) if (k.startsWith('a3d.box.lw-') || k === 'a3d.box.suggest') localStorage.removeItem(k);
    } catch { /* private window */ }
    resetWidth('left');
    for (const el of this.col.querySelectorAll('.lw-widget')) el.dataset.place = '';
    this.widgets.project.dataset.place = '';
    this.apply();
    for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement, true);
    this.onProject?.();
  }

  // ---------------------------------------------------------------------------------------------- placing

  /** The widgets docked in workspace `ws`, in their order. */
  docked(ws = this.ws()) {
    return this.st.order.filter((w) => (w === 'project' ? this.st.project === 'dock' && this.shown : this.mode(w, ws) === 'dock'));
  }

  widgetEl(w, ws = this.ws()) { return w === 'panel' ? this.widgets.panel[ws] : this.widgets[w]; }

  /** The project tree's box (parts.js) where its mode puts it. */
  placeTree() {
    const tree = document.getElementById('projTree');
    if (!tree) return;
    if (this.st.project === 'popup') { if (tree.parentElement !== this.layout) this.layout.appendChild(tree); }
    else if (tree.parentElement !== this.widgets.project) this.widgets.project.appendChild(tree);
  }

  /** Float `el` over the view `vp` (moved there and made a floating box, when not yet). */
  floatIn(el, vp, w, ws) {
    const kind = `lw-${w}-${ws}`;
    if (el.parentElement === vp && el.dataset.place === kind) return;
    vp.appendChild(el);
    el.classList.add('floating');
    el.removeAttribute('style');
    if (el.fb) el.fb.def = '';
    el.dataset.place = kind;
    floatBox(el, vp, { kind, handle: '.lw-head', min: [180, 70], dock: w });
    this.headTip(el);
  }

  dockIn(el) {
    if (el.parentElement !== this.col) this.col.appendChild(el);
    if (el.classList.contains('floating')) {
      el.classList.remove('floating', 'fb-box', 'fb-sized', 'fb-front');
      el.removeAttribute('style');
      el.querySelector(':scope > .lw-head')?.classList.remove('fb-handle');
      el.querySelector(':scope > .fb-size')?.remove();
      el.dataset.place = '';
      this.headTip(el);
    }
  }

  apply() {
    if (!this.layout) return;
    const ws = this.ws(), me = this.my(ws), body = document.body;
    this.lastWs = ws;
    this.placeTree();
    // the project tree
    const pw = this.widgets.project, pm = this.st.project;
    if (pm === 'float' && this.shown) this.floatIn(pw, this.layout.querySelector(VIEW[ws]), 'project', ws);
    else this.dockIn(pw);
    pw.hidden = pm === 'popup' || !this.shown;
    // the workspace panels (each its own workspace's)
    for (const [w, el] of Object.entries(this.widgets.panel)) {
      if (this.mode('panel', w) === 'float') this.floatIn(el, this.layout.querySelector(VIEW[w]), 'panel', w);
      else this.dockIn(el);
    }
    this.widgets.suggest.hidden = this.st.suggest !== 'dock';
    // the column: its widgets in order, a splitter between two, the heights
    const docked = this.docked(ws);
    this.splits ||= [];
    this.splits.forEach((sp, i) => { sp.hidden = i >= docked.length - 1; }); // (kept: one may be in the hand now)
    const H = this.col.clientHeight;
    const open = docked.filter((w) => !me.fold[w]);
    const flex = open.includes('panel') ? 'panel' : open[open.length - 1];
    docked.forEach((w, i) => {
      const el = this.widgetEl(w, ws);
      el.style.order = String(i * 2);
      el.classList.toggle('folded', !!me.fold[w]);
      const caret = me.fold[w] ? '▸' : '▾', f = el.querySelector(':scope > .lw-head > .lw-fold');
      if (f.textContent !== caret) f.textContent = caret;
      el.style.minHeight = w === flex ? '110px' : ''; // (the stretching one keeps some room: the others give way)
      if (me.fold[w]) el.style.flex = '0 0 auto';
      else if (w === flex) el.style.flex = '1 1 0';
      else el.style.flex = `0 1 ${Math.round(clamp(me.h[w] ?? this.defHeight(w, H), MIN_H, Math.max(MIN_H, H - MIN_H)))}px`;
      if (i) { const sp = this.splitter(i - 1); sp.dataset.a = docked[i - 1]; sp.dataset.b = w; sp.style.order = String(i * 2 - 1); }
    });
    for (const w of ['project', 'suggest']) if (!docked.includes(w)) this.widgets[w].classList.remove('folded');
    const none = !docked.length;
    if (body.classList.contains('lw-empty') !== none) body.classList.toggle('lw-empty', none);
    if (body.classList.contains('lp-docked') !== docked.includes('project')) body.classList.toggle('lp-docked', docked.includes('project'));
    this.titles();
    this.applyOpacity();
    this.sync();
  }

  defHeight(w, H) { return w === 'project' ? Math.round((H || 600) * 0.38) : w === 'suggest' ? 200 : Math.round((H || 600) * 0.5); }

  /** The splitter between docked widgets a (above) and b: dragged, the one of them that is not the stretching one
   *  gets taller or shorter; a double-click: the usual heights. */
  splitter(i) {
    if (this.splits[i]) { this.splits[i].hidden = false; return this.splits[i]; }
    const sp = this.splits[i] = document.createElement('div');
    sp.className = 'lw-split';
    sp.title = t('Drag to share the height between them — double-click for the usual heights');
    sp.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      sp.setPointerCapture(e.pointerId);
      const { a, b } = sp.dataset, ws = this.ws(), me = this.my(ws), ea = this.widgetEl(a, ws), eb = this.widgetEl(b, ws);
      const fa = ea.style.flex.startsWith('1') || ea.classList.contains('folded');
      const w = fa ? b : a, el = fa ? eb : ea, h0 = el.getBoundingClientRect().height, y0 = e.clientY, sign = fa ? -1 : 1;
      document.body.classList.add('resizing-v');
      sp.classList.add('on');
      const move = (ev) => { me.h[w] = Math.round(Math.max(MIN_H, h0 + sign * (ev.clientY - y0))); delete me.fold[w]; this.apply(); };
      const up = () => {
        sp.removeEventListener('pointermove', move);
        document.body.classList.remove('resizing-v');
        sp.classList.remove('on');
        const n = this.widgetEl(w, ws);
        if (n && !n.classList.contains('folded')) me.h[w] = Math.round(n.getBoundingClientRect().height); // (as it fits)
        this.save();
      };
      sp.addEventListener('pointermove', move);
      sp.addEventListener('pointerup', up, { once: true });
      sp.addEventListener('pointercancel', up, { once: true });
    });
    sp.addEventListener('dblclick', () => { const me = this.my(); delete me.h[sp.dataset.a]; delete me.h[sp.dataset.b]; this.save(); this.apply(); });
    this.col.appendChild(sp);
    return sp;
  }

  /** The suggestions table of view `vp` (suggest.js): in the left column (over its place there) or floating. */
  placeSuggest(box, vp, again = false) {
    if (!box || !vp) return;
    box.sgOpts ||= {};
    if (this.st.suggest === 'dock') {
      if (!box.classList.contains('docked')) {
        box.classList.add('docked');
        box.classList.remove('fb-box', 'fb-sized', 'fb-front');
        box.removeAttribute('style');
        box.querySelector(':scope > .vs-head')?.classList.remove('fb-handle');
        box.querySelector(':scope > .fb-size')?.remove();
      }
      const ws = Object.keys(VIEW).find((k) => vp.matches(VIEW[k]));
      box.dataset.ws = ws || '';
      const head = box.querySelector(':scope > .vs-head');
      if (head) head.title = '';
      this.sync();
      return;
    }
    if (box.classList.contains('docked') || again) { box.classList.remove('docked'); box.removeAttribute('style'); if (box.fb) box.fb.def = ''; }
    floatBox(box, vp, { ...box.sgOpts, dock: 'suggest' });
    const head = box.querySelector(':scope > .vs-head');
    if (head) head.title = t(OP_TIP);
  }

  /** The docked suggestions over their place in the column (they stay in their view: position fixed). */
  sync() {
    if (!this.col) return;
    const ph = this.widgets.suggest, ws = this.ws();
    const on = this.st.suggest === 'dock' && !ph.hidden && !ph.classList.contains('folded') && ph.offsetParent && !document.body.classList.contains('none-open');
    const r = on ? ph.getBoundingClientRect() : null, hh = ph.querySelector(':scope > .lw-head').offsetHeight;
    let any = false;
    for (const box of document.querySelectorAll('.view-suggest.docked')) {
      const show = on && box.dataset.ws === ws && box.parentElement?.offsetParent;
      box.classList.toggle('lw-off', !show);
      if (!show) continue;
      any = true;
      Object.assign(box.style, { left: `${Math.round(r.left)}px`, top: `${Math.round(r.top + hh)}px`, width: `${Math.round(r.width)}px`, height: `${Math.max(0, Math.round(r.height - hh))}px` });
    }
    ph.classList.toggle('has-sg', any);
  }

  // ---------------------------------------------------------------------------------------------- dragging

  /** Where a widget would go if dropped at (x, y): {col: index in the column} or {vp: the view} or null. */
  target(x, y, w) {
    const lr = this.layout.getBoundingClientRect();
    if (y < lr.top || y > lr.bottom) return null;
    const cr = this.col.getBoundingClientRect(), right = document.body.classList.contains('lw-empty') ? lr.left + 40 : cr.right;
    if (x >= lr.left && x <= right) {
      const els = this.docked().filter((d) => d !== w).map((d) => this.widgetEl(d)).filter((el) => el && !el.hidden);
      let i = 0;
      for (const el of els) { const r = el.getBoundingClientRect(); if (y > r.top + r.height / 2) i++; }
      const at = i === 0 ? cr.top : els[i - 1].getBoundingClientRect().bottom;
      return { col: i, y: at - lr.top };
    }
    const vp = this.layout.querySelector(VIEW[this.ws()]);
    const vr = vp?.getBoundingClientRect();
    if (vr && x >= vr.left && x <= vr.right && y >= vr.top && y <= vr.bottom) return { vp, x: x - vr.left, y: y - vr.top };
    return null;
  }

  /** The drop line in the column while a widget is dragged over it. */
  showMark(tg) {
    const m = this.mark;
    m.hidden = !tg?.col && tg?.col !== 0;
    if (m.hidden) return;
    const empty = document.body.classList.contains('lw-empty');
    m.classList.toggle('zone', empty);
    if (!empty) m.style.top = `${Math.max(0, tg.y - 2)}px`;
  }

  /** A floating widget dragged (floatbox.js): over the column, the drop line. */
  dragOver(w, e) { document.body.classList.add('lw-dragging'); this.showMark(this.target(e.clientX, e.clientY, w)); }

  /** A floating widget let go: over the column it docks there (true), else it stays where it was put. */
  dropFloating(w, e) {
    document.body.classList.remove('lw-dragging');
    this.mark.hidden = true;
    const tg = e && this.target(e.clientX, e.clientY, w);
    if (!tg || tg.col === undefined) return false;
    this.dock(w, tg.col);
    if (w === 'suggest') for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement);
    return true;
  }

  /** A docked widget's (or the ☰ popup's) header pressed: a drag once the mouse moves; let go in the column: there,
   *  on the view: floating there; a click without a move: nothing (the buttons do their own). */
  dragStart(w, e, head) {
    if (e.button !== 0 || e.target.closest(CONTROLS)) return;
    const x0 = e.clientX, y0 = e.clientY;
    let ghost = null;
    const move = (m) => {
      if (!ghost) {
        if (Math.hypot(m.clientX - x0, m.clientY - y0) < 5) return;
        ghost = document.createElement('div');
        ghost.className = 'lw-ghost';
        ghost.textContent = head.querySelector('b')?.textContent || '';
        document.body.appendChild(ghost);
        document.body.classList.add('lw-dragging');
      }
      m.preventDefault();
      Object.assign(ghost.style, { left: `${m.clientX + 12}px`, top: `${m.clientY + 8}px` });
      const tg = this.target(m.clientX, m.clientY, w);
      ghost.classList.toggle('float', !!tg?.vp);
      ghost.classList.toggle('none', !tg);
      this.showMark(tg);
    };
    const up = (u) => {
      window.removeEventListener('pointermove', move, true);
      window.removeEventListener('pointerup', up, true);
      if (!ghost) return;
      ghost.remove();
      document.body.classList.remove('lw-dragging');
      this.mark.hidden = true;
      const tg = this.target(u.clientX, u.clientY, w);
      if (!tg) return;
      if (tg.col !== undefined) { this.dock(w, tg.col); if (w === 'project') this.onProject?.(); return; }
      const hr = head.getBoundingClientRect();
      this.float(w, tg.x - Math.min(40, hr.width / 2), tg.y - 10);
      if (w === 'project') this.onProject?.();
    };
    window.addEventListener('pointermove', move, true);
    window.addEventListener('pointerup', up, true);
  }

  // ---------------------------------------------------------------------------------------------- the ⋯ menu

  closeMenu() { this.pop?.remove(); this.pop = null; }

  menu(w, btn) {
    if (this.pop?.dataset.w === w) { this.closeMenu(); return; }
    this.closeMenu();
    const m = this.mode(w), pop = this.pop = document.createElement('div');
    pop.className = 'lw-pop';
    pop.dataset.w = w;
    const items = [];
    if (m !== 'dock') items.push(['dock', `📌 ${t('Dock in the left panel')}`, t('Into the left panel, always in sight (or drag its header there)')]);
    if (m !== 'float') items.push(['float', `⧉ ${t('Float over the view')}`, t('A box over the view — drag its header where you want it')]);
    if (w === 'project') items.push(['popup', `☰ ${t('Back behind the ☰ button')}`, t('The project tree opens from the ☰ button again')]);
    pop.innerHTML = `${items.map(([k, l, tip]) => `<button data-a="${k}" title="${tip}">${l}</button>`).join('')}
      ${m === 'float' ? `<label class="lw-opl" title="${t('How much of the view shows through it — also Ctrl+wheel on its header')}">${t('Opacity')} <input type="range" min="30" max="100" step="5" value="${Math.round(this.opacity(w) * 100)}"><span class="lw-opv">${Math.round(this.opacity(w) * 100)} %</span></label>` : ''}
      <div class="menu-sep"></div><button data-a="reset" title="${t('Every widget back to its usual place and size: the project tree behind ☰, the panels in the left panel, the suggestions in the view\'s corner')}">↺ ${t('Default layout')}</button>`;
    for (const b of pop.querySelectorAll('[data-a]')) {
      b.addEventListener('click', () => {
        this.closeMenu();
        const a = b.dataset.a;
        if (a === 'dock') { this.dock(w); if (w === 'suggest') for (const x of document.querySelectorAll('.view-suggest')) this.placeSuggest(x, x.parentElement); }
        if (a === 'float') this.float(w);
        if (a === 'popup') this.unpin();
        if (a === 'reset') this.reset();
        if (w === 'project') this.onProject?.();
      });
    }
    const r = pop.querySelector('input[type=range]');
    r?.addEventListener('input', () => this.setOpacity(w, r.value / 100, this.widgetEl(w)?.querySelector('.lw-head')));
    document.body.appendChild(pop);
    const br = btn.getBoundingClientRect(), pw = pop.offsetWidth;
    Object.assign(pop.style, { left: `${Math.round(clamp(br.right - pw, 4, innerWidth - pw - 4))}px`, top: `${Math.round(Math.min(br.bottom + 4, innerHeight - pop.offsetHeight - 4))}px` });
  }
}

export const leftDock = new LeftDock();
