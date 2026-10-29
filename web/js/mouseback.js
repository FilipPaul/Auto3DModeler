// The mouse's side buttons and the browser's Back: the app never leaves its page by accident. ◀ (button 3, "back") is
// Undo and ▶ (button 4, "forward") is Redo in the workspace on screen — sent as Ctrl+Z / Ctrl+Y, so they take the very
// path the keys do (3D model, sketch, assembly, sheet, 2D drawing, quick part). In a text field they do nothing (the
// browser's own text undo is the keys'). Back from elsewhere (Alt+←, a touchpad swipe, the toolbar's ←) lands on a
// guard entry in the tab's history and stays here. No "leave the page?" prompt: the autosave keeps the project on
// close / reload (pagehide), and a prompt would also stop 📄 New project's fresh load.
const SIDE = { 3: { key: 'z', code: 'KeyZ' }, 4: { key: 'y', code: 'KeyY' } };
const GUARD = 'a3dGuard';

const typing = (el) => !!el?.closest?.('input,select,textarea,[contenteditable]:not([contenteditable=false])');

/** Undo (-1) / redo (+1) as the keys do it: a Ctrl+Z / Ctrl+Y keydown on the page. */
export function undoRedo(dir) {
  const k = SIDE[dir < 0 ? 3 : 4];
  document.body.dispatchEvent(new KeyboardEvent('keydown', { key: k.key, code: k.code, ctrlKey: true, bubbles: true, cancelable: true }));
}

export function initMouseBack() {
  // ◀ / ▶: the browser goes back / forward on the button's release unless it is stopped — stopped on both, done once
  // on the press
  for (const type of ['mousedown', 'mouseup', 'auxclick']) {
    document.addEventListener(type, (e) => {
      if (!SIDE[e.button]) return;
      e.preventDefault();
      if (type === 'mousedown' && !typing(e.target)) undoRedo(e.button === 3 ? -1 : 1);
    }, true);
  }
  // the guard: one entry over the page's own, put back each time Back takes it away (pushed again after the first
  // click / key too — the browser skips entries a page added before anyone touched it)
  const guard = () => window.history.pushState({ [GUARD]: true }, '', location.href);
  if (!window.history.state?.[GUARD]) guard();
  let touched = false;
  const first = (e) => {
    if (touched || !e.isTrusted) return;
    touched = true;
    guard();
  };
  addEventListener('pointerdown', first, true);
  addEventListener('keydown', first, true);
  addEventListener('popstate', () => guard());
}
