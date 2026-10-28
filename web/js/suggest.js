// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected. Its header drags it
// elsewhere in the view; that place is remembered.
import { t } from './i18n.js';
import { floatBox } from './floatbox.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
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

/** The 3D snap filters (what 📏 Measure catches, and a spot placed on a face): {corner, midpoint, centre, quadrant,
 *  guides} (guides: in line with those while a hole / text is placed — modeler/facesnap.js) (remembered). */
export function snapKinds() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(SNAP_KEY) || 'null'); } catch { saved = null; }
  return { corner: true, midpoint: true, centre: true, quadrant: false, guides: true, ...(saved || {}) }; // (quadrants: asked for — near a rim they would take a click meant for it)
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
  const k = snapKinds(), F = [['corner', '⌜', 'Corners'], ['midpoint', '⊹', 'Edge midpoints'], ['centre', '◎', 'Centres'], ['quadrant', '◔', 'Quadrants'], ['guides', '┆', 'Guides']];
  const hk = hoverKinds(), HV = [['edges', '⟋', 'Edges'], ['points', '•', 'Snap points']];
  bar.innerHTML = `<span class="skf-t">${esc(t('Snap'))}:</span>${F.map(([key, i, l]) => `<button class="${k[key] ? 'on' : ''}" data-snap="${key}" title="${esc(`${t(l)}: ${t(key === 'guides' ? 'Line up a hole or a text with corners, midpoints and centres while placing it — click to switch' : 'What 📏 Measure and a click catch — click to switch')}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}
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
  fitFilterRow(viewport.querySelector(':scope > .snap-filters'));
}

/** A filter row (.sk-filters) fitted to its view, names first: one line with every name; the groups not in use
 *  (.skf-g without .active) as icons; each group on a line of its own, named; icons only (the names stay in the
 *  tooltips) on one line, then on two. Its height goes to the view (--skf-h): the suggestions / size box sit above it. */
export function fitFilterRow(bar) {
  if (!bar) return;
  const over = () => bar.scrollWidth > bar.clientWidth + 1, groups = [...bar.querySelectorAll('.skf-g')];
  const vp = bar.parentElement, dock = vp?.querySelector(':scope > .view-actions'); // (up to Finish / OK in the corner)
  bar.style.maxWidth = dock?.offsetWidth ? `${Math.max(120, dock.getBoundingClientRect().left - vp.getBoundingClientRect().left - bar.offsetLeft - 10)}px` : '';
  bar.classList.remove('compact', 'wrap');
  for (const g of groups) g.classList.remove('compact');
  const steps = groups.length > 1 ? [
    () => { for (const g of groups) if (!g.classList.contains('active')) g.classList.add('compact'); },
    () => { for (const g of groups) g.classList.remove('compact'); bar.classList.add('wrap'); },
    () => { bar.classList.remove('wrap'); bar.classList.add('compact'); },
    () => bar.classList.add('wrap')] : [() => bar.classList.add('compact')];
  for (const step of steps) { if (!over()) break; step(); }
  vp?.style.setProperty('--skf-h', `${bar.offsetHeight}px`);
}

/** In its corner (bottom left): under the command bar, its rows scroll. */
function cornerPlace(box, viewport) {
  const vr = viewport.getBoundingClientRect(), bar = viewport.querySelector(':scope > .m-cmdbar'), top = bar ? bar.offsetTop + bar.offsetHeight + 8 : 8;
  box.style.maxHeight = vr.height ? `${Math.max(150, vr.height - top - (parseFloat(getComputedStyle(box).bottom) || 34))}px` : '';
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
  floatBox(box, viewport, { kind: 'suggest', handle: '.vs-head', min: [170, 90], onDefault: (b) => cornerPlace(b, viewport) }); // (moved / resized / remembered)
  return box;
}
