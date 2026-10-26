// 🕘 AI history: the whole project after each AI turn, kept by the server (data/history/) — browse it, load one back.
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const when = (s) => new Date(s * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' });

export class AiHistory {
  /** hooks: {project() -> the project file (or null: nothing to keep), restore(project) (opens it), toast} */
  constructor(hooks) { this.hooks = hooks; }

  async save(prompt, tools, kind = 'ai') {
    const proj = this.hooks.project();
    if (!proj?.parts?.length) return null;
    try {
      const res = await fetch('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project: proj, prompt, tools, kind }) });
      return res.ok ? await res.json() : null;
    } catch { return null; } // the server went away: nothing kept this time
  }

  async list() { return (await (await fetch('/api/history')).json()).states || []; }

  /** Load a state back; the project on screen is kept first (as "before loading"), so nothing is lost. */
  async load(id) {
    const res = await fetch(`/api/history/${encodeURIComponent(id)}`);
    const proj = await res.json();
    if (!res.ok || proj.error) throw new Error(proj.error || res.statusText);
    await this.save(t('Before loading a state from the history'), 0, 'before-load');
    await this.hooks.restore(proj);
  }

  async open() {
    this.close();
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose aih" role="dialog" aria-modal="true">
      <h3>🕘 AI history</h3><p class="hint">The whole project after each change Claude made — kept on the server. Load one to go back to it (the project on screen is kept here too).</p>
      <div class="aih-list"><p class="hint">Loading…</p></div>
      <button class="mini choose-x" title="Close">✕</button></div>`;
    this.back = back;
    back.querySelector('.choose-x').addEventListener('click', () => this.close());
    back.addEventListener('click', (e) => { if (e.target === back) this.close(); });
    this.onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); this.close(); } };
    document.addEventListener('keydown', this.onKey, true);
    document.body.appendChild(back);
    await this.renderList();
  }

  close() {
    if (!this.back) return;
    document.removeEventListener('keydown', this.onKey, true);
    this.back.remove();
    this.back = null;
  }

  async renderList() {
    const box = this.back?.querySelector('.aih-list');
    if (!box) return;
    let states;
    try { states = await this.list(); } catch (e) { box.innerHTML = `<p class="hint">${esc(e.message)}</p>`; return; }
    if (!states.length) { box.innerHTML = '<p class="hint">Nothing yet — after Claude changes the project, it is kept here.</p>'; return; }
    box.innerHTML = states.map((s) => `<div class="aih-row" data-id="${esc(s.id)}">
      <div class="aih-text"><span class="aih-when">${esc(when(s.time))}${s.kind === 'before-load' ? ` · <i>${esc(t('before loading'))}</i>` : ''}</span>
        <span class="aih-prompt" data-no-i18n>${esc(s.kind === 'before-load' ? '' : s.prompt || '')}</span>
        <span class="aih-parts" data-no-i18n>${esc((s.parts || []).map((p) => p.name).join(', '))}${s.tools ? ` · ${esc(tv('{n} tool call(s)', { n: s.tools }))}` : ''}</span></div>
      <span class="aih-acts"><button class="btn small primary" data-load title="Open the project as it was then">Load</button>
        <button class="mini danger" data-del title="Delete this state">✕</button></span></div>`).join('');
    for (const row of box.querySelectorAll('.aih-row')) {
      const id = row.dataset.id;
      row.querySelector('[data-load]').addEventListener('click', async () => {
        try {
          await this.load(id);
          this.close();
          this.hooks.toast(tv('Loaded the project as it was at {at}.', { at: when(states.find((s) => s.id === id).time) }), 'ok', 6000);
        } catch (e) { this.hooks.toast(e.message, 'error'); }
      });
      row.querySelector('[data-del]').addEventListener('click', async () => {
        await fetch(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE' });
        await this.renderList();
      });
    }
  }
}
