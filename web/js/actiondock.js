// Action buttons — OK / Cancel of a step, ✓ Finish sketch, Done — float in the bottom-right corner of the view, in
// every workspace; the toolbars keep the drawing tools. A panel or toolbar draws them as usual in a `.mp-actions`
// row; the row is moved here and a hidden placeholder keeps its place, so a panel drawn again brings its own row
// (and the old one goes).

const TIPS = { ok: 'Apply and close (Enter)', cancel: 'Close without changing anything (Esc)' };

export function actionDock(viewport, sources) {
  const dock = document.createElement('div');
  dock.className = 'view-actions';
  dock.hidden = true;
  viewport.appendChild(dock);
  const held = new Map(); // placeholder -> its row
  const sync = () => {
    for (const src of sources) {
      for (const row of src.querySelectorAll('.mp-actions')) {
        if (row.closest('.view-actions')) continue;
        const at = document.createElement('i');
        at.className = 'mp-actions-at';
        at.hidden = true;
        row.replaceWith(at);
        held.set(at, row);
        for (const b of row.querySelectorAll('button:not([title])')) { // (every button says what it does)
          const tip = TIPS[b.dataset.a]; // (by its action: its text may be translated already)
          if (tip) b.title = tip;
        }
      }
    }
    for (const [at, row] of held) if (!at.isConnected) { held.delete(at); row.remove(); }
    for (const row of held.values()) if (row.parentNode !== dock) dock.appendChild(row);
    dock.hidden = !held.size;
    document.body.classList.toggle('view-acts', [...document.querySelectorAll('.view-actions')].some((d) => !d.hidden && d.offsetParent));
  };
  const mo = new MutationObserver(sync);
  for (const src of sources) mo.observe(src, { childList: true, subtree: true });
  sync();
  return dock;
}
