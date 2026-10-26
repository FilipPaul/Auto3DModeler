import { t } from './i18n.js';

// A project holds several parts, shown as tabs in the top bar (like browser tabs). Every file you open
// becomes a part; click a tab to switch, double-click to rename, ✕ to close. Only the active part lives
// in the app state — the others are kept as their saved payload (the same JSON a part is saved with)
// together with their undo history, so switching back restores them exactly. A part is either "classic"
// (a drawing, picture outline or imported file — the Quick part workspace) or a "model" (sketches and
// features — the 3D model workspace).

const CLOSE_TIP = 'Close this part (it is removed from the project)';

export class Project {
  /** hooks: {payload(kind), load(payload, {switching, kind}), settle(), getHistory(kind), setHistory(h, kind),
   *  newModel(), toast(msg, kind)} */
  constructor(el, hooks) {
    this.el = el;
    this.hooks = hooks;
    this.parts = []; // {id, name, kind: 'classic' | 'model', data, history}
    this.active = null;
    this.next = 1;
    this.busy = false;
    document.addEventListener('click', () => this.el.querySelector('.part-add')?.classList.remove('open'));
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

  /** A new 3D model part (its own tab) — empty, or with first steps (data) and a command to open (then). */
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

  async show(p, extra = {}) {
    await this.hooks.load(p.data, { switching: true, kind: p.kind, ...extra });
    if (p.history) this.hooks.setHistory(p.history, p.kind);
    p.data = 'live';
  }

  async switchTo(id) {
    if (id === this.active || this.busy) return;
    const p = this.parts.find((q) => q.id === id);
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

  async close(id) {
    if (this.parts.length < 2 || this.busy) return;
    const p = this.parts.find((q) => q.id === id);
    if (!p || !confirm(`Close the part “${p.name}”? It is removed from the project (Save project keeps the rest).`)) return;
    const i = this.parts.indexOf(p);
    if (id === this.active) {
      const to = this.parts[i + 1] || this.parts[i - 1];
      await this.switchTo(to.id);
    }
    this.parts = this.parts.filter((q) => q !== p);
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
        .map((p) => ({ id: p.id, kind: p.kind, name: p.name, [p.kind === 'classic' ? 'classic' : p.kind]: p.data })),
    };
    if (this.current) this.current.data = 'live';
    return out;
  }

  /** Open a version-3 project: every part as a tab, the active one on screen. */
  async loadAll(proj) {
    this.parts = proj.parts.map((p) => ({ id: p.id, name: p.name, kind: p.kind, data: p.kind === 'classic' ? p.classic : p[p.kind], history: null }));
    this.next = 1 + Math.max(0, ...this.parts.map((p) => parseInt(String(p.id).replace(/\D/g, ''), 10) || 0));
    const act = this.parts.find((p) => p.id === proj.active?.part) || this.parts[0];
    this.active = act.id;
    this.render();
    await this.show(act);
    this.render();
  }

  render() {
    const el = this.el;
    el.hidden = !this.parts.length;
    el.innerHTML = '';
    for (const p of this.parts) {
      const tab = document.createElement('div');
      tab.className = `part-tab ${p.kind}${p.id === this.active ? ' on' : ''}`;
      tab.dataset.part = p.id;
      tab.title = p.id === this.active ? 'The part on screen — double-click to rename' : 'Click to show this part — double-click to rename';
      const name = document.createElement('span');
      name.className = 'pt-name';
      name.dataset.noI18n = '';
      name.textContent = p.name || '…';
      tab.appendChild(name);
      if (this.parts.length > 1) {
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
    add.querySelector('.pt-add').addEventListener('click', (e) => { e.stopPropagation(); add.classList.toggle('open'); });
    for (const b of add.querySelectorAll('[data-new]')) {
      b.addEventListener('click', () => { add.classList.remove('open'); if (b.dataset.new === 'assembly') this.newAssembly(); else this.newModel(); });
    }
    for (const b of add.querySelectorAll('[data-open]')) {
      b.addEventListener('click', () => { add.classList.remove('open'); document.getElementById(b.dataset.open).click(); });
    }
    el.appendChild(add);
  }

  editName(p, el) {
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
