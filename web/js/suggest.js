// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected. Its header drags it
// elsewhere in the view (that place is remembered) or into the left panel, where it stays docked (📌 too) — leftdock.js.
// The keyboard: ↓ / ↑ into it and between its rows, Enter runs one, Esc leaves it. suggestMenu: the same rows as a
// small menu at a place (a tab's right-click).
import { t } from './i18n.js';
import { leftDock } from './leftdock.js';
import { scrollFade } from './floatbox.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let askAI = null; // (the app: what is selected, into the AI chat)

/** How ✨ hands the selection to the AI chat: fn(refs text). */
export const setAskAI = (fn) => { askAI = fn; };

const SNAP_KEY = 'a3d.snap3d', HOVER_KEY = 'a3d.hover3d', SHOW_KEY = 'a3d.show3d';
/** What the view shows besides the parts: {joints} — an assembly's joint symbols (remembered). */
export function showKinds() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(SHOW_KEY) || 'null'); } catch { saved = null; }
  return { joints: true, ...(saved || {}) };
}
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
/** opts.show: the "Show:" group's keys for this view (an assembly: ['joints']); opts.onShow: called after a switch. */
export function showSnapFilters(viewport, on = true, opts = viewport.snapOpts || {}) {
  viewport.snapOpts = opts;
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
  const sk = { ...showKinds(), ...(opts.isOn ? Object.fromEntries((opts.show || []).map((key) => [key, opts.isOn(key)])) : {}) };
  const SH = [['joints', '🔗', 'Joints', "the joints' symbols in the view — click to hide or show them"],
    ['dims', '📏', 'Dimensions', "the part's sizes on the view — click to hide or show them (as Sizes: All / None)"]];
  bar.innerHTML = `<span class="skf-t">${esc(t('Snap'))}:</span>${F.map(([key, i, l]) => `<button class="${k[key] ? 'on' : ''}" data-snap="${key}" title="${esc(`${t(l)}: ${t(key === 'guides' ? 'Line up a hole or a text with corners, midpoints and centres while placing it — click to switch' : 'What 📏 Measure and a click catch — click to switch')}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}
    <span class="sep"></span><span class="skf-t">${esc(t('Hover'))}:</span>${HV.map(([key, i, l]) => `<button class="${hk[key] ? 'on' : ''}" data-hover="${key}" title="${esc(`${t(l)}: ${t(key === 'edges' ? 'Light up the edge under the mouse (a line or a circle) — click to switch' : 'Show the snap points of the step / face under the mouse — click to switch')}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}${
    opts.show?.length ? `<span class="sep"></span><span class="skf-t">${esc(t('Show'))}:</span>${SH.filter(([key]) => opts.show.includes(key)).map(([key, i, l, w]) => `<button class="${sk[key] ? 'on' : ''}" data-show="${key}" title="${esc(`${t(l)}: ${t(w)}`)}">${i} <span class="skf-l">${esc(t(l))}</span></button>`).join('')}` : ''}`;
  const flip = (store, read, key) => {
    const now = { ...read(), [key]: !read()[key] };
    try { localStorage.setItem(store, JSON.stringify(now)); } catch { /* private window */ }
    showSnapFilters(viewport);
  };
  for (const b of bar.querySelectorAll('[data-snap]')) b.addEventListener('click', () => flip(SNAP_KEY, snapKinds, b.dataset.snap));
  for (const b of bar.querySelectorAll('[data-hover]')) b.addEventListener('click', () => flip(HOVER_KEY, hoverKinds, b.dataset.hover));
  for (const b of bar.querySelectorAll('[data-show]')) b.addEventListener('click', () => {
    if (opts.toggle) { opts.toggle(b.dataset.show); showSnapFilters(viewport); } else flip(SHOW_KEY, showKinds, b.dataset.show); // (a view keeping the state itself)
    opts.onShow?.();
  });
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

const ALL_KEY = 'a3d.suggestAll';
/** How many suggestions show before ⋯ Show all: the suggestions widget's ⋯ Rows (leftdock.js — per workspace; 8 at
 *  first, or the old a3d.suggestTop; empty: all of them). */
export function suggestLimit() {
  const n = leftDock.rowsLimit('suggest');
  return n >= 1 ? n : Infinity;
}
export function setSuggestLimit(n) {
  const v = Math.round(+n);
  if (Number.isFinite(v)) leftDock.setRows('suggest', Math.min(30, Math.max(3, v)));
}
const topLabel = () => (Number.isFinite(suggestLimit()) ? t('Top {n}').replace('{n}', suggestLimit()) : t('All'));
// the ⋯ Rows changed (its ⋯ menu, ↺ Default layout), opened / closed: the tables on screen drawn again
const redraw = () => { for (const b of document.querySelectorAll('.view-suggest')) b.again?.(); };
window.addEventListener('a3d:suggest-rows', redraw);
window.addEventListener('a3d:lang', redraw); // (the 💡 button's texts: its own)

// ✕ closes the table: a 💡 Suggestions (n) button in the view's bottom-left corner instead, until it is clicked (or
// Space); its "Automatically" switch (also the table's ⋯ menu): the table opens on a selection by itself, as at first.
// Docked: closed = folded to its header. Per workspace, in the layout (leftdock.js sgState).
/** The suggestions opened again (the 💡 button, Space, the AI running a row). */
export function openSuggest() { leftDock.setSg({ closed: false }); redraw(); }
/** ✕: closed — and no longer opening by itself (said once). */
export function closeSuggest() {
  const was = leftDock.sgState().auto;
  leftDock.setSg({ closed: true, auto: false });
  redraw();
  let told = false;
  try { told = localStorage.getItem('a3d.sgToldClose') === '1'; localStorage.setItem('a3d.sgToldClose', '1'); } catch { /* private window */ }
  if (was && !told) {
    const tst = document.createElement('div');
    tst.className = 'toast info';
    tst.textContent = t('The suggestions no longer open by themselves — turn them on with the button in the bottom-left corner');
    tst.addEventListener('click', () => tst.remove());
    document.getElementById('toasts')?.appendChild(tst);
    setTimeout(() => tst.remove(), 6000);
  }
}
const isClosed = (b) => b.classList.contains('vs-closed') || (b.classList.contains('docked') && leftDock.folded('suggest'));

/** The 💡 button in the view's corner while the table is closed: how many suggestions there are for what is
 *  selected (n), the Automatically switch. */
function pill(vp, on, n) {
  let p = vp.querySelector(':scope > .vs-pill');
  if (!on) { p?.remove(); return; }
  if (!p) {
    p = document.createElement('div');
    p.className = 'vs-pill';
    p.dataset.noI18n = '';
    p.innerHTML = '<button class="vs-open"><span class="vs-i">💡</span> <span class="vs-n"></span></button><label class="vs-auto"><input type="checkbox"> <span></span></label>';
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick']) p.addEventListener(ev, (x) => x.stopPropagation());
    p.querySelector('.vs-open').addEventListener('click', () => openSuggest());
    const cb = p.querySelector('input');
    cb.addEventListener('change', () => { leftDock.setSg(cb.checked ? { auto: true, closed: false } : { auto: false }); redraw(); });
    vp.appendChild(p);
  }
  const b = p.querySelector('.vs-open'), l = p.querySelector('.vs-auto');
  b.querySelector('.vs-n').textContent = `${t('Suggestions')} (${n})`;
  b.title = t('Open the suggestions for what is selected (Space)');
  l.lastElementChild.textContent = t('Automatically');
  l.title = t('On: the suggestions open by themselves when you select something, and close when nothing is selected');
  l.querySelector('input').checked = leftDock.sgState().auto;
}

// Space (not in a box or on a button): the table opened / closed
document.addEventListener('keydown', (e) => {
  if (e.key !== ' ' || e.ctrlKey || e.altKey || e.metaKey || e.repeat || document.querySelector('.wz-stage')) return;
  const a = document.activeElement;
  if (a && a !== document.body && a.closest('input, textarea, select, button, a, [contenteditable]')) return;
  const vp = [...document.querySelectorAll('.viewport')].find((v) => v.offsetParent && v.querySelector(':scope > .view-suggest, :scope > .vs-pill'));
  if (!vp) return;
  e.preventDefault();
  if (leftDock.sgState().closed) openSuggest(); else closeSuggest();
});
/** ⋯ Show all opened: every table shows everything until ▴ Fewer (for this session). */
const showingAll = () => { try { return sessionStorage.getItem(ALL_KEY) === '1'; } catch { return false; } };
const setShowingAll = (on) => { try { if (on) sessionStorage.setItem(ALL_KEY, '1'); else sessionStorage.removeItem(ALL_KEY); } catch { /* private window */ } };

/** The rows to show: the same action twice (icon and label) once; more than the limit: only the most relevant ones
 *  (rank: lower first — none: its place in the list), kept in the list's order, under their sections. A row with
 *  `always` (a chosen hole's types and sizes: a choice to see whole) always shows and does not count to the limit. */
function pickRows(items, all) {
  const seen = new Set(), acts = [], pinned = [];
  items.forEach((it, i) => {
    if (it.section !== undefined) return;
    const key = `${it.icon || ''}|${it.label}`;
    if (seen.has(key)) return;
    seen.add(key);
    if (it.always) pinned.push(i);
    else acts.push({ i, r: Number.isFinite(it.rank) ? it.rank : i });
  });
  const over = acts.length > suggestLimit();
  const keep = new Set([...pinned, ...(over && !all ? [...acts].sort((a, b) => a.r - b.r || a.i - b.i).slice(0, suggestLimit()) : acts).map((a) => a.i)]);
  let sec = null;
  const rows = [];
  items.forEach((it, i) => {
    if (it.section !== undefined) { sec = it; return; }
    if (!keep.has(i)) return;
    if (sec) { rows.push(sec); sec = null; } // (a heading only above rows that show)
    rows.push({ ...it, i });
  });
  return { rows, total: acts.length + pinned.length, over, ranked: [...acts].sort((a, b) => a.r - b.r || a.i - b.i).map((a) => a.i) };
}

/** Show (or with no items: remove) the table in `viewport`: title (what is selected), items [{icon, label, title,
 *  run, danger, rank, always (shown past the limit), on (the current choice: ✓), hover?: (on) => … (shows what it would do)}, {section} or {icon, label, title, rank, chips: [{label, title, on, primary, run}]} (a row of
 *  values to pick with one click — a tolerance, a roughness; on: the current one, ✓)], hint (a line under it), refs (what is selected, as the AI's tools name it: ✨ puts
 *  it in the chat). More rows than the user's limit (suggestLimit): the most relevant ones, then ⋯ Show all (n). */
export function showSuggest(viewport, title, items, hint = '', refs = '') {
  let box = viewport.querySelector(':scope > .view-suggest');
  const closed = leftDock.sgState().closed && !leftDock.suggestDocked; // (docked: folded instead — leftdock.js)
  pill(viewport, closed, items?.length ? pickRows(items, true).total : 0);
  if (!items?.length) { box?.remove(); return null; }
  if (!box) {
    box = document.createElement('div');
    box.className = 'view-suggest';
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick']) box.addEventListener(ev, (x) => x.stopPropagation());
    viewport.appendChild(box);
  }
  const again = () => showSuggest(viewport, title, items, hint, refs);
  box.again = again;
  const all = showingAll(), { rows, total, over, ranked } = pickRows(items, all), setting = box.dataset.setting === '1';
  box.sg = { title, hint, refs, items, ranked, shown: rows.filter((it) => it.section === undefined).map((it) => it.i) }; // (for the AI: suggestTables)
  box.dataset.noI18n = '';
  box.classList.toggle('vs-closed', closed);
  const keep = box.contains(document.activeElement) && document.activeElement.dataset.sg; // (drawn again: the row in the keyboard's hand stays there)
  box.innerHTML = `<div class="vs-head"><button class="vs-pin" title="${esc(t('Dock it in the left panel — always in sight (or drag its header there)'))}">📌</button><b title="${esc(title)}">${esc(title)}</b><button class="vs-set${setting ? ' on' : ''}" title="${esc(t('How many suggestions show before ⋯ Show all — click to change'))}">${esc(topLabel())}</button>${refs && askAI ? `<button class="vs-ai" title="${esc(t('Ask the AI about it — what is selected goes into the chat'))}">✨</button>` : ''}<button class="vs-menu lw-menu" title="${esc(t('Layout: dock it, float it over the view, its opacities, ↺ Default layout'))}">⋯</button><button class="vs-x" title="${esc(t('Close the suggestions — 💡 in the view\'s bottom-left corner opens them again (Space)'))}">✕</button></div>
    ${setting ? `<label class="vs-top" title="${esc(t('The most relevant suggestions first; the rest under ⋯ Show all'))}">${esc(t('Show first'))} <input type="number" min="3" max="30" step="1" value="${Number.isFinite(suggestLimit()) ? suggestLimit() : ''}"> ${esc(t('suggestions'))}</label>` : ''}
    <div class="vs-list">${rows.map((it) => (it.section !== undefined ? `<div class="vs-sec">${esc(it.section)}</div>` // (a heading: what the rows under it act on)
      : it.chips ? `<div class="vs-chips" title="${esc(it.title || '')}">${it.label ? `<span class="vs-cl"><span class="vs-i">${it.icon || '•'}</span> ${esc(it.label)}</span>` : ''}<div class="vs-cg">${it.chips.map((c, j) => // (a row of values, one click each: the current one ✓)
        `<button class="chip${c.on ? ' on' : ''}${c.primary ? ' vs-pri' : ''}" data-sgc="${it.i}:${j}" title="${esc(c.title || '')}">${c.on ? '✓ ' : ''}${esc(c.label)}</button>`).join('')}</div></div>`
      : `<button data-sg="${it.i}" class="${it.danger ? 'danger' : ''}${it.always ? ' vs-pin-row' : ''}${it.on ? ' on' : ''}" title="${esc(it.title || '')}"><span class="vs-i">${it.icon || '•'}</span> <span>${esc(it.label)}</span>${it.on ? '<span class="vs-on">✓</span>' : ''}</button>`)).join('')}${!over ? ''
      : all ? `<button class="vs-more" data-sg-fewer title="${esc(t('Only the most relevant suggestions'))}"><span class="vs-i">▴</span> <span>${esc(t('Fewer'))}</span></button>`
        : `<button class="vs-more" data-sg-all title="${esc(t('Everything that can be done with what is selected'))}"><span class="vs-i">⋯</span> <span>${esc(t('Show all'))} (${total})</span></button>`}</div>
    ${hint ? `<p class="vs-hint">${esc(hint)}</p>` : ''}`;
  for (const b of box.querySelectorAll('[data-sg]')) b.addEventListener('click', () => items[+b.dataset.sg].run());
  for (const b of box.querySelectorAll('[data-sgc]')) b.addEventListener('click', () => { const [i, j] = b.dataset.sgc.split(':').map(Number); items[i].chips[j].run(); });
  for (const b of box.querySelectorAll('[data-sg]')) { // a row with hover(on): shows what it would do while the mouse (or the keyboard) is on it
    const it = items[+b.dataset.sg];
    if (!it.hover) continue;
    b.addEventListener('mouseenter', () => it.hover(true));
    b.addEventListener('mouseleave', () => it.hover(false));
    b.addEventListener('focus', () => it.hover(true));
    b.addEventListener('blur', () => it.hover(false));
  }
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
  const mb = box.querySelector('.vs-menu'); // (⋯: its place, opacities, ↕ Automatic height, Rows — as every widget's)
  mb.addEventListener('click', (e) => { e.stopPropagation(); leftDock.menu('suggest', mb); });
  box.querySelector('.vs-x').addEventListener('click', (e) => { e.stopPropagation(); closeSuggest(); });
  box.querySelector('.vs-pin')?.addEventListener('click', (e) => { e.stopPropagation(); leftDock.dock('suggest'); for (const b of document.querySelectorAll('.view-suggest')) leftDock.placeSuggest(b, b.parentElement); });
  box.sgOpts = { kind: 'suggest', handle: '.vs-head', min: [170, 90], onDefault: (b) => cornerPlace(b, viewport) };
  leftDock.placeSuggest(box, viewport); // (floating: moved / resized / remembered; or docked in the left column)
  scrollFade(box.querySelector('.vs-list')); // (no scrollbar: a fade where rows are hidden)
  if (keep) box.querySelector(`[data-sg="${keep}"]`)?.focus();
  return box;
}

/** The suggestion tables the user sees now (floating, docked, a menu), for the AI: [{box, title, hint, refs, docked,
 *  menu, rows: [{i, icon, label, title, section, rank_pos, shown}]} — every action, the ones under ⋯ Show all with
 *  shown false; rank_pos 1 = the most relevant]. */
export function suggestTables() {
  return [...document.querySelectorAll('.view-suggest, .sg-menu')].filter((b) => b.sg && (b.classList.contains('sg-menu') || b.parentElement?.offsetParent)
    && (isClosed(b) || (b.getClientRects().length && !b.classList.contains('lw-off')))).map((box) => { // (closed by the user: there too, closed)
    const { title, hint, refs, items, ranked, shown } = box.sg, on = new Set(shown);
    let sec = null;
    const secOf = new Map();
    items.forEach((it, i) => { if (it.section !== undefined) sec = it.section; else secOf.set(i, sec); });
    return { box, title, hint, refs, docked: box.classList.contains('docked'), menu: box.classList.contains('sg-menu'), closed: isClosed(box),
      rows: ranked.map((i, k) => ({ i, icon: items[i].icon || '', label: items[i].label, title: items[i].title || '', section: secOf.get(i) || undefined, rank_pos: k + 1, shown: on.has(i) })) };
  });
}

/** Run the row `i` of a table from suggestTables as the user would: a row under ⋯ Show all shown first (then the
 *  table goes back to its top rows, as the user had it). -> false when the row is not there. */
export function runSuggestion(box, i) {
  if (isClosed(box)) openSuggest(); // (closed by the user: opened first, as they would)
  let row = box.querySelector(`[data-sg="${i}"]`), opened = false;
  if (!row && box.querySelector('[data-sg-all]')) { box.querySelector('[data-sg-all]').click(); opened = true; row = box.querySelector(`[data-sg="${i}"]`); }
  if (!row) return false;
  row.dispatchEvent(new MouseEvent('mouseenter'));
  row.click();
  if (opened) setShowingAll(false);
  return true;
}

// ---------------------------------------------------------------------------------------------- the keyboard
// ↓ / ↑ with nothing being typed: into the suggestions table on screen (its first / last row), then from row to row;
// Enter runs the row (and nothing else that listens for Enter); Esc leaves the table (the app's Esc follows: the
// selection goes, and with it the table). Home / End: the first / last row. A menu (suggestMenu) the same way.
const ROWS = '.vs-list button';
const shownTables = () => [...document.querySelectorAll('.sg-menu, .view-suggest')].filter((b) => b.getClientRects().length && b.querySelector(ROWS));
function onKeys(e) {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const a = document.activeElement, box = a?.closest?.('.view-suggest, .sg-menu');
  const free = !a || a === document.body || a.tagName === 'CANVAS'; // (no field, no list of its own in the keyboard's hand)
  const nav = { ArrowDown: 1, ArrowUp: -1, Home: 'first', End: 'last' }[e.key];
  if (nav !== undefined && (box || (free && typeof nav === 'number'))) {
    const tb = box || shownTables()[0];
    const rows = tb ? [...tb.querySelectorAll(ROWS)] : [];
    if (!rows.length) return;
    const i = rows.indexOf(a);
    const n = nav === 'first' ? 0 : nav === 'last' ? rows.length - 1 : i < 0 ? (nav > 0 ? 0 : rows.length - 1) : (i + nav + rows.length) % rows.length;
    e.preventDefault();
    e.stopPropagation();
    rows[n].focus();
    return;
  }
  if (!box || !a.matches(ROWS)) return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); a.click(); }
  else if (e.key === 'Escape') {
    a.blur();
    if (box.classList.contains('sg-menu')) { e.stopPropagation(); box.close?.(); }
  }
}
window.addEventListener('keydown', onKeys, true);

/** A small menu of suggestions at a place (a tab right-clicked, long-pressed): the table's look and keys. at: an element
 *  (under it) or {x, y}; items as showSuggest's ({icon, label, title, run, danger} or {section}). Closes on a pick, a
 *  click elsewhere, Esc. -> the menu element. */
export function suggestMenu(at, title, items) {
  document.querySelector('.sg-menu')?.close();
  const box = document.createElement('div');
  box.className = 'sg-menu';
  box.dataset.noI18n = '';
  box.setAttribute('role', 'menu');
  box.sg = { title, hint: '', refs: '', items, ranked: items.map((it, i) => (it.section === undefined ? i : -1)).filter((i) => i >= 0), shown: items.map((_, i) => i) };
  box.innerHTML = `${title ? `<div class="vs-head"><b title="${esc(title)}">${esc(title)}</b></div>` : ''}<div class="vs-list">${items.map((it, i) => (it.section !== undefined
    ? `<div class="vs-sec">${esc(it.section)}</div>`
    : `<button data-sg="${i}" role="menuitem" class="${it.danger ? 'danger' : ''}" title="${esc(it.title || '')}"><span class="vs-i">${it.icon || '•'}</span> <span>${esc(it.label)}</span>${it.key ? `<kbd class="vs-key">${esc(it.key)}</kbd>` : ''}</button>`)).join('')}</div>`;
  const off = (e) => { if (!box.contains(e.target)) box.close(); };
  box.close = () => { document.removeEventListener('pointerdown', off, true); box.remove(); };
  for (const b of box.querySelectorAll('[data-sg]')) b.addEventListener('click', () => { box.close(); items[+b.dataset.sg].run(); });
  document.body.appendChild(box);
  const r = at instanceof Element ? at.getBoundingClientRect() : { left: at.x, bottom: at.y }, w = box.offsetWidth, h = box.offsetHeight;
  box.style.left = `${Math.max(4, Math.min(innerWidth - w - 4, r.left))}px`;
  box.style.top = `${Math.max(4, r.bottom + h + 4 > innerHeight ? r.bottom - h - 4 : r.bottom + 2)}px`;
  setTimeout(() => document.addEventListener('pointerdown', off, true), 0);
  box.querySelector(ROWS)?.focus();
  return box;
}
