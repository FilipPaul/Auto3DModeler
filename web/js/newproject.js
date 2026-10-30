// 📄 New project: the project on screen is kept (autosave: Open ▾ › 🕘 Recent projects has it), then this window
// starts again with an empty one — the start screen, a new autosave record. The page is loaded afresh (nothing of the
// old project lingers in the workspaces); a toast says where the old one is and ↶ opens it again. ⧉ New project in a
// new window: this one stays as it is. Ctrl+Alt+N (Ctrl+N is the browser's own new window).
import { t } from './i18n.js';

const AFTER = 'a3d.newProject'; // sessionStorage: {name, id} of the project kept — the toast after the fresh load
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
    if (!hooks.autosave.kept() && !confirm(t('The project could not be kept on the server (see “⚠ Not saved”). Start a new project anyway? Its last changes would be lost.'))) return null;
    try { sessionStorage.setItem(AFTER, JSON.stringify({ name: hooks.name(), id: hooks.autosave.id })); } catch { /* private window */ }
    hooks.keepChat?.(); // (this window's AI chat goes on in the new project)
    location.assign(url());
    return null;
  }

  // the fresh page: where the old project is, ↶ to open it again
  if (new URLSearchParams(location.search).has('new')) {
    history.replaceState(null, '', location.pathname); // (a reload later: an ordinary start)
    let was = null;
    try { was = JSON.parse(sessionStorage.getItem(AFTER) || 'null'); sessionStorage.removeItem(AFTER); } catch { was = null; }
    if (was?.id) {
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
  return { start, handlers: () => newProjectHandlers(start, hooks) };
}

/** new_project: as 📄 New project — answered first, the page starts again a moment later (the chat goes on). */
export function newProjectHandlers(start, hooks) {
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
  };
}
