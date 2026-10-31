// The 3D view of the model workspace: the body from the CAD kernel (one face id per triangle, so faces can
// be highlighted and picked), its edges, the three base planes (Top / Front / Right) and, in sketch mode,
// the sketch plane with a grid, the sketch shapes and their editable sizes.
import { paintedFaces } from './paint.js';
import * as THREE from 'three';
import { FreeControls } from '../freecontrols.js';
import { finishOf } from './materials.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { t } from '../i18n.js';
import { snapKinds } from '../suggest.js';
import { ViewCube } from './viewcube.js';
import { accelerate } from './bvh.js';
import { capGeometry } from './sectioncap.js';

const BODY = new THREE.Color(0xd9dee6), HOVER = new THREE.Color(0x6cb6ff), PICKED = new THREE.Color(0x4f8cff);
const FEATURE = new THREE.Color(0xa9cdf5), SELECTED = new THREE.Color(0xf2cc60); // the step under the mouse / the chosen step
const CAP = new THREE.Color(0xc0604a); // ✂ the section's cut faces (a brick red: not a face of the part, not a pick)
const MARK = new THREE.Color(0xff7b54); // faces the AI asked to see lit in its picture (get_screenshot highlight)
const SHADES = [new THREE.Color(0x9ec5ef), new THREE.Color(0xf0b77a)]; // ✂ Split's preview: one shade per body
const DATUM_COLORS = { XY: 0x4f8cff, XZ: 0x7ee787, YZ: 0xffa657 };
export const DATUMS = {
  XY: { o: [0, 0, 0], x: [1, 0, 0], n: [0, 0, 1] },
  XZ: { o: [0, 0, 0], x: [1, 0, 0], n: [0, -1, 0] },
  YZ: { o: [0, 0, 0], x: [0, 1, 0], n: [1, 0, 0] },
};

/** A base plane {datum, offset} -> its frame (moved offset mm along its normal). */
export function datumFrame(plane) {
  const fr = DATUMS[plane?.datum] || DATUMS.XY, off = +plane?.offset || 0;
  return { ...fr, o: fr.o.map((v, i) => v + off * fr.n[i]) };
}

/** The snap points of edges: an edge's ends (corner), its middle (midpoint), a round edge's centre (centre) —
 *  matrix: where the part is placed; kinds: the snap filters -> [{point, kind, r?}] (r: a centre's / quadrant's ring radius). */
export function snapPoints(edges, matrix = null, kinds = null) {
  const key = `${matrix ? matrix.elements.join() : ''}|${kinds ? Object.entries(kinds).map(([k, v]) => (v ? k : '')).join() : '*'}`;
  const memo = edges && memoOf(SNAPS, edges), had = memo?.get(key);
  if (had) return had.map((q) => ({ ...q, point: q.point.clone() }));
  const pts = pointsOf(edges, matrix, kinds);
  if (memo) keep(memo, key, pts.map((q) => ({ ...q, point: q.point.clone() })));
  return pts;
}
const SNAPS = new WeakMap(); // edge list -> key -> pts (hovering asks for the same points again and again)

/** A memo's map for an edge list — one per place the list is drawn at: the parts placed many times share their part's
 *  edges (500 screws of four kinds), so one record per list was made again for every placed part on every hover. */
function memoOf(memos, edges) {
  let m = memos.get(edges);
  if (!m) memos.set(edges, (m = new Map()));
  return m;
}
const keep = (memo, key, v) => { if (memo.size >= 1024) memo.clear(); memo.set(key, v); return v; };

function pointsOf(edges, matrix, kinds) {
  const out = [], push = (point, kind, r) => { if (!kinds || kinds[kind]) out.push(r ? { point, kind, r } : { point, kind }); };
  for (const e of edges || []) {
    const n = e.pts.length;
    if (n < 6) continue;
    const P = (k) => { const p = new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]); return matrix ? p.applyMatrix4(matrix) : p; };
    const closed = Math.hypot(e.pts[0] - e.pts[n - 3], e.pts[1] - e.pts[n - 2], e.pts[2] - e.pts[n - 1]) < 1e-6;
    if (closed) { // a round edge (a hole's rim, a pin's end): its centre
      const c = new THREE.Vector3();
      for (let k = 0; k < n - 3; k += 3) c.add(new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]));
      c.multiplyScalar(3 / (n - 3));
      const r0 = Math.hypot(e.pts[0] - c.x, e.pts[1] - c.y, e.pts[2] - c.z); // (its radius: how big the ring is on the screen says whether its points are taken)
      if (!kinds || kinds.quadrant) { // its four quadrant points: along the world axis lying best in its plane, and across
        const a = new THREE.Vector3(e.pts[0], e.pts[1], e.pts[2]).sub(c), b = new THREE.Vector3(e.pts[3 * Math.floor((n / 3 - 1) / 4)], e.pts[3 * Math.floor((n / 3 - 1) / 4) + 1], e.pts[3 * Math.floor((n / 3 - 1) / 4) + 2]).sub(c);
        const nn = a.clone().cross(b).normalize(), rad = a.length();
        if (nn.lengthSq() > 0.5 && rad > 0) {
          const ax = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)].sort((p, q) => Math.abs(p.dot(nn)) - Math.abs(q.dot(nn)))[0];
          const u = ax.clone().addScaledVector(nn, -ax.dot(nn)).normalize().multiplyScalar(rad), w = nn.clone().cross(u);
          for (const d of [u, w, u.clone().negate(), w.clone().negate()]) { const q = c.clone().add(d); out.push({ point: matrix ? q.applyMatrix4(matrix) : q, kind: 'quadrant', r: rad }); }
        }
      }
      push(matrix ? c.applyMatrix4(matrix) : c, 'centre', r0);
      continue;
    }
    if (e.faces.length < 2) continue; // a seam on a round face: not a real edge
    push(P(0), 'corner');
    push(P(n - 3), 'corner');
    let L = 0; // its middle: half its length along it
    for (let k = 3; k < n; k += 3) L += Math.hypot(e.pts[k] - e.pts[k - 3], e.pts[k + 1] - e.pts[k - 2], e.pts[k + 2] - e.pts[k - 1]);
    for (let k = 3, s = 0; k < n; k += 3) {
      const l = Math.hypot(e.pts[k] - e.pts[k - 3], e.pts[k + 1] - e.pts[k - 2], e.pts[k + 2] - e.pts[k - 1]);
      if (s + l >= L / 2 && l > 0) { push(P(k - 3).lerp(P(k), (L / 2 - s) / l), 'midpoint'); break; }
      s += l;
    }
  }
  return out;
}

/** The measure tool's snap points near the mouse (within px on the screen): an edge's end (corner), the middle of an
 *  edge (midpoint), the centre of a round edge (centre) — list: [{edges, matrix?, inst?}] -> {point, kind, inst} or null.
 *  seen(point): only points it says are in sight (not hidden behind a surface) are taken. */
export function snapNear(list, camera, rect, clientX, clientY, px = 10, kinds = null, seen = null) {
  let best = null, bd = px;
  const cam = camKey(camera, rect);
  for (const { edges, matrix, inst } of list) {
    // the points on the screen, kept while the camera, the part and the filters stay (the mouse moves over a still view)
    const mk = `${matrix ? matrix.elements.join() : ''}|${kinds ? Object.entries(kinds).map(([k, v]) => (v ? k : '')).join() : '*'}`, key = `${cam}|${mk}`;
    const memos = edges && memoOf(SNAP_SCREEN, edges);
    let memo = memos?.get(mk);
    if (memo?.key !== key) {
      const pts = snapPoints(edges, matrix, kinds), scr = new Float64Array(pts.length * 3), q = new THREE.Vector3();
      pts.forEach(({ point: p }, k) => {
        q.copy(p).project(camera);
        scr[k * 3] = rect.left + (q.x + 1) / 2 * rect.width;
        scr[k * 3 + 1] = rect.top + (1 - q.y) / 2 * rect.height;
        scr[k * 3 + 2] = q.z;
      });
      memo = { key, pts, scr };
      if (memos) keep(memos, mk, memo);
    }
    const { pts, scr } = memo;
    for (let k = 0; k < pts.length; k++) {
      if (scr[k * 3 + 2] > 1) continue; // (behind the camera)
      const d = Math.hypot(scr[k * 3] - clientX, scr[k * 3 + 1] - clientY);
      if (d < bd && (!seen || seen(pts[k].point))) { bd = d; best = { point: pts[k].point.clone(), kind: pts[k].kind, inst, ...(pts[k].r ? { r: pts[k].r } : {}) }; }
    }
  }
  return best;
}
const SNAP_SCREEN = new WeakMap(); // edge list -> its placement and filters -> {key, pts, scr: x, y, z on the screen per point}

/** How big (px, its radius) the ring a centre / quadrant s ({point, r}) belongs to looks on the screen; Infinity for
 *  another snap point. A small ring's points are neither shown nor taken: its few px would be all snap points, and a
 *  click there means its round face. */
export function ringPx(s, camera, rect) {
  if (!s?.r) return Infinity;
  camera.updateMatrixWorld();
  const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1).normalize().multiplyScalar(s.r);
  const a = s.point.clone().project(camera), b = s.point.clone().add(up).project(camera);
  return Math.hypot((b.x - a.x) / 2 * rect.width, (b.y - a.y) / 2 * rect.height);
}

/** The camera as it looks now (its place, its lens) and the canvas: a key that changes when anything moves on screen. */
export function camKey(camera, rect) {
  camera.updateMatrixWorld();
  return `${camera.matrixWorld.elements.join()}|${camera.projectionMatrix.elements.join()}|${rect.left},${rect.top},${rect.width},${rect.height}`;
}

/** A soft studio for reflections (metal looks like metal): a light sky, a darker floor, a few bright panels round. */
const STUDIO = new WeakMap(); // (one per renderer: a WebGL texture belongs to its own context)
function studio(renderer) {
  if (STUDIO.has(renderer)) return STUDIO.get(renderer);
  const room = new THREE.Scene(), geo = new THREE.SphereGeometry(10, 32, 16), col = [];
  const pos = geo.getAttribute('position');
  for (let i = 0; i < pos.count; i++) { // sky to floor
    const k = (pos.getZ(i) / 10 + 1) / 2, c = new THREE.Color(0x2a2f36).lerp(new THREE.Color(0xdfe6ee), k);
    col.push(c.r, c.g, c.b);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  room.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
  for (const [x, y, z, w, h] of [[0, -8, 5, 9, 4], [7, 4, 6, 4, 7], [-8, 2, 3, 3, 6], [0, 0, 9.5, 8, 8]]) { // soft boxes
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }));
    panel.position.set(x, y, z);
    panel.lookAt(0, 0, 0);
    room.add(panel);
  }
  const pmrem = new THREE.PMREMGenerator(renderer);
  const tex = pmrem.fromScene(room, 0.03).texture;
  pmrem.dispose();
  STUDIO.set(renderer, tex);
  return tex;
}

const b64 = (s, T) => { // (a binary answer's arrays come as typed arrays already: modeler/packed.js)
  if (typeof s !== 'string') return s;
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};
const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const EDGE_SCREEN = new WeakMap(); // edge list -> its points on the screen (ModelView.edgesOnScreen)

/** A plane frame {o, x, n} -> three vectors (origin, x, y, normal). */
export function axes(fr) {
  const o = V(fr.o), x = V(fr.x).normalize(), n = V(fr.n).normalize();
  return { o, x, y: new THREE.Vector3().crossVectors(n, x), n };
}

/** 🔩 Cosmetic threads as line segments [x0, y0, z0, x1, …]: on each threaded hole's wall (a hair inside it, so the
 *  wall does not hide it) a right-hand helix at the thread's pitch, 24 pieces a turn, and a ring at its major Ø a hair
 *  above the face it goes in from. holes: the kernel's thread_holes [{at, axis, depth, major, minor, pitch}]. */
export function threadSegments(holes) {
  const out = [];
  for (const h of holes || []) {
    const a = V(h.axis).normalize(), o = V(h.at);
    const u = new THREE.Vector3(Math.abs(a.x) < 0.9 ? 1 : 0, Math.abs(a.x) < 0.9 ? 0 : 1, 0).cross(a).normalize(), v = a.clone().cross(u);
    const at = (r, ang, z) => o.clone().addScaledVector(u, r * Math.cos(ang)).addScaledVector(v, r * Math.sin(ang)).addScaledVector(a, z);
    const line = (n, p) => { let q = p(0); for (let i = 1; i <= n; i++) { const w = p(i / n); out.push(q.x, q.y, q.z, w.x, w.y, w.z); q = w; } };
    line(Math.max(1, Math.round((h.depth / h.pitch) * 24)), (k) => at((h.minor / 2) * 0.995, (2 * Math.PI * k * h.depth) / h.pitch, k * h.depth));
    line(48, (k) => at(h.major / 2, 2 * Math.PI * k, -0.01));
  }
  return out;
}

export class ModelView {
  /** cube: the view cube in the top-right corner (the 3D model, the assembly). */
  constructor(container, { cube = false } = {}) {
    this.container = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);
    this.labels = new CSS2DRenderer();
    Object.assign(this.labels.domElement.style, { position: 'absolute', inset: '0', pointerEvents: 'none' });
    container.appendChild(this.labels.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(80, -160, 120);
    this.controls = new FreeControls(this.camera, this.renderer.domElement); // turns without limits (over the top too)
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.3));
    this.scene.environment = studio(this.renderer); // (what metal reflects: a soft studio)
    const key = new THREE.DirectionalLight(0xffffff, 1.7);
    key.position.set(1, -1.5, 2.5);
    this.camera.add(key); // light follows the camera: every face stays readable
    this.scene.add(this.camera);
    const fill = new THREE.DirectionalLight(0xffffff, 0.5);
    fill.position.set(-2, 1, -1);
    this.scene.add(fill);

    this.bodyGroup = new THREE.Group();
    this.datumGroup = new THREE.Group();
    this.sketchGroup = new THREE.Group();
    this.sketchHiGroup = new THREE.Group(); // what a sketch size under the mouse measures (drawn apart: its labels stay)
    this.outlineGroup = new THREE.Group(); // sketches shown as lines outside sketch mode
    this.edgeGroup = new THREE.Group();    // highlighted edges (Fillet / Chamfer)
    this.tagGroup = new THREE.Group();     // the chosen step's sizes, as labels on the part
    this.scene.add(this.bodyGroup, this.datumGroup, this.sketchGroup, this.sketchHiGroup, this.outlineGroup, this.edgeGroup, this.tagGroup);
    this.material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.05, side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    this.edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1b2430 });
    this.threadMaterial = new THREE.LineBasicMaterial({ color: 0x4a5566 }); // 🔩 cosmetic threads: thin, quieter than the edges
    this.body = null;
    this.size = 100;
    this.hover = -1;
    this.picked = new Set();

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.dirty = true;
    this.controls.addEventListener('change', () => { this.dirty = true; this.onCamera?.(); });
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
      if (!this.dirty || this.held) return; // (held: the AI's click aimed through its picture's camera — not drawn)
      this.dirty = false;
      this.updatePlaneArrow(); // (end-on or from the side: the camera may have turned)
      this.updateCaps();
      this.renderer.render(this.scene, this.camera);
      this.paintedAll = false; // (the colours are on the GPU now)
      this.labels.render(this.scene, this.camera);
      this.cube?.update(this.camera);
    };
    loop();
    this.showDatums(true);
    // the origin, always: short x / y / z arrows (drawn over the part)
    this.origin = new THREE.AxesHelper(1);
    this.origin.material.depthTest = false;
    this.origin.renderOrder = 11;
    this.scene.add(this.origin);
    this.sizeOrigin();
    if (cube) this.cube = new ViewCube(container, (dir) => this.setView(dir));
  }

  sizeOrigin() {
    const k = Math.max(this.size * 0.12, 0.2); // small parts (an SMD part of 1.6 mm) too
    this.origin.scale.set(k, k, k);
    this.invalidate();
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.labels.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  invalidate() { this.dirty = true; }

  clear(g) {
    for (const o of [...g.children]) {
      g.remove(o);
      o.traverse?.((c) => { c.geometry?.dispose?.(); if (c.isCSS2DObject) c.element.remove(); });
    }
  }

  // ------------------------------------------------------------------ the body
  setBody(body) {
    this.clear(this.bodyGroup);
    this.body = body;
    this.hover = -1;
    this.picked.clear();
    if (!body) { this.mesh = null; this.invalidate(); return; }
    const pos = b64(body.positions, Float32Array);
    this.faceIds = b64(body.face_ids, Uint32Array);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(pos.length), 3));
    geo.computeVertexNormals();
    this.mesh = accelerate(new THREE.Mesh(geo, this.material));
    this.faceTris = null;
    this.bodyGroup.add(this.mesh);
    const seg = [];
    for (const { pts: pl } of body.edges) for (let i = 0; i + 5 < pl.length; i += 3) seg.push(pl[i], pl[i + 1], pl[i + 2], pl[i + 3], pl[i + 4], pl[i + 5]);
    const eg = new THREE.BufferGeometry();
    eg.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
    this.bodyGroup.add(new THREE.LineSegments(eg, this.edgeMaterial));
    const [x0, y0, z0, x1, y1, z1] = body.bbox;
    this.size = Math.max(x1 - x0, y1 - y0, z1 - z0, 1);
    this.sizeOrigin();
    this.paint();
  }

  /** 🖨 Print check of the part as it lies on the bed (its lowest z): faces hanging over more than `overhang`° from
   *  upright (facing down, not on the bed) and walls thinner than `minWall` mm (a ray in from each face meets the other
   *  side sooner) — marked red / orange over the part; null takes the marks off. -> {overhang: {area, box}, thin:
   *  {area, box, min}} (mm², [x0 … z1] round them). */
  printCheck(opts) {
    if (this.printMarks) { this.scene.remove(this.printMarks); this.printMarks.geometry.dispose(); this.printMarks = null; }
    if (!opts || !this.mesh || !this.body) { this.invalidate(); return null; }
    const { minWall = 1.2, overhang = 45 } = opts, pos = this.mesh.geometry.attributes.position.array, n = pos.length / 9, z0 = this.body.bbox[2];
    const lim = -Math.cos((90 - overhang) * Math.PI / 180) - 1e-4; // (a face's normal more downward than this: it hangs over; a face at just 45°, a teardrop's side, does not)
    const side = new THREE.Mesh(this.mesh.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })), ray = new THREE.Raycaster();
    const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3(), N = new THREE.Vector3(), M = new THREE.Vector3();
    const res = { overhang: { area: 0, box: null }, thin: { area: 0, box: null, min: null } }, out = [], col = [];
    const grow = (r, p) => { r.box = r.box ? [Math.min(r.box[0], p.x), Math.min(r.box[1], p.y), Math.min(r.box[2], p.z), Math.max(r.box[3], p.x), Math.max(r.box[4], p.y), Math.max(r.box[5], p.z)] : [p.x, p.y, p.z, p.x, p.y, p.z]; };
    const step = Math.max(1, Math.ceil(n / 4000)); // (a big mesh: every k-th face for the walls)
    for (let i = 0; i < n; i++) {
      A.fromArray(pos, 9 * i); B.fromArray(pos, 9 * i + 3); C.fromArray(pos, 9 * i + 6);
      N.subVectors(B, A).cross(M.subVectors(C, A));
      const area = N.length() / 2;
      if (area < 1e-9) continue;
      N.normalize();
      let kind = null;
      const onBed = Math.max(A.z, B.z, C.z) - z0 < 1e-3;
      if (N.z < lim && !onBed) kind = 'overhang';
      else if (i % step === 0) {
        M.copy(A).add(B).add(C).multiplyScalar(1 / 3);
        ray.set(M.clone().addScaledVector(N, -1e-3), N.clone().negate());
        ray.far = minWall;
        const hit = ray.intersectObject(side, false).find((h) => h.distance > 1e-3);
        if (hit) { kind = 'thin'; res.thin.min = Math.min(res.thin.min ?? Infinity, hit.distance + 1e-3); }
      }
      if (!kind) continue;
      res[kind].area += area * (kind === 'thin' ? step : 1);
      for (const p of [A, B, C]) { grow(res[kind], p); out.push(p.x + N.x * 0.02, p.y + N.y * 0.02, p.z + N.z * 0.02); col.push(...(kind === 'overhang' ? [0.97, 0.32, 0.29] : [1, 0.62, 0.1])); }
    }
    if (out.length) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(out, 3));
      g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      this.printMarks = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2 }));
      this.scene.add(this.printMarks);
    }
    const r1 = (v) => Math.round(v * 10) / 10;
    for (const k of ['overhang', 'thin']) { res[k].area = r1(res[k].area); if (res[k].box) res[k].box = res[k].box.map(r1); }
    if (res.thin.min !== null) res.thin.min = Math.round(res.thin.min * 100) / 100;
    this.invalidate();
    return res;
  }

  /** The rest of an assembly around a part edited in place: [{positions (base64), matrix (16, in the part's frame)}],
   *  grey and see-through, not picked. */
  setContext(list = []) {
    if (!this.ctxGroup) { this.ctxGroup = new THREE.Group(); this.scene.add(this.ctxGroup); }
    this.clear(this.ctxGroup);
    for (const c of list) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(b64(c.positions, Float32Array), 3));
      geo.computeVertexNormals();
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x8b95a3, transparent: true, opacity: 0.25, depthWrite: false, side: THREE.DoubleSide }));
      mesh.matrixAutoUpdate = false;
      mesh.matrix.fromArray(c.matrix);
      this.ctxGroup.add(mesh);
    }
    this.invalidate();
  }

  /** 🔩 Cosmetic threads (view only — the solid is not changed): thread_holes' helix and ring lines; null: none. */
  setThreads(holes) {
    if (!this.threadGroup) { this.threadGroup = new THREE.Group(); this.scene.add(this.threadGroup); }
    this.clear(this.threadGroup);
    const seg = threadSegments(holes);
    this.threadCount = seg.length ? holes.length : 0; // (how many holes show a thread)
    if (seg.length) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
      this.threadGroup.add(new THREE.LineSegments(g, this.threadMaterial));
    }
    this.invalidate();
  }

  /** Reference solids: shown see-through (not part of the part): [{id, positions (base64), face_ids, faces}]. Their
   *  faces can be picked (pick's refs: a sketch on a bought part's face, its outline taken into a sketch). */
  setRefs(list = []) {
    if (!this.refGroup) { this.refGroup = new THREE.Group(); this.scene.add(this.refGroup); }
    this.clear(this.refGroup);
    for (const r of list) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(b64(r.positions, Float32Array), 3));
      geo.computeVertexNormals();
      // drawn through the part (a cover built around it hides it otherwise)
      const mesh = accelerate(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x58a6ff, transparent: true, opacity: 0.35, depthWrite: false, depthTest: false, side: THREE.DoubleSide })));
      mesh.renderOrder = 4;
      mesh.userData.ref = { id: r.id, faces: r.faces || [], faceIds: r.face_ids ? b64(r.face_ids, Uint32Array) : null };
      this.refGroup.add(mesh);
    }
    this.invalidate();
  }

  /** A face of a reference solid by its name (its frame for a sketch on it), or null. */
  refFace(name) {
    for (const m of this.refGroup?.children || []) {
      const f = m.userData.ref?.faces.find((x) => x.name === name || (x.names || []).includes(name));
      if (f) return { ...f, refSolid: m.userData.ref.id };
    }
    return null;
  }

  /** How far a face reaches along a frame's x and y, from the frame's origin: [u0, u1, v0, v1] (null: no such face). */
  faceSpan(name, fr) {
    if (!this.mesh || !this.body || !name) return null;
    const ids = new Set(this.body.faces.filter((f) => f.name === name || (f.names || []).includes(name)).map((f) => f.id));
    const pos = this.mesh.geometry.attributes.position.array, [o, x, n] = [fr.o, fr.x, fr.n];
    const y = [n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0]], s = [Infinity, -Infinity, Infinity, -Infinity];
    for (let t = 0; t < this.faceIds.length; t++) {
      if (!ids.has(this.faceIds[t])) continue;
      for (let k = t * 9; k < t * 9 + 9; k += 3) {
        const d = [pos[k] - o[0], pos[k + 1] - o[1], pos[k + 2] - o[2]];
        const u = d[0] * x[0] + d[1] * x[1] + d[2] * x[2], v = d[0] * y[0] + d[1] * y[1] + d[2] * y[2];
        s[0] = Math.min(s[0], u); s[1] = Math.max(s[1], u); s[2] = Math.min(s[2], v); s[3] = Math.max(s[3], v);
      }
    }
    return s[0] === Infinity ? null : s;
  }

  /** The part's look: its colour ("#rrggbb", none = the usual grey) and opacity (1 = solid, less = see-through). */
  setLook({ color, opacity, paint, material } = {}) {
    this.bodyColor = color ? new THREE.Color(color) : null;
    Object.assign(this.material, finishOf(material), { envMapIntensity: finishOf(material).metalness > 0.5 ? 1 : 0.35 }); // (metal: metallic)
    // faces painted on their own (paint.js)
    this.faceColor = new Map([...paintedFaces(this.body?.faces || [], paint)].map(([id, p]) => [id, new THREE.Color(p.color)]));
    // the colours an imported STEP file brought (under the faces painted here)
    this.fileColor = new Map((this.body?.faces || []).filter((f) => f.color).map((f) => [f.id, new THREE.Color(f.color)]));
    const o = Number.isFinite(+opacity) ? Math.min(1, Math.max(0.1, +opacity)) : 1;
    Object.assign(this.material, { transparent: o < 1, opacity: o, depthWrite: o >= 1 });
    this.material.needsUpdate = true;
    this.paint();
  }

  /** A face's colour now: under the mouse, picked, of the hovered step, of the chosen step, painted … */
  colorOf(f) {
    return this.markSet?.has(f) ? MARK : f === this.hover ? HOVER : this.picked.has(f) ? PICKED : this.hoverSet?.has(f) ? FEATURE : this.selSet?.has(f) ? SELECTED
      : this.shades ? SHADES[(this.body.faces[f]?.solid || 0) % SHADES.length]
        : this.faceColor?.get(f) || this.fileColor?.get(f) || this.bodyColor || BODY;
  }

  paint() {
    if (!this.mesh) return;
    const col = this.mesh.geometry.attributes.color;
    for (let t = 0; t < this.faceIds.length; t++) {
      const c = this.colorOf(this.faceIds[t]);
      for (let k = 0; k < 3; k++) col.setXYZ(t * 3 + k, c.r, c.g, c.b);
    }
    col.clearUpdateRanges();
    col.needsUpdate = true;
    this.paintedAll = true; // (all of it goes to the GPU with the next frame)
    this.invalidate();
  }

  /** Only these faces painted again (a hover: a few faces of a part of a million triangles) — and only their
   *  triangles sent to the GPU. */
  repaint(faces) {
    if (!this.mesh) return;
    if (!this.faceTris) { // face id -> its triangles (counted, then listed: start[f] … start[f + 1])
      const n = this.body.faces.reduce((m, f) => Math.max(m, f.id + 1), 0), start = new Uint32Array(n + 2), tris = new Uint32Array(this.faceIds.length);
      for (const f of this.faceIds) start[Math.min(f, n) + 1]++;
      for (let i = 1; i < start.length; i++) start[i] += start[i - 1];
      const at = start.slice();
      this.faceIds.forEach((f, t) => { tris[at[Math.min(f, n)]++] = t; });
      this.faceTris = { start, tris, n };
    }
    const { start, tris, n } = this.faceTris, col = this.mesh.geometry.attributes.color, runs = [];
    for (const f of faces) {
      if (!(f >= 0 && f < n)) continue;
      const c = this.colorOf(f);
      for (let i = start[f]; i < start[f + 1]; i++) {
        const t = tris[i];
        for (let k = 0; k < 3; k++) col.setXYZ(t * 3 + k, c.r, c.g, c.b);
        const last = runs[runs.length - 1];
        if (last && last[1] === t) last[1] = t + 1; else runs.push([t, t + 1]);
      }
    }
    if (!runs.length) return;
    if (!this.paintedAll) { // (a whole repaint not sent yet: it sends all anyway)
      if (runs.length > 64) { const lo = Math.min(...runs.map((x) => x[0])), hi = Math.max(...runs.map((x) => x[1])); runs.length = 0; runs.push([lo, hi]); }
      for (const [a, b] of runs) col.addUpdateRange(a * 9, (b - a) * 9);
    }
    col.needsUpdate = true;
    this.invalidate();
  }

  /** ✂ Split's preview: each body (solid) of the part in a shade of its own — on / off. */
  setShades(on) {
    if (!!this.shades === !!on) return;
    this.shades = !!on;
    this.paint();
  }

  /** Sketch mode: the part see-through, so the sketch, the grid and dimensions show even behind it. */
  setGhost(on) {
    this.ghost = on;
    Object.assign(this.material, { transparent: on, opacity: on ? 0.28 : 1, depthWrite: !on });
    this.material.needsUpdate = true;
    this.edgeMaterial.transparent = on;
    this.edgeMaterial.opacity = on ? 0.45 : 1;
    this.invalidate();
  }

  /** faceId: the face under the mouse; also: the faces of its whole step (lighter). */
  setHover(faceId, also = null) {
    const was = this.hoverAlso || [], now = also || [], same = also === this.hoverFrom || (was.length === now.length && now.every((f, i) => f === was[i]));
    if (faceId === this.hover && same) return;
    const changed = new Set([this.hover, faceId]); // (only the faces whose colour may change: a big step's other faces stay)
    if (!same) {
      const set = also ? new Set(also) : null;
      for (const f of was) if (!set?.has(f)) changed.add(f);
      for (const f of now) if (!this.hoverSet?.has(f)) changed.add(f);
      this.hoverSet = set;
      this.hoverAlso = also ? [...also] : null;
    }
    this.hoverFrom = also; // (the same list again: the same faces, not compared one by one)
    this.hover = faceId;
    this.repaint(changed);
  }

  /** Labels on the part: [{p: [x, y, z], el}] and thin lines [[a, b]] (from the label to what it measures). */
  setTags(tags = [], lines = []) {
    this.clear(this.tagGroup);
    for (const t of tags) {
      t.el.style.pointerEvents = 'auto';
      const o = new CSS2DObject(t.el);
      o.position.set(...t.p);
      this.tagGroup.add(o);
    }
    if (lines.length) {
      const pts = lines.flatMap(([a, b]) => [new THREE.Vector3(...a), new THREE.Vector3(...b)]);
      const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xd2a8ff, depthTest: false, transparent: true }));
      l.renderOrder = 7;
      this.tagGroup.add(l);
    }
    this.invalidate();
  }

  /** The faces of the chosen step, tinted (until something else is chosen). */
  setSelectedFaces(ids) {
    this.selSet = ids?.length ? new Set(ids) : null;
    this.paint();
  }

  face(id) { return (this.body?.faces[id]?.id === id ? this.body.faces[id] : this.body?.faces.find((f) => f.id === id)) || null; }

  // ------------------------------------------------------------------ base planes
  showDatums(on, size) {
    this.clear(this.datumGroup);
    this.datumGroup.visible = on;
    if (!on) { this.invalidate(); return; }
    const s = size || Math.max(this.size * 0.8, 60);
    for (const [name, fr] of Object.entries(DATUMS)) {
      const { o, x, y, n } = axes(fr);
      const m = new THREE.Mesh(new THREE.PlaneGeometry(s, s), new THREE.MeshBasicMaterial({
        color: DATUM_COLORS[name], transparent: true, opacity: 0.035, side: THREE.DoubleSide, depthWrite: false })); // (faint: they stay out of the way)
      m.matrix.makeBasis(x, y, n).setPosition(o.clone().addScaledVector(x, s / 2).addScaledVector(y, s / 2));
      m.matrixAutoUpdate = false;
      m.userData.datum = name;
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), new THREE.LineBasicMaterial({ color: DATUM_COLORS[name], transparent: true, opacity: 0.22 }));
      edge.matrix.copy(m.matrix);
      edge.matrixAutoUpdate = false;
      this.datumGroup.add(m, edge);
      const el = document.createElement('div');
      el.className = 'datum-label';
      el.textContent = { XY: 'Top', XZ: 'Front', YZ: 'Right' }[name];
      const lab = new CSS2DObject(el);
      lab.position.copy(o).addScaledVector(x, s * 0.92).addScaledVector(y, s * 0.92);
      this.datumGroup.add(lab);
    }
    this.invalidate();
  }

  highlightDatum(name) {
    for (const m of this.datumGroup.children) if (m.userData.datum) m.material.opacity = m.userData.datum === name ? 0.2 : 0.035;
    this.invalidate();
  }

  // ------------------------------------------------------------------ picking
  ray(clientX, clientY) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    return ray;
  }

  /** What is under the mouse: {face} (a face of the body) or {datum} (a base plane), or null. refs: a face of a 👁
   *  reference solid too, when it is nearer (the face marked refSolid: the solid step's id; not one of the body's). */
  pick(clientX, clientY, { datums = false, refs = false } = {}) {
    const ray = this.ray(clientX, clientY);
    const h = this.mesh ? ray.intersectObject(this.mesh, false)[0] : null;
    const rh = refs && this.refGroup?.children.length ? ray.intersectObjects(this.refGroup.children, false).find((x) => x.object.userData.ref?.faceIds) : null;
    if (rh && (!h || rh.distance < h.distance)) {
      const u = rh.object.userData.ref, id = u.faceIds[rh.faceIndex], f = u.faces[id]?.id === id ? u.faces[id] : u.faces.find((x) => x.id === id);
      if (f) return { face: { ...f, refSolid: u.id }, point: rh.point };
    }
    if (h) return { face: this.face(this.faceIds[h.faceIndex]), point: h.point };
    if (datums && this.datumGroup.visible) {
      const h = ray.intersectObjects(this.datumGroup.children.filter((c) => c.userData.datum), false)[0];
      if (h) return { datum: h.object.userData.datum, point: h.point };
    }
    return null;
  }

  /** The mouse on a sketch plane -> sketch coordinates [u, v] (or null when looking along the plane). */
  planePoint(clientX, clientY, fr) {
    const { o, x, y, n } = axes(fr);
    const hit = new THREE.Vector3();
    if (!this.ray(clientX, clientY).ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(n, o), hit)) return null;
    hit.sub(o);
    return [hit.dot(x), hit.dot(y)];
  }

  /** How many mm one screen pixel is at the sketch origin. */
  mmPerPixel(fr) {
    const o = V(fr.o);
    const d = this.camera.position.distanceTo(o);
    const h = 2 * d * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    return h / this.renderer.domElement.clientHeight;
  }

  /** A point of a sketch (u, v on its frame) on the screen -> [x, y] (client pixels). */
  uvToScreen(fr, [u, v]) {
    const o = V(fr.o), x = V(fr.x), n = V(fr.n), y = new THREE.Vector3().crossVectors(n, x);
    return this.toScreen(o.addScaledVector(x, u).addScaledVector(y, v));
  }

  toScreen(p) {
    const v = p.clone().project(this.camera), r = this.renderer.domElement.getBoundingClientRect();
    return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height];
  }

  // ------------------------------------------------------------------ camera
  fitBox() {
    const box = new THREE.Box3();
    if (this.mesh) box.setFromObject(this.mesh);
    else if (!this.outlineGroup.children.length) box.setFromObject(this.datumGroup);
    if (this.outlineGroup.children.length) box.expandByObject(this.outlineGroup); // sketches not extruded yet too
    return box;
  }

  /** Look from a side ('iso', 'top', 'front', 'right', 'back', 'left', 'bottom') or from a direction [x, y, z] (the
   *  view cube's edges and corners), all of it fitted. Z stays up; the top is seen with +Y up, the bottom with -Y. */
  setView(name) {
    const box = this.fitBox(), c = box.getCenter(new THREE.Vector3()), s = Math.max(box.getSize(new THREE.Vector3()).length(), 1);
    const dirs = { iso: [0.55, -0.9, 0.7], top: [0, -0.0001, 1], front: [0, -1, 0.0001], right: [1, 0, 0.0001],
      back: [0, 1, 0.0001], left: [-1, 0, 0.0001], bottom: [0, 0.0001, -1] };
    const dir = V(Array.isArray(name) ? name : dirs[name] || dirs.iso).normalize();
    this.camera.up.set(0, 0, 1);
    if (name === 'top') this.camera.up.set(0, 1, 0);
    if (name === 'bottom') this.camera.up.set(0, -1, 0);
    this.camera.position.copy(c).addScaledVector(dir, s * 1.6);
    this.controls.target.copy(c);
    this.controls.update();
    this.invalidate();
  }

  /** All of it in the view, seen from where the camera looks now: the ball round its box inside the narrower of the
   *  view's two angles (a view narrower than high: farther, so the sides are in it too), a little room round it. */
  fit() {
    const box = this.fitBox(), c = box.getCenter(new THREE.Vector3()), s = Math.max(box.getSize(new THREE.Vector3()).length(), 1);
    const dir = this.camera.position.clone().sub(this.controls.target);
    if (dir.lengthSq() < 1e-12) dir.set(0.55, -0.9, 0.7);
    const half = Math.atan(Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) * Math.min(1, this.camera.aspect || 1));
    this.camera.position.copy(c).addScaledVector(dir.normalize(), (s / 2 / Math.sin(half)) * 1.05);
    this.controls.target.copy(c);
    this.controls.update();
    this.invalidate();
  }

  /** The camera as it is now: {position, quaternion, up, fov, zoom, aspect, near, far, target} (setCamera puts it back). */
  cameraState() {
    const c = this.camera;
    return { position: c.position.clone(), quaternion: c.quaternion.clone(), up: c.up.clone(), fov: c.fov, zoom: c.zoom,
      aspect: c.aspect, near: c.near, far: c.far, target: this.controls.target.clone() };
  }

  /** Put a camera from cameraState() on the view (its shape too: a picture's 4:3 on a wider view is stretched). */
  setCamera(s) {
    const c = this.camera;
    c.position.copy(s.position);
    c.quaternion.copy(s.quaternion);
    c.up.copy(s.up);
    Object.assign(c, { fov: s.fov, zoom: s.zoom, aspect: s.aspect, near: s.near, far: s.far });
    c.updateProjectionMatrix();
    c.updateMatrixWorld();
    this.controls.target.copy(s.target);
    this.invalidate();
  }

  /** A picture of the view for the AI, w × h px whatever the panel's shape (a chat beside it made it a narrow strip):
   *  fitted when asked, without the mouse's hover, the picks or the chosen step's tint — only `faces` (ids) lit in
   *  orange. over(ctx, layer) draws on it while the labels sit where this camera puts them (layer: their box on
   *  the page, w × h). The view on screen is put back as it was (fitted to its own shape when fit). -> a canvas. */
  snapshot({ w = 1200, h = 900, fit = true, faces = null, over = null, background = '#161b22' } = {}) {
    const { clientWidth: sw, clientHeight: sh } = this.container;
    const tint = [this.hover, this.hoverSet, this.picked, this.selSet, this.markSet];
    Object.assign(this, { hover: -1, hoverSet: null, picked: new Set(), selSet: null, markSet: faces?.length ? new Set(faces) : null });
    // an assembly's chosen / hovered part glows: not in the picture (a clash's red stays)
    const glow = (this.meshes || []).map((m) => [m.material, m.material.emissive?.getHex()]).filter(([, hex]) => hex !== undefined && hex !== 0x6a0d0d);
    for (const [mat] of glow) mat.emissive.setHex(0x000000);
    const marks = this.markGroup?.visible;
    if (this.markGroup) this.markGroup.visible = false;
    const own = !!this.faceIds; // (a part's faces are painted one by one; an assembly's parts are not)
    if (own) this.paint();
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    try {
      this.renderer.setSize(w, h, false);
      this.labels.setSize(w, h);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      if (fit) this.fit();
      this.updatePlaneArrow?.();
      this.updateCaps();
      this.renderer.render(this.scene, this.camera);
      this.labels.render(this.scene, this.camera);
      this.shot = { w, h, ...this.cameraState() }; // (the camera that drew it: a point of the picture is aimed through it)
      const ctx = c.getContext('2d');
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(this.renderer.domElement, 0, 0, w, h);
      over?.(ctx, this.labels.domElement.getBoundingClientRect());
    } finally {
      [this.hover, this.hoverSet, this.picked, this.selSet, this.markSet] = tint;
      for (const [mat, hex] of glow) mat.emissive.setHex(hex);
      if (this.markGroup) this.markGroup.visible = marks;
      if (own) this.paint();
      if (sw && sh) {
        this.renderer.setSize(sw, sh);
        this.labels.setSize(sw, sh);
        this.camera.aspect = sw / sh;
        this.camera.updateProjectionMatrix();
      }
      if (fit) this.fit();
      this.labels.render(this.scene, this.camera);
      this.invalidate();
    }
    return c;
  }

  /** Look straight at a sketch plane (its y axis up). */
  lookAt(fr, span) {
    const { o, y, n } = axes(fr);
    const s = Math.max(span || this.size * 1.6, 40);
    const target = o.clone(); // centred on the sketch origin (a face's centre, or the world origin)
    this.camera.up.copy(y);
    this.camera.position.copy(target).addScaledVector(n, s * 1.8);
    this.controls.target.copy(target);
    this.controls.update();
    this.invalidate();
  }

  // ------------------------------------------------------------------ sketch mode
  /** Draw a sketch on its plane: a grid, the origin, and what the sketcher hands over —
   *  lines [[a, b, colour, dashed?]], circles [[centre, r, colour]], dots [[p, colour]], labels [{el, u, v}]. */
  setSketch(fr, { lines = [], circles = [], dots = [], labels = [], grid = 1 } = {}) {
    this.clear(this.sketchGroup);
    this.invalidate();
    if (!fr) { this.clear(this.sketchHiGroup); return; }
    const { o, x, y, n } = axes(fr);
    const lift = this.size * 0.0005;
    const P = (u, v) => o.clone().addScaledVector(x, u).addScaledVector(y, v).addScaledVector(n, lift);
    const add = (o3) => { o3.renderOrder = 6; this.sketchGroup.add(o3); };
    if (!grid) grid = this.size / 60 || 1; // only lines and labels (no grid, no plane): dimensions on the part
    else this.drawSketchPlane(P, grid, x, y, n, lift);
    this.drawSketchItems(P, add, grid, { lines, circles, dots, labels });
  }

  /** Lines, circles and points lit up over the sketch, without drawing it again (its labels stay as they are). */
  setSketchHighlight(fr, { lines = [], circles = [], dots = [] } = {}) {
    this.clear(this.sketchHiGroup);
    this.invalidate();
    if (!fr) return;
    const { o, x, y, n } = axes(fr);
    const lift = this.size * 0.0007;
    const P = (u, v) => o.clone().addScaledVector(x, u).addScaledVector(y, v).addScaledVector(n, lift);
    this.drawSketchItems(P, (o3) => { o3.renderOrder = 7; this.sketchHiGroup.add(o3); }, 1, { lines, circles, dots, labels: [] });
  }

  drawSketchPlane(P, grid, x, y, n, lift) {
    const span = Math.max(this.size * 1.4, grid * 60);
    const half = Math.ceil(span / 2 / grid) * grid;
    const pts = [];
    for (let t = -half; t <= half + 1e-9; t += grid) pts.push(P(-half, t), P(half, t), P(t, -half), P(t, half));
    const gridLines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
      this.sketchMat('grid', () => new THREE.LineBasicMaterial({ color: 0x39d0d8, transparent: true, opacity: 0.09, depthWrite: false, depthTest: false })));
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(2 * half, 2 * half), this.sketchMat('plane', () => new THREE.MeshBasicMaterial({
      color: 0x1a2a3a, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false })));
    plane.matrix.makeBasis(x, y, n).setPosition(P(0, 0).addScaledVector(n, -lift * 0.6));
    plane.matrixAutoUpdate = false;
    const axesLines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([P(-half, 0), P(half, 0), P(0, -half), P(0, half)]),
      this.sketchMat('axes', () => new THREE.LineBasicMaterial({ color: 0x8b95a3, transparent: true, opacity: 0.45, depthTest: false })));
    this.sketchGroup.add(plane, gridLines, axesLines);
  }

  /** A sketch drawing's material, made once and kept (a sketch is drawn again at every hover: new materials each
   *  time cost the GPU set-up of each). */
  sketchMat(key, make) {
    if (!this.sketchMats) this.sketchMats = new Map();
    let m = this.sketchMats.get(key);
    if (!m) { m = make(); this.sketchMats.set(key, m); }
    return m;
  }

  drawSketchItems(P, add, grid, { lines, circles, dots, labels }) {
    // lines and circles of one colour (and dashing) drawn as one object (a sketch of 700 shapes: a few objects, not 700)
    const groups = new Map(), group = (color, dashed) => {
      const key = `${new THREE.Color(color).getHexString()}|${dashed ? `d${grid}` : ''}`;
      if (!groups.has(key)) groups.set(key, { color, dashed, pts: [] });
      return groups.get(key).pts;
    };
    for (const [a, b, color, dashed] of lines) group(color, dashed).push(P(a[0], a[1]), P(b[0], b[1]));
    for (const [c, r, color] of circles) {
      const ring = Array.from({ length: 97 }, (_, i) => { const a = (i / 96) * Math.PI * 2; return P(c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)); });
      const pts = group(color, false);
      for (let i = 0; i + 1 < ring.length; i++) pts.push(ring[i], ring[i + 1]);
    }
    for (const [key, { color, dashed, pts }] of groups) {
      const mat = this.sketchMat(`l${key}`, () => (dashed ? new THREE.LineDashedMaterial({ color, dashSize: grid * 0.6, gapSize: grid * 0.4, depthTest: false, transparent: true, opacity: 0.7 })
        : new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true })));
      const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat);
      if (dashed) l.computeLineDistances(); // (each piece dashed from its own start, as one line of its own)
      add(l);
    }
    if (dots.length) {
      const geo = new THREE.BufferGeometry().setFromPoints(dots.map(([p]) => P(p[0], p[1])));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(dots.flatMap(([, c]) => { const k = new THREE.Color(c); return [k.r, k.g, k.b]; }), 3));
      add(new THREE.Points(geo, this.sketchMat('dots', () => new THREE.PointsMaterial({ size: 7, sizeAttenuation: false, vertexColors: true, depthTest: false, transparent: true }))));
    }
    for (const l of labels) {
      if (l.el.classList.contains('edit')) l.el.style.pointerEvents = 'auto';
      const lab = new CSS2DObject(l.el);
      lab.position.copy(P(l.u, l.v));
      this.sketchGroup.add(lab);
    }
  }

  /** Sketches as lines in the 3D view (outside sketch mode): [{id, frame, lines: [[a, b]], circles: [[c, r]], dim}].
   *  A sketch used by an extrude is drawn faint (dim), one that is not extruded yet bright. */
  setOutlines(list) {
    this.clear(this.outlineGroup);
    this.invalidate();
    for (const sk of list) {
      const { o, x, y, n } = axes(sk.frame);
      const lift = this.size * 0.0008;
      const P = (u, v) => o.clone().addScaledVector(x, u).addScaledVector(y, v).addScaledVector(n, lift);
      const pts = [];
      for (const [a, b] of sk.lines) pts.push(P(a[0], a[1]), P(b[0], b[1]));
      for (const [c, r] of sk.circles) {
        for (let i = 0; i < 96; i++) {
          const a0 = (i / 96) * Math.PI * 2, a1 = ((i + 1) / 96) * Math.PI * 2;
          pts.push(P(c[0] + r * Math.cos(a0), c[1] + r * Math.sin(a0)), P(c[0] + r * Math.cos(a1), c[1] + r * Math.sin(a1)));
        }
      }
      if (!pts.length) continue;
      const seg = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({
        color: sk.sel ? 0xf2cc60 : sk.dim ? 0x5a8f9a : 0x39d0d8, transparent: true, opacity: sk.dim ? 0.55 : 1, depthTest: !!sk.dim && !sk.sel }));
      seg.renderOrder = 4;
      Object.assign(seg.userData, { sketch: sk.id, dim: !!sk.dim, sel: !!sk.sel });
      this.outlineGroup.add(seg);
    }
  }

  /** The sketch whose lines are under the mouse (within ~6 px), or null. Over a face of the part, the face comes first:
   *  a used sketch's faint lines (on it, or under it seen through) are not picked there, and the chosen sketch's
   *  only right on its line (~2 px); a sketch not extruded yet (bright, the next step) still is. */
  pickOutline(clientX, clientY) {
    const ray = this.ray(clientX, clientY), face = this.mesh && ray.intersectObject(this.mesh, false)[0];
    ray.params.Line = { threshold: this.size * 0.012 };
    for (const h of ray.intersectObjects(this.outlineGroup.children, false)) {
      const { sketch, dim, sel } = h.object.userData;
      if (!face) return sketch;
      if (dim) continue;
      if (!sel) return sketch;
      const near = this.ray(clientX, clientY);
      near.params.Line = { threshold: this.size * 0.004 };
      if (near.intersectObject(h.object, false).length) return sketch;
    }
    return null;
  }

  // ------------------------------------------------------------------ edges (Fillet / Chamfer)
  /** The edge of the body nearest to the mouse on screen (within maxPx), preferring the one nearer the
   *  camera when two are about as close; -1 when none. */
  pickEdge(clientX, clientY, maxPx = 9) {
    if (!this.body) return -1;
    return this.edgeAt([{ edges: this.body.edges }], clientX, clientY, maxPx, this.mesh ? [this.mesh] : [])?.i ?? -1;
  }

  /** The edge nearest to the mouse on screen among list [{edges, matrix?, inst?}] (within maxPx), preferring the one
   *  nearer the camera when two are about as close; one behind the surface of `solids` is not taken
   *  -> {edge, i, matrix, inst} or null. */
  edgeAt(list, clientX, clientY, maxPx = 9, solids = []) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const mx = clientX - r.left, my = clientY - r.top, v = new THREE.Vector3();
    // an edge hidden behind the part is not pickable: it must not be farther than the surface under the mouse
    const mray = this.ray(clientX, clientY), hit = solids.length ? mray.intersectObjects(solids, false)[0] : null;
    const q = new THREE.Vector3();
    const cam = this.camera.position, slack = this.size * 0.01, ck = camKey(this.camera, r);
    let best = null, bestD = maxPx, bestZ = Infinity;
    for (const { edges, matrix, inst } of list) {
      const W = (p, k) => { v.set(p[k], p[k + 1], p[k + 2]); return matrix ? v.applyMatrix4(matrix) : v; };
      const { scr, at, box } = this.edgesOnScreen(edges || [], matrix, ck, r);
      (edges || []).forEach((e, i) => {
        if (e.faces.length < 2) return; // a seam on a round face: not a real edge
        // (its points' box on the screen farther than maxPx from the mouse: no piece of it is nearer)
        if (mx < box[i * 4] - maxPx || mx > box[i * 4 + 2] + maxPx || my < box[i * 4 + 1] - maxPx || my > box[i * 4 + 3] + maxPx) return;
        const p = e.pts;
        for (let k = 3, j = at[i] + 3; k < p.length; k += 3, j += 3) {
          const px = scr[j - 3], py = scr[j - 2], pz = scr[j - 1];
          const dx = scr[j] - px, dy = scr[j + 1] - py, L = dx * dx + dy * dy || 1;
          const t = Math.max(0, Math.min(1, ((mx - px) * dx + (my - py) * dy) / L));
          const d = Math.hypot(px + t * dx - mx, py + t * dy - my), z = pz + t * (scr[j + 2] - pz);
          if (d < maxPx && hit) {
            // (the piece's point nearest the mouse ray — not the screen's t lerped in 3D, which a perspective view
            // shifts along an edge seen at a slant, far enough to call a visible edge hidden)
            const a = W(p, k - 3).clone();
            mray.ray.distanceSqToSegment(a, W(p, k), undefined, q);
            if (q.distanceTo(cam) > hit.distance + slack) continue;
          }
          if (d < bestD - 2 || (d < bestD + 2 && d < maxPx && z < bestZ)) { best = { edge: e, i, matrix, inst }; bestD = Math.min(d, bestD); bestZ = z; }
        }
      });
    }
    return best;
  }

  /** Edges' points on the screen (x, y from the canvas' corner, z: depth) and each edge's box there, kept while the
   *  camera, the canvas and the placement stay -> {scr, at: each edge's first in scr, box: x0, y0, x1, y1 per edge}. */
  edgesOnScreen(edges, matrix, ck, r) {
    const key = `${ck}|${matrix ? matrix.elements.join() : ''}`, memo = EDGE_SCREEN.get(edges);
    if (memo?.key === key) return memo;
    const at = new Uint32Array(edges.length), box = new Float64Array(edges.length * 4), v = new THREE.Vector3();
    let n = 0;
    edges.forEach((e, i) => { at[i] = n; n += e.pts.length; });
    const scr = new Float64Array(n);
    edges.forEach((e, i) => {
      const p = e.pts;
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (let k = 0, j = at[i]; k < p.length; k += 3, j += 3) {
        v.set(p[k], p[k + 1], p[k + 2]);
        if (matrix) v.applyMatrix4(matrix);
        v.project(this.camera);
        const x = (v.x + 1) / 2 * r.width, y = (1 - v.y) / 2 * r.height;
        scr[j] = x; scr[j + 1] = y; scr[j + 2] = v.z;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
      box.set([x0, y0, x1, y1], i * 4);
    });
    const out = { key, scr, at, box };
    EDGE_SCREEN.set(edges, out);
    return out;
  }

  /** The edge under the mouse lit (a line or a circle): [{pts, matrix?}], drawn over the part; key: the same -> kept. */
  setHoverEdges(list = [], key = '') {
    if (!this.hoverEdgeGroup) { this.hoverEdgeGroup = new THREE.Group(); this.scene.add(this.hoverEdgeGroup); }
    if (key === (this.hoverEdgeKey || '')) return;
    this.hoverEdgeKey = key;
    this.clear(this.hoverEdgeGroup);
    this.invalidate();
    const pts = [];
    for (const { pts: p, matrix } of list) {
      for (let k = 0; k + 5 < p.length; k += 3) {
        const a = new THREE.Vector3(p[k], p[k + 1], p[k + 2]), b = new THREE.Vector3(p[k + 3], p[k + 4], p[k + 5]);
        pts.push(matrix ? a.applyMatrix4(matrix) : a, matrix ? b.applyMatrix4(matrix) : b);
      }
    }
    if (!pts.length) return;
    const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xffd75e, depthTest: false, transparent: true }));
    const dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(pts), new THREE.PointsMaterial({ color: 0xffd75e, size: 3.5, sizeAttenuation: false, depthTest: false, transparent: true, opacity: 0.85 }));
    l.renderOrder = dots.renderOrder = 12;
    this.hoverEdgeGroup.add(l, dots);
  }

  /** The hovered step's / face's snap points shown as small dots (corners, edge middles, centres): [{point}]. */
  setHoverSnaps(points = [], key = '') {
    if (!this.hoverSnapGroup) { this.hoverSnapGroup = new THREE.Group(); this.scene.add(this.hoverSnapGroup); }
    if (key === (this.hoverSnapKey || '')) return;
    this.hoverSnapKey = key;
    this.clear(this.hoverSnapGroup);
    this.invalidate();
    // only the points the camera sees (one behind the part is left out; the camera moves only by a drag, which clears these)
    const solids = (this.meshes || (this.mesh ? [this.mesh] : [])).filter((m) => m.visible), cam = this.camera.position, rc = new THREE.Raycaster(), slack = this.size * 0.01;
    const seen = points.slice(0, 600).map((p) => p.point).filter((p) => {
      const dist = p.distanceTo(cam);
      rc.set(cam, p.clone().sub(cam).normalize());
      const h = rc.intersectObjects(solids, false)[0];
      return !h || h.distance >= dist - slack;
    });
    if (!seen.length) return;
    const dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(seen),
      new THREE.PointsMaterial({ color: 0x7ee787, size: 6, sizeAttenuation: false, depthTest: false, transparent: true, opacity: 0.85 }));
    dots.renderOrder = 13;
    this.hoverSnapGroup.add(dots);
  }

  /** No hover marks (the mouse left, a tool started, the part was rebuilt). */
  clearHoverMarks() { this.setHoverEdges([]); this.setHoverSnaps([]); }

  /** Highlight edges: hovered (yellow) and selected (blue), drawn over the part. */
  setEdgeHighlight(hover = -1, selected = []) {
    this.clear(this.edgeGroup);
    this.invalidate();
    if (!this.body) return;
    const add = (ids, color) => {
      const pts = [];
      for (const i of ids) {
        const p = this.body.edges[i]?.pts;
        if (!p) continue;
        for (let k = 0; k + 5 < p.length; k += 3) pts.push(new THREE.Vector3(p[k], p[k + 1], p[k + 2]), new THREE.Vector3(p[k + 3], p[k + 4], p[k + 5]));
      }
      if (!pts.length) return;
      const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true }));
      l.renderOrder = 12;
      this.edgeGroup.add(l);
      // a soft glow: the same lines again, as fat points
      const dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(pts), new THREE.PointsMaterial({ color, size: 4, sizeAttenuation: false, depthTest: false, transparent: true, opacity: 0.8 }));
      dots.renderOrder = 12;
      this.edgeGroup.add(dots);
    };
    add(selected, 0x4f8cff);
    const hv = [].concat(hover).filter((i) => i >= 0); // (one edge, or a ⛓ chain of them)
    if (hv.length) add(hv, 0xf2cc60);
  }

  // ------------------------------------------------------------------ section view
  /** Cut the view along a plane: axis x / y / z, at offset (mm), flip = show the other side; null = no cut. Kept
   *  without flip: the half away from the iso / front / right / top cameras (x and z below the cut, y behind it), so
   *  the cut faces the viewer. The plane sits a hair into the kept side: a face lying in the cut is cut away whole,
   *  not left flickering half drawn; the cut faces are filled (updateCaps). */
  setSection(sec) {
    this.renderer.localClippingEnabled = !!sec;
    const planes = [];
    if (sec) {
      const n = new THREE.Vector3(sec.axis === 'x' ? -1 : 0, sec.axis === 'y' ? 1 : 0, sec.axis === 'z' ? -1 : 0);
      if (sec.flip) n.negate();
      const along = n.x + n.y + n.z; // (±1)
      planes.push(new THREE.Plane(n, -along * sec.offset - Math.max(this.size || 1, 1) * 1e-4));
    }
    this.material.clippingPlanes = planes;
    this.edgeMaterial.clippingPlanes = planes;
    this.threadMaterial.clippingPlanes = planes;
    this.material.needsUpdate = this.edgeMaterial.needsUpdate = this.threadMaterial.needsUpdate = true;
    if (!sec) this.updateCaps(); // (no cut: its caps gone now, not at the next frame drawn)
    this.invalidate();
  }

  /** ✂ The cut faces filled: each part sliced by the section plane (sectioncap.js), in a colour of its own — remade
   *  when the cut, a part or its place changes (a mechanism playing moves them). Called before each picture. */
  updateCaps() {
    const plane = this.material.clippingPlanes?.[0] || null;
    if (!this.capGroup) { if (!plane) return; this.capGroup = new THREE.Group(); this.scene.add(this.capGroup); }
    if (plane) this.scene.updateMatrixWorld();
    const meshes = plane ? (this.meshes || (this.mesh ? [this.mesh] : [])).filter((m) => m.visible) : [];
    const key = plane ? `${plane.normal.toArray()}|${plane.constant}|${meshes.map((m) => `${m.geometry.uuid}:${m.matrixWorld.elements.join()}`).join('|')}` : '';
    if (key === this.capKey) return;
    this.capKey = key;
    for (const o of [...this.capGroup.children]) { this.capGroup.remove(o); o.geometry.dispose(); o.material.dispose(); }
    for (const m of meshes) {
      const geo = capGeometry(m, plane);
      if (!geo) continue;
      const own = !m.material.vertexColors && m.material.color; // (an assembly's part: the cap a little toward its colour)
      const cap = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: own ? CAP.clone().lerp(own, 0.25) : CAP, roughness: 0.8, metalness: 0, side: THREE.DoubleSide }));
      cap.userData.cap = true;
      this.capGroup.add(cap);
    }
  }

  // ------------------------------------------------------------------ measuring
  /** The point a measure click means: a reference point or a corner of the part within 10 px, else the point on the
   *  surface. (A reference point: snap 'point', its step's id.) */
  measurePoint(clientX, clientY) {
    const h = this.pick(clientX, clientY), rect = this.renderer.domElement.getBoundingClientRect();
    const kinds = snapKinds();
    let s = snapNear([{ edges: this.body?.edges }], this.camera, rect, clientX, clientY, 10, kinds), ref = null;
    s = this.withOrigin(s, clientX, clientY, 10, kinds);
    for (const p of this.refPoints || []) { // (a reference point beats a corner under it)
      const q = p.point.clone().project(this.camera), d = Math.hypot(rect.left + (q.x + 1) / 2 * rect.width - clientX, rect.top + (1 - q.y) / 2 * rect.height - clientY);
      if (q.z <= 1 && d < 10 && (!ref || d < ref.d)) ref = { d, ...p };
    }
    if (ref) s = { point: ref.point.clone(), kind: 'point', id: ref.id, name: ref.name };
    if (!s && !h) return null;
    return { point: s ? s.point : h.point.clone(), corner: s?.kind === 'corner', snap: s?.kind || null, face: h?.face || null, ...(s?.id ? { id: s.id, name: s.name } : {}), ...(s?.r ? { r: s.r } : {}) }; // (r: a ring's radius)
  }

  /** ⊕ The origin (0, 0, 0) — its x / y / z arrows are shown — within px of the mouse on the screen: how far (px), or
   *  null. */
  originNear(clientX, clientY, px = 10) {
    if (!this.origin?.visible) return null;
    const q = new THREE.Vector3().project(this.camera);
    if (q.z > 1) return null; // (behind the camera)
    const [x, y] = this.toScreen(new THREE.Vector3()), d = Math.hypot(x - clientX, y - clientY);
    return d < px ? d : null;
  }

  /** A snap s (snapNear's, or null) — or the ⊕ origin instead when it is as near the mouse: a snap point like a corner
   *  (the Corners filter says whether it is taken), named "Origin"; a corner on the origin is the origin. */
  withOrigin(s, clientX, clientY, px = 10, kinds = snapKinds()) {
    const d = kinds.corner ? this.originNear(clientX, clientY, px) : null;
    if (d === null) return s;
    if (s) { const [x, y] = this.toScreen(s.point); if (Math.hypot(x - clientX, y - clientY) + 1 < d) return s; }
    return { point: new THREE.Vector3(), kind: 'origin', inst: null };
  }

  /** The origin's x / y / z arrow under the mouse (within px, not at the origin itself): 'X', 'Y', 'Z' or null. */
  originAxis(clientX, clientY, px = 6) {
    if (!this.origin?.visible) return null;
    const [ox, oy] = this.toScreen(new THREE.Vector3()), k = this.origin.scale.x;
    if (Math.hypot(ox - clientX, oy - clientY) < 10) return null; // (the origin itself: a snap point)
    let best = null;
    for (const [name, dir] of [['X', [1, 0, 0]], ['Y', [0, 1, 0]], ['Z', [0, 0, 1]]]) {
      const [ex, ey] = this.toScreen(new THREE.Vector3(...dir).multiplyScalar(k)), dx = ex - ox, dy = ey - oy, L = dx * dx + dy * dy;
      if (L < 4) continue; // (seen end-on)
      const s = Math.max(0, Math.min(1, ((clientX - ox) * dx + (clientY - oy) * dy) / L));
      const d = Math.hypot(ox + s * dx - clientX, oy + s * dy - clientY);
      if (d < px && (!best || d < best.d)) best = { d, name };
    }
    return best?.name || null;
  }

  /** The reference points (point steps): a small ✛ and its name each — [{id, name, xyz, on}] (on: the chosen one). */
  setPoints(list = []) {
    if (!this.pointGroup) { this.pointGroup = new THREE.Group(); this.scene.add(this.pointGroup); }
    const key = JSON.stringify(list);
    if (key === this.pointKey) return;
    this.pointKey = key;
    this.clear(this.pointGroup);
    this.invalidate();
    this.refPoints = list.map((p) => ({ id: p.id, name: p.name, point: new THREE.Vector3(...p.xyz) }));
    for (const p of list) {
      const at = new THREE.Vector3(...p.xyz);
      const dot = new THREE.Points(new THREE.BufferGeometry().setFromPoints([at]), new THREE.PointsMaterial({ color: p.on ? 0xf2cc60 : 0xd2a8ff, size: 9, sizeAttenuation: false, depthTest: false }));
      dot.renderOrder = 14;
      const el = document.createElement('div');
      el.className = `m-pt${p.on ? ' on' : ''}${p.bad ? ' bad' : ''}`;
      el.dataset.id = p.id;
      el.textContent = `• ${p.name}`;
      const lab = new CSS2DObject(el);
      lab.position.copy(at);
      this.pointGroup.add(dot, lab);
    }
  }

  /** The measure tool's snap under the mouse, shown: a green point and its name (corner, midpoint, centre). */
  /** The way a positive offset moves a sketch plane: an arrow from its origin along its normal, labelled (null: none;
   *  plus false: the label alone, no "+"). */
  setPlaneArrow(fr, label = '', plus = true) {
    if (!this.arrowGroup) { this.arrowGroup = new THREE.Group(); this.scene.add(this.arrowGroup); }
    this.clear(this.arrowGroup);
    this.planeArrow = null;
    this.invalidate();
    if (!fr) return;
    const o = new THREE.Vector3(...fr.o), n = new THREE.Vector3(...fr.n).normalize(), L = Math.max(10, (this.size || 40) * 0.35);
    const arrow = new THREE.ArrowHelper(n, o, L, 0xd2a8ff, L * 0.22, L * 0.12);
    arrow.traverse((x) => { if (x.material) { x.material.depthTest = false; x.material.transparent = true; } x.renderOrder = 13; });
    const el = document.createElement('div');
    el.className = 'm-snap m-plane-plus';
    const lab = new CSS2DObject(el);
    this.arrowGroup.add(arrow, lab);
    this.planeArrow = { arrow, lab, el, o, n, x: new THREE.Vector3(...fr.x).normalize(), L, text: plus ? label : '', bare: plus ? '' : label, seen: null };
    this.updatePlaneArrow();
  }

  /** The offset arrow as it is seen: looked at end-on (e.g. the Top view down +Z) a cone tip is a blob, so it is the
   *  CAD symbol instead — ⊙ toward you, ⊗ away — beside the origin; from the side, the arrow and "+ label" at its tip. */
  updatePlaneArrow() {
    const pa = this.planeArrow;
    if (!pa) return;
    const toCam = this.camera.position.clone().sub(pa.o).normalize(), d = toCam.dot(pa.n);
    const seen = d > 0.9 ? 'toward' : d < -0.9 ? 'away' : 'side';
    if (seen === pa.seen) return;
    pa.seen = seen;
    pa.arrow.visible = seen === 'side';
    if (seen === 'side') {
      pa.el.textContent = pa.bare || `+ ${pa.text}`;
      pa.lab.position.copy(pa.o).addScaledVector(pa.n, pa.L * 1.15);
    } else {
      pa.el.textContent = pa.bare || `${seen === 'toward' ? '⊙' : '⊗'} ${pa.text}`;
      pa.lab.position.copy(pa.o).addScaledVector(pa.x, -pa.L * 0.3); // (beside the origin, clear of its axes)
    }
  }

  /** An open extrude's pull arrow: from o along the unit direction dir, len long (null: none) — its tip is dragged. */
  setPullArrow(o, dir, len) {
    if (!this.pullGroup) { this.pullGroup = new THREE.Group(); this.scene.add(this.pullGroup); }
    this.clear(this.pullGroup);
    this.pull = null;
    this.invalidate();
    if (!o) return;
    const a = V(o), n = V(dir).normalize(), head = Math.max(2, Math.min(len * 0.4, (this.size || 40) * 0.08));
    const arrow = new THREE.ArrowHelper(n, a, len + head, 0xf0883e, head, head * 0.55);
    arrow.traverse((x) => { if (x.material) { x.material.depthTest = false; x.material.transparent = true; } x.renderOrder = 14; });
    this.pullGroup.add(arrow);
    this.pull = { o: a, n, len, head };
  }

  /** Is the mouse on the pull arrow's head (within 12 px of it)? */
  pullHit(clientX, clientY) {
    const p = this.pull;
    if (!p) return false;
    const [x, y] = this.toScreen(p.o.clone().addScaledVector(p.n, p.len + p.head * 0.5));
    return Math.hypot(x - clientX, y - clientY) < 12;
  }

  /** How far along the pull arrow (mm from its start) the mouse is: the point of its line nearest the mouse's ray. */
  pullAlong(clientX, clientY) {
    const p = this.pull;
    if (!p) return null;
    const big = (this.size || 40) * 50, at = new THREE.Vector3();
    this.ray(clientX, clientY).ray.distanceSqToSegment(p.o.clone().addScaledVector(p.n, -big), p.o.clone().addScaledVector(p.n, big), null, at);
    return at.sub(p.o).dot(p.n) - p.head * 0.5;
  }

  setSnapMark(mp) {
    if (!this.snapGroup) { this.snapGroup = new THREE.Group(); this.scene.add(this.snapGroup); }
    const key = mp?.snap ? `${mp.snap}:${mp.point.toArray().map((v) => v.toFixed(4))}` : '';
    if (key === this.snapKey) return;
    this.snapKey = key;
    this.clear(this.snapGroup);
    this.invalidate();
    if (!key) return;
    const dot = new THREE.Points(new THREE.BufferGeometry().setFromPoints([mp.point]), new THREE.PointsMaterial({ color: 0x7ee787, size: 11, sizeAttenuation: false, depthTest: false }));
    dot.renderOrder = 14;
    const el = document.createElement('div');
    el.className = 'm-snap';
    el.textContent = mp.snap === 'point' ? mp.name : t({ corner: 'corner', midpoint: 'midpoint', centre: 'centre', quadrant: 'quadrant', origin: 'Origin' }[mp.snap]);
    const lab = new CSS2DObject(el);
    lab.position.copy(mp.point);
    this.snapGroup.add(dot, lab);
  }

  /** ⚖ The centre of mass marked: ⊕ at p ([x, y, z]; null: none), over the parts, with a short label. Made once and
   *  only moved after (an assembly's moves it on every frame while a mechanism plays). */
  setCog(p, label = '') {
    if (!p) { if (this.cog) { this.cog.visible = false; this.invalidate(); } return; }
    if (!this.cog) {
      const el = document.createElement('div');
      el.className = 'm-cog';
      el.innerHTML = '<i>⊕</i><span></span>';
      this.cog = new CSS2DObject(el);
      this.scene.add(this.cog);
    }
    this.cog.visible = true;
    this.cog.position.set(...p);
    const s = this.cog.element.querySelector('span');
    if (s.textContent !== label) s.textContent = label;
    this.invalidate();
  }

  /** The measure overlay: points and a line between them, with a label. */
  setMeasure(points = [], text = '') {
    if (!this.measureGroup) { this.measureGroup = new THREE.Group(); this.scene.add(this.measureGroup); }
    this.clear(this.measureGroup);
    this.invalidate();
    if (!points.length) return;
    const dots = new THREE.Points(new THREE.BufferGeometry().setFromPoints(points), new THREE.PointsMaterial({ color: 0xf2cc60, size: 8, sizeAttenuation: false, depthTest: false }));
    dots.renderOrder = 13;
    this.measureGroup.add(dots);
    if (points.length === 2) {
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: 0xf2cc60, depthTest: false }));
      l.renderOrder = 13;
      this.measureGroup.add(l);
      if (text) {
        const el = document.createElement('div');
        el.className = 'sk-label live';
        el.textContent = text;
        const lab = new CSS2DObject(el);
        lab.position.copy(points[0]).add(points[1]).multiplyScalar(0.5);
        this.measureGroup.add(lab);
      }
    }
  }
}
