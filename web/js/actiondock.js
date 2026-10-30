// Action buttons — OK / Cancel of a step, ✓ Finish sketch, Done — float in the bottom-right corner of the view, in
// every workspace; the toolbars keep the drawing tools. A panel or toolbar draws them as usual in a `.mp-actions`
// row; the row is moved here and a hidden placeholder keeps its place, so a panel drawn again brings its own row
// (and the old one goes).
//
// A right-click in the view confirms (as in SolidWorks): it presses the dock's primary button (OK, ✓ Finish sketch,
// Done) — or a panel's button marked `data-rclick-ok` — the very same click, so the same undo step. Only a click:
// a right press moved less than RC_MOVE px and let go within RC_MS; a right drag pans the view as before. Only on
// the view's picture (a canvas / svg), not on its labels, fields or buttons; the panels keep the browser's menu
// (copy / paste in a field). Nothing to confirm: nothing happens (the view's own menus stay).
// While the mouse is over the view a small hint by the cursor says it ("🖱 OK"), with what Esc does when the
// workspace tells (esc(): 'cancel' -> "Esc Cancel" in red, 'keep' -> "Esc Done", null -> not said).
// A workspace may take the right-click over (rclick()): { word, run } -> a right-click runs that and the hint says its
// word (a sketch: "🖱 End circle" — it ends the drawing tool, not the sketch); false -> it does nothing (no 🖱 in the
// hint); undefined -> the primary button, as above.

import { t } from './i18n.js';

const TIPS = { ok: 'Apply and close (Enter)', cancel: 'Close without changing anything (Esc)' };
const RC_TIP = 'Right mouse button = OK';
const RC_MOVE = 4, RC_MS = 400;
const NOT_VIEW = 'button, input, textarea, select, a, label, [contenteditable], .view-actions, .menu-list, .floating';
// a mouse, its right button filled
const MOUSE = `<svg class="rc-mouse" viewBox="0 0 10 14" width="9" height="13" aria-hidden="true"><rect x="0.6" y="0.6" width="8.8" height="12.8" rx="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/>
  <path d="M5 0.6 A4.4 4.4 0 0 1 9.4 5 V5.6 H5 Z" fill="var(--accent)"/><path d="M0.6 5.6 H9.4 M5 0.6 V5.6" stroke="currentColor" stroke-width="0.9" fill="none"/></svg>`;

const usable = (b) => b && !b.disabled && b.isConnected && !!b.offsetParent;

export function actionDock(viewport, sources, { esc, rclick } = {}) {
  const dock = document.createElement('div');
  dock.className = 'view-actions';
  dock.hidden = true;
  viewport.appendChild(dock);
  const tip = document.createElement('div'); // the hint by the cursor
  tip.className = 'rc-hint';
  tip.hidden = true;
  tip.dataset.noI18n = '';
  viewport.appendChild(tip);
  const held = new Map(); // placeholder -> its row
  const marked = () => sources.flatMap((s) => [...s.querySelectorAll('[data-rclick-ok]')]);
  const primaries = () => [...dock.querySelectorAll('.mp-actions .primary'), ...marked()];
  /** The button a right-click presses now, or null. */
  const confirmBtn = () => primaries().find(usable) || null;
  /** What a right-click does now: { word, run } or null (nothing). */
  const rcAction = () => {
    const own = rclick?.();
    if (own !== undefined) return own ? { word: t(own.word), run: own.run } : null;
    const b = confirmBtn();
    return b ? { word: b.textContent.replace(/^[^\p{L}\p{N}]+/u, '').trim() || 'OK', run: () => b.click() } : null;
  };
  let shown = ''; // the hint's html
  let at = null; // where the mouse is over the view (client x, y), null: not over it / dragging
  const showTip = () => {
    const b = at && rcAction(), e = at ? esc?.() : null;
    if (!b && !e) { tip.hidden = true; return; }
    const word = b ? b.word : '';
    const html = `${b ? `${MOUSE}<b>${word.replace(/[&<>]/g, '')}</b>` : ''}${b && e ? '<i>·</i>' : ''}${e ? `<span class="rc-esc ${e}"><kbd>Esc</kbd> ${t(e === 'cancel' ? 'Cancel' : 'Done')}</span>` : ''}`;
    if (shown !== html) { shown = html; tip.innerHTML = html; } // (the same: not again — the observer would call this again)
    const r = viewport.getBoundingClientRect();
    tip.style.left = `${at.x - r.left + 14}px`; // (below right: a snap label sits above right)
    tip.style.top = `${at.y - r.top + 16}px`;
    tip.hidden = false;
  };
  const sync = () => {
    for (const src of sources) {
      for (const row of src.querySelectorAll('.mp-actions')) {
        if (row.closest('.view-actions')) continue;
        const ph = document.createElement('i');
        ph.className = 'mp-actions-at';
        ph.hidden = true;
        row.replaceWith(ph);
        held.set(ph, row);
        for (const b of row.querySelectorAll('button:not([title])')) { // (every button says what it does)
          const tp = TIPS[b.dataset.a]; // (by its action: its text may be translated already)
          if (tp) b.title = tp;
        }
      }
    }
    for (const [ph, row] of held) if (!ph.isConnected) { held.delete(ph); row.remove(); }
    for (const row of held.values()) if (row.parentNode !== dock) dock.appendChild(row);
    dock.hidden = !held.size;
    // its tooltip says a right-click presses it (also when its tooltip changes later) — not where the workspace takes
    // the right-click over (a sketch: there it ends the drawing tool)
    if (rclick?.() === undefined) for (const b of primaries()) {
      const tp = b.title || '';
      if (!tp.includes(RC_TIP) && !tp.includes(t(RC_TIP))) b.title = tp ? `${tp}\n${RC_TIP}` : RC_TIP;
    }
    document.body.classList.toggle('view-acts', [...document.querySelectorAll('.view-actions')].some((d) => !d.hidden && d.offsetParent));
    showTip();
  };
  const mo = new MutationObserver(sync);
  for (const src of sources) mo.observe(src, { childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'disabled'] });
  sync();

  // right-click = OK
  const onView = (el) => el instanceof Element && viewport.contains(el) && !!el.closest('canvas, svg') && !el.closest(NOT_VIEW);
  let press = null;
  let confirmedAt = 0;
  viewport.addEventListener('pointerdown', (e) => {
    press = e.button === 2 && e.pointerType !== 'touch' && onView(e.target) ? { x: e.clientX, y: e.clientY, t: performance.now(), id: e.pointerId } : null;
  }, true);
  viewport.addEventListener('pointermove', (e) => {
    if (press && e.pointerId === press.id && Math.hypot(e.clientX - press.x, e.clientY - press.y) >= RC_MOVE) press = null; // moved: a drag, it pans
    at = !e.buttons && e.pointerType !== 'touch' && onView(e.target) ? { x: e.clientX, y: e.clientY } : null; // (hidden while dragging)
    showTip();
  }, true);
  viewport.addEventListener('pointerleave', () => { at = null; showTip(); });
  window.addEventListener('keyup', () => { if (at) showTip(); }); // (Esc / Enter may have ended the command)
  window.addEventListener('pointerup', (e) => {
    const p = press;
    if (e.button !== 2 || !p || e.pointerId !== p.id) return;
    press = null;
    if (Math.hypot(e.clientX - p.x, e.clientY - p.y) >= RC_MOVE || performance.now() - p.t > RC_MS || !rcAction()) return;
    const f = document.activeElement; // a value still being typed counts (as when OK is clicked: the field loses focus)
    if (f && f !== document.body && f.matches?.('input, textarea, select')) f.blur();
    const a = rcAction(); // (again: the field's change may have drawn the panel again)
    if (!a) return;
    confirmedAt = performance.now();
    a.run();
    showTip();
  }, true);
  viewport.addEventListener('contextmenu', (e) => { // no browser menu over the view while a command can be confirmed
    if (onView(e.target) && (rcAction() || performance.now() - confirmedAt < 1000)) e.preventDefault();
  }, true);
  return dock;
}
