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

const BODY = new THREE.Color(0xd9dee6), HOVER = new THREE.Color(0x6cb6ff), PICKED = new THREE.Color(0x4f8cff);
const FEATURE = new THREE.Color(0xa9cdf5), SELECTED = new THREE.Color(0xf2cc60); // the step under the mouse / the chosen step
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
 *  matrix: where the part is placed; kinds: the snap filters -> [{point, kind}]. */
export function snapPoints(edges, matrix = null, kinds = null) {
  const out = [], push = (point, kind) => { if (!kinds || kinds[kind]) out.push({ point, kind }); };
  for (const e of edges || []) {
    const n = e.pts.length;
    if (n < 6) continue;
    const P = (k) => { const p = new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]); return matrix ? p.applyMatrix4(matrix) : p; };
    const closed = Math.hypot(e.pts[0] - e.pts[n - 3], e.pts[1] - e.pts[n - 2], e.pts[2] - e.pts[n - 1]) < 1e-6;
    if (closed) { // a round edge (a hole's rim, a pin's end): its centre
      const c = new THREE.Vector3();
      for (let k = 0; k < n - 3; k += 3) c.add(new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]));
      c.multiplyScalar(3 / (n - 3));
      if (!kinds || kinds.quadrant) { // its four quadrant points: along the world axis lying best in its plane, and across
        const a = new THREE.Vector3(e.pts[0], e.pts[1], e.pts[2]).sub(c), b = new THREE.Vector3(e.pts[3 * Math.floor((n / 3 - 1) / 4)], e.pts[3 * Math.floor((n / 3 - 1) / 4) + 1], e.pts[3 * Math.floor((n / 3 - 1) / 4) + 2]).sub(c);
        const nn = a.clone().cross(b).normalize(), rad = a.length();
        if (nn.lengthSq() > 0.5 && rad > 0) {
          const ax = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)].sort((p, q) => Math.abs(p.dot(nn)) - Math.abs(q.dot(nn)))[0];
          const u = ax.clone().addScaledVector(nn, -ax.dot(nn)).normalize().multiplyScalar(rad), w = nn.clone().cross(u);
          for (const d of [u, w, u.clone().negate(), w.clone().negate()]) { const q = c.clone().add(d); out.push({ point: matrix ? q.applyMatrix4(matrix) : q, kind: 'quadrant' }); }
        }
      }
      push(matrix ? c.applyMatrix4(matrix) : c, 'centre');
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
 *  edge (midpoint), the centre of a round edge (centre) — list: [{edges, matrix?, inst?}] -> {point, kind, inst} or null. */
export function snapNear(list, camera, rect, clientX, clientY, px = 10, kinds = null) {
  let best = null, bd = px;
  for (const { edges, matrix, inst } of list) {
    for (const { point: p, kind } of snapPoints(edges, matrix, kinds)) {
      const q = p.clone().project(camera);
      if (q.z > 1) continue; // (behind the camera)
      const d = Math.hypot(rect.left + (q.x + 1) / 2 * rect.width - clientX, rect.top + (1 - q.y) / 2 * rect.height - clientY);
      if (d < bd) { bd = d; best = { point: p, kind, inst }; }
    }
  }
  return best;
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

/** A plane frame {o, x, n} -> three vectors (origin, x, y, normal). */
export function axes(fr) {
  const o = V(fr.o), x = V(fr.x).normalize(), n = V(fr.n).normalize();
  return { o, x, y: new THREE.Vector3().crossVectors(n, x), n };
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
      if (!this.dirty) return;
      this.dirty = false;
      this.renderer.render(this.scene, this.camera);
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
    this.mesh = new THREE.Mesh(geo, this.material);
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

  /** Reference solids: shown see-through (not part of the part, not picked): [{positions (base64)}]. */
  setRefs(list = []) {
    if (!this.refGroup) { this.refGroup = new THREE.Group(); this.scene.add(this.refGroup); }
    this.clear(this.refGroup);
    for (const r of list) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(b64(r.positions, Float32Array), 3));
      geo.computeVertexNormals();
      // drawn through the part (a cover built around it hides it otherwise)
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x58a6ff, transparent: true, opacity: 0.35, depthWrite: false, depthTest: false, side: THREE.DoubleSide }));
      mesh.renderOrder = 4;
      this.refGroup.add(mesh);
    }
    this.invalidate();
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

  paint() {
    if (!this.mesh) return;
    const col = this.mesh.geometry.attributes.color;
    for (let t = 0; t < this.faceIds.length; t++) {
      const f = this.faceIds[t];
      const c = f === this.hover ? HOVER : this.picked.has(f) ? PICKED : this.hoverSet?.has(f) ? FEATURE : this.selSet?.has(f) ? SELECTED
        : this.shades ? SHADES[(this.body.faces[f]?.solid || 0) % SHADES.length]
          : this.faceColor?.get(f) || this.fileColor?.get(f) || this.bodyColor || BODY;
      for (let k = 0; k < 3; k++) col.setXYZ(t * 3 + k, c.r, c.g, c.b);
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
    const key = also ? also.join(',') : '';
    if (faceId === this.hover && key === (this.hoverKey || '')) return;
    this.hover = faceId;
    this.hoverKey = key;
    this.hoverSet = also ? new Set(also) : null;
    this.paint();
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

  face(id) { return this.body?.faces.find((f) => f.id === id) || null; }

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

  /** What is under the mouse: {face} (a face of the body) or {datum} (a base plane), or null. */
  pick(clientX, clientY, { datums = false } = {}) {
    const ray = this.ray(clientX, clientY);
    if (this.mesh) {
      const h = ray.intersectObject(this.mesh, false)[0];
      if (h) return { face: this.face(this.faceIds[h.faceIndex]), point: h.point };
    }
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

  /** All of it in the view, seen from where the camera looks now. */
  fit() {
    const box = this.fitBox(), c = box.getCenter(new THREE.Vector3()), s = Math.max(box.getSize(new THREE.Vector3()).length(), 1);
    const dir = this.camera.position.clone().sub(this.controls.target);
    if (dir.lengthSq() < 1e-12) dir.set(0.55, -0.9, 0.7);
    this.camera.position.copy(c).addScaledVector(dir.normalize(), s * 1.6);
    this.controls.target.copy(c);
    this.controls.update();
    this.invalidate();
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
      new THREE.LineBasicMaterial({ color: 0x39d0d8, transparent: true, opacity: 0.09, depthWrite: false, depthTest: false }));
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(2 * half, 2 * half), new THREE.MeshBasicMaterial({
      color: 0x1a2a3a, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }));
    plane.matrix.makeBasis(x, y, n).setPosition(P(0, 0).addScaledVector(n, -lift * 0.6));
    plane.matrixAutoUpdate = false;
    const axesLines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([P(-half, 0), P(half, 0), P(0, -half), P(0, half)]),
      new THREE.LineBasicMaterial({ color: 0x8b95a3, transparent: true, opacity: 0.45, depthTest: false }));
    this.sketchGroup.add(plane, gridLines, axesLines);
  }

  drawSketchItems(P, add, grid, { lines, circles, dots, labels }) {
    for (const [a, b, color, dashed] of lines) {
      const geo = new THREE.BufferGeometry().setFromPoints([P(a[0], a[1]), P(b[0], b[1])]);
      const mat = dashed ? new THREE.LineDashedMaterial({ color, dashSize: grid * 0.6, gapSize: grid * 0.4, depthTest: false, transparent: true, opacity: 0.7 })
        : new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true });
      const l = new THREE.Line(geo, mat);
      if (dashed) l.computeLineDistances();
      add(l);
    }
    for (const [c, r, color] of circles) {
      const ring = Array.from({ length: 97 }, (_, i) => { const a = (i / 96) * Math.PI * 2; return P(c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)); });
      add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ring), new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true })));
    }
    if (dots.length) {
      const geo = new THREE.BufferGeometry().setFromPoints(dots.map(([p]) => P(p[0], p[1])));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(dots.flatMap(([, c]) => { const k = new THREE.Color(c); return [k.r, k.g, k.b]; }), 3));
      add(new THREE.Points(geo, new THREE.PointsMaterial({ size: 7, sizeAttenuation: false, vertexColors: true, depthTest: false, transparent: true })));
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
      seg.userData.sketch = sk.id;
      this.outlineGroup.add(seg);
    }
  }

  /** The sketch whose lines are under the mouse (within ~6 px), or null. */
  pickOutline(clientX, clientY) {
    const ray = this.ray(clientX, clientY);
    ray.params.Line = { threshold: this.size * 0.012 };
    const h = ray.intersectObjects(this.outlineGroup.children, false)[0];
    return h?.object.userData.sketch || null;
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
    const hit = solids.length ? this.ray(clientX, clientY).intersectObjects(solids, false)[0] : null;
    const cam = this.camera.position, slack = this.size * 0.01;
    let best = null, bestD = maxPx, bestZ = Infinity;
    for (const { edges, matrix, inst } of list) {
      const W = (p, k) => { v.set(p[k], p[k + 1], p[k + 2]); return matrix ? v.applyMatrix4(matrix) : v; };
      const scr = (p, k) => { const w = W(p, k).project(this.camera); return [(w.x + 1) / 2 * r.width, (1 - w.y) / 2 * r.height, w.z]; };
      (edges || []).forEach((e, i) => {
        if (e.faces.length < 2) return; // a seam on a round face: not a real edge
        const p = e.pts;
        let prev = scr(p, 0);
        for (let k = 3; k < p.length; k += 3) {
          const cur = scr(p, k);
          const dx = cur[0] - prev[0], dy = cur[1] - prev[1], L = dx * dx + dy * dy || 1;
          const t = Math.max(0, Math.min(1, ((mx - prev[0]) * dx + (my - prev[1]) * dy) / L));
          const d = Math.hypot(prev[0] + t * dx - mx, prev[1] + t * dy - my), z = prev[2] + t * (cur[2] - prev[2]);
          if (d < maxPx && hit) {
            const a = W(p, k - 3).clone(), q = a.lerp(W(p, k), t);
            if (q.distanceTo(cam) > hit.distance + slack) { prev = cur; continue; }
          }
          if (d < bestD - 2 || (d < bestD + 2 && d < maxPx && z < bestZ)) { best = { edge: e, i, matrix, inst }; bestD = Math.min(d, bestD); bestZ = z; }
          prev = cur;
        }
      });
    }
    return best;
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
    const solids = this.meshes || (this.mesh ? [this.mesh] : []), cam = this.camera.position, rc = new THREE.Raycaster(), slack = this.size * 0.01;
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
    if (hover >= 0) add([hover], 0xf2cc60);
  }

  // ------------------------------------------------------------------ section view
  /** Cut the view along a plane: axis x / y / z, at offset (mm), flip = show the other side; null = no cut. */
  setSection(sec) {
    this.renderer.localClippingEnabled = !!sec;
    const planes = [];
    if (sec) {
      const n = new THREE.Vector3(sec.axis === 'x' ? 1 : 0, sec.axis === 'y' ? 1 : 0, sec.axis === 'z' ? 1 : 0);
      if (!sec.flip) n.negate();
      planes.push(new THREE.Plane(n, sec.flip ? -sec.offset : sec.offset));
    }
    this.material.clippingPlanes = planes;
    this.edgeMaterial.clippingPlanes = planes;
    this.material.needsUpdate = this.edgeMaterial.needsUpdate = true;
    this.invalidate();
  }

  // ------------------------------------------------------------------ measuring
  /** The point a measure click means: a reference point or a corner of the part within 10 px, else the point on the
   *  surface. (A reference point: snap 'point', its step's id.) */
  measurePoint(clientX, clientY) {
    const h = this.pick(clientX, clientY), rect = this.renderer.domElement.getBoundingClientRect();
    let s = snapNear([{ edges: this.body?.edges }], this.camera, rect, clientX, clientY, 10, snapKinds()), ref = null;
    for (const p of this.refPoints || []) { // (a reference point beats a corner under it)
      const q = p.point.clone().project(this.camera), d = Math.hypot(rect.left + (q.x + 1) / 2 * rect.width - clientX, rect.top + (1 - q.y) / 2 * rect.height - clientY);
      if (q.z <= 1 && d < 10 && (!ref || d < ref.d)) ref = { d, ...p };
    }
    if (ref) s = { point: ref.point.clone(), kind: 'point', id: ref.id, name: ref.name };
    if (!s && !h) return null;
    return { point: s ? s.point : h.point.clone(), corner: s?.kind === 'corner', snap: s?.kind || null, face: h?.face || null, ...(s?.id ? { id: s.id, name: s.name } : {}) };
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
    this.invalidate();
    if (!fr) return;
    const o = new THREE.Vector3(...fr.o), n = new THREE.Vector3(...fr.n).normalize(), L = Math.max(10, (this.size || 40) * 0.35);
    const arrow = new THREE.ArrowHelper(n, o, L, 0xd2a8ff, L * 0.22, L * 0.12);
    arrow.traverse((x) => { if (x.material) { x.material.depthTest = false; x.material.transparent = true; } x.renderOrder = 13; });
    const el = document.createElement('div');
    el.className = 'm-snap m-plane-plus';
    el.textContent = plus ? `+ ${label}` : label;
    const lab = new CSS2DObject(el);
    lab.position.copy(o).addScaledVector(n, L * 1.15);
    this.arrowGroup.add(arrow, lab);
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
    el.textContent = mp.snap === 'point' ? mp.name : t({ corner: 'corner', midpoint: 'midpoint', centre: 'centre', quadrant: 'quadrant' }[mp.snap]);
    const lab = new CSS2DObject(el);
    lab.position.copy(mp.point);
    this.snapGroup.add(dot, lab);
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
