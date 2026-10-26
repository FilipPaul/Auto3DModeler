// A question with a few answers (more than OK / Cancel): a small dialog over the page.
import { t } from './i18n.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** text: the question; options: [{value, label, hint?, primary?, danger?}] -> the chosen value (null: Esc / ✕). */
export function choose(text, options) {
  return new Promise((resolve) => {
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose" role="dialog" aria-modal="true"><p>${esc(text)}</p>
      <div class="choose-opts">${options.map((o, i) => `<button class="btn ${o.primary ? 'primary' : ''} ${o.danger ? 'danger' : ''}" data-i="${i}">${esc(t(o.label))}
        ${o.hint ? `<span class="choose-hint">${esc(t(o.hint))}</span>` : ''}</button>`).join('')}</div>
      <button class="mini choose-x" data-i="-1" title="${esc(t('Cancel'))}">✕</button></div>`;
    const done = (v) => { document.removeEventListener('keydown', onKey, true); back.remove(); resolve(v); };
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); done(null); } };
    for (const b of back.querySelectorAll('[data-i]')) b.addEventListener('click', () => done(+b.dataset.i < 0 ? null : options[+b.dataset.i].value));
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(back);
    back.querySelector('.btn.primary, .btn')?.focus();
  });
}
