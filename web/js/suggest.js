// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected. Its header drags it
// elsewhere in the view; that place is remembered.
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const KEY = 'a3d.suggestAt';

const savedAt = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; } };

/** Where the user put it: [x, y] as parts of the view (0 … 1), kept inside it. */
function place(box, viewport) {
  const at = savedAt();
  if (!at) { box.style.left = box.style.top = box.style.bottom = ''; return; }
  const vr = viewport.getBoundingClientRect(), w = box.offsetWidth || 236, h = box.offsetHeight || 120;
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
 *  run, danger}], hint (a line under it). */
export function showSuggest(viewport, title, items, hint = '') {
  let box = viewport.querySelector(':scope > .view-suggest');
  if (!items?.length) { box?.remove(); return null; }
  if (!box) {
    box = document.createElement('div');
    box.className = 'view-suggest';
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick']) box.addEventListener(ev, (x) => x.stopPropagation());
    viewport.appendChild(box);
  }
  box.dataset.noI18n = '';
  box.innerHTML = `<div class="vs-head"><b>${esc(title)}</b><span>${esc(t('Suggested'))}</span></div>
    <div class="vs-list">${items.map((it, i) => `<button data-sg="${i}" class="${it.danger ? 'danger' : ''}" title="${esc(it.title || '')}"><span class="vs-i">${it.icon || '•'}</span> <span>${esc(it.label)}</span></button>`).join('')}</div>
    ${hint ? `<p class="vs-hint">${esc(hint)}</p>` : ''}`;
  for (const b of box.querySelectorAll('[data-sg]')) b.addEventListener('click', () => items[+b.dataset.sg].run());
  draggable(box, viewport);
  place(box, viewport);
  return box;
}
