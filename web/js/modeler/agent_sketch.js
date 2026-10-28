// The AI tools for one sketch step: read it (shapes, relations, dimensions, what is free, what does not fit), 🪄
// auto-dimension it, set / lock / free one dimension, ✂ trim a piece, ∪ union overlapping closed shapes. Each works
// like the user's own click: a sketch that is not open is opened in the editor, changed and finished again (one
// undo step in the model); one that is open stays open. What the sketcher says in toasts comes back as `messages`.

import { Sketcher } from './sketcher.js';

const r4 = (v) => +(+v).toFixed(4);
const KIND = { len: 'length', dia: 'diameter', rad: 'radius', dx: 'distance along x', dy: 'distance along y', dist: 'distance', ang: 'angle', pl: 'distance from a line', bw: 'outline width' };

/** A dimension's ends in words ("origin", a point id, "part edge", "middle of l2"). */
const endOf = (x) => (x === 'O' ? 'origin' : typeof x === 'string' ? x : x?.mid ? `middle of ${x.mid}` : x?.edge || x?.vertex ? 'part edge' : x?.axis ? 'part axis' : x?.point ? 'reference point' : 'fixed point');

export function sketchHandlers({ modeler: m, needModel, settle }) {
  const sketchOf = (id) => {
    const f = m.part.features.find((x) => x.id === id);
    if (!f || f.type !== 'sketch') throw new Error(`No sketch step ${id} — get_model lists the steps.`);
    return f;
  };
  /** The sketcher of step `id`: the open one, or a new one in the editor (opened = true: finish it afterwards). */
  const openSketch = async (id) => {
    if (m.mode === 'sketch' && m.sk?.f.id === id) return { sk: m.sk, opened: false };
    if (m.mode === 'sketch' && m.sk) throw new Error(`Another sketch (${m.sk.f.id}) is open — finish it first (gui_action "Finish sketch").`);
    sketchOf(id);
    if (m.cmd) m.closeAll?.();
    m.cmd = null;
    m.mode = 'part';
    m.edit(id);
    const until = Date.now() + 8000;
    while (!(m.mode === 'sketch' && m.sk && m.sk.dof !== null) && Date.now() < until) await new Promise((r) => setTimeout(r, 40));
    if (m.mode !== 'sketch' || !m.sk) throw new Error(`The sketch ${id} could not be opened.`);
    return { sk: m.sk, opened: true };
  };
  /** Run fn(sketcher) on step `id`, catching the sketcher's toasts; a sketch opened for it is finished again. */
  const withSketch = async (id, fn) => {
    needModel();
    await settle();
    const { sk, opened } = await openSketch(id);
    const said = [], toast = m.toast, own = Object.prototype.hasOwnProperty.call(m, 'toast');
    m.toast = (text, kind, ...rest) => { said.push(`${kind === 'error' ? 'Error: ' : ''}${text}`); return toast.call(m, text, kind, ...rest); };
    let out;
    try { out = await fn(sk); } finally { if (own) m.toast = toast; else delete m.toast; }
    const state = await readSketch(sk.f, sk);
    if (opened) { m.finishSketch(); await settle(); }
    return { out, said, state, opened };
  };

  /** The sketch as the AI reads it: shapes with coordinates, relations, dimensions with names and values, what is free. */
  const readSketch = async (feature, live = null) => {
    const sk = live || new Sketcher(m, structuredClone(feature), false);
    const f = sk.f, P = (p) => sk.P(p) || [0, 0];
    const res = await fetch('/api/model/sketch/solve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sketch: f, detail: true }) });
    const r = await res.json();
    if (!res.ok) throw new Error(r.error || res.statusText);
    sk.takeState(r);
    const xy = (p) => P(p).map(r4);
    const shapes = f.entities.map((e) => {
      const o = { id: e.id, t: e.t, state: sk.stateOf(e) || 'unknown', ...(e.construction ? { construction: true } : {}) };
      if (e.t === 'line') Object.assign(o, { a: e.a, b: e.b, from: xy(e.a), to: xy(e.b), length: r4(Math.hypot(P(e.b)[0] - P(e.a)[0], P(e.b)[1] - P(e.a)[1])) });
      else if (e.t === 'circle') Object.assign(o, { c: e.c, centre: xy(e.c), d: r4(2 * e.r) });
      else if (e.t === 'arc') Object.assign(o, { c: e.c, a: e.a, b: e.b, centre: xy(e.c), from: xy(e.a), to: xy(e.b), r: r4(sk.arcR(e)), ccw: true });
      else if (e.t === 'spline') Object.assign(o, { points: e.pts.length, from: xy(e.pts[0]), to: xy(e.pts[e.pts.length - 1]), ...(e.fit ? { joined: true } : {}) });
      else if (e.t === 'block') Object.assign(o, { at: e.at, w: r4(e.w0 * (e.scale || 1)), h: r4(e.h0 * (e.scale || 1)), ...(e.text !== undefined ? { text: e.text } : {}) });
      return o;
    });
    const dims = f.dims.map((d) => {
      const v = d.free ? sk.measure(d) : d.v;
      return { id: d.id, kind: d.t, name: ['len', 'dist', 'pl', 'bw'].includes(d.t) ? `${KIND[d.t]} ${sk.dimName({ ...d, v })}` : sk.dimName({ ...d, v }), // ("length 65", "x -20", "R23")
        kind_name: KIND[d.t] || d.t, value: r4(v), locked: !d.free,
        between: d.e ? [d.e, ...(d.e2 ? [d.e2] : []), ...(d.a ? [endOf(d.a)] : [])] : [endOf(d.a), endOf(d.b)] };
    });
    const rules = f.constraints.map((k) => ({ id: k.id, t: k.t, name: sk.ruleNames([k.id])[0] || k.t,
      on: [k.e, k.e2, k.arc, k.p, k.p2, ...(k.lines || [])].filter(Boolean) }));
    const conflicting = r.conflicting || [], redundant = r.redundant || [];
    return { id: f.id, name: f.name, dof: r.dof, fully_defined: r.ok && r.dof === 0, points: Object.fromEntries(Object.keys(f.points).map((k) => [k, xy(k)])),
      shapes, relations: rules, dims, free: { points: [...(sk.free?.points || [])], shapes: shapes.filter((s) => s.state === 'free').map((s) => s.id), ...(r.free?.partial ? { partial: true } : {}) },
      conflicts: { contradicting: sk.ruleNames(conflicting).map((n, i) => `${conflicting[i]} ${n}`), held_twice: sk.ruleNames(redundant).map((n, i) => `${redundant[i]} ${n}`) } };
  };

  /** A dimension: its id, or a shape's own size "len:l1" / "dia:c1" / "rad:a1" -> {spec, d (the dim, if any)}. */
  const dimOf = (sk, dim) => {
    const d = sk.f.dims.find((x) => x.id === dim);
    if (d) return { spec: d, d };
    const [t, e] = String(dim).split(':'), ent = sk.ent(e);
    if (!['len', 'dia', 'rad'].includes(t) || !ent || (t === 'len') !== (ent.t === 'line') || (t === 'dia' && ent.t !== 'circle') || (t === 'rad' && ent.t !== 'arc')) {
      throw new Error(`dim: a dimension id from get_sketch's dims, or a shape's own size "len:<line>", "dia:<circle>", "rad:<arc>" — not ${dim}.`);
    }
    return { spec: { t, e }, d: sk.findDim({ t, e }) || null };
  };

  return {
    get_sketch: async ({ id }) => {
      needModel();
      const live = m.mode === 'sketch' && m.sk?.f.id === id ? m.sk : null;
      return { text: JSON.stringify(await readSketch(live ? live.f : sketchOf(id), live)) };
    },

    sketch_auto_dims: async ({ id, round = false }) => {
      const { out, said, state } = await withSketch(id, (sk) => sk.autoDimension({ round: !!round }));
      return { text: JSON.stringify({ ...out, locked: state.dims.filter((d) => d.locked).length, fully_defined: state.fully_defined,
        ...(state.conflicts.contradicting.length ? { conflicts: state.conflicts } : {}), messages: said }) };
    },

    sketch_dim: async ({ id, dim, value, locked }) => {
      if (value === undefined && locked === undefined) throw new Error('Give value (it locks the dimension at it) and / or locked (true / false).');
      const { said, state } = await withSketch(id, async (sk) => {
        const { spec, d } = dimOf(sk, dim);
        if (value !== undefined && locked !== false) await sk.setSize(spec, value);
        else if (locked === false && d && !d.free) await sk.toggleLock(d);
        else if (locked === true && (!d || d.free)) await sk.toggleLock(d || spec);
      });
      const errors = said.filter((x) => x.startsWith('Error'));
      if (errors.length) throw new Error(`${errors.join(' ')} (the sketch is as it was)`);
      return { text: JSON.stringify({ dims: state.dims, dof: state.dof, fully_defined: state.fully_defined, messages: said }) };
    },

    sketch_trim: async ({ sketch, shape, at }) => {
      if (!Array.isArray(at) || at.length !== 2 || !at.every(Number.isFinite)) throw new Error('at: [x, y] on the shape, in the piece to cut away (sketch mm).');
      const { out, said, state } = await withSketch(sketch, async (sk) => {
        const e = sk.ent(shape);
        if (!e || !['line', 'circle', 'arc'].includes(e.t)) throw new Error(`shape: a line, circle or arc of the sketch (get_sketch's shapes) — not ${shape}.`);
        const P = (p) => sk.P(p);
        let q = at; // (the point on the shape nearest `at`: that is where it is clicked)
        if (e.t === 'line') {
          const a = P(e.a), b = P(e.b), d = [b[0] - a[0], b[1] - a[1]], L = d[0] * d[0] + d[1] * d[1] || 1;
          const s = Math.max(0, Math.min(1, ((at[0] - a[0]) * d[0] + (at[1] - a[1]) * d[1]) / L));
          q = [a[0] + s * d[0], a[1] + s * d[1]];
        } else {
          const c = P(e.c), r = e.t === 'circle' ? e.r : sk.arcR(e), w = Math.atan2(at[1] - c[1], at[0] - c[0]);
          q = [c[0] + r * Math.cos(w), c[1] + r * Math.sin(w)];
        }
        const n = sk.f.entities.length;
        const ok = await sk.trimAt(q);
        return { ok, shapes: [n, sk.f.entities.length] };
      });
      if (!out.ok) throw new Error(said.join(' ') || 'Nothing trimmed there.');
      return { text: JSON.stringify({ shapes: { before: out.shapes[0], after: out.shapes[1] }, dof: state.dof, shapes_now: state.shapes, messages: said }) };
    },

    sketch_union: async ({ sketch }) => {
      const { out, said, state } = await withSketch(sketch, (sk) => sk.unionShapes());
      if (!out) throw new Error('No closed shapes overlap in this sketch — nothing to unite.');
      return { text: JSON.stringify({ trimmed_pieces: out.trimmed, shapes: { before: out.before, after: out.after }, dof: state.dof,
        relations: state.relations.map((k) => k.name), messages: said }) };
    },
  };
}
