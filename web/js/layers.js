// Design layers panel: mask × fill, turned into 3D (emboss / engrave / cut through) by the server.

const OPS = [
  ['emboss', 'Emboss (raise)'], ['engrave', 'Engrave (cut in)'], ['cut', 'Cut through'], ['guide', 'Guide only (no geometry)'],
];
const MASKS = [['face', 'Whole face'], ['rect', 'Rectangle'], ['ellipse', 'Ellipse'], ['image', 'Image / logo']];
const PATTERNS = [
  ['solid', 'Solid'], ['square', 'Square grid'], ['rect', 'Rectangular grid'], ['diamond', 'Diagonal / diamond'],
  ['triangle', 'Triangular (isometric)'], ['hex', 'Hexagonal (honeycomb)'], ['dots', 'Dots'], ['columns', 'Columns / slats'],
  ['radial', 'Radial (rings + rays)'],
];

export function nice(v) {
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));
}

let uid = 0;
const newId = () => `L${Date.now().toString(36)}${(uid++).toString(36)}`;

export function newLayer(kind, solution, extra = {}) {
  const [x0, y0, x1, y1] = solution.bbox;
  const h = y1 - y0;
  const t = solution.thickness;
  const s = nice(h / 8);
  const base = {
    id: newId(), visible: true, face: 'top', op: 'emboss', depth: nice(t * 0.15), margin: 0,
    mask: { kind: 'face', x: (x0 + x1) / 2, y: (y0 + y1) / 2, w: h * 0.6, h: h * 0.4, rot: 0, invert: false },
    fill: { pattern: 'solid', sx: s, sy: s, angle: 0, origin: 'center', ox: 0, oy: 0, width: nice(s / 8), use: 'lines' },
  };
  if (kind === 'grid') {
    Object.assign(base, { name: 'Grid', margin: nice(h / 20) });
    base.fill.pattern = 'square';
  } else if (kind === 'shape') {
    Object.assign(base, { name: 'Shape', op: 'engrave' });
    base.mask.kind = 'rect';
  } else if (kind === 'image') {
    Object.assign(base, { name: extra.name || 'Logo' });
    base.mask = { ...base.mask, kind: 'image', polygons: extra.polygons, h: h * 0.5, w: h * 0.5 * extra.aspect, aspect: extra.aspect };
  }
  return base;
}

/** Outline rings (model space) of a layer's mask, for the selection highlight and hit testing. */
export function maskRings(layer) {
  const m = layer.mask;
  if (!m || m.kind === 'face') return null;
  const rot = ((m.rot || 0) * Math.PI) / 180;
  const tf = ([u, v]) => [m.x + u * Math.cos(rot) - v * Math.sin(rot), m.y + u * Math.sin(rot) + v * Math.cos(rot)];
  if (m.kind === 'rect') return [[[-m.w / 2, -m.h / 2], [m.w / 2, -m.h / 2], [m.w / 2, m.h / 2], [-m.w / 2, m.h / 2]].map(tf)];
  if (m.kind === 'ellipse') {
    return [Array.from({ length: 64 }, (_, i) => tf([(m.w / 2) * Math.cos((i / 64) * 2 * Math.PI), (m.h / 2) * Math.sin((i / 64) * 2 * Math.PI)]))];
  }
  if (m.kind === 'image') return (m.polygons || []).flatMap((poly) => poly.map((ring) => ring.map(([u, v]) => tf([u * m.w, v * m.h]))));
  return null;
}

export function hitMask(layer, x, y) {
  const m = layer.mask;
  if (!m || m.kind === 'face') return false;
  const rot = (-(m.rot || 0) * Math.PI) / 180;
  const dx = x - m.x, dy = y - m.y;
  const u = dx * Math.cos(rot) - dy * Math.sin(rot), v = dx * Math.sin(rot) + dy * Math.cos(rot);
  return Math.abs(u) <= m.w / 2 && Math.abs(v) <= m.h / 2;
}

export class LayersPanel {
  constructor(root, { onChange, onSelect, unit }) {
    this.root = root;
    this.onChange = onChange;
    this.onSelect = onSelect;
    this.layers = [];
    this.selected = null;
    this.unit = unit;
  }

  set(layers) { this.layers = layers; this.render(); }

  add(layer) {
    this.layers.push(layer);
    this.selected = layer.id;
    this.render();
    this.onChange();
    this.onSelect(layer);
  }

  select(id) {
    this.selected = this.selected === id ? null : id;
    this.render();
    this.onSelect(this.layers.find((l) => l.id === this.selected) || null);
  }

  render() {
    const root = this.root;
    root.innerHTML = '';
    if (!this.layers.length) {
      root.innerHTML = '<div class="empty small">No design layers yet. Add a grid, a shape or an image —<br>each can be embossed, engraved or cut through.</div>';
      return;
    }
    this.layers.forEach((L, idx) => root.appendChild(this.card(L, idx)));
  }

  card(L, idx) {
    const card = document.createElement('div');
    card.className = `layer${L.id === this.selected ? ' open' : ''}${L.visible ? '' : ' hidden-layer'}`;
    const opLabel = { emboss: '↑ emboss', engrave: '↓ engrave', cut: '⊘ cut', guide: '┄ guide' }[L.op];
    card.innerHTML = `
      <div class="layer-head">
        <input type="checkbox" class="vis" title="Show / include in export" ${L.visible ? 'checked' : ''}>
        <span class="layer-name"></span>
        <span class="op-badge ${L.op}">${opLabel}</span>
        <button class="icon-btn up" title="Move up">↑</button>
        <button class="icon-btn down" title="Move down">↓</button>
        <button class="icon-btn del" title="Delete layer">✕</button>
      </div>
      <div class="layer-body"></div>`;
    card.querySelector('.layer-name').textContent = L.name;
    const head = card.querySelector('.layer-head');
    head.addEventListener('click', (e) => { if (!e.target.closest('input,button')) this.select(L.id); });
    card.querySelector('.vis').addEventListener('change', (e) => { L.visible = e.target.checked; this.render(); this.onChange(); });
    card.querySelector('.del').addEventListener('click', () => {
      this.layers.splice(idx, 1);
      if (this.selected === L.id) { this.selected = null; this.onSelect(null); }
      this.render(); this.onChange();
    });
    card.querySelector('.up').addEventListener('click', () => { if (idx > 0) { [this.layers[idx - 1], this.layers[idx]] = [L, this.layers[idx - 1]]; this.render(); this.onChange(); } });
    card.querySelector('.down').addEventListener('click', () => { if (idx < this.layers.length - 1) { [this.layers[idx + 1], this.layers[idx]] = [L, this.layers[idx + 1]]; this.render(); this.onChange(); } });
    if (L.id === this.selected) this.body(L, card.querySelector('.layer-body'));
    return card;
  }

  body(L, el) {
    const u = this.unit;
    const isPattern = L.fill.pattern !== 'solid';
    const m = L.mask;
    const rows = [
      ['Name', text(L, 'name')],
      ['Face', select(L, 'face', [['top', 'Front (top)'], ['bottom', 'Back (bottom)']])],
      ['Operation', select(L, 'op', OPS)],
      ...(L.op === 'emboss' || L.op === 'engrave' ? [[L.op === 'emboss' ? `Height (${u})` : `Depth (${u})`, num(L, 'depth', 0.01)]] : []),
      ['section', 'Mask — where it applies'],
      ['Mask', select(m, 'kind', MASKS.filter(([k]) => k !== 'image' || m.polygons), () => this.render())],
      ...(m.kind !== 'face' ? [
        [`Centre (${u})`, pair(num(m, 'x', 0.1), num(m, 'y', 0.1))],
        [`Size (${u})`, pair(num(m, 'w', 0.1, m.kind === 'image' ? (v) => { m.h = v / (m.aspect || 1); } : null),
          num(m, 'h', 0.1, m.kind === 'image' ? (v) => { m.w = v * (m.aspect || 1); } : null))],
        ['Rotation °', num(m, 'rot', 5)],
      ] : []),
      [`Edge margin (${u})`, num(L, 'margin', 0.1)],
      ['Invert mask', check(m, 'invert')],
      ['section', 'Fill'],
      ['Fill', select(L.fill, 'pattern', PATTERNS, () => this.render())],
      ...(isPattern ? [
        ['Use', select(L.fill, 'use', [['lines', 'Pattern lines (ribs)'], ['cells', 'Cells between lines']])],
        [`Spacing (${u})`, L.fill.pattern === 'rect' || L.fill.pattern === 'dots' ? pair(num(L.fill, 'sx', 0.1), num(L.fill, 'sy', 0.1)) : num(L.fill, 'sx', 0.1)],
        [`Line width (${u})`, num(L.fill, 'width', 0.01)],
        ['Angle °', num(L.fill, 'angle', 5)],
        ['Origin', select(L.fill, 'origin', [['center', 'Centre'], ['corner', 'Bottom-left corner']])],
        [`Offset (${u})`, pair(num(L.fill, 'ox', 0.1), num(L.fill, 'oy', 0.1))],
      ] : []),
    ];
    for (const [label, ctl] of rows) {
      if (label === 'section') {
        const h = document.createElement('div');
        h.className = 'layer-section';
        h.textContent = ctl;
        el.appendChild(h);
        continue;
      }
      const row = document.createElement('div');
      row.className = 'field';
      const lab = document.createElement('label');
      lab.textContent = label;
      row.append(lab, ctl);
      el.appendChild(row);
    }
    const self = this;
    function changed(rerender) {
      if (rerender) self.render();
      self.onChange();
      self.onSelect(L);
    }
    function text(obj, key) {
      const i = document.createElement('input');
      i.value = obj[key];
      i.addEventListener('change', () => { obj[key] = i.value.trim() || obj[key]; changed(true); });
      return i;
    }
    function num(obj, key, step, also) {
      const i = document.createElement('input');
      i.type = 'number';
      i.step = step;
      i.value = +(+obj[key] || 0).toFixed(4);
      i.dataset.key = key;
      i.addEventListener('input', () => {
        const v = parseFloat(i.value);
        if (!Number.isFinite(v)) return;
        obj[key] = v;
        also?.(v);
        changed(false);
      });
      i.addEventListener('change', () => self.render());
      return i;
    }
    function select(obj, key, opts, after) {
      const s = document.createElement('select');
      for (const [v, t] of opts) s.add(new Option(t, v, false, obj[key] === v));
      s.addEventListener('change', () => { obj[key] = s.value; after?.(); changed(true); });
      return s;
    }
    function check(obj, key) {
      const c = document.createElement('input');
      c.type = 'checkbox';
      c.checked = !!obj[key];
      c.addEventListener('change', () => { obj[key] = c.checked; changed(false); });
      return c;
    }
    function pair(a, b) {
      const d = document.createElement('div');
      d.className = 'pair';
      d.append(a, b);
      return d;
    }
  }

  /** Update displayed numeric values of the open layer after a drag. */
  refreshOpen() {
    if (this.selected) this.render();
  }
}
