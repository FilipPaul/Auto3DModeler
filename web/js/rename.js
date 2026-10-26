// Rename in place: the name's element becomes editable; Enter / leaving it keeps the new name, Esc goes back.

/** el: the element showing the name; done(name) gets the new name (not called when unchanged or empty). */
export function renameInPlace(el, done) {
  const before = el.textContent;
  el.contentEditable = 'true';
  el.classList.add('renaming');
  el.focus();
  document.getSelection().selectAllChildren(el);
  let finished = false;
  const finish = (keep) => {
    if (finished) return;
    finished = true;
    el.contentEditable = 'false';
    el.classList.remove('renaming');
    const n = el.textContent.trim();
    if (keep && n && n !== before) done(n);
    else el.textContent = before;
  };
  el.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  });
  for (const t of ['click', 'dblclick', 'pointerdown']) el.addEventListener(t, (e) => e.stopPropagation());
  el.addEventListener('blur', () => finish(true), { once: true });
}
