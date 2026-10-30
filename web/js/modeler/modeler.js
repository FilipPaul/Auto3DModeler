// The 3D model workspace: sketches (rectangles, lines, circles drawn with the mouse on a plane or a flat face,
// sizes locked 🔒 by typing them — sketcher.js)
// turned into a solid by Extrude (add material / cut), step by step in a feature tree — like Solid Edge or
// SolidWorks, but only the few tools that need almost no input (docs/ARCHITECTURE-modeler.md, §3).
// The server's CAD kernel builds the body (/api/model/rebuild); this module edits the part JSON.
import { History } from '../history.js';
import { t } from '../i18n.js';
import { toolGroup } from '../toolgroups.js';
import { fitBar } from '../compactbar.js';
import { renameInPlace } from '../rename.js';
import { choose, confirmIn } from '../choose.js';
import { paintedFaces, repaint } from './paint.js';
import { ModelView, DATUMS, datumFrame, snapPoints } from './view.js';
import { Sketcher, upgradeSketch, arcPts, splinePts, RELATIONS, BIG_SKETCH } from './sketcher.js';
import { textOutline } from '../outlinepanel.js';
import { sectionBar, sectionMiddle } from './sectionbar.js';
import { originSeg, originKey, sameOrigin, moveOrigin, shiftSketch, shiftPoints, HOLE_ORIGINS, FROM_TEXT } from './origin.js';
import { libraryFactsHtml } from '../library/browser.js';
import { roundAxes, axisOf } from './axes.js';
import { fetchRebuild } from './packed.js';
import { newRid, cancelRid, wasCancelled } from '../progressbox.js';
import { busy, busyShown, busyStep } from '../busy.js';
import { snapOnFace, snapDrawing, toFace } from './facesnap.js';
import { holeUnder, holeHint, holeLocked, setHoleLock, HoleDrag } from './holedrag.js';
import { HOLE_SIZES, HOLE_SHAPES, THREADS, dFlat, holeSpec, setHole, nearestSize } from './holes.js';
import { stepIcon, stepKind, stepGroup, treeIcon, treeShape, rollbackNote } from './steptree.js';
import { dimIcons, setExtrude } from './dimicons.js';
import { params, isPlain, exprText, readField } from '../params.js';
import { exprField, takeField, setExpr } from '../paramsui.js';

const TYPE_NAME = { point: 'Point', rib: 'Rib', draft: 'Draft', sketch: 'Sketch', extrude: 'Extrude', revolve: 'Revolve', fillet: 'Fillet', chamfer: 'Chamfer', hole: 'Hole', shell: 'Shell', pattern: 'Pattern',
  loft: 'Loft', sweep: 'Sweep', solid: 'Solid', decal: 'Decoration', mirror: 'Mirror', split: 'Split' };
const LIMIT_FIELDS = { extrude: ['d', 'offset'], revolve: ['angle'], fillet: ['r'], chamfer: ['d'], hole: ['d', 'depth'], shell: ['t'],
  pattern: ['count', 'spacing'], decal: ['h', 'depth'] }; // the numbers the kernel finds ranges for (doc.LIMIT_FIELDS)
const NEXT_ROWS = 6; // ✨ Next step (nothing chosen): its rows — few, it stays up over the part
const ROUND_PICK_PX = 16; // ◜ / ◸: a click this near an edge takes that edge, not all the edges of the face under it
const REPEATABLE = new Set(['extrude', 'revolve', 'hole', 'pattern', 'loft', 'sweep', 'decal', 'mirror']);
const MIRROR_PLANES = { YZ: 'left ↔ right', XZ: 'front ↔ back', XY: 'top ↔ bottom' }; // the base planes to mirror across
const AXES = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };
const USES_SKETCH = new Set(['extrude', 'revolve', 'loft', 'sweep', 'rib']);
const PLACES = new Set(['hole', 'decal']); // tools whose click in the view places (and, editing, only once asked)
/** A sketch that is one open line (straight lines end to end, not closed — what ⊿ Rib takes). */
const isOpenLine = (f) => {
  const es = (f?.entities || []).filter((e) => !e.construction), ends = {};
  if (!es.length || es.some((e) => e.t !== 'line')) return false;
  for (const e of es) for (const p of [e.a, e.b]) ends[p] = (ends[p] || 0) + 1;
  return Object.values(ends).some((c) => c === 1) && Object.values(ends).every((c) => c <= 2);
};
/** The sketches a step is made from. */
const sketchesOf = (f) => (f.type === 'loft' ? f.sketches || [] : f.type === 'sweep' ? [f.profile, f.path] : USES_SKETCH.has(f.type) ? [f.sketch] : []).filter(Boolean);
// densities for the mass (g/cm³), common 3D-printing materials
import { MATERIALS, MATERIAL_GROUPS, MATERIAL_COLOR, lookColor, cogText } from './materials.js';
import { showSuggest, showSnapFilters, snapKinds, hoverKinds } from '../suggest.js';
import { floatBox } from '../floatbox.js';
import { pointAt } from '../pointat.js';
import { MeasureTool, snapWins } from '../measure.js';
export { MATERIALS }; // g/cm³ (materials.js: grouped, with their colours)
const DATUM_NAME = { XY: 'Top', XZ: 'Front', YZ: 'Right' };
const fmt = (v) => (+(+v).toFixed(3)).toString();
const TREE_OPEN_KEY = 'a3d.treeOpen'; // the step tree's rows folded open
const SIZES_KEY = 'a3d.sizes', SIZE_MODES = ['all', 'locked', 'none'];
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
/** A slider's new top round a typed number past it (a soft range grows): 1.5× it, up to a round 1 / 2 / 5 × 10ⁿ. */
const growTo = (v) => { const x = Math.abs(v) * 1.5, e = 10 ** Math.floor(Math.log10(x || 1)); return [1, 2, 5, 10].map((k) => k * e).find((k) => k >= x - 1e-9); };
/** Why a number stops at its max (a real limit — the kernel cannot build more), by step type and field. */
const LIMIT_WHY = { 'fillet.r': 'max {v} — a bigger rounding does not fit here', 'chamfer.d': 'max {v} — a bigger chamfer does not fit here',
  'hole.d': 'max {v} — the part is not wider here', 'hole.depth': 'max {v} — deeper is the same as Through all',
  'extrude.d': 'max {v} — deeper goes through the part anyway', 'shell.t': 'max {v} — a thicker wall does not fit here',
  'revolve.angle': 'max {v}° — a full turn', 'draft.angle': 'A draft angle is less than 45° (either way).' };
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export class Modeler {
  /** els: {left, viewport, right}; hooks: {toast, download, safeName, onChange} */
  constructor(els, hooks) {
    this.els = els;
    this.hooks = hooks;
    this.part = { features: [] };
    this.result = null;
    this.mode = 'part'; // 'part' | 'plane' (picking a sketch plane) | 'sketch'
    this.cmd = null;    // the open command (Extrude): {feature, isNew}
    this.sk = null;     // the open sketch (a Sketcher)
    this.selected = null; // feature id selected in the tree
    this.history = new History({
      capture: () => ({ features: this.part.features, rollback: this.part.rollback ?? null, look: { color: this.part.color, opacity: this.part.opacity, paint: this.part.paint, threads: this.part.threads, hidden_dims: this.part.hidden_dims } }),
      restore: async (s) => {
        this.part.features = s.features;
        if (s.rollback) this.part.rollback = s.rollback; else delete this.part.rollback;
        for (const k of ['color', 'opacity', 'paint', 'threads', 'hidden_dims']) { if (s.look?.[k] === undefined) delete this.part[k]; else this.part[k] = s.look[k]; }
        this.closeAll();
        this.render();
        await this.rebuild();
      },
      onChange: () => this.updateUndo(),
    });
    try { this.sizeMode = localStorage.getItem(SIZES_KEY); } catch { /* private mode */ }
    if (!SIZE_MODES.includes(this.sizeMode)) this.sizeMode = 'all';
    this.bigAll = new Set(); // big sketches whose every size is shown anyway
    this.build();
    this.bindSizes(this.els.left);
    this.view = new ModelView(this.els.view, { cube: true });
    this.view.onCamera = () => this.sk?.draw();
    this.ms = new MeasureTool({ ws: 'model', view: () => this.view, viewport: this.els.viewport, list: (make) => (make ? (this.part.measures ||= []) : this.part.measures),
      pick: (e) => this.measurePick(e), hover: (x) => this.view.setHover(x?.kind === 'face' ? x.faceId : -1), hint: (s) => this.hint(s),
      changed: () => this.hooks.onChange?.(), stop: () => { if (this.measuring) this.toggleMeasure(); }, toast: (...a) => this.hooks.toast(...a) });
    this.bindPointer();
    this.render();
    window.addEventListener('a3d:lang', () => this.render()); // (texts built with t(): in the new language)
  }

  // ------------------------------------------------------------------ DOM
  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = `
      <div class="mt-head"><b>Model</b><span class="mt-sub">steps, from the first to the last</span></div>
      ${this.sizesHtml()}
      <div class="mt-tree"></div>
      <div class="mt-start" hidden>
        <p><b>Make a part in 3 steps</b></p>
        <ol><li><b>✏ Sketch</b> — draw a rectangle or a circle</li><li><b>⬆ Extrude</b> — give it a height</li>
        <li>Sketch on a <b>face</b> of the part to add holes, pockets and bosses</li></ol>
      </div>`;
    viewport.innerHTML = `
      <div class="m-cmdbar"></div>
      <div class="m-hint" hidden></div>
      <div class="m-view"></div>
      <div class="m-busy" hidden><span>Building the 3D model…</span><button class="mini" data-a="stop" title="Stop this (the part stays as it was)">✕ Stop</button><button class="mini" data-a="again" hidden title="Build the part again as it is now">↻ Rebuild</button></div>
      <div class="m-install" hidden></div>
      <div class="m-status"></div>`;
    right.innerHTML = '<div class="mp-body"></div>';
    this.els.view = viewport.querySelector('.m-view');
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
    this.$('.m-busy [data-a=stop]').addEventListener('click', () => this.cancelRebuild());
    this.$('.m-busy [data-a=again]').addEventListener('click', () => this.rebuild());
  }

  render() {
    this.renderCmdBar();
    this.renderTree();
    this.renderProps();
    this.renderStatus();
  }

  /** The Top / Front / Right planes shown (when wanted): ◫ Planes off hides them — except while a sketch plane is
   *  being chosen. */
  datums(on, size) {
    if (this.planesOn === undefined) { try { this.planesOn = localStorage.getItem('a3d.planes') !== '0'; } catch { this.planesOn = true; } }
    this.view.showDatums(!!on && (this.planesOn || this.mode === 'plane'), size);
  }

  /** 🖨 Print check on / off: the marks on the part and a small box with what was found (and the thinnest wall to
   *  look for — remembered). It follows the part as it changes. */
  togglePrintCheck() {
    this.printChk = this.printChk ? null : { minWall: +(localStorage.getItem('a3d.minWall') || 1.2) || 1.2 };
    this.runPrintCheck();
    this.renderCmdBar();
  }

  runPrintCheck() {
    this.els.viewport.querySelector(':scope > .m-printcheck')?.remove();
    const r = this.view.printCheck(this.printChk && this.result?.body ? { minWall: this.printChk.minWall } : null);
    if (!this.printChk || !r) return r;
    const box = document.createElement('div');
    box.className = 'm-printcheck';
    const ok = !r.overhang.area && !r.thin.area;
    box.innerHTML = `<div class="mpc-head"><b>🖨 ${esc(t('Print check'))}</b></div>
      <div class="mpc-row"><i class="mpc-dot" style="background:#f8524a"></i>${esc(t('Overhangs over 45°'))}: <b data-no-i18n>${r.overhang.area ? `${fmt(r.overhang.area)} mm²` : '—'}</b></div>
      <div class="mpc-row"><i class="mpc-dot" style="background:#ff9e1a"></i>${esc(t('Walls thinner than'))} <input type="number" step="0.1" min="0.1" data-k="minWall" value="${fmt(this.printChk.minWall)}"> mm: <b data-no-i18n>${r.thin.area ? `${fmt(r.thin.area)} mm² (${t('thinnest')} ${fmt(r.thin.min)})` : '—'}</b></div>
      <p class="hint">${esc(t(ok ? 'Nothing to worry about — it prints as it lies.' : 'Overhangs need supports (or turn the part); thin walls may not print — make them thicker.'))}</p>`;
    for (const ev of ['pointerdown', 'pointerup', 'click', 'keydown']) box.addEventListener(ev, (x) => x.stopPropagation());
    const w = box.querySelector('[data-k=minWall]');
    w.addEventListener('change', () => {
      const v = parseFloat(String(w.value).replace(',', '.'));
      if (v > 0) { this.printChk.minWall = v; try { localStorage.setItem('a3d.minWall', String(v)); } catch { /* private window */ } }
      this.runPrintCheck();
    });
    this.els.viewport.appendChild(box);
    const bar = this.$('.m-cmdbar'), vr = this.els.viewport.getBoundingClientRect(); // (below the toolbar, however many rows it takes)
    if (bar) box.style.top = `${Math.max(56, bar.getBoundingClientRect().bottom - vr.top + 8)}px`;
    floatBox(box, this.els.viewport, { kind: 'printcheck', handle: '.mpc-head', min: [200, 80] });
    return r;
  }

  togglePlanes() {
    this.planesOn = !this.planesOn;
    try { localStorage.setItem('a3d.planes', this.planesOn ? '1' : '0'); } catch { /* private window */ }
    this.datums(!this.result?.body || this.mode === 'plane' || this.planesOn);
    this.renderCmdBar();
  }

  renderCmdBar() {
    const bar = this.$('.m-cmdbar');
    const btn = (a, label, title, cls = '') => `<button class="chip ${cls} ${toolGroup(a)}" data-a="${a}" title="${esc(title)}">${label}</button>`;
    if (this.mode === 'sketch') {
      const t = this.sk.tool;
      // a new, empty sketch on a base plane can still move to another base plane
      const dat = this.sk.isNew && !this.sk.f.entities.length && this.sk.f.plane?.datum;
      const planes = dat ? `<span class="m-say">on</span>${['XY', 'XZ', 'YZ'].map((k) => btn(`plane-${k}`, DATUM_NAME[k], `Sketch on the ${DATUM_NAME[k]} plane`, k === dat ? 'on' : '')).join('')}<span class="sep"></span>` : '';
      const onDatum = this.sk.f.plane?.datum;
      const nrm = onDatum ? datumFrame({ datum: onDatum }).n : null, k = nrm ? nrm.findIndex((c) => Math.abs(c) > 0.5) : -1;
      const plus = k >= 0 ? `${nrm[k] > 0 ? '+' : '−'}${'XYZ'[k]}` : ''; // (which way a positive offset moves it)
      const offset = onDatum ? `<label class="chip m-offset" title="Move the sketch plane along its normal (e.g. 30 mm above the bed — for a loft's second profile); a positive offset moves it along the arrow"><span class="m-offl">↕ Plane at</span>
        <input type="number" step="any" data-k="planeOffset" value="${fmt(this.sk.f.plane.offset || 0)}"> mm <span class="m-plus" data-no-i18n>(+ = ${plus})</span></label><span class="sep"></span>` : '';
      this.planeArrowLabel = onDatum ? plus : null; // (drawn only while the ↕ Plane at chip is pointed at / its field typed in)
      this.view.setPlaneArrow(null);
      const origin = originSeg(this.sk.f.plane, originKey(this.sk.f.plane?.origin));
      bar.innerHTML = `<span class="m-mode">Sketch</span>${planes}${offset}${origin ? `${origin}<span class="sep"></span>` : ''}
        ${btn('rect', '▭ Rectangle', 'Draw a rectangle: click two corners (R)', t === 'rect' ? 'on' : '')}
        ${btn('line', '⟋ Line', 'Draw lines: click point after point; click the first point to close the shape (L)', t === 'line' ? 'on' : '')}
        ${btn('circle', '◯ Circle', 'Draw a circle: click the centre, then the edge (C)', t === 'circle' ? 'on' : '')}
        ${btn('slot', '⊂⊃ Slot', 'Draw a slot: click the centres of its two round ends, then move out to its width and click', t === 'slot' ? 'on' : '')}
        ${btn('spline', '〰 Spline', 'Draw a smooth curve: click the points it goes through — double-click or Enter to finish; its first point closes it, a line end joins it (S)', t === 'spline' ? 'on' : '')}
        ${btn('arc', '◠ Arc', 'Draw an arc: click where it starts and ends, then bend it with the mouse and click (A)', t === 'arc' ? 'on' : '')}
        ${this.hooks.pickOutline ? btn('outline', '🖼 Outline', 'Insert an outline from a picture, a DXF / DWG drawing or a PDF drawing (as one shape you can move and size)') : ''}
        ${btn('text', '𝐓 Text', 'Write text in the sketch — an outline to extrude or cut in: type the text and its height in the panel')}
        ${btn('round', '◜ Round corner', 'Round a corner of lines: click the corner, type the radius (F)', t === 'round' ? 'on' : '')}
        ${btn('trim', '✂ Trim', 'Cut away a piece of a line, circle or arc — up to where other shapes cross it (T)', t === 'trim' ? 'on' : '')}
        ${btn('extend', '⟷ Extend', 'Lengthen a line up to the next shape it meets: click near its end (E)', t === 'extend' ? 'on' : '')}
        ${btn('construction', '┄ Construction', 'Construction (helper) lines and circles: the selected shape becomes one (or back) — nothing selected: new shapes are drawn as construction while it is on. They guide (a revolve axis, a mirror line, dimensions) but are not part of the outline', this.sk.consMode ? 'on' : '')}
        ${btn('mirror', '⇋ Mirror', 'Mirror shapes across a line or the X / Y axis — a copy that stays the mirror image, or moved', t === 'mirror' ? 'on' : '')}
        ${btn('offset', '⧈ Offset', 'A parallel copy of a closed shape, a distance outside or inside it (O)', t === 'offset' ? 'on' : '')}
        ${btn('pattern', '⁂ Pattern', 'Repeat the selected shapes in a row or around a point: select them (⬚ Select, Ctrl+click or a box), then type how many and how far apart — the copies follow the original', t === 'pattern' ? 'on' : '')}
        ${btn('merge', '⛓ Merge', 'Merge many small shapes into few: pick them (click or a box; nothing picked: click them now), then ⛓ Join into one curve, 🧹 Simplify or ◆ One outline', this.sk.merging ? 'on' : '')}
        <div class="menu sk-relmenu">${btn('relate', `⟂ Relations ▾`, 'Make shapes keep a relation: horizontal, vertical, parallel, perpendicular, equal, concentric, coincident, tangent, fixed', t === 'relate' ? 'on' : '')}
          <div class="menu-list">${Object.entries(RELATIONS).filter(([, r]) => !r.tool).map(([k, r]) => `<button data-rel="${k}" title="${esc(r.hint || '')}">${r.icon} ${esc(r.name)}</button>`).join('')}</div></div>
        ${btn('dim', '↔ Dimension', 'Add a distance: click two points, circles, lines or edges of the part, then type the value (D)', t === 'dim' ? 'on' : '')}
        ${btn('autodim', '🪄 Auto-dimension', 'Lock the sizes the sketch still needs to be fully defined: each shape sized, and placed from the nearest edges of the part (or the origin)')}
        ${btn('select', '⬚ Select', 'Select a shape or a corner to move it (drag) or delete it (Esc)', t === 'select' ? 'on' : '')}
        <div class="mp-actions">${btn('finish', '✓ Finish sketch', 'Done drawing — next: Extrude (Enter)', 'primary')}
        ${btn('cancelSketch', '✕ Cancel', 'Leave the sketch without changing the part')}</div>`;
    } else if (this.mode === 'plane') {
      bar.innerHTML = `<span class="m-mode">Sketch on…</span><span class="m-say">click a flat face of the part — or a plane:</span>
        ${btn('datum-XY', 'Top', 'Sketch on the Top plane (XY)')}${btn('datum-XZ', 'Front', 'Sketch on the Front plane (XZ)')}${btn('datum-YZ', 'Right', 'Sketch on the Right plane (YZ)')}
        <span class="sep"></span>${btn('midPlane', '⇳ Midway', 'Sketch midway between two parallel flat faces (e.g. a rib in the middle of a part): click one face, then the other — the sketch stays in the middle when they move', this.midPick ? 'on' : '')}
        <div class="mp-actions">${btn('cancelPlane', '✕ Cancel', 'Do not start a sketch (Esc)')}</div>`;
      this.showNext(); // (✨ Next: not while a plane is chosen)
    } else {
      this.els.viewport.querySelector(':scope > .view-suggest[data-from=sketch]')?.remove(); // (the sketch's suggestions)
      this.view.setPlaneArrow(this.cmd?.feature.type === 'split' ? this.splitFrame() : null, t('this side'), false); // (✂ Split: which side is "this side")
      showSnapFilters(this.els.viewport, !!this.result?.body && (!this.cmd || ['hole', 'decal'].includes(this.cmd.feature.type)), { // (📏 Show: Dimensions = Sizes All / None)
        show: ['dims'], isOn: () => this.sizeMode !== 'none',
        toggle: () => { if (this.sizeMode === 'none') this.setSizeMode(this.sizesBefore || 'all', true); else { this.sizesBefore = this.sizeMode; this.setSizeMode('none'); } } }); // (what 📏 Measure catches, and a hole / text placed on a face — not while other features are made)
      if (this.cmd || this.measuring || this.painting) this.dropSuggest(); // (a tool at work: not the face's)
      const canExtrude = this.sketches().length > 0;
      bar.innerHTML = `
        ${btn('sketch', '✏ Sketch', 'Start a sketch: on a plane, or on a flat face of the part (S)', 'tool')}
        ${btn('extrude', '⬆ Extrude', canExtrude ? 'Give a sketch a height: add material or cut (E)' : 'Draw a sketch first', 'tool')}
        ${btn('revolve', '⟳ Revolve', canExtrude ? 'Spin a sketch around an axis (vases, knobs, wheels)' : 'Draw a sketch first', 'tool')}
        ${btn('loft', '⧫ Loft', 'A shape from one outline to another (e.g. a square base to a round top): two sketches, one above the other', 'tool')}
        ${btn('sweep', '〰 Sweep', 'Move an outline along a path (pipes, handles, rails): a profile sketch and a path sketch', 'tool')}
        ${btn('solidFile', '▣ Solid from a file', 'Add a STEP / STL / OBJ / 3MF solid: joined to the part, cut out of it (a cavity it fits in), or as a see-through reference to build around', 'tool')}
        ${btn('fillet', '◜ Fillet', 'Round edges: click the edges, give the radius (F)', 'tool')}
        ${btn('chamfer', '◸ Chamfer', 'Bevel edges: click the edges, give the size', 'tool')}
        ${btn('shell', '▢ Shell', 'Hollow the part out: click the face(s) to leave open, give the wall thickness', 'tool')}
        ${btn('draft', '⟋ Draft', 'Tilt the side walls of an extrude by a few degrees (so a moulded or cast part comes out of its mould)', 'tool')}
        ${btn('split', '✂ Split', 'Cut the part in two along a plane or a flat face: keep both pieces (two bodies) or one side', 'tool')}
        ${btn('rib', '⊿ Rib', 'A rib (a gusset): draw a line from a wall to the plate in a sketch, give the thickness — it fills up to the part', 'tool')}
        ${btn('hole', '◎ Hole', 'Drill holes: click on a flat face where they go, give the diameter (H)', 'tool')}
        ${btn('decal', 'Aa Text / picture', 'Decorate a flat face: text or a picture outline, raised or engraved', 'tool')}
        ${btn('mirror', '⇋ Mirror', 'Mirror the part (or one step) across a base plane or a flat face — as a copy, or moved', 'tool')}
        ${btn('pattern', '⁂ Pattern', 'Repeat a step (holes, a boss, a cut) in a row or around a circle: give how many and how far apart', 'tool')}
        <span class="sep"></span>
        <button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
        <span class="sep"></span>
        ${btn('paint', '🎨 Paint', 'Colour faces, or whole bodies of an imported file: click them (Ctrl+click: more), then pick a colour', this.painting ? 'on' : '')}
        ${btn('measure', '📏 Measure', 'Measure: click a face or an edge (its size), or two spots (the distance between them) (M)', this.measuring ? 'on' : '')}
        ${btn('section', '✂ Section', 'Look inside: cut the view along X, Y or Z', this.section ? 'on' : '')}
        ${btn('printcheck', '🖨 Print check', 'Check the part for 3D printing as it lies on the bed: overhangs over 45° (red) and walls too thin to print (orange)', this.printChk ? 'on' : '')}
        ${btn('planes', '◫ Planes', 'Show or hide the Top, Front and Right planes (while a sketch plane is chosen they show anyway)', this.planesOn !== false ? 'on' : '')}`; // (the views: the view cube, top right)
      bar.querySelector('[data-a=extrude]').disabled = !canExtrude || !!this.cmd;
      bar.querySelector('[data-a=sketch]').disabled = !!this.cmd;
      for (const a of ['fillet', 'chamfer', 'hole', 'shell', 'pattern', 'decal', 'mirror', 'split', 'draft', 'rib']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body || !!this.cmd;
      bar.querySelector('[data-a=revolve]').disabled = !canExtrude || !!this.cmd;
      for (const a of ['loft', 'sweep']) bar.querySelector(`[data-a=${a}]`).disabled = this.sketches().length < 2 || !!this.cmd;
      bar.querySelector('[data-a=solidFile]').disabled = !!this.cmd;
      for (const a of ['measure', 'section', 'paint']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body;
      this.showNext(); // (nothing chosen: what usually comes next, in the suggestions table)
    }
    for (const b of bar.querySelectorAll('[data-a]:not([data-a=relate])')) b.addEventListener('click', () => this.action(b.dataset.a));
    for (const b of bar.querySelectorAll('[data-origin]')) b.addEventListener('click', () => this.setSketchOrigin(b.dataset.origin));
    this.sketchState();
    if (this.mode === 'sketch') { this.sk.renderFilters(); showSnapFilters(this.els.viewport, false); } else this.els.viewport.querySelector(':scope > .sk-filters:not(.snap-filters)')?.remove();
    bar.querySelector('[data-a=relate]')?.addEventListener('click', (e) => { e.stopPropagation(); bar.querySelector('.sk-relmenu').classList.toggle('open'); });
    for (const b of bar.querySelectorAll('[data-rel]')) {
      b.addEventListener('click', () => { bar.querySelector('.sk-relmenu').classList.remove('open'); this.sk.relType = b.dataset.rel; this.sk.setTool('relate'); });
    }
    const off = bar.querySelector('[data-k=planeOffset]');
    if (off) {
      const chip = off.closest('.m-offset'), show = () => chip.isConnected && this.showPlaneArrow((chip.matches(':hover') || chip.contains(document.activeElement)));
      for (const ev of ['mouseenter', 'mouseleave', 'focusin', 'focusout']) chip.addEventListener(ev, () => setTimeout(show));
      show(); // (drawn again over a bar drawn anew under the mouse)
      off.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') off.blur(); });
      off.addEventListener('change', () => {
        const v = parseFloat(String(off.value).replace(',', '.'));
        if (!Number.isFinite(v) || !this.sk) return;
        this.sk.f.plane = { ...this.sk.f.plane, offset: v };
        if (!v) delete this.sk.f.plane.offset;
        this.view.lookAt(this.frame(), this.sketchSpan());
        this.sk.draw();
        show(); // (the arrow moves with the plane)
      });
    }
    this.updateUndo();
    fitBar(bar); // (icons only when the names do not fit)
    const h = this.$('.m-hint');
    if (h) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`;
  }

  /** The offset arrow (which way + moves the sketch plane) — only while the ↕ Plane at chip is pointed at or typed
   *  in: it would be in the way of drawing otherwise. */
  showPlaneArrow(on) {
    this.view.setPlaneArrow(on && this.mode === 'sketch' && this.planeArrowLabel != null ? this.frame() : null, this.planeArrowLabel || '');
  }

  updateUndo() {
    const u = this.$('.m-cmdbar [data-a=undo]'), r = this.$('.m-cmdbar [data-a=redo]');
    if (u) u.disabled = !this.history.canUndo();
    if (r) r.disabled = !this.history.canRedo();
  }

  action(a) {
    if (a === 'sketch') return this.startSketch();
    if (a === 'extrude') return this.startExtrude();
    if (a === 'fillet' || a === 'chamfer') return this.startRound(a);
    if (a === 'hole') return this.startHole();
    if (a === 'revolve') return this.startRevolve();
    if (a === 'toPrint') return this.toPrint();
    if (a === 'measure') return this.toggleMeasure();
    if (a === 'paint') return this.togglePaint();
    if (a === 'section') return this.toggleSection();
    if (a === 'planes') return this.togglePlanes();
    if (a === 'printcheck') return this.togglePrintCheck();
    if (a === 'cog') return this.toggleCog();
    if (a === 'shell') return this.startShell();
    if (a === 'pattern') return this.mode === 'sketch' ? this.sk.startPattern() : this.startPattern();
    if (a === 'draft') return this.startDraft();
    if (a === 'split') return this.startSplit();
    if (a === 'rib') return this.startRib();
    if (a === 'solidFile') return this.pickSolid();
    if (a === 'duplicatePart') return this.hooks.duplicatePart?.();
    if (a === 'saveToLibrary') return this.hooks.saveToLibrary?.();
    if (a === 'saveBack') return this.hooks.saveBackToLibrary?.();
    if (a === 'mirror') return this.mode === 'sketch' ? this.sk.setTool('mirror') : this.startMirror();
    if (a === 'construction' && this.mode === 'sketch') return this.sk.toggleConstruction();
    if (a === 'merge' && this.mode === 'sketch') return this.sk.startMerge();
    if (a === 'loft' || a === 'sweep') return this.startProfiles(a);
    if (a === 'decal') return this.startDecal();
    if (a === 'undo') return this.history.go(-1);
    if (a === 'redo') return this.history.go(1);
    if (a.startsWith('view-')) return this.view.setView(a.slice(5));
    if (a.startsWith('datum-')) return this.enterSketch({ datum: a.slice(6) });
    if (a.startsWith('plane-')) return this.movePlane(a.slice(6));
    if (a === 'cancelPlane') return this.cancelPlane();
    if (a === 'midPlane') return this.toggleMidPick();
    if (a === 'autodim' && this.sk) return this.sk.autoDimension();
    if (['rect', 'line', 'slot', 'spline', 'circle', 'arc', 'round', 'trim', 'extend', 'offset', 'select', 'dim'].includes(a)) return this.sk.setTool(a);
    if (a === 'outline') return this.insertOutline();
    if (a === 'text' && this.sk) return this.insertText();
    if (a === 'finish') return this.finishSketch();
    if (a === 'cancelSketch') return this.cancelSketch();
    return null;
  }

  toast(...a) { this.hooks.toast(...a); }

  /** The line under the toolbar; point: the control it names (pointat.js — a short ring on it). */
  hint(text, point = null) {
    const h = this.$('.m-hint'), bar = this.$('.m-cmdbar');
    h.hidden = !text;
    h.textContent = text || '';
    if (bar) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`; // below the bar, also when it wraps to two rows
    if (text && point) pointAt(point, { key: text });
  }

  // ------------------------------------------------------------------ feature tree
  sketches() { return this.part.features.slice(0, this.usable()).filter((f) => f.type === 'sketch'); }
  status(id) { return this.result?.features?.find((s) => s.id === id); }

  renderTree() {
    if (this.barDrag) return; // (the rollback bar is being dragged: drawn again when let go)
    const tree = this.$('.mt-tree');
    const fs = this.part.features, byId = new Map(fs.map((f) => [f.id, f]));
    this.$('.mt-start').hidden = fs.length > 0;
    tree.innerHTML = '';
    // the tree's shape: a step with the sketch it is made from under it, pattern / mirror with links to what they
    // repeat, the reference points in "Reference" at the top (each row's fold remembered; folded at first)
    const shape = this.treeShapeNow = treeShape(fs, sketchesOf);
    this.rolledIds = new Set(fs.slice(this.barAt()).map((f) => f.id)); // (⏮ under the rollback bar: greyed)
    for (const id of [this.selected, this.sk?.f.id, this.cmd?.feature.id]) this.openTo(id);
    if (fs.length) this.refGroup(tree, shape, byId);
    const addRow = (f, depth, hidden, parentId) => {
      const kids = (shape.kids.get(f.id) || []).filter((k) => byId.has(k.id)), open = this.treeOpen.has(f.id);
      const row = this.stepRow(f, depth, parentId, kids.length ? open : null, shape);
      row.hidden = hidden;
      tree.appendChild(row);
      for (const k of kids) {
        if (!k.link) { addRow(byId.get(k.id), depth + 1, hidden || !open, f.id); continue; }
        const l = this.linkRow(byId.get(k.id), k.why, depth + 1, shape);
        l.hidden = hidden || !open;
        tree.appendChild(l);
      }
    };
    for (const id of shape.top) addRow(byId.get(id), 0, false, null);
    this.rollbar(tree, shape);
    if (this.selected && this.selected !== this.treeScrolled) { // chosen (also by a click on the part): its row in sight
      const row = tree.querySelector(`.mt-item[data-id="${CSS.escape(this.selected)}"]`);
      if (row && !row.hidden) row.scrollIntoView({ block: 'nearest' });
    }
    this.treeScrolled = this.selected;
    this.showPoints();
  }

  /** The rows folded open (remembered): the Reference group 'ref' and the steps with something under them. */
  get treeOpen() {
    if (!this._treeOpen) { try { this._treeOpen = new Set(JSON.parse(localStorage.getItem(TREE_OPEN_KEY) || '[]')); } catch { this._treeOpen = new Set(); } }
    return this._treeOpen;
  }

  saveTreeOpen() { try { localStorage.setItem(TREE_OPEN_KEY, JSON.stringify([...this.treeOpen].slice(-200))); } catch { /* private mode */ } }

  /** The rows above a step folded open (it was chosen, or is being changed): its row can be seen. */
  openTo(id) {
    const par = this.treeShapeNow?.parent;
    let p = id && par?.get(id), changed = false;
    for (let n = 0; p && n < 20; n++, p = par.get(p)) if (!this.treeOpen.has(p)) { this.treeOpen.add(p); changed = true; }
    if (changed) this.saveTreeOpen();
  }

  toggleFold(id) {
    if (this.treeOpen.has(id)) this.treeOpen.delete(id); else this.treeOpen.add(id);
    this.saveTreeOpen();
    this.renderTree();
  }

  /** ▸ / ▾ in front of a row that has something under it (open: true / false), else an empty place of its width. */
  twist(open, what) {
    if (open === null || open === undefined) return '<span class="mt-tw"></span>';
    return `<span class="mt-tw" data-a="twist" title="${open ? `Hide ${what}` : `Show ${what}`}">${open ? '▾' : '▸'}</span>`;
  }

  /** The faces of a step lit lightly while the mouse is on its row (a sketch: the faces made from it). */
  hoverRow(row, id) {
    row.addEventListener('mouseenter', () => { if (this.mode === 'part' && this.result?.body) this.view.setHover(-1, this.stepFaceIds(id)); });
    row.addEventListener('mouseleave', () => { if (this.mode === 'part') this.view.setHover(-1, null); });
  }

  /** The Reference group at the top: the Top / Front / Right planes (✏ or a double-click: sketch on one) and the
   *  reference points. */
  refGroup(tree, shape, byId) {
    const open = this.treeOpen.has('ref'), free = this.mode === 'part' && !this.cmd;
    const head = document.createElement('div');
    head.className = 'mt-row mt-group';
    head.dataset.group = 'ref';
    head.title = 'The base planes and the reference points the part is built on';
    head.innerHTML = `${this.twist(open, 'the planes and points')}<span class="mt-icon">${treeIcon('plane', 'ref')}</span><span class="mt-name">Reference</span>`;
    head.addEventListener('click', () => this.toggleFold('ref'));
    tree.appendChild(head);
    for (const k of ['XY', 'XZ', 'YZ']) {
      const row = document.createElement('div');
      row.className = 'mt-row mt-plane';
      row.dataset.datum = k;
      row.hidden = !open;
      row.style.setProperty('--d', 1);
      row.title = 'Double-click: sketch on this plane';
      row.innerHTML = `${this.twist(null)}<span class="mt-icon">${treeIcon('plane', 'ref')}</span><span class="mt-name"></span><span class="mt-what">${k}</span>
        <span class="mt-acts"><button class="mini" data-a="sketchOn" title="Sketch on the ${DATUM_NAME[k]} plane (${k})">✏</button></span>`;
      row.querySelector('.mt-name').textContent = DATUM_NAME[k];
      const go = () => { if (free) this.enterSketch({ datum: k }); };
      row.addEventListener('click', (e) => { if (e.target.closest('[data-a=sketchOn]')) go(); });
      row.addEventListener('dblclick', go);
      tree.appendChild(row);
    }
    for (const id of shape.refs) {
      const row = this.stepRow(byId.get(id), 1, 'ref', null, shape);
      row.hidden = !open;
      tree.appendChild(row);
    }
  }

  /** A link to a step shown elsewhere in the tree (a sketch a second step is made from too, what a pattern / mirror
   *  repeats): lighter; a click goes to it. */
  linkRow(g, why, depth, shape) {
    const row = document.createElement('div');
    row.className = 'mt-row mt-link';
    row.dataset.link = g.id;
    row.dataset.why = why;
    row.style.setProperty('--d', depth);
    const at = this.part.features.find((x) => x.id === shape.parent.get(g.id));
    row.title = why === 'repeats' ? `Repeats “${g.name}” — click to go to it` : why === 'mirrors' ? `Mirrors “${g.name}” — click to go to it`
      : `Made from “${g.name}” too (it is under “${at?.name || '?'}”) — click to go to it`;
    row.innerHTML = `${this.twist(null)}<span class="mt-icon">${stepIcon(g)}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span><span class="mt-lnk">${treeIcon('link', 'link')}</span>`;
    row.querySelector('.mt-name').textContent = g.name;
    row.addEventListener('click', () => { this.treeScrolled = null; this.selectStep(g.id); });
    this.hoverRow(row, g.id);
    return row;
  }

  /** A step's row: ▸ (its sketch under it), icon, name, what it makes; ● 🏷 ✎ ✕ on hover; dragged up or down: it
   *  moves with its sketch. */
  stepRow(f, depth, parentId, open, shape) {
    const st = this.status(f.id);
    const row = document.createElement('div');
    const editing = (this.sk && this.sk.f.id === f.id) || (this.cmd && this.cmd.feature.id === f.id);
    const warn = st && st.ok && st.warnings?.length;
    row.className = `mt-row mt-item${f.id === this.selected ? ' on' : ''}${st && !st.ok ? ' bad' : ''}${warn ? ' warned' : ''}${editing ? ' editing' : ''}${f.suppressed ? ' off' : ''}${this.rolledIds?.has(f.id) ? ' rolled' : ''}`;
    row.dataset.id = f.id;
    row.dataset.kind = stepKind(f);
    row.dataset.group = stepGroup(f);
    row.dataset.depth = depth;
    if (parentId) row.dataset.parent = parentId;
    row.style.setProperty('--d', depth);
    row.innerHTML = `${this.twist(open, f.type === 'pattern' || f.type === 'mirror' ? 'what it repeats' : 'its sketch')}<span class="mt-icon">${stepIcon(f)}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>
      ${st && !st.ok ? '<span class="mt-warn">⚠</span>' : warn ? '<span class="mt-warn soft">⚠</span>' : ''}
      <span class="mt-acts"><button class="mini" data-a="off" title="${f.suppressed ? 'Turn this step on again' : 'Turn this step off for now (it is kept)'}">${f.suppressed ? '◌' : '●'}</button><button class="mini" data-a="rename" title="Rename this step">🏷</button><button class="mini" data-a="edit" title="Change this step (or double-click it)">✎</button><button class="mini danger" data-a="del" title="Delete this step">✕</button></span>`;
    row.querySelector('.mt-name').textContent = f.name;
    row.querySelector('.mt-what').textContent = f.suppressed ? 'off' : this.whatText(f);
    if (st && !st.ok) row.title = st.issues.join(' ');
    else if (warn) row.title = st.warnings.join(' ');
    else if (this.rolledIds?.has(f.id)) row.title = t('Rolled back: under the rollback bar — kept, not built now. Drag the bar below it, or ⤓ To the end.');
    row.addEventListener('contextmenu', (e) => { e.preventDefault(); this.stepMenu(f, e); });
    row.addEventListener('click', (e) => {
      const a = e.target.closest('[data-a]')?.dataset.a;
      if (a === 'twist') return this.toggleFold(f.id);
      if (a === 'edit') return this.edit(f.id);
      if (a === 'del') return this.remove(f.id);
      if (a === 'off') return this.toggleOff(f.id);
      if (a === 'rename') {
        renameInPlace(row.querySelector('.mt-name'), (n) => { f.name = n; this.history.commit(); this.render(); this.hooks.onChange?.(); });
        return null;
      }
      this.picks = [];
      if (!this.cmd) this.view.setEdgeHighlight();
      this.selectStep(f.id);
      if (!this.suggestStep(f.id)) this.dropSuggest(); // (what can be done with it: edit, rename, move, delete …)
      return null;
    });
    row.addEventListener('dblclick', (e) => { if (!e.target.closest('[data-a=twist]')) this.edit(f.id); });
    this.hoverRow(row, f.id);
    if (!editing && this.mode === 'part' && !this.cmd && depth === 0) { // dragged up or down the list: the step moves with its sketch (if what it uses stays before it)
      const block = (id) => [...(shape.kids.get(id) || []).filter((k) => !k.link).map((k) => k.id), id];
      const first = (id) => { const ids = new Set(block(id)); return this.part.features.find((x) => ids.has(x.id))?.id || id; };
      row.draggable = true;
      row.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/a3d-step', f.id); e.dataTransfer.effectAllowed = 'move'; row.classList.add('dragging'); });
      row.addEventListener('dragend', () => row.classList.remove('dragging'));
      row.addEventListener('dragover', (e) => {
        if (!e.dataTransfer.types.includes('text/a3d-step')) return;
        e.preventDefault();
        const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
        row.classList.toggle('drop-before', !after);
        row.classList.toggle('drop-after', after);
      });
      row.addEventListener('dragleave', () => row.classList.remove('drop-before', 'drop-after'));
      row.addEventListener('drop', (e) => {
        e.preventDefault();
        row.classList.remove('drop-before', 'drop-after');
        const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2, id = e.dataTransfer.getData('text/a3d-step');
        if (id && id !== f.id) this.moveStep(block(id), after ? f.id : first(f.id), after);
      });
    }
    return row;
  }

  // ------------------------------------------------------------------ ⏮ the rollback bar (SolidWorks / Solid Edge)
  /** How many steps are built: all, or those above the rollback bar (part.rollback: the id of the step it is under;
   *  saved with the part, one undo step each move). Exports, the print copy, assemblies and drawings follow it too (the
   *  server builds the part as the bar stands: doc.at_bar; steptree.js stepsAtBar). */
  barAt() {
    const r = this.part.rollback, i = r ? this.part.features.findIndex((f) => f.id === r) : -1;
    return i >= 0 ? i + 1 : this.part.features.length;
  }

  rolledBack() { return this.barAt() < this.part.features.length; }

  /** The steps above the bar (all of them when it is at the end). */
  builtSteps() { return this.part.features.slice(0, this.barAt()); }

  /** How many steps (from the first) a step being made may use — its sketch, what it repeats: those above the bar, or,
   *  while a step under the bar is changed, those before it. */
  usable() {
    const i = this.cmd && !this.cmd.isNew ? this.part.features.findIndex((f) => f.id === this.cmd.feature.id) : -1;
    return Math.max(this.barAt(), i);
  }

  /** New steps go in at the bar (at the end when it is there); the bar stays right under them. */
  insertSteps(...fs) {
    this.part.features.splice(this.barAt(), 0, ...fs);
    if (this.part.rollback) this.part.rollback = fs[fs.length - 1].id;
  }

  /** After a change: the bar under a deleted step goes up to the step before it; under the last step it is at the end. */
  fixBar() {
    const r = this.part.rollback, fs = this.part.features;
    if (!r) return;
    if (!fs.some((f) => f.id === r)) {
      const was = (this.history.base?.features || []).map((f) => f.id), live = new Set(fs.map((f) => f.id)), i = was.indexOf(r);
      const prev = i > 0 ? was.slice(0, i).reverse().find((id) => live.has(id)) : null;
      if (prev) this.part.rollback = prev; else delete this.part.rollback;
    }
    if (this.part.rollback === fs[fs.length - 1]?.id) delete this.part.rollback;
  }

  /** ⏮ The bar put under step `id` (null / 'end': at the end — every step built again): one undo step. */
  setRollback(id) {
    if (this.mode !== 'part' || this.cmd) return null;
    const fs = this.part.features;
    if (id && id !== 'end' && !fs.some((f) => f.id === id)) throw new Error(`No step ${id} — get_model lists the steps.`);
    if (!id || id === 'end') delete this.part.rollback; else this.part.rollback = id;
    this.closeCtx();
    this.commit();
    return this.inflight;
  }

  /** The bar in the tree (6 px, a line with a grip) under the last step built; dragged up or down between the top-level
   *  steps (the 3D view follows while dragging; Esc: back), ↑ / ↓ / Home / End keys; a double-click puts it at the
   *  end. Rolled back: "⤓ To the end" under the tree. */
  rollbar(tree, shape) {
    const fs = this.part.features, at = new Map(fs.map((f, i) => [f.id, i])), n = this.barAt();
    const top = shape.top.filter((id) => at.has(id));
    if (!top.length) return;
    const rows = top.map((id) => tree.querySelector(`.mt-item[data-depth="0"][data-id="${CSS.escape(id)}"]`));
    const block = (id) => [id, ...(shape.kids.get(id) || []).filter((k) => !k.link && at.has(k.id)).flatMap((k) => block(k.id))];
    // gap j: under top-level block j -> the bar under its last step in the part's order (the last gap: the end)
    const gapId = (j) => (j >= top.length - 1 ? null : block(top[j]).reduce((a, b) => (at.get(b) > at.get(a) ? b : a)));
    let cur = -1;
    top.forEach((id, j) => { if (at.get(id) < n) cur = j; });
    const free = this.mode === 'part' && !this.cmd, rolled = n < fs.length;
    const bar = document.createElement('div');
    bar.className = `mt-rollbar${rolled ? ' rolled' : ''}`;
    bar.tabIndex = free ? 0 : -1;
    bar.setAttribute('role', 'separator');
    bar.setAttribute('aria-orientation', 'horizontal');
    bar.setAttribute('aria-label', t('Rollback bar'));
    bar.title = t(free ? 'Rollback bar: drag it up to see the part as it was after that step — new steps go in here; drag it back down (or double-click it) for all steps. Keys: ↑ ↓, End'
      : 'Rollback bar (finish the open command to move it)');
    bar.innerHTML = '<i class="mt-rb-grip"></i>';
    let endBtn = null;
    if (rolled) {
      endBtn = document.createElement('div');
      endBtn.className = 'mt-rb-end';
      endBtn.innerHTML = `<span class="hint">${esc(t2('{n} step(s) rolled back', { n: fs.length - n }))}</span><button class="btn small" data-a="toEnd" title="${esc(t('Move the rollback bar to the end: every step built again'))}">⤓ ${esc(t('To the end'))}</button>`;
      endBtn.querySelector('button').disabled = !free;
      endBtn.querySelector('button').addEventListener('click', () => this.setRollback('end'));
      tree.appendChild(endBtn);
    }
    const place = (j) => { const next = rows[j + 1]; if (next) tree.insertBefore(bar, next); else if (endBtn) tree.insertBefore(bar, endBtn); else tree.appendChild(bar); };
    place(cur);
    if (this.barFocus && free) bar.focus({ preventScroll: true });
    bar.addEventListener('focus', () => { this.barFocus = true; });
    bar.addEventListener('blur', () => setTimeout(() => { if (bar.isConnected) this.barFocus = false; })); // (drawn anew: the new bar takes the focus)
    if (!free) return;
    const grey = () => { const k = this.barAt(); for (const r of tree.querySelectorAll('.mt-item')) r.classList.toggle('rolled', (at.get(r.dataset.id) ?? -1) >= k); };
    const preview = (j) => { const id = gapId(j); if (id) this.part.rollback = id; else delete this.part.rollback; grey(); this.rebuild(); };
    bar.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      bar.focus({ preventScroll: true }); // (keys move it next)
      bar.classList.add('dragging');
      const was = this.part.rollback, from = cur;
      this.barDrag = true;
      let moved = false;
      const bottom = () => { const all = [...tree.querySelectorAll('.mt-row')].filter((r) => !r.hidden); return all.length ? all[all.length - 1].getBoundingClientRect().bottom : 0; };
      const move = (ev) => {
        const ys = top.map((_, j) => (rows[j + 1] ? rows[j + 1].getBoundingClientRect().top : bottom()));
        let best = 0;
        ys.forEach((y, j) => { if (Math.abs(ev.clientY - y) < Math.abs(ev.clientY - ys[best])) best = j; });
        if (best !== cur) { cur = best; moved = true; place(cur); preview(cur); }
      };
      let done = false;
      const end = (cancel) => {
        if (done) return;
        done = true;
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', back);
        window.removeEventListener('keydown', key, true);
        bar.classList.remove('dragging');
        this.barDrag = false;
        if (cancel && cur !== from) { if (was) this.part.rollback = was; else delete this.part.rollback; this.render(); this.rebuild(); return; }
        if ((this.part.rollback || null) !== (was || null)) this.commit(); else if (moved) this.renderTree(); // (not moved: left as it is — a double-click finds the same bar)
      };
      const up = () => end(false), back = () => end(true);
      const key = (ev) => { if (ev.key === 'Escape') { ev.stopPropagation(); ev.preventDefault(); end(true); } };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', back);
      window.addEventListener('keydown', key, true);
    });
    bar.addEventListener('dblclick', () => this.setRollback('end'));
    bar.addEventListener('keydown', (e) => {
      const go = { ArrowUp: Math.max(0, cur - 1), ArrowDown: Math.min(top.length - 1, cur + 1), Home: 0, End: top.length - 1, Enter: top.length - 1 }[e.key];
      if (go === undefined) return;
      e.preventDefault();
      e.stopPropagation();
      this.barFocus = true;
      if (go !== cur) this.setRollback(gapId(go) || 'end');
    });
  }

  /** A step's row right-clicked: ⏮ Roll back to here (the bar under it), ⤓ To the end, ✎ Edit, ✕ Delete. Esc closes. */
  stepMenu(f, e) {
    this.closeCtx();
    if (this.mode !== 'part' || this.cmd) return;
    const fs = this.part.features, i = fs.indexOf(f), n = this.barAt();
    const items = [
      ['rollHere', '⏮', 'Roll back to here', 'Show the part as it was after this step — the steps under it are kept but not built; new steps go in under it', i === n - 1],
      ...(n < fs.length ? [['toEnd', '⤓', 'To the end', 'Move the rollback bar to the end: every step built again']] : []),
      ['edit', '✎', 'Edit the step', 'Change this step (or double-click it)'],
      ['del', '✕', 'Delete the step', 'Delete this step']];
    const menu = document.createElement('div');
    menu.className = 'menu-list mt-ctx';
    menu.innerHTML = items.map(([a, ic, label, title, off]) => `<button data-a="${a}" title="${esc(t(title))}"${off ? ' disabled' : ''}>${ic} ${esc(t(label))}</button>`).join('');
    menu.addEventListener('click', (ev) => {
      const a = ev.target.closest('[data-a]')?.dataset.a;
      if (!a) return;
      this.closeCtx();
      if (a === 'rollHere') this.setRollback(f.id);
      if (a === 'toEnd') this.setRollback('end');
      if (a === 'edit') this.edit(f.id);
      if (a === 'del') this.remove(f.id);
    });
    document.body.appendChild(menu);
    Object.assign(menu.style, { left: `${Math.max(4, Math.min(e.clientX, innerWidth - menu.offsetWidth - 4))}px`, top: `${Math.max(4, Math.min(e.clientY, innerHeight - menu.offsetHeight - 4))}px` });
    this.ctx = menu;
    const away = (ev) => { if (!menu.contains(ev.target)) this.closeCtx(); };
    const key = (ev) => { if (ev.key === 'Escape') { ev.stopPropagation(); this.closeCtx(); } };
    window.addEventListener('pointerdown', away, true);
    window.addEventListener('keydown', key, true);
    this.ctxOff = () => { window.removeEventListener('pointerdown', away, true); window.removeEventListener('keydown', key, true); };
  }

  /** The reference points (point steps) in the 3D view: a dot and its name each, the chosen one lit. */
  showPoints() {
    const at = this.result?.points || {};
    this.view.setPoints(this.part.features.filter((f) => f.type === 'point' && !f.suppressed && at[f.id])
      .map((f) => ({ id: f.id, name: f.name, xyz: at[f.id], on: f.id === this.selected, bad: this.status(f.id)?.ok === false })));
  }

  whatText(f) {
    const n = (k) => (f[k] || []).length;
    if (f.type === 'sketch') return this.planeText(f);
    if (f.type === 'extrude' && f.draft) return `${this.whatText({ ...f, draft: 0 })} · draft ${fmt(f.draft)}°`;
    if (f.type === 'extrude' && f.d2 && !f.symmetric) return `${this.whatText({ ...f, d2: 0 })} · other side ${fmt(f.d2)} mm`;
    if (f.type === 'extrude' && f.upto_next) return f.op === 'cut' ? 'cut up to next' : 'up to next';
    if (f.type === 'extrude' && f.upto) return `${f.op === 'cut' ? 'cut ' : ''}up to a face${f.offset ? ` ${f.offset > 0 ? '+' : ''}${fmt(f.offset)} mm` : ''}`;
    if (f.type === 'extrude') return f.op === 'cut' ? (f.through ? 'cut through all' : `cut ${fmt(f.d)} mm`) : `${fmt(f.d)} mm`;
    if (f.type === 'fillet') return `R ${fmt(f.r)} · ${n('edges')} edge(s)`;
    if (f.type === 'chamfer') return `${fmt(f.d)} mm · ${n('edges')} edge(s)`;
    if (f.type === 'hole') return `${this.holeSizeText(f)}${holeSpec(f).threaded ? '' : f.standard ? ` Ø${fmt(f.d)}` : ''}${holeSpec(f).shape === 'd_flat' ? ` D${fmt(f.flat ?? dFlat(f.d))}` : ''}${f.fit ? ` ${f.fit}` : ''}${f.head === 'cbore' ? ` ⌴Ø${fmt(f.head_d)}×${fmt(f.head_depth)}` : f.head === 'csk' ? ` ⌵Ø${fmt(f.head_d)}` : ''}${f.teardrop ? ' ▲ teardrop' : ''} · ${n('points')} hole(s)${f.through === false ? ` · ${fmt(f.depth)} deep` : ''}`;
    if (f.type === 'revolve') return `${fmt(f.angle)}°${f.op === 'cut' ? ' cut' : ''}`;
    if (f.type === 'shell') return `wall ${fmt(f.t)} mm · ${n('faces')} open`;
    if (f.type === 'decal') return `${f.source === 'text' ? `“${f.text}”` : 'picture'} · ${fmt(f.h)} mm${f.op === 'cut' ? ' · engraved' : ' · raised'}`;
    if (f.type === 'loft') return `${(f.sketches || []).length} sketches${f.op === 'cut' ? ' · cut' : ''}`;
    if (f.type === 'sweep') return `along ${this.part.features.find((g) => g.id === f.path)?.name || '?'}${f.op === 'cut' ? ' · cut' : ''}`;
    if (f.type === 'draft') return `${fmt(f.angle)}° · ${this.part.features.find((g) => g.id === f.of)?.name || '?'}`;
    if (f.type === 'rib') return `${fmt(f.t)} mm · ${this.part.features.find((g) => g.id === f.sketch)?.name || '?'}${f.flip ? ' · ⇅' : ''}`;
    if (f.type === 'point') {
      const p = this.result?.points?.[f.id], at = f.at || {};
      const on = at.vertex ? 'a corner' : at.centre ? 'a centre' : at.mid ? 'an edge middle' : 'a fixed place';
      return `${on}${p ? ` · ${p.map((v) => fmt(+v.toFixed(3))).join(', ')}` : ''}`;
    }
    if (f.type === 'solid') return `${f.file || 'solid'} · ${{ add: 'joined', cut: 'cut out', ref: 'reference' }[f.op || 'add']}`;
    if (f.type === 'mirror') {
      const of = f.of === 'body' || !f.of ? 'the part' : this.part.features.find((g) => g.id === f.of)?.name || '?';
      return `${of} · ${f.plane?.datum ? f.plane.datum : 'a face'}${f.copy === false ? ' · moved' : ' · copy'}`;
    }
    if (f.type === 'split') {
      const pl = f.plane || {}, where = pl.datum ? DATUM_NAME[pl.datum] : pl.mid ? 'midway between two faces' : 'a face';
      return `${{ above: 'this side', below: 'the other side' }[f.keep] || 'both pieces'} · ${where}${pl.offset ? ` · ${pl.offset > 0 ? '+' : ''}${fmt(pl.offset)} mm` : ''}`;
    }
    if (f.type === 'pattern') return f.kind === 'circular' ? `${f.count}× around` : `${f.count}× · ${fmt(f.spacing)} mm apart`;
    return '';
  }

  /** The step a face belongs to: "F2:side:l1" -> F2 (also first-version {feature, role}). */
  faceOwner(ref) { return ref?.feature || String(ref?.name || '').split(':')[0] || null; }

  planeText(f) {
    if (f.plane?.datum) return `on ${DATUM_NAME[f.plane.datum]}${f.plane.offset ? ` ${f.plane.offset > 0 ? '+' : ''}${fmt(f.plane.offset)} mm` : ''}`;
    const src = this.part.features.find((g) => g.id === this.faceOwner(f.plane?.face));
    return src ? `on a face of ${src.name}` : 'on a face';
  }

  // ------------------------------------------------------------------ pointing at / clicking the part
  /** The step a face was made by, and the ids of all faces it made now. */
  stepFaces(face) {
    const id = this.faceOwner({ name: face?.name }), step = this.part.features.find((f) => f.id === id);
    if (!step) return null;
    const body = this.result?.body; // (each step's faces looked up once per body: the mouse asks again and again)
    if (this.stepIds?.body !== body) this.stepIds = { body, of: new Map() };
    if (!this.stepIds.of.has(id)) this.stepIds.of.set(id, (body?.faces || []).filter((f) => [f.name, ...(f.names || [])].some((n) => String(n).split(':')[0] === id)).map((f) => f.id));
    return { step, ids: this.stepIds.of.get(id) }; // (the same list while the body stays: not changed by its users)
  }

  /** With no tool on: the edge under the mouse lit (a line or a circle), and the snap points of the hovered step
   *  (its faces' corners, edge middles and centres, by the snap filters) shown as dots. */
  hoverMarks(e, fs) {
    const body = this.view.body, hk = hoverKinds(), i = body && hk.edges ? this.view.pickEdge(e.clientX, e.clientY, 7) : -1;
    this.view.setHoverEdges(i >= 0 ? [{ pts: body.edges[i].pts }] : [], i >= 0 ? `e${i}` : '');
    if (!fs || !body || !hk.points) { this.view.setHoverSnaps([]); return; }
    const kinds = snapKinds(), key = `${fs.step.id}|${Object.entries(kinds).map(([k, v]) => (v ? k : '')).join('')}`;
    if (key === this.view.hoverSnapKey) return;
    const ids = new Set(fs.ids), idx = new Set(body.faces.map((f, k) => (ids.has(f.id) ? k : -1)).filter((k) => k >= 0));
    this.view.setHoverSnaps(snapPoints(body.edges.filter((ed) => ed.faces.some((k) => idx.has(k))), null, kinds), key);
  }

  /** The faces a step made; for a sketch, the faces of the steps made from it. */
  stepFaceIds(id) {
    const f = this.part.features.find((g) => g.id === id);
    const ids = f?.type === 'sketch' ? this.part.features.filter((g) => sketchesOf(g).includes(id)).map((g) => g.id) : [id];
    return (this.result?.body?.faces || []).filter((x) => [x.name, ...(x.names || [])].some((n) => ids.includes(String(n).split(':')[0]))).map((x) => x.id);
  }

  /** A step chosen (in the list, or by a click on the part): it is marked in the 3D view and its sizes show on the
   *  finished part, to change them there (a sketch's sizes on its plane). */
  selectStep(id) {
    this.openTo(id); // (its row in the tree in sight: what it is under folded open)
    if (this.mode !== 'part' || this.cmd) { this.selected = id; this.renderTree(); return; }
    this.closeCtx();
    const was = this.part.features.find((g) => g.id === this.selected);
    this.selected = id;
    const f = this.part.features.find((g) => g.id === id);
    this.view.setSelectedFaces(f ? this.stepFaceIds(id) : null);
    this.renderTree();
    if (id) this.$(`.mt-tree .mt-item[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' }); // (its row in sight)
    if (was?.type === 'hole' || f?.type === 'hole') this.renderProps(); // (a hole's own fields in the right panel — or the part's again)
    this.showOutlines();
    this.showStepDims(f || null);
  }

  /** The little name label at the mouse. */
  tip(t) {
    let el = this.$('.m-tip');
    if (!t) { if (el) el.hidden = true; return; }
    if (!el) { el = document.createElement('div'); el.className = 'm-tip'; this.els.viewport.appendChild(el); }
    const vr = this.els.viewport.getBoundingClientRect();
    el.hidden = false;
    el.textContent = t.text;
    Object.assign(el.style, { left: `${t.x - vr.left + 14}px`, top: `${t.y - vr.top + 14}px` });
  }

  /** A snap point picked (no tool on): marked, and what to do with it suggested — what it belongs to first (a round
   *  edge's centre / quadrant: ◎ Select the hole, ◯ Select the circle; an edge's middle or a corner: ⟋ Select the edge),
   *  then measure from it, copy it, ask the AI; an edge's middle (edge `ei` under it): round / bevel that edge. */
  pickSnap(sp, ei = -1, at = null) {
    const p = sp.point, xyz = [p.x, p.y, p.z].map((v) => fmt(+v.toFixed(3))).join(', ');
    const kind = sp.snap === 'point' ? sp.name : `${t({ corner: 'A corner', midpoint: 'An edge midpoint', centre: 'A centre', quadrant: 'A quadrant', origin: 'Origin' }[sp.snap])}${sp.r ? ` Ø${fmt(+(2 * sp.r).toFixed(2))}` : ''}`; // (a ring's: its Ø)
    if (sp.snap === 'point') this.selectStep(sp.id); // a reference point: its step chosen
    this.view.setMeasure([p]);
    const ref = ei >= 0 && this.edgeRef(ei);
    if (ref) this.view.setEdgeHighlight(-1, [ei]);
    const sg = showSuggest(this.els.viewport, `${kind} · ${xyz}`, [
      ...this.ownerItems(sp, ei, at),
      ...(ref ? this.edgeItems([ref]) : []),
      ...(['corner', 'midpoint', 'centre'].includes(sp.snap) ? [{ icon: '•', label: t('Reference point here'), title: t('A point that stays on this place of the part when it changes — sketches and 📏 Measure snap to it'),
        run: () => { this.dropSuggest(); this.addPoint(sp); } }] : []),
      { icon: '📏', label: t('Measure from here'), run: () => {
        this.dropSuggest();
        if (!this.measuring) this.toggleMeasure();
        if (this.measuring) this.ms.from({ kind: 'point', p: p.clone(), snap: sp.snap, name: sp.name || '' });
      } },
      { icon: '⧉', label: t('Copy its coordinates'), run: () => { navigator.clipboard?.writeText(xyz).catch(() => {}); this.hooks.toast(`${t('Copied')}: ${xyz}`, 'info', 2500); } },
    ], t('No tool on: a click on a corner, an edge\'s middle or a centre picks it'), `${t('in the 3D model')}: ${t('the point')} (${xyz}) — ${kind.toLowerCase()} ${t('of the part')}`);
    if (sg) sg.dataset.from = 'face';
  }

  /** What a snap point belongs to, as rows that choose it (the table then becomes its): a round edge's centre or
   *  quadrant -> ◎ Select the hole (a Hole step: the step; another round cut: its round face) and ◯ Select the circle;
   *  an edge's middle -> ⟋ Select the edge; a corner -> the edges that meet there. */
  ownerItems(sp, ei = -1, at = null) {
    const b = this.result?.body, p = sp.point, out = [];
    if (!b) return out;
    const near = (q) => q.distanceTo(p) < 1e-5 * (1 + this.view.size);
    const named = (e) => e.faces.length === 2 && e.faces.every((k) => b.faces[k]?.name);
    if (sp.snap === 'centre' || sp.snap === 'quadrant') {
      const rings = b.edges.map((e, i) => [e, i]).filter(([e]) => named(e) && snapPoints([e], null, { [sp.snap]: true }).some((q) => near(q.point)));
      const holes = new Map(), walls = new Map();
      for (const [e] of rings) {
        for (const k of e.faces) {
          const f = b.faces[k], step = this.part.features.find((g) => g.id === this.faceOwner({ name: f.name }));
          if (step?.type === 'hole') holes.set(step.id, step);
          else if (f.type === 'cylinder' && !walls.has(k)) walls.set(k, f);
        }
      }
      for (const h of holes.values()) {
        out.push({ icon: '◎', label: `${t('Select the hole')} ${this.holeSizeText(h)}`, rank: -6, title: t('The hole step: its type, size, ⁂ pattern, Ø'),
          run: () => { this.dropSuggest(); this.selectStep(h.id); this.suggestStep(h.id); } });
      }
      if (!holes.size) {
        for (const [k, f] of walls) {
          out.push({ icon: '◎', label: `${t('Select the round face')} Ø${fmt(2 * (f.radius || 0))}`, rank: -6, title: t('Its round face: what can be done with it'),
            run: () => { const fs = this.stepFaces(f); if (fs) this.faceTable({ face: this.view.face(k) || f, point: p.clone() }, fs, at || { clientX: 0, clientY: 0 }); } });
        }
      }
      for (const [e, i] of rings) {
        const r = this.edgeRef(i), sz = this.edgeSize(i);
        if (!r || !sz) continue;
        const full = Math.hypot(e.pts[0] - e.pts[e.pts.length - 3], e.pts[1] - e.pts[e.pts.length - 2], e.pts[2] - e.pts[e.pts.length - 1]) < 1e-6;
        out.push({ icon: full ? '◯' : '◠', label: full ? `${t('Select the circle')} Ø${fmt(sz.d)}` : `${t('Select the arc')} R${fmt(sz.d / 2)}`, rank: -5,
          title: t('The round edge: fillet / chamfer it, its size'), run: () => this.pickEdge(i, r) });
      }
    } else if (sp.snap === 'midpoint' && ei >= 0) {
      const r = this.edgeRef(ei);
      if (r) out.push({ icon: '⟋', label: t('Select the edge'), rank: -5, title: t('The edge: fillet / chamfer it, its length'), run: () => this.pickEdge(ei, r) });
    } else if (sp.snap === 'corner') {
      b.edges.forEach((e, i) => {
        if (out.length >= 3 || !named(e) || e.pts.length < 6) return;
        const n = e.pts.length, ends = [[e.pts[0], e.pts[1], e.pts[2]], [e.pts[n - 3], e.pts[n - 2], e.pts[n - 1]]];
        if (!ends.some((q) => Math.hypot(q[0] - p.x, q[1] - p.y, q[2] - p.z) < 1e-5 * (1 + this.view.size))) return;
        const r = this.edgeRef(i), sz = this.edgeSize(i);
        if (r) out.push({ icon: '⟋', label: `${t('Select the edge')} · ${fmt(+sz.L.toFixed(2))} mm`, rank: -5 + out.length * 0.1, title: t('The edge: fillet / chamfer it, its length'), run: () => this.pickEdge(i, r) });
      });
    }
    return out;
  }

  /** A snap point of the part -> what a point step keeps: the faces meeting at the corner, or the round / straight edge
   *  it is the centre / middle of (named by its two faces), so it follows the part; null: none here. */
  pointRef(p, snap) {
    const b = this.result?.body;
    if (!b) return null;
    const name = (k) => b.faces[k]?.name, fp = [p.x, p.y, p.z].map((v) => +v.toFixed(6));
    if (snap === 'corner') {
      const faces = new Set();
      for (const e of b.edges) {
        for (const k of [0, e.pts.length - 3]) {
          if (Math.hypot(e.pts[k] - p.x, e.pts[k + 1] - p.y, e.pts[k + 2] - p.z) < 1e-5) for (const fi of e.faces) if (name(fi)) faces.add(name(fi));
        }
      }
      return faces.size ? { vertex: { faces: [...faces], fp } } : null;
    }
    if (snap !== 'centre' && snap !== 'midpoint') return null;
    for (const e of b.edges) {
      if (e.faces.length !== 2 || !name(e.faces[0]) || !name(e.faces[1])) continue;
      if (snapPoints([e], null, { [snap]: true }).some((q) => q.point.distanceTo(p) < 1e-5)) return { [snap === 'centre' ? 'centre' : 'mid']: { a: name(e.faces[0]), b: name(e.faces[1]), fp: e.mid } };
    }
    return null;
  }

  /** • A reference point on a snap point of the part (a corner, an edge's middle, a centre): a step that follows it. */
  addPoint(sp) {
    if (this.mode !== 'part' || this.cmd) return null;
    const at = this.pointRef(sp.point, sp.snap);
    if (!at) { this.hooks.toast(t('No corner, edge middle or centre of the part here.'), 'warning', 4000); return null; }
    const f = { id: this.newId(), type: 'point', name: this.nextName('point'), at };
    this.insertSteps(f);
    this.selected = f.id;
    this.commit();
    return f;
  }

  /** The suggestions table of the 3D model (a face's tools) gone — the ✨ Next table in its place (nothing chosen). */
  dropSuggest() {
    const b = this.els.viewport.querySelector(':scope > .view-suggest[data-from=face]');
    b?.remove();
    if (!this.measuring) this.view.setMeasure([]);
    if (b) this.picks = []; // (the table gone: so is what it was for)
    if (b && !this.cmd) this.view.setEdgeHighlight(); // (picked edges: no longer marked)
    this.showNext();
  }

  /** ◜ / ◸ for picked edges (refs {a, b, fp}): the command open with them chosen (and their tangent chains). */
  roundPicked(type, refs) {
    this.picks = [];
    this.startRound(type);
    const f = this.cmd?.feature;
    if (!f) return;
    for (const i of this.refEdges(refs)) for (const j of this.chainOf(i, f)) { const r = this.edgeRef(j); if (r && !f.edges.some((x) => this.sameRef(x, r))) f.edges.push(r); }
    this.cmd.lastPick = t2('{n} edge(s) chosen — click more, or OK.', { n: f.edges.length });
    this.renderProps();
    this.rebuild();
  }

  /** An edge's size: its length, or (a full circle) its diameter -> {round, d, L}. */
  edgeSize(i) {
    const ed = this.result?.body?.edges[i];
    if (!ed) return null;
    let L = 0;
    for (let k = 3; k < ed.pts.length; k += 3) L += Math.hypot(ed.pts[k] - ed.pts[k - 3], ed.pts[k + 1] - ed.pts[k - 2], ed.pts[k + 2] - ed.pts[k - 1]);
    const P = [];
    for (let k = 0; k < ed.pts.length; k += 3) P.push(ed.pts.slice(k, k + 3));
    if (P.length > 2 && Math.hypot(...P[0].map((x, j) => x - P[P.length - 1][j])) < 1e-6) P.pop(); // a closed loop: its first point twice
    const c = P.reduce((s, p) => s.map((x, j) => x + p[j] / P.length), [0, 0, 0]);
    const rs = P.map((p) => Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2])), r0 = rs.reduce((s, x) => s + x, 0) / rs.length;
    const round = P.length > 8 && rs.every((x) => Math.abs(x - r0) < r0 * 0.01 + 1e-6) && Math.abs(L - 2 * Math.PI * r0) < L * 0.02;
    return { round, d: 2 * r0, L };
  }

  /** The suggestions for picked edges (refs): ◜ Fillet and ◸ Chamfer first — a single edge: its size too. */
  edgeItems(refs) {
    const one = refs.length === 1, idx = one ? this.refEdges(refs)[0] : -1, sz = idx >= 0 ? this.edgeSize(idx) : null;
    return [
      { icon: '◜', label: t(one ? 'Fillet this edge' : 'Fillet these edges'), rank: 0, title: t('Round it off — the radius in the panel, the preview in the view'), run: () => { this.dropSuggest(); this.roundPicked('fillet', refs); } },
      { icon: '◸', label: t(one ? 'Chamfer this edge' : 'Chamfer these edges'), rank: 1, title: t('Bevel it — the size in the panel, the preview in the view'), run: () => { this.dropSuggest(); this.roundPicked('chamfer', refs); } },
      ...(sz ? [{ icon: '📏', label: sz.round ? `Ø ${fmt(sz.d)} mm` : `${t('Length')} ${fmt(sz.L)} mm`, rank: 2.5, title: t('Its size — 📏 Measure for more'), run: () => this.hooks.toast(sz.round ? `Ø ${fmt(sz.d)} mm` : `${t('Length')} ${fmt(sz.L)} mm`, 'info', 3000) }] : []),
    ];
  }

  /** One edge clicked (no tool on): it is marked and ◜ Fillet / ◸ Chamfer it suggested first; a Hole step's rim: that
   *  hole chosen too, its Type / Size rows above. */
  pickEdge(i, ref) {
    const hole = [ref.a, ref.b].map((n) => this.part.features.find((g) => g.id === this.faceOwner({ name: n }))).find((g) => g?.type === 'hole');
    this.selectStep(hole ? hole.id : null);
    this.view.setEdgeHighlight(-1, [i]);
    const items = [...(hole ? [...this.holeItems(hole), { section: t('An edge') }] : []), ...this.edgeItems([ref])];
    const sg = showSuggest(this.els.viewport, hole ? `${hole.name} · ${t('An edge')}` : t('An edge'), items, t('Ctrl+click more edges: round them all at once'),
      `${t('in the 3D model')}: ${t('the edge between faces')} ${ref.a} ${t('and')} ${ref.b}`);
    if (sg) sg.dataset.from = 'face';
  }

  /** ✨ Next: with nothing chosen (no tool on), what usually comes next — the obvious next step first: a new model:
   *  ✏ a sketch; a sketch not used yet: ⬆ Extrude it; a solid: a sketch on it, ◎ a hole, ◜ / ◸ its edges … (ranked by
   *  the last step made). The rest of the 3D model's tools stay in the bar above. */
  showNext() {
    const vp = this.els.viewport, box = vp.querySelector(':scope > .view-suggest');
    const on = this.mode === 'part' && !this.cmd && !this.measuring && !this.painting && !this.selected && !this.$('.m-install:not([hidden])');
    if (!on) { if (box?.dataset.from === 'next') box.remove(); return; }
    if (box && box.dataset.from !== 'next') return; // (a face's / a step's table is up)
    const fs = this.part.features, body = this.result?.body, used = new Set(fs.flatMap(sketchesOf));
    const free = this.sketches().filter((s) => !used.has(s.id)).at(-1), last = this.builtSteps().filter((f) => f.type !== 'point').at(-1);
    const items = [];
    const add = (key, icon, label, title, run, rank) => items.push({ key, icon, label: t(label), title: t(title), rank, run: () => { this.dropSuggest(); run(); } });
    if (free) {
      if (isOpenLine(free)) { if (body) items.push({ icon: '⊿', label: `${t('Rib from')} „${free.name}“`, rank: 0, title: t('A rib from the open line: give the thickness — it fills up to the part'), run: () => { this.dropSuggest(); this.startRib(free.id); } }); }
      else {
        items.push({ icon: '⬆', label: `${t('Extrude the sketch')} „${free.name}“`, rank: 0, title: t('Give the sketch a height: add material or cut (E)'), run: () => { this.dropSuggest(); this.openExtrude(this.newExtrude(free.id), true); } });
        items.push({ icon: '⟳', label: `${t('Revolve the sketch')} „${free.name}“`, rank: 3, title: t('Spin a sketch around an axis (vases, knobs, wheels)'), run: () => { this.dropSuggest(); this.startRevolve(); } });
      }
      add('editsk', '✎', 'Edit the sketch', 'Change the sketch that is not used yet', () => this.edit(free.id), 4);
    }
    if (!body) {
      add('sketch', '✏', 'Sketch on a plane…', 'Start a sketch on the Top plane (another plane: in the bar of the sketch) — then ⬆ Extrude it', () => this.startSketch(), free ? 1 : 0);
      add('solid', '▣', 'Solid from a file…', 'Start from a STEP / STL / OBJ / 3MF solid', () => this.pickSolid(), 5);
    } else {
      // ranked by what was made last: a hole -> repeat it; a solid -> a sketch on it, a hole, its edges
      const R = last?.type === 'hole' ? { pattern: 0, mirror: 1, hole: 2, sketch: 3, fillet: 4, chamfer: 5, shell: 6, measure: 7 }
        : last?.type === 'fillet' || last?.type === 'chamfer' ? { sketch: 0, hole: 1, fillet: 2, chamfer: 3, print: 4, measure: 5, shell: 6, pattern: 7 }
          : { sketch: 0, hole: 1, fillet: 2, chamfer: 3, shell: 4, pattern: 5, mirror: 6, measure: 7 };
      const off = free ? 1 : 0; // (⬆ the free sketch first)
      add('sketch', '✏', 'Sketch on a face or plane…', 'Click a flat face of the part (pockets, bosses, holes) — or choose Top / Front / Right', () => this.startSketch(), (R.sketch ?? 8) + off);
      add('hole', '◎', 'Hole…', 'Drill holes: click on a flat face where they go (standard sizes, threads)', () => this.startHole(), (R.hole ?? 8) + off);
      add('fillet', '◜', 'Fillet edges…', 'Round edges: click the edges (or a face: all its edges), give the radius', () => this.startRound('fillet'), (R.fillet ?? 8) + off);
      add('chamfer', '◸', 'Chamfer edges…', 'Bevel edges: click the edges, give the size', () => this.startRound('chamfer'), (R.chamfer ?? 8) + off);
      add('shell', '▢', 'Shell…', 'Hollow the part out: click the face(s) to leave open, give the wall thickness', () => this.startShell(), (R.shell ?? 9) + off);
      if (this.repeatable().length) add('pattern', '⁂', last?.type === 'hole' ? 'Pattern the last hole' : 'Pattern…', 'Repeat a step (holes, a boss, a cut) in a row or around a circle', () => this.startPattern(last?.type === 'hole' ? last.id : null), (R.pattern ?? 9) + off);
      add('mirror', '⇋', 'Mirror…', 'Mirror the part across a base plane or a flat face', () => this.startMirror(), (R.mirror ?? 10) + off);
      add('measure', '📏', 'Measure', 'Click a face or an edge (its size), or two spots (the distance between them) (M)', () => this.toggleMeasure(), (R.measure ?? 10) + off);
      if (this.hooks.toPrint) add('print', '🖨', 'Prepare for 3D print', 'Check it fits your printer, split it into exact pieces with joints — in a printing copy of this part', () => this.toPrint(), (R.print ?? 11) + off);
      add('paint', '🎨', 'Paint faces', 'Colour faces: click them, then pick a colour', () => this.togglePaint(), 12);
      if (this.hooks.newSheet) add('sheet', '📄', 'Drawing', 'A drawing sheet of this part to edit: its views and dimensions (light / medium / full), moved, deleted, added — it follows the part when it changes', () => this.hooks.newSheet(), (R.sheet ?? 4.5) + off);
    }
    // short (it stays up while nothing is chosen — over the part): the likeliest few; the rest are in the bar above
    const top = [...items].sort((a, b) => a.rank - b.rank).slice(0, NEXT_ROWS);
    const sg = showSuggest(vp, fs.length ? t('Next step') : t('New part'), top,
      body && fs.length <= 2 ? t('Or click a face, an edge or a step: what fits it is offered') : '', `${t('in the 3D model')}: ${t('nothing selected')}`);
    if (sg) sg.dataset.from = 'next';
  }

  /** A step chosen in the list: what can be done with it — ✎ Edit first (a sketch not used yet: ⬆ Extrude it), then
   *  rename, turn off, move up / down, delete; a hole or a boss: ⁂ repeat it. */
  suggestStep(id) {
    const f = this.part.features.find((g) => g.id === id);
    if (this.mode !== 'part' || this.cmd || !f) return null;
    if (isOpenLine(f)) return this.suggestSketch(id);
    const used = new Set(this.part.features.flatMap(sketchesOf)), top = this.treeShapeNow?.top || [], k = top.indexOf(id);
    const items = [];
    const add = (icon, label, run, rank, o = {}) => items.push({ icon, label: t(label), rank, run: () => { this.dropSuggest(); run(); }, ...o });
    const hole = f.type === 'hole';
    if (hole) items.push(...this.holeItems(f)); // its types, sizes, thread (all shown), ✎ Edit the hole; ⁂, 📏, ✕ and ↑ / ↓ next (🏷, ◌, ⏮ under ⋯ Show all)
    if (f.type === 'sketch' && !used.has(f.id)) {
      add('⬆', 'Extrude it', () => this.openExtrude(this.newExtrude(f.id), true), 0, { title: t('Give the sketch a height: add material or cut (E)') });
      add('⟳', 'Revolve it', () => this.startRevolve(), 5);
    }
    if (f.type !== 'hole') add('✎', f.type === 'sketch' ? 'Edit the sketch' : 'Edit the step', () => this.edit(f.id), 1, { title: t('Change this step (or double-click it)') });
    add('🏷', 'Rename', () => this.renameStep(f.id), hole ? 8.5 : 2);
    if (REPEATABLE.has(f.type) && f.type !== 'pattern' && this.result?.body && !f.suppressed) add('⁂', 'Pattern it', () => this.startPattern(f.id), 3, { title: t('Repeat this step in a row or around a circle') });
    add(f.suppressed ? '●' : '◌', f.suppressed ? 'Turn it on' : 'Turn it off', () => this.toggleOff(f.id), hole ? 8.7 : 6);
    if (k > 0) add('↑', 'Move up', () => this.moveStep(this.stepBlock(id), this.blockFirst(top[k - 1]), false), 7, { title: t('One place earlier in the list (refused when it would come before a step it uses)') });
    if (k >= 0 && k < top.length - 1) add('↓', 'Move down', () => this.moveStep(this.stepBlock(id), top[k + 1], true), 7.5, { title: t('One place later in the list') });
    const i = this.part.features.indexOf(f);
    if (i !== this.barAt() - 1) add('⏮', 'Roll back to here', () => this.setRollback(f.id), 8, { title: t('Show the part as it was after this step — the steps under it are kept but not built; new steps go in under it') });
    add('✕', 'Delete the step', () => this.remove(f.id), 4, { danger: true });
    const sg = showSuggest(this.els.viewport, f.name, hole ? items : items.sort((a, b) => a.rank - b.rank), '', `${t('in the 3D model')}: ${t('step')} ${f.id} “${f.name}”`); // (a hole's: in its sections, ranked by the table)
    if (sg) sg.dataset.from = 'face';
    return sg;
  }

  /** A Hole step's own rows in the suggestions, its properties each on its own (as in SolidWorks / Solid Edge): its
   *  shape (plain, ⌴, ⌵, D — the current one ✓), its thread (🔩 With thread M5 ✓ — a click takes it off — or 🔩 Add
   *  thread M5; threaded: Thread: show / hide, Real ↔ Cosmetic), its depth (through all ⇄ to a depth) and the sizes next
   *  to its own — one click switches it in place, one undo step; then ✎ Edit the hole and 📏 its Ø. The choices always
   *  show (past the table's top N); the table scrolls when they do not fit. Only steps made by ◎ Hole. */
  holeItems(f) {
    const sp = holeSpec(f), id = f.id, out = [], through = f.through !== false;
    out.push({ section: t('Shape') });
    HOLE_SHAPES.forEach(([k, l, icon], j) => out.push({ icon, label: t(l).replace(/^[⌴⌵]\s*/, ''), on: k === sp.shape, always: true, rank: -30 + j,
      title: t('The hole’s shape: plain, ⌴ counterbore (a socket head sunk in), ⌵ countersink (a flat head flush), D (a shaft with a flat)'), run: () => this.setHoleProps(id, { shape: k }) }));
    if (sp.shape !== 'd_flat') {
      out.push({ section: t('Thread') });
      const m = this.threadFor(f);
      if (sp.threaded) {
        const mode = this.part.threads || 'hidden';
        out.push({ icon: '🔩', label: `${t('With thread')} ${sp.standard || m}`, on: true, always: true, rank: -25,
          title: t('Threaded — click: without a thread (the hole becomes the screw’s clearance Ø)'), run: () => this.setHoleProps(id, { threaded: false }) });
        out.push({ icon: '👁', label: mode === 'hidden' ? t('Thread: show') : t('Thread: hide'), always: true, rank: -24,
          title: t('Show the threads of the part’s threaded holes as light lines — or hide them (plain holes at the tap drill)'),
          run: () => this.holeThreads(id, mode === 'hidden' ? 'cosmetic' : 'hidden') });
        out.push(mode === 'real'
          ? { icon: '〰', label: t('Cosmetic thread'), always: true, rank: -23, title: t('Thin helix lines on the holes — view only, quick'), run: () => this.holeThreads(id, 'cosmetic') }
          : { icon: '⚙', label: t('Real thread (slower)'), always: true, rank: -23, title: t('The threads cut into the solid (ISO metric, 60°) — in STEP / STL / 3MF exports and the print split; slower'), run: () => this.holeThreads(id, 'real') });
      } else {
        out.push({ icon: '🔩', label: `${t('Add thread')} ${m}`, always: true, rank: -25, title: t('Make it a threaded hole of this size (its Ø becomes the tap drill’s)'), run: () => this.setHoleProps(id, { threaded: true, standard: m }) });
      }
    }
    out.push({ section: t('Depth') });
    out.push({ icon: through ? '⇣' : '↧', label: through ? `${t('Through all')} ⇄ ${t('to a depth')}` : `${t('To a depth')} ${fmt(f.depth)} mm ⇄ ${t('through all')}`, always: true, rank: -22,
      title: t('Through the part, or only to a depth (its number: ✎ Edit the hole, or its label on the part)'), run: () => this.setHoleDepth(id, !through) });
    out.push({ section: t('Size') });
    this.holeSizes(f).forEach((o, j) => out.push({ icon: '⌀', label: o.label, on: o.on, always: true, rank: -20 + j,
      title: t('The sizes next to this one (all of them: ✎ Edit the hole)'), run: () => this.setHoleSize(id, o.value) }));
    out.push({ section: `${t('Hole')} · ${f.name}` });
    out.push({ icon: '✎', label: t('Edit the hole'), rank: -2, title: t('All its settings — and ＋ Add position for more holes'), run: () => { this.dropSuggest(); this.edit(id); } });
    out.push({ icon: '📏', label: `${t('Measure it')}: Ø${fmt(f.d)}`, rank: 3.5, run: () => { this.dropSuggest(); this.hooks.toast(`${f.name}: Ø${fmt(f.d)}${f.head_d ? ` · ${t('Head Ø')} ${fmt(f.head_d)}` : ''}${f.through === false ? ` · ↧ ${fmt(f.depth)}` : ` · ${t('Through all')}`}`, 'info', 5000); } });
    return out;
  }

  /** The thread a hole without one would get: its screw size (a clearance / counterbore … for M5: M5), else the size whose
   *  tap drill its Ø is (Ø4.2: M5) or the nearest such. */
  threadFor(f) {
    const size = holeSpec(f).standard;
    if (size in THREADS) return size;
    return Object.keys(THREADS).reduce((a, b) => (Math.abs(THREADS[b] - f.d) < Math.abs(THREADS[a] - f.d) ? b : a));
  }

  /** 🔩 The thread rows of a chosen hole: how the part's threads show; the table shown again with the new state. */
  async holeThreads(id, mode) {
    await this.setThreads(mode);
    if (this.selected === id && !this.cmd) this.suggestStep(id);
  }

  /** Change properties of hole step f ({shape, threaded, standard} — the others kept): its sizes filled again from the
   *  table. A thread or a head needs a size: its own, else the last one used, else the nearest to its Ø; a D hole has
   *  no thread (threading one makes it plain); a hole made plain without a thread keeps its size (the clearance Ø). */
  applyHoleProps(f, props) {
    const next = { ...holeSpec(f), ...props };
    if (props.shape === 'd_flat') next.threaded = false;
    if (props.threaded && next.shape === 'd_flat') next.shape = 'plain';
    if (!next.standard && (next.threaded || next.shape === 'counterbore' || next.shape === 'countersink')) next.standard = this.lastHoleSize || nearestSize(f.d || 5);
    if (props.standard) this.lastHoleSize = props.standard;
    if (next.shape === 'd_flat' && f.flat === undefined) f.flat = dFlat(f.d);
    setHole(f, next);
  }

  /** A chosen hole's properties switched in place (the suggestions, its panel): one undo step. */
  setHoleProps(id, props) {
    const f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    this.applyHoleProps(f, props);
    this.changedHole(f);
  }

  /** A chosen hole through all, or to a depth (10 mm, or the depth it had): one undo step. */
  setHoleDepth(id, through) {
    const f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    f.through = through;
    if (!through && !(f.depth > 0)) f.depth = 10;
    this.changedHole(f);
  }

  /** A chosen hole's size switched in place (one undo step): "M6" (a screw's hole) or a Ø (mm). */
  setHoleSize(id, v) {
    const f = this.part.features.find((g) => g.id === id);
    if (!f || this.holeSizes(f).find((o) => o.value === v)?.on) return;
    if (typeof v === 'string') this.applyHoleProps(f, { standard: v });
    else {
      if (holeSpec(f).shape === 'd_flat' && (f.flat === undefined || f.flat === dFlat(f.d))) f.flat = dFlat(v); // (the flat follows the Ø while it is the default)
      f.d = v;
    }
    this.changedHole(f);
  }

  /** "M5" (a screw's hole), else "Ø6". */
  holeSizeText(f) {
    const sp = holeSpec(f);
    return sp.standard && sp.shape !== 'd_flat' ? sp.standard : `Ø${fmt(f.d)}`;
  }

  /** The sizes a hole's Size ▾ offers: the 2 below and the 2 above in the screw series (M2 … M20), or for a plain Ø
   *  the next steps (0.5 mm up to 6, then 1 mm) -> [{value, label, on}]. */
  holeSizes(f) {
    const sp = holeSpec(f), std = sp.standard && sp.shape !== 'd_flat';
    if (std) {
      const S = Object.keys(HOLE_SIZES), cur = sp.standard;
      let i = S.indexOf(cur);
      if (i < 0) i = S.reduce((a, k, j) => (Math.abs(parseFloat(k.slice(1)) - f.d) < Math.abs(parseFloat(S[a].slice(1)) - f.d) ? j : a), 0);
      return S.slice(Math.max(0, i - 2), i + 3).map((k) => ({ value: k, label: k, on: k === cur }));
    }
    const grid = [...Array.from({ length: 12 }, (_, j) => (j + 1) / 2), ...Array.from({ length: 94 }, (_, j) => j + 7)]; // 0.5 … 6, 7 … 100
    const d = f.d, below = grid.filter((v) => v < d - 1e-9).slice(-2), above = grid.filter((v) => v > d + 1e-9).slice(0, 2);
    return [...below, d, ...above].map((v) => ({ value: v, label: `Ø${fmt(v)}`, on: v === d }));
  }

  /** A chosen hole changed from the suggestions / its panel: one undo step, built, its rows shown again. */
  async changedHole(f) {
    this.commit();
    await this.rebuild();
    if (this.selected === f.id && !this.cmd) { this.renderProps(); this.suggestStep(f.id); }
  }

  /** A hole's properties as 4 short rows (the chosen step's panel and the Hole tool's): Shape (4 icons), Thread (on /
   *  off; on: cosmetic / real — the part's), Depth (through all / to a depth + its number), Size (M2 … M20, or a plain
   *  Ø: Custom Ø + its number — a thread or a head needs a screw size). */
  holePropsHtml(f) {
    const sp = holeSpec(f), dh = sp.shape === 'd_flat', mode = this.part.threads || 'hidden', through = f.through !== false;
    const needSize = sp.threaded || sp.shape === 'counterbore' || sp.shape === 'countersink';
    return `<div class="field m-hprop m-hshape"><label>${esc(t('Shape'))}</label><div class="seg">${HOLE_SHAPES.map(([k, l, icon]) => `<button type="button" data-shape="${k}" class="${k === sp.shape ? 'on' : ''}" title="${esc(t(l))}">${icon}</button>`).join('')}</div></div>
      ${dh ? '' : `<div class="field m-hprop m-hthread"><label>🔩 ${esc(t('Thread'))}</label><div class="m-hrow"><label class="check" title="${esc(t('Threaded: the hole is the tap drill (M5: Ø4.2); without: the screw’s clearance Ø (M5: Ø5.5)'))}"><input type="checkbox" data-k="threaded" ${sp.threaded ? 'checked' : ''}> ${esc(t('Threaded'))}</label>
        ${sp.threaded ? `<div class="seg mp-thr-hole"><button type="button" data-thr="cosmetic" class="${mode !== 'real' ? 'on' : ''}" title="${esc(t('Thin helix lines on the holes — view only, quick'))}">${esc(t('Cosmetic'))}</button><button type="button" data-thr="real" class="${mode === 'real' ? 'on' : ''}" title="${esc(t('The threads cut into the solid (ISO metric, 60°) — in STEP / STL / 3MF exports and the print split; slower'))}">${esc(t('Real (slower)'))}</button></div>` : ''}</div></div>`}
      <div class="field m-hprop m-hdepth"><label>${esc(t('Depth'))}</label><div class="m-hrow"><div class="seg"><button type="button" data-through="1" class="${through ? 'on' : ''}" title="${esc(t('Through the whole part'))}">${esc(t('Through all'))}</button><button type="button" data-through="0" class="${through ? '' : 'on'}" title="${esc(t('Only this deep'))}">${esc(t('To a depth'))}</button></div>
        ${through ? '' : `<input type="number" step="any" min="0" data-k="depth" value="${fmt(f.depth)}"><span class="unit">mm</span>`}</div></div>
      <div class="field m-hprop m-hsize"><label>${esc(t('Size'))}</label><div class="m-hrow">${dh ? '' : `<select data-k="standard" title="${esc(t('The screw’s size — the hole’s sizes are filled from the ISO tables'))}">${Object.keys(HOLE_SIZES).map((v) => `<option value="${v}" ${v === sp.standard ? 'selected' : ''}>${v}</option>`).join('')}${needSize ? '' : `<option value="" ${sp.standard ? '' : 'selected'}>${esc(t('Custom Ø'))}</option>`}</select>`}
        ${sp.standard && !dh ? '' : `<input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}" title="${esc(t('The hole’s diameter'))}"><span class="unit">mm</span>`}</div></div>`;
  }

  /** The rows of holePropsHtml at work: `changed` after each switch (the tool: shown again and rebuilt; a chosen step:
   *  one undo step). typed: the Ø / depth fields too (a chosen step's — the tool binds its own, live). */
  bindHoleProps(box, f, changed, typed = false) {
    for (const b of box.querySelectorAll('[data-shape]')) b.addEventListener('click', () => { if (!b.classList.contains('on')) { this.applyHoleProps(f, { shape: b.dataset.shape }); changed(); } });
    box.querySelector('[data-k=threaded]')?.addEventListener('change', (e) => { this.applyHoleProps(f, { threaded: e.target.checked }); changed(); });
    for (const b of box.querySelectorAll('.mp-thr-hole [data-thr]')) b.addEventListener('click', () => { this.setThreads(b.dataset.thr).then(() => this.renderProps()); });
    for (const b of box.querySelectorAll('[data-through]')) b.addEventListener('click', () => { if (b.classList.contains('on')) return; f.through = b.dataset.through === '1'; if (!f.through && !(f.depth > 0)) f.depth = 10; changed(); });
    box.querySelector('[data-k=standard]')?.addEventListener('change', (e) => {
      if (e.target.value) this.applyHoleProps(f, { standard: e.target.value });
      else setHole(f, { ...holeSpec(f), threaded: false, standard: null }); // (Custom Ø: a plain hole, its Ø kept)
      changed();
    });
    if (!typed) return;
    for (const k of ['d', 'depth']) {
      const el = box.querySelector(`.m-hprop [data-k=${k}]`);
      el?.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      el?.addEventListener('change', () => {
        const v = parseFloat(String(el.value).replace(',', '.'));
        if (!(v > 0)) { el.value = fmt(f[k]); return; }
        if (k === 'd' && holeSpec(f).shape === 'd_flat' && (f.flat === undefined || f.flat === dFlat(f.d))) f.flat = dFlat(v);
        f[k] = v;
        changed();
      });
    }
  }

  /** A chosen hole changed from the suggestions / its panel: one undo step, built, its rows shown again. */
  async changedHole(f) {
    this.commit();
    await this.rebuild();
    if (this.selected === f.id && !this.cmd) { this.renderProps(); this.suggestStep(f.id); }
  }

  /** The right panel while a Hole step is chosen (no tool open): its shape, thread, depth and size — changed here at
   *  once (one undo step each); ✎ Edit the hole for the rest, ＋ Add position for more holes. */
  renderHoleStep(box, f) {
    const st = this.status(f.id);
    box.innerHTML = `<h2 data-no-i18n>${esc(f.name)}</h2>
      <p class="hint">${esc(t2('◎ Hole step · {n} hole(s) — changed here at once (Ctrl+Z takes a change back).', { n: f.points.length }))}</p>
      ${this.holePropsHtml(f)}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="row-actions wrap"><button class="btn small primary" data-a="editHole" title="${esc(t('All its settings — and ＋ Add position for more holes'))}">✎ ${esc(t('Edit the hole'))}</button>
        <button class="btn small" data-a="addHolePos" title="${esc(t('Then click on the face where another hole goes (click again for more); click this again to stop'))}">＋ ${esc(t('Add position'))}</button></div>`;
    this.bindHoleProps(box, f, () => this.changedHole(f), true);
    box.querySelector('[data-a=editHole]').addEventListener('click', () => this.edit(f.id));
    box.querySelector('[data-a=addHolePos]').addEventListener('click', () => { this.edit(f.id); if (this.cmd?.feature.id === f.id) this.armPlace(); });
  }

  /** 🏷 Rename a step in its row of the list (typed in place). */
  renameStep(id) {
    const f = this.part.features.find((g) => g.id === id);
    this.openTo(id);
    this.renderTree();
    const el = f && this.$(`.mt-tree .mt-item[data-id="${CSS.escape(id)}"] .mt-name`);
    if (el) renameInPlace(el, (n) => { f.name = n; this.history.commit(); this.render(); this.hooks.onChange?.(); });
  }

  /** A top step of the list and the sketches under it (they move together). */
  stepBlock(id) { return [...(this.treeShapeNow?.kids.get(id) || []).filter((k) => !k.link).map((k) => k.id), id]; }

  /** The first step of a block in the list (its sketch, before it). */
  blockFirst(id) { const ids = new Set(this.stepBlock(id)); return this.part.features.find((x) => ids.has(x.id))?.id || id; }

  /** A click on the part: its step is chosen (its sizes show) and everything for that face is suggested (bottom left),
   *  in sections: on this face, its edges, the part, the step. */
  clickFace(e) {
    this.closeCtx();
    const line = !(e.ctrlKey || e.metaKey) && this.view.pickOutline(e.clientX, e.clientY);
    if (line) { this.picks = []; this.view.setEdgeHighlight(); this.selectStep(line); if (!this.suggestStep(line)) this.dropSuggest(); return; } // a sketch's lines: the sketch chosen (in the tree too; not used yet: ⬆ Extrude it; an open line: ⊿ Rib)
    const sp = this.view.measurePoint(e.clientX, e.clientY), more = e.ctrlKey || e.metaKey;
    // an edge under the mouse (lit while hovered): ◜ / ◸ it — also on its middle (a snap point there too)
    const ei = (!sp?.snap || sp.snap === 'midpoint') && hoverKinds().edges ? this.view.pickEdge(e.clientX, e.clientY, 7) : -1, eref = ei >= 0 ? this.edgeRef(ei) : null;
    const h = sp?.snap ? null : this.view.pick(e.clientX, e.clientY), fs = h?.face && this.stepFaces(h.face);
    const pick = eref && (more || !sp?.snap) ? { kind: 'edge', ref: eref, point: (sp?.point || h?.point)?.clone() || null }
      : sp?.snap ? { kind: 'point', point: sp.point.clone(), snap: sp.snap } : fs ? { kind: 'face', step: fs.step, face: h.face, point: h.point.clone() } : null;
    if (more && pick && this.picks?.length) { this.addPick(pick); return; } // Ctrl+click: one more in the selection
    this.picks = pick ? [pick] : [];
    if (!this.cmd) this.view.setEdgeHighlight();
    if (sp?.snap) { this.pickSnap(sp, eref ? ei : -1, { clientX: e.clientX, clientY: e.clientY }); return; } // a corner, an edge's middle, a centre
    if (pick?.kind === 'edge') { this.pickEdge(ei, eref); return; }
    if (!this.measuring) this.view.setMeasure([]);
    if (!fs) { this.selectStep(null); this.dropSuggest(); return; }
    this.faceTable(h, fs, { clientX: e.clientX, clientY: e.clientY });
  }

  /** A face chosen (h: {face, point} — clicked, or chosen from a snap point; fs: its step): its step chosen and the
   *  suggestions for it — this face, its edges, the part, the step. at: where the click was (the tools that start there). */
  faceTable(h, fs, at) {
    this.selectStep(fs.step.id);
    const flat = h.face.type === 'plane';
    // [key, icon, label, do it] by section: this face, its edges, the whole part, the step it belongs to
    const sections = [
      [t('On this face'), [
        flat && ['sketch', '✏', t('Sketch on this face'), () => this.enterSketch({ frame: h.face.frame, ...(h.face.ref ? { face: h.face.ref } : {}) })],
        flat && this.result?.body && ['faceup', '⬆', t('Extrude this face'), () => this.extrudeFace(h.face)],
        flat && ['hole', '◎', t('Hole here'), () => { this.startHole(); if (this.cmd) this.clickHole(at); }],
        flat && ['decal', 'Aa', t('Text / picture here'), () => { this.startDecal(); if (this.cmd) this.clickDecal(at); }],
        flat && ['shell', '▢', t('Hollow out, open here'), () => { this.startShell(); if (this.cmd) this.clickShell(at); }]]],
      [t('Its edges'), [
        ['fillet', '◜', t('Round its edges'), () => { this.startRound('fillet'); if (this.cmd) this.clickCommand(at); }],
        ['chamfer', '◸', t('Bevel its edges'), () => { this.startRound('chamfer'); if (this.cmd) this.clickCommand(at); }]]],
      [t('The part'), [
        flat && ['mirror', '⇋', t('Mirror across this face'), () => { this.startMirror(); if (this.cmd) this.clickMirror(at); }],
        flat && ['split', '✂', t('Split here'), () => this.startSplit(this.splitPlane(h.face))],
        this.threadHoles().length && (this.part.threads && this.part.threads !== 'hidden'
          ? ['threads', '🔩', t('Hide all threads'), () => this.setThreads('hidden')]
          : ['threads', '🔩', t('Show all threads'), () => this.askThreads()]),
        ['measure', '📏', t('Measure it'), () => { if (!this.measuring) this.toggleMeasure(); if (this.measuring) this.clickMeasure(at); }],
        ['paint', '🎨', t('Paint this face'), () => { if (!this.painting) this.togglePaint(); if (this.painting) { this.clickPaint(at); this.renderProps(); } }]]],
      [`${t('Step')} · ${fs.step.name}`, [
        fs.step.type !== 'hole' && ['edit', '✎', t('Edit the step'), () => this.edit(fs.step.id)], // (a hole: ✎ Edit the hole, above)
        REPEATABLE.has(fs.step.type) && fs.step.type !== 'pattern' && !fs.step.suppressed && ['pattern', '⁂', t('Pattern it'), () => this.startPattern(fs.step.id)],
        ['rename', '🏷', t('Rename'), () => this.renameStep(fs.step.id)],
        ['off', fs.step.suppressed ? '●' : '◌', t(fs.step.suppressed ? 'Turn it on' : 'Turn it off'), () => this.toggleOff(fs.step.id)],
        ['del', '✕', t('Delete the step'), () => this.remove(fs.step.id), 'danger']]],
    ].map(([title, items]) => [title, items.filter(Boolean)]).filter(([, items]) => items.length);
    const face = t(this.faceLabel(h.face.name).replace(/ of .*$/, '').replace(/^the /, ''));
    // the most relevant first (the table shows the top ones, the rest under ⋯ Show all): a flat face — sketch on it,
    // extrude it, a hole, round / bevel, edit; a round one — its edges, threads, edit
    // a hole's / a boss' face: ⁂ repeat it among the top rows
    const rep = fs.step.type === 'hole' || fs.step.op === 'cut';
    const RANK = { sketch: 0, faceup: 0.5, hole: 1, fillet: 2, chamfer: 3, edit: 4, pattern: rep ? 2.5 : 8.5, measure: 5.5, decal: 6.5, shell: 6, del: 7, mirror: 8, split: 9, rename: 9.5, paint: 9.8, off: 10, threads: flat ? 11 : 2.5 };
    const sg = showSuggest(this.els.viewport, `${fs.step.name} · ${face}`, [...(fs.step.type === 'hole' ? this.holeItems(fs.step) : []), // (a Hole step's: its types, sizes, thread first)
      ...sections.flatMap(([title, items]) => [{ section: title },
        ...items.map(([key, icon, label, run, cls, title]) => ({ icon, label, title, rank: RANK[key], danger: cls === 'danger', run: () => { this.dropSuggest(); run(); } }))])], '',
      `${t('in the 3D model')}: ${t('step')} ${fs.step.id} “${fs.step.name}”, ${t('face')} ${h.face.name}${h.face.type === 'plane' ? ` (${t('flat')})` : h.face.type === 'cylinder' ? ` (${t('round')}, Ø${fmt(2 * (h.face.radius || 0))})` : ''}`);
    if (sg) sg.dataset.from = 'face';
  }

  /** A sketch of one open line chosen: what it is for suggested — ⊿ Rib from it first. Others: nothing. */
  suggestSketch(id) {
    const f = this.part.features.find((g) => g.id === id);
    if (this.mode !== 'part' || this.cmd || !isOpenLine(f)) return null;
    const RANK = { rib: 0, edit: 1, del: 2 };
    const items = [
      this.result?.body && ['rib', '⊿', t('Rib from this line'), () => this.startRib(f.id)],
      ['edit', '✎', t('Edit the sketch'), () => this.edit(f.id)],
      ['del', '✕', t('Delete the step'), () => this.remove(f.id), 'danger']].filter(Boolean);
    const sg = showSuggest(this.els.viewport, `${f.name} · ${t('an open line')}`, items.map(([key, icon, label, run, cls]) => ({ icon, label, rank: RANK[key], danger: cls === 'danger', run: () => { this.dropSuggest(); run(); } })),
      '', `${t('in the 3D model')}: ${t('step')} ${f.id} “${f.name}” (${t('an open line')})`);
    if (sg) sg.dataset.from = 'face';
    return sg;
  }

  closeCtx() { this.ctxOff?.(); this.ctxOff = null; this.ctx?.remove(); this.ctx = null; }

  /** Ctrl+click: a face (its step) or a snap point more in the selection — or, chosen already, taken out of it. */
  addPick(pick) {
    const same = (a, b) => a.kind === b.kind && (a.kind === 'face' ? a.step.id === b.step.id && a.face.id === b.face.id : a.kind === 'edge' ? this.sameRef(a.ref, b.ref) : a.point.distanceTo(b.point) < 1e-6);
    const i = this.picks.findIndex((q) => same(q, pick));
    if (i >= 0) this.picks.splice(i, 1); else this.picks.push(pick);
    this.showPicks();
  }

  /** Several things chosen (Ctrl+click): all marked — their steps' faces, the points — and what fits them suggested:
   *  the distance between two (the gap between two parallel flat faces), turning their steps off, deleting them. */
  showPicks() {
    const ps = (this.picks || []).filter((q) => q.kind === 'point' || q.kind === 'edge' || this.part.features.includes(q.step));
    this.picks = ps;
    if (!ps.length) { this.selectStep(null); this.view.setEdgeHighlight(); this.dropSuggest(); this.view.setMeasure([]); return; }
    const steps = [...new Map(ps.filter((q) => q.kind === 'face').map((q) => [q.step.id, q.step])).values()];
    this.selectStep(null);
    this.view.setSelectedFaces(steps.flatMap((s) => this.stepFaceIds(s.id)));
    const pts = ps.filter((q) => q.kind === 'point').map((q) => q.point), edges = ps.filter((q) => q.kind === 'edge').map((q) => q.ref);
    this.view.setMeasure(pts);
    this.view.setEdgeHighlight(-1, this.refEdges(edges));
    const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2], xyz = (p) => [p.x, p.y, p.z].map((v) => fmt(+v.toFixed(3))).join(', ');
    const items = [];
    if (edges.length) items.push({ section: `${t('Edges')} (${edges.length})` }, ...this.edgeItems(edges)); // (◜ / ◸ first)
    if (ps.length === 2 && !edges.length) {
      const [a, b] = ps, d = a.point.distanceTo(b.point), fa = a.kind === 'face' && a.face.type === 'plane' && a.face.frame, fb = b.kind === 'face' && b.face.type === 'plane' && b.face.frame;
      const gap = fa && fb && Math.abs(Math.abs(dot(fa.n, fb.n)) - 1) < 1e-6 ? Math.abs(dot(fb.o.map((v, k) => v - fa.o[k]), fa.n)) : null;
      const show = (text) => { this.view.setMeasure([a.point, b.point], text); this.hooks.toast(text, 'info', 3000); };
      items.push({ section: t('Between them') },
        ...(gap !== null ? [{ icon: '↕', label: `${t('Gap between the faces')} ${fmt(gap)} mm`, title: t('The two flat faces are parallel'), run: () => show(`${fmt(gap)} mm`) }] : []),
        { icon: '📏', label: `${t('Distance')} ${fmt(d)} mm`, title: `Δx ${fmt(Math.abs(b.point.x - a.point.x))} Δy ${fmt(Math.abs(b.point.y - a.point.y))} Δz ${fmt(Math.abs(b.point.z - a.point.z))}`, run: () => show(`${fmt(d)} mm`) });
    }
    if (steps.length) {
      const allOff = steps.every((s) => s.suppressed), one = steps.length === 1;
      items.push({ section: one ? `${t('Step')} · ${steps[0].name}` : `${steps.length} ${t('steps')}: ${steps.map((s) => s.name).join(', ')}` },
        { icon: allOff ? '●' : '◌', label: t(allOff ? (one ? 'Turn it on' : 'Turn them on') : (one ? 'Turn it off' : 'Turn them off')), run: () => {
          for (const s of steps) { if (allOff) delete s.suppressed; else s.suppressed = true; }
          this.picks = [];
          this.dropSuggest();
          this.commit();
        } },
        { icon: '✕', label: t(one ? 'Delete the step' : 'Delete them'), danger: true, run: () => this.removeSteps(steps.map((s) => s.id)) });
    }
    const refs = `${t('in the 3D model')}: ${ps.map((q) => (q.kind === 'face' ? `${t('step')} ${q.step.id} “${q.step.name}” ${t('face')} ${q.face.name}` : q.kind === 'edge' ? `${t('the edge between faces')} ${q.ref.a} ${t('and')} ${q.ref.b}` : `${t('the point')} (${xyz(q.point)})`)).join('; ')}`;
    const sg = showSuggest(this.els.viewport, `${ps.length} ${t('selected')}`, items, t('Ctrl+click: add more, or take one away'), refs);
    if (sg) sg.dataset.from = 'face';
  }

  /** Delete several steps at once (and the steps that need them, after asking). */
  async removeSteps(ids) {
    if (this.mode !== 'part' || this.cmd) return;
    const gone = new Set(ids.flatMap((id) => [...this.dependents(id, false).gone]));
    const more = [...gone].filter((x) => !ids.includes(x)).map((x) => this.part.features.find((f) => f.id === x)?.name);
    if (more.length && !(await confirmIn(`${t('These steps need them and are deleted too')}: ${more.join(', ')}.`, { ok: 'Delete them', danger: true }))) return;
    this.part.features = this.part.features.filter((f) => !gone.has(f.id));
    this.selected = null;
    this.picks = [];
    this.dropSuggest();
    this.commit();
  }

  // ------------------------------------------------------------------ 🏷 which sizes are shown
  /** 🏷 Sizes: All / 🔒 Locked / None — the size labels on the sketch and on the part (remembered). */
  sizesHtml() {
    const b = (k, label, title) => `<button data-sz="${k}" class="${this.sizeMode === k ? 'on' : ''}" title="${title}">${label}</button>`;
    return `<div class="m-sizes"><span title="Which sizes are shown on the sketch and on the part">🏷 Sizes</span><div class="seg">${b('all', 'All', 'Every size (and the ones hidden one by one)')}${b('locked', '🔒 Locked', 'Only the sizes you locked (and a step\'s own, like an extrude\'s height)')}${b('none', 'None', 'No sizes — a clean view')}</div></div>`;
  }

  bindSizes(box) {
    for (const b of box.querySelectorAll('[data-sz]')) b.addEventListener('click', () => this.setSizeMode(b.dataset.sz, b.dataset.sz === 'all'));
    box.querySelector('[data-a=bigAll]')?.addEventListener('click', () => {
      const id = this.sk?.f?.id;
      if (this.bigAll.has(id)) this.bigAll.delete(id); else this.bigAll.add(id);
      this.setSizeMode(this.sizeMode);
    });
  }

  /** unhide: the sizes hidden one by one (☐ Show in a size's editor) come back — All clicked, 📏 switched on (an undo step). */
  setSizeMode(m, unhide = false) {
    if (unhide && this.part.hidden_dims?.length) { delete this.part.hidden_dims; this.history.commit(); this.hooks.onChange?.(); }
    this.sizeMode = SIZE_MODES.includes(m) ? m : 'all';
    try { localStorage.setItem(SIZES_KEY, this.sizeMode); } catch { /* ignore */ }
    for (const b of document.querySelectorAll('.m-sizes [data-sz]')) b.classList.toggle('on', b.dataset.sz === this.sizeMode);
    if (this.els.viewport.querySelector(':scope > .snap-filters')) showSnapFilters(this.els.viewport); // (📏 in the bottom row: on / off with it)
    if (this.mode === 'sketch' && this.sk) { this.sk.draw(); if (!this.cmd) this.renderProps(); }
    else if (this.mode === 'part' && !this.cmd) this.showStepDims(this.part.features.find((f) => f.id === this.dimStep) || null);
  }

  /** A sketch so big its shapes' own sizes are not labelled (unless asked). */
  isBigSketch(sk) { return (sk?.entities?.length || 0) > BIG_SKETCH && !this.bigAll.has(sk.id); }

  /** Is a size label shown: a locked one unless None; a free one under All, not on a big sketch. */
  sizeShown(locked, sk) {
    if (this.sizeMode === 'none') return false;
    return locked || (this.sizeMode === 'all' && !this.isBigSketch(sk));
  }

  // ------------------------------------------------------------------ the chosen step's sizes, on the part
  /** Show (or with null hide) the sizes of a step as labels on the part — click one to change it (number + slider). */
  showStepDims(step, { keepEdit = false } = {}) {
    this.dimStep = step ? step.id : null;
    if (!keepEdit) this.closeDimEdit();
    if (!step || this.mode !== 'part' || this.sizeMode === 'none') { this.view.setTags([]); return; }
    const tags = [], lines = [], hidden = new Set(this.part.hidden_dims || []);
    this.dimTagEls = []; // ([label, its size] — the editor opens again on it after an icon's change)
    const add = (p, text, edit, title = '') => {
      edit.key = edit.key || (edit.sketch ? `${edit.sketch.id}:${JSON.stringify([edit.sketch.spec.t, edit.sketch.spec.e, edit.sketch.spec.a, edit.sketch.spec.b])}` : `${edit.stepId}:${edit.field}`);
      if (hidden.has(edit.key)) return; // (☐ Show in its editor: Sizes All brings it back)
      const el = document.createElement('div');
      el.className = 'm-dimtag';
      el.textContent = text;
      el.title = title || 'Click to change it';
      for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
      el.addEventListener('click', (ev) => { ev.stopPropagation(); this.openDimEdit(el, edit); });
      tags.push({ p, el });
      this.dimTagEls.push([el, edit]);
    };
    const P3 = (fr, u, v) => { const y = cross(fr.n, fr.x); return [0, 1, 2].map((i) => fr.o[i] + u * fr.x[i] + v * y[i]); };
    const f = step, num = (k, label, o = {}) => ({ get: () => f[k], set: (v) => { f[k] = v; }, label, field: k, stepId: f.id, ...o });
    const skOf = (id) => this.part.features.find((g) => g.id === id);
    const frameOf = (sk) => (sk?.plane?.datum ? datumFrame(sk.plane) : this.frames?.[sk?.id] || sk?.plane?.frame);
    if (f.type === 'extrude' || f.type === 'revolve') {
      const sk = skOf(f.sketch), fr = frameOf(sk);
      if (sk && fr) {
        this.sketchTags(sk, fr, add, P3);
        if (f.type === 'extrude') { // its height — or how far it goes (up to a face / next, through all): the ⇅ ⇕ icons at it
          const s = (f.op === 'cut' ? -1 : 1) * (f.flip ? -1 : 1), c = this.sketchCorner(sk), dist = !f.upto && !f.upto_next && !f.through;
          const a = P3(fr, c[0], c[1]), dir = fr.n.map((v) => v * s), L = dist ? f.d * (f.symmetric ? 0.5 : 1) : this.wentLength(f, a, dir);
          const b = a.map((v, i) => v + dir[i] * L);
          lines.push([a, b]);
          const mode = f.upto_next ? 'up to next' : f.upto ? 'up to the face' : f.through ? 'through all' : null;
          add(b.map((v, i) => v + dir[i] * this.view.size * 0.02), mode ? `↕ ${t(mode)}` : `↕ ${fmt(f.d)}`,
            num('d', 'Height', { min: 0.1, icons: true, set: (v) => { if (dist || Math.abs(v - f.d) > 1e-9) { setExtrude(f, 'distance'); f.through = false; } f.d = v; } }), `${f.name}: the height`);
        }
        if (f.type === 'revolve') add(P3(fr, 0, 0), `${fmt(f.angle)}°`, num('angle', 'Angle', { min: 1, max: 360, unit: '°', icons: true }));
      }
    } else if (f.type === 'sketch') {
      const fr = frameOf(f);
      if (fr) this.sketchTags(f, fr, add, P3);
    } else if (f.type === 'hole' && f.plane?.frame) {
      const fr = this.holeFrame(f);
      f.points.forEach((p, i) => {
        const at = P3(fr, p[0], p[1]);
        if (i === 0) add(at, `Ø${fmt(f.d)}`, num('d', 'Diameter', { min: 0.2 }), `${f.name}: the diameter`);
        for (const [axis, k] of [['x', 0], ['y', 1]]) {
          const r = f.from?.[i]?.[axis], c = r && (r.mid ? this.edgeCoord(f, r.mid[0], k) : this.refCoord(f, r, k)); // (in the middle: from its left / lower edge)
          if (r && c !== null && c !== undefined && c !== false) {
            const q = k === 0 ? [c, p[1]] : [p[0], c], dist = r.mid ? Math.abs(p[k] - c) : Math.abs(r.d);
            lines.push([P3(fr, ...q), at]);
            const on = holeLocked(f, i, axis);
            add(P3(fr, (q[0] + p[0]) / 2, (q[1] + p[1]) / 2), `${on ? '🔒 ' : ''}${k ? '↕' : '↔'} ${fmt(dist)}`, {
              label: 'Distance', min: 0, get: () => dist, key: `${f.id}:at${i}${axis}`,
              set: (v) => this.setHoleDist(f, i, axis, v, r.mid ? r.mid[0] : null),
              lock: { on, set: (x) => setHoleLock(f, i, axis, x) }, // (🔒 in its editor: dragging the hole keeps it)
            }, `${f.name}: ${on ? 'locked' : 'click to type it (it is then locked)'}`);
          }
        }
      });
      if (f.through === false) add(P3(fr, f.points[0][0], f.points[0][1]).map((v, i) => v - fr.n[i] * f.depth), `↓ ${fmt(f.depth)}`, num('depth', 'Depth', { min: 0.1 }));
    } else if ((f.type === 'fillet' || f.type === 'chamfer') && f.edges?.length) {
      const k = f.type === 'fillet' ? 'r' : 'd';
      add(f.edges[0].fp, `${f.type === 'fillet' ? 'R' : '◸'} ${fmt(f[k])}`, num(k, f.type === 'fillet' ? 'Radius' : 'Size', { min: 0.1 }));
    } else if (f.type === 'shell' && f.faces?.length) {
      add(f.faces[0].fp, `wall ${fmt(f.t)}`, num('t', 'Wall', { min: 0.2 }));
    } else if (f.type === 'decal' && f.plane?.frame) {
      const fr = f.plane.frame;
      add(P3(fr, f.at[0], f.at[1]), `${fmt(f.h)} high`, num('h', 'Height', { min: 0.5 }));
    } else if (f.type === 'pattern') {
      const b = this.result?.body?.bbox, c = b ? [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[5]] : [0, 0, 0];
      add(c, `${f.count}×`, num('count', 'How many', { min: 2, max: Math.max(20, f.count * 2), soft: true, step: 1, int: true }));
      if (f.kind !== 'circular') add(c.map((v, i) => v + (i === 2 ? this.view.size * 0.05 : 0)), `${fmt(f.spacing)} apart`, num('spacing', 'Apart', { min: 0.1 }));
    }
    this.view.setTags(tags, lines);
  }

  /** How far extrude f went from point a (on its sketch) along dir — up to a face / next, through all: from where the
   *  kernel says it went (along an axis); else its height. */
  wentLength(f, a, dir) {
    const w = this.status(f.id)?.went, k = typeof w?.along === 'string' ? 'xyz'.indexOf(w.along[1]) : -1;
    if (k >= 0 && w.range && Math.abs(dir[k]) > 0.999) {
      const L = ((w.along[0] === '+' ? w.range[1] : w.range[0]) - a[k]) * Math.sign(dir[k]);
      if (L > 1e-6) return L;
    }
    return f.d || 10;
  }

  /** The size editor's icons (an extrude's height, a revolve's angle): one click changes how the step goes — an undo
   *  step, the part follows; the editor opens again on the size's new label. Up to a face… opens the Extrude panel to
   *  click the face. Up to next is offered once the kernel finds a face that way (asked in the background). */
  dimIconRow(box, edit, before, settle) {
    const f = this.part.features.find((g) => g.id === edit.stepId);
    if (!f || (f.type !== 'extrude' && f.type !== 'revolve')) return;
    const i = this.part.features.indexOf(f), solidBefore = this.part.features.slice(0, i).some((g) => !g.suppressed && !['sketch', 'point'].includes(g.type));
    const row = document.createElement('div');
    row.className = `m-dimicons g-${f.op === 'cut' ? 'cut' : 'add'}`;
    const draw = (canNext) => {
      row.innerHTML = dimIcons(f, { canUpto: solidBefore, canNext }).map((x) => `<button type="button" data-ic="${x.key}" class="${x.on ? 'on' : ''}" title="${esc(t(x.title))}">${x.html}</button>`).join('');
      for (const b of row.querySelectorAll('[data-ic]')) b.addEventListener('click', () => this.dimIcon(f.id, b.dataset.ic, b.classList.contains('on'), edit, before, settle));
    };
    draw(false);
    box.querySelector('.m-dimedit-row').after(row);
    if (f.type === 'extrude' && solidBefore && !f.upto_next) this.canGoNext(f).then((ok) => { if (ok && this.dimEdit === box) draw(true); });
  }

  /** Would extrude f, up to next, find a face (the steps before it as they are)? Asked the kernel once per setting. */
  async canGoNext(f) {
    const fs = this.shown(), i = fs.findIndex((g) => g.id === f.id);
    if (i < 0) return false;
    const g = structuredClone(f);
    setExtrude(g, 'next');
    const features = [...fs.slice(0, i), g], key = JSON.stringify(features);
    this.nextCache = this.nextCache || new Map();
    if (!this.nextCache.has(key)) {
      this.nextCache.set(key, fetchRebuild({ features }, newRid('m'), 'Checking Up to next').then(({ res, r }) => !!(res.ok && r.features?.find((s) => s.id === f.id)?.ok)).catch(() => false));
    }
    return this.nextCache.get(key);
  }

  /** An icon of the size editor clicked: the step changed (on: the lit one — clicked again it goes back to a typed
   *  distance / is turned off), one undo step; the editor opens again on the size. */
  async dimIcon(id, key, on, edit, before, settle) {
    await settle(); // (a preview still building first)
    let f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    this.closeDimEdit();
    if (key === 'upto' && !on) { // the face is clicked in the Extrude panel (OK / Cancel there)
      this.part.features = before;
      f = this.part.features.find((g) => g.id === id);
      const g = structuredClone(f);
      setExtrude(g, 'upto');
      this.view.setTags([]);
      this.openExtrude(g, false);
      this.hint('Up to a face — click a flat face of the part. Enter = OK, Esc = Cancel.');
      return;
    }
    if (f.type === 'revolve') { if (key === 'op') f.op = f.op === 'cut' ? 'add' : 'cut'; else f.angle = key === 'full' ? 360 : 180; }
    else if (key === 'flip') setExtrude(f, 'flip', true, this.isFaceExtrude(f));
    else if (key === 'symmetric' || key === 'through') setExtrude(f, key, !on);
    else if (key === 'op') setExtrude(f, 'op');
    else setExtrude(f, on ? 'distance' : key);
    this.commit();
    await this.inflight;
    this.reshowDims();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))); // (the labels placed first: it opens by its label)
    const tag = (this.dimTagEls || []).find(([, e]) => e.stepId === id && e.field === edit.field);
    if (tag) this.openDimEdit(...tag);
  }

  /** The sketch's front-right corner (largest x, smallest y): where the height is shown, on a visible edge. */
  sketchCorner(sk) {
    const ps = Object.values(upgradeSketch(sk).points || {});
    return ps.length ? [Math.max(...ps.map((p) => p[0])), Math.min(...ps.map((p) => p[1]))] : [0, 0];
  }

  sketchCentre(sk) {
    const ps = Object.values(upgradeSketch(sk).points || {});
    if (!ps.length) return [0, 0];
    return [ps.reduce((s, p) => s + p[0], 0) / ps.length, ps.reduce((s, p) => s + p[1], 0) / ps.length];
  }

  /** A sketch's sizes as labels on its plane: its locked / measuring dimensions and its shapes' own sizes. */
  sketchTags(sk0, fr, add, P3) {
    const sk = upgradeSketch(sk0), P = (id) => (id === 'O' ? [0, 0] : sk.points[id]);
    const S = new Sketcher(this, structuredClone(sk), false);
    const shown = new Set();
    const label = (spec, v) => ({ len: fmt(v), dia: `Ø${fmt(v)}`, rad: `R${fmt(v)}`, dx: `↔ ${fmt(Math.abs(v))}`, dy: `↕ ${fmt(Math.abs(v))}`, dist: `⤢ ${fmt(Math.abs(v))}` }[spec.t]);
    const at = (spec) => {
      if (spec.t === 'len') { const e = sk.entities.find((x) => x.id === spec.e), a = P(e.a), b = P(e.b); return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; }
      if (spec.t === 'dia') { const e = sk.entities.find((x) => x.id === spec.e), c = P(e.c); return [c[0] + e.r * 0.7, c[1] + e.r * 0.7]; }
      if (spec.t === 'rad') { const e = sk.entities.find((x) => x.id === spec.e), ps = S.arcOf(e); return ps[Math.floor(ps.length / 2)]; }
      const a = S.endUV(spec.a), b = S.endUV(spec.b);
      return spec.t === 'dx' ? [(a[0] + b[0]) / 2, b[1]] : spec.t === 'dy' ? [b[0], (a[1] + b[1]) / 2] : [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    };
    const tag = (spec) => {
      const key = JSON.stringify([spec.t, spec.e, spec.a, spec.b]);
      if (shown.has(key)) return;
      shown.add(key);
      const d = S.findDim(spec);
      if (!this.sizeShown(!!d && !d.free, sk0)) return;
      const v = S.measure(spec);
      if ((spec.a === 'O' || spec.b === 'O') && Math.abs(v) < 1e-9) return; // "on the origin"
      const [u, w] = at(spec);
      add(P3(fr, u, w), `${d && !d.free ? '🔒 ' : ''}${label(spec, v)}`, { label: { len: 'Length', dia: 'Diameter', rad: 'Radius' }[spec.t] || 'Distance', min: spec.t === 'dx' || spec.t === 'dy' ? -1e6 : 0.1,
        get: () => Math.abs(v), sketch: { id: sk0.id, spec }, lock: { on: !!d && !d.free } }, `${sk0.name}: ${d && !d.free ? 'locked' : 'click to type it (it is then locked)'}`);
    };
    for (const d of sk.dims) if (d.t !== 'bw') tag({ t: d.t, e: d.e, a: d.a, b: d.b });
    if (!this.sizeShown(false, sk0)) return; // the shapes' own (free) sizes
    const groups = new Set();
    for (const e of sk.entities) {
      if (e.t === 'line') {
        if (S.isHidden({ t: 'len', e: e.id })) continue;
        if (e.g) {
          const kk = sk.constraints.find((c) => c.e === e.id && (c.t === 'h' || c.t === 'v'))?.t;
          if (groups.has(`${e.g}:${kk}`)) continue;
          groups.add(`${e.g}:${kk}`);
        }
        tag({ t: 'len', e: e.id });
      } else if (e.t === 'circle' && !S.isHidden({ t: 'dia', e: e.id })) tag({ t: 'dia', e: e.id });
      else if (e.t === 'arc' && !S.isHidden({ t: 'rad', e: e.id })) tag({ t: 'rad', e: e.id });
    }
  }

  /** The editor of one size: a number and a slider; the part follows while sliding; Enter / OK keeps it, Esc goes back.
   *  Its max is hard (edit.max, or the kernel's: past it is refused, saying why) or soft (none given, edit.soft, the
   *  kernel's "_soft": a bigger number typed is taken and the slider grows round it). */
  openDimEdit(el, edit) {
    this.closeDimEdit();
    const before = structuredClone(this.part.features), toolBefore = edit.tool && this.cmd ? structuredClone(this.cmd.feature) : null;
    const v0 = edit.get(), step = edit.step || (Math.abs(v0) >= 20 ? 0.5 : 0.1), ex0 = this.dimExpr(edit);
    let lo = edit.min ?? 0.1, hi = edit.max ?? Math.max(10, Math.abs(v0) * 3), soft = !!edit.soft || edit.max === undefined, shownHi = hi;
    const box = document.createElement('div');
    box.className = 'm-dimedit';
    box.innerHTML = `<div class="m-dimedit-t">${esc(t(edit.label || 'Size'))}</div>
      <div class="m-dimedit-row"><input type="text" class="px-in" autocomplete="off" spellcheck="false" step="${step}" value="${esc(ex0 ?? fmt(v0))}" title="${esc(t('A number — or an expression of the project’s parameters: L, L/2 + 5, =D. “L = 100” makes the parameter L.'))}"><span class="unit">${edit.unit || (edit.int ? '' : 'mm')}</span></div>
      <input type="range" min="${edit.int ? lo : 0}" max="${Math.max(hi, v0)}" step="${edit.int ? 1 : step}" value="${v0}">
      ${edit.tool ? '' : `<div class="m-dimedit-checks">${edit.lock ? `<label title="${esc(t('Locked: the size holds at its number. Unticked: it only measures (a reference) — the other sizes drive it'))}"><input type="checkbox" data-c="lock" ${edit.lock.on ? 'checked' : ''}> 🔒 ${esc(t('Locked'))}</label>` : ''}
        <label title="${esc(t('Show this size in the view — unticked it is hidden (🏷 Sizes: All brings it back)'))}"><input type="checkbox" data-c="show" checked> ${esc(t('Show'))}</label></div>`}
      <div class="m-dimedit-why mp-warn" hidden></div>
      <div class="m-dimedit-acts"><button class="btn small primary" data-a="ok" data-rclick-ok>OK</button><button class="btn small" data-a="cancel">Cancel</button>
        <button class="btn small" data-a="restore" disabled title="${esc(t('Back to the size it had when this was opened'))}" data-no-i18n>↺ ${fmt(v0)}</button></div>`;
    const vr = this.els.viewport.getBoundingClientRect(), r = el.getBoundingClientRect();
    Object.assign(box.style, { left: `${Math.min(r.left - vr.left, vr.width - 220)}px`, top: `${Math.min(r.bottom - vr.top + 6, vr.height - (edit.icons ? 172 : 140) - (edit.tool ? 0 : 22))}px` });
    for (const t2 of ['pointerdown', 'pointerup']) box.addEventListener(t2, (ev) => ev.stopPropagation());
    this.els.viewport.appendChild(box);
    floatBox(box, this.els.viewport, { kind: 'dimedit', handle: '.m-dimedit-t', remember: 'size', min: [170, 100] }); // (opens by the size clicked)
    this.dimEdit = box;
    const num = box.querySelector('.m-dimedit-row input'), slider = box.querySelector('input[type=range]');
    if (edit.field && edit.stepId) { // the real range of this number of the step
      this.limitsFor(this.part.features, edit.stepId).then((lim) => {
        const r = lim[edit.field];
        if (!r || this.dimEdit !== box) return;
        const approx = (lim._approx || []).includes(edit.field); // (a rounding's max found to 1 %: a bit more may fit)
        soft = (lim._soft || []).includes(edit.field);
        [lo, hi] = r;
        const cur = parseFloat(slider.value);
        Object.assign(slider, { min: String(lo), max: String(soft && cur > hi ? growTo(cur) : hi) });
        Object.assign(num, { min: String(lo), max: String(approx ? +(hi * 1.02).toFixed(2) : hi) });
        const tag = document.createElement('div');
        tag.className = 'mp-range';
        tag.textContent = `${fmt(lo)} – ${approx && !soft ? '≈' : ''}${fmt(hi)}${soft ? '+' : ''}${edit.unit || (edit.int ? '' : ' mm')}`;
        tag.title = soft ? t('A suggestion — type a bigger number and the slider grows') : t('The most that can be built here');
        shownHi = hi;
        if (approx) hi = +(hi * 1.02).toFixed(2);
        slider.after(tag);
      });
    }
    let pending = null, busy = false;
    const preview = async (v) => {
      pending = v;
      if (busy) return;
      busy = true;
      while (pending !== null) {
        const x = pending;
        pending = null;
        await this.applyDim(edit, x, false);
      }
      busy = false;
    };
    const valid = (v) => Number.isFinite(v) && (soft || v <= hi) && (edit.int ? Number.isInteger(v) && v >= lo : lo <= v || lo < 0);
    const whyBox = box.querySelector('.m-dimedit-why');
    const why = (v) => { // past a hard max: why it stops there (the step's own reason, else in general)
      if (!(Number.isFinite(v) && !soft && v > hi)) return '';
      const st = this.part.features.find((g) => g.id === edit.stepId), k = LIMIT_WHY[`${st?.type}.${edit.field}`];
      return k ? t2(k, { v: fmt(shownHi) }) : t2('{v} is the most that works here (with what is around it).', { v: fmt(shownHi) });
    };
    // 𝑥 a number or an expression of the parameters (L / 2; "L = 100" makes L when it is kept)
    const read = (keep = false) => {
      try { const r = keep ? takeField(num.value) : readField(num.value, params.list); num.classList.remove('px-bad'); num.title = ''; return r; } catch (e) {
        num.classList.add('px-bad');
        num.title = `⚠ ${e.message}`;
        return { value: NaN, error: e.message };
      }
    };
    const back = box.querySelector('[data-a=restore]'), moved = () => { back.disabled = Math.abs(read().value - v0) < 1e-9; };
    const lockBox = box.querySelector('[data-c=lock]'), showBox = box.querySelector('[data-c=show]');
    const typed = () => { if (lockBox) lockBox.checked = true; }; // (a size typed is locked)
    lockBox?.addEventListener('change', () => { if (!lockBox.checked && !back.disabled) back.click(); }); // (freed: back to what it measures)
    num.addEventListener('input', () => {
      const v = read().value, w = why(v);
      moved();
      typed();
      whyBox.hidden = !w;
      whyBox.textContent = w;
      if (!valid(v)) return;
      if (v > +slider.max) slider.max = String(growTo(v)); // (a soft range: it grows round what was typed)
      slider.value = v;
      preview(v);
    });
    slider.addEventListener('input', () => { const v = Math.max(parseFloat(slider.value), edit.min > 0 ? edit.min : 0); num.value = fmt(v); moved(); typed(); preview(v); });
    back.addEventListener('click', () => { num.value = fmt(v0); slider.value = v0; moved(); preview(v0); num.focus(); num.select(); }); // (the editor stays open)
    // OK: the number (locked) — or ☐ 🔒 Locked: the size freed, it only measures; ☐ Show: hidden. One undo step.
    const ok = async () => {
      const free = lockBox && !lockBox.checked, hide = showBox && !showBox.checked;
      const r0 = free ? { value: v0 } : read();
      if (r0.error) { this.hooks.toast(r0.error, 'warning', 6000); return; }
      if (!free && !valid(r0.value)) { this.hooks.toast(why(r0.value) || 'That size does not fit here.', 'warning'); return; }
      const r = free ? r0 : read(true), v = r.value;
      while (busy) await new Promise((res) => setTimeout(res, 20));
      this.closeDimEdit();
      if (!free) {
        if (await this.applyDim(edit, v, !hide, r.expr) === false) { this.part.features = before; this.rebuild(); return; }
        if (!hide) return;
      } else {
        this.freeDim(edit);
        if (!hide && JSON.stringify(before) === JSON.stringify(this.part.features)) { this.reshowDims(); return; } // (it was free already)
      }
      if (hide) this.part.hidden_dims = [...new Set([...(this.part.hidden_dims || []), edit.key])];
      this.commit();
      await this.inflight;
      this.reshowDims();
      if (hide) this.hooks.toast(t('The size is hidden — 🏷 Sizes: All shows it again.'), 'info');
    };
    const cancel = async () => {
      while (busy) await new Promise((res) => setTimeout(res, 20));
      this.closeDimEdit();
      if (toolBefore) { if (this.cmd) { Object.assign(this.cmd.feature, toolBefore); this.renderProps(); await this.rebuild(); } return; } // (the open tool's step as it was)
      this.part.features = before; await this.rebuild(); this.reshowDims();
    };
    if (edit.icons) this.dimIconRow(box, edit, before, async () => { while (busy) await new Promise((res) => setTimeout(res, 20)); });
    num.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') ok(); if (e.key === 'Escape') cancel(); });
    box.querySelector('[data-a=ok]').addEventListener('click', ok);
    box.querySelector('[data-a=cancel]').addEventListener('click', cancel);
    setTimeout(() => { num.focus(); num.select(); }, 0);
  }

  closeDimEdit() { this.dimEdit?.remove(); this.dimEdit = null; }

  /** ☐ 🔒 Locked in a size's editor: the size freed — a hole's distance is no longer kept when it is dragged; a
   *  sketch's shape size loses its lock, a distance stays as a reference that only measures (as in the sketch). */
  freeDim(edit) {
    if (edit.lock?.set) { edit.lock.set(false); return; }
    const sk = edit.sketch && this.part.features.find((g) => g.id === edit.sketch.id);
    if (!sk) return;
    const S = new Sketcher(this, structuredClone(upgradeSketch(sk)), false), d = S.findDim(edit.sketch.spec);
    if (!d) return;
    if (['len', 'dia', 'rad'].includes(d.t)) S.f.dims = S.f.dims.filter((x) => x !== d);
    else Object.assign(d, { free: true, v: +S.measure(d).toFixed(6) });
    sk.dims = S.f.dims;
  }

  /** 𝑥 The expression a size in the view is set by (a step's number, a sketch's locked size), or null. */
  dimExpr(edit) {
    if (edit.sketch) {
      const sk = this.part.features.find((g) => g.id === edit.sketch.id);
      const d = sk && new Sketcher(this, structuredClone(upgradeSketch(sk)), false).findDim(edit.sketch.spec);
      return d?.expr?.v ? exprText(d.expr.v) : null;
    }
    const e = edit.stepId && this.part.features.find((g) => g.id === edit.stepId)?.expr?.[edit.field];
    return e ? exprText(e) : null;
  }

  /** Put a size in: a step's own number, or a sketch's size (solved, with its locks). final = an undo step. expr: the
   *  parameters' expression it comes from (null: a plain number — an expression it had goes; undefined: kept). */
  async applyDim(edit, v, final, expr) {
    if (edit.tool) { // a size of the open tool's step (a hole's distance on the part): its preview; OK of the tool keeps it
      if (!this.cmd) return false;
      edit.set(v);
      if (final) this.renderProps();
      await this.rebuild();
      return true;
    }
    if (edit.sketch) {
      const sk = this.part.features.find((g) => g.id === edit.sketch.id);
      if (!sk) return false;
      const S = new Sketcher(this, structuredClone(upgradeSketch(sk)), false), spec = edit.sketch.spec;
      const f = S.f, cur = S.measure(spec);
      let value = v;
      if ((spec.t === 'dx' || spec.t === 'dy') && cur < 0) value = -Math.abs(v);
      const d = S.findDim(spec);
      if (d) { d.v = value; delete d.free; } else f.dims.push({ id: S.newId('d'), ...spec, v: value });
      if (expr !== undefined) setExpr(S.findDim(spec), 'v', expr && value < 0 ? `-(${expr})` : expr);
      let hold = null;
      if (spec.t === 'len') { const e = S.ent(spec.e); if (e.a !== 'O') hold = { [e.a]: S.P(e.a) }; }
      else if (spec.t === 'dia' || spec.t === 'rad') { const e = S.ent(spec.e); if (e.c !== 'O') hold = { [e.c]: S.P(e.c) }; }
      else if (typeof spec.a === 'string' && spec.a !== 'O' && f.points[spec.a]) hold = { [spec.a]: S.P(spec.a) };
      const r = await S.solve(hold, S.keepFor(spec));
      if (!r.ok) {
        if (final) this.hooks.toast(r.error || 'That does not fit the sketch\'s other locked sizes — open the sketch and unlock one.', 'error', 6000);
        return false;
      }
      S.apply(r);
      Object.assign(sk, { points: f.points, entities: f.entities, dims: f.dims });
    } else {
      edit.set(edit.int ? Math.round(v) : v);
      if (expr !== undefined && edit.field) setExpr(this.part.features.find((g) => g.id === edit.stepId), edit.field, expr);
    }
    if (final) { this.commit(); await this.inflight; } else await this.rebuild();
    this.reshowDims(!final);
    return true;
  }

  reshowDims(keepEdit = false) {
    const s = this.part.features.find((g) => g.id === this.dimStep);
    if (s && !this.cmd && this.mode === 'part') this.showStepDims(s, { keepEdit }); else this.view.setTags([]);
  }

  toggleOff(id) {
    if (this.mode !== 'part' || this.cmd) return;
    const f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    if (f.suppressed) delete f.suppressed;
    else f.suppressed = true;
    this.commit();
  }

  /** A new step's name: "Extrude 3" — or, made from a sketch the user named, "Extrude – Slot". */
  nextName(type, sketchId = null) {
    const base = t(TYPE_NAME[type] || type); // named in the language on screen
    const sk = sketchId && this.part.features.find((f) => f.id === sketchId && f.type === 'sketch');
    if (sk?.name && !/^\S+ \d+$/.test(sk.name.trim())) return `${base} – ${sk.name.trim()}`; // (not a "Sketch 2" / "Skica 2")
    const n = Math.max(0, ...this.part.features.filter((f) => f.type === type).map((f) => parseInt(String(f.name).replace(/\D/g, ''), 10) || 0));
    return `${base} ${n + 1}`;
  }

  newId() {
    const n = Math.max(0, ...this.part.features.map((f) => parseInt(String(f.id).replace(/\D/g, ''), 10) || 0));
    return `F${n + 1}`;
  }

  edit(id) {
    if (this.mode !== 'part' || this.cmd) return;
    const f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    if (f.type === 'sketch') this.enterSketch(f.plane, f);
    else if (f.type === 'point') this.selectStep(id); // (nothing to set: made again by a click on the part)
    else if (f.type === 'extrude') this.openExtrude(structuredClone(f), false);
    else this.openCommand(structuredClone(f), false);
  }

  /** Delete a step and the steps that need it (an extrude of a deleted sketch, a sketch on its faces). */
  /** What deleting step `id` takes with it. hard: steps that cannot be without it (they round its edges, extrude
   *  its sketch …); soft: steps that only stand on it — a sketch or hole on its face, a size measured from its edges,
   *  "up to" its face — and can stay where they are now instead. keep = true: soft ones stay (not deleted). */
  dependents(id, keep) {
    const gone = new Set([id]), soft = new Set();
    const owns = (name) => gone.has(this.faceOwner({ name }));
    for (const f of this.part.features) {
      if (f.id === id) continue;
      const onEdge = (f.edges || []).some((e) => owns(e.a) || owns(e.b));
      const onFaces = (f.faces || []).some((r) => gone.has(this.faceOwner(r)));
      const needs = sketchesOf(f).some((x) => gone.has(x)) || onEdge || onFaces || (f.type === 'pattern' && (f.features || []).some((x) => gone.has(x)))
        || ((f.type === 'mirror' || f.type === 'draft') && gone.has(f.of)) || (f.type === 'loft' && (f.sketches || []).some((x) => gone.has(x)));
      const stands = gone.has(this.faceOwner(f.plane?.face)) || gone.has(this.faceOwner(f.upto)) || this.refsTo(f, owns) || this.pointOn(f, owns);
      if (needs || (stands && !keep)) gone.add(f.id);
      else if (stands) soft.add(f.id);
    }
    return { gone, soft };
  }

  /** Does step f measure from (or place holes from) an edge / corner of a face that `owns` says goes? */
  refsTo(f, owns) {
    const endRefs = (x) => x && typeof x === 'object' && ((x.edge && (owns(x.edge.a) || owns(x.edge.b))) || (x.vertex?.faces || []).some(owns) || (x.point && owns(`${x.point}:`)) || (x.axis && owns(x.axis.face)));
    if ((f.dims || []).some((d) => endRefs(d.a) || endRefs(d.b))) return true;
    return (f.from || []).some((s) => s && ['x', 'y'].some((k) => (s[k]?.edge && (owns(s[k].edge.a) || owns(s[k].edge.b))) || (s[k]?.axis && owns(s[k].axis.face))
      || (s[k]?.mid || []).some((e) => owns(e.a) || owns(e.b))));
  }

  /** Is step f a reference point on a corner / edge of a face that `owns` says goes? */
  pointOn(f, owns) {
    const at = f.type === 'point' ? f.at || {} : {};
    return (at.vertex?.faces || []).some(owns) || [at.centre, at.mid].some((e) => e && (owns(e.a) || owns(e.b)));
  }

  /** Keep step f where it is now, no longer on step `gone`: its plane fixed where the face is now, its sizes from
   *  that step's edges fixed at their place, "up to" its face -> the distance it has. */
  detach(f, owns) {
    const g = structuredClone(f);
    if (g.plane?.face && owns(this.faceOwner(g.plane.face) + ':')) g.plane = { frame: structuredClone(this.frames?.[g.id] || g.plane.frame) };
    for (const d of g.dims || []) {
      for (const k of ['a', 'b']) {
        const x = d[k];
        if (x && typeof x === 'object' && ((x.edge && (owns(x.edge.a) || owns(x.edge.b))) || (x.vertex?.faces || []).some(owns) || (x.point && owns(`${x.point}:`)) || (x.axis && owns(x.axis.face)))) d[k] = { ref: x.ref };
      }
    }
    (g.from || []).forEach((s) => { for (const k of ['x', 'y']) if ((s?.[k]?.edge && (owns(s[k].edge.a) || owns(s[k].edge.b))) || (s?.[k]?.axis && owns(s[k].axis.face)) || (s?.[k]?.mid || []).some((e) => owns(e.a) || owns(e.b))) delete s[k]; });
    if (g.upto && owns(this.faceOwner(g.upto) + ':')) { delete g.upto; g.d = g.d || 10; }
    if (this.pointOn(g, owns)) g.at = { xyz: [...(this.result?.points?.[g.id] || Object.values(g.at)[0]?.fp || [0, 0, 0])] }; // (a fixed place)
    return g;
  }

  /** Delete a step; steps that stand on it are asked about (how: 'keep' / 'all' answers it already — the AI). */
  /** A step dragged to another place in the list (before / after `toId`): refused when it would come before a step it
   *  uses (or after one that uses it); taken back when the model no longer builds there. -> moved */
  async moveStep(id, toId, after = false) {
    const fs = this.part.features, ids = new Set([].concat(id)), moving = fs.filter((x) => ids.has(x.id)), to = fs.find((x) => x.id === toId);
    if (!moving.length || !to || ids.has(toId) || this.mode !== 'part' || this.cmd) return false;
    const order = fs.filter((x) => !ids.has(x.id));
    order.splice(order.indexOf(to) + (after ? 1 : 0), 0, ...moving);
    if (order.every((x, i) => x === fs[i])) return false;
    const at = new Map(order.map((x, i) => [x.id, i]));
    for (const a of [...order].reverse()) { // what uses a step must stay after it (the nearest one named: a step, not its sketch)
      for (const b of this.dependents(a.id, false).gone) {
        if (b !== a.id && at.get(b) < at.get(a.id)) {
          this.hooks.toast(t2('“{b}” uses “{a}” — it has to stay after it.', { a: a.name, b: fs.find((x) => x.id === b)?.name || b }), 'warning', 6000);
          return false;
        }
      }
    }
    const badBefore = new Set((this.result?.features || []).filter((s) => !s.ok).map((s) => s.id));
    this.part.features = order;
    this.commit();
    await this.inflight;
    const bad = (this.result?.features || []).filter((s) => !s.ok && !badBefore.has(s.id));
    if (bad.length) { // it builds no more there: back
      this.history.go(-1);
      await this.inflight;
      const s = bad[0], name = fs.find((x) => x.id === s.id)?.name || s.id;
      this.hooks.toast(t2('Not moved — “{name}” cannot be built there: {why}', { name, why: (s.issues || [])[0] || '' }), 'warning', 8000);
      return false;
    }
    this.hooks.onChange?.();
    return true;
  }

  async remove(id, how = null) {
    if (this.mode !== 'part' || this.cmd) return;
    const all = this.dependents(id, false), kept = this.dependents(id, true);
    const name = (x) => this.part.features.find((f) => f.id === x)?.name;
    const names = [...all.gone].filter((x) => x !== id).map(name);
    let gone = all.gone;
    if (kept.soft.size) { // some can stay where they are: ask
      const pick = how || await choose(`${t('Delete')} “${name(id)}”? ${t('These steps use it')}: ${names.join(', ')}.`, [
        { value: 'keep', primary: true, label: 'Keep them where they are', hint: kept.gone.size > 1 ? `${t('Deleted too (they cannot be without it)')}: ${[...kept.gone].filter((x) => x !== id).map(name).join(', ')}` : 'A sketch keeps its place and its sizes; it no longer follows the deleted step.' },
        { value: 'all', danger: true, label: 'Delete them too' },
        { value: null, label: 'Cancel' }]);
      if (!pick) return;
      if (pick === 'keep') {
        gone = kept.gone;
        const owns = (n) => gone.has(this.faceOwner({ name: n }));
        this.part.features = this.part.features.map((f) => (kept.soft.has(f.id) ? this.detach(f, owns) : f));
      }
    } else if (gone.size > 1 && !how && !(await confirmIn(`Delete “${name(id)}”? These steps need it and are deleted too: ${names.join(', ')}.`, { ok: 'Delete them', danger: true }))) return;
    this.part.features = this.part.features.filter((f) => !gone.has(f.id));
    this.selected = null;
    this.commit();
  }

  // ------------------------------------------------------------------ property panel
  /** The sketch's state on its buttons: ✓ Finish sketch green when every size is fixed; 🪄 Auto-dimension only while
   *  sizes are still free. */
  sketchState() {
    if (this.mode !== 'sketch' || !this.sk) return;
    const dof = this.sk.dof, any = this.sk.f.entities.length > 0;
    const fin = this.els.viewport.querySelector('[data-a=finish]'), auto = this.els.viewport.querySelector('.m-cmdbar [data-a=autodim]');
    if (fin) {
      fin.classList.toggle('done', any && dof === 0);
      fin.title = t(any && dof === 0 ? 'Every size is fixed — done drawing, next: Extrude (Enter)'
        : any && dof > 0 ? 'Some sizes are still free (they follow when you drag) — it can be finished anyway; 🪄 Auto-dimension fixes them (Enter)' : 'Done drawing — next: Extrude (Enter)');
    }
    if (auto) auto.hidden = !(any && dof > 0);
    const o = originKey(this.sk.f.plane?.origin); // (after an undo: the origin it went back to)
    for (const b of this.els.viewport.querySelectorAll('.m-cmdbar [data-origin]')) b.classList.toggle('on', b.dataset.origin === o);
  }

  renderProps() {
    this.sketchState();
    const box = this.$('.mp-body');
    if (this.painting && !this.cmd) { this.renderPaint(box); return null; }
    if (this.cmd) {
      const ty = this.cmd.feature.type;
      const r = ty === 'extrude' ? this.renderExtrude(box) : ty === 'hole' ? this.renderHole(box) : ty === 'revolve' ? this.renderRevolve(box)
        : ty === 'shell' ? this.renderShell(box) : ty === 'pattern' ? this.renderPattern(box)
        : ty === 'loft' || ty === 'sweep' ? this.renderProfiles(box) : ty === 'decal' ? this.renderDecal(box) : ty === 'mirror' ? this.renderMirror(box) : ty === 'draft' ? this.renderDraft(box) : ty === 'split' ? this.renderSplit(box) : ty === 'rib' ? this.renderRib(box) : ty === 'solid' ? this.renderSolid(box) : this.renderRound(box);
      this.addSliders(box);
      return r;
    }
    if (this.mode === 'sketch') {
      box.innerHTML = this.sk.propsHtml();
      this.bindSizes(box);
      box.querySelector('[data-a=delSel]')?.addEventListener('click', () => this.sk.deleteSel());
      for (const b of box.querySelectorAll('[data-del]')) b.addEventListener('click', () => this.sk.delDim(b.dataset.del));
      for (const b of box.querySelectorAll('[data-lock]')) b.addEventListener('click', () => this.sk.toggleLock(this.sk.f.dims.find((d) => d.id === b.dataset.lock)));
      box.querySelector('[data-a=showSizes]')?.addEventListener('click', () => this.sk.showAllSizes());
      for (const b of box.querySelectorAll('[data-delrel]')) b.addEventListener('click', () => this.sk.delRelation(b.dataset.delrel));
      this.sk.bindProps?.(box); // (its own rows and buttons)
      for (const inp of box.querySelectorAll('input[data-bk]')) {
        inp.addEventListener('change', () => this.sk.setBlock(inp.dataset.bk, inp.value));
        inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); });
      }
      for (const inp of box.querySelectorAll('input[data-bt]')) {
        inp.addEventListener('change', () => this.retext(inp.value));
        inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); this.textFocus = 0; if (ev.key === 'Enter') inp.blur(); });
        if (Date.now() - (this.textFocus || 0) < 2000) { inp.focus(); inp.select(); } // (a text just put in: type over it)
      }
      return null;
    }
    if (this.mode === 'plane') {
      box.innerHTML = '<h2>New sketch</h2><p class="hint">Click a flat face of the part to sketch on it — holes, pockets and bosses go there. Or choose a plane in the bar above.</p>';
      return null;
    }
    const chosen = this.mode === 'part' && this.selected && this.part.features.find((g) => g.id === this.selected);
    if (chosen?.type === 'hole') { this.renderHoleStep(box, chosen); return null; }
    const b = this.result?.body;
    if (!this.part.features.length) {
      box.innerHTML = `<h2>New 3D model</h2><p class="hint">Start with a sketch: draw a rectangle or a circle, then give it a height with Extrude.</p>
        <div class="row-actions"><button class="btn primary" data-a="sketch">✏ Start a sketch</button></div>`;
    } else {
      const bad = (this.result?.features || []).filter((s) => !s.ok);
      const rb = rollbackNote(this.part), rbNote = rb ? `<p class="hint mp-rb-note" data-no-i18n>${esc(rb)}</p>` : ''; // (⏮ the bar is up: print and export follow it)
      box.innerHTML = `<h2>Part</h2>
        ${b ? `<div class="mp-facts"><span>Size</span><b>${fmt(b.bbox[3] - b.bbox[0])} × ${fmt(b.bbox[4] - b.bbox[1])} × ${fmt(b.bbox[5] - b.bbox[2])} mm</b>
          <span>Volume</span><b>${fmt(b.volume / 1000)} cm³</b>
          <span>Mass</span><b>${fmt(+(b.volume / 1000 * (MATERIALS[this.part.material || 'PLA'])).toFixed(1))} g <span class="mp-sub">(solid)</span></b>
          ${Number.isFinite(b.area) ? `<span>Area</span><b>${fmt(+(b.area / 100).toFixed(2))} cm²</b>` : ''}
          ${b.cog ? `<span title="${esc(t("Centre of mass (centre of gravity) of the solid, in the part's coordinates"))}">CoG</span><b class="mp-cog"><span data-no-i18n>${cogText(b.cog)} mm</span>
            <button class="btn small ${this.cogOn ? 'on' : ''}" data-a="cog" title="${esc(t('Show the centre of mass in the view (⊕)'))}">⊕</button></b>` : ''}</div>
          <div class="field"><label>Material</label><select data-k="material">${MATERIAL_GROUPS.map(([g, ms]) => `<optgroup label="${esc(t(g))}">${ms.map(([k, rho]) => `<option value="${k}" ${k === (this.part.material || 'PLA') ? 'selected' : ''}>${esc(t(k))} — ${rho} g/cm³</option>`).join('')}</optgroup>`).join('')}</select></div>
          <div class="field"><label>Colour</label><input type="color" data-k="color" value="${lookColor(this.part) || '#d9dee6'}" title="Its colour here and in assemblies (without one: its material's)"></div>
          <details class="mp-more"${this.moreOpen ? ' open' : ''}><summary title="Tolerances for the 2D drawing, see-through">More…</summary>
          <div class="field"><label>Tolerances</label><select data-k="tolerance" title="The general tolerances (ISO 2768) for sizes without their own — on the 2D drawing">
            ${[['', '—'], ['f', 'ISO 2768-f (fine)'], ['m', 'ISO 2768-m (medium)'], ['c', 'ISO 2768-c (coarse)']].map(([v, l]) => `<option value="${v}" ${v === (this.part.tolerance || '') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
          <div class="field mp-look"><label>See-through</label><input type="range" min="0" max="90" step="5" data-k="clear" value="${Math.round((1 - (this.part.opacity ?? 1)) * 100)}"><span class="unit">${Math.round((1 - (this.part.opacity ?? 1)) * 100)} %</span></div>
          </details>
          ${this.threadsHtml()}`
      : '<p class="hint">No solid yet — extrude a sketch.</p>'}
        ${bad.length ? `<p class="mp-bad">⚠ ${bad.length} step(s) could not be built — point at ⚠ in the list to see why.</p>` : ''}
        ${libraryFactsHtml(this.part.library)}
        ${this.part.libEdit && this.hooks.saveBackToLibrary ? `<div class="mp-libedit"><b>📚 ${esc(t('Library part'))}</b> <span data-no-i18n>${esc(this.part.libEdit.name || '')}</span>
          <p class="hint">${esc(t('You are changing a part of your library. Save it back to keep the change there — parts already in projects stay as they were.'))}</p>
          <div class="row-actions"><button class="btn small primary" data-a="saveBack">📚 ${esc(t('Save back to the library'))}</button></div></div>` : ''}
        <div class="row-actions wrap">${this.hooks.saveToLibrary && this.part.features.length ? '<button class="btn small" data-a="saveToLibrary" title="Keep this 3D model in your parts library (on the server) — to use it again in any project">📚 Save to the library</button>' : ''}
        ${this.hooks.duplicatePart ? '<button class="btn small" data-a="duplicatePart" title="A copy of this 3D model as a new part of its own (its own tab) — change it without changing this one">⧉ Duplicate as a new part</button>' : ''}</div>
        ${b ? '<div data-dock="mexport">' : ''}${b && this.hooks.toPrint ? `<h3>3D print</h3>
          <div class="row-actions"><button class="btn small primary" data-a="toPrint" title="Check it fits your printer, split it into exact pieces with joints — in a printing copy of this part">🖨 Prepare for 3D print</button></div>${rbNote}` : ''}
        ${b ? `<h3>Export</h3>${rbNote}<div class="row-actions wrap"><button class="btn small" data-x="stl" title="For 3D printing">STL</button>
          <button class="btn small" data-x="step" title="For other CAD programs (exact circles and faces)">STEP</button>
          <button class="btn small" data-x="iges" title="For CAD programs that ask for IGES (exact solid, mm) — STEP is better where it is read">IGES</button>
          <button class="btn small" data-x="glb" title="glTF for viewers and rendering: its colour and material (metal / plastic)">GLB</button>
          <button class="btn small" data-x="obj" title="A mesh for 3D programs and renderers that take OBJ (mm)">OBJ</button>
          <button class="btn small" data-x="pdf" title="A 2D drawing: front, top and right views, sizes, holes, title block">📐 Drawing (PDF)</button></div>
          ${this.hooks.newSheet ? '<div class="row-actions"><button class="btn small primary" data-a="newSheet" title="A drawing sheet of this part to edit: its views and dimensions (light / medium / full), moved, deleted, added — it follows the part when it changes">📄 Drawing sheet</button></div>' : ''}</div>` : ''}`; // (data-dock: its own widget — leftdock.js)
    }
    for (const el of box.querySelectorAll('[data-a]')) el.addEventListener('click', () => (el.dataset.a === 'newSheet' ? this.hooks.newSheet() : this.action(el.dataset.a)));
    for (const el of box.querySelectorAll('[data-x]')) el.addEventListener('click', () => this.export(el.dataset.x));
    box.querySelector('[data-k=material]')?.addEventListener('change', (e) => this.setMaterial(e.target.value));
    box.querySelector('.mp-more')?.addEventListener('toggle', (e) => { this.moreOpen = e.target.open; }); // (open stays open while the panel is drawn again)
    box.querySelector('[data-k=tolerance]')?.addEventListener('change', (e) => { if (e.target.value) this.part.tolerance = e.target.value; else delete this.part.tolerance; this.history.commit(); });
    const col = box.querySelector('[data-k=color]'), clr = box.querySelector('[data-k=clear]');
    col?.addEventListener('input', () => { this.part.color = col.value; this.view.setLook({ ...this.part, color: lookColor(this.part) }); });
    col?.addEventListener('change', () => { this.history.commit(); this.hooks.onChange?.(); });
    clr?.addEventListener('input', () => {
      this.part.opacity = +(1 - clr.value / 100).toFixed(2);
      if (this.part.opacity >= 1) delete this.part.opacity;
      clr.nextElementSibling.textContent = `${clr.value} %`;
      this.view.setLook({ ...this.part, color: lookColor(this.part) });
    });
    clr?.addEventListener('change', () => { this.history.commit(); this.hooks.onChange?.(); });
    for (const el of box.querySelectorAll('[data-thr]')) el.addEventListener('click', () => this.setThreads(el.dataset.thr));
    return null;
  }

  // ------------------------------------------------------------------ 🔩 threads
  /** The part's threaded holes as built (the kernel's thread_holes: where each starts, its axis, depth, Ø, pitch). */
  threadHoles() { return (this.result?.threads?.holes || []); }

  /** The Part panel's Threads choice (only for a part with threaded holes): Hidden / Cosmetic / Real, and what the
   *  real ones took (or why they could not be cut). */
  threadsHtml() {
    const n = this.threadHoles().length, mode = this.part.threads || 'hidden', real = this.result?.threads?.real;
    if (!n) return '';
    const b = (k, label, title) => `<button data-thr="${k}" class="${mode === k ? 'on' : ''}" title="${esc(t(title))}">${esc(t(label))}</button>`;
    const note = mode === 'real' && real ? (real.issue ? `<p class="mp-bad">⚠ ${esc(real.issue)}</p>`
      : real.stopped ? `<p class="mp-bad">⚠ ${esc(t('The threads were not cut (stopped) — the next change cuts them.'))}</p>`
      : real.pending ? `<p class="hint mp-thr-pending">⏳ ${esc(t2('{n} real threads being cut — shown as lines until then', { n: real.holes }))}</p>`
      : `<p class="hint mp-thr-real">${esc(t2('{n} real threads, cut in {s} s', { n: real.cut, s: fmt(real.seconds) }))}${real.warning ? ` — ${esc(t('the part may rebuild slowly'))}` : ''}</p>`) : '';
    return `<div class="field mp-threads"><label title="${esc(t('How the threads of its threaded holes show'))}">🔩 ${esc(t('Threads'))}</label><div class="seg">${b('hidden', 'Hidden', 'Plain holes at the tap drill (the threads are on the drawing)')}${b('cosmetic', 'Cosmetic', 'Thin helix lines on the holes — view only, quick')}${b('real', 'Real', 'The threads cut into the solid (ISO metric, 60°) — in STEP / STL / 3MF exports and the print split; slower')}</div></div>${note}`;
  }

  /** 🔩 A thread just made (a tapped hole new since the last undo step — the tools, a type switched, the AI) is seen at
   *  once: threads hidden -> shown as cosmetic lines (in the same undo step), saying so; real ones stay one choice away
   *  (🔩 Real thread in the hole's panel, 🔩 Threads in the Part panel). Parts as they were opened keep their setting. */
  showNewThreads() {
    if (this.part.threads === 'cosmetic' || this.part.threads === 'real') return;
    const had = new Set((this.history.base?.features || []).filter((f) => f.type === 'hole' && f.thread).map((f) => f.id));
    if (!this.part.features.some((f) => f.type === 'hole' && f.thread && !f.suppressed && !had.has(f.id))) return;
    this.part.threads = 'cosmetic';
    this.hooks.toast(t('🔩 The thread shows as light lines (cosmetic). A real, cut thread: 🔩 Real thread (slower) in the hole’s panel.'), 'info', 5000);
  }

  /** 🔩 Show all threads (the suggestions table): asked once — cosmetic lines or real geometry. */
  async askThreads() {
    const mode = await choose(t('Show the threads as'), [
      { value: 'cosmetic', label: 'Cosmetic (light)', hint: 'Thin helix lines — view only, quick', primary: true },
      { value: 'real', label: 'Real geometry (slower)', hint: 'Cut into the solid: exports and 3D print' }]);
    return mode ? this.setThreads(mode) : null;
  }

  /** What the rebuild asks for: real threads only with no tool and no sketch open (else cosmetic lines — each preview
   *  would cut them again). */
  threadsShown() { return this.part.threads === 'real' && (this.cmd || this.mode !== 'part') ? 'cosmetic' : this.part.threads; }

  /** 🔩 How the part's threaded holes show: 'hidden' (as the tap drill) | 'cosmetic' (helix lines, view only) | 'real'
   *  (cut into the solid: exports, the print split). */
  async setThreads(mode) {
    if (!['hidden', 'cosmetic', 'real'].includes(mode)) throw new Error('threads is "hidden", "cosmetic" or "real".');
    if ((this.part.threads || 'hidden') === mode) return null;
    if (mode === 'hidden') delete this.part.threads; else this.part.threads = mode;
    this.history.commit();
    this.hooks.onChange?.();
    this.showThreads();
    this.renderProps();
    await this.rebuild();
    await this.threading; // (🔩 real: the cut, when it was left for later)
    const real = this.result?.threads?.real;
    if (mode === 'real' && real) {
      if (real.issue) this.hooks.toast(real.issue, 'error', 8000);
      else this.hooks.toast(`${t2('{n} real threads, cut in {s} s', { n: real.cut, s: fmt(real.seconds) })}${real.warning ? ` — ${t('the part may rebuild slowly')}` : ''}`, real.warning ? 'warning' : 'info', 5000);
    }
    return this.result;
  }

  /** Cosmetic threads drawn on the part (not while sketching; real ones while a tool is open, or not cut yet). */
  showThreads() {
    const mode = this.result?.threads?.mode ?? this.part.threads, lines = mode === 'cosmetic' || (mode === 'real' && this.result?.threads?.real?.pending);
    this.view.setThreads(this.mode === 'part' && lines && this.part.threads ? this.threadHoles() : null);
  }

  /** 🔩 The real threads of the part on screen (a rebuild left them for later: threads.real.pending), cut by the
   *  kernel in a process of its own (the ⚙ jobs list: Cutting real threads) while the part shows with thread lines and
   *  can be edited on — swapped in when they come, unless the part has changed since (then its own cut follows). One at
   *  a time; this.threading: until the last one is in. */
  cutThreads(features) {
    this.cutQueued = features;
    if (!this.threading) this.threading = this.cutPump().finally(() => { this.threading = null; });
    return this.threading;
  }

  async cutPump() {
    while (this.cutQueued) {
      const features = this.cutQueued, key = JSON.stringify([features, 'real']);
      this.cutQueued = null;
      const rid = newRid('t');
      try {
        const { res, r } = await fetchRebuild({ features, threads: 'real' }, rid, undefined, { cut: true });
        if (key !== this.resultKey || this.cutQueued) continue; // (the part changed meanwhile)
        if (r.cancelled || wasCancelled(rid)) { // (✕ Stop in the jobs list: lines until the next change)
          if (this.result?.threads?.real) this.result.threads.real.stopped = true;
        } else if (!res.ok) throw new Error(r.error || res.statusText);
        else {
          this.result = r;
          this.view.setBody(r.body);
          this.view.setLook({ ...this.part, color: lookColor(this.part) });
          this.view.setRefs(r.refs || []);
          this.showThreads();
          if (this.printChk) this.runPrintCheck();
          this.renderStatus();
        }
        if (!this.cmd && this.mode === 'part') this.renderProps();
      } catch (e) {
        this.hooks.toast(e.message, 'error', 7000);
      }
    }
  }

  renderStatus() {
    const b = this.result?.body;
    const el = this.$('.m-status'), n = this.barAt(); // (⏮ rolled back: said after the sizes, in its own line part)
    el.textContent = b ? `${fmt(b.bbox[3] - b.bbox[0])} × ${fmt(b.bbox[4] - b.bbox[1])} × ${fmt(b.bbox[5] - b.bbox[2])} mm · volume ${fmt(b.volume / 1000)} cm³` : '';
    if (n < this.part.features.length) {
      const rb = document.createElement('span');
      rb.className = 'm-rb-note';
      rb.textContent = `⏮ ${t2('Rolled back after “{name}”', { name: this.part.features[n - 1]?.name || '' })}`;
      el.appendChild(rb);
    }
  }

  // ------------------------------------------------------------------ rebuild
  /** The features to show: the part, with the open command's preview, or rolled back to the open sketch. */
  shown() {
    const fs = this.part.features, upTo = this.builtSteps(); // (⏮ rolled back: the steps above the bar)
    if (this.mode === 'sketch' || this.mode === 'plane') {
      const i = this.sk && !this.sk.isNew ? fs.findIndex((f) => f.id === this.sk.f.id) : -1;
      return i >= 0 ? fs.slice(0, i) : upTo;
    }
    if (this.cmd) {
      const f = this.cmd.feature, i = fs.findIndex((g) => g.id === f.id);
      if (this.cmd.isNew) return [...upTo, ...(this.cmd.pre || []), f]; // (inserted at the bar)
      return fs.slice(0, Math.max(upTo.length, i + 1)).map((g) => (g.id === f.id ? f : g)); // (a step under the bar: the part up to it)
    }
    return upTo;
  }

  /** ✕ Cancel of a rebuild: its kernel job stopped (only that process restarts); what waited is dropped — the part
   *  keeps its last result with "Cancelled — ↻ Rebuild" until the next change (or that button). */
  cancelRebuild() {
    if (!this.inflight || !this.rid) return;
    this.queued = null;
    this.cancelling = this.rid;
    this.busyBox('Cancelling…');
    cancelRid(this.rid);
  }

  /** The busy box in the view: text (null: hidden); note: "Cancelled" with ↻ Rebuild instead of Cancel. */
  busyBox(text, note = false) {
    const box = this.$('.m-busy');
    box.hidden = text == null;
    if (text == null) return;
    box.querySelector('span').textContent = text;
    box.querySelector('[data-a=stop]').hidden = note;
    box.querySelector('[data-a=stop]').disabled = text === 'Cancelling…';
    box.querySelector('[data-a=again]').hidden = !note;
    box.classList.toggle('m-cancelled', note);
  }

  rebuild() {
    this.queued = this.shown();
    if (!this.inflight) this.inflight = this.pump();
    return this.inflight;
  }

  async pump() {
    while (this.queued) {
      const features = this.queued;
      this.queued = null;
      const rid = (this.rid = newRid('m'));
      this.busyBox(null);
      const timer = setTimeout(() => { if (this.cancelling !== rid) this.busyBox('Building the 3D model…'); }, 350);
      let cancelled = false, card = null;
      const T = performance.now();
      try {
        const threads = this.threadsShown(), key = JSON.stringify([features, threads]);
        // (🔩 real threads not cut yet: the part first, with thread lines — the cut follows by itself, cutThreads)
        const { res, r } = await fetchRebuild({ features, threads }, rid, undefined, { later: true });
        if (res.status === 501) { this.showInstall(r.error); continue; }
        if (r.cancelled || wasCancelled(rid)) { cancelled = true; continue; } // (not sent again: the last result stays)
        if (!res.ok) throw new Error(r.error || res.statusText);
        this.result = r;
        this.resultKey = key;
        if (r.threads?.real?.pending) this.cutThreads(features);
        // a big part: "Drawing…" on screen before its mesh is made (the page may stop a moment there)
        if (busyShown()) await busyStep('Drawing…');
        else if (r.body && performance.now() - T > 1500) { card = busy('Drawing the 3D model…'); await card.painted; }
        this.applyUpdates(r);
        this.frames = { ...this.frames, ...r.frames }; // also while rolled back before an open sketch
        for (const s of r.features || []) if (s.outline) this.faceOutlines = { ...this.faceOutlines, [s.id]: s.outline }; // (⬆ faces' outlines, for drawing them)
        const first = !this.view.body && r.body;
        this.view.setBody(r.body);
        this.view.setLook({ ...this.part, color: lookColor(this.part) });
        this.view.setShades(this.cmd?.feature.type === 'split'); // (✂ Split's preview: the pieces in two shades)
        this.view.setRefs(r.refs || []);
        this.showThreads();
        this.showCog();
        if (this.printChk) this.runPrintCheck(); // (it follows the part)
        if (first && this.mode === 'part') this.view.setView('iso');
        const gone = (r.features || []).flatMap((s) => s.issues || []).find((x) => /^BLOB_MISSING/.test(x));
        if (gone) this.hooks.toast(t('The file of an imported solid is not on this computer — open the project file (it carries the file) again.'), 'error', 9000);
        this.datums(!r.body || this.mode === 'plane');
        this.sk?.draw();
      } catch (e) {
        this.hooks.toast(e.message, 'error', 7000);
      } finally {
        clearTimeout(timer);
        card?.done();
        if (cancelled && !this.queued) this.busyBox('Cancelled —', true); else this.busyBox(null);
        if (this.cancelling === rid) this.cancelling = null;
      }
    }
    this.rid = null;
    this.inflight = null;
    this.showOutlines();
    if (this.section) this.renderSection();
    if (this.cmd && (this.cmd.feature.type === 'fillet' || this.cmd.feature.type === 'chamfer')) this.view.setEdgeHighlight(-1, this.refEdges(this.cmd.feature.edges));
    if (this.dimStep && !this.dimEdit && !this.cmd && this.mode === 'part') this.reshowDims();
    if (this.cmd) this.refreshLimits();
    if (this.cmd?.feature.type === 'hole') {
      this.drawHoleDims();
      // the panel shows this rebuild's state (issues, moved holes) — unless a value is being typed in it
      if (this.$('.mp-body').contains(document.activeElement)) this.syncHoleInputs(); else this.renderProps();
    }
    this.renderTree();
    this.renderStatus();
    if (this.mode === 'part') this.renderCmdBar(); // the tools that need a solid wake up when the first one arrives
    if (!this.cmd && this.mode === 'part') this.renderProps();
    this.showPullArrow();
    this.hooks.onChange?.();
  }

  /** Steps whose dimensions come from the part's edges and corners: the rebuild found those again and moved the
   *  sketch points / hole centres with them — keep the new places (not an undo step: the same model, followed). */
  applyUpdates(r) {
    for (const s of r.features || []) {
      if (!s.update) continue;
      if (this.sk?.f.id === s.id) continue; // being edited: the sketcher has it
      const f = this.cmd?.feature.id === s.id ? this.cmd.feature : this.part.features.find((g) => g.id === s.id);
      if (f) Object.assign(f, structuredClone(s.update));
    }
  }

  showInstall(msg) {
    const box = this.$('.m-install');
    box.hidden = false;
    box.innerHTML = `<div><b>The 3D model workspace needs its CAD kernel.</b><p>${esc(msg || '')}</p>
      <p>Run this once in the app's folder, then restart the app:</p><code>py -m pip install -r requirements-modeler.txt</code></div>`;
  }

  /** Record a step in the undo history and rebuild. */
  commit() {
    this.fixBar();
    this.showNewThreads();
    this.history.commit();
    this.render();
    this.rebuild();
  }

  closeAll() {
    if (this.measuring) this.toggleMeasure();
    if (this.mode === 'sketch' || this.mode === 'plane') this.leaveSketchMode();
    this.cmd = null;
    this.mode = 'part';
    this.hint('');
  }

  /** Sketches as lines in the 3D view: not extruded yet = bright (the next step), used = faint. Hidden while
   *  sketching (the open sketch is drawn by the sketcher) and for sketches after an open one. */
  showOutlines() {
    if (this.mode === 'sketch') { this.view.setOutlines([]); return; }
    const used = new Set(this.part.features.filter((f) => !f.suppressed).flatMap(sketchesOf));
    if (this.cmd?.feature) for (const x of sketchesOf(this.cmd.feature)) used.add(x);
    const list = [];
    for (const f of this.part.features.slice(0, this.usable())) { // (⏮ not the sketches under the rollback bar)
      if (f.type !== 'sketch') continue;
      const fr = f.plane?.datum ? datumFrame(f.plane) : this.frames?.[f.id] || f.plane?.frame;
      if (!fr) continue;
      const sk = upgradeSketch(f), P = (id) => (id === 'O' ? [0, 0] : sk.points[id]);
      const lines = sk.entities.filter((e) => e.t === 'line' && P(e.a) && P(e.b)).map((e) => [P(e.a), P(e.b)]);
      const circles = sk.entities.filter((e) => e.t === 'circle' && P(e.c)).map((e) => [P(e.c), e.r]);
      for (const e of sk.entities.filter((x) => x.t === 'arc' && P(x.a) && P(x.b) && P(x.c))) {
        const ps = arcPts(P(e.c), P(e.a), P(e.b));
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1]]);
      }
      for (const e of sk.entities.filter((x) => x.t === 'spline' && (x.pts || []).every(P))) { // smooth curves
        const ps = splinePts(e.pts.map(P));
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1]]);
      }
      for (const e of sk.entities.filter((x) => x.t === 'outline')) { // ⬆ a face's outline: as the last rebuild found it
        for (const r of this.faceOutlines?.[f.id]?.[e.id] || []) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length]]);
      }
      for (const e of sk.entities.filter((x) => x.t === 'block')) {
        const k = e.scale || 1, [au, av] = e.at || [0, 0];
        for (const poly of e.polys || []) for (const r of poly) for (let i = 0; i < r.length; i++) {
          const a = r[i], b = r[(i + 1) % r.length];
          lines.push([[au + k * a[0], av + k * a[1]], [au + k * b[0], av + k * b[1]]]);
        }
      }
      list.push({ id: f.id, frame: fr, lines, circles, dim: used.has(f.id) && f.id !== this.selected, sel: f.id === this.selected && this.mode === 'part' });
    }
    this.view.setOutlines(list);
  }

  /** 🖼 Outline in a sketch: a picture (traced), a DXF / DWG or a PDF drawing -> its outline as a block. */
  async insertOutline() {
    if (!this.sk) return;
    const o = await this.hooks.pickOutline();
    if (!o || !this.sk) return;
    this.sk.addBlock(o);
  }

  /** 𝐓 Text in a sketch: "Text" 10 mm high as a block, its text and height typed in the panel. */
  async insertText(text = 'Text', h = 10) {
    const o = await this.textBlock(text, h);
    if (!o || !this.sk) return;
    this.textFocus = Date.now(); // (the panel is drawn again once the sketch is solved: renderProps focuses it then)
    this.sk.addBlock(o, { text });
  }

  /** The text's outline h mm high, its lower-left corner at 0: {name, polygons, width, height} (null: no ink). */
  async textBlock(text, h) {
    try {
      const o = await textOutline(text, { bold: true });
      if (!o) { this.hooks.toast('Type some text first.', 'warning'); return null; }
      // the letters' own box (the trace keeps a margin) scaled to h high, its lower-left corner at 0
      const pts = o.polygons.flat(2), xs = pts.map((p) => p[0] * o.aspect), ys = pts.map((p) => p[1]);
      const x0 = Math.min(...xs), y0 = Math.min(...ys), k = h / (Math.max(...ys) - y0 || 1);
      const polygons = o.polygons.map((poly) => poly.map((r) => r.map(([x, y]) => [+((x * o.aspect - x0) * k).toFixed(4), +((y - y0) * k).toFixed(4)])));
      return { name: text, polygons, width: (Math.max(...xs) - x0) * k, height: h };
    } catch (e) { this.hooks.toast(e.message, 'error'); return null; }
  }

  /** A text block's text typed anew: traced again, its height and corner kept. */
  async retext(text) {
    const e = this.sk?.ent(this.sk.sel?.id);
    if (!e || e.t !== 'block' || e.text === undefined || !String(text).trim()) return;
    const o = await this.textBlock(text, e.h0 * (e.scale || 1));
    if (!o || !this.sk || this.sk.ent(e.id) !== e) return;
    this.sk.step();
    Object.assign(e, { text, name: text, polys: o.polygons, w0: o.width, h0: o.height, scale: 1 });
    this.sk.changed();
  }

  // ------------------------------------------------------------------ sketch: choosing the plane
  startSketch() {
    if (this.mode !== 'part' || this.cmd) return;
    if (this.measuring) this.toggleMeasure();
    if (!this.result?.body) {
      // nothing to sketch on yet: start right away on the Top plane (one click less)
      this.enterSketch({ datum: 'XY' });
      this.hooks.toast('Sketching on the Top plane — click two corners to draw a rectangle.', 'info', 4000);
      return;
    }
    this.mode = 'plane';
    this.datums(true);
    this.hint('Click a flat face of the part to sketch on it — or choose Top / Front / Right above. Esc cancels.');
    this.render();
  }

  /** ⇳ Midway: the next two clicks on parallel flat faces put the sketch halfway between them. */
  toggleMidPick() {
    this.midPick = this.midPick ? null : {};
    this.view.setSelectedFaces(null);
    this.hint(this.midPick ? 'Midway — click a flat face, then the face opposite it. Esc cancels.' : 'Click a flat face of the part to sketch on it — or choose Top / Front / Right above. Esc cancels.');
    this.render();
  }

  cancelPlane() {
    this.midPick = null;
    this.view.setSelectedFaces(null);
    this.mode = 'part';
    this.view.setHover(-1);
    this.datums(!this.result?.body);
    this.hint('');
    this.render();
  }

  // ------------------------------------------------------------------ sketch mode (sketcher.js does the drawing)
  enterSketch(plane, existing = null) {
    this.midPick = null;
    this.closeCtx();
    this.closeDimEdit();
    this.dimStep = null;
    this.view.setTags([]);
    this.view.setSelectedFaces(null);
    this.view.setHover(-1);
    this.tip(null);
    const feature = existing ? structuredClone(existing)
      : { id: this.newId(), type: 'sketch', name: this.nextName('sketch'), plane, points: {}, entities: [], constraints: [], dims: [] };
    this.sk = new Sketcher(this, feature, !existing);
    this.mode = 'sketch';
    this.showOutlines();
    this.view.setHover(-1);
    this.datums(false);
    this.view.setGhost(true); // the part see-through: the sketch and its dimensions show through it
    this.view.controls.enableRotate = false; // left button draws; right button pans, wheel zooms
    this.view.controls.mouseButtons = { LEFT: null, MIDDLE: 2, RIGHT: 2 };
    this.view.lookAt(this.frame(), this.sketchSpan());
    this.render();
    this.hint(this.sk.hint());
    if (!this.sk.isNew) this.rebuild(); // show the part as it was before this sketch
    this.sk.draw();
    this.sk.init();
    this.sk.renderSuggest(); // (the sketch's own table in place of the part's: what to draw / do next)
  }

  /** A new, empty sketch: put it on another base plane. */
  movePlane(datum) {
    if (!this.sk || this.sk.f.entities.length) return;
    this.sk.f.plane = { datum, ...(this.sk.f.plane?.offset ? { offset: this.sk.f.plane.offset } : {}) };
    this.view.lookAt(this.frame(), this.sketchSpan());
    this.renderCmdBar();
    this.sk.draw();
  }

  leaveSketchMode() {
    this.sk = null;
    setTimeout(() => this.showOutlines(), 0); // after the mode is back to part
    this.view.setSketch(null);
    this.view.setGhost(false);
    this.sk?.closeChooser?.();
    this.view.controls.enableRotate = true;
    this.view.controls.mouseButtons = { LEFT: 0, MIDDLE: 1, RIGHT: 2 };
  }

  /** The frame of the open sketch (from the last rebuild when the kernel moved it with its face). */
  frame() {
    const f = this.sk.f;
    if (f.plane?.datum) return datumFrame(f.plane);
    const fr = this.frames?.[f.id];
    return fr && sameOrigin(fr, f.plane) ? fr : f.plane.frame; // (an origin just switched: the plane's own)
  }

  /** The sketch's Origin (◎ the face's centre, ⌜ its corner, ⊕ the part's origin): its 0, 0 moves there, the shapes
   *  keep their place on the part (their coordinates shift; one undo step). */
  setSketchOrigin(how) {
    const f = this.sk.f;
    if (originKey(f.plane?.origin) === how) return;
    const r = moveOrigin(this, f.plane, this.frame(), how);
    if (!r) { this.hooks.toast('The face is not in the view — the origin stays where it is.', 'warning'); return; }
    this.sk.step();
    shiftSketch(f, r.du, r.dv);
    f.plane = r.plane;
    this.sk.changed();
  }

  sketchSpan() {
    // the sketch's own points, and the edges of the face it is on (fit the face, not the whole part)
    const ps = [...Object.values(this.sk.f.points), ...this.sk.refs().points,
      ...this.sk.f.entities.filter((e) => e.t === 'block').flatMap((e) => this.sk.blockRings(e).flat()),
      ...this.sk.f.entities.filter((e) => e.t === 'outline').flatMap((e) => this.sk.outlineRings(e).flat())];
    const rs = this.sk.f.entities.filter((e) => e.t === 'circle').map((e) => [...(this.sk.P(e.c) || [0, 0]), e.r]);
    if (!ps.length) return Math.max(this.view.size * 1.4, 80);
    const ext = Math.max(...ps.map((p) => Math.max(Math.abs(p[0]), Math.abs(p[1]))), ...rs.map(([u, v, r]) => Math.max(Math.abs(u), Math.abs(v)) + r));
    return Math.max(ext * 2.2, 20);
  }

  finishSketch() {
    const f = this.sk.result();
    if (!f.entities.length) { this.hooks.toast('Draw a rectangle, lines or a circle first — or Cancel.', 'warning'); return; }
    const { isNew } = this.sk;
    if (isNew) this.insertSteps(f);
    else this.part.features = this.part.features.map((g) => (g.id === f.id ? f : g));
    this.leaveSketchMode();
    this.mode = 'part';
    this.hint('');
    this.history.commit();
    if (isNew) {
      this.openExtrude(this.newExtrude(f.id), true); // the obvious next step, ready to go
      return;
    }
    this.selected = null;
    this.render();
    this.rebuild();
    this.view.setView('iso');
  }

  cancelSketch() {
    this.leaveSketchMode();
    this.mode = 'part';
    this.hint('');
    this.render();
    this.rebuild();
    this.view.setView('iso');
  }

  // ------------------------------------------------------------------ Extrude
  newExtrude(sketchId) {
    const sk = this.part.features.find((f) => f.id === sketchId);
    const onFace = !!sk?.plane?.face && !!this.result?.body;
    // a sketch on a face of the part usually makes a hole or a pocket; on a plane, new material
    return { id: this.newId(), type: 'extrude', name: this.nextName('extrude', sketchId), sketch: sketchId, op: onFace ? 'cut' : 'add',
      d: onFace ? 5 : 10, symmetric: false, flip: false, through: false };
  }

  /** A sketch whose one shape is a flat face's outline — its outer loop and holes, the face's own edges found again each
   *  rebuild (as projected edges: it follows the face when earlier steps change it). */
  faceSketch(face, id = this.newId()) {
    return { id, type: 'sketch', name: this.nextName('sketch'), plane: { face: face.ref || { name: face.name }, frame: face.frame },
      points: {}, entities: [{ id: 'o1', t: 'outline', face: { name: face.name, fp: face.centroid } }], constraints: [], dims: [] };
  }

  /** ⬆ Extrude this face: its outline sketch and an extrude of it 10 mm out of the part, the panel open (⇅: a cut into
   *  the part instead). OK keeps both as ordinary steps; Cancel drops the sketch too (it was never a step). */
  extrudeFace(face) {
    if (this.mode !== 'part' || this.cmd || face?.type !== 'plane') return;
    const sk = this.faceSketch(face), n = parseInt(sk.id.replace(/\D/g, ''), 10) || 0;
    this.openExtrude({ id: `F${n + 1}`, type: 'extrude', name: this.nextName('extrude'), sketch: sk.id, op: 'add', d: 10, symmetric: false, flip: false, through: false }, true, [sk]);
  }

  /** The sketch of a step (also the open ⬆ Extrude this face's own, not a step yet). */
  sketchOf(id) { return this.part.features.find((g) => g.id === id) || this.cmd?.pre?.find((g) => g.id === id) || null; }

  /** An extrude of a face's outline (its sketch only that, on that face): ⇅ makes it a cut into the part. */
  isFaceExtrude(f) {
    const sk = f?.type === 'extrude' && this.sketchOf(f.sketch), es = sk?.entities || [];
    return !!es.length && es.every((e) => e.t === 'outline' && e.face?.name === sk.plane?.face?.name);
  }

  /** The open extrude's pull arrow: from its sketch along the way it goes, as long as its distance — drag its tip. */
  showPullArrow() {
    const f = this.cmd?.feature, sk = f?.type === 'extrude' && this.mode === 'part' && !f.upto && !f.upto_next && !f.through && this.sketchOf(f.sketch);
    const fr = sk && (sk.plane?.datum ? datumFrame(sk.plane) : this.frames?.[sk.id] || sk.plane?.frame);
    if (!fr || !(f.d > 0)) { this.view.setPullArrow(null); return; }
    const c = this.isFaceExtrude(f) ? [0, 0] : this.sketchCentre(sk), y = [fr.n[1] * fr.x[2] - fr.n[2] * fr.x[1], fr.n[2] * fr.x[0] - fr.n[0] * fr.x[2], fr.n[0] * fr.x[1] - fr.n[1] * fr.x[0]];
    const s = (f.op === 'cut' ? -1 : 1) * (f.flip ? -1 : 1), o = [0, 1, 2].map((i) => fr.o[i] + c[0] * fr.x[i] + c[1] * y[i]);
    this.view.setPullArrow(o, fr.n.map((v) => v * s), f.symmetric ? f.d / 2 : f.d);
  }

  /** The pull arrow dragged: the distance follows the mouse along it (0.5 mm steps), the panel's number too. */
  pullTo(e) {
    const f = this.cmd?.feature, t0 = this.view.pullAlong(e.clientX, e.clientY);
    if (!f || t0 === null) return;
    const d = Math.max(0.5, Math.round(t0 * (f.symmetric ? 2 : 1) * 2) / 2);
    if (d === f.d) return;
    f.d = d;
    const num = this.$('.mp-body input[data-k=d]');
    if (num) { num.value = fmt(d); num.dispatchEvent(new Event('input', { bubbles: true })); } else this.rebuild();
    this.showPullArrow();
  }

  startExtrude() {
    if (this.mode !== 'part' || this.cmd) return;
    const used = new Set(this.part.features.flatMap(sketchesOf));
    const sks = this.sketches();
    if (!sks.length) { this.hooks.toast('Draw a sketch first (✏ Sketch).', 'warning', 4500, { point: '.m-cmdbar [data-a=sketch]' }); return; }
    const sk = [...sks].reverse().find((s) => !used.has(s.id)) || sks[sks.length - 1];
    this.openExtrude(this.newExtrude(sk.id), true);
  }

  openExtrude(feature, isNew, pre = null) {
    if (this.measuring) this.toggleMeasure();
    this.cmd = { feature, isNew, ...(pre ? { pre } : {}) };
    this.mode = 'part';
    this.selected = feature.id;
    this.hint('Extrude — the preview is in the view. Enter = OK, Esc = Cancel.');
    this.render();
    this.rebuild();
    this.view.setView('iso');
    setTimeout(() => { const i = this.$('.mp-body input[data-k=d]'); i?.focus(); i?.select(); }, 30);
  }

  renderExtrude(box) {
    const f = this.cmd.feature, sks = this.sketches(), st = this.status(f.id);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="seg big"><button data-op="add" class="${f.op !== 'cut' ? 'on' : ''}" title="Add material">⬆ Add material</button><button data-op="cut" class="${f.op === 'cut' ? 'on' : ''}" title="Remove material (holes, pockets)">⬇ Cut</button></div>
      ${this.result?.body || f.upto || f.upto_next ? `<div class="seg"><button data-upto="0" class="${!f.upto && !f.upto_next ? 'on' : ''}" title="A height you type">Distance</button><button data-upto="1" class="${f.upto && !f.upto_next ? 'on' : ''}" title="As far as a face of the part — it follows the face when the part changes">Up to a face</button><button data-upto="next" class="${f.upto_next ? 'on' : ''}" title="As far as the first face of the part across the whole sketch — it follows the part">Up to next</button></div>` : ''}
      ${f.upto_next ? `<p class="mp-count">Up to the next face of the part across the whole sketch.</p>
        <div class="row-actions"><button class="btn small" data-k="flip" title="Extrude to the other side of the sketch">⇅ Flip direction</button></div>`
      : f.upto ? `<p class="mp-count">${f.upto.name ? `Up to the face <b>${esc(this.faceLabel(f.upto.name))}</b>` : 'Click a flat face of the part (parallel to the sketch).'}</p>
        <div class="field"><label>Offset</label><input type="number" step="any" data-k="offset" value="${fmt(f.offset || 0)}"><span class="unit">mm</span></div>
        <p class="hint">Offset: more = past the face, less (negative) = short of it. Click another face to change it.</p>`
      : `<div class="field"><label>Distance</label><input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}" ${f.through ? 'disabled' : ''}><span class="unit">mm</span></div>
      ${f.op === 'cut' ? `<label class="check"><input type="checkbox" data-k="through" ${f.through ? 'checked' : ''}> Through all</label>` : ''}
      <label class="check"><input type="checkbox" data-k="symmetric" ${f.symmetric ? 'checked' : ''}> Both sides (symmetric)</label>
      <div class="row-actions"><button class="btn small" data-k="flip" title="Extrude to the other side of the sketch">⇅ Flip direction</button></div>`}
      <label class="check" title="Also extrude a distance to the other side of the sketch"><input type="checkbox" data-k="other" ${f.d2 ? 'checked' : ''}> ＋ Other side</label>
      ${f.d2 ? `<div class="field"><label>Other side</label><input type="number" step="any" min="0" data-k="d2" value="${fmt(f.d2)}"><span class="unit">mm</span></div>` : ''}
      ${f.upto_next || f.through ? '' : `<div class="field" title="Taper the side walls: they lean in going away from the sketch (negative: out) — so a moulded or cast part comes out"><label>Draft</label><input type="number" step="0.5" min="-44" max="44" data-k="draft" data-slider="1" value="${fmt(f.draft || 0)}"><span class="unit">°</span></div>`}
      ${sks.length > 1 && !this.cmd.pre ? `<div class="field"><label>Sketch</label><select data-k="sketch">${sks.map((s) => `<option value="${s.id}" ${s.id === f.sketch ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></div>` : ''}
      <p class="mp-bad" ${st && !st.ok ? '' : 'hidden'}>${st && !st.ok ? `⚠ ${esc(st.issues.join(' '))}` : ''}</p>
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>
      <p class="hint">The preview is in the 3D view. Enter = OK, Esc = Cancel.</p>`;
    const issue = () => { // (once built: what is wrong with these settings, e.g. nothing to go up to that way)
      const s2 = this.status(f.id), p = box.querySelector('.mp-bad');
      if (this.cmd?.feature !== f || !p) return;
      p.hidden = !s2 || s2.ok;
      p.textContent = p.hidden ? '' : `⚠ ${s2.issues.join(' ')}`;
    };
    const rebuild = () => this.rebuild().then(issue);
    const changed = () => { this.renderExtrude(box); rebuild(); };
    // (how it goes: setExtrude — the same as the icons at its height on the part)
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { if ((f.op === 'cut') !== (b.dataset.op === 'cut')) setExtrude(f, 'op'); changed(); });
    for (const b of box.querySelectorAll('[data-upto]')) {
      b.addEventListener('click', () => {
        setExtrude(f, { 1: 'upto', next: 'next' }[b.dataset.upto] || 'distance');
        if (f.upto) this.hint('Up to a face — click a flat face of the part. Enter = OK, Esc = Cancel.');
        changed();
      });
    }
    for (const d of box.querySelectorAll('[data-k=d], [data-k=offset], [data-k=d2]')) {
      d.addEventListener('input', () => {
        const v = parseFloat(d.value);
        if (d.dataset.k === 'offset' ? Number.isFinite(v) : v > 0) { f[d.dataset.k] = v; rebuild(); }
      });
      d.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okExtrude(); if (e.key === 'Escape') this.cancelExtrude(); });
    }
    const dr = box.querySelector('[data-k=draft]'); // (0: straight walls — the field off the step)
    dr?.addEventListener('input', () => { const v = parseFloat(String(dr.value).replace(',', '.')); if (Number.isFinite(v) && Math.abs(v) < 45) { if (v) f.draft = v; else delete f.draft; rebuild(); } });
    dr?.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okExtrude(); if (e.key === 'Escape') this.cancelExtrude(); });
    box.querySelector('[data-k=through]')?.addEventListener('change', (e) => { setExtrude(f, 'through', e.target.checked); changed(); });
    // ＋ Other side and Both sides (symmetric) are two ways of the same thing: one unticks the other
    box.querySelector('[data-k=symmetric]')?.addEventListener('change', (e) => { setExtrude(f, 'symmetric', e.target.checked); changed(); });
    box.querySelector('[data-k=other]')?.addEventListener('change', (e) => {
      if (e.target.checked) { f.d2 = 5; f.symmetric = false; } else delete f.d2;
      changed();
      if (f.d2) setTimeout(() => { const i = box.querySelector('[data-k=d2]'); i?.focus(); i?.select(); }, 0);
    });
    box.querySelector('[data-k=flip]')?.addEventListener('click', () => { setExtrude(f, 'flip', true, this.isFaceExtrude(f)); changed(); }); // (a face's outline: out of the part, or a cut into it)
    box.querySelector('[data-k=sketch]')?.addEventListener('change', (e) => { f.sketch = e.target.value; changed(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okExtrude());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelExtrude());
    this.addSliders(box);
  }

  /** A slider under every number of a tool's panel: sliding types into the number (the part previews), typing
   *  moves the slider. Its range: from the number's min (or below 0 when it may be negative) to about 3× the value.
   *  Hard limits (the number's max: what the kernel can build, a full turn): a number past it is pulled back, saying
   *  why. Soft ones (no max — only a suggested range, "_soft" from the kernel): a number past it is kept and the
   *  slider grows round it. */
  addSliders(box) {
    // the ranges known for these very settings (not the ones from before e.g. a pattern went round)
    if (this.cmd?.limits && this.cmd.limitsKey === this.limitsKey(this.shown(), this.cmd.feature.id)) setTimeout(() => this.applyLimits(box, this.cmd.limits), 0);
    for (const num of box.querySelectorAll('input[type=number]')) {
      if (num.dataset.slider || num.disabled) continue;
      num.dataset.slider = '1';
      const v0 = parseFloat(num.value) || 0, int = num.step === '1', deg = /°/.test(num.parentElement?.textContent || '') || num.dataset.k === 'angle';
      const lo = num.dataset.lo !== undefined ? +num.dataset.lo : num.min !== '' ? parseFloat(num.min) : -Math.max(10, Math.abs(v0) * 3);
      const hi = num.dataset.hi !== undefined ? +num.dataset.hi : num.max !== '' ? parseFloat(num.max) : deg ? 360 : int ? Math.max(20, v0 * 2) : Math.max(10, Math.abs(v0) * 3, lo + 1);
      const sl = document.createElement('input');
      Object.assign(sl, { type: 'range', min: String(Math.max(lo, int ? 2 : lo)), max: String(hi), step: num.dataset.step || (int ? '1' : hi > 50 ? '0.5' : '0.1'), value: String(v0) });
      sl.className = 'mp-slider';
      sl.title = 'Slide to change it — the part follows';
      sl.addEventListener('input', () => {
        num.value = fmt(Math.max(+sl.value, num.min !== '' ? +num.min : -Infinity));
        num.dispatchEvent(new Event('input', { bubbles: true }));
      });
      sl.addEventListener('change', () => num.dispatchEvent(new Event('change', { bubbles: true })));
      const typed = () => [isPlain(num.value) ? parseFloat(num.value) : NaN, num.min !== '' ? +num.min : -Infinity, num.max !== '' ? +num.max : Infinity]; // (an expression: held to the range once worked out)
      num.addEventListener('input', (e) => {
        const [v, lo, hi] = typed();
        if (Number.isFinite(v) && v > (num.dataset.top ? +num.dataset.top : hi)) { // (≈ max: a little above it may fit)
          num.value = fmt(hi);
          const why = LIMIT_WHY[`${this.cmd?.feature.type}.${num.dataset.k}`];
          this.hooks.toast(why ? t2(why, { v: num.value }) : t2('{v} is the most that works here (with what is around it).', { v: num.value }), 'info', 3500);
        } else if (Number.isFinite(v) && v < lo) e.stopImmediatePropagation(); // (half typed — "1" on the way to "10": not used; held to the min when done)
      }, true);
      num.addEventListener('change', () => {
        const [v, lo] = typed();
        if (!(Number.isFinite(v) && v < lo)) return;
        num.value = fmt(lo);
        this.hooks.toast(t2('{v} is the least that works here.', { v: num.value }), 'info', 3500);
        num.dispatchEvent(new Event('input', { bubbles: true }));
      }, true);
      num.addEventListener('input', () => {
        const v = parseFloat(num.value);
        if (!Number.isFinite(v)) return;
        if (v > +sl.max) sl.max = String(growTo(v)); // (a soft range: it grows round what was typed)
        sl.value = String(v);
      });
      const row = num.closest('.field, .mp-hd, label') || num.parentElement;
      row.after(sl);
    }
    // 𝑥 the step's numbers also take an expression of the project's parameters (L / 2), kept in its expr
    for (const num of box.querySelectorAll('input[type=number][data-k]')) exprField(num, { owner: () => this.cmd?.feature, key: num.dataset.k });
  }

  // ------------------------------------------------------------------ the range each number can take
  /** {field: [min, max]} for step `id` (with the steps before it as they are): asked from the kernel, remembered. */
  /** What a step's ranges depend on: the steps before it, and the step without its own ranged numbers. */
  limitsKey(features, id) {
    const i = features.findIndex((f) => f.id === id);
    if (i < 0) return null;
    const strip = { ...features[i] };
    for (const k of LIMIT_FIELDS[strip.type] || []) delete strip[k];
    return JSON.stringify([features.slice(0, i), strip]);
  }

  async limitsFor(features, id) {
    const i = features.findIndex((f) => f.id === id);
    if (i < 0) return {};
    const key = this.limitsKey(features, id);
    this.limitCache = this.limitCache || new Map();
    if (this.limitCache.has(key)) return this.limitCache.get(key);
    try {
      const res = await fetch('/api/model/limits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features: features.slice(0, i + 1) }, id }) });
      const r = res.ok ? await res.json() : {};
      this.limitCache.set(key, r);
      return r;
    } catch { return {}; }
  }

  /** The open tool's ranges, asked again when what they depend on changes; put on its numbers and sliders. */
  async refreshLimits() {
    const f = this.cmd?.feature;
    if (!f || !LIMIT_FIELDS[f.type]) return;
    const key = this.limitsKey(this.shown(), f.id), lim = await this.limitsFor(this.shown(), f.id);
    if (this.cmd?.feature !== f || this.limitsKey(this.shown(), f.id) !== key) return; // changed meanwhile: asked again
    this.cmd.limits = lim;
    this.cmd.limitsKey = key;
    this.applyLimits(this.$('.mp-body'), lim);
  }

  /** Numbers and sliders held to their ranges; the range shown under the slider; a value outside is pulled in.
   *  An approximate max (lim._approx: a rounding's, found to 1 %) shows "≈"; a number up to 2 % above it is left as typed.
   *  A soft max (lim._soft: only how far the kernel looked, or a pattern's copies that reach the part) is no max: the
   *  slider ends there (or round a bigger number typed) and grows when more is typed. */
  applyLimits(box, lim) {
    for (const [k, [lo, hi]] of Object.entries(lim || {}).filter(([q]) => !q.startsWith('_'))) {
      const approx = (lim._approx || []).includes(k), soft = (lim._soft || []).includes(k), top = soft ? Infinity : approx ? +(hi * 1.02).toFixed(2) : hi;
      for (const num of box.querySelectorAll(`input[type=number][data-k="${k}"], input.px-in[data-k="${k}"]`)) {
        num.min = String(lo);
        if (soft) num.removeAttribute('max'); else num.max = String(hi);
        num.toggleAttribute('data-soft', soft);
        if (approx && !soft) num.dataset.top = String(top); else delete num.dataset.top; // (typed up to it: left as it is)
        const sl = num.closest('.field, label, .mp-hd')?.nextElementSibling;
        if (sl?.classList.contains('mp-slider')) {
          const st = +sl.step || 0.1;
          sl.min = String(Math.floor(lo / st) * st); // on the step grid (0.01 would make 8 into 7.99); the number holds the min
          const cur = parseFloat(num.value);
          sl.max = String(soft && cur > hi ? growTo(cur) : hi);
          let tag = sl.nextElementSibling;
          if (!tag?.classList.contains('mp-range')) { tag = document.createElement('div'); tag.className = 'mp-range'; sl.after(tag); }
          tag.textContent = `${fmt(lo)} – ${approx && !soft ? '≈' : ''}${fmt(hi)}${soft ? '+' : ''}${k === 'count' ? '' : k === 'angle' ? '°' : ' mm'}`;
          tag.title = soft ? t('A suggestion — type a bigger number and the slider grows') : t('The most that can be built here');
        }
        const v = isPlain(num.value) ? parseFloat(num.value) : NaN;
        if (Number.isFinite(v) && (v > top || v < lo)) {
          num.value = fmt(Math.min(hi, Math.max(lo, v)));
          num.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }
    }
  }

  okExtrude() { this.okCommand(); }

  okCommand() {
    this.closeDimEdit();
    const { feature: f, isNew } = this.cmd;
    if (f.type === 'extrude' && f.upto && !f.upto.name) { this.hooks.toast('Click the face to go up to first.', 'warning'); return; }
    if (f.type === 'extrude' && !f.upto && !f.upto_next && !f.through && !(f.d > 0)) { this.hooks.toast('The distance must be greater than zero.', 'error'); return; }
    if (f.type === 'extrude' && f.d2 !== undefined && !(f.d2 > 0)) { this.hooks.toast('The distance must be greater than zero.', 'error'); return; }
    if ((f.type === 'fillet' || f.type === 'chamfer') && !f.edges.length) { this.hooks.toast('Click at least one edge first.', 'warning'); return; }
    if (f.type === 'shell' && !f.faces.length) { this.hooks.toast('Click the face(s) to leave open first.', 'warning'); return; }
    if (f.type === 'decal' && (!f.plane || !f.polys)) { this.hooks.toast(f.plane ? 'Type some text, or choose a picture.' : 'Click on a flat face where it goes.', 'warning'); return; }
    if (f.type === 'hole' && !f.points.length) { this.hooks.toast('Click on a flat face where the hole goes.', 'warning'); return; }
    if (isNew) this.insertSteps(...(this.cmd.pre || []), f); // (⬆ Extrude this face: its outline sketch first)
    else this.part.features = this.part.features.map((g) => (g.id === f.id ? f : g));
    this.cmd = null;
    this.view.setPullArrow(null);
    this.holePick = null;
    this.splitMid = false;
    this.view.setEdgeHighlight();
    this.view.setHover(-1);
    this.view.setSketch(null);
    this.hint('');
    this.selected = null; // (done: ✨ Next offers what usually follows)
    this.commit();
  }

  cancelExtrude() { this.cancelCommand(); }

  /** What a tool that places things one click after another has placed so far (holes, edges to round, faces left
   *  open), as text to compare — null for the other tools. */
  placed(f) {
    const list = { hole: f.points, fillet: f.edges, chamfer: f.edges, shell: f.faces }[f.type];
    return list ? JSON.stringify(list) : null;
  }

  /** ＋ Add position / ⌖ Move by clicking (an edited hole / text): a click in the view places from now on (the
   *  mouse shows where); again: off. */
  armPlace() {
    if (!this.cmd) return;
    this.cmd.place = !this.cmd.place;
    if (!this.cmd.place) { this.showSpot(null); this.els.viewport.querySelector('canvas').style.cursor = ''; }
    const hole = this.cmd.feature.type === 'hole';
    if (hole) this.drawHoleDims(); // (its numbers on the part: to click while not placing)
    this.hint(this.cmd.place ? (hole ? 'Click on the face where another hole goes (click again for more). Enter = OK.' : 'Click on a flat face where it goes. Enter = OK.') : '');
    this.renderProps();
  }

  /** Esc in a tool: one that places things click after click and has placed some (new ones, or changed what an
   *  edited step had) ends there and KEEPS them — as OK, saying so; nothing placed (or another tool): cancelled.
   *  Cancel (the button) always throws it all away. Picking a hole's reference: Esc ends only that pick. */
  escCommand() {
    if (!this.cmd) return;
    if (this.holePick) { this.holePick = null; this.hint(''); this.renderProps(); return; }
    const f = this.cmd.feature, now = this.placed(f);
    if (now === null || now === '[]' || now === this.cmd.placed0) { this.cancelCommand(); return; }
    const n = JSON.parse(now).length;
    const what = { hole: 'Hole: {n} position(s) kept (Ctrl+Z takes them back).', fillet: 'Fillet: {n} edge(s) kept (Ctrl+Z takes them back).',
      chamfer: 'Chamfer: {n} edge(s) kept (Ctrl+Z takes them back).', shell: 'Shell: {n} open face(s) kept (Ctrl+Z takes them back).' }[f.type];
    this.okCommand();
    if (!this.cmd) this.hooks.toast(t2(what, { n }), 'ok', 3500); // (OK refused — a missing setting: the tool stays open)
  }

  /** What a right-click in the view does now (actiondock.js): in a sketch it ends the drawing tool ({ word, run }) or
   *  nothing (false) — the sketch is finished only by ✓ Finish sketch / Enter; elsewhere undefined (the OK button). */
  rclickAction() {
    if (!this.active || this.mode !== 'sketch' || !this.sk) return undefined;
    return this.ctx ? false : this.sk.rclick() || false;
  }

  /** What Esc does now (the hint at the cursor says it): 'cancel', 'keep' (it ends a tool that keeps what is placed)
   *  or null (something smaller, e.g. it ends a sketch tool or a hole's reference pick). */
  escMeaning() {
    if (!this.active || this.ctx) return null;
    if (this.mode === 'plane') return 'cancel';
    if (this.mode !== 'part' || !this.cmd || this.holePick) return null;
    const now = this.placed(this.cmd.feature);
    return now === null || now === '[]' || now === this.cmd.placed0 ? 'cancel' : 'keep';
  }

  cancelCommand() {
    this.closeDimEdit();
    this.cmd = null; // (⬆ Extrude this face: its outline sketch goes with it — it was never a step)
    this.view.setPullArrow(null);
    this.holePick = null;
    this.splitMid = false;
    this.view.setSketch(null);
    this.view.setEdgeHighlight();
    this.view.setHover(-1);
    this.hint('');
    this.selected = null;
    this.render();
    this.rebuild();
  }


  // ------------------------------------------------------------------ Fillet / Chamfer / Hole
  startRound(type) {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const f = { id: this.newId(), type, name: this.nextName(type), edges: [] };
    if (type === 'fillet') f.r = 1;
    else f.d = 1;
    this.openCommand(f, true);
  }

  startHole() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    this.openCommand({ id: this.newId(), type: 'hole', name: this.nextName('hole'), plane: null, points: [], d: 5, through: true, depth: 10 }, true);
  }

  openCommand(feature, isNew) {
    this.closeCtx();
    this.view.setSelectedFaces(null);
    this.dimStep = null;
    this.closeDimEdit();
    this.view.setTags([]);
    if (this.measuring) this.toggleMeasure();
    // place: a click in the view places (a new hole / text); an edited one only after ＋ Add position / ⌖ Move by
    // clicking — opening a step to change it never arms its placing (the mouse shows no new hole)
    this.cmd = { feature, isNew, placed0: isNew ? '[]' : this.placed(feature), place: isNew || !PLACES.has(feature.type) }; // (Esc keeps what is placed past this)
    this.mode = 'part';
    this.selected = feature.id;
    this.hint(feature.type === 'revolve' ? 'Revolve — choose the axis and the angle; the preview is in the view. Enter = OK, Esc = Cancel.'
      : feature.type === 'shell' ? 'Shell — click the face(s) to leave open, give the wall thickness. Enter / Esc = done (keeps them), Cancel = throw away.'
      : feature.type === 'decal' ? 'Text / picture — click on a flat face where it goes (click again to move it). Enter = OK, Esc = Cancel.'
      : feature.type === 'loft' ? 'Loft — choose the sketch it starts from and the one it goes to. Enter = OK, Esc = Cancel.'
      : feature.type === 'sweep' ? 'Sweep — choose the outline (profile) and the path it moves along. Enter = OK, Esc = Cancel.'
      : feature.type === 'solid' ? 'Solid from a file — joined to the part, cut out of it, or a see-through reference. Enter = OK, Esc = Cancel.'
      : feature.type === 'mirror' ? 'Mirror — choose the plane, or click a flat face to mirror across it. Enter = OK, Esc = Cancel.'
      : feature.type === 'split' ? 'Split — choose a plane, or click a flat face to cut along it; keep both pieces or one side. Enter = OK, Esc = Cancel.'
      : feature.type === 'pattern' ? 'Pattern — how many and how far apart. Click an edge for the direction (or a round face for the axis). Enter = OK, Esc = Cancel.'
      : feature.type === 'hole' && !isNew ? 'Hole — change its settings; ＋ Add position to click more holes. Enter = OK, Esc = Cancel.'
      : feature.type === 'decal' && !isNew ? 'Text / picture — change it; ⌖ Move by clicking to put it elsewhere. Enter = OK, Esc = Cancel.'
      : feature.type === 'hole' ? 'Hole — click on a flat face where it goes (click again for more holes). Enter / Esc = done (keeps them), Cancel = throw away.'
      : `${feature.type === 'fillet' ? 'Fillet' : 'Chamfer'} — click the edges (or a face: all its edges). Enter / Esc = done (keeps them), Cancel = throw away.`);
    this.render();
    this.rebuild();
  }

  /** An edge of the shown body -> a reference {a, b, fp}: the names of its two faces and its middle. */
  edgeRef(i) {
    const b = this.result?.body, e = b?.edges[i];
    if (!e || e.faces.length !== 2) return null;
    const [fa, fb] = e.faces.map((k) => b.faces[k]?.name);
    if (!fa || !fb) return null;
    const own = this.cmd && `${this.cmd.feature.id}:`;
    if (own && (fa.startsWith(own) || fb.startsWith(own))) return null; // made by this very step
    return { a: fa, b: fb, fp: e.mid };
  }

  /** ⛓ The edges a click on edge i picks: its tangent chain (the edges that go on smoothly from it — a fillet rounds
   *  them all anyway) while the panel's "Whole chain" is on, else the edge alone. */
  chainOf(i, f = this.cmd?.feature) {
    const b = this.result?.body, k = b?.edges[i]?.chain;
    if (k === undefined || f?.chain === false) return [i];
    const out = [];
    b.edges.forEach((e, j) => { if (e.chain === k && this.edgeRef(j)) out.push(j); });
    return out.length ? out : [i];
  }

  /** The edges of the shown body that the command's references point at (for the blue highlight). */
  refEdges(refs) {
    const b = this.result?.body;
    if (!b) return [];
    const out = [];
    for (const r of refs) {
      let best = -1, bd = Infinity;
      b.edges.forEach((e, i) => {
        if (e.faces.length !== 2) return;
        const ns = e.faces.map((k) => b.faces[k]?.name);
        if (!((ns[0] === r.a && ns[1] === r.b) || (ns[0] === r.b && ns[1] === r.a))) return;
        const d = Math.hypot(e.mid[0] - r.fp[0], e.mid[1] - r.fp[1], e.mid[2] - r.fp[2]);
        if (d < bd) { bd = d; best = i; }
      });
      if (best >= 0) out.push(best);
    }
    return out;
  }

  sameRef(a, b) { return ((a.a === b.a && a.b === b.b) || (a.a === b.b && a.b === b.a)) && Math.hypot(a.fp[0] - b.fp[0], a.fp[1] - b.fp[1], a.fp[2] - b.fp[2]) < 1e-6 * (1 + this.view.size); }

  clickCommand(e) {
    const f = this.cmd.feature;
    if (f.type === 'extrude') return this.clickUpTo(e);
    if (f.type === 'hole') return this.clickHole(e);
    if (f.type === 'shell') return this.clickShell(e);
    if (f.type === 'pattern') return this.clickPattern(e);
    if (f.type === 'decal') return this.clickDecal(e);
    if (f.type === 'mirror') return this.clickMirror(e);
    if (f.type === 'draft') return this.clickDraft(e);
    if (f.type === 'split') return this.clickSplit(e);
    if (f.type === 'revolve') return null;
    const i = this.view.pickEdge(e.clientX, e.clientY, ROUND_PICK_PX); // (a click just beside an edge: that edge, not the whole face)
    if (i >= 0) {
      const ref = this.edgeRef(i);
      if (!ref) return null;
      const k = f.edges.findIndex((r) => this.sameRef(r, ref)), run = this.chainOf(i);
      if (run.length > 1) { // ⛓ the whole chain: picked again -> all of it dropped
        const refs = run.map((j) => this.edgeRef(j));
        if (k >= 0) f.edges = f.edges.filter((r) => !refs.some((x) => this.sameRef(r, x)));
        else for (const x of refs) if (!f.edges.some((r) => this.sameRef(r, x))) f.edges.push(x);
        this.cmd.lastPick = `${k >= 0 ? 'Dropped' : 'Added'} a chain of ${run.length} edges.`;
      } else {
        if (k >= 0) f.edges.splice(k, 1);
        else f.edges.push(ref);
        // what the click did, in words (the panel says it): the edge's two faces
        this.cmd.lastPick = `${k >= 0 ? 'Dropped' : 'Added'} the edge between ${this.faceLabel(ref.a)} and ${this.faceLabel(ref.b)}.`;
      }
    } else {
      // a face: all of its edges (that are not picked yet)
      const h = this.view.pick(e.clientX, e.clientY);
      if (!h?.face) return null;
      let n = 0;
      this.result.body.edges.forEach((ed, j) => {
        if (!ed.faces.includes(h.face.id)) return;
        const ref = this.edgeRef(j);
        if (ref && !f.edges.some((r) => this.sameRef(r, ref))) { f.edges.push(ref); n++; }
      });
      const what = this.faceLabel(h.face.name);
      this.cmd.lastPick = n ? `Added ${n} edge(s) of ${what}.` : `All edges of ${what} are picked already.`;
    }
    this.renderProps();
    this.rebuild()?.then?.(() => { if (this.cmd?.feature === f) this.renderProps(); }); // (its result shown when built, not the last one's)
    return null;
  }

  /** Extrude, up to a face: the clicked flat face (not one this extrude makes). */
  clickUpTo(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (!f.upto) return;
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) { this.hooks.toast('Click a flat face of the part.', 'info', 3000); return; }
    f.upto = { name: h.face.name, fp: h.face.centroid };
    this.renderProps();
    this.rebuild();
  }

  /** "the top of Extrude 1" for a face name. */
  faceLabel(name) {
    const [id, role, sub] = String(name).split(':'), g = this.part.features.find((x) => x.id === id);
    const what = { end: 'the top of', start: 'the bottom of', side: 'a wall of', hole: 'a hole of', round: 'a rounding of', cut: 'the cut face of' }[role] || 'a face of';
    return g ? `${what} ${g.name}` : name;
  }

  /** A click while the Hole tool is open (h: what is under it — given when it was picked earlier: sameHoleOn). An
   *  edited hole (placing off) on its own face: ＋ Add a hole here offered (the suggestions' first row, the toast's
   *  button); another flat face: one step's holes are on one face — ＋ Same hole on this face offered. */
  clickHole(e, h = this.view.pick(e.clientX, e.clientY)) {
    const f = this.cmd.feature;
    if (this.holePick) { this.pickHoleRef(e); return; }
    if (this.dimEdit) { this.closeDimEdit(); return; } // (a size being typed: the click ends that, it keeps what is shown)
    if (!h?.face) return;
    if (h.face.type !== 'plane') { this.hooks.toast('Holes go on flat faces — click a flat face.', 'warning'); return; }
    if (f.plane && (f.plane.face?.name !== h.face.name || h.face.normal.some((v, k) => Math.abs(v - f.plane.frame.n[k]) > 1e-6))) {
      if (!h.face.name?.startsWith(`${f.id}:`)) this.offerSameHole(e, h);
      return;
    }
    if (!f.plane) f.plane = { face: h.face.ref || null, frame: h.face.frame };
    // snapped (facesnap.js): a corner, an edge's middle, a centre, another hole, in line with one of them …, else a 0.5 mm grid
    const at = this.faceSpot(e, f, h);
    if (!at) return;
    if (!this.cmd.place) { this.offerHoleHere(e, h); return; } // (an edited hole: a click alone adds none — offered, one click)
    const [u, v] = at.s.uv;
    f.points.push([u, v]);
    // placed from the nearest edges of the face (left / right and below / above): it keeps that distance
    // when the part changes (a step measured from a corner / the part's origin: from that); in line with another
    // hole: from that hole's centre; on the face's centre or a middle line (in line with edge midpoints): midway
    // between the two edges
    f.from = f.from || [];
    const i = f.points.length - 1;
    if (!f.plane.origin) f.from[i] = this.nearestEdges(f, [u, v]);
    this.holeKeyRefs(f, i, at.s);
    this.spotKey = null;
    this.renderProps();
    this.rebuild();
  }

  /** An edited hole's face clicked with placing off (opening a step never arms it): ＋ Add a hole here — that spot
   *  placed and ＋ Add position on (more clicks add more) — the suggestions' first row and the toast's button. */
  offerHoleHere(e, h) {
    const f = this.cmd.feature, spot = { clientX: e.clientX, clientY: e.clientY, shiftKey: e.shiftKey, altKey: e.altKey }, label = t('Add a hole here');
    const run = () => {
      this.dropSuggest();
      if (this.cmd?.feature !== f) return;
      if (!this.cmd.place) this.armPlace();
      this.clickHole(spot, h);
    };
    const sg = showSuggest(this.els.viewport, `${f.name} · ${t('its face')}`, [
      { id: 'holeHere', icon: '＋', label, rank: 0, title: t('A hole of this step where you clicked — then each click adds one more (＋ Add position stops it)'), run },
      { id: 'addPos', icon: '＋', label: t('Add position'), rank: 1, title: t('Then click on the face where another hole goes (click again for more); click this again to stop'), run: () => { this.dropSuggest(); if (this.cmd && !this.cmd.place) this.armPlace(); } }]);
    if (sg) sg.dataset.from = 'face';
    this.hooks.toast(t('A hole here? ＋ Add a hole here — or ＋ Add position, then click for more.'), 'info', 5000, { point: { suggest: 'holeHere' }, action: { label: `＋ ${label}`, run } });
  }

  /** Another flat face clicked while a Hole step is open: the step's holes stay on their face — ＋ Same hole on this
   *  face (the suggestions' first row, the toast's button) ends this step (OK) and starts a new one there. */
  offerSameHole(e, h) {
    const f = this.cmd.feature, spot = { e: { clientX: e.clientX, clientY: e.clientY, shiftKey: e.shiftKey, altKey: e.altKey }, h };
    const run = () => this.sameHoleOn(spot), label = t('Same hole on this face');
    const sg = showSuggest(this.els.viewport, `${f.name} · ${t('another face')}`, [
      { id: 'sameHole', icon: '＋', label, rank: 0, title: t('This hole is done (OK) — a new Hole step on the face you clicked, of the same type, size and thread, where you clicked'), run },
      { id: 'okHole', icon: '✓', label: t('OK — the hole is done'), rank: 1, title: t('The holes of one step are on one face: this step ends here'), run: () => { this.dropSuggest(); this.okCommand(); } }]);
    if (sg) sg.dataset.from = 'face';
    this.hooks.toast(t('The holes of one step are on one face — this face gets a Hole step of its own.'), 'info', 7000, { point: { suggest: 'sameHole' }, action: { label: `＋ ${label}`, run } });
  }

  /** ＋ Same hole on this face: the open Hole step done (OK), a new one on the face of `spot` ({e, h}: the click and what
   *  it picked) with the same type, size, thread, depth — its first hole where the click was. */
  sameHoleOn({ e, h }) {
    if (this.cmd?.feature.type !== 'hole') return;
    const same = structuredClone(this.cmd.feature);
    for (const k of ['id', 'name', 'plane', 'points', 'from', 'lock', 'suppressed']) delete same[k]; // (its place: not the size)
    this.dropSuggest();
    this.okCommand();
    if (this.cmd) return; // (OK refused: the step stays open)
    const f = { ...same, id: this.newId(), name: this.nextName('hole'), plane: null, points: [] };
    this.openCommand(f, true);
    this.clickHole(e, h);
    if (f.points.length) this.hooks.toast(t2('{name}: the same hole on this face — click for more, Enter = OK.', { name: f.name }), 'ok', 4000);
  }

  /** Hole i placed (or dragged — holedrag.js) onto snap s: what a coordinate came from becomes what it is measured
   *  from — the face's centre / a middle line: kept in the middle; another hole of this step: from it; a round edge:
   *  from its centre. axes: only those ('x', 'y'). */
  holeKeyRefs(f, i, s, axes = ['x', 'y']) {
    const [u, v] = f.points[i];
    f.from = f.from || [];
    for (const [axis, k] of [['x', 0], ['y', 1]]) {
      if (!axes.includes(axis)) continue;
      const key = s.keys?.[axis];
      const mid = (key?.kind === 'face' || key?.kind === 'midpoint') && this.midEdges(f, [u, v], k);
      if (mid) f.from[i] = { ...(f.from[i] || {}), [axis]: mid }; // (the face's centre, the middle line: kept in the middle)
      else if (key?.hole !== undefined) f.from[i] = { ...(f.from[i] || {}), [axis]: { hole: key.hole, d: 0, round: true } };
      else if (key?.round) {
        const c = this.axisEdges(f, k, true).find((r) => r.round && Math.hypot(...r.ref.fp.map((w, j) => w - key.round.fp[j])) < 1e-6);
        if (c) f.from[i] = { ...(f.from[i] || {}), [axis]: { edge: c.ref, d: +([u, v][k] - c.c).toFixed(6), round: true } };
      }
    }
  }

  /** The spot on a flat face under the mouse, snapped (facesnap.js) — for f a hole (on its face only) or a text /
   *  picture: {h, fr, s} (s: facesnap's snap, in fr's coordinates), or null. Shift / Alt: not snapped. */
  faceSpot(e, f, h = this.view.pick(e.clientX, e.clientY)) {
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) return null;
    let fr = h.face.frame;
    if (f.type === 'hole' && f.plane) {
      if (f.plane.face?.name !== h.face.name || h.face.normal.some((w, k) => Math.abs(w - f.plane.frame.n[k]) > 1e-6)) return null;
      fr = this.holeFrame(f);
    } else if (f.plane?.frame && f.plane.face?.name === h.face.name) fr = f.plane.frame;
    const extra = f.type === 'hole' && f.plane ? f.points.map((p, j) => ({ uv: p, kind: 'hole', hole: j })) : [];
    const s = snapOnFace(this.view, { face: h.face, fr, uv: toFace(fr, h.point), mpp: this.view.mmPerPixel(fr), skip: `${f.id}:`, extra, free: !!(e.shiftKey || e.altKey) });
    return { h, fr, s };
  }

  /** The hole's face as it is now (the rebuild follows it when it moves), else where it was clicked. */
  holeFrame(f) { const fr = this.result?.frames?.[f.id]; return fr && sameOrigin(fr, f.plane) ? fr : f.plane?.frame || null; }

  /** The holes' From (⇤ each from its nearest edges, ⌜ all from the face's corner, ⊕ from the part's origin): they
   *  keep their place, their numbers are from the new reference. */
  setHoleOrigin(how) {
    const f = this.cmd.feature, r = moveOrigin(this, f.plane, this.holeFrame(f), how === 'edges' ? 'centre' : how);
    if (!r) { this.hooks.toast('The face is not in the view — the holes stay measured as they are.', 'warning'); return; }
    f.points = shiftPoints(f.points, r.du, r.dv);
    f.plane = r.plane;
    f.from = how === 'edges' ? f.points.map((p) => this.nearestEdges(f, p)) : [];
    this.renderProps();
    this.rebuild();
  }

  /** The straight edges of the part in the hole's face plane, in its coordinates: [{a: [u, v], b, ref: {a, b, fp}}]. */
  planeEdges(f) {
    const b = this.result?.body, fr = this.holeFrame(f);
    if (!b || !fr) return [];
    const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
    const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
    const tol = Math.max(this.view.size * 1e-5, 1e-4), out = [];
    for (const e of b.edges) {
      if (e.pts.length !== 6 || e.faces.length !== 2) continue;
      const names = e.faces.map((k) => b.faces[k]?.name);
      if (names.some((nm) => !nm || nm.startsWith(`${f.id}:`))) continue; // the holes of this very step
      const P = [e.pts.slice(0, 3), e.pts.slice(3)].map((p) => [p[0] - o[0], p[1] - o[1], p[2] - o[2]]);
      if (P.some((d) => Math.abs(dot(d, n)) > tol)) continue;
      out.push({ a: [dot(P[0], x), dot(P[0], y)], b: [dot(P[1], x), dot(P[1], y)], ref: { a: names[0], b: names[1], fp: e.mid } });
    }
    return out;
  }

  /** Edges running across an axis (k = 0: along y, so they give an x; k = 1: along x) -> [{c: their x (or y), ref}].
   *  round: also the round edges of the face (other holes) — their centre. */
  axisEdges(f, k, round = false) {
    const j = 1 - k;
    const straight = this.planeEdges(f).filter((e) => Math.abs(e.a[k] - e.b[k]) < 1e-6 && Math.abs(e.a[j] - e.b[j]) > 1e-6)
      .map((e) => ({ c: (e.a[k] + e.b[k]) / 2, lo: Math.min(e.a[j], e.b[j]), hi: Math.max(e.a[j], e.b[j]), ref: e.ref }));
    return round ? [...straight, ...this.roundEdges(f).map((e) => ({ c: e.c[k], lo: -Infinity, hi: Infinity, ref: e.ref, round: true }))] : straight;
  }

  /** Round edges (circles, arcs) lying in the hole's face, with their centre in its coordinates. */
  roundEdges(f) {
    const b = this.result?.body, fr = this.holeFrame(f);
    if (!b || !fr) return [];
    const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
    const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
    const tol = Math.max(this.view.size * 1e-5, 1e-4), out = [];
    for (const e of b.edges) {
      if (e.pts.length < 15 || e.faces.length !== 2) continue;
      const names = e.faces.map((k) => b.faces[k]?.name);
      if (names.some((nm) => !nm || nm.startsWith(`${f.id}:`))) continue;
      const P = [];
      for (let i = 0; i < e.pts.length; i += 3) P.push([e.pts[i] - o[0], e.pts[i + 1] - o[1], e.pts[i + 2] - o[2]]);
      if (P.some((d) => Math.abs(dot(d, n)) > tol)) continue;
      const uv = P.map((d) => [dot(d, x), dot(d, y)]);
      // the centre: of the circle through three of its points
      const [a, m, c] = [uv[0], uv[Math.floor(uv.length / 3)], uv[Math.floor((2 * uv.length) / 3)]];
      const D = 2 * (a[0] * (m[1] - c[1]) + m[0] * (c[1] - a[1]) + c[0] * (a[1] - m[1]));
      if (Math.abs(D) < 1e-9) continue;
      const q = (p) => p[0] * p[0] + p[1] * p[1];
      const cc = [(q(a) * (m[1] - c[1]) + q(m) * (c[1] - a[1]) + q(c) * (a[1] - m[1])) / D, (q(a) * (c[0] - m[0]) + q(m) * (a[0] - c[0]) + q(c) * (m[0] - a[0])) / D];
      const r = Math.hypot(a[0] - cc[0], a[1] - cc[1]);
      if (uv.some((p) => Math.abs(Math.hypot(p[0] - cc[0], p[1] - cc[1]) - r) > r * 0.01 + 1e-6)) continue; // not round
      out.push({ c: cc, r, ref: { a: names[0], b: names[1], fp: e.mid } });
    }
    return out;
  }

  /** 🎯 the edge under the mouse as a hole reference for the axis being picked -> {edge, c, round}, or null. */
  holeRefAt(i) {
    const f = this.cmd.feature, { axis, i: me } = this.holePick, k = axis === 'x' ? 0 : 1, e = this.result?.body?.edges[i];
    if (!e) return null;
    // another hole of this very step: by its number (it is placed first, this one from it)
    const own = e.faces.map((q) => this.result.body.faces[q]?.name || '').map((nm) => nm.match(new RegExp(`^${f.id}:hole:(\\d+)$`))).find(Boolean);
    if (own) return +own[1] === me ? null : { c: f.points[+own[1]][k], ref: { hole: +own[1] }, round: true };
    return this.axisEdges(f, k, true).find((x) => Math.hypot(...x.ref.fp.map((v, j) => v - e.mid[j])) < 1e-6) || null;
  }

  /** 🎯 a round face under the mouse (a shaft, a cross hole — or an edge of one) as a hole reference: its axis, when
   *  it is square to the face or runs straight across the axis being picked -> {c, ref: {axis}, face}, or null. */
  holeAxisAt(clientX, clientY, edge = -1) {
    const f = this.cmd.feature, k = this.holePick.axis === 'x' ? 0 : 1, b = this.result?.body;
    if (!b) return null;
    const ids = [...(edge >= 0 ? b.edges[edge]?.faces || [] : []), this.view.pick(clientX, clientY)?.face?.id].filter((x) => x !== undefined);
    const axes = roundAxes(b, this.holeFrame(f), (nm) => nm.startsWith(`${f.id}:`));
    const q = axes.find((a) => ids.includes(a.face) || ids.some((x) => b.faces[x]?.name === a.ref.face));
    return q && (!q.dir || Math.abs(q.dir[k]) < 1e-6) ? { c: q.c[k], ref: { axis: q.ref }, face: q.face } : null;
  }

  pickHoleRef(e) {
    const f = this.cmd.feature, { i, axis } = this.holePick, k = axis === 'x' ? 0 : 1;
    const idx = this.view.pickEdge(e.clientX, e.clientY), r = (idx >= 0 && this.holeRefAt(idx)) || this.holeAxisAt(e.clientX, e.clientY, idx);
    if (!r) { this.hooks.toast(axis === 'x' ? 'Click a straight edge running up / down on this face, another hole, or a round face (its axis).' : 'Click a straight edge running left / right on this face, another hole, or a round face (its axis).', 'info', 4000); return; }
    f.from = f.from || [];
    f.from[i] = { ...(f.from[i] || {}), [axis]: { ...(r.ref.hole !== undefined ? { hole: r.ref.hole } : r.ref.axis ? { axis: r.ref.axis } : { edge: r.ref }), d: +(f.points[i][k] - r.c).toFixed(6), ...(r.round ? { round: true } : {}) } };
    this.holePick = null;
    this.view.setEdgeHighlight();
    this.hint('Hole — click on a flat face where it goes (click again for more holes). Enter = OK, Esc = Cancel.');
    this.renderProps();
    this.drawHoleDims();
  }

  /** The nearest edge on each axis for a hole at p (an edge beside it is preferred over one beyond its ends). */
  nearestEdges(f, p, side = 0) {
    const out = {};
    for (const [axis, k] of [['x', 0], ['y', 1]]) {
      const es = this.axisEdges(f, k).filter((e) => !side || Math.sign(p[k] - e.c) === side || Math.abs(p[k] - e.c) < 1e-9);
      const score = (e) => Math.abs(p[k] - e.c) + (p[1 - k] < e.lo - 1e-6 || p[1 - k] > e.hi + 1e-6 ? 1e6 : 0);
      const best = es.sort((a, b) => score(a) - score(b))[0];
      if (best) out[axis] = { edge: best.ref, d: +(p[k] - best.c).toFixed(6) };
    }
    return out;
  }

  /** A hole at p midway between the nearest edges on either side along axis k -> its from {mid: [edge, edge], d: 0}
   *  (it stays in the middle when the part changes), else null. */
  midEdges(f, p, k) {
    const es = this.axisEdges(f, k).filter((e) => p[1 - k] >= e.lo - 1e-6 && p[1 - k] <= e.hi + 1e-6);
    const lo = es.filter((e) => e.c < p[k] - 1e-6).sort((a, b) => b.c - a.c)[0], hi = es.filter((e) => e.c > p[k] + 1e-6).sort((a, b) => a.c - b.c)[0];
    return lo && hi && Math.abs((lo.c + hi.c) / 2 - p[k]) < 1e-6 ? { mid: [lo.ref, hi.ref], d: 0 } : null;
  }

  /** Where a hole's reference is now along axis k: another hole of this step, an edge, or midway between two edges. */
  refCoord(f, r, k) {
    if (r.mid) { const [a, b] = r.mid.map((e) => this.edgeCoord(f, e, k)); return a === null || b === null ? null : (a + b) / 2; }
    if (r.axis) return axisOf(roundAxes(this.result?.body, this.holeFrame(f)), r.axis)?.c[k] ?? null; // (a round face's axis)
    return r.hole !== undefined ? f.points[r.hole]?.[k] ?? null : this.edgeCoord(f, r.edge, k);
  }

  /** Where a hole's reference edge is now (its x or y in the face), or null. */
  edgeCoord(f, ref, k) {
    let best = null, bd = Infinity;
    for (const e of this.axisEdges(f, k, true)) {
      const same = (e.ref.a === ref.a && e.ref.b === ref.b) || (e.ref.a === ref.b && e.ref.b === ref.a);
      const d = Math.hypot(...e.ref.fp.map((v, i) => v - ref.fp[i])) + (same ? 0 : 1e6);
      if (d < bd) { bd = d; best = e; }
    }
    return best && bd < 1e6 ? best.c : best?.c ?? null;
  }

  /** The hole's distances to its edges, drawn on the face: a dimension line from the edge to the centre. at: the spot
   *  under the mouse (faceSpot) — the hole there, its distances to the nearest edges, the guides it is snapped by. */
  drawHoleDims(at = null) {
    const f = this.cmd?.feature;
    if (!f || f.type !== 'hole' || (!f.plane?.frame && !at)) { this.view.setSketch(null); return; }
    const g = f.plane ? f : { ...f, plane: { face: at.h.face.ref || null, frame: at.h.face.frame } }; // (the first hole: on the face under the mouse)
    const fr = this.holeFrame(g), lines = [], labels = [], circles = [], dots = [], C = 0xd2a8ff, mpp = this.view.mmPerPixel(fr);
    // a placed hole's number: click it to type it (number + slider, as a chosen step's sizes; OK of the tool keeps it) —
    // not while placing (the labels would stand in the way of the mouse there: the panel's fields take the numbers)
    const editable = (el, edit, title) => {
      if (this.cmd.place) return;
      el.classList.add('edit');
      el.title = t(title);
      for (const ev of ['pointerdown', 'pointerup']) el.addEventListener(ev, (x) => x.stopPropagation());
      el.addEventListener('click', (x) => { x.stopPropagation(); this.openDimEdit(el, { tool: true, min: 0, ...edit }); });
    };
    if (at) {
      const p = at.s.uv, near = this.nearestEdges(g, p), draw = snapDrawing(at.s, mpp);
      circles.push([p, (f.d || 5) / 2, 0x7ee787]);
      for (const [axis, k] of [['x', 0], ['y', 1]]) {
        const r = near[axis];
        if (!r) continue;
        const a = k === 0 ? [p[0] - r.d, p[1]] : [p[0], p[1] - r.d];
        lines.push([a, p, C]); // (purple like the placed ones: the dashed green guides stay apart)
        const el = document.createElement('div');
        el.className = 'sk-label hole-dim live';
        el.textContent = fmt(Math.abs(r.d));
        labels.push({ el, u: (a[0] + p[0]) / 2 + (k === 1 ? mpp * 12 : 0), v: (a[1] + p[1]) / 2 + (k === 0 ? mpp * 10 : 0) });
      }
      lines.push(...draw.lines); dots.push(...draw.dots); circles.push(...draw.circles); labels.push(...draw.labels);
    }
    f.points.forEach((p, i) => {
      for (const [axis, k] of [['x', 0], ['y', 1]]) {
        const r = f.from?.[i]?.[axis];
        if (!r) continue;
        const cs = r.mid ? r.mid.map((e) => this.edgeCoord(f, e, k)) : [this.refCoord(f, r, k)]; // (midway: from both edges)
        cs.forEach((c, j) => {
          if (c === null) return;
          const a = k === 0 ? [c, p[1]] : [p[0], c];
          lines.push([a, p, C]);
          const el = document.createElement('div');
          el.className = `sk-label hole-dim${holeLocked(f, i, axis) ? ' locked' : ''}`; // (🔒 before it: CSS)
          el.textContent = fmt(r.mid ? Math.abs(p[k] - c) : Math.abs(r.d));
          editable(el, { label: 'Distance', get: () => (r.mid ? Math.abs(p[k] - c) : Math.abs(r.d)), set: (v) => this.setHoleDist(f, i, axis, v, r.mid ? r.mid[j] : null) },
            'Click to type the distance (from this edge)');
          labels.push({ el, u: (a[0] + p[0]) / 2 + (k === 1 ? mpp * 12 : 0), v: (a[1] + p[1]) / 2 + (k === 0 ? mpp * 10 : 0) });
        });
      }
    });
    if (f.points.length && f.plane?.frame) { // its Ø (and depth): typed on the part too
      const [u, v] = f.points[0], r = (f.d || 5) / 2, sp = holeSpec(f);
      const el = document.createElement('div');
      el.className = 'sk-label hole-dim hole-size';
      el.textContent = `Ø${fmt(f.d)}`;
      if (!sp.threaded) {
        editable(el, { label: 'Diameter', min: 0.2, get: () => f.d, set: (x) => { if (!(x > 0)) return; if (sp.shape === 'd_flat' && (f.flat === undefined || f.flat === dFlat(f.d))) f.flat = dFlat(x); f.d = x; } },
          'Click to type the hole’s diameter');
      }
      labels.push({ el, u: u + r * 0.75 + mpp * 18, v: v + r * 0.75 + mpp * 10 });
      if (f.through === false) {
        const de = document.createElement('div');
        de.className = 'sk-label hole-dim hole-size';
        de.textContent = `↓ ${fmt(f.depth)}`;
        editable(de, { label: 'Depth', min: 0.1, get: () => f.depth, set: (x) => { if (x > 0) f.depth = x; } }, 'Click to type how deep it goes');
        labels.push({ el: de, u: u + r * 0.75 + mpp * 18, v: v + r * 0.75 - mpp * 12 });
      }
    }
    this.view.setSketch(fr, { lines, circles, dots, labels, grid: 0 });
  }

  /** A hole's distance along axis typed (≥ 0; it stays on its side of what it is measured from): the hole moves, the
   *  distance is locked 🔒 (dragging the hole keeps it). edge: a hole kept in the middle typed from one of its two
   *  edges — from now on measured from that edge. */
  setHoleDist(f, i, axis, v, edge = null) {
    const k = axis === 'x' ? 0 : 1, r = f.from?.[i]?.[axis], p = f.points[i];
    if (!r || !(v >= 0)) return;
    setHoleLock(f, i, axis, true);
    if (r.mid) {
      const c = this.edgeCoord(f, edge || r.mid[0], k);
      if (c === null) return;
      const sgn = Math.sign(p[k] - c) || 1;
      f.from[i][axis] = { edge: edge || r.mid[0], d: +(sgn * v).toFixed(6) };
      p[k] = +(c + sgn * v).toFixed(6);
      return;
    }
    const c = this.refCoord(f, r, k);
    if (c === null || c === undefined || c === false) return;
    r.d = (Math.sign(r.d) || 1) * v;
    p[k] = +(c + r.d).toFixed(6);
  }

  /** The spot under the mouse while a hole / text / picture is being placed: snapped, the guides and (a hole) its
   *  preview drawn — redrawn only when it changes. */
  showSpot(e) {
    const f = this.cmd?.feature, at = e && f ? this.faceSpot(e, f) : null;
    this.spot = at;
    const key = at ? JSON.stringify([at.h.face.id, at.s.uv, at.s.kind, at.s.guides]) : '';
    this.view.setHover(at ? at.h.face.id : -1);
    if (key === this.spotKey) return at;
    this.spotKey = key;
    if (f?.type === 'hole') this.drawHoleDims(at);
    else if (at) this.view.setSketch(at.fr, { ...snapDrawing(at.s, this.view.mmPerPixel(at.fr)), grid: 0 });
    else this.view.setSketch(null);
    return at;
  }

  /** After a rebuild moved holes (their edges moved), show the new numbers without retyping. */
  syncHoleInputs() {
    const f = this.cmd.feature, box = this.$('.mp-body');
    for (const el of box.querySelectorAll('[data-u]')) if (document.activeElement !== el) el.value = fmt(f.points[+el.dataset.u][0]);
    for (const el of box.querySelectorAll('[data-v]')) if (document.activeElement !== el) el.value = fmt(f.points[+el.dataset.v][1]);
  }

  /** One row of a hole's position: "↔ 12 mm from the left edge ⇄", or x / y from the face's centre (no edge there);
   *  its 🔒: a locked distance stays when the hole is dragged on the part (typed: locked). */
  holeDimRow(f, i, axis, k) {
    const r = f.from?.[i]?.[axis], p = f.points[i], on = holeLocked(f, i, axis);
    const lock = `<button type="button" class="mini mp-lock ${on ? 'on' : ''}" data-lockhd="${i}:${axis}" title="${esc(t(on ? 'Locked: dragging the hole on the part keeps this distance — click to free it' : 'Free: drag the hole on the part to change it — click to lock it'))}">${on ? '🔒' : '🔓'}</button>`;
    if (r?.mid && !r.d) { // midway between two edges: its distance from the left / lower one — typed, it is measured from that edge
      const c = this.edgeCoord(f, r.mid[0], k), dist = c === null ? '' : fmt(Math.abs(p[k] - c));
      return `<label class="mp-hd">${k ? '↕' : '↔'} <input type="number" step="any" min="0" data-hd="${i}:${axis}" value="${dist}" title="${esc(t(k ? 'Type a distance: it is then measured from the lower edge' : 'Type a distance: it is then measured from the left edge'))}"> <span>mm <span>${esc(t(k ? 'in the middle of the lower and upper edges' : 'in the middle of the left and right edges'))}</span></span>
        <button type="button" class="mini ${this.holePick?.i === i && this.holePick?.axis === axis ? 'on' : ''}" data-pickref="${i}:${axis}" title="Measure from another edge, hole or round face (its axis): click it in the view">🎯</button>${lock}</label>`;
    }
    if (!r) return `<label class="mp-hd">${axis} <input type="number" step="any" data-${k ? 'v' : 'u'}="${i}" value="${fmt(p[k])}"> <span class="hint">${FROM_TEXT[originKey(f.plane?.origin)] || 'from the reference point'}</span>${lock}</label>`;
    const side = r.mid ? (k === 0 ? (r.d >= 0 ? 'right of the middle' : 'left of the middle') : (r.d >= 0 ? 'above the middle' : 'below the middle'))
      : r.axis ? (k === 0 ? (r.d >= 0 ? 'right of the axis' : 'left of the axis') : (r.d >= 0 ? 'above the axis' : 'below the axis'))
      : r.round ? (k === 0 ? (r.d >= 0 ? 'right of the hole' : 'left of the hole') : (r.d >= 0 ? 'above the hole' : 'below the hole'))
      : k === 0 ? (r.d >= 0 ? 'from the left edge' : 'from the right edge') : (r.d >= 0 ? 'from the lower edge' : 'from the upper edge');
    const picking = this.holePick?.i === i && this.holePick?.axis === axis;
    return `<label class="mp-hd">${k ? '↕' : '↔'} <input type="number" step="any" min="0" data-hd="${i}:${axis}" value="${fmt(Math.abs(r.d))}"> <span>mm ${side}</span>
      ${r.mid ? '' : `<button type="button" class="mini" data-flip="${i}:${axis}" title="Measure from the edge on the other side">⇄</button>`}
      <button type="button" class="mini ${picking ? 'on' : ''}" data-pickref="${i}:${axis}" title="Measure from another edge, hole or round face (its axis): click it in the view">🎯</button>${lock}</label>`;
  }

  /** ▲ Teardrop: offered when the hole goes sideways (its axis level with the print bed, square to Z) — else greyed,
   *  the tooltip says why (still on when it was ticked, so it can be taken off). */
  teardropRow(f) {
    const fr = this.holeFrame(f), side = !!fr && Math.abs(fr.n[2]) < 1e-4, on = !!f.teardrop;
    const tip = side ? 'The top of the hole becomes a 45° point, so it prints lying on its side without support'
      : fr ? 'Only for a hole that goes sideways (its axis level with the print bed) — this one goes up / down'
        : 'Click a face on the side of the part first: a teardrop is for a hole that goes sideways';
    return `<label class="check ${side || on ? '' : 'off'}" title="${tip}"><input type="checkbox" data-k="teardrop" ${on ? 'checked' : ''} ${side || on ? '' : 'disabled'}> Teardrop (print sideways)</label>`;
  }

  renderRound(box) {
    const f = this.cmd.feature, st = this.status(f.id), fillet = f.type === 'fillet', k = fillet ? 'r' : 'd';
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <p class="hint">${fillet ? 'Click the edges to round' : 'Click the edges to bevel'} — click a face to take all of its edges, click a picked edge again to drop it.</p>
      <div class="field"><label>${fillet ? 'Radius' : 'Size'}</label><input type="number" step="any" min="0" data-k="${k}" value="${fmt(f[k])}"><span class="unit">mm</span></div>
      <label class="check" title="${esc(t('On: a click picks the edge and the edges that go on smoothly from it (tangent) — they are rounded together anyway'))}"><input type="checkbox" data-k="chain" ${f.chain !== false ? 'checked' : ''}> ⛓ Whole chain</label>
      <p class="mp-count">${f.edges.length ? `${f.edges.length} edge(s) picked` : 'No edges picked yet'}</p>
      ${this.cmd.lastPick ? `<p class="hint mp-last" title="${esc(t('What your last click in the view picked'))}">${esc(this.cmd.lastPick)}</p>` : ''}
      ${f.edges.length ? '<div class="row-actions"><button class="btn small" data-a="clear">Drop all edges</button></div>' : ''}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : st?.warnings?.length ? `<p class="mp-warn">⚠ ${esc(st.warnings.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>
      <p class="hint">The preview is in the 3D view. Enter = OK, Esc = Cancel.</p>`;
    const inp = box.querySelector(`[data-k=${k}]`);
    inp.addEventListener('input', () => { const v = parseFloat(inp.value); if (v > 0) { f[k] = v; this.rebuild(); } });
    inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    box.querySelector('[data-k=chain]').addEventListener('change', (e) => { if (e.target.checked) delete f.chain; else f.chain = false; this.rebuild(); });
    box.querySelector('[data-a=clear]')?.addEventListener('click', () => { f.edges = []; this.cmd.lastPick = null; this.renderProps(); this.rebuild(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  renderHole(box) {
    const f = this.cmd.feature, st = this.status(f.id), sp = holeSpec(f), size = sp.standard || '', dh = sp.shape === 'd_flat';
    const std = !!size && !dh; // (a screw's hole: sized from the table)
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      ${this.cmd.isNew ? '<p class="hint">Click on a flat face where a hole goes — click again for more holes on the same face. A click near the face\'s centre snaps to it.</p>' : ''}
      ${f.plane?.face ? `<div class="field m-holefrom"><label>From</label>${originSeg(f.plane, f.plane.origin ? originKey(f.plane.origin) : f.from?.some((x) => x?.x || x?.y) ? 'edges' : '', '', HOLE_ORIGINS)}</div>` : ''}
      ${this.holePropsHtml(f)}
      ${dh ? `<div class="field m-dflat"><label>Across the flat</label><input type="number" step="any" min="0" data-k="flat" value="${fmt(f.flat ?? dFlat(f.d))}" data-lo="${fmt(f.d / 2 + 0.05)}" data-hi="${fmt(f.d - 0.05)}" data-step="0.05" title="${esc(t('From the flat to the far side of the hole — a D-shaft’s size (Ø5: 4.5)'))}"><span class="unit">mm</span>
        <button class="mini" data-a="turnflat" title="${esc(t('Turn the flat by 90°'))}">⇄</button></div>` : ''}
      ${std ? `<details class="m-holesizes" ${this.holeSizesOpen || !(size in HOLE_SIZES) ? 'open' : ''}><summary>Edit sizes</summary>
        <div class="field"><label>${sp.threaded ? 'Tap drill Ø' : 'Hole Ø'}</label><input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}" ${sp.threaded ? 'disabled' : ''}><span class="unit">mm</span></div>
        ${f.head ? `<div class="field"><label>Head Ø</label><input type="number" step="any" min="0" data-k="head_d" value="${fmt(f.head_d)}"><span class="unit">mm</span></div>` : ''}
        ${f.head === 'cbore' ? `<div class="field"><label>Head depth</label><input type="number" step="any" min="0" data-k="head_depth" value="${fmt(f.head_depth)}"><span class="unit">mm</span></div>` : ''}
      </details>` : ''}
      ${dh ? '' : this.teardropRow(f)}
      ${!std || f.fit ? `<div class="field"><label>Fit</label><select data-k="fit" title="An ISO 286 fit for the hole — shown on the 2D drawing (Ø8 H7 and its deviations); the model keeps the nominal size">
        ${['', 'H6', 'H7', 'H8', 'H9'].map((v) => `<option value="${v}" ${v === (f.fit || '') ? 'selected' : ''}>${v || '—'}</option>`).join('')}</select></div>` : ''}
      ${f.points.length ? `<h3>Holes</h3><div class="mp-holes">${f.points.map((p, i) => `<div class="mp-hole">
        <span>${i + 1}</span><div class="mp-hole-dims">${['x', 'y'].map((axis, k) => this.holeDimRow(f, i, axis, k)).join('')}</div>
        <button class="mini danger" data-del="${i}" title="Remove this hole">✕</button></div>`).join('')}</div>
        <p class="hint">${f.plane?.origin === 'corner' ? 'The holes keep their distances from the corner — they follow it when the part changes.'
          : f.plane?.origin ? 'The holes stay where these numbers put them, also when the part changes.'
          : 'Each hole keeps its distance from the edge it is measured from, also when the part changes. ⇄ measures from the other side.'}</p>`
        : '<p class="mp-count">No holes yet — click on a face.</p>'}
      ${this.cmd.isNew ? '' : `<div class="row-actions"><button class="btn small ${this.cmd.place ? 'on' : ''}" data-a="addpos" title="${esc(t('Then click on the face where another hole goes (click again for more); click this again to stop'))}">＋ ${esc(t('Add position'))}</button></div>`}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const num = (el, set) => {
      el.addEventListener('input', () => { const v = parseFloat(el.value); if (Number.isFinite(v)) { set(v); this.rebuild(); } });
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    };
    num(box.querySelector('[data-k=d]'), (v) => {
      if (!(v > 0)) return;
      if (dh && (f.flat === undefined || f.flat === dFlat(f.d))) { f.flat = dFlat(v); box.querySelector('[data-k=flat]').value = fmt(f.flat); } // (the flat follows the Ø while it is the default)
      f.d = v;
    });
    const fl = box.querySelector('[data-k=flat]');
    if (fl) num(fl, (v) => { if (v > 0) f.flat = v; });
    box.querySelector('[data-a=turnflat]')?.addEventListener('click', () => { f.flat_angle = ((f.flat_angle || 0) + 90) % 360; if (!f.flat_angle) delete f.flat_angle; this.rebuild(); });
    box.querySelector('.m-holesizes')?.addEventListener('toggle', (e) => { this.holeSizesOpen = e.target.open; });
    box.querySelector('[data-a=addpos]')?.addEventListener('click', () => this.armPlace());
    this.bindHoleProps(box, f, () => { this.renderProps(); this.rebuild(); });
    const dep = box.querySelector('[data-k=depth]');
    if (dep) num(dep, (v) => { if (v > 0) f.depth = v; });
    box.querySelector('[data-k=fit]')?.addEventListener('change', (e) => { if (e.target.value) f.fit = e.target.value; else delete f.fit; this.renderProps(); });
    box.querySelector('[data-k=teardrop]')?.addEventListener('change', (e) => { if (e.target.checked) f.teardrop = true; else delete f.teardrop; this.rebuild(); });
    for (const k of ['head_d', 'head_depth']) { const el = box.querySelector(`[data-k=${k}]`); if (el) num(el, (v) => { if (v > 0) f[k] = v; }); }
    for (const el of box.querySelectorAll('[data-u]')) num(el, (v) => { f.points[+el.dataset.u][0] = v; setHoleLock(f, +el.dataset.u, 'x', true); });
    for (const el of box.querySelectorAll('[data-v]')) num(el, (v) => { f.points[+el.dataset.v][1] = v; setHoleLock(f, +el.dataset.v, 'y', true); });
    for (const el of box.querySelectorAll('[data-lockhd]')) { // 🔒 / 🔓: a distance kept (or not) when the hole is dragged on the part
      el.addEventListener('click', (e) => {
        e.preventDefault(); // (in its row's label: not the number field)
        const [i, axis] = el.dataset.lockhd.split(':');
        setHoleLock(f, +i, axis, !holeLocked(f, +i, axis));
        this.renderProps();
        this.drawHoleDims();
      });
    }
    // a distance from an edge: typed as a positive number, the hole stays on its side of the edge
    for (const el of box.querySelectorAll('[data-hd]')) {
      const [i, axis] = el.dataset.hd.split(':'), k = axis === 'x' ? 0 : 1;
      num(el, (v) => { this.setHoleDist(f, +i, axis, v); this.drawHoleDims(); });
    }
    for (const el of box.querySelectorAll('[data-pickref]')) {
      el.addEventListener('click', () => {
        const [i, axis] = el.dataset.pickref.split(':');
        this.holePick = this.holePick?.i === +i && this.holePick?.axis === axis ? null : { i: +i, axis };
        this.hint(this.holePick ? `Click the edge (or another hole) to measure the ${axis === 'x' ? '↔' : '↕'} distance from. Esc = stop.` : '');
        this.renderProps();
      });
    }
    for (const el of box.querySelectorAll('[data-flip]')) {
      el.addEventListener('click', () => {
        const [i, axis] = el.dataset.flip.split(':'), r = f.from[+i][axis];
        const other = this.nearestEdges(f, f.points[+i], -(Math.sign(r.d) || 1))[axis];
        if (!other) { this.hooks.toast('There is no edge on the other side to measure from.', 'info'); return; }
        f.from[+i][axis] = other;
        this.renderProps();
        this.drawHoleDims();
      });
    }
    for (const el of box.querySelectorAll('[data-del]')) {
      el.addEventListener('click', () => {
        const gone = +el.dataset.del;
        f.points.splice(gone, 1);
        f.from?.splice(gone, 1);
        f.lock?.splice(gone, 1);
        for (const spec of f.from || []) {
          for (const axis of ['x', 'y']) {
            const r = spec?.[axis];
            if (r?.hole === gone) delete spec[axis];
            else if (r?.hole > gone) r.hole -= 1;
          }
        }
        if (!f.points.length) f.plane = null;
        this.renderProps();
        this.rebuild();
      });
    }
    for (const b of box.querySelectorAll('[data-origin]')) b.addEventListener('click', () => this.setHoleOrigin(b.dataset.origin));
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }


  // ------------------------------------------------------------------ Revolve / Shell
  startRevolve() {
    if (this.mode !== 'part' || this.cmd) return;
    const used = new Set(this.part.features.flatMap(sketchesOf));
    const sks = this.sketches();
    if (!sks.length) { this.hooks.toast('Draw a sketch first (✏ Sketch).', 'warning', 4500, { point: '.m-cmdbar [data-a=sketch]' }); return; }
    const sk = [...sks].reverse().find((x) => !used.has(x.id)) || sks[sks.length - 1];
    const helper = (sk.entities || []).find((e) => e.t === 'line' && e.construction); // (a construction line drawn for it: the axis)
    this.openCommand({ id: this.newId(), type: 'revolve', name: this.nextName('revolve', sk.id), sketch: sk.id, axis: helper ? helper.id : 'y', angle: 360, op: 'add' }, true);
  }

  startShell() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    this.openCommand({ id: this.newId(), type: 'shell', name: this.nextName('shell'), faces: [], t: 2 }, true);
  }

  renderRevolve(box) {
    const f = this.cmd.feature, sks = this.sketches(), st = this.status(f.id);
    const sk = this.part.features.find((g) => g.id === f.sketch);
    const lines = upgradeSketch(sk || { entities: [] }).entities.filter((e) => e.t === 'line');
    const cons = lines.filter((e) => e.construction), plain = lines.filter((e) => !e.construction);
    const axes = [['y', "The sketch's vertical axis"], ['x', "The sketch's horizontal axis"], ...cons.map((e, i) => [e.id, `┄ ${t('Construction line')} ${i + 1}`]),
      ...plain.map((e) => [e.id, `Line ${lines.indexOf(e) + 1} of the sketch`])];
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="seg big"><button data-op="add" class="${f.op !== 'cut' ? 'on' : ''}">⬆ Add material</button><button data-op="cut" class="${f.op === 'cut' ? 'on' : ''}">⬇ Cut</button></div>
      <div class="field"><label>Axis</label><select data-k="axis">${axes.map(([v, l]) => `<option value="${v}" ${v === f.axis ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></div>
      <div class="field"><label>Angle</label><input type="number" step="any" min="1" max="360" data-k="angle" value="${fmt(f.angle)}"><span class="unit">°</span></div>
      ${sks.length > 1 ? `<div class="field"><label>Sketch</label><select data-k="sketch">${sks.map((x) => `<option value="${x.id}" ${x.id === f.sketch ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>` : ''}
      <p class="hint">The sketch is spun around the axis — draw half of the shape on one side of it (e.g. half a vase beside the vertical axis).</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { f.op = b.dataset.op; changed(); });
    box.querySelector('[data-k=axis]').addEventListener('change', (e) => { f.axis = e.target.value; changed(); });
    box.querySelector('[data-k=sketch]')?.addEventListener('change', (e) => { f.sketch = e.target.value; f.axis = 'y'; changed(); });
    const a = box.querySelector('[data-k=angle]');
    a.addEventListener('input', () => { const v = parseFloat(a.value); if (v > 0 && v <= 360) { f.angle = v; this.rebuild(); } });
    a.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  renderShell(box) {
    const f = this.cmd.feature, st = this.status(f.id);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <p class="hint">Click the face(s) to leave open — e.g. the top of a cup or a box. Click a picked face in the list to drop it.</p>
      <div class="field"><label>Wall</label><input type="number" step="any" min="0" data-k="t" value="${fmt(f.t)}"><span class="unit">mm</span></div>
      ${f.faces.length ? `<div class="sk-dims">${f.faces.map((r, i) => `<div class="sk-dim"><span>Open face ${i + 1}</span><button class="mini danger" data-del="${i}" title="Close this face again">✕</button></div>`).join('')}</div>`
        : '<p class="mp-count">No face picked yet — click the face to leave open.</p>'}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const tIn = box.querySelector('[data-k=t]');
    tIn.addEventListener('input', () => { const v = parseFloat(tIn.value); if (v > 0) { f.t = v; this.rebuild(); } });
    tIn.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    for (const el of box.querySelectorAll('[data-del]')) el.addEventListener('click', () => { f.faces.splice(+el.dataset.del, 1); this.renderProps(); this.rebuild(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  clickShell(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (!h?.face?.name || h.face.name.startsWith(`${f.id}:`)) return;
    const ref = { name: h.face.name, fp: h.face.centroid };
    const k = f.faces.findIndex((r) => r.name === ref.name && Math.hypot(...r.fp.map((v, i) => v - ref.fp[i])) < 1e-6);
    if (k >= 0) f.faces.splice(k, 1);
    else f.faces.push(ref);
    this.renderProps();
    this.rebuild();
  }


  // ------------------------------------------------------------------ Text / picture on a face
  startDecal() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    this.openCommand({ id: this.newId(), type: 'decal', name: this.nextName('decal'), source: 'text', text: 'Text', h: 8, depth: 1, op: 'add', plane: null, at: [0, 0] }, true);
    this.traceDecal();
  }

  /** The text's outline (or keep the picture's). */
  async traceDecal() {
    const f = this.cmd?.feature;
    if (!f || f.source !== 'text') return;
    const want = f.text;
    try {
      const o = await textOutline(want, { bold: true });
      if (this.cmd?.feature !== f || f.text !== want) return; // typed on meanwhile
      if (!o) { f.polys = null; this.hooks.toast('Type some text first.', 'warning'); return; }
      f.polys = o.polygons;
      f.aspect = +o.aspect.toFixed(6);
      this.rebuild();
    } catch (e) { this.hooks.toast(e.message, 'error'); }
  }

  clickDecal(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (!this.cmd.place) { this.hooks.toast(t('To move it by clicking, click ⌖ Move by clicking first.'), 'info', 3000, { point: '[data-a=movepos]' }); return; }
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) { this.hooks.toast('Click a flat face of the part.', 'info', 3000); return; }
    const same = f.plane && f.plane.face?.name === h.face.name;
    if (!same) f.plane = { face: h.face.ref || { name: h.face.name }, frame: h.face.frame };
    f.at = this.faceSpot(e, f).s.uv; // snapped (facesnap.js): the face's centre, a corner, in line with a hole …, else a 0.5 mm grid
    this.spotKey = null;
    this.renderProps();
    this.rebuild();
  }

  /** The text / picture's place on its face: X, Y from the face's middle (sliders across the face) and its turn. */
  decalPlace(f) {
    if (!f.plane?.frame) return '';
    const sp = this.view.faceSpan(f.plane.face?.name, f.plane.frame) || [-50, 50, -50, 50], at = f.at || [0, 0];
    const r = (v) => Math.round(v * 2) / 2; // the slider on whole half mm
    const row = (k, i, lo, hi) => `<div class="field"><label>${k}</label><input type="number" step="0.5" data-at="${i}" data-lo="${r(Math.min(lo, at[i]))}" data-hi="${r(Math.max(hi, at[i]))}" data-step="0.5" value="${fmt(at[i])}"><span class="unit">mm</span></div>`;
    return `${row('X', 0, sp[0], sp[1])}${row('Y', 1, sp[2], sp[3])}
      <div class="field"><label>Turn</label><input type="number" step="any" data-k="angle" data-lo="-180" data-hi="180" data-step="1" value="${fmt(f.angle || 0)}"><span class="unit">°</span></div>`;
  }

  renderDecal(box) {
    const f = this.cmd.feature, st = this.status(f.id);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="seg"><button data-src="text" class="${f.source === 'text' ? 'on' : ''}">Aa Text</button><button data-src="picture" class="${f.source !== 'text' ? 'on' : ''}">🖼 Picture</button></div>
      ${f.source === 'text' ? `<div class="field"><label>Text</label><input type="text" data-k="text" value="${esc(f.text || '')}"></div>`
        : `<div class="row-actions"><button class="btn small" data-a="pickPicture">${f.polys ? 'Another picture…' : 'Choose a picture…'}</button></div>`}
      <div class="field"><label>Height</label><input type="number" step="any" min="0" data-k="h" value="${fmt(f.h)}"><span class="unit">mm</span></div>
      ${this.decalPlace(f)}
      <div class="seg"><button data-op="add" class="${f.op !== 'cut' ? 'on' : ''}">Raised</button><button data-op="cut" class="${f.op === 'cut' ? 'on' : ''}">Engraved</button></div>
      <div class="field"><label>Depth</label><input type="number" step="any" min="0" data-k="depth" value="${fmt(f.depth)}"><span class="unit">mm</span></div>
      ${this.cmd.isNew ? `<p class="hint">${f.plane ? 'Click on the face again to move it — near the face\'s centre it snaps to it.' : 'Click on a flat face of the part where it goes.'}</p>`
        : `<div class="row-actions"><button class="btn small ${this.cmd.place ? 'on' : ''}" data-a="movepos" title="${esc(t('Then click on a flat face where it goes; click this again to stop'))}">⌖ ${esc(t('Move by clicking'))}</button></div>`}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    for (const b of box.querySelectorAll('[data-src]')) {
      b.addEventListener('click', () => {
        f.source = b.dataset.src;
        f.polys = null;
        changed();
        if (f.source === 'text') this.traceDecal();
      });
    }
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { f.op = b.dataset.op; changed(); });
    box.querySelector('[data-a=movepos]')?.addEventListener('click', () => this.armPlace());
    const txt = box.querySelector('[data-k=text]');
    if (txt) {
      let timer = null;
      txt.addEventListener('input', () => { f.text = txt.value; clearTimeout(timer); timer = setTimeout(() => this.traceDecal(), 350); });
      txt.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    }
    for (const inp of box.querySelectorAll('[data-at], [data-k=angle]')) { // where on the face, and turned
      inp.addEventListener('input', () => {
        const v = parseFloat(String(inp.value).replace(',', '.'));
        if (!Number.isFinite(v)) return;
        if (inp.dataset.at !== undefined) { f.at = [...(f.at || [0, 0])]; f.at[+inp.dataset.at] = v; } else f.angle = v;
        this.rebuild();
      });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    }
    for (const k of ['h', 'depth']) {
      const inp = box.querySelector(`[data-k=${k}]`);
      inp.addEventListener('input', () => { const v = parseFloat(inp.value); if (v > 0) { f[k] = v; this.rebuild(); } });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    }
    box.querySelector('[data-a=pickPicture]')?.addEventListener('click', async () => {
      const o = await this.hooks.pickOutline?.();
      if (!o || this.cmd?.feature !== f) return;
      // to a unit square centred on 0, like traced text
      f.polys = o.polygons.map((poly) => poly.map((ring) => ring.map(([px, py]) => [+(px / o.width - 0.5).toFixed(6), +(py / o.height - 0.5).toFixed(6)])));
      f.aspect = +(o.width / o.height).toFixed(6);
      f.name = o.name ? `${t('Decoration')} ${o.name}` : f.name;
      changed();
    });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Loft / Sweep
  /** A sketch that is an open line (a path): its lines / arcs have loose ends and no circles. */
  isPath(sk) {
    const f = upgradeSketch(sk), n = {};
    for (const e of f.entities) {
      if (e.t === 'circle' || e.t === 'block') return false;
      if (e.t === 'line' || e.t === 'arc') for (const p of [e.a, e.b]) n[p] = (n[p] || 0) + 1;
      if (e.t === 'spline' && e.pts?.length > 1) for (const p of [e.pts[0], e.pts[e.pts.length - 1]]) n[p] = (n[p] || 0) + 1;
    }
    return Object.values(n).some((c) => c === 1);
  }

  startProfiles(type) {
    if (this.mode !== 'part' || this.cmd) return;
    const sks = this.sketches(), used = new Set(this.part.features.flatMap(sketchesOf));
    if (sks.length < 2) { this.hooks.toast('Draw two sketches first.', 'warning'); return; }
    const fresh = [...sks].reverse().filter((x) => !used.has(x.id)), pick = [...fresh, ...[...sks].reverse()];
    const f = { id: this.newId(), type, name: this.nextName(type), op: 'add' };
    if (type === 'loft') {
      const two = [...new Set(pick.filter((x) => !this.isPath(x)).map((x) => x.id))].slice(0, 2).reverse();
      f.sketches = two.length === 2 ? two : [sks[sks.length - 2].id, sks[sks.length - 1].id];
    } else {
      f.path = (pick.find((x) => this.isPath(x)) || pick[0]).id;
      f.profile = (pick.find((x) => x.id !== f.path && !this.isPath(x)) || pick.find((x) => x.id !== f.path)).id;
    }
    this.openCommand(f, true);
  }

  renderProfiles(box) {
    const f = this.cmd.feature, st = this.status(f.id), sks = this.sketches();
    const sel = (k, v, label) => `<div class="field"><label>${label}</label><select data-k="${k}">${sks.map((x) => `<option value="${x.id}" ${x.id === v ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>`;
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="seg big"><button data-op="add" class="${f.op !== 'cut' ? 'on' : ''}">⬆ Add material</button><button data-op="cut" class="${f.op === 'cut' ? 'on' : ''}">⬇ Cut</button></div>
      ${f.type === 'loft' ? `${sel('s0', f.sketches[0], 'From')}${sel('s1', f.sketches[1], 'To')}
        <p class="hint">Each sketch: one closed outline. Put them one above the other (a sketch's Offset moves its plane up).</p>`
        : `${sel('profile', f.profile, 'Profile')}${sel('path', f.path, 'Path')}
        <p class="hint">The profile: a closed outline at the start of the path, across it. The path: lines and arcs joined end to end.</p>`}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { f.op = b.dataset.op; changed(); });
    for (const el of box.querySelectorAll('select')) {
      el.addEventListener('change', () => {
        if (el.dataset.k === 's0' || el.dataset.k === 's1') f.sketches[+el.dataset.k.slice(1)] = el.value;
        else f[el.dataset.k] = el.value;
        changed();
      });
    }
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ a solid from a file (STEP / IGES / STL / OBJ)
  pickSolid() {
    if (this.mode !== 'part' || this.cmd || !this.hooks.importSolid) return;
    const inp = document.createElement('input');
    Object.assign(inp, { type: 'file', accept: '.step,.stp,.igs,.iges,.stl,.obj,.3mf' });
    inp.addEventListener('change', async () => {
      const file = inp.files[0];
      if (!file) return;
      let r;
      try { r = await this.hooks.importSolid(file); } catch (e) { this.hooks.toast(e.message.replace(/^MESH_TOO_BIG /, ''), 'error', 9000); return; }
      if (this.mode !== 'part' || this.cmd) return;
      if (r.warning) this.hooks.toast(t(r.warning), r.op === 'ref' ? 'warning' : 'info', 10000); // (an IGES: sewn, or not closed)
      // with a part there: a reference to build around (a cover, a holder); else the part itself (open surfaces: a reference)
      this.openCommand({ id: this.newId(), type: 'solid', name: r.name.replace(/\.[^.]+$/, ''), blob: r.blob, file: r.file || r.name, op: this.result?.body ? 'ref' : r.op || 'add' }, true);
    });
    inp.click();
  }

  renderSolid(box) {
    const f = this.cmd.feature, st = this.status(f.id), bb = st?.bbox, op = f.op || 'add';
    const size = bb ? `${fmt(bb[3] - bb[0])} × ${fmt(bb[4] - bb[1])} × ${fmt(bb[5] - bb[2])} mm` : '';
    box.innerHTML = `<h2 data-no-i18n>${esc(f.name)}</h2><p class="hint" data-no-i18n>${esc(f.file || '')}${size ? ` · ${size}` : ''}</p>
      <div class="seg big"><button data-op="add" class="${op === 'add' ? 'on' : ''}">▣ Joined</button><button data-op="cut" class="${op === 'cut' ? 'on' : ''}">⬚ Cut out</button><button data-op="ref" class="${op === 'ref' ? 'on' : ''}">👁 Reference</button></div>
      <label class="mp-check"><input type="checkbox" data-k="colours" ${f.colours === false ? '' : 'checked'}> ${esc(t("Keep the file's colours"))}</label>
      <p class="hint">${op === 'add' ? 'Part of the part: sketch on its faces, drill it, round its edges.'
        : op === 'cut' ? 'Cut out of the part: a cavity it fits in exactly (e.g. inside a cover you built around it).'
        : 'Shown see-through, not part of the part: build around it — a cover, a holder — then Cut out a copy of it to make it fit.'}</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { f.op = b.dataset.op; this.renderProps(); this.rebuild(); });
    box.querySelector('[data-k=colours]').addEventListener('change', (e) => { if (e.target.checked) delete f.colours; else f.colours = false; this.rebuild(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Mirror
  startMirror() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    this.openCommand({ id: this.newId(), type: 'mirror', name: this.nextName('mirror'), of: 'body', plane: { datum: 'YZ' }, copy: true }, true);
  }

  clickMirror(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) { this.hooks.toast('Click a flat face — it mirrors across it.', 'info', 3000); return; }
    f.plane = { face: h.face.ref || { name: h.face.name }, frame: h.face.frame };
    this.cmd.facePick = false;
    this.renderProps();
    this.rebuild();
  }

  renderMirror(box) {
    const f = this.cmd.feature, st = this.status(f.id), at = this.part.features.findIndex((x) => x.id === f.id);
    const rs = this.repeatable().filter((g) => g.id !== f.id && (at < 0 || this.part.features.indexOf(g) < at));
    const body = !f.of || f.of === 'body';
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="field"><label>Mirror</label><select data-k="of"><option value="body" ${body ? 'selected' : ''}>The whole part</option>
        ${rs.map((g) => `<option value="${g.id}" ${g.id === f.of ? 'selected' : ''} data-no-i18n>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Across</label><div class="seg">${Object.entries(MIRROR_PLANES).map(([k, v]) => `<button data-pl="${k}" class="${f.plane?.datum === k && !this.cmd.facePick ? 'on' : ''}" title="${esc(t(v))}">${k}</button>`).join('')}<button data-pl="face" class="${!f.plane?.datum || this.cmd.facePick ? 'on' : ''}" title="${esc(t('Mirror across a flat face of the part: click this, then the face in the view'))}">▱ ${esc(t('Face'))}</button></div></div>
      ${this.cmd.facePick ? `<p class="mp-count">${esc(t('Click a flat face of the part in the view.'))}</p>`
        : f.plane?.datum ? `<p class="hint">${esc(t(MIRROR_PLANES[f.plane.datum]))} — ${esc(t('or click a flat face to mirror across it.'))}</p>`
        : `<p class="mp-count">Across the face <b>${esc(this.faceLabel(f.plane?.face?.name || ''))}</b></p><p class="hint">${esc(t('Click another face to change it.'))}</p>`}
      ${body ? `<div class="seg big"><button data-copy="1" class="${f.copy !== false ? 'on' : ''}">⇋ Mirror and copy</button><button data-copy="0" class="${f.copy === false ? 'on' : ''}">↦ Mirror only</button></div>
        <p class="hint">${f.copy !== false ? 'The part and its mirror image, joined.' : 'The part turned into its mirror image.'}</p>` : '<p class="hint">The step is copied to the other side (holes stay holes).</p>'}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}${st?.warnings?.length ? `<p class="mp-warn">${esc(st.warnings.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    box.querySelector('[data-k=of]').addEventListener('change', (e) => { f.of = e.target.value; if (f.of !== 'body') f.copy = true; changed(); });
    for (const b of box.querySelectorAll('[data-pl]')) {
      b.addEventListener('click', () => {
        if (b.dataset.pl === 'face') { // (the face comes with the next click in the view)
          this.cmd.facePick = true;
          this.hint('Mirror — click a flat face of the part: it mirrors across it. Enter = OK, Esc = Cancel.');
          this.renderProps();
          return;
        }
        this.cmd.facePick = false;
        f.plane = { datum: b.dataset.pl };
        changed();
      });
    }
    for (const b of box.querySelectorAll('[data-copy]')) b.addEventListener('click', () => { f.copy = b.dataset.copy === '1'; changed(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ ✂ Split
  /** Where the part lies along a plane's normal: [lowest, highest] of its mesh's points (0 = on the plane). */
  planeSpan(fr) {
    const p = this.view.mesh?.geometry.attributes.position.array, o = fr.o, n = fr.n;
    if (!p) return [0, 0];
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < p.length; i += 3) {
      const s = (p[i] - o[0]) * n[0] + (p[i + 1] - o[1]) * n[1] + (p[i + 2] - o[2]) * n[2];
      if (s < lo) lo = s;
      if (s > hi) hi = s;
    }
    return [lo, hi];
  }

  /** The plane a clicked flat face splits along: its own plane when that goes through the part (a step's floor, a
   *  boss's top), else (an outer face) midway between it and the farthest parallel face across — the part in halves. */
  splitPlane(face) {
    const pl = { face: face.ref || { name: face.name }, frame: face.frame }, n = face.frame.n, slack = 1e-6 * (1 + this.view.size);
    const [lo, hi] = this.planeSpan(face.frame);
    if (lo < -slack && hi > slack) return pl;
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const across = (this.result?.body?.faces || []).filter((g) => g.type === 'plane' && g.name && Math.abs(Math.abs(dot(g.frame.n, n)) - 1) < 1e-6)
      .map((g) => ({ g, gap: dot(g.frame.o.map((v, k) => v - face.frame.o[k]), n) })).filter((x) => Math.abs(x.gap) > slack)
      .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap))[0];
    if (across) return { ...pl, mid: across.g.ref || { name: across.g.name }, frame: { ...face.frame, o: face.frame.o.map((v, k) => v + (across.gap / 2) * n[k]) } };
    return { ...pl, offset: +((lo + hi) / 2).toFixed(3) };
  }

  /** The base plane `datum` through the middle of the part (its offset to there). */
  datumThroughMiddle(datum) {
    const b = this.result?.body?.bbox, n = datumFrame({ datum }).n;
    const off = b ? +[0, 1, 2].reduce((s, k) => s + ((b[k] + b[k + 3]) / 2) * n[k], 0).toFixed(3) : 0;
    return { datum, ...(off ? { offset: off } : {}) };
  }

  /** ✂ Split: the part cut in two — by default across its longest side, in the middle (or along `plane`). */
  startSplit(plane = null) {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    if (!plane) {
      const b = this.result.body.bbox, size = [0, 1, 2].map((k) => b[k + 3] - b[k]);
      plane = this.datumThroughMiddle(['YZ', 'XZ', 'XY'][size.indexOf(Math.max(...size))]);
    }
    this.splitMid = false;
    this.openCommand({ id: this.newId(), type: 'split', name: this.nextName('split'), plane, keep: 'both' }, true);
  }

  /** The split's plane as built, its origin in the middle of the part (its arrow points to "this side"). */
  splitFrame() {
    const f = this.cmd?.feature, pl = f?.plane || {}, b = this.result?.body?.bbox;
    let fr = this.result?.frames?.[f?.id];
    if (!fr) {
      fr = pl.datum ? datumFrame(pl) : pl.frame;
      if (fr && pl.offset && !pl.datum) fr = { ...fr, o: fr.o.map((v, k) => v + pl.offset * fr.n[k]) };
    }
    if (!fr || !b) return fr;
    const c = [0, 1, 2].map((k) => (b[k] + b[k + 3]) / 2), s = [0, 1, 2].reduce((a, k) => a + (c[k] - fr.o[k]) * fr.n[k], 0);
    return { ...fr, o: c.map((v, k) => v - s * fr.n[k]) };
  }

  /** A click on a flat face: the split goes along it — or, after ⇳ Midway, halfway between the first face and this one. */
  clickSplit(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) { this.hooks.toast('Click a flat face — the part is cut along it.', 'info', 3000); return; }
    if (this.splitMid && f.plane?.face) {
      const nm = f.plane.face.name, first = this.result.body.faces.find((g) => g.type === 'plane' && (g.name === nm || (g.names || []).includes(nm)))?.frame || f.plane.frame;
      const n = first.n, dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], gap = dot(h.face.frame.o.map((v, k) => v - first.o[k]), n);
      if (Math.abs(Math.abs(dot(h.face.frame.n, n)) - 1) > 1e-6 || Math.abs(gap) < 1e-6) { this.hooks.toast('Click a flat face parallel to the first one, across from it.', 'warning', 4000); return; }
      f.plane = { face: f.plane.face, mid: h.face.ref || { name: h.face.name }, frame: { ...first, o: first.o.map((v, k) => v + (gap / 2) * n[k]) } };
      this.splitMid = false;
    } else f.plane = this.splitPlane(h.face);
    this.renderProps();
    this.rebuild();
  }

  renderSplit(box) {
    const f = this.cmd.feature, st = this.status(f.id), pl = f.plane || {}, face = !pl.datum;
    const where = face ? (pl.mid ? t('Midway between two faces') : t('Along the face you clicked')) : `${t(DATUM_NAME[pl.datum])} — ${t('through the part')}`;
    const keeps = [['both', '✂ Both'], ['above', 'This side'], ['below', 'Other side']];
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="field"><label>Plane</label><div class="seg">${Object.entries(DATUM_NAME).map(([k, v]) => `<button data-pl="${k}" class="${pl.datum === k ? 'on' : ''}">${esc(t(v))}</button>`).join('')}</div></div>
      ${face ? `<div class="field"><label></label><div class="seg"><button data-a="mid" class="${pl.mid || this.splitMid ? 'on' : ''}" title="${esc(t('Midway between this face and another one parallel to it: click the other face'))}">⇳ Midway</button></div></div>` : ''}
      <p class="hint">${esc(where)}${this.splitMid ? ` — ${esc(t('now click the face across from it.'))}` : ` — ${esc(t('or click a flat face to cut along it.'))}`}</p>
      <div class="field"><label>Offset</label><input type="number" step="any" data-k="offset" value="${fmt(pl.offset || 0)}"><span class="unit">mm</span></div>
      <div class="field"><label>Keep</label><div class="seg big">${keeps.map(([k, label]) => `<button data-keep="${k}" class="${(f.keep || 'both') === k ? 'on' : ''}">${esc(t(label))}</button>`).join('')}</div></div>
      <p class="hint">${esc(t((f.keep || 'both') === 'both' ? 'Both pieces stay, as two bodies of this part (two shades here).' : 'This side: where the arrow points.'))}${st?.ok && st.bodies ? ` ${esc(t('Bodies'))}: ${st.bodies}` : ''}</p>
      ${(f.keep || 'both') === 'both' && st?.ok && this.hooks.newParts ? `<button class="btn" data-a="pieces" title="${esc(t('Two new parts: this part\'s steps up to here, each keeping one piece'))}">⧉ Make each piece its own part</button>` : ''}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}${st?.warnings?.length ? `<p class="mp-warn">${esc(st.warnings.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild()?.then?.(() => { if (this.cmd?.feature === f) this.renderProps(); }); }; // (its result shown when built)
    for (const b of box.querySelectorAll('[data-pl]')) b.addEventListener('click', () => { f.plane = this.datumThroughMiddle(b.dataset.pl); this.splitMid = false; changed(); });
    box.querySelector('[data-a=mid]')?.addEventListener('click', () => {
      this.splitMid = !this.splitMid;
      if (!this.splitMid && f.plane.mid) { const { mid, ...rest } = f.plane; f.plane = rest; changed(); return; } // (off again: along the face itself)
      this.renderProps();
    });
    const off = box.querySelector('[data-k=offset]');
    off.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') off.blur(); if (e.key === 'Escape') this.escCommand(); });
    off.addEventListener('change', () => {
      const v = parseFloat(String(off.value).replace(',', '.'));
      if (!Number.isFinite(v)) return;
      f.plane = { ...f.plane, offset: v };
      if (!v) delete f.plane.offset;
      changed();
    });
    for (const b of box.querySelectorAll('[data-keep]')) b.addEventListener('click', () => { f.keep = b.dataset.keep; changed(); });
    box.querySelector('[data-a=pieces]')?.addEventListener('click', () => this.piecesAsParts());
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  /** ⧉ Each piece its own part: the split is kept here (both pieces), and two new model parts get this part's steps
   *  up to the split, one keeping this side, the other the other side. */
  async piecesAsParts() {
    const f = this.cmd?.feature;
    if (!f || f.type !== 'split') return;
    this.okCommand();
    await this.inflight;
    const at = this.part.features.findIndex((g) => g.id === f.id), name = this.hooks.safeName?.() || t('3D model');
    if (at < 0) return;
    const pieces = [['above', 1], ['below', 2]].map(([keep, k]) => ({ name: `${name} — ${t('piece')} ${k}`,
      data: { ...this.payload(), features: structuredClone(this.part.features.slice(0, at + 1)).map((g) => (g.id === f.id ? { ...g, keep } : g)) } }));
    await this.hooks.newParts(pieces);
  }

  // ------------------------------------------------------------------ Rib
  startRib(id = null) {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const used = new Set(this.part.features.flatMap(sketchesOf)), sks = this.sketches();
    const sk = sks.find((s) => s.id === id) || [...sks].reverse().find((s) => !used.has(s.id) && (s.entities || []).some((e) => e.t === 'line' && !e.construction));
    if (!sk) { this.hooks.toast('Draw the rib\'s line first: a sketch on a plane across the corner, one line from the wall to the plate.', 'warning', 6000); return; }
    this.openCommand({ id: this.newId(), type: 'rib', name: this.nextName('rib', sk.id), sketch: sk.id, t: 3 }, true);
  }

  renderRib(box) {
    const f = this.cmd.feature, st = this.status(f.id), sks = this.sketches();
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="field"><label>Sketch</label><select data-k="sketch">${sks.map((g) => `<option value="${g.id}" ${g.id === f.sketch ? 'selected' : ''} data-no-i18n>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Thickness</label><input type="number" step="any" min="0" data-k="t" value="${fmt(f.t)}"><span class="unit">mm</span></div>
      <div class="row-actions"><button class="btn small ${f.flip ? 'on' : ''}" data-k="flip" title="Fill the other side of the line (when both sides close against the part, e.g. across a bore)">⇅ Flip direction</button></div>
      <p class="hint">${esc(t('Its line is filled up to the part, on the side where it closes, half the thickness each side of the sketch plane.'))}</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.rebuild().then(() => { if (this.cmd?.feature === f) this.renderProps(); }); };
    box.querySelector('[data-k=sketch]').addEventListener('change', (e) => { f.sketch = e.target.value; changed(); });
    const th = box.querySelector('[data-k=t]');
    th.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') th.blur(); });
    th.addEventListener('change', () => { const v = parseFloat(String(th.value).replace(',', '.')); if (v > 0) { f.t = v; changed(); } });
    box.querySelector('[data-k=flip]').addEventListener('click', () => { if (f.flip) delete f.flip; else f.flip = true; this.renderProps(); changed(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Draft
  /** The extrudes whose side walls a draft can tilt (before step `before`). */
  draftable(before = null) {
    const at = before ? this.part.features.findIndex((x) => x.id === before) : -1;
    return this.part.features.slice(0, this.usable()).filter((g) => g.type === 'extrude' && !g.suppressed && (at < 0 || this.part.features.indexOf(g) < at));
  }

  startDraft() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const es = this.draftable();
    if (!es.length) { this.hooks.toast('Draft tilts the walls of an extrude — make one first.', 'warning'); return; }
    const sel = es.find((g) => g.id === this.selected) || es[es.length - 1]; // (the chosen one, else the newest)
    this.openCommand({ id: this.newId(), type: 'draft', name: this.nextName('draft'), of: sel.id, angle: 3 }, true);
  }

  /** A click on a wall: the extrude it belongs to is the one drafted. */
  clickDraft(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY), owner = h?.face && this.faceOwner({ name: h.face.name });
    if (!owner || !this.draftable(f.id).some((g) => g.id === owner)) { this.hooks.toast('Click a wall of an extrude.', 'info', 3000); return; }
    f.of = owner;
    this.renderProps();
    this.rebuild();
  }

  renderDraft(box) {
    const f = this.cmd.feature, st = this.status(f.id), es = this.draftable(f.id);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="field"><label>Walls of</label><select data-k="of">${es.map((g) => `<option value="${g.id}" ${g.id === f.of ? 'selected' : ''} data-no-i18n>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Angle</label><input type="number" step="0.5" min="-44.5" max="44.5" data-k="angle" value="${fmt(f.angle)}"><span class="unit">°</span></div>
      <p class="hint">${esc(t('Its side walls lean in going up from its base (negative: out) — or click a wall of another extrude.'))}</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild()?.then?.(() => { if (this.cmd?.feature === f) this.renderProps(); }); }; // (its result shown when built)
    box.querySelector('[data-k=of]').addEventListener('change', (e) => { f.of = e.target.value; changed(); });
    const ang = box.querySelector('[data-k=angle]');
    ang.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') ang.blur(); });
    ang.addEventListener('change', () => { const v = parseFloat(String(ang.value).replace(',', '.')); if (Number.isFinite(v)) { f.angle = v; changed(); } });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Pattern
  repeatable() { return this.part.features.slice(0, this.usable()).filter((f) => REPEATABLE.has(f.type) && !f.suppressed); }

  startPattern(of = null) {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const rs = this.repeatable();
    if (!rs.length) { this.hooks.toast('Make something to repeat first — a hole, a boss or a cut.', 'warning'); return; }
    // the step asked for (a suggestion), else the newest hole or cut — the usual thing to repeat —, else the newest step
    const last = rs.find((f) => f.id === of) || [...rs].reverse().find((f) => f.type === 'hole' || f.op === 'cut') || rs[rs.length - 1];
    this.openCommand({ id: this.newId(), type: 'pattern', name: this.nextName('pattern'), features: [last.id], kind: 'linear', dir: [1, 0, 0], count: 3, spacing: 10 }, true);
  }

  /** A straight edge's direction (unit), or null for a curved one. */
  edgeDir(i) {
    const flat = this.result?.body?.edges[i]?.pts || [], pts = [];
    for (let k = 0; k + 2 < flat.length; k += 3) pts.push([flat[k], flat[k + 1], flat[k + 2]]);
    if (pts.length < 2) return null;
    const a = pts[0], b = pts[pts.length - 1], d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], L = Math.hypot(...d);
    if (L < 1e-9) return null;
    const u = d.map((v) => v / L);
    // straight: every point lies on the line a–b
    const off = pts.some((p) => {
      const w = [p[0] - a[0], p[1] - a[1], p[2] - a[2]], t = w[0] * u[0] + w[1] * u[1] + w[2] * u[2];
      return Math.hypot(w[0] - t * u[0], w[1] - t * u[1], w[2] - t * u[2]) > 1e-4 * (1 + L);
    });
    return off ? null : u.map((v) => +v.toFixed(9));
  }

  clickPattern(e) {
    const f = this.cmd.feature;
    if (f.kind === 'circular') {
      const h = this.view.pick(e.clientX, e.clientY);
      if (!h?.face?.axis) { this.hooks.toast('Click a round face — the pattern goes around its axis.', 'warning'); return; }
      f.axis = structuredClone(h.face.axis);
    } else {
      const i = this.view.pickEdge(e.clientX, e.clientY), d = i >= 0 ? this.edgeDir(i) : null;
      if (!d) return;
      f.dir = d;
    }
    this.renderProps();
    this.rebuild()?.then?.(() => { if (this.cmd?.feature === f) this.renderProps(); }); // (its warning — copies off the part — when built)
  }

  /** "x" | "y" | "z" when the direction (or the axis, through the origin) is a main axis, else null. */
  axisLabel(f) {
    const d = f.kind === 'circular' ? f.axis?.d || [0, 0, 1] : f.dir || [1, 0, 0];
    const k = Object.keys(AXES).find((a) => Math.abs(Math.abs(AXES[a].reduce((s, v, i) => s + v * d[i], 0)) - 1) < 1e-9);
    if (f.kind === 'circular') return k && !(f.axis?.o || []).some((v) => Math.abs(v) > 1e-9) ? k : null;
    return k || null;
  }

  renderPattern(box) {
    const f = this.cmd.feature, st = this.status(f.id), circ = f.kind === 'circular';
    const at = this.part.features.findIndex((x) => x.id === f.id);
    const rs = this.repeatable().filter((g) => g.id !== f.id && (at < 0 || this.part.features.indexOf(g) < at));
    const ax = this.axisLabel(f);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="seg big"><button data-kind="linear" class="${!circ ? 'on' : ''}">▦ In a row</button><button data-kind="circular" class="${circ ? 'on' : ''}">◌ Around</button></div>
      <div class="mp-of"><div class="mp-of-t">${esc(t('Repeat'))} <span class="mp-count">${esc(t2('{n} step(s)', { n: f.features.length }))}</span></div>
        <div class="mp-checks">${[...rs].reverse().map((g) => `<label class="check" title="${esc(t('Tick it to repeat this step too'))}"><input type="checkbox" data-of="${g.id}" ${f.features.includes(g.id) ? 'checked' : ''}> <span data-no-i18n>${esc(g.name)}</span></label>`).join('')}</div>
        <p class="hint">${esc(t('Tick more steps to repeat them together (e.g. a boss and its hole).'))}</p></div>
      <div class="field"><label>How many</label><input type="number" step="1" min="2" data-k="count" value="${f.count}"></div>
      ${circ ? '' : `<div class="field"><label>Apart</label><input type="number" step="any" min="0" data-k="spacing" value="${fmt(f.spacing)}"><span class="unit">mm</span></div>`}
      <div class="field"><label>${circ ? 'Around' : 'Direction'}</label><div class="seg">${Object.keys(AXES).map((a) => `<button data-ax="${a}" class="${ax === a ? 'on' : ''}">${a.toUpperCase()}</button>`).join('')}${circ ? '' : '<button data-a="flipDir" title="The other way">⇄</button>'}</div></div>
      <p class="hint">${circ ? (ax ? 'Evenly around the axis through the origin. Or click a round face (a hole, a shaft) to go around its axis.' : 'Evenly around the axis of the round face you clicked.')
        : (ax ? 'Or click a straight edge in the view to go along it.' : 'Along the edge you clicked.')}</p>
      <div data-st>${this.statusHtml(st)}</div>
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    for (const b of box.querySelectorAll('[data-kind]')) {
      b.addEventListener('click', () => {
        f.kind = b.dataset.kind;
        if (f.kind === 'circular') { f.axis = f.axis || { o: [0, 0, 0], d: [0, 0, 1] }; if (f.count < 4) f.count = 6; }
        changed();
      });
    }
    for (const b of box.querySelectorAll('[data-ax]')) {
      b.addEventListener('click', () => {
        if (circ) f.axis = { o: [0, 0, 0], d: AXES[b.dataset.ax] };
        else f.dir = AXES[b.dataset.ax];
        changed();
      });
    }
    box.querySelector('[data-a=flipDir]')?.addEventListener('click', () => { f.dir = f.dir.map((v) => (v ? -v : 0)); changed(); });
    for (const c of box.querySelectorAll('[data-of]')) {
      c.addEventListener('change', () => {
        const on = rs.filter((g) => (g.id === c.dataset.of ? c.checked : f.features.includes(g.id))).map((g) => g.id); // (in the order of the steps)
        if (!on.length) { c.checked = true; this.hooks.toast('A pattern repeats at least one step.', 'info', 2500); return; }
        f.features = on;
        changed();
      });
    }
    for (const k of ['count', 'spacing']) {
      const inp = box.querySelector(`[data-k=${k}]`);
      if (!inp) continue;
      inp.addEventListener('input', () => {
        const v = parseFloat(inp.value);
        if (v > 0 && (k !== 'count' || (Number.isInteger(v) && v >= 2))) {
          f[k] = v;
          this.rebuild()?.then?.(() => { const el = box.querySelector('[data-st]'); if (el && this.cmd?.feature === f) el.innerHTML = this.statusHtml(this.status(f.id)); });
        }
      });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.escCommand(); });
    }
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  /** A step's problem (red) or warnings (yellow) for its panel. */
  statusHtml(st) {
    return st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : st?.warnings?.length ? `<p class="mp-warn">⚠ ${esc(st.warnings.join(' '))}</p>` : '';
  }

  // ------------------------------------------------------------------ 🎨 paint faces / bodies
  togglePaint() {
    if (this.mode !== 'part' || this.cmd || (!this.painting && !this.result?.body)) return;
    if (this.measuring) this.toggleMeasure();
    this.painting = this.painting ? null : { by: 'face', sel: new Set() };
    this.view.picked.clear();
    this.view.paint();
    this.hint(this.painting ? 'Paint — click a face (or a body), Ctrl+click for more, then pick a colour. Esc ends.' : '');
    this.renderCmdBar();
    this.renderProps();
  }

  /** The faces chosen for painting, marked. */
  paintMarks() {
    this.view.picked = new Set(this.painting?.sel || []);
    this.view.paint();
  }

  clickPaint(e) {
    const ps = this.painting, b = this.result?.body, h = this.view.pick(e.clientX, e.clientY), more = e.ctrlKey || e.metaKey;
    if (!h?.face) { if (!more) ps.sel.clear(); this.paintMarks(); this.renderProps(); return; }
    // a whole body: every face of its solid
    const ids = ps.by === 'solid' && Number.isInteger(h.face.solid) ? b.faces.filter((f) => f.solid === h.face.solid).map((f) => f.id) : [h.face.id];
    if (more) {
      const all = ids.every((n) => ps.sel.has(n));
      for (const n of ids) (all ? ps.sel.delete(n) : ps.sel.add(n));
    } else ps.sel = new Set(ids);
    this.paintMarks();
    this.renderProps();
  }

  renderPaint(box) {
    const ps = this.painting, b = this.result?.body, n = ps.sel.size, now = paintedFaces(b?.faces || [], this.part.paint);
    const solids = new Set((b?.faces || []).map((f) => f.solid).filter(Number.isInteger)).size;
    const first = [...ps.sel].find((x) => now.has(x));
    box.innerHTML = `<h2>🎨 Paint</h2>
      <div class="seg"><button data-by="face" class="${ps.by === 'face' ? 'on' : ''}">▢ Faces</button><button data-by="solid" class="${ps.by === 'solid' ? 'on' : ''}" ${solids > 1 ? '' : 'disabled title="This part is one body"'}>▣ Bodies${solids > 1 ? ` (${solids})` : ''}</button></div>
      <p class="hint">Click ${ps.by === 'solid' ? 'a body' : 'a face'} — Ctrl+click adds more (or takes one away).</p>
      <p class="mp-count">${n ? t2('{n} face(s) chosen', { n }) : t('Nothing chosen yet')}</p>
      <div class="field"><label>Colour</label><input type="color" data-k="paint" value="${(first !== undefined && now.get(first).color) || this.part.color || '#d9dee6'}" ${n ? '' : 'disabled'}></div>
      <div class="row-actions wrap"><button class="btn small" data-a="unpaint" ${n && [...ps.sel].some((x) => now.has(x)) ? '' : 'disabled'}>↺ Their own colour off</button>
        <button class="btn small" data-a="unpaintAll" ${now.size ? '' : 'disabled'}>Clear all colours</button></div>
      <p class="hint">${t2('{n} face(s) of this part have their own colour (shown in assemblies too).', { n: now.size })}</p>
      <div class="mp-actions"><button class="btn primary" data-a="donePaint">Done</button></div>`;
    for (const el of box.querySelectorAll('[data-by]')) el.addEventListener('click', () => { ps.by = el.dataset.by; ps.sel.clear(); this.paintMarks(); this.renderProps(); });
    const col = box.querySelector('[data-k=paint]');
    const commit = () => { this.history.commit(); this.hooks.onChange?.(); };
    const setPaint = (p) => { if (p.length) this.part.paint = p; else delete this.part.paint; this.view.setLook({ ...this.part, color: lookColor(this.part) }); };
    col.addEventListener('input', () => setPaint(repaint(b.faces, this.part.paint, ps.sel, col.value)));
    col.addEventListener('change', () => { commit(); this.renderProps(); });
    box.querySelector('[data-a=unpaint]').addEventListener('click', () => { setPaint(repaint(b.faces, this.part.paint, ps.sel, null)); commit(); this.renderProps(); });
    box.querySelector('[data-a=unpaintAll]').addEventListener('click', () => { setPaint([]); commit(); this.renderProps(); });
    box.querySelector('[data-a=donePaint]').addEventListener('click', () => this.togglePaint());
  }

  // ------------------------------------------------------------------ measure, section
  toggleMeasure() {
    if (this.mode !== 'part' || this.cmd) return;
    this.measuring = this.measuring ? null : { a: null };
    if (this.measuring) this.ms.start(); else this.ms.stop();
    this.view.setHover(-1);
    if (!this.measuring) { this.hint(''); this.view.setSnapMark(null); }
    this.renderCmdBar();
  }

  /** 📏 What a measure click takes (measure.js): a corner / reference point near the mouse, else an edge under it (its
   *  middle and a round edge's centre only when the mouse is right on them — snapWins), else the face. */
  measurePick(e) {
    const b = this.result?.body, v = this.view;
    if (!b) return null;
    const mp = v.measurePoint(e.clientX, e.clientY);
    const ei = snapWins(v, mp, e) ? -1 : v.pickEdge(e.clientX, e.clientY, 6);
    if (mp?.snap && ei < 0) return { kind: 'point', p: mp.point.clone(), snap: mp.snap, name: mp.name || '' };
    if (ei >= 0) {
      const ed = b.edges[ei], names = ed.faces.map((k) => b.faces[k]?.name || ''), n = ed.pts.length / 3, k = 3 * Math.floor(n / 2);
      return { kind: 'edge', pts: ed.pts, id: `E${ei + 1}`, at: mp?.point?.clone() || [ed.pts[k], ed.pts[k + 1], ed.pts[k + 2]],
        hole: names.some((x) => x.includes(':hole')), tip: names.filter(Boolean).map((x) => this.faceLabel(x)).join(' / ') };
    }
    if (!mp?.face) return null;
    const f = mp.face, i = b.faces.indexOf(f);
    return { kind: 'face', face: f, faceId: f.id, id: `F${(i >= 0 ? i : f.id) + 1}`, at: mp.point.clone(), hole: String(f.name).includes(':hole'), tip: this.faceLabel(f.name) };
  }

  clickMeasure(e) { if (this.result?.body) this.ms.click(e); }

  toggleSection() {
    if (this.section) { // (off also when the part has no solid now: rolled back, its solid step deleted, another model)
      this.section = null;
      this.view.setSection(null);
      this.$('.m-section')?.remove();
    } else {
      const bb = this.result?.body?.bbox;
      if (!bb) return;
      this.section = { axis: 'y', offset: sectionMiddle(bb, 'y'), flip: false };
      this.view.setSection(this.section);
      this.renderSection();
    }
    this.renderCmdBar();
  }

  renderSection() {
    const s = this.section, bb = this.result?.body?.bbox;
    if (!s || !bb) return;
    sectionBar(this.els.viewport, s, bb, { onChange: (x) => this.view.setSection(x), onClose: () => this.toggleSection() });
  }

  // ------------------------------------------------------------------ mouse and keys
  bindPointer() {
    const cv = this.view.renderer.domElement;
    let down = null;
    cv.addEventListener('contextmenu', (e) => e.preventDefault()); // (the right button pans; a left click suggests everything)
    // with no tool on, the mouse over the part: the work once a frame (the mouse sends more moves than the screen shows)
    const hoverNow = () => {
      const e = this.hoverEv;
      this.hoverEv = null;
      if (!e || this.mode !== 'part' || this.cmd || down) return;
      const id = this.view.pickOutline(e.clientX, e.clientY);
      if (id) { this.view.clearHoverMarks(); this.view.setHover(-1); this.tip(null); cv.style.cursor = 'pointer'; cv.title = 'Double-click to edit this sketch'; return; }
      cv.title = '';
      if (this.measuring) { this.view.setHoverSnaps([]); this.ms.hover(e); return; } // (what a click measures: lit, named)
      const sp = this.view.measurePoint(e.clientX, e.clientY);
      this.view.setSnapMark(sp); // (a corner, an edge's middle, a centre, the origin: it can be picked)
      const ax = !sp?.snap && this.view.originAxis(e.clientX, e.clientY);
      if (ax) { // the origin's arrows (drawn over the part): named
        this.view.setHover(-1);
        this.view.clearHoverMarks();
        this.tip({ x: e.clientX, y: e.clientY, text: t({ X: 'X axis', Y: 'Y axis', Z: 'Z axis' }[ax]) });
        cv.style.cursor = '';
        return;
      }
      // a made hole: it can be dragged on its face (holedrag.js) — said at the mouse, its step lit
      const hd = !this.painting && holeUnder(this, e.clientX, e.clientY);
      if (hd) {
        const fs = this.stepFaces({ name: `${hd.f.id}:` });
        this.view.setHover(-1, fs?.ids || null);
        this.hoverMarks(e, fs);
        this.tip({ x: e.clientX, y: e.clientY, text: holeHint(hd) });
        cv.style.cursor = hd.free.x || hd.free.y ? 'move' : 'pointer';
        return;
      }
      // the step under the mouse: all its faces light up, its name at the mouse
      const h = this.view.pick(e.clientX, e.clientY), fs = h?.face && this.stepFaces(h.face);
      this.view.setHover(h?.face ? h.face.id : -1, fs?.ids || null);
      this.hoverMarks(e, fs);
      this.tip(fs ? { x: e.clientX, y: e.clientY, text: `${fs.step.name} — ${this.faceLabel(h.face.name).replace(/ of .*$/, '').replace(/^the /, '')}` } : null);
      cv.style.cursor = h?.face ? 'pointer' : '';
    };
    cv.addEventListener('pointerdown', (e) => {
      if (this.hoverEv) hoverNow(); // (a move not shown yet: as it came, before the press)
      if (e.button !== 0 || (e.buttons & ~1)) { down = null; return; } // the left button alone
      down = { x: e.clientX, y: e.clientY, drag: null };
      if (this.mode === 'part' && this.cmd?.feature.type === 'extrude' && this.view.pullHit(e.clientX, e.clientY)) { // the pull arrow's tip: drag the distance
        down.pull = true;
        this.view.controls.enabled = false;
        cv.setPointerCapture(e.pointerId);
        return;
      }
      if (this.mode === 'sketch') {
        down.drag = this.sk.down(e);
        if (down.drag) cv.setPointerCapture(e.pointerId);
      }
      if (this.mode === 'part' && !this.cmd && !this.measuring && !this.painting && !e.shiftKey && !e.ctrlKey && !e.metaKey) { // a made hole: dragged once the mouse goes (a click still chooses it)
        const g = holeUnder(this, e.clientX, e.clientY);
        if (g && (g.free.x || g.free.y)) {
          down.hole = g;
          this.view.controls.enabled = false; // (not the camera)
          cv.setPointerCapture(e.pointerId);
        }
      }
    });
    cv.addEventListener('pointermove', (e) => {
      if (down?.pull) { this.pullTo(e); return; }
      if (down?.hole) { // a hole held: past a few pixels it moves (Esc: back where it was)
        if (!this.holeDrag && !down.hole.done && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) {
          this.holeDrag = new HoleDrag(this, down.hole);
          down.hole.done = true; // (one drag per press: after Esc it does not start again)
          this.view.controls.enabled = false;
          this.view.clearHoverMarks();
          this.view.setSnapMark(null);
          this.view.setHover(-1);
          cv.style.cursor = 'move';
        }
        this.holeDrag?.move(e);
        return;
      }
      if (this.mode === 'part' && this.cmd?.feature.type === 'extrude' && !down && this.view.pullHit(e.clientX, e.clientY)) { cv.style.cursor = 'grab'; return; }
      if (this.mode === 'plane') {
        const h = this.view.pick(e.clientX, e.clientY, { datums: true });
        this.view.setHover(h?.face?.type === 'plane' ? h.face.id : -1);
        this.view.highlightDatum(h?.datum || null);
        cv.style.cursor = (h?.face?.type === 'plane' || h?.datum) ? 'pointer' : '';
        return;
      }
      if (this.mode === 'sketch') {
        if (!down?.drag) { const uv = this.view.planePoint(e.clientX, e.clientY, this.frame()); cv.style.cursor = uv && this.sk.dimHitAt(uv) ? 'grab' : cv.style.cursor === 'grab' ? '' : cv.style.cursor; }
        this.sk.move(e, down?.drag || null);
      }
      if (this.mode !== 'part' || this.cmd || down) this.view.clearHoverMarks(); // (only with no tool on)
      if (this.mode === 'part' && this.cmd && !down && (!USES_SKETCH.has(this.cmd.feature.type) || this.cmd.feature.upto)) {
        const f = this.cmd.feature;
        if (f.type === 'extrude') {
          const h = f.upto ? this.view.pick(e.clientX, e.clientY) : null, ok = h?.face?.type === 'plane' && !h.face.name?.startsWith(`${f.id}:`);
          this.view.setHover(ok ? h.face.id : -1);
          cv.style.cursor = ok ? 'pointer' : '';
        } else if (f.type === 'decal' || (f.type === 'hole' && !this.holePick)) {
          cv.style.cursor = this.cmd.place && this.showSpot(e) ? 'crosshair' : ''; // (snapped, with guides and the hole's preview; editing: once asked)
        } else if (f.type === 'mirror' || f.type === 'split') {
          const h = this.view.pick(e.clientX, e.clientY), ok = h?.face?.type === 'plane' && !h.face.name?.startsWith(`${f.id}:`);
          this.view.setHover(ok ? h.face.id : -1);
          cv.style.cursor = ok ? 'crosshair' : '';
        } else if (f.type === 'hole' && this.holePick) {
          const i = this.view.pickEdge(e.clientX, e.clientY), ok = i >= 0 && this.holeRefAt(i), ax = !ok && this.holeAxisAt(e.clientX, e.clientY, i);
          this.view.setEdgeHighlight(ok ? i : -1, []);
          this.view.setHover(ax ? ax.face : -1);
          cv.style.cursor = ok || ax ? 'pointer' : '';
        } else if (f.type === 'pattern') {
          const i = f.kind === 'circular' ? -1 : this.view.pickEdge(e.clientX, e.clientY);
          const straight = i >= 0 && this.edgeDir(i);
          this.view.setEdgeHighlight(straight ? i : -1, []);
          const h = f.kind === 'circular' ? this.view.pick(e.clientX, e.clientY) : null;
          this.view.setHover(h?.face?.axis ? h.face.id : -1);
          cv.style.cursor = straight || h?.face?.axis ? 'pointer' : '';
        } else if (f.type === 'shell') {
          const h = this.view.pick(e.clientX, e.clientY);
          this.view.setHover(h?.face ? h.face.id : -1);
          cv.style.cursor = h?.face ? 'pointer' : '';
        } else {
          const i = this.view.pickEdge(e.clientX, e.clientY, ROUND_PICK_PX), ok = i >= 0 && this.edgeRef(i); // (as the click)
          this.view.setEdgeHighlight(ok ? this.chainOf(i) : -1, this.refEdges(f.edges));
          const h = ok ? null : this.view.pick(e.clientX, e.clientY);
          this.view.setHover(h?.face ? h.face.id : -1);
          cv.style.cursor = ok || h?.face ? 'pointer' : '';
        }
      } else if (this.mode === 'part' && !this.cmd && !down) {
        this.hoverEv = e;
        if (!this.hoverRaf) this.hoverRaf = requestAnimationFrame(() => { this.hoverRaf = 0; hoverNow(); });
      }
    });
    cv.addEventListener('pointerup', (e) => {
      if (e.button !== 0 || !down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4;
      const drag = down.drag;
      if (down.pull) { down = null; this.view.controls.enabled = true; return; } // (the pull arrow let go)
      if (down.hole) {
        const g = down.hole;
        down = null;
        this.view.controls.enabled = true;
        if (this.holeDrag) { this.holeDrag.drop(); return; } // (let go: the hole goes there)
        if (g.done) return; // (Esc'd)
        if (!moved) this.clickFace(e); // a plain click: the hole chosen, as ever
        return;
      }
      down = null;
      if (drag) { this.sk?.up(drag); if (drag.moved || moved) return; }
      if (moved) return; // the camera was moved
      if (this.mode === 'plane') return this.clickPlane(e);
      if (this.mode === 'sketch') return this.sk.click(e);
      if (this.mode === 'part' && this.cmd && (!USES_SKETCH.has(this.cmd.feature.type) || this.cmd.feature.upto)) return this.clickCommand(e);
      if (this.mode === 'part' && this.measuring) return this.clickMeasure(e);
      if (this.mode === 'part' && this.painting) return this.clickPaint(e);
      if (this.mode === 'part' && !this.cmd) return this.clickFace(e);
      return null;
    });
    cv.addEventListener('pointerleave', () => { this.hoverEv = null; this.view.clearHoverMarks(); if (this.measuring) this.ms.hover(null); if (['hole', 'decal'].includes(this.cmd?.feature.type) && !this.holePick) this.showSpot(null); if (this.mode === 'part' && !this.cmd) { this.view.setHover(-1); this.tip(null); } });
    cv.addEventListener('dblclick', (e) => {
      if (this.mode !== 'part' || this.cmd) return;
      const id = this.view.pickOutline(e.clientX, e.clientY);
      if (id) this.edit(id);
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  clickPlane(e) {
    const h = this.view.pick(e.clientX, e.clientY, { datums: true });
    if (h?.face) {
      if (h.face.type !== 'plane') { this.hooks.toast('Pick a flat face — sketches go on flat faces.', 'warning'); return; }
      if (this.midPick) return this.clickMid(h);
      const plane = { frame: h.face.frame };
      if (h.face.ref) plane.face = h.face.ref;
      this.enterSketch(plane);
    } else if (h?.datum) this.enterSketch({ datum: h.datum });
  }

  /** ⇳ Midway's clicks: the first face kept (lit), the second one parallel to it -> the sketch halfway between. */
  clickMid(h) {
    const ref = h.face.ref || (h.face.name ? { name: h.face.name } : null);
    const first = this.midPick.first;
    if (!first) {
      this.midPick.first = { id: h.face.id, ref, frame: h.face.frame };
      this.view.setSelectedFaces([h.face.id]);
      this.hint('Now click the face opposite it (parallel to it). Esc cancels.');
      return;
    }
    const fr = first.frame, n = fr.n, p = [h.point.x, h.point.y, h.point.z];
    const par = Math.abs(n[0] * h.face.frame.n[0] + n[1] * h.face.frame.n[1] + n[2] * h.face.frame.n[2]);
    const gap = (p[0] - fr.o[0]) * n[0] + (p[1] - fr.o[1]) * n[1] + (p[2] - fr.o[2]) * n[2];
    if (Math.abs(par - 1) > 1e-6 || Math.abs(gap) < 1e-6) { this.hooks.toast('Click a face parallel to the first one, across from it.', 'warning'); return; }
    const plane = { frame: { ...fr, o: fr.o.map((v, i) => v + (gap / 2) * n[i]) } };
    if (first.ref && ref) Object.assign(plane, { face: first.ref, mid: ref });
    this.midPick = null;
    this.view.setSelectedFaces(null);
    this.enterSketch(plane);
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    if (document.querySelector('.wizard, .lightbox')) return;
    const k = e.key.toLowerCase();
    if (this.holeDrag) { if (e.key === 'Escape') this.holeDrag.cancel(); return; } // (a hole being dragged: Esc puts it back)
    if (this.ctx && e.key === 'Escape') { this.closeCtx(); return; }
    if (this.mode === 'sketch') {
      if (e.key === 'Enter') { this.finishSketch(); return; }
      this.sk.key(e);
      return;
    }
    if (this.mode === 'plane') { if (e.key === 'Escape') this.cancelPlane(); return; }
    if (this.cmd) {
      if (e.key === 'Escape') this.escCommand();
      if (e.key === 'Enter') this.okCommand();
      return;
    }
    if (this.measuring && e.key === 'Escape') { this.toggleMeasure(); return; }
    if (this.painting && e.key === 'Escape') { this.togglePaint(); return; }
    if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')) { e.preventDefault(); this.history.go(k === 'y' || e.shiftKey ? 1 : -1); return; }
    if (k === 'm') this.toggleMeasure();
    if (k === 's' && !e.ctrlKey) this.startSketch();
    if (k === 'e') this.startExtrude();
    if (k === 'f') this.startRound('fillet');
    if (k === 'h') this.startHole();
    if (e.key === 'Delete' && this.selected) this.remove(this.selected);
    if (e.key === 'Escape' && (this.selected || this.picks?.length)) { this.picks = []; this.view.setEdgeHighlight(); this.selectStep(null); this.dropSuggest(); } // (nothing chosen: ✨ Next)
  }

  // ------------------------------------------------------------------ the part as a project tab
  /** Editing this part in place, from an assembly: the other parts around it, a bar with ◇ Back to the assembly. */
  setContext(ctx) {
    this.context = ctx || null;
    this.view.setContext(ctx?.context || []);
    this.$('.m-editctx')?.remove();
    if (!ctx) return;
    const bar = document.createElement('div');
    bar.className = 'm-editctx';
    bar.innerHTML = `<span>✎ ${esc(t('Editing it in'))} <b data-no-i18n>${esc(ctx.assembly || '')}</b> — ${esc(t('the other parts are see-through; changes show in the assembly.'))}</span>
      <button class="btn small primary" data-a="ctxBack">◇ ${esc(t('Back to the assembly'))}</button>`;
    bar.querySelector('[data-a=ctxBack]').addEventListener('click', () => this.hooks.backTo?.(ctx.back));
    this.els.viewport.appendChild(bar);
    if (ctx.face) this.pickFaceNamed(ctx.face); // (✎ from a face picked in the assembly: that face chosen here too)
  }

  /** A face chosen by its name once the part is built (✎ Edit the part here from a face picked in an assembly): its
   *  suggestions — a sketch on it, a hole — one click away. Not there (renamed, not built in ~15 s): nothing chosen. */
  pickFaceNamed(name, tries = 0) {
    const f = (this.view.body?.faces || []).find((x) => x.name === name || (x.names || []).includes(name)), fs = f && this.stepFaces(f);
    if (!fs) { if (tries < 150 && this.context?.face === name) setTimeout(() => this.pickFaceNamed(name, tries + 1), 100); return; }
    const p = this.view.camera.position.clone().set(...f.centroid), q = p.clone().project(this.view.camera), r = this.view.renderer.domElement.getBoundingClientRect();
    this.picks = [{ kind: 'face', step: fs.step, face: f, point: p }];
    this.faceTable({ face: f, point: p }, fs, { clientX: r.left + (q.x + 1) / 2 * r.width, clientY: r.top + (1 - q.y) / 2 * r.height });
  }

  load(data, { then } = {}) {
    this.setContext(null);
    if (this.section) this.toggleSection();
    this.closeAll();
    this.part = structuredClone(data || { features: [] });
    this.part.features = this.part.features || [];
    this.result = null;
    this.frames = {};
    this.selected = null;
    this.$('.m-install').hidden = true;
    this.view.setBody(null);
    this.history.reset();
    this.ms.reset(); // (its measurements: this part's)
    this.render();
    this.rebuild().then(() => {
      if (then === 'extrude' && this.sketches().length) { this.startExtrude(); return; }
      if (then === 'none') { if (this.result?.body) this.view.setView('iso'); return; } // (the AI builds it)
      if (this.result?.body) this.view.setView('iso');
      else if (!this.part.features.length && this.active) this.startSketch();
      else if (!this.result?.body) this.view.setView('top');
    });
  }

  payload() { return structuredClone(this.part); }

  async export(fmtName) {
    const res = await fetch(`/api/model/export/${fmtName}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part: this.part, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json()).error}`, 'error'); return; }
    if (await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.${{ iges: 'igs' }[fmtName] || fmtName}`)) {
      const said = fmtName === 'pdf' ? 'Exported the drawing (PDF).' : fmtName === 'glb' ? 'Exported GLB (glTF: metres, Y up, its colours and material).' : `Exported ${fmtName.toUpperCase()} (in mm).`;
      const note = rollbackNote(this.part); // (⏮ the bar is up: the file is the part as it stands — said, so it never surprises)
      this.hooks.toast(note ? `${t(said)} ${note}` : said, note ? 'warning' : 'ok', note ? 8000 : undefined);
    }
  }

  hasBody() { return !!this.result?.body; }

  /** ⚖ The centre of mass marked in the view (⊕ in the Part panel) or not. */
  toggleCog() { this.cogOn = !this.cogOn; this.showCog(); this.renderProps(); }

  showCog() { const c = this.cogOn && this.result?.body?.cog; this.view.setCog(c || null, c ? t('Centre of mass') : ''); }

  /** The body's mass in grams (solid), with the part's material. */
  massGrams() { const b = this.result?.body; return b ? +(b.volume / 1000 * MATERIALS[this.part.material || 'PLA']).toFixed(2) : null; }

  setMaterial(name) {
    if (!MATERIALS[name]) throw new Error(`material is one of ${Object.keys(MATERIALS).join(', ')}.`);
    this.part.material = name;
    this.view.setLook({ ...this.part, color: lookColor(this.part) }); // (its colour: the material's, unless it has its own)
    this.history.commit();
    this.renderProps();
    this.hooks.onChange?.();
  }

  /** A printing copy of this part: its STEP opened as a Quick part (printer fit, splitting, joints) — the pieces of a
   * split are cut from the exact solid, so curved walls stay smooth. ⏮ As the rollback bar stands (the copy keeps the note). */
  async toPrint() {
    const res = await fetch('/api/model/export/step', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part: this.part, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json()).error}`, 'error'); return; }
    await this.hooks.toPrint(await res.blob(), rollbackNote(this.part));
  }
}
