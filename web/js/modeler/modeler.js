// The 3D model workspace: sketches (rectangles, lines, circles drawn with the mouse on a plane or a flat face,
// sizes locked 🔒 by typing them — sketcher.js)
// turned into a solid by Extrude (add material / cut), step by step in a feature tree — like Solid Edge or
// SolidWorks, but only the few tools that need almost no input (docs/ARCHITECTURE-modeler.md, §3).
// The server's CAD kernel builds the body (/api/model/rebuild); this module edits the part JSON.
import { History } from '../history.js';
import { t } from '../i18n.js';
import { toolGroup } from '../toolgroups.js';
import { renameInPlace } from '../rename.js';
import { choose } from '../choose.js';
import { paintedFaces, repaint } from './paint.js';
import { ModelView, DATUMS, datumFrame, snapPoints } from './view.js';
import { Sketcher, upgradeSketch, arcPts, splinePts, RELATIONS, BIG_SKETCH } from './sketcher.js';
import { textOutline } from '../outlinepanel.js';
import { sectionBar, sectionMiddle } from './sectionbar.js';
import { originSeg, originKey, sameOrigin, moveOrigin, shiftSketch, shiftPoints, HOLE_ORIGINS, FROM_TEXT } from './origin.js';
import { libraryFactsHtml } from '../library/browser.js';

const ICON = { sketch: '✏', extrude: '⬆', cut: '⬇', revolve: '⟳', fillet: '◜', chamfer: '◸', hole: '◎', shell: '▢', pattern: '⁂', loft: '⧫', sweep: '〰', solid: '▣', decal: 'Aa', mirror: '⇋', draft: '⟋', rib: '⊿', point: '•' };
const TYPE_NAME = { point: 'Point', rib: 'Rib', draft: 'Draft', sketch: 'Sketch', extrude: 'Extrude', revolve: 'Revolve', fillet: 'Fillet', chamfer: 'Chamfer', hole: 'Hole', shell: 'Shell', pattern: 'Pattern',
  loft: 'Loft', sweep: 'Sweep', solid: 'Solid', decal: 'Decoration', mirror: 'Mirror' };
const LIMIT_FIELDS = { extrude: ['d', 'offset'], revolve: ['angle'], fillet: ['r'], chamfer: ['d'], hole: ['d', 'depth'], shell: ['t'],
  pattern: ['count', 'spacing'], decal: ['h', 'depth'] }; // the numbers the kernel finds ranges for (doc.LIMIT_FIELDS)
const REPEATABLE = new Set(['extrude', 'revolve', 'hole', 'pattern', 'loft', 'sweep', 'decal', 'mirror']);
const MIRROR_PLANES = { YZ: 'left ↔ right', XZ: 'front ↔ back', XY: 'top ↔ bottom' }; // the base planes to mirror across
const AXES = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };
const USES_SKETCH = new Set(['extrude', 'revolve', 'loft', 'sweep', 'rib']);
/** The sketches a step is made from. */
// ISO metric coarse threads -> their tap drill (as auto3d/modeler/doc.py THREADS)
const THREADS = { M2: 1.6, 'M2.5': 2.05, M3: 2.5, M4: 3.3, M5: 4.2, M6: 5, M8: 6.8, M10: 8.5, M12: 10.2, M16: 14, M20: 17.5 };
const sketchesOf = (f) => (f.type === 'loft' ? f.sketches || [] : f.type === 'sweep' ? [f.profile, f.path] : USES_SKETCH.has(f.type) ? [f.sketch] : []).filter(Boolean);
// densities for the mass (g/cm³), common 3D-printing materials
import { MATERIALS, MATERIAL_GROUPS, MATERIAL_COLOR, lookColor } from './materials.js';
import { showSuggest, showSnapFilters, snapKinds, hoverKinds } from '../suggest.js';
export { MATERIALS }; // g/cm³ (materials.js: grouped, with their colours)
const DATUM_NAME = { XY: 'Top', XZ: 'Front', YZ: 'Right' };
const fmt = (v) => (+(+v).toFixed(3)).toString();
const SIZES_KEY = 'a3d.sizes', SIZE_MODES = ['all', 'locked', 'none'];
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
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
      capture: () => ({ features: this.part.features, look: { color: this.part.color, opacity: this.part.opacity, paint: this.part.paint } }),
      restore: async (s) => {
        this.part.features = s.features;
        for (const k of ['color', 'opacity', 'paint']) { if (s.look?.[k] === undefined) delete this.part[k]; else this.part[k] = s.look[k]; }
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
      <div class="m-busy" hidden><span>Building the 3D model…</span><button class="mini" title="Stop this (the part stays as it was)">Cancel</button></div>
      <div class="m-install" hidden></div>
      <div class="m-status"></div>`;
    right.innerHTML = '<div class="mp-body"></div>';
    this.els.view = viewport.querySelector('.m-view');
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
    this.$('.m-busy button').addEventListener('click', () => { if (this.rid) fetch(`/api/progress/${this.rid}/cancel`, { method: 'POST' }); });
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
    box.innerHTML = `<b>🖨 ${esc(t('Print check'))}</b>
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
      const offset = onDatum ? `<label class="chip m-offset" title="Move the sketch plane along its normal (e.g. 30 mm above the bed — for a loft's second profile); a positive offset moves it along the arrow">↕ Plane at
        <input type="number" step="any" data-k="planeOffset" value="${fmt(this.sk.f.plane.offset || 0)}"> mm <span class="m-plus" data-no-i18n>(+ = ${plus})</span></label><span class="sep"></span>` : '';
      this.view.setPlaneArrow(onDatum ? this.frame() : null, plus);
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
    } else {
      this.els.viewport.querySelector(':scope > .view-suggest[data-from=sketch]')?.remove(); // (the sketch's suggestions)
      this.view.setPlaneArrow(null);
      showSnapFilters(this.els.viewport, !!this.result?.body && !this.cmd); // (what 📏 Measure catches — not while a feature is made)
      if (this.cmd || this.measuring || this.painting) this.dropSuggest(); // (a tool at work: not the face's)
      const canExtrude = this.sketches().length > 0;
      bar.innerHTML = `
        ${btn('sketch', '✏ Sketch', 'Start a sketch: on a plane, or on a flat face of the part (S)', 'tool')}
        ${btn('extrude', '⬆ Extrude', canExtrude ? 'Give a sketch a height: add material or cut (E)' : 'Draw a sketch first', 'tool')}
        ${btn('revolve', '⟳ Revolve', canExtrude ? 'Spin a sketch around an axis (vases, knobs, wheels)' : 'Draw a sketch first', 'tool')}
        ${btn('loft', '⧫ Loft', 'A shape from one outline to another (e.g. a square base to a round top): two sketches, one above the other', 'tool')}
        ${btn('sweep', '〰 Sweep', 'Move an outline along a path (pipes, handles, rails): a profile sketch and a path sketch', 'tool')}
        ${btn('solidFile', '▣ Solid from a file', 'Add a STEP / STL / OBJ solid: joined to the part, cut out of it (a cavity it fits in), or as a see-through reference to build around', 'tool')}
        ${btn('fillet', '◜ Fillet', 'Round edges: click the edges, give the radius (F)', 'tool')}
        ${btn('chamfer', '◸ Chamfer', 'Bevel edges: click the edges, give the size', 'tool')}
        ${btn('shell', '▢ Shell', 'Hollow the part out: click the face(s) to leave open, give the wall thickness', 'tool')}
        ${btn('draft', '⟋ Draft', 'Tilt the side walls of an extrude by a few degrees (so a moulded or cast part comes out of its mould)', 'tool')}
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
      for (const a of ['fillet', 'chamfer', 'hole', 'shell', 'pattern', 'decal', 'mirror', 'draft', 'rib']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body || !!this.cmd;
      bar.querySelector('[data-a=revolve]').disabled = !canExtrude || !!this.cmd;
      for (const a of ['loft', 'sweep']) bar.querySelector(`[data-a=${a}]`).disabled = this.sketches().length < 2 || !!this.cmd;
      for (const a of ['measure', 'section', 'paint']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body;
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
      off.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') off.blur(); });
      off.addEventListener('change', () => {
        const v = parseFloat(String(off.value).replace(',', '.'));
        if (!Number.isFinite(v) || !this.sk) return;
        this.sk.f.plane = { ...this.sk.f.plane, offset: v };
        if (!v) delete this.sk.f.plane.offset;
        this.view.lookAt(this.frame(), this.sketchSpan());
        this.sk.draw();
      });
    }
    this.updateUndo();
    const h = this.$('.m-hint');
    if (h) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`;
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
    if (a === 'shell') return this.startShell();
    if (a === 'pattern') return this.mode === 'sketch' ? this.sk.startPattern() : this.startPattern();
    if (a === 'draft') return this.startDraft();
    if (a === 'rib') return this.startRib();
    if (a === 'solidFile') return this.pickSolid();
    if (a === 'duplicatePart') return this.hooks.duplicatePart?.();
    if (a === 'saveToLibrary') return this.hooks.saveToLibrary?.();
    if (a === 'saveBack') return this.hooks.saveBackToLibrary?.();
    if (a === 'mirror') return this.mode === 'sketch' ? this.sk.setTool('mirror') : this.startMirror();
    if (a === 'construction' && this.mode === 'sketch') return this.sk.toggleConstruction();
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

  hint(text) {
    const h = this.$('.m-hint'), bar = this.$('.m-cmdbar');
    h.hidden = !text;
    h.textContent = text || '';
    if (bar) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`; // below the bar, also when it wraps to two rows
  }

  // ------------------------------------------------------------------ feature tree
  sketches() { return this.part.features.filter((f) => f.type === 'sketch'); }
  status(id) { return this.result?.features?.find((s) => s.id === id); }

  renderTree() {
    const tree = this.$('.mt-tree');
    const fs = this.part.features;
    this.$('.mt-start').hidden = fs.length > 0;
    tree.innerHTML = '';
    for (const f of fs) {
      const st = this.status(f.id);
      const row = document.createElement('div');
      const editing = (this.sk && this.sk.f.id === f.id) || (this.cmd && this.cmd.feature.id === f.id);
      const warn = st && st.ok && st.warnings?.length;
      row.className = `mt-item${f.id === this.selected ? ' on' : ''}${st && !st.ok ? ' bad' : ''}${warn ? ' warned' : ''}${editing ? ' editing' : ''}${f.suppressed ? ' off' : ''}`;
      row.dataset.id = f.id;
      const icon = f.type === 'extrude' ? ICON[f.op === 'cut' ? 'cut' : 'extrude'] : ICON[f.type] || '•';
      row.innerHTML = `<span class="mt-icon">${icon}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>
        ${st && !st.ok ? '<span class="mt-warn">⚠</span>' : warn ? '<span class="mt-warn soft">⚠</span>' : ''}
        <span class="mt-acts"><button class="mini" data-a="off" title="${f.suppressed ? 'Turn this step on again' : 'Turn this step off for now (it is kept)'}">${f.suppressed ? '◌' : '●'}</button><button class="mini" data-a="rename" title="Rename this step">🏷</button><button class="mini" data-a="edit" title="Change this step (or double-click it)">✎</button><button class="mini danger" data-a="del" title="Delete this step">✕</button></span>`;
      row.querySelector('.mt-name').textContent = f.name;
      row.querySelector('.mt-what').textContent = f.suppressed ? 'off' : this.whatText(f);
      if (st && !st.ok) row.title = st.issues.join(' ');
      else if (warn) row.title = st.warnings.join(' ');
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'edit') return this.edit(f.id);
        if (a === 'del') return this.remove(f.id);
        if (a === 'off') return this.toggleOff(f.id);
        if (a === 'rename') {
          renameInPlace(row.querySelector('.mt-name'), (n) => { f.name = n; this.history.commit(); this.render(); this.hooks.onChange?.(); });
          return null;
        }
        this.selectStep(f.id);
        return null;
      });
      row.addEventListener('dblclick', () => this.edit(f.id));
      if (!editing && this.mode === 'part' && !this.cmd) { // dragged up or down the list: the step moves (if what it uses stays before it)
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
          const r = row.getBoundingClientRect();
          this.moveStep(e.dataTransfer.getData('text/a3d-step'), f.id, e.clientY > r.top + r.height / 2);
        });
      }
      tree.appendChild(row);
    }
    this.showPoints();
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
    if (f.type === 'extrude' && f.upto) return `${f.op === 'cut' ? 'cut ' : ''}up to a face${f.offset ? ` ${f.offset > 0 ? '+' : ''}${fmt(f.offset)} mm` : ''}`;
    if (f.type === 'extrude') return f.op === 'cut' ? (f.through ? 'cut through all' : `cut ${fmt(f.d)} mm`) : `${fmt(f.d)} mm`;
    if (f.type === 'fillet') return `R ${fmt(f.r)} · ${n('edges')} edge(s)`;
    if (f.type === 'chamfer') return `${fmt(f.d)} mm · ${n('edges')} edge(s)`;
    if (f.type === 'hole') return `${f.thread || `Ø${fmt(f.d)}`}${f.fit ? ` ${f.fit}` : ''}${f.head === 'cbore' ? ` ⌴Ø${fmt(f.head_d)}×${fmt(f.head_depth)}` : f.head === 'csk' ? ` ⌵Ø${fmt(f.head_d)}` : ''} · ${n('points')} hole(s)${f.through === false ? ` · ${fmt(f.depth)} deep` : ''}`;
    if (f.type === 'revolve') return `${fmt(f.angle)}°${f.op === 'cut' ? ' cut' : ''}`;
    if (f.type === 'shell') return `wall ${fmt(f.t)} mm · ${n('faces')} open`;
    if (f.type === 'decal') return `${f.source === 'text' ? `“${f.text}”` : 'picture'} · ${fmt(f.h)} mm${f.op === 'cut' ? ' · engraved' : ' · raised'}`;
    if (f.type === 'loft') return `${(f.sketches || []).length} sketches${f.op === 'cut' ? ' · cut' : ''}`;
    if (f.type === 'sweep') return `along ${this.part.features.find((g) => g.id === f.path)?.name || '?'}${f.op === 'cut' ? ' · cut' : ''}`;
    if (f.type === 'draft') return `${fmt(f.angle)}° · ${this.part.features.find((g) => g.id === f.of)?.name || '?'}`;
    if (f.type === 'rib') return `${fmt(f.t)} mm · ${this.part.features.find((g) => g.id === f.sketch)?.name || '?'}`;
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
    const ids = (this.result?.body?.faces || []).filter((f) => [f.name, ...(f.names || [])].some((n) => String(n).split(':')[0] === id)).map((f) => f.id);
    return { step, ids };
  }

  /** With no tool on: the edge under the mouse lit (a line or a circle), and the snap points of the hovered step
   *  (its faces' corners, edge middles and centres, by the snap filters) shown as dots. */
  hoverMarks(e, fs) {
    const body = this.view.body, hk = hoverKinds(), i = body && hk.edges ? this.view.pickEdge(e.clientX, e.clientY, 7) : -1;
    this.view.setHoverEdges(i >= 0 ? [{ pts: body.edges[i].pts }] : [], i >= 0 ? `e${i}` : '');
    if (!fs || !body || !hk.points) { this.view.setHoverSnaps([]); return; }
    const ids = new Set(fs.ids), idx = new Set(body.faces.map((f, k) => (ids.has(f.id) ? k : -1)).filter((k) => k >= 0));
    const kinds = snapKinds(), key = `${fs.step.id}|${Object.entries(kinds).map(([k, v]) => (v ? k : '')).join('')}`;
    if (key === this.view.hoverSnapKey) return;
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
    if (this.mode !== 'part' || this.cmd) { this.selected = id; this.renderTree(); return; }
    this.closeCtx();
    this.selected = id;
    const f = this.part.features.find((g) => g.id === id);
    this.view.setSelectedFaces(f ? this.stepFaceIds(id) : null);
    this.renderTree();
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

  /** A snap point picked (no tool on): marked, and what to do with it suggested — measure from it, copy it, ask the AI. */
  pickSnap(sp) {
    const p = sp.point, xyz = [p.x, p.y, p.z].map((v) => fmt(+v.toFixed(3))).join(', ');
    const kind = sp.snap === 'point' ? sp.name : t({ corner: 'A corner', midpoint: 'An edge midpoint', centre: 'A centre', quadrant: 'A quadrant' }[sp.snap]);
    if (sp.snap === 'point') this.selectStep(sp.id); // a reference point: its step chosen
    this.view.setMeasure([p]);
    const sg = showSuggest(this.els.viewport, `${kind} · ${xyz}`, [
      ...(['corner', 'midpoint', 'centre'].includes(sp.snap) ? [{ icon: '•', label: t('Reference point here'), title: t('A point that stays on this place of the part when it changes — sketches and 📏 Measure snap to it'),
        run: () => { this.dropSuggest(); this.addPoint(sp); } }] : []),
      { icon: '📏', label: t('Measure from here'), run: () => {
        this.dropSuggest();
        if (!this.measuring) this.toggleMeasure();
        this.measuring.a = p;
        this.view.setMeasure([p]);
        this.measureBox(`<div class="mm-rows"><b>${esc(kind)}</b><span>${esc(t('Point'))}</span><b>${xyz}</b></div><p class="hint">${esc(t('Click a second spot for the distance.'))}</p>`);
      } },
      { icon: '⧉', label: t('Copy its coordinates'), run: () => { navigator.clipboard?.writeText(xyz).catch(() => {}); this.hooks.toast(`${t('Copied')}: ${xyz}`, 'info', 2500); } },
    ], t('No tool on: a click on a corner, an edge\'s middle or a centre picks it'), `${t('in the 3D model')}: ${t('the point')} (${xyz}) — ${kind.toLowerCase()} ${t('of the part')}`);
    if (sg) sg.dataset.from = 'face';
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
    this.part.features.push(f);
    this.selected = f.id;
    this.commit();
    return f;
  }

  /** The suggestions table of the 3D model (a face's tools) gone. */
  dropSuggest() { const b = this.els.viewport.querySelector(':scope > .view-suggest[data-from=face]'); b?.remove(); if (!this.measuring) this.view.setMeasure([]); }

  /** A click on the part: its step is chosen (its sizes show) and everything for that face is suggested (bottom left),
   *  in sections: on this face, its edges, the part, the step. */
  clickFace(e) {
    this.closeCtx();
    const sp = this.view.measurePoint(e.clientX, e.clientY), more = e.ctrlKey || e.metaKey;
    const h = sp?.snap ? null : this.view.pick(e.clientX, e.clientY), fs = h?.face && this.stepFaces(h.face);
    const pick = sp?.snap ? { kind: 'point', point: sp.point.clone(), snap: sp.snap } : fs ? { kind: 'face', step: fs.step, face: h.face, point: h.point.clone() } : null;
    if (more && pick && this.picks?.length) { this.addPick(pick); return; } // Ctrl+click: one more in the selection
    this.picks = pick ? [pick] : [];
    if (sp?.snap) { this.pickSnap(sp); return; } // a corner, an edge's middle, a centre
    if (!this.measuring) this.view.setMeasure([]);
    if (!fs) { this.selectStep(null); this.dropSuggest(); return; }
    this.selectStep(fs.step.id);
    const flat = h.face.type === 'plane', at = { clientX: e.clientX, clientY: e.clientY };
    // [key, icon, label, do it] by section: this face, its edges, the whole part, the step it belongs to
    const sections = [
      [t('On this face'), [
        flat && ['sketch', '✏', t('Sketch on this face'), () => this.enterSketch({ frame: h.face.frame, ...(h.face.ref ? { face: h.face.ref } : {}) })],
        flat && ['hole', '◎', t('Hole here'), () => { this.startHole(); if (this.cmd) this.clickHole(at); }],
        flat && ['decal', 'Aa', t('Text / picture here'), () => { this.startDecal(); if (this.cmd) this.clickDecal(at); }],
        flat && ['shell', '▢', t('Hollow out, open here'), () => { this.startShell(); if (this.cmd) this.clickShell(at); }]]],
      [t('Its edges'), [
        ['fillet', '◜', t('Round its edges'), () => { this.startRound('fillet'); if (this.cmd) this.clickCommand(at); }],
        ['chamfer', '◸', t('Bevel its edges'), () => { this.startRound('chamfer'); if (this.cmd) this.clickCommand(at); }]]],
      [t('The part'), [
        flat && ['mirror', '⇋', t('Mirror across this face'), () => { this.startMirror(); if (this.cmd) this.clickMirror(at); }]]],
      [`${t('Step')} · ${fs.step.name}`, [
        ['edit', '✎', t('Edit the step'), () => this.edit(fs.step.id)],
        ['off', fs.step.suppressed ? '●' : '◌', t(fs.step.suppressed ? 'Turn it on' : 'Turn it off'), () => this.toggleOff(fs.step.id)],
        ['del', '✕', t('Delete the step'), () => this.remove(fs.step.id), 'danger']]],
    ].map(([title, items]) => [title, items.filter(Boolean)]).filter(([, items]) => items.length);
    const face = t(this.faceLabel(h.face.name).replace(/ of .*$/, '').replace(/^the /, ''));
    const sg = showSuggest(this.els.viewport, `${fs.step.name} · ${face}`, sections.flatMap(([title, items]) => [{ section: title },
      ...items.map(([, icon, label, run, cls]) => ({ icon, label, danger: cls === 'danger', run: () => { this.dropSuggest(); run(); } }))]), '',
      `${t('in the 3D model')}: ${t('step')} ${fs.step.id} “${fs.step.name}”, ${t('face')} ${h.face.name}${h.face.type === 'plane' ? ` (${t('flat')})` : h.face.type === 'cylinder' ? ` (${t('round')}, Ø${fmt(2 * (h.face.radius || 0))})` : ''}`);
    if (sg) sg.dataset.from = 'face';
  }

  closeCtx() { this.ctx?.remove(); this.ctx = null; }

  /** Ctrl+click: a face (its step) or a snap point more in the selection — or, chosen already, taken out of it. */
  addPick(pick) {
    const same = (a, b) => a.kind === b.kind && (a.kind === 'face' ? a.step.id === b.step.id && a.face.id === b.face.id : a.point.distanceTo(b.point) < 1e-6);
    const i = this.picks.findIndex((q) => same(q, pick));
    if (i >= 0) this.picks.splice(i, 1); else this.picks.push(pick);
    this.showPicks();
  }

  /** Several things chosen (Ctrl+click): all marked — their steps' faces, the points — and what fits them suggested:
   *  the distance between two (the gap between two parallel flat faces), turning their steps off, deleting them. */
  showPicks() {
    const ps = (this.picks || []).filter((q) => q.kind === 'point' || this.part.features.includes(q.step));
    this.picks = ps;
    if (!ps.length) { this.selectStep(null); this.dropSuggest(); this.view.setMeasure([]); return; }
    const steps = [...new Map(ps.filter((q) => q.kind === 'face').map((q) => [q.step.id, q.step])).values()];
    this.selectStep(null);
    this.view.setSelectedFaces(steps.flatMap((s) => this.stepFaceIds(s.id)));
    const pts = ps.filter((q) => q.kind === 'point').map((q) => q.point);
    this.view.setMeasure(pts);
    const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2], xyz = (p) => [p.x, p.y, p.z].map((v) => fmt(+v.toFixed(3))).join(', ');
    const items = [];
    if (ps.length === 2) {
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
    const refs = `${t('in the 3D model')}: ${ps.map((q) => (q.kind === 'face' ? `${t('step')} ${q.step.id} “${q.step.name}” ${t('face')} ${q.face.name}` : `${t('the point')} (${xyz(q.point)})`)).join('; ')}`;
    const sg = showSuggest(this.els.viewport, `${ps.length} ${t('selected')}`, items, t('Ctrl+click: add more, or take one away'), refs);
    if (sg) sg.dataset.from = 'face';
  }

  /** Delete several steps at once (and the steps that need them, after asking). */
  removeSteps(ids) {
    if (this.mode !== 'part' || this.cmd) return;
    const gone = new Set(ids.flatMap((id) => [...this.dependents(id, false).gone]));
    const more = [...gone].filter((x) => !ids.includes(x)).map((x) => this.part.features.find((f) => f.id === x)?.name);
    if (more.length && !confirm(`${t('These steps need them and are deleted too')}: ${more.join(', ')}.`)) return;
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
    return `<div class="m-sizes"><span title="Which sizes are shown on the sketch and on the part">🏷 Sizes</span><div class="seg">${b('all', 'All', 'Every size')}${b('locked', '🔒 Locked', 'Only the sizes you locked (and a step\'s own, like an extrude\'s height)')}${b('none', 'None', 'No sizes — a clean view')}</div></div>`;
  }

  bindSizes(box) {
    for (const b of box.querySelectorAll('[data-sz]')) b.addEventListener('click', () => this.setSizeMode(b.dataset.sz));
    box.querySelector('[data-a=bigAll]')?.addEventListener('click', () => {
      const id = this.sk?.f?.id;
      if (this.bigAll.has(id)) this.bigAll.delete(id); else this.bigAll.add(id);
      this.setSizeMode(this.sizeMode);
    });
  }

  setSizeMode(m) {
    this.sizeMode = SIZE_MODES.includes(m) ? m : 'all';
    try { localStorage.setItem(SIZES_KEY, this.sizeMode); } catch { /* ignore */ }
    for (const b of document.querySelectorAll('.m-sizes [data-sz]')) b.classList.toggle('on', b.dataset.sz === this.sizeMode);
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
    const tags = [], lines = [];
    const add = (p, text, edit, title = '') => {
      const el = document.createElement('div');
      el.className = 'm-dimtag';
      el.textContent = text;
      el.title = title || 'Click to change it';
      for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
      el.addEventListener('click', (ev) => { ev.stopPropagation(); this.openDimEdit(el, edit); });
      tags.push({ p, el });
    };
    const P3 = (fr, u, v) => { const y = cross(fr.n, fr.x); return [0, 1, 2].map((i) => fr.o[i] + u * fr.x[i] + v * y[i]); };
    const f = step, num = (k, label, o = {}) => ({ get: () => f[k], set: (v) => { f[k] = v; }, label, field: k, stepId: f.id, ...o });
    const skOf = (id) => this.part.features.find((g) => g.id === id);
    const frameOf = (sk) => (sk?.plane?.datum ? datumFrame(sk.plane) : this.frames?.[sk?.id] || sk?.plane?.frame);
    if (f.type === 'extrude' || f.type === 'revolve') {
      const sk = skOf(f.sketch), fr = frameOf(sk);
      if (sk && fr) {
        this.sketchTags(sk, fr, add, P3);
        if (f.type === 'extrude' && !f.upto && !f.through) {
          const s = (f.op === 'cut' ? -1 : 1) * (f.flip ? -1 : 1), c = this.sketchCorner(sk);
          const a = P3(fr, c[0], c[1]), b = a.map((v, i) => v + fr.n[i] * f.d * s * (f.symmetric ? 0.5 : 1));
          lines.push([a, b]);
          add(b.map((v, i) => v + fr.n[i] * this.view.size * 0.02), `↕ ${fmt(f.d)}`, num('d', 'Height', { min: 0.1 }), `${f.name}: the height`);
        }
        if (f.type === 'revolve') add(P3(fr, 0, 0), `${fmt(f.angle)}°`, num('angle', 'Angle', { min: 1, max: 360, unit: '°' }));
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
          const r = f.from?.[i]?.[axis], c = r && this.refCoord(f, r, k);
          if (r && c !== null && c !== undefined) {
            const q = k === 0 ? [c, p[1]] : [p[0], c];
            lines.push([P3(fr, ...q), at]);
            add(P3(fr, (q[0] + p[0]) / 2, (q[1] + p[1]) / 2), `${k ? '↕' : '↔'} ${fmt(Math.abs(r.d))}`, {
              label: 'Distance', min: 0, get: () => Math.abs(r.d),
              set: (v) => { r.d = (Math.sign(r.d) || 1) * v; f.points[i][k] = +(c + r.d).toFixed(6); },
            });
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
      add(c, `${f.count}×`, num('count', 'How many', { min: 2, max: Math.max(20, f.count * 2), step: 1, int: true }));
      if (f.kind !== 'circular') add(c.map((v, i) => v + (i === 2 ? this.view.size * 0.05 : 0)), `${fmt(f.spacing)} apart`, num('spacing', 'Apart', { min: 0.1 }));
    }
    this.view.setTags(tags, lines);
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
        get: () => Math.abs(v), sketch: { id: sk0.id, spec } }, `${sk0.name}: ${d && !d.free ? 'locked' : 'click to type it (it is then locked)'}`);
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

  /** The editor of one size: a number and a slider; the part follows while sliding; Enter / OK keeps it, Esc goes back. */
  openDimEdit(el, edit) {
    this.closeDimEdit();
    const before = structuredClone(this.part.features);
    const v0 = edit.get(), step = edit.step || (Math.abs(v0) >= 20 ? 0.5 : 0.1);
    let lo = edit.min ?? 0.1, hi = edit.max ?? Math.max(10, Math.abs(v0) * 3);
    const box = document.createElement('div');
    box.className = 'm-dimedit';
    box.innerHTML = `<div class="m-dimedit-t">${esc(t(edit.label || 'Size'))}</div>
      <div class="m-dimedit-row"><input type="number" step="${step}" value="${fmt(v0)}"><span class="unit">${edit.unit || (edit.int ? '' : 'mm')}</span></div>
      <input type="range" min="${edit.int ? lo : 0}" max="${hi}" step="${edit.int ? 1 : step}" value="${v0}">
      <div class="m-dimedit-acts"><button class="btn small primary" data-a="ok">OK</button><button class="btn small" data-a="cancel">Cancel</button>
        <button class="btn small" data-a="restore" disabled title="${esc(t('Back to the size it had when this was opened'))}" data-no-i18n>↺ ${fmt(v0)}</button></div>`;
    const vr = this.els.viewport.getBoundingClientRect(), r = el.getBoundingClientRect();
    Object.assign(box.style, { left: `${Math.min(r.left - vr.left, vr.width - 220)}px`, top: `${Math.min(r.bottom - vr.top + 6, vr.height - 140)}px` });
    for (const t2 of ['pointerdown', 'pointerup']) box.addEventListener(t2, (ev) => ev.stopPropagation());
    this.els.viewport.appendChild(box);
    this.dimEdit = box;
    const num = box.querySelector('input[type=number]'), slider = box.querySelector('input[type=range]');
    if (edit.field && edit.stepId) { // the real range of this number of the step
      this.limitsFor(this.part.features, edit.stepId).then((lim) => {
        const r = lim[edit.field];
        if (!r || this.dimEdit !== box) return;
        [lo, hi] = r;
        Object.assign(slider, { min: String(lo), max: String(hi) });
        Object.assign(num, { min: String(lo), max: String(hi) });
        const tag = document.createElement('div');
        tag.className = 'mp-range';
        tag.textContent = `${fmt(lo)} – ${fmt(hi)}${edit.unit || (edit.int ? '' : ' mm')}`;
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
    const valid = (v) => Number.isFinite(v) && v <= hi && (edit.int ? Number.isInteger(v) && v >= lo : lo <= v || lo < 0);
    const back = box.querySelector('[data-a=restore]'), moved = () => { back.disabled = Math.abs(parseFloat(num.value) - v0) < 1e-9; };
    num.addEventListener('input', () => { const v = parseFloat(num.value); moved(); if (valid(v)) { slider.value = v; preview(v); } });
    slider.addEventListener('input', () => { const v = Math.max(parseFloat(slider.value), edit.min > 0 ? edit.min : 0); num.value = fmt(v); moved(); preview(v); });
    back.addEventListener('click', () => { num.value = fmt(v0); slider.value = v0; moved(); preview(v0); num.focus(); num.select(); }); // (the editor stays open)
    const ok = async () => {
      const v = parseFloat(num.value);
      if (!valid(v)) { this.hooks.toast('That size does not fit here.', 'warning'); return; }
      while (busy) await new Promise((res) => setTimeout(res, 20));
      this.closeDimEdit();
      if (await this.applyDim(edit, v, true) === false) { this.part.features = before; this.rebuild(); }
    };
    const cancel = async () => { while (busy) await new Promise((res) => setTimeout(res, 20)); this.closeDimEdit(); this.part.features = before; await this.rebuild(); this.reshowDims(); };
    num.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') ok(); if (e.key === 'Escape') cancel(); });
    box.querySelector('[data-a=ok]').addEventListener('click', ok);
    box.querySelector('[data-a=cancel]').addEventListener('click', cancel);
    setTimeout(() => { num.focus(); num.select(); }, 0);
  }

  closeDimEdit() { this.dimEdit?.remove(); this.dimEdit = null; }

  /** Put a size in: a step's own number, or a sketch's size (solved, with its locks). final = an undo step. */
  async applyDim(edit, v, final) {
    if (edit.sketch) {
      const sk = this.part.features.find((g) => g.id === edit.sketch.id);
      if (!sk) return false;
      const S = new Sketcher(this, structuredClone(upgradeSketch(sk)), false), spec = edit.sketch.spec;
      const f = S.f, cur = S.measure(spec);
      let value = v;
      if ((spec.t === 'dx' || spec.t === 'dy') && cur < 0) value = -Math.abs(v);
      const d = S.findDim(spec);
      if (d) { d.v = value; delete d.free; } else f.dims.push({ id: S.newId('d'), ...spec, v: value });
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
    } else edit.set(edit.int ? Math.round(v) : v);
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
    const endRefs = (x) => x && typeof x === 'object' && ((x.edge && (owns(x.edge.a) || owns(x.edge.b))) || (x.vertex?.faces || []).some(owns) || (x.point && owns(`${x.point}:`)));
    if ((f.dims || []).some((d) => endRefs(d.a) || endRefs(d.b))) return true;
    return (f.from || []).some((s) => s && ['x', 'y'].some((k) => s[k]?.edge && (owns(s[k].edge.a) || owns(s[k].edge.b))));
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
        if (x && typeof x === 'object' && ((x.edge && (owns(x.edge.a) || owns(x.edge.b))) || (x.vertex?.faces || []).some(owns) || (x.point && owns(`${x.point}:`)))) d[k] = { ref: x.ref };
      }
    }
    (g.from || []).forEach((s) => { for (const k of ['x', 'y']) if (s?.[k]?.edge && (owns(s[k].edge.a) || owns(s[k].edge.b))) delete s[k]; });
    if (g.upto && owns(this.faceOwner(g.upto) + ':')) { delete g.upto; g.d = g.d || 10; }
    if (this.pointOn(g, owns)) g.at = { xyz: [...(this.result?.points?.[g.id] || Object.values(g.at)[0]?.fp || [0, 0, 0])] }; // (a fixed place)
    return g;
  }

  /** Delete a step; steps that stand on it are asked about (how: 'keep' / 'all' answers it already — the AI). */
  /** A step dragged to another place in the list (before / after `toId`): refused when it would come before a step it
   *  uses (or after one that uses it); taken back when the model no longer builds there. -> moved */
  async moveStep(id, toId, after = false) {
    const fs = this.part.features, f = fs.find((x) => x.id === id), to = fs.find((x) => x.id === toId);
    if (!f || !to || f === to || this.mode !== 'part' || this.cmd) return false;
    const order = fs.filter((x) => x !== f);
    order.splice(order.indexOf(to) + (after ? 1 : 0), 0, f);
    if (order.every((x, i) => x === fs[i])) return false;
    const at = new Map(order.map((x, i) => [x.id, i]));
    for (const a of order) { // what uses a step must stay after it
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
    } else if (gone.size > 1 && !how && !confirm(`Delete “${name(id)}”? These steps need it and are deleted too: ${names.join(', ')}.`)) return;
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
        : ty === 'loft' || ty === 'sweep' ? this.renderProfiles(box) : ty === 'decal' ? this.renderDecal(box) : ty === 'mirror' ? this.renderMirror(box) : ty === 'draft' ? this.renderDraft(box) : ty === 'rib' ? this.renderRib(box) : ty === 'solid' ? this.renderSolid(box) : this.renderRound(box);
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
    const b = this.result?.body;
    if (!this.part.features.length) {
      box.innerHTML = `<h2>New 3D model</h2><p class="hint">Start with a sketch: draw a rectangle or a circle, then give it a height with Extrude.</p>
        <div class="row-actions"><button class="btn primary" data-a="sketch">✏ Start a sketch</button></div>`;
    } else {
      const bad = (this.result?.features || []).filter((s) => !s.ok);
      box.innerHTML = `<h2>Part</h2>
        ${b ? `<div class="mp-facts"><span>Size</span><b>${fmt(b.bbox[3] - b.bbox[0])} × ${fmt(b.bbox[4] - b.bbox[1])} × ${fmt(b.bbox[5] - b.bbox[2])} mm</b>
          <span>Volume</span><b>${fmt(b.volume / 1000)} cm³</b>
          <span>Mass</span><b>${fmt(+(b.volume / 1000 * (MATERIALS[this.part.material || 'PLA'])).toFixed(1))} g <span class="mp-sub">(solid)</span></b></div>
          <div class="field"><label>Material</label><select data-k="material">${MATERIAL_GROUPS.map(([g, ms]) => `<optgroup label="${esc(t(g))}">${ms.map(([k, rho]) => `<option value="${k}" ${k === (this.part.material || 'PLA') ? 'selected' : ''}>${esc(t(k))} — ${rho} g/cm³</option>`).join('')}</optgroup>`).join('')}</select></div>
          <div class="field"><label>Tolerances</label><select data-k="tolerance" title="The general tolerances (ISO 2768) for sizes without their own — on the 2D drawing">
            ${[['', '—'], ['f', 'ISO 2768-f (fine)'], ['m', 'ISO 2768-m (medium)'], ['c', 'ISO 2768-c (coarse)']].map(([v, l]) => `<option value="${v}" ${v === (this.part.tolerance || '') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
          <div class="field"><label>Colour</label><input type="color" data-k="color" value="${lookColor(this.part) || '#d9dee6'}" title="Its colour here and in assemblies (without one: its material's)"></div>
          <div class="field mp-look"><label>See-through</label><input type="range" min="0" max="90" step="5" data-k="clear" value="${Math.round((1 - (this.part.opacity ?? 1)) * 100)}"><span class="unit">${Math.round((1 - (this.part.opacity ?? 1)) * 100)} %</span></div>`
      : '<p class="hint">No solid yet — extrude a sketch.</p>'}
        ${bad.length ? `<p class="mp-bad">⚠ ${bad.length} step(s) could not be built — point at ⚠ in the list to see why.</p>` : ''}
        <h3>Next</h3><p class="hint">${esc(this.nextHint())}</p>
        <div class="row-actions wrap"><button class="btn small" data-a="sketch">✏ Sketch</button>
        ${this.sketches().length ? '<button class="btn small" data-a="extrude">⬆ Extrude</button>' : ''}</div>
        ${libraryFactsHtml(this.part.library)}
        ${this.part.libEdit && this.hooks.saveBackToLibrary ? `<div class="mp-libedit"><b>📚 ${esc(t('Library part'))}</b> <span data-no-i18n>${esc(this.part.libEdit.name || '')}</span>
          <p class="hint">${esc(t('You are changing a part of your library. Save it back to keep the change there — parts already in projects stay as they were.'))}</p>
          <div class="row-actions"><button class="btn small primary" data-a="saveBack">📚 ${esc(t('Save back to the library'))}</button></div></div>` : ''}
        ${this.hooks.saveToLibrary && this.part.features.length ? '<div class="row-actions"><button class="btn small" data-a="saveToLibrary" title="Keep this 3D model in your parts library (on the server) — to use it again in any project">📚 Save to the library</button></div>' : ''}
        ${this.hooks.duplicatePart ? '<div class="row-actions"><button class="btn small" data-a="duplicatePart" title="A copy of this 3D model as a new part of its own (its own tab) — change it without changing this one">⧉ Duplicate as a new part</button></div>' : ''}
        ${b && this.hooks.toPrint ? `<h3>3D print</h3><p class="hint">Check it fits your printer, split it into pieces with joints — in a printing copy of this part.</p>
          <div class="row-actions"><button class="btn small primary" data-a="toPrint">🖨 Prepare for 3D print</button></div>` : ''}
        ${b ? `<h3>Export</h3><div class="row-actions"><button class="btn small" data-x="stl" title="For 3D printing">STL</button>
          <button class="btn small" data-x="step" title="For other CAD programs (exact circles and faces)">STEP</button>
          <button class="btn small" data-x="pdf" title="A 2D drawing: front, top and right views, sizes, holes, title block">📐 Drawing (PDF)</button></div>
          ${this.hooks.newSheet ? '<div class="row-actions"><button class="btn small primary" data-a="newSheet" title="A drawing sheet of this part to edit: its views and dimensions (light / medium / full), moved, deleted, added — it follows the part when it changes">📄 Drawing sheet</button></div>' : ''}` : ''}`;
    }
    for (const el of box.querySelectorAll('[data-a]')) el.addEventListener('click', () => (el.dataset.a === 'newSheet' ? this.hooks.newSheet() : this.action(el.dataset.a)));
    for (const el of box.querySelectorAll('[data-x]')) el.addEventListener('click', () => this.export(el.dataset.x));
    box.querySelector('[data-k=material]')?.addEventListener('change', (e) => this.setMaterial(e.target.value));
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
    return null;
  }

  nextHint() {
    const used = new Set(this.part.features.flatMap(sketchesOf));
    if (this.sketches().some((s) => !used.has(s.id))) return 'A sketch is not used yet (bright lines in the view) — Extrude it, or double-click its lines to change it.';
    if (!this.result?.body) return 'Extrude a sketch to make the solid.';
    return 'Click ✏ Sketch, then a flat face of the part, to add a pocket or a boss — or ◎ Hole, ◜ Fillet, ◸ Chamfer. Double-click a step to change it.';
  }

  renderStatus() {
    const b = this.result?.body;
    this.$('.m-status').textContent = b ? `${fmt(b.bbox[3] - b.bbox[0])} × ${fmt(b.bbox[4] - b.bbox[1])} × ${fmt(b.bbox[5] - b.bbox[2])} mm · volume ${fmt(b.volume / 1000)} cm³` : '';
  }

  // ------------------------------------------------------------------ rebuild
  /** The features to show: the part, with the open command's preview, or rolled back to the open sketch. */
  shown() {
    const fs = this.part.features;
    if (this.mode === 'sketch' || this.mode === 'plane') {
      const i = this.sk && !this.sk.isNew ? fs.findIndex((f) => f.id === this.sk.f.id) : -1;
      return i >= 0 ? fs.slice(0, i) : fs;
    }
    if (this.cmd) {
      const f = this.cmd.feature;
      return this.cmd.isNew ? [...fs, f] : fs.map((g) => (g.id === f.id ? f : g));
    }
    return fs;
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
      this.rid = `m${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
      const timer = setTimeout(() => { this.$('.m-busy').hidden = false; }, 350);
      try {
        const res = await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features }, rid: this.rid }) });
        const r = await res.json();
        if (res.status === 501) { this.showInstall(r.error); continue; }
        if (!res.ok) throw new Error(r.error || res.statusText);
        if (r.cancelled) { this.hooks.toast('Cancelled — the model is shown as it was.', 'info'); continue; }
        this.result = r;
        this.applyUpdates(r);
        this.frames = { ...this.frames, ...r.frames }; // also while rolled back before an open sketch
        const first = !this.view.body && r.body;
        this.view.setBody(r.body);
        this.view.setLook({ ...this.part, color: lookColor(this.part) });
        this.view.setRefs(r.refs || []);
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
        this.$('.m-busy').hidden = true;
      }
    }
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
    for (const f of this.part.features) {
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
      ...this.sk.f.entities.filter((e) => e.t === 'block').flatMap((e) => this.sk.blockRings(e).flat())];
    const rs = this.sk.f.entities.filter((e) => e.t === 'circle').map((e) => [...(this.sk.P(e.c) || [0, 0]), e.r]);
    if (!ps.length) return Math.max(this.view.size * 1.4, 80);
    const ext = Math.max(...ps.map((p) => Math.max(Math.abs(p[0]), Math.abs(p[1]))), ...rs.map(([u, v, r]) => Math.max(Math.abs(u), Math.abs(v)) + r));
    return Math.max(ext * 2.2, 20);
  }

  finishSketch() {
    const f = this.sk.result();
    if (!f.entities.length) { this.hooks.toast('Draw a rectangle, lines or a circle first — or Cancel.', 'warning'); return; }
    const { isNew } = this.sk;
    if (isNew) this.part.features.push(f);
    else this.part.features = this.part.features.map((g) => (g.id === f.id ? f : g));
    this.leaveSketchMode();
    this.mode = 'part';
    this.hint('');
    this.history.commit();
    if (isNew) {
      this.openExtrude(this.newExtrude(f.id), true); // the obvious next step, ready to go
      return;
    }
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

  startExtrude() {
    if (this.mode !== 'part' || this.cmd) return;
    const used = new Set(this.part.features.flatMap(sketchesOf));
    const sks = this.sketches();
    if (!sks.length) { this.hooks.toast('Draw a sketch first (✏ Sketch).', 'warning'); return; }
    const sk = [...sks].reverse().find((s) => !used.has(s.id)) || sks[sks.length - 1];
    this.openExtrude(this.newExtrude(sk.id), true);
  }

  openExtrude(feature, isNew) {
    if (this.measuring) this.toggleMeasure();
    this.cmd = { feature, isNew };
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
      ${this.result?.body || f.upto ? `<div class="seg"><button data-upto="0" class="${!f.upto ? 'on' : ''}" title="A height you type">Distance</button><button data-upto="1" class="${f.upto ? 'on' : ''}" title="As far as a face of the part — it follows the face when the part changes">Up to a face</button></div>` : ''}
      ${f.upto ? `<p class="mp-count">${f.upto.name ? `Up to the face <b>${esc(this.faceLabel(f.upto.name))}</b>` : 'Click a flat face of the part (parallel to the sketch).'}</p>
        <div class="field"><label>Offset</label><input type="number" step="any" data-k="offset" value="${fmt(f.offset || 0)}"><span class="unit">mm</span></div>
        <p class="hint">Offset: more = past the face, less (negative) = short of it. Click another face to change it.</p>`
      : `<div class="field"><label>Distance</label><input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}" ${f.through ? 'disabled' : ''}><span class="unit">mm</span></div>
      ${f.op === 'cut' ? `<label class="check"><input type="checkbox" data-k="through" ${f.through ? 'checked' : ''}> Through all</label>` : ''}
      <label class="check"><input type="checkbox" data-k="symmetric" ${f.symmetric ? 'checked' : ''}> Both sides (symmetric)</label>
      <div class="row-actions"><button class="btn small" data-k="flip" title="Extrude to the other side of the sketch">⇅ Flip direction</button></div>`}
      ${sks.length > 1 ? `<div class="field"><label>Sketch</label><select data-k="sketch">${sks.map((s) => `<option value="${s.id}" ${s.id === f.sketch ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></div>` : ''}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>
      <p class="hint">The preview is in the 3D view. Enter = OK, Esc = Cancel.</p>`;
    const changed = () => { this.renderExtrude(box); this.rebuild(); };
    for (const b of box.querySelectorAll('[data-op]')) b.addEventListener('click', () => { f.op = b.dataset.op; if (f.op === 'add') f.through = false; changed(); });
    for (const b of box.querySelectorAll('[data-upto]')) {
      b.addEventListener('click', () => {
        if (b.dataset.upto === '1') { f.upto = f.upto || { name: null }; f.through = false; this.hint('Up to a face — click a flat face of the part. Enter = OK, Esc = Cancel.'); } else delete f.upto;
        changed();
      });
    }
    const d = box.querySelector('[data-k=d]') || box.querySelector('[data-k=offset]');
    d.addEventListener('input', () => {
      const v = parseFloat(d.value);
      if (d.dataset.k === 'offset' ? Number.isFinite(v) : v > 0) { f[d.dataset.k] = v; this.rebuild(); }
    });
    d.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okExtrude(); if (e.key === 'Escape') this.cancelExtrude(); });
    box.querySelector('[data-k=through]')?.addEventListener('change', (e) => { f.through = e.target.checked; changed(); });
    box.querySelector('[data-k=symmetric]')?.addEventListener('change', (e) => { f.symmetric = e.target.checked; changed(); });
    box.querySelector('[data-k=flip]')?.addEventListener('click', () => { f.flip = !f.flip; changed(); });
    box.querySelector('[data-k=sketch]')?.addEventListener('change', (e) => { f.sketch = e.target.value; changed(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okExtrude());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelExtrude());
    this.addSliders(box);
  }

  /** A slider under every number of a tool's panel: sliding types into the number (the part previews), typing
   *  moves the slider. Its range: from the number's min (or below 0 when it may be negative) to about 3× the value. */
  addSliders(box) {
    // the ranges known for these very settings (not the ones from before e.g. a pattern went round)
    if (this.cmd?.limits && this.cmd.limitsKey === this.limitsKey(this.shown(), this.cmd.feature.id)) setTimeout(() => this.applyLimits(box, this.cmd.limits), 0);
    for (const num of box.querySelectorAll('input[type=number]')) {
      if (num.dataset.slider || num.disabled) continue;
      num.dataset.slider = '1';
      const v0 = parseFloat(num.value) || 0, int = num.step === '1', deg = /°/.test(num.parentElement?.textContent || '') || num.dataset.k === 'angle';
      const lo = num.dataset.lo !== undefined ? +num.dataset.lo : num.min !== '' ? parseFloat(num.min) : -Math.max(10, Math.abs(v0) * 3);
      const hi = num.dataset.hi !== undefined ? +num.dataset.hi : deg ? 360 : int ? Math.max(20, v0 * 2) : Math.max(10, Math.abs(v0) * 3, lo + 1);
      const sl = document.createElement('input');
      Object.assign(sl, { type: 'range', min: String(Math.max(lo, int ? 2 : lo)), max: String(hi), step: num.dataset.step || (int ? '1' : hi > 50 ? '0.5' : '0.1'), value: String(v0) });
      sl.className = 'mp-slider';
      sl.title = 'Slide to change it — the part follows';
      sl.addEventListener('input', () => {
        num.value = fmt(Math.max(+sl.value, num.min !== '' ? +num.min : -Infinity));
        num.dispatchEvent(new Event('input', { bubbles: true }));
      });
      sl.addEventListener('change', () => num.dispatchEvent(new Event('change', { bubbles: true })));
      num.addEventListener('input', () => {
        const v = parseFloat(num.value), lo = num.min !== '' ? +num.min : -Infinity, hi = num.max !== '' ? +num.max : Infinity;
        if (Number.isFinite(v) && (v > hi || v < lo)) {
          num.value = fmt(Math.min(hi, Math.max(lo, v)));
          this.hooks.toast(t2('{v} is the most that works here (with what is around it).', { v: num.value }), 'info', 2500);
        }
      }, true);
      num.addEventListener('input', () => {
        const v = parseFloat(num.value);
        if (!Number.isFinite(v)) return;
        if (v > +sl.max) sl.max = String(v * 1.5);
        sl.value = String(v);
      });
      const row = num.closest('.field, .mp-hd, label') || num.parentElement;
      row.after(sl);
    }
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

  /** Numbers and sliders held to their ranges; the range shown under the slider; a value outside is pulled in. */
  applyLimits(box, lim) {
    for (const [k, [lo, hi]] of Object.entries(lim || {})) {
      for (const num of box.querySelectorAll(`input[type=number][data-k="${k}"]`)) {
        num.min = String(lo);
        num.max = String(hi);
        const sl = num.closest('.field, label, .mp-hd')?.nextElementSibling;
        if (sl?.classList.contains('mp-slider')) {
          const st = +sl.step || 0.1;
          sl.min = String(Math.floor(lo / st) * st); // on the step grid (0.01 would make 8 into 7.99); the number holds the min
          sl.max = String(hi);
          let tag = sl.nextElementSibling;
          if (!tag?.classList.contains('mp-range')) { tag = document.createElement('div'); tag.className = 'mp-range'; sl.after(tag); }
          tag.textContent = `${fmt(lo)} – ${fmt(hi)}${k === 'count' ? '' : k === 'angle' ? '°' : ' mm'}`;
        }
        const v = parseFloat(num.value);
        if (Number.isFinite(v) && (v > hi || v < lo)) {
          num.value = fmt(Math.min(hi, Math.max(lo, v)));
          num.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }
    }
  }

  okExtrude() { this.okCommand(); }

  okCommand() {
    const { feature: f, isNew } = this.cmd;
    if (f.type === 'extrude' && f.upto && !f.upto.name) { this.hooks.toast('Click the face to go up to first.', 'warning'); return; }
    if (f.type === 'extrude' && !f.upto && !f.through && !(f.d > 0)) { this.hooks.toast('The distance must be greater than zero.', 'error'); return; }
    if ((f.type === 'fillet' || f.type === 'chamfer') && !f.edges.length) { this.hooks.toast('Click at least one edge first.', 'warning'); return; }
    if (f.type === 'shell' && !f.faces.length) { this.hooks.toast('Click the face(s) to leave open first.', 'warning'); return; }
    if (f.type === 'decal' && (!f.plane || !f.polys)) { this.hooks.toast(f.plane ? 'Type some text, or choose a picture.' : 'Click on a flat face where it goes.', 'warning'); return; }
    if (f.type === 'hole' && !f.points.length) { this.hooks.toast('Click on a flat face where the hole goes.', 'warning'); return; }
    if (isNew) this.part.features.push(f);
    else this.part.features = this.part.features.map((g) => (g.id === f.id ? f : g));
    this.cmd = null;
    this.holePick = null;
    this.view.setEdgeHighlight();
    this.view.setHover(-1);
    this.view.setSketch(null);
    this.hint('');
    this.commit();
  }

  cancelExtrude() { this.cancelCommand(); }

  cancelCommand() {
    this.cmd = null;
    this.holePick = null;
    this.view.setSketch(null);
    this.view.setEdgeHighlight();
    this.view.setHover(-1);
    this.hint('');
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
    this.cmd = { feature, isNew };
    this.mode = 'part';
    this.selected = feature.id;
    this.hint(feature.type === 'revolve' ? 'Revolve — choose the axis and the angle; the preview is in the view. Enter = OK, Esc = Cancel.'
      : feature.type === 'shell' ? 'Shell — click the face(s) to leave open, give the wall thickness. Enter = OK, Esc = Cancel.'
      : feature.type === 'decal' ? 'Text / picture — click on a flat face where it goes (click again to move it). Enter = OK, Esc = Cancel.'
      : feature.type === 'loft' ? 'Loft — choose the sketch it starts from and the one it goes to. Enter = OK, Esc = Cancel.'
      : feature.type === 'sweep' ? 'Sweep — choose the outline (profile) and the path it moves along. Enter = OK, Esc = Cancel.'
      : feature.type === 'solid' ? 'Solid from a file — joined to the part, cut out of it, or a see-through reference. Enter = OK, Esc = Cancel.'
      : feature.type === 'mirror' ? 'Mirror — choose the plane, or click a flat face to mirror across it. Enter = OK, Esc = Cancel.'
      : feature.type === 'pattern' ? 'Pattern — how many and how far apart. Click an edge for the direction (or a round face for the axis). Enter = OK, Esc = Cancel.'
      : feature.type === 'hole' ? 'Hole — click on a flat face where it goes (click again for more holes). Enter = OK, Esc = Cancel.'
      : `${feature.type === 'fillet' ? 'Fillet' : 'Chamfer'} — click the edges (or a face: all its edges). Enter = OK, Esc = Cancel.`);
    this.render();
    this.rebuild();
  }

  /** An edge of the shown body -> a reference {a, b, fp}: the names of its two faces and its middle. */
  edgeRef(i) {
    const b = this.result?.body, e = b?.edges[i];
    if (!e || e.faces.length !== 2) return null;
    const [fa, fb] = e.faces.map((k) => b.faces[k]?.name);
    if (!fa || !fb) return null;
    if (fa.startsWith(`${this.cmd.feature.id}:`) || fb.startsWith(`${this.cmd.feature.id}:`)) return null; // made by this very step
    return { a: fa, b: fb, fp: e.mid };
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
    if (f.type === 'revolve') return null;
    const i = this.view.pickEdge(e.clientX, e.clientY);
    if (i >= 0) {
      const ref = this.edgeRef(i);
      if (!ref) return null;
      const k = f.edges.findIndex((r) => this.sameRef(r, ref));
      if (k >= 0) f.edges.splice(k, 1);
      else f.edges.push(ref);
    } else {
      // a face: all of its edges (that are not picked yet)
      const h = this.view.pick(e.clientX, e.clientY);
      if (!h?.face) return null;
      this.result.body.edges.forEach((ed, j) => {
        if (!ed.faces.includes(h.face.id)) return;
        const ref = this.edgeRef(j);
        if (ref && !f.edges.some((r) => this.sameRef(r, ref))) f.edges.push(ref);
      });
    }
    this.renderProps();
    this.rebuild();
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
    const what = { end: 'the top of', start: 'the bottom of', side: 'a wall of', hole: 'a hole of', round: 'a rounding of' }[role] || 'a face of';
    return g ? `${what} ${g.name}` : name;
  }

  clickHole(e) {
    const f = this.cmd.feature, h = this.view.pick(e.clientX, e.clientY);
    if (this.holePick) { this.pickHoleRef(e); return; }
    if (!h?.face) return;
    if (h.face.type !== 'plane') { this.hooks.toast('Holes go on flat faces — click a flat face.', 'warning'); return; }
    if (f.plane && (f.plane.face?.name !== h.face.name || h.face.normal.some((v, k) => Math.abs(v - f.plane.frame.n[k]) > 1e-6))) {
      this.hooks.toast('The holes of one step go on one face — press OK, then make another Hole for the other face.', 'warning', 6000);
      return;
    }
    if (!f.plane) f.plane = { face: h.face.ref || null, frame: h.face.frame };
    const fr = this.holeFrame(f); // the clicked face's frame (a later rebuild only moves it along its normal)
    const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
    const d = [h.point.x - o[0], h.point.y - o[1], h.point.z - o[2]];
    let u = d[0] * x[0] + d[1] * x[1] + d[2] * x[2], v = d[0] * y[0] + d[1] * y[1] + d[2] * y[2];
    // snap: to the face centre within ~10 px, else to a 0.5 mm grid
    const mpp = this.view.mmPerPixel(fr);
    if (Math.hypot(u, v) < mpp * 10 && !f.plane.origin) { u = 0; v = 0; } else { u = Math.round(u * 2) / 2; v = Math.round(v * 2) / 2; }
    f.points.push([u, v]);
    // placed from the nearest edges of the face (left / right and below / above): it keeps that distance
    // when the part changes (a step measured from a corner / the part's origin: from that)
    f.from = f.from || [];
    if (!f.plane.origin) f.from[f.points.length - 1] = this.nearestEdges(f, [u, v]);
    this.renderProps();
    this.rebuild();
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

  pickHoleRef(e) {
    const f = this.cmd.feature, { i, axis } = this.holePick, k = axis === 'x' ? 0 : 1;
    const idx = this.view.pickEdge(e.clientX, e.clientY), r = idx >= 0 && this.holeRefAt(idx);
    if (!r) { this.hooks.toast(axis === 'x' ? 'Click a straight edge running up / down on this face, or another hole.' : 'Click a straight edge running left / right on this face, or another hole.', 'info', 4000); return; }
    f.from = f.from || [];
    f.from[i] = { ...(f.from[i] || {}), [axis]: { ...(r.ref.hole !== undefined ? { hole: r.ref.hole } : { edge: r.ref }), d: +(f.points[i][k] - r.c).toFixed(6), ...(r.round ? { round: true } : {}) } };
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

  /** Where a hole's reference is now along axis k: another hole of this step, or an edge. */
  refCoord(f, r, k) { return r.hole !== undefined ? f.points[r.hole]?.[k] ?? null : this.edgeCoord(f, r.edge, k); }

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

  /** The hole's distances to its edges, drawn on the face: a dimension line from the edge to the centre. */
  drawHoleDims() {
    const f = this.cmd?.feature;
    if (!f || f.type !== 'hole' || !f.plane?.frame) { this.view.setSketch(null); return; }
    const fr = this.holeFrame(f), lines = [], labels = [], C = 0xd2a8ff, mpp = this.view.mmPerPixel(fr);
    f.points.forEach((p, i) => {
      for (const [axis, k] of [['x', 0], ['y', 1]]) {
        const r = f.from?.[i]?.[axis];
        if (!r) continue;
        const c = this.refCoord(f, r, k);
        if (c === null) continue;
        const a = k === 0 ? [c, p[1]] : [p[0], c];
        lines.push([a, p, C]);
        const el = document.createElement('div');
        el.className = 'sk-label hole-dim';
        el.textContent = fmt(Math.abs(r.d));
        labels.push({ el, u: (a[0] + p[0]) / 2 + (k === 1 ? mpp * 12 : 0), v: (a[1] + p[1]) / 2 + (k === 0 ? mpp * 10 : 0) });
      }
    });
    this.view.setSketch(fr, { lines, labels, grid: 0 });
  }

  /** After a rebuild moved holes (their edges moved), show the new numbers without retyping. */
  syncHoleInputs() {
    const f = this.cmd.feature, box = this.$('.mp-body');
    for (const el of box.querySelectorAll('[data-u]')) if (document.activeElement !== el) el.value = fmt(f.points[+el.dataset.u][0]);
    for (const el of box.querySelectorAll('[data-v]')) if (document.activeElement !== el) el.value = fmt(f.points[+el.dataset.v][1]);
  }

  /** One row of a hole's position: "↔ 12 mm from the left edge ⇄", or x / y from the face's centre (no edge there). */
  holeDimRow(f, i, axis, k) {
    const r = f.from?.[i]?.[axis], p = f.points[i];
    if (!r) return `<label class="mp-hd">${axis} <input type="number" step="any" data-${k ? 'v' : 'u'}="${i}" value="${fmt(p[k])}"> <span class="hint">${FROM_TEXT[originKey(f.plane?.origin)] || 'from the reference point'}</span></label>`;
    const side = r.round ? (k === 0 ? (r.d >= 0 ? 'right of the hole' : 'left of the hole') : (r.d >= 0 ? 'above the hole' : 'below the hole'))
      : k === 0 ? (r.d >= 0 ? 'from the left edge' : 'from the right edge') : (r.d >= 0 ? 'from the lower edge' : 'from the upper edge');
    const picking = this.holePick?.i === i && this.holePick?.axis === axis;
    return `<label class="mp-hd">${k ? '↕' : '↔'} <input type="number" step="any" min="0" data-hd="${i}:${axis}" value="${fmt(Math.abs(r.d))}"> <span>mm ${side}</span>
      <button type="button" class="mini" data-flip="${i}:${axis}" title="Measure from the edge on the other side">⇄</button>
      <button type="button" class="mini ${picking ? 'on' : ''}" data-pickref="${i}:${axis}" title="Measure from another edge or hole: click it in the view">🎯</button></label>`;
  }

  renderRound(box) {
    const f = this.cmd.feature, st = this.status(f.id), fillet = f.type === 'fillet', k = fillet ? 'r' : 'd';
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <p class="hint">${fillet ? 'Click the edges to round' : 'Click the edges to bevel'} — click a face to take all of its edges, click a picked edge again to drop it.</p>
      <div class="field"><label>${fillet ? 'Radius' : 'Size'}</label><input type="number" step="any" min="0" data-k="${k}" value="${fmt(f[k])}"><span class="unit">mm</span></div>
      <p class="mp-count">${f.edges.length ? `${f.edges.length} edge(s) picked` : 'No edges picked yet'}</p>
      ${f.edges.length ? '<div class="row-actions"><button class="btn small" data-a="clear">Drop all edges</button></div>' : ''}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : st?.warnings?.length ? `<p class="mp-warn">⚠ ${esc(st.warnings.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>
      <p class="hint">The preview is in the 3D view. Enter = OK, Esc = Cancel.</p>`;
    const inp = box.querySelector(`[data-k=${k}]`);
    inp.addEventListener('input', () => { const v = parseFloat(inp.value); if (v > 0) { f[k] = v; this.rebuild(); } });
    inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
    box.querySelector('[data-a=clear]')?.addEventListener('click', () => { f.edges = []; this.renderProps(); this.rebuild(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  renderHole(box) {
    const f = this.cmd.feature, st = this.status(f.id);
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <p class="hint">Click on a flat face where a hole goes — click again for more holes on the same face. A click near the face's centre snaps to it.</p>
      ${f.plane?.face ? `<div class="field m-holefrom"><label>From</label>${originSeg(f.plane, f.plane.origin ? originKey(f.plane.origin) : f.from?.some((x) => x?.x || x?.y) ? 'edges' : '', '', HOLE_ORIGINS)}</div>` : ''}
      <div class="field"><label>Thread</label><select data-k="thread" title="A threaded hole: drilled with its tap drill (M5: Ø4.2), labelled M5 on the drawing">
        ${['', ...Object.keys(THREADS)].map((v) => `<option value="${v}" ${v === (f.thread || '') ? 'selected' : ''}>${v || '—'}</option>`).join('')}</select></div>
      <div class="field"><label>Diameter</label><input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}" ${f.thread ? 'disabled' : ''}><span class="unit">mm</span></div>
      <label class="check"><input type="checkbox" data-k="through" ${f.through !== false ? 'checked' : ''}> Through all</label>
      ${f.through === false ? `<div class="field"><label>Depth</label><input type="number" step="any" min="0" data-k="depth" value="${fmt(f.depth)}"><span class="unit">mm</span></div>` : ''}
      <div class="field"><label>Head</label><select data-k="head" title="Room for a screw's head: ⌴ a counterbore (a socket head sunk in), ⌵ a countersink (a flat head flush with the face)">
        ${[['', '—'], ['cbore', '⌴ Counterbore'], ['csk', '⌵ Countersink']].map(([v, l]) => `<option value="${v}" ${v === (f.head || '') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      ${f.head ? `<div class="field"><label>Head Ø</label><input type="number" step="any" min="0" data-k="head_d" value="${fmt(f.head_d)}"><span class="unit">mm</span></div>` : ''}
      ${f.head === 'cbore' ? `<div class="field"><label>Head depth</label><input type="number" step="any" min="0" data-k="head_depth" value="${fmt(f.head_depth)}"><span class="unit">mm</span></div>` : ''}
      <div class="field"><label>Fit</label><select data-k="fit" title="An ISO 286 fit for the hole — shown on the 2D drawing (Ø8 H7 and its deviations); the model keeps the nominal size">
        ${['', 'H6', 'H7', 'H8', 'H9'].map((v) => `<option value="${v}" ${v === (f.fit || '') ? 'selected' : ''}>${v || '—'}</option>`).join('')}</select></div>
      ${f.points.length ? `<h3>Holes</h3><div class="mp-holes">${f.points.map((p, i) => `<div class="mp-hole">
        <span>${i + 1}</span><div class="mp-hole-dims">${['x', 'y'].map((axis, k) => this.holeDimRow(f, i, axis, k)).join('')}</div>
        <button class="mini danger" data-del="${i}" title="Remove this hole">✕</button></div>`).join('')}</div>
        <p class="hint">${f.plane?.origin === 'corner' ? 'The holes keep their distances from the corner — they follow it when the part changes.'
          : f.plane?.origin ? 'The holes stay where these numbers put them, also when the part changes.'
          : 'Each hole keeps its distance from the edge it is measured from, also when the part changes. ⇄ measures from the other side.'}</p>`
        : '<p class="mp-count">No holes yet — click on a face.</p>'}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const num = (el, set) => {
      el.addEventListener('input', () => { const v = parseFloat(el.value); if (Number.isFinite(v)) { set(v); this.rebuild(); } });
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
    };
    num(box.querySelector('[data-k=d]'), (v) => { if (v > 0) f.d = v; });
    const dep = box.querySelector('[data-k=depth]');
    if (dep) num(dep, (v) => { if (v > 0) f.depth = v; });
    box.querySelector('[data-k=through]').addEventListener('change', (e) => { f.through = e.target.checked; this.renderProps(); this.rebuild(); });
    box.querySelector('[data-k=fit]').addEventListener('change', (e) => { if (e.target.value) f.fit = e.target.value; else delete f.fit; });
    box.querySelector('[data-k=thread]').addEventListener('change', (e) => { // (its tap drill as the diameter)
      if (e.target.value) Object.assign(f, { thread: e.target.value, d: THREADS[e.target.value] }); else delete f.thread;
      this.renderProps();
      this.rebuild();
    });
    box.querySelector('[data-k=head]').addEventListener('change', (e) => { // (a screw head's room, sized from the hole: ISO 4762 / 10642-like)
      const h = e.target.value;
      delete f.head; delete f.head_d; delete f.head_depth;
      if (h) Object.assign(f, { head: h, head_d: +(f.d * (h === 'cbore' ? 1.8 : 2)).toFixed(1) }, h === 'cbore' ? { head_depth: +(+f.d).toFixed(1) } : {});
      this.renderProps();
      this.rebuild();
    });
    for (const k of ['head_d', 'head_depth']) { const el = box.querySelector(`[data-k=${k}]`); if (el) num(el, (v) => { if (v > 0) f[k] = v; }); }
    for (const el of box.querySelectorAll('[data-u]')) num(el, (v) => { f.points[+el.dataset.u][0] = v; });
    for (const el of box.querySelectorAll('[data-v]')) num(el, (v) => { f.points[+el.dataset.v][1] = v; });
    // a distance from an edge: typed as a positive number, the hole stays on its side of the edge
    for (const el of box.querySelectorAll('[data-hd]')) {
      const [i, axis] = el.dataset.hd.split(':'), k = axis === 'x' ? 0 : 1;
      num(el, (v) => {
        const r = f.from[+i][axis], c = this.refCoord(f, r, k);
        if (v < 0 || c === null) return;
        r.d = (Math.sign(r.d) || 1) * v;
        f.points[+i][k] = +(c + r.d).toFixed(6);
        this.drawHoleDims();
      });
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
    if (!sks.length) { this.hooks.toast('Draw a sketch first (✏ Sketch).', 'warning'); return; }
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
    a.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
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
    tIn.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
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
    if (!h?.face || h.face.type !== 'plane' || h.face.name?.startsWith(`${f.id}:`)) { this.hooks.toast('Click a flat face of the part.', 'info', 3000); return; }
    const same = f.plane && f.plane.face?.name === h.face.name;
    if (!same) f.plane = { face: h.face.ref || { name: h.face.name }, frame: h.face.frame };
    const fr = f.plane.frame, o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
    const dd = [h.point.x - o[0], h.point.y - o[1], h.point.z - o[2]];
    let u = dd[0] * x[0] + dd[1] * x[1] + dd[2] * x[2], v = dd[0] * y[0] + dd[1] * y[1] + dd[2] * y[2];
    const mpp = this.view.mmPerPixel(fr);
    if (Math.hypot(u, v) < mpp * 12) { u = 0; v = 0; } else { u = Math.round(u * 2) / 2; v = Math.round(v * 2) / 2; } // near the centre: on it
    f.at = [u, v];
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
      <p class="hint">${f.plane ? 'Click on the face again to move it — near the face\'s centre it snaps to it.' : 'Click on a flat face of the part where it goes.'}</p>
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
    const txt = box.querySelector('[data-k=text]');
    if (txt) {
      let timer = null;
      txt.addEventListener('input', () => { f.text = txt.value; clearTimeout(timer); timer = setTimeout(() => this.traceDecal(), 350); });
      txt.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
    }
    for (const inp of box.querySelectorAll('[data-at], [data-k=angle]')) { // where on the face, and turned
      inp.addEventListener('input', () => {
        const v = parseFloat(String(inp.value).replace(',', '.'));
        if (!Number.isFinite(v)) return;
        if (inp.dataset.at !== undefined) { f.at = [...(f.at || [0, 0])]; f.at[+inp.dataset.at] = v; } else f.angle = v;
        this.rebuild();
      });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
    }
    for (const k of ['h', 'depth']) {
      const inp = box.querySelector(`[data-k=${k}]`);
      inp.addEventListener('input', () => { const v = parseFloat(inp.value); if (v > 0) { f[k] = v; this.rebuild(); } });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
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

  // ------------------------------------------------------------------ a solid from a file (STEP / STL / OBJ)
  pickSolid() {
    if (this.mode !== 'part' || this.cmd || !this.hooks.importSolid) return;
    const inp = document.createElement('input');
    Object.assign(inp, { type: 'file', accept: '.step,.stp,.stl,.obj' });
    inp.addEventListener('change', async () => {
      const file = inp.files[0];
      if (!file) return;
      let r;
      try { r = await this.hooks.importSolid(file); } catch (e) { this.hooks.toast(e.message.replace(/^MESH_TOO_BIG /, ''), 'error', 9000); return; }
      if (this.mode !== 'part' || this.cmd) return;
      // with a part there: a reference to build around (a cover, a holder); else the part itself
      this.openCommand({ id: this.newId(), type: 'solid', name: r.name.replace(/\.[^.]+$/, ''), blob: r.blob, file: r.file || r.name, op: this.result?.body ? 'ref' : 'add' }, true);
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
      <div class="field"><label>Across</label><div class="seg">${Object.entries(MIRROR_PLANES).map(([k, v]) => `<button data-pl="${k}" class="${f.plane?.datum === k ? 'on' : ''}" title="${esc(t(v))}">${k}</button>`).join('')}</div></div>
      <p class="hint">${f.plane?.datum ? `${esc(t(MIRROR_PLANES[f.plane.datum]))} — ${esc(t('or click a flat face to mirror across it.'))}` : esc(t('Across the face you clicked (click another one to change it).'))}</p>
      ${body ? `<div class="seg big"><button data-copy="1" class="${f.copy !== false ? 'on' : ''}">⇋ Mirror and copy</button><button data-copy="0" class="${f.copy === false ? 'on' : ''}">↦ Mirror only</button></div>
        <p class="hint">${f.copy !== false ? 'The part and its mirror image, joined.' : 'The part turned into its mirror image.'}</p>` : '<p class="hint">The step is copied to the other side (holes stay holes).</p>'}
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}${st?.warnings?.length ? `<p class="mp-warn">${esc(st.warnings.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.renderProps(); this.rebuild(); };
    box.querySelector('[data-k=of]').addEventListener('change', (e) => { f.of = e.target.value; if (f.of !== 'body') f.copy = true; changed(); });
    for (const b of box.querySelectorAll('[data-pl]')) b.addEventListener('click', () => { f.plane = { datum: b.dataset.pl }; changed(); });
    for (const b of box.querySelectorAll('[data-copy]')) b.addEventListener('click', () => { f.copy = b.dataset.copy === '1'; changed(); });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Rib
  startRib() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const used = new Set(this.part.features.flatMap(sketchesOf)), sks = this.sketches();
    const sk = [...sks].reverse().find((s) => !used.has(s.id) && (s.entities || []).some((e) => e.t === 'line' && !e.construction));
    if (!sk) { this.hooks.toast('Draw the rib\'s line first: a sketch on a plane across the corner, one line from the wall to the plate.', 'warning', 6000); return; }
    this.openCommand({ id: this.newId(), type: 'rib', name: this.nextName('rib', sk.id), sketch: sk.id, t: 3 }, true);
  }

  renderRib(box) {
    const f = this.cmd.feature, st = this.status(f.id), sks = this.sketches();
    box.innerHTML = `<h2>${esc(f.name)}</h2>
      <div class="field"><label>Sketch</label><select data-k="sketch">${sks.map((g) => `<option value="${g.id}" ${g.id === f.sketch ? 'selected' : ''} data-no-i18n>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Thickness</label><input type="number" step="any" min="0" data-k="t" value="${fmt(f.t)}"><span class="unit">mm</span></div>
      <p class="hint">${esc(t('Its line is filled up to the part, on the side where it closes, half the thickness each side of the sketch plane.'))}</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
      <div class="mp-actions"><button class="btn primary" data-a="ok">OK</button><button class="btn" data-a="cancel">Cancel</button></div>`;
    const changed = () => { this.rebuild().then(() => { if (this.cmd?.feature === f) this.renderProps(); }); };
    box.querySelector('[data-k=sketch]').addEventListener('change', (e) => { f.sketch = e.target.value; changed(); });
    const th = box.querySelector('[data-k=t]');
    th.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') th.blur(); });
    th.addEventListener('change', () => { const v = parseFloat(String(th.value).replace(',', '.')); if (v > 0) { f.t = v; changed(); } });
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
  }

  // ------------------------------------------------------------------ Draft
  /** The extrudes whose side walls a draft can tilt (before step `before`). */
  draftable(before = null) {
    const at = before ? this.part.features.findIndex((x) => x.id === before) : -1;
    return this.part.features.filter((g) => g.type === 'extrude' && !g.suppressed && (at < 0 || this.part.features.indexOf(g) < at));
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
      <div class="field"><label>Angle</label><input type="number" step="0.5" data-k="angle" value="${fmt(f.angle)}"><span class="unit">°</span></div>
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
  repeatable() { return this.part.features.filter((f) => REPEATABLE.has(f.type) && !f.suppressed); }

  startPattern() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    const rs = this.repeatable();
    if (!rs.length) { this.hooks.toast('Make something to repeat first — a hole, a boss or a cut.', 'warning'); return; }
    // the newest hole or cut is the usual thing to repeat, else the newest step
    const last = [...rs].reverse().find((f) => f.type === 'hole' || f.op === 'cut') || rs[rs.length - 1];
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
    this.rebuild();
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
      <div class="field"><label>Repeat</label><select data-k="of">${rs.map((g) => `<option value="${g.id}" ${g.id === f.features[0] ? 'selected' : ''}>${esc(g.name)}</option>`).join('')}</select></div>
      <div class="field"><label>How many</label><input type="number" step="1" min="2" data-k="count" value="${f.count}"></div>
      ${circ ? '' : `<div class="field"><label>Apart</label><input type="number" step="any" min="0" data-k="spacing" value="${fmt(f.spacing)}"><span class="unit">mm</span></div>`}
      <div class="field"><label>${circ ? 'Around' : 'Direction'}</label><div class="seg">${Object.keys(AXES).map((a) => `<button data-ax="${a}" class="${ax === a ? 'on' : ''}">${a.toUpperCase()}</button>`).join('')}${circ ? '' : '<button data-a="flipDir" title="The other way">⇄</button>'}</div></div>
      <p class="hint">${circ ? (ax ? 'Evenly around the axis through the origin. Or click a round face (a hole, a shaft) to go around its axis.' : 'Evenly around the axis of the round face you clicked.')
        : (ax ? 'Or click a straight edge in the view to go along it.' : 'Along the edge you clicked.')}</p>
      ${st && !st.ok ? `<p class="mp-bad">⚠ ${esc(st.issues.join(' '))}</p>` : ''}
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
    box.querySelector('[data-k=of]').addEventListener('change', (e) => { f.features = [e.target.value]; changed(); });
    for (const k of ['count', 'spacing']) {
      const inp = box.querySelector(`[data-k=${k}]`);
      if (!inp) continue;
      inp.addEventListener('input', () => {
        const v = parseFloat(inp.value);
        if (v > 0 && (k !== 'count' || (Number.isInteger(v) && v >= 2))) { f[k] = v; this.rebuild(); }
      });
      inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') this.okCommand(); if (e.key === 'Escape') this.cancelCommand(); });
    }
    box.querySelector('[data-a=ok]').addEventListener('click', () => this.okCommand());
    box.querySelector('[data-a=cancel]').addEventListener('click', () => this.cancelCommand());
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
    this.view.setMeasure();
    this.hint(this.measuring ? 'Measure — click a face or an edge for its size, or two spots for the distance between them. Esc ends.' : '');
    if (!this.measuring) { this.$('.m-measure')?.remove(); this.view.setSnapMark(null); }
    this.renderCmdBar();
  }

  measureBox(html) {
    let box = this.$('.m-measure');
    if (!box) {
      box = document.createElement('div');
      box.className = 'm-measure';
      this.els.viewport.appendChild(box);
    }
    box.innerHTML = html;
  }

  clickMeasure(e) {
    const ms = this.measuring, b = this.result?.body;
    if (!b) return;
    const f3 = (p) => `${fmt(p.x)}, ${fmt(p.y)}, ${fmt(p.z)}`;
    // an edge under the mouse: its length / diameter (when no point is picked yet)
    const ei = this.view.pickEdge(e.clientX, e.clientY, 6);
    const mp = this.view.measurePoint(e.clientX, e.clientY);
    if (!mp && ei < 0) return;
    if (!ms.a) {
      let what = '';
      if (ei >= 0 && !mp?.snap) {
        const ed = b.edges[ei];
        let L = 0;
        for (let k = 3; k < ed.pts.length; k += 3) L += Math.hypot(ed.pts[k] - ed.pts[k - 3], ed.pts[k + 1] - ed.pts[k - 2], ed.pts[k + 2] - ed.pts[k - 1]);
        const P = []; for (let k = 0; k < ed.pts.length; k += 3) P.push(ed.pts.slice(k, k + 3));
        if (P.length > 2 && Math.hypot(...P[0].map((x, i) => x - P[P.length - 1][i])) < 1e-6) P.pop(); // a closed loop: its first point twice
        const c = P.reduce((s, p) => s.map((x, i) => x + p[i] / P.length), [0, 0, 0]);
        const rs = P.map((p) => Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2])), r0 = rs.reduce((s, x) => s + x, 0) / rs.length;
        const round = P.length > 8 && rs.every((x) => Math.abs(x - r0) < r0 * 0.01 + 1e-6) && Math.abs(L - 2 * Math.PI * r0) < L * 0.02;
        what = round ? `<b>Circular edge</b><span>Ø</span><b>${fmt(2 * r0)} mm</b>` : `<b>Edge</b><span>Length</span><b>${fmt(L)} mm</b>`;
      } else if (mp?.face) {
        const f = mp.face;
        what = `<b>${f.type === 'cylinder' ? 'Round face' : f.type === 'plane' ? 'Flat face' : 'Face'}</b><span>Area</span><b>${fmt(f.area)} mm²</b>${f.radius ? `<span>Ø</span><b>${fmt(2 * f.radius)} mm</b>` : ''}`;
      }
      ms.a = mp?.point || null;
      this.view.setMeasure(ms.a ? [ms.a] : []);
      this.measureBox(`<div class="mm-rows">${what}${ms.a ? `<span>${{ corner: 'Corner', midpoint: 'Midpoint', centre: 'Centre' }[mp.snap] || 'Point'}</span><b>${f3(ms.a)}</b>` : ''}</div>
        <p class="hint">Click a second spot for the distance.</p>`);
      return;
    }
    if (!mp) return;
    const a = ms.a, p = mp.point, d = a.distanceTo(p);
    this.view.setMeasure([a, p], `${fmt(d)} mm`);
    this.measureBox(`<div class="mm-rows"><b>Distance</b><span></span><b>${fmt(d)} mm</b>
      <span>Δx</span><b>${fmt(Math.abs(p.x - a.x))}</b><span>Δy</span><b>${fmt(Math.abs(p.y - a.y))}</b><span>Δz</span><b>${fmt(Math.abs(p.z - a.z))}</b></div>
      <p class="hint">Click again to measure from a new spot.</p>`);
    ms.a = null;
  }

  toggleSection() {
    if (!this.result?.body) return;
    if (this.section) {
      this.section = null;
      this.view.setSection(null);
      this.$('.m-section')?.remove();
    } else {
      const bb = this.result.body.bbox;
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
    cv.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || (e.buttons & ~1)) { down = null; return; } // the left button alone
      down = { x: e.clientX, y: e.clientY, drag: null };
      if (this.mode === 'sketch') {
        down.drag = this.sk.down(e);
        if (down.drag) cv.setPointerCapture(e.pointerId);
      }
    });
    cv.addEventListener('pointermove', (e) => {
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
        } else if (f.type === 'decal' || f.type === 'mirror') {
          const h = this.view.pick(e.clientX, e.clientY), ok = h?.face?.type === 'plane' && !h.face.name?.startsWith(`${f.id}:`);
          this.view.setHover(ok ? h.face.id : -1);
          cv.style.cursor = ok ? 'crosshair' : '';
        } else if (f.type === 'hole' && this.holePick) {
          const i = this.view.pickEdge(e.clientX, e.clientY), ok = i >= 0 && this.holeRefAt(i);
          this.view.setEdgeHighlight(ok ? i : -1, []);
          cv.style.cursor = ok ? 'pointer' : '';
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
        } else if (f.type === 'hole') {
          const h = this.view.pick(e.clientX, e.clientY);
          this.view.setHover(h?.face?.type === 'plane' ? h.face.id : -1);
          cv.style.cursor = h?.face?.type === 'plane' ? 'crosshair' : '';
        } else {
          const i = this.view.pickEdge(e.clientX, e.clientY), ok = i >= 0 && this.edgeRef(i);
          this.view.setEdgeHighlight(ok ? i : -1, this.refEdges(f.edges));
          const h = ok ? null : this.view.pick(e.clientX, e.clientY);
          this.view.setHover(h?.face ? h.face.id : -1);
          cv.style.cursor = ok || h?.face ? 'pointer' : '';
        }
      } else if (this.mode === 'part' && !this.cmd && !down) {
        const id = this.view.pickOutline(e.clientX, e.clientY);
        if (id) { this.view.clearHoverMarks(); this.view.setHover(-1); this.tip(null); cv.style.cursor = 'pointer'; cv.title = 'Double-click to edit this sketch'; return; }
        cv.title = '';
        if (this.measuring) { this.view.clearHoverMarks(); this.view.setSnapMark(this.view.measurePoint(e.clientX, e.clientY)); return; } // (where a click measures from)
        this.view.setSnapMark(this.view.measurePoint(e.clientX, e.clientY)); // (a corner, an edge's middle, a centre: it can be picked)
        // the step under the mouse: all its faces light up, its name at the mouse
        const h = this.view.pick(e.clientX, e.clientY), fs = h?.face && this.stepFaces(h.face);
        this.view.setHover(h?.face ? h.face.id : -1, fs?.ids || null);
        this.hoverMarks(e, fs);
        this.tip(fs ? { x: e.clientX, y: e.clientY, text: `${fs.step.name} — ${this.faceLabel(h.face.name).replace(/ of .*$/, '').replace(/^the /, '')}` } : null);
        cv.style.cursor = h?.face ? 'pointer' : '';
      }
    });
    cv.addEventListener('pointerup', (e) => {
      if (e.button !== 0 || !down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4;
      const drag = down.drag;
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
    cv.addEventListener('pointerleave', () => { this.view.clearHoverMarks(); if (this.mode === 'part' && !this.cmd) { this.view.setHover(-1); this.tip(null); } });
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
    if (this.ctx && e.key === 'Escape') { this.closeCtx(); return; }
    if (this.mode === 'sketch') {
      if (e.key === 'Enter') { this.finishSketch(); return; }
      this.sk.key(e);
      return;
    }
    if (this.mode === 'plane') { if (e.key === 'Escape') this.cancelPlane(); return; }
    if (this.cmd) {
      if (e.key === 'Escape') this.cancelCommand();
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
    if (await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.${fmtName}`)) {
      this.hooks.toast(fmtName === 'pdf' ? 'Exported the drawing (PDF).' : `Exported ${fmtName.toUpperCase()} (in mm).`, 'ok');
    }
  }

  hasBody() { return !!this.result?.body; }

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

  /** A printing copy of this part: its STL opened as a Quick part (printer fit, splitting, joints). */
  async toPrint() {
    const res = await fetch('/api/model/export/stl', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part: this.part, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json()).error}`, 'error'); return; }
    await this.hooks.toPrint(await res.blob());
  }
}
