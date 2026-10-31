// 🔍 Find in a tree — the assembly's parts list and the project tree share it: the rows whose name has the typed text
// in it, no matter the case or the accents ("zakladni" finds "Základní"), the rows they are in kept and folded open
// for them (while searching only — not saved); the field filters 150 ms after the last key, Esc or its ✕ clears it.

/** A text for comparing: no accents, lower case. */
export const plainText = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim();

/** The rows the query leaves in a tree: roots = nodes, each {key, name (or a function -> it), kids ([nodes] or null),
 *  also (another text that counts as a hit when equal: a row's id)} -> {hits, shown: the hits and the rows they are
 *  in, open: those to fold open for them} — or null (nothing typed). A node's name is asked once per name. */
export function findInTree(query, roots) {
  const q = plainText(query);
  if (!q) return null;
  const hits = new Set(), shown = new Set(), open = new Set(), names = new Map();
  const has = (n) => {
    const raw = typeof n.name === 'function' ? n.name() : n.name;
    if (!names.has(raw)) names.set(raw, plainText(raw));
    return names.get(raw).includes(q) || (n.also != null && String(n.also).toLowerCase() === q);
  };
  const walk = (n) => { // -> whether it or a row in it is a hit
    let any = false;
    for (const k of (typeof n.kids === 'function' ? n.kids() : n.kids) || []) any = walk(k) || any;
    if (any) open.add(n.key);
    if (has(n)) hits.add(n.key);
    if (any || hits.has(n.key)) shown.add(n.key);
    return any || hits.has(n.key);
  };
  for (const n of roots) walk(n);
  return { hits, shown, open };
}

/** The find field: onQuery(text) 150 ms after the last key (not on every key), at once on Esc (cleared, the field
 *  left) and on its ✕ (type=search). Its keys are its own (not the workspace's Delete, H …). Bound once. */
export function bindFind(input, onQuery) {
  if (!input || input.__find) return;
  input.__find = true;
  let timer = 0;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    if (!input.value) { onQuery(''); return; } // (its ✕: everything again at once)
    timer = setTimeout(() => onQuery(input.value), 150);
  });
  input.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Escape') { input.value = ''; clearTimeout(timer); onQuery(''); input.blur(); }
  });
}
