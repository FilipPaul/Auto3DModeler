// 𝑥 Project parameters on screen (params.js holds them): the small 𝑥 Parameters widget in the left column of the 3D
// model and the assembly (hidden while there are none: "L = 100" typed in any number field makes the first), the
// number fields that take an expression (exprField), and every part following a changed parameter — the part on
// screen rebuilt as usual, the others through the same /api/model/rebuild (the ⚙ jobs list names them), the
// assembly's joints and parts too.
import { t } from './i18n.js';
import { confirmIn } from './choose.js';
import { leftDock } from './leftdock.js';
import { params, readField, isPlain, resolveIn, uses, exprText, ParamError } from './params.js';
import { fetchRebuild } from './modeler/packed.js';
import { newRid } from './progressbox.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v) => (+(+v).toFixed(3)).toString();
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
const TIP = 'A number — or an expression of the project’s parameters: L, L/2 + 5, =D. “L = 100” makes the parameter L.';
let hooks = { toast: () => {} };

/** Keep an expression in obj.expr[key] (null: none — the plain number). */
export function setExpr(obj, key, expr) {
  if (!obj) return;
  if (expr) obj.expr = { ...(obj.expr || {}), [key]: expr };
  else if (obj.expr && key in obj.expr) {
    delete obj.expr[key];
    if (!Object.keys(obj.expr).length) delete obj.expr;
  }
}

/** What a field's text makes: {value, expr, assign?} — an assignment ("L = 100") makes / changes the parameter at
 *  once (an undo step of its own) and the field keeps "L". Throws ParamError. */
export function takeField(text) {
  const r = readField(text, params.list);
  if (r.assign) params.set(r.assign.name, r.assign.expr).catch((e) => hooks.toast(e.message, 'error', 6000));
  return r;
}

/** A number field of a tool's panel that also takes an expression of the parameters. owner(): the object its number
 *  is in (the step), key: the number's key there. The panel's own listeners get a plain number, as before: an
 *  expression is worked out first and its value handed to them; when they took it, the expression is kept beside it
 *  (owner.expr) — shown as "L/2 = 50" while the field is not being typed in. A bad one: said under the mouse and in
 *  red, the number stays as it was. */
export function exprField(inp, { owner, key }) {
  if (!inp || inp.dataset.px) return;
  inp.dataset.px = '1';
  if (inp.type === 'number') { const v = inp.value; inp.type = 'text'; inp.value = v; }
  Object.assign(inp, { autocomplete: 'off', spellcheck: false });
  inp.classList.add('px-in');
  const tip0 = inp.title;
  inp.title = [tip0, t(TIP)].filter(Boolean).join('\n');
  let inner = false, plain = false, shown = null;
  const exprNow = () => { const e = owner()?.expr?.[key]; return e ? exprText(e) : null; };
  const show = () => { // "L/2 = 50" while not typed in; the expression alone while typing
    const e = exprNow(), o = owner();
    shown = e && document.activeElement !== inp && Number.isFinite(+o?.[key]) ? `${e} = ${fmt(o[key])}` : null;
    inp.value = shown ?? e ?? inp.value;
    inp.classList.toggle('px-on', !!e);
  };
  const bad = (msg) => {
    inp.classList.toggle('px-bad', !!msg);
    inp.title = msg ? `⚠ ${msg}` : [tip0, t(TIP)].filter(Boolean).join('\n');
  };
  const raw = () => (shown !== null && inp.value === shown ? exprNow() : inp.value);
  const text = () => raw().trim();
  const pre = (e) => {
    if (inner) return;
    const typed = raw(), s = typed.trim(), at = [inp.selectionStart, inp.selectionEnd];
    plain = s === '' || isPlain(s);
    if (plain) { bad(null); return; }
    e.stopImmediatePropagation();
    let r;
    try { r = readField(s, params.list); } catch (err) {
      if (!(err instanceof ParamError) && !err.code) throw err;
      bad(err.message);
      if (e.type === 'change') hooks.toast(err.message, 'warning', 6000);
      return;
    }
    bad(null);
    const o = owner(), before = o?.expr?.[key], commit = e.type === 'change';
    let keep = r.expr; // (what the field keeps; a parameter still being typed: only its value so far)
    if (r.assign) { if (commit) takeField(s); else keep = null; }
    setExpr(o, key, keep); // (kept before the panel draws itself again)
    inner = true;
    try {
      inp.value = fmt(r.value);
      inp.dispatchEvent(new Event(e.type, { bubbles: true }));
    } finally { inner = false; }
    if (o && Math.abs(+o[key] - r.value) > 1e-9) setExpr(o, key, before ?? null); // (the panel did not take it)
    inp.value = r.assign && commit ? r.assign.name : typed; // (as typed, the caret where it was)
    if (!inp.isConnected) return;
    if (!commit && document.activeElement === inp) inp.setSelectionRange(...at);
    inp.classList.toggle('px-on', !!exprNow());
  };
  const post = () => { if (!inner && plain) { setExpr(owner(), key, null); inp.classList.remove('px-on'); } };
  for (const ev of ['input', 'change']) {
    inp.addEventListener(ev, pre, true);
    inp.addEventListener(ev, post);
  }
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !isPlain(text())) inp.dispatchEvent(new Event('change', { bubbles: true })); // (an assignment: made before the panel's OK)
    if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && isPlain(inp.value)) { // (as a number field did)
      e.preventDefault();
      const st = parseFloat(inp.step) || 1, v = parseFloat(inp.value.replace(',', '.')) + (e.key === 'ArrowUp' ? st : -st);
      inp.value = fmt(v);
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }, true);
  inp.addEventListener('focus', () => { if (shown !== null && inp.value === shown) { inp.value = exprNow(); shown = null; inp.select(); } });
  inp.addEventListener('blur', () => setTimeout(() => { if (inp.isConnected && document.activeElement !== inp) show(); }, 0));
  show();
}

/** The label of a size with an expression: "50" -> "L/2 = 50", "Ø8" -> "Ø D = 8". */
export function exprLabel(text, expr) {
  if (!expr) return text;
  const m = /^(.*?)(-?[\d.]+)(°?)$/.exec(text);
  return m ? `${m[1]}${m[1] && !/\s$/.test(m[1]) ? ' ' : ''}${expr} = ${m[2]}${m[3]}` : `${text} (${expr})`;
}

// ---------------------------------------------------------------------------------------------- the widget
class ParamsPanel {
  constructor(ws) {
    this.ws = ws;
    this.w = `params-${ws}`;
    this.box = leftDock.addWidget(this.w, ws, { title: '𝑥 Parameters', h: 120 });
    this.box.classList.add('px-box');
  }

  render() {
    const on = params.list.length > 0;
    leftDock.show(this.w, on);
    if (!this.list) this.build();
    const nw = this.box.querySelector('.px-new');
    nw.placeholder = t('New: L = 100');
    nw.title = t('A new parameter: its name, =, its value or an expression (t = L / 20)');
    if (this.list.contains(document.activeElement)) return; // (being typed in: drawn when done)
    const used = usedBy();
    this.list.innerHTML = params.list.map((p) => {
      const err = params.errors[p.name], v = params.values[p.name], where = used[p.name] || [];
      return `<div class="px-row ${err ? 'bad' : ''}" data-px="${esc(p.name)}">
        <b class="px-name" data-no-i18n title="${esc(where.length ? t2('Used in: {parts}', { parts: where.join(', ') }) : t('Not used yet — type its name in a number field'))}">${esc(p.name)}</b><span class="px-eq">=</span>
        <input class="px-expr" data-pxe="${esc(p.name)}" value="${esc(p.expr)}" spellcheck="false" autocomplete="off" title="${esc(err ? `⚠ ${err}` : t('Its value or an expression of the others (L / 20) — Enter: every part that uses it follows'))}">
        <span class="px-res" data-no-i18n>${err ? '⚠' : isPlain(p.expr) ? '' : `= ${fmt(v)}`}</span>
        <button class="mini px-del" data-pxdel="${esc(p.name)}" title="${esc(t('Delete it (the numbers that use it keep their values)'))}">✕</button></div>`;
    }).join('');
    for (const inp of this.list.querySelectorAll('[data-pxe]')) {
      const name = inp.dataset.pxe, put = () => {
        if (inp.value.trim() === params.get(name)?.expr) return;
        params.set(name, inp.value).catch((e) => { hooks.toast(e.message, 'warning', 6000); inp.classList.add('px-bad'); inp.title = `⚠ ${e.message}`; inp.value = params.get(name)?.expr ?? ''; });
      };
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') inp.blur(); if (e.key === 'Escape') { inp.value = params.get(name)?.expr ?? ''; inp.blur(); } });
      inp.addEventListener('change', put);
      inp.addEventListener('blur', () => setTimeout(() => renderAll(), 0));
    }
    for (const b of this.list.querySelectorAll('[data-pxdel]')) {
      b.addEventListener('click', async () => {
        const name = b.dataset.pxdel, where = usedBy()[name] || [];
        if (where.length && !(await confirmIn(t2('{name} is used in: {parts}. Delete it? Those numbers keep their values.', { name, parts: where.join(', ') }), { ok: 'Delete', danger: true }))) return;
        params.remove(name);
      });
    }
  }

  /** The list's place and the "New: L = 100" field under it (kept as it is: several typed in a row). */
  build() {
    this.box.innerHTML = '<div class="px-list"></div><input class="px-new" spellcheck="false" autocomplete="off">';
    this.list = this.box.querySelector('.px-list');
    const nw = this.box.querySelector('.px-new');
    const add = () => {
      const s = nw.value.trim();
      if (!s) return;
      const m = /^([^=]+)=(.*)$/.exec(s);
      if (!m) { hooks.toast(t('Type it as name = value, e.g. L = 100.'), 'warning', 5000); return; }
      params.set(m[1], m[2]).catch((e) => { hooks.toast(e.message, 'warning', 6000); nw.classList.add('px-bad'); nw.title = `⚠ ${e.message}`; });
      if (params.get(m[1].trim())?.expr === m[2].trim()) { nw.value = ''; renderAll(); } // (taken: listed at once)
    };
    nw.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') add(); if (e.key === 'Escape') { nw.value = ''; nw.blur(); } });
    nw.addEventListener('input', () => { nw.classList.remove('px-bad'); });
  }
}

const panels = [];
const renderAll = () => panels.forEach((p) => p.render());

/** Parameter name -> the parts that use it (by name). */
function usedBy() {
  const out = {}, P = hooks.project;
  for (const p of P?.parts || []) {
    if (p.kind !== 'model' && p.kind !== 'assembly') continue;
    const data = liveData(p);
    for (const q of params.list) if (data && uses(data, new Set([q.name]))) (out[q.name] ||= []).push(p.name);
  }
  return out;
}

/** A part's data as it is now (the one on screen: the live object, edited in place). */
function liveData(p) {
  const P = hooks.project;
  if (p.id === P.active && p.data === 'live') return p.kind === 'model' ? hooks.modeler.part : p.kind === 'assembly' ? hooks.assembly.doc : null;
  return p.data && typeof p.data === 'object' ? p.data : null;
}

/** A part not on screen built again with its new numbers (its sketches solved again on the server: their points
 *  kept) — through the usual rebuild, so the ⚙ jobs list shows it by name. -> {ok, volume, issues}. */
async function rebuildStored(p) {
  try {
    const { res, r } = await fetchRebuild({ features: p.data.features, threads: p.data.threads }, newRid('x'), p.name);
    if (!res.ok || r.cancelled) return { ok: false, issues: [r.error || 'Cancelled'] };
    for (const s of r.features || []) {
      const f = s.update && p.data.features.find((g) => g.id === s.id);
      if (f) Object.assign(f, structuredClone(s.update));
    }
    return { ok: !!r.ok, volume: r.body?.volume ?? null, issues: (r.features || []).filter((s) => !s.ok).flatMap((s) => s.issues || []) };
  } catch (e) { return { ok: false, issues: [e.message] }; }
}

/** The parameters changed: every number that uses one gets its new value; the parts with a changed number are built
 *  again (the one on screen as usual), an assembly on screen places its parts again. -> [{part, kind, ok, volume?,
 *  issues}] of the parts that changed (for the AI). */
async function follow(values) {
  const { project: P, modeler: M, assembly: A } = hooks;
  const jobs = [];
  let models = 0;
  for (const p of P.parts) {
    if (p.kind !== 'model' && p.kind !== 'assembly') continue;
    const data = liveData(p), live = p.id === P.active && p.data === 'live';
    if (!data) continue;
    const ch = resolveIn(p.kind === 'model' ? data.features : data.mates, values);
    if (live && p.kind === 'model') {
      if (M.cmd) ch.push(...resolveIn(M.cmd.feature, values));
      if (M.sk && resolveIn(M.sk.f, values).length) M.sk.relock?.(() => {}); // (the open sketch: solved with its new sizes)
    }
    if (!ch.length) continue;
    if (p.kind === 'model') models++;
    const said = (r) => {
      if (r.issues?.length) hooks.toast(`${p.name}: ${t(r.issues[0])}`, 'warning', 7000);
      return { part: p.name, kind: p.kind, ...r };
    };
    if (live && p.kind === 'model') {
      M.render();
      jobs.push(M.rebuild().then(() => said({ ok: !!M.result?.ok, volume: M.result?.body?.volume ?? null, issues: (M.result?.features || []).filter((s) => !s.ok).flatMap((s) => s.issues || []) })));
    } else if (live) {
      A.applyMates();
      A.render?.();
      jobs.push(Promise.resolve({ part: p.name, kind: p.kind, ok: true }));
    } else if (p.kind === 'model') jobs.push(rebuildStored(p).then(said));
    else jobs.push(Promise.resolve({ part: p.name, kind: p.kind, ok: true }));
  }
  const cur = P.current;
  const asm = cur?.kind === 'assembly' && cur.data === 'live' && models ? A.refresh() : null;
  renderAll();
  window.dispatchEvent(new Event('a3d:changed')); // (autosave)
  const out = await Promise.all(jobs);
  await asm;
  return out;
}

/** Start: the widgets, the store's hook, an undo of a part putting its numbers as the parameters say now.
 *  h: {project, modeler, assembly, toast}. */
export function initParams(h) {
  hooks = h;
  panels.push(new ParamsPanel('model'), new ParamsPanel('assembly'));
  params.onChange = (values) => follow(values);
  for (const hist of [h.modeler.history, h.assembly.history]) { // (an older snapshot of a part: its numbers as the parameters say now)
    const restore = hist.restore;
    hist.restore = (s) => { resolveIn(s.features || s.mates || [], params.values); return restore(s); };
  }
  params.history.onChange = () => { h.modeler.updateUndo?.(); h.assembly.updateUndo?.(); }; // (↶ may now take a parameter back)
  window.addEventListener('a3d:lang', renderAll);
  renderAll();
}

// ---------------------------------------------------------------------------------------------- the AI's tools
/** Numbers of an AI tool's arguments that are expressions ("L / 2"; "L = 100" makes L): -> {args with their values,
 *  expr: {key: expression}, plain: [keys given as plain numbers]}. Throws with the reason (English, for the AI). */
export function exprArgs(args, keys) {
  const out = { ...args }, expr = {}, plain = [];
  for (const k of keys) {
    const v = args?.[k];
    if (typeof v === 'number') { plain.push(k); continue; }
    if (typeof v !== 'string') continue;
    if (isPlain(v)) { out[k] = parseFloat(v.replace(',', '.')); plain.push(k); continue; }
    let r;
    try { r = takeField(v); } catch (e) { throw new Error(`${k}: ${e.en || e.message} (get_parameters lists the parameters)`); }
    out[k] = r.value;
    expr[k] = r.expr;
  }
  return { args: out, expr, plain };
}

/** The expressions kept on the step built from them (only where it took the value); plain numbers drop theirs. */
export function keepExprs(f, { args, expr, plain }) {
  if (!f) return;
  for (const k of plain) setExpr(f, k, null);
  for (const [k, e] of Object.entries(expr)) if (Math.abs(+f[k] - args[k]) < 1e-9) setExpr(f, k, e);
}

const listOut = () => {
  const used = usedBy();
  return params.list.map((p) => ({ name: p.name, expr: p.expr, ...(params.errors[p.name] ? { error: params.errors[p.name] } : { value: +(+params.values[p.name]).toFixed(6) }), used_in: used[p.name] || [] }));
};

/** get_parameters / set_parameter (they work in every workspace). */
export function paramHandlers() {
  return {
    get_parameters: async () => ({ text: JSON.stringify({ parameters: listOut(), how: 'Numbers of steps (add_feature / edit_feature), sketch sizes (sketch_dim) and joints may be expressions of these: "L / 2", "D + 1"; "L = 100" there makes L.' }) }),
    set_parameter: async ({ name, value, delete: del } = {}) => {
      if (!name) throw new Error('name: the parameter\'s name (a letter first: L, D2, wall).');
      if (del) {
        if (!params.get(name)) throw new Error(`No parameter “${name}” — get_parameters lists them.`);
        await params.remove(name);
        return { text: JSON.stringify({ deleted: name, parameters: listOut() }) };
      }
      if (value === undefined || value === null || String(value).trim() === '') throw new Error('value: a number or an expression of the other parameters ("L / 20").');
      let rebuilt = [];
      const was = params.onChange;
      params.onChange = async (values) => { rebuilt = await follow(values); };
      try { await params.set(name, String(value)); } catch (e) { throw new Error(e.en || e.message); } finally { params.onChange = was; }
      return { text: JSON.stringify({ parameters: listOut(), rebuilt: rebuilt.map((r) => ({ ...r, ...(r.volume != null ? { volume: +r.volume.toFixed(3) } : {}) })) }) };
    },
  };
}

/** A project opened: its parameters, the widgets drawn. */
export function loadParams(list) {
  params.load(list);
  renderAll();
}

export { renderAll as renderParams };
