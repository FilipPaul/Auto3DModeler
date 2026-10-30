// A question with a few answers (more than OK / Cancel): a small dialog over the page.
import { t } from './i18n.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** text: the question; options: [{value, label, hint?, primary?, danger?}]; cls: an extra class on the dialog
 *  -> the chosen value (null: Esc / ✕). */
export function choose(text, options, { cls = '' } = {}) {
  return new Promise((resolve) => {
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose ${cls}" role="dialog" aria-modal="true"><p>${esc(text)}</p>
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

/** Yes / no in the page (never the browser's own confirm dialog: no pop-ups outside the app): text: the question
 *  (translated here, as the old dialog was); ok: the yes button's word; danger: it deletes / loses something
 *  -> true (yes) / false (Cancel, Esc, ✕). */
export async function confirmIn(text, { ok = 'OK', danger = false } = {}) {
  return (await choose(t(text), [{ value: true, primary: true, danger, label: ok }, { value: false, label: 'Cancel' }], { cls: 'confirm' })) === true;
}

/** A short text to type (a name, a scale): text: the question; value: what it starts with; check(v) -> an error
 *  message or '' (shown under the field, OK waits) -> the text (trimmed), or null (Esc / Cancel). */
export function ask(text, value = '', { hint = '', placeholder = '', ok = 'OK', check = null } = {}) {
  return new Promise((resolve) => {
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose ask" role="dialog" aria-modal="true"><p>${esc(text)}</p>
      <input type="text" class="ask-in" value="${esc(value)}" placeholder="${esc(placeholder)}">
      ${hint ? `<p class="hint ask-hint">${esc(hint)}</p>` : ''}<p class="mp-bad ask-bad" hidden></p>
      <div class="row-actions"><button class="btn primary" data-a="ok">${esc(t(ok))}</button><button class="btn" data-a="no">${esc(t('Cancel'))}</button></div>
      <button class="mini choose-x" data-a="no" title="${esc(t('Cancel'))}">✕</button></div>`;
    const inp = back.querySelector('.ask-in'), bad = back.querySelector('.ask-bad');
    const done = (v) => { document.removeEventListener('keydown', onKey, true); back.remove(); resolve(v); };
    const okNow = () => {
      const v = inp.value.trim(), err = !v ? t('Type something first.') : check ? check(v) : '';
      bad.hidden = !err;
      bad.textContent = err || '';
      if (!err) done(v);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); done(null); }
      if (e.key === 'Enter') { e.stopPropagation(); e.preventDefault(); okNow(); }
    };
    for (const b of back.querySelectorAll('[data-a=no]')) b.addEventListener('click', () => done(null));
    back.querySelector('[data-a=ok]').addEventListener('click', okNow);
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(back);
    inp.focus();
    inp.select();
  });
}
