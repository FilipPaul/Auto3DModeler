import { t } from './i18n.js';
import { leftDock } from './leftdock.js';
import { params } from './params.js';
import { loadParams } from './paramsui.js';

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
ICON_PATH.library = '<path d="M2.5 2.5h2.6v11H2.5zM5.9 2.5h2.6v11H5.9z"/><path d="M9.4 3.4l2.5-.7 2.6 10.1-2.5.7z"/><path d="M2.5 5h2.6M5.9 5h2.6M2.5 11h2.6M5.9 11h2.6" opacity=".7"/>'; // a library part as it came

/** A short hash of a part's steps (a library part keeps the one it came with: changed steps — no longer the library's). */
export function stepsHash(features) {
  const s = JSON.stringify(features || []);
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16);
}

/** A library part not changed since it came in (its icon: the library's). */
export const fromLibrary = (data) => !!data?.library && (!data.library.steps || data.library.steps === stepsHash(data.features));

export const kindIcon = (kind) => `<svg class="ico ico-${ICON_PATH[kind] ? kind : 'classic'}" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${ICON_PATH[kind] || ICON_PATH.classic}</svg>`;

/** A one-click ✕ made safe without a dialog: the first click turns it into a red "Delete?" for 3 s, a second
 *  click (or Enter / Space) runs `run`; moving the pointer or the focus away, or waiting, puts the ✕ back. */
export function armDelete(btn, run) {
  const label = btn.textContent, tip = btn.title;
  let timer = 0;
  const disarm = () => { clearTimeout(timer); timer = 0; btn.classList.remove('armed'); btn.textContent = label; btn.title = tip; };
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (timer) { disarm(); run(); return; }
    btn.classList.add('armed'); btn.textContent = t('Delete?'); btn.title = t('Click again to delete it (↶ Undo brings it back)');
    timer = setTimeout(disarm, 3000);
  });
  btn.addEventListener('pointerleave', () => { if (timer) disarm(); });
  btn.addEventListener('blur', () => { if (timer) disarm(); });
}

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
  async newAssembly(name = null, data = null) {
    if (this.busy) return;
    await this.hooks.settle();
    if (this.current) this.stash();
    const n = 1 + this.parts.filter((q) => q.kind === 'assembly').length;
    const p = { id: `P${this.next++}`, name: name || `${t('Assembly')} ${n}`, kind: 'assembly', data: data || { instances: [] }, history: null };
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
  addBackground(name, data, kind = 'model') {
    const p = { id: `P${this.next++}`, name, kind, data, history: null, closed: true };
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
    if (this.active === p.id) p.data = 'live'; // (another tab opened while this one loaded — a sheet of it: that kept its data)
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
    this.lastDeleted = { p, at: this.parts.indexOf(p), when: Date.now() }; // (↶ in the tree brings it back)
    this.parts = this.parts.filter((q) => q !== p);
    if (!this.openParts.length && this.parts.length) delete this.parts[0].closed;
    this.render();
    clearTimeout(this.undoTimer);
    this.undoTimer = setTimeout(() => { this.lastDeleted = null; this.render(); }, 30000);
  }

  /** A part taken out of the project without asking (an undo took away what made it: ⧉ Make it its own part's
   *  copy) -> {p, at} for putBack, or null (it is on screen). */
  take(id) {
    const p = this.parts.find((q) => q.id === id);
    if (!p || p.id === this.active || this.busy) return null;
    const at = this.parts.indexOf(p);
    this.parts.splice(at, 1);
    this.render();
    return { p, at };
  }

  /** A part taken back where it was (a redo). */
  putBack({ p, at }) {
    if (this.parts.some((q) => q.id === p.id)) return;
    this.parts.splice(Math.min(at, this.parts.length), 0, p);
    this.render();
  }

  /** ↶ The part deleted last back where it was (with its data; assemblies that used it find it again). */
  undoDelete() {
    const d = this.lastDeleted;
    if (!d || this.parts.some((q) => q.id === d.p.id)) return;
    this.parts.splice(Math.min(d.at, this.parts.length), 0, d.p);
    this.lastDeleted = null;
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
      parameters: params.toJSON(), // (𝑥 the project's parameters)
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
    loadParams(proj.parameters); // (its numbers agree with them already: project.migrate)
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
    all.className = `pt-all${(leftDock.project === 'popup' ? this.treeOpen : !leftDock.folded('project')) ? ' on' : ''}`;
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
      tab.insertAdjacentHTML('beforeend', kindIcon(this.libraryPart(p) ? 'library' : p.kind));
      tab.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); }); // (no scrolling cursor)
      tab.addEventListener('auxclick', (e) => { if (e.button === 1) { e.preventDefault(); this.close(p.id); } }); // a middle click closes it
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

  /** ☰ The project's tree on / off (remembered); docked or floating (a widget — leftdock.js): folded / unfolded. */
  toggleTree(on) {
    if (leftDock.project !== 'popup' && this.parts.length) { leftDock.fold('project', on === undefined ? undefined : !on); this.render(); return; }
    on ??= !this.treeOpen;
    this.treeOpen = on;
    try { localStorage.setItem('a3d.tree', on ? '1' : ''); } catch { /* private window */ }
    this.render();
  }

  /** Is it a library part as it came (not changed)? */
  libraryPart(p) {
    if (p.kind !== 'model') return false;
    try { return fromLibrary(this.dataOf(p)); } catch { return false; }
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
      // a double-click on a row: its name to edit (the part opens with the first click)
      this.tree.addEventListener('dblclick', (e) => { const r = e.target.closest('.pt-row'); if (r && !e.target.closest('.pt-win, .pt-del')) this.renameInTree(r.dataset.part); });
      // the header dragged: into the left column (docked) or onto the view (floating) — leftdock.js
      this.tree.addEventListener('pointerdown', (e) => { const h = e.target.closest('.tr-head'); if (h) leftDock.dragStart('project', e, h); });
      leftDock.onProject = () => this.render();
      leftDock.onUnpin = () => this.toggleTree(true); // (unpinned: there as the ☰ popup, ✕ closes it)
      window.addEventListener('a3d:changed', () => { // (what is in an assembly changes as it is edited)
        if (!this.treeOpen && leftDock.project === 'popup') return;
        clearTimeout(this.treeTimer);
        this.treeTimer = setTimeout(() => this.renderTree(), 400);
      });
    }
    const box = this.tree;
    if (box.querySelector('.tr-rename')) return; // (a name being typed: not now)
    const popup = leftDock.project === 'popup';
    leftDock.setShown(this.parts.length > 0);
    box.classList.toggle('open', (!popup || !!this.treeOpen) && this.parts.length > 0);
    box.classList.toggle('in-widget', !popup);
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
    const undo = this.lastDeleted ? `<button class="btn small tr-undo" title="${t('Bring back the part deleted last')}">↶ ${t('Undo')}: <span data-no-i18n></span></button>` : '';
    box.innerHTML = popup ? `<div class="tr-head" title="${t('Drag the header into the left panel to dock it there, or onto the view to float it')}"><b>☰ ${t('Project')}</b>${undo}<button class="mini tr-pin" title="${t('Dock it in the left panel — always in sight, in every workspace (or drag its header there)')}">📌</button><button class="mini tr-x" title="${t('Close the project tree')}">✕</button></div>
      <p class="hint">${t('Click a part to open it — ⧉ in a new window, ✕ deletes it from the project.')}</p><div class="tr-list"></div>`
      : `${undo ? `<div class="tr-undo-row">${undo}</div>` : ''}<div class="tr-list"></div>`;
    box.querySelector('.tr-x')?.addEventListener('click', () => this.toggleTree(false));
    box.querySelector('.tr-pin')?.addEventListener('click', () => { leftDock.dock('project'); this.render(); });
    const ub = box.querySelector('.tr-undo');
    if (ub) { ub.querySelector('span').textContent = this.lastDeleted.p.name || ''; ub.addEventListener('click', () => this.undoDelete()); }
    const list = box.querySelector('.tr-list');
    for (const { p, depth, qty } of rows) {
      const row = document.createElement('div');
      row.className = `pt-row tr-row ${p.kind}${p.id === this.active && !this.none ? ' on' : ''}${p.closed ? ' closed' : ''}`;
      row.dataset.part = p.id;
      row.style.paddingLeft = `${4 + 14 * depth}px`;
      row.innerHTML = `<button class="pt-open" title="${t(p.closed ? 'Open it (a tab) — double-click: rename it' : 'Show it — double-click: rename it')}"><span class="pt-kind">${kindIcon(this.libraryPart(p) ? 'library' : p.kind)}</span><span class="pt-rname" data-no-i18n></span>${qty > 1 ? `<i class="tr-qty" data-no-i18n>×${qty}</i>` : ''}</button>${this.hooks.openWindow ? `<button class="mini pt-win" title="${t(WIN_TIP)}">⧉</button>` : ''}${this.parts.length > 1 ? `<button class="mini danger pt-del" title="${t('Delete it from the project (↶ Undo brings it back)')}">✕</button>` : ''}`;
      row.querySelector('.pt-rname').textContent = p.name || '…';
      row.querySelector('.pt-open').addEventListener('click', () => this.switchTo(p.id));
      row.querySelector('.pt-win')?.addEventListener('click', (e) => { e.stopPropagation(); this.hooks.openWindow(p.id); });
      const del = row.querySelector('.pt-del');
      if (del) armDelete(del, () => this.remove(p.id, false)); // (a second click deletes; ↶ undoes it)
      if (p.kind !== 'sheet' && p.kind !== 'drawing') { // dragged into an assembly's view: it goes in
        row.draggable = true;
        row.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/a3d-insert', p.id); e.dataTransfer.effectAllowed = 'copy'; this.hidePreview(); });
      }
      row.addEventListener('mouseenter', () => this.showPreview(p, row));
      row.addEventListener('mouseleave', () => this.hidePreview());
      list.appendChild(row);
    }
  }

  /** A double-click on a row in the tree: its name in a field (Enter keeps it, Esc not), once the part is open. */
  renameInTree(id) {
    const go = () => {
      if (this.busy) { setTimeout(go, 80); return; }
      const p = this.parts.find((q) => q.id === id), row = this.tree?.querySelector(`.pt-row[data-part="${CSS.escape(id)}"]`);
      if (!p || !row || row.querySelector('.tr-rename')) return;
      this.hidePreview();
      const btn = row.querySelector('.pt-open'), inp = document.createElement('input');
      inp.className = 'tr-rename';
      inp.value = p.name || '';
      inp.title = t('Enter: rename it — Esc: keep the name');
      btn.hidden = true;
      row.insertBefore(inp, btn.nextSibling);
      inp.focus();
      inp.select();
      let finished = false;
      const done = (keep) => {
        if (finished) return;
        finished = true;
        const n = inp.value.trim();
        inp.remove();
        btn.hidden = false;
        if (keep && n && n !== p.name) { p.name = n; this.hooks.toast(`Part renamed to “${n}”.`, 'ok'); }
        this.render();
      };
      inp.addEventListener('keydown', (e) => {
        e.stopPropagation(); // (not the app's keys: Delete, Ctrl+Z …)
        if (e.key === 'Enter') { e.preventDefault(); done(true); }
        if (e.key === 'Escape') { e.preventDefault(); done(false); }
      });
      inp.addEventListener('blur', () => done(true), { once: true });
    };
    go();
  }

  /** A picture of what is in a part, beside its row in the tree (after a moment on it). */
  showPreview(p, row) {
    clearTimeout(this.previewTimer);
    if (!this.hooks.thumb) return;
    this.previewTimer = setTimeout(async () => {
      let box = document.querySelector('.tr-preview');
      if (!box) { box = document.createElement('div'); box.className = 'tr-preview'; document.body.appendChild(box); }
      const r = row.getBoundingClientRect();
      Object.assign(box.style, { left: `${r.right + 8}px`, top: `${Math.max(8, Math.min(r.top - 40, innerHeight - 220))}px` });
      box.innerHTML = `<b data-no-i18n></b><div class="tp-img">${t('…')}</div>`;
      box.querySelector('b').textContent = p.name || '';
      box.hidden = false;
      this.previewFor = p.id;
      let url = null;
      try { url = await this.hooks.thumb(p); } catch { url = null; }
      if (this.previewFor !== p.id) return;
      box.querySelector('.tp-img').innerHTML = url ? `<img alt="" src="${url}">` : `<i>${t('Nothing to show yet')}</i>`;
    }, 280);
  }

  hidePreview() {
    clearTimeout(this.previewTimer);
    this.previewFor = null;
    const box = document.querySelector('.tr-preview');
    if (box) box.hidden = true;
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
