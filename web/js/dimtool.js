// Adding / removing / promoting dimensions.
//
// The driving dimensions of each axis form a tree over the coordinate levels
// (one constraint per level, nothing over-defined). A new dimension between two
// levels therefore has to replace one constraint on the tree path between them:
// an estimated / assumed one is replaced automatically, otherwise the user picks
// which existing dimension becomes a driven reference.

const fmt = (v) => (+(+v).toFixed(4)).toString();

export function treePath(model, axis, from, to, skip = null) {
  const adj = new Map();
  for (const p of model.params) {
    if (p.kind !== 'linear' || p.axis !== axis || p.role !== 'driving' || p.id === skip) continue;
    for (const [a, b] of [[p.lo, p.hi], [p.hi, p.lo]]) {
      if (!adj.has(a)) adj.set(a, []);
      adj.get(a).push([b, p]);
    }
  }
  const prev = new Map([[from, null]]);
  const queue = [from];
  while (queue.length) {
    const n = queue.shift();
    if (n === to) break;
    for (const [m, p] of adj.get(n) || []) if (!prev.has(m)) { prev.set(m, [n, p]); queue.push(m); }
  }
  if (!prev.has(to)) return null;
  const path = [];
  for (let n = to; prev.get(n); n = prev.get(n)[0]) path.push(prev.get(n)[1]);
  return path;
}

/** What adding a driving dimension between levels a and b would do. */
export function planDimension(model, userSet, axis, a, b, skip = null) {
  const path = treePath(model, axis, a, b, skip) || [];
  const soft = path.find((p) => (p.source === 'estimated' || p.source === 'aligned') && !userSet.has(p.id));
  return { path, auto: soft || null };
}

export function addDimension(model, state, { axis, lo, hi, value, latRef, replace }) {
  const n = model.params.filter((p) => p.source === 'added').length + 1;
  const id = `u${Date.now().toString(36)}`;
  const param = {
    id, kind: 'linear', axis, lo, hi, value, unit: model.unit, source: 'added', role: 'driving', text: null,
    draw: null, attach: null, lat_draw: null, lat_ref: latRef,
    name: `Dimension ${n} (${axis === 'x' ? 'horizontal' : 'vertical'})`,
  };
  if (replace === 'reference') {
    param.role = 'reference';
  } else if (replace) {
    const old = model.params.find((p) => p.id === replace);
    if (old.source === 'estimated' || old.source === 'aligned') {
      model.params = model.params.filter((p) => p !== old);
      param.replaced = { removed: old };
    } else {
      old.role = 'reference';
      param.replaced = { demoted: old.id };
    }
  }
  model.params.push(param);
  state.values[id] = value;
  return param;
}

/** Remove a user-added dimension and restore what it replaced, keeping the geometry unchanged. */
export function deleteDimension(model, state, id) {
  const p = model.params.find((q) => q.id === id);
  if (!p) return;
  model.params = model.params.filter((q) => q !== p);
  delete state.values[id];
  state.userSet.delete(id);
  if (p.role !== 'driving') return;
  const connected = () => treePath(model, p.axis, p.lo, p.hi) !== null;
  const r = p.replaced;
  if (r?.removed) {
    const old = r.removed;
    const ok = treePath(model, p.axis, old.lo, old.hi) === null;
    if (ok) {
      model.params.push(old);
      state.values[old.id] = Math.abs(state.solution.levels[old.hi] - state.solution.levels[old.lo]) || old.value;
    }
  } else if (r?.demoted) {
    const old = model.params.find((q) => q.id === r.demoted);
    if (old && treePath(model, old.axis, old.lo, old.hi) === null) old.role = 'driving';
  }
  if (!connected()) {
    // nothing could be restored: keep the current size as an estimated (editable) value
    const lv = state.solution.levels;
    const [lo, hi] = lv[p.lo] <= lv[p.hi] ? [p.lo, p.hi] : [p.hi, p.lo];
    const est = { ...p, id: `e${Date.now().toString(36)}`, lo, hi, source: 'estimated', role: 'driving', name: `${p.name} (kept)`, replaced: undefined };
    est.value = lv[hi] - lv[lo];
    model.params.push(est);
    state.values[est.id] = est.value;
  }
}

/** Turn a reference dimension into a driving one, demoting/replacing `replace` on its path. */
export function promoteDimension(model, state, id, replace) {
  const p = model.params.find((q) => q.id === id);
  const old = model.params.find((q) => q.id === replace);
  if (!p) return;
  if (old?.source === 'estimated' || old?.source === 'aligned') model.params = model.params.filter((q) => q !== old);
  else if (old) old.role = 'reference';
  p.role = 'driving';
  state.values[id] = state.solution.values[id];
}

// ------------------------------------------------------------------ the picking tool
export class DimensionTool {
  constructor({ viewer, getState, onAdd, toast }) {
    this.viewer = viewer;
    this.getState = getState;
    this.onAdd = onAdd;
    this.toast = toast;
    this.active = false;
    this.first = null;
    this.popup = null;
    this.canvas = viewer.renderer.domElement;
    this.move = (e) => this.onMove(e);
    this.click = (e) => this.onClick(e);
    this.key = (e) => { if (e.key === 'Escape') this.stop(); };
  }

  start() {
    const { model, solution } = this.getState();
    if (!model || !solution) return;
    this.active = true;
    this.first = null;
    this.canvas.addEventListener('pointermove', this.move);
    this.canvas.addEventListener('click', this.click, true);
    window.addEventListener('keydown', this.key);
    this.canvas.style.cursor = 'crosshair';
    this.hint('Pick the first edge or corner (Esc to cancel)');
    document.getElementById('dimToolBtn').classList.add('on');
  }

  stop() {
    this.active = false;
    this.first = null;
    this.canvas.removeEventListener('pointermove', this.move);
    this.canvas.removeEventListener('click', this.click, true);
    window.removeEventListener('keydown', this.key);
    this.canvas.style.cursor = '';
    this.viewer.setHelpers();
    this.closePopup();
    this.hint(null);
    document.getElementById('dimToolBtn').classList.remove('on');
  }

  hint(text) {
    const el = document.getElementById('toolHint');
    el.hidden = !text;
    el.textContent = text || '';
  }

  /** Nearest pickable corner or straight axis-aligned edge under the cursor. */
  pick(e) {
    const { model, solution } = this.getState();
    const lv = solution.levels, z = solution.thickness;
    const P = (v) => [lv[v.x], lv[v.y]];
    let best = null;
    for (const v of model.vertices) {
      const p = P(v);
      const s = this.viewer.toScreen(p[0], p[1], z);
      const d = Math.hypot(s.x - e.clientX, s.y - e.clientY);
      if (d < 10 && (!best || d < best.d)) best = { d, type: 'vertex', x: v.x, y: v.y, pt: p };
    }
    if (best) return best;
    for (const ed of model.edges) {
      const [va, vb] = ed.v.map((i) => model.vertices[i]);
      const axis = va.x === vb.x ? 'x' : va.y === vb.y ? 'y' : null;
      if (!axis) continue;
      const a = P(va), b = P(vb);
      const sa = this.viewer.toScreen(a[0], a[1], z), sb = this.viewer.toScreen(b[0], b[1], z);
      const d = segDist(e.clientX, e.clientY, sa, sb);
      if (d < 8 && (!best || d < best.d)) best = { d, type: 'edge', axis, level: va[axis], seg: [a, b] };
    }
    return best;
  }

  feedback(cur) {
    const segs = [], pts = [];
    for (const p of [this.first, cur]) {
      if (!p) continue;
      if (p.type === 'edge') segs.push(p.seg); else pts.push(p.pt);
    }
    this.viewer.setHelpers({ segments: segs, points: pts });
  }

  onMove(e) {
    if (this.popup) return;
    this.feedback(this.pick(e));
  }

  onClick(e) {
    if (this.popup) return;
    e.stopPropagation();
    const p = this.pick(e);
    if (!p) { this.toast('Click on an edge or a corner of the part.', 'warning', 2500); return; }
    if (!this.first) {
      this.first = p;
      this.hint('Pick the second edge or corner — the click position sets where the dimension is drawn');
      this.feedback(null);
      return;
    }
    const axes = axesFor(this.first, p);
    if (!axes.length) { this.toast('Pick two parallel edges (or corners) to measure between.', 'warning'); return; }
    const facePt = this.viewer.pickFace(e.clientX, e.clientY, 'top');
    this.openPopup(this.first, p, axes, e, facePt);
  }

  openPopup(a, b, axes, e, facePt) {
    const { model, solution, userSet } = this.getState();
    const lv = solution.levels;
    const levelOf = (p, axis) => (p.type === 'edge' ? p.level : p[axis]);
    const measure = (axis) => Math.abs(lv[levelOf(b, axis)] - lv[levelOf(a, axis)]);
    let axis = axes.length === 2 ? (measure('x') >= measure('y') ? 'x' : 'y') : axes[0];

    const pop = document.createElement('div');
    pop.className = 'dim-popup';
    this.popup = pop;
    document.body.appendChild(pop);
    const vp = document.getElementById('viewport').getBoundingClientRect();
    pop.style.left = `${Math.min(e.clientX + 12, vp.right - 300)}px`;
    pop.style.top = `${Math.min(e.clientY + 12, vp.bottom - 260)}px`;

    const render = () => {
      const la = levelOf(a, axis), lb = levelOf(b, axis);
      if (la === lb) {
        pop.innerHTML = `<div class="dp-title">Same position</div><p>Both picks lie at the same ${axis === 'x' ? 'horizontal' : 'vertical'} position.</p>
          ${axes.length === 2 ? '<button class="btn small" data-a="swap">Measure the other direction</button>' : ''}<button class="btn small" data-a="cancel">Cancel</button>`;
      } else {
        const [lo, hi] = lv[la] <= lv[lb] ? [la, lb] : [lb, la];
        const plan = planDimension(model, userSet, axis, lo, hi);
        this.current = { axis, lo, hi, plan };
        const opts = plan.path.map((p) => `<option value="${p.id}">${escapeHtml(p.name)} = ${fmt(solution.values[p.id])}</option>`).join('');
        pop.innerHTML = `
          <div class="dp-title">New ${axis === 'x' ? 'horizontal' : 'vertical'} dimension</div>
          ${axes.length === 2 ? `<div class="seg"><button data-axis="x" class="${axis === 'x' ? 'on' : ''}">↔ Horizontal</button><button data-axis="y" class="${axis === 'y' ? 'on' : ''}">↕ Vertical</button></div>` : ''}
          <label class="dp-row">Value <input type="text" class="dp-val" value="${fmt(lv[hi] - lv[lo])}"> <span>${model.unit}</span></label>
          ${plan.auto
            ? `<p class="dp-info">Replaces the estimated value <b>${escapeHtml(plan.auto.name)}</b>.</p>`
            : `<p class="dp-info warn">This distance is already defined by other dimensions. Choose which one becomes a driven reference:</p>
               <select class="dp-rep">${opts}<option value="reference">— keep them; add the new one as a reference —</option></select>`}
          <div class="dp-actions"><button class="btn small" data-a="cancel">Cancel</button><button class="btn small primary" data-a="add">Add dimension</button></div>`;
        const lat = axis === 'x' ? facePt?.y : facePt?.x;
        this.lat = Number.isFinite(lat) ? lat : null;
        this.viewer.setHelpers({
          segments: [a, b].filter((p) => p.type === 'edge').map((p) => p.seg),
          points: [a, b].filter((p) => p.type === 'vertex').map((p) => p.pt),
          preview: axis === 'x' ? [[lv[lo], this.lat ?? 0], [lv[hi], this.lat ?? 0]] : [[this.lat ?? 0, lv[lo]], [this.lat ?? 0, lv[hi]]],
        });
        setTimeout(() => pop.querySelector('.dp-val')?.select(), 0);
      }
      pop.querySelectorAll('[data-axis]').forEach((btn) => btn.addEventListener('click', () => { axis = btn.dataset.axis; render(); }));
      pop.querySelector('[data-a=swap]')?.addEventListener('click', () => { axis = axis === 'x' ? 'y' : 'x'; render(); });
      pop.querySelector('[data-a=cancel]').addEventListener('click', () => this.stop());
      pop.querySelector('[data-a=add]')?.addEventListener('click', () => this.commit());
      pop.querySelector('.dp-val')?.addEventListener('keydown', (ev) => {
        ev.stopPropagation();
        if (ev.key === 'Enter') this.commit();
        if (ev.key === 'Escape') this.stop();
      });
    };
    render();
  }

  commit() {
    const { axis, lo, hi, plan } = this.current;
    const { solution } = this.getState();
    const raw = this.popup.querySelector('.dp-val').value;
    const value = evalNumber(raw);
    if (!(value > 0)) { this.toast('Enter a positive number.', 'warning'); return; }
    const replace = plan.auto ? plan.auto.id : this.popup.querySelector('.dp-rep')?.value || null;
    // anchor the label to the nearest level of the other axis, so it follows the geometry
    const other = axis === 'x' ? 'y' : 'x';
    let latRef = null;
    if (this.lat !== null) {
      let best = null;
      for (const [id, v] of Object.entries(solution.levels)) {
        if (id[0] !== other) continue;
        if (!best || Math.abs(v - this.lat) < Math.abs(best[1] - this.lat)) best = [id, v];
      }
      if (best) latRef = { level: best[0], offset: this.lat - best[1] };
    }
    this.onAdd({ axis, lo, hi, value, latRef, replace });
    this.stop();
  }

  closePopup() {
    this.popup?.remove();
    this.popup = null;
  }
}

function axesFor(a, b) {
  const can = (p, axis) => p.type === 'vertex' || p.axis === axis;
  return ['x', 'y'].filter((ax) => can(a, ax) && can(b, ax));
}

function segDist(px, py, a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const L2 = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / L2));
  return Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy));
}

export function evalNumber(text) {
  const s = String(text).replace(',', '.').trim();
  if (!/^[\d.+\-*/()\s]+$/.test(s)) return NaN;
  try { return Number(Function(`"use strict";return (${s})`)()); } catch { return NaN; }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
