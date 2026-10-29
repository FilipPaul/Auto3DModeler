// 𝑥 Project parameters: named values of the project — L = 100, D = 8, t = L / 20 — that any number field takes as
// an expression (L, L/2 + 5, =D; "L = 100" typed in a field makes L). A field keeps its expression next to its number:
// the object it is in gets `expr: {<key>: "L/2"}` (a sketch size shown as a radius: {x: "L", k: 0.5}: the value is
// the expression's / k), and its number is always the resolved value — so the server, exports and older code read
// numbers as before. Changing a parameter puts the new values in every part's numbers (resolveIn) and builds them
// again (paramsui.js). Read with a small parser of our own (no eval): numbers (2.5 or 2,5; a unit mm / ° after one is
// skipped), names, + - * / and brackets. auto3d/modeler/params.py is the same in Python (the project file, tests);
// tests/param_cases.json holds the cases both must agree on.
import { History } from './history.js';
import { t } from './i18n.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
const fill = (text, vars) => text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
export const NAME_RE = /^[\p{L}_][\p{L}\p{N}_]*$/u;
const UNITS = new Set(['mm', 'deg', '°']);
const PLAIN = /^\s*[-+]?(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?\s*$/;

/** What went wrong in an expression: code (for tests and the AI), message (in the app's language), en (English). */
export class ParamError extends Error {
  constructor(code, text, vars = {}) {
    super(t2(text, vars));
    Object.assign(this, { code, en: fill(text, vars) });
  }
}

/** A plain number ("12", "-2.5", "2,5")? */
export const isPlain = (s) => PLAIN.test(String(s ?? ''));

function tokens(text) {
  const out = [];
  const s = String(text);
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (/\s/.test(c)) { i++; continue; }
    const num = /^(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?/.exec(s.slice(i));
    if (num) { out.push({ t: 'num', v: parseFloat(num[0].replace(',', '.')), at: i }); i += num[0].length; continue; }
    const name = /^[\p{L}_][\p{L}\p{N}_]*/u.exec(s.slice(i));
    if (name) { out.push({ t: 'name', v: name[0], at: i }); i += name[0].length; continue; }
    const op = { '+': '+', '-': '-', '−': '-', '*': '*', '×': '*', '·': '*', '/': '/', '÷': '/', '(': '(', ')': ')', '°': '°' }[c];
    if (!op) throw new ParamError('char', 'Cannot read “{c}” in “{text}”.', { c, text: s.trim() });
    out.push({ t: op, at: i });
    i++;
  }
  return out;
}

/** text -> a tree: ['num', v] | ['ref', name] | ['neg', a] | [op, a, b]. Throws ParamError. */
export function parse(text) {
  const src = String(text ?? '').trim().replace(/^=\s*/, '');
  if (!src) throw new ParamError('empty', 'Type a value or an expression.');
  const tk = tokens(src);
  let i = 0;
  const peek = () => tk[i], take = () => tk[i++];
  const end = () => new ParamError('end', 'The expression “{text}” is not finished.', { text: src });
  const unit = (node) => { // (a unit after a value: skipped — values are mm or °)
    const n = peek();
    if (n && (n.t === '°' || (n.t === 'name' && UNITS.has(n.v)))) i++;
    return node;
  };
  const primary = () => {
    const n = take();
    if (!n) throw end();
    if (n.t === 'num') return unit(['num', n.v]);
    if (n.t === 'name') return unit(['ref', n.v]);
    if (n.t === '(') {
      const e = sum();
      if (peek()?.t !== ')') throw new ParamError('paren', 'A bracket is not closed in “{text}”.', { text: src });
      i++;
      return unit(e);
    }
    if (n.t === '-' || n.t === '+') { const a = primary(); return n.t === '-' ? ['neg', a] : a; }
    throw new ParamError('char', 'Cannot read “{c}” in “{text}”.', { c: n.t, text: src });
  };
  const product = () => {
    let a = primary();
    while (peek()?.t === '*' || peek()?.t === '/') { const op = take().t; a = [op, a, primary()]; }
    return a;
  };
  const sum = () => {
    let a = product();
    while (peek()?.t === '+' || peek()?.t === '-') { const op = take().t; a = [op, a, product()]; }
    return a;
  };
  const tree = sum();
  if (i < tk.length) throw new ParamError(tk[i].t === ')' ? 'paren' : 'extra', 'Something extra after the expression: “{rest}”.', { rest: src.slice(tk[i].at) });
  return tree;
}

/** The names an expression uses. */
export function refs(tree, out = new Set()) {
  if (tree[0] === 'ref') out.add(tree[1]);
  else if (tree[0] !== 'num') for (const x of tree.slice(1)) refs(x, out);
  return out;
}

/** A tree's value; value(name) gives a parameter's (throws for an unknown one). */
export function calc(tree, value) {
  const [op, a, b] = tree;
  if (op === 'num') return a;
  if (op === 'ref') return value(a);
  if (op === 'neg') return -calc(a, value);
  const x = calc(a, value), y = calc(b, value);
  if (op === '+') return x + y;
  if (op === '-') return x - y;
  if (op === '*') return x * y;
  if (y === 0) throw new ParamError('zero', 'Division by zero.');
  return x / y;
}

const unknown = (name) => new ParamError('unknown', 'There is no parameter “{name}” — type {name} = 100 to make it.', { name });

/** Every parameter's value: list [{name, expr}] -> {values: {name: number}, errors: {name: message}} (a parameter that
 *  refers to one with an error, or round in a circle, has an error too). */
export function evaluateAll(list) {
  const byName = new Map((list || []).map((p) => [p.name, p]));
  const values = {}, errors = {}, codes = {}, state = {};
  const visit = (name, path) => {
    if (state[name] === 'done') { if (errors[name]) throw new ParamError('bad', 'The parameter “{name}” has an error: {why}', { name, why: errors[name] }); return values[name]; }
    if (state[name] === 'busy') throw new ParamError('cycle', 'The parameters refer to each other in a circle: {names}.', { names: [...path.slice(path.indexOf(name)), name].join(' → ') });
    const p = byName.get(name);
    if (!p) throw unknown(name);
    state[name] = 'busy';
    try {
      const v = calc(parse(p.expr), (n) => visit(n, [...path, name]));
      if (!Number.isFinite(v)) throw new ParamError('zero', 'Division by zero.');
      values[name] = v;
    } catch (e) {
      if (!(e instanceof ParamError)) throw e;
      errors[name] = e.message;
      codes[name] = e.code;
      state[name] = 'done';
      throw e;
    }
    state[name] = 'done';
    return values[name];
  };
  for (const p of list || []) { try { visit(p.name, []); } catch { /* (its error is in errors) */ } }
  return { values, errors, codes };
}

/** What a field's text says: a number, an expression or "name = expression" (a new / changed parameter).
 *  -> {value, expr: what the field keeps (null: a plain number), assign?: {name, expr}}; throws ParamError.
 *  list: the parameters there are (an assignment is checked with it: no circles). */
export function readField(text, list) {
  const s = String(text ?? '').trim();
  if (isPlain(s)) return { value: parseFloat(s.replace(',', '.')), expr: null };
  const m = /^([\p{L}_][\p{L}\p{N}_]*)\s*=\s*(.*)$/u.exec(s);
  if (m && !UNITS.has(m[1])) {
    const [, name, rhs] = m;
    const next = [...(list || []).filter((p) => p.name !== name), { name, expr: rhs.trim() }];
    const r = evaluateAll(next);
    if (r.errors[name]) throw Object.assign(new Error(r.errors[name]), { code: r.codes[name], en: r.errors[name] });
    return { value: r.values[name], expr: name, assign: { name, expr: rhs.trim() } };
  }
  if (s.replace(/^=/, '').includes('=')) throw new ParamError('name', 'A parameter name starts with a letter: L, D2, wall.');
  const { values, errors } = evaluateAll(list);
  const v = calc(parse(s), (n) => {
    if (errors[n]) throw new ParamError('bad', 'The parameter “{name}” has an error: {why}', { name: n, why: errors[n] });
    if (!(n in values)) throw unknown(n);
    return values[n];
  });
  if (!Number.isFinite(v)) throw new ParamError('zero', 'Division by zero.');
  return { value: v, expr: s.replace(/^=\s*/, '') };
}

/** An expression's value with these parameter values; throws ParamError. */
export function evalText(expr, values) {
  const v = calc(parse(expr), (n) => { if (!(n in values)) throw unknown(n); return values[n]; });
  if (!Number.isFinite(v)) throw new ParamError('zero', 'Division by zero.');
  return v;
}

/** An expression's value with these values (null: it cannot be worked out now). */
export function valueOf(expr, values) {
  try { return evalText(expr, values); } catch { return null; }
}

/** The text and scale of an expr entry ("L/2", or {x: "L", k: 0.5} for a size shown as a radius). */
export const exprText = (e) => (typeof e === 'string' ? e : e?.x ?? '');
const exprScale = (e) => (typeof e === 'string' ? 1 : +e?.k || 1);

/** Put the values in: every object in `root` (its arrays and objects, deep) with an `expr` gets its numbers worked
 *  out again. -> [{obj, key, from, to}] that changed (an expression that cannot be worked out keeps its number). */
export function resolveIn(root, values) {
  const out = [];
  const walk = (o, depth) => {
    if (!o || typeof o !== 'object' || depth > 12) return;
    if (Array.isArray(o)) {
      if (!o.length || typeof o[0] === 'number') return; // (coordinates)
      for (const x of o) walk(x, depth + 1);
      return;
    }
    if (ArrayBuffer.isView(o)) return;
    if (o.expr && typeof o.expr === 'object' && !Array.isArray(o.expr)) {
      for (const [k, e] of Object.entries(o.expr)) {
        const v = valueOf(exprText(e), values);
        if (v === null) continue;
        const to = +(v / exprScale(e)).toFixed(9);
        if (o[k] !== to) { out.push({ obj: o, key: k, from: o[k], to }); o[k] = to; }
      }
    }
    for (const [k, x] of Object.entries(o)) if (k !== 'expr' && x && typeof x === 'object') walk(x, depth + 1);
  };
  walk(root, 0);
  return out;
}

/** Does something in root use one of these names (all: any parameter)? */
export function uses(root, names = null) {
  let hit = false;
  const walk = (o, depth) => {
    if (hit || !o || typeof o !== 'object' || depth > 12 || ArrayBuffer.isView(o)) return;
    if (Array.isArray(o)) { if (o.length && typeof o[0] !== 'number') for (const x of o) walk(x, depth + 1); return; }
    if (o.expr && typeof o.expr === 'object') {
      for (const e of Object.values(o.expr)) {
        try { if (!names || [...refs(parse(exprText(e)))].some((n) => names.has(n))) { hit = true; return; } } catch { /* (a bad one: not a use) */ }
      }
    }
    for (const [k, x] of Object.entries(o)) if (k !== 'expr' && x && typeof x === 'object') walk(x, depth + 1);
  };
  walk(root, 0);
  return hit;
}

// ---------------------------------------------------------------------------------------------- the store
/** The project's parameters: the list, their values, its own undo history (Ctrl+Z takes a parameter change back
 *  when it was the last thing done — History.first). onChange(values, names): every part follows (paramsui.js). */
class ParamStore {
  constructor() {
    this.list = [];
    this.values = {};
    this.errors = {};
    this.onChange = () => {};
    this.mine = { undo: 0, redo: 0 }; // (how many steps on top of the undo / redo stacks are a parameter's)
    this.history = new History({ capture: () => this.list, restore: (s) => this.put(s, null) });
    History.committed = (h) => { if (h !== this.history) this.mine = { undo: 0, redo: 0 }; };
    History.first = (dir, h, probe) => {
      if (h === this.history) return null;
      const n = dir < 0 ? this.mine.undo : this.mine.redo;
      if (!n || !(dir < 0 ? this.history.canUndo() : this.history.canRedo())) return null;
      if (probe) return true;
      if (dir < 0) { this.mine.undo--; this.mine.redo++; } else { this.mine.redo--; this.mine.undo++; }
      return this.history.go(dir).then(() => true);
    };
    this.history.reset();
  }

  get(name) { return this.list.find((p) => p.name === name) || null; }
  evaluate() { ({ values: this.values, errors: this.errors } = evaluateAll(this.list)); }

  /** A new list in (an undo, a project opened): the values worked out, the parts told (changed: the names that
   *  changed, null: all). */
  async put(list, changed) {
    const old = this.values;
    this.list = structuredClone(list || []);
    this.evaluate();
    const names = changed || new Set([...Object.keys(old), ...Object.keys(this.values)].filter((n) => old[n] !== this.values[n]));
    await this.onChange(this.values, names);
  }

  /** A project opened: its parameters (no undo step). */
  load(list) {
    this.list = Array.isArray(list) ? list.filter((p) => p && NAME_RE.test(p.name) && typeof p.expr === 'string').map((p) => ({ name: p.name, expr: p.expr })) : [];
    this.evaluate();
    this.history.reset();
    this.mine = { undo: 0, redo: 0 };
  }

  toJSON() { return this.list.map((p) => ({ ...p })); }

  /** Set (or make) a parameter: name = expr. Checked first (a bad expression, a circle: ParamError, nothing changes).
   *  -> its value. An undo step. */
  async set(name, expr) {
    name = String(name ?? '').trim();
    expr = String(expr ?? '').trim();
    if (!NAME_RE.test(name) || UNITS.has(name)) throw new ParamError('name', 'A parameter name starts with a letter: L, D2, wall.');
    const r = readField(`${name} = ${expr}`, this.list);
    const next = this.get(name) ? this.list.map((p) => (p.name === name ? { name, expr } : p)) : [...this.list, { name, expr }];
    await this.commit(next);
    return r.value;
  }

  /** Delete a parameter: the numbers that used it keep their values (their expressions go — paramsui.js). */
  async remove(name) {
    if (!this.get(name)) return;
    await this.commit(this.list.filter((p) => p.name !== name), new Set([name]));
  }

  async commit(next, changed = null) {
    const old = this.values;
    this.list = next;
    this.evaluate();
    if (this.history.commit()) { this.mine.undo++; this.mine.redo = 0; }
    const names = changed || new Set([...Object.keys(old), ...Object.keys(this.values)].filter((n) => old[n] !== this.values[n]));
    await this.onChange(this.values, names);
  }
}

export const params = new ParamStore();
