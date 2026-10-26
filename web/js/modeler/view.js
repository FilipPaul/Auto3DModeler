// The 3D view of the model workspace: the body from the CAD kernel (one face id per triangle, so faces can
// be highlighted and picked), its edges, the three base planes (Top / Front / Right) and, in sketch mode,
// the sketch plane with a grid, the sketch shapes and their editable sizes.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';

const BODY = new THREE.Color(0xd9dee6), HOVER = new THREE.Color(0x6cb6ff), PICKED = new THREE.Color(0x4f8cff);
const FEATURE = new THREE.Color(0xa9cdf5), SELECTED = new THREE.Color(0xf2cc60); // the step under the mouse / the chosen step
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

const b64 = (s, T) => {
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
  constructor(container) {
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
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.3));
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
    this.outlineGroup = new THREE.Group(); // sketches shown as lines outside sketch mode
    this.edgeGroup = new THREE.Group();    // highlighted edges (Fillet / Chamfer)
    this.tagGroup = new THREE.Group();     // the chosen step's sizes, as labels on the part
    this.scene.add(this.bodyGroup, this.datumGroup, this.sketchGroup, this.outlineGroup, this.edgeGroup, this.tagGroup);
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
    };
    loop();
    this.showDatums(true);
    // the origin, always: short x / y / z arrows (drawn over the part)
    this.origin = new THREE.AxesHelper(1);
    this.origin.material.depthTest = false;
    this.origin.renderOrder = 11;
    this.scene.add(this.origin);
    this.sizeOrigin();
  }

  sizeOrigin() {
    const k = Math.max(this.size * 0.12, 6);
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

  paint() {
    if (!this.mesh) return;
    const col = this.mesh.geometry.attributes.color;
    for (let t = 0; t < this.faceIds.length; t++) {
      const f = this.faceIds[t];
      const c = f === this.hover ? HOVER : this.picked.has(f) ? PICKED : this.hoverSet?.has(f) ? FEATURE : this.selSet?.has(f) ? SELECTED : BODY;
      for (let k = 0; k < 3; k++) col.setXYZ(t * 3 + k, c.r, c.g, c.b);
    }
    col.needsUpdate = true;
    this.invalidate();
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
        color: DATUM_COLORS[name], transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }));
      m.matrix.makeBasis(x, y, n).setPosition(o.clone().addScaledVector(x, s / 2).addScaledVector(y, s / 2));
      m.matrixAutoUpdate = false;
      m.userData.datum = name;
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), new THREE.LineBasicMaterial({ color: DATUM_COLORS[name], transparent: true, opacity: 0.55 }));
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
    for (const m of this.datumGroup.children) if (m.userData.datum) m.material.opacity = m.userData.datum === name ? 0.28 : 0.08;
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

  setView(name) {
    const box = this.fitBox(), c = box.getCenter(new THREE.Vector3()), s = Math.max(box.getSize(new THREE.Vector3()).length(), 20);
    const dirs = { iso: [0.55, -0.9, 0.7], top: [0, -0.0001, 1], front: [0, -1, 0.0001], right: [1, 0, 0.0001] };
    const dir = V(dirs[name] || dirs.iso).normalize();
    this.camera.up.set(0, 0, 1);
    if (name === 'top') this.camera.up.set(0, 1, 0);
    this.camera.position.copy(c).addScaledVector(dir, s * 1.6);
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
    if (!fr) return;
    const { o, x, y, n } = axes(fr);
    const lift = this.size * 0.0005;
    const P = (u, v) => o.clone().addScaledVector(x, u).addScaledVector(y, v).addScaledVector(n, lift);
    const add = (o3) => { o3.renderOrder = 6; this.sketchGroup.add(o3); };
    if (!grid) grid = this.size / 60 || 1; // only lines and labels (no grid, no plane): dimensions on the part
    else this.drawSketchPlane(P, grid, x, y, n, lift);
    this.drawSketchItems(P, add, grid, { lines, circles, dots, labels });
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
    const r = this.renderer.domElement.getBoundingClientRect();
    const mx = clientX - r.left, my = clientY - r.top;
    const scr = (x, y, z) => {
      const v = new THREE.Vector3(x, y, z).project(this.camera);
      return [(v.x + 1) / 2 * r.width, (1 - v.y) / 2 * r.height, v.z];
    };
    // an edge hidden behind the part is not pickable: it must not be farther than the surface under the mouse
    const hit = this.mesh ? this.ray(clientX, clientY).intersectObject(this.mesh, false)[0] : null;
    const cam = this.camera.position, slack = this.size * 0.01;
    let best = -1, bestD = maxPx, bestZ = Infinity;
    this.body.edges.forEach((e, i) => {
      if (e.faces.length < 2) return; // a seam on a round face: not a real edge
      const p = e.pts;
      let prev = scr(p[0], p[1], p[2]);
      for (let k = 3; k < p.length; k += 3) {
        const cur = scr(p[k], p[k + 1], p[k + 2]);
        const dx = cur[0] - prev[0], dy = cur[1] - prev[1], L = dx * dx + dy * dy || 1;
        const t = Math.max(0, Math.min(1, ((mx - prev[0]) * dx + (my - prev[1]) * dy) / L));
        const d = Math.hypot(prev[0] + t * dx - mx, prev[1] + t * dy - my), z = prev[2] + t * (cur[2] - prev[2]);
        if (d < maxPx && hit) {
          const q = new THREE.Vector3(p[k - 3] + t * (p[k] - p[k - 3]), p[k - 2] + t * (p[k + 1] - p[k - 2]), p[k - 1] + t * (p[k + 2] - p[k - 1]));
          if (q.distanceTo(cam) > hit.distance + slack) { prev = cur; continue; }
        }
        if (d < bestD - 2 || (d < bestD + 2 && d < maxPx && z < bestZ)) { best = i; bestD = Math.min(d, bestD); bestZ = z; }
        prev = cur;
      }
    });
    return best;
  }

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
  /** The point a measure click means: a corner of the part within 10 px, else the point on the surface. */
  measurePoint(clientX, clientY) {
    const h = this.pick(clientX, clientY);
    const r = this.renderer.domElement.getBoundingClientRect();
    let best = null, bd = 10;
    for (const e of this.body?.edges || []) {
      const n = e.pts.length;
      if (e.faces.length < 2) continue; // a seam on a round face: not a real edge
      if (Math.hypot(e.pts[0] - e.pts[n - 3], e.pts[1] - e.pts[n - 2], e.pts[2] - e.pts[n - 1]) < 1e-6) continue; // a closed edge (a circle): no corner
      for (const k of [0, n - 3]) {
        const p = new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]);
        const q = p.clone().project(this.camera);
        const d = Math.hypot(r.left + (q.x + 1) / 2 * r.width - clientX, r.top + (1 - q.y) / 2 * r.height - clientY);
        if (d < bd) { bd = d; best = p; }
      }
    }
    if (!best && !h) return null;
    return { point: best || h.point.clone(), corner: !!best, face: h?.face || null };
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
