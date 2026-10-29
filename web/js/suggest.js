// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected. Its header drags it
// elsewhere in the view (that place is remembered) or into the left panel, where it stays docked (📌 too) — leftdock.js.
import { t } from './i18n.js';
import { leftDock } from './leftdock.js';

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

/** One 3D snap filter switched (remembered) — also from a sketch on the part (its "On the part" group: one choice). */
export function setSnapKind(key, on) {
  try { localStorage.setItem(SNAP_KEY, JSON.stringify({ ...snapKinds(), [key]: !!on })); } catch { /* private window */ }
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

const TOP_KEY = 'a3d.suggestTop', ALL_KEY = 'a3d.suggestAll';
/** How many suggestions show before ⋯ Show all (the user's setting, 3…30; default 8). */
export function suggestLimit() {
  let v = NaN;
  try { v = parseInt(localStorage.getItem(TOP_KEY), 10); } catch { /* private window */ }
  return Number.isFinite(v) && v >= 3 && v <= 30 ? v : 8;
}
export function setSuggestLimit(n) {
  const v = Math.round(+n);
  try { if (Number.isFinite(v)) localStorage.setItem(TOP_KEY, String(Math.min(30, Math.max(3, v)))); } catch { /* private window */ }
}
/** ⋯ Show all opened: every table shows everything until ▴ Fewer (for this session). */
const showingAll = () => { try { return sessionStorage.getItem(ALL_KEY) === '1'; } catch { return false; } };
const setShowingAll = (on) => { try { if (on) sessionStorage.setItem(ALL_KEY, '1'); else sessionStorage.removeItem(ALL_KEY); } catch { /* private window */ } };

/** The rows to show: the same action twice (icon and label) once; more than the limit: only the most relevant ones
 *  (rank: lower first — none: its place in the list), kept in the list's order, under their sections. */
function pickRows(items, all) {
  const seen = new Set(), acts = [];
  items.forEach((it, i) => {
    if (it.section !== undefined) return;
    const key = `${it.icon || ''}|${it.label}`;
    if (seen.has(key)) return;
    seen.add(key);
    acts.push({ i, r: Number.isFinite(it.rank) ? it.rank : i });
  });
  const over = acts.length > suggestLimit();
  const keep = new Set((over && !all ? [...acts].sort((a, b) => a.r - b.r || a.i - b.i).slice(0, suggestLimit()) : acts).map((a) => a.i));
  let sec = null;
  const rows = [];
  items.forEach((it, i) => {
    if (it.section !== undefined) { sec = it; return; }
    if (!keep.has(i)) return;
    if (sec) { rows.push(sec); sec = null; } // (a heading only above rows that show)
    rows.push({ ...it, i });
  });
  return { rows, total: acts.length, over };
}

/** Show (or with no items: remove) the table in `viewport`: title (what is selected), items [{icon, label, title,
 *  run, danger, rank} or {section}], hint (a line under it), refs (what is selected, as the AI's tools name it: ✨ puts
 *  it in the chat). More rows than the user's limit (suggestLimit): the most relevant ones, then ⋯ Show all (n). */
export function showSuggest(viewport, title, items, hint = '', refs = '') {
  let box = viewport.querySelector(':scope > .view-suggest');
  if (!items?.length) { box?.remove(); return null; }
  if (!box) {
    box = document.createElement('div');
    box.className = 'view-suggest';
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick']) box.addEventListener(ev, (x) => x.stopPropagation());
    viewport.appendChild(box);
  }
  const again = () => showSuggest(viewport, title, items, hint, refs);
  const all = showingAll(), { rows, total, over } = pickRows(items, all), setting = box.dataset.setting === '1';
  box.dataset.noI18n = '';
  box.innerHTML = `<div class="vs-head"><button class="vs-pin" title="${esc(t('Dock it in the left panel — always in sight (or drag its header there)'))}">📌</button><b>${esc(title)}</b><button class="vs-set${setting ? ' on' : ''}" title="${esc(t('How many suggestions show before ⋯ Show all — click to change'))}">${esc(t('Suggested'))}</button>${refs && askAI ? `<button class="vs-ai" title="${esc(t('Ask the AI about it — what is selected goes into the chat'))}">✨</button>` : ''}</div>
    ${setting ? `<label class="vs-top" title="${esc(t('The most relevant suggestions first; the rest under ⋯ Show all'))}">${esc(t('Show first'))} <input type="number" min="3" max="30" step="1" value="${suggestLimit()}"> ${esc(t('suggestions'))}</label>` : ''}
    <div class="vs-list">${rows.map((it) => (it.section !== undefined ? `<div class="vs-sec">${esc(it.section)}</div>` // (a heading: what the rows under it act on)
      : `<button data-sg="${it.i}" class="${it.danger ? 'danger' : ''}" title="${esc(it.title || '')}"><span class="vs-i">${it.icon || '•'}</span> <span>${esc(it.label)}</span></button>`)).join('')}${!over ? ''
      : all ? `<button class="vs-more" data-sg-fewer title="${esc(t('Only the most relevant suggestions'))}"><span class="vs-i">▴</span> <span>${esc(t('Fewer'))}</span></button>`
        : `<button class="vs-more" data-sg-all title="${esc(t('Everything that can be done with what is selected'))}"><span class="vs-i">⋯</span> <span>${esc(t('Show all'))} (${total})</span></button>`}</div>
    ${hint ? `<p class="vs-hint">${esc(hint)}</p>` : ''}`;
  for (const b of box.querySelectorAll('[data-sg]')) b.addEventListener('click', () => items[+b.dataset.sg].run());
  box.querySelector('[data-sg-all]')?.addEventListener('click', () => { setShowingAll(true); again(); });
  box.querySelector('[data-sg-fewer]')?.addEventListener('click', () => { setShowingAll(false); again(); });
  box.querySelector('.vs-set').addEventListener('click', () => { // (the setting: a small number field under the head)
    box.dataset.setting = setting ? '' : '1';
    again();
    box.querySelector('.vs-top input')?.select();
  });
  const top = box.querySelector('.vs-top input');
  top?.addEventListener('change', () => { setSuggestLimit(top.value); again(); box.querySelector('.vs-top input')?.focus(); });
  top?.addEventListener('keydown', (e) => {
    e.stopPropagation(); // (not the app's keys: Delete, Esc …)
    if (e.key === 'Enter') { setSuggestLimit(top.value); box.dataset.setting = ''; again(); }
    if (e.key === 'Escape') { box.dataset.setting = ''; again(); }
  });
  box.querySelector('.vs-ai')?.addEventListener('click', (e) => { e.stopPropagation(); askAI(refs); });
  box.querySelector('.vs-ai')?.addEventListener('pointerdown', (e) => e.stopPropagation()); // (not a drag of the table)
  box.querySelector('.vs-pin')?.addEventListener('click', (e) => { e.stopPropagation(); leftDock.dock('suggest'); for (const b of document.querySelectorAll('.view-suggest')) leftDock.placeSuggest(b, b.parentElement); });
  box.sgOpts = { kind: 'suggest', handle: '.vs-head', min: [170, 90], onDefault: (b) => cornerPlace(b, viewport) };
  leftDock.placeSuggest(box, viewport); // (floating: moved / resized / remembered; or docked in the left column)
  return box;
}
