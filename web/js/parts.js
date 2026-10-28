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
// one small drawn icon per kind of part (tabs, the project tree): its colour from the kind (CSS .ico-<kind>)
const ICON_PATH = {
  model: '<path d="M8 1.6 14 5v6L8 14.4 2 11V5z"/><path d="M2 5l6 3.4L14 5M8 8.4v6"/>', // a block
  assembly: '<path d="M5.5 1.8 9.5 4v4.4L5.5 10.6 1.5 8.4V4z"/><path d="M1.5 4l4 2.2 4-2.2M5.5 6.2v4.4"/><path d="M10.5 6.6 14.5 8.8v4.4l-4 2.2-4-2.2" opacity=".85"/>', // two blocks
  drawing: '<path d="M2 14.2V2.2l12 12z"/><path d="M5 11.2V8.4l2.8 2.8z"/><path d="M2 5h1.6M2 8h1.6" opacity=".8"/>', // a set square (DXF / DWG / PCB)
  sheet: '<path d="M3 1.6h7l3 3v9.8H3z"/><path d="M10 1.6v3h3"/><rect x="5" y="7.6" width="6" height="3.6" rx=".3"/><path d="M5 13h6" opacity=".7"/>', // a drawing sheet
  classic: '<path d="M8 2 14 5 8 8 2 5z"/><path d="M2 8l6 3 6-3M2 11l6 3 6-3"/>', // layers (a quick part)
};
export const kindIcon = (kind) => `<svg class="ico ico-${ICON_PATH[kind] ? kind : 'classic'}" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${ICON_PATH[kind] || ICON_PATH.classic}</svg>`;

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
    // a tab dragged in from another window of this project (onto the tab row, not onto a tab): it opens here
    el.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('text/a3d-part')) e.preventDefault(); });
    el.addEventListener('drop', (e) => {
      if (e.target.closest('.part-tab') || !e.dataTransfer.types.includes('text/a3d-part')) return;
      e.preventDefault();
      const from = this.fromElsewhere(e);
      if (from) this.adopt(e.dataTransfer.getData('text/a3d-part'), from); else this.droppedHere = true;
    });
  }

  /** ⧉ This window shows only these tabs (a window opened for one part); the rest stay in the project (☰). */
  showOnly(...ids) { this.shown = new Set(ids); this.render(); }

  /** Where a dragged tab comes from: {win, project} when it is another window's, else null. */
  fromElsewhere(e) {
    try {
      const f = JSON.parse(e.dataTransfer.getData('text/a3d-from') || '{}');
      return f.win && f.win !== this.hooks.windowId?.() ? f : null;
    } catch { return null; }
  }

  /** A tab dragged in from another window: its part opens here (that window lets it go). -> done */
  async adopt(id, from) {
    if (from.project !== this.hooks.projectId?.()) { this.hooks.toast(t('That tab is from another project — open that project here first.'), 'warning', 5000); return false; }
    const p = this.parts.find((q) => q.id === id);
    if (!p) { this.hooks.toast(t('That part has not reached this window yet — try again in a moment.'), 'warning', 4000); return false; }
    this.shown?.add(id);
    delete p.closed;
    await this.switchTo(id);
    this.render();
    this.hooks.tookTab?.(id, from.win);
    return true;
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
    if (p) this.shown?.add(id); // (a window of its own: this tab now too)
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

  get openParts() { return this.parts.filter((p) => !p.closed && (!this.shown || this.shown.has(p.id))); }

  /** ✕ on a tab: the tab goes, the part stays in the project (☰ Parts opens it again). */
  async close(id) {
    const open = this.openParts, p = open.find((q) => q.id === id);
    if (!p || this.busy) return;
    // (a window of its own: the tab goes from this window only — the part stays open in the others)
    const shut = () => { if (this.shown) this.shown.delete(id); else p.closed = true; };
    if (open.length < 2) { // the last tab: nothing on screen (☰ opens a part again)
      if (id === this.active) this.setNone(true);
      shut();
      this.render();
      return;
    }
    if (id === this.active) {
      const i = open.indexOf(p);
      await this.switchTo((open[i + 1] || open[i - 1]).id);
      if (this.active === id) return;
    }
    shut();
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
    if (this.shown && this.active && !this.none) this.shown.add(this.active); // (a part made in this window: its tab here)
    const el = this.el;
    el.hidden = !this.parts.length;
    el.innerHTML = '';
    // ☰: the project's tree in the left panel (every part, open or not) — click to open, ⧉ a window, ✕ to delete
    const all = document.createElement('button');
    all.className = `pt-all${this.treeOpen ? ' on' : ''}`;
    all.title = 'The project: all its parts, as they go together — open one, open it in a new window, or delete it';
    all.innerHTML = `☰ <span data-no-i18n>${this.parts.length}</span>`;
    all.addEventListener('click', (e) => { e.stopPropagation(); el.querySelector('.part-add')?.classList.remove('open'); this.toggleTree(); });
    el.appendChild(all);
    this.renderTree();
    const open = this.openParts;
    for (const p of open) {
      const tab = document.createElement('div');
      tab.className = `part-tab ${p.kind}${p.id === this.active && !this.none ? ' on' : ''}`;
      tab.dataset.part = p.id;
      tab.title = p.id === this.active ? 'The part on screen — double-click to rename, drag to move the tab (out of the window: a new window)' : 'Click to show it — double-click to rename, drag to move the tab (out of the window: a new window)';
      tab.draggable = true;
      tab.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/a3d-part', p.id);
        e.dataTransfer.setData('text/a3d-from', JSON.stringify({ win: this.hooks.windowId?.(), project: this.hooks.projectId?.() }));
        e.dataTransfer.effectAllowed = 'move';
        this.droppedHere = false;
        tab.classList.add('dragging');
      });
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
        const id = e.dataTransfer.getData('text/a3d-part'), r = tab.getBoundingClientRect(), after = e.clientX > r.left + r.width / 2, from = this.fromElsewhere(e);
        if (from) { this.adopt(id, from).then((ok) => ok && this.move(id, p.id, after)); return; } // (from another window: it opens here, there)
        this.droppedHere = true;
        this.move(id, p.id, after);
      });
      tab.addEventListener('dragend', (e) => {
        tab.classList.remove('dragging');
        if (e.dataTransfer.dropEffect === 'move' && !this.droppedHere) { this.close(p.id); return; } // taken by another window: it goes from here
        const out = e.clientX <= 0 || e.clientY <= 0 || e.clientX >= innerWidth || e.clientY >= innerHeight;
        if (out && e.dataTransfer.dropEffect === 'none' && this.hooks.openWindow) this.hooks.openWindow(p.id); // dropped outside: its own window
      });
      tab.insertAdjacentHTML('beforeend', kindIcon(p.kind));
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

  /** ☰ The project's tree on / off (remembered). */
  toggleTree(on = !this.treeOpen) {
    this.treeOpen = on;
    try { localStorage.setItem('a3d.tree', on ? '1' : ''); } catch { /* private window */ }
    this.render();
  }

  /** A part's data now (the one on screen: as it is on screen). */
  dataOf(p) { return p.id === this.active && p.data === 'live' ? this.hooks.payload(p.kind) : p.data; }

  /** The project's tree over the left panel: the assemblies with what is in them (sub-assemblies inside), each part's
   *  drawing sheets under it, then the parts in no assembly. */
  renderTree() {
    if (!this.tree) {
      this.tree = document.createElement('aside');
      this.tree.className = 'proj-tree';
      this.tree.id = 'projTree';
      document.querySelector('main.layout')?.appendChild(this.tree);
      try { this.treeOpen = this.treeOpen ?? localStorage.getItem('a3d.tree') === '1'; } catch { this.treeOpen = false; }
      window.addEventListener('a3d:changed', () => { // (what is in an assembly changes as it is edited)
        if (!this.treeOpen) return;
        clearTimeout(this.treeTimer);
        this.treeTimer = setTimeout(() => this.renderTree(), 400);
      });
    }
    const box = this.tree;
    box.classList.toggle('open', !!this.treeOpen && this.parts.length > 0);
    if (!box.classList.contains('open')) { box.innerHTML = ''; return; }
    const data = new Map(this.parts.map((p) => { try { return [p.id, this.dataOf(p)]; } catch { return [p.id, null]; } }));
    const byId = new Map(this.parts.map((p) => [p.id, p])), used = new Set(), sheets = new Map(), kids = new Map();
    for (const p of this.parts) {
      const d = data.get(p.id);
      if (p.kind === 'assembly') {
        const n = new Map();
        for (const it of d?.instances || []) if (byId.has(it.part)) n.set(it.part, (n.get(it.part) || 0) + 1);
        kids.set(p.id, [...n]);
        for (const id of n.keys()) used.add(id);
      } else if (p.kind === 'sheet' && byId.has(d?.source)) {
        if (!sheets.has(d.source)) sheets.set(d.source, []);
        sheets.get(d.source).push(p);
      }
    }
    const rows = [];
    const add = (p, depth, qty, path) => {
      rows.push({ p, depth, qty });
      for (const s of sheets.get(p.id) || []) rows.push({ p: s, depth: depth + 1 });
      if (path.has(p.id)) return;
      for (const [id, n] of kids.get(p.id) || []) add(byId.get(id), depth + 1, n, new Set([...path, p.id]));
    };
    const top = this.parts.filter((p) => !used.has(p.id) && !(p.kind === 'sheet' && byId.has(data.get(p.id)?.source)));
    for (const p of [...top.filter((q) => q.kind === 'assembly'), ...top.filter((q) => q.kind !== 'assembly')]) add(p, 0, 1, new Set());
    box.innerHTML = `<div class="tr-head"><b>☰ ${t('Project')}</b><button class="mini tr-x" title="${t('Close the project tree')}">✕</button></div>
      <p class="hint">${t('Click a part to open it — ⧉ in a new window, ✕ deletes it from the project.')}</p><div class="tr-list"></div>`;
    box.querySelector('.tr-x').addEventListener('click', () => this.toggleTree(false));
    const list = box.querySelector('.tr-list');
    for (const { p, depth, qty } of rows) {
      const row = document.createElement('div');
      row.className = `pt-row tr-row ${p.kind}${p.id === this.active && !this.none ? ' on' : ''}${p.closed ? ' closed' : ''}`;
      row.dataset.part = p.id;
      row.style.paddingLeft = `${4 + 14 * depth}px`;
      row.innerHTML = `<button class="pt-open" title="${t(p.closed ? 'Open it (a tab)' : 'Show it')}"><span class="pt-kind">${kindIcon(p.kind)}</span><span class="pt-rname" data-no-i18n></span>${qty > 1 ? `<i class="tr-qty" data-no-i18n>×${qty}</i>` : ''}</button>${this.hooks.openWindow ? `<button class="mini pt-win" title="${t(WIN_TIP)}">⧉</button>` : ''}${this.parts.length > 1 ? `<button class="mini danger pt-del" title="${t('Delete it from the project')}">✕</button>` : ''}`;
      row.querySelector('.pt-rname').textContent = p.name || '…';
      row.querySelector('.pt-open').addEventListener('click', () => this.switchTo(p.id));
      row.querySelector('.pt-win')?.addEventListener('click', (e) => { e.stopPropagation(); this.hooks.openWindow(p.id); });
      row.querySelector('.pt-del')?.addEventListener('click', (e) => { e.stopPropagation(); this.remove(p.id); });
      list.appendChild(row);
    }
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
