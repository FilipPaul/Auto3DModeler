// The 3D model's step tree: a small drawn icon per kind of step (coloured by what it does — adds material, cuts,
// rounds edges, changes faces, repeats, sketches, references) and the tree's shape (SolidWorks / Solid Edge style):
// a step shows the sketch it is made from under itself, a pattern / mirror the steps it repeats as links, and the
// reference points sit in a "Reference" group at the top with the Top / Front / Right planes.

import { t } from '../i18n.js';

// 16×16, drawn with strokes like parts.js kindIcon
const PATH = {
  sketch: '<path d="M3 13l.9-3.1 7.3-7.3 2.2 2.2-7.3 7.3z"/><path d="M9.9 3.9l2.2 2.2"/><path d="M2 14.6h5" opacity=".6"/>', // a pencil
  extrude: '<path d="M2.5 11.3 8 13.8l5.5-2.5L8 8.8z"/><path d="M8 1.8v5.4M5.7 4.1 8 1.8l2.3 2.3"/>', // a face pushed up
  cut: '<path d="M1.8 6.5h3.6v3.8h5.2V6.5h3.6v7.3H1.8z"/><path d="M8 1.4v5.8M6 5.2 8 7.2l2-2"/>', // a pocket pushed in
  revolve: '<path d="M8 1.5v13" stroke-dasharray="1.6 1.4" opacity=".7"/><path d="M12.6 7.2A5 2.6 0 1 1 9.6 5.6"/><path d="M9.2 3.9l1.2 1.8-1.9 1"/>', // turned round an axis
  hole: '<rect x="2" y="2" width="12" height="12" rx="1.2"/><circle cx="8" cy="8" r="3"/>',
  fillet: '<path d="M3 14V8a5 5 0 0 1 5-5h6"/><path d="M3 6.5V3h3.5" stroke-dasharray="1.2 1.2" opacity=".6"/>', // a rounded corner
  chamfer: '<path d="M3 14V7.5L7.5 3H14"/><path d="M3 6.5V3h3.5" stroke-dasharray="1.2 1.2" opacity=".6"/>', // a cut-off corner
  pattern: '<rect x="1.3" y="5.8" width="3.6" height="4.4" rx=".5"/><rect x="6.2" y="5.8" width="3.6" height="4.4" rx=".5"/><rect x="11.1" y="5.8" width="3.6" height="4.4" rx=".5"/>', // in a row
  'pattern-c': '<circle cx="8" cy="8" r="4.6" stroke-dasharray="1.2 1.6" opacity=".6"/><circle cx="8" cy="3.4" r="1.5"/><circle cx="12" cy="10.3" r="1.5"/><circle cx="4" cy="10.3" r="1.5"/>', // around
  mirror: '<path d="M8 1.5v13" stroke-dasharray="1.8 1.4"/><path d="M6 4 2.2 12H6z"/><path d="M10 4l3.8 8H10z"/>',
  shell: '<rect x="2" y="3" width="12" height="10.5" rx="1"/><path d="M4.6 3v8h6.8V3"/>', // hollowed
  draft: '<path d="M4 14 6 3h4l2 11z"/><path d="M6 3 5 1.6M10 3l1-1.4" opacity=".6"/>', // tapered walls
  rib: '<path d="M2 2v12h12"/><path d="M2 5.5 10.5 14"/><path d="M2 8.2l3.2 3.3M2 11l1.4 1.4" opacity=".55"/>', // a web in a corner
  loft: '<rect x="2" y="10.2" width="12" height="3.6" rx=".5"/><ellipse cx="8" cy="3.4" rx="3" ry="1.5"/><path d="M5 3.8 2 10.2M11 3.8l3 6.4"/>', // between two shapes
  sweep: '<path d="M3 12.5c4 0 3.2-9 9.2-9h1.6"/><circle cx="3.6" cy="12.2" r="2"/>', // along a path
  decal: '<path d="M3 13.6 7 2.4h2l4 11.2M5 9.6h6"/>', // a letter
  split: '<rect x="2" y="4" width="12" height="8" rx="1"/><path d="M9.6 1.4 6.4 14.6" stroke-dasharray="2 1.4"/>', // cut in two
  solid: '<path d="M8 1.6 14 5v6L8 14.4 2 11V5z"/><path d="M2 5l6 3.4L14 5M8 8.4v6"/>', // a block from a file
  point: '<circle cx="8" cy="8" r="2"/><path d="M8 1.8v3M8 11.2v3M1.8 8h3M11.2 8h3"/>',
  plane: '<path d="M1.5 11.5 4.8 4.5h9.7l-3.3 7z"/>',
  link: '<path d="M6.6 9.4l2.8-2.8"/><path d="M7.4 4.8l1.4-1.4a2.4 2.4 0 0 1 3.4 3.4l-1.4 1.4M8.6 11.2l-1.4 1.4a2.4 2.4 0 0 1-3.4-3.4l1.4-1.4"/>', // a chain
};

/** The icon's kind for a step (an extrude that cuts: cut; a pattern around an axis: pattern-c). */
export const stepKind = (f) => (f.type === 'extrude' && f.op === 'cut' ? 'cut'
  : f.type === 'pattern' && f.kind === 'circular' ? 'pattern-c' : PATH[f.type] ? f.type : 'solid');

/** What a step does, for its colour: add (green), cut (red), edge (blue), face (teal), pattern (purple), sketch
 *  (grey-blue), ref (yellow). */
export function stepGroup(f) {
  if (f.type === 'sketch') return 'sketch';
  if (f.type === 'point' || (f.type === 'solid' && f.op === 'ref')) return 'ref';
  if (f.type === 'fillet' || f.type === 'chamfer') return 'edge';
  if (f.type === 'pattern' || f.type === 'mirror') return 'pattern';
  if (f.type === 'shell' || f.type === 'draft' || f.type === 'split') return 'face';
  if (f.type === 'hole' || f.op === 'cut') return 'cut';
  return 'add';
}

/** A drawn icon (14 px) of the kind, coloured by its group (CSS .ico-step.g-<group>). */
export const treeIcon = (kind, group) => `<svg class="ico ico-step g-${group}" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${PATH[kind] || PATH.solid}</svg>`;

export const stepIcon = (f) => treeIcon(stepKind(f), stepGroup(f));

/** The tree's shape from the steps in order (sketchesOf(f): the sketches a step is made from):
 *  {top: [ids at the top level], refs: [point ids], kids: Map id -> [{id, link, why}], parent: Map id -> parent id
 *  ('ref' for the Reference group)}. A sketch goes under the first step made from it; a later step made from it
 *  too, a pattern's / mirror's steps: links (why: 'uses' / 'repeats' / 'mirrors'). */
export function treeShape(features, sketchesOf) {
  const byId = new Map(features.map((f) => [f.id, f])), owner = new Map(), kids = new Map(), parent = new Map();
  const add = (p, k) => { if (!kids.has(p)) kids.set(p, []); kids.get(p).push(k); };
  for (const f of features) {
    if (f.type === 'sketch' || f.type === 'point') continue;
    for (const s of sketchesOf(f)) {
      if (byId.get(s)?.type !== 'sketch') continue;
      if (!owner.has(s)) { owner.set(s, f.id); parent.set(s, f.id); add(f.id, { id: s }); } else if (owner.get(s) !== f.id) add(f.id, { id: s, link: true, why: 'uses' });
    }
    if (f.type === 'pattern') for (const s of f.features || []) if (byId.has(s)) add(f.id, { id: s, link: true, why: 'repeats' });
    if (f.type === 'mirror' && f.of && f.of !== 'body' && byId.has(f.of)) add(f.id, { id: f.of, link: true, why: 'mirrors' });
  }
  const refs = features.filter((f) => f.type === 'point').map((f) => f.id);
  for (const id of refs) parent.set(id, 'ref');
  const top = features.filter((f) => !owner.has(f.id) && f.type !== 'point').map((f) => f.id);
  return { top, refs, kids, parent, owner };
}

// ------------------------------------------------------------------ ⏮ the rollback bar, for whatever uses the part
// (the server builds the same: auto3d/modeler/doc.py at_bar — exports, the print copy, assemblies and drawings follow
// the bar, as in SolidWorks)
/** A part's steps as its rollback bar stands (part.rollback: the id of the step it is under; absent or not there: all). */
export function stepsAtBar(part) {
  const fs = part?.features || [], i = part?.rollback ? fs.findIndex((f) => f.id === part.rollback) : -1;
  return i >= 0 ? fs.slice(0, i + 1) : fs;
}

/** The steps under the bar (none when it is at the end). */
export const rolledSteps = (part) => (part?.features || []).slice(stepsAtBar(part).length);

/** What the bar leaves out, in plain words — "without the last 2 steps (Extrude 2, Extrude 3)" — or '' at the end. The
 *  sketches of the steps left out are not counted (the user sees the steps); up to four names. */
export function rolledText(part) {
  const all = rolledSteps(part), main = all.filter((f) => f.type !== 'sketch'), list = main.length ? main : all;
  if (!list.length) return '';
  const names = list.slice(0, 4).map((f) => f.name || f.id).join(', ') + (list.length > 4 ? ', …' : '');
  return list.length === 1 ? t('without the last step ({names})').replace('{names}', names)
    : t('without the last {n} steps ({names})').replace('{n}', list.length).replace('{names}', names);
}

/** The note an export / the print copy shows while the bar is up: "⏮ As the history bar stands: without …" ('' at the end). */
export function rollbackNote(part) {
  const s = rolledText(part);
  return s ? `⏮ ${t('As the history bar stands')}: ${s}` : '';
}
