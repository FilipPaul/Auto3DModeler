// The AI tools for 3D model parts (they arrive from the app's MCP server like the classic ones in app.js):
// list / open / start parts, read the model, find faces and edges, add / change / delete / turn off steps,
// a screenshot, a printing copy. Every change goes through the modeler like a user edit (visible, undoable).

import { roundCorner } from './sketcher.js';

const r3 = (v) => +(+v).toFixed(3);
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const DATUM = { XY: 'XY', TOP: 'XY', XZ: 'XZ', FRONT: 'XZ', YZ: 'YZ', RIGHT: 'YZ' };

/** A sketch from simple shapes: rect {x, y, w, h, r} (lower-left corner, r = rounded corners), circle {x, y, d} (centre), polyline {points}
 *  (closed). lock: every size and position is locked (the sketch is fully defined). */
export function sketchFromShapes(shapes, lock = true) {
  const f = { points: {}, entities: [], constraints: [], dims: [] };
  let n = { p: 0, l: 0, c: 0, r: 0, k: 0, d: 0 };
  const id = (k) => `${k}${(n[k] = (n[k] || 0) + 1)}`;
  const dim = (spec) => { if (lock) f.dims.push({ id: id('d'), ...spec }); };
  const point = (u, v, locked) => {
    const p = id('p');
    f.points[p] = [r3(u), r3(v)];
    if (locked) { dim({ t: 'dx', a: 'O', b: p, v: r3(u) }); dim({ t: 'dy', a: 'O', b: p, v: r3(v) }); }
    return p;
  };
  for (const s of shapes || []) {
    if (s.rect) {
      const { x = 0, y = 0, w, h, r = 0 } = s.rect;
      if (!(w > 0 && h > 0)) throw new Error('A rectangle needs w and h greater than zero.');
      if (r < 0 || 2 * r >= Math.min(w, h)) throw new Error('A rectangle\'s corner radius r must be less than half its shorter side.');
      const g = id('r');
      const ps = [point(x, y, true), point(x + w, y), point(x + w, y + h), point(x, y + h)];
      ps.forEach((a, i) => {
        const l = id('l');
        f.entities.push({ id: l, t: 'line', a, b: ps[(i + 1) % 4], g });
        f.constraints.push({ id: id('k'), t: i % 2 ? 'v' : 'h', e: l });
        if (i === 0) dim({ t: 'len', e: l, v: r3(w) });
        if (i === 1) dim({ t: 'len', e: l, v: r3(h) });
      });
      if (r > 0) {
        for (const p of ps) {
          const arc = roundCorner(f, p, r, id);
          dim({ t: 'rad', e: arc, v: r3(r) });
        }
      }
    } else if (s.circle) {
      const { x = 0, y = 0, d } = s.circle;
      if (!(d > 0)) throw new Error('A circle needs a diameter d greater than zero.');
      const c = id('c');
      f.entities.push({ id: c, t: 'circle', c: point(x, y, true), r: r3(d / 2) });
      dim({ t: 'dia', e: c, v: r3(d) });
    } else if (s.slot) {
      // a slot: two half circles of width w around the centres (x1, y1) and (x2, y2), joined by straight sides
      const { x1 = 0, y1 = 0, x2, y2 = y1, w } = s.slot;
      const L = Math.hypot(x2 - x1, y2 - y1);
      if (!(w > 0) || !(L > 0)) throw new Error('A slot needs x1, y1, x2, y2 (the centres of its round ends, apart) and w > 0.');
      const r = w / 2, nx = (-(y2 - y1) / L) * r, ny = ((x2 - x1) / L) * r;
      const c1 = point(x1, y1, true), c2 = point(x2, y2, true);
      const A = point(x1 - nx, y1 - ny), B = point(x2 - nx, y2 - ny), C = point(x2 + nx, y2 + ny), D = point(x1 + nx, y1 + ny);
      const a1 = id('c'), a2 = id('c');
      f.entities.push({ id: id('l'), t: 'line', a: A, b: B }, { id: a1, t: 'arc', c: c2, a: B, b: C },
        { id: id('l'), t: 'line', a: C, b: D }, { id: a2, t: 'arc', c: c1, a: D, b: A });
      dim({ t: 'rad', e: a1, v: r3(r) });
      dim({ t: 'rad', e: a2, v: r3(r) });
    } else if (s.path) {
      // an open line (a sweep's path): points joined in order, not closed
      const pts = s.path.points || [];
      if (pts.length < 2) throw new Error('A path needs at least 2 points.');
      const ps = pts.map(([u, v], i) => point(u, v, i === 0));
      for (let i = 0; i + 1 < ps.length; i++) f.entities.push({ id: id('l'), t: 'line', a: ps[i], b: ps[i + 1] });
    } else if (s.polyline) {
      const pts = s.polyline.points || [];
      if (pts.length < 3) throw new Error('A polyline needs at least 3 points (it is closed automatically).');
      const ps = pts.map(([u, v]) => point(u, v, true));
      ps.forEach((a, i) => {
        const b = ps[(i + 1) % ps.length], l = id('l');
        f.entities.push({ id: l, t: 'line', a, b });
        const [p, q] = [f.points[a], f.points[b]];
        if (Math.abs(p[1] - q[1]) < 1e-9) f.constraints.push({ id: id('k'), t: 'h', e: l });
        else if (Math.abs(p[0] - q[0]) < 1e-9) f.constraints.push({ id: id('k'), t: 'v', e: l });
      });
    } else throw new Error('Each shape is {rect: {x, y, w, h}}, {circle: {x, y, d}} or {polyline: {points: [[u, v], …]}}.');
  }
  // a locked polyline / rectangle corner already fixes its points: the H / V rules there are redundant locks
  if (lock) {
    const fixedLine = (l) => {
      const e = f.entities.find((x) => x.id === l);
      const fixed = (p) => f.dims.some((d) => d.t === 'dx' && d.b === p) && f.dims.some((d) => d.t === 'dy' && d.b === p);
      return e && fixed(e.a) && fixed(e.b);
    };
    f.constraints = f.constraints.filter((k) => !fixedLine(k.e));
  }
  return f;
}

const KIND = { model: '3D model', assembly: 'assembly' };

export function modelHandlers({ modeler: m, project, getWorkspace }) {
  const needModel = () => {
    if (getWorkspace() !== 'model') throw new Error('The part on screen is not a 3D model — use get_part for it, or list_parts / open_part / new_model.');
  };
  const settle = async () => {
    await new Promise((r) => setTimeout(r, 30));
    while (m.inflight) await m.inflight;
  };
  const body = () => m.result?.body;
  const faceOf = (name) => {
    const b = body();
    const fs = (b?.faces || []).filter((f) => f.name === name || (f.names || []).includes(name));
    if (!fs.length) throw new Error(`No face named “${name}” — use find_refs to get face names.`);
    return fs.sort((a, c) => c.area - a.area)[0];
  };
  const planeOf = (plane) => {
    if (plane && typeof plane === 'object' && plane.datum) {
      const d = DATUM[String(plane.datum).toUpperCase()];
      if (!d) throw new Error('plane.datum: "XY", "XZ" or "YZ".');
      return { datum: d, ...(plane.offset ? { offset: +plane.offset } : {}) };
    }
    if (!plane || typeof plane === 'string') {
      const d = DATUM[String(plane || 'XY').toUpperCase()];
      if (!d) throw new Error('plane is "XY" (top), "XZ" (front), "YZ" (right) or {face: "<face name>"}.');
      return { datum: d };
    }
    const f = faceOf(plane.face);
    if (f.type !== 'plane') throw new Error(`The face “${plane.face}” is not flat — sketches and holes go on flat faces.`);
    return { face: f.ref || { name: f.name }, frame: f.frame };
  };
  const summary = () => {
    const b = body();
    return b ? { size_mm: [r3(b.bbox[3] - b.bbox[0]), r3(b.bbox[4] - b.bbox[1]), r3(b.bbox[5] - b.bbox[2])], bbox: b.bbox.map(r3), volume_mm3: r3(b.volume),
      material: m.part.material || 'PLA', mass_g_solid: m.massGrams(), faces: b.faces.length } : null;
  };
  const stepResult = (id) => {
    const st = m.status(id);
    const f = m.part.features.find((x) => x.id === id);
    return { id, name: f?.name, ok: st ? st.ok : null, issues: st?.issues || [], warnings: st?.warnings || [], body: summary() };
  };
  const commitAnd = async (id) => { m.commit(); await settle(); return { text: JSON.stringify(stepResult(id)) }; };
  const ready = () => { if (m.mode !== 'part' || m.cmd) m.closeAll?.(); m.cmd = null; m.mode = 'part'; m.render(); };

  /** A feature from the AI's description -> the feature JSON the modeler stores. */
  const build = (spec) => {
    const type = spec.type;
    const base = { id: m.newId(), type, name: spec.name || m.nextName(type) };
    if (type === 'sketch') {
      return { ...base, plane: planeOf(spec.plane), ...sketchFromShapes(spec.shapes, spec.lock !== false) };
    }
    if (type === 'extrude' || type === 'revolve') {
      const sk = spec.sketch || [...m.sketches()].pop()?.id;
      if (!m.part.features.some((f) => f.id === sk && f.type === 'sketch')) throw new Error('sketch: the id of a sketch step (from get_model).');
      return type === 'extrude'
        ? { ...base, sketch: sk, op: spec.op === 'cut' ? 'cut' : 'add', d: spec.d ?? 10, through: !!spec.through, symmetric: !!spec.symmetric, flip: !!spec.flip,
          ...(spec.up_to ? { upto: { name: faceOf(spec.up_to).name, fp: faceOf(spec.up_to).centroid }, offset: spec.offset || 0 } : {}) }
        : { ...base, sketch: sk, op: spec.op === 'cut' ? 'cut' : 'add', axis: spec.axis || 'y', angle: spec.angle ?? 360 };
    }
    if (type === 'fillet' || type === 'chamfer') {
      const edges = (spec.edges || []).map((e) => (e.ref || e));
      if (!edges.length || edges.some((e) => !e.a || !e.b || !e.fp)) throw new Error('edges: edge refs {a, b, fp} from find_refs.');
      return { ...base, edges, ...(type === 'fillet' ? { r: spec.r ?? 1 } : { d: spec.d ?? 1 }) };
    }
    if (type === 'hole') {
      if (!spec.face) throw new Error('face: the name of the flat face the holes go into (find_refs).');
      return { ...base, plane: planeOf({ face: spec.face }), points: spec.points || [[0, 0]], d: spec.d ?? 5,
        through: spec.through !== false, depth: spec.depth ?? 10, ...(spec.from ? { from: spec.from } : {}) };
    }
    if (type === 'shell') {
      const faces = (spec.faces || []).map((n) => { const f = faceOf(typeof n === 'string' ? n : n.name); return { name: f.name, fp: f.centroid }; });
      return { ...base, faces, t: spec.t ?? 2 };
    }
    if (type === 'loft') {
      const ids = [].concat(spec.sketches || []);
      if (ids.length < 2 || ids.some((x) => !m.part.features.some((g) => g.id === x && g.type === 'sketch'))) throw new Error('sketches: the ids of two (or more) sketch steps, in order.');
      return { ...base, sketches: ids, op: spec.op === 'cut' ? 'cut' : 'add' };
    }
    if (type === 'sweep') {
      for (const k of ['profile', 'path']) if (!m.part.features.some((g) => g.id === spec[k] && g.type === 'sketch')) throw new Error(`${k}: the id of a sketch step.`);
      return { ...base, profile: spec.profile, path: spec.path, op: spec.op === 'cut' ? 'cut' : 'add' };
    }
    if (type === 'pattern') {
      const of = [].concat(spec.of || spec.features || []);
      if (!of.length || of.some((id) => !m.part.features.some((f) => f.id === id && ['extrude', 'revolve', 'hole', 'pattern'].includes(f.type)))) {
        throw new Error('of: the id(s) of the extrude / revolve / hole / pattern step(s) to repeat (get_model).');
      }
      const AX = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };
      const vec = (v, what) => {
        if (typeof v === 'string' && AX[v.toLowerCase()]) return AX[v.toLowerCase()];
        if (Array.isArray(v) && v.length === 3 && v.every(Number.isFinite)) return v;
        throw new Error(`${what}: "x", "y", "z" or [dx, dy, dz].`);
      };
      if (spec.kind === 'circular') {
        let axis = { o: [0, 0, 0], d: [0, 0, 1] };
        if (typeof spec.axis === 'string' && !AX[spec.axis.toLowerCase()]) {
          const f = faceOf(spec.axis); // a round face: its axis
          if (!f.axis) throw new Error(`axis: “${spec.axis}” is not a round face — give "x" / "y" / "z", {o, d} or a round face's name.`);
          axis = f.axis;
        } else if (spec.axis && typeof spec.axis === 'object' && !Array.isArray(spec.axis)) axis = { o: spec.axis.o || [0, 0, 0], d: vec(spec.axis.d, 'axis.d') };
        else if (spec.axis) axis = { o: [0, 0, 0], d: vec(spec.axis, 'axis') };
        return { ...base, features: of, kind: 'circular', axis, count: spec.count ?? 6, ...(spec.angle ? { angle: spec.angle } : {}) };
      }
      return { ...base, features: of, kind: 'linear', dir: vec(spec.dir || 'x', 'dir'), count: spec.count ?? 3, spacing: spec.spacing ?? 10 };
    }
    throw new Error('type is sketch, extrude, revolve, fillet, chamfer, hole, shell, pattern, loft or sweep.');
  };

  /** An edge polyline that is a circle or an arc (a hole's edge often comes as two half circles) -> its centre and radius. */
  const circleOf = (pts) => {
    const P = [];
    for (let i = 0; i < pts.length; i += 3) P.push([pts[i], pts[i + 1], pts[i + 2]]);
    if (P.length < 5) return null;
    // the circle through the first, middle and last point (circumcentre in 3D)
    const a = P[0], b = P[Math.floor(P.length / 2)], c = P[P.length - 1] === a || len(sub(P[P.length - 1], a)) < 1e-9 ? P[Math.floor(P.length / 4)] : P[P.length - 1];
    const cross = (p, q) => [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]];
    const ab = sub(b, a), ac = sub(c, a), n = cross(ab, ac);
    const den = 2 * dot(n, n);
    if (den < 1e-12) return null; // a straight edge
    // centre = a + (|ac|² (n × ab) + |ab|² (ac × n)) / (2 |n|²)
    const t1 = cross(n, ab), t2 = cross(ac, n), kac = dot(ac, ac), kab = dot(ab, ab);
    const u = [0, 1, 2].map((i) => (kac * t1[i] + kab * t2[i]) / den);
    const centre = [a[0] + u[0], a[1] + u[1], a[2] + u[2]], r = len(u);
    return P.every((p) => Math.abs(len(sub(p, centre)) - r) < r * 0.01 + 1e-6) ? { centre: centre.map(r3), radius: r3(r) } : null;
  };

  return {
    list_parts: async () => ({ text: JSON.stringify(project.parts.map((p) => ({ id: p.id, name: p.name, kind: KIND[p.kind] || 'quick part', on_screen: p.id === project.active }))) }),

    open_part: async ({ id }) => {
      const p = project.parts.find((q) => q.id === id || q.name === id);
      if (!p) throw new Error(`No part “${id}” — see list_parts.`);
      await project.switchTo(p.id);
      await settle();
      return { text: `On screen: ${p.name} (${KIND[p.kind] || 'quick part'}).` };
    },

    new_model: async ({ name }) => {
      await project.newModel(null, name || null, 'none');
      await settle();
      return { text: `New 3D model “${project.current?.name}” (empty). Next: add_feature {type: "sketch", …}, then an extrude.` };
    },

    get_model: async () => {
      needModel();
      await settle();
      const steps = m.part.features.map((f) => {
        const st = m.status(f.id) || {};
        const out = { id: f.id, type: f.type, name: f.name, what: m.whatText(f), ok: st.ok ?? null };
        if (st.issues?.length) out.issues = st.issues;
        if (st.warnings?.length) out.warnings = st.warnings;
        if (f.suppressed) out.off = true;
        if (f.type === 'sketch') {
          out.plane = f.plane?.datum || f.plane?.face?.name;
          out.shapes = (f.entities || []).map((e) => e.t).reduce((a, t) => ({ ...a, [t]: (a[t] || 0) + 1 }), {});
          out.locked_sizes = (f.dims || []).filter((d) => !d.free).length;
        }
        if (f.type === 'extrude') Object.assign(out, { sketch: f.sketch, op: f.op, d: f.d, through: !!f.through, symmetric: !!f.symmetric });
        if (f.type === 'revolve') Object.assign(out, { sketch: f.sketch, op: f.op, axis: f.axis, angle: f.angle });
        if (f.type === 'fillet') Object.assign(out, { r: f.r, edges: f.edges.length });
        if (f.type === 'chamfer') Object.assign(out, { d: f.d, edges: f.edges.length });
        if (f.type === 'hole') Object.assign(out, { face: f.plane?.face?.name, d: f.d, points: f.points, through: f.through !== false, depth: f.depth });
        if (f.type === 'shell') Object.assign(out, { t: f.t, open_faces: f.faces.map((x) => x.name) });
        if (f.type === 'loft') Object.assign(out, { sketches: f.sketches, op: f.op });
        if (f.type === 'sweep') Object.assign(out, { profile: f.profile, path: f.path, op: f.op });
        if (f.type === 'pattern') Object.assign(out, { of: f.features, kind: f.kind, count: f.count, ...(f.kind === 'circular' ? { axis: f.axis } : { dir: f.dir, spacing: f.spacing }) });
        return out;
      });
      return { text: JSON.stringify({ name: project.current?.name, unit: 'mm', steps, body: summary() }) };
    },

    find_refs: async ({ kind = 'face', name, normal, extreme, near, of_face, circular, limit = 12 }) => {
      needModel();
      await settle();
      const b = body();
      if (!b) throw new Error('The model has no solid yet.');
      if (kind === 'face') {
        let fs = b.faces.filter((f) => f.name);
        if (name) fs = fs.filter((f) => f.name.includes(name));
        if (normal) { const n = normal.map(Number), L = len(n) || 1; fs = fs.filter((f) => f.normal && dot(f.normal, n) / L > 0.999); }
        if (extreme && fs.length) {
          const dir = normal || [0, 0, 1], L = len(dir) || 1;
          const key = (f) => dot(f.centroid, dir) / L;
          const best = extreme === 'min' ? Math.min(...fs.map(key)) : Math.max(...fs.map(key));
          fs = fs.filter((f) => Math.abs(key(f) - best) < 1e-6 * (1 + Math.abs(best)));
        }
        if (near) fs.sort((a, c) => len(sub(a.centroid, near)) - len(sub(c.centroid, near)));
        else fs.sort((a, c) => c.area - a.area);
        return { text: JSON.stringify(fs.slice(0, limit).map((f) => ({ name: f.name, type: f.type, normal: f.normal, centroid: f.centroid, area: r3(f.area), radius: f.radius }))) };
      }
      if (kind === 'edge') {
        let es = b.edges.map((e, i) => ({ e, i })).filter(({ e }) => e.faces.length === 2);
        if (of_face) {
          const ids = b.faces.filter((f) => f.name === of_face).map((f) => f.id);
          es = es.filter(({ e }) => e.faces.some((k) => ids.includes(k)));
        }
        const info = es.map(({ e }) => {
          const [fa, fb] = e.faces.map((k) => b.faces[k]?.name);
          let L = 0;
          for (let k = 3; k < e.pts.length; k += 3) L += Math.hypot(e.pts[k] - e.pts[k - 3], e.pts[k + 1] - e.pts[k - 2], e.pts[k + 2] - e.pts[k - 1]);
          const c = circleOf(e.pts);
          return { ref: { a: fa, b: fb, fp: e.mid }, between: [fa, fb], mid: e.mid, length: r3(L), ...(c ? { circle: c } : {}) };
        }).filter((x) => x.ref.a && x.ref.b && (circular === undefined || !!x.circle === !!circular));
        if (near) info.sort((a, c) => len(sub(a.mid, near)) - len(sub(c.mid, near)));
        return { text: JSON.stringify(info.slice(0, limit)) };
      }
      throw new Error('kind is "face" or "edge".');
    },

    add_feature: async (spec) => {
      needModel();
      ready();
      await settle();
      const f = build(spec);
      m.part.features.push(f);
      return commitAnd(f.id);
    },

    edit_feature: async ({ id, fields = {} }) => {
      needModel();
      ready();
      const f = m.part.features.find((x) => x.id === id);
      if (!f) throw new Error(`No step ${id} — see get_model.`);
      if (f.type === 'sketch' && (fields.shapes || fields.plane)) {
        Object.assign(f, sketchFromShapes(fields.shapes || [], fields.lock !== false));
        if (fields.plane) f.plane = planeOf(fields.plane);
      } else {
        const next = build({ ...f, ...fields, type: f.type, of: fields.of || f.features, name: fields.name || f.name, face: fields.face || f.plane?.face?.name, faces: fields.faces || f.faces?.map((x) => x.name), sketch: fields.sketch || f.sketch });
        Object.assign(f, { ...next, id: f.id, name: fields.name || f.name });
      }
      return commitAnd(id);
    },

    delete_feature: async ({ id }) => {
      needModel();
      ready();
      if (!m.part.features.some((x) => x.id === id)) throw new Error(`No step ${id}.`);
      const before = m.part.features.length;
      const keep = window.confirm;
      window.confirm = () => true; // the AI was asked to; the steps that need it go too (listed in the result)
      try { m.remove(id); } finally { window.confirm = keep; }
      await settle();
      return { text: `Deleted ${before - m.part.features.length} step(s). ${JSON.stringify({ steps: m.part.features.map((x) => x.id), body: summary() })}` };
    },

    turn_off_feature: async ({ id, off = true }) => {
      needModel();
      ready();
      const f = m.part.features.find((x) => x.id === id);
      if (!f) throw new Error(`No step ${id}.`);
      if (!!f.suppressed !== !!off) m.toggleOff(id);
      await settle();
      return { text: JSON.stringify(stepResult(id)) };
    },

    set_material: async ({ material }) => {
      needModel();
      m.setMaterial(String(material || '').toUpperCase());
      return { text: JSON.stringify(summary()) };
    },

    prepare_print: async () => {
      needModel();
      await settle();
      if (!body()) throw new Error('The model has no solid yet.');
      await m.toPrint();
      return { text: 'A printing copy is open as a quick part on the 3D print tab — use check_print (and export) on it now.' };
    },

    // the model versions of shared tools
    model_screenshot: async ({ view }) => {
      needModel();
      await settle();
      if (view) m.view.setView({ front: 'front', back: 'front', side: 'right', top: 'top' }[view] || 'iso');
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const v = m.view;
      v.renderer.render(v.scene, v.camera);
      const src = v.renderer.domElement, k = Math.min(1, 900 / Math.max(src.width, src.height));
      const c = document.createElement('canvas');
      c.width = Math.round(src.width * k);
      c.height = Math.round(src.height * k);
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#161b22';
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(src, 0, 0, c.width, c.height);
      return { text: `3D view (${view || 'current'}). ${JSON.stringify(summary())}`, image: c.toDataURL('image/png').split(',')[1] };
    },
    model_body: async () => { needModel(); return { text: 'ok', body: { model_part: m.payload(), name: project.current?.name } }; },
    model_undo: async () => { needModel(); const ok = await m.history.go(-1); await settle(); return { text: ok ? `Undone. ${JSON.stringify(summary())}` : 'Nothing to undo.' }; },
  };
}
