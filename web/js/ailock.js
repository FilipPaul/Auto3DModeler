// 🔒 AI lock: parts and assemblies the AI must not change — bought parts, parts already made, approved designs. Only
// the user locks and unlocks (the project tree's and the assembly list's 🔒, several at once from the suggestions and
// the rows' ⋯ menu, the properties panel with a reason: bought / made / approved); the user is never stopped by it.
// The AI's tool calls (agent.js startBridge) pass guard() first: a call that would change a locked part — its steps,
// sketches, material, look, name, the parameters it uses; a locked assembly's parts, joints, harnesses, mechanisms —
// is refused with a plain answer, so the AI can take another way. Adding joints (to a locked part, into a locked
// sub-assembly), inserting, measuring, drawings and the BOM stay open. Library parts are always locked for the AI.
// The lock is kept on the project's part (`ai_lock: {reason}`, saved in the .a3d); its changes are one undo step each.
import { t } from './i18n.js';
import { History } from './history.js';
import { params, parse, refs } from './params.js';
import { suggestMenu } from './suggest.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
export const REASONS = ['bought', 'made', 'approved'];
const REASON_LABEL = { bought: 'bought', made: 'made', approved: 'approved' };
const WHY_CS = { bought: 'koupený díl', made: 'vyrobený díl', approved: 'schválený návrh', library: 'díl z knihovny' };

let ctx = null; // {state, project, assembly, modeler, toast, refresh()}
let aiCalling = 0; // (a tool call of the AI running: its changes are not the user's — no note)
const told = new Set(); // (the parts whose "locked for the AI" note the user saw in this session)

// ------------------------------------------------------------------------------------------- what is locked
const partOf = (id) => ctx?.project.parts.find((p) => p.id === id) || null;
const dataOf = (p) => { try { return ctx.project.dataOf(p); } catch { return null; } };

/** A part's AI lock -> {reason, library?} or null. A library part is always locked (unless the user opened it to
 *  change the library's own item: ✎ Edit in the library). */
export function lockOf(idOrPart) {
  const p = typeof idOrPart === 'string' ? partOf(idOrPart) : idOrPart;
  if (!p) return null;
  if (p.ai_lock) return { reason: p.ai_lock.reason || null };
  if (p.kind === 'model') {
    const d = dataOf(p);
    if (d?.library && !d.libEdit) return { reason: 'library', library: true };
  }
  return null;
}

/** For the AI's reports (list_parts, get_model, get_assembly): {ai_locked, ai_lock_reason} or {}. */
export function lockInfo(id) {
  const l = lockOf(id);
  return l ? { ai_locked: true, ...(l.reason ? { ai_lock_reason: l.reason } : {}) } : {};
}

/** The answer to a refused call (Czech, as the owner wrote it; the AI reads it). */
export function refusal(p) {
  if (typeof p === 'string') p = partOf(p) || { name: p };
  const l = lockOf(p), asm = p.kind === 'assembly';
  return `🔒 ${p.name} je ${asm ? 'zamčená' : 'zamčený'} pro AI (${WHY_CS[l?.reason] || (asm ? 'schválená sestava' : 'koupený / vyrobený díl')}) — tohle se na ${asm ? 'ní' : 'něm'} měnit nesmí; vazby přidat lze. `
    + '(AI lock: only the user can unlock it. Add joints, change another part, or ask the user.)';
}

// ------------------------------------------------------------------------------------------- the user's side
let mine = { undo: 0, redo: 0 }; // (how many steps on top of the undo / redo stacks are a lock's — as params.js)
const locksNow = () => Object.fromEntries((ctx?.project.parts || []).filter((p) => p.ai_lock).map((p) => [p.id, p.ai_lock]));
const hist = new History({ capture: locksNow, restore: (s) => { put(s); } });

function put(s) {
  for (const p of ctx.project.parts) { if (s[p.id]) p.ai_lock = { ...s[p.id] }; else delete p.ai_lock; }
  changed();
}

function changed() {
  ctx.refresh?.();
  window.dispatchEvent(new Event('a3d:changed')); // (autosave)
}

/** Lock (on) or unlock these parts for the AI; reason: kept as it was unless given ('' takes it away). One undo step. */
export function setLock(ids, on, reason) {
  if (!ctx) return 0;
  if (!mine.undo && !mine.redo) hist.reset(); // (other steps since: the locks as they are now are where an undo goes back to)
  let n = 0;
  for (const id of new Set(ids)) {
    const p = partOf(id);
    if (!p || (on && lockOf(p)?.library && !p.ai_lock)) { if (p && on) n++; continue; } // (a library part: locked anyway)
    if (on) {
      const r = reason === undefined ? p.ai_lock?.reason : reason;
      p.ai_lock = REASONS.includes(r) ? { reason: r } : {};
      n++;
    } else if (p.ai_lock) { delete p.ai_lock; n++; }
  }
  if (hist.commit()) { mine.undo++; mine.redo = 0; }
  changed();
  return n;
}

// Ctrl+Z / ↶ in any workspace takes a lock change back when it was the last thing done (History.first, as the 𝑥
// parameters do — params.js; their hooks kept and called after these)
{
  const prevFirst = History.first, prevCommitted = History.committed;
  History.committed = (h) => { prevCommitted?.(h); if (h !== hist) mine = { undo: 0, redo: 0 }; };
  History.first = (dir, h, probe) => {
    if (h === hist) return null;
    const n = dir < 0 ? mine.undo : mine.redo;
    if (n && (dir < 0 ? hist.undo.length : hist.redo.length)) {
      if (probe) return true;
      if (dir < 0) { mine.undo--; mine.redo++; } else { mine.redo--; mine.undo++; }
      return hist.go(dir).then(() => true);
    }
    return prevFirst ? prevFirst(dir, h, probe) : null;
  };
  hist.onChange = () => { ctx?.modeler?.updateUndo?.(); ctx?.assembly?.updateUndo?.(); };
}

/** The 🔒 toggle of a row (the project tree, the assembly list): shown when locked, on hover when not. */
export function lockBtn(id) {
  const l = lockOf(id);
  if (!l) return `<button class="mini ai-lock" data-ailock="${esc(id)}" title="${esc(t('Lock it for the AI: the AI may add joints to it, but not change it'))}">🔒</button>`;
  if (l.library) return `<span class="mini ai-lock on ai-lib" title="${esc(t('Library part — always locked for the AI'))}">🔒</span>`;
  return `<button class="mini ai-lock on" data-ailock="${esc(id)}" title="${esc(t('Locked for the AI — click to unlock'))}${l.reason ? ` (${esc(t(REASON_LABEL[l.reason]))})` : ''}">🔒</button>`;
}

/** The suggestion rows for these parts (several chosen; a row's ⋯ menu): 🔒 Lock for the AI (n) / 🔓 Unlock (n). */
export function lockItems(ids, rank = 6) {
  const ps = [...new Set(ids)].map(partOf).filter(Boolean);
  const open = ps.filter((p) => !lockOf(p)), mineL = ps.filter((p) => p.ai_lock);
  return [
    ...(open.length ? [{ icon: '🔒', label: t2('Lock for the AI ({n})', { n: open.length }), rank, title: t('The AI may add joints to them, but not change them (bought, made or approved parts)'),
      run: () => { setLock(open.map((p) => p.id), true); ctx.toast(t2('Locked for the AI: {n}', { n: open.length }), 'ok', 3000); } }] : []),
    ...(mineL.length ? [{ icon: '🔓', label: t2('Unlock for the AI ({n})', { n: mineL.length }), rank: rank + 0.5, title: t('The AI may change them again'),
      run: () => { setLock(mineL.map((p) => p.id), false); ctx.toast(t2('Unlocked for the AI: {n}', { n: mineL.length }), 'ok', 3000); } }] : []),
  ];
}

/** A row's ⋯ menu: the lock for that row's part — or for all chosen, when the row is one of them. */
export function lockMenu(at, ids, title = '') {
  const items = lockItems(ids, 0);
  if (!items.length) items.push({ icon: '🔒', label: t('Library part — always locked for the AI'), run: () => {} });
  suggestMenu(at, title, items);
}

/** The properties panel's row (a part, an assembly): 🔒 Locked for the AI with its toggle and the reason chips. */
export function lockPanel(box, id = ctx?.project.active) {
  const p = partOf(id), h = box.querySelector('h2');
  if (!p || !h) return;
  box.querySelector('.ai-lock-panel')?.remove();
  const l = lockOf(p), el = document.createElement('div');
  el.className = `ai-lock-panel${l ? ' on' : ''}`;
  el.innerHTML = l?.library
    ? `<span class="ai-lock-state">🔒 ${esc(t('Locked for the AI'))}</span> <span class="hint">${esc(t('Library part — always locked for the AI'))}</span>`
    : `<label class="ai-lock-state" title="${esc(t('The AI may add joints to it, but not change it — you can still change it'))}"><input type="checkbox" data-ailock-toggle ${l ? 'checked' : ''}> 🔒 ${esc(t('Locked for the AI'))}</label>
      ${l ? `<span class="ai-reasons">${REASONS.map((r) => `<button class="chip${l.reason === r ? ' on' : ''}" data-reason="${r}">${esc(t(REASON_LABEL[r]))}</button>`).join('')}</span>` : ''}`;
  h.after(el);
  el.querySelector('[data-ailock-toggle]')?.addEventListener('change', (e) => setLock([p.id], e.target.checked));
  for (const b of el.querySelectorAll('[data-reason]')) b.addEventListener('click', () => setLock([p.id], true, l.reason === b.dataset.reason ? '' : b.dataset.reason));
}

// a 🔒 / ⋯ in a row: handled here before the row's own click (that would open or choose the part)
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-ailock], [data-ailock-menu]');
  if (!b || !ctx) return;
  e.stopPropagation();
  e.preventDefault();
  if (b.dataset.ailock) { setLock([b.dataset.ailock], !lockOf(b.dataset.ailock)); return; }
  let ids = b.dataset.ailockMenu.split(',').filter(Boolean);
  if (ids[0]?.startsWith('@')) { // (a row of the assembly's list, "@I3" / "@I3/I2": all chosen when it is one of them)
    const key = ids[0].slice(1), keys = ctx.assembly.selKeys();
    ids = keysParts(keys.length > 1 && keys.includes(key) ? keys : [key]);
  }
  lockMenu(b, ids, ids.length > 1 ? t2('{n} parts chosen', { n: ids.length }) : partOf(ids[0])?.name || '');
}, true);

// the user changing a locked part by hand: a gentle note, once a part (never stopped) — only a step right after the
// user's own input (not a rebuild's late update, not the AI's)
let lastInput = 0;
for (const ev of ['pointerdown', 'keydown', 'change', 'input']) {
  document.addEventListener(ev, (e) => {
    lastInput = Date.now();
    if (e.isTrusted && clicking?.until !== Infinity) clicking = null; // (the user's own input after the AI's click: theirs again)
  }, true);
}
History.watchers.add((h, dir) => {
  if (dir !== 0 || aiCalling || !ctx || Date.now() - lastInput > 2000) return;
  const p = ctx.project.current;
  if (!p || told.has(p.id) || !lockOf(p) || (h !== ctx.modeler?.history && h !== ctx.assembly?.history)) return;
  told.add(p.id);
  ctx.toast(t(p.kind === 'assembly' ? 'The assembly is locked for the AI — you can still change it.' : 'The part is locked for the AI — you can still change it.'), 'info', 5000);
});

// ------------------------------------------------------------------------------------------- the AI's side
const PART_EDIT = new Set(['add_feature', 'edit_feature', 'delete_feature', 'turn_off_feature', 'rollback', 'sketch_auto_dims', 'sketch_dim',
  'sketch_trim', 'sketch_union', 'simplify_sketch', 'set_material', 'set_look', 'paint_faces', 'set_dimensions', 'set_make', 'set_part_options',
  'add_object', 'add_shape', 'add_design_layer', 'update_item', 'remove_item', 'add_dimension', 'drawing_delete', 'drawing_add', 'drawing_units',
  'drawing_set_size', 'undo']);
// in a locked assembly on screen: everything that changes it but adding joints
const ASM_EDIT = new Set(['insert_part', 'place_part', 'remove_from_assembly', 'add_fasteners', 'bolt_parts', 'set_travel', 'lock_motion', 'name_motion',
  'move_free', 'remove_joint', 'edit_joint', 'add_harness', 'edit_harness', 'edit_chain', 'library_pair', 'set_look', 'paint_faces', 'undo']);
// a part given by its place in the assembly: refused when it is inside a locked sub-assembly (moved, taken out …)
const INNER_EDIT = new Set(['place_part', 'move_free', 'remove_from_assembly', 'set_travel', 'lock_motion', 'name_motion']);

/** The parts along a placed part's path in the assembly on screen ("I3/I2" -> [I3's part, I2's part in it]). */
function pathParts(path) {
  const A = ctx.assembly, ids = String(path || '').split('/');
  let list = A.doc?.instances || [];
  const out = [];
  for (const id of ids) {
    const it = list.find((q) => q.id === id);
    if (!it) break;
    out.push(it.part);
    const p = partOf(it.part);
    list = p?.kind === 'assembly' ? (dataOf(p)?.instances || []) : [];
  }
  return out;
}

/** The parts of these rows of the assembly on screen ("I3", "I3/I2"), once each. */
export function keysParts(keys) { return [...new Set(keys.map((k) => pathParts(k).at(-1)).filter(Boolean))]; }

/** The parameters whose value follows this one (it, and those that use it, all the way). */
function following(name) {
  const out = new Set([name]);
  for (let grew = true; grew;) {
    grew = false;
    for (const q of params.list) {
      if (out.has(q.name)) continue;
      let r;
      try { r = refs(parse(q.expr)); } catch { continue; }
      if ([...r].some((n) => out.has(n))) { out.add(q.name); grew = true; }
    }
  }
  return out;
}

/** Does a part's data use one of these parameters? */
function usesAny(data, names) {
  let hit = false;
  const walk = (o, depth) => {
    if (hit || !o || typeof o !== 'object' || depth > 12 || ArrayBuffer.isView(o)) return;
    if (Array.isArray(o)) { if (o.length && typeof o[0] !== 'number') for (const x of o) walk(x, depth + 1); return; }
    if (o.expr && typeof o.expr === 'object') {
      for (const e of Object.values(o.expr)) {
        try { if ([...refs(parse(typeof e === 'string' ? e : e?.x ?? ''))].some((n) => names.has(n))) { hit = true; return; } } catch { /* (a bad one: not a use) */ }
      }
    }
    for (const [k, x] of Object.entries(o)) if (k !== 'expr' && x && typeof x === 'object') walk(x, depth + 1);
  };
  walk(data, 0);
  return hit;
}

const no = (p) => ({ text: refusal(p), error: true });

/** An AI tool call checked before it runs -> null (it may) or {text, error} (refused: a locked part it would change). */
export function guard(tool, args = {}) {
  if (!ctx) return null;
  const { state, project, assembly } = ctx, cur = project.current, ws = state.workspace;
  const named = (v) => project.parts.find((q) => q.id === v || q.name === v);
  if (tool === 'rename_part' || tool === 'delete_part') { const p = named(args.id); return p && lockOf(p) ? no(p) : null; }
  if (tool === 'take_part') { const p = named(args.part); return p && lockOf(p) ? no(p) : null; }
  if (tool === 'set_parameter') {
    if (args.delete || !args.name) return null; // (deleted: the numbers that used it keep their values — nothing is rebuilt)
    const names = following(String(args.name));
    const p = project.parts.find((q) => (q.kind === 'model' || q.kind === 'assembly') && lockOf(q) && usesAny(dataOf(q), names));
    return p ? { text: `${refusal(p)} The parameter ${args.name} drives it — set_parameter would rebuild it.`, error: true } : null;
  }
  if (ws === 'assembly' && cur?.kind === 'assembly') {
    if (ASM_EDIT.has(tool) || (tool === 'drive_mechanism' && (args.name != null || args.driver != null)) || (tool === 'library_add' && (args.to || 'assembly') === 'assembly')) {
      if (lockOf(cur)) return no(cur);
    }
    if (tool === 'set_look' || tool === 'paint_faces') { const p = partOf(pathParts(args.part).at(-1)); return p && lockOf(p) ? no(p) : null; }
    if (tool === 'bolt_parts') { // (it drills holes: in the part it starts at and the one it goes through — the others: assembly.js)
      for (const k of [args.part, args.through]) { const p = k ? partOf(pathParts(k).at(-1)) : null; if (p && lockOf(p)) return no(p); }
    }
    if (INNER_EDIT.has(tool) && String(args.part || '').includes('/')) {
      const subs = pathParts(args.part).slice(0, -1).map(partOf).filter(Boolean);
      const p = subs.find((q) => lockOf(q));
      if (p) return no(p);
    }
    return null;
  }
  if (cur && (PART_EDIT.has(tool) || tool === 'sheet_edit') && ws !== 'assembly' && lockOf(cur)) return no(cur); // (a locked drawing sheet: an approved drawing)
  return null;
}

/** Run an AI tool call with the lock checked (agent.js startBridge); its clicks (gui_action) watched as they change. */
export async function guarded(tool, args, run) {
  const r = guard(tool, args);
  if (r) return r;
  aiCalling++;
  try { return tool === 'gui_action' ? await clicked(run) : await run(); } finally { aiCalling--; }
}

// ------------------------------------------------------------------------------------------- the AI's clicks (gui_action)
// The AI may click the app as the user would: what that changes is checked where every change is recorded (History.veto,
// the undo step) — not by the button — so a step that would change a locked part or assembly is refused and put back,
// whichever button made it (a fillet from the suggestions, ✎ Edit in place, a dimension dragged, a field typed into). A
// joint added to a locked assembly stays allowed (as snap_faces); choosing, turning the view, measuring and hiding are
// no change. What changed without a step (a field not confirmed yet) is put back when the click is done; a rename or a
// delete of the part is refused where the project applies it (aiHolds).
let clicking = null; // {snap: {id: {name, data}}, until, refused: Set} — while the AI's click runs (and a moment after it: a late step)
const VIEW_KEYS = ['measures', 'hidden_dims', 'display', 'light', 'editable']; // (what the view keeps in a part: no change)
const TAIL_MS = 3000;

/** A part's data as the lock compares it: the view's keys left out (poses: the placed parts' places, left out too). */
function bare(d, poses = false) {
  if (!d || typeof d !== 'object') return d ?? null;
  const o = { ...d };
  for (const k of VIEW_KEYS) delete o[k];
  if (poses && Array.isArray(o.instances)) o.instances = o.instances.map(({ matrix, hang, ...it }) => it);
  return o;
}
/** JSON with the keys sorted (a saved version and the part on screen compared). */
const canon = (x) => JSON.stringify(x, (k, v) => (v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : 1))) : v));

/** Only joints added (the old ones all kept), else as it was but the poses: a joint moves the parts it holds (a part
 *  dragged, a mechanism driven by clicking — no joint added: a change, as move_free). */
function jointsOnly(was, now) {
  const a = bare(was, true), b = bare(now, true), ma = a?.mates || [], mb = b?.mates || [];
  if (!a || !b || mb.length <= ma.length) return false;
  const ids = new Set(mb.map((m) => m.id));
  if (!ma.every((m) => ids.has(m.id))) return false;
  return canon({ ...a, mates: null }) === canon({ ...b, mates: null });
}

const lockedNow = () => Object.fromEntries((ctx?.project.parts || []).filter((p) => lockOf(p)).map((p) => [p.id, { name: p.name, data: structuredClone(dataOf(p)) }]));

/** The locked parts the AI's click changed -> [{id, p (null: gone), s: as they were}]. */
function broken(c) {
  const out = [];
  for (const [id, s] of Object.entries(c.snap)) {
    const p = partOf(id), d = p ? dataOf(p) : null;
    if (p && p.name === s.name && (canon(bare(d)) === canon(bare(s.data)) || jointsOnly(s.data, d))) continue;
    out.push({ id, p, s });
  }
  return out;
}

const live = () => !!clicking && (clicking.until === Infinity || Date.now() <= clicking.until);

function refused(c, ids) {
  for (const id of ids) c.refused.add(id);
  if (c.until !== Infinity) ctx.toast(t('The AI tried to change a part locked for it — put back as it was.'), 'warning', 6000); // (a late step: the AI was answered already)
}

// a step about to be recorded while the AI clicks: refused when it changes a locked part (the other locked parts it
// touched — a bolt's holes drilled into one — put back with it)
History.veto = (h) => {
  if (!ctx || h === hist || !clicking) return false;
  if (!live()) { clicking = null; return false; }
  const bad = broken(clicking), cur = ctx.project.current;
  if (!bad.length) return false;
  for (const { p, s } of bad) if (p && p !== cur) { p.data = structuredClone(s.data); p.name = s.name; }
  refused(clicking, bad.map((b) => b.id));
  return true;
};

/** The project about to apply a rename or a delete of this part: refused (true) while the AI clicks and it is locked. */
export function aiHolds(idOrPart) {
  if (!live()) return false;
  const p = typeof idOrPart === 'string' ? partOf(idOrPart) : idOrPart;
  if (!p || !lockOf(p)) return false;
  refused(clicking, [p.id]);
  return true;
}

/** What the click left changed without a step: put back as it was (the part on screen: its step undone, else loaded again). */
async function putBack(c) {
  const bad = broken(c);
  if (!bad.length) return;
  for (const { id, p, s } of bad) {
    c.refused.add(id);
    if (!p) { if (ctx.project.lastDeleted?.p.id === id) ctx.project.undoDelete(); continue; }
    p.name = s.name;
    if (p !== ctx.project.current) { p.data = structuredClone(s.data); continue; }
    const h = p.kind === 'model' ? ctx.modeler?.history : p.kind === 'assembly' ? ctx.assembly?.history : null;
    if (h?.base && JSON.stringify(h.capture()) !== h.baseKey) await h.restore(structuredClone(h.base));
    if (broken({ snap: { [id]: s } }).length) {
      const hs = ctx.project.hooks.getHistory(p.kind);
      await ctx.project.hooks.load(structuredClone(s.data), { switching: true, kind: p.kind });
      ctx.project.hooks.setHistory(hs, p.kind);
    }
  }
  ctx.refresh?.();
}

/** The AI's gui_action run with its changes watched: a locked part changed -> refused with the lock's answer, put back. */
async function clicked(run) {
  const c = clicking = { snap: lockedNow(), until: Infinity, refused: new Set() };
  let r;
  try { r = await run(); } finally { c.until = Date.now() + TAIL_MS; }
  await putBack(c);
  if (!c.refused.size) return r;
  const p = partOf([...c.refused][0]);
  return { ...r, text: `${p ? refusal(p) : '🔒'} — the click's change to it was not applied (put back as it was). ${r?.text ?? ''}`, error: true };
}

/** 🔒 The project a version / a variant would bring (restore_version, switch_variant) -> null, or the refusal when it
 *  would change a part locked for the AI (its data, its name, its lock — or take it away). now: the project file now. */
export function lockedChange(next, now) {
  if (!ctx || !next?.parts) return null;
  const was = new Map((now?.parts || []).map((q) => [q.id, q]));
  for (const p of ctx.project.parts) {
    if (!lockOf(p)) continue;
    const a = was.get(p.id), b = next.parts.find((q) => q.id === p.id);
    const side = (q) => (q ? canon([q.name, bare(q[q.kind === 'classic' ? 'classic' : q.kind]), q.ai_lock || null]) : null);
    if (a && side(a) !== side(b)) return { text: `${refusal(p)} The version would change it — it was not restored.`, error: true };
  }
  return null;
}

/** Start: what the lock looks at, and how the screens draw it again (app.js). */
export function initAiLock(c) {
  ctx = c;
  window.addEventListener('a3d:project-loading', () => { mine = { undo: 0, redo: 0 }; told.clear(); });
}
