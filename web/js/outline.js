// Picture -> outline wizard: detect candidate outlines, let the user steer the detection
// (object / background colours, a click inside the object, 'not this' points, a box around the
// object), combine candidates and edit the outline by hand (brush, eraser, lasso, polygon),
// then give its real size.
const NS = 'http://www.w3.org/2000/svg';
const COLORS = ['#ff2d95', '#3fb950', '#58a6ff', '#f2cc60', '#a371f7', '#ff7b72', '#39d0d8', '#ffa657', '#e6e9ee', '#7ee787'];
const EDIT_COLOR = '#ff2d95';
const CURRENT_COLOR = '#ffffff'; // the outline the part is made from
const MAX_UPLOAD = 1600;
const fmt = (v) => (+(+v).toFixed(2)).toString();

const HINT_TOOLS = {
  object: 'Click colours that belong to the object',
  background: 'Click colours of the background',
  seed: 'Click inside the object you want — only outlines containing the point are kept',
  notthis: 'Click on something that is NOT the object (background, shadow, a neighbour) — outlines containing it are dropped',
  box: 'Drag a box around the object — everything outside is treated as background',
  measure: 'Click two points to measure — in picture pixels and, with the size set, in mm',
};
// edit tools draw a shape; the edit mode says what the shape does to the outline
const EDIT_TOOLS = {
  brush: 'Drag to paint',
  lasso: 'Drag a freehand loop',
  poly: 'Click corner points — double-click, Enter or a click on the first point closes it · Backspace / right-click removes the last point',
};
const EDIT_MODES = {
  add: ['＋ Add', 'adds it to the outline', '#ff2d95'],
  remove: ['− Remove', 'removes it from the outline', '#ff7b72'],
  keep: ['✂ Cut out', 'keeps only what is inside it (cut the object out)', '#f2cc60'],
};

function svgEl(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent?.appendChild(e);
  return e;
}

const pathOf = (polys) => polys.map((poly) => poly.map((ring) => `M${ring.map((p) => p.join(',')).join('L')}Z`).join('')).join('');
const hex = ([r, g, b]) => `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`;

/** Load an image file (any browser-readable format, incl. SVG) as a data URL of at most MAX_UPLOAD px. */
export async function imageToDataURL(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('not an image')); i.src = url; });
    const w0 = img.naturalWidth || 800, h0 = img.naturalHeight || 800;
    const s = Math.min(1, MAX_UPLOAD / Math.max(w0, h0));
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w0 * s));
    c.height = Math.max(1, Math.round(h0 * s));
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    return { url: c.toDataURL('image/png'), width: c.width, height: c.height, canvas: c };
  } finally { URL.revokeObjectURL(url); }
}

export class OutlineWizard {
  constructor({ api, toast }) {
    this.api = api;
    this.toast = toast;
    this.hints = { count: 6, tolerance: 0, smoothing: 1, holes: false, object_colors: [], background_colors: [], seeds: [], bg_seeds: [], rect: null };
  }

  /** Open for a picture. Resolves to {polygons, img_w, img_h, width, height, preset, image, source,
   *  editor: {mask, hints}} or null.
   *  current: the outline in use ({polygons, mask, hints} — the editor state saved with the project):
   *  it is listed first and selected, the painted edit and the detection hints are restored. */
  async open(file, { replace = false, size = null, current = null, purpose = 'part' } = {}) {
    let img;
    try { img = await imageToDataURL(file.url ? await (await fetch(file.url)).blob() : file); } catch (e) {
      this.toast(`Could not open the picture: ${e.message}`, 'error');
      return null;
    }
    this.img = img;
    this.source = file.name || file.source || 'image.png';
    this.replace = replace;
    this.purpose = purpose; // 'part' (make a part) or 'layer' (a design-layer mask)
    this.userSized = false;
    this.sizeTouched = null;
    this.size = size;
    this.cands = [];
    this.edit = null;      // the hand-edited candidate (from the mask)
    this.current = null;   // the outline the part is made from (when reopened)
    this.mask = null;      // canvas: white = object
    this.undo = [];
    this.sel = 0;
    this.tool = null;
    this.poly = [];        // pending polygon points
    // hints belong to a picture: a new picture starts clean, a reopened one gets its own back
    Object.assign(this.hints, { count: 6, tolerance: 0, smoothing: 1, holes: false, object_colors: [], background_colors: [],
      seeds: [], bg_seeds: [], rect: null }, structuredClone(current?.hints || {}));
    this.build();
    if (current?.polygons?.length) await this.restore(current);
    this.render();
    this.detect();
    return new Promise((res) => { this.resolve = res; });
  }

  /** Show the outline in use as the first, selected candidate; with a saved mask it is the edit again. */
  async restore(current) {
    const area = this.areaOf(current.polygons);
    if (current.mask) {
      try {
        const im = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = current.mask; });
        this.ensureMask();
        this.mask.getContext('2d').drawImage(im, 0, 0, this.img.width, this.img.height);
        // the exact outline in use (re-tracing the mask could shift it slightly)
        this.edit = { id: 'edit', polygons: current.polygons, area, methods: ['your edit — in use'], edited: true, current: true };
        return;
      } catch { /* no usable mask: show the outline without it */ }
    }
    this.current = { id: 'current', polygons: current.polygons, area, methods: ['in use'], current: true };
  }

  /** Share of the picture covered by polygons. */
  areaOf(polys) {
    const r = this.raster(polys);
    let n = 0;
    for (const v of r) n += v;
    return Math.round((n / r.length) * 10000) / 10000;
  }

  close(result) {
    this.root?.remove();
    this.root = null;
    window.removeEventListener('keydown', this.onKey, true);
    window.removeEventListener('keyup', this.onKeyUp, true);
    this.resolve?.(result);
    this.resolve = null;
  }

  /** Candidates as shown: the hand edit and / or the outline in use first, then the detected ones. */
  list() { return [...(this.edit ? [this.edit] : []), ...(this.current ? [this.current] : []), ...this.cands]; }

  /** Number of pinned (not detected) entries at the top of the list. */
  pinned() { return (this.edit ? 1 : 0) + (this.current ? 1 : 0); }

  build() {
    const r = document.createElement('div');
    r.className = 'wizard';
    r.innerHTML = `
      <div class="wz-box">
        <div class="wz-head"><b>Outline from picture</b><span class="wz-src"></span><button class="icon-btn wz-x" title="Close (Esc)">✕</button></div>
        <div class="wz-main">
          <div class="wz-stage-wrap">
            <div class="wz-tools">
              <span class="wz-tl">Detect:</span>
              <button class="chip" data-tool="seed">✚ Inside object</button>
              <button class="chip" data-tool="notthis">✖ Not this</button>
              <button class="chip" data-tool="box">▭ Box around object</button>
              <button class="chip" data-tool="object">◉ Object colour</button>
              <button class="chip" data-tool="background">◌ Background colour</button>
              <button class="chip wz-clear" title="Remove all detection hints">Clear hints</button>
              <span class="sep"></span>
              <button class="chip tool wz-edit-btn" title="Edit the selected outline by hand — or draw one from scratch">✎ Edit outline</button>
              <button class="chip" data-tool="measure" title="Measure between two points (px / mm)">📏 Measure</button>
              <span class="wz-zoom" title="Zoom: mouse wheel · pan: drag (no tool), middle mouse or Space + drag · keys + − 0">
                <button class="chip wz-zoom-out">−</button><span class="wz-zoom-val">100%</span><button class="chip wz-zoom-in">+</button><button class="chip wz-zoom-fit">Fit</button>
              </span>
            </div>
            <div class="wz-tools wz-edit-tools" hidden>
              <span class="wz-tl">Edit:</span>
              <button class="chip" data-tool="poly" title="Polygon (P): click corner points">⬠ Polygon</button>
              <button class="chip" data-tool="lasso" title="Lasso (L): drag a freehand loop">◯ Lasso</button>
              <button class="chip" data-tool="brush" title="Brush (B): paint">🖌 Brush</button>
              <span class="seg wz-mode">
                <button data-mode="add" title="Add (1)">＋ Add</button>
                <button data-mode="remove" title="Remove (2)">− Remove</button>
                <button data-mode="keep" title="Cut out (3): keep only what is inside the polygon / loop">✂ Cut out</button>
              </span>
              <label class="wz-size" title="Brush size (picture pixels)">size <input type="range" min="2" max="200" step="1" class="wz-brush"><span></span></label>
              <button class="chip wz-undo" title="Undo (Ctrl+Z)">↶ Undo</button>
              <button class="chip wz-empty" title="Start from an empty outline and draw it yourself">Empty</button>
              <button class="chip wz-done" title="Leave edit mode (your edit stays as candidate ✎)">Done</button>
            </div>
            <div class="wz-stage"><img alt=""><canvas class="wz-maskview"></canvas><svg></svg><div class="wz-busy" hidden>Detecting…</div><div class="wz-tip" hidden></div></div>
            <div class="wz-chips"></div>
          </div>
          <div class="wz-side">
            <div class="layer-section">Candidates — most likely first</div>
            <div class="wz-list"></div>
            <p class="hint">＋ / − on a candidate adds it to / cuts it from your edit — e.g. body ＋ wheels − shadow.</p>
            <div class="layer-section">Detection</div>
            <div class="field"><label>Candidates</label><div class="wz-range"><input type="range" min="3" max="10" step="1" data-h="count"><span></span></div></div>
            <div class="field"><label title="Colour tolerance (0 = automatic)">Tolerance</label><div class="wz-range"><input type="range" min="0" max="60" step="1" data-h="tolerance"><span></span></div></div>
            <div class="field"><label title="Rounds off pixel steps and small bumps (pixels)">Smoothing</label><div class="wz-range"><input type="range" min="0" max="6" step="0.5" data-h="smoothing"><span></span></div></div>
            <label class="check"><input type="checkbox" data-h="holes"> Keep inner holes</label>
            <button class="btn small wz-detect">↻ Detect again</button>
            <div class="layer-section">Real size</div>
            <div class="field two"><label>Width × height</label><input type="number" class="wz-w" min="0" step="1"><input type="number" class="wz-h" min="0" step="1"></div>
            <p class="hint wz-size-hint">mm — aspect ratio is kept (change it later in Dimensions).</p>
            <div class="wz-make">
              <div class="layer-section">Make</div>
              <div class="seg wz-preset">
                <button data-p="cutter" class="on" title="Thin cutting wall + flange, printed flange-down">Cookie cutter</button>
                <button data-p="solid" title="The whole shape, extruded">Solid shape</button>
                <button data-p="custom" title="Start with the plain outline and add your own objects">Custom</button>
              </div>
            </div>
            <div class="wz-actions"><button class="btn wz-cancel">Cancel</button><button class="btn primary wz-use" disabled>Use this outline</button></div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(r);
    this.root = r;
    const $ = (s) => r.querySelector(s);
    this.$ = $;
    $('.wz-src').textContent = this.source;
    $('.wz-make').hidden = this.replace || this.purpose === 'layer';
    $('.wz-use').textContent = this.purpose === 'layer' ? (this.replace ? 'Apply to the layer' : 'Add as design layer')
      : this.replace ? 'Apply to the part' : 'Use this outline';
    if (this.size?.mmPerPx > 0) {
      $('.wz-size-hint').textContent = 'mm — the part keeps its scale, so what you do not change keeps its real size. Type a size to rescale.';
    }
    const img = $('.wz-stage img');
    img.src = this.img.url;
    const svg = $('.wz-stage svg');
    svg.setAttribute('viewBox', `0 0 ${this.img.width} ${this.img.height}`);
    this.svg = svg;
    this.view = $('.wz-maskview');
    this.view.width = this.img.width;
    this.view.height = this.img.height;
    this.preset = 'cutter';
    this.brush = Math.max(4, Math.round(Math.max(this.img.width, this.img.height) / 40));

    // picture, mask and overlay share one box: fitted to the stage × zoom, shifted by the pan
    this.zoom = 1;
    this.pan = [0, 0];
    this.layout = () => {
      if (!this.root) { ro.disconnect(); return; }
      const stage = $('.wz-stage');
      const W = stage.clientWidth, H = stage.clientHeight;
      const s0 = Math.min((W - 16) / this.img.width, (H - 16) / this.img.height);
      if (!(s0 > 0)) return;
      const s = s0 * this.zoom, w = this.img.width * s, h = this.img.height * s;
      // keep at least a quarter of the stage covered by the picture
      const mx = Math.max(0, (w - W) / 2 + W / 4), my = Math.max(0, (h - H) / 2 + H / 4);
      this.pan = [Math.min(mx, Math.max(-mx, this.pan[0])), Math.min(my, Math.max(-my, this.pan[1]))];
      const box = { left: `${(W - w) / 2 + this.pan[0]}px`, top: `${(H - h) / 2 + this.pan[1]}px`, width: `${w}px`, height: `${h}px` };
      for (const el of [img, svg, this.view]) Object.assign(el.style, box);
      this.scale = s;
      $('.wz-zoom-val').textContent = `${Math.round(this.zoom * 100)}%`;
    };
    const ro = new ResizeObserver(() => this.layout());
    ro.observe($('.wz-stage'));
    img.addEventListener('load', () => this.layout());
    $('.wz-zoom-in').addEventListener('click', () => this.zoomBy(1.5));
    $('.wz-zoom-out').addEventListener('click', () => this.zoomBy(1 / 1.5));
    $('.wz-zoom-fit').addEventListener('click', () => { this.zoom = 1; this.pan = [0, 0]; this.layout(); this.renderOverlay(); });

    $('.wz-x').addEventListener('click', () => this.close(null));
    $('.wz-cancel').addEventListener('click', () => this.close(null));
    this.onKey = (e) => {
      if (!this.root || e.target.closest?.('input')) return;
      if (e.key === 'Escape') {
        e.stopPropagation();
        if (this.poly.length) { this.poly = []; this.renderOverlay(); } else if (this.tool) this.setTool(null); else this.close(null);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && this.mask) {
        e.preventDefault();
        this.undoStep();
      } else if (e.key === 'Enter' && this.poly.length > 2) this.closePoly();
      else if (e.key === 'Backspace' && this.poly.length) { e.preventDefault(); this.poly.pop(); this.renderOverlay(); }
      else if (e.key === ' ') { e.preventDefault(); this.spaceDown = true; this.$('.wz-stage').classList.add('can-pan'); }
      else if (e.key === '+' || e.key === '=') this.zoomBy(1.5);
      else if (e.key === '-') this.zoomBy(1 / 1.5);
      else if (e.key === '0') { this.zoom = 1; this.pan = [0, 0]; this.layout(); this.renderOverlay(); }
      else if (this.editing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const tool = { p: 'poly', l: 'lasso', b: 'brush' }[e.key.toLowerCase()];
        const mode = { 1: 'add', 2: 'remove', 3: 'keep' }[e.key];
        if (tool) this.setTool(tool);
        if (mode) this.setMode(mode);
      }
    };
    window.addEventListener('keydown', this.onKey, true);
    this.onKeyUp = (e) => { if (e.key === ' ') { this.spaceDown = false; this.root?.querySelector('.wz-stage').classList.remove('can-pan'); } };
    window.addEventListener('keyup', this.onKeyUp, true);
    r.addEventListener('pointerdown', (e) => { if (e.target === r) this.close(null); });

    for (const inp of r.querySelectorAll('[data-h]')) {
      const k = inp.dataset.h;
      const out = inp.nextElementSibling;
      const show = () => { if (out) out.textContent = k === 'tolerance' && !+inp.value ? 'auto' : inp.value; };
      if (inp.type === 'checkbox') inp.checked = !!this.hints[k];
      else inp.value = this.hints[k];
      show();
      inp.addEventListener('input', show);
      inp.addEventListener('change', () => {
        this.hints[k] = inp.type === 'checkbox' ? inp.checked : +inp.value;
        if (k === 'smoothing' || k === 'holes') this.traceMask();
        this.detect();
      });
    }
    const brush = $('.wz-brush');
    brush.max = Math.max(20, Math.round(Math.max(this.img.width, this.img.height) / 6));
    brush.value = this.brush;
    brush.nextElementSibling.textContent = this.brush;
    brush.addEventListener('input', () => { this.brush = +brush.value; brush.nextElementSibling.textContent = brush.value; });

    $('.wz-detect').addEventListener('click', () => this.detect());
    $('.wz-clear').addEventListener('click', () => {
      Object.assign(this.hints, { object_colors: [], background_colors: [], seeds: [], bg_seeds: [], rect: null });
      this.renderChips();
      this.detect();
    });
    // detection tools toggle; an edit tool stays on until another one is picked
    for (const b of r.querySelectorAll('[data-tool]')) {
      b.addEventListener('click', () => {
        const t = b.dataset.tool;
        this.setTool(this.tool === t && !EDIT_TOOLS[t] ? null : t);
      });
    }
    $('.wz-edit-btn').addEventListener('click', () => (this.editing ? this.setEditing(false) : this.startEdit()));
    $('.wz-done').addEventListener('click', () => this.setEditing(false));
    $('.wz-undo').addEventListener('click', () => this.undoStep());
    $('.wz-empty').addEventListener('click', () => {
      this.pushUndo();
      this.mask.getContext('2d').clearRect(0, 0, this.img.width, this.img.height);
      this.maskChanged();
      this.setTool('poly');
      this.setMode('add');
    });
    for (const b of r.querySelectorAll('[data-mode]')) b.addEventListener('click', () => this.setMode(b.dataset.mode));
    this.mode = 'add';
    for (const b of r.querySelectorAll('.wz-preset button')) {
      b.addEventListener('click', () => {
        this.preset = b.dataset.p;
        r.querySelectorAll('.wz-preset button').forEach((x) => x.classList.toggle('on', x === b));
      });
    }
    this.bindStage($('.wz-stage'));
    const wIn = $('.wz-w'), hIn = $('.wz-h');
    wIn.addEventListener('input', () => { const a = this.aspect(); if (a && +wIn.value > 0) hIn.value = fmt(+wIn.value / a); this.sizeTouched = 'w'; this.userSized = true; });
    hIn.addEventListener('input', () => { const a = this.aspect(); if (a && +hIn.value > 0) wIn.value = fmt(+hIn.value * a); this.sizeTouched = 'h'; this.userSized = true; });
    $('.wz-use').addEventListener('click', () => this.use());
  }

  setTool(t) {
    this.tool = t;
    this.poly = [];
    this.root.querySelectorAll('[data-tool]').forEach((x) => x.classList.toggle('on', x.dataset.tool === t));
    const stage = this.$('.wz-stage');
    stage.classList.toggle('picking', !!t);
    this.updateTip();
    this.renderOverlay();
  }

  setMode(m) {
    // painting cannot 'cut out' (there is no inside of a brush stroke)
    if (m === 'keep' && this.tool === 'brush') this.setTool('poly');
    this.mode = m;
    this.root.querySelectorAll('[data-mode]').forEach((x) => x.classList.toggle('on', x.dataset.mode === m));
    this.updateTip();
    this.renderOverlay();
  }

  updateTip() {
    const t = this.tool, tip = this.$('.wz-tip');
    tip.hidden = !t;
    if (EDIT_TOOLS[t]) {
      if (t === 'brush' && this.mode === 'keep') this.mode = 'add';
      this.root.querySelectorAll('[data-mode]').forEach((x) => {
        x.classList.toggle('on', x.dataset.mode === this.mode);
        x.disabled = t === 'brush' && x.dataset.mode === 'keep';
      });
      const [label, effect, color] = EDIT_MODES[this.mode];
      tip.textContent = `${label}: ${EDIT_TOOLS[t]} — ${effect}`;
      tip.style.background = color;
      tip.style.color = this.mode === 'keep' ? '#111' : '#fff';
    } else {
      tip.textContent = HINT_TOOLS[t] || '';
      tip.style.background = tip.style.color = '';
    }
  }

  setEditing(on) {
    this.editing = on;
    this.$('.wz-edit-tools').hidden = !on;
    this.$('.wz-edit-btn').classList.toggle('on', on);
    if (!on && EDIT_TOOLS[this.tool]) this.setTool(null);
    this.drawMaskView();
    this.renderOverlay();
  }

  // ---------------------------------------------------------------- mask editing
  ensureMask() {
    if (this.mask) return;
    this.mask = document.createElement('canvas');
    this.mask.width = this.img.width;
    this.mask.height = this.img.height;
  }

  /** Start editing from the selected candidate (or continue the current edit). */
  startEdit() {
    this.ensureMask();
    const cur = this.list()[this.sel];
    if (!this.edit && cur) {
      this.pushUndo();
      this.paintPolys(cur.polygons, true);
      this.maskChanged();
    }
    this.setEditing(true);
    if (!EDIT_TOOLS[this.tool]) this.setTool('poly');
    this.setMode(this.mode || 'add');
  }

  /** ＋ / − a candidate to / from the edit. */
  combine(c, add) {
    this.ensureMask();
    const cur = this.list()[this.sel];
    this.pushUndo();
    if (!this.edit && cur && cur !== c) {
      // the selected candidate is the starting point: its own undo step
      this.paintPolys(cur.polygons, true);
      this.pushUndo();
    }
    this.paintPolys(c.polygons, add);
    this.maskChanged();
    if (!this.editing) this.setEditing(true);
  }

  /** Apply a shape to the mask: mode 'add' / true, 'remove' / false, or 'keep' (only what is inside). */
  paintPolys(polys, mode) {
    const ctx = this.mask.getContext('2d');
    const op = mode === 'keep' ? 'destination-in' : mode === 'remove' || mode === false ? 'destination-out' : 'source-over';
    ctx.globalCompositeOperation = op;
    ctx.fillStyle = '#fff';
    ctx.fill(new Path2D(pathOf(polys)), 'evenodd');
    ctx.globalCompositeOperation = 'source-over';
  }

  pushUndo() {
    this.ensureMask();
    this.undo.push(this.mask.getContext('2d').getImageData(0, 0, this.img.width, this.img.height));
    if (this.undo.length > 30) this.undo.shift();
  }

  undoStep() {
    const prev = this.undo.pop();
    if (!prev) return;
    this.mask.getContext('2d').putImageData(prev, 0, 0);
    this.maskChanged();
  }

  maskChanged() {
    this.drawMaskView();
    clearTimeout(this.traceTimer);
    this.traceTimer = setTimeout(() => this.traceMask(true), 250);
  }

  drawMaskView() {
    const v = this.view.getContext('2d');
    v.clearRect(0, 0, this.view.width, this.view.height);
    if (!this.mask || !this.editing) return;
    v.drawImage(this.mask, 0, 0);
    v.globalCompositeOperation = 'source-in';
    v.fillStyle = 'rgba(255, 45, 149, 0.38)';
    v.fillRect(0, 0, this.view.width, this.view.height);
    v.globalCompositeOperation = 'source-over';
  }

  /** The painted mask -> smooth outline on the server -> candidate ✎. `select`: an edit was just
   *  made, so show it; otherwise (e.g. smoothing changed) the current selection is kept. */
  async traceMask(select = false) {
    if (!this.mask || !this.root) return;
    const ticket = (this.maskTicket = (this.maskTicket || 0) + 1);
    try {
      const res = await (await this.api('/api/outline/mask', { mask: this.mask.toDataURL('image/png'), smoothing: this.hints.smoothing, holes: this.hints.holes })).json();
      if (ticket !== this.maskTicket || !this.root) return;
      const prev = this.list()[this.sel];
      this.edit = res.polygons.length ? { id: 'edit', polygons: res.polygons, area: res.area, methods: ['your edit'], edited: true } : null;
      this.sel = select && this.edit ? 0 : this.reselect(prev);
      this.render();
    } catch (e) { this.toast(e.message, 'error'); }
  }

  /** Index of `prev` in the current list after it was rebuilt (re-detection with other settings
   *  changes order and shape slightly): the edit stays the edit, a detected outline is matched by
   *  overlap with the new candidates. Falls back to the first one. */
  reselect(prev) {
    const items = this.list();
    if (!prev || !items.length) return 0;
    if (items.includes(prev)) return items.indexOf(prev); // pinned entries survive as they are
    if (prev.edited) return 0; // the edit is always listed first
    const a = this.raster(prev.polygons);
    let best = 0, bestIoU = 0.5;
    items.forEach((c, i) => {
      if (c.edited || c.current) return;
      const b = this.raster(c.polygons);
      let inter = 0, union = 0;
      for (let k = 0; k < a.length; k++) { inter += a[k] & b[k]; union += a[k] | b[k]; }
      const iou = union ? inter / union : 0;
      if (iou > bestIoU) { bestIoU = iou; best = i; }
    });
    return best;
  }

  /** Polygons -> small binary raster (for overlap comparisons). */
  raster(polys) {
    const s = 160 / Math.max(this.img.width, this.img.height);
    const c = (this.rasterCanvas ||= document.createElement('canvas'));
    c.width = Math.max(1, Math.round(this.img.width * s));
    c.height = Math.max(1, Math.round(this.img.height * s));
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.setTransform(s, 0, 0, s, 0, 0);
    ctx.fillStyle = '#fff';
    ctx.fill(new Path2D(pathOf(polys)), 'evenodd');
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    const out = new Uint8Array(c.width * c.height);
    for (let k = 0; k < out.length; k++) out[k] = d[k * 4 + 3] > 127 ? 1 : 0;
    return out;
  }

  // ---------------------------------------------------------------- pointer input
  bindStage(stage) {
    let drag = null;
    // no native image drag / text selection / context menu: every gesture belongs to the tools
    stage.querySelector('img').draggable = false;
    stage.addEventListener('dragstart', (e) => e.preventDefault());
    stage.addEventListener('contextmenu', (e) => e.preventDefault());
    const ctxStroke = (a, b, erase) => {
      const ctx = this.mask.getContext('2d');
      ctx.globalCompositeOperation = erase ? 'destination-out' : 'source-over';
      ctx.strokeStyle = ctx.fillStyle = '#fff';
      ctx.lineWidth = this.brush;
      ctx.lineCap = ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0] + 0.01, b[1]);
      ctx.stroke();
      ctx.globalCompositeOperation = 'source-over';
      this.drawMaskView();
    };
    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.zoomBy(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)), e.clientX, e.clientY);
    }, { passive: false });
    stage.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.wz-zoom')) return;
      e.preventDefault();
      const t = this.tool;
      // pan: middle mouse, Space + drag, or a plain drag while no tool is active
      if (e.button === 1 || (e.button === 0 && (this.spaceDown || !t))) {
        drag = { pan: true, from: [e.clientX, e.clientY], pan0: [...this.pan], start: this.imgPoint(e), moved: false, click: e.button === 0 && !t && !this.spaceDown };
        stage.setPointerCapture(e.pointerId);
        stage.classList.add('panning');
        return;
      }
      if (e.button === 2) {
        // right-click: take back the last polygon point
        if (this.poly.length) { this.poly.pop(); this.renderOverlay(); }
        return;
      }
      if (e.button !== 0) return;
      const pt = this.imgPoint(e);
      drag = { start: pt, last: pt, moved: false, pts: [pt] };
      stage.setPointerCapture(e.pointerId);
      if (EDIT_TOOLS[t]) this.ensureMask();
      if (t === 'brush') { this.pushUndo(); ctxStroke(pt, pt, this.mode === 'remove'); }
    });
    stage.addEventListener('pointermove', (e) => {
      const pt = this.imgPoint(e);
      this.cursor = pt;
      if (drag?.pan) {
        const dx = e.clientX - drag.from[0], dy = e.clientY - drag.from[1];
        if (Math.hypot(dx, dy) > 4) drag.moved = true;
        if (drag.moved) { this.pan = [drag.pan0[0] + dx, drag.pan0[1] + dy]; this.layout(); }
        return;
      }
      if (!drag) { if (this.tool === 'brush' || this.poly.length || (this.tool === 'measure' && this.measure && !this.measure.b)) this.renderOverlay(); return; }
      if (this.screenDist(pt, drag.start) > 4) drag.moved = true;
      const t = this.tool;
      if (t === 'brush') ctxStroke(drag.last, pt, this.mode === 'remove');
      else if (t === 'lasso') drag.pts.push(pt);
      drag.last = pt;
      if (t === 'box' || t === 'lasso') this.renderOverlay(drag);
    });
    stage.addEventListener('pointerup', (e) => {
      if (!drag) return;
      const d = drag;
      drag = null;
      const pt = this.imgPoint(e), t = this.tool;
      if (d.pan) {
        stage.classList.remove('panning');
        if (!d.moved && d.click) this.click(pt, null); // a click without a tool selects an outline
        return;
      }
      if (t === 'brush') this.maskChanged();
      else if (t === 'lasso') {
        if (d.pts.length > 3 && d.moved) {
          this.pushUndo();
          this.paintPolys([[d.pts]], this.mode);
          this.maskChanged();
        }
      } else if (t === 'box') {
        if (d.moved) {
          const [x0, x1] = [d.start[0], pt[0]].sort((a, b) => a - b), [y0, y1] = [d.start[1], pt[1]].sort((a, b) => a - b);
          this.hints.rect = [x0 / this.img.width, y0 / this.img.height, x1 / this.img.width, y1 / this.img.height];
          this.renderChips();
          this.detect();
        }
      } else if (t === 'poly') this.polyClick(pt);
      else if (t === 'measure') {
        this.measure = !this.measure || this.measure.b ? { a: pt } : { ...this.measure, b: pt };
      }
      else if (!d.moved) this.click(pt, t);
      this.renderOverlay();
    });
    // a double-click is two clicks on the same spot: the second one closes the polygon (polyClick)
    stage.addEventListener('dblclick', (e) => { e.preventDefault(); if (this.tool === 'poly' && this.poly.length > 2) this.closePoly(); });
    stage.addEventListener('pointerleave', () => { this.cursor = null; this.renderOverlay(); });
  }

  /** mm per picture pixel for the selected outline: the part's scale when re-editing, else the typed size. */
  mmPerPx() {
    if (this.size?.mmPerPx > 0 && !this.userSized) return this.size.mmPerPx;
    const e = this.extent(), w = +this.$('.wz-w')?.value;
    return e && w > 0 ? w / e[0] : null;
  }

  /** Zoom by `f` keeping the picture point under (clientX, clientY) — default the stage centre — in place. */
  zoomBy(f, clientX, clientY) {
    const stage = this.$('.wz-stage'), r = stage.getBoundingClientRect();
    const cx = (clientX ?? r.left + r.width / 2) - r.left, cy = (clientY ?? r.top + r.height / 2) - r.top;
    const z = Math.min(20, Math.max(1, this.zoom * f));
    if (z === this.zoom) return;
    // stage coords of the picture origin before; the point under the cursor must stay there
    const W = stage.clientWidth, H = stage.clientHeight, s = this.scale, s2 = (s / this.zoom) * z;
    const left = (W - this.img.width * s) / 2 + this.pan[0], top = (H - this.img.height * s) / 2 + this.pan[1];
    const u = (cx - left) / s, v = (cy - top) / s;
    this.zoom = z;
    this.pan = [cx - u * s2 - (W - this.img.width * s2) / 2, cy - v * s2 - (H - this.img.height * s2) / 2];
    this.layout();
    this.renderOverlay();
  }

  /** Distance of two picture points in screen pixels (tolerances should not depend on the zoom). */
  screenDist(a, b) {
    const k = this.svg.getBoundingClientRect().width / this.img.width;
    return Math.hypot(a[0] - b[0], a[1] - b[1]) * k;
  }

  /** A polygon click: a new corner, or — on the first point or on the last one again (double-click) — close. */
  polyClick(pt) {
    const n = this.poly.length;
    if (n > 2 && (this.screenDist(pt, this.poly[0]) < 12 || this.screenDist(pt, this.poly[n - 1]) < 6)) {
      this.closePoly();
      return;
    }
    if (n && this.screenDist(pt, this.poly[n - 1]) < 6) return; // double-click on a short polygon
    this.poly.push(pt);
  }

  closePoly() {
    if (this.poly.length > 2) {
      this.ensureMask();
      this.pushUndo();
      this.paintPolys([[this.poly]], this.mode);
      this.maskChanged();
    }
    this.poly = [];
    this.renderOverlay();
  }

  click(pt, tool) {
    if (!tool) {
      // click on an outline selects it (smallest containing candidate first)
      const hits = this.list().map((c, i) => ({ i, c })).filter(({ c }) => c.polygons.some((p) => inside(p[0], pt)));
      if (hits.length) this.select(hits.sort((a, b) => a.c.area - b.c.area)[0].i);
      return;
    }
    const norm = [pt[0] / this.img.width, pt[1] / this.img.height];
    if (tool === 'seed') this.hints.seeds.push(norm);
    else if (tool === 'notthis') this.hints.bg_seeds.push(norm);
    else if (tool === 'object' || tool === 'background') {
      const ctx = this.img.canvas.getContext('2d');
      // average a small neighbourhood: a single pixel of a photo is noisy
      const r = 2, x = Math.round(pt[0]), y = Math.round(pt[1]);
      const d = ctx.getImageData(Math.max(0, x - r), Math.max(0, y - r), 2 * r + 1, 2 * r + 1).data;
      const rgb = [0, 0, 0];
      for (let i = 0; i < d.length; i += 4) for (let k = 0; k < 3; k++) rgb[k] += d[i + k];
      const col = rgb.map((v) => Math.round(v / (d.length / 4)));
      this.hints[tool === 'object' ? 'object_colors' : 'background_colors'].push(col);
    } else return;
    this.renderChips();
    this.detect();
  }

  imgPoint(e) {
    const r = this.svg.getBoundingClientRect();
    return [Math.min(this.img.width, Math.max(0, ((e.clientX - r.left) / r.width) * this.img.width)),
      Math.min(this.img.height, Math.max(0, ((e.clientY - r.top) / r.height) * this.img.height))];
  }

  // ---------------------------------------------------------------- detection
  /** [width, height] in picture pixels of the selected outline. */
  extent() {
    const c = this.list()[this.sel];
    if (!c) return null;
    const pts = c.polygons.flatMap((p) => p[0]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    return [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
  }

  aspect() {
    const e = this.extent();
    return e ? e[0] / e[1] : null;
  }

  /** Keep the typed dimension, recompute the other one for the selected outline's aspect ratio.
   *  When editing the outline of a part, the part's scale (mm per picture pixel) is kept instead —
   *  what did not change keeps its real size — until a size is typed. */
  syncSize() {
    const wIn = this.$('.wz-w'), hIn = this.$('.wz-h');
    const a = this.aspect();
    if (!a) return;
    if (this.size?.mmPerPx > 0 && !this.userSized) {
      const [bw, bh] = this.extent();
      wIn.value = fmt(bw * this.size.mmPerPx);
      hIn.value = fmt(bh * this.size.mmPerPx);
      return;
    }
    if (!(+wIn.value > 0) && !(+hIn.value > 0)) {
      wIn.value = fmt(this.size?.width || 100);
      this.sizeTouched = 'w';
    }
    if (this.sizeTouched === 'h') wIn.value = fmt(+hIn.value * a);
    else hIn.value = fmt(+wIn.value / a);
  }

  renderChips() {
    const box = this.$('.wz-chips');
    box.innerHTML = '';
    const add = (label, remove, swatch) => {
      const c = document.createElement('span');
      c.className = 'wz-chip';
      c.innerHTML = `${swatch ? `<i style="background:${swatch}"></i>` : ''}<span></span><button title="Remove">✕</button>`;
      c.querySelector('span').textContent = label;
      c.querySelector('button').addEventListener('click', () => { remove(); this.renderChips(); this.detect(); });
      box.appendChild(c);
    };
    const each = (list, label, swatch) => list.forEach((v, i) => add(label(i), () => list.splice(i, 1), swatch?.(v)));
    each(this.hints.object_colors, () => 'object', hex);
    each(this.hints.background_colors, () => 'background', hex);
    each(this.hints.seeds, (i) => `inside ${i + 1}`);
    each(this.hints.bg_seeds, (i) => `not this ${i + 1}`);
    if (this.hints.rect) add('box', () => { this.hints.rect = null; });
  }

  async detect() {
    const busy = this.$('.wz-busy');
    busy.hidden = false;
    const ticket = (this.ticket = (this.ticket || 0) + 1);
    try {
      const res = await (await this.api('/api/outline/detect', { image: this.img.url, hints: this.hints })).json();
      if (ticket !== this.ticket || !this.root) return;
      const prev = this.list()[this.sel];
      this.cands = res.candidates;
      this.sel = this.reselect(prev);
      if (!this.cands.length && !this.edit) this.toast('No outline found — give a hint (inside point, box, colours) or draw it with ✎ Edit outline.', 'warning', 7000);
    } catch (e) {
      if (this.root) this.toast(e.message, 'error');
    } finally {
      if (ticket === this.ticket && this.root) busy.hidden = true;
    }
    if (this.root) this.render();
  }

  select(i) {
    this.sel = i;
    this.render();
  }

  render() {
    this.renderOverlay();
    const list = this.$('.wz-list');
    list.innerHTML = '';
    const items = this.list();
    if (!items.length) list.innerHTML = '<div class="empty small">No candidates.</div>';
    items.forEach((c, i) => {
      const row = document.createElement('div');
      row.className = `wz-cand${i === this.sel ? ' on' : ''}${c.edited ? ' edited' : ''}`;
      const pieces = c.polygons.length > 1 ? ` · ${c.polygons.length} pieces` : '';
      const holes = c.polygons.reduce((n, p) => n + p.length - 1, 0);
      const head = c.edited ? `<b>✎ ${c.current ? 'In use — your edit' : 'Your edit'}</b>`
        : c.current ? '<b>● In use</b> <span class="wz-meta">(the part is made from it)</span>'
          : `<b>#${i - this.pinned() + 1}</b> <span class="wz-conf">${c.confidence}%</span>`;
      row.className += c.current ? ' current' : '';
      row.innerHTML = `<i style="background:${this.colorOf(i)}"></i>
        <div class="wz-cbody">${head}
        <div class="wz-meta">${Math.round(c.area * 100)}% of picture${pieces}${holes ? ` · ${holes} hole(s)` : ''}<br>${c.methods.join(', ')}</div></div>
        <div class="wz-cact">${c.edited ? '<button class="mini" data-a="edit" title="Continue editing">✎</button><button class="mini danger" data-a="drop" title="Discard your edit">✕</button>'
          : c.current ? '<button class="mini" data-a="editfrom" title="Edit this outline by hand">✎</button>'
            : '<button class="mini" data-a="add" title="Add to your edit">＋</button><button class="mini" data-a="sub" title="Cut from your edit">−</button>'}</div>`;
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'add' || a === 'sub') this.combine(c, a === 'add');
        else if (a === 'edit') this.startEdit();
        else if (a === 'editfrom') { this.sel = i; this.startEdit(); }
        else if (a === 'drop') {
          // discarding the edit of the outline in use keeps that outline listed
          if (this.edit.current) this.current = { ...this.edit, id: 'current', edited: false, methods: ['in use'] };
          this.edit = null;
          this.mask = null;
          this.undo = [];
          this.setEditing(false);
          this.sel = 0;
          this.render();
        } else this.select(i);
      });
      row.addEventListener('mouseenter', () => this.renderOverlay(null, i));
      row.addEventListener('mouseleave', () => this.renderOverlay());
      list.appendChild(row);
    });
    this.$('.wz-use').disabled = !items.length;
    this.syncSize();
  }

  colorOf(i) {
    const c = this.list()[i];
    if (c?.edited) return EDIT_COLOR;
    if (c?.current) return CURRENT_COLOR;
    return COLORS[(i - this.pinned() + 1) % COLORS.length];
  }

  renderOverlay(drag = null, hover = -1) {
    const svg = this.svg;
    if (!svg) return;
    svg.innerHTML = '';
    // line widths in picture pixels, constant on screen whatever the zoom
    const lw = Math.max(this.img.width, this.img.height) / 260 / (this.zoom || 1);
    const items = this.list();
    // the selected outline on top, others thin; while editing only the edit and the hovered one
    const order = items.map((c, i) => i).sort((a, b) => (a === this.sel) - (b === this.sel));
    for (const i of order) {
      const c = items[i], col = this.colorOf(i), on = i === this.sel || i === hover;
      if (this.editing && !c.edited && i !== hover) continue;
      svgEl('path', {
        d: pathOf(c.polygons), fill: on && !this.editing ? `${col}33` : 'none', 'fill-rule': 'evenodd', stroke: col,
        'stroke-width': on ? lw * 1.6 : lw * 0.7, 'stroke-opacity': on ? 1 : 0.75, 'stroke-dasharray': on ? '' : `${lw * 3} ${lw * 2}`,
      }, svg);
    }
    const mark = (x, y, color, cross) => {
      const cx = x * this.img.width, cy = y * this.img.height, s = lw * 2;
      svgEl('circle', { cx, cy, r: lw * 3, fill: color, stroke: '#000', 'stroke-width': lw * 0.6 }, svg);
      svgEl('path', { d: cross ? `M${cx - s},${cy - s}L${cx + s},${cy + s}M${cx + s},${cy - s}L${cx - s},${cy + s}` : `M${cx - s},${cy}H${cx + s}M${cx},${cy - s}V${cy + s}`, stroke: '#000', 'stroke-width': lw * 0.7 }, svg);
    };
    for (const [x, y] of this.hints.seeds) mark(x, y, '#fff', false);
    for (const [x, y] of this.hints.bg_seeds) mark(x, y, '#ff7b72', true);
    const rect = (x0, y0, x1, y1, dash) => svgEl('rect', { x: Math.min(x0, x1), y: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0), fill: 'none', stroke: '#f2cc60', 'stroke-width': lw, 'stroke-dasharray': dash ? `${lw * 4} ${lw * 2}` : '' }, svg);
    if (this.hints.rect) {
      const [a, b, c, d] = this.hints.rect;
      rect(a * this.img.width, b * this.img.height, c * this.img.width, d * this.img.height, true);
    }
    if (drag && this.tool === 'box') rect(drag.start[0], drag.start[1], drag.last[0], drag.last[1], false);
    const modeCol = EDIT_MODES[this.mode]?.[2] || EDIT_COLOR;
    if (drag && this.tool === 'lasso' && drag.pts?.length > 1) {
      svgEl('polyline', { points: drag.pts.map((p) => p.join(',')).join(' '), fill: `${modeCol}33`, stroke: modeCol, 'stroke-width': lw }, svg);
    }
    if (this.poly.length) {
      const pts = [...this.poly, ...(this.cursor ? [this.cursor] : [])];
      svgEl('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: `${modeCol}22`, stroke: modeCol, 'stroke-width': lw }, svg);
      for (const [x, y] of this.poly) svgEl('circle', { cx: x, cy: y, r: lw * 1.5, fill: modeCol }, svg);
      if (this.poly.length > 2) {
        // the first point closes the polygon: show it as a target, bigger when the cursor is on it
        const [x, y] = this.poly[0];
        const hot = this.cursor && this.screenDist(this.cursor, this.poly[0]) < 12;
        svgEl('circle', { cx: x, cy: y, r: lw * (hot ? 5 : 3.5), fill: hot ? `${modeCol}66` : 'none', stroke: modeCol, 'stroke-width': lw * 0.8 }, svg);
      }
    }
    if (this.measure) {
      const { a } = this.measure, b = this.measure.b || (this.tool === 'measure' ? this.cursor : null);
      svgEl('circle', { cx: a[0], cy: a[1], r: lw * 1.6, fill: '#39d0d8' }, svg);
      if (b) {
        svgEl('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: '#39d0d8', 'stroke-width': lw }, svg);
        svgEl('circle', { cx: b[0], cy: b[1], r: lw * 1.6, fill: '#39d0d8' }, svg);
        const px = Math.hypot(b[0] - a[0], b[1] - a[1]), k = this.mmPerPx();
        const label = `${fmt(px)} px${k ? ` = ${fmt(px * k)} mm` : ''}`;
        const fs = lw * 9, tx = (a[0] + b[0]) / 2, ty = (a[1] + b[1]) / 2 - fs * 0.6;
        svgEl('rect', { x: tx - label.length * fs * 0.3, y: ty - fs, width: label.length * fs * 0.6, height: fs * 1.35, rx: fs * 0.25, fill: '#0f1216e0', stroke: '#39d0d8', 'stroke-width': lw * 0.5 }, svg);
        svgEl('text', { x: tx, y: ty, 'text-anchor': 'middle', fill: '#c8f7fa', 'font-size': fs, 'font-family': 'Segoe UI, sans-serif', 'font-weight': 600 }, svg).textContent = label;
      }
    }
    if (this.cursor && this.tool === 'brush') {
      svgEl('circle', { cx: this.cursor[0], cy: this.cursor[1], r: this.brush / 2, fill: 'none', stroke: this.mode === 'remove' ? '#ff7b72' : '#fff', 'stroke-width': lw * 0.6 }, svg);
    }
  }

  use() {
    const c = this.list()[this.sel];
    if (!c) return;
    const w = +this.$('.wz-w').value, h = +this.$('.wz-h').value;
    if (!(w > 0) || !(h > 0)) { this.toast('Enter the real width / height in mm.', 'warning'); return; }
    this.close({
      polygons: c.polygons, img_w: this.img.width, img_h: this.img.height, width: w, height: h,
      preset: this.preset, image: this.img.url, source: this.source,
      // saved with the project, so reopening the editor brings the edit and the hints back
      editor: { mask: c.edited && this.mask ? this.mask.toDataURL('image/png') : null, hints: structuredClone(this.hints) },
    });
  }
}

function inside(ring, [x, y]) {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}
