// The bill of materials (BOM) of an assembly, its whole hierarchy rolled up — one engine for the assembly's 📋 BOM, the
// drawing set's BOM pages, the left panel's tree and the AI. A part's total is the sum over every place it is in: the
// assembly itself, its sub-assemblies at any depth, a sub-assembly placed n times counting its parts n times — a screw
// placed in the top assembly and inside a sub-assembly both counted, nothing twice.
//
// ctx: {partData(id), kindOf(id) ('model' | 'classic' | 'assembly' …), partName(id), massOf?(id) -> g each or null}.
import { isStandard } from './fasteners.js';
import { printed } from '../modeler/materials.js';
import { harnessBom } from './harness.js';
import { linksOf } from '../library/cableparts.js';

/** Make or buy, by the part's library facts and its material (the one place the browser decides it; the server's
 *  auto3d/modeler/materials.made_how is the same rule): a library or standard part (screws, nuts, inserts, pins) is
 *  bought; an own part is made — "made (3D print)" of a printing plastic (none chosen: PLA), else "made" (metals,
 *  engineering plastics …) -> {buy, how: 'bought' | 'made (3D print)' | 'made'}. */
export function makeBuy(data, name = '') {
  if (data?.library || isStandard(data, name)) return { buy: true, how: 'bought' };
  return { buy: false, how: printed(data?.material) ? 'made (3D print)' : 'made' };
}

/** The placed parts of assembly `aid` as a tree, instance by instance: [{id, path ("I3/I2"), part, kind, children
 *  (a sub-assembly's own, else null)}]. A sub-assembly already on the way down (a loop) is not opened again. */
export function instanceTree(ctx, aid, pre = '', stack = new Set()) {
  if (stack.has(aid)) return [];
  const inner = new Set(stack).add(aid);
  return (ctx.partData(aid)?.instances || []).map((it) => {
    const path = pre ? `${pre}/${it.id}` : it.id, kind = ctx.kindOf(it.part);
    return { id: it.id, path, part: it.part, kind, children: kind === 'assembly' ? instanceTree(ctx, it.part, path, inner) : null };
  });
}

/** One numbering of the parts from assembly `root` down (the drawing set's: a part keeps its number on every page and
 *  in the BOM): the root's parts first, then each sub-assembly's new ones in page order -> Map(part id -> n). */
export function itemNumbers(ctx, root) {
  const nums = new Map(), seen = new Set();
  const visit = (aid) => {
    if (seen.has(aid)) return;
    seen.add(aid);
    const parts = [...new Set((ctx.partData(aid)?.instances || []).map((it) => it.part))];
    for (const p of parts) if (!nums.has(p)) nums.set(p, nums.size + 1);
    for (const p of parts) if (ctx.kindOf(p) === 'assembly') visit(p);
  };
  visit(root);
  return nums;
}

/** A part's facts for a BOM row. */
function factsOf(ctx, part) {
  const data = ctx.partData(part) || {}, kind = ctx.kindOf(part), name = ctx.partName(part) || part, lib = data.library || null;
  if (kind === 'assembly') return { part, name, kind, material: '', maker: '', pn: '', description: '', order: {}, library: false, buy: false, how: 'assembly', mass_g: null };
  const mb = makeBuy(data, name), m = ctx.massOf?.(part);
  return { part, name, kind, material: data.material || (lib ? '' : 'PLA'), maker: lib?.maker || '', pn: lib?.pn || '', description: lib?.description || '',
    order: lib?.order || {}, library: !!lib, approx: !!lib?.approx, buy: mb.buy, how: mb.how, mass_g: Number.isFinite(m) ? +(+m).toFixed(2) : null };
}

/** The BOM of assembly `aid` -> {
 *    assembly: {id, name},
 *    tree: [{pos, part, name, kind, qty (in its parent), total (in the whole), …facts, children}] — structured: per
 *      assembly a node per part (its placements counted), the quantities multiplied down the levels;
 *    rows: [{pos, part, name, qty (the total), …facts, mass_total_g, in: [{assembly, qty, times}]}] — summary: one row
 *      per part (sub-assemblies left out: their parts are in), by position;
 *    lines: the rows of `mode` to show / write: summary -> rows; structured -> the tree flattened, each with its depth;
 *    pieces (all parts counted), kinds (distinct parts), mass_g (known masses × totals), mass_unknown (parts without one)}.
 *  numbering: the assembly whose drawing set numbers the positions (default: aid itself). */
export function bomOf(ctx, aid, { mode = 'summary', numbering = null } = {}) {
  const nums = itemNumbers(ctx, numbering || aid), facts = new Map();
  const fact = (p) => { if (!facts.has(p)) facts.set(p, factsOf(ctx, p)); return facts.get(p); };
  const level = (id, times, stack) => {
    if (stack.has(id)) return [];
    const inner = new Set(stack).add(id), groups = new Map();
    for (const it of ctx.partData(id)?.instances || []) groups.set(it.part, (groups.get(it.part) || 0) + linksOf(ctx.partData(id), it)); // (⛓ a chain: its links)
    return [...groups].map(([part, qty]) => {
      const f = fact(part), total = qty * times;
      return { pos: nums.get(part) ?? null, ...f, qty, total, in: id, children: f.kind === 'assembly' ? level(part, total, inner) : null };
    }).sort((a, b) => (a.pos ?? 1e9) - (b.pos ?? 1e9)).concat(harnessBom(ctx.partData(id)).map((w) => ({ // 🔌 a line per wire / cable, after the parts
      pos: null, part: `🔌${id}|${w.key}`, name: w.name, kind: 'harness', material: '', maker: '', pn: '', description: w.harness_name, order: {}, library: false,
      buy: true, how: 'bought', mass_g: null, length_mm: w.length_mm, colour: w.colour, qty: w.qty, total: w.qty * times, in: id, children: null })));
  };
  const tree = level(aid, 1, new Set());
  const rows = new Map();
  const add = (nodes) => {
    for (const n of nodes) {
      if (n.children) { add(n.children); continue; }
      const r = rows.get(n.part) || { ...(n.kind === 'harness' ? { ...n, children: undefined } : fact(n.part)), pos: n.pos, qty: 0, in: [] };
      r.qty += n.total;
      r.in.push({ assembly: ctx.partName(n.in) || n.in, qty: n.qty, times: n.total / n.qty });
      rows.set(n.part, r);
    }
  };
  add(tree);
  const list = [...rows.values()].sort((a, b) => (a.pos ?? 1e9) - (b.pos ?? 1e9));
  for (const r of list) r.mass_total_g = r.mass_g === null ? null : +(r.mass_g * r.qty).toFixed(2);
  const flat = [], walk = (nodes, depth) => { for (const n of nodes) { flat.push({ ...n, depth, mass_total_g: n.mass_g === null ? null : +(n.mass_g * n.total).toFixed(2) }); if (n.children) walk(n.children, depth + 1); } };
  walk(tree, 0);
  return {
    assembly: { id: aid, name: ctx.partName(aid) || aid }, mode, tree, rows: list, lines: mode === 'structured' ? flat : list,
    pieces: list.reduce((s, r) => s + r.qty, 0), kinds: list.length,
    mass_g: +list.reduce((s, r) => s + (r.mass_total_g || 0), 0).toFixed(2), mass_unknown: list.filter((r) => r.mass_g === null && r.kind !== 'harness').length,
  };
}

/** The columns of a BOM table (CSV, Excel, the window, the drawing page) for `mode`: [[key, English header]]. */
export function bomColumns(mode, shops = []) {
  return [['pos', 'Pos.'], ...(mode === 'structured' ? [['level', 'Level']] : []), ['name', 'Name'],
    ...(mode === 'structured' ? [['qty', 'Qty per parent'], ['total', 'Total qty']] : [['qty', 'Qty']]),
    ['material', 'Material'], ['mass_g', 'Mass each (g)'], ['mass_total_g', 'Mass total (g)'], ['maker', 'Maker'], ['pn', 'Part number'],
    ...shops.map((s) => [`order:${s}`, `Order (${s})`]), ['description', 'Description'], ['how', 'Make / buy']];
}

/** A BOM's lines as table cells (texts through `tr`, numbers as numbers) -> {head: [texts], rows: [[cells]], levels}. */
export function bomTable(bom, tr = (s) => s) {
  const shops = [...new Set(bom.rows.flatMap((r) => Object.keys(r.order || {})))], cols = bomColumns(bom.mode, shops);
  const cell = (r, k) => {
    if (k === 'level') return r.depth + 1;
    if (k === 'how') return r.kind === 'assembly' ? tr('assembly') : tr(r.how);
    if (k === 'material') return r.material ? tr(r.material) : ''; // (by the names the material select shows: ocel, hliník …)
    if (k.startsWith('order:')) return r.order?.[k.slice(6)] || '';
    if (k === 'qty' || k === 'total' || k === 'pos') return r[k] ?? '';
    if (k === 'mass_g' || k === 'mass_total_g') return r[k] ?? '';
    return r[k] ?? '';
  };
  return { head: cols.map(([, h]) => tr(h)), keys: cols.map(([k]) => k), rows: bom.lines.map((r) => cols.map(([k]) => cell(r, k))), levels: bom.lines.map((r) => r.depth || 0) };
}

/** A BOM as CSV for Excel: ; separated, decimal commas, UTF-8 with its mark. */
export function bomCsv(bom, tr = (s) => s) {
  const { head, rows } = bomTable(bom, tr);
  const q = (v) => { const s = typeof v === 'number' ? String(v).replace('.', ',') : String(v ?? ''); return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return '﻿' + [head, ...rows].map((r) => r.map(q).join(';')).join('\r\n');
}
