// The suggestions table: what can be done with what is selected (one shape or part, or several with Ctrl+click),
// in the bottom-left corner of the view — small, out of the way, gone when nothing is selected.
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

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
  return box;
}
