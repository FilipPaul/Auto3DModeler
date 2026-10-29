// ⧉ Windows: a part of the project opened in a browser window of its own (another monitor). Every window holds the
// whole project; a part changed in one window is sent to the others (a BroadcastChannel per project), which take it
// in — a part on screen there is shown again, an assembly or a drawing sheet using it is built again. The project is
// saved by each window (autosave) and is the same in all of them.
// Every window of the app (any project) also answers "which project is open here?" (the channel a3d-windows):
// a new window's "continue where you left off" skips the projects open elsewhere, 🕘 Recent projects marks them.

const newId = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);
const keyOf = (p, data) => JSON.stringify([p.name, p.kind, data]);

export class Windows {
  /** hooks: {project (the Project), live() -> the part on screen's data, reloadLive(part) (shows it again with its new
   *  data), rebuild() (the part on screen uses changed parts: built again), saveNow(), toast} */
  constructor(hooks) {
    this.hooks = hooks;
    this.wid = newId();
    this.ch = null;
    this.room = null;
    this.sent = new Map(); // part id -> what the others have of it (its name, kind, data)
    this.timer = null;
    window.addEventListener('a3d:changed', () => { clearTimeout(this.timer); this.timer = setTimeout(() => this.send(), 250); });
    window.addEventListener('a3d:project-loading', () => this.connect(null)); // (another project: not sent to this one's windows)
    if (typeof BroadcastChannel !== 'undefined') { // (asked by another window: the project open here, if any)
      this.all = new BroadcastChannel('a3d-windows');
      this.all.onmessage = (e) => {
        if (e.data?.ask && this.room && this.hooks.project.parts.length) this.all.postMessage({ answer: e.data.ask, room: this.room, from: this.wid });
      };
    }
  }

  /** The ids of the projects open in the app's other windows (those that answer within `ms`). */
  async openElsewhere(ms = 250) {
    const got = new Set();
    if (!this.all) return got;
    const ask = newId(), ch = new BroadcastChannel('a3d-windows');
    ch.onmessage = (e) => { if (e.data?.answer === ask && e.data.from !== this.wid) got.add(e.data.room); };
    ch.postMessage({ ask });
    await new Promise((r) => setTimeout(r, ms));
    ch.close();
    return got;
  }

  /** The windows of project `id` (null: none). What there is now is what they have (a new window loads it saved) —
   *  resend: they do not (the project went back to an earlier state here): all of it goes to them. */
  connect(id, resend = false) {
    this.ch?.close();
    this.ch = null;
    this.room = id;
    this.sent = new Map();
    if (!id || typeof BroadcastChannel === 'undefined') return;
    if (!resend) for (const p of this.parts()) this.sent.set(p.id, keyOf(p, p.data));
    this.ch = new BroadcastChannel(`a3d-project-${id}`);
    this.ch.onmessage = (e) => this.receive(e.data).catch((err) => console.warn('windows:', err));
  }

  /** Every part with its data now (the one on screen: as it is on screen). */
  parts() {
    const pr = this.hooks.project;
    return pr.parts.map((p) => ({ id: p.id, name: p.name, kind: p.kind, data: p.id === pr.active && p.data === 'live' ? this.hooks.live() : p.data }))
      .filter((p) => p.data && typeof p.data === 'object');
  }

  send() {
    if (!this.ch || this.hooks.project.busy) return;
    const all = this.parts(), changed = [];
    for (const p of all) {
      const k = keyOf(p, p.data);
      if (this.sent.get(p.id) === k) continue;
      this.sent.set(p.id, k);
      changed.push(p);
    }
    const ids = this.hooks.project.parts.map((p) => p.id);
    const gone = [...this.sent.keys()].filter((id) => !ids.includes(id));
    for (const id of gone) this.sent.delete(id);
    if (changed.length || gone.length) this.ch.postMessage({ from: this.wid, parts: changed, gone, next: this.hooks.project.next });
  }

  /** A note to the other windows of the project (not a change of parts). */
  tell(note) { this.ch?.postMessage({ from: this.wid, note }); }

  async receive(msg) {
    if (!msg || msg.from === this.wid) return;
    if (msg.note) { // a tab of this window was dragged into another one: it goes from here
      if (msg.note.took && msg.note.win === this.wid) await this.hooks.gave?.(msg.note.took);
      return;
    }
    const pr = this.hooks.project;
    while (pr.busy) await new Promise((r) => setTimeout(r, 100)); // (a part being switched to)
    this.send(); // (what changed here first: not lost under theirs)
    let live = null, others = false;
    for (const q of msg.parts || []) {
      const k = keyOf(q, q.data);
      this.sent.set(q.id, k);
      const p = pr.parts.find((x) => x.id === q.id);
      if (!p) { pr.parts.push({ id: q.id, name: q.name, kind: q.kind, data: q.data, history: null, closed: true }); continue; } // (its tab: ☰ Parts)
      p.name = q.name;
      if (p.id === pr.active && p.data === 'live') {
        if (keyOf(p, this.hooks.live()) !== k) live = { p, data: q.data };
      } else { p.data = q.data; p.kind = q.kind; others = true; }
    }
    for (const id of msg.gone || []) {
      if (id === pr.active) continue; // (on screen here: it stays)
      pr.parts = pr.parts.filter((p) => p.id !== id);
      this.sent.delete(id);
    }
    pr.next = Math.max(pr.next, msg.next || 0);
    if (live) {
      live.p.data = live.data;
      await this.hooks.reloadLive(live.p);
      this.sent.set(live.p.id, keyOf(live.p, this.hooks.live())); // (as shown here: not sent back)
    } else if (others) await this.hooks.rebuild();
    pr.render();
  }

  /** ⧉ A part in a new window (the project saved first: the window loads it). */
  async open(partId) {
    await this.hooks.saveNow();
    if (!this.room) throw new Error('The project is not saved yet — make a change first, then try again.');
    const url = `${location.pathname}?project=${encodeURIComponent(this.room)}&part=${encodeURIComponent(partId)}`;
    const w = window.open(url, `a3d-${this.room}-${partId}`, 'popup=yes,width=1400,height=900');
    if (!w) throw new Error('The browser blocked the new window — allow pop-ups for this page.');
    w.focus();
    return w;
  }
}
