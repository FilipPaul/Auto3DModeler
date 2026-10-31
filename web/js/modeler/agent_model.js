// The AI tools for 3D model parts (they arrive from the app's MCP server like the classic ones in app.js):
// list / open / start parts, read the model, find faces and edges, add / change / delete / turn off steps,
// a screenshot, a printing copy. Every change goes through the modeler like a user edit (visible, undoable).

import { MATERIALS } from './materials.js';
import { makePattern, roundCorner } from './sketcher.js';
import { textOutline } from '../outlinepanel.js';
import { originAt, worldToUV } from './origin.js';
import { roundAxes, axisOf } from './axes.js';
import { datumFrame } from './view.js';
import { nextFrames } from '../frames.js';
import { sketchHandlers } from './agent_sketch.js';
import { HOLE_SIZES, HOLE_SHAPES, dFlat, holeSpec, presetFor } from './holes.js';
import { exprArgs, keepExprs } from '../paramsui.js';

// 𝑥 the numbers of a step the AI may give as an expression of the project's parameters ("L / 2")
const EXPR_KEYS = ['d', 'd2', 'offset', 'draft', 'r', 'angle', 't', 'depth', 'count', 'spacing', 'h', 'flat', 'flat_angle', 'head_d', 'head_depth', 'head_angle'];

const r3 = (v) => +(+v).toFixed(3);
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const DATUM = { XY: 'XY', TOP: 'XY', XZ: 'XZ', FRONT: 'XZ', YZ: 'YZ', RIGHT: 'YZ' };

/** A sketch from simple shapes: rect {x, y, w, h, r} (lower-left corner, r = rounded corners), circle {x, y, d} (centre), polyline {points}
 *  (closed). Any shape may add pattern: {count, spacing} (copies in a row along X) or {count, around: [x, y]} (around that
 *  point, over 360°) — a ⁂ Pattern of the sketch, the copies follow it. lock: every size and position is locked (the
 *  sketch is fully defined). A shape's from: {axis: <a round face's name>} measures its place across that axis from it
 *  (it follows the axis): axisAt(name) -> {ref: {face, fp}, c: [u, v] of the axis, dir: [du, dv] or null (square)}. */
export function sketchFromShapes(shapes, lock = true, axisAt = null) {
  const f = { points: {}, entities: [], constraints: [], dims: [] };
  let n = { p: 0, l: 0, c: 0, r: 0, k: 0, d: 0 };
  const id = (k) => `${k}${(n[k] = (n[k] || 0) + 1)}`;
  const dim = (spec) => { if (lock) f.dims.push({ id: id('d'), ...spec }); };
  let from = null; // (the shape's axis to measure from, or null: from the origin)
  const r9 = (v) => +(+v).toFixed(9);
  const point = (u, v, locked, exact = false) => { // (exact: a point worked out from others — rounded it would not fit them)
    const p = id('p');
    f.points[p] = exact ? [r9(u), r9(v)] : [r3(u), r3(v)];
    if (!locked) return p;
    for (const [t, k] of [['dx', 0], ['dy', 1]]) {
      const ax = from && (!from.dir || Math.abs(from.dir[k]) < 1e-6) ? from : null; // (an axis along the plane gives only the place across it)
      const at = [r3(u), r3(v)];
      if (ax) at[k] = r3(ax.c[k]);
      dim(ax ? { t, a: { ref: ax.dir ? at : ax.c.map(r3), axis: ax.ref }, b: p, v: r3([u, v][k] - ax.c[k]) } : { t, a: 'O', b: p, v: r3([u, v][k]) });
    }
    return p;
  };
  for (const s of shapes || []) {
    const first = f.entities.length; // (this shape's entities: from here)
    from = null;
    if (s.from) {
      if (!s.from.axis || !axisAt) throw new Error('from: {axis: "<a round face\'s name>"} (find_refs kind "axis").');
      from = axisAt(s.from.axis);
    }
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
      const [X1, Y1, X2, Y2] = [x1, y1, x2, y2].map(r3);
      const A = point(X1 - nx, Y1 - ny, false, true), B = point(X2 - nx, Y2 - ny, false, true), C = point(X2 + nx, Y2 + ny, false, true), D = point(X1 + nx, Y1 + ny, false, true);
      const a1 = id('c'), a2 = id('c'), s1 = id('l'), s2 = id('l');
      f.entities.push({ id: s1, t: 'line', a: A, b: B }, { id: a1, t: 'arc', c: c2, a: B, b: C },
        { id: s2, t: 'line', a: C, b: D }, { id: a2, t: 'arc', c: c1, a: D, b: A });
      // the sides tangent to both ends, the ends alike: its two centres and one radius fix it (5 sizes)
      f.constraints.push({ id: id('k'), t: 'tan', e: s1, arc: a1, p: B }, { id: id('k'), t: 'tan', e: s1, arc: a2, p: A },
        { id: id('k'), t: 'tan', e: s2, arc: a1, p: C }, { id: id('k'), t: 'tan', e: s2, arc: a2, p: D },
        { id: id('k'), t: 'eq', e: a1, e2: a2, user: true });
      dim({ t: 'rad', e: a1, v: r3(r) });
    } else if (s.path) {
      // an open line (a sweep's path): points joined in order, not closed
      const pts = s.path.points || [];
      if (pts.length < 2) throw new Error('A path needs at least 2 points.');
      const ps = pts.map(([u, v], i) => point(u, v, i === 0));
      for (let i = 0; i + 1 < ps.length; i++) f.entities.push({ id: id('l'), t: 'line', a: ps[i], b: ps[i + 1] });
    } else if (s.profile) {
      // a closed outline: corners [x, y] joined by straight lines, {arc: [x, y]} an arc through that point to the
      // next corner, {smooth: [[x, y], …]} a smooth curve through those points to the next corner
      const items = s.profile.points || s.profile;
      if (!Array.isArray(items) || items.length < 2) throw new Error('A profile needs its points: [[x, y], {smooth: [[x, y], …]}, {arc: [x, y]}, …] (closed).');
      const corners = [];
      items.forEach((it, i) => {
        if (Array.isArray(it)) corners.push({ at: it, next: null });
        else if (it && (it.smooth || it.arc)) {
          if (!corners.length) throw new Error('A profile starts with a corner [x, y] (then smooth / arc parts may follow).');
          corners[corners.length - 1].next = it;
        } else throw new Error(`Profile item ${i + 1}: a corner [x, y], {smooth: [[x, y], …]} or {arc: [x, y]}.`);
      });
      if (corners.length < 2 && !corners[0]?.next) throw new Error('A profile needs at least 2 corners, or a smooth part.');
      const ids = corners.map((c) => point(c.at[0], c.at[1], true)), arcs = [];
      corners.forEach((c, i) => {
        const a = ids[i], b = ids[(i + 1) % ids.length], A = c.at, B = corners[(i + 1) % corners.length].at;
        if (c.next?.smooth) {
          const mids = c.next.smooth.map(([u, v]) => point(u, v, true));
          f.entities.push({ id: id('s'), t: 'spline', pts: [a, ...mids, b] });
        } else if (c.next?.arc) {
          const M = c.next.arc, ax = B[0] - A[0], ay = B[1] - A[1], bx = M[0] - A[0], by = M[1] - A[1], dd = 2 * (ax * by - ay * bx);
          if (Math.abs(dd) < 1e-12) throw new Error(`Profile: the arc through [${M}] is a straight line — move that point off the line.`);
          const ux = (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / dd, uy = (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / dd;
          // its centre is not locked: with both ends locked that would hold it twice (a conflict, the sketch red)
          const cc = point(A[0] + ux, A[1] + uy, false, true), arc = id('a');
          // the sketch's arcs run counter-clockwise from a to b: from A through M to B, or the other way round
          f.entities.push(dd > 0 ? { id: arc, t: 'arc', c: cc, a: b, b: a } : { id: arc, t: 'arc', c: cc, a, b });
          arcs.push({ arc, cc, ends: [a, b], r: Math.hypot(ux, uy) });
        } else if (a !== b) {
          const l = id('l');
          f.entities.push({ id: l, t: 'line', a, b });
          if (Math.abs(A[1] - B[1]) < 1e-9) f.constraints.push({ id: id('k'), t: 'h', e: l });
          else if (Math.abs(A[0] - B[0]) < 1e-9) f.constraints.push({ id: id('k'), t: 'v', e: l });
        }
      });
      // an arc the line beside it runs into smoothly is tangent to it (that fixes the arc, with its locked ends);
      // a sharp one gets its radius locked instead. One tangent at most: a second would hold it twice.
      const P = (p) => f.points[p];
      for (const { arc, cc, ends, r } of arcs) {
        const tan = ends.map((p) => {
          const l = f.entities.slice(first).find((e) => e.t === 'line' && (e.a === p || e.b === p));
          if (!l) return null;
          const q = P(l.a === p ? l.b : l.a), o = P(p), c = P(cc), L = Math.hypot(q[0] - o[0], q[1] - o[1]) * r;
          return L && Math.abs((q[0] - o[0]) * (o[0] - c[0]) + (q[1] - o[1]) * (o[1] - c[1])) / L < Math.sin(Math.PI / 360) ? { e: l.id, p } : null;
        }).find(Boolean);
        if (tan) f.constraints.push({ id: id('k'), t: 'tan', e: tan.e, arc, p: tan.p });
        else dim({ t: 'rad', e: arc, v: r3(r) });
      }
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
    } else throw new Error('Each shape is {rect: {x, y, w, h}}, {circle: {x, y, d}}, {polyline: {points: [[u, v], …]}} or {profile: {points: [[u, v], {smooth: [[u, v], …]}, {arc: [u, v]}, …]}}.');
    if (s.pattern) { // ⁂ copies of this shape, held by a pattern relation (as the sketch's ⁂ Pattern makes them)
      const pt = s.pattern, n = pt.count ?? pt.n, at = pt.around;
      if (at !== undefined && !(Array.isArray(at) && at.length === 2 && at.every(Number.isFinite))) throw new Error('pattern.around: the centre [x, y].');
      const c = at ? (Math.hypot(at[0], at[1]) < 1e-9 ? 'O' : point(at[0], at[1], true)) : null;
      makePattern(f, f.entities.slice(first).map((e) => e.id), c ? { kind: 'around', n, c } : { kind: 'row', n, d: pt.spacing ?? pt.d }, id);
    }
  }
  // a locked polyline / rectangle corner already fixes its points: the H / V rules there are redundant locks
  if (lock) {
    const fixedLine = (l) => {
      const e = f.entities.find((x) => x.id === l);
      const fixed = (p) => f.dims.some((d) => d.t === 'dx' && d.b === p) && f.dims.some((d) => d.t === 'dy' && d.b === p);
      return e && fixed(e.a) && fixed(e.b);
    };
    f.constraints = f.constraints.filter((k) => !((k.t === 'h' || k.t === 'v') && fixedLine(k.e)));
  }
  return f;
}

/** The size labels shown over the 3D view (page elements, not part of the WebGL picture) drawn onto a screenshot of
 *  it: ctx the picture's 2D context, box the label layer's box on the page (as big as the picture's render). */
function drawLabels(ctx, box) {
  const sx = ctx.canvas.width / (box.width || 1), sy = ctx.canvas.height / (box.height || 1);
  ctx.font = `${Math.round(11 * sx)}px sans-serif`;
  ctx.textBaseline = 'middle';
  for (const el of document.querySelectorAll('#modelViewport .sk-label, #modelViewport .m-dimtag')) {
    const r = el.getBoundingClientRect();
    if (!r.width || r.right < box.left || r.left > box.right || r.bottom < box.top || r.top > box.bottom) continue;
    const text = (el.querySelector('.sk-val')?.textContent ?? el.textContent).replace(/\s+/g, ' ').trim() + (el.classList.contains('locked') ? ' 🔒' : '');
    const x = (r.left - box.left) * sx, y = (r.top - box.top) * sy, w = Math.max(r.width * sx, ctx.measureText(text).width + 6 * sx), h = r.height * sy;
    ctx.fillStyle = el.classList.contains('locked') ? '#2a1d45e6' : '#0d1117d9';
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = el.classList.contains('locked') ? '#e2d4ff' : '#c9d1d9';
    ctx.fillText(text, x + 3 * sx, y + h / 2);
  }
}

const KIND = { model: '3D model', assembly: 'assembly', drawing: '2D drawing', sheet: 'drawing sheet' };
const FITS = ['H6', 'H7', 'H8', 'H9'];
/** A hole's fit as written ("h7", "H7") -> "H7", or null (none / unknown: refused by the caller's check). */
const fitOf = (v) => { if (!v) return null; const f = String(v).toUpperCase(); if (!FITS.includes(f)) throw new Error(`fit: one of ${FITS.join(', ')} (ISO 286 holes), not ${v}.`); return f; };
const ADDS = new Set(['extrude', 'revolve', 'loft', 'sweep']); // (steps that add a solid unless op: cut)
const MATERIAL_NAME =Object.fromEntries(Object.keys(MATERIALS).map((k) => [k.toLowerCase(), k])); // (any case)

export function modelHandlers({ modeler: m, project, getWorkspace }) {
  const needModel = () => {
    if (getWorkspace() !== 'model') throw new Error('The part on screen is not a 3D model — use get_part for it, or list_parts / open_part / new_model.');
  };
  const settle = async () => {
    await new Promise((r) => setTimeout(r, 30));
    while (m.inflight || m.threading) await (m.inflight || m.threading); // (🔩 real threads: their cut too)
  };
  const body = () => m.result?.body;
  const faceOf = (name) => {
    const b = body(), is = (f) => f.name === name || (f.names || []).includes(name);
    // (a 👁 reference solid's faces too: a sketch on a bought part's face, its outline taken)
    const fs = [...(b?.faces || []).filter(is), ...(m.result?.refs || []).flatMap((r) => (r.faces || []).filter(is))];
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
    if (plane.mid) { // midway between this face and the parallel face across from it (follows both)
      const g = faceOf(plane.mid), n = f.frame.n, dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      const gap = g.type === 'plane' ? dot(g.frame.o.map((v, i) => v - f.frame.o[i]), n) : 0;
      if (g.type !== 'plane' || Math.abs(Math.abs(dot(n, g.frame.n)) - 1) > 1e-6 || Math.abs(gap) < 1e-6) throw new Error(`mid: “${plane.mid}” must be a flat face parallel to “${plane.face}”, across from it.`);
      return withOrigin({ face: f.ref || { name: f.name }, mid: g.ref || { name: g.name }, frame: { ...f.frame, o: f.frame.o.map((v, i) => v + (gap / 2) * n[i]) } }, plane.origin);
    }
    return withOrigin({ face: f.ref || { name: f.name }, frame: f.frame }, plane.origin);
  };
  /** A face plane measured from origin "corner" / "world" / {point} (none, "centre": the face's centre). */
  const withOrigin = (pl, how) => {
    if (how == null || how === 'centre' || how === 'center') return pl;
    const o = how === 'corner' || how === 'world' ? how : typeof how === 'object' && how.point ? { point: how.point } : null;
    if (!o) throw new Error(`origin: "corner" (the face's corner with the smallest u and v), "world" (the part's origin: world coordinates) or {point: "<a point step's id>"}.`);
    if (o.point && !m.part.features.some((g) => g.id === o.point && g.type === 'point')) throw new Error(`origin.point: ${o.point} is not a point step — add_feature point first.`);
    const p = originAt(o, pl.frame, { span: (fr) => m.view.faceSpan(pl.face?.name, fr), points: m.result?.points });
    return { ...pl, origin: o, frame: p ? { ...pl.frame, o: p } : pl.frame };
  };
  /** A sketch drawn in world coordinates: where the face's v runs against the world axis, turned over to it. */
  const fromWorld = (sk, fr) => {
    if (!worldToUV(fr).flip) return sk;
    for (const [k, p] of Object.entries(sk.points)) sk.points[k] = [p[0], r3(-p[1])];
    for (const d of sk.dims) {
      if (d.t === 'dy') d.v = r3(-d.v);
      if (Array.isArray(d.a?.ref)) d.a = { ...d.a, ref: [d.a.ref[0], r3(-d.a.ref[1])] };
    }
    for (const e of sk.entities) if (e.t === 'arc') [e.a, e.b] = [e.b, e.a]; // (counter-clockwise again)
    return sk;
  };
  const summary = () => {
    const b = body();
    return b ? { size_mm: [r3(b.bbox[3] - b.bbox[0]), r3(b.bbox[4] - b.bbox[1]), r3(b.bbox[5] - b.bbox[2])], bbox: b.bbox.map(r3), volume_mm3: r3(b.volume),
      material: m.part.material || 'PLA', mass_g_solid: m.massGrams(), ...(Number.isFinite(b.area) ? { area_mm2: r3(b.area) } : {}), ...(b.cog ? { cog_mm: b.cog.map(r3) } : {}),
      faces: b.faces.length, ...(b.solids > 1 ? { solids: b.solids } : {}) } : null;
  };
  const stepResult = (id) => {
    const st = m.status(id);
    const f = m.part.features.find((x) => x.id === id);
    const under = f && m.part.features.indexOf(f) >= m.barAt(); // (⏮ under the rollback bar: kept, not built now)
    return { id, name: f?.name, ok: st ? st.ok : null, issues: st?.issues || [], warnings: st?.warnings || [], ...(st?.went ? { went: st.went } : {}), ...(under ? { rolled_back: true } : {}), body: summary() };
  };
  const commitAnd = async (id) => {
    const v0 = body()?.volume ?? 0;
    m.commit();
    await settle();
    const r = stepResult(id), dv = (body()?.volume ?? 0) - v0;
    if (r.ok && r.body) r.volume_change_mm3 = r3(dv); // (an add that adds nothing, a cut that cuts nothing: the wrong way?)
    const f = m.part.features.find((x) => x.id === id);
    if (r.ok && r.body && v0 > 0 && ADDS.has(f?.type) && (f.op || 'add') === 'add' && Math.abs(dv) < 1e-6 * (1 + v0)) // (the kernel says it of a cut)
      r.warnings = [...r.warnings, 'It adds nothing — it lies inside the part (⇅ flip: true sends it the other way).'];
    return { text: JSON.stringify(r) };
  };
  const ready = () => { if (m.mode !== 'part' || m.cmd) m.closeAll?.(); m.cmd = null; m.mode = 'part'; m.render(); };

  /** A round face's axis on a sketch's plane, for a shape's from: {axis} (world: v turned over as the shapes are). */
  const axisAtOn = (plane) => (name) => {
    const fr = plane.datum ? datumFrame(plane) : plane.frame, g = faceOf(name);
    const q = axisOf(roundAxes(body(), fr), { face: g.name, fp: g.centroid });
    if (!q) throw new Error(`from.axis: “${name}” is not a round face (a cylinder) — find_refs kind "axis" lists them.`);
    if (q.dir && Math.abs(q.dir[0]) > 1e-6 && Math.abs(q.dir[1]) > 1e-6) throw new Error(`from.axis: the axis of “${name}” runs slanted across the sketch — measure from an axis along its x or y, or square to it.`);
    const flip = plane.origin === 'world' && worldToUV(fr).flip ? -1 : 1;
    return { ref: q.ref, c: [q.c[0], flip * q.c[1]], dir: q.dir && [q.dir[0], flip * q.dir[1]] };
  };
  /** A hole's from: {x: {axis: <name>, d}} -> the round face's ref {face, fp} (edges and holes as given). */
  const holeFrom = (from) => (Array.isArray(from) ? from.map((s) => {
    if (!s || typeof s !== 'object') return s;
    const out = { ...s };
    for (const k of ['x', 'y']) {
      const mid = s[k]?.mid; // (midway between two straight edges: kept in the middle)
      if (mid !== undefined) {
        if (!Array.isArray(mid) || mid.length !== 2 || mid.some((e) => !e?.a || !e?.b || !e?.fp)) throw new Error(`from.${k}.mid: two edge refs {a, b, fp} from find_refs (the edges on either side).`);
        out[k] = { mid, d: +s[k].d || 0 };
      }
      const ax = s[k]?.axis;
      if (!ax) continue;
      const g = faceOf(typeof ax === 'string' ? ax : ax.face);
      if (!g.axis) throw new Error(`from.${k}.axis: “${g.name}” is not a round face (a cylinder) — find_refs kind "axis" lists them.`);
      out[k] = { ...s[k], axis: typeof ax === 'string' ? { face: g.name, fp: g.centroid } : ax };
    }
    return out;
  }) : from);
  /** 🔒 A hole's positions locked (the user's drag keeps them — holedrag.js; the kernel ignores it): true = every
   *  position both ways, false / null = none, [{x, y} | true | null, …] per position -> f.lock, or null. */
  const holeLock = (lock, n) => {
    if (!lock) return null;
    if (lock !== true && !Array.isArray(lock)) throw new Error('lock: true (every position, both ways), false (none) or [{x: true, y: true} | null, …] — one per position.');
    const one = (q) => (q === true ? { x: true, y: true } : q && typeof q === 'object' ? Object.fromEntries(['x', 'y'].filter((k) => q[k]).map((k) => [k, true])) : {});
    const out = Array.from({ length: n }, (_, i) => { const q = one(lock === true ? true : lock[i]); return Object.keys(q).length ? q : null; });
    return out.some(Boolean) ? out : null;
  };
  /** A hole's stored distances, short for the AI: per position {x, y: {d, from: "edge" | "axis" | "mid" | "hole", ref}}. */
  const fromInfo = (from) => (from || []).map((s) => Object.fromEntries(['x', 'y'].filter((k) => s?.[k]).map((k) => {
    const q = s[k], kind = ['edge', 'axis', 'mid', 'hole'].find((x) => q[x] !== undefined);
    const ref = kind === 'edge' ? `${q.edge.a}|${q.edge.b}` : kind === 'axis' ? q.axis.face : kind === 'mid' ? q.mid.map((e) => `${e.a}|${e.b}`) : kind === 'hole' ? q.hole : undefined;
    return [k, { d: q.d, ...(kind ? { from: kind } : {}), ...(ref !== undefined ? { ref } : {}) }];
  })));

  /** A feature from the AI's description -> the feature JSON the modeler stores. */
  const build = (spec) => {
    const type = spec.type;
    const base = { id: m.newId(), type, name: spec.name || m.nextName(type, spec.sketch || (['extrude', 'revolve'].includes(type) ? [...m.sketches()].pop()?.id : null)) };
    if (type === 'sketch') {
      const plane = planeOf(spec.origin && spec.plane && typeof spec.plane === 'object' ? { ...spec.plane, origin: spec.origin } : spec.plane);
      const takes = (spec.shapes || []).filter((x) => x?.from_face || x?.from_edges); // (⇱ taken from the part: its edges, held to it)
      const sk = sketchFromShapes((spec.shapes || []).filter((x) => !takes.includes(x)), spec.lock !== false, axisAtOn(plane));
      const out = { ...base, plane, ...(plane.origin === 'world' ? fromWorld(sk, plane.frame) : sk) };
      for (const x of takes) {
        if (x.from_face) { const g = faceOf(x.from_face); out.constraints.push({ t: 'proj', face: { name: g.name, fp: g.centroid } }); continue; }
        const es = (Array.isArray(x.from_edges) ? x.from_edges : [x.from_edges]).map((e) => e?.ref || e);
        if (!es.length || es.some((e) => !e?.a || !e?.b || !e?.fp)) throw new Error('from_edges: edge refs {a, b, fp} from find_refs.');
        out.constraints.push({ t: 'proj', edges: es });
      }
      return out;
    }
    if (type === 'extrude' || type === 'revolve') {
      const sk = spec.sketch || [...m.sketches()].pop()?.id;
      if (!m.part.features.some((f) => f.id === sk && f.type === 'sketch')) throw new Error('sketch: the id of a sketch step (from get_model).');
      return type === 'extrude'
        ? { ...base, sketch: sk, op: spec.op === 'cut' ? 'cut' : 'add', d: spec.d ?? 10, through: !!spec.through, symmetric: !!spec.symmetric, flip: !!spec.flip,
          ...(spec.up_to ? { upto: { name: faceOf(spec.up_to).name, fp: faceOf(spec.up_to).centroid }, offset: spec.offset || 0 } : {}),
          ...(spec.upto_next && !spec.up_to ? { upto_next: true } : {}), ...(spec.d2 && !spec.symmetric ? { d2: +spec.d2 } : {}), ...(+spec.draft ? { draft: +spec.draft } : {}) }
        : { ...base, sketch: sk, op: spec.op === 'cut' ? 'cut' : 'add', axis: spec.axis || 'y', angle: spec.angle ?? 360 };
    }
    if (type === 'fillet' || type === 'chamfer') {
      let edges = (spec.edges || []).map((e) => (e.ref || e));
      if (!edges.length || edges.some((e) => !e.a || !e.b || !e.fp)) throw new Error('edges: edge refs {a, b, fp} from find_refs.');
      if (spec.chain !== false && !spec.keepEdges) { // ⛓ as a click in the panel: each edge with its tangent chain
        const all = [];
        for (const e of edges) {
          const [i] = m.refEdges([e]);
          for (const x of i === undefined ? [e] : m.chainOf(i, {}).map((j) => m.edgeRef(j) || e)) if (!all.some((y) => m.sameRef(x, y))) all.push(x);
        }
        edges = all;
      }
      return { ...base, edges, ...(type === 'fillet' ? { r: spec.r ?? 1 } : { d: spec.d ?? 1 }), ...(spec.chain === false ? { chain: false } : {}) };
    }
    if (type === 'hole') {
      const headOf = (x, d) => { // ⌴ / ⌵ room for a screw head (sized from the hole — a thread's nominal Ø, M3: 3 — unless given)
        if (!x.head) return {};
        if (!['cbore', 'csk'].includes(x.head)) throw new Error('head: "cbore" (a counterbore) or "csk" (a countersink).');
        return { head: x.head, head_d: x.head_d ?? +(d * (x.head === 'cbore' ? 1.8 : 2)).toFixed(1), ...(x.head === 'cbore' ? { head_depth: x.head_depth ?? +(+d).toFixed(1) } : { ...(x.head_angle ? { head_angle: x.head_angle } : {}) }) };
      };
      if (!spec.face) throw new Error('face: the name of the flat face the holes go into (find_refs).');
      const thrSize = typeof spec.thread === 'string' ? spec.thread : spec.thread?.standard; // (thread: "M5", true, {standard, kind} or false)
      if (thrSize && !/^M(2|2\.5|3|4|5|6|8|10|12|16|20)$/.test(thrSize)) throw new Error('thread: M2, M2.5, M3, M4, M5, M6, M8, M10, M12, M16 or M20.');
      const plane = planeOf({ face: spec.face, origin: spec.origin });
      const W = plane.origin === 'world' && !spec.uv ? worldToUV(plane.frame) : null; // (spec.uv: the stored places, an edit)
      const points = (spec.points || [[0, 0]]).map((p) => (W ? W.uv(p) : p));
      // its properties, each on its own (shape, thread, standard — or the old hole_type): its sizes from the table, a size
      // given wins (not a threaded hole's drill); none of them (d, thread "M5", head given as such): as given
      const OLD = { simple: 1, clearance: 1, counterbore: 1, countersink: 1, tapped: 1, d_flat: 1 };
      if (spec.hole_type && !OLD[spec.hole_type]) throw new Error('hole_type: "clearance", "counterbore", "countersink", "tapped", "d_flat" or "simple" — or give shape, thread and standard.');
      if (spec.shape && !HOLE_SHAPES.some(([v]) => v === spec.shape)) throw new Error('shape: "plain", "counterbore", "countersink" or "d_flat".');
      const props = spec.shape || spec.hole_type || spec.standard || typeof spec.thread === 'boolean' || (spec.thread && typeof spec.thread === 'object');
      const hs = props ? holeSpec({ ...spec, ...(spec.thread === true ? { thread: spec.standard || 'M5' } : {}), ...(!spec.shape && !spec.hole_type ? { shape: spec.head === 'cbore' ? 'counterbore' : spec.head === 'csk' ? 'countersink' : 'plain' } : {}) }) : null;
      const dh = hs?.shape === 'd_flat'; // (a D hole: its Ø and the size across its flat, no screw size)
      if (dh && (spec.thread || spec.head)) throw new Error('A D hole (shape "d_flat") has no thread or head — give d and flat.');
      if (hs && !dh && !hs.standard && (hs.threaded || hs.shape !== 'plain')) throw new Error(`standard: the screw's size — ${Object.keys(HOLE_SIZES).join(', ')}.`);
      const std = hs && !dh && hs.standard && presetFor(hs.shape, hs.threaded, hs.standard);
      if (hs && !dh && hs.standard && !std) throw new Error(`standard: the screw's size — ${Object.keys(HOLE_SIZES).join(', ')}.`);
      const kindOf = spec.thread?.kind; // (🔩 cosmetic / real: how the part's threads show)
      if (kindOf && ['cosmetic', 'real'].includes(kindOf)) m.part.threads = kindOf;
      const sizes = dh ? { shape: 'd_flat', d: spec.d ?? 5, flat: spec.flat ?? dFlat(spec.d ?? 5), ...(+spec.flat_angle ? { flat_angle: +spec.flat_angle } : {}) }
        : std ? { shape: hs.shape, standard: hs.standard, ...std, ...(spec.d && !hs.threaded ? { d: spec.d } : {}),
          ...(std.head && spec.head_d ? { head_d: spec.head_d } : {}), ...(std.head === 'cbore' && spec.head_depth ? { head_depth: spec.head_depth } : {}) }
          : hs ? { shape: 'plain', d: spec.d ?? 5 }
            : { d: spec.d ?? 5, ...(spec.thread ? { thread: spec.thread } : {}), ...headOf(spec, spec.thread ? parseFloat(spec.thread.slice(1)) : spec.d ?? 5) };
      return { ...base, plane, points, ...sizes,
        through: spec.through !== false, depth: spec.depth ?? 10, ...(spec.from ? { from: holeFrom(spec.from) } : {}), ...(fitOf(spec.fit) ? { fit: fitOf(spec.fit) } : {}),
        ...(spec.teardrop ? { teardrop: true } : {}), ...(holeLock(spec.lock, points.length) ? { lock: holeLock(spec.lock, points.length) } : {}) };
    }
    if (type === 'rib') {
      const sk = spec.sketch || [...m.sketches()].pop()?.id;
      if (!m.part.features.some((f) => f.id === sk && f.type === 'sketch')) throw new Error('sketch: the id of the sketch with the rib\'s line (from get_model).');
      return { ...base, sketch: sk, t: spec.t ?? 3, ...(spec.flip ? { flip: true } : {}) };
    }
    if (type === 'shell') {
      const faces = (spec.faces || []).map((n) => { const f = faceOf(typeof n === 'string' ? n : n.name); return { name: f.name, fp: f.centroid }; });
      return { ...base, faces, t: spec.t ?? 2 };
    }
    if (type === 'decal') {
      if (!spec.face) throw new Error('face: the name of the flat face it goes on (find_refs).');
      if (!spec.text) throw new Error('text: what to write (a picture is chosen by the user in the app).');
      return (async () => {
        const o = await textOutline(spec.text, { bold: spec.bold !== false });
        if (!o) throw new Error('That text draws nothing.');
        return { ...base, source: 'text', text: spec.text, polys: o.polygons, aspect: +o.aspect.toFixed(6), h: spec.h ?? 8, depth: spec.depth ?? 1,
          op: spec.op === 'cut' ? 'cut' : 'add', plane: planeOf({ face: spec.face }), at: spec.at || [0, 0], ...(spec.angle ? { angle: +spec.angle } : {}) };
      })();
    }
    if (type === 'mirror') {
      const of = spec.of || 'body';
      if (of !== 'body' && !m.part.features.some((g) => g.id === of)) throw new Error('of: "body" (the whole part) or the id of a step to mirror.');
      const pd = typeof spec.plane === 'object' && spec.plane ? spec.plane.datum : spec.plane; // a name, or the step's own plane (an edit)
      const plane = spec.face ? planeOf({ face: spec.face }) : { datum: ['XY', 'XZ', 'YZ'].includes(pd) ? pd : 'YZ' };
      return { ...base, of, plane, copy: of !== 'body' || spec.copy !== false };
    }
    if (type === 'split') { // ✂ cut in two along a plane: both pieces (two bodies) or one side
      const keep = spec.keep || 'both';
      if (!['both', 'above', 'below'].includes(keep)) throw new Error('keep: "both" (two bodies), "above" (the side the plane\'s normal points to) or "below".');
      let pl = spec.plane;
      if (pl && typeof pl === 'object' && pl.face && typeof pl.face === 'object') { // the step's own plane (an edit): by its faces' names
        const moved = spec.face && spec.face !== pl.face.name;
        pl = { face: moved ? spec.face : pl.face.name, ...(pl.mid && !moved ? { mid: pl.mid.name } : {}), offset: pl.offset };
      } else if (!pl && spec.face) pl = { face: spec.face };
      const off = +(spec.offset ?? (typeof pl === 'object' ? pl?.offset : 0) ?? 0) || 0;
      const plane = planeOf(pl && typeof pl === 'object' ? { ...pl, offset: pl.datum ? off : 0 } : pl || 'XY');
      if (off) plane.offset = off; else delete plane.offset;
      return { ...base, plane, keep };
    }
    if (type === 'draft') {
      if (!m.part.features.some((g) => g.id === spec.of && g.type === 'extrude')) throw new Error('of: the id of an extrude step (its side walls are tilted).');
      const a = +spec.angle;
      if (!Number.isFinite(a) || !a || Math.abs(a) >= 45) throw new Error('angle: degrees, 0 … 45 (negative: the walls lean out).');
      return { ...base, of: spec.of, angle: a };
    }
    if (type === 'point') { // a reference point: a corner (the one nearest a place), a round edge's centre, an edge's middle
      const at = spec.at && typeof spec.at === 'object' ? spec.at : {};
      if (at.vertex?.faces?.length || (Array.isArray(at.xyz) && at.xyz.length === 3)) return { ...base, at: at.vertex ? { vertex: at.vertex } : { xyz: at.xyz.map(Number) } };
      const e = at.centre || at.center || at.mid;
      if (e) {
        if (!e.a || !e.b || !e.fp) throw new Error('at: {centre: <a round edge ref {a, b, fp} from find_refs>} or {mid: <an edge ref>}.');
        return { ...base, at: { [at.mid ? 'mid' : 'centre']: { a: e.a, b: e.b, fp: e.fp } } };
      }
      const near = Array.isArray(at.corner) ? at.corner : Array.isArray(spec.at) ? spec.at : null;
      if (near) {
        const c = corners().sort((p, q) => len(sub(p.corner, near)) - len(sub(q.corner, near)))[0];
        if (!c) throw new Error('The model has no corners yet.');
        return { ...base, at: c.ref };
      }
      throw new Error('at: {corner: [x, y, z]} (the corner nearest it), {centre: <a round edge ref from find_refs>}, {mid: <an edge ref>} or a ref from find_refs kind "point".');
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
    if (type === 'solid') { // ▣ a solid from a file: the server read `path` into the blob store (server.py _solid_from_path)
      if (!spec.blob) throw new Error('path: the STEP / IGES / STL / OBJ / 3MF file on disk.');
      const op = ['add', 'cut', 'ref'].includes(spec.op) ? spec.op : (body() ? 'ref' : 'add');
      if (op === 'cut' && !body()) throw new Error('There is nothing to cut it out of yet — make the part first, or op "ref".');
      return { ...base, name: spec.name || String(spec.file || 'solid').replace(/\.[^.]+$/, ''), blob: spec.blob, file: spec.file || 'solid', op };
    }
    throw new Error('type is sketch, extrude, revolve, fillet, chamfer, hole, shell, pattern, loft, sweep, decal, mirror, draft, rib, point, split or solid.');
  };

  /** The part's corners, each with a ready ref for a point step: [{corner: [x, y, z], ref: {vertex: {faces, fp}}}]. */
  const corners = () => {
    const out = [], seen = new Set();
    for (const e of body()?.edges || []) {
      if (e.faces.length < 2) continue;
      for (const k of [0, e.pts.length - 3]) {
        const p = [e.pts[k], e.pts[k + 1], e.pts[k + 2]], key = p.map((v) => v.toFixed(4)).join(',');
        if (seen.has(key)) continue;
        seen.add(key);
        const ref = m.pointRef({ x: p[0], y: p[1], z: p[2] }, 'corner');
        if (ref) out.push({ corner: p.map(r3), ref });
      }
    }
    return out;
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

    duplicate_part: async ({ id, name }) => {
      const p = project.parts.find((q) => q.id === (id || project.active) || q.name === id);
      if (!p) throw new Error(`No part “${id}” — see list_parts.`);
      const nid = await project.duplicate(p.id, true);
      if (name) project.parts.find((q) => q.id === nid).name = name;
      project.render();
      await settle();
      return { text: `New part “${project.current?.name}” (${nid}), a copy of ${p.name}, on screen.` };
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
        if (m.part.features.indexOf(f) >= m.barAt()) out.rolled_back = true; // (under the rollback bar)
        if (f.type === 'sketch') {
          out.plane = f.plane?.datum || f.plane?.face?.name;
          out.shapes = (f.entities || []).map((e) => e.t).reduce((a, t) => ({ ...a, [t]: (a[t] || 0) + 1 }), {});
          out.locked_sizes = (f.dims || []).filter((d) => !d.free).length;
          const of = (f.entities || []).filter((e) => e.t === 'outline').map((e) => e.face?.name); // (⬆ a face's outline: which face)
          if (of.length) out.outline_of = of;
          const pj = (f.constraints || []).filter((k) => k.t === 'proj'); // (⇱ shapes taken from the part's faces / edges)
          if (pj.length) out.taken_from = pj.map((k) => (k.face ? { face: k.face.name, shapes: (k.ents || []).length } : { edges: (k.edges || []).length, shapes: (k.ents || []).length }));
        }
        if (f.expr) out.expressions = f.expr; // (𝑥 numbers set by the project's parameters)
        if (f.type === 'extrude') Object.assign(out, { sketch: f.sketch, op: f.op, d: f.d, through: !!f.through, symmetric: !!f.symmetric, ...(f.draft ? { draft: f.draft } : {}) });
        if (f.type === 'revolve') Object.assign(out, { sketch: f.sketch, op: f.op, axis: f.axis, angle: f.angle });
        if (f.type === 'fillet') Object.assign(out, { r: f.r, edges: f.edges.length, ...(f.chain === false ? { chain: false } : {}) });
        if (f.type === 'chamfer') Object.assign(out, { d: f.d, edges: f.edges.length, ...(f.chain === false ? { chain: false } : {}) });
        if (f.plane?.origin) out.origin = f.plane.origin;
        const W = f.type === 'hole' && f.plane?.origin === 'world' ? worldToUV(f.plane.frame) : null; // (as given: world X / Y)
        if (f.type === 'hole') Object.assign(out, { face: f.plane?.face?.name, ...(f.shape || f.hole_type ? { shape: holeSpec(f).shape, standard: holeSpec(f).standard || undefined } : {}), ...(holeSpec(f).shape === 'd_flat' ? { flat: f.flat, ...(f.flat_angle ? { flat_angle: f.flat_angle } : {}) } : {}), d: f.d, ...(f.thread ? { thread: f.thread } : {}), points: W ? f.points.map(([u, v]) => [u, W.flip ? -v : v]) : f.points, through: f.through !== false, depth: f.depth, ...(f.fit ? { fit: f.fit } : {}),
          ...(f.head ? { head: f.head, head_d: f.head_d, ...(f.head_depth ? { head_depth: f.head_depth } : {}), ...(f.head_angle ? { head_angle: f.head_angle } : {}) } : {}), ...(f.teardrop ? { teardrop: true } : {}),
          ...(f.from?.some(Boolean) ? { from: fromInfo(f.from) } : {}), ...(f.lock ? { lock: f.lock } : {}) });
        if (f.type === 'shell') Object.assign(out, { t: f.t, open_faces: f.faces.map((x) => x.name) });
        if (f.type === 'loft') Object.assign(out, { sketches: f.sketches, op: f.op });
        if (f.type === 'sweep') Object.assign(out, { profile: f.profile, path: f.path, op: f.op });
        if (f.type === 'solid') Object.assign(out, { file: f.file, op: f.op || 'add', bbox: st.bbox });
        if (f.type === 'pattern') Object.assign(out, { of: f.features, kind: f.kind, count: f.count, ...(f.kind === 'circular' ? { axis: f.axis } : { dir: f.dir, spacing: f.spacing }) });
        if (f.type === 'point') Object.assign(out, { on: Object.keys(f.at || {})[0], xyz: m.result?.points?.[f.id] || null });
        return out;
      });
      const n = m.barAt(), fs = m.part.features;
      const rollback = n < fs.length ? { after: fs[n - 1].id, name: fs[n - 1].name, rolled_back: fs.slice(n).map((f) => f.id),
        note: 'The view, body and new steps are as after this step (new steps go in under it); exports, the print copy, assemblies and drawings are the part as the bar stands too. rollback {to: "end"} brings them back.' } : undefined;
      return { text: JSON.stringify({ name: project.current?.name, unit: 'mm', steps, ...(rollback ? { rollback } : {}), body: summary() }) };
    },

    rollback: async ({ to } = {}) => {
      needModel();
      ready();
      await settle();
      if (to === undefined || to === null || to === '') throw new Error('to: a step id (the bar goes under it) or "end".');
      await m.setRollback(String(to));
      await settle();
      const n = m.barAt(), fs = m.part.features;
      return { text: JSON.stringify(n < fs.length ? { rolled_back_after: fs[n - 1].id, built: fs.slice(0, n).map((f) => f.id), rolled_back: fs.slice(n).map((f) => f.id), body: summary() }
        : { rollback: 'end — every step built', body: summary() }) };
    },

    find_refs: async ({ kind = 'face', name, normal, extreme, near, of_face, of_step, between_steps, circular, limit = 12 }) => {
      needModel();
      await settle();
      const b = body(), rfs = (m.result?.refs || []).flatMap((r) => (r.faces || []).map((f) => ({ ...f, refSolid: r.id }))); // (👁 reference solids' faces: ref true)
      if (!b && !(kind === 'face' && rfs.length)) throw new Error('The model has no solid yet.');
      const namesOf = (f) => (f?.names?.length ? f.names : f?.name ? [f.name] : []);
      const ofStep = (f, id) => namesOf(f).some((n) => n.split(':')[0] === id); // (a face the step made, e.g. F10:side:l2)
      for (const id of [of_step, ...(between_steps || [])].filter(Boolean)) {
        if (!m.part.features.some((g) => g.id === id)) throw new Error(`No step ${id} — get_model lists the steps.`);
      }
      if (between_steps && (!Array.isArray(between_steps) || between_steps.length !== 2)) throw new Error('between_steps: two step ids, e.g. ["F2", "F10"].');
      if (kind === 'face') {
        let fs = [...(b?.faces || []), ...rfs].filter((f) => f.name);
        if (name) fs = fs.filter((f) => namesOf(f).some((n) => n.includes(name)));
        if (of_step) fs = fs.filter((f) => ofStep(f, of_step));
        if (normal) { const n = normal.map(Number), L = len(n) || 1; fs = fs.filter((f) => f.normal && dot(f.normal, n) / L > 0.999); }
        if (extreme && fs.length) {
          const dir = normal || [0, 0, 1], L = len(dir) || 1;
          const key = (f) => dot(f.centroid, dir) / L;
          const best = extreme === 'min' ? Math.min(...fs.map(key)) : Math.max(...fs.map(key));
          fs = fs.filter((f) => Math.abs(key(f) - best) < 1e-6 * (1 + Math.abs(best)));
        }
        if (near) fs.sort((a, c) => len(sub(a.centroid, near)) - len(sub(c.centroid, near)));
        else fs.sort((a, c) => c.area - a.area);
        return { text: JSON.stringify(fs.slice(0, limit).map((f) => ({ name: f.name, ...(namesOf(f).length > 1 ? { names: namesOf(f) } : {}), type: f.type, normal: f.normal, centroid: f.centroid, area: r3(f.area), radius: f.radius, ...(f.refSolid ? { ref: true } : {}) }))) };
      }
      if (kind === 'edge') {
        let es = b.edges.map((e, i) => ({ e, i })).filter(({ e }) => e.faces.length === 2);
        if (of_face) {
          const ids = b.faces.filter((f) => f.name === of_face).map((f) => f.id);
          es = es.filter(({ e }) => e.faces.some((k) => ids.includes(k)));
        }
        if (of_step) es = es.filter(({ e }) => e.faces.some((k) => ofStep(b.faces[k], of_step))); // (all the step's edges: to round them at once)
        if (between_steps) { // (where the two steps meet: a rib on its plate)
          const [s1, s2] = between_steps;
          es = es.filter(({ e }) => { const [fa, fb] = e.faces.map((k) => b.faces[k]); const only = (f, x, y) => ofStep(f, x) && !ofStep(f, y); return (only(fa, s1, s2) && only(fb, s2, s1)) || (only(fa, s2, s1) && only(fb, s1, s2)); }); // (a face flush with both: not a joint)
        }
        const info = es.map(({ e }) => {
          const [fa, fb] = e.faces.map((k) => b.faces[k]?.name);
          let L = 0;
          for (let k = 3; k < e.pts.length; k += 3) L += Math.hypot(e.pts[k] - e.pts[k - 3], e.pts[k + 1] - e.pts[k - 2], e.pts[k + 2] - e.pts[k - 1]);
          const c = circleOf(e.pts);
          const run = e.chain === undefined ? 0 : b.edges.filter((x) => x.chain === e.chain).length; // (⛓ the edges a fillet of it takes)
          return { ref: { a: fa, b: fb, fp: e.mid }, between: [fa, fb], mid: e.mid, length: r3(L), ...(c ? { circle: c } : {}), ...(run ? { chain: run } : {}) };
        }).filter((x) => x.ref.a && x.ref.b && (circular === undefined || !!x.circle === !!circular));
        if (near) info.sort((a, c) => len(sub(a.mid, near)) - len(sub(c.mid, near)));
        return { text: JSON.stringify(info.slice(0, limit)) };
      }
      if (kind === 'point') { // the reference points (point steps), then the part's corners with a ready ref for add_feature point
        const at = m.result?.points || {};
        const ps = m.part.features.filter((f) => f.type === 'point' && at[f.id]).map((f) => ({ point: f.id, name: f.name, xyz: at[f.id] }));
        let cs = corners();
        if (of_face) {
          const want = b.faces.filter((f) => namesOf(f).includes(of_face)).map((f) => f.name);
          cs = cs.filter((c) => c.ref.vertex.faces.some((n) => want.includes(n)));
        }
        if (of_step) cs = cs.filter((c) => c.ref.vertex.faces.some((n) => n.split(':')[0] === of_step));
        const all = [...ps, ...cs];
        if (near) all.sort((p, q) => len(sub(p.xyz || p.corner, near)) - len(sub(q.xyz || q.corner, near)));
        return { text: JSON.stringify(all.slice(0, limit)) };
      }
      if (kind === 'axis') { // the round faces' axes (shafts, holes, bosses): a ref for a sketch shape's / a hole's from
        let fs = b.faces.filter((f) => f.name && f.axis && !/:(round|bevel):/.test(f.name));
        if (name) fs = fs.filter((f) => namesOf(f).some((n) => n.includes(name)));
        if (of_step) fs = fs.filter((f) => ofStep(f, of_step));
        const seen = new Set();
        fs = fs.filter((f) => !seen.has(f.name) && seen.add(f.name)); // (a round face in two halves: once)
        if (near) fs.sort((a, c) => len(sub(a.centroid, near)) - len(sub(c.centroid, near)));
        else fs.sort((a, c) => c.area - a.area);
        return { text: JSON.stringify(fs.slice(0, limit).map((f) => ({ axis: f.name, radius: f.radius, through: f.axis.o.map(r3), direction: f.axis.d.map(r3), centroid: f.centroid }))) };
      }
      throw new Error('kind is "face", "edge", "point" or "axis".');
    },

    add_feature: async (spec) => {
      needModel();
      ready();
      await settle();
      let sk = null;
      if (spec.type === 'extrude' && spec.face && !spec.sketch) { // ⬆ a face extruded: its outline sketch first, as the GUI's Extrude this face
        const g = faceOf(spec.face);
        if (g.type !== 'plane') throw new Error(`The face “${spec.face}” is not flat — only a flat face can be extruded.`);
        sk = m.faceSketch(g);
        m.insertSteps(sk); // (at the rollback bar, when it is up)
        spec = { ...spec, sketch: sk.id, flip: false };
      }
      let f, ex;
      const rb = m.part.rollback;
      try {
        ex = exprArgs(spec, EXPR_KEYS);
        f = await build(ex.args);
      } catch (e) { if (sk) { m.part.features = m.part.features.filter((g) => g !== sk); if (rb) m.part.rollback = rb; } throw e; }
      keepExprs(f, ex);
      m.insertSteps(f); // (at the rollback bar, when it is up)
      return commitAnd(f.id);
    },

    edit_feature: async ({ id, fields = {}, ...rest }) => {
      needModel();
      const stray = Object.keys(rest);
      if (stray.length) throw new Error(`edit_feature takes id and fields — put the changes in fields: {${stray.map((k) => `${k}: …`).join(', ')}}.`);
      if (!fields || typeof fields !== 'object' || Array.isArray(fields)) throw new Error('fields: an object of the changes, e.g. {d: 15}.');
      ready();
      const f = m.part.features.find((x) => x.id === id);
      if (!f) throw new Error(`No step ${id} — see get_model.`);
      const ex = exprArgs(fields, EXPR_KEYS); // (𝑥 "L / 2": its value in, the expression kept below)
      fields = ex.args;
      if (f.type === 'sketch' && (fields.shapes || fields.plane)) {
        if (fields.shapes) { // (a new plane alone keeps the shapes)
          for (const k of ['place', 'rd', 'hidden']) delete f[k]; // (they named the old shapes' ids — new shapes reuse them)
          Object.assign(f, sketchFromShapes(fields.shapes, fields.lock !== false, axisAtOn(f.plane)));
        }
        if (fields.plane || fields.origin) { // (a new origin alone: the shapes keep their numbers, from the new 0, 0)
          const pl = typeof fields.plane === 'string' ? { datum: fields.plane } : fields.plane || (f.plane?.face ? { face: f.plane.face.name, ...(f.plane.mid ? { mid: f.plane.mid.name } : {}) } : { ...f.plane });
          f.plane = planeOf(fields.origin && !pl.datum ? { ...pl, origin: fields.origin } : pl);
        }
      } else {
        // a hole's new type / size: its sizes from the table again (those given in fields kept), a simple hole keeps its Ø
        // a hole's new shape / thread / size (or the old hole_type): its properties as they were, the given ones changed
        const restd = f.type === 'hole' && ['hole_type', 'standard', 'shape', 'thread'].some((k) => k in fields);
        const OLD = { simple: ['plain', false], clearance: ['plain', false], counterbore: ['counterbore', false], countersink: ['countersink', false], tapped: ['plain', true], d_flat: ['d_flat', false] };
        const cur = holeSpec(f), old = OLD[fields.hole_type];
        const shape = fields.shape || old?.[0] || cur.shape, threaded = 'thread' in fields ? !!fields.thread : old ? old[1] : cur.threaded;
        const size = fields.standard || (typeof fields.thread === 'string' ? fields.thread : fields.thread?.standard) || (fields.hole_type === 'simple' ? null : cur.standard);
        const simple = shape === 'plain' && !threaded && !size;
        const drop = restd ? ['thread', 'head', 'head_d', 'head_depth', 'head_angle', 'hole_type', 'standard', 'shape', ...(simple || shape === 'd_flat' ? [] : ['d']), ...(shape === 'd_flat' ? [] : ['flat', 'flat_angle'])] : [];
        const was = Object.fromEntries(Object.entries(f).filter(([k]) => !drop.includes(k)));
        if (holeSpec(f).shape === 'd_flat' && 'd' in fields && !('flat' in fields) && f.flat === dFlat(f.d)) delete was.flat; // (the default flat follows the Ø)
        if (restd) Object.assign(was, { shape, ...(size ? { standard: size } : {}), thread: threaded && fields.thread?.kind ? { standard: size, kind: fields.thread.kind } : threaded });
        if (restd) { fields = { ...fields }; delete fields.hole_type; delete fields.thread; if ('shape' in fields) delete fields.shape; if (!fields.standard) delete fields.standard; }
        const next = build({ ...was, ...fields, keepEdges: !('edges' in fields), type: f.type, origin: 'origin' in fields ? fields.origin : f.plane?.origin, uv: !fields.points, of: fields.of || f.features, name: fields.name || f.name, face: fields.face || f.plane?.face?.name, faces: fields.faces || f.faces?.map((x) => x.name), sketch: fields.sketch || f.sketch });
        // on the same face from the same origin: the stored frame stays (picked again, the face's centre may have moved —
        // holes cut into it since — and the step with it)
        const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
        if (next.plane?.face && f.plane?.frame && next.plane.face.name === f.plane.face?.name && same(next.plane.mid?.name, f.plane.mid?.name) && same(next.plane.origin, f.plane.origin)) {
          next.plane = { ...next.plane, frame: f.plane.frame };
        }
        for (const k of drop) delete f[k];
        Object.assign(f, { ...next, id: f.id, name: fields.name || f.name });
        if ('fit' in fields && !fields.fit) delete f.fit; // (a hole's fit taken off)
        if ('thread' in fields && !fields.thread) delete f.thread; // (its thread taken off)
        if ('head' in fields && !fields.head) for (const k of ['head', 'head_d', 'head_depth', 'head_angle']) delete f[k]; // (its head taken off)
        if ('teardrop' in fields && !fields.teardrop) delete f.teardrop; // (round again)
        if ('chain' in fields && fields.chain !== false) delete f.chain; // (⛓ on again: the default)
        if (f.type === 'hole' && !next.lock) delete f.lock; // (🔒 taken off — or its positions gone)
        if (f.type === 'extrude') { // up to next / up to a face / a distance: one at a time; d2 off (or symmetric on): no other side
          if (!next.upto_next) delete f.upto_next;
          if (fields.upto_next || ('up_to' in fields && !fields.up_to)) delete f.upto;
          if (!next.d2) delete f.d2;
          if (!next.draft) delete f.draft; // (draft 0: straight walls again)
        }
        if (f.type === 'rib' && !next.flip) delete f.flip; // (flip: false — its own side again)
        keepExprs(f, ex);
      }
      return commitAnd(id);
    },

    delete_feature: async ({ id, keep_dependents = true }) => {
      needModel();
      ready();
      if (!m.part.features.some((x) => x.id === id)) throw new Error(`No step ${id}.`);
      const before = m.part.features.length;
      // the AI was asked to: steps that only stand on it stay where they are (or go too), steps that need it go
      await m.remove(id, keep_dependents === false ? 'all' : 'keep');
      await settle();
      return { text: `Deleted ${before - m.part.features.length} step(s). ${JSON.stringify({ steps: m.part.features.map((x) => x.id), body: summary() })}` };
    },

    simplify_sketch: async ({ id, op = 'simplify', tol }) => {
      needModel();
      ready();
      const f = m.part.features.find((x) => x.id === id);
      if (!f || f.type !== 'sketch') throw new Error(`No sketch step ${id} — see get_model.`);
      if (!['simplify', 'join', 'outline'].includes(op)) throw new Error('op: simplify, join or outline.');
      const ids = op === 'simplify' ? null : (f.entities || []).filter((e) => !e.construction).map((e) => e.id); // (join / outline: all of it)
      const res = await fetch('/api/model/sketch/clean', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ op, ids, tol, sketch: { points: f.points, entities: f.entities, constraints: f.constraints, dims: f.dims } }) });
      const j = await res.json();
      if (!res.ok || j.error) throw new Error(j.error || res.statusText);
      Object.assign(f, j.sketch);
      const r = JSON.parse((await commitAnd(id)).text), rep = j.report;
      return { text: JSON.stringify({ ...r, shapes: { before: rep.before.entities, after: rep.after.entities }, points: { before: rep.before.points, after: rep.after.points },
        area_mm2: { before: rep.area[0], after: rep.area[1] }, tol: rep.tol, dropped_sizes_relations: rep.dropped, issues: rep.issues }) };
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

    check_print: async ({ min_wall = 1.2, overhang = 45 } = {}) => {
      needModel();
      await settle();
      if (!body()) throw new Error('The model has no solid yet.');
      const r = m.view.printCheck({ minWall: +min_wall, overhang: +overhang }); // (marked on screen too, until the part changes)
      return { text: JSON.stringify({ as_it_lies: 'on the bed at its lowest z', overhang_over_deg: +overhang, overhang_mm2: r.overhang.area, overhang_box: r.overhang.box,
        min_wall_mm: +min_wall, thin_mm2: r.thin.area, thin_box: r.thin.box, thinnest_mm: r.thin.min, ok: !r.overhang.area && !r.thin.area }) };
    },

    set_material: async ({ material, tolerance }) => {
      needModel();
      if (material) m.setMaterial(MATERIAL_NAME[String(material).toLowerCase()] || String(material));
      if (tolerance !== undefined) {
        if (tolerance && !['f', 'm', 'c'].includes(tolerance)) throw new Error('tolerance: "f", "m" or "c" (ISO 2768), or null for none.');
        if (tolerance) m.part.tolerance = tolerance; else delete m.part.tolerance;
        m.history.commit();
      }
      return { text: JSON.stringify(summary()) };
    },

    prepare_print: async () => {
      needModel();
      await settle();
      if (!body()) throw new Error('The model has no solid yet.');
      const rolled = m.rolledBack() && m.part.rollback; // (⏮ the copy is the part as its rollback bar stands)
      await m.toPrint();
      return { text: `A printing copy is open as a quick part on the 3D print tab — use check_print (and export) on it now.${rolled ? ` Rolled back: it is the part as after step ${rolled} (the print tab says so to the user); rollback {to: "end"} on the model and prepare_print again for every step.` : ''}` };
    },

    // the model versions of shared tools
    model_screenshot: async ({ view, fit = true, highlight }) => {
      needModel();
      await settle();
      if (view) m.view.setView({ front: 'front', back: 'back', side: 'right', top: 'top' }[view] || 'iso'); // (back: the front's mirror image)
      // highlight: face names or step ids (all the faces it made) -> lit in orange; the hover, picks and chosen step are not
      const want = (Array.isArray(highlight) ? highlight : highlight ? [highlight] : []).map(String);
      const named = (f, n) => [f.name, ...(f.names || [])].some((q) => q === n || q?.startsWith(`${n}:`));
      const lit = (body()?.faces || []).filter((f) => want.some((n) => named(f, n)));
      const missing = want.filter((n) => !lit.some((f) => named(f, n)));
      if (missing.length) throw new Error(`highlight: no face named ${missing.map((n) => `“${n}”`).join(', ')} — find_refs lists face names; a step's id lights all its faces.`);
      await nextFrames();
      const c = m.view.snapshot({ fit: fit !== false, faces: lit.map((f) => f.id), over: drawLabels });
      // lit faces seen edge-on or behind the part from this side: the picture is the plain one — said, not left to guess
      const unseen = lit.length && changedPixels(c, m.view.snapshot({ fit: fit !== false, over: drawLabels })) < 40; // (a few: a rim's antialiasing)
      const said = lit.length ? ` Lit in orange: ${[...new Set(lit.map((f) => f.name))].slice(0, 12).join(', ')}${lit.length > 12 ? ' …' : ''}.${unseen
        ? ' None of them shows from this side (seen edge-on or hidden behind the part) — try another view (iso, back, side).' : ''}` : '';
      return { text: `3D view (${view || 'current'}), ${c.width} × ${c.height} px (gui_action / gui_highlight at = [x, y] are its pixels).${said} ${JSON.stringify(summary())}`, image: c.toDataURL('image/png').split(',')[1] };
    },
    model_body: async () => { needModel(); return { text: 'ok', body: { model_part: m.payload(), name: project.current?.name } }; },
    model_undo: async () => { needModel(); const ok = await m.history.go(-1); await settle(); return { text: ok ? `Undone. ${JSON.stringify(summary())}` : 'Nothing to undo.' }; },
    ...sketchHandlers({ modeler: m, needModel, settle }), // (get_sketch, sketch_auto_dims, sketch_dim, sketch_trim, sketch_union)
  };
}

/** How many pixels of two canvases of one size differ clearly (get_screenshot: did the highlight light anything?). */
function changedPixels(a, b) {
  if (a.width !== b.width || a.height !== b.height) return Infinity;
  const p = a.getContext('2d').getImageData(0, 0, a.width, a.height).data, q = b.getContext('2d').getImageData(0, 0, b.width, b.height).data;
  let n = 0;
  for (let i = 0; i < p.length; i += 4) if (Math.abs(p[i] - q[i]) + Math.abs(p[i + 1] - q[i + 1]) + Math.abs(p[i + 2] - q[i + 2]) > 48) n++;
  return n;
}
