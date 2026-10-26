// Sketch mode of the 3D model workspace: draw rectangles, lines and circles on a plane; every size shows a
// label — type a number to lock it 🔒 (it then holds while you drag or change other sizes), click 🔒 to free
// it again. The server's sketch solver (planegcs, /api/model/sketch/solve) keeps the locks and the drawn
// horizontal / vertical rules; everything else stays free and follows the mouse.
//
// Sketch JSON (see auto3d/modeler/constraints.py): points {id: [u, v]}, entities (line a-b, circle c r,
// g = drawn together), constraints (h / v of a line), dims (locked sizes: len, dia, dx, dy, dist; an end of a
// distance can be a fixed reference {ref: [u, v]} on an edge of the part the sketch is on). A block is an
// outline taken from a picture / DXF / PDF part {t: 'block', polys, w0, h0, at, scale}: rigid, moved by
// dragging, sized by its width.

const fmt = (v) => (+(+v).toFixed(3)).toString();
const nice = (x) => { const p = 10 ** Math.floor(Math.log10(x)); return [1, 2, 5, 10].map((k) => k * p).find((s) => s >= x); };
const ORIGIN = 'O';
const HV_DEG = 3; // a line drawn within 3° of horizontal / vertical becomes exactly that

/** An arc (centre c, from a counter-clockwise to b, radius |a - c|) as points from a to b. */
export function arcPts(c, a, b, stepDeg = 5) {
  const r = Math.hypot(a[0] - c[0], a[1] - c[1]), t0 = Math.atan2(a[1] - c[1], a[0] - c[0]);
  let sweep = (Math.atan2(b[1] - c[1], b[0] - c[0]) - t0) % (2 * Math.PI);
  if (sweep <= 1e-12) sweep += 2 * Math.PI;
  const n = Math.max(2, Math.ceil((sweep * 180) / Math.PI / stepDeg)), out = [];
  for (let i = 0; i <= n; i++) out.push([c[0] + r * Math.cos(t0 + (sweep * i) / n), c[1] + r * Math.sin(t0 + (sweep * i) / n)]);
  out[0] = [...a];
  out[n] = [...b];
  return out;
}

/** The arc through three points: start s, end e, and m on it -> {c, a, b} (counter-clockwise a -> b), or null. */
export function arcThrough(s, e, m) {
  const d = 2 * (s[0] * (e[1] - m[1]) + e[0] * (m[1] - s[1]) + m[0] * (s[1] - e[1]));
  if (Math.abs(d) < 1e-9) return null; // in a line
  const q = (p) => p[0] * p[0] + p[1] * p[1];
  const c = [(q(s) * (e[1] - m[1]) + q(e) * (m[1] - s[1]) + q(m) * (s[1] - e[1])) / d,
    (q(s) * (m[0] - e[0]) + q(e) * (s[0] - m[0]) + q(m) * (e[0] - s[0])) / d];
  const ang = (p) => Math.atan2(p[1] - c[1], p[0] - c[0]), tau = 2 * Math.PI, norm = (x) => ((x % tau) + tau) % tau;
  const ccw = norm(ang(m) - ang(s)) < norm(ang(e) - ang(s)); // going counter-clockwise from s, m comes before e
  return ccw ? { c, a: s, b: e, swap: false } : { c, a: e, b: s, swap: true };
}

/** The two lines meeting at a sketch point (a corner that can be rounded), or null. */
export function cornerLines(f, pid) {
  const ls = f.entities.filter((e) => e.t === 'line' && (e.a === pid || e.b === pid));
  if (ls.length !== 2 || f.entities.some((e) => e.t !== 'line' && (e.a === pid || e.b === pid || e.c === pid))) return null;
  const P = (id) => (id === 'O' ? [0, 0] : f.points[id]);
  const [u1, u2] = ls.map((l) => { const q = P(l.a === pid ? l.b : l.a), p = P(pid), L = Math.hypot(q[0] - p[0], q[1] - p[1]); return L ? [(q[0] - p[0]) / L, (q[1] - p[1]) / L, L] : null; });
  if (!u1 || !u2 || Math.abs(u1[0] * u2[1] - u1[1] * u2[0]) < 1e-6) return null; // in a straight line: no corner
  return { lines: ls, u1, u2 };
}

/** Round the corner at point pid with radius r: the two lines get shorter and an arc joins them, tangent to both.
 *  The sharp corner stays as a point on both lines (sizes measured to it still hold — a rectangle keeps its width;
 *  dimensions can still start from it). newId(prefix) gives free ids. -> the arc's id, or throws. */
export function roundCorner(f, pid, r, newId) {
  const c = cornerLines(f, pid);
  if (!c) throw new Error('Round a corner where exactly two lines meet.');
  const { lines: [l1, l2], u1, u2 } = c;
  const p = pid === 'O' ? [0, 0] : f.points[pid];
  const half = Math.acos(Math.max(-1, Math.min(1, u1[0] * u2[0] + u1[1] * u2[1]))) / 2;
  const t = r / Math.tan(half);
  if (!(r > 0) || t >= u1[2] - 1e-9 || t >= u2[2] - 1e-9) throw new Error('That radius is too big for these lines.');
  const T1 = [p[0] + u1[0] * t, p[1] + u1[1] * t], T2 = [p[0] + u2[0] * t, p[1] + u2[1] * t];
  const bx = u1[0] + u2[0], by = u1[1] + u2[1], bl = Math.hypot(bx, by), k = r / Math.sin(half);
  const C = [p[0] + (bx / bl) * k, p[1] + (by / bl) * k], mid = [C[0] - (bx / bl) * r, C[1] - (by / bl) * r];
  const geo = arcThrough(T1, T2, mid);
  const r6 = (q) => q.map((v) => +v.toFixed(9));
  const t1 = newId('p'); f.points[t1] = r6(T1);
  const t2 = newId('p'); f.points[t2] = r6(T2);
  const cc = newId('p'); f.points[cc] = r6(C);
  for (const [l, tp] of [[l1, t1], [l2, t2]]) {
    // a locked length of a line now runs to the sharp corner (not to the shortened end)
    // (the line's own size label goes — it is shorter now; a rectangle shows its size on the opposite side)
    const len = f.dims.find((d) => d.t === 'len' && d.e === l.id);
    if (len) Object.assign(len, { t: 'dist', a: pid, b: l.a === pid ? l.b : l.a, e: undefined });
    if (l.a === pid) l.a = tp; else l.b = tp;
    f.hidden = [...new Set([...(f.hidden || []), `len:${l.id}`])];
  }
  f.dims.forEach((d) => { if (d.e === undefined) delete d.e; });
  const id = newId('a');
  f.entities.push({ id, t: 'arc', c: cc, a: geo.swap ? t2 : t1, b: geo.swap ? t1 : t2 });
  f.constraints.push({ id: newId('k'), t: 'tan', e: l1.id, arc: id, p: t1 }, { id: newId('k'), t: 'tan', e: l2.id, arc: id, p: t2 },
    { id: newId('k'), t: 'corner', p: pid, lines: [l1.id, l2.id] });
  return id;
}

const segDist = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L));
  return Math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]);
};

/** First-version sketches (rect / circle with their own size and centre) -> points, lines and circles. */
export function upgradeSketch(f) {
  const out = { ...f, points: { ...(f.points || {}) }, entities: [], constraints: [...(f.constraints || [])], dims: [...(f.dims || [])] };
  let n = 0;
  const pid = () => { while (out.points[`p${++n}`]); return `p${n}`; };
  let k = 0;
  const kid = (pre) => { while (out.entities.some((e) => e.id === `${pre}${++k}`) || out.constraints.some((c) => c.id === `${pre}${k}`)); return `${pre}${k}`; };
  for (const e of f.entities || []) {
    if (e.t === 'rect') {
      const hw = e.w / 2, hh = e.h / 2, g = kid('r');
      const ids = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => { const p = pid(); out.points[p] = [e.cx + a * hw, e.cy + b * hh]; return p; });
      ids.forEach((a, i) => {
        const id = kid('l');
        out.entities.push({ id, t: 'line', a, b: ids[(i + 1) % 4], g });
        out.constraints.push({ id: kid('k'), t: i % 2 ? 'v' : 'h', e: id });
      });
    } else if (e.t === 'circle' && !('c' in e)) {
      const p = pid();
      out.points[p] = [e.cx, e.cy];
      out.entities.push({ id: kid('c'), t: 'circle', c: p, r: e.d / 2 });
    } else out.entities.push(e);
  }
  return out;
}

export class Sketcher {
  /** m: the Modeler (view, frame(), toast, hint …) */
  constructor(m, feature, isNew) {
    this.m = m;
    this.f = upgradeSketch(feature);
    this.isNew = isNew;
    this.tool = isNew ? 'rect' : 'select';
    this.sel = null;     // {kind: 'point' | 'entity' | 'group', id}
    this.chain = null;   // line tool: the last point of the chain {id}, and the first one
    this.start = null;   // rect / circle: the first click {uv, id}
    this.cursor = null;  // snapped mouse position {uv, id}
    this.undo = [];
    this.solver = true;  // false when the sketch solver is not installed (sizes are then just set)
    this.dof = null;
  }

  get view() { return this.m.view; }
  frame() { return this.m.frame(); }
  P(id) { return id === ORIGIN ? [0, 0] : this.f.points[id]; }
  ent(id) { return this.f.entities.find((e) => e.id === id); }
  newId(pre) {
    const used = new Set([...Object.keys(this.f.points), ...this.f.entities.map((e) => e.id), ...this.f.constraints.map((c) => c.id), ...this.f.dims.map((d) => d.id)]);
    let n = 0;
    while (used.has(`${pre}${++n}`));
    return `${pre}${n}`;
  }
  step() { this.undo.push(structuredClone({ points: this.f.points, entities: this.f.entities, constraints: this.f.constraints, dims: this.f.dims })); }
  back() {
    const s = this.undo.pop();
    if (!s) return;
    Object.assign(this.f, s);
    this.sel = null;
    this.chain = null;
    this.changed();
  }

  changed() {
    if (this.isNew && this.f.entities.length && this.f.plane?.datum && this.m.$('.m-cmdbar [data-a^=plane-]')) this.m.renderCmdBar();
    this.m.renderProps();
    this.m.hint(this.hint());
    this.draw();
    this.refreshDof();
  }

  /** How many sizes are still free (after any change; asks the solver, nothing moves). */
  refreshDof() {
    clearTimeout(this.dofTimer);
    this.dofTimer = setTimeout(async () => {
      if (!this.solver || !this.f.entities.length) { if (this.dof !== null && !this.f.entities.length) { this.dof = null; this.m.renderProps(); } return; }
      const r = await this.solve();
      if (r.dof !== undefined && r.dof !== this.dof && this.m.sk === this) { this.dof = r.dof; this.m.renderProps(); }
    }, 120);
  }

  hint() {
    if (this.tool === 'rect') return this.start ? 'Click the second corner (Esc = stop drawing).' : 'Click the first corner of a rectangle.';
    if (this.tool === 'circle') return this.start ? 'Click to set the size (Esc = stop drawing).' : 'Click the centre of a circle.';
    if (this.tool === 'round') return 'Round corner: click a corner where two lines meet, then type the radius.';
    if (this.tool === 'arc') return !this.start ? 'Click where the arc starts.' : !this.arcEnd ? 'Click where the arc ends.' : 'Move the mouse to bend the arc, click to place it (Esc = stop drawing).';
    if (this.tool === 'line') return this.chain ? 'Click the next point — click the first point to close the shape, double-click or Esc to stop.' : 'Click where the line starts.';
    if (this.tool === 'dim') return this.dimA ? 'Now click the second one — the same line or circle again for its own size (Esc = start again).' : 'Dimension: click a point, a circle (its centre), a line or an edge of the part — then a second one.';
    return this.sel ? 'Drag to move it · click a size to type it and lock it 🔒 · Delete removes it.' : 'Click a shape or a corner to select it — or pick a drawing tool.';
  }

  setTool(t) {
    this.tool = t;
    this.start = null;
    this.arcEnd = null;
    this.chain = null;
    this.dimA = null;
    this.closeChooser();
    if (t !== 'select') this.sel = null;
    this.m.renderCmdBar();
    this.changed();
  }

  // ------------------------------------------------------------------ geometry helpers
  mpp() { return this.view.mmPerPixel(this.frame()); }

  /** Snap to existing points (they get connected), the origin, then the grid. Alt = no snapping. */
  snap(uv, free = false, skip = null) {
    if (free) return { uv };
    const tol = this.mpp() * 9;
    let best = null;
    // a sketch point on the origin wins over the origin itself (so the new line joins it)
    for (const [id, p] of [...Object.entries(this.f.points), [ORIGIN, [0, 0]]]) {
      if (id === skip) continue;
      const d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol && (!best || d < best.d)) best = { id, d, uv: [...p] };
    }
    if (best) return best;
    for (const r of this.refs().points) {
      const d = Math.hypot(r[0] - uv[0], r[1] - uv[1]);
      if (d < tol && (!best || d < best.d)) best = { d, uv: [...r], ref: true };
    }
    if (best) return best;
    const g = this.gridStep();
    return { uv: [Math.round(uv[0] / g) * g, Math.round(uv[1] / g) * g].map((x) => +x.toFixed(6)) };
  }

  gridStep() { return nice(this.mpp() * 12); }

  /** A new point at a snapped place; on the origin it is locked there (shown as x 0 / y 0 🔒, can be freed). */
  pointAt(s) {
    if (s.id && s.id !== ORIGIN) return s.id;
    const id = this.newId('p');
    this.f.points[id] = [...s.uv];
    if (s.id === ORIGIN) {
      this.f.dims.push({ id: this.newId('d'), t: 'dx', a: ORIGIN, b: id, v: 0 }, { id: this.newId('d'), t: 'dy', a: ORIGIN, b: id, v: 0 });
    }
    return id;
  }

  groupOf(e) { return e?.g ? this.f.entities.filter((x) => x.g === e.g) : e ? [e] : []; }

  pointsOfSel(sel = this.sel) {
    if (!sel) return [];
    if (sel.kind === 'point') return [sel.id];
    if (sel.kind === 'entity' && this.ent(sel.id)?.t === 'block') return [];
    const es = sel.kind === 'group' ? this.f.entities.filter((e) => e.g === sel.id) : [this.ent(sel.id)].filter(Boolean);
    return [...new Set(es.flatMap((e) => (e.t === 'line' ? [e.a, e.b] : e.t === 'arc' ? [e.a, e.b, e.c] : [e.c])))].filter((p) => p !== ORIGIN);
  }

  /** What is under the mouse: a point, a line, a circle (edge or inside) or a rectangle (inside). */
  hit(uv) {
    const tol = this.mpp() * 7;
    let best = null;
    const consider = (d, sel) => { if (d < tol && (!best || d < best.d)) best = { d, sel }; };
    for (const [id, p] of Object.entries(this.f.points)) consider(Math.hypot(p[0] - uv[0], p[1] - uv[1]) * 0.6, { kind: 'point', id });
    for (const e of this.f.entities) {
      if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
        const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
        consider(Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]), e.g ? { kind: 'group', id: e.g } : { kind: 'entity', id: e.id });
      } else if (e.t === 'circle') {
        const c = this.P(e.c), d = Math.hypot(c[0] - uv[0], c[1] - uv[1]);
        consider(Math.abs(d - e.r), { kind: 'entity', id: e.id });
        if (d < e.r) consider(tol * 0.9, { kind: 'entity', id: e.id });
      } else if (e.t === 'arc') {
        consider(this.arcDist(e, uv), { kind: 'entity', id: e.id });
      }
    }
    for (const e of this.f.entities) {
      if (e.t !== 'block') continue;
      for (const r of this.blockRings(e)) {
        for (let i = 0; i < r.length; i++) {
          const a = r[i], b = r[(i + 1) % r.length], dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
          const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
          consider(Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]), { kind: 'entity', id: e.id });
        }
      }
    }
    if (best) return best.sel;
    const blk = this.f.entities.find((e) => e.t === 'block' && this.inBlock(e, uv));
    if (blk) return { kind: 'entity', id: blk.id };
    // inside a rectangle (the smallest one)
    const groups = [...new Set(this.f.entities.filter((e) => e.g).map((e) => e.g))];
    let inside = null;
    for (const g of groups) {
      const ps = this.pointsOfSel({ kind: 'group', id: g }).map((p) => this.P(p));
      const xs = ps.map((p) => p[0]), ys = ps.map((p) => p[1]);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      if (uv[0] > x0 && uv[0] < x1 && uv[1] > y0 && uv[1] < y1) {
        const area = (x1 - x0) * (y1 - y0);
        if (!inside || area < inside.area) inside = { area, sel: { kind: 'group', id: g } };
      }
    }
    return inside?.sel || null;
  }

  arcOf(e) { return arcPts(this.P(e.c), this.P(e.a), this.P(e.b)); }
  arcR(e) { const c = this.P(e.c), a = this.P(e.a); return Math.hypot(a[0] - c[0], a[1] - c[1]); }
  arcDist(e, uv) {
    const ps = this.arcOf(e);
    let d = Infinity;
    for (let i = 0; i + 1 < ps.length; i++) d = Math.min(d, segDist(uv, ps[i], ps[i + 1]));
    return d;
  }

  // ------------------------------------------------------------------ solving
  async solve(drag = null, keep = null) {
    if (!this.solver) return { ok: true };
    const res = await fetch('/api/model/sketch/solve', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sketch: this.f, drag, keep }) });
    let r;
    try { r = await res.json(); } catch { return { ok: false, error: `The sketch could not be solved (server error ${res.status}).` }; }
    if (res.status === 501) { this.solver = false; this.m.toast(r.error, 'warning', 8000); return { ok: true }; }
    if (!res.ok) return { ok: false, error: r.error };
    return r;
  }

  apply(r) {
    if (r.points) for (const [k, v] of Object.entries(r.points)) if (this.f.points[k]) this.f.points[k] = v;
    if (r.radii) for (const [k, v] of Object.entries(r.radii)) { const e = this.ent(k); if (e) e.r = v; }
    if (r.dof !== undefined) this.dof = r.dof;
    for (const d of this.f.dims) if (d.free) d.v = +this.measure(d).toFixed(6);
  }

  /** Change the locks (dims) and solve; when the result contradicts other locks, go back and say which. */
  async relock(mutate, hold = null, keep = null) {
    const before = structuredClone(this.f);
    this.step();
    mutate();
    const r = await this.solve(hold, keep);
    if (!r.ok) {
      Object.assign(this.f, before);
      this.undo.pop();
      const names = (r.conflicts || []).map((id) => this.dimName(this.f.dims.find((d) => d.id === id))).filter(Boolean);
      this.m.toast(r.error || (names.length ? `That does not fit the other locked sizes (${names.join(', ')}) — unlock one of them first.`
        : 'That does not fit the other locked sizes — unlock one of them first.'), 'error', 7000);
    } else this.apply(r);
    this.changed();
  }

  dimName(d) {
    if (!d) return '';
    if (d.t === 'dia') return `Ø${fmt(d.v)}`;
    if (d.t === 'rad') return `R${fmt(d.v)}`;
    if (d.t === 'dx') return `x ${fmt(d.v)}`;
    if (d.t === 'dy') return `y ${fmt(d.v)}`;
    return fmt(d.v);
  }

  /** The value a size has now (locked or not). */
  measure(spec) {
    if (spec.t === 'bw') { const e = this.ent(spec.e); return e.w0 * (e.scale || 1); }
    if (spec.t === 'len') { const e = this.ent(spec.e), a = this.P(e.a), b = this.P(e.b); return Math.hypot(b[0] - a[0], b[1] - a[1]); }
    if (spec.t === 'dia') return 2 * this.ent(spec.e).r;
    if (spec.t === 'rad') return this.arcR(this.ent(spec.e));
    const a = this.endUV(spec.a), b = this.endUV(spec.b);
    if (spec.t === 'dist') return Math.hypot(b[0] - a[0], b[1] - a[1]);
    return spec.t === 'dx' ? b[0] - a[0] : b[1] - a[1];
  }

  /** An end of a distance: a sketch point id, the origin, or a fixed reference {ref: [u, v]}. */
  endUV(x) { return x && typeof x === 'object' ? x.ref : this.P(x); }

  findDim(spec) {
    const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
    return this.f.dims.find((d) => d.t === spec.t && (spec.e ? d.e === spec.e : same(d.a, spec.a) && same(d.b, spec.b)));
  }

  /** Type a value: the size is locked at it. Holds the point it is measured from, so it grows from there. */
  async setSize(spec, value) {
    if (spec.t === 'bw') { this.sel = { kind: 'entity', id: spec.e }; this.setBlock('w', value); return; }
    let v = parseFloat(String(value).replace(',', '.'));
    if (!Number.isFinite(v) || (['len', 'dia', 'rad', 'dist'].includes(spec.t) && v <= 0)) {
      this.m.toast('A size must be greater than zero.', 'error');
      return;
    }
    let hold = null;
    if (spec.t === 'dx' || spec.t === 'dy') {
      const cur = this.measure(spec);
      if (v > 0 && cur < 0) v = -v; // "12 to the left" stays to the left
    }
    // a distance is measured from a (it stays) to b (it moves): hold a when it is a sketch point
    if (['dx', 'dy', 'dist'].includes(spec.t) && typeof spec.a === 'string' && spec.a !== ORIGIN && this.f.points[spec.a]) hold = { [spec.a]: this.P(spec.a) };
    if (spec.t === 'len') { const e = this.ent(spec.e); if (e.a !== ORIGIN) hold = { [e.a]: this.P(e.a) }; }
    if (spec.t === 'dia' || spec.t === 'rad') {
      // a rounded corner keeps its sharp corner (the rounding slides along the lines), a circle / arc its centre
      const e = this.ent(spec.e), k = this.f.constraints.find((c) => c.t === 'corner' && this.f.constraints.some((t) => t.t === 'tan' && t.arc === e.id && c.lines.includes(t.e)));
      const keep = k ? k.p : e.c;
      if (keep !== ORIGIN) hold = { [keep]: this.P(keep) };
    }
    if (!this.solver) { this.setDirect(spec, v); return; }
    await this.relock(() => {
      const d = this.findDim(spec);
      if (d) { d.v = v; delete d.free; } else this.f.dims.push({ id: this.newId('d'), ...spec, v });
      this.unhide(spec);
    }, hold, this.keepFor(spec));
  }

  /** A typed size along x keeps every point's y (and the other way round), when the sketch allows it. */
  keepFor(spec) {
    if (spec.t === 'dx') return 'v';
    if (spec.t === 'dy') return 'u';
    const a = spec.t === 'len' ? this.ent(spec.e) : spec.t === 'dist' ? spec : null;
    if (!a) return null;
    const p = this.endUV(a.a), q = this.endUV(a.b);
    if (!p || !q) return null;
    return Math.abs(p[1] - q[1]) < 1e-7 ? 'v' : Math.abs(p[0] - q[0]) < 1e-7 ? 'u' : null;
  }

  /** Without the solver: set the size directly (no locks). */
  setDirect(spec, v) {
    this.step();
    if (spec.t === 'dia') this.ent(spec.e).r = v / 2;
    else if (spec.t === 'rad') {
      const e = this.ent(spec.e), c = this.P(e.c);
      for (const k of [e.a, e.b]) {
        const p = this.P(k), L = Math.hypot(p[0] - c[0], p[1] - c[1]) || 1;
        if (this.f.points[k]) this.f.points[k] = [c[0] + ((p[0] - c[0]) / L) * v, c[1] + ((p[1] - c[1]) / L) * v];
      }
    } else if (spec.t === 'len') {
      const e = this.ent(spec.e), a = this.P(e.a), b = this.P(e.b), L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      this.f.points[e.b] = [a[0] + ((b[0] - a[0]) / L) * v, a[1] + ((b[1] - a[1]) / L) * v];
    } else {
      const p = this.f.points[spec.b], a = this.P(spec.a);
      if (p) p[spec.t === 'dx' ? 0 : 1] = a[spec.t === 'dx' ? 0 : 1] + v;
    }
    this.changed();
  }

  async toggleLock(spec) {
    const d = this.findDim(spec);
    // a shape's own size: unlocked = no dimension; a dimension you added: unlocked = it only measures (🔓)
    if (d && (d.t === 'len' || d.t === 'dia' || d.t === 'rad')) await this.relock(() => { this.f.dims = this.f.dims.filter((x) => x !== d); });
    else if (d && !d.free) await this.relock(() => { d.free = true; });
    else if (d) await this.relock(() => { delete d.free; d.v = +this.measure(d).toFixed(6); });
    else await this.relock(() => this.f.dims.push({ id: this.newId('d'), ...spec, v: +this.measure(spec).toFixed(6) }));
  }

  // ------------------------------------------------------------------ hiding a shape's own sizes
  sizeKey(spec) { return `${spec.t}:${spec.e}`; }
  isHidden(spec) { return (this.f.hidden || []).includes(this.sizeKey(spec)); }
  unhide(spec) { if (spec.e) this.f.hidden = (this.f.hidden || []).filter((k) => k !== this.sizeKey(spec)); }

  /** ✕ on a shape's size: no lock on it any more, and its label is not shown (↔ Dimension on it brings it back). */
  async hideSize(spec) {
    await this.relock(() => {
      this.f.dims = this.f.dims.filter((d) => !(d.t === spec.t && d.e === spec.e));
      this.f.hidden = [...new Set([...(this.f.hidden || []), this.sizeKey(spec)])];
    });
  }

  /** The sizes ✕ hid (not the lengths of lines shortened by a rounded corner — those stay hidden). */
  userHidden() {
    const rounded = new Set(this.f.constraints.filter((c) => c.t === 'corner').flatMap((c) => c.lines.map((l) => `len:${l}`)));
    return (this.f.hidden || []).filter((k) => !rounded.has(k));
  }

  async showAllSizes() { const keep = new Set(this.userHidden()); await this.relock(() => { this.f.hidden = this.f.hidden.filter((k) => !keep.has(k)); }); }

  deleteSel() {
    if (!this.sel) return;
    this.step();
    const s = this.sel;
    let gone;
    if (s.kind === 'point') gone = new Set(this.f.entities.filter((e) => e.a === s.id || e.b === s.id || e.c === s.id).map((e) => e.id));
    else gone = new Set(s.kind === 'group' ? this.f.entities.filter((e) => e.g === s.id).map((e) => e.id) : [s.id]);
    this.f.entities = this.f.entities.filter((e) => !gone.has(e.id));
    this.f.constraints = this.f.constraints.filter((c) => !gone.has(c.e) && !gone.has(c.arc) && !(c.lines || []).some((l) => gone.has(l))
      && !(s.kind === 'point' && c.p === s.id && c.t === 'corner'));
    const used = new Set([...this.f.entities.flatMap((e) => [e.a, e.b, e.c]), ...this.f.constraints.filter((c) => c.t === 'corner').map((c) => c.p)]);
    for (const p of Object.keys(this.f.points)) if (!used.has(p)) delete this.f.points[p];
    this.f.dims = this.f.dims.filter((d) => !gone.has(d.e) && (!d.a || d.a === ORIGIN || this.f.points[d.a]) && (!d.b || this.f.points[d.b]));
    this.sel = null;
    this.changed();
  }

  // ------------------------------------------------------------------ mouse
  down(e) {
    if (this.tool !== 'select') return null;
    const uv = this.view.planePoint(e.clientX, e.clientY, this.frame());
    const h = uv && this.hit(uv);
    if (!h) return null;
    this.sel = h;
    this.changed();
    const blk = h.kind === 'entity' && this.ent(h.id)?.t === 'block' ? this.ent(h.id) : null;
    if (blk) return { uv0: uv, block: blk, from: [...blk.at], moved: false };
    const ids = this.pointsOfSel(h);
    return { uv0: uv, ids, from: Object.fromEntries(ids.map((id) => [id, [...this.P(id)]])), moved: false, snapshot: structuredClone(this.f) };
  }

  async move(e, drag) {
    const uv = this.view.planePoint(e.clientX, e.clientY, this.frame());
    if (!uv) return;
    if (drag?.block) {
      const g = e.altKey ? 0 : this.gridStep();
      let du = uv[0] - drag.uv0[0], dv = uv[1] - drag.uv0[1];
      if (g) { du = Math.round(du / g) * g; dv = Math.round(dv / g) * g; }
      if (!drag.moved && (du || dv)) { drag.moved = true; this.step(); }
      drag.block.at = [+(drag.from[0] + du).toFixed(6), +(drag.from[1] + dv).toFixed(6)];
      this.draw();
      return;
    }
    if (drag) {
      let du = uv[0] - drag.uv0[0], dv = uv[1] - drag.uv0[1];
      if (drag.ids.length === 1 && !e.altKey) { // a single point snaps to the grid / other points
        const s = this.snap([drag.from[drag.ids[0]][0] + du, drag.from[drag.ids[0]][1] + dv], false, drag.ids[0]);
        du = s.uv[0] - drag.from[drag.ids[0]][0];
        dv = s.uv[1] - drag.from[drag.ids[0]][1];
      } else if (!e.altKey) { const g = this.gridStep(); du = Math.round(du / g) * g; dv = Math.round(dv / g) * g; }
      const target = Object.fromEntries(drag.ids.map((id) => [id, [drag.from[id][0] + du, drag.from[id][1] + dv]]));
      if (!drag.moved && (du || dv)) { drag.moved = true; this.step(); }
      if (!drag.moved) return;
      drag.pending = target;
      if (drag.busy) return; // one solve at a time; the last position wins
      drag.busy = true;
      while (drag.pending) {
        const t = drag.pending;
        drag.pending = null;
        if (this.solver) {
          const r = await this.solve(t);
          if (r.ok || r.points) this.apply(r);
        } else for (const [k, v] of Object.entries(t)) this.f.points[k] = v;
        this.draw();
      }
      drag.busy = false;
      return;
    }
    this.cursor = this.snap(uv, e.altKey);
    const hv = this.tool === 'round' ? this.cornerAt(uv)
      : this.tool === 'dim' ? this.pickTarget(uv)
      : this.tool === 'select' ? ((h) => (h?.kind === 'point' ? { kind: 'point', end: h.id, uv: this.P(h.id) } : h))(this.hit(uv))
      : this.cursor.id || this.cursor.ref ? { kind: 'point', end: this.cursor.ref ? { ref: this.cursor.uv } : this.cursor.id, uv: this.cursor.uv } : null;
    const key = JSON.stringify(hv && { ...hv, d: undefined });
    const changed = key !== this.hoverKey;
    this.hover = hv;
    this.hoverKey = key;
    if (this.tool !== 'select' || changed) this.draw();
    this.view.renderer.domElement.style.cursor = this.tool === 'select' ? (this.hit(uv) ? 'move' : '') : 'crosshair';
  }

  async up(drag) {
    if (!drag) return;
    while (drag.busy) await new Promise((r) => setTimeout(r, 15));
    if (!drag.moved) return;
    this.changed();
  }

  click(e) {
    const uv0 = this.view.planePoint(e.clientX, e.clientY, this.frame());
    if (!uv0) return;
    if (this.tool === 'select') { this.sel = this.hit(uv0); this.changed(); return; }
    if (this.tool === 'dim') { this.dimClick(uv0, e); return; }
    const s = this.snap(uv0, e.altKey);
    if (this.tool === 'line') { this.linePoint(s, e.detail >= 2); return; }
    if (this.tool === 'arc') { this.arcPoint(s); return; }
    if (this.tool === 'round') { this.roundAt(uv0); return; }
    if (!this.start) { this.start = s; this.m.hint(this.hint()); this.draw(); return; }
    const a = this.start;
    this.start = null;
    if (this.tool === 'rect') this.addRect(a, s);
    else this.addCircle(a, s);
  }

  addRect(a, b) {
    const [u0, v0] = a.uv, [u1, v1] = b.uv;
    if (Math.abs(u1 - u0) < 1e-9 || Math.abs(v1 - v0) < 1e-9) { this.changed(); return; }
    this.step();
    const g = this.newId('r');
    // corners in order from the first click; the first corner may be an existing point (connected)
    const p1 = this.pointAt(a);
    const ids = [p1];
    for (const uv of [[u1, v0], [u1, v1], [u0, v1]]) { const id = this.newId('p'); this.f.points[id] = uv; ids.push(id); }
    if (b.id && b.id !== ORIGIN) { delete this.f.points[ids[2]]; ids[2] = b.id; }
    ids.forEach((p, i) => {
      const id = this.newId('l');
      this.f.entities.push({ id, t: 'line', a: p, b: ids[(i + 1) % 4], g });
      this.f.constraints.push({ id: this.newId('k'), t: i % 2 ? 'v' : 'h', e: id });
    });
    this.sel = { kind: 'group', id: g };
    this.changed();
  }

  addCircle(a, b) {
    const r = Math.hypot(b.uv[0] - a.uv[0], b.uv[1] - a.uv[1]);
    if (r < 1e-9) { this.changed(); return; }
    this.step();
    const c = this.pointAt(a);
    const id = this.newId('c');
    this.f.entities.push({ id, t: 'circle', c, r: +r.toFixed(6) });
    this.sel = { kind: 'entity', id };
    this.changed();
  }

  /** A corner under the mouse that can be rounded (two lines meet there) -> a hover target, or null. */
  cornerAt(uv) {
    const tol = this.mpp() * 10;
    let best = null;
    for (const [id, p] of Object.entries(this.f.points)) {
      const d = Math.hypot(p[0] - uv[0], p[1] - uv[1]);
      if (d < tol && (!best || d < best.d) && cornerLines(this.f, id)) best = { d, kind: 'point', end: id, uv: p, corner: true };
    }
    return best;
  }

  /** ◜ Round corner: the corner gets an arc (radius: a fifth of the shorter line, locked), then type the radius. */
  async roundAt(uv) {
    const h = this.cornerAt(uv);
    if (!h) { this.m.toast('Click a corner where two lines meet.', 'info', 3000); return; }
    const { u1, u2 } = cornerLines(this.f, h.end), r0 = Math.min(u1[2], u2[2]) / 5;
    const r = r0 >= 1 ? Math.round(r0) : +r0.toFixed(1);
    let arc = null;
    await this.relock(() => {
      arc = roundCorner(this.f, h.end, r, (pre) => this.newId(pre));
      this.f.dims.push({ id: this.newId('d'), t: 'rad', e: arc, v: r });
    });
    if (!arc || !this.ent(arc)) return;
    this.sel = { kind: 'entity', id: arc };
    this.changed();
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    const d = this.findDim({ t: 'rad', e: arc });
    const el = d && this.m.els.viewport.querySelector(`.sk-label[data-dim="${d.id}"]`);
    if (el) this.editLabel(el, { t: 'rad', e: arc });
  }

  /** Arc tool: start, end, then a point it goes through (the bend). */
  arcPoint(s) {
    if (!this.start) { this.start = s; this.m.hint(this.hint()); this.draw(); return; }
    if (!this.arcEnd) {
      if (Math.hypot(s.uv[0] - this.start.uv[0], s.uv[1] - this.start.uv[1]) < 1e-9) return;
      this.arcEnd = s;
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const geo = arcThrough(this.start.uv, this.arcEnd.uv, s.uv);
    if (!geo) { this.m.toast('Move the mouse to one side to bend the arc.', 'info', 3000); return; }
    this.step();
    const [p, q] = geo.swap ? [this.arcEnd, this.start] : [this.start, this.arcEnd];
    const a = this.pointAt(p), b = this.pointAt(q), c = this.newId('p');
    this.f.points[c] = geo.c.map((x) => +x.toFixed(6));
    const id = this.newId('a');
    this.f.entities.push({ id, t: 'arc', c, a, b });
    this.start = null;
    this.arcEnd = null;
    this.sel = { kind: 'entity', id };
    this.changed();
  }

  linePoint(s, dbl) {
    if (dbl) { this.chain = null; this.changed(); return; }
    if (!this.chain) {
      this.step();
      this.chain = { last: this.pointAt(s), first: null };
      this.chain.first = this.chain.last;
      this.m.hint(this.hint());
      this.draw();
      return;
    }
    const prev = this.chain.last;
    const closing = s.id && s.id === this.chain.first;
    if (s.id === prev) return;
    const a = this.P(prev), b0 = s.id ? this.P(s.id) : s.uv;
    if (Math.hypot(b0[0] - a[0], b0[1] - a[1]) < 1e-9) return;
    this.step(); // every line is its own undo step
    const p = closing ? this.chain.first : this.pointAt(s);
    const b = this.P(p);
    const id = this.newId('l');
    this.f.entities.push({ id, t: 'line', a: prev, b: p });
    // nearly horizontal / vertical -> exactly
    const ang = Math.abs((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI);
    if (Math.min(ang, 180 - ang) < HV_DEG) { this.f.constraints.push({ id: this.newId('k'), t: 'h', e: id }); this.f.points[p] = [b[0], a[1]]; }
    else if (Math.abs(ang - 90) < HV_DEG) { this.f.constraints.push({ id: this.newId('k'), t: 'v', e: id }); this.f.points[p] = [a[0], b[1]]; }
    if (closing || (s.id && s.id !== ORIGIN && s.id !== prev && this.f.entities.some((e) => e.id !== id && (e.a === s.id || e.b === s.id)))) {
      this.chain = null; // closed, or joined onto another shape: this line is done
      this.sel = { kind: 'entity', id };
    } else this.chain.last = p;
    this.changed();
  }

  key(e) {
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); this.back(); return true; }
    if (e.key === 'Escape') {
      if (this.chooser) this.closeChooser();
      else if (this.start || this.chain || this.dimA) { this.start = null; this.arcEnd = null; this.chain = null; this.dimA = null; this.changed(); } else this.setTool('select');
      return true;
    }
    if (e.key === 'Delete' || e.key === 'Backspace') { this.deleteSel(); return true; }
    if (k === 'r') this.setTool('rect');
    if (k === 'l') this.setTool('line');
    if (k === 'c') this.setTool('circle');
    if (k === 'a') this.setTool('arc');
    if (k === 'f') this.setTool('round');
    if (k === 'd') this.setTool('dim');
    return false;
  }



  // ------------------------------------------------------------------ blocks (outlines from other parts)
  /** The rings of a block in sketch coordinates. */
  blockRings(e) {
    const k = e.scale || 1, [au, av] = e.at || [0, 0];
    return (e.polys || []).flatMap((poly) => poly.map((r) => r.map(([x, y]) => [au + k * x, av + k * y])));
  }

  /** Is uv inside the block's outline (even-odd over all its rings)? */
  inBlock(e, uv) {
    let inside = false;
    for (const r of this.blockRings(e)) {
      for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
        const [xi, yi] = r[i], [xj, yj] = r[j];
        if ((yi > uv[1]) !== (yj > uv[1]) && uv[0] < ((xj - xi) * (uv[1] - yi)) / (yj - yi) + xi) inside = !inside;
      }
    }
    return inside;
  }

  /** Add an outline as a block: on a face it is centred on the face's centre, on a plane its corner is at the origin. */
  addBlock(o) {
    this.step();
    const id = this.newId('b');
    const onFace = !this.f.plane?.datum;
    this.f.entities.push({ id, t: 'block', name: o.name, polys: o.polygons, w0: o.width, h0: o.height, scale: 1,
      at: onFace ? [-o.width / 2, -o.height / 2] : [0, 0] });
    this.sel = { kind: 'entity', id };
    this.setTool('select');
    this.m.view.lookAt(this.frame(), this.m.sketchSpan());
    this.changed();
  }

  setBlock(k, value) {
    const e = this.ent(this.sel?.id);
    const v = parseFloat(String(value).replace(',', '.'));
    if (!e || e.t !== 'block' || !Number.isFinite(v)) return;
    if (k === 'w' && v <= 0) { this.m.toast('A size must be greater than zero.', 'error'); return; }
    this.step();
    if (k === 'w') e.scale = v / e.w0;
    else if (k === 'x') e.at = [v, e.at[1]];
    else if (k === 'y') e.at = [e.at[0], v];
    this.changed();
  }

  // ------------------------------------------------------------------ the dimension tool and the part's edges
  /** The edges of the part lying in the sketch plane (the outline of the face sketched on), as fixed
   *  references: dashed lines to snap to and to dimension from. */
  refs() {
    const body = this.m.result?.body, fr = this.frame();
    const key = `${body?.volume}|${JSON.stringify(fr)}`;
    if (this._refsKey === key) return this._refs;
    // lines / points: [u, v] in the sketch; lineIds / pointIds: which edge / corner of the part they are (by the
    // names of its faces), so a dimension from them follows the part when earlier steps change
    const out = { lines: [], curves: [], points: [], lineIds: [], pointIds: [] };
    if (body) {
      const o = fr.o, x = fr.x, n = fr.n, y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]];
      const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      const tol = Math.max(this.view.size * 1e-5, 1e-4), seen = new Set();
      const fname = (i) => body.faces[i]?.name;
      const k3 = (p) => p.map((v) => v.toFixed(4)).join(',');
      const corner = new Map(); // a corner (3D) -> the names of the faces meeting there
      for (const e of body.edges) {
        const pl = e.pts;
        for (const p of [[pl[0], pl[1], pl[2]], [pl[pl.length - 3], pl[pl.length - 2], pl[pl.length - 1]]]) {
          const s = corner.get(k3(p)) || new Set();
          for (const fi of e.faces) if (fname(fi)) s.add(fname(fi));
          corner.set(k3(p), s);
        }
      }
      for (const { pts: pl, faces: efs, mid } of body.edges) {
        const uv = [];
        let on = true;
        for (let i = 0; i < pl.length; i += 3) {
          const d = [pl[i] - o[0], pl[i + 1] - o[1], pl[i + 2] - o[2]];
          if (Math.abs(dot(d, n)) > tol) { on = false; break; }
          uv.push([+dot(d, x).toFixed(5), +dot(d, y).toFixed(5)]);
        }
        if (!on || uv.length < 2) continue;
        if (uv.length === 2) {
          out.lines.push(uv);
          out.lineIds.push(efs.length === 2 && fname(efs[0]) && fname(efs[1]) ? { a: fname(efs[0]), b: fname(efs[1]), fp: mid } : null);
        } else out.curves.push(uv);
        const ends = [[pl[0], pl[1], pl[2]], [pl[pl.length - 3], pl[pl.length - 2], pl[pl.length - 1]]];
        [uv[0], uv[uv.length - 1]].forEach((p, j) => {
          const k = p.join(',');
          if (seen.has(k)) return;
          seen.add(k);
          out.points.push(p);
          const faces = [...(corner.get(k3(ends[j])) || [])];
          out.pointIds.push(faces.length ? { faces, fp: ends[j].map((v) => +v.toFixed(6)) } : null);
        });
      }
    }
    this._refsKey = key;
    this._refs = out;
    return out;
  }

  /** What the dimension tool can use under the mouse: a point (a sketch point, a circle's centre, the origin,
   *  a corner of the part) or a straight line (of the sketch or an edge of the part). */
  pickTarget(uv) {
    const tol = this.mpp() * 8;
    let best = null, bestPoint = null;
    // a point (corner, centre) within reach always beats a line through it
    const near = (d, t) => {
      if (d >= tol) return;
      if (t.kind === 'point') { if (!bestPoint || d < bestPoint.d) bestPoint = { d, ...t }; } else if (!best || d < best.d) best = { d, ...t };
    };
    const segD = (a, b) => {
      const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((uv[0] - a[0]) * dx + (uv[1] - a[1]) * dy) / L));
      return Math.hypot(a[0] + t * dx - uv[0], a[1] + t * dy - uv[1]);
    };
    const dirOf = (a, b) => (Math.abs(a[1] - b[1]) < 1e-7 ? 'h' : Math.abs(a[0] - b[0]) < 1e-7 ? 'v' : 's');
    near(Math.hypot(uv[0], uv[1]), { kind: 'point', end: ORIGIN, uv: [0, 0] });
    for (const [id, p] of Object.entries(this.f.points)) near(Math.hypot(p[0] - uv[0], p[1] - uv[1]), { kind: 'point', end: id, uv: p });
    const R = this.refs();
    R.points.forEach((r, i) => near(Math.hypot(r[0] - uv[0], r[1] - uv[1]), { kind: 'point', end: R.pointIds[i] ? { ref: r, vertex: R.pointIds[i] } : { ref: r }, uv: r }));
    for (const e of this.f.entities) {
      if (e.t === 'circle') {
        const c = this.P(e.c), d = Math.hypot(c[0] - uv[0], c[1] - uv[1]);
        near(Math.min(Math.abs(d - e.r), d < e.r ? tol * 0.8 : Infinity), { kind: 'point', end: e.c, uv: c, circle: e.id });
      } else if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        near(segD(a, b), { kind: 'line', a: e.a, b: e.b, uvA: a, uvB: b, dir: dirOf(a, b), line: e.id });
      } else if (e.t === 'arc') {
        near(this.arcDist(e, uv), { kind: 'point', end: e.c, uv: this.P(e.c), arc: e.id });
      }
    }
    R.lines.forEach(([a, b], i) => {
      const id = R.lineIds[i] ? { edge: R.lineIds[i] } : {};
      near(segD(a, b), { kind: 'line', a: { ref: a, ...id }, b: { ref: b, ...id }, uvA: a, uvB: b, dir: dirOf(a, b) });
    });
    return bestPoint || best;
  }

  /** The dimensions possible between two picks: along x, along y, straight. The sketch point is the end that moves. */
  dimOptions(A, B) {
    const sketchy = (x) => typeof x === 'string' && x !== ORIGIN;
    const order = (a, b) => (sketchy(a) || !sketchy(b) ? [b, a] : [a, b]); // [fixed-ish, moving] -> dims are b - a
    const opts = [];
    const add = (t, a, b) => {
      const [p, q] = order(a, b), spec = { t, a: p, b: q }, v = this.measure(spec);
      if (Math.abs(v) > 1e-7) opts.push({ spec, v });
    };
    if (A.kind === 'point' && B.kind === 'point') {
      if (JSON.stringify(A.end) === JSON.stringify(B.end)) return [];
      add('dx', A.end, B.end);
      add('dy', A.end, B.end);
      if (Math.abs(A.uv[0] - B.uv[0]) > 1e-7 && Math.abs(A.uv[1] - B.uv[1]) > 1e-7) add('dist', A.end, B.end);
    } else if (A.kind !== B.kind) {
      const [P, L] = A.kind === 'point' ? [A, B] : [B, A];
      if (L.dir === 'h') add('dy', P.end, L.a);
      else if (L.dir === 'v') add('dx', P.end, L.a);
    } else if (A.dir === B.dir && A.dir !== 's' && (A.line || A.a) !== (B.line || B.a)) add(A.dir === 'h' ? 'dy' : 'dx', A.a, B.a);
    return opts;
  }

  dimClick(uv, e) {
    this.closeChooser();
    const t = this.pickTarget(uv);
    if (!t) { this.m.toast('Click a point, a circle, a line or an edge of the part.', 'info', 3000); return; }
    if (!this.dimA) { this.dimA = t; this.m.hint(this.hint()); this.draw(); return; }
    const A = this.dimA;
    let opts;
    if (A.line && t.line === A.line) opts = [{ spec: { t: 'len', e: A.line }, v: this.measure({ t: 'len', e: A.line }) }];
    else if (A.circle && t.circle === A.circle) opts = [{ spec: { t: 'dia', e: A.circle }, v: this.measure({ t: 'dia', e: A.circle }) }];
    else if (A.arc && t.arc === A.arc) opts = [{ spec: { t: 'rad', e: A.arc }, v: this.measure({ t: 'rad', e: A.arc }) }];
    else opts = this.dimOptions(A, t);
    this.dimA = null;
    this.m.hint(this.hint());
    if (!opts.length) { this.m.toast('Those two cannot be dimensioned — pick points, or a point and a straight horizontal / vertical edge.', 'warning', 5000); this.draw(); return; }
    if (opts.length === 1) { this.addDim(opts[0]); return; }
    this.showChooser(opts, e);
  }

  showChooser(opts, e) {
    const box = document.createElement('div');
    box.className = 'sk-choose';
    const vr = this.m.els.viewport.getBoundingClientRect();
    Object.assign(box.style, { left: `${e.clientX - vr.left + 12}px`, top: `${e.clientY - vr.top + 12}px` });
    const name = { dx: '↔ along x', dy: '↕ along y', dist: '⤢ straight' };
    box.innerHTML = '<div class="sk-choose-t">Which distance?</div>';
    for (const o of opts) {
      const b = document.createElement('button');
      b.className = 'btn small';
      b.textContent = `${name[o.spec.t]} — ${fmt(Math.abs(o.v))}`;
      b.addEventListener('click', (ev) => { ev.stopPropagation(); this.closeChooser(); this.addDim(o); });
      box.appendChild(b);
    }
    for (const t of ['pointerdown', 'pointerup']) box.addEventListener(t, (ev) => ev.stopPropagation());
    this.m.els.viewport.appendChild(box);
    this.chooser = box;
  }

  closeChooser() { this.chooser?.remove(); this.chooser = null; }

  /** Add a dimension (locked at the distance it has now), then let the user type the value right away. */
  async addDim(o) {
    const v = +o.v.toFixed(6);
    await this.relock(() => {
      if (!this.findDim(o.spec)) this.f.dims.push({ id: this.newId('d'), ...o.spec, v });
      this.unhide(o.spec);
    });
    const d = this.findDim(o.spec);
    if (!d) return;
    // labels reach the page with the next frame of the 3D view
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const el = this.m.els.viewport.querySelector(`.sk-label[data-dim="${d.id}"]`);
    if (el) this.editLabel(el, o.spec);
  }

  async delDim(id) {
    await this.relock(() => { this.f.dims = this.f.dims.filter((d) => d.id !== id); });
  }

  // ------------------------------------------------------------------ drawing
  /** One size label: the value (click = type it and lock it) and a lock button (🔒 locked / 🔓 free). */
  label(spec, u, v, text, title) {
    const locked = !!this.findDim(spec);
    const el = document.createElement('div');
    el.className = `sk-label edit${locked ? ' locked' : ''}`;
    el.innerHTML = '<span class="sk-val"></span><button class="sk-lock"></button>';
    el.querySelector('.sk-val').textContent = text;
    el.querySelector('.sk-val').title = `${title} — click to type it (that locks it)`;
    const lock = el.querySelector('.sk-lock');
    lock.textContent = locked ? '🔒' : '🔓';
    lock.title = locked ? 'Locked — click to free this size' : 'Free — click to lock this size as it is';
    lock.addEventListener('click', (ev) => { ev.stopPropagation(); this.toggleLock(spec); });
    el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); this.editLabel(el, spec); });
    const dim = this.findDim(spec);
    if (dim) el.dataset.dim = dim.id;
    const x = document.createElement('button');
    x.className = 'sk-del';
    x.textContent = '✕';
    x.title = 'Hide this size (and unlock it) — ↔ Dimension on the shape shows it again';
    x.addEventListener('click', (ev) => { ev.stopPropagation(); this.hideSize(spec); });
    el.appendChild(x);
    for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
    return { el, u, v };
  }

  /** A distance label: the value (click = type a new one) and ✕ (delete the dimension). */
  distLabel(d, u, v) {
    const el = document.createElement('div');
    el.className = `sk-label edit dist${d.free ? '' : ' locked'}`;
    el.dataset.dim = d.id;
    el.innerHTML = '<span class="sk-val"></span><button class="sk-lock"></button><button class="sk-del" title="Delete this dimension">✕</button>';
    el.querySelector('.sk-val').textContent = `${{ dx: '↔', dy: '↕', dist: '⤢' }[d.t]} ${fmt(Math.abs(d.free ? this.measure(d) : d.v))}`;
    el.querySelector('.sk-val').title = d.free ? 'Measured distance (free) — click to type a value and lock it' : 'Locked distance — click to type a new value';
    const lock = el.querySelector('.sk-lock');
    lock.textContent = d.free ? '🔓' : '🔒';
    lock.title = d.free ? 'Free — it only measures. Click to lock it at this value' : 'Locked — click to free it (it then only measures)';
    lock.addEventListener('click', (ev) => { ev.stopPropagation(); this.toggleLock(d); });
    el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); this.editLabel(el, d); });
    el.querySelector('.sk-del').addEventListener('click', (ev) => { ev.stopPropagation(); this.delDim(d.id); });
    for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
    return { el, u, v };
  }

  editLabel(el, spec) {
    const inp = document.createElement('input');
    inp.className = 'sk-input';
    inp.value = fmt(Math.abs(this.measure(spec)));
    const r = el.getBoundingClientRect(), vr = this.m.els.viewport.getBoundingClientRect();
    Object.assign(inp.style, { left: `${r.left - vr.left}px`, top: `${r.top - vr.top - 2}px` });
    this.m.els.viewport.appendChild(inp);
    inp.focus();
    inp.select();
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      inp.remove();
      if (ok && inp.value.trim() !== '') this.setSize(spec, inp.value);
    };
    inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') finish(true); if (ev.key === 'Escape') finish(false); });
    inp.addEventListener('blur', () => finish(true));
  }

  draw() {
    const f = this.f, mpp = this.mpp(), labels = [], lines = [], circles = [], dots = [];
    const SEL = 0xf2cc60, NORM = 0x39d0d8, LOCKED = 0xd2a8ff;
    const selPts = new Set(this.pointsOfSel());
    const isSel = (e) => this.sel && ((this.sel.kind === 'entity' && this.sel.id === e.id) || (this.sel.kind === 'group' && this.sel.id === e.g));
    const shownGroups = new Set();
    for (const e of f.entities) {
      if (e.t === 'line') {
        const a = this.P(e.a), b = this.P(e.b);
        lines.push([a, b, isSel(e) ? SEL : NORM]);
        // a rectangle shows its width and height once; a free line its length
        if (e.g) {
          const k = f.constraints.find((c) => c.e === e.id && (c.t === 'h' || c.t === 'v'))?.t;
          const key = `${e.g}:${k}`;
          if (shownGroups.has(key) || this.isHidden({ t: 'len', e: e.id })) continue; // a hidden side: the opposite one shows it
          shownGroups.add(key);
        }
        const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (L < 1e-9) continue;
        const nx = -(b[1] - a[1]) / L, ny = (b[0] - a[0]) / L;
        // the label goes on the outside of a closed shape (away from its centre)
        const c = this.centreOf(e) || [a[0] + nx, a[1] + ny];
        const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        const side = (mid[0] - c[0]) * nx + (mid[1] - c[1]) * ny >= 0 ? 1 : -1;
        if (!this.isHidden({ t: 'len', e: e.id })) labels.push(this.label({ t: 'len', e: e.id }, mid[0] + side * nx * mpp * 16, mid[1] + side * ny * mpp * 16, fmt(L), 'Length'));
      } else if (e.t === 'block') {
        for (const r of this.blockRings(e)) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length], isSel(e) ? SEL : NORM]);
        const k = e.scale || 1, [au, av] = e.at;
        const el = document.createElement('div');
        el.className = 'sk-label edit block';
        el.innerHTML = '<span class="sk-val"></span>';
        el.querySelector('.sk-val').textContent = `↔ ${fmt(e.w0 * k)}`;
        el.querySelector('.sk-val').title = 'Width of the outline — click to type it (the height follows)';
        el.querySelector('.sk-val').addEventListener('click', (ev) => { ev.stopPropagation(); this.editLabel(el, { t: 'bw', e: e.id }); });
        for (const t of ['pointerdown', 'pointerup']) el.addEventListener(t, (ev) => ev.stopPropagation());
        labels.push({ el, u: au + (e.w0 * k) / 2, v: av - mpp * 14 });
      } else if (e.t === 'arc') {
        const ps = this.arcOf(e), col = isSel(e) ? SEL : NORM;
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], col]);
        const m = ps[Math.floor(ps.length / 2)], c = this.P(e.c), r = this.arcR(e) || 1;
        if (!this.isHidden({ t: 'rad', e: e.id })) {
          labels.push(this.label({ t: 'rad', e: e.id }, m[0] + ((m[0] - c[0]) / r) * mpp * 16, m[1] + ((m[1] - c[1]) / r) * mpp * 16, `R${fmt(r)}`, 'Radius'));
        }
      } else if (e.t === 'circle') {
        const c = this.P(e.c);
        circles.push([c, e.r, isSel(e) ? SEL : NORM]);
        if (!this.isHidden({ t: 'dia', e: e.id })) labels.push(this.label({ t: 'dia', e: e.id }, c[0] + e.r * 0.72 + mpp * 18, c[1] + e.r * 0.72 + mpp * 8, `Ø${fmt(2 * e.r)}`, 'Diameter'));
      }
    }
    for (const k of f.constraints.filter((c) => c.t === 'corner')) {
      const p = this.P(k.p);
      for (const l of k.lines.map((id) => this.ent(id)).filter(Boolean)) {
        const near = [l.a, l.b].map((q) => this.P(q)).sort((x, y) => Math.hypot(x[0] - p[0], x[1] - p[1]) - Math.hypot(y[0] - p[0], y[1] - p[1]))[0];
        if (p && near) lines.push([near, p, 0x8b95a3, true]);
      }
    }
    for (const [id, p] of Object.entries(f.points)) {
      const fixed = f.dims.some((d) => (d.t === 'dx' || d.t === 'dy') && d.b === id && d.a === ORIGIN);
      dots.push([p, selPts.has(id) ? SEL : fixed ? LOCKED : NORM]);
    }
    // the part's edges in this plane (fixed references), dashed
    const refs = this.refs();
    for (const [a, b] of refs.lines) lines.push([a, b, 0x8b95a3, true]);
    for (const c of refs.curves) for (let i = 0; i + 1 < c.length; i++) lines.push([c[i], c[i + 1], 0x8b95a3, true]);
    // distances (dimension tool): a dimension line from the moving end, an extension line to the other end
    for (const d of f.dims) {
      if (!['dx', 'dy', 'dist'].includes(d.t)) continue;
      const A = this.endUV(d.a), B = this.endUV(d.b);
      if (!A || !B) continue;
      if ((d.a === ORIGIN || d.b === ORIGIN) && Math.abs(d.v) < 1e-9) continue; // "locked at the origin": the purple point says it
      let mid, end;
      const DC = d.free ? 0x8b95a3 : LOCKED;
      if (d.t === 'dx') { end = [A[0], B[1]]; lines.push([B, end, DC], [A, end, DC, true]); mid = [(A[0] + B[0]) / 2, B[1] + mpp * 10]; }
      else if (d.t === 'dy') { end = [B[0], A[1]]; lines.push([B, end, DC], [A, end, DC, true]); mid = [B[0] + mpp * 22, (A[1] + B[1]) / 2]; }
      else { lines.push([A, B, DC]); mid = [(A[0] + B[0]) / 2 + mpp * 8, (A[1] + B[1]) / 2 + mpp * 8]; }
      labels.push(this.distLabel(d, mid[0], mid[1]));
    }
    // the dimension tool's first pick
    if (this.dimA) {
      if (this.dimA.kind === 'point') dots.push([this.dimA.uv, 0x7ee787]);
      else lines.push([this.dimA.uvA, this.dimA.uvB, 0x7ee787]);
    }
    // the origin, always: an orange point with short x / y arrows
    const ax = mpp * 26;
    lines.push([[0, 0], [ax, 0], 0xff7b72], [[0, 0], [0, ax], 0x7ee787]);
    dots.push([[0, 0], 0xffa657]);
    // what the mouse is on (what a dimension or a new point attaches to), highlighted with its name
    const HL = 0x7ee787, hv = this.hover;
    if (hv) {
      let name = '', at = null;
      if (hv.kind === 'point') {
        circles.push([hv.uv, mpp * 6, HL]);
        dots.push([hv.uv, HL]);
        if (hv.circle) { const c = this.ent(hv.circle); circles.push([this.P(c.c), c.r, HL]); name = 'circle (its centre)'; }
        else if (hv.arc) { const ps = this.arcOf(this.ent(hv.arc)); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], HL]); name = 'arc (its centre)'; }
        else name = hv.corner ? 'corner' : hv.end === ORIGIN ? 'origin' : typeof hv.end === 'object' ? 'corner of the part' : 'point';
        at = hv.uv;
      } else if (hv.kind === 'line') {
        lines.push([hv.uvA, hv.uvB, HL], [hv.uvA, hv.uvB, HL]);
        name = hv.line ? 'line' : 'edge of the part';
        at = [(hv.uvA[0] + hv.uvB[0]) / 2, (hv.uvA[1] + hv.uvB[1]) / 2];
      } else if (hv.kind === 'entity' || hv.kind === 'group') {
        const ents = hv.kind === 'group' ? this.f.entities.filter((x) => x.g === hv.id) : [this.ent(hv.id)].filter(Boolean);
        for (const x of ents) {
          if (x.t === 'line') lines.push([this.P(x.a), this.P(x.b), HL]);
          else if (x.t === 'circle') circles.push([this.P(x.c), x.r, HL]);
          else if (x.t === 'arc') { const ps = this.arcOf(x); for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], HL]); }
          else if (x.t === 'block') for (const r of this.blockRings(x)) for (let i = 0; i < r.length; i++) lines.push([r[i], r[(i + 1) % r.length], HL]);
        }
      }
      if (name && at) {
        const el = document.createElement('div');
        el.className = 'sk-label hover';
        el.textContent = name;
        labels.push({ el, u: at[0] + mpp * 10, v: at[1] + mpp * 12 });
      }
    }
    // what is being drawn
    const cur = this.cursor?.uv;
    let live = null;
    if (cur && this.start && this.tool === 'rect') {
      const [u0, v0] = this.start.uv, [u1, v1] = cur;
      for (const [a, b] of [[[u0, v0], [u1, v0]], [[u1, v0], [u1, v1]], [[u1, v1], [u0, v1]], [[u0, v1], [u0, v0]]]) lines.push([a, b, SEL]);
      live = { text: `${fmt(Math.abs(u1 - u0))} × ${fmt(Math.abs(v1 - v0))}`, u: (u0 + u1) / 2, v: (v0 + v1) / 2 };
    } else if (cur && this.start && this.tool === 'circle') {
      const r = Math.hypot(cur[0] - this.start.uv[0], cur[1] - this.start.uv[1]);
      circles.push([this.start.uv, r, SEL]);
      live = { text: `Ø${fmt(2 * r)}`, u: this.start.uv[0], v: this.start.uv[1] };
    } else if (cur && this.start && this.tool === 'arc') {
      const geo = this.arcEnd && arcThrough(this.start.uv, this.arcEnd.uv, cur);
      if (geo) {
        const ps = arcPts(geo.c, geo.a, geo.b);
        for (let i = 0; i + 1 < ps.length; i++) lines.push([ps[i], ps[i + 1], SEL]);
        live = { text: `R${fmt(Math.hypot(geo.a[0] - geo.c[0], geo.a[1] - geo.c[1]))}`, u: cur[0], v: cur[1] + mpp * 14 };
      } else lines.push([this.start.uv, this.arcEnd ? this.arcEnd.uv : cur, SEL, true]);
    } else if (cur && this.chain && this.tool === 'line') {
      const a = this.P(this.chain.last);
      lines.push([a, cur, SEL]);
      live = { text: fmt(Math.hypot(cur[0] - a[0], cur[1] - a[1])), u: (a[0] + cur[0]) / 2, v: (a[1] + cur[1]) / 2 };
    }
    if (live) {
      const el = document.createElement('div');
      el.className = 'sk-label live';
      el.textContent = live.text;
      labels.push({ el, u: live.u, v: live.v });
    }
    if (cur && this.tool !== 'select' && this.tool !== 'dim') dots.push([cur, this.cursor.id || this.cursor.ref ? 0x7ee787 : SEL]); // green = joins / snaps to that point
    this.view.setSketch(this.frame(), { lines, circles, dots, labels, grid: this.gridStep() });
  }

  centreOf(e) {
    if (!e.g) return null;
    const ps = this.pointsOfSel({ kind: 'group', id: e.g }).map((p) => this.P(p));
    return [ps.reduce((s, p) => s + p[0], 0) / ps.length, ps.reduce((s, p) => s + p[1], 0) / ps.length];
  }

  // ------------------------------------------------------------------ the property panel
  propsHtml() {
    const free = this.dof;
    const st = free === null ? '' : free === 0 ? '<p class="sk-dof ok">✓ Fully locked — every size is fixed.</p>'
      : `<p class="sk-dof">${free} free — those sizes follow when you drag. Type a size (or click 🔓) to lock it.</p>`;
    const s = this.sel;
    let what = '';
    const blk = s?.kind === 'entity' && this.ent(s.id)?.t === 'block' ? this.ent(s.id) : null;
    if (blk) {
      const row = (k, label, v) => `<div class="field"><label>${label}</label><input type="number" step="any" data-bk="${k}" value="${fmt(v)}"><span class="unit">mm</span></div>`;
      what = `<h3>Outline</h3><p class="hint" data-no-i18n>${(blk.name || '').replace(/[<>&]/g, '')}</p>
        ${row('w', 'Width', blk.w0 * (blk.scale || 1))}<p class="hint">Height ${fmt(blk.h0 * (blk.scale || 1))} mm (follows the width).</p>
        ${row('x', 'Corner x', blk.at[0])}${row('y', 'Corner y', blk.at[1])}
        <p class="hint">Drag it in the view to move it. The corner is its lower-left corner, from the sketch's origin.</p>
        <div class="row-actions"><button class="btn small danger" data-a="delSel" title="Delete it (Delete)">Delete</button></div>`;
    } else if (s) {
      const name = s.kind === 'point' ? 'Point' : s.kind === 'group' ? 'Rectangle' : ({ circle: 'Circle', arc: 'Arc' })[this.ent(s.id)?.t] || 'Line';
      what = `<h3>${name}</h3><p class="hint">Sizes and the position are shown in the view: click one to type it.</p>
        <div class="row-actions"><button class="btn small danger" data-a="delSel" title="Delete it (Delete)">Delete</button></div>`;
    }
    const name = (d) => {
      const v = fmt(Math.abs(d.v));
      if (d.t === 'len') return `Length ${v}`;  // (a free distance shows its measured value)
      if (d.t === 'dia') return `Ø${v}`;
      if (d.t === 'rad') return `R${v}`;
      const at = (x) => (x === ORIGIN ? 'origin' : typeof x === 'object' ? 'part edge' : 'point');
      if ((d.a === ORIGIN || d.b === ORIGIN) && Math.abs(d.v) < 1e-9) return `${d.t === 'dx' ? '↔' : '↕'} 0 (on the origin)`;
      return `${{ dx: '↔', dy: '↕', dist: '⤢' }[d.t]} ${v} (from the ${at(d.a)})`;
    };
    const hidden = this.userHidden().length;
    const list = (this.f.dims.length ? `<h3>Dimensions</h3><div class="sk-dims">${this.f.dims.map((d) =>
      `<div class="sk-dim"><span>${d.free ? '🔓' : '🔒'} ${name(d.free ? { ...d, v: this.measure(d) } : d)}</span>
        <span class="sk-dim-acts">${['len', 'dia', 'rad'].includes(d.t) ? '' : `<button class="mini" data-lock="${d.id}" title="${d.free ? 'Lock it at this value' : 'Free it (it then only measures)'}">${d.free ? '🔒' : '🔓'}</button>`}
        <button class="mini danger" data-del="${d.id}" title="Delete this dimension">✕</button></span></div>`).join('')}</div>` : '')
      + (hidden ? `<div class="row-actions"><button class="btn small" data-a="showSizes">Show ${hidden} hidden size(s)</button></div>` : '');
    return `<h2>Sketch</h2><p class="hint">${this.hint()}</p>${st}${what}${list}
      <h3>Tips</h3><p class="hint">A shape inside another one becomes a hole. Lines that meet at a point are joined; click the
      first point again to close a shape. 🔒 = locked size (it stays when other sizes change). ↔ Dimension adds a distance
      between two points, circles or edges (also the part's edges, dashed). Right mouse button pans, wheel zooms, Ctrl+Z undoes.</p>`;
  }

  async init() {
    // a reopened sketch: ask the solver for the free degrees (nothing moves)
    if (this.f.entities.length) { const r = await this.solve(); if (r.dof !== undefined) this.dof = r.dof; this.m.renderProps(); }
  }

  result() {
    const { points, entities, constraints, dims } = this.f;
    return { ...this.f, points, entities, constraints, dims };
  }
}
