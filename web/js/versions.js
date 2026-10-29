// 🕘 Versions: the project's states kept on the server (auto3d/versions.py) — a small widget in the left column of the
// 3D model and the assembly, folded at first. Automatic versions come with the autosave (at most one every few
// minutes, a part added or removed at once) and with Save project; 💾 Save version… names one (one field). The
// timeline (the newest first): a thumbnail of the view, when, the description or "automatic", the parts changed. A
// click previews a version read-only (a banner: ↩ Back to current / ⤺ Restore this version — restoring keeps the
// state before as a version first, so it can be undone); ⇄ compares it with the project now (steps added, removed,
// values "Extrude 1: 10 → 15 mm", the volume); ⑂ makes a variant (a branch, with its own timeline) from it. The
// variant switcher on top; "Take a part from a variant…" copies one part of another variant's newest version here.
import { t, getLang } from './i18n.js';
import { leftDock } from './leftdock.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
const when = (s) => new Date(s * 1000).toLocaleString(getLang() === 'cs' ? 'cs-CZ' : undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const fmt = (v) => (v === null || v === undefined ? '—' : typeof v === 'number' ? (+v.toFixed(3)).toString() : String(v));
const GAP = 180; // s: the server's AUTO_GAP — no thumbnail made for an automatic version it would not keep
const VID = /^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}(-[0-9]+)?$/; // a version's id (as auto3d/versions.py makes them)
const WS = ['model', 'assembly'];

async function call(url, body) {
  const res = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const r = await res.json().catch(() => ({ error: res.statusText }));
  if (!res.ok || r.error) throw new Error(t(r.error || res.statusText));
  return r;
}

export class Versions {
  /** hooks: {id() -> the project's id (autosave), project() -> the project file or null, load(project, {preview})
   *  (opens it), thumb() -> a small JPEG data URL of the view or null, volumes() -> {part id: mm³}, autosave, toast} */
  constructor(hooks) {
    this.hooks = hooks;
    this.data = null;      // the server's list: {current, variant, variants, versions, base}
    this.pid = null;
    this.preview = null;   // {vid, m, saved: the project on screen before, volumes, thumb}
    this.lastAuto = 0;
    this.lastParts = '';
    this.open = null;      // the version whose comparison is shown
    this.diffs = {};
    this.ask = null;       // {kind: 'save' | 'variant', vid}: the one field shown
    this.boxes = WS.map((ws) => {
      const w = `versions-${ws}`, box = leftDock.addWidget(w, ws, { title: '🕘 Versions', h: 220, folded: true });
      box.classList.add('vr-box');
      leftDock.show(w, true);
      return box;
    });
    window.addEventListener('a3d:lang', () => this.render());
    this.guard();
  }

  url(path = '') { return `/api/versions/${encodeURIComponent(this.hooks.id())}${path}`; }

  /** The project on screen changed (opened, a new one): its versions. */
  changed() { this.pid = null; this.data = null; this.lastAuto = 0; this.lastParts = ''; this.open = null; this.diffs = {}; this.refresh(); }

  async refresh() {
    const id = this.hooks.id();
    if (!id) return null;
    try {
      this.data = await call(this.url());
      this.open = null; // (a comparison with the project as it was: gone)
      this.pid = id;
      const head = this.data.versions[0];
      if (head) this.lastAuto = Math.max(this.lastAuto, head.time);
    } catch (e) { this.data = null; }
    this.render();
    return this.data;
  }

  /** The project on screen as it is (while previewing: as it was before the preview). */
  now() {
    if (this.preview) return { project: this.preview.saved, volumes: this.preview.volumes, thumb: this.preview.thumb };
    let thumb = null;
    try { thumb = this.hooks.thumb(); } catch { thumb = null; }
    return { project: this.hooks.project(), volumes: this.hooks.volumes?.() || {}, thumb };
  }

  /** A version of the project now -> its manifest (same: true when not kept). */
  async save(label = '', { auto = false, force = false } = {}) {
    const { project, volumes, thumb } = this.now();
    if (!project?.parts?.length) return null;
    const m = await call(this.url(), { project, label, auto, force, thumb, volumes });
    if (!m.same) { this.lastAuto = m.time; this.lastParts = project.parts.map((p) => p.id).join(); }
    await this.refresh();
    return m;
  }

  /** The autosave kept the project: an automatic version, at most one every few minutes (a part added or removed:
   *  at once). Called after each autosave. */
  async auto() {
    if (this.preview || !this.hooks.id()) return;
    const proj = this.hooks.project();
    if (!proj?.parts?.length) return;
    const ids = proj.parts.map((p) => p.id).join();
    if (Date.now() / 1000 - this.lastAuto < GAP && (ids === this.lastParts || !this.lastParts)) return;
    this.lastParts = ids;
    try { await this.save('', { auto: true }); } catch { /* the next autosave tries again */ }
  }

  // ------------------------------------------------------------------------------------------ preview, restore
  async previewVersion(vid) {
    if (this.preview?.vid === vid) return;
    const r = await call(this.url(`/v/${encodeURIComponent(vid)}`));
    if (!this.preview) {
      await this.hooks.autosave?.saveNow();
      const cur = this.now();
      if (!cur.project) return;
      this.preview = { saved: structuredClone(cur.project), volumes: cur.volumes, thumb: cur.thumb };
      if (this.hooks.autosave) this.hooks.autosave.paused = true; // (the preview is not the project: not kept)
    }
    Object.assign(this.preview, { vid, m: r.version });
    document.body.classList.add('vr-preview');
    await this.hooks.load(r.project, { preview: true });
    this.banner();
    this.render();
  }

  /** ↩ Back to the project as it was before the preview. */
  async back() {
    const p = this.preview;
    if (!p) return;
    this.preview = null;
    document.body.classList.remove('vr-preview');
    this.banner();
    await this.hooks.load(p.saved, { preview: false, same: true });
    if (this.hooks.autosave) this.hooks.autosave.paused = false;
    this.render();
  }

  /** ⤺ The project back as version vid was (the one now kept first as a version) -> the new version. */
  async restore(vid) {
    const { project, volumes, thumb } = this.now();
    const r = await call(this.url(`/v/${encodeURIComponent(vid)}/restore`), { project, volumes, thumb });
    this.preview = null;
    document.body.classList.remove('vr-preview');
    this.banner();
    await this.hooks.load(r.project, { preview: false });
    if (this.hooks.autosave) { this.hooks.autosave.paused = false; await this.hooks.autosave.saveNow(); }
    await this.refresh();
    const tip = this.hooks.toast(t2('The version of {when} is back — the state before it is kept as a version.', { when: when(r.version.note?.time || r.version.time) }), 'ok', 9000);
    if (tip && r.before && !r.before.same) {
      const b = document.createElement('button');
      b.className = 'mini vr-undo';
      b.textContent = t('↶ Undo');
      b.addEventListener('click', () => { tip.remove(); this.restore(r.before.id).catch((e) => this.hooks.toast(e.message, 'error')); });
      tip.append(' ', b);
    }
    return r;
  }

  /** While previewing: nothing on the page changes the project (the view still turns; the banner, this widget and
   *  the language switch work). */
  guard() {
    const free = (el) => !!el?.closest?.('.vr-banner, .vr-box, .lw-widget[data-w^=versions] > .lw-head, #langBtn, .toast');
    const stop = (e) => {
      if (!this.preview || free(e.target)) return;
      if (e.type === 'pointerdown' && e.target.tagName === 'CANVAS' && !(e.button === 0 && e.target.closest('#asmViewport'))) return; // (turning the view; an assembly's left button would drag a part)
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    for (const ev of ['pointerdown', 'click', 'dblclick', 'contextmenu', 'drop']) document.addEventListener(ev, stop, true);
    document.addEventListener('keydown', (e) => {
      if (!this.preview || free(e.target)) return;
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); this.back(); return; }
      if (/^(Arrow|Page|Home|End)/.test(e.key) && !e.ctrlKey) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    }, true);
  }

  banner() {
    let b = document.querySelector('.vr-banner');
    if (!this.preview) { b?.remove(); return; }
    if (!b) {
      b = document.createElement('div');
      b.className = 'vr-banner';
      b.setAttribute('role', 'status');
      (document.querySelector('main.layout') || document.body).appendChild(b);
    }
    const m = this.preview.m;
    b.innerHTML = `<span>🕘 ${esc(t2('Viewing the version of {when}', { when: when(m.time) }))}${m.label ? ` — <b data-no-i18n>${esc(m.label)}</b>` : ''} · ${esc(t('read only'))}</span>
      <button class="btn small" data-vb="back">↩ ${esc(t('Back to current'))}</button><button class="btn small primary" data-vb="restore">⤺ ${esc(t('Restore this version'))}</button>`;
    b.querySelector('[data-vb=back]').addEventListener('click', () => this.back().catch((e) => this.hooks.toast(e.message, 'error')));
    b.querySelector('[data-vb=restore]').addEventListener('click', () => this.restore(this.preview.vid).catch((e) => this.hooks.toast(e.message, 'error')));
  }

  // ------------------------------------------------------------------------------------------ compare
  async compare(a, b = 'current') {
    const cur = b === 'current' || a === 'current' ? this.now() : {};
    return call(this.url('/diff'), { a, b, project: cur.project, volumes: cur.volumes });
  }

  /** A comparison in words: [lines] ("Extrude 1: 10 → 15 mm", "Volume: 8000 → 12000 mm³"). */
  diffLines(d) {
    const out = [];
    for (const p of d.parts) {
      const head = p.status === 'added' ? `＋ ${t2('New part: {name}', { name: p.name })}` : p.status === 'removed' ? `✕ ${t2('Part removed: {name}', { name: p.name })}` : p.name;
      out.push({ cls: 'part', text: head });
      if (p.renamed) out.push({ text: `${t('Renamed')}: ${p.renamed[0]} → ${p.renamed[1]}` });
      for (const s of p.steps || []) {
        if (s.status === 'added') out.push({ cls: 'add', text: `＋ ${s.step}` });
        else if (s.status === 'removed') out.push({ cls: 'del', text: `− ${s.step}` });
        else {
          const vals = s.values || [];
          if (!vals.length) out.push({ text: `${s.step}: ${t('changed')}` });
          for (const v of vals) {
            const key = vals.length > 1 && v.key !== 'name' ? ` (${v.key})` : '';
            if (v.key === 'name') out.push({ text: `${t('Renamed')}: ${v.before} → ${v.after}` });
            else if (v.changed) out.push({ text: `${s.step}${key}: ${t('changed')}` });
            else out.push({ text: `${s.step}${key}: ${fmt(v.before)} → ${fmt(v.after)}${v.unit ? ` ${v.unit}` : ''}` });
          }
        }
      }
      const [va, vb] = p.volume || [];
      if (va != null || vb != null) out.push({ cls: 'vol', text: `${t('Volume')}: ${fmt(va == null ? null : +va.toFixed(1))} → ${fmt(vb == null ? null : +vb.toFixed(1))} mm³` });
    }
    for (const x of d.project || []) {
      if (x.what === 'parameter') out.push({ text: `𝑥 ${x.name}: ${fmt(x.before)} → ${fmt(x.after)}` });
      else if (x.what === 'name') out.push({ text: `${t('Project name')}: ${x.before} → ${x.after}` });
      else if (x.what === 'order') out.push({ text: t('The parts are in another order.') });
    }
    if (!out.length) out.push({ text: t('No difference.') });
    return out;
  }

  // ------------------------------------------------------------------------------------------ variants
  async createVariant(from, name) {
    if (this.preview) await this.back();
    await this.save('', { auto: true, force: true }); // (the project now kept in its variant first)
    const r = await call(this.url('/variants'), { from, name });
    await this.hooks.load(r.project, { preview: false });
    await this.hooks.autosave?.saveNow();
    await this.refresh();
    this.hooks.toast(t2('Variant “{name}” made — its own versions from here on.', { name }), 'ok', 6000);
    return r;
  }

  async switchVariant(id) {
    if (this.preview) await this.back();
    await this.save('', { auto: true, force: true });
    const r = await call(this.url(`/variants/${encodeURIComponent(id)}/switch`), {});
    if (r.project) await this.hooks.load(r.project, { preview: false });
    await this.hooks.autosave?.saveNow();
    await this.refresh();
    return r;
  }

  /** One part as it is in another variant's newest version, put into the project here (kept as a named version). */
  async takePart(variant, part) {
    if (this.preview) await this.back();
    const r = await call(this.url('/take-part'), { variant, part });
    const proj = this.hooks.project(), i = proj.parts.findIndex((p) => p.id === part);
    if (i >= 0) proj.parts[i] = r.part; else proj.parts.push(r.part);
    await this.hooks.load(proj, { preview: false });
    await this.hooks.autosave?.saveNow();
    const v = this.data?.variants.find((x) => x.id === variant);
    await this.save(t2('“{part}” taken from variant “{variant}”', { part: r.part.name, variant: this.varName(v) }));
    return r;
  }

  varName(v) { return v?.name || t('main'); }

  /** The parts of the other variants' newest versions: [{variant, name, part, partName}]. */
  async otherParts() {
    const out = [];
    for (const v of this.data?.variants || []) {
      if (v.id === this.data.current || !v.head) continue;
      const r = await call(`${this.url()}?variant=${encodeURIComponent(v.id)}`);
      const head = r.versions.find((m) => m.id === v.head) || r.base;
      for (const [pid, name] of Object.entries(head?.names || {})) out.push({ variant: v.id, vname: this.varName(v), part: pid, name });
    }
    return out;
  }

  // ------------------------------------------------------------------------------------------ the widget
  label(m) {
    if (m.label) return { text: m.label, own: true };
    if (m.note?.what === 'before-restore') return { text: t('Before restoring') };
    if (m.note?.what === 'restored') return { text: t2('Restored: {what}', { what: m.note.label || when(m.note.time) }) };
    return { text: t('automatic'), auto: true };
  }

  row(m, { base = false } = {}) {
    const l = this.label(m), on = this.preview?.vid === m.id;
    const cur = !base && m.id === this.data?.versions?.[0]?.id; // (the newest of this variant: what the project is now)
    const tag = on ? `<span class="vr-tag look">👁 ${esc(t('viewing'))}</span>` : cur ? `<span class="vr-tag cur">● ${esc(t('current'))}</span>` : '';
    const parts = m.changed?.length ? t2('Changed: {parts}', { parts: m.changed.join(', ') }) : '';
    const thumb = m.thumb ? `<img class="vr-thumb" alt="" loading="lazy" src="${esc(this.url(`/v/${m.id}/thumb`))}">` : '<span class="vr-thumb none">🕘</span>';
    return `<div class="vr-row${on ? ' on' : ''}${cur ? ' cur' : ''}${base ? ' base' : ''}" data-v="${esc(m.id)}" tabindex="0" title="${esc(cur ? t('The current version: the project is as this one (with the changes since)') : t('Click: look at it (read only)'))}">${thumb}
      <div class="vr-text"><span class="vr-when">${base ? '⑂ ' : ''}${esc(when(m.time))}${tag}</span>
        <span class="vr-label${l.auto ? ' auto' : ''}"${l.own ? ' data-no-i18n' : ''}>${esc(l.text)}</span>
        ${parts ? `<span class="vr-parts" data-no-i18n>${esc(parts)}</span>` : ''}</div>
      <span class="vr-acts"><button class="mini" data-cmp title="${esc(t('Compare with current'))}">⇄</button><button class="mini" data-var title="${esc(t('Create a variant from this version'))}">⑂</button></span></div>
      ${this.open === m.id && this.diffs[m.id] ? `<div class="vr-diff" data-no-i18n>${this.diffLines(this.diffs[m.id]).map((x) => `<div class="${x.cls || ''}">${esc(x.text)}</div>`).join('')}</div>` : ''}
      ${this.ask?.kind === 'variant' && this.ask.vid === m.id ? `<input class="vr-ask" data-ask="variant" placeholder="${esc(t('Name of the variant — Enter'))}" maxlength="60">` : ''}`;
  }

  render() {
    const d = this.data;
    const vars = d?.variants || [{ id: 'main', name: '' }];
    const list = d?.versions || [];
    const html = `<div class="vr-top"><label class="vr-varl">${esc(t('Variant:'))} <select class="vr-var" title="${esc(t('Variants of the project — each with its own versions'))}">${vars.map((v) =>
      `<option value="${esc(v.id)}"${v.id === d?.current ? ' selected' : ''}>${esc(this.varName(v))}</option>`).join('')}</select></label>
      <button class="mini vr-save" title="${esc(t('Keep the project as it is now as a named version'))}">💾 ${esc(t('Save version…'))}</button></div>
      ${this.ask?.kind === 'save' ? `<input class="vr-ask" data-ask="save" placeholder="${esc(t('A short description — Enter'))}" maxlength="120">` : ''}
      <div class="vr-list">${list.map((m) => this.row(m)).join('') || `<p class="hint">${esc(t('No versions yet — they come by themselves as you work, or 💾 Save version…'))}</p>`}
      ${d?.base ? this.row(d.base, { base: true }) : ''}</div>
      ${vars.length > 1 ? `<select class="vr-take" title="${esc(t('Copy one part as it is in another variant into this one'))}"><option value="">${esc(t('Take a part from a variant…'))}</option></select>` : ''}`;
    for (const box of this.boxes) {
      if (box.contains(document.activeElement) && document.activeElement.matches('.vr-ask')) continue; // (being typed in)
      const top = box.scrollTop; // (drawn again where it was scrolled to)
      box.innerHTML = html;
      box.scrollTop = top;
      this.wire(box);
    }
  }

  wire(box) {
    const err = (e) => this.hooks.toast(e.message, 'error', 7000);
    box.querySelector('.vr-var').addEventListener('change', (e) => this.switchVariant(e.target.value).catch(err));
    box.querySelector('.vr-save').addEventListener('click', () => { this.ask = this.ask?.kind === 'save' ? null : { kind: 'save' }; this.render(); this.focusAsk(box); });
    for (const row of box.querySelectorAll('.vr-row')) {
      const vid = row.dataset.v;
      row.addEventListener('click', (e) => { if (!e.target.closest('button')) this.previewVersion(vid).catch(err); });
      row.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target === row) this.previewVersion(vid).catch(err); });
      row.querySelector('[data-cmp]').addEventListener('click', async () => {
        if (this.open === vid) { this.open = null; this.render(); return; }
        try { this.diffs[vid] = await this.compare(vid, 'current'); this.open = vid; this.render(); } catch (e) { err(e); }
      });
      row.querySelector('[data-var]').addEventListener('click', () => { this.ask = this.ask?.vid === vid ? null : { kind: 'variant', vid }; this.render(); this.focusAsk(box); });
    }
    const ask = box.querySelector('.vr-ask');
    ask?.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Escape') { this.ask = null; this.render(); return; }
      if (e.key !== 'Enter') return;
      const text = ask.value.trim(), a = this.ask;
      if (a.kind === 'variant' && !text) return;
      this.ask = null;
      ask.blur();
      if (a.kind === 'save') this.save(text || t('Saved by hand')).then((m) => m && this.hooks.toast(t2('Version “{label}” saved.', { label: m.label }), 'ok')).catch(err);
      else this.createVariant(a.vid, text).catch(err);
    });
    const take = box.querySelector('.vr-take');
    if (take) {
      take.addEventListener('focus', async () => {
        if (take.options.length > 1) return;
        try {
          for (const o of await this.otherParts()) take.insertAdjacentHTML('beforeend', `<option value="${esc(`${o.variant}|${o.part}`)}" data-no-i18n>${esc(`${o.vname} · ${o.name}`)}</option>`);
        } catch (e) { err(e); }
      });
      take.addEventListener('change', () => {
        const [variant, part] = take.value.split('|');
        if (part) this.takePart(variant, part).then((r) => this.hooks.toast(t2('“{part}” taken from the other variant.', { part: r.part.name }), 'ok')).catch(err);
      });
    }
  }

  focusAsk(box) { setTimeout(() => box.querySelector('.vr-ask')?.focus(), 0); }

  // ------------------------------------------------------------------------------------------ the AI's tools
  handlers() {
    const brief = (m) => ({ id: m.id, time: new Date(m.time * 1000).toISOString(), label: this.label(m).text, auto: !!m.auto, changed: m.changed || [], ...(m.note ? { note: m.note.what } : {}) });
    const need = async () => { if (!this.data || this.pid !== this.hooks.id()) await this.refresh(); if (!this.data) throw new Error('No versions here yet — save_version keeps one.'); };
    const variantOf = (which) => { // its id or name (list_versions variants)
      const w = String(which ?? '').trim().toLowerCase(), vs = this.data.variants;
      const v = vs.find((x) => x.id === which || this.varName(x).toLowerCase() === w) || vs.find((x) => w && this.varName(x).toLowerCase().includes(w));
      if (!v) throw new Error(`No variant “${which ?? ''}” — the variants: ${vs.map((x) => `${x.id} “${this.varName(x)}”`).join(', ')}.`);
      return v;
    };
    return {
      list_versions: async () => {
        await need();
        const d = this.data;
        return { text: JSON.stringify({ variant: { id: d.current, name: this.varName(d.variants.find((v) => v.id === d.current)) },
          variants: d.variants.map((v) => ({ id: v.id, name: this.varName(v), head: v.head })), versions: d.versions.map(brief), ...(d.base ? { made_from: brief(d.base) } : {}),
          previewing: this.preview?.vid || null }) };
      },
      save_version: async ({ label } = {}) => {
        const m = await this.save(String(label || '').trim() || 'Saved by the AI');
        return { text: JSON.stringify(m.same ? { same: true, note: 'Nothing changed since the last version.', version: brief(m) } : { saved: brief(m) }) };
      },
      restore_version: async ({ id } = {}) => {
        if (!VID.test(String(id ?? ''))) throw new Error('id: a version id from list_versions (e.g. 20261029-152453-b9f9ef).');
        const r = await this.restore(id);
        return { text: JSON.stringify({ restored: id, version: brief(r.version), before: r.before ? brief(r.before) : null, undo: r.before ? `restore_version {id: "${r.before.id}"}` : null }) };
      },
      compare_versions: async ({ a, b = 'current' } = {}) => {
        if (![a, b || 'current'].every((x) => x === 'current' || VID.test(String(x ?? '')))) throw new Error('a, b: version ids from list_versions, or "current" (the project now: the default of b).');
        const d = await this.compare(a, b || 'current');
        return { text: JSON.stringify({ ...d, summary: this.diffLines(d).map((x) => x.text) }) };
      },
      create_variant: async ({ from, name } = {}) => {
        if (!name) throw new Error('name: the new variant\'s name.');
        await need();
        const src = from || this.data.versions[0]?.id || this.data.base?.id;
        if (!src) throw new Error('No version to start the variant from — save_version first.');
        const r = await this.createVariant(src, String(name));
        return { text: JSON.stringify({ variant: { id: r.variant.id, name: r.variant.name }, from: src }) };
      },
      switch_variant: async ({ variant } = {}) => {
        await need();
        const v = variantOf(variant);
        if (v.id === this.data.current) return { text: `“${this.varName(v)}” is the variant on screen already.` };
        await this.switchVariant(v.id);
        return { text: JSON.stringify({ variant: { id: v.id, name: this.varName(v) }, parts: (this.hooks.project()?.parts || []).map((p) => p.name) }) };
      },
      take_part: async ({ variant, part } = {}) => {
        await need();
        const v = variantOf(variant);
        if (v.id === this.data.current) throw new Error(`“${this.varName(v)}” is the variant on screen — take_part takes a part from another one.`);
        const there = (await this.otherParts()).filter((o) => o.variant === v.id), w = String(part ?? '').toLowerCase();
        const o = there.find((x) => x.part === part || x.name.toLowerCase() === w) || there.find((x) => w && x.name.toLowerCase().includes(w));
        if (!o) throw new Error(`No part “${part}” in variant “${this.varName(v)}” — its parts: ${there.map((x) => `${x.part} “${x.name}”`).join(', ') || 'none saved'}.`);
        const r = await this.takePart(v.id, o.part);
        return { text: `“${r.part.name}” taken from variant “${this.varName(v)}” (as it is in its newest version) into the project on screen — kept as a named version.` };
      },
    };
  }
}
