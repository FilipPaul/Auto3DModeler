// 🎬 Demo projects (Open ▾ → Demo projects…): the ready-made projects of demos/ (served read-only: /api/demos), each
// with its name and what it shows, in the app's language. A click opens one as a new project — a copy: the demo
// file itself never changes (auto3d/demos.py).
import { t, getLang } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

/** The list as a dialog. hooks: {open(project) — puts it on screen as a new project, toast}. */
export async function showDemos({ open, toast }) {
  const back = document.createElement('div');
  back.className = 'choose-back';
  back.innerHTML = `<div class="choose aih demos" role="dialog" aria-modal="true"><h3>🎬 ${esc(t('Demo projects'))}</h3>
    <p class="hint">${esc(t('Ready-made projects to try — each opens as a new copy, the demo itself stays as it is.'))}</p>
    <div class="aih-list"><p class="hint">${esc(t('Loading…'))}</p></div>
    <button class="mini choose-x" title="${esc(t('Close'))}">✕</button></div>`;
  const close = () => { document.removeEventListener('keydown', onKey, true); back.remove(); };
  const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  document.addEventListener('keydown', onKey, true);
  back.querySelector('.choose-x').addEventListener('click', close);
  back.addEventListener('pointerdown', (e) => { if (e.target === back) close(); });
  document.body.appendChild(back);
  const box = back.querySelector('.aih-list');
  let list = [];
  try { list = (await (await fetch('/api/demos')).json()).demos || []; } catch { list = []; }
  if (!list.length) { box.innerHTML = `<p class="hint">${esc(t('No demo projects found.'))}</p>`; return; }
  const cs = getLang() === 'cs';
  box.innerHTML = list.map((d) => `<div class="aih-row" data-demo="${esc(d.file)}"><div class="aih-text">
      <span class="aih-prompt" data-no-i18n><b>${esc(cs ? d.name_cs : d.name)}</b></span>
      <span class="aih-when" data-no-i18n>${esc(cs ? d.text_cs : d.text)}</span>
      <span class="aih-parts" data-no-i18n>${esc(d.parts.join(', '))}</span></div>
    <span class="aih-acts"><button class="btn small primary" data-open>${esc(t('Open'))}</button></span></div>`).join('');
  for (const row of box.querySelectorAll('[data-demo]')) {
    row.querySelector('[data-open]').addEventListener('click', async () => {
      const d = list.find((x) => x.file === row.dataset.demo);
      close();
      try {
        const res = await fetch(`/api/demos/${encodeURIComponent(d.file)}`), proj = await res.json();
        if (!res.ok || proj.error) throw new Error(proj.error || res.statusText);
        await open(proj);
        toast(tv('Demo “{name}” opened as a new project — try ⚙ Mechanism ▶.', { name: cs ? d.name_cs : d.name }), 'ok', 5000);
      } catch (e) { toast(e.message, 'error'); }
    });
  }
}
