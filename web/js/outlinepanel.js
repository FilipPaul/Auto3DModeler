// Part panel — the same for every part: where it comes from (a PDF drawing, an outline traced from a
// picture or read from a DXF, an imported 3D file), 2D shapes added to / cut from its profile, and 3D
// objects booleaned onto it. Outline parts also choose what to make (cookie cutter / solid shape /
// custom stack of objects). Everything is stored on the model and built by the server.
import { nice } from './layers.js';

const PRESET_FIELDS = {
  cutter: [
    ['wall', 'Wall thickness', 0.1], ['height', 'Total height', 1], ['tip', 'Cutting edge', 0.05], ['tip_h', 'Edge height', 0.5],
    ['flange_w', 'Flange width', 0.5], ['flange_t', 'Flange thickness', 0.2], ['clearance', 'Clearance', 0.1],
  ],
  solid: [['thickness', 'Thickness', 0.5], ['offset', 'Grow / shrink', 0.1]],
};
const PRESET_HINT = {
  cutter: 'Printed flange-down; the inside of the wall is exactly on the outline (+ clearance), so cookies come out at the size you set. The cutting edge is the thinner top part of the wall.',
  solid: 'The whole shape extruded — e.g. the cookie itself, a plaque or a base. Design layers (right tab) can emboss or engrave its top.',
  custom: 'Objects are built from the top of the list down: each one adds (∪), removes (−) or keeps only the overlap (∩) with everything above it.',
};
const OPS = [['union', '∪ Add (union)'], ['subtract', '− Subtract'], ['intersect', '∩ Intersect']];
const OP_BADGE = { union: '∪ add', subtract: '− cut', intersect: '∩ overlap', add: '∪ add', };
const SOURCES = [['outline', 'Outline'], ['circle', 'Circle / cylinder'], ['rect', 'Rectangle / box'], ['line', 'Line / bar'], ['poly', 'Text']];
const FONTS = [
  ['"Arial Black", Arial, sans-serif', 'Bold sans'], ['Verdana, sans-serif', 'Sans'], ['Georgia, serif', 'Serif'],
  ['Impact, sans-serif', 'Impact'], ['"Comic Sans MS", cursive', 'Comic'], ['"Segoe Script", "Brush Script MT", cursive', 'Script'],
  ['"Courier New", monospace', 'Mono'],
];
const CLEANUP_HINT = 'Applied to the traced outline in mm. Cookie cutters cannot cut notches narrower than about twice the wall — close or round them here.';

let uid = 0;
const newId = (p) => `${p}${Date.now().toString(36)}${(uid++).toString(36)}`;

/** Outline rings (model space) of a circle / rectangle / line, for selection and hit testing. */
/** Text as an outline: drawn on a canvas, cropped to its ink, traced by the server.
 *  -> {polygons (a unit square centred on 0, y up), aspect (width / height)}, or null when it draws nothing. */
export async function textOutline(text, { font = FONTS[0][0], bold = false } = {}) {
  const px = 160, f = `${bold ? 'bold ' : ''}${px}px ${font}`;
  const lines = String(text || '').split('\n');
  const c = document.createElement('canvas');
  let ctx = c.getContext('2d');
  ctx.font = f;
  c.width = Math.ceil(Math.max(1, ...lines.map((l) => ctx.measureText(l).width)) + px);
  c.height = Math.ceil(px * 1.3 * lines.length + px);
  ctx = c.getContext('2d');
  Object.assign(ctx, { font: f, textAlign: 'center', textBaseline: 'middle', fillStyle: '#000' });
  lines.forEach((l, i) => ctx.fillText(l, c.width / 2, px / 2 + px * 1.3 * (i + 0.5)));
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
    if (d[(y * c.width + x) * 4 + 3] > 40) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  }
  if (x1 < 0) return null;
  const crop = document.createElement('canvas');
  crop.width = x1 - x0 + 3;
  crop.height = y1 - y0 + 3;
  crop.getContext('2d').drawImage(c, x0 - 1, y0 - 1, crop.width, crop.height, 0, 0, crop.width, crop.height);
  const res = await fetch('/api/trace', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: crop.toDataURL('image/png'), max_px: 1024 }) });
  const r = await res.json();
  if (!res.ok) throw new Error(r.error || res.statusText);
  return r.polygons?.length ? { polygons: r.polygons, aspect: r.aspect } : null;
}

export function shapeRings(s) {
  // 2D shapes name the primitive in `kind`, 3D objects in `source`
  const kind = s && (s.source && s.source !== 'outline' ? s.source : s.source ? null : s.kind);
  if (!kind) return null;
  if (kind === 'line') {
    const dx = s.x2 - s.x, dy = s.y2 - s.y, L = Math.hypot(dx, dy) || 1, hw = (s.width || 1) / 2;
    const nx = (-dy / L) * hw, ny = (dx / L) * hw;
    return [[[s.x + nx, s.y + ny], [s.x2 + nx, s.y2 + ny], [s.x2 - nx, s.y2 - ny], [s.x - nx, s.y - ny]]];
  }
  const rot = ((s.rot || 0) * Math.PI) / 180;
  const tf = ([u, v]) => [s.x + u * Math.cos(rot) - v * Math.sin(rot), s.y + u * Math.sin(rot) + v * Math.cos(rot)];
  const w = s.w || 1, h = s.h || w;
  if (kind === 'poly' && s.polygons) {
    // the traced text / logo itself (unit box, y up)
    return s.polygons.flatMap((poly) => poly.map((ring) => ring.map(([u, v]) => tf([u * w, v * h]))));
  }
  if (kind === 'circle') return [Array.from({ length: 64 }, (_, i) => tf([(w / 2) * Math.cos((i / 64) * 2 * Math.PI), (h / 2) * Math.sin((i / 64) * 2 * Math.PI)]))];
  return [[[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]].map(tf)];
}

/** Is (x, y) on a primitive (within its bounding shape)? */
export function hitShape(s, x, y) {
  // traced shapes (text) are hit anywhere in their box, not only on the letters
  const rings = shapeRings(s?.polygons ? { ...s, polygons: null } : s);
  if (!rings) return false;
  const r = rings[0];
  let c = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

export class OutlinePanel {
  constructor(root, { onChange, onSelect, onChangeOutline, getSolution, api, toast, pick, canEditOutline }) {
    this.root = root;
    this.canEditOutline = canEditOutline;
    this.pick = pick; // pick({hint}, onPick(hit)): the next click on the part
    this.api = api;
    this.toast = toast;
    this.onChange = onChange;
    this.onSelect = onSelect;
    this.onChangeOutline = onChangeOutline;
    this.getSolution = getSolution;
    this.model = null;
    this.selected = null; // id of the open object / shape
  }

  set(model) {
    this.model = model || null;
    this.selected = null;
    this.render();
  }

  /** The selected primitive (object or 2D shape), for dragging. */
  selectedItem() {
    const m = this.model;
    if (!m || !this.selected) return null;
    return [...(m.objects || []), ...(m.extras || []), ...(m.shapes || [])].find((o) => o.id === this.selected) || null;
  }

  /** Draggable primitives, topmost first (custom objects only count while they are used). */
  draggables() {
    const m = this.model;
    if (!m) return [];
    const objs = m.kind === 'outline' && m.preset === 'custom' ? (m.objects || []) : (m.extras || []);
    return [...(m.shapes || []), ...objs].filter((s) => s.visible !== false && shapeRings(s)).reverse();
  }

  select(id) {
    this.selected = this.selected === id ? null : id;
    this.render();
    this.onSelect(shapeRings(this.selectedItem()));
  }

  changed(rerender) {
    if (rerender) this.render();
    this.onChange();
    this.onSelect(shapeRings(this.selectedItem()));
  }

  // ---------------------------------------------------------------- defaults
  frame() {
    const sol = this.getSolution();
    const [x0, y0, x1, y1] = sol?.outline_bbox || sol?.bbox || [0, 0, 100, 100];
    return { x0, y0, x1, y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, s: Math.min(x1 - x0, y1 - y0), top: sol?.z_range?.[1] ?? 5 };
  }

  newShape(kind) {
    const f = this.frame(), d = nice(f.s / 4);
    if (kind === 'hole') {
      const dia = nice(Math.max(3, f.s / 12));
      return { id: newId('S'), name: 'Hole', kind: 'circle', op: 'subtract', visible: true, x: f.cx, y: f.y1 - dia * 1.4, w: dia, h: dia, rot: 0, stroke: 0 };
    }
    if (kind === 'text') {
      return { id: newId('S'), name: 'Text', kind: 'poly', op: 'add', visible: true, x: f.cx, y: f.cy, h: nice(f.s / 6), w: 1, rot: 0, stroke: 0, text: 'Text', font: FONTS[0][0], bold: false };
    }
    const base = { id: newId('S'), name: { circle: 'Circle', rect: 'Rectangle', line: 'Line' }[kind], kind, op: 'add', visible: true, x: f.cx, y: f.cy };
    if (kind === 'line') return { ...base, x: f.cx - d, x2: f.cx + d, y2: f.cy, width: nice(f.s / 20), round: true };
    return { ...base, w: d, h: d, rot: 0, stroke: 0 };
  }

  newObject(kind) {
    const f = this.frame(), d = nice(f.s / 4), t = +(f.top || 5).toFixed(2);
    const base = { id: newId('O'), visible: true, op: 'union', z0: 0, z1: t };
    if (kind === 'fill') return { ...base, name: 'Outline', source: 'outline', mode: 'fill', offset: 0 };
    if (kind === 'band') return { ...base, name: 'Outline band', source: 'outline', mode: 'band', inner: 0, outer: nice(f.s / 40) };
    if (kind === 'text') {
      return { ...base, name: 'Text', source: 'poly', z0: 0, z1: Math.min(t, 3), x: f.cx, y: f.cy, h: nice(f.s / 8), w: 1, rot: 0, stroke: 0, text: 'Text', font: FONTS[0][0], bold: false };
    }
    if (kind === 'line') return { ...base, name: 'Bar', source: 'line', x: f.cx - d, y: f.cy, x2: f.cx + d, y2: f.cy, width: nice(f.s / 20), round: true };
    return { ...base, name: kind === 'circle' ? 'Cylinder' : 'Box', source: kind, x: f.cx, y: f.cy, w: d, h: d, rot: 0, stroke: 0 };
  }

  // ---------------------------------------------------------------- render
  render() {
    const root = this.root;
    root.innerHTML = '';
    const m = this.model;
    if (!m) return;
    if (m.kind === 'outline') this.renderOutline(root);
    else if (m.kind === 'mesh') root.appendChild(this.meshSection());
    else root.appendChild(this.drawingSection());
    if (!(m.kind === 'outline' && m.preset === 'custom')) root.appendChild(this.objectsSection('extras'));
    if (m.kind !== 'mesh') root.appendChild(this.shapesSection());
  }

  /** What the base 2D shape of this part is called in the UI. */
  profileName() { return this.model?.kind === 'outline' ? 'outline' : this.model?.kind === 'mesh' ? 'footprint' : 'profile'; }

  drawingSection() {
    const box = document.createElement('div');
    box.innerHTML = `<p class="hint">Made from the drawing <b></b>: its dimensions drive the part (Dimensions tab).
      Below, cut or add 2D shapes on its profile and add 3D objects — holes, posts, bars, text, offsets of the profile.</p>`;
    box.querySelector('b').textContent = this.model.source;
    return box;
  }

  meshSection() {
    const m = this.model, o = (m.mesh_opts = m.mesh_opts || {});
    const sol = this.getSolution();
    const box = document.createElement('div');
    box.innerHTML = `<p class="hint">Imported 3D file <b></b>. It is cut into flat slices — exact for walls that are vertical
      between flat faces, steps for slanted / curved walls. Scale it in Dimensions (or with a dimension you add).</p>`;
    box.querySelector('b').textContent = m.source;
    const ch = () => this.changed(false);
    const rot = document.createElement('div');
    rot.className = 'pair';
    for (const [label, d] of [['⟲ 90°', 90], ['⟳ 90°', -90]]) {
      const b = document.createElement('button');
      b.className = 'btn small';
      b.textContent = label;
      b.addEventListener('click', () => { o.rot = (((+o.rot || 0) + d) % 360 + 360) % 360; this.changed(true); });
      rot.appendChild(b);
    }
    const rows = [
      ['Up is', selectInput(o, 'up', [['z', '+Z (as in the file)'], ['-z', '−Z (upside down)'], ['y', '+Y'], ['-y', '−Y'], ['x', '+X'], ['-x', '−X']], () => this.changed(true))],
      ['Turn', rot],
      ['Mirror', checkInput(o, 'mirror', ch)],
      ['Slice height', numInput(o, 'layer', 0.05, ch)],
    ];
    for (const [label, ctl] of rows) box.appendChild(field(label, ctl));
    const size = hint('');
    size.classList.add('mesh-size');
    box.appendChild(size);
    this.refreshInfo();
    return box;
  }

  /** Live values shown in the panel (after every rebuild). */
  refreshInfo() {
    const el = this.root.querySelector('.mesh-size'), v = this.getSolution()?.values;
    if (el && v?.size_x) el.textContent = `Size: ${fmtNum(v.size_x)} × ${fmtNum(v.size_y)} × ${fmtNum(v.size_z)} mm`;
  }

  renderOutline(root) {
    const m = this.model;
    const o = m.outline;
    const head = document.createElement('div');
    head.innerHTML = `
      <div class="row-actions"><span class="hint" style="margin:0">${m.outline.space === 'mm' ? 'Outline from the drawing' : 'Outline from'} <b class="ol-src"></b></span>
        <button class="btn small primary ol-change" title="Open the outline editor with this outline (your edit and hints are kept) — edit it or pick another one; size, shapes and objects stay">✎ Edit outline…</button></div>
      <label class="check"><input type="checkbox" class="ol-lock"> Keep aspect ratio (width ↔ height)</label>
      <label class="check" title="Flip left ↔ right. A cookie cutter is turned over to use it, so mirror it if the cookie must look exactly like the picture."><input type="checkbox" class="ol-mirror"> Mirror outline</label>
      <div class="ol-cleanup"></div>
      <h3>Make</h3>
      <div class="seg ol-preset">
        <button data-p="cutter">Cookie cutter</button><button data-p="solid">Solid shape</button><button data-p="custom">Custom</button>
      </div>
      <p class="hint ol-phint"></p>`;
    root.appendChild(head);
    head.querySelector('.ol-src').textContent = m.source;
    const change = head.querySelector('.ol-change');
    change.hidden = !this.canEditOutline?.();
    change.addEventListener('click', () => this.onChangeOutline());
    const lock = head.querySelector('.ol-lock'), mirror = head.querySelector('.ol-mirror');
    lock.checked = o.lock !== false;
    mirror.checked = !!o.mirror;
    lock.addEventListener('change', () => { o.lock = lock.checked; this.onChange(true); });
    mirror.addEventListener('change', () => { o.mirror = mirror.checked; this.changed(false); });
    head.querySelector('.ol-cleanup').replaceWith(this.cleanupSection());
    for (const b of head.querySelectorAll('.ol-preset button')) {
      b.classList.toggle('on', b.dataset.p === m.preset);
      b.addEventListener('click', () => {
        if (m.preset === b.dataset.p) return;
        if (b.dataset.p === 'custom' && !(m.objects || []).length) this.toCustom(false);
        m.preset = b.dataset.p;
        if (PRESET_FIELDS[m.preset]) m.preset_opts = { ...this.defaults(m.preset), ...(m.preset_opts_by?.[m.preset] || {}) };
        this.changed(true);
      });
    }
    head.querySelector('.ol-phint').textContent = PRESET_HINT[m.preset] || '';

    if (PRESET_FIELDS[m.preset]) {
      const box = document.createElement('div');
      for (const [k, label, step] of PRESET_FIELDS[m.preset]) {
        box.appendChild(field(`${label} (mm)`, numInput(m.preset_opts, k, step, () => {
          m.preset_opts_by = { ...(m.preset_opts_by || {}), [m.preset]: { ...m.preset_opts } };
          this.changed(false);
        })));
      }
      const conv = document.createElement('button');
      conv.className = 'btn small';
      conv.textContent = 'Edit as 3D objects →';
      conv.title = 'Switch to Custom with the objects this preset is made of, to add holes, handles, extra offsets…';
      conv.addEventListener('click', () => this.toCustom(true));
      box.appendChild(conv);
      root.appendChild(box);
    } else {
      root.appendChild(this.objectsSection('objects'));
    }
  }

  defaults(preset) {
    return preset === 'cutter'
      ? { wall: 1, height: 15, flange_w: 4, flange_t: 2, tip: 0.5, tip_h: 3, clearance: 0 }
      : { thickness: 6, offset: 0 };
  }

  /** Copy the objects the current preset is made of into the custom list. */
  toCustom(switchNow) {
    const m = this.model, sol = this.getSolution();
    const src = m.preset !== 'custom' && sol?.objects ? sol.objects : [this.newObject('fill')];
    m.objects = structuredClone([...src, ...(switchNow ? m.extras || [] : [])]).map((ob) => ({ ...ob, id: newId('O') }));
    if (switchNow) m.extras = [];
    if (switchNow) {
      m.preset = 'custom';
      this.changed(true);
    }
  }

  cleanupSection() {
    const o = this.model.outline;
    const c = (o.cleanup = o.cleanup || {});
    const box = document.createElement('details');
    box.className = 'ol-clean';
    const active = ['fill_holes', 'close', 'smooth', 'simplify', 'hull'].filter((k) => c[k]).length + (c.keep === 'largest' ? 1 : 0);
    box.open = !!this.cleanupOpen;
    box.addEventListener('toggle', () => { this.cleanupOpen = box.open; });
    box.innerHTML = `<summary>Outline clean-up${active ? ` <span class="count">${active}</span>` : ''}</summary>`;
    const ch = () => this.changed(false);
    const rows = [
      ['Fill holes', checkInput(c, 'fill_holes', ch)],
      ['Close gaps (mm)', numInput(c, 'close', 0.5, ch)],
      ['Round corners (mm)', numInput(c, 'smooth', 0.5, ch)],
      ['Simplify (mm)', numInput(c, 'simplify', 0.1, ch)],
      ['Pieces', selectInput(c, 'keep', [['all', 'Keep all'], ['largest', 'Largest only']], ch)],
      ['Convex hull', checkInput(c, 'hull', ch)],
    ];
    box.appendChild(hint(CLEANUP_HINT));
    for (const [label, ctl] of rows) box.appendChild(field(label, ctl));
    const reset = document.createElement('button');
    reset.className = 'btn small';
    reset.textContent = 'Reset clean-up';
    reset.addEventListener('click', () => { o.cleanup = {}; this.changed(true); });
    box.appendChild(reset);
    return box;
  }

  /** Render text in the browser (any installed font) and trace it on the server into polygons. */
  async traceText(it) {
    if (!String(it.text || '').trim()) { this.toast('Type some text first.', 'warning'); return false; }
    try {
      const res = await textOutline(it.text, { font: it.font || FONTS[0][0], bold: it.bold });
      if (!res) { this.toast('This text produced no outline.', 'warning'); return false; }
      it.polygons = res.polygons;
      it.aspect = res.aspect;
      it.w = +(it.h * res.aspect).toFixed(4);
      return true;
    } catch (e) { this.toast(e.message, 'error'); return false; }
  }

  async addText(arr, item, isObject) {
    if (!(await this.traceText(item))) return;
    arr.push(item);
    this.selected = item.id;
    this.changed(true);
    this.placeOnPart(item, isObject);
  }

  /** Click where a new primitive goes: it is centred there; a 3D object starts on the clicked face
   *  (standing on a top face, hanging from a bottom face). Esc keeps the default place. */
  placeOnPart(it, isObject) {
    if (!this.pick) return;
    const what = isObject ? it.name.toLowerCase() : `${it.name.toLowerCase()} (2D)`;
    this.pick({ hint: `Click on the part where the ${what} goes` }, (h) => {
      this.moveTo(it, h);
      if (isObject && Math.abs(h.normal[2]) > 0.5) {
        // 3 mm (text 1 mm) whatever the part's unit
        const mm = { mm: 1, cm: 10, m: 1000, in: 25.4 }[this.model?.unit] || 1;
        const height = +((it.source === 'poly' ? 1 : 3) / mm).toFixed(6);
        if (h.normal[2] > 0) Object.assign(it, { z0: h.z, z1: +(h.z + height).toFixed(4) });
        else Object.assign(it, { z0: +(h.z - height).toFixed(4), z1: h.z });
      }
      this.changed(true);
    });
  }

  /** Centre a primitive on a picked point. */
  moveTo(it, h) {
    if ((it.source || it.kind) === 'line') {
      const dx = h.x - (it.x + it.x2) / 2, dy = h.y - (it.y + it.y2) / 2;
      Object.assign(it, { x: +(it.x + dx).toFixed(4), x2: +(it.x2 + dx).toFixed(4), y: +(it.y + dy).toFixed(4), y2: +(it.y2 + dy).toFixed(4) });
    } else Object.assign(it, { x: h.x, y: h.y });
  }

  /** A small ⌖ button: pick on the part, then apply(hit). */
  pickBtn(title, apply) {
    const b = document.createElement('button');
    b.className = 'mini pick';
    b.textContent = '⌖';
    b.title = `${title} — click on the part (corners and face heights snap)`;
    b.addEventListener('click', (e) => {
      e.preventDefault();
      this.pick?.({ hint: title }, (h) => { apply(h); this.changed(true); });
    });
    return b;
  }

  objectsSection(key = 'objects') {
    const m = this.model;
    const box = document.createElement('div');
    const pn = this.profileName(), Pn = pn[0].toUpperCase() + pn.slice(1);
    box.innerHTML = `<h3>${key === 'extras' ? '3D objects added to the part' : '3D objects'}</h3>
      ${key === 'extras' ? '<p class="hint">Booleaned onto the part above, from the top of the list down (a hole = Subtract).</p>' : ''}
      <div class="row-actions add-layer wrap">
        <button class="btn small" data-a="fill" title="The ${pn}, grown or shrunk by an offset, extruded">＋ ${Pn}</button>
        <button class="btn small" data-a="band" title="A wall along the ${pn}: the area between two offsets">＋ ${Pn} band</button>
        <button class="btn small" data-a="circle">＋ Cylinder</button>
        <button class="btn small" data-a="rect">＋ Box</button>
        <button class="btn small" data-a="line">＋ Bar</button>
        <button class="btn small" data-a="text" title="Raised or cut text, e.g. a name on the flange">＋ Text</button>
      </div>`;
    for (const b of box.querySelectorAll('[data-a]')) {
      b.addEventListener('click', () => {
        const ob = this.newObject(b.dataset.a);
        if (b.dataset.a === 'fill' || b.dataset.a === 'band') ob.name = `${Pn}${b.dataset.a === 'band' ? ' band' : ''}`;
        if (key === 'extras' && ob.source === 'outline') {
          // on top of the finished part: a raised step (profile) or a rim / wall around it (band)
          const top = +(this.frame().top || 0).toFixed(4), mm = { mm: 1, cm: 10, m: 1000, in: 25.4 }[m.unit] || 1;
          Object.assign(ob, { z0: top, z1: +(top + 3 / mm).toFixed(4) });
        }
        m[key] = m[key] || [];
        if (b.dataset.a === 'text') { this.addText(m[key], ob, true); return; }
        m[key] = [...m[key], ob];
        this.selected = ob.id;
        this.changed(true);
        if (ob.source !== 'outline') this.placeOnPart(ob, true);
      });
    }
    const list = document.createElement('div');
    if (!(m[key] || []).length) list.innerHTML = '<div class="empty small">No objects yet — click ＋ and then where it goes on the part.</div>';
    (m[key] || []).forEach((ob, i) => list.appendChild(this.card(ob, i, m[key], true)));
    box.appendChild(list);
    return box;
  }

  shapesSection() {
    const m = this.model;
    const box = document.createElement('div');
    box.innerHTML = `<h3>2D shapes on the ${this.profileName()}</h3>
      <p class="hint">Added to or cut from the ${this.profileName()} itself before anything is built${this.model.kind === 'outline' ? ' — a cookie cutter wall follows them too' : ''}.</p>
      <div class="row-actions add-layer wrap">
        <button class="btn small" data-a="circle">＋ Circle</button><button class="btn small" data-a="rect">＋ Rectangle</button><button class="btn small" data-a="line">＋ Line</button>
        <button class="btn small" data-a="text" title="Letters joined to (or cut from) the outline">＋ Text</button>
        <button class="btn small" data-a="hole" title="A round hole near the top — e.g. to hang an ornament">＋ Hole</button>
      </div>`;
    for (const b of box.querySelectorAll('[data-a]')) {
      b.addEventListener('click', () => {
        const s = this.newShape(b.dataset.a);
        if (b.dataset.a === 'text') { m.shapes = m.shapes || []; this.addText(m.shapes, s, false); return; }
        m.shapes = [...(m.shapes || []), s];
        this.selected = s.id;
        this.changed(true);
        this.placeOnPart(s, false);
      });
    }
    const list = document.createElement('div');
    if (!(m.shapes || []).length) list.innerHTML = '<div class="empty small">None — drag shapes on the part once added.</div>';
    (m.shapes || []).forEach((s, i) => list.appendChild(this.card(s, i, m.shapes, false)));
    box.appendChild(list);
    return box;
  }

  card(it, idx, arr, isObject) {
    const card = document.createElement('div');
    const open = it.id === this.selected;
    card.className = `layer${open ? ' open' : ''}${it.visible === false ? ' hidden-layer' : ''}`;
    const op = it.op || (isObject ? 'union' : 'add');
    const badge = isObject ? OP_BADGE[op] : op === 'subtract' ? '− cut' : '∪ add';
    const cls = { union: 'emboss', add: 'emboss', subtract: 'cut', intersect: 'guide' }[op];
    card.innerHTML = `
      <div class="layer-head">
        <input type="checkbox" class="vis" title="Include" ${it.visible === false ? '' : 'checked'}>
        <span class="layer-name"></span><span class="op-badge ${cls}">${badge}</span>
        <button class="icon-btn up" title="Move up">↑</button><button class="icon-btn down" title="Move down">↓</button>
        <button class="icon-btn dup" title="Duplicate">⧉</button><button class="icon-btn del" title="Delete">✕</button>
      </div><div class="layer-body"></div>`;
    card.querySelector('.layer-name').textContent = it.name;
    card.querySelector('.layer-head').addEventListener('click', (e) => { if (!e.target.closest('input,button')) this.select(it.id); });
    card.querySelector('.vis').addEventListener('change', (e) => { it.visible = e.target.checked; this.changed(true); });
    card.querySelector('.del').addEventListener('click', () => { arr.splice(idx, 1); if (open) this.selected = null; this.changed(true); });
    card.querySelector('.dup').addEventListener('click', () => {
      const c = { ...structuredClone(it), id: newId(isObject ? 'O' : 'S'), name: `${it.name} copy` };
      arr.splice(idx + 1, 0, c);
      this.selected = c.id;
      this.changed(true);
    });
    card.querySelector('.up').addEventListener('click', () => { if (idx > 0) { [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]; this.changed(true); } });
    card.querySelector('.down').addEventListener('click', () => { if (idx < arr.length - 1) { [arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]]; this.changed(true); } });
    if (open) this.body(it, card.querySelector('.layer-body'), isObject);
    return card;
  }

  body(it, el, isObject) {
    const ch = (re) => () => this.changed(re);
    const rows = [['Name', textInput(it, 'name', ch(true))]];
    if (isObject) {
      rows.push(['Operation', selectInput(it, 'op', OPS, ch(true))]);
      // 'Outline' reads 'Profile' / 'Footprint' on drawings / 3D files
      const pn = this.profileName();
      const sources = SOURCES.map(([v, t]) => (v === 'outline' ? [v, pn[0].toUpperCase() + pn.slice(1)] : [v, t]));
      rows.push(['Made from', selectInput(it, 'source', sources, () => {
        const f = this.frame(), d = nice(f.s / 4);
        if (it.source === 'poly') {
          Object.assign(it, { x: it.x ?? f.cx, y: it.y ?? f.cy, h: it.h || nice(f.s / 8), rot: it.rot || 0, stroke: 0, text: it.text || 'Text', font: it.font || FONTS[0][0] });
          this.traceText(it).then(() => this.changed(true));
          return;
        }
        if (it.source === 'outline') Object.assign(it, { mode: it.mode || 'fill', offset: it.offset ?? 0, inner: it.inner ?? 0, outer: it.outer ?? nice(f.s / 40) });
        else if (it.source === 'line') Object.assign(it, { x: it.x ?? f.cx - d, y: it.y ?? f.cy, x2: it.x2 ?? f.cx + d, y2: it.y2 ?? f.cy, width: it.width || nice(f.s / 20) });
        else Object.assign(it, { x: it.x ?? f.cx, y: it.y ?? f.cy, w: it.w || d, h: it.h || d, rot: it.rot || 0, stroke: it.stroke || 0 });
        this.changed(true);
      })]);
    } else {
      rows.push(['Operation', selectInput(it, 'op', [['add', '∪ Add to outline'], ['subtract', '− Cut from outline']], ch(true))]);
    }
    const kind = isObject ? it.source : it.kind;
    if (!isObject && kind !== 'poly' && it.kind !== 'line') {
      rows.push(['Shape', selectInput(it, 'kind', [['circle', 'Circle / ellipse'], ['rect', 'Rectangle']], ch(true))]);
    }
    if (kind === 'outline') {
      rows.push(['Region', selectInput(it, 'mode', [['fill', 'Filled (offset)'], ['band', 'Band between offsets']], ch(true))]);
      if (it.mode === 'band') rows.push(['Offsets in / out', pair(numInput(it, 'inner', 0.1, ch(false)), numInput(it, 'outer', 0.1, ch(false)))]);
      else rows.push(['Offset (mm)', numInput(it, 'offset', 0.1, ch(false))]);
      rows.push(['', hint('Offsets are measured from the outline: + outwards, − inwards.')]);
    } else if (kind === 'poly') {
      const retrace = () => this.traceText(it).then((ok) => { if (ok) this.changed(true); });
      const ta = document.createElement('textarea');
      ta.rows = 2;
      ta.value = it.text || '';
      ta.addEventListener('change', () => { it.text = ta.value; retrace(); });
      rows.push(['Text', ta]);
      rows.push(['Font', selectInput(it, 'font', FONTS, retrace)]);
      rows.push(['Bold', checkInput(it, 'bold', retrace)]);
      rows.push(['Centre x / y', withPick(pair(numInput(it, 'x', 0.5, ch(false)), numInput(it, 'y', 0.5, ch(false))), this.pickBtn('Pick the centre', (h) => this.moveTo(it, h)))]);
      rows.push(['Letter height', numInput(it, 'h', 0.5, () => { it.w = +(it.h * (it.aspect || 1)).toFixed(4); this.changed(false); })]);
      rows.push(['Rotation °', numInput(it, 'rot', 5, ch(false))]);
      rows.push(['', hint(`Width follows the text: ${fmtNum(it.w)} mm. Height is the height of the whole text block.`)]);
    } else if (kind === 'line') {
      rows.push(['Start x / y', withPick(pair(numInput(it, 'x', 0.5, ch(false)), numInput(it, 'y', 0.5, ch(false))),
        this.pickBtn('Pick the start point', (h) => Object.assign(it, { x: h.x, y: h.y })))]);
      rows.push(['End x / y', withPick(pair(numInput(it, 'x2', 0.5, ch(false)), numInput(it, 'y2', 0.5, ch(false))),
        this.pickBtn('Pick the end point', (h) => Object.assign(it, { x2: h.x, y2: h.y })))]);
      rows.push(['Width (mm)', numInput(it, 'width', 0.1, ch(false))]);
      rows.push(['Round ends', checkInput(it, 'round', ch(false))]);
    } else {
      rows.push(['Centre x / y', withPick(pair(numInput(it, 'x', 0.5, ch(false)), numInput(it, 'y', 0.5, ch(false))), this.pickBtn('Pick the centre', (h) => this.moveTo(it, h)))]);
      rows.push([kind === 'circle' ? 'Diameter w / h' : 'Size w / h', pair(numInput(it, 'w', 0.5, ch(false)), numInput(it, 'h', 0.5, ch(false)))]);
      rows.push(['Rotation °', numInput(it, 'rot', 5, ch(false))]);
      rows.push(['Ring width', numInput(it, 'stroke', 0.1, ch(false))]);
      rows.push(['', hint('Ring width 0 = filled; > 0 = only a ring (tube / frame) of that width.')]);
    }
    if (isObject) {
      // heights by clicking: a face gives its height, a corner / edge its z
      rows.push(['Bottom / top z', pair(
        withPick(numInput(it, 'z0', 0.5, ch(false)), this.pickBtn('Pick the bottom height (extrude from)', (h) => { it.z0 = h.z; })),
        withPick(numInput(it, 'z1', 0.5, ch(false)), this.pickBtn('Pick the top height (extrude to)', (h) => { it.z1 = h.z; })))]);
      rows.push(['', hint('⌖ = click on the part: a face gives its height, corners and edges snap.')]);
    }
    for (const [label, ctl] of rows) el.appendChild(field(label, ctl));
  }

  /** Re-render values of the open card (after dragging on the part). */
  refreshOpen() { if (this.selected) this.render(); }
}

// ------------------------------------------------------------------ small form helpers

const fmtNum = (v) => (+(+v || 0).toFixed(2)).toString();

function field(label, ctl) {
  const row = document.createElement('div');
  row.className = 'field';
  const lab = document.createElement('label');
  lab.textContent = label;
  row.append(lab, ctl);
  return row;
}

function hint(text) {
  const p = document.createElement('div');
  p.className = 'hint';
  p.style.margin = '0';
  p.textContent = text;
  return p;
}

function textInput(obj, key, after) {
  const i = document.createElement('input');
  i.value = obj[key] ?? '';
  i.addEventListener('change', () => { obj[key] = i.value.trim() || obj[key]; after(); });
  return i;
}

function numInput(obj, key, step, after) {
  const i = document.createElement('input');
  i.type = 'number';
  i.step = step;
  i.value = +(+obj[key] || 0).toFixed(4);
  i.addEventListener('input', () => {
    const v = parseFloat(i.value);
    if (!Number.isFinite(v)) return;
    obj[key] = v;
    after();
  });
  return i;
}

function selectInput(obj, key, opts, after) {
  const s = document.createElement('select');
  for (const [v, t] of opts) s.add(new Option(t, v, false, obj[key] === v));
  s.addEventListener('change', () => { obj[key] = s.value; after(); });
  return s;
}

function checkInput(obj, key, after) {
  const c = document.createElement('input');
  c.type = 'checkbox';
  c.checked = !!obj[key];
  c.addEventListener('change', () => { obj[key] = c.checked; after(); });
  return c;
}

function withPick(ctl, btn) {
  const d = document.createElement('div');
  d.className = 'with-pick';
  d.append(ctl, btn);
  return d;
}

function pair(a, b) {
  const d = document.createElement('div');
  d.className = 'pair';
  d.append(a, b);
  return d;
}
