import { t } from './i18n.js';

// A project holds several parts; the open ones are tabs in the top bar (like browser tabs). Every file you open
// becomes a part; click a tab to switch, double-click to rename, ✕ to close the tab (the part stays in the project:
// ☰ Parts lists them all, opens one again or deletes it). Only the active part lives
// in the app state — the others are kept as their saved payload (the same JSON a part is saved with)
// together with their undo history, so switching back restores them exactly. A part is either "classic"
// (a drawing, picture outline or imported file — the Quick part workspace) or a "model" (sketches and
// features — the 3D model workspace).

const CLOSE_TIP = 'Close this tab (the part stays in the project — ☰ Parts opens it again)';
const WIN_TIP = 'Open it in a new window (e.g. on another monitor) — the windows stay linked: a change in one is in the others';
const KIND_ICON = { model: '◆', assembly: '◇', drawing: '📐', sheet: '📄', classic: '▤' };

export class Project {
  /** hooks: {payload(kind), load(payload, {switching, kind}), settle(), getHistory(kind), setHistory(h, kind),
   *  newModel(), toast(msg, kind)} */
  constructor(el, hooks) {
    this.el = el;
    this.hooks = hooks;
    this.parts = []; // {id, name, kind: 'classic' | 'model' | 'assembly' | 'drawing', data, history, closed (no tab)}
    this.active = null;
    this.next = 1;
    this.busy = false;
    document.addEventListener('click', () => { for (const m of this.el.querySelectorAll('.part-add, .part-all')) m.classList.remove('open'); });
  }

  get current() { return this.parts.find((p) => p.id === this.active) || null; }

  /** A file is being opened: the part on screen (if any) is kept as its own tab and a new tab is made. */
  beginOpen() {
    const cur = this.current;
    if (cur && cur.data === null) return; // reserved already (several loads for one open)
    if (cur) this.stash();
    const p = { id: `P${this.next++}`, name: null, kind: 'classic', data: null, history: null };
    this.parts.push(p);
    this.active = p.id;
  }

  /** A new, empty 3D model part (its own tab). */
  /** A new assembly (its own tab): 3D model parts of the project placed together. */
  async newAssembly(name = null) {
    if (this.busy) return;
    await this.hooks.settle();
    if (this.current) this.stash();
    const n = 1 + this.parts.filter((q) => q.kind === 'assembly').length;
    const p = { id: `P${this.next++}`, name: name || `${t('Assembly')} ${n}`, kind: 'assembly', data: { instances: [] }, history: null };
    this.parts.push(p);
    this.active = p.id;
    this.render();
    await this.show(p);
    this.render();
  }

  /** A 2D drawing (a DXF / DWG as it is) as a new part, on screen. */
  async newDrawing(data, name) {
    if (this.busy) return;
    await this.hooks.settle();
    if (this.current) this.stash();
    const p = { id: `P${this.next++}`, name: name || t('Drawing'), kind: 'drawing', data, history: null };
    this.parts.push(p);
    this.active = p.id;
    this.render();
    await this.show(p);
    this.render();
  }

  /** The drawing sheet of a part (📄, its own tab): the one there is, or a new one. */
  async newSheet(source, name) {
    if (this.busy) return;
    const have = this.parts.find((q) => q.kind === 'sheet' && (q.data === 'live' ? null : q.data?.source) === source);
    if (have) { await this.switchTo(have.id); return; }
    await this.hooks.settle();
    if (this.current) this.stash();
    const now = new Date().toISOString();
    const p = { id: `P${this.next++}`, name: name || t('Drawing'), kind: 'sheet', data: { source, preset: 'medium', created: now, changed: now, rev: 1 }, history: null };
    this.parts.push(p);
    this.active = p.id;
    this.render();
    await this.show(p);
    this.render();
  }

  /** A new 3D model part (its own tab) — empty, or with first steps (data) and a command to open (then). */
  /** A 3D model part added to the project without opening it (a standard part for an assembly; no tab). -> its id */
  addBackground(name, data) {
    const p = { id: `P${this.next++}`, name, kind: 'model', data, history: null, closed: true };
    this.parts.push(p);
    this.render();
    return p.id;
  }

  async newModel(data = null, name = null, then = null) {
    if (this.busy) return;
    await this.hooks.settle();
    if (this.current) this.stash();
    const n = 1 + this.parts.filter((q) => q.kind === 'model').length;
    const p = { id: `P${this.next++}`, name: name || `${t('3D model')} ${n}`, kind: 'model', data: data || { features: [] }, history: null };
    this.parts.push(p);
    this.active = p.id;
    this.render();
    await this.show(p, { then });
    this.render();
  }

  /** The new part is on screen: give it its name (from the file) unless the user named it. */
  endOpen(name) {
    const cur = this.current;
    if (cur) {
      cur.data = cur.data ?? 'live';
      if (!cur.name) cur.name = name || cur.id;
    }
    this.render();
  }

  /** An open failed: drop the empty tab and go back to the part that was on screen. */
  async cancelOpen() {
    const cur = this.current;
    if (!cur || cur.data !== null) return;
    this.parts = this.parts.filter((p) => p !== cur);
    const back = this.parts[this.parts.length - 1];
    this.active = back?.id || null;
    if (back) await this.show(back);
    this.render();
  }

  stash() {
    const cur = this.current;
    if (!cur) return;
    cur.data = this.hooks.payload(cur.kind);
    cur.history = this.hooks.getHistory(cur.kind);
  }

  /** The last tab closed: nothing on screen (the part stays live underneath, so nothing is lost); a part opened again
   *  shows it. */
  setNone(on) {
    this.none = on;
    this.hooks.showNone?.(on);
  }

  async show(p, extra = {}) {
    if (this.none) this.setNone(false);
    await this.hooks.load(p.data, { switching: true, kind: p.kind, ...extra });
    if (p.history) this.hooks.setHistory(p.history, p.kind);
    p.data = 'live';
  }

  /** A copy of a part as a new, independent part (its own tab, after it) -> its id. open: put it on screen. */
  async duplicate(id = this.active, open = true) {
    const src = this.parts.find((p) => p.id === id);
    if (!src || this.busy) return null;
    const live = src.id === this.active;
    if (live) this.stash();
    const data = structuredClone(src.data);
    if (live) src.data = 'live';
    const base = `${src.name} (${t('copy')})`;
    let name = base;
    for (let n = 2; this.parts.some((p) => p.name === name); n++) name = `${base.slice(0, -1)} ${n})`;
    const p = { id: `P${this.next++}`, name, kind: src.kind, data, history: null, closed: !open || undefined };
    this.parts.splice(this.parts.indexOf(src) + 1, 0, p);
    if (open) await this.switchTo(p.id);
    else this.render();
    return p.id;
  }

  async switchTo(id) {
    const p = this.parts.find((q) => q.id === id);
    if (p?.closed) { delete p.closed; this.render(); } // opened again: its tab comes back
    if (id === this.active && this.none) { this.setNone(false); this.render(); return; }
    if (id === this.active || this.busy) return;
    if (!p) return;
    this.busy = true;
    try {
      await this.hooks.settle();
      this.stash();
      this.active = id;
      this.render();
      await this.show(p);
    } finally {
      this.busy = false;
      this.render();
    }
  }

  get openParts() { return this.parts.filter((p) => !p.closed); }

  /** ✕ on a tab: the tab goes, the part stays in the project (☰ Parts opens it again). */
  async close(id) {
    const open = this.openParts, p = open.find((q) => q.id === id);
    if (!p || this.busy) return;
    if (open.length < 2) { // the last tab: nothing on screen (☰ opens a part again)
      if (id === this.active) this.setNone(true);
      p.closed = true;
      this.render();
      return;
    }
    if (id === this.active) {
      const i = open.indexOf(p);
      await this.switchTo((open[i + 1] || open[i - 1]).id);
      if (this.active === id) return;
    }
    p.closed = true;
    this.render();
    if (!this.toldClosed) { this.toldClosed = true; this.hooks.toast(t('The tab is closed — the part stays in the project (☰ Parts opens it again).'), 'info', 5000); }
  }

  /** The assemblies that use a part -> their names. */
  usedBy(id) {
    return this.parts.filter((a) => a.kind === 'assembly' && a.id !== id).filter((a) => {
      const data = a.id === this.active ? this.hooks.payload('assembly') : a.data;
      return (data?.instances || []).some((it) => it.part === id);
    }).map((a) => a.name);
  }

  /** Delete a part from the project (☰ Parts ✕), after asking. */
  async remove(id, ask = true) {
    const p = this.parts.find((q) => q.id === id);
    if (!p || this.parts.length < 2 || this.busy) return;
    const used = this.usedBy(id);
    const msg = `${t('Delete the part “{name}” from the project?').replace('{name}', p.name)}${used.length ? `\n\n${t('It is used in: {list} — it would be missing there.').replace('{list}', used.join(', '))}` : ''}`;
    if (ask && !confirm(msg)) return;
    if (id === this.active) {
      const others = this.parts.filter((q) => q !== p), to = others.find((q) => !q.closed) || others[0];
      await this.switchTo(to.id);
      if (this.active === id) return;
    }
    this.parts = this.parts.filter((q) => q !== p);
    if (!this.openParts.length && this.parts.length) delete this.parts[0].closed;
    this.render();
  }

  /** A tab dragged onto another: the part goes before it (after it: `after`). */
  move(id, to, after = false) {
    const p = this.parts.find((q) => q.id === id), q = this.parts.find((x) => x.id === to);
    if (!p || !q || p === q) return;
    this.parts.splice(this.parts.indexOf(p), 1);
    this.parts.splice(this.parts.indexOf(q) + (after ? 1 : 0), 0, p);
    this.render();
  }

  rename(id, name) {
    const p = this.parts.find((q) => q.id === id);
    if (p && name) p.name = name;
    this.render();
  }

  /** The parts for the project file (version 3). */
  toJSON() {
    if (this.current) this.stash();
    const out = {
      active: { part: this.active },
      parts: this.parts.filter((p) => p.data && p.data !== 'live')
        .map((p) => ({ id: p.id, kind: p.kind, name: p.name, [p.kind === 'classic' ? 'classic' : p.kind]: p.data, ...(p.closed ? { closed: true } : {}) })),
    };
    if (this.current) this.current.data = 'live';
    return out;
  }

  /** Open a version-3 project: every part as a tab, the active one on screen. */
  async loadAll(proj) {
    window.dispatchEvent(new Event('a3d:project-loading'));
    this.parts = proj.parts.map((p) => ({ id: p.id, name: p.name, kind: p.kind, data: p.kind === 'classic' ? p.classic : p[p.kind], history: null, ...(p.closed ? { closed: true } : {}) }));
    this.next = 1 + Math.max(0, ...this.parts.map((p) => parseInt(String(p.id).replace(/\D/g, ''), 10) || 0));
    const act = this.parts.find((p) => p.id === proj.active?.part) || this.parts.find((p) => !p.closed) || this.parts[0];
    delete act.closed;
    this.active = act.id;
    this.render();
    await this.show(act);
    this.render();
  }

  render() {
    window.dispatchEvent(new Event('a3d:changed')); // (a part added, renamed, closed …: autosave)
    const el = this.el;
    el.hidden = !this.parts.length;
    el.innerHTML = '';
    // ☰ Parts: every part of the project (open or not) — click to open, ✕ to delete
    const all = document.createElement('div');
    all.className = 'menu part-all';
    all.innerHTML = `<button class="pt-all" title="All the parts of the project — open one, or delete it">☰ <span data-no-i18n>${this.parts.length}</span></button>
      <div class="menu-list"></div>`;
    const list = all.querySelector('.menu-list');
    for (const p of this.parts) {
      const row = document.createElement('div');
      row.className = `pt-row${p.id === this.active ? ' on' : ''}${p.closed ? ' closed' : ''}`;
      row.dataset.part = p.id;
      row.innerHTML = `<button class="pt-open" title="${p.closed ? 'Open it (a tab)' : 'Show it'}"><span class="pt-kind">${KIND_ICON[p.kind] || '▤'}</span><span class="pt-rname" data-no-i18n></span></button>${this.hooks.openWindow ? `<button class="mini pt-win" title="${WIN_TIP}">⧉</button>` : ''}${this.parts.length > 1 ? '<button class="mini danger pt-del" title="Delete it from the project">✕</button>' : ''}`;
      row.querySelector('.pt-rname').textContent = p.name || '…';
      row.querySelector('.pt-open').addEventListener('click', () => { all.classList.remove('open'); this.switchTo(p.id); });
      row.querySelector('.pt-win')?.addEventListener('click', (e) => { e.stopPropagation(); all.classList.remove('open'); this.hooks.openWindow(p.id); });
      row.querySelector('.pt-del')?.addEventListener('click', (e) => { e.stopPropagation(); all.classList.remove('open'); this.remove(p.id); });
      list.appendChild(row);
    }
    all.querySelector('.pt-all').addEventListener('click', (e) => { e.stopPropagation(); el.querySelector('.part-add')?.classList.remove('open'); all.classList.toggle('open'); });
    el.appendChild(all);
    const open = this.openParts;
    for (const p of open) {
      const tab = document.createElement('div');
      tab.className = `part-tab ${p.kind}${p.id === this.active && !this.none ? ' on' : ''}`;
      tab.dataset.part = p.id;
      tab.title = p.id === this.active ? 'The part on screen — double-click to rename, drag to move the tab (out of the window: a new window)' : 'Click to show it — double-click to rename, drag to move the tab (out of the window: a new window)';
      tab.draggable = true;
      tab.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/a3d-part', p.id); e.dataTransfer.effectAllowed = 'move'; tab.classList.add('dragging'); });
      tab.addEventListener('dragover', (e) => {
        if (!e.dataTransfer.types.includes('text/a3d-part')) return;
        e.preventDefault();
        const r = tab.getBoundingClientRect(), after = e.clientX > r.left + r.width / 2;
        tab.classList.toggle('drop-before', !after);
        tab.classList.toggle('drop-after', after);
      });
      tab.addEventListener('dragleave', () => tab.classList.remove('drop-before', 'drop-after'));
      tab.addEventListener('drop', (e) => {
        e.preventDefault();
        const id = e.dataTransfer.getData('text/a3d-part'), r = tab.getBoundingClientRect();
        this.move(id, p.id, e.clientX > r.left + r.width / 2);
      });
      tab.addEventListener('dragend', (e) => {
        tab.classList.remove('dragging');
        const out = e.clientX <= 0 || e.clientY <= 0 || e.clientX >= innerWidth || e.clientY >= innerHeight;
        if (out && e.dataTransfer.dropEffect === 'none' && this.hooks.openWindow) this.hooks.openWindow(p.id); // dropped outside: its own window
      });
      const name = document.createElement('span');
      name.className = 'pt-name';
      name.dataset.noI18n = '';
      name.textContent = p.name || '…';
      tab.appendChild(name);
      if (this.hooks.openWindow) {
        const w = document.createElement('button');
        w.className = 'pt-win';
        w.textContent = '⧉';
        w.title = WIN_TIP;
        w.addEventListener('click', (e) => { e.stopPropagation(); this.hooks.openWindow(p.id); });
        tab.appendChild(w);
      }
      {
        const x = document.createElement('button');
        x.className = 'pt-x';
        x.textContent = '✕';
        x.title = CLOSE_TIP;
        x.addEventListener('click', (e) => { e.stopPropagation(); this.close(p.id); });
        tab.appendChild(x);
      }
      tab.addEventListener('click', () => this.switchTo(p.id));
      tab.addEventListener('dblclick', (e) => { e.preventDefault(); this.editName(p, name); });
      el.appendChild(tab);
    }
    const add = document.createElement('div');
    add.className = 'menu part-add';
    add.innerHTML = `<button class="pt-add" title="Add a part to this project — every file you open becomes its own part">＋</button>
      <div class="menu-list">
        <button data-new="model">＋ New 3D model</button>
        <button data-new="assembly">＋ New assembly</button>
        <button data-open="pdfInput">Open PDF</button>
        <button data-open="imgInput">Open picture</button>
        <button data-open="cadInput">Open CAD / 3D</button>
        <button data-open="sampleBtn">Sample drawing</button>
      </div>`;
    add.querySelector('.pt-add').addEventListener('click', (e) => { e.stopPropagation(); all.classList.remove('open'); add.classList.toggle('open'); });
    for (const b of add.querySelectorAll('[data-new]')) {
      b.addEventListener('click', () => { add.classList.remove('open'); if (b.dataset.new === 'assembly') this.newAssembly(); else this.newModel(); });
    }
    for (const b of add.querySelectorAll('[data-open]')) {
      b.addEventListener('click', () => { add.classList.remove('open'); document.getElementById(b.dataset.open).click(); });
    }
    el.appendChild(add);
  }

  editName(p, el) {
    el.closest('.part-tab')?.classList.add('editing');
    el.contentEditable = 'true';
    el.focus();
    document.getSelection().selectAllChildren(el);
    let finished = false;
    const done = (keep) => {
      if (finished) return;
      finished = true;
      el.contentEditable = 'false';
      const n = el.textContent.trim();
      if (keep && n && n !== p.name) { p.name = n; this.hooks.toast(`Part renamed to “${n}”.`, 'ok'); }
      this.render();
    };
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); done(true); }
      if (e.key === 'Escape') { e.preventDefault(); done(false); }
      e.stopPropagation();
    });
    el.addEventListener('blur', () => done(true), { once: true });
  }
}
