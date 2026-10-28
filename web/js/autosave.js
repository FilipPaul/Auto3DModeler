// Autosave: the project on screen kept on the server (data/projects/) a few seconds after each change — a closed tab or
// a browser crash loses nothing — and 🕘 Recent projects to open again (the last one offered when the app starts empty).
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const when = (s) => new Date(s * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const newId = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);

export class Autosave {
  /** hooks: {project() -> the project file or null (nothing to keep), restore(project) (opens it), toast, status(el)} */
  constructor(hooks, { delay = 3000 } = {}) {
    this.hooks = hooks;
    this.delay = delay;
    this.id = newId();
    this.last = '';
    this.timer = null;
    window.addEventListener('a3d:changed', () => { this.schedule(); this.dropOffer(); });
    // the last change, when the tab is closed or reloaded
    window.addEventListener('pagehide', () => this.saveNow({ beacon: true }));
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.saveNow(); });
  }

  /** A project opened from a file is a project of its own (its own id); one opened from the recent ones keeps its id. */
  fresh(id = null) { this.id = id || newId(); this.last = ''; this.hooks.onId?.(this.id); }

  schedule() { clearTimeout(this.timer); this.timer = setTimeout(() => this.saveNow(), this.delay); }

  async saveNow({ beacon = false } = {}) {
    clearTimeout(this.timer);
    let proj;
    try { proj = this.hooks.project(); } catch { return null; }
    if (!proj?.parts?.length) return null;
    const text = JSON.stringify(proj);
    if (text === this.last) return null;
    const body = JSON.stringify({ project: proj }), url = `/api/projects/${encodeURIComponent(this.id)}`;
    if (beacon && navigator.sendBeacon) { if (navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }))) this.last = text; return null; }
    try {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || res.statusText);
      this.last = text;
      this.savedAt = r.time;
      this.showStatus();
      return r;
    } catch (e) {
      this.showStatus(e.message);
      return null;
    }
  }

  showStatus(error) {
    const el = this.hooks.status?.();
    if (!el) return;
    el.hidden = false;
    el.classList.toggle('bad', !!error);
    el.textContent = error ? '⚠ Not saved' : `✓ Saved ${new Date(this.savedAt * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
    el.title = error ? `The project could not be kept on the server: ${error}` : 'Kept on the server a few seconds after each change — 🕘 Recent projects opens it again.';
  }

  async recent() { return (await (await fetch('/api/projects')).json()).projects || []; }

  async open(id) {
    const res = await fetch(`/api/projects/${encodeURIComponent(id)}`), proj = await res.json();
    if (!res.ok || proj.error) throw new Error(proj.error || res.statusText);
    await this.saveNow(); // (the one on screen kept first)
    await this.hooks.restore(proj);
    this.fresh(id);
    this.last = JSON.stringify(this.hooks.project() || {});
  }

  /** The user started working (a part opened or made): the offer of the last project goes away. */
  dropOffer() {
    if (!this.bar?.isConnected) return;
    if (!this.hooks.partCount?.()) return; // (counted, not serialized: the project file is not built mid-load)
    this.bar.remove();
  }

  /** The app started empty: the last project is offered (Open / Recent… / ✕) in a strip under the top bar (in the
   *  page's flow, so it covers no button; it goes when a part is opened or made). */
  async offerLast() {
    let list;
    try { list = await this.recent(); } catch { return; }
    const last = list[0];
    if (!last || this.hooks.project()?.parts?.length) return;
    const bar = document.createElement('div');
    bar.className = 'restore-bar';
    bar.innerHTML = `<span>Continue where you left off:</span> <b data-no-i18n>${esc(last.name)}</b> <i data-no-i18n>${esc(when(last.time))}</i> <i>${last.parts.length} part(s)</i>
      <button class="btn small primary" data-a="open">Open</button><button class="btn small" data-a="recent">🕘 Recent projects…</button><button class="mini" data-a="x" title="Close">✕</button>`;
    bar.querySelector('[data-a=open]').addEventListener('click', async () => { bar.remove(); try { await this.open(last.id); this.hooks.toast(tv('“{name}” is open again.', { name: last.name }), 'ok'); } catch (e) { this.hooks.toast(e.message, 'error'); } });
    bar.querySelector('[data-a=recent]').addEventListener('click', () => { bar.remove(); this.showRecent(); });
    bar.querySelector('[data-a=x]').addEventListener('click', () => bar.remove());
    const top = document.querySelector('body > .topbar');
    if (top) top.after(bar); else document.body.prepend(bar);
    this.bar = bar;
  }

  async showRecent() {
    this.bar?.remove();
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose aih" role="dialog" aria-modal="true"><h3>🕘 Recent projects</h3>
      <p class="hint">Every project is kept on the server a few seconds after each change (data/projects/). Open one to go on with it.</p>
      <div class="aih-list"><p class="hint">Loading…</p></div>
      <div class="row-actions"><button class="btn small" data-clean title="Delete every empty project that still has the name the app gave it (no steps, no parts, no shapes) — the one on screen stays">🧹 Clean up empty projects</button></div>
      <button class="mini choose-x" title="Close">✕</button></div>`;
    const close = () => { document.removeEventListener('keydown', onKey, true); back.remove(); };
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onKey, true);
    back.querySelector('.choose-x').addEventListener('click', close);
    back.addEventListener('pointerdown', (e) => { if (e.target === back) close(); });
    document.body.appendChild(back);
    const render = async () => {
      const box = back.querySelector('.aih-list'), list = await this.recent().catch(() => []);
      if (!list.length) { box.innerHTML = '<p class="hint">Nothing kept yet.</p>'; return; }
      box.innerHTML = list.map((p) => `<div class="aih-row" data-id="${esc(p.id)}"><div class="aih-text">
          <span class="aih-when"><span data-no-i18n>${esc(when(p.time))}</span>${p.id === this.id ? ' · <b>on screen</b>' : ''}</span>
          <span class="aih-prompt" data-no-i18n>${esc(p.name)}</span><span class="aih-parts" data-no-i18n>${esc(p.parts.map((x) => x.name).join(', '))}</span></div>
        <span class="aih-acts"><button class="btn small primary" data-open ${p.id === this.id ? 'disabled' : ''}>Open</button>
          <button class="mini danger" data-del title="Forget it (the file on the server is deleted)">✕</button></span></div>`).join('');
      for (const row of box.querySelectorAll('.aih-row')) {
        const p = list.find((x) => x.id === row.dataset.id);
        row.querySelector('[data-open]').addEventListener('click', async () => {
          close();
          try { await this.open(p.id); this.hooks.toast(tv('“{name}” is open again.', { name: p.name }), 'ok'); } catch (e) { this.hooks.toast(e.message, 'error'); }
        });
        row.querySelector('[data-del]').addEventListener('click', async () => {
          if (!confirm(tv('Forget “{name}”? Its file on the server is deleted.', { name: p.name }))) return;
          await fetch(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'DELETE' });
          render();
        });
      }
    };
    back.querySelector('[data-clean]').addEventListener('click', async () => {
      const ask = async (dry) => (await (await fetch('/api/projects-cleanup', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keep: this.id, dry_run: dry }) })).json()).projects || [];
      const found = await ask(true);
      if (!found.length) { this.hooks.toast(t('Nothing to clean up — every kept project has something in it or a name of yours.'), 'info', 5000); return; }
      const names = found.slice(0, 8).map((p) => `${p.name} (${when(p.time)})`).join('\n');
      if (!confirm(`${tv('Delete {n} empty project(s) with default names?', { n: found.length })}\n\n${names}${found.length > 8 ? '\n…' : ''}`)) return;
      const gone = await ask(false);
      this.hooks.toast(tv('{n} empty project(s) deleted.', { n: gone.length }), 'ok', 4000);
      render();
    });
    render();
  }
}
