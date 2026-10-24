// Bends panel: folds (roof / gutter / U shapes) and rolls (arcs, tubes), plus a tool to place a fold
// line by clicking on the part. Bends are applied by the server as the last 3D step.

let uid = 0;
const newId = () => `B${Date.now().toString(36)}${(uid++).toString(36)}`;
const fmt = (v) => (+(+v).toFixed(3)).toString();

export class BendsPanel {
  constructor(root, { onChange, getSolution, viewer, toast, ensureFlat }) {
    this.root = root;
    this.onChange = onChange;
    this.getSolution = getSolution;
    this.viewer = viewer;
    this.toast = toast;
    this.ensureFlat = ensureFlat;
    this.bends = [];
    this.unit = 'mm';
    this.info = {};
    this.placing = null;
  }

  set(bends) { this.bends = bends || []; this.render(); }

  setInfo(list) {
    this.info = Object.fromEntries((list || []).map((i) => [i.id, i]));
    this.render();
  }

  defaults(axis, pos) {
    const sol = this.getSolution();
    const t = sol.thickness;
    return {
      id: newId(), name: `Bend ${this.bends.length + 1}`, visible: true, mode: 'bend', axis, pos,
      angle: 90, radius: +(t).toFixed(4), toward: 'back',
    };
  }

  addRoll() {
    const sol = this.getSolution();
    if (!sol) return;
    const [x0, y0, x1, y1] = sol.bbox;
    const axis = x1 - x0 >= y1 - y0 ? 'x' : 'y';
    this.bends = this.bends.filter((b) => b.mode !== 'roll' || b.axis !== axis);
    this.bends.push({ ...this.defaults(axis, 0), name: 'Roll', mode: 'roll', angle: 180 });
    this.render();
    this.onChange();
  }

  /** Let the user click where the fold line goes (on the flat part). */
  async startPlacing() {
    const sol = this.getSolution();
    if (!sol) return;
    await this.ensureFlat();
    const [x0, y0, x1, y1] = this.getSolution().bbox;
    this.placing = { axis: x1 - x0 >= y1 - y0 ? 'x' : 'y' };
    const canvas = this.viewer.renderer.domElement;
    const hint = document.getElementById('toolHint');
    const show = () => {
      hint.hidden = false;
      hint.textContent = `Click where the fold line goes · fold line ${this.placing.axis === 'x' ? 'vertical' : 'horizontal'} (press R to rotate, Esc to cancel)`;
    };
    show();
    canvas.style.cursor = 'crosshair';
    const line = (pt) => {
      const [bx0, by0, bx1, by1] = this.getSolution().bbox;
      return this.placing.axis === 'x' ? [[pt.x, by0], [pt.x, by1]] : [[bx0, pt.y], [bx1, pt.y]];
    };
    const inside = (pt) => {
      const [bx0, by0, bx1, by1] = this.getSolution().bbox;
      return pt && pt.x >= bx0 && pt.x <= bx1 && pt.y >= by0 && pt.y <= by1;
    };
    const move = (e) => {
      const pt = this.viewer.pickFace(e.clientX, e.clientY, 'top');
      this.viewer.setHelpers(inside(pt) ? { segments: [line(pt)] } : {});
    };
    const done = () => {
      canvas.removeEventListener('pointermove', move);
      canvas.removeEventListener('click', click, true);
      window.removeEventListener('keydown', key);
      canvas.style.cursor = '';
      hint.hidden = true;
      this.viewer.setHelpers();
      this.placing = null;
    };
    const click = (e) => {
      e.stopPropagation();
      const pt = this.viewer.pickFace(e.clientX, e.clientY, 'top');
      if (!inside(pt)) { this.toast('Click on the part to place the fold line.', 'warning', 2500); return; }
      const axis = this.placing.axis;
      done();
      this.bends.push(this.defaults(axis, +(axis === 'x' ? pt.x : pt.y).toFixed(4)));
      this.render();
      this.onChange(true);
    };
    const key = (e) => {
      if (e.key === 'Escape') done();
      if (e.key === 'r' || e.key === 'R') { this.placing.axis = this.placing.axis === 'x' ? 'y' : 'x'; show(); }
    };
    canvas.addEventListener('pointermove', move);
    canvas.addEventListener('click', click, true);
    window.addEventListener('keydown', key);
  }

  render() {
    const r = this.root;
    r.innerHTML = '';
    if (!this.bends.length) {
      r.innerHTML = '<div class="empty small">No bends — the part is flat.<br>Add a fold (roof ∧, gutter ∨, U or Z shapes) or roll the whole part into an arc / tube.</div>';
      return;
    }
    const u = this.unit;
    this.bends.forEach((b, idx) => {
      const info = this.info[b.id];
      const card = document.createElement('div');
      card.className = `layer open${b.visible ? '' : ' hidden-layer'}`;
      card.innerHTML = `
        <div class="layer-head">
          <input type="checkbox" class="vis" ${b.visible ? 'checked' : ''} title="Apply this bend">
          <span class="layer-name"></span>
          <span class="op-badge ${b.mode === 'roll' ? 'guide' : 'emboss'}">${b.mode === 'roll' ? '◠ roll' : b.toward === 'back' ? '∧ fold' : '∨ fold'}</span>
          <button class="icon-btn del" title="Remove bend">✕</button>
        </div>
        <div class="layer-body"></div>`;
      card.querySelector('.layer-name').textContent = b.name;
      card.querySelector('.vis').addEventListener('change', (e) => { b.visible = e.target.checked; this.render(); this.onChange(); });
      card.querySelector('.del').addEventListener('click', () => { this.bends.splice(idx, 1); this.render(); this.onChange(); });
      const body = card.querySelector('.layer-body');
      const field = (label, el) => {
        const row = document.createElement('div');
        row.className = 'field';
        const l = document.createElement('label');
        l.textContent = label;
        row.append(l, el);
        body.appendChild(row);
      };
      const num = (key, step, min) => {
        const i = document.createElement('input');
        i.type = 'number';
        i.step = step;
        if (min !== undefined) i.min = min;
        i.value = fmt(b[key]);
        i.addEventListener('change', () => {
          const v = parseFloat(i.value);
          if (!Number.isFinite(v)) return;
          b[key] = v;
          this.onChange();
        });
        return i;
      };
      const sel = (key, opts) => {
        const s = document.createElement('select');
        for (const [v, t] of opts) s.add(new Option(t, v, false, b[key] === v));
        s.addEventListener('change', () => { b[key] = s.value; this.render(); this.onChange(); });
        return s;
      };
      field('Type', sel('mode', [['bend', 'Fold at a line'], ['roll', 'Roll the whole length']]));
      field('Shape', sel('toward', [['back', 'Front outside (roof ∧ / tube)'], ['front', 'Front inside (gutter ∨)']]));
      field('Fold line', sel('axis', [['x', 'Vertical (bends left–right)'], ['y', 'Horizontal (bends up–down)']]));
      field('Angle °', num('angle', 5, 1));
      if (b.mode !== 'roll') {
        field(`Position (${u})`, num('pos', 0.1));
        field(`Inner radius (${u})`, num('radius', 0.1, 0));
      }
      if (info) {
        const p = document.createElement('p');
        p.className = 'hint';
        p.textContent = b.mode === 'roll'
          ? `Inner radius ${fmt(info.radius)} ${u} (from the length and angle).`
          : `Bend zone ${fmt(info.start)}–${fmt(info.end)} ${u} (${fmt(info.length)} ${u} of material).`;
        body.appendChild(p);
      }
      r.appendChild(card);
    });
  }
}
