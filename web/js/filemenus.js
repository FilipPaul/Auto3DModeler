// 📂 Open ▾ and Export ▾ in the top bar: panels in sections (Project, Demos, Import · CAD and 3D, · 2D drawings,
// · PCB | 3D, 2D / drawings, Data, Project), an icon and a short hint per item. An Open item with data-pick opens its
// file input (each filtered to its types; all go the one way a file opens — its type decides). Export: every format
// listed, those that do not fit the tab on screen greyed with the reason in place of the hint. The keyboard: ↑↓ the
// items, ←→ the other column, Home / End, Enter runs one, Esc closes; a click outside closes.
import { t } from './i18n.js';
import { thumbHtml } from './autosave.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const when = (s) => new Date(s * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const ITEMS = '.fm-item:not(.off), .fm-proj';

/** The items one can go to, in the order they are read. */
const itemsOf = (list) => [...list.querySelectorAll(ITEMS)].filter((b) => b.offsetParent);

/** ↑↓ ←→ Home End Esc in an open menu (wrap: its .menu, btn: what opens it). */
function menuKeys(wrap, btn) {
  const list = wrap.querySelector('.menu-list');
  const close = () => { wrap.classList.remove('open'); btn.focus(); };
  btn.addEventListener('keydown', (e) => { // ↓ on the closed button opens it
    if (e.key !== 'ArrowDown' || wrap.classList.contains('open') || btn.disabled) return;
    e.preventDefault();
    btn.click();
  });
  list.addEventListener('pointermove', (e) => { // (the pointer and the keys: one item lit)
    const b = e.target.closest(ITEMS);
    if (b && document.activeElement !== b) b.focus({ preventScroll: true });
  });
  list.addEventListener('keydown', (e) => {
    const all = itemsOf(list), i = all.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key === 'Tab') { wrap.classList.remove('open'); return; }
    let to = null;
    if (e.key === 'ArrowDown') to = all[(i + 1) % all.length];
    else if (e.key === 'ArrowUp') to = all[(i - 1 + all.length) % all.length];
    else if (e.key === 'Home') to = all[0];
    else if (e.key === 'End') to = all[all.length - 1];
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') to = beside(all, all[i], e.key === 'ArrowRight' ? 1 : -1);
    else if (e.key === 'Enter' && document.activeElement?.matches('.fm-item.off')) { e.preventDefault(); return; }
    if (!to) return;
    e.preventDefault();
    to.focus();
  });
}

/** The item of the next column (dir 1: right, -1: left) at the height of `from`. */
function beside(all, from, dir) {
  if (!from) return all[0];
  const r = from.getBoundingClientRect(), y = r.top + r.height / 2;
  let best = null, bd = Infinity;
  for (const b of all) {
    const q = b.getBoundingClientRect();
    if (dir > 0 ? q.left < r.right - 1 : q.right > r.left + 1) continue;
    const d = Math.abs(q.top + q.height / 2 - y) + Math.abs(q.left - r.left) / 1000; // (the nearest column first)
    if (d < bd) { bd = d; best = b; }
  }
  return best;
}

/** The menu just opened: its first item focused (the keys work at once; no ring after a click). */
function focusFirst(wrap) {
  if (!wrap.classList.contains('open')) return;
  requestAnimationFrame(() => itemsOf(wrap.querySelector('.menu-list'))[0]?.focus({ preventScroll: true }));
}

/** hooks: {autosave (autosave.js: the recent projects), toast(text, kind)}. */
export function initFileMenus(hooks) {
  const wrap = $('openMenuWrap'), btn = $('openBtn'), menu = $('openMenu');
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (wrap.classList.toggle('open')) { fillRecent(hooks, $('openRecent')); focusFirst(wrap); }
  });
  // an item picks its kind of file: the input filtered to those types
  for (const b of menu.querySelectorAll('[data-pick]')) b.addEventListener('click', () => $(b.dataset.pick).click());
  // a choice closes the menu (the file dialog opens from the item)
  menu.addEventListener('click', (e) => { if (e.target.closest('.fm-item, .fm-proj')) setTimeout(() => wrap.classList.remove('open'), 0); });
  document.addEventListener('click', (e) => { if (!e.target.closest('#openMenuWrap')) wrap.classList.remove('open'); });
  menuKeys(wrap, btn);

  const xwrap = $('exportMenuWrap'), xbtn = $('exportBtn');
  xbtn.addEventListener('click', () => focusFirst(xwrap)); // (app.js toggles it and marks what applies, first)
  menuKeys(xwrap, xbtn);
}

/** Export ▾: the items that fit the tab on screen (ws: quick, model, assembly, sheet, drawing) lit, the others greyed
 *  with their reason; canSave: the project can be saved (.a3d). */
export function markExport(ws, { canSave = true } = {}) {
  for (const b of $('exportMenu').querySelectorAll('[data-fmt]')) {
    const on = b.dataset.ws.split(' ').includes(ws) && (b.dataset.fmt !== 'a3d' || canSave);
    b.classList.toggle('off', !on);
    b.setAttribute('aria-disabled', on ? 'false' : 'true');
  }
}

/** 🕘 the last three projects kept on the server, under Recent projects (a click opens one). */
async function fillRecent(hooks, el) {
  const a = hooks.autosave;
  if (!el || !a) return;
  let list = [];
  try { list = (await a.recent()).filter((p) => p.id !== a.id); } catch { list = []; }
  list = [...list.filter((p) => p.id === a.first), ...list.filter((p) => p.id !== a.first)].slice(0, 3); // (✕ the project just closed: first)
  el.hidden = !list.length;
  el.innerHTML = list.map((p) => `<button class="fm-proj" role="menuitem" data-id="${esc(p.id)}" title="${esc(t('Open'))}: ${esc(p.name)}">
    ${thumbHtml(p, 'fm-thumb')}<b data-no-i18n>${esc(p.name)}</b><i data-no-i18n>${esc(when(p.time))}</i></button>`).join('');
  for (const b of el.querySelectorAll('.fm-proj')) {
    b.addEventListener('click', async () => {
      const p = list.find((x) => x.id === b.dataset.id);
      try { await a.open(p.id); hooks.toast(t('“{name}” is open again.').replace('{name}', p.name), 'ok'); } catch (e) { hooks.toast(e.message, 'error'); }
    });
  }
}
