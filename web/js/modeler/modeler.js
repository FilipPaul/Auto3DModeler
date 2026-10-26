// The 3D model workspace: sketches (rectangles, lines, circles drawn with the mouse on a plane or a flat face,
// sizes locked 🔒 by typing them — sketcher.js)
// turned into a solid by Extrude (add material / cut), step by step in a feature tree — like Solid Edge or
// SolidWorks, but only the few tools that need almost no input (docs/ARCHITECTURE-modeler.md, §3).
// The server's CAD kernel builds the body (/api/model/rebuild); this module edits the part JSON.
import { History } from '../history.js';
import { t } from '../i18n.js';
import { ModelView, DATUMS, datumFrame } from './view.js';
import { Sketcher, upgradeSketch, arcPts } from './sketcher.js';

const ICON = { sketch: '✏', extrude: '⬆', cut: '⬇', revolve: '⟳', fillet: '◜', chamfer: '◸', hole: '◎', shell: '▢', pattern: '⁂', loft: '⧫', sweep: '〰', solid: '▣' };
const TYPE_NAME = { sketch: 'Sketch', extrude: 'Extrude', revolve: 'Revolve', fillet: 'Fillet', chamfer: 'Chamfer', hole: 'Hole', shell: 'Shell', pattern: 'Pattern',
  loft: 'Loft', sweep: 'Sweep', solid: 'Solid' };
const REPEATABLE = new Set(['extrude', 'revolve', 'hole', 'pattern', 'loft', 'sweep']);
const AXES = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };
const USES_SKETCH = new Set(['extrude', 'revolve', 'loft', 'sweep']);
/** The sketches a step is made from. */
const sketchesOf = (f) => (f.type === 'loft' ? f.sketches || [] : f.type === 'sweep' ? [f.profile, f.path] : USES_SKETCH.has(f.type) ? [f.sketch] : []).filter(Boolean);
// densities for the mass (g/cm³), common 3D-printing materials
export const MATERIALS = { PLA: 1.24, PETG: 1.27, ABS: 1.04, ASA: 1.07, TPU: 1.21, PA: 1.14 };
const DATUM_NAME = { XY: 'Top', XZ: 'Front', YZ: 'Right' };
const fmt = (v) => (+(+v).toFixed(3)).toString();
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
      capture: () => ({ features: this.part.features }),
      restore: async (s) => { this.part.features = s.features; this.closeAll(); this.render(); await this.rebuild(); },
      onChange: () => this.updateUndo(),
    });
    this.build();
    this.view = new ModelView(this.els.view);
    this.view.onCamera = () => this.sk?.draw();
    this.bindPointer();
    this.render();
  }

  // ------------------------------------------------------------------ DOM
  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = `
      <div class="mt-head"><b>Model</b><span class="mt-sub">steps, from the first to the last</span></div>
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

  renderCmdBar() {
    const bar = this.$('.m-cmdbar');
    const btn = (a, label, title, cls = '') => `<button class="chip ${cls}" data-a="${a}" title="${esc(title)}">${label}</button>`;
    if (this.mode === 'sketch') {
      const t = this.sk.tool;
      // a new, empty sketch on a base plane can still move to another base plane
      const dat = this.sk.isNew && !this.sk.f.entities.length && this.sk.f.plane?.datum;
      const planes = dat ? `<span class="m-say">on</span>${['XY', 'XZ', 'YZ'].map((k) => btn(`plane-${k}`, DATUM_NAME[k], `Sketch on the ${DATUM_NAME[k]} plane`, k === dat ? 'on' : '')).join('')}<span class="sep"></span>` : '';
      const onDatum = this.sk.f.plane?.datum;
      const offset = onDatum ? `<label class="m-offset" title="Move the sketch plane along its normal (e.g. 30 mm above the bed — for a loft's second profile)">Offset
        <input type="number" step="any" data-k="planeOffset" value="${fmt(this.sk.f.plane.offset || 0)}"> mm</label><span class="sep"></span>` : '';
      bar.innerHTML = `<span class="m-mode">Sketch</span>${planes}${offset}
        ${btn('rect', '▭ Rectangle', 'Draw a rectangle: click two corners (R)', t === 'rect' ? 'on' : '')}
        ${btn('line', '⟋ Line', 'Draw lines: click point after point; click the first point to close the shape (L)', t === 'line' ? 'on' : '')}
        ${btn('circle', '◯ Circle', 'Draw a circle: click the centre, then the edge (C)', t === 'circle' ? 'on' : '')}
        ${btn('arc', '◠ Arc', 'Draw an arc: click where it starts and ends, then bend it with the mouse and click (A)', t === 'arc' ? 'on' : '')}
        ${btn('round', '◜ Round corner', 'Round a corner of lines: click the corner, type the radius (F)', t === 'round' ? 'on' : '')}
        ${btn('trim', '✂ Trim', 'Cut away a piece of a line, circle or arc — up to where other shapes cross it (T)', t === 'trim' ? 'on' : '')}
        ${this.hooks.pickOutline ? btn('outline', '🖼 Outline', 'Insert an outline from a picture, a DXF / DWG drawing or a PDF drawing (as one shape you can move and size)') : ''}
        ${btn('dim', '↔ Dimension', 'Add a distance: click two points, circles, lines or edges of the part, then type the value (D)', t === 'dim' ? 'on' : '')}
        ${btn('select', '⬚ Select', 'Select a shape or a corner to move it (drag) or delete it (Esc)', t === 'select' ? 'on' : '')}
        <span class="sep"></span>
        ${btn('finish', '✓ Finish sketch', 'Done drawing — next: Extrude (Enter)', 'primary')}
        ${btn('cancelSketch', '✕ Cancel', 'Leave the sketch without changing the part')}`;
    } else if (this.mode === 'plane') {
      bar.innerHTML = `<span class="m-mode">Sketch on…</span><span class="m-say">click a flat face of the part — or a plane:</span>
        ${btn('datum-XY', 'Top', 'Sketch on the Top plane (XY)')}${btn('datum-XZ', 'Front', 'Sketch on the Front plane (XZ)')}${btn('datum-YZ', 'Right', 'Sketch on the Right plane (YZ)')}
        <span class="sep"></span>${btn('cancelPlane', '✕ Cancel', 'Do not start a sketch (Esc)')}`;
    } else {
      const canExtrude = this.sketches().length > 0;
      bar.innerHTML = `
        ${btn('sketch', '✏ Sketch', 'Start a sketch: on a plane, or on a flat face of the part (S)', 'tool')}
        ${btn('extrude', '⬆ Extrude', canExtrude ? 'Give a sketch a height: add material or cut (E)' : 'Draw a sketch first', 'tool')}
        ${btn('revolve', '⟳ Revolve', canExtrude ? 'Spin a sketch around an axis (vases, knobs, wheels)' : 'Draw a sketch first', 'tool')}
        ${btn('loft', '⧫ Loft', 'A shape from one outline to another (e.g. a square base to a round top): two sketches, one above the other', 'tool')}
        ${btn('sweep', '〰 Sweep', 'Move an outline along a path (pipes, handles, rails): a profile sketch and a path sketch', 'tool')}
        ${btn('fillet', '◜ Fillet', 'Round edges: click the edges, give the radius (F)', 'tool')}
        ${btn('chamfer', '◸ Chamfer', 'Bevel edges: click the edges, give the size', 'tool')}
        ${btn('hole', '◎ Hole', 'Drill holes: click on a flat face where they go, give the diameter (H)', 'tool')}
        ${btn('shell', '▢ Shell', 'Hollow the part out: click the face(s) to leave open, give the wall thickness', 'tool')}
        ${btn('pattern', '⁂ Pattern', 'Repeat a step (holes, a boss, a cut) in a row or around a circle: give how many and how far apart', 'tool')}
        <span class="sep"></span>
        <button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
        <span class="sep"></span>
        ${btn('measure', '📏 Measure', 'Measure: click a face or an edge (its size), or two spots (the distance between them) (M)', this.measuring ? 'on' : '')}
        ${btn('section', '✂ Section', 'Look inside: cut the view along X, Y or Z', this.section ? 'on' : '')}
        <span class="sep"></span>
        ${btn('view-iso', 'Iso', 'View from the front-right, above')}${btn('view-top', 'Top', 'View from above')}${btn('view-front', 'Front', 'View from the front')}${btn('view-right', 'Right', 'View from the right')}`;
      bar.querySelector('[data-a=extrude]').disabled = !canExtrude || !!this.cmd;
      bar.querySelector('[data-a=sketch]').disabled = !!this.cmd;
      for (const a of ['fillet', 'chamfer', 'hole', 'shell', 'pattern']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body || !!this.cmd;
      bar.querySelector('[data-a=revolve]').disabled = !canExtrude || !!this.cmd;
      for (const a of ['loft', 'sweep']) bar.querySelector(`[data-a=${a}]`).disabled = this.sketches().length < 2 || !!this.cmd;
      for (const a of ['measure', 'section']) bar.querySelector(`[data-a=${a}]`).disabled = !this.result?.body;
    }
    for (const b of bar.querySelectorAll('[data-a]')) b.addEventListener('click', () => this.action(b.dataset.a));
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
    if (a === 'section') return this.toggleSection();
    if (a === 'shell') return this.startShell();
    if (a === 'pattern') return this.startPattern();
    if (a === 'loft' || a === 'sweep') return this.startProfiles(a);
    if (a === 'undo') return this.history.go(-1);
    if (a === 'redo') return this.history.go(1);
    if (a.startsWith('view-')) return this.view.setView(a.slice(5));
    if (a.startsWith('datum-')) return this.enterSketch({ datum: a.slice(6) });
    if (a.startsWith('plane-')) return this.movePlane(a.slice(6));
    if (a === 'cancelPlane') return this.cancelPlane();
    if (['rect', 'line', 'circle', 'arc', 'round', 'trim', 'select', 'dim'].includes(a)) return this.sk.setTool(a);
    if (a === 'outline') return this.insertOutline();
    if (a === 'finish') return this.finishSketch();
    if (a === 'cancelSketch') return this.cancelSketch();
    return null;
  }

  toast(...a) { this.hooks.toast(...a); }

  hint(text) {
    const h = this.$('.m-hint');
    h.hidden = !text;
    h.textContent = text || '';
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
        <span class="mt-acts"><button class="mini" data-a="off" title="${f.suppressed ? 'Turn this step on again' : 'Turn this step off for now (it is kept)'}">${f.suppressed ? '◌' : '●'}</button><button class="mini" data-a="edit" title="Change this step (or double-click it)">✎</button><button class="mini danger" data-a="del" title="Delete this step">✕</button></span>`;
      row.querySelector('.mt-name').textContent = f.name;
      row.querySelector('.mt-what').textContent = f.suppressed ? 'off' : this.whatText(f);
      if (st && !st.ok) row.title = st.issues.join(' ');
      else if (warn) row.title = st.warnings.join(' ');
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'edit') return this.edit(f.id);
        if (a === 'del') return this.remove(f.id);
        if (a === 'off') return this.toggleOff(f.id);
        this.selected = f.id;
        this.renderTree();
        return null;
      });
      row.addEventListener('dblclick', () => this.edit(f.id));
      tree.appendChild(row);
    }
  }

  whatText(f) {
    const n = (k) => (f[k] || []).length;
    if (f.type === 'sketch') return this.planeText(f);
    if (f.type === 'extrude' && f.upto) return `${f.op === 'cut' ? 'cut ' : ''}up to a face${f.offset ? ` ${f.offset > 0 ? '+' : ''}${fmt(f.offset)} mm` : ''}`;
    if (f.type === 'extrude') return f.op === 'cut' ? (f.through ? 'cut through all' : `cut ${fmt(f.d)} mm`) : `${fmt(f.d)} mm`;
    if (f.type === 'fillet') return `R ${fmt(f.r)} · ${n('edges')} edge(s)`;
    if (f.type === 'chamfer') return `${fmt(f.d)} mm · ${n('edges')} edge(s)`;
    if (f.type === 'hole') return `Ø${fmt(f.d)} · ${n('points')} hole(s)${f.through === false ? ` · ${fmt(f.depth)} deep` : ''}`;
    if (f.type === 'revolve') return `${fmt(f.angle)}°${f.op === 'cut' ? ' cut' : ''}`;
    if (f.type === 'shell') return `wall ${fmt(f.t)} mm · ${n('faces')} open`;
    if (f.type === 'loft') return `${(f.sketches || []).length} sketches${f.op === 'cut' ? ' · cut' : ''}`;
    if (f.type === 'sweep') return `along ${this.part.features.find((g) => g.id === f.path)?.name || '?'}${f.op === 'cut' ? ' · cut' : ''}`;
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

  toggleOff(id) {
    if (this.mode !== 'part' || this.cmd) return;
    const f = this.part.features.find((g) => g.id === id);
    if (!f) return;
    if (f.suppressed) delete f.suppressed;
    else f.suppressed = true;
    this.commit();
  }

  nextName(type) {
    const base = t(TYPE_NAME[type] || type); // named in the language on screen
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
    else if (f.type === 'extrude') this.openExtrude(structuredClone(f), false);
    else this.openCommand(structuredClone(f), false);
  }

  /** Delete a step and the steps that need it (an extrude of a deleted sketch, a sketch on its faces). */
  remove(id) {
    if (this.mode !== 'part' || this.cmd) return;
    const gone = new Set([id]);
    for (const f of this.part.features) {
      const onFace = gone.has(this.faceOwner(f.plane?.face));
      const onEdge = (f.edges || []).some((e) => gone.has(this.faceOwner({ name: e.a })) || gone.has(this.faceOwner({ name: e.b })));
      const onFaces = (f.faces || []).some((r) => gone.has(this.faceOwner(r)));
      const repeats = (f.type === 'pattern' && (f.features || []).some((x) => gone.has(x))) || gone.has(this.faceOwner(f.upto));
      if (sketchesOf(f).some((x) => gone.has(x)) || onFace || onEdge || onFaces || repeats) gone.add(f.id);
    }
    const names = this.part.features.filter((f) => gone.has(f.id)).map((f) => f.name);
    if (gone.size > 1 && !confirm(`Delete “${names[0]}”? These steps need it and are deleted too: ${names.slice(1).join(', ')}.`)) return;
    this.part.features = this.part.features.filter((f) => !gone.has(f.id));
    this.selected = null;
    this.commit();
  }

  // ------------------------------------------------------------------ property panel
  renderProps() {
    const box = this.$('.mp-body');
    if (this.cmd) {
      const ty = this.cmd.feature.type;
      return ty === 'extrude' ? this.renderExtrude(box) : ty === 'hole' ? this.renderHole(box) : ty === 'revolve' ? this.renderRevolve(box)
        : ty === 'shell' ? this.renderShell(box) : ty === 'pattern' ? this.renderPattern(box)
        : ty === 'loft' || ty === 'sweep' ? this.renderProfiles(box) : this.renderRound(box);
    }
    if (this.mode === 'sketch') {
      box.innerHTML = this.sk.propsHtml();
      box.querySelector('[data-a=delSel]')?.addEventListener('click', () => this.sk.deleteSel());
      for (const b of box.querySelectorAll('[data-del]')) b.addEventListener('click', () => this.sk.delDim(b.dataset.del));
      for (const b of box.querySelectorAll('[data-lock]')) b.addEventListener('click', () => this.sk.toggleLock(this.sk.f.dims.find((d) => d.id === b.dataset.lock)));
      box.querySelector('[data-a=showSizes]')?.addEventListener('click', () => this.sk.showAllSizes());
      for (const inp of box.querySelectorAll('input[data-bk]')) {
        inp.addEventListener('change', () => this.sk.setBlock(inp.dataset.bk, inp.value));
        inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); });
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
          <div class="field"><label>Material</label><select data-k="material">${Object.keys(MATERIALS).map((k) => `<option ${k === (this.part.material || 'PLA') ? 'selected' : ''}>${k}</option>`).join('')}</select></div>`
      : '<p class="hint">No solid yet — extrude a sketch.</p>'}
        ${bad.length ? `<p class="mp-bad">⚠ ${bad.length} step(s) could not be built — point at ⚠ in the list to see why.</p>` : ''}
        <h3>Next</h3><p class="hint">${esc(this.nextHint())}</p>
        <div class="row-actions wrap"><button class="btn small" data-a="sketch">✏ Sketch</button>
        ${this.sketches().length ? '<button class="btn small" data-a="extrude">⬆ Extrude</button>' : ''}</div>
        ${b && this.hooks.toPrint ? `<h3>3D print</h3><p class="hint">Check it fits your printer, split it into pieces with joints — in a printing copy of this part.</p>
          <div class="row-actions"><button class="btn small primary" data-a="toPrint">🖨 Prepare for 3D print</button></div>` : ''}
        ${b ? `<h3>Export</h3><div class="row-actions"><button class="btn small" data-x="stl" title="For 3D printing">STL</button>
          <button class="btn small" data-x="step" title="For other CAD programs (exact circles and faces)">STEP</button></div>` : ''}`;
    }
    for (const el of box.querySelectorAll('[data-a]')) el.addEventListener('click', () => this.action(el.dataset.a));
    for (const el of box.querySelectorAll('[data-x]')) el.addEventListener('click', () => this.export(el.dataset.x));
    box.querySelector('[data-k=material]')?.addEventListener('change', (e) => { this.part.material = e.target.value; this.history.commit(); this.renderProps(); });
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
        if (first && this.mode === 'part') this.view.setView('iso');
        this.view.showDatums(!r.body || this.mode === 'plane');
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
      for (const e of sk.entities.filter((x) => x.t === 'block')) {
        const k = e.scale || 1, [au, av] = e.at || [0, 0];
        for (const poly of e.polys || []) for (const r of poly) for (let i = 0; i < r.length; i++) {
          const a = r[i], b = r[(i + 1) % r.length];
          lines.push([[au + k * a[0], av + k * a[1]], [au + k * b[0], av + k * b[1]]]);
        }
      }
      list.push({ id: f.id, frame: fr, lines, circles, dim: used.has(f.id) });
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
    this.view.showDatums(true);
    this.hint('Click a flat face of the part to sketch on it — or choose Top / Front / Right above. Esc cancels.');
    this.render();
  }

  cancelPlane() {
    this.mode = 'part';
    this.view.setHover(-1);
    this.view.showDatums(!this.result?.body);
    this.hint('');
    this.render();
  }

  // ------------------------------------------------------------------ sketch mode (sketcher.js does the drawing)
  enterSketch(plane, existing = null) {
    const feature = existing ? structuredClone(existing)
      : { id: this.newId(), type: 'sketch', name: this.nextName('sketch'), plane, points: {}, entities: [], constraints: [], dims: [] };
    this.sk = new Sketcher(this, feature, !existing);
    this.mode = 'sketch';
    this.showOutlines();
    this.view.setHover(-1);
    this.view.showDatums(false);
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
    return this.frames?.[f.id] || f.plane.frame;
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
    return { id: this.newId(), type: 'extrude', name: this.nextName('extrude'), sketch: sketchId, op: onFace ? 'cut' : 'add',
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
  }

  okExtrude() { this.okCommand(); }

  okCommand() {
    const { feature: f, isNew } = this.cmd;
    if (f.type === 'extrude' && f.upto && !f.upto.name) { this.hooks.toast('Click the face to go up to first.', 'warning'); return; }
    if (f.type === 'extrude' && !f.upto && !f.through && !(f.d > 0)) { this.hooks.toast('The distance must be greater than zero.', 'error'); return; }
    if ((f.type === 'fillet' || f.type === 'chamfer') && !f.edges.length) { this.hooks.toast('Click at least one edge first.', 'warning'); return; }
    if (f.type === 'shell' && !f.faces.length) { this.hooks.toast('Click the face(s) to leave open first.', 'warning'); return; }
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
    if (this.measuring) this.toggleMeasure();
    this.cmd = { feature, isNew };
    this.mode = 'part';
    this.selected = feature.id;
    this.hint(feature.type === 'revolve' ? 'Revolve — choose the axis and the angle; the preview is in the view. Enter = OK, Esc = Cancel.'
      : feature.type === 'shell' ? 'Shell — click the face(s) to leave open, give the wall thickness. Enter = OK, Esc = Cancel.'
      : feature.type === 'loft' ? 'Loft — choose the sketch it starts from and the one it goes to. Enter = OK, Esc = Cancel.'
      : feature.type === 'sweep' ? 'Sweep — choose the outline (profile) and the path it moves along. Enter = OK, Esc = Cancel.'
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
    const fr = f.plane.frame; // the clicked face's frame (a later rebuild only moves it along its normal)
    const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
    const d = [h.point.x - o[0], h.point.y - o[1], h.point.z - o[2]];
    let u = d[0] * x[0] + d[1] * x[1] + d[2] * x[2], v = d[0] * y[0] + d[1] * y[1] + d[2] * y[2];
    // snap: to the face centre within ~10 px, else to a 0.5 mm grid
    const mpp = this.view.mmPerPixel(fr);
    if (Math.hypot(u, v) < mpp * 10) { u = 0; v = 0; } else { u = Math.round(u * 2) / 2; v = Math.round(v * 2) / 2; }
    f.points.push([u, v]);
    // placed from the nearest edges of the face (left / right and below / above): it keeps that distance
    // when the part changes
    f.from = f.from || [];
    f.from[f.points.length - 1] = this.nearestEdges(f, [u, v]);
    this.renderProps();
    this.rebuild();
  }

  /** The hole's face as it is now (the rebuild follows it when it moves), else where it was clicked. */
  holeFrame(f) { return this.result?.frames?.[f.id] || f.plane?.frame || null; }

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
    if (!r) return `<label class="mp-hd">${axis} <input type="number" step="any" data-${k ? 'v' : 'u'}="${i}" value="${fmt(p[k])}"> <span class="hint">from the face's centre</span></label>`;
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
      <div class="field"><label>Diameter</label><input type="number" step="any" min="0" data-k="d" value="${fmt(f.d)}"><span class="unit">mm</span></div>
      <label class="check"><input type="checkbox" data-k="through" ${f.through !== false ? 'checked' : ''}> Through all</label>
      ${f.through === false ? `<div class="field"><label>Depth</label><input type="number" step="any" min="0" data-k="depth" value="${fmt(f.depth)}"><span class="unit">mm</span></div>` : ''}
      ${f.points.length ? `<h3>Holes</h3><div class="mp-holes">${f.points.map((p, i) => `<div class="mp-hole">
        <span>${i + 1}</span><div class="mp-hole-dims">${['x', 'y'].map((axis, k) => this.holeDimRow(f, i, axis, k)).join('')}</div>
        <button class="mini danger" data-del="${i}" title="Remove this hole">✕</button></div>`).join('')}</div>
        <p class="hint">Each hole keeps its distance from the edge it is measured from, also when the part changes. ⇄ measures from the other side.</p>`
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
    this.openCommand({ id: this.newId(), type: 'revolve', name: this.nextName('revolve'), sketch: sk.id, axis: 'y', angle: 360, op: 'add' }, true);
  }

  startShell() {
    if (this.mode !== 'part' || this.cmd || !this.result?.body) return;
    this.openCommand({ id: this.newId(), type: 'shell', name: this.nextName('shell'), faces: [], t: 2 }, true);
  }

  renderRevolve(box) {
    const f = this.cmd.feature, sks = this.sketches(), st = this.status(f.id);
    const sk = this.part.features.find((g) => g.id === f.sketch);
    const lines = upgradeSketch(sk || { entities: [] }).entities.filter((e) => e.t === 'line');
    const axes = [['y', "The sketch's vertical axis"], ['x', "The sketch's horizontal axis"], ...lines.map((e, i) => [e.id, `Line ${i + 1} of the sketch`])];
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


  // ------------------------------------------------------------------ Loft / Sweep
  /** A sketch that is an open line (a path): its lines / arcs have loose ends and no circles. */
  isPath(sk) {
    const f = upgradeSketch(sk), n = {};
    for (const e of f.entities) {
      if (e.t === 'circle' || e.t === 'block') return false;
      if (e.t === 'line' || e.t === 'arc') for (const p of [e.a, e.b]) n[p] = (n[p] || 0) + 1;
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

  // ------------------------------------------------------------------ measure, section
  toggleMeasure() {
    if (this.mode !== 'part' || this.cmd) return;
    this.measuring = this.measuring ? null : { a: null };
    this.view.setMeasure();
    this.hint(this.measuring ? 'Measure — click a face or an edge for its size, or two spots for the distance between them. Esc ends.' : '');
    if (!this.measuring) this.$('.m-measure')?.remove();
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
      if (ei >= 0 && !mp?.corner) {
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
      this.measureBox(`<div class="mm-rows">${what}${ms.a ? `<span>${mp.corner ? 'Corner' : 'Point'}</span><b>${f3(ms.a)}</b>` : ''}</div>
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
      this.section = { axis: 'y', offset: +((bb[1] + bb[4]) / 2).toFixed(3), flip: false };
      this.view.setSection(this.section);
      this.renderSection();
    }
    this.renderCmdBar();
  }

  renderSection() {
    const s = this.section, bb = this.result?.body?.bbox;
    if (!s || !bb) return;
    const i = { x: 0, y: 1, z: 2 }[s.axis], lo = bb[i], hi = bb[i + 3];
    let box = this.$('.m-section');
    if (!box) { box = document.createElement('div'); box.className = 'm-section'; this.els.viewport.appendChild(box); }
    box.innerHTML = `<span>✂</span><div class="seg">${['x', 'y', 'z'].map((a) => `<button data-ax="${a}" class="${a === s.axis ? 'on' : ''}">${a.toUpperCase()}</button>`).join('')}</div>
      <input type="range" min="${lo}" max="${hi}" step="${(hi - lo) / 200 || 0.1}" value="${s.offset}"><b>${fmt(s.offset)} mm</b>
      <button class="mini" data-flip title="Show the other side">⇄</button><button class="mini" data-x title="No section">✕</button>`;
    for (const b of box.querySelectorAll('[data-ax]')) b.addEventListener('click', () => {
      s.axis = b.dataset.ax;
      const k = { x: 0, y: 1, z: 2 }[s.axis];
      s.offset = +((bb[k] + bb[k + 3]) / 2).toFixed(3);
      this.view.setSection(s);
      this.renderSection();
    });
    const r = box.querySelector('input');
    r.addEventListener('input', () => { s.offset = +r.value; box.querySelector('b').textContent = `${fmt(s.offset)} mm`; this.view.setSection(s); });
    box.querySelector('[data-flip]').addEventListener('click', () => { s.flip = !s.flip; this.view.setSection(s); });
    box.querySelector('[data-x]').addEventListener('click', () => this.toggleSection());
  }

  // ------------------------------------------------------------------ mouse and keys
  bindPointer() {
    const cv = this.view.renderer.domElement;
    let down = null;
    cv.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
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
      if (this.mode === 'sketch') this.sk.move(e, down?.drag || null);
      else if (this.mode === 'part' && this.cmd && !down && (!USES_SKETCH.has(this.cmd.feature.type) || this.cmd.feature.upto)) {
        const f = this.cmd.feature;
        if (f.type === 'extrude') {
          const h = f.upto ? this.view.pick(e.clientX, e.clientY) : null, ok = h?.face?.type === 'plane' && !h.face.name?.startsWith(`${f.id}:`);
          this.view.setHover(ok ? h.face.id : -1);
          cv.style.cursor = ok ? 'pointer' : '';
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
        cv.style.cursor = id ? 'pointer' : '';
        cv.title = id ? 'Double-click to edit this sketch' : '';
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
      return null;
    });
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
      const plane = { frame: h.face.frame };
      if (h.face.ref) plane.face = h.face.ref;
      this.enterSketch(plane);
    } else if (h?.datum) this.enterSketch({ datum: h.datum });
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    if (document.querySelector('.wizard, .lightbox')) return;
    const k = e.key.toLowerCase();
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
    if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')) { e.preventDefault(); this.history.go(k === 'y' || e.shiftKey ? 1 : -1); return; }
    if (k === 'm') this.toggleMeasure();
    if (k === 's' && !e.ctrlKey) this.startSketch();
    if (k === 'e') this.startExtrude();
    if (k === 'f') this.startRound('fillet');
    if (k === 'h') this.startHole();
    if (e.key === 'Delete' && this.selected) this.remove(this.selected);
  }

  // ------------------------------------------------------------------ the part as a project tab
  load(data, { then } = {}) {
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
    if (await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.${fmtName}`)) this.hooks.toast(`Exported ${fmtName.toUpperCase()} (in mm).`, 'ok');
  }

  hasBody() { return !!this.result?.body; }

  /** The body's mass in grams (solid), with the part's material. */
  massGrams() { const b = this.result?.body; return b ? +(b.volume / 1000 * MATERIALS[this.part.material || 'PLA']).toFixed(2) : null; }

  setMaterial(name) {
    if (!MATERIALS[name]) throw new Error(`material is one of ${Object.keys(MATERIALS).join(', ')}.`);
    this.part.material = name;
    this.history.commit();
    this.renderProps();
  }

  /** A printing copy of this part: its STL opened as a Quick part (printer fit, splitting, joints). */
  async toPrint() {
    const res = await fetch('/api/model/export/stl', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part: this.part, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json()).error}`, 'error'); return; }
    await this.hooks.toPrint(await res.blob());
  }
}
