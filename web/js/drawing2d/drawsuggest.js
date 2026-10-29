// The 2D drawing's suggestions table (suggest.js showSuggest, bottom left of the view): what to do with the shapes
// clicked — all like it, a size, a layer, into a sketch or a quick part, delete — or, with nothing chosen, the next
// steps (the drawing as a sketch of a new 3D model or a quick part, measure, ⬇ DXF). One click a row; a row that needs
// a value asks for one.
import { t } from '../i18n.js';
import { choose, ask } from '../choose.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const NAMES = { line: 'Line', circle: 'Circle', arc: 'Arc', poly: 'Polyline', text: 'Text' };

/** The table for the drawing editor `ed` (a DrawingEditor) -> {title, items, hint, refs} or null (none: a tool is on). */
export function drawingSuggest(ed) {
  if (ed.tool !== 'select' || ed.picking || !ed.d.entities.length) return null;
  const sel = ed.d.entities.filter((e) => ed.sel.has(e.id)), refs = `${t('in the 2D drawing')} “${ed.hooks.safeName?.() || ed.d.source || ''}”`;
  if (!sel.length) {
    return { title: `📐 ${t('Drawing')}`, refs, hint: t('Click a shape: what to do with it (Ctrl+click: more).'), items: [
      { icon: '✏', label: t('As a sketch of a new 3D model'), title: t('The shown layers as a clean sketch: ends welded, lines and arcs joined — then extrude it'), rank: 0, run: () => ed.use('sketch') },
      { icon: '▤', label: t('As a quick part (its closed outlines)'), title: t('The closed outlines of the shown layers as a quick part: thickness, holes, 3D print'), rank: 1, run: () => ed.use('quick') },
      { icon: '📏', label: t('Measure'), title: t('Measure: two spots, or a circle for its Ø (M)'), rank: 2, run: () => ed.setTool('measure') },
      { icon: '⬇', label: t('Export DXF'), title: t('Save the shown layers as a DXF (in mm, its layers and colours; traces keep their width, pads and areas filled)'), rank: 3, run: () => ed.exportDxf() },
    ] };
  }
  const e = sel[0], one = sel.length === 1, all = (...ts) => sel.every((x) => ts.includes(x.t));
  const size = all('circle') ? ['dia', 'Ø'] : all('circle', 'arc') ? ['r', 'R'] : all('line') ? ['len', t('Length')] : null;
  const items = [];
  if (one) items.push({ icon: '≡', label: t('All like this'), title: t('Filters for shapes like this one (its shape, layer and size) — and select them all'), rank: 0, run: () => ed.likeThis(e) });
  if (size) items.push({ icon: '↔', label: tv('{what}: change the size…', { what: size[1] }), title: sel.length > 1 ? tv('Type it: all {n} change.', { n: sel.length }) : t('Type it: it changes.'), rank: 1, run: () => askSize(ed, size) });
  items.push({ icon: '✏', label: t('These as a sketch'), title: t('Only the chosen shapes as a clean sketch of a new 3D model'), rank: 2, run: () => ed.useShapes('sketch', sel) });
  items.push({ icon: '▤', label: t('These as a quick part'), title: t('Only the chosen shapes\' closed outlines as a quick part'), rank: 3, run: () => ed.useShapes('quick', sel) });
  if (ed.d.layers.length > 1) items.push({ icon: '◫', label: t('To another layer…'), title: t('Move the chosen shapes to another layer'), rank: 4, run: () => pickLayer(ed, sel) });
  items.push({ icon: '✕', label: t('Delete'), title: t('Delete the chosen shapes (Delete; Ctrl+Z brings them back)'), danger: true, rank: 5, run: () => ed.removeSel() });
  const what = one ? `${t(NAMES[e.t] || e.t)}${e.t === 'circle' ? ` Ø${fmt(2 * e.r)}` : e.t === 'arc' ? ` R${fmt(e.r)}` : e.t === 'line' ? ` ${fmt(Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]))} mm` : ''}` : tv('{n} shapes', { n: sel.length });
  return { title: what, items, hint: t('Ctrl+click: add more, or take one away'), refs: `${refs}: ${sel.slice(0, 12).map((x) => x.id).join(', ')}` };
}

async function askSize(ed, [kind, label]) {
  const sel = ed.d.entities.filter((x) => ed.sel.has(x.id)), e = sel[0];
  const now = kind === 'dia' ? 2 * e.r : kind === 'r' ? e.r : Math.hypot(e.b[0] - e.a[0], e.b[1] - e.a[1]);
  const v = await ask(`${label} (mm)`, fmt(now), { check: (x) => (parseFloat(x.replace(',', '.')) > 0 ? '' : t('The size must be greater than zero.')) });
  if (v !== null) ed.setSize(kind, v);
}

async function pickLayer(ed, sel) {
  const to = await choose(t('To which layer?'), [...ed.d.layers.map((l) => ({ value: l.name, label: l.name, primary: l.name === sel[0].layer })), { value: null, label: 'Cancel' }]);
  if (to === null) return;
  for (const x of sel) x.layer = to;
  ed.d.entities = [...ed.d.entities];
  ed.commit();
}
