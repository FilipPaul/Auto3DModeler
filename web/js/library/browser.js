// 📚 The parts library window: search and browse the real parts (by category), choose the size (and length), see it in
// 3D with its maker, part number and shop links — then open it as a new 3D model or put it into the assembly on screen.
import { t } from '../i18n.js';
import { ModelView } from '../modeler/view.js';
import { buildPart, sizesOf, lengthsOf, shopLinks, fill, varsOf, modelKey } from './build.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

/** The items, fetched once per open. */
export async function libraryItems() {
  const r = await (await fetch('/api/library')).json();
  return r.items || [];
}

/** How well an item matches a search (0: not at all): its name, category, maker, part numbers, sizes. */
export function matchScore(item, query) {
  const words = norm(query).split(/\s+/).filter(Boolean);
  if (!words.length) return 1;
  const sizes = sizesOf(item);
  const hay = norm([item.name, item.category, item.maker, item.standard, item.pn, item.description, item.id,
    ...sizes.map((s) => `${s.key} ${s.pn || ''}`)].join(' '));
  let score = 0;
  for (const w of words) {
    if (!hay.includes(w)) return 0;
    score += norm(item.name).includes(w) ? 3 : 1;
  }
  return score;
}

export class LibraryBrowser {
  /** hooks: {toast, canInsert() (an assembly on screen), openAsModel(name, data), insertIntoAssembly(name, data),
   *  importSolid(file) -> {blob, name} (a STEP read and stored on the server)} */
  constructor(hooks) { this.hooks = hooks; this.state = { q: '', item: null, size: null, length: null }; }

  async open(query = '') {
    this.close();
    const back = document.createElement('div');
    back.className = 'choose-back lib-back';
    back.innerHTML = `<div class="choose lib" role="dialog" aria-modal="true">
      <div class="lib-head"><h3>📚 Parts library</h3><input type="search" class="lib-q" placeholder="Search: M3, bearing 608, SMC, SICK, LED, stepper…"></div>
      <div class="lib-main"><div class="lib-list"><p class="hint">Loading…</p></div><div class="lib-detail"><p class="hint">Choose a part on the left.</p></div></div>
      <button class="mini choose-x" title="Close">✕</button></div>`;
    this.back = back;
    back.querySelector('.choose-x').addEventListener('click', () => this.close());
    back.addEventListener('pointerdown', (e) => { if (e.target === back) this.close(); });
    this.onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); this.close(); } };
    document.addEventListener('keydown', this.onKey, true);
    document.body.appendChild(back);
    const q = back.querySelector('.lib-q');
    if (query) this.state.q = query; // a search asked for, else the last one
    q.value = this.state.q;
    q.addEventListener('input', () => { this.state.q = q.value; this.renderList(); });
    q.addEventListener('keydown', (e) => e.stopPropagation());
    q.focus();
    try { this.items = await libraryItems(); } catch (e) { this.items = []; this.hooks.toast(e.message, 'error'); }
    this.renderList();
    const keep = this.items.find((i) => i.id === this.state.item);
    if (keep) this.select(keep.id, this.state.size, this.state.length);
  }

  close() {
    if (!this.back) return;
    document.removeEventListener('keydown', this.onKey, true);
    this.view?.container.remove(); // kept for the next time: one WebGL context for the window, ever (too many and
    // the browser drops the oldest — the 3D model's own view goes blank)
    this.back.remove();
    this.back = null;
  }

  renderList() {
    const box = this.back?.querySelector('.lib-list');
    if (!box) return;
    const q = this.state.q.trim();
    const found = this.items.map((it) => ({ it, s: matchScore(it, q) })).filter((x) => x.s > 0);
    if (q) found.sort((a, b) => b.s - a.s);
    if (!found.length) { box.innerHTML = `<p class="hint">${esc(tv('Nothing found for “{q}”.', { q }))}</p>`; return; }
    const groups = new Map();
    for (const { it } of found) {
      const g = q ? t('Found') : it.category.split(' / ')[0];
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(it);
    }
    box.innerHTML = [...groups].map(([g, list]) => `<div class="lib-group"><div class="lib-gname">${esc(g)} <span>${list.length}</span></div>
      ${list.map((it) => `<button class="lib-item${it.id === this.state.item ? ' on' : ''}" data-item="${esc(it.id)}">
        <span class="lib-iname" data-no-i18n>${esc(it.name)}</span><span class="lib-isub" data-no-i18n>${esc([it.maker, it.standard, it.category.split(' / ').slice(1).join(' / ')].filter(Boolean).join(' · '))}${it.source === 'user' ? ' · ★' : ''}</span></button>`).join('')}</div>`).join('');
    for (const b of box.querySelectorAll('[data-item]')) b.addEventListener('click', () => this.select(b.dataset.item));
  }

  select(id, size = null, length = null) {
    const it = this.items.find((x) => x.id === id);
    if (!it) return;
    const sizes = sizesOf(it);
    this.state.item = id;
    this.state.size = sizes.some((s) => s.key === size) ? size : sizes[0]?.key;
    const ls = lengthsOf(it, this.state.size);
    this.state.length = ls ? (ls.values.includes(length) ? length : ls.values[Math.min(ls.values.length - 1, Math.floor(ls.values.length / 3))]) : null;
    for (const b of this.back.querySelectorAll('.lib-item')) b.classList.toggle('on', b.dataset.item === id);
    this.renderDetail();
  }

  current() {
    const it = this.items.find((x) => x.id === this.state.item);
    return it ? { it, built: buildPart(it, this.state.size, this.state.length ?? undefined) } : null;
  }

  renderDetail() {
    const box = this.back.querySelector('.lib-detail'), cur = this.current();
    if (!cur) return;
    const { it, built } = cur, lib = built.data.library, sizes = sizesOf(it), ls = lengthsOf(it, this.state.size);
    const order = Object.entries(lib.order || {}).filter(([, v]) => v);
    const asm = this.hooks.canInsert();
    box.innerHTML = `<h2 data-no-i18n>${esc(built.name)}</h2>
      ${lib.approx ? `<p class="lib-approx" title="${esc(t('Drawn as its outline from the catalogue sizes — check the maker\'s drawing before you rely on it.'))}">≈ ${esc(t('outline'))}</p>` : ''}
      <div class="lib-choose">${sizes.length > 1 || sizes[0]?.key ? `<label>${esc(t('Size'))} <select data-k="size">${sizes.map((s) => `<option value="${esc(s.key)}" ${s.key === this.state.size ? 'selected' : ''}>${esc(s.key)}</option>`).join('')}</select></label>` : ''}
        ${ls ? `<label>${esc(t(ls.name))} <select data-k="length">${ls.values.map((v) => `<option value="${v}" ${v === this.state.length ? 'selected' : ''}>${v} ${esc(ls.unit)}</option>`).join('')}</select></label>` : ''}</div>
      <div class="lib-view"></div>
      <p class="lib-desc" data-no-i18n>${esc(lib.description)}</p>
      <div class="lib-facts">${lib.maker ? `<span>${esc(t('Maker'))}</span><b data-no-i18n>${esc(lib.maker)}</b>` : ''}
        ${lib.pn ? `<span>${esc(t('Part number'))}</span><b data-no-i18n>${esc(lib.pn)}</b>` : ''}
        ${lib.standard ? `<span>${esc(t('Standard'))}</span><b data-no-i18n>${esc(lib.standard)}</b>` : ''}
        ${order.map(([k, v]) => `<span>${esc(k.toUpperCase())}</span><b data-no-i18n>${esc(v)}</b>`).join('')}</div>
      ${lib.pn ? `<div class="lib-shops">${esc(t('Find it at'))} ${shopLinks(lib.pn).map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.shop)}</a>`).join(' · ')}</div>` : ''}
      <div class="lib-real">${lib.real ? `<span class="lib-realon">✓ ${esc(t('The maker\'s model'))}: <b data-no-i18n>${esc(lib.real)}</b></span>
          <button class="btn small" data-a="unreal" title="${esc(t('Use the drawn model again for this size'))}">✕</button>`
        : `<label class="btn small" title="${esc(t('Download the maker\'s 3D model (STEP) for this part number, then choose it here — the library uses it (its own colours) for this size from now on'))}">📎 ${esc(t('Use the maker\'s model (STEP)…'))}<input type="file" data-a="real" accept=".step,.stp,.STEP,.STP" hidden></label>`}</div>
      <div class="row-actions wrap lib-acts">
        <button class="btn primary" data-a="insert" ${asm ? '' : `disabled title="${esc(t('Open an assembly first (＋ New assembly)'))}"`}>⤵ Put into the assembly</button>
        <button class="btn" data-a="model">◆ Open as a new 3D model</button>
        ${it.source === 'user' ? '<button class="btn small danger" data-a="del" title="Delete your own part from the library">✕</button>' : ''}</div>`;
    for (const sel of box.querySelectorAll('select[data-k]')) sel.addEventListener('change', () => {
      if (sel.dataset.k === 'size') this.select(it.id, sel.value, this.state.length);
      else { this.state.length = +sel.value; this.renderDetail(); }
    });
    const key = modelKey(this.state.size, ls ? this.state.length : undefined);
    const setModel = async (blob, file) => {
      const res = await fetch('/api/library/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item: it.id, key, blob, file }) });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || res.statusText);
      if (Object.keys(r.models).length) it.models = r.models; else delete it.models;
      this.renderDetail();
    };
    box.querySelector('[data-a=real]')?.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const r = await this.hooks.importSolid(file);
        await setModel(r.blob, file.name);
        this.hooks.toast(tv('{file} is the model of {name} now (its own colours).', { file: file.name, name: built.name }), 'ok', 6000);
      } catch (err) { this.hooks.toast(err.message, 'error', 8000); }
    });
    box.querySelector('[data-a=unreal]')?.addEventListener('click', () => setModel(null, '').catch((err) => this.hooks.toast(err.message, 'error')));
    box.querySelector('[data-a=insert]').addEventListener('click', async () => { const c = this.current(); this.close(); await this.hooks.insertIntoAssembly(c.built.name, c.built.data); });
    box.querySelector('[data-a=model]').addEventListener('click', async () => { const c = this.current(); this.close(); await this.hooks.openAsModel(c.built.name, c.built.data); });
    box.querySelector('[data-a=del]')?.addEventListener('click', async () => {
      if (!confirm(tv('Delete “{name}” from your library?', { name: it.name }))) return;
      await fetch(`/api/library/${encodeURIComponent(it.id)}`, { method: 'DELETE' });
      this.items = await libraryItems();
      this.state.item = null;
      this.renderList();
      box.innerHTML = '';
    });
    this.preview(built.data);
  }

  /** The chosen part in 3D (built by the kernel). */
  async preview(data) {
    const holder = this.back?.querySelector('.lib-view');
    if (!holder) return;
    if (!this.view) { // made once, then moved into each window
      const c = document.createElement('div');
      c.className = 'lib-canvas';
      holder.appendChild(c);
      this.view = new ModelView(c);
    } else if (!holder.contains(this.view.container)) holder.appendChild(this.view.container);
    const run = (this.run = (this.run || 0) + 1);
    holder.classList.add('busy');
    try {
      const res = await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features: data.features } }) });
      const r = await res.json();
      if (run !== this.run || !this.view) return;
      if (!res.ok || !r.body) throw new Error(r.error || (r.features || []).flatMap((s) => s.issues || []).join(' ') || 'No solid.');
      this.view.setBody(r.body);
      this.view.setLook({ color: data.color, paint: data.paint });
      this.view.showDatums?.(false); // the part alone, without the base planes
      this.view.setView('iso');
      this.lastBody = r.body;
    } catch (e) {
      holder.dataset.error = e.message;
    } finally { holder.classList.remove('busy'); }
  }
}

/** 📚 Save to the library: a small form (name, category; maker and part number if it is a bought part) -> the item
 *  kept on the server, or null (cancelled). */
export async function saveToLibrary(name, data, toast) {
  const items = await libraryItems().catch(() => []);
  const cats = [...new Set(items.map((i) => i.category))].sort();
  return new Promise((resolve) => {
    const back = document.createElement('div');
    back.className = 'choose-back';
    back.innerHTML = `<div class="choose lib-save" role="dialog" aria-modal="true"><h3>📚 Save to the library</h3>
      <p class="hint">This 3D model, as it is now, becomes a part of your library (kept on the server in data/library/) — use it again in any project.</p>
      <div class="field"><label>Name</label><input data-k="name" value="${esc(name)}"></div>
      <div class="field"><label>Category</label><input data-k="category" list="lib-cats" value="My parts"><datalist id="lib-cats">${cats.map((c) => `<option value="${esc(c)}">`).join('')}</datalist></div>
      <details><summary>A bought part? Its maker and part number</summary>
        <div class="field"><label>Maker</label><input data-k="maker" value="${esc(data.library?.maker || '')}"></div>
        <div class="field"><label>Part number</label><input data-k="pn" value="${esc(data.library?.pn || '')}"></div></details>
      <div class="row-actions"><button class="btn primary" data-a="save">Save</button><button class="btn" data-a="cancel">Cancel</button></div>
      <button class="mini choose-x" data-a="cancel" title="Cancel">✕</button></div>`;
    const done = (v) => { back.remove(); resolve(v); };
    const val = (k) => back.querySelector(`[data-k=${k}]`).value.trim();
    for (const el of back.querySelectorAll('input')) el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') back.querySelector('[data-a=save]').click(); if (e.key === 'Escape') done(null); });
    for (const b of back.querySelectorAll('[data-a=cancel]')) b.addEventListener('click', () => done(null));
    back.querySelector('[data-a=save]').addEventListener('click', async () => {
      const item = itemFromModel(val('name') || name, data, { category: val('category') || 'My parts', maker: val('maker'), pn: val('pn') });
      const res = await fetch('/api/library', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item }) });
      const r = await res.json();
      if (!res.ok) { toast(r.error || res.statusText, 'error'); return; }
      toast(tv('“{name}” is in your library now (📚 Library, {category}).', { name: r.name, category: r.category }), 'ok', 5000);
      done(r);
    });
    document.body.appendChild(back);
    back.querySelector('[data-k=name]').select();
  });
}

/** A library part's facts for a panel: maker, part number, order numbers, shop links (html). */
export function libraryFactsHtml(lib) {
  if (!lib) return '';
  const order = Object.entries(lib.order || {}).filter(([, v]) => v);
  return `<div class="lib-part"><b>📚 ${esc(t('Library part'))}</b>${lib.approx ? ` <span class="lib-approx">≈ ${esc(t('outline'))}</span>` : ''}
    <div class="lib-facts">${lib.maker ? `<span>${esc(t('Maker'))}</span><b data-no-i18n>${esc(lib.maker)}</b>` : ''}${lib.pn ? `<span>${esc(t('Part number'))}</span><b data-no-i18n>${esc(lib.pn)}</b>` : ''}
    ${order.map(([k, v]) => `<span>${esc(k.toUpperCase())}</span><b data-no-i18n>${esc(v)}</b>`).join('')}</div>
    ${lib.pn ? `<div class="lib-shops">${esc(t('Find it at'))} ${shopLinks(lib.pn).map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.shop)}</a>`).join(' · ')}</div>` : ''}</div>`;
}

/** A part (name, data) as a library item of the user's own: a fixed 3D model with its maker and part number. */
export function itemFromModel(name, data, { category = 'My parts', maker = '', pn = '' } = {}) {
  const id = `my-${norm(name).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'part'}-${Date.now().toString(36).slice(-4)}`;
  return { id, name, category, maker, pn, description: name, features: structuredClone(data.features || []), ...(data.color ? { color: data.color } : {}),
    ...(data.paint?.length ? { paint: structuredClone(data.paint) } : {}) };
}

export { fill, varsOf };
