// Floating boxes over a view (the suggestions table, 🖨 Print check, 📏 Measure, ✂ Section, the size editor, the
// sketch's quick boxes): dragged by their header (or a slim ⠿ strip), resized by any edge or corner (the grip bottom right),
// the place and size remembered per kind (localStorage a3d.box.<kind>), a double-click on the header puts the box back,
// always inside the view (pulled back in when the view gets smaller), the one in hand on top.
import { t } from './i18n.js';

const PAD = 4;
const CONTROLS = 'button, input, select, textarea, a, label, [contenteditable]';
const watched = new WeakSet(); // (the views whose size is watched)
const EDGES = ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se']; // (the resize zones: edges, then corners on top of them)
const CURSOR = { n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize', nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize' };

/** A scroll container without a visible scrollbar: a soft fade at the edge where more is hidden (classes fade-top /
 *  fade-bottom, styles.css .fb-fade) — kept up to date on scroll and when it or its content changes size. */
export function scrollFade(el) {
  if (!el) return;
  el.classList.add('fb-fade');
  const upd = () => {
    const more = el.scrollHeight - el.clientHeight;
    el.classList.toggle('fade-top', more > 1 && el.scrollTop > 1);
    el.classList.toggle('fade-bottom', more > 1 && el.scrollTop < more - 1);
  };
  if (!el.fbFade) {
    el.fbFade = upd;
    el.addEventListener('scroll', () => el.fbFade(), { passive: true });
    if (window.ResizeObserver) new ResizeObserver(() => el.fbFade()).observe(el);
  }
  upd();
  requestAnimationFrame(upd); // (after the layout settles)
}

const keyOf = (kind) => `a3d.box.${kind}`;
let dockHook = null; // (leftdock.js: a box with `dock` dragged over the left column docks there)
/** hook: {move(name, event), drop(name, event) -> true when it took the box}. */
export const setDockHook = (h) => { dockHook = h; };
const load = (kind) => { try { return JSON.parse(localStorage.getItem(keyOf(kind)) || 'null'); } catch { return null; } };
const store = (kind, v) => { try { if (v) localStorage.setItem(keyOf(kind), JSON.stringify(v)); else localStorage.removeItem(keyOf(kind)); } catch { /* private window */ } };

/** The top a box may go up to: under the view's command bar (the toolbar stays clear). */
function topMin(vp) {
  const bar = vp.querySelector(':scope > .m-cmdbar, :scope > .dw-bar');
  return bar?.offsetHeight ? bar.offsetTop + bar.offsetHeight + PAD : PAD;
}

/** Make `box` (absolutely placed in `viewport`, already in it) a floating box; call it again after its content is
 *  re-rendered. Options: kind (the memory key), handle (a selector of its header; none: a ⠿ strip is added on top),
 *  remember ('all', or 'size' for a box that opens by the mouse — it keeps its size but opens where it was asked for),
 *  min [w, h], onDefault(box) (the box at its default place: what the caller does there), dock (a widget's name: dragged
 *  over the left column it docks there — leftdock.js). */
export function floatBox(box, viewport, opts = {}) {
  const o = { remember: 'all', min: [120, 40], ...opts };
  if (!box.fb) {
    box.fb = { def: box.getAttribute('style') || '' }; // (its default place: the caller's own inline style, or the CSS)
    box.addEventListener('pointerdown', (e) => { if (box.classList.contains('fb-box')) down(box, box.fb.vp, e); }, true); // (a widget docked in the left column: not a floating box now)
    box.addEventListener('dblclick', (e) => {
      if (!box.classList.contains('fb-box') || !e.target.closest('.fb-handle') || e.target.closest(CONTROLS)) return;
      e.stopPropagation();
      store(box.fb.o.kind, null);
      apply(box, box.fb.vp);
    });
    box.addEventListener('scroll', () => { for (const g of box.querySelectorAll(':scope > .fb-edge')) g.style.transform = `translate(${box.scrollLeft}px, ${box.scrollTop}px)`; }); // (the edges stay on the edges)
  }
  if (!watched.has(viewport) && window.ResizeObserver) {
    watched.add(viewport);
    new ResizeObserver(() => { for (const b of viewport.querySelectorAll(':scope > .fb-box')) if (b.fb) (b.fb.o.remember === 'all' ? apply : fit)(b, viewport); }).observe(viewport); // (a remembered box back at its side of the view)
  }
  box.fb.vp = viewport; // (a widget may float over another workspace's view later)
  box.fb.o = o;
  box.classList.add('fb-box');
  let head = o.handle ? box.querySelector(o.handle) : null;
  if (!head) {
    head = box.querySelector(':scope > .fb-strip');
    if (!head) { head = document.createElement('div'); head.className = 'fb-strip'; box.prepend(head); }
  }
  for (const h of box.querySelectorAll('.fb-handle')) if (h !== head) h.classList.remove('fb-handle');
  head.classList.add('fb-handle');
  head.title = t('Drag to move — double-click to put it back');
  for (const dir of EDGES) { // (invisible zones along every edge and corner; the bottom-right one a visible grip)
    let z = box.querySelector(`:scope > .fb-edge[data-dir=${dir}]`);
    if (!z) { z = document.createElement('div'); z.className = dir === 'se' ? 'fb-edge fb-size' : 'fb-edge'; z.dataset.dir = dir; box.appendChild(z); }
    z.title = t('Drag to resize — double-click the header to put it back');
  }
  apply(box, viewport);
  return box;
}

/** The box where it was left (or at its default place), then kept inside the view. */
function apply(box, vp) {
  const { o, def } = box.fb, s = load(o.kind);
  box.setAttribute('style', def);
  box.classList.remove('fb-sized');
  if (!s || (o.remember === 'size' && !s.w)) { o.onDefault?.(box); fit(box, vp); return; }
  if (s.w) size(box, s.w, s.h);
  if (o.remember !== 'size' && s.ax) {
    const vw = vp.clientWidth, vh = vp.clientHeight, w = box.offsetWidth, h = box.offsetHeight;
    pin(box, s.ax === 'l' ? s.dx : vw - w - s.dx, s.ay === 't' ? s.dy : vh - h - s.dy);
  }
  fit(box, vp);
}

const size = (box, w, h) => {
  box.classList.add('fb-sized');
  Object.assign(box.style, { width: `${Math.round(w)}px`, height: `${Math.round(h)}px`, maxWidth: 'none', maxHeight: 'none', minWidth: '0', boxSizing: 'border-box' });
};
const pin = (box, x, y) => Object.assign(box.style, { left: `${Math.round(x)}px`, top: `${Math.round(y)}px`, right: 'auto', bottom: 'auto', transform: 'none' });

/** Pulled back inside the view (a sized box also made smaller when the view is). */
function fit(box, vp) {
  if (!box.isConnected || !box.offsetWidth) return;
  const vw = vp.clientWidth, vh = vp.clientHeight, top = topMin(vp);
  if (box.classList.contains('fb-sized')) {
    const w = Math.min(box.offsetWidth, vw - 2 * PAD), h = Math.min(box.offsetHeight, vh - top - PAD);
    if (w !== box.offsetWidth || h !== box.offsetHeight) size(box, Math.max(w, box.fb.o.min[0]), Math.max(h, box.fb.o.min[1]));
  }
  const r = rel(box, vp), x = Math.max(PAD, Math.min(r.x, vw - r.w - PAD)), y = Math.max(top, Math.min(r.y, vh - r.h - PAD));
  if (Math.abs(x - r.x) > 0.5 || Math.abs(y - r.y) > 0.5) pin(box, x, y);
}

/** The box's place in the view (px from its top left) and size. */
function rel(box, vp) {
  const b = box.getBoundingClientRect(), v = vp.getBoundingClientRect();
  return { x: b.left - v.left - vp.clientLeft, y: b.top - v.top - vp.clientTop, w: b.width, h: b.height };
}

/** Remember where the box is: from the nearer side of the view, so a box in a corner stays in it. */
function save(box, vp) {
  const r = rel(box, vp), vw = vp.clientWidth, vh = vp.clientHeight, right = vw - r.x - r.w, bottom = vh - r.y - r.h;
  const s = { ax: r.x <= right ? 'l' : 'r', dx: Math.round(Math.max(0, Math.min(r.x, right))), ay: r.y <= bottom ? 't' : 'b', dy: Math.round(Math.max(0, Math.min(r.y, bottom))) };
  if (box.classList.contains('fb-sized')) Object.assign(s, { w: Math.round(r.w), h: Math.round(r.h) });
  store(box.fb.o.kind, box.fb.o.remember === 'size' ? (s.w ? { w: s.w, h: s.h } : null) : s);
}

/** A press in the box: it comes to the front; on its header a move, on an edge / corner a resize from that side (the
 *  opposite side stays put) — window listeners in the capture phase (the box keeps its own events from the view). */
function down(box, vp, e) {
  for (const b of vp.querySelectorAll(':scope > .fb-front')) if (b !== box) b.classList.remove('fb-front');
  box.classList.add('fb-front');
  if (e.button !== 0) return;
  const edge = e.target.closest('.fb-edge'), dir = edge?.parentElement === box ? edge.dataset.dir || 'se' : '', head = !dir && e.target.closest('.fb-handle');
  if (!dir && (!head || e.target.closest(CONTROLS))) return;
  e.preventDefault();
  e.stopPropagation();
  const r0 = rel(box, vp), vw = vp.clientWidth, vh = vp.clientHeight, top = topMin(vp), [mw, mh] = box.fb.o.min;
  pin(box, r0.x, r0.y);
  if (dir) size(box, r0.w, r0.h);
  document.body.classList.add(dir ? 'fb-resizing' : 'fb-moving');
  if (dir) document.body.style.setProperty('--fb-cur', CURSOR[dir]);
  const R = r0.x + r0.w, B = r0.y + r0.h; // (the right / bottom side: stays when the left / top one is dragged)
  const move = (m) => {
    const dx = m.clientX - e.clientX, dy = m.clientY - e.clientY;
    if (!dir) {
      if (box.fb.o.dock) dockHook?.move(box.fb.o.dock, m);
      pin(box, Math.max(PAD, Math.min(r0.x + dx, vw - r0.w - PAD)), Math.max(top, Math.min(r0.y + dy, vh - r0.h - PAD)));
      return;
    }
    let { x, y, w, h } = r0;
    if (dir.includes('e')) w = Math.max(mw, Math.min(r0.w + dx, vw - r0.x - PAD));
    if (dir.includes('s')) h = Math.max(mh, Math.min(r0.h + dy, vh - r0.y - PAD));
    if (dir.includes('w')) { x = Math.max(Math.min(PAD, R - mw), Math.min(r0.x + dx, R - mw)); w = R - x; }
    if (dir.includes('n')) { y = Math.max(Math.min(top, B - mh), Math.min(r0.y + dy, B - mh)); h = B - y; }
    size(box, w, h);
    if (x !== r0.x || y !== r0.y || dir.includes('w') || dir.includes('n')) pin(box, x, y);
  };
  const up = (u) => {
    window.removeEventListener('pointermove', move, true);
    window.removeEventListener('pointerup', up, true);
    document.body.classList.remove('fb-resizing', 'fb-moving');
    document.body.style.removeProperty('--fb-cur');
    if (!dir && box.fb.o.dock && dockHook?.drop(box.fb.o.dock, u)) return; // (docked in the left column)
    save(box, vp);
  };
  window.addEventListener('pointermove', move, true);
  window.addEventListener('pointerup', up, true);
}
