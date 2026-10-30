// Widgets: the ☰ project tree, the workspace's own panel (the step tree, the assembly's parts …), the suggestions
// table, and on the right the workspace's properties (its right panel — a 3D model's part / step, an assembly's
// selected part …) with the sections of it that stand on their own (a 3D model's Export / 3D print, an assembly's parts
// list and export, a sheet's title block: SECTIONS — a workspace marks such a part of its panel data-dock="<name>" and
// it shows in that widget). Two columns, the same mechanics in both: each widget is docked in the left or the right
// column (stacked, a splitter between two to share the height, ▾ folds one to its
// header) or floats over the view (moved / resized like the other floating boxes — floatbox.js — with its own
// two opacities: the panel's — its background, border, header — and its content's: Ctrl+wheel / Ctrl+Shift+wheel on
// its header or the two sliders in its ⋯ menu; the mouse over it shows the content whole). Everything by dragging the header: into the left
// column (a line shows where it goes) to dock it, onto the view to float it. The project tree also stays behind the
// ☰ button (as it was) until it is docked; 📌 docks it at once. The column's width is the left splitter's
// (splitters.js); a column with nothing docked goes away (the view takes its room).
// Remembered (localStorage a3d.leftDock): where the project tree and the suggestions are (the same in every workspace —
// they belong to the project / the selection) and the order; per workspace (quick / model / assembly / drawing /
// sheet): where its panel is, the heights, the folded ones, the opacities (the floating places: floatbox.js, per
// workspace). ↺ Default layout in a widget's ⋯ menu puts it all back.
// A workspace may add widgets of its own (addWidget: the assembly's ⚙ Mechanism): there only while it has something
// to show (show()), docked or floating like the others, closed by its ✕.
// The app's own project actions (projectMenu: 📄 New project, ⧉ … in a new window) head the project tree's ⋯ menu;
// the first one is also the row of the suggestions widget with nothing selected.
import { t } from './i18n.js';
import { resetWidth } from './splitters.js';
import { floatBox, setDockHook, scrollFade } from './floatbox.js';

const KEY = 'a3d.leftDock'; // (both columns now: the old left-only layout is read as it was, the right panels added)
const WS = ['quick', 'model', 'assembly', 'drawing', 'sheet'];
const PANEL = { quick: '.panel.left.quick-only', model: '#modelLeft', assembly: '#asmLeft', drawing: '#dwgLeft', sheet: '#shLeft' };
const RPANEL = { quick: '.panel.right.quick-only', model: '#modelRight', assembly: '#asmRight', drawing: '#dwgRight', sheet: '#shRight' };
// the parts of a right panel that are widgets of their own: [name (data-dock), title, the id of its box]
const SECTIONS = { model: [['mexport', 'Export / 3D print', 'modelExport']], assembly: [['abom', 'Parts list and export', 'asmBom']], sheet: [['stitle', 'Title block', 'shTitle']] };
// the rows of a list-type widget (its ⋯ Rows: the first N, then ⋯ More (k) / ▴ Fewer) — a widget may name its own
// (addWidget's rows); the suggestions table counts its own (suggest.js: suggestLimit)
const ROWS = { project: '.pt-row', 'panel:model': '.mt-tree > .mt-row', 'panel:assembly': '.as-list > .mt-item', mech: '.mc-list > *',
  'versions-': '.vr-row', 'params-': '.px-row', 'measure-': '.ms-row', suggest: '.vs-list > [data-sg]' };
const SUGGEST_ROWS = 8; // (the suggestions' first N — as before: "Top 8")
const SIDES = ['dock', 'right']; // (docked: in the left column — 'dock', as before — or in the right one)
const inCol = (m) => m === 'dock' || m === 'right';
const VIEW = { quick: '#viewport', model: '#modelViewport', assembly: '#asmViewport', drawing: '#dwgViewport', sheet: '#shViewport' };
const WS_CLASS = { quick: 'quick-only', model: 'model-only', assembly: 'asm-only', drawing: 'dwg-only', sheet: 'sheet-only' };
const TITLES = { quick: 'Quick part', model: '3D model', assembly: 'Assembly', drawing: '2D drawing', sheet: 'Drawing sheet' };
const MIN_H = 60; // a docked widget's least height (px, its header included)
const CONTROLS = 'button, input, select, textarea, a, label, [contenteditable]';
const OP_TIP = 'Drag: move it — into the left or right panel to dock it · Ctrl+wheel: the panel\'s opacity, Ctrl+Shift+wheel: its content\'s · double-click: back to its place';
// the two opacities: the panel (its background, border, header — 0: only its content floats over the view) and its
// content (rows, buttons, text — at least 30 %: it stays usable)
const OPS = { pop: { min: 0, label: 'Panel', tip: 'The panel\'s background, border and header — 0 %: only its content floats over the view (also Ctrl+wheel on its header)' },
  cop: { min: 0.3, label: 'Content', tip: 'Its rows, buttons and texts — at least 30 %, they stay usable; the mouse over it shows them whole (also Ctrl+Shift+wheel on its header)' } };

const fresh = () => ({ v: 2, project: 'dock', suggest: 'float', order: ['project', 'panel', 'suggest', 'props'], ws: {} });
/** The layout as remembered. v1 (the left column only: no 'props', no 'right') reads as it was — its order kept, what
 *  it did not know added (the right panels: in the right column). */
function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (!s || typeof s !== 'object') return fresh();
    const f = fresh(), order = Array.isArray(s.order) ? s.order.filter((w) => typeof w === 'string') : []; // (a workspace's own widgets too)
    for (const w of f.order) if (!order.includes(w)) order.push(w);
    return {
      v: 2,
      project: ['popup', 'dock', 'right', 'float'].includes(s.project) ? s.project : f.project,
      suggest: ['dock', 'right', 'float'].includes(s.suggest) ? s.suggest : f.suggest,
      order,
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
    this.extra = {}; // a workspace's own widgets: w -> {ws, el, title, h, on}
    this.fits = {}; // how tall a widget's content is (fitContent)
  }

  /** The workspace on screen (body.ws-*; none of them: the quick part). */
  ws() {
    const b = document.body.classList;
    return WS.slice(1).find((w) => b.contains(`ws-${w}`)) || 'quick';
  }

  /** The workspace's own record (its panel's place, heights, folded widgets, opacities). */
  my(ws = this.ws()) {
    const r = this.st.ws[ws] || (this.st.ws[ws] = {});
    r.h ||= {}; r.fold ||= {}; r.pop ||= {}; r.cop ||= {}; r.auto ||= {}; r.rows ||= {};
    if (r.op) { Object.assign(r.cop, r.op); delete r.op; } // (one opacity before: now the content's)
    return r;
  }

  /** Where a widget is now: 'dock' (the left column), 'right' (the right one), 'float' (the project tree also 'popup':
   *  behind ☰). */
  mode(w, ws = this.ws()) {
    return w === 'panel' ? (this.my(ws).panel || 'dock') : w === 'props' ? (this.my(ws).props || 'right')
      : this.extra[w] ? (this.my(this.extra[w].ws).modes?.[w] || this.extra[w].side) : this.st[w];
  }
  setMode(w, m, ws = this.ws()) {
    if (w === 'panel') this.my(ws).panel = m;
    else if (w === 'props') this.my(ws).props = m;
    else if (this.extra[w]) (this.my(this.extra[w].ws).modes ||= {})[w] = m;
    else this.st[w] = m;
  }
  get project() { return this.st.project; }
  get suggestDocked() { return inCol(this.st.suggest); }
  folded(w) { return this.isFold(this.my(), w); }
  /** Folded in workspace record `me`: as the user left it, else as it starts (a widget added folded: 🕘 Versions). */
  isFold(me, w) { return w in me.fold ? !!me.fold[w] : !!this.extra[w]?.folded; }

  save() { try { localStorage.setItem(KEY, JSON.stringify(this.st)); } catch { /* private window: not remembered */ } }

  /** layout: main.layout (the grid). The workspace panels go into the left column, their right panels into the right
   *  one, each in a widget. */
  init(layout) {
    if (this.layout || !layout) return;
    const col = this.col = document.createElement('div');
    col.className = 'left-col lw-col';
    col.id = 'leftCol';
    layout.insertBefore(col, layout.querySelector(':scope > .panel.left') || layout.firstChild);
    const rcol = document.createElement('div');
    rcol.className = 'right-col lw-col';
    rcol.id = 'rightCol';
    layout.appendChild(rcol);
    this.cols = { dock: col, right: rcol };
    this.widgets = { project: this.widget('project'), suggest: this.widget('suggest'), panel: {}, props: {} };
    col.append(this.widgets.project, this.widgets.suggest);
    for (const ws of WS) {
      const p = layout.querySelector(PANEL[ws]);
      if (!p) continue;
      const w = this.widget('panel', ws);
      w.appendChild(p);
      col.appendChild(w);
      this.widgets.panel[ws] = w;
    }
    for (const ws of WS) {
      const p = layout.querySelector(RPANEL[ws]);
      if (!p) continue;
      const w = this.widget('props', ws);
      w.appendChild(p);
      rcol.appendChild(w);
      this.widgets.props[ws] = w;
      this.sections(ws, p);
    }
    this.layout = layout;
    for (const [w, x] of Object.entries(this.extra)) this.colOf(this.mode(w, x.ws)).appendChild(x.el);
    // nothing selected: what to do, and the project's own row (📄 New project — the app's projectMenu)
    const empty = document.createElement('div');
    empty.className = 'lw-empty-sg';
    empty.innerHTML = `<p class="hint"></p><div class="vs-list"><button class="lw-sg-new"><span class="vs-i">📄</span> <span></span></button></div>`;
    empty.querySelector('p').textContent = t('Nothing selected — click a face, an edge, a part or a step: what can be done with it shows here.');
    empty.querySelector('.lw-sg-new').addEventListener('click', () => this.projectMenu?.()[0]?.[3]());
    this.widgets.suggest.appendChild(empty);
    this.emptySg = empty;
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
      ro.observe(rcol);
    }
    window.addEventListener('resize', () => this.sync());
    window.addEventListener('a3d:lang', () => this.titles());
    // Ctrl+wheel on a floating widget's header: the panel's opacity; Ctrl+Shift+wheel: its content's
    window.addEventListener('wheel', (e) => {
      if (!e.ctrlKey) return;
      const head = e.target.closest?.('.lw-widget.floating > .lw-head, .view-suggest:not(.docked) > .vs-head');
      if (!head) return;
      e.preventDefault();
      e.stopPropagation();
      const w = head.classList.contains('vs-head') ? 'suggest' : head.parentElement.dataset.w;
      const k = e.shiftKey ? 'cop' : 'pop', dv = e.deltaY || e.deltaX; // (Shift+wheel: the browser may turn it sideways)
      this.setOpacity(w, k, this.opacity(w, k) + (dv < 0 ? 0.05 : -0.05), head);
    }, { passive: false, capture: true });
    document.addEventListener('pointerdown', (e) => { if (this.pop && !e.target.closest('.lw-pop, .lw-menu')) this.closeMenu(); }, true);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.pop) { e.stopPropagation(); this.closeMenu(); } }, true);
    this.apply();
  }

  /** The column a docked mode puts a widget in (not docked: the left one, hidden there). */
  colOf(m) { return m === 'right' ? this.cols.right : this.cols.dock; }

  /** The parts of workspace `ws`'s right panel `p` that are widgets of their own (SECTIONS): each time the panel is
   *  drawn, what it marked data-dock="<name>" moves into that widget (shown while it has it). The workspace's own
   *  lookups in its panel (its $(…): p.querySelector) still find them there. */
  sections(ws, p) {
    const list = SECTIONS[ws];
    if (!list) return;
    const bodies = list.map(([w, title, id]) => {
      const b = this.addWidget(w, ws, { title, side: 'right', h: 190 });
      b.id = id;
      b.classList.add('panel', 'lw-sec');
      return [w, b];
    });
    const own = Element.prototype.querySelector;
    p.querySelector = function (s) { return own.call(this, s) || bodies.reduce((f, [, b]) => f || own.call(b, s), null); };
    const mo = new MutationObserver((recs) => {
      const drawn = recs.some((r) => r.type === 'childList' && r.target.parentElement === p); // (its box drawn anew)
      const found = new Map([...p.querySelectorAll('[data-dock]')].map((el) => [el.dataset.dock, el]));
      for (const [w, b] of bodies) {
        const el = found.get(w);
        if (el) {
          const y = b.scrollTop;
          b.replaceChildren(el);
          b.scrollTop = y;
          this.show(w, true);
          if (b.offsetParent) this.fitContent(w, el.offsetHeight + 20 + 27); // (its first height: as tall as what is in it — its padding, its header)
        } else if (drawn) { b.replaceChildren(); this.show(w, false); }
      }
      mo.takeRecords(); // (its own moves: not a drawing of the panel)
    });
    mo.observe(p, { childList: true, subtree: true });
  }

  /** A widget: its header (⠿ title … ▾ ⋯) and what is in it. */
  widget(w, ws) {
    const el = document.createElement('div');
    el.className = `lw-widget${ws ? ` ${WS_CLASS[ws]}` : ''}`;
    el.dataset.w = w;
    if (ws) el.dataset.ws = ws;
    el.innerHTML = `<div class="lw-head"><span class="lw-grip" aria-hidden="true">⠿</span><b></b><span class="lw-op" hidden></span>
      <button class="mini lw-fold" title="${t('Fold or unfold it (its header stays)')}">▾</button><button class="mini lw-menu" title="${t('Layout: dock it, float it over the view, its opacities, ↺ Default layout')}">⋯</button></div>`;
    const head = el.firstElementChild;
    head.querySelector('.lw-fold').addEventListener('click', (e) => { e.stopPropagation(); this.fold(w); });
    head.querySelector('.lw-menu').addEventListener('click', (e) => { e.stopPropagation(); this.menu(w, e.currentTarget); });
    head.addEventListener('pointerdown', (e) => { if (!el.classList.contains('floating')) this.dragStart(w, e, head); });
    // floating over a view: its clicks are its own (not a pick in the view)
    for (const ev of ['pointerdown', 'pointerup', 'pointermove', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu']) {
      el.addEventListener(ev, (e) => { if (el.classList.contains('floating')) e.stopPropagation(); });
    }
    // its grip / edges dragged while floating: a size of the user's own — ↕ Automatic height off
    el.addEventListener('pointerdown', (e) => { if (el.classList.contains('floating') && e.target.closest('.fb-size, .fb-edge, [data-edge]')) this.autoOff(w); }, true);
    this.watch(el, w);
    return el;
  }

  /** Watch widget element `el` (name w): its content changed -> its rows cut again, ↕ Automatic height follows. */
  watch(el, w) {
    if (!window.MutationObserver) return;
    const mo = new MutationObserver((recs) => {
      const own = (n) => n.nodeType === 1 && n.classList.contains('lw-more');
      if (recs.every((r) => [...r.addedNodes, ...r.removedNodes].every(own))) return; // (its own ⋯ More row)
      this.later(w);
    });
    mo.observe(el, { childList: true, subtree: true, characterData: true });
  }

  /** Once the content settles (a frame later): widget w's rows cut, the ↕ Automatic heights fitted. */
  later(w) {
    (this.due ||= new Set()).add(w);
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      const ws = this.ws(), due = [...this.due];
      this.due.clear();
      for (const x of due) this.cutRows(x, ws);
      this.autoFit();
      for (const x of due) this.fades(x, ws);
    });
  }

  // ---------------------------------------------------------------------------------------------- rows and heights

  /** The rows selector of list-type widget w in workspace ws (none: a form — no ⋯ Rows). */
  rowSel(w, ws = this.ws()) {
    if (this.extra[w]?.rows) return this.extra[w].rows;
    if (w === 'panel' || w === 'props') return ROWS[`${w}:${ws}`] || null;
    return ROWS[w] || Object.entries(ROWS).find(([k]) => k.endsWith('-') && w.startsWith(k))?.[1] || null;
  }

  /** Widget w's ⋯ Rows: how many show (0: all). The suggestions: 8 at first (or the old "Top N" setting). */
  rowsLimit(w, ws = this.ws()) {
    const v = this.my(ws).rows[w];
    if (Number.isFinite(v)) return v;
    if (w !== 'suggest') return 0;
    let old = NaN;
    try { old = parseInt(localStorage.getItem('a3d.suggestTop'), 10); } catch { /* private window */ }
    return Number.isFinite(old) && old >= 1 ? old : SUGGEST_ROWS;
  }

  /** Widget w's ⋯ Rows set (n: a number ≥ 1, else all). */
  setRows(w, n, ws = this.ws()) {
    const v = Math.round(+n);
    this.my(ws).rows[w] = Number.isFinite(v) && v >= 1 ? Math.min(999, v) : 0;
    if (w === 'suggest') { try { if (v >= 1) localStorage.setItem('a3d.suggestTop', String(v)); else localStorage.removeItem('a3d.suggestTop'); } catch { /* private window */ } }
    this.save();
    if (w === 'suggest') window.dispatchEvent(new CustomEvent('a3d:suggest-rows'));
    this.later(w);
  }

  /** List widget w: only its first N rows shown, then a row ⋯ More (k) (▴ Fewer once opened). */
  cutRows(w, ws = this.ws()) {
    const sel = this.rowSel(w, ws), el = w === 'suggest' ? null : this.widgetEl(w, ws);
    if (!sel || !el) return;
    for (const b of el.querySelectorAll('.lw-more')) b.remove();
    for (const r of el.querySelectorAll('.lw-cut')) r.classList.remove('lw-cut');
    const n = this.rowsLimit(w, ws), rows = [...el.querySelectorAll(sel)].filter((r) => r.offsetParent || getComputedStyle(r).display !== 'none');
    if (!n || rows.length <= n) return;
    this.opened ||= {};
    const open = !!this.opened[`${w}:${ws}`];
    if (!open) for (const r of rows.slice(n)) r.classList.add('lw-cut');
    const b = document.createElement('button');
    b.className = 'lw-more';
    b.textContent = open ? `▴ ${t('Fewer')}` : `⋯ ${t('More')} (${rows.length - n})`;
    b.title = t(open ? 'Only the first rows (⋯ Rows in the widget\'s ⋯ menu)' : 'Show every row');
    b.addEventListener('click', (e) => { e.stopPropagation(); this.opened[`${w}:${ws}`] = !open; this.cutRows(w, ws); this.autoFit(); });
    b.addEventListener('pointerdown', (e) => e.stopPropagation());
    const last = open ? rows[rows.length - 1] : rows[n - 1];
    last.after(b);
  }

  /** How tall widget element el would be with all its content shown (its inner scrolling boxes opened too). */
  natural(el) {
    const st = el.style, keep = { flex: st.flex, minHeight: st.minHeight, height: st.height, maxHeight: st.maxHeight };
    Object.assign(st, { flex: '0 0 auto', minHeight: '0', height: 'auto', maxHeight: 'none' });
    let h = el.offsetHeight;
    for (const x of el.querySelectorAll('*')) { // (a box inside that scrolls: what it hides)
      if (x.scrollHeight > x.clientHeight + 1 && x.clientHeight > 0 && /auto|scroll/.test(getComputedStyle(x).overflowY)) h += x.scrollHeight - x.clientHeight;
    }
    Object.assign(st, keep);
    return Math.ceil(h);
  }

  /** The docked suggestions' height as their content asks (they are shown over their widget: suggest.js). */
  suggestNatural() {
    const box = [...document.querySelectorAll('.view-suggest.docked')].find((b) => !b.classList.contains('lw-off'));
    if (!box) return null;
    let h = 26 + 2;
    for (const c of box.children) h += c.classList.contains('vs-list') ? c.scrollHeight : c.offsetHeight;
    return Math.ceil(h);
  }

  /** ↕ Automatic height on? (widget w, the workspace on screen) */
  isAuto(w, me = this.my()) { return !!me.auto[w]; }
  setAuto(w, on) {
    const me = this.my();
    if (on) me.auto[w] = true; else delete me.auto[w];
    if (on) delete me.h[w];
    this.save();
    this.nat = {};
    this.apply();
  }
  /** A size of the user's own (a splitter, a floating box's grip): ↕ Automatic height off for w. */
  autoOff(w) {
    const me = this.my();
    if (!me.auto[w]) return;
    delete me.auto[w];
    this.save();
  }

  /** The ↕ Automatic heights of the workspace on screen fitted to their content: docked — the column laid out again
   *  when one changed; floating — as tall as its content, at most the view's height. */
  autoFit() {
    if (!this.layout) return;
    const ws = this.ws(), me = this.my(ws);
    this.nat ||= {};
    let again = false;
    for (const w of Object.keys(me.auto)) {
      if (!me.auto[w]) continue;
      const m = this.mode(w, ws);
      if (inCol(m)) {
        if (!this.docked(ws, m).includes(w) || this.isFold(me, w)) continue;
        const el = this.widgetEl(w, ws), h = w === 'suggest' ? this.suggestNatural() : this.natural(el);
        if (h && Math.abs((this.nat[w] || 0) - h) > 1) { this.nat[w] = h; again = true; }
      } else if (m === 'float') {
        const el = w === 'suggest' ? document.querySelector(`${VIEW[ws]} > .view-suggest`) : this.widgetEl(w, ws);
        if (!el?.offsetParent) continue;
        const vp = el.parentElement, top = el.offsetTop, max = Math.max(80, vp.clientHeight - top - 8);
        el.style.height = 'auto';
        el.style.maxHeight = 'none';
        const h = Math.min(max, this.natural(el));
        Object.assign(el.style, { height: `${h}px`, maxHeight: `${max}px` });
      }
    }
    if (again) this.apply();
  }

  /** The widget's scrolling boxes: no scrollbar, a fade at the edge that has more (as the suggestions table). */
  fades(w, ws = this.ws()) {
    const el = w === 'suggest' ? null : this.widgetEl(w, ws);
    for (const x of el ? el.querySelectorAll(':scope > :not(.lw-head):not(.fb-size), :scope > .panel .mt-tree, :scope > .panel .as-list') : []) scrollFade(x);
  }

  /** A widget of workspace `ws` only (w: its name, e.g. 'mech'), docked under the others at first; hidden until
   *  show(w, true). title: its header (English, translated); h: its first height docked (px); close(): its ✕ was
   *  clicked (it is hidden then); folded: folded to its header the first time (🕘 Versions: unobtrusive). -> the
   *  element to fill. */
  addWidget(w, ws, { title, h = 160, close, folded = false, side = 'dock' } = {}) {
    if (this.extra[w]) return this.extra[w].body;
    const el = this.widget(w, ws), body = document.createElement('div');
    el.hidden = true;
    body.className = 'lw-body';
    el.appendChild(body);
    if (close) {
      const x = document.createElement('button');
      x.className = 'mini lw-close';
      x.textContent = '✕';
      x.title = t('Close it (it comes back from the toolbar)');
      x.addEventListener('click', (e) => { e.stopPropagation(); close(); });
      el.querySelector(':scope > .lw-head').appendChild(x);
    }
    this.extra[w] = { ws, el, body, title, h, on: false, folded, side: side === 'right' ? 'right' : 'dock' }; // side: where it docks at first
    if (this.cols) this.colOf(this.mode(w, ws)).appendChild(el);
    this.apply();
    return body;
  }

  /** A workspace's own widget shown (it has something to show) or hidden. */
  show(w, on) { const x = this.extra[w]; if (x && x.on !== !!on) { x.on = !!on; this.apply(); } }

  /** The texts that follow the language. */
  titles() {
    if (!this.widgets) return;
    const set = (el, s) => { const b = el.querySelector(':scope > .lw-head > b'); if (b.textContent !== s) b.textContent = s; };
    set(this.widgets.project, `☰ ${t('Project')}`);
    set(this.widgets.suggest, `💡 ${t('Suggested')}`);
    for (const [ws, el] of Object.entries(this.widgets.panel)) set(el, t(TITLES[ws]));
    for (const el of Object.values(this.widgets.props)) set(el, t('Properties'));
    for (const x of Object.values(this.extra)) set(x.el, t(x.title));
    for (const el of this.layout.querySelectorAll('.lw-widget')) this.headTip(el);
    for (const c of Object.values(this.cols)) { const tip = c.classList.contains('col-empty') ? t('Empty — drag a widget\'s header here to dock it') : ''; if (c.title !== tip) c.title = tip; }
    const nb = this.emptySg?.querySelector('.lw-sg-new');
    if (nb) {
      nb.lastElementChild.textContent = t('New project');
      nb.title = t('Start a new, empty project in this window — the one on screen is kept (🕘 Recent projects opens it again) (Ctrl+Alt+N)');
    }
  }

  headTip(el) {
    const head = el.querySelector(':scope > .lw-head');
    const tip = t(el.classList.contains('floating') ? OP_TIP : 'Drag the header: up or down, into the other side panel, or onto the view to float it there');
    if (head.title !== tip) head.title = tip;
  }

  /** Is the project widget there to show (a project with parts)? (parts.js) */
  setShown(on) { if (this.shown !== on) { this.shown = on; this.apply(); } }

  // ---------------------------------------------------------------------------------------------- changes

  /** Dock widget `w` in the left column (side 'right': the right one) as its `at`-th one (default: the project tree on
   *  top, others at the end). */
  dock(w, at, side = 'dock') {
    if (!SIDES.includes(side)) side = 'dock';
    const ws = this.ws(), docked = this.docked(ws, side).filter((x) => x !== w);
    at = clamp(at ?? (w === 'project' ? 0 : docked.length), 0, docked.length);
    docked.splice(at, 0, w);
    this.st.order = [...docked, ...this.st.order.filter((x) => !docked.includes(x))];
    this.setMode(w, side, ws);
    const me = this.my(ws);
    delete me.fold[w];
    if (this.extra[w]?.folded) me.fold[w] = false; // (docked by hand: open)
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
    this.setMode(w, 'float', ws);
    this.save();
    if (w !== 'suggest') this.widgetEl(w, ws).dataset.place = ''; // (placed anew)
    this.apply();
    if (w === 'suggest') for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement, true);
  }

  /** The project tree back behind the ☰ button (open there: parts.js onUnpin). */
  unpin() { this.st.project = 'popup'; this.save(); this.onUnpin?.(); this.apply(); this.onProject?.(); }

  fold(w, on) {
    on ??= !this.folded(w);
    const me = this.my(), f = me.fold;
    if (on === !!this.extra[w]?.folded) delete f[w]; else f[w] = on; // (kept: only what differs from how it starts)
    if (w === 'suggest' && inCol(this.st.suggest)) { if (on) me.sgClosed = true; else delete me.sgClosed; } // (docked: closed = folded)
    this.save();
    this.apply();
  }

  /** The suggestions table of the workspace on screen: {closed (✕: a 💡 button in the view's corner instead — docked:
   *  folded), auto (opens on a selection by itself — as at first)}. */
  sgState(ws = this.ws()) { const me = this.my(ws); return { closed: !!me.sgClosed, auto: me.sgAuto !== false }; }
  setSg({ closed, auto }, ws = this.ws()) {
    const me = this.my(ws);
    if (auto !== undefined) { if (auto) delete me.sgAuto; else me.sgAuto = false; }
    if (closed !== undefined) {
      if (closed) me.sgClosed = true; else delete me.sgClosed;
      if (inCol(this.st.suggest)) { this.fold('suggest', !!closed); return; }
    }
    this.save();
  }

  /** A floating widget's opacity, k: 'pop' (the panel) or 'cop' (its content), 0…1. */
  opacity(w, k) { return this.my()[k][w] ?? 1; }
  setOpacity(w, k, v, head) {
    v = Math.round(clamp(v, OPS[k].min, 1) * 100) / 100;
    if (v >= 1) delete this.my()[k][w]; else this.my()[k][w] = v;
    this.save();
    this.applyOpacity();
    const say = `${t(OPS[k].label)} ${Math.round(v * 100)} %`, badge = head?.querySelector('.lw-op');
    if (badge) { badge.textContent = say; badge.hidden = false; clearTimeout(badge.timer); badge.timer = setTimeout(() => { badge.hidden = true; }, 1200); }
    else if (head) { head.dataset.op = say; clearTimeout(head.opTimer); head.opTimer = setTimeout(() => { delete head.dataset.op; }, 1200); }
    const r = this.pop?.dataset.w === w && this.pop.querySelector(`input[data-k=${k}]`);
    if (r) { r.value = Math.round(v * 100); r.nextElementSibling.textContent = `${r.value} %`; }
  }

  /** The opacities of the workspace on screen: CSS variables --pop-<widget> / --cop-<widget> (styles.css). */
  applyOpacity() {
    const s = document.body.style, me = this.my();
    for (const k of ['pop', 'cop']) {
      for (const w of ['project', 'panel', 'suggest', 'props']) {
        const v = me[k][w] !== undefined ? String(me[k][w]) : '';
        if (s.getPropertyValue(`--${k}-${w}`) !== v) { if (v) s.setProperty(`--${k}-${w}`, v); else s.removeProperty(`--${k}-${w}`); }
      }
    }
    for (const [w, x] of Object.entries(this.extra)) { // (a workspace's own widget: its two opacities on itself — styles.css reads --pop / --cop)
      const fl = x.el.classList.contains('floating');
      for (const k of ['pop', 'cop']) { if (fl && me[k][w] !== undefined) x.el.style.setProperty(`--${k}`, String(me[k][w])); else x.el.style.removeProperty(`--${k}`); }
    }
  }

  /** ↺ Default layout: the project tree behind ☰, the panels docked, the suggestions in their corner, the usual sizes. */
  reset() {
    this.st = fresh();
    this.save();
    try {
      for (const k of Object.keys(localStorage)) if (k.startsWith('a3d.box.lw-') || k === 'a3d.box.suggest' || k === 'a3d.suggestTop') localStorage.removeItem(k);
    } catch { /* private window */ }
    resetWidth('left');
    resetWidth('right');
    this.opened = {};
    this.nat = {};
    window.dispatchEvent(new CustomEvent('a3d:suggest-rows'));
    for (const el of this.layout.querySelectorAll('.lw-widget')) el.dataset.place = '';
    this.apply();
    for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement, true);
    this.onProject?.();
  }

  // ---------------------------------------------------------------------------------------------- placing

  /** The widgets docked in workspace `ws` in the left column (side 'right': the right one), in their order. */
  docked(ws = this.ws(), side = 'dock') {
    const order = [...this.st.order, ...Object.keys(this.extra).filter((w) => !this.st.order.includes(w))];
    return order.filter((w) => (w === 'project' ? this.st.project === side && this.shown
      : this.extra[w] ? this.extra[w].ws === ws && this.extra[w].on && this.mode(w, ws) === side
        : w === 'panel' || w === 'props' ? !!this.widgets?.[w][ws] && this.mode(w, ws) === side : this.mode(w, ws) === side));
  }

  widgetEl(w, ws = this.ws()) { return w === 'panel' || w === 'props' ? this.widgets[w][ws] : this.widgets[w] || this.extra[w]?.el; }

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

  dockIn(el, col = this.col) {
    if (el.parentElement !== col) col.appendChild(el);
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
    else this.dockIn(pw, this.colOf(pm));
    pw.hidden = pm === 'popup' || !this.shown;
    // the workspace panels, left and right (each its own workspace's)
    for (const k of ['panel', 'props']) {
      for (const [w, el] of Object.entries(this.widgets[k])) {
        const m = this.mode(k, w);
        if (m === 'float') this.floatIn(el, this.layout.querySelector(VIEW[w]), k, w);
        else this.dockIn(el, this.colOf(m));
      }
    }
    for (const [w, x] of Object.entries(this.extra)) { // (a workspace's own: there only in it, while it has something to show)
      const here = x.on && x.ws === ws, m = this.mode(w, x.ws);
      if (here && m === 'float') this.floatIn(x.el, this.layout.querySelector(VIEW[ws]), w, ws);
      else this.dockIn(x.el, this.colOf(m === 'float' ? x.side : m));
      x.el.hidden = !here;
      x.el.classList.toggle('folded', here && this.isFold(me, w));
    }
    this.widgets.suggest.hidden = !inCol(this.st.suggest);
    if (inCol(this.st.suggest)) this.dockIn(this.widgets.suggest, this.colOf(this.st.suggest));
    // each column: its widgets in order, a splitter between two, the heights; an empty one: a thin strip
    const counts = {};
    for (const side of SIDES) counts[side] = this.layoutCol(side, ws, me);
    for (const w of ['project', 'suggest']) if (!this.docked(ws, 'dock').includes(w) && !this.docked(ws, 'right').includes(w)) this.widgets[w].classList.remove('folded');
    for (const [side, cls] of [['dock', 'lw-empty'], ['right', 'rw-empty']]) {
      const none = !counts[side];
      if (body.classList.contains(cls) !== none) body.classList.toggle(cls, none);
      this.cols[side].classList.toggle('col-empty', none);
    }
    const lp = this.docked(ws, 'dock').includes('project') || this.docked(ws, 'right').includes('project');
    if (body.classList.contains('lp-docked') !== lp) body.classList.toggle('lp-docked', lp);
    this.titles();
    this.applyOpacity();
    this.sync();
    if (Object.values(me.auto).some(Boolean)) this.later('');
  }

  /** Column `side` of workspace `ws`: its docked widgets in order, a splitter between two, the heights. -> how many. */
  layoutCol(side, ws, me) {
    const col = this.cols[side], docked = this.docked(ws, side);
    this.splits ||= {};
    const splits = this.splits[side] ||= [];
    splits.forEach((sp, i) => { sp.hidden = i >= docked.length - 1; }); // (kept: one may be in the hand now)
    const H = col.clientHeight;
    const open = docked.filter((w) => !this.isFold(me, w)), free = open.filter((w) => !this.isAuto(w, me)); // (↕ Automatic height: as tall as its content)
    const flex = free.includes('panel') ? 'panel' : free.includes('props') ? 'props' : free[free.length - 1];
    this.nat ||= {};
    docked.forEach((w, i) => {
      const el = this.widgetEl(w, ws);
      el.style.order = String(i * 2);
      el.classList.toggle('folded', this.isFold(me, w));
      const caret = this.isFold(me, w) ? '▸' : '▾', f = el.querySelector(':scope > .lw-head > .lw-fold');
      if (f.textContent !== caret) f.textContent = caret;
      el.style.minHeight = w === flex ? '110px' : ''; // (the stretching one keeps some room: the others give way)
      if (this.isFold(me, w)) el.style.flex = '0 0 auto';
      else if (this.isAuto(w, me)) el.style.flex = `0 1 ${Math.round(Math.max(MIN_H, this.nat[w] ?? this.defHeight(w, H)))}px`;
      else if (w === flex) el.style.flex = '1 1 0';
      else el.style.flex = `0 1 ${Math.round(clamp(me.h[w] ?? this.defHeight(w, H), MIN_H, Math.max(MIN_H, H - MIN_H)))}px`;
      if (i) { const sp = this.splitter(i - 1, side); sp.dataset.a = docked[i - 1]; sp.dataset.b = w; sp.style.order = String(i * 2 - 1); }
    });
    return docked.length;
  }

  defHeight(w, H) {
    if (this.extra[w]) return this.fits[w] ? Math.min(this.fits[w], Math.round((H || 600) * 0.6)) : this.extra[w].h; // (a right panel's section: as tall as it is)
    if (w === 'project') return Math.min(clamp(Math.round((H || 600) * 0.34), 150, 230), this.fits.project ? Math.max(80, this.fits.project) : 1e9); // (no taller than its rows)
    return w === 'suggest' ? 200 : Math.round((H || 600) * 0.5);
  }

  /** A docked widget's content is `px` tall: its first height follows (a project of 2 parts: a short tree, the panel
   *  under it gets the room) until the user sets one with the splitter. */
  fitContent(w, px) {
    px = Math.round(px);
    if (!px || this.fits[w] === px) return;
    this.fits[w] = px;
    if (this.my().h[w] === undefined && (this.docked().includes(w) || this.docked(undefined, 'right').includes(w))) this.apply();
  }

  /** The splitter between docked widgets a (above) and b: dragged, the one of them that is not the stretching one
   *  gets taller or shorter; a double-click: the usual heights. */
  splitter(i, side = 'dock') {
    const splits = this.splits[side];
    if (splits[i]) { splits[i].hidden = false; return splits[i]; }
    const sp = splits[i] = document.createElement('div');
    sp.className = 'lw-split';
    sp.title = 'Drag to share the height between them — double-click for the usual heights'; // (English: the page's translation follows a language switch)
    sp.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      sp.setPointerCapture(e.pointerId);
      const { a, b } = sp.dataset, ws = this.ws(), me = this.my(ws), ea = this.widgetEl(a, ws), eb = this.widgetEl(b, ws);
      const fa = ea.style.flex.startsWith('1') || ea.classList.contains('folded');
      const w = fa ? b : a, el = fa ? eb : ea, h0 = el.getBoundingClientRect().height, y0 = e.clientY, sign = fa ? -1 : 1;
      document.body.classList.add('resizing-v');
      sp.classList.add('on');
      const move = (ev) => { if (me.auto[w]) delete me.auto[w]; me.h[w] = Math.round(Math.max(MIN_H, h0 + sign * (ev.clientY - y0))); if (this.isFold(me, w)) me.fold[w] = false; this.apply(); };
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
    this.cols[side].appendChild(sp);
    return sp;
  }

  /** The suggestions table of view `vp` (suggest.js): in the left column (over its place there) or floating. */
  placeSuggest(box, vp, again = false) {
    if (!box || !vp) return;
    if (this.layout) this.later("suggest"); // (its rows changed: ↕ Automatic height follows)
    box.sgOpts ||= {};
    if (inCol(this.st.suggest)) {
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
    const on = inCol(this.st.suggest) && !ph.hidden && !ph.classList.contains('folded') && ph.offsetParent && !document.body.classList.contains('none-open');
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

  /** Where a widget would go if dropped at (x, y): {side, col: index in that column} or {vp: the view} or null. An
   *  empty column takes it over a 40 px strip at its side of the view. */
  target(x, y, w) {
    const lr = this.layout.getBoundingClientRect();
    if (y < lr.top || y > lr.bottom) return null;
    for (const side of SIDES) {
      const col = this.cols[side], cr = col.getBoundingClientRect(), empty = col.classList.contains('col-empty');
      const [x0, x1] = side === 'dock' ? [lr.left, empty ? lr.left + 40 : cr.right] : [empty ? cr.right - 40 : cr.left, cr.right];
      if (x < x0 || x > x1) continue;
      const els = this.docked(this.ws(), side).filter((d) => d !== w).map((d) => this.widgetEl(d)).filter((el) => el && !el.hidden);
      let i = 0;
      for (const el of els) { const r = el.getBoundingClientRect(); if (y > r.top + r.height / 2) i++; }
      const at = i === 0 ? cr.top : els[i - 1].getBoundingClientRect().bottom;
      return { side, col: i, y: at - lr.top, empty, x: x0 - lr.left, w: x1 - x0 };
    }
    const vp = this.layout.querySelector(VIEW[this.ws()]);
    const vr = vp?.getBoundingClientRect();
    if (vr && x >= vr.left && x <= vr.right && y >= vr.top && y <= vr.bottom) return { vp, x: x - vr.left, y: y - vr.top };
    return null;
  }

  /** The drop line in a column while a widget is dragged over it (an empty column: its strip lit). */
  showMark(tg) {
    const m = this.mark;
    m.hidden = !tg?.col && tg?.col !== 0;
    if (m.hidden) return;
    m.classList.toggle('zone', tg.empty);
    Object.assign(m.style, { left: `${Math.round(tg.x)}px`, width: `${Math.round(tg.w)}px`, top: tg.empty ? '' : `${Math.max(0, tg.y - 2)}px` });
  }

  /** A floating widget dragged (floatbox.js): over the column, the drop line. */
  dragOver(w, e) { document.body.classList.add('lw-dragging'); this.showMark(this.target(e.clientX, e.clientY, w)); }

  /** A floating widget let go: over the column it docks there (true), else it stays where it was put. */
  dropFloating(w, e) {
    document.body.classList.remove('lw-dragging');
    this.mark.hidden = true;
    const tg = e && this.target(e.clientX, e.clientY, w);
    if (!tg || tg.col === undefined) return false;
    this.dock(w, tg.col, tg.side);
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
      if (tg.col !== undefined) {
        this.dock(w, tg.col, tg.side);
        if (w === 'suggest') for (const b of document.querySelectorAll('.view-suggest')) this.placeSuggest(b, b.parentElement);
        if (w === 'project') this.onProject?.();
        return;
      }
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
    if (m !== 'right') items.push(['right', `📌 ${t('Dock in the right panel')}`, t('Into the right panel, always in sight (or drag its header there)')]);
    if (m !== 'float') items.push(['float', `⧉ ${t('Float over the view')}`, t('A box over the view — drag its header where you want it')]);
    if (w === 'project') items.push(['popup', `☰ ${t('Back behind the ☰ button')}`, t('The project tree opens from the ☰ button again')]);
    if (w === 'suggest') items.push(['sgauto', `💡 ${t('Open by itself')}${this.sgState().auto ? ' ✓' : ''}`, t('On: the suggestions open when you select something and close when nothing is selected. Off: they stay closed until you click 💡 in the view\'s bottom-left corner')]);
    const own = w === 'project' ? this.projectMenu?.() || [] : []; // (the app's: 📄 New project …)
    pop.innerHTML = `${own.map(([i, l, tip], k) => `<button data-own="${k}" title="${tip}">${i} ${l}</button>`).join('')}${own.length ? '<div class="menu-sep"></div>' : ''}
      ${items.map(([k, l, tip]) => `<button data-a="${k}" title="${tip}">${l}</button>`).join('')}
      ${m === 'float' ? Object.entries(OPS).map(([k, o]) => { const v = Math.round(this.opacity(w, k) * 100); return `<label class="lw-opl" title="${t(o.tip)}"><span class="lw-opn">${t(o.label)}</span><input type="range" data-k="${k}" min="${o.min * 100}" max="100" step="5" value="${v}"><span class="lw-opv">${v} %</span></label>`; }).join('') : ''}
      <div class="menu-sep"></div><button data-a="auto" class="lw-auto${this.isAuto(w) ? ' on' : ''}" title="${t('Grow or shrink to show all of it, with no scrolling — as far as there is room; dragging its size by hand turns it off')}">↕ ${t('Automatic height')}<span class="lw-tick">${this.isAuto(w) ? ' ✓' : ''}</span></button>
      ${this.rowSel(w) ? `<label class="lw-rows" title="${t('Only this many rows, then ⋯ More — empty: all of them')}"><span class="lw-rown">${t('Rows')}</span><input type="number" min="1" max="999" step="1" placeholder="${t('all')}" value="${this.rowsLimit(w) || ''}"></label>` : ''}
      <div class="menu-sep"></div><button data-a="reset" title="${t('Every widget back to its usual place and size: the project tree and the workspace\'s panel on the left, its properties on the right, the suggestions in the view\'s corner')}">↺ ${t('Default layout')}</button>`;
    for (const b of pop.querySelectorAll('[data-a]')) {
      b.addEventListener('click', () => {
        this.closeMenu();
        const a = b.dataset.a;
        if (a === 'dock' || a === 'right') { this.dock(w, undefined, a); if (w === 'suggest') for (const x of document.querySelectorAll('.view-suggest')) this.placeSuggest(x, x.parentElement); }
        if (a === 'float') this.float(w);
        if (a === 'popup') this.unpin();
        if (a === 'reset') this.reset();
        if (a === 'auto') this.setAuto(w, !this.isAuto(w));
        if (a === 'sgauto') { const on = !this.sgState().auto; this.setSg(on ? { auto: true, closed: false } : { auto: false }); window.dispatchEvent(new CustomEvent('a3d:suggest-rows')); }
        if (w === 'project') this.onProject?.();
      });
    }
    for (const b of pop.querySelectorAll('[data-own]')) b.addEventListener('click', () => { this.closeMenu(); own[+b.dataset.own][3](); });
    const head = () => (w === 'suggest' && this.mode(w) === 'float' ? document.querySelector(`${VIEW[this.ws()]} > .view-suggest > .vs-head`) : this.widgetEl(w)?.querySelector('.lw-head'));
    for (const r of pop.querySelectorAll('input[type=range]')) r.addEventListener('input', () => this.setOpacity(w, r.dataset.k, r.value / 100, head()));
    const rows = pop.querySelector('.lw-rows input');
    rows?.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') { this.setRows(w, rows.value); this.closeMenu(); } });
    rows?.addEventListener('change', () => this.setRows(w, rows.value));
    document.body.appendChild(pop);
    const br = btn.getBoundingClientRect(), pw = pop.offsetWidth;
    Object.assign(pop.style, { left: `${Math.round(clamp(br.right - pw, 4, innerWidth - pw - 4))}px`, top: `${Math.round(Math.min(br.bottom + 4, innerHeight - pop.offsetHeight - 4))}px` });
  }
}

export const leftDock = new LeftDock();

// ---------------------------------------------------------------------------------------------- for the AI
const WHERE = { dock: 'left', right: 'right', float: 'float', popup: 'behind ☰' };
const ALIAS = { suggestions: 'suggest', suggested: 'suggest', properties: 'props', tree: 'project' };

/** set_layout: the widgets of the workspace on screen (what the user does by dragging headers and in a widget's ⋯
 *  menu) and the suggestions table's ✕ / Automatically. */
export function layoutHandlers(dock = leftDock) {
  const list = () => {
    const ws = dock.ws(), me = dock.my(ws);
    const names = ['project', 'panel', 'suggest', 'props', ...Object.keys(dock.extra).filter((w) => dock.extra[w].ws === ws && dock.extra[w].on)];
    return names.filter((w) => w !== 'panel' && w !== 'props' ? true : !!dock.widgets?.[w][ws]).map((w) => {
      const el = w === 'suggest' ? dock.widgets.suggest : dock.widgetEl(w, ws), m = dock.mode(w, ws);
      return { widget: w, title: el?.querySelector(':scope > .lw-head > b')?.textContent || w, where: WHERE[m] || m,
        ...(dock.isFold(me, w) ? { folded: true } : {}), ...(dock.isAuto(w, me) ? { auto_height: true } : {}), ...(dock.rowSel(w, ws) ? { rows: dock.rowsLimit(w, ws) || 'all' } : {}) };
    });
  };
  const answer = (done) => { const sg = dock.sgState(); return { text: JSON.stringify({ ...(done.length ? { done } : {}), workspace: dock.ws(), widgets: list(), suggestions: { closed: sg.closed, auto: sg.auto } }) }; };
  return {
    set_layout: async ({ widget, place, at, fold, auto_height, rows, suggestions, reset } = {}) => {
      if (!dock.layout) throw new Error('The app has no widgets yet — open a part first.');
      const done = [];
      if (reset) { dock.reset(); done.push('↺ default layout'); }
      let w = null;
      if (widget !== undefined && widget !== null && widget !== '') {
        const want = String(widget).trim().toLowerCase(), all = list();
        w = ALIAS[want] || all.find((x) => x.widget.toLowerCase() === want)?.widget || all.find((x) => x.title.toLowerCase().includes(want))?.widget;
        if (!w) throw new Error(`No widget “${widget}” in this workspace — it has: ${all.map((x) => `${x.widget} (${x.title})`).join(', ')}.`);
      }
      const needW = (k) => { if (!w) throw new Error(`${k}: say which widget (widget: its name or title — set_layout {} lists them).`); };
      if (place !== undefined) {
        needW('place');
        if (place === 'left' || place === 'right') { dock.dock(w, at === undefined ? undefined : Math.max(0, Math.round(+at) - 1), place === 'left' ? 'dock' : 'right'); if (w === 'suggest') for (const x of document.querySelectorAll('.view-suggest')) dock.placeSuggest(x, x.parentElement); }
        else if (place === 'float') dock.float(w);
        else if (place === 'hidden') { if (w !== 'project') throw new Error('Only the project tree hides behind ☰ — fold another one (fold: true), or close the suggestions (suggestions: {closed: true}).'); dock.unpin(); }
        else throw new Error('place: "left", "right", "float" or "hidden" (the project tree behind ☰).');
        done.push(`${w} ${place}`);
      }
      if (fold !== undefined) { needW('fold'); dock.fold(w, !!fold); done.push(`${w} ${fold ? 'folded' : 'unfolded'}`); }
      if (auto_height !== undefined) { needW('auto_height'); dock.setAuto(w, !!auto_height); done.push(`${w} automatic height ${auto_height ? 'on' : 'off'}`); }
      if (rows !== undefined) {
        needW('rows');
        if (!dock.rowSel(w)) throw new Error(`${w} is not a list — it has no Rows setting.`);
        dock.setRows(w, rows === null || rows === 'all' ? 0 : rows);
        done.push(`${w} rows ${dock.rowsLimit(w) || 'all'}`);
      }
      if (suggestions && typeof suggestions === 'object') { // ✕ closed (a 💡 button instead) / open; Automatically: opens on a selection by itself
        const { closed, auto } = suggestions;
        dock.setSg({ ...(closed !== undefined ? { closed: !!closed } : {}), ...(auto !== undefined ? { auto: !!auto } : {}), ...(auto && closed === undefined ? { closed: false } : {}) });
        window.dispatchEvent(new CustomEvent('a3d:suggest-rows'));
        done.push(`suggestions ${closed !== undefined ? (closed ? 'closed' : 'open') : ''}${auto !== undefined ? ` automatically ${auto ? 'on' : 'off'}` : ''}`.trim());
      }
      await new Promise((r) => setTimeout(r, 80)); // (the rows cut, the heights fitted: a frame later)
      return answer(done);
    },
  };
}
