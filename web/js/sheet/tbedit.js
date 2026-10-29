// Typing straight into the title block (📄): which of its cells take text, which are computed, and which texts go
// to every sheet of an assembly's drawing set when the user says so. The cells are transparent rects over the drawn
// title block (data-tcell = the field's key; data-ro on the computed ones), made by every style (tbstyles.js, the
// Modern ones in sheet.js) with hitRect(); SheetEditor.editCell() lays an <input> over one.
import { t } from '../i18n.js';

/** The fields typed into the title block — key: {label, propagate}. propagate says what "Ano" of the question
 *  "Přepsat i ve všech listech sestavy?" may do with it:
 *    true     — a project-wide fact (who drew / checked / approved it, the company, the standards): asked;
 *    false    — this drawing's own identity (its title, drawing no., note): never asked, never copied;
 *    'typed'  — only where it is typed text: the material of an assembly's sheet (a part's comes from its model). */
export const TB_EDIT = {
  title: { label: 'Title', propagate: false },              // the part's own name
  number: { label: 'Drawing no.', propagate: false },       // the part / drawing number
  note: { label: 'Note', propagate: false },                // a note about this part
  drawn: { label: 'Drawn by', propagate: true },
  checked: { label: 'Checked by', propagate: true },
  approved: { label: 'Approved by', propagate: true },
  company: { label: 'Company', propagate: true },
  address: { label: 'Address', propagate: true },
  tolstd: { label: 'Tolerance standard', propagate: true }, // the general tolerances, e.g. ISO 2768 (the class -m is the part's)
  surface: { label: 'Roughness (Ra)', propagate: true },    // the default surface finish
  material: { label: 'Material', propagate: 'typed' },      // typed on an assembly's sheet only
};

/** The cells computed from the model or the sheet: shown, never typed — their tooltip says where they come from.
 *  (Never copied to other sheets: the mass, the scale, the sheet number, the revision are each sheet's own.) */
export const TB_COMPUTED = {
  material: 'Material — from the part\'s model: open the part to change it (each part keeps its own)',
  mass: 'Mass — computed from the part\'s volume and material',
  scale: 'Scale — the sheet\'s: change it with Scale in the panel',
  paper: 'Paper — change it with Paper in the panel',
  sheet: 'Sheet — this page\'s number in the drawing set',
  rev: 'Revision — goes up by itself when the part changes',
  date: 'Date — of the last change of the part',
  created: 'Created — the day the sheet was made',
  changed: 'Changed · Rev — the last change of the part and its revision',
};

const n2 = (v) => +(+v).toFixed(2);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** A cell's place to click (mm): an editable one (a text cursor, a light outline on hover) or a computed one (its
 *  tooltip only). ro: a Set of the keys that are computed on this sheet (the material of a part's sheet). */
export function hitRect(key, x, y, w, h, ro) {
  const comp = ro?.has(key) || (!TB_EDIT[key] && !!TB_COMPUTED[key]);
  const tip = comp ? t(TB_COMPUTED[key] || '') : `${t(TB_EDIT[key]?.label || key)} — ${t('click and type')}`;
  return `<rect x="${n2(x)}" y="${n2(y)}" width="${n2(w)}" height="${n2(h)}" fill="#fff" fill-opacity="0" stroke="none" data-tcell="${key}"${comp ? ' data-ro="1" class="sh-tro"' : ' class="sh-tcell"'}><title>${esc(tip)}</title></rect>`;
}

/** Whether a field's text may go to the other sheets of the set (asm: the sheet is an assembly's). */
export function propagates(key, asm = false) {
  const p = TB_EDIT[key]?.propagate;
  return p === true || (p === 'typed' && asm);
}

/** The answers "Ano" / "Jen tady" the user asked not to be asked again, per field — for this session. */
export const remembered = new Map();
