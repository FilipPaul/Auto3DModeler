// The assembly's Suggested table in categories: each row gets a `group` — joint (Vazby), part (Díl), asm (Sestava),
// cable (Kabeláž), fast (Spojovací materiál), motion (Pohyb), insert (Vložit díly), other (Ostatní). Set where the row
// is made when its icon could mean two things (✕ Take it out, ⧉ Copy its coordinates / Make it its own part, ⚙ a gear
// pair / Moving sub-assembly, ＋ New part on this face, a library part's companions), else from its icon here.
// suggest.js shows the categories under small headers, the one holding the most relevant row first; a row's category
// colours its icon (a joint blue, a part purple, an assembly green — the trees' colours of those kinds).
import { showSuggest as show } from '../suggest.js';
import { JOINT_TYPES } from './joints.js';

const BY_ICON = new Map([
  ...Object.values(JOINT_TYPES).filter((j) => !j.pick).map((j) => [j.icon, 'joint']), // (⧉ ↔ ▭ ◎ ∥ ⟂ ∠ ⌒ ● ◉ 🔗 〰)
  ['▤', 'joint'],
  ['◆', 'part'], ['✎', 'part'], ['✏', 'part'], ['📌', 'part'], ['↻', 'part'], ['⤵', 'part'], ['🏷', 'part'], ['👁', 'part'],
  ['🔒', 'part'], ['🔓', 'part'], ['🎨', 'part'],
  ['◇', 'asm'], ['🧱', 'asm'],
  ['🔌', 'cable'], ['📎', 'cable'], ['➰', 'cable'], ['⛓', 'cable'],
  ['🔩', 'fast'],
  ['⚙', 'motion'], ['⇤⇥', 'motion'], ['⇤', 'motion'], ['⇥', 'motion'],
  ['＋', 'insert'], ['📚', 'insert'], ['📂', 'insert'],
]);

/** The category of an assembly suggestion: its own, else by its icon, else Other. */
export const groupOf = (it) => it.group || BY_ICON.get(it.icon) || 'other';

/** A placed part's rows (assembly.js partItems): a placed sub-assembly's moves, fixing, renaming, hiding … are about
 *  that assembly — Sestava, green — not a part. kind: its part's kind. */
export const placedRows = (kind, items) => (kind !== 'assembly' ? items
  : items.map((it) => (it.section === undefined && groupOf(it) === 'part' ? { ...it, group: 'asm' } : it)));

/** showSuggest with every row in a category (assembly.js imports this one). */
export function showSuggest(viewport, title, items, ...rest) {
  return show(viewport, title, (items || []).map((it) => (it.section !== undefined || it.group ? it : { ...it, group: groupOf(it) })), ...rest);
}
