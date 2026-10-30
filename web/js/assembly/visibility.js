// 👁 Hiding parts of an assembly: a placed part (or a placed sub-assembly, all its parts) hidden or see-through — display
// only: a hidden part is not drawn, picked or snapped to; a see-through one is drawn at 25 % and picked only when nothing
// else is under the mouse. Collisions, mechanisms, the BOM, exports and drawings do not change. Kept in the assembly's
// document as `display` {inst id: 'hidden' | 'clear'} (saved with it, not an undo step). The suggestions table's
// 👁 Hide / show… opens its choices in a list beside it (hover: a preview); 👁 in the parts list; H / Shift+H / Alt+H.
import { t } from '../i18n.js';
import { changed } from '../history.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
/** A see-through part's opacity. */
export const CLEAR = 0.25;

/** How a placed part is shown: 'hidden', 'clear' (see-through) or null (as it is) — a row's hover preview first. */
export function displayOf(asm, id) {
  const p = asm.visPreview;
  if (p && id in p) return p[id];
  return asm.doc.display?.[id] || null;
}

/** The placed parts hidden / see-through now -> {hidden: [ids], clear: [ids]}. */
export function displayed(asm) {
  const out = { hidden: [], clear: [] };
  for (const it of asm.doc.instances) {
    const s = asm.doc.display?.[it.id];
    if (s === 'hidden') out.hidden.push(it.id);
    else if (s === 'clear') out.clear.push(it.id);
  }
  return out;
}

/** Set how parts are shown: states {id: 'hidden' | 'clear' | null}; the others as they were. Saved with the assembly. */
export function setDisplay(asm, states) {
  const d = { ...(asm.doc.display || {}) };
  for (const [id, s] of Object.entries(states)) { if (s === 'hidden' || s === 'clear') d[id] = s; else delete d[id]; }
  for (const id of Object.keys(d)) if (!asm.inst(id)) delete d[id]; // (parts taken out: forgotten)
  if (Object.keys(d).length) asm.doc.display = d; else delete asm.doc.display;
  asm.visPreview = null;
  asm.visSet = performance.now();
  asm.renderList();
  asm.draw();
  asm.renderSuggest();
  asm.hooks.onChange?.();
  changed(); // (autosaved)
}

/** What `how` does to the parts `ids` -> the states to set ({id: state}): hide / clear / show them, isolate (the
 *  others hidden), clearOthers (the others see-through), all (everything shown). */
export function statesFor(asm, how, ids) {
  const mine = new Set(ids), out = {};
  for (const it of asm.doc.instances) {
    const own = mine.has(it.id);
    if (how === 'all') out[it.id] = null;
    else if (how === 'isolate' || how === 'clearOthers') out[it.id] = own ? null : how === 'isolate' ? 'hidden' : 'clear';
    else if (own) out[it.id] = how === 'show' ? null : how;
  }
  return out;
}

/** The chosen parts (one, or more with Ctrl / Shift+click). */
const chosen = (asm) => asm.selIds();

/** 👁 row of the suggestions table for the chosen parts `ids`: 👁 Hide / show…, always; a click opens its choices in a
 *  small list beside it (each previews what it does while the mouse is on it). */
export function displayItems(asm, ids) {
  if (!ids.length) return [];
  const st = ids.map((id) => asm.doc.display?.[id] || null), any = displayed(asm), some = any.hidden.length + any.clear.length;
  const opt = (icon, label, title, how) => ({ icon, label: t(label), title: t(title),
    hover: (on) => { // (not right after a click: the table drawn again puts the focus back on the row there — a preview of the opposite)
      if (on && performance.now() - (asm.visSet || 0) < 400) return;
      asm.visPreview = on ? statesFor(asm, how, ids) : null;
      asm.draw();
    },
    run: () => setDisplay(asm, statesFor(asm, how, ids)) });
  return [{ icon: '👁', label: t('Hide / show…'), always: true, rank: 30, // (its choices in a list beside it — suggest.js subMenu)
    title: t('Hide it, make it see-through, show only it … — display only (H hides, Shift+H shows all, Alt+H isolates)'), sub: [
    st.every((s) => s === 'hidden') ? opt('👁', 'Show it', 'Draw it again (H)', 'show') : opt('🚫', 'Hide it', 'Not drawn, not picked — a click there takes what is behind it (H)', 'hidden'),
    st.every((s) => s === 'clear') ? opt('◼', 'Solid again', 'Not see-through any more', 'show') : opt('◐', 'Make see-through', 'Drawn see-through (25 %) — a click takes it only when nothing else is there', 'clear'),
    opt('◎', 'Hide the others (isolate)', 'Only it is shown (Alt+H)', 'isolate'),
    opt('◌', 'Others see-through', 'The other parts see-through around it', 'clearOthers'),
    ...(some ? [opt('👁', 'Show all parts', 'Every part drawn again, solid (Shift+H)', 'all')] : []),
  ] }];
}

/** H: the chosen parts hidden (all hidden already: shown); Shift+H: everything shown; Alt+H: only the chosen ones shown.
 *  -> handled? */
export function displayKey(asm, e) {
  if (e.key.toLowerCase() !== 'h' || e.ctrlKey || e.metaKey) return false;
  const ids = chosen(asm);
  if (e.shiftKey) { setDisplay(asm, statesFor(asm, 'all', [])); return true; }
  if (!ids.length) return false;
  const hidden = ids.every((id) => asm.doc.display?.[id] === 'hidden');
  setDisplay(asm, statesFor(asm, e.altKey ? 'isolate' : hidden ? 'show' : 'hidden', ids));
  return true;
}

/** 👁 on a row of the parts list: a click hides / shows it; Alt+click: see-through / solid. */
export function eyeHtml(asm, id) {
  const s = asm.doc.display?.[id] || null;
  return `<button class="mini as-eye${s ? ` ${s}` : ''}" data-a="eye" title="${t(s === 'hidden' ? 'Hidden — click to show it' : s === 'clear' ? 'See-through — click to hide it, Alt+click: solid again' : 'Shown — click to hide it (H), Alt+click: see-through')}">👁</button>`;
}
export function clickEye(asm, id, alt) {
  const s = asm.doc.display?.[id] || null;
  setDisplay(asm, { [id]: alt ? (s === 'clear' ? null : 'clear') : (s === 'hidden' ? null : 'hidden') });
}

/** The note above the parts list while some are hidden / see-through: "👁 2 hidden · Show all". */
export function displayNote(asm, el) {
  if (!el) return;
  const { hidden, clear } = displayed(asm);
  el.hidden = !hidden.length && !clear.length;
  el.dataset.noI18n = '';
  if (el.hidden) { el.innerHTML = ''; return; }
  const what = [hidden.length ? t2('{n} hidden', { n: hidden.length }) : '', clear.length ? t2('{n} see-through', { n: clear.length }) : ''].filter(Boolean).join(', ');
  el.innerHTML = `<span>👁 ${what}</span> · <button class="link as-showall" title="${t('Every part drawn again, solid (Shift+H)')}">${t('Show all parts')}</button>`;
  el.querySelector('.as-showall').addEventListener('click', () => setDisplay(asm, statesFor(asm, 'all', [])));
}

/** For the AI (set_visibility): hide / transparent / show / isolate (ids I…; isolate: the others hidden, or see-through
 *  with others: "transparent"), show_all -> what is hidden and see-through now. */
export function setVisibility(asm, { hide, transparent, show, isolate, others, show_all: all } = {}) {
  const ids = (v, what) => {
    if (v === undefined || v === null) return [];
    const list = Array.isArray(v) ? v : [v];
    for (const id of list) if (!asm.inst(id)) throw new Error(`${what}: no placed part ${id} — get_assembly lists them (I1, I2 …).`);
    return list;
  };
  const states = {};
  if (all) Object.assign(states, statesFor(asm, 'all', []));
  const iso = ids(isolate, 'isolate');
  if (iso.length) {
    if (others !== undefined && others !== 'hidden' && others !== 'transparent') throw new Error('others: "hidden" (the default) or "transparent".');
    Object.assign(states, statesFor(asm, others === 'transparent' ? 'clearOthers' : 'isolate', iso));
  }
  for (const id of ids(show, 'show')) states[id] = null;
  for (const id of ids(transparent, 'transparent')) states[id] = 'clear';
  for (const id of ids(hide, 'hide')) states[id] = 'hidden';
  if (!Object.keys(states).length) throw new Error('Give hide, transparent, show or isolate (placed part ids I… from get_assembly), or show_all: true.');
  setDisplay(asm, states);
  const d = displayed(asm);
  return `Hidden: ${d.hidden.join(', ') || 'none'}; see-through: ${d.clear.join(', ') || 'none'} — display only (collisions, mechanisms, the BOM and exports are unchanged); get_screenshot shows it.`;
}
