// The drawing sheet's suggestions table (suggest.js showSuggest, bottom left of the sheet): what can be done with what
// is clicked — a view, a dimension, an edge or a circle of a view, the title block — or, with nothing chosen, the next
// steps of the sheet (the missing sizes, ⬇ PDF, a view to show, the template). Every row is one click; a row that needs
// a value asks for one (a tolerance, a text) — never more.
import { t } from '../i18n.js';
import { choose, ask } from '../choose.js';
import { FIT_LIST, deviationText } from './fits.js';
import { RA_LIST, PROCS, raText } from './rough.js';
import { missRows, moveRows } from './dimcandidates.js';

const fmt = (v) => (+(+v).toFixed(2)).toString();
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
/** The standard scales (ISO 5455), biggest first — a view's Bigger / Smaller go one step along them. */
const STEPS = [[10, 1], [5, 1], [2, 1], [1, 1], [1, 2], [1, 5], [1, 10], [1, 20], [1, 50], [1, 100]];
const sText = (s) => `${fmt(s[0])}:${fmt(s[1])}`;

/** A typed tolerance -> its text on the dimension ("0.1" / "±0.1" -> "±0.1"; "+0.2 -0.1" / "+0.2/-0.1" ->
 *  "+0.2/−0.1"), '' (none) or null (not a tolerance). */
export function tolText(s) {
  const v = String(s ?? '').trim().replace(/,/g, '.').replace(/−/g, '-');
  if (!v || v === '0' || v === '-') return '';
  let m = /^(?:±|\+-|\+\/-)?\s*(\d*\.?\d+)$/.exec(v);
  if (m) return `±${fmt(m[1])}`;
  m = /^([+-]?\d*\.?\d+)\s*[/ ;]\s*([+-]?\d*\.?\d+)$/.exec(v);
  if (!m) return null;
  const sg = (x) => (+x === 0 ? '0' : +x > 0 ? `+${fmt(Math.abs(x))}` : `−${fmt(Math.abs(x))}`), [a, b] = [+m[1], +m[2]].sort((x, y) => y - x);
  return a === -b ? `±${fmt(a)}` : `${sg(a)}/${sg(b)}`;
}

/** The tolerances the sheet offers on a dimension, one click each (as tolText writes them): symmetric, then one-sided. */
export const TOL_LIST = ['±0.01', '±0.02', '±0.05', '±0.1', '±0.2', '±0.5', '+0.1/0', '0/−0.1', '+0.2/0', '0/−0.2'];

/** The table for the sheet editor `ed` (a SheetEditor) -> {title, items, hint, refs} or null (no table). */
export function sheetSuggest(ed) {
  const d = ed.d;
  if (d && ed.setMode) return setItems(ed);
  if (!d || !ed.geo || ed.tool !== 'select') return null;
  const refs = `${t('on the drawing sheet of')} “${ed.hooks.partName(d.source) || ''}”`;
  if (ed.sel) return dimItems(ed, refs);
  if (ed.selRough) return roughItems(ed, refs);
  if (ed.selGeo) return geoItems(ed, refs);
  if (ed.selView) return viewItems(ed, refs);
  if (ed.selTitle) return titleItems(ed, refs);
  return sheetItems(ed, refs);
}

// ---------------------------------------------------------------- nothing chosen: the sheet's next steps (a few
// rows — the table must not cover the drawing; the sheet's settings are under a click on the title block)
function sheetItems(ed, refs) {
  const d = ed.d, ck = ed.checked, items = [], hidden = ['Front', 'Top', 'Right', 'Iso'].filter((v) => d.off[v] && !(v === 'Right' && d.section));
  const lost = ed.allDims().filter((x) => ed.value(x) === null);
  if (ck?.missing.length) items.push({ icon: '📐', label: tv('Add the missing sizes ({n})', { n: ck.missing.length }), title: t('Every size the check misses, each from the part\'s edge (the orange ? marks)'), rank: 0, run: () => { ed.addAllMissing(); ed.clearSel(); ed.render(); } });
  items.push(...missRows(ed)); // (each missing size once: hovered, its ghosts in every view it can go in)
  if (ck && (ck.dup.size || ck.over.size)) items.push({ icon: '⧉', label: tv('Remove sizes given twice ({n})', { n: ck.dup.size + ck.over.size }), title: t('Dimensions that give a size another one gives already'), rank: 1, run: () => { for (const id of [...ck.dup, ...ck.over]) ed.remove(id); } });
  if (lost.length) items.push({ icon: '⚠', label: tv('Remove lost dimensions ({n})', { n: lost.length }), title: t('Dimensions whose points are gone — the part changed'), rank: 1, run: () => { for (const x of lost) ed.remove(x.id); } });
  const [setRow, setPdf] = setRows(ed, 0.5, 3.5); // (the drawing set: right after the fixes — the rows show in this order)
  if (setRow) items.push(setRow);
  for (const v of hidden.slice(0, 2)) items.push({ icon: '👁', label: tv('Show view: {v}', { v: ed.viewName(v) }), title: t('Show this view on the sheet'), rank: 4, run: () => { delete d.off[v]; ed.commit(); } });
  items.push({ icon: '⬇', label: t('Export PDF'), title: t('The sheet as a PDF — as you see it'), rank: 2, run: () => ed.exportPdf() });
  items.push({ icon: '🖨', label: t('Print'), title: t('Print the sheet (its PDF, on the paper size it is drawn for)'), rank: 3, run: () => ed.printPdf() });
  if (setPdf) items.push(setPdf);
  if (d.asm && !d.bomPage) items.push({ icon: '📋', label: t('Add BOM page'), title: t('A page with the bill of materials of this assembly after this page'), rank: 5, run: () => { d.bomPage = 'summary'; ed.commit(); } });
  const done = ck && ck.ok && !ck.over.size;
  return { title: `📄 ${ed.hooks.partName(d.source) || t('Drawing')}`, items, hint: done ? `✓ ${t('Fully dimensioned. Click a view, a dimension or the title block for more.')}` : t('Click a view, a dimension, an edge or the title block: what to do with it.'), refs };
}

// ---------------------------------------------------------------- the drawing set (an assembly, its parts, BOM pages)
/** The drawing set this sheet is a page of -> {root, name, n, pages} (n: its sheets — the assemblies, the made parts,
 *  a BOM page per assembly sheet that has one) or null (not in an assembly). */
export function setOf(ed) {
  const root = ed.hooks.drawingCtx ? ed.rootOf(ed.d.source) : null;
  if (!root) return null;
  const ctx = ed.hooks.drawingCtx(), pages = ed.pagesOf(root);
  const bom = pages.filter((p) => p.kind === 'assembly' && (p.id === ed.d.source ? ed.d.bomPage : ctx.sheetOf(p.id)?.bomPage)).length;
  return { root, name: ed.hooks.partName(root) || root, n: pages.length + bom, pages };
}

const PDF_ALL = 'The whole drawing set as one PDF: the assembly, each part\'s sheet, the BOM page';

/** 📑 the whole set on screen (📚 All pages) and ⤓ its PDF — an assembly's sheet; a part's: 📑 its assembly's sheets. */
function setRows(ed, rank, pdfRank) {
  const set = setOf(ed);
  if (!set) return [];
  const asm = ed.hooks.kindOf?.(ed.d.source) === 'assembly', out = [];
  out.push(asm ? { icon: '📑', label: tv('All sheets of the assembly ({n})', { n: set.n }), title: t('The assembly\'s sheet, each part\'s sheet and the BOM page, one below the other — scroll or jump between them; double-click one to edit it'), rank, run: () => ed.action('setview') }
    : { icon: '📑', label: tv('Sheets of the assembly “{a}”', { a: set.name }), title: tv('The whole drawing set of “{a}” ({n} sheets), this part\'s sheet in sight — scroll or jump between them', { a: set.name, n: set.n }), rank, run: () => ed.action('setview') });
  if (asm && ed.hooks.setPdf) out.push({ icon: '⤓', label: t('PDF of all sheets'), title: t(PDF_ALL), rank: pdfRank, run: () => ed.hooks.setPdf(set.root) });
  return out;
}

/** 📚 All pages on screen: from sheet to sheet, the set's PDF, back to this sheet. */
function setItems(ed) {
  const set = setOf(ed);
  if (!set) return null;
  const ids = set.pages.map((p) => p.id), at = Math.max(0, ids.indexOf(ed.seen || ed.d.source)), items = [];
  const go = (i) => ed.stage.querySelector(`[data-pageid="${ids[i]}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (at < ids.length - 1) items.push({ icon: '▼', label: tv('Next sheet: {p}', { p: set.pages[at + 1].name }), title: t('Scroll to the next sheet of the set'), rank: 0, run: () => go(at + 1) });
  if (at > 0) items.push({ icon: '▲', label: tv('Previous sheet: {p}', { p: set.pages[at - 1].name }), title: t('Scroll to the sheet before'), rank: 1, run: () => go(at - 1) });
  if (ed.hooks.setPdf) items.push({ icon: '⤓', label: t('PDF of all sheets'), title: t(PDF_ALL), rank: 2, run: () => ed.hooks.setPdf(set.root) });
  items.push({ icon: '↩', label: t('Back to this sheet'), title: t('Only this sheet again, to edit it (or double-click a sheet: edit that one)'), rank: 3, run: () => ed.action('setview') });
  return { title: `📑 ${set.name} (${set.n})`, items, hint: t('The Pages list on the left jumps to a sheet too.'), refs: `${t('the drawing set of')} “${set.name}”` };
}

// ---------------------------------------------------------------- a view
function viewItems(ed, refs) {
  const d = ed.d, v = ed.selView, iso = v === 'Iso', sec = v === 'Section', items = [];
  const per = (ed.checked?.missing || []).filter((m) => m.view === v);
  if (per.length) items.push({ icon: '📐', label: tv('Add its missing sizes ({n})', { n: per.length }), title: t('The sizes the check misses in this view'), rank: 0, run: () => { for (const m of per) ed.addMissing(m); ed.clearSel(); ed.selView = v; ed.render(); } });
  if (!iso && !sec && !d.asm) {
    const vp = d.vpreset?.[v];
    if (vp !== 'all') items.push({ icon: '📏', label: t('All its sizes'), title: t('Every size this view shows, also the ones given in another view'), rank: 1, run: () => ed.setViewPreset(v, 'all') });
    else items.push({ icon: '📏', label: t('Its sizes as the sheet'), title: t('This view\'s dimensions as the sheet\'s preset again'), rank: 1, run: () => ed.setViewPreset(v, null) });
  }
  if (!iso) items.push({ icon: '＋', label: t('Add a dimension'), title: t('Click an edge (twice: its length), two edges, two points or a circle — the value comes from the part'), rank: 1.5, run: () => ed.action('dim') });
  const now = d.vscale?.[v] || ed.scaleArr(), r = now[0] / now[1];
  const bigger = [...STEPS].reverse().find((s) => s[0] / s[1] > r * 1.0001), smaller = STEPS.find((s) => s[0] / s[1] < r * 0.9999);
  if (bigger) items.push({ icon: '🔍', label: tv('Bigger ({s})', { s: sText(bigger) }), title: t('The view at the next bigger standard scale — its label says it'), rank: 2, run: () => ed.setViewScale(v, bigger) });
  if (smaller) items.push({ icon: '🔎', label: tv('Smaller ({s})', { s: sText(smaller) }), title: t('The view at the next smaller standard scale — its label says it'), rank: 3, run: () => ed.setViewScale(v, smaller) });
  if (d.vscale?.[v]) items.push({ icon: '⟲', label: tv('As the sheet ({s})', { s: sText(ed.scaleArr()) }), title: t('The view back at the sheet\'s scale'), rank: 3.5, run: () => ed.setViewScale(v, null) });
  if (!d.asm && !d.section && (v === 'Front' || v === 'Right')) items.push({ icon: '◩', label: t('Add Section A–A'), title: t('The part cut through its middle and seen from the right, the cut hatched — in the right view\'s place'), rank: 4, run: () => ed.setSection(true) });
  if (ed.d.views[v]) items.push({ icon: '⌖', label: t('Back to its place'), title: t('Where the sheet put it — in line with the others'), rank: 5, run: () => { delete d.views[v]; ed.commit(); ed.replace(); } });
  items.push({ icon: '✎', label: t('Rename'), title: t('The view\'s name under it — e.g. "Side A"'), rank: 6, run: () => ed.renameOnSheet(v) });
  if (iso && d.asm) items.push({ icon: '💥', label: t(d.exploded ? 'Not exploded' : 'Exploded'), title: t('The parts pulled apart in the iso view, the balloons on them'), rank: 2, run: () => { if (d.exploded) delete d.exploded; else d.exploded = true; delete d.balloons; ed.history.commit(); ed.ensure(true); } });
  items.push({ icon: '✕', label: t('Hide the view'), title: t('Take it off the sheet (Delete; ↶ or 👁 Show view brings it back)'), danger: true, rank: 7, run: () => ed.hideView(v) });
  return { title: `▣ ${ed.viewLabel(v)}`, items, hint: t('Drag the view to move it (Shift: freely) — it snaps in line with the others.'), refs: `${refs}, ${t('view')} ${v}` };
}

// ---------------------------------------------------------------- a dimension
function dimItems(ed, refs) {
  const dim = ed.allDims().find((x) => x.id === ed.sel);
  if (!dim) return null;
  const v = ed.value(dim), items = [];
  const label = v === null ? '⚠ ?' : ed.dimText(dim, v);
  if (dim.kind === 'dia' && !dim.thread) { // a Ø: its fit (ISO 286), a hole's and a shaft's — the deviations in the tooltip
    const now = (dim.post || '').trim(), chip = (f) => ({ label: f, on: f === now, primary: f === 'H7' || f === 'h6', title: fitTip(f, v), run: () => ed.setFit(dim.id, f === now ? '' : f) });
    items.push({ icon: '⌀', label: t('Fit — hole'), title: t('An ISO 286 fit of a hole: H7 the usual one (a pin, a bearing seat), H11 a loose one'), rank: 0, chips: FIT_LIST.hole.map(chip) });
    items.push({ icon: '⌀', label: t('Fit — shaft'), title: t('An ISO 286 fit of a shaft: h6 sliding, g6 / f7 running, k6 / m6 a push fit, p6 a press fit'), rank: 0.1, chips: FIT_LIST.shaft.map(chip) });
    items.push({ icon: now ? '○' : '✓', label: t('General tolerance (ISO 2768-m)'), title: t('No fit of its own: the general tolerance in the title block applies'), rank: 0.2, run: () => { if (now) ed.setFit(dim.id, ''); } });
  } else if (dim.kind !== 'pcd') { // a size: the common tolerances, one click each; Custom… types another
    const chip = (x) => ({ label: x, on: x === dim.tol, primary: x === '±0.1', title: tv('{t} mm after the size — click again: none', { t: x }), run: () => ed.setDimProps(dim.id, { tol: x === dim.tol ? undefined : x }) });
    items.push({ icon: '±', label: t('Tolerance'), title: t('A tolerance after the size (mm): symmetric ±, or one-sided'), rank: 0, chips: TOL_LIST.map(chip) });
    items.push({ icon: dim.tol ? '○' : '✓', label: t('General tolerance (ISO 2768-m)'), title: t('No tolerance of its own: the general tolerance in the title block applies'), rank: 0.2, run: () => { if (dim.tol) ed.setDimProps(dim.id, { tol: undefined }); } });
    const own = dim.tol && !TOL_LIST.includes(dim.tol);
    items.push({ icon: own ? '✓' : '✎', label: own ? tv('Custom: {t}', { t: dim.tol }) : t('Custom…'), title: t('Type another tolerance: ±0.03, or +0.2/−0.1'), rank: 0.3, run: () => askTol(ed, dim) });
  }
  items.push({ icon: '( )', label: t(dim.ref ? 'Not a reference dimension' : 'Reference dimension'), title: t('A reference dimension is in brackets: for information only, not to be checked'), rank: 1, run: () => ed.setDimProps(dim.id, { ref: !dim.ref }) });
  if (dim.kind === 'linear' && !dim.ord) {
    const other = { t: 'b', b: 't', l: 'r', r: 'l' }[dim.side || (dim.dir === 'h' ? 'b' : 'r')];
    items.push({ icon: '⇅', label: t('To the other side'), title: t('The dimension on the other side of the view'), rank: 2, run: () => ed.setDimProps(dim.id, { side: other }) });
    items.push(...moveRows(ed, dim)); // (⇄ the same size in another view)
  }
  items.push({ icon: '✕', label: t('Delete'), title: t(dim.auto ? 'Delete it (Delete) — ↺ Bring back deleted ones brings an automatic one back' : 'Delete it (Delete)'), danger: true, rank: 4, run: () => ed.remove(dim.id) });
  return { title: `⟷ ${label}`, items, hint: t('Drag the dimension to move it; its value comes from the part.'), refs: `${refs}, ${t('dimension')} ${dim.id} (${label})` };
}

// ---------------------------------------------------------------- an edge or a circle of a view
function geoItems(ed, refs) {
  const { view, edge, c } = ed.selGeo, items = [];
  if (c) {
    const co = c.full && ed.calloutFor(view, c.key), step = co?.hole;
    const has = ed.allDims().find((x) => x.view === view && (x.a === c.key || (step && x.hole === step)) && x.kind !== 'linear');
    if (has) items.push({ icon: '⟷', label: tv('Its dimension: {t}', { t: ed.value(has) === null ? '?' : ed.dimText(has, ed.value(has)) }), title: t('It has one already — choose it (tolerance, fit, delete …)'), rank: 0, run: () => { ed.clearSel(); ed.sel = has.id; ed.render(); } });
    else if (co) items.push({ icon: '⌖', label: tv('Hole callout ({t})', { t: ed.dimText(co, 2 * c.r) }), title: t('All this step\'s holes in this view in one callout: their count, size, depth and head'), rank: 0, run: () => ed.addGeoDim() });
    else items.push({ icon: c.full ? '⌀' : '◜', label: c.full ? tv('Dimension Ø{d}', { d: fmt(2 * c.r) }) : tv('Dimension R{r}', { r: fmt(c.r) }), title: t('Its size as a dimension, measured from the part'), rank: 0, run: () => ed.addGeoDim() });
    items.push({ icon: '↔', label: t('Distance from it…'), title: t('Then click an edge or a point of the same view'), rank: 1, run: () => ed.startDimFrom() });
    const title = c.full ? `◯ Ø${fmt(2 * c.r)}` : `◜ R${fmt(c.r)}`;
    return { title: `${title} · ${ed.viewName(view)}`, items, hint: '', refs: `${refs}, ${t('view')} ${view}, ${t('circle')} ${c.key}` };
  }
  const L = Math.hypot(edge.b[0] - edge.a[0], edge.b[1] - edge.a[1]);
  items.push({ icon: '↔', label: tv('Dimension its length ({l} mm)', { l: fmt(L) }), title: t('Its length as a dimension, measured from the part'), rank: 0, run: () => ed.addGeoDim() });
  items.push({ icon: '⟷', label: t('Distance or angle to…'), title: t('Then click another edge (parallel: the distance; meeting at an angle: the angle) or a point'), rank: 1, run: () => ed.startDimFrom() });
  if (view !== 'Iso') items.push(roughRow(ed, null, (ra) => ed.addRough({ view, edge: edge.key, ra, proc: ed.roughProc })), ...procRows(ed, null));
  return { title: `⟋ ${t('Edge')} ${fmt(L)} mm · ${ed.viewName(view)}`, items, hint: '', refs: `${refs}, ${t('view')} ${view}, ${t('edge')} ${edge.key}` };
}

// ---------------------------------------------------------------- a roughness symbol (ISO 21920 / ISO 1302) on an edge
/** A row of the Ra values: on a chosen surface's symbol (sym) its own Ra ✓; on an edge: placing one (put(ra)). */
function roughRow(ed, sym, put) {
  return { icon: '✓', label: sym ? t('Roughness Ra (µm)') : t('Surface roughness'), title: t('The ISO 21920 roughness symbol on this surface with its Ra in µm: 0.8 ground, 1.6 finely machined, 3.2 machined, 6.3 rough machined, 12.5 / 25 rough'), rank: 1.5,
    chips: RA_LIST.map((ra) => ({ label: raText(ra), on: sym?.ra === ra, primary: ra === 3.2, title: tv('Ra {ra} µm', { ra }), run: () => put(ra) })) };
}

/** Material removal (folded: one row until opened): any process / required (machined) / not allowed. */
function procRows(ed, sym) {
  const now = sym?.proc || ed.roughProc || 'any', tip = t('Whether material must be removed (machined) or must not be — the symbol shows it');
  if (!ed.roughMore) return [{ icon: '▸', label: tv('Process: {p}', { p: t(PROCS[now][0]) }), title: tip, rank: 1.6, run: () => { ed.roughMore = true; ed.renderSuggest(); } }];
  return [{ icon: '▾', label: t('Process'), title: tip, rank: 1.6,
    chips: Object.entries(PROCS).map(([k, [label, hint]]) => ({ label: t(label), title: t(hint), on: k === now, run: () => { ed.roughProc = k; if (sym) ed.setRough(sym.id, { proc: k }); else ed.renderSuggest(); } })) }];
}

function roughItems(ed, refs) {
  const sym = ed.roughOf(ed.selRough);
  if (!sym) return null;
  const items = [roughRow(ed, sym, (ra) => ed.setRough(sym.id, { ra })), ...procRows(ed, sym)];
  items.push({ icon: '✕', label: t('Delete'), title: t('Delete it (Delete)'), danger: true, rank: 4, run: () => ed.removeRough(sym.id) });
  return { title: `✓ ${raText(sym.ra)} · ${ed.viewName(sym.view)}`, items, hint: t('Drag the symbol along its surface, or away from it (a leader line).'), refs: `${refs}, ${t('roughness symbol')} ${sym.id} (${raText(sym.ra)})` };
}

// ---------------------------------------------------------------- the title block
function titleItems(ed, refs) {
  const X = ed.textsOf(), items = [], [setRow, setPdf] = setRows(ed, 0.5, 9.5);
  if (setRow) items.push(setRow); // (first: the set this sheet is a page of)
  const field = (k, icon, label, rank) => items.push({ icon, label: X[k] ? `${t(label)}: ${X[k]}` : `${t(label)}…`, title: t('Type it straight into its cell of the title block'), rank, run: () => editText(ed, k, label) });
  field('title', '✎', 'Title', 0);
  field('number', '№', 'Drawing no.', 1);
  field('drawn', '👤', 'Drawn by', 2);
  field('note', '🗒', 'Note', 4);
  const ra = raText(ed.textsOf().surface);
  items.push({ icon: '✓', label: t('Roughness (Ra)'), title: t('The general surface roughness in the title block (ISO 21920): the surfaces with no symbol of their own'), rank: 3.5,
    chips: RA_LIST.map((v) => ({ label: raText(v), on: ra === raText(v), primary: v === 3.2, title: tv('Ra {ra} µm', { ra: v }), run: () => ed.typed('surface', raText(v)) })) });
  items.push({ icon: '🧱', label: t('Material (in the part)'), title: t('The material comes from the part — open it and choose one; the drawing follows'), rank: 3, run: () => ed.hooks.openPart?.(ed.d.source) });
  items.push({ icon: '▤', label: tv('Template: {n}', { n: ed.tplOf().builtin ? t(ed.tplName()) : ed.tplName() }), title: t('The title block\'s template: its layout, fields, company, logo and frame'), rank: 5, run: () => pickTemplate(ed) });
  items.push({ icon: '▭', label: t('Frame…'), title: t('The border line and the margins of the paper'), rank: 6, run: () => pickFrame(ed) });
  const paper = ed.lay?.paper || 'A4', other = paper === 'A3' ? 'A4' : 'A3';
  items.push({ icon: '📄', label: tv('Paper {p}', { p: other }), title: tv('Draw the sheet on {p} (now {now}) — the views placed again', { p: other, now: paper }), rank: 6.5, run: () => ed.setPaper(other) });
  items.push({ icon: '⬇', label: t('Export DXF'), title: t('The sheet as a DXF for AutoCAD, SolidWorks or Solid Edge drafting: the paper in true size (mm), real dimensions'), rank: 9, run: () => ed.exportDxf() });
  if (setPdf) items.push(setPdf);
  items.push({ icon: '💾', label: t('Save as template…'), title: t('Keep this title block (layout, fields, company, address, drawn by, note, tolerance standard, logo, frame) as a template for all your projects'), rank: 7, run: () => ed.saveTemplate().catch((e) => ed.hooks.toast?.(e.message, 'error', 6000)) });
  items.push({ icon: '🏢', label: t('Company, logo and fields'), title: t('Company, address, tolerance standard, logo, layout and the fields shown'), rank: 8, run: () => ed.openTitleMore() });
  return { title: `▤ ${t('Title block')}`, items, hint: t('Click a cell and type: Enter keeps it, Tab goes to the next, Esc goes back.'), refs: `${refs}, ${t('title block')}` };
}

// ---------------------------------------------------------------- the one value a row asks for
/** A title-block text: typed in its own cell on the sheet (sheet.js editCell); a field the title block does not show
 *  (its style leaves it out): asked for. */
async function editText(ed, k, label) {
  if (ed.editCell(k)) return;
  const v = await ask(t(label), ed.cellValue(k), { ok: 'OK' });
  if (v === null) return;
  ed.typed(k, v);
}

async function askTol(ed, dim) {
  const v = await ask(t('Tolerance (mm): ±0.1, or +0.2/−0.1 — empty: none'), dim.tol || '±0.1', { placeholder: '±0.1', check: (x) => (tolText(x) === null ? t('Write it as ±0.1 or +0.2/−0.1.') : '') });
  if (v === null) return;
  ed.setDimProps(dim.id, { tol: tolText(v) || undefined });
}

/** A fit's tooltip: its limit deviations at this size and what it is for ("H7: +0.015 / 0 mm — a pin, a bearing seat"). */
function fitTip(f, size) {
  const dev = size ? deviationText(f, size) : '', use = { H7: 'a pin, a bearing seat', H8: 'a looser hole', H9: 'a loose hole', H11: 'a very loose hole', h6: 'a sliding shaft', h7: 'a shaft, looser', g6: 'a running shaft, close', f7: 'a running shaft', k6: 'a push fit', m6: 'a push fit, tighter', p6: 'a press fit' }[f];
  return `${f}${dev ? `: ${dev} mm` : ''}${use ? ` — ${t(use)}` : ''}`;
}

async function pickTemplate(ed) {
  const now = ed.tplName(), name = await choose(t('Title block template'), [...ed.tpls.map((x) => ({ value: x.name, label: x.builtin ? t(x.name) : x.name, primary: x.name === now })), { value: null, label: 'Cancel' }]);
  if (name === null || name === now) return;
  try { ed.useTemplate(name); } catch (e) { ed.hooks.toast?.(e.message, 'error', 6000); }
}

async function pickFrame(ed) {
  const now = ed.frameOf().preset, opts = [['iso', 'Standard ISO 5457', '20 mm on the left for filing, 10 mm elsewhere, zones and centring marks'], ['simple', 'Simple (10 mm)', 'A thin frame 10 mm from the edge all round'], ['narrow', 'Narrow', '5 mm all round — the most room for the views'], ['none', 'None', 'No frame line']];
  const f = await choose(t('Frame'), [...opts.map(([value, label, hint]) => ({ value, label, hint, primary: value === now })), { value: null, label: 'Cancel' }]);
  if (f === null || f === now) return;
  ed.setFrame(f);
}
