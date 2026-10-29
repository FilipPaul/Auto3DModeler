// The icons at a step's size on the part (the size editor, Modeler.openDimEdit): one click switches how an extrude
// goes — ⇅ the other way, both sides, up to a face, up to the next face, through all, add ↔ cut — or a revolve's
// full / half turn. Drawn 16×16 with strokes like the step tree's icons (steptree.js); the mode that is on is lit in
// the step's colour (add green, cut red), the others grey. Modes that do not apply are left out, not greyed.

import { treeIcon } from './steptree.js';

const PATH = {
  // a line (the sketch) and an arrow going down from it: the other way
  flip: '<path d="M2 3.2h12"/><path d="M8 5.4v8.3M5.4 11.1 8 13.7l2.6-2.6"/>',
  // arrows both ways out of a centre line
  symmetric: '<path d="M2 8h12" stroke-dasharray="1.8 1.4"/><path d="M8 6.2V1.8M6 3.8 8 1.8l2 2M8 9.8v4.4M6 12.2l2 2 2-2"/>',
  // an arrow stopping at a plane (a face chosen by a click)
  upto: '<path d="M1.6 5 4 1.6h10.4L12 5z"/><path d="M7.5 14.4V7.2M5.4 9.3 7.5 7.2l2.1 2.1"/><path d="M4.5 14.4h6" opacity=".55"/>',
  // an arrow stopping at the first of two planes
  next: '<path d="M2 2.2h12" opacity=".45" stroke-dasharray="1.6 1.3"/><path d="M2 6.2h12"/><path d="M8 14.4V8.4M5.9 10.5 8 8.4l2.1 2.1"/>',
  // an arrow through a block
  through: '<rect x="2.3" y="5.2" width="11.4" height="5.6" rx=".8"/><path d="M8 1.2v13.2M5.8 12.2 8 14.4l2.2-2.2"/>',
  // a full turn round an axis / half a turn
  full: '<path d="M13.6 8A5.6 5.6 0 1 1 10.9 3.2"/><path d="M8.6 1.6l2.6 1.5-1.4 2.6"/><circle cx="8" cy="8" r=".9"/>',
  half: '<path d="M2.4 9.5a5.6 5.6 0 0 1 11.2 0"/><path d="M11.4 8.1l2.2 1.6 1.8-2.1"/><path d="M1.2 11.6h13.6" opacity=".5"/>',
};

const svg = (kind) => `<svg class="ico" viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${PATH[kind]}</svg>`;

/** Set how extrude f goes (the Extrude panel and the icons both use this, so they agree):
 *  'distance' (a typed height), 'upto' (up to a face — {name: null} until one is clicked), 'next' (up to the next
 *  face), 'through' on / off (cuts), 'symmetric' on / off, 'flip' (⇅; on a face's own outline: add ↔ cut, faceOwn),
 *  'op' add ↔ cut. */
export function setExtrude(f, key, on = true, faceOwn = false) {
  if (key === 'distance') { delete f.upto; delete f.upto_next; }
  else if (key === 'upto') { f.upto = f.upto || { name: null }; delete f.upto_next; f.through = false; }
  else if (key === 'next') { f.upto_next = true; delete f.upto; f.through = false; f.symmetric = false; delete f.draft; }
  else if (key === 'through') { f.through = !!on; if (on) { delete f.draft; delete f.upto; delete f.upto_next; } }
  else if (key === 'symmetric') { f.symmetric = !!on; if (on) { delete f.d2; delete f.upto; delete f.upto_next; } }
  else if (key === 'flip') {
    if (faceOwn && !f.upto && !f.upto_next) { f.op = f.op === 'cut' ? 'add' : 'cut'; f.flip = false; if (f.op === 'add') f.through = false; } // (out of the part, or a cut into it)
    else f.flip = !f.flip;
  } else if (key === 'op') { f.op = f.op === 'cut' ? 'add' : 'cut'; if (f.op === 'add') f.through = false; }
}

/** The icons for step f's size (an extrude's height, a revolve's angle): [{key, html, title, on}] — those that apply.
 *  canUpto: there is a part to go up to; canNext: up to the next face finds one (or null: not known yet). */
export function dimIcons(f, { canUpto = false, canNext = false } = {}) {
  if (f.type === 'revolve') {
    return [
      { key: 'full', html: svg('full'), title: 'Full turn — 360°', on: +f.angle === 360 },
      { key: 'half', html: svg('half'), title: 'Half a turn — 180°', on: +f.angle === 180 },
      { key: 'op', html: treeIcon(f.op === 'cut' ? 'revolve' : 'cut', f.op === 'cut' ? 'add' : 'cut'), title: f.op === 'cut' ? 'Make it add material' : 'Make it a cut (remove material)', on: false },
    ];
  }
  if (f.type !== 'extrude') return [];
  const cut = f.op === 'cut', dist = !f.upto && !f.upto_next;
  return [
    { key: 'flip', html: svg('flip'), title: '⇅ Flip direction — to the other side of the sketch', on: !!f.flip },
    ...(f.upto_next ? [] : [{ key: 'symmetric', html: svg('symmetric'), title: 'Both sides — half the height each way from the sketch', on: !!f.symmetric && dist }]),
    ...(canUpto || f.upto ? [{ key: 'upto', html: svg('upto'), title: 'Up to a face… — then click a flat face of the part', on: !!f.upto }] : []),
    ...(canNext || f.upto_next ? [{ key: 'next', html: svg('next'), title: 'Up to next — as far as the first face of the part it meets', on: !!f.upto_next }] : []),
    ...(cut ? [{ key: 'through', html: svg('through'), title: 'Through all — the cut goes right through the part', on: !!f.through && dist }] : []),
    { key: 'op', html: treeIcon(cut ? 'extrude' : 'cut', cut ? 'add' : 'cut'), title: cut ? 'Make it add material' : 'Make it a cut (remove material)', on: false },
  ];
}
