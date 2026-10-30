// 📄 New project: the project on screen is kept (autosave: Open ▾ › 🕘 Recent projects has it), then this window
// starts again with an empty one — the start screen, a new autosave record. The page is loaded afresh (nothing of the
// old project lingers in the workspaces); a toast says where the old one is and ↶ opens it again. ⧉ New project in a
// new window: this one stays as it is. Ctrl+Alt+N (Ctrl+N is the browser's own new window).
// ✕ Close project: the same, its picture drawn first — the start screen again, the closed project first in 🕘 Recent
// projects (one click opens it again). The chat and a ⏺ recording go on; the undo history goes with the page. No
// shortcut: Ctrl+W (Ctrl+Shift+W) closes the browser's tab or window.
import { t } from './i18n.js';
import { confirmIn } from './choose.js';

const AFTER = 'a3d.newProject'; // sessionStorage: {name, id, closed} of the project kept — the toast after the fresh load
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

/** hooks: {autosave, name() -> the project's name ('' when empty), empty() -> nothing in it, keepChat(), toast} */
export function initNewProject(hooks) {
  const url = () => `${location.pathname}?new`;

  async function start(inNewWindow = false) {
    if (inNewWindow) {
      const w = window.open(url(), '_blank', 'popup=yes,width=1400,height=900');
      if (!w) hooks.toast(t('The browser blocked the new window — allow pop-ups for this page.'), 'warning', 7000);
      return w;
    }
    if (hooks.empty()) { hooks.toast(t('This project is empty already — start with one of the cards.'), 'info', 4000); return null; }
    await hooks.autosave.saveNow();
    if (!hooks.autosave.kept() && !(await confirmIn('The project could not be kept on the server (see “⚠ Not saved”). Start a new project anyway? Its last changes would be lost.', { ok: 'Start a new one', danger: true }))) return null;
    try { sessionStorage.setItem(AFTER, JSON.stringify({ name: hooks.name(), id: hooks.autosave.id })); } catch { /* private window */ }
    hooks.keepChat?.(); // (this window's AI chat goes on in the new project)
    location.assign(url());
    return null;
  }

  /** ✕ Close project: kept (saved now, its picture drawn) -> the start screen; not kept: “Close anyway” / “Back”. */
  async function close() {
    const empty = hooks.empty();
    if (!empty) {
      await hooks.autosave.saveNow();
      if (hooks.autosave.kept()) await hooks.autosave.keepThumb({ force: true });
      else if (!(await confirmIn('The project could not be saved on the server (see “⚠ Not saved”). Close it anyway? Its last changes would be lost.', { ok: 'Close anyway', cancel: 'Back', danger: true }))) return false;
    }
    try { sessionStorage.setItem(AFTER, JSON.stringify({ name: hooks.name(), id: empty ? '' : hooks.autosave.id, closed: true })); } catch { /* private window */ }
    hooks.keepChat?.();
    location.assign(url());
    return true;
  }

  // the fresh page: where the old project is, ↶ to open it again
  if (new URLSearchParams(location.search).has('new')) {
    history.replaceState(null, '', location.pathname); // (a reload later: an ordinary start)
    let was = null;
    try { was = JSON.parse(sessionStorage.getItem(AFTER) || 'null'); sessionStorage.removeItem(AFTER); } catch { was = null; }
    if (was?.closed) {
      if (was.id) hooks.autosave.first = was.id; // (🕘 Recent projects: it first)
      hooks.toast(was.id ? tv('“{name}” is closed — it is first in 🕘 Recent projects, one click opens it again.', { name: was.name || t('Project') })
        : t('The project is closed.'), 'ok', 6000).dataset.noI18n = '';
    } else if (was?.id) {
      const el = hooks.toast(tv('The previous project “{name}” is kept — Open ▾ › 🕘 Recent projects.', { name: was.name || t('Project') }), 'ok', 9000);
      el.dataset.noI18n = '';
      const b = document.createElement('button');
      b.className = 'mini';
      b.textContent = `↶ ${t('Open it again')}`;
      b.title = t('Back to the previous project (this empty one is not kept)');
      b.addEventListener('click', async () => {
        el.remove();
        try { await hooks.autosave.open(was.id); } catch (e) { hooks.toast(e.message, 'error'); }
      });
      el.append(' ', b);
    }
  }

  // Ctrl+Alt+N (not while typing): the key's place, not its letter — on a Czech keyboard Ctrl+Alt is AltGr
  window.addEventListener('keydown', (e) => {
    if (!(e.ctrlKey || e.metaKey) || !e.altKey || e.shiftKey || e.code !== 'KeyN') return;
    if (e.target.closest?.('input,select,textarea,[contenteditable=true]')) return;
    e.preventDefault();
    start(false);
  });
  return { start, close, handlers: () => newProjectHandlers(start, hooks, close) };
}

/** new_project: as 📄 New project; close_project: as ✕ Close project — answered first, the page starts again a moment
 *  later (the chat goes on). */
export function newProjectHandlers(start, hooks, close) {
  return {
    new_project: async ({ new_window } = {}) => {
      if (new_window) {
        if (!start(true)) throw new Error('The browser blocked the new window — the user allows pop-ups for this page, or clicks ⧉ New project in a new window.');
        return { text: 'A new, empty project opened in a window of its own; this one stays as it is (the tools keep working on this window).' };
      }
      if (hooks.empty()) return { text: 'This project is empty already — nothing to keep; go on in it (new_model / new_assembly).' };
      const name = hooks.name();
      setTimeout(() => start(false), 300); // (after this answer is sent: the page loads afresh)
      return { text: `The project “${name || 'Project'}” is kept (Open ▾ › 🕘 Recent projects) and this window starts a new, empty one — wait a moment, then list_parts (empty) and new_model / new_assembly.` };
    },
    close_project: async () => {
      const name = hooks.name(), empty = hooks.empty();
      if (!empty) {
        await hooks.autosave.saveNow();
        if (!hooks.autosave.kept()) throw new Error('The project could not be saved on the server (“⚠ Not saved”) — not closed. Tell the user; they can close it anyway with Open ▾ › ✕ Close project.');
      }
      setTimeout(() => close(), 300); // (after this answer is sent: the page loads afresh)
      return { text: empty ? 'The empty project is closed — the start screen shows (wait a moment).'
        : `The project “${name || 'Project'}” is saved and closed — the start screen shows it first in 🕘 Recent projects (the user's one click on it opens it again). Wait a moment before the next tool.` };
    },
  };
}
