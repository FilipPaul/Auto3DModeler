// Undo / redo by snapshots: a step is recorded when the state differs from the last recorded one.
// Used by the 3D model workspace (one instance per model part); the Quick part keeps its own in app.js.

const clone = (x) => (x === undefined || x === null ? x : structuredClone(x));
/** Something changed (a step, an undo): autosave listens. */
export const changed = () => window.dispatchEvent(new Event('a3d:changed'));

export class History {
  // Hooks for a history all the workspaces share (the project's 𝑥 parameters, params.js): first(dir, history, probe)
  // takes an undo / redo of `history` when its own step is the last one (-> a promise; probe: only whether it would);
  // committed(history): a step was recorded.
  static first = null;
  static committed = null;
  // Who else hears of every step, in every workspace: fn(history, dir) — dir 0: recorded, -1: undone, +1: redone (⏺ the
  // recording of moves, recorder.js).
  static watchers = new Set();

  /** capture(): the state to record; restore(snapshot): put it back; onChange(): update the buttons. */
  constructor({ capture, restore, onChange = () => {}, limit = 100 }) {
    Object.assign(this, { capture, restore, onChange, limit });
    this.undo = [];
    this.redo = [];
    this.base = null;
    this.baseKey = '';
  }

  reset() {
    this.undo = [];
    this.redo = [];
    this.base = clone(this.capture());
    this.baseKey = JSON.stringify(this.base);
    this.onChange();
  }

  /** Record the current state as a step (nothing happens when it did not change). */
  commit() {
    const did = this.record();
    if (did) { History.committed?.(this); for (const fn of History.watchers) fn(this, 0); }
    return did;
  }

  record() {
    const cur = clone(this.capture()), k = JSON.stringify(cur);
    if (k === this.baseKey) return false;
    if (this.base !== null) this.undo.push(this.base);
    if (this.undo.length > this.limit) this.undo.shift();
    this.redo = [];
    this.base = cur;
    this.baseKey = k;
    this.onChange();
    changed();
    return true;
  }

  canUndo() { return this.undo.length > 0 || !!History.first?.(-1, this, true); }
  canRedo() { return this.redo.length > 0 || !!History.first?.(1, this, true); }

  async go(dir) {
    const other = History.first?.(dir, this, false); // (a 𝑥 parameter changed last: that goes back first — params.js)
    if (other) return other;
    const from = dir < 0 ? this.undo : this.redo, to = dir < 0 ? this.redo : this.undo;
    const snap = from.pop();
    if (!snap) return false;
    to.push(this.base);
    this.base = snap;
    this.baseKey = JSON.stringify(snap);
    await this.restore(clone(snap));
    this.onChange();
    changed();
    for (const fn of History.watchers) fn(this, dir);
    return true;
  }

  /** For switching parts: the whole history, and back. */
  get state() { return { undo: this.undo, redo: this.redo, base: this.base, baseKey: this.baseKey }; }
  set state(s) { Object.assign(this, s); this.onChange(); }
}
