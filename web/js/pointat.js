// Point at a control: when a message (a toast, a hint) tells the user to use a control — "click ＋ Add position first",
// "⚙ Drive the mechanism" — that control gets a short pulsing ring (the AI's gui_highlight ring, agent_teach.js, without
// its dimming) and is brought into view: a folded widget unfolded, a floating one raised, a closed suggestions table
// opened, a closed <details> opened, its box scrolled to it. In moderation: one ring at a time, gone after ~2.6 s or
// on the next press anywhere, and the same message repeated right away does not point again (a click on the toast
// does: "show it again"). A target: an element, a CSS selector (the first one on screen), or {suggest: id} — the
// suggestions row an item marked `id` made (suggest.js data-sgid).
import { t } from './i18n.js';
import { leftDock } from './leftdock.js';
import { openSuggest } from './suggest.js';

const PAD = 4, MS = 2600, AGAIN_MS = 8000; // px around the control; how long the ring stays; the same message again: not before
let cur = null, lastKey = '', lastAt = 0;

/** The element a target means now (null: not on screen yet). */
function find(target) {
  if (!target) return null;
  if (target instanceof Element) return target.isConnected ? target : null;
  if (typeof target === 'function') return find(target());
  const sel = typeof target === 'string' ? target : target.suggest ? `.view-suggest [data-sgid="${CSS.escape(target.suggest)}"]` : '';
  if (!sel) return null;
  const all = [...document.querySelectorAll(sel)];
  return all.find((el) => el.getClientRects().length) || all.find((el) => el.closest('.lw-widget.folded, .view-suggest, details')) || null;
}

/** Bring el where the user sees it: its widget unfolded / to the front, the suggestions opened, scrolled to. */
export function reveal(el) {
  const w = el.closest('.lw-widget');
  if (w?.classList.contains('folded') && w.dataset.w) leftDock.fold(w.dataset.w, false);
  for (const box of [w, el.closest('.view-suggest')]) { // (floating: raised over the other boxes)
    if (!box?.classList.contains('floating') && !box?.classList.contains('fb-box')) continue;
    for (const b of box.parentElement?.querySelectorAll(':scope > .fb-front') || []) if (b !== box) b.classList.remove('fb-front');
    box.classList.add('fb-front');
  }
  const sg = el.closest('.view-suggest');
  if (sg && (sg.classList.contains('vs-closed') || (sg.classList.contains('docked') && leftDock.folded('suggest')))) openSuggest();
  for (let d = el.closest('details:not([open])'); d; d = d.parentElement?.closest('details:not([open])')) d.open = true;
  if (el.isConnected) el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

/** The ring gone (the next press, its time up, another one shown). */
export function clearPoint() {
  if (!cur) return;
  const c = cur;
  cur = null;
  cancelAnimationFrame(c.raf);
  clearTimeout(c.timer);
  removeEventListener('pointerdown', c.off, true);
  c.ring.classList.add('pt-out');
  setTimeout(() => c.ring.remove(), 250);
}

/** Point at `target` (see above) -> the element, or null (not on screen; or the same `key` pointed at a moment ago and
 *  not `again`). ms: how long the ring stays. */
export function pointAt(target, { key = '', again = false, ms = MS } = {}) {
  if (!again && key && key === lastKey && Date.now() - lastAt < AGAIN_MS) return null;
  let el = find(target);
  if (!el) return null;
  lastKey = key;
  lastAt = Date.now();
  clearPoint();
  reveal(el);
  const ring = document.createElement('div');
  ring.className = 'teach-ring pt-ring';
  document.body.appendChild(ring);
  const c = cur = { ring, raf: 0, timer: 0, off: null, target };
  const place = () => {
    if (!el.isConnected) el = find(target) || el; // (drawn anew — the panel, the suggestions: the same control again)
    const r = el.isConnected ? el.getBoundingClientRect() : null;
    ring.hidden = !r?.width;
    if (r?.width) Object.assign(ring.style, { left: `${r.left - PAD}px`, top: `${r.top - PAD}px`, width: `${r.width + 2 * PAD}px`, height: `${r.height + 2 * PAD}px` });
    c.raf = requestAnimationFrame(place);
  };
  place();
  c.off = () => clearPoint();
  setTimeout(() => { if (cur === c) addEventListener('pointerdown', c.off, true); }, 0); // (not the press that brought it)
  c.timer = setTimeout(() => { if (cur === c) clearPoint(); }, ms);
  return el;
}

/** What is pointed at now (for tests and the AI): the element, or null. */
export const pointed = () => (cur ? find(cur.target) : null);

/** A toast that names a control: it points at it now, and a click on its text points again (instead of closing it). */
export function pointToast(el, target) {
  el.classList.add('pt-toast');
  el.title = t('Click: show me where');
  pointAt(target, { key: el.textContent });
  el.addEventListener('click', (e) => { if (!e.target.closest('button, a')) pointAt(target, { again: true }); }); // (the toast's own click: it stays — app.js)
}

/** A button in a toast that does what it suggests (it closes the toast). */
export function toastAction(el, { label, title = '', run }) {
  const b = document.createElement('button');
  b.className = 'mini pt-act';
  b.textContent = label;
  if (title) b.title = title;
  b.addEventListener('click', () => { el.remove(); run(); });
  el.append(' ', b);
  return b;
}
