// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected. Its header drags it
// elsewhere in the view; that place is remembered.
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const KEY = 'a3d.suggestAt';
let askAI = null; // (the app: what is selected, into the AI chat)

/** How ✨ hands the selection to the AI chat: fn(refs text). */
export const setAskAI = (fn) => { askAI = fn; };

const SNAP_KEY = 'a3d.snap3d', HOVER_KEY = 'a3d.hover3d';
/** The hover filters: what lights up under the mouse with no tool on — {edges, points} (remembered). */
export function hoverKinds() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(HOVER_KEY) || 'null'); } catch { saved = null; }
  return { edges: true, points: true, ...(saved || {}) };
}

/** The 3D snap filters (what 📏 Measure catches): {corner, midpoint, centre} (remembered). */
export function snapKinds() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(SNAP_KEY) || 'null'); } catch { saved = null; }
  return { corner: true, midpoint: true, centre: true, quadrant: false, ...(saved || {}) }; // (quadrants: asked for — near a rim they would take a click meant for it)
}

/** The row of 3D snap filters in the bottom-left corner of a view (the Suggested table above it). */
export function showSnapFilters(viewport, on = true) {
  let bar = viewport.querySelector(':scope > .snap-filters');
  if (!on) { bar?.remove(); return; }
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'sk-filters snap-filters';
    for (const ev of ['pointerdown', 'pointerup', 'click']) bar.addEventListener(ev, (x) => x.stopPropagation());
    viewport.appendChild(bar);
  }
  const k = snapKinds(), F = [['corner', '⌜', 'Corners'], ['midpoint', '⊹', 'Edge midpoints'], ['centre', '◎', 'Centres'], ['quadrant', '◔', 'Quadrants']];
  const hk = hoverKinds(), HV = [['edges', '⟋', 'Edges'], ['points', '•', 'Snap points']];
  bar.innerHTML = `<span class="skf-t">${esc(t('Snap'))}:</span>${F.map(([key, i, l]) => `<button class="${k[key] ? 'on' : ''}" data-snap="${key}" title="${esc(`${t(l)}: ${t('What 📏 Measure and a click catch — click to switch')}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}
    <span class="sep"></span><span class="skf-t">${esc(t('Hover'))}:</span>${HV.map(([key, i, l]) => `<button class="${hk[key] ? 'on' : ''}" data-hover="${key}" title="${esc(`${t(l)}: ${t(key === 'edges' ? 'Light up the edge under the mouse (a line or a circle) — click to switch' : 'Show the snap points of the step / face under the mouse — click to switch')}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}`;
  const flip = (store, read, key) => {
    const now = { ...read(), [key]: !read()[key] };
    try { localStorage.setItem(store, JSON.stringify(now)); } catch { /* private window */ }
    showSnapFilters(viewport);
  };
  for (const b of bar.querySelectorAll('[data-snap]')) b.addEventListener('click', () => flip(SNAP_KEY, snapKinds, b.dataset.snap));
  for (const b of bar.querySelectorAll('[data-hover]')) b.addEventListener('click', () => flip(HOVER_KEY, hoverKinds, b.dataset.hover));
  fitSnapFilters(viewport);
  if (!viewport.snapFit && window.ResizeObserver) (viewport.snapFit = new ResizeObserver(() => fitSnapFilters(viewport))).observe(viewport);
}

/** The filter row as icons only when its names do not fit the view (no scrollbar under it). */
function fitSnapFilters(viewport) {
  const bar = viewport.querySelector(':scope > .snap-filters');
  if (!bar) return;
  bar.classList.remove('compact');
  if (bar.scrollWidth > bar.clientWidth + 1) bar.classList.add('compact');
}

const savedAt = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; } };

/** Where the user put it: [x, y] as parts of the view (0 … 1), kept inside it. */
function place(box, viewport) {
  const at = savedAt(), vr = viewport.getBoundingClientRect();
  if (!at) {
    box.style.left = box.style.top = box.style.bottom = '';
    const bar = viewport.querySelector(':scope > .m-cmdbar'), top = bar ? bar.offsetTop + bar.offsetHeight + 8 : 8; // (in its corner: under the command bar, its rows scroll)
    box.style.maxHeight = vr.height ? `${Math.max(150, vr.height - top - (parseFloat(getComputedStyle(box).bottom) || 34))}px` : '';
    return;
  }
  box.style.maxHeight = '';
  const w = box.offsetWidth || 236, h = box.offsetHeight || 120;
  Object.assign(box.style, { left: `${Math.max(4, Math.min(at[0] * vr.width, vr.width - w - 4))}px`, top: `${Math.max(4, Math.min(at[1] * vr.height, vr.height - h - 4))}px`, bottom: 'auto' });
}

function draggable(box, viewport) {
  const head = box.querySelector('.vs-head');
  head.title = t('Drag to move the table — it stays there');
  head.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const vr = viewport.getBoundingClientRect(), br = box.getBoundingClientRect(), dx = e.clientX - br.left, dy = e.clientY - br.top;
    const move = (m) => {
      Object.assign(box.style, { left: `${Math.max(4, Math.min(m.clientX - vr.left - dx, vr.width - br.width - 4))}px`,
        top: `${Math.max(4, Math.min(m.clientY - vr.top - dy, vr.height - br.height - 4))}px`, bottom: 'auto' });
    };
    const up = () => {
      window.removeEventListener('pointermove', move, true);
      window.removeEventListener('pointerup', up, true);
      const r = box.getBoundingClientRect();
      try { localStorage.setItem(KEY, JSON.stringify([(r.left - vr.left) / vr.width, (r.top - vr.top) / vr.height])); } catch { /* private window */ }
    };
    window.addEventListener('pointermove', move, true); // (before the table, which keeps the mouse to itself)
    window.addEventListener('pointerup', up, true);
  });
  head.addEventListener('dblclick', () => { try { localStorage.removeItem(KEY); } catch { /* */ } place(box, viewport); }); // (back to its corner)
}

/** Show (or with no items: remove) the table in `viewport`: title (what is selected), items [{icon, label, title,
 *  run, danger}], hint (a line under it), refs (what is selected, as the AI's tools name it: ✨ puts it in the chat). */
export function showSuggest(viewport, title, items, hint = '', refs = '') {
  let box = viewport.querySelector(':scope > .view-suggest');
  if (!items?.length) { box?.remove(); return null; }
  if (!box) {
    box = document.createElement('div');
    box.className = 'view-suggest';
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick']) box.addEventListener(ev, (x) => x.stopPropagation());
    viewport.appendChild(box);
  }
  box.dataset.noI18n = '';
  box.innerHTML = `<div class="vs-head"><b>${esc(title)}</b><span>${esc(t('Suggested'))}</span>${refs && askAI ? `<button class="vs-ai" title="${esc(t('Ask the AI about it — what is selected goes into the chat'))}">✨</button>` : ''}</div>
    <div class="vs-list">${items.map((it, i) => (it.section !== undefined ? `<div class="vs-sec">${esc(it.section)}</div>` // (a heading: what the rows under it act on)
      : `<button data-sg="${i}" class="${it.danger ? 'danger' : ''}" title="${esc(it.title || '')}"><span class="vs-i">${it.icon || '•'}</span> <span>${esc(it.label)}</span></button>`)).join('')}</div>
    ${hint ? `<p class="vs-hint">${esc(hint)}</p>` : ''}`;
  for (const b of box.querySelectorAll('[data-sg]')) b.addEventListener('click', () => items[+b.dataset.sg].run());
  box.querySelector('.vs-ai')?.addEventListener('click', (e) => { e.stopPropagation(); askAI(refs); });
  box.querySelector('.vs-ai')?.addEventListener('pointerdown', (e) => e.stopPropagation()); // (not a drag of the table)
  draggable(box, viewport);
  place(box, viewport);
  return box;
}
