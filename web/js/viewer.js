// Three.js scene: the solid (from the server mesh), dimension annotations, design guides,
// picking helpers for the dimension tool, printer build volume and split pieces.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { GLTFExporter } from 'three/addons/GLTFExporter.js';

const DIM_COLORS = {
  drawing: 0x58a6ff, estimated: 0xe3a008, default: 0xe3a008, user: 0xa371f7, added: 0xa371f7, reference: 0x8b95a3,
};
const PIECE_COLORS = [0x6cb6ff, 0x7ee787, 0xffa657, 0xd2a8ff, 0xff7b72, 0x79c0ff, 0xf2cc60, 0x56d364];

function decodeMesh(m) {
  const bin = atob(m.positions);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const pos = new Float32Array(bytes.buffer);
  const tb = atob(m.tags);
  const tags = new Uint8Array(tb.length);
  for (let i = 0; i < tb.length; i++) tags[i] = tb.charCodeAt(i);
  return { pos, tags };
}

export class Viewer {
  constructor(container) {
    this.container = container;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setClearColor(0x000000, 0); // show the viewport's CSS gradient
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.labels = new CSS2DRenderer();
    Object.assign(this.labels.domElement.style, { position: 'absolute', inset: '0', pointerEvents: 'none' });
    container.appendChild(this.labels.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.01, 10000);
    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.3));
    const key = new THREE.DirectionalLight(0xffffff, 1.7);
    key.position.set(1, -1.5, 2.5);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.6);
    fill.position.set(-2, 1, -1);
    this.scene.add(fill);

    this.part = new THREE.Group();
    this.dims = new THREE.Group();
    this.overlay = new THREE.Group(); // guides, selected-layer outline
    this.helpers = new THREE.Group(); // dimension tool
    this.printGroup = new THREE.Group(); // build volume + pieces
    this.scene.add(this.part, this.dims, this.overlay, this.helpers, this.printGroup);
    this.material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, metalness: 0.05, side: THREE.DoubleSide });
    this.baseColor = new THREE.Color(0xd9dee6);
    this.featureColor = new THREE.Color(0x4f8cff);
    this.edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1b2430, transparent: true, opacity: 0.85 });
    this.wire = false;
    this.dimsVisible = true;
    this.hasFitted = false;

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    // render on demand: only while the camera moves or after the scene changed
    this.dirty = true;
    this.controls.addEventListener('change', () => { this.dirty = true; });
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
      if (!this.dirty) return;
      this.dirty = false;
      this.renderer.render(this.scene, this.camera);
      this.labels.render(this.scene, this.camera);
    };
    loop();
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.labels.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.invalidate();
  }

  invalidate() { this.dirty = true; }

  clearGroup(g) {
    for (const o of [...g.children]) {
      g.remove(o);
      o.traverse?.((c) => {
        c.geometry?.dispose?.();
        if (c.isCSS2DObject) c.element.remove();
      });
    }
  }

  buildGeometry(mesh, colorFor) {
    const { pos, tags } = decodeMesh(mesh);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const col = new Float32Array(pos.length);
    for (let t = 0; t < tags.length; t++) {
      const c = colorFor(tags[t]);
      for (let k = 0; k < 3; k++) col.set([c.r, c.g, c.b], (t * 3 + k) * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    geo.computeVertexNormals();
    return geo;
  }

  /** Rebuild the part from a solver result (with server mesh). */
  setSolution(solution) {
    this.invalidate();
    this.solution = solution;
    this.clearGroup(this.part);
    const geo = this.buildGeometry(solution.mesh, (tag) => (tag ? this.featureColor : this.baseColor));
    this.mesh = new THREE.Mesh(geo, this.material);
    this.mesh.visible = !this.wire;
    this.part.add(this.mesh);
    this.part.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), this.edgeMaterial));

    const [x0, y0, x1, y1] = solution.bbox;
    this.zRange = solution.z_range || [0, solution.thickness];
    this.size = Math.max(x1 - x0, y1 - y0, solution.thickness);
    this.setGuides(solution.guides || []);
    if (!this.hasFitted) { this.setView('iso'); this.hasFitted = true; }
  }

  setColors(base, feature) {
    this.invalidate();
    this.baseColor.set(base);
    this.featureColor.set(feature);
    if (this.solution) this.setSolution(this.solution);
  }

  faceZ(face) { return face === 'bottom' ? 0 : this.solution.thickness; }

  /** Height of a face plane: 'top' / 'bottom' = the faces design layers go on (the first object of
   *  an outline part, else the part), 'over' = above everything (2D outline shapes). */
  planeZ(face) {
    const lf = this.solution?.layer_faces;
    if (face === 'over') return this.zRange[1];
    if (face === 'bottom') return lf ? lf.bottom : this.zRange[0];
    return lf ? lf.top : this.zRange[1];
  }

  setGuides(guides) {
    this.invalidate();
    this.clearGroup(this.overlay);
    const mat = new THREE.LineDashedMaterial({ color: 0x2f81f7, dashSize: this.size / 150, gapSize: this.size / 300, depthTest: false });
    // guides / mask outlines live on the flat face; they are hidden while the part is shown bent
    for (const g of this.solution?.bent ? [] : guides) {
      const z = g.z + (g.z > 0 ? 1 : -1) * this.size * 0.0008;
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(g.points.map((p) => new THREE.Vector3(p[0], p[1], z))), mat);
      line.computeLineDistances();
      line.renderOrder = 4;
      this.overlay.add(line);
    }
    if (this.selectionRings) this.setSelection(this.selectionRings, this.selectionFace);
  }

  /** Outline of the selected design layer's mask. */
  setSelection(rings, face) {
    this.invalidate();
    this.selectionRings = rings;
    this.selectionFace = face;
    for (const o of this.overlay.children.filter((c) => c.userData.selection)) {
      this.overlay.remove(o);
      o.geometry.dispose();
    }
    if (!rings || !this.solution || this.solution.bent) return;
    const z = this.planeZ(face) + (face === 'bottom' ? -1 : 1) * this.size * 0.001;
    const mat = new THREE.LineBasicMaterial({ color: 0xff2d95, depthTest: false });
    for (const r of rings) {
      const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(r.map((p) => new THREE.Vector3(p[0], p[1], z))), mat);
      line.renderOrder = 7;
      line.userData.selection = true;
      this.overlay.add(line);
    }
  }

  /** Draw dimension annotations. `makeLabel(annotation)` returns the HTML element for the value label. */
  setAnnotations(annotations, makeLabel, statusOf) {
    this.invalidate();
    this.clearGroup(this.dims);
    this.annotationObjects = {};
    if (!this.solution) return;
    const z = this.solution.thickness + this.size * 0.001;
    const arrow = this.size * 0.012;
    const [bx0, by0, bx1, by1] = this.solution.bbox;

    for (const a of annotations) {
      const status = statusOf(a.param);
      const color = DIM_COLORS[status] ?? DIM_COLORS.drawing;
      const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false });
      const g = new THREE.Group();
      // on a bent part the server maps the label points onto the bent surface (drawn as a chord)
      const p1 = a.p1_3d ? new THREE.Vector3(...a.p1_3d) : new THREE.Vector3(a.p1[0], a.p1[1], a.z ?? z);
      const p2 = a.p2_3d ? new THREE.Vector3(...a.p2_3d) : new THREE.Vector3(a.p2[0], a.p2[1], a.z2 ?? a.z ?? z);
      const pts = [p1, p2];
      // extension lines (point-to-point dimensions along an axis): pairs of 3D points
      for (const [u, w] of a.ext || []) pts.push(new THREE.Vector3(...u), new THREE.Vector3(...w));
      if (a.axis !== 'z' && !a.p1_3d) {
        const horiz = Math.abs(a.p1[1] - a.p2[1]) < 1e-9;
        if (horiz && (a.p1[1] < by0 || a.p1[1] > by1)) {
          const edge = a.p1[1] < by0 ? by0 : by1;
          for (const p of [p1, p2]) pts.push(new THREE.Vector3(p.x, edge, z), new THREE.Vector3(p.x, p.y + Math.sign(p.y - edge) * arrow * 0.6, z));
        } else if (!horiz && (a.p1[0] < bx0 || a.p1[0] > bx1)) {
          const edge = a.p1[0] < bx0 ? bx0 : bx1;
          for (const p of [p1, p2]) pts.push(new THREE.Vector3(edge, p.y, z), new THREE.Vector3(p.x + Math.sign(p.x - edge) * arrow * 0.6, p.y, z));
        }
      }
      const line = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat);
      line.renderOrder = 5;
      g.add(line);
      const dir = new THREE.Vector3().subVectors(p2, p1);
      const len = dir.length();
      if (len > 1e-9) {
        dir.normalize();
        const head = Math.min(arrow, len * 0.3);
        const coneGeo = new THREE.ConeGeometry(head * 0.32, head, 10);
        const coneMat = new THREE.MeshBasicMaterial({ color, depthTest: false });
        for (const [p, d] of [[p2, dir], [p1, dir.clone().negate()]]) {
          const c = new THREE.Mesh(coneGeo, coneMat);
          c.position.copy(p).addScaledVector(d, -head / 2);
          c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d);
          c.renderOrder = 6;
          g.add(c);
        }
      }
      const el = makeLabel(a);
      const label = new CSS2DObject(el);
      label.position.copy(p1).add(p2).multiplyScalar(0.5);
      g.add(label);
      g.userData = { param: a.param, el, mat };
      this.annotationObjects[a.param] = g;
      this.dims.add(g);
    }
    this.syncDimsVisibility();
  }

  /** CSS2D labels only honour their own `visible` flag (not their parents'), so set it explicitly. */
  syncDimsVisibility() {
    const v = this.dimsVisible && !this.piecesShown;
    this.dims.visible = v;
    this.dims.traverse((o) => { if (o.isCSS2DObject) o.visible = v; });
    this.invalidate();
  }

  highlight(paramId, on) {
    this.invalidate();
    const g = this.annotationObjects?.[paramId];
    if (!g) return;
    g.userData.el.classList.toggle('hl', on);
    g.userData.mat.color.offsetHSL(0, 0, on ? 0.15 : -0.15);
  }

  setDimsVisible(v) {
    this.dimsVisible = v;
    this.syncDimsVisibility();
  }

  setWire(v) {
    this.invalidate();
    this.wire = v;
    if (this.mesh) this.mesh.visible = !v;
  }

  setView(name) {
    this.invalidate();
    if (!this.solution) return;
    const box = new THREE.Box3().setFromObject(this.piecesShown ? this.printGroup : this.part);
    const c = box.getCenter(new THREE.Vector3());
    const sz = box.getSize(new THREE.Vector3());
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const fitW = sz.x * 1.25 / (2 * Math.tan(fov / 2) * this.camera.aspect);
    const fitH = Math.max(sz.y, sz.z) * 1.35 / (2 * Math.tan(fov / 2));
    const s = Math.max(sz.x, sz.y, sz.z);
    const d = Math.max(fitW, fitH, s * 0.5);
    const dirs = {
      iso: new THREE.Vector3(0.18, -0.55, 1),
      front: new THREE.Vector3(0, -0.0001, 1),
      back: new THREE.Vector3(0, 0.0001, -1),
      side: new THREE.Vector3(1, -0.25, 0.25),
    };
    const flat = name === 'front' || name === 'back';
    const dir = (dirs[name] || dirs.iso).clone().normalize();
    this.camera.up.set(0, flat ? 1 : 0, flat ? 0 : 1);
    this.camera.position.copy(c).addScaledVector(dir, d * (name === 'iso' ? 1.15 : 1));
    this.camera.near = s / 1000;
    this.camera.far = s * 100;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(c);
    this.controls.update();
  }

  // ------------------------------------------------------------------ picking
  ray(clientX, clientY) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    return ray;
  }

  /** Ray-cast a screen point onto a face plane; returns model {x, y} or null. */
  pickFace(clientX, clientY, face) {
    if (!this.solution) return null;
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -this.planeZ(face));
    const hit = new THREE.Vector3();
    if (!this.ray(clientX, clientY).ray.intersectPlane(plane, hit)) return null;
    return { x: hit.x, y: hit.y };
  }

  /** Ray-cast a screen point onto the part itself: {x, y, z, normal, snap} or null.
   *  Snaps to a corner of the part within 10 px, and on walls to the height of a face edge
   *  (z_levels) within 8 px; on a flat face z is that face's height. */
  pickSurface(clientX, clientY) {
    if (!this.mesh || !this.solution || this.solution.bent || this.piecesShown) return null;
    const hits = this.ray(clientX, clientY).intersectObject(this.mesh, false);
    if (!hits.length) return null;
    const h = hits[0], n = h.face.normal;
    const pos = this.mesh.geometry.attributes.position;
    const v = new THREE.Vector3(), q = new THREE.Vector3();
    let p = h.point.clone(), snap = 'surface', best = 10;
    // the nearest corner of the part on screen (any triangle, so edges between faces snap too),
    // unless it is hidden behind the surface under the cursor
    const box = this.renderer.domElement.getBoundingClientRect();
    const mx = ((clientX - box.left) / box.width) * 2 - 1, my = -((clientY - box.top) / box.height) * 2 + 1;
    const kx = box.width / 2, ky = box.height / 2;
    const cam = this.camera.position, reach = h.distance + this.size * 0.01;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      q.copy(v).project(this.camera);
      const d = Math.hypot((q.x - mx) * kx, (q.y - my) * ky);
      if (d < best && v.distanceTo(cam) <= reach) { best = d; p = v.clone(); snap = 'corner'; }
    }
    const levels = this.solution.z_levels || [this.zRange[0], this.zRange[1]];
    if (snap !== 'corner') {
      if (Math.abs(n.z) > 0.9) {
        // a flat face: exactly its height
        const z = levels.reduce((a, b) => (Math.abs(b - p.z) < Math.abs(a - p.z) ? b : a), p.z);
        if (Math.abs(z - p.z) < this.size * 1e-3) p.z = z;
        snap = n.z > 0 ? 'top face' : 'bottom face';
      } else {
        let bestD = 8;
        for (const z of levels) {
          const s = this.toScreen(p.x, p.y, z);
          const d = Math.hypot(s.x - clientX, s.y - clientY);
          if (d < bestD) { bestD = d; p.z = z; snap = 'edge'; }
        }
        if (snap !== 'edge') snap = 'wall';
      }
    }
    const r = (x) => Math.round(x * 1e6) / 1e6;
    return { x: r(p.x), y: r(p.y), z: r(p.z), normal: [n.x, n.y, n.z], snap };
  }

  /** The measure tool: points (1 or 2) and, with two, the line between them with a label. */
  setMeasure(points, text) {
    this.invalidate();
    if (!this.measureGroup) { this.measureGroup = new THREE.Group(); this.scene.add(this.measureGroup); }
    this.clearGroup(this.measureGroup);
    if (!points?.length) return;
    const v = points.map((p) => new THREE.Vector3(p.x, p.y, p.z));
    for (const p of v) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(this.size * 0.006, 12, 8), new THREE.MeshBasicMaterial({ color: 0x39d0d8, depthTest: false }));
      m.position.copy(p);
      m.renderOrder = 10;
      this.measureGroup.add(m);
    }
    if (v.length === 2) {
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(v), new THREE.LineBasicMaterial({ color: 0x39d0d8, depthTest: false }));
      line.renderOrder = 10;
      this.measureGroup.add(line);
      // the axis-aligned legs (dx, dy, dz) as a dashed path
      const [a, b] = v;
      const legs = [a, new THREE.Vector3(b.x, a.y, a.z), new THREE.Vector3(b.x, b.y, a.z), b];
      const dash = new THREE.Line(new THREE.BufferGeometry().setFromPoints(legs),
        new THREE.LineDashedMaterial({ color: 0x39d0d8, dashSize: this.size / 120, gapSize: this.size / 200, depthTest: false, transparent: true, opacity: 0.6 }));
      dash.computeLineDistances();
      dash.renderOrder = 9;
      this.measureGroup.add(dash);
      if (text) {
        const el = document.createElement('div');
        el.className = 'measure-label';
        el.textContent = text;
        const lab = new CSS2DObject(el);
        lab.position.copy(a).add(b).multiplyScalar(0.5);
        this.measureGroup.add(lab);
      }
    }
  }

  /** Picking feedback: a dot at `p` with a small label (or nothing). */
  setMarker(p, text) {
    this.invalidate();
    if (!this.markers) { this.markers = new THREE.Group(); this.scene.add(this.markers); }
    this.clearGroup(this.markers);
    if (!p) return;
    const m = new THREE.Mesh(new THREE.SphereGeometry(this.size * 0.007, 14, 10), new THREE.MeshBasicMaterial({ color: 0xf2cc60, depthTest: false }));
    m.position.set(p.x, p.y, p.z);
    m.renderOrder = 10;
    this.markers.add(m);
    if (text) {
      const el = document.createElement('div');
      el.className = 'pick-label';
      el.textContent = text;
      const lab = new CSS2DObject(el);
      lab.position.set(p.x, p.y, p.z);
      lab.center.set(-0.08, 1.2);
      this.markers.add(lab);
    }
  }

  /** Model point (x, y, z) -> client pixel coordinates. */
  toScreen(x, y, z) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const v = new THREE.Vector3(x, y, z).project(this.camera);
    return { x: r.left + ((v.x + 1) / 2) * r.width, y: r.top + ((1 - v.y) / 2) * r.height };
  }

  /** Dimension-tool feedback: highlighted edges/points and a preview dimension. */
  setHelpers({ segments = [], points = [], preview = null } = {}) {
    this.invalidate();
    this.clearGroup(this.helpers);
    if (!this.solution) return;
    const z = this.solution.thickness + this.size * 0.002;
    const mat = new THREE.LineBasicMaterial({ color: 0xff2d95, depthTest: false });
    if (segments.length) {
      const pts = segments.flatMap(([a, b]) => [new THREE.Vector3(a[0], a[1], z), new THREE.Vector3(b[0], b[1], z)]);
      const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat);
      l.renderOrder = 9;
      this.helpers.add(l);
    }
    const r = this.size * 0.006;
    for (const p of points) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff2d95, depthTest: false }));
      m.position.set(p[0], p[1], z);
      m.renderOrder = 9;
      this.helpers.add(m);
    }
    if (preview) {
      const pm = new THREE.LineDashedMaterial({ color: 0xa371f7, dashSize: this.size / 120, gapSize: this.size / 240, depthTest: false });
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(preview[0][0], preview[0][1], z), new THREE.Vector3(preview[1][0], preview[1][1], z)]), pm);
      l.computeLineDistances();
      l.renderOrder = 9;
      this.helpers.add(l);
    }
  }

  // ------------------------------------------------------------------ printing
  /** Show the printer's build volume next to / around the part (sizes in model units). */
  setBuildVolume(vol) {
    this.buildVolume = vol;
    if (!this.piecesShown) this.renderBuildVolume();
  }

  _volumeBox(vx, vy, vz, at, color) {
    const g = new THREE.Group();
    const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(vx, vy, vz)),
      new THREE.LineDashedMaterial({ color, dashSize: vx / 60, gapSize: vx / 90, transparent: true, opacity: 0.8 }));
    box.computeLineDistances();
    box.position.set(at[0] + vx / 2, at[1] + vy / 2, at[2] + vz / 2);
    g.add(box);
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(vx, vy),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }));
    plate.position.set(at[0] + vx / 2, at[1] + vy / 2, at[2] - this.size * 0.0005);
    g.add(plate);
    return g;
  }

  renderBuildVolume() {
    this.invalidate();
    this.clearGroup(this.printGroup);
    const v = this.buildVolume;
    if (!v || !this.solution) return;
    const [x0, y0] = this.solution.bbox3 || this.solution.bbox;
    this.printGroup.add(this._volumeBox(v.x, v.y, v.z, [x0 - v.margin, y0 - v.margin, this.zRange[0]], v.fits ? 0x3fb950 : 0xf85149));
  }

  /** Exploded view of split pieces, each on its own build plate. */
  showPieces(pieces, vol, connectors = [], seams = []) {
    this.invalidate();
    this.piecesShown = !!pieces?.length;
    this.clearGroup(this.printGroup);
    this.part.visible = !this.piecesShown;
    this.syncDimsVisibility();
    this.overlay.visible = !this.piecesShown;
    if (!this.piecesShown) { this.renderBuildVolume(); return; }
    const gap = this.size * 0.08;
    const xs = [...new Set(pieces.map((p) => p.rect[0]))].sort((a, b) => a - b);
    const ys = [...new Set(pieces.map((p) => p.rect[1]))].sort((a, b) => a - b);
    const offsets = {};
    pieces.forEach((p, i) => {
      const color = new THREE.Color(PIECE_COLORS[i % PIECE_COLORS.length]);
      const geo = this.buildGeometry(p.mesh, (tag) => (tag ? color.clone().offsetHSL(0, 0, -0.2) : color));
      const g = new THREE.Group();
      g.add(new THREE.Mesh(geo, this.material));
      g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), this.edgeMaterial));
      const ox = xs.indexOf(p.rect[0]) * gap, oy = ys.indexOf(p.rect[1]) * gap;
      g.position.set(ox, oy, 0);
      const fits = p.orientation !== 'too big';
      const rot = p.orientation === 'rotated';
      const [vx, vy] = rot ? [vol.y, vol.x] : [vol.x, vol.y];
      // plate under the piece's actual mesh (bent pieces are not where their flat rectangle was)
      geo.computeBoundingBox();
      const bb = geo.boundingBox;
      const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2;
      g.add(this._volumeBox(vx, vy, vol.z * 0.15, [cx - vx / 2, cy - vy / 2, bb.min.z], fits ? 0x3fb950 : 0xf85149));
      const tag = document.createElement('div');
      tag.className = `piece-tag${fits ? '' : ' bad'}`;
      tag.textContent = `#${p.index}  ${p.size_mm[0].toFixed(0)}×${p.size_mm[1].toFixed(0)} mm${rot ? ' ⟲90°' : ''}`;
      const lbl = new CSS2DObject(tag);
      lbl.position.set(cx, cy, bb.max.z + this.size * 0.02);
      g.add(lbl);
      this.printGroup.add(g);
      offsets[p.index] = [ox, oy];
    });

    // connector parts: between the two pieces they join; keys/plates lifted off their face
    const connColor = new THREE.Color(0xf2cc60);
    for (const grp of connectors || []) {
      for (const inst of grp.instances) {
        const seam = seams?.[inst.seam];
        const [a, b] = (seam?.pieces || []).map((idx) => offsets[idx] || [0, 0]);
        const geo = this.buildGeometry(inst.mesh, () => connColor);
        const m = new THREE.Group();
        m.add(new THREE.Mesh(geo, this.material));
        m.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), this.edgeMaterial));
        m.position.set(((a?.[0] ?? 0) + (b?.[0] ?? 0)) / 2, ((a?.[1] ?? 0) + (b?.[1] ?? 0)) / 2,
          inst.lift * this.size * 0.06);
        this.printGroup.add(m);
      }
    }
  }

  exportGLB(toMetres = 1) {
    return new Promise((resolve, reject) => {
      const root = new THREE.Group();
      const part = this.part.clone();
      part.scale.setScalar(toMetres);
      part.rotation.x = -Math.PI / 2; // glTF is Y-up
      root.add(part);
      new GLTFExporter().parse(root, resolve, reject, { binary: true });
    });
  }
}
