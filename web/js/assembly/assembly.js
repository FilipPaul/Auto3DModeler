// The assembly workspace: 3D model parts of the project placed together — insert a part, snap it face to face onto
// another one with joints that hold (touch, gap, flush, concentric, parallel, perpendicular, angle, tangent —
// joints.js), put a screw (+ nut / insert) or a pin through parts, drilling their holes, move it and turn it to any
// angle, an exploded view, a parts list with masses, export the whole as STL or STEP. No motion (parts do not move).
//
// Assembly JSON (in the project file, `parts[].assembly`):
//   {"instances": [{"id": "I1", "part": "P2", "matrix": [16 numbers, three.js column-major]}],
//    "mates": [{"id": "J1", "type": "touch" | "gap" | "flush" | "axis" | "parallel" | "perp" | "angle" | "tangent",
//               "move": "I2", "face": "F2:start", "onto": "I1", "ontoFace": "F2:end", "gap": 0, "value": 30, "flip": false,
//               "angle": 0 (its turn locked there), "name": "bearing on the shaft" (the user's own)}],
//    "bolts": [{"id": "B1", "text": "M3×20 screw + M3 nut", "holes": [{"part": "P2", "feature": {the hole step drilled}}]}]}
//   an instance's "travel": {"J2:along": {"min": 0, "max": 25}} — the limits of a free motion (motionsOf keys)
//   a placed sub-assembly's "inner": {"I2": [16 numbers]} — its parts moved inside it by its own joints, in this
//   placement only (in the sub-assembly's frame; innerAsm / keepInner); its own document stays as it is
//   "light": {"P3": true | false} — 🪶 a part shown simplified (true) or with full data (false); not said: a big
//   imported part (thousands of faces) is simplified
//   an instance's "moveNames": {"J3:turn": "crank"} — a free motion's own name (nameMotion); "mechs": the ⚙ Mechanism
//   widget's names, drivers and speeds (mechanism.js); "couplings": ⚙ gear pairs, ⛓ belts, ▤ racks — one part's turn
//   tied to another's by a ratio (couplings.js)
import * as THREE from 'three';
import { History } from '../history.js';
import { t } from '../i18n.js';
import { toolGroup } from '../toolgroups.js';
import { fitBar } from '../compactbar.js';
import { renameInPlace } from '../rename.js';
import { paintedFaces, repaint } from '../modeler/paint.js';
import { sectionBar, sectionMiddle } from '../modeler/sectionbar.js';
import { ModelView } from '../modeler/view.js';
import { accelerate } from '../modeler/bvh.js';
import { fetchRebuild } from '../modeler/packed.js';
import { newRid, trackProgress, cancelRid, wasCancelled } from '../progressbox.js';
import { threadSegments } from '../modeler/view.js';
import { JOINT_TYPES, applyJoint, spinOf, axialGap, jointMiss } from './joints.js';
import { snapNear, snapPoints } from '../modeler/view.js';
import { showSuggest, showSnapFilters, snapKinds, hoverKinds } from '../suggest.js';
import { floatBox } from '../floatbox.js';
import { freeMotions, motionMatrix } from './dof.js';
import { findLoops, solveLoop, loopFreedom, worstMiss, screwBetween, stepsBetween } from './loops.js';
import { fastenerModel, findCandidates, planBolt, isStandard, BOLT_KINDS, SIZES } from './fasteners.js';
import { MATERIALS } from '../modeler/modeler.js';
import { lookColor, finishOf, cogText } from '../modeler/materials.js';
import { exprField } from '../paramsui.js';
import { stepTree } from './stepfile.js';
import { bomOf, bomCsv, instanceTree } from './bom.js';
import { openBomWindow } from './bomview.js';
import { kindIcon, fromLibrary } from '../parts.js';
import { MechanismPanel, driveTo } from './mechanism.js';
import { saveAnimation } from './anim.js';
import { startDrag } from './drag.js';
import { isPin } from './missing.js';
import { COUPLING_TYPES, couplingOptions, addCoupling, followCouplings, couplingsHtml, bindCouplingRows, couplingsSummary, ratioText, coupledWith } from './couplings.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const ID = () => new THREE.Matrix4().identity().toArray();
const tidy = (a) => a.map((v) => (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v) : +v.toFixed(9))); // (a matrix: whole numbers kept whole)
const COLORS = [0xd9dee6, 0x9ecbff, 0xffd8a8, 0xb5f5c5, 0xe2c6ff, 0xffc2c2, 0xfff3b0];

const b64 = (s, T) => { // (a binary answer's arrays come as typed arrays already: modeler/packed.js)
  if (typeof s !== 'string') return s;
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};

/** The 3D view with several parts, each with its own placement. */
class AsmView extends ModelView {
  setBodies(list) {
    // each body's triangles, normals and edge lines are made once and kept while it is drawn (a hover, the explode
    // slider, a part chosen draw everything again: only the materials and placements change)
    const was = this.shapes || new Map();
    this.shapes = new Map();
    for (const o of [...this.bodyGroup.children]) this.bodyGroup.remove(o);
    this.meshes = [];
    let box = null;
    for (const it of list) {
      if (!it.body) continue;
      let sh = this.shapes.get(it.body) || was.get(it.body);
      if (!sh) {
        const base = new THREE.BufferGeometry(), seg = [];
        base.setAttribute('position', new THREE.BufferAttribute(b64(it.body.positions, Float32Array), 3));
        base.computeVertexNormals();
        for (const { pts: pl } of it.body.edges) for (let i = 0; i + 5 < pl.length; i += 3) seg.push(pl[i], pl[i + 1], pl[i + 2], pl[i + 3], pl[i + 4], pl[i + 5]);
        const eg = new THREE.BufferGeometry();
        eg.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
        sh = { base, ids: b64(it.body.face_ids, Uint32Array), edges: eg, coloured: new Map(), threads: null };
      }
      this.shapes.set(it.body, sh);
      const pos = sh.base.attributes.position.array, ids = sh.ids;
      let geo = sh.base;
      const o = Number.isFinite(it.opacity) ? it.opacity : 1;
      // a chosen part keeps its own colours and painted faces: it glows blue (it was drawn all blue — its look hidden)
      const fin = it.finish || { metalness: 0.05, roughness: 0.55 }; // (a metal part: metallic)
      const mat = new THREE.MeshStandardMaterial({ color: it.colour || COLORS[it.color % COLORS.length], roughness: fin.roughness, metalness: fin.metalness, envMapIntensity: fin.metalness > 0.5 ? 1 : 0.35,
        side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, emissive: it.clash ? 0x6a0d0d : it.selected ? 0x1e4f86 : it.hover ? 0x1b2a44 : 0x000000,
        transparent: o < 1, opacity: o, depthWrite: o >= 1, clippingPlanes: this.clip || [] });
      const painted = paintedFaces(it.body.faces, it.paint || []);
      const fromFile = !it.ownColour ? it.body.faces.filter((f) => f.color) : [];
      const lit = it.lit ? it.body.faces.filter((f) => f.name.startsWith(it.lit)) : []; // (a part inside a sub-assembly chosen in the list)
      if (painted?.size || fromFile.length || lit.length) { // faces painted in their part, or coloured in its STEP file
        const base = new THREE.Color(it.colour || COLORS[it.color % COLORS.length]);
        const key = `${base.getHexString()}|${fromFile.length}|${it.lit || ''}|${[...(painted || [])].map(([id, p]) => `${id}:${p.color}`).join()}`;
        geo = sh.coloured.get(key);
        if (!geo) { // (its colours: made once for these colours; the same positions and normals)
          const col = new Float32Array(pos.length), byId = new Map(fromFile.map((f) => [f.id, new THREE.Color(f.color)]));
          for (const [id, p] of painted || []) byId.set(id, new THREE.Color(p.color));
          for (const f of lit) byId.set(f.id, new THREE.Color(0x3b82f6));
          for (let tr = 0; tr < ids.length; tr++) {
            const c = byId.get(ids[tr]) || base;
            for (let k = 0; k < 3; k++) col.set([c.r, c.g, c.b], tr * 9 + k * 3);
          }
          geo = new THREE.BufferGeometry();
          geo.setAttribute('position', sh.base.attributes.position);
          geo.setAttribute('normal', sh.base.attributes.normal);
          geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
          if (sh.coloured.size >= 6) { for (const g of sh.coloured.values()) g.dispose(); sh.coloured.clear(); }
          sh.coloured.set(key, geo);
        }
        mat.vertexColors = true;
        mat.color.set(0xffffff);
      }
      const mesh = accelerate(new THREE.Mesh(geo, mat));
      mesh.matrixAutoUpdate = false;
      mesh.matrix.fromArray(it.matrix);
      if (it.explode) mesh.matrix.premultiply(new THREE.Matrix4().makeTranslation(...it.explode));
      mesh.userData = { inst: it.id, faceIds: ids, body: it.body };
      this.bodyGroup.add(mesh);
      const lines = new THREE.LineSegments(sh.edges, this.edgeMaterial);
      lines.matrixAutoUpdate = false;
      lines.matrix.copy(mesh.matrix);
      this.bodyGroup.add(lines);
      if (it.threads === 'cosmetic' && !sh.threads) { // 🔩 its part's cosmetic threads
        const thr = threadSegments(it.body.threads);
        sh.threads = new THREE.BufferGeometry();
        sh.threads.setAttribute('position', new THREE.Float32BufferAttribute(thr, 3));
      }
      if (it.threads === 'cosmetic' && sh.threads.attributes.position.count) {
        const tl = new THREE.LineSegments(sh.threads, this.threadMaterial);
        tl.matrixAutoUpdate = false;
        tl.matrix.copy(mesh.matrix);
        this.bodyGroup.add(tl);
      }
      this.meshes.push(mesh);
      mesh.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(mesh);
      box = box ? box.union(bb) : bb;
    }
    for (const [body, sh] of was) { // (bodies no longer drawn: their shapes freed)
      if (this.shapes.has(body)) continue;
      for (const g of [sh.base, sh.edges, sh.threads, ...sh.coloured.values()]) g?.dispose();
    }
    this.mesh = this.meshes[0] || null; // fitting the view, the origin size
    this.clearHoverMarks(); // (the parts drawn anew: the hover marks were on the old ones)
    if (box) { const s = box.getSize(new THREE.Vector3()); this.size = Math.max(s.x, s.y, s.z, 1); this.sizeOrigin(); }
    this.showDatums(!this.meshes.length);
    this.invalidate();
  }

  /** ✂ The section: the same cut on every part (and on the marks over them). */
  setSection(sec) {
    super.setSection(sec);
    this.clip = this.material.clippingPlanes;
    for (const g of [this.bodyGroup, this.markGroup]) g?.traverse((o) => { if (o.material && o.material !== this.edgeMaterial) { o.material.clippingPlanes = this.clip; o.material.needsUpdate = true; } });
    this.invalidate();
  }

  /** ⚠ Where parts overlap: red boxes ([x0, y0, z0, x1, y1, z1] each). */
  setClashBoxes(boxes = []) {
    if (!this.clashGroup) { this.clashGroup = new THREE.Group(); this.scene.add(this.clashGroup); }
    this.clear(this.clashGroup);
    for (const b of boxes) {
      if (b?.length !== 6) continue;
      const box = new THREE.Box3(new THREE.Vector3(b[0], b[1], b[2]), new THREE.Vector3(b[3], b[4], b[5]));
      if (box.getSize(new THREE.Vector3()).length() < 1e-6) continue;
      const h = new THREE.Box3Helper(box, 0xff4d4d);
      h.material.depthTest = false;
      h.renderOrder = 9;
      this.clashGroup.add(h);
      const fill = new THREE.Mesh(new THREE.BoxGeometry(...box.getSize(new THREE.Vector3()).toArray().map((v) => Math.max(v, 0.05))),
        new THREE.MeshBasicMaterial({ color: 0xff4d4d, transparent: true, opacity: 0.35, depthTest: false }));
      fill.position.copy(box.getCenter(new THREE.Vector3()));
      fill.renderOrder = 8;
      this.clashGroup.add(fill);
    }
    this.invalidate();
  }

  /** The camera onto a box ([x0, y0, z0, x1, y1, z1]), looking from where it looks now — close, with room round it. */
  focusBox(b) {
    const box = new THREE.Box3(new THREE.Vector3(b[0], b[1], b[2]), new THREE.Vector3(b[3], b[4], b[5]));
    const c = box.getCenter(new THREE.Vector3()), s = Math.max(box.getSize(new THREE.Vector3()).length() * 3, 30);
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    this.controls.target.copy(c);
    this.camera.position.copy(c).addScaledVector(dir.lengthSq() ? dir : new THREE.Vector3(0.55, -0.9, 0.7).normalize(), s);
    this.controls.update();
    this.invalidate();
  }

  /** The box round every placed part as shown (exploded too) -> [x0, y0, z0, x1, y1, z1] or null. */
  shownBox() {
    if (!this.meshes?.length) return null;
    const b = new THREE.Box3();
    for (const m of this.meshes) b.union(new THREE.Box3().setFromObject(m));
    return [b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z].map((v) => +v.toFixed(3));
  }

  /** Faces drawn over in a colour: [{inst, faces: [face ids], color}] (the face under the mouse, a part's joints). */
  setMarks(marks = []) {
    if (!this.markGroup) { this.markGroup = new THREE.Group(); this.scene.add(this.markGroup); }
    this.clear(this.markGroup);
    for (const mk of marks) {
      const mesh = (this.meshes || []).find((m) => m.userData.inst === mk.inst);
      if (!mesh) continue;
      const want = new Set(mk.faces), pos = mesh.geometry.attributes.position.array, ids = mesh.userData.faceIds, out = [];
      for (let t = 0; t < ids.length; t++) if (want.has(ids[t])) for (let k = 0; k < 9; k++) out.push(pos[t * 9 + k]);
      if (!out.length) continue;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(out, 3));
      const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: mk.color, transparent: true, opacity: 0.75, side: THREE.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, depthWrite: false, clippingPlanes: this.clip || [] }));
      m.matrixAutoUpdate = false;
      m.matrix.copy(mesh.matrix);
      this.markGroup.add(m);
    }
    this.invalidate();
  }

  /** See-through standard parts before they go in: [{o, d, len, r, sides, color}] (a cylinder from o along d). */
  setGhost(list = []) {
    if (!this.ghostGroup) { this.ghostGroup = new THREE.Group(); this.scene.add(this.ghostGroup); }
    this.clear(this.ghostGroup);
    for (const g of list) {
      const d = new THREE.Vector3(...g.d).normalize();
      const m = new THREE.Mesh(new THREE.CylinderGeometry(g.r, g.r, g.len, g.sides || 24),
        new THREE.MeshBasicMaterial({ color: g.color || 0xf2cc60, transparent: true, opacity: 0.6, depthTest: false }));
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d);
      m.position.set(...g.o).addScaledVector(d, g.len / 2);
      m.renderOrder = 5;
      this.ghostGroup.add(m);
    }
    this.invalidate();
  }

  fitBox() {
    const box = new THREE.Box3();
    for (const m of this.meshes || []) box.expandByObject(m);
    return box.isEmpty() ? new THREE.Box3().setFromObject(this.datumGroup) : box;
  }

  /** For 📏 Measure: the spot under the mouse — a corner of a part's edge when one is near (10 px), else the point on
   *  the face — with that face (world) and the part: {point, corner, face, inst} or null. */
  measurePoint(clientX, clientY, px = 10) {
    const h = this.pickInst(clientX, clientY), r = this.renderer.domElement.getBoundingClientRect();
    const s = snapNear((this.meshes || []).map((m) => ({ edges: m.userData.body.edges, matrix: m.matrix, inst: m.userData.inst })), this.camera, r, clientX, clientY, px, snapKinds());
    if (!s && !h?.point) return null;
    return { point: s ? s.point : h.point.clone(), corner: s?.kind === 'corner', snap: s?.kind || null, face: s ? null : h?.face || null, inst: s ? s.inst : h.inst };
  }

  /** A round edge near the mouse (within px): the edge of a hole or of a pin, seen as a circle — -> {inst, face: the
   *  round face it bounds (world coordinates), px} or null. Joints that want a round face take it (as in CAD: click
   *  the circle). */
  roundEdgeAt(clientX, clientY, px = 12) {
    const r = this.renderer.domElement.getBoundingClientRect(), v = new THREE.Vector3();
    const screen = (x, y, z, m) => { v.set(x, y, z).applyMatrix4(m).project(this.camera); return [(v.x + 1) / 2 * r.width + r.left, (1 - v.y) / 2 * r.height + r.top, v.z]; };
    let best = null;
    for (const mesh of this.meshes || []) {
      const { inst, body } = mesh.userData, m = mesh.matrix;
      for (const e of body.edges || []) {
        const cyl = (e.faces || []).map((i) => body.faces[i]).find((f) => f?.type === 'cylinder');
        if (!cyl) continue;
        const p = e.pts;
        let prev = screen(p[0], p[1], p[2], m);
        for (let k = 3; k + 2 < p.length; k += 3) {
          const cur = screen(p[k], p[k + 1], p[k + 2], m);
          const dx = cur[0] - prev[0], dy = cur[1] - prev[1], L = dx * dx + dy * dy || 1;
          const tt = Math.max(0, Math.min(1, ((clientX - prev[0]) * dx + (clientY - prev[1]) * dy) / L));
          const d = Math.hypot(prev[0] + tt * dx - clientX, prev[1] + tt * dy - clientY);
          if (d < px && cur[2] < 1 && (!best || d < best.px)) best = { inst, body, cyl, m, px: d };
          prev = cur;
        }
      }
    }
    if (!best) return null;
    const nm = new THREE.Matrix3().getNormalMatrix(best.m);
    return { inst: best.inst, px: best.px, face: { ...best.cyl, centroid: new THREE.Vector3(...best.cyl.centroid).applyMatrix4(best.m),
      normal: best.cyl.normal ? new THREE.Vector3(...best.cyl.normal).applyMatrix3(nm).normalize() : null }, edge: true };
  }

  /** What is under the mouse: {inst, face (in world coordinates)} or null. */
  pickInst(clientX, clientY) {
    const h = this.ray(clientX, clientY).intersectObjects(this.meshes || [], false)[0];
    if (!h) return null;
    const { inst, faceIds, body } = h.object.userData, fid = faceIds[h.faceIndex];
    const f = body.faces[fid]?.id === fid ? body.faces[fid] : body.faces.find((x) => x.id === fid);
    if (!f) return { inst };
    const m = h.object.matrix, nm = new THREE.Matrix3().getNormalMatrix(m);
    const centroid = new THREE.Vector3(...f.centroid).applyMatrix4(m);
    const normal = f.normal ? new THREE.Vector3(...f.normal).applyMatrix3(nm).normalize() : null;
    return { inst, face: { ...f, centroid, normal }, point: h.point };
  }
}

export class Assembly {
  /** els: {left, viewport, right}; hooks: {toast, download, safeName, parts() -> [{id, name, kind, data}], partData(id), onChange} */
  constructor(els, hooks) {
    this.els = els;
    this.hooks = hooks;
    this.doc = { instances: [], mates: [] }; // mates: snaps that hold — {move, face, onto, ontoFace}
    this.bodies = {}; // part id -> {key, body, error}
    this.sel = null;
    this.mode = 'idle'; // 'idle' | 'joint-from' | 'joint-to' (picking the two faces of a new joint)
    this.jointType = 'touch';
    this.explode = 0;
    this.history = new History({
      capture: () => ({ instances: this.doc.instances, mates: this.doc.mates, bolts: this.doc.bolts || [], ...(this.doc.mechs?.length ? { mechs: this.doc.mechs } : {}), ...(this.doc.couplings?.length ? { couplings: this.doc.couplings } : {}) }),
      restore: async (s) => {
        this.mech?.stop(false);
        this.doc.instances = s.instances; this.doc.mates = s.mates || []; this.doc.bolts = s.bolts || []; this.mode = 'idle'; this.bolt = null;
        if (s.mechs) this.doc.mechs = s.mechs; else delete this.doc.mechs;
        if (s.couplings) this.doc.couplings = s.couplings; else delete this.doc.couplings;
        this.syncDrills(); // the holes drilled for bolts: back as they were
        this.tidyCopies(); // (⧉ its own part undone: its copy goes too)
        this.render();
        await this.refresh();
      },
      onChange: () => this.updateUndo(),
    });
    this.build();
    this.view = new AsmView(this.els.view, { cube: true });
    this.mech = new MechanismPanel(this); // (⚙ Mechanism: a widget of the left column while there is one)
    this.bindPointer();
    this.render();
    window.addEventListener('a3d:lang', () => this.render()); // (texts built with t(): in the new language)
  }

  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = `<div class="mt-head"><b>Assembly</b><span class="mt-sub">its parts</span></div><div class="as-list"></div>
      <div class="mt-start as-start" hidden><p><b>Put parts together</b></p><ol><li><b>＋ Insert part</b> — a 3D model of this project</li>
      <li><b>🔗 Join</b> — click a face of one part, Ctrl+click a face of the other, pick the joint (a pin in a hole: ◎ Concentric)</li>
      <li><b>⚙ Mechanism</b> — shows by itself once the joints let the parts move</li></ol></div>`;
    viewport.innerHTML = `<div class="m-cmdbar"></div><div class="m-hint" hidden></div><div class="m-view"></div><div class="m-status"></div>`;
    right.innerHTML = '<div class="mp-body"></div>';
    this.els.view = viewport.querySelector('.m-view');
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
  }

  render() { this.mech?.render(); this.renderBar(); this.renderList(); this.renderProps(); this.renderStatus(); this.renderSuggest(); showSnapFilters(this.els.viewport, this.doc.instances.length > 0); }

  /** The suggestions for faces picked with no tool on: one face — the joints it can start (then a face of another
   *  part); two faces of two parts (Ctrl+click) — the joints that fit them (two round: concentric; two flat: touch,
   *  flush, gap …; round and flat: tangent), made by a click. */
  suggestFaces(vp, fp) {
    const kindOf = (q) => (q.face.type === 'cylinder' ? 'round' : q.face.type === 'plane' ? 'flat' : 'other');
    const fits = (k1, k2) => Object.entries(JOINT_TYPES).filter(([, j]) => !j.pick && (
      (j.faces === 'plane' && k1 === 'flat' && (k2 === undefined || k2 === 'flat')) || (j.faces === 'cylinder' && k1 === 'round' && (k2 === undefined || k2 === 'round'))
      || (j.faces === 'mixed' && (k2 === undefined ? k1 !== 'other' : new Set([k1, k2]).size === 2 && ![k1, k2].includes('other')))));
    const what = (q) => `${this.partName(this.inst(q.inst)?.part)} ${q.inst} · ${this.faceText(q.inst, q.face.name)}`;
    const refs = `${t('in the assembly')} “${this.hooks.safeName?.() || ''}”: ${fp.map((q) => `${t('part')} ${q.inst} ${t('face')} ${q.face.name}${q.face.type === 'cylinder' && q.face.radius ? ` (${t('round')}, Ø${fmt(2 * q.face.radius)})` : q.face.type === 'plane' ? ` (${t('flat')})` : ''}`).join(', ')}`;
    const done = () => { this.facePicks = []; this.renderSuggest(); this.drawMarks(); };
    if (fp.length === 2 && kindOf(fp[0]) === 'round' && kindOf(fp[1]) === 'round') { // a pin in a hole: ◎ first, with its Ø
      const dia = fp.map((q) => fmt(+(2 * (q.face.radius || 0)).toFixed(2))), d = dia[0] === dia[1] ? `Ø${dia[0]}` : `Ø${dia[0]} ↔ Ø${dia[1]}`;
      const seat = this.seatPair(fp[0], fp[1]), cpl = this.couplingItems(fp, done); // (⚙ two gears that turn: first)
      showSuggest(vp, `${what(fp[0])} ↔ ${what(fp[1])}`, [
        ...cpl.filter((x) => x.rank < 0),
        ...(seat ? [{ icon: '◎', label: `${t('Concentric + seat')} · ${d}`, rank: 0, title: t('A pin in a hole: on one axis and down on the face around it (Concentric + Touch) — it can still turn'), run: () => { this.joinRound(fp, true); done(); } }] : []),
        { icon: '◎', label: `${t(seat ? 'Concentric only' : 'Concentric')} · ${d}`, rank: 1, title: t(JOINT_TYPES.axis.hint), run: () => { this.joinRound(fp, false); done(); } },
        ...cpl.filter((x) => x.rank >= 0),
      ], t("A joint between the two faces — the first one's part moves"), refs);
      return;
    }
    if (fp.length === 2) {
      const same = fp[0].face.normal && fp[1].face.normal && fp[0].face.normal.dot(fp[1].face.normal) > 0.999; // (facing the same way: ▭ Flush first, as they stand)
      const js = fits(kindOf(fp[0]), kindOf(fp[1])).sort(([a], [b]) => (same ? (b === 'flush') - (a === 'flush') : 0)), on = this.putOn(fp[0], fp[1]), cpl = this.couplingItems(fp, done);
      const put = on ? [{ icon: '⧉', label: t2('Put {a} on {b}', { a: this.partName(this.inst(on.move.inst)?.part), b: this.partName(this.inst(on.onto.inst)?.part) }), rank: -1,
        title: t('Its face on the other side (the underside) touches this face — no need to turn the view to click it'), run: () => {
          this.jointType = 'touch';
          this.mode = 'joint-to';
          this.jointFrom = on.move;
          this.clickJoint(on.onto);
          if (this.mode !== 'idle') this.cancelJoint();
          done();
        } }] : [];
      showSuggest(vp, `${what(fp[0])} ↔ ${what(fp[1])}`, [...put, ...cpl.filter((x) => x.rank < 0), ...js.map(([type, j]) => ({ icon: j.icon, label: t(j.name), title: t(j.hint || ''), run: () => {
        this.jointType = type; // (as if the two faces had been clicked with that joint)
        this.mode = 'joint-to';
        this.jointFrom = fp[0];
        this.clickJoint(fp[1]);
        if (this.mode !== 'idle') this.cancelJoint();
        done();
      } })), ...cpl.filter((x) => x.rank >= 0)], js.length ? t('A joint between the two faces — the first one\'s part moves') : t('No joint fits these two faces.'), refs);
      return;
    }
    const q = fp[0], js = fits(kindOf(q)), a = this.inst(q.inst);
    const after = (x) => ({ ...x, run: async () => { await x.run(); this.renderSuggest(); } });
    showSuggest(vp, what(q), [ // (the face's joints first, then its part: the table shows the top ones, the rest under ⋯ Show all)
      { section: t('This face') },
      ...js.map(([type, j], k) => ({ icon: j.icon, label: `${t(j.name)}…`, rank: ['parallel', 'perp', 'angle'].includes(type) ? 10 + k : k, title: t('Then click a face of the other part'), run: () => {
        this.startJoint(type);
        this.jointFrom = q;
        this.mode = 'joint-to';
        this.jointHint();
        this.facePicks = [];
        this.drawMarks();
      } })),
      { icon: '📏', label: t('Measure from here'), rank: 7, run: () => { done(); this.toggleMeasure(); } },
      { section: `${this.partName(a.part)} ${a.id}` },
      { icon: '◆', label: t('Select the whole part'), rank: 5, title: t('The part chosen, not its face: its moves and joints in the panel'), run: () => { this.facePicks = []; this.snapPick = null; this.view.setMeasure([]); this.choose(a.id); this.drawMarks(); } },
      ...this.partItems(a).map((x, k) => ({ ...after(x), rank: x.icon === '🔗' ? 20 : 8 + k })), // (joining: the face's own joints above)
    ], t('Ctrl+click a face of another part: the joints that fit the two'), refs);
  }

  /** Two picked faces of two parts that can be coupled (couplings.js): ⚙ a gear pair / ⛓ a belt (two round faces on
   *  parallel axes, apart), ▤ a rack and pinion (a round face and a flat face along its axis) — first in the list when
   *  both parts can move that way (turn about those axes; the rack: slide), with the ratio from their Ø. */
  couplingItems(picks, done) {
    if (picks.length !== 2 || picks[0].inst === picks[1].inst) return [];
    let fp;
    try { fp = picks.map((q) => ({ inst: q.inst, face: this.worldFace(q.inst, q.face.name) })); } catch { return []; } // (their axes in the world)
    const can = (q, kind, dir) => {
      let d = null;
      try { d = this.motionsOf(q.inst); } catch { d = null; }
      return !!d?.motions.some((mo) => mo.kind === kind && Math.abs(mo.dir.clone().normalize().dot(dir)) > (kind === 'turn' ? 0.999 : 0.9));
    };
    const pins = fp.map((q) => (q.face.type === 'cylinder' ? isPin(this.bodyOf(this.inst(q.inst))?.body, q.face.name) : null));
    return couplingOptions(fp[0].face, fp[1].face, pins).map((o) => {
      const ct = COUPLING_TYPES[o.type], cyl = fp.find((q) => q.face.type === 'cylinder'), flat = fp.find((q) => q.face.type === 'plane');
      const moves = o.type === 'rack'
        ? can(cyl, 'turn', cyl.face.axis.d) && can(flat, 'move', new THREE.Vector3().crossVectors(cyl.face.axis.d, flat.face.normal).normalize())
        : fp.every((q) => can(q, 'turn', q.face.axis.d));
      return { icon: ct.icon, label: `${t(ct.name)} · ${ratioText(o)}`, rank: (moves ? -1 : 6) + o.rank, title: t(ct.hint), run: () => { this.couple(fp[0], fp[1], o.type); done(); } };
    });
  }

  /** ⚙ A coupling made between two picked faces (couplings.js addCoupling) — one undo step, a word on what it does. */
  couple(qa, qb, type, ratio = null) {
    let c;
    try { c = addCoupling(this, qa, qb, type, ratio); } catch (e) { this.hooks.toast(e.message, 'warning', 5000); return null; }
    this.sel = c.a;
    this.sel2 = null;
    this.applyMates();
    this.hooks.toast(t2('{type} {id}: {a} ↔ {b}, {ratio} — turn either one, the other follows (⇄ in its row: the other way round; Ctrl+Z: back).', {
      type: t(COUPLING_TYPES[type].name), id: c.id, a: this.partName(this.inst(c.a)?.part), b: this.partName(this.inst(c.b)?.part), ratio: ratioText(c) }), 'ok', 5000);
    this.commit();
    return c;
  }

  /** The flat faces a round face (a hole, a pin) ends on — across its axis, bigger than the round face's own end (a
   *  pin's cap, a blind hole's bottom left out): [{name, face (world)}]. */
  roundEnds(q) {
    const b = this.bodyOf(this.inst(q.inst))?.body;
    if (!b || q.face.type !== 'cylinder' || !q.face.radius) return [];
    const own = new Set(b.faces.map((f, i) => (f.name === q.face.name ? i : -1)).filter((i) => i >= 0)), next = new Set();
    for (const e of b.edges || []) if ((e.faces || []).some((i) => own.has(i))) for (const i of e.faces) if (!own.has(i)) next.add(i);
    let axis;
    try { axis = this.worldFace(q.inst, q.face.name).axis.d; } catch { return []; }
    const disc = Math.PI * q.face.radius ** 2, names = [...new Set([...next].map((i) => b.faces[i]).filter((f) => f?.type === 'plane' && f.area > disc * 1.05).map((f) => f.name))];
    return names.map((name) => { try { return { name, face: this.worldFace(q.inst, name) }; } catch { return null; } })
      .filter((x) => x && Math.abs(x.face.normal.dot(axis)) > 0.999);
  }

  /** A pin in a hole (two round faces, the first one's part moves): the flat faces that seat it — the moving part's
   *  face at the round face's end onto the other part's, the pair that faces each other and is nearest along the axis
   *  -> {move: {inst, face}, onto: {inst, face}} or null (the moving part is joined already, both are 📌 fixed, a
   *  through hole in both: which faces is not clear). */
  seatPair(qa, qb) {
    let [a, b] = [qa, qb];
    if (this.inst(a.inst)?.fixed) [a, b] = [b, a];
    if (this.inst(a.inst)?.fixed || (this.doc.mates || []).some((m) => m.move === a.inst && !(m.onto === b.inst && m.type === 'axis'))) return null;
    const A = this.roundEnds(a), B = this.roundEnds(b);
    if (!A.length || !B.length || (A.length > 1 && B.length > 1)) return null;
    let best = null;
    for (const x of A) {
      for (const y of B) {
        const facing = x.face.normal.dot(y.face.normal) < 0, apart = Math.abs(x.face.centroid.clone().sub(y.face.centroid).dot(y.face.normal));
        const score = (facing ? 0 : 1e6) + apart;
        if (!best || score < best.score) best = { score, move: { inst: a.inst, face: x.face }, onto: { inst: b.inst, face: y.face } };
      }
    }
    return best && { move: best.move, onto: best.onto };
  }

  /** Two flat faces facing up the same way (a part's top and the base's top): the moving part's face on its other side
   *  (its underside — hard to click without turning the view) can touch the other face -> {move: {inst, face},
   *  onto: {inst, face}} or null. The moving part: the first one's, unless it is 📌 fixed. */
  putOn(qa, qb) {
    let [a, b] = [qa, qb];
    if (this.inst(a.inst)?.fixed) [a, b] = [b, a];
    if (this.inst(a.inst)?.fixed || a.inst === b.inst || a.face.type !== 'plane' || b.face.type !== 'plane' || !a.face.normal || !b.face.normal) return null;
    const n = a.face.normal;
    if (n.dot(b.face.normal) < 0.999 || n.z < 0.7) return null; // (faces up: a part put down on it, as on a table)
    const body = this.bodyOf(this.inst(a.inst))?.body;
    let best = null;
    for (const name of new Set((body?.faces || []).filter((f) => f.type === 'plane').map((f) => f.name))) {
      let f;
      try { f = this.worldFace(a.inst, name); } catch { continue; }
      if (f.normal.dot(n) > -0.999) continue;
      const depth = f.centroid.dot(n), key = depth - f.area * 1e-9; // (the farthest one back; the larger of two at the same depth)
      if (!best || key < best.key) best = { key, face: f };
    }
    return best && { move: { inst: a.inst, face: best.face }, onto: { inst: b.inst, face: b.face } };
  }

  /** ◎ Two round faces joined: Concentric — with `seat`, also Touch on the faces around them (a pin in a hole sits down
   *  on its face; Solid Edge's Insert). One undo step. */
  joinRound(fp, seat) {
    const before = new Set(this.unmet().map((m) => m.id)), nj = this.addJoint(fp[0], fp[1], 'axis');
    if (!nj) return;
    if (/:hole:/.test(nj.face) && /:hole:/.test(nj.ontoFace)) this.autoDistance(nj);
    this.applyMates();
    let tj = null;
    if (seat) {
      const s = this.seatPair({ inst: nj.move, face: this.worldFace(nj.move, nj.face) }, { inst: nj.onto, face: this.worldFace(nj.onto, nj.ontoFace) });
      if (s) { tj = this.addJoint(s.move, s.onto, 'touch'); this.applyMates(); }
    }
    this.sel = nj.move;
    this.sel2 = null;
    const fights = this.unmet().filter((m) => !before.has(m.id));
    if (fights.length) this.hooks.toast(t2('{type} added, but it fights another joint: {ids} no longer hold — see the red joint(s) in the panel.', { type: t(JOINT_TYPES.axis.name), ids: fights.map((m) => m.id).join(', ') }), 'warning', 7000);
    else if (tj) this.hooks.toast(t2('{a} + {b}: {part} sits on the face around the pin and can still turn (Ctrl+Z: back).', { a: t('Concentric'), b: t('Touch'), part: this.partName(this.inst(nj.move)?.part) }), 'ok', 4000);
    else this.hooks.toast(`${JOINT_TYPES.axis.name} — it now holds (change it or ✕ it in the panel).`, 'ok', 3000);
    this.commit();
  }

  /** The suggestions table (bottom left of the view) for the chosen part — or the two chosen with Ctrl+click. */
  renderSuggest() {
    const vp = this.els.viewport, a = this.inst(this.sel), b = this.inst(this.sel2);
    if (!a || this.mode !== 'idle' || this.measuring || this.painting || this.bolt) { showSuggest(vp, '', []); return; }
    const fp = (this.facePicks || []).filter((q) => this.inst(q.inst));
    if (fp.length) { this.suggestFaces(vp, fp); return; }
    const name = (it) => `${this.partName(it.part)} ${it.id}`;
    const refs = `${t('in the assembly')} “${this.hooks.safeName?.() || ''}”: ${[a, b].filter(Boolean).map((x) => `${t('part')} ${x.id} “${this.partName(x.part)}”`).join(', ')}`;
    const show = (title, items, hint) => showSuggest(vp, title, items.map((x) => ({ ...x, run: async () => { await x.run(); this.renderSuggest(); } })), hint, refs); // (an action started: the table follows)
    if (b) {
      show( `${this.partName(a.part)} ↔ ${this.partName(b.part)}`, [
        { icon: '🔗', label: t('Join them'), title: t('Pick a face of each — touch, gap, flush, a pin in a hole …'), run: () => this.startJoint('touch', a.id) },
        { icon: '📏', label: t('Measure between them'), run: () => this.toggleMeasure() },
        { icon: '⚠', label: t('Check for collisions'), run: () => this.checkClashes() },
        { icon: '◆', label: `${t('Only')} ${name(a)}`, run: () => this.choose(a.id) },
      ]);
      return;
    }
    const sp = this.snapPick?.inst === a.id ? this.snapPick : null, p = sp?.point;
    const xyz = p ? [p.x, p.y, p.z].map((v) => fmt(+v.toFixed(3))).join(', ') : '', kind = sp ? t({ corner: 'A corner', midpoint: 'An edge midpoint', centre: 'A centre', quadrant: 'A quadrant' }[sp.snap]) : '';
    show(sp ? `${name(a)} · ${kind}` : name(a), [
      ...(sp ? [
        { section: kind },
        { icon: '📏', label: t('Measure from here'), title: xyz, run: () => {
          this.snapPick = null;
          if (!this.measuring) this.toggleMeasure();
          this.measuring.a = { point: p, face: null, inst: a.id };
          this.view.setMeasure([p]);
          this.measureBox(`<div class="mm-rows"><b>${esc(kind)}</b><span>Of</span><b data-no-i18n>${esc(this.partName(a.part))} ${a.id}</b><span>${esc(t('Point'))}</span><b>${xyz}</b></div><p class="hint">${esc(t('Click a second spot for the distance.'))}</p>`);
        } },
        { icon: '⧉', label: t('Copy its coordinates'), title: xyz, run: () => { navigator.clipboard?.writeText(xyz).catch(() => {}); this.hooks.toast(`${t('Copied')}: ${xyz}`, 'info', 2500); } },
        { section: name(a) }] : []),
      ...this.partItems(a), // (the owner's choice: a click shows its actions in the table, as everywhere)
    ], t('Ctrl+click another part: what fits the two'));
  }

  /** What can be done with a placed part: open / edit its part, join, simplified, fix, its own part, take it out. */
  partItems(a) {
    const joined = (this.doc.mates || []).some((m) => m.move === a.id), model = this.kindOf(a.part) === 'model';
    const light = this.bodies[a.part]?.body?.light;
    return [ // (the most relevant first: join it, open / edit its part, fix it)
      { icon: '🔗', label: t(joined ? 'Join it to one more part' : 'Join it to another part'), run: () => this.startJoint('touch', a.id) },
      ...(this.mech?.list.some((m) => m.parts.includes(a.id)) ? [{ icon: '⚙', label: t('Drive the mechanism'), title: t('One slider moves the whole mechanism — ▶ plays it'), run: () => this.mech.open(a.id) }] : []),
      ...(this.hooks.openPart ? [{ icon: this.kindOf(a.part) === 'assembly' ? '◇' : '◆', label: t('Open its part'), title: t('Change it in its own tab (the assembly follows)'), run: () => this.hooks.openPart(a.part) }] : []),
      ...(this.hooks.editInPlace && model ? [this.editable(a.part)
        ? { icon: '✎', label: t('Edit it here'), title: t('Change its part here, the rest of the assembly see-through around it'), run: () => this.editInPlace(a.id) }
        : { icon: '🔓', label: t('Unlock and edit it here'), title: t('Its part can be changed from this assembly then'), run: () => { this.toggleEditable(a.part); this.editInPlace(a.id); } }] : []),
      { icon: '📌', label: t(a.fixed ? 'Free it (not fixed)' : 'Fix in place'), run: () => this.toggleFixed(a.id) },
      ...(model ? [{ icon: '🪶', label: t(light ? 'Show it in full' : 'Show it simplified'), title: t('Simplified: a coarser mesh and less data — quicker to load and show'), run: async () => { this.doc.light = { ...(this.doc.light || {}), [a.part]: !light }; await this.refresh(); this.commit(); } }] : []),
      ...(this.hooks.duplicatePart ? [{ icon: '⧉', label: t('Make it its own part'), title: t('A copy of its part for this place only'), run: () => this.ownPart(a.id) }] : []),
      { icon: '✕', label: t('Take it out'), danger: true, run: () => this.removeInst(a.id) },
    ];
  }

  /** The parts that can go in: 3D models, and quick parts (drawings, pictures, imports) with a shape. */
  modelParts() {
    const self = this.hooks.selfId?.();
    return this.hooks.parts().filter((p) => p.kind === 'model' || (p.kind === 'classic' && this.hooks.partData(p.id)?.model)
      || (p.kind === 'assembly' && p.id !== self && !this.contains(p.id, self)));
  }

  /** Does assembly `pid` hold `target` (directly or in its own sub-assemblies)? */
  contains(pid, target, seen = new Set()) {
    if (!target || seen.has(pid)) return false;
    seen.add(pid);
    const data = this.hooks.partData(pid);
    return (data?.instances || []).some((i) => i.part === target || (this.kindOf(i.part) === 'assembly' && this.contains(i.part, target, seen)));
  }

  kindOf(pid) { return this.hooks.parts().find((p) => p.id === pid)?.kind; }

  /** A part's icon in the tree: the project tree's (a library part as it came: the library's). */
  partIcon(pid) {
    const kind = this.kindOf(pid);
    let lib = false;
    try { lib = kind === 'model' && fromLibrary(this.hooks.partData(pid)); } catch { /* (no data yet) */ }
    return kindIcon(lib ? 'library' : kind);
  }

  /** A part's steps for the CAD kernel: a 3D model's own; a quick part as one solid (its STEP export). */
  async partFeatures(pid, data) {
    const p = this.hooks.parts().find((q) => q.id === pid);
    if (p?.kind !== 'classic') return data.features || [];
    const res = await fetch('/api/export/step', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: data.model, values: data.values, layers: data.layers, bends: data.bends }) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || 'The quick part could not be made solid.');
    const bytes = new Uint8Array(await res.arrayBuffer());
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return [{ id: 'Q1', type: 'solid', name: p.name, step: btoa(bin) }];
  }
  partName(id) { return this.hooks.parts().find((p) => p.id === id)?.name || id; }
  inst(id) { return this.doc.instances.find((i) => i.id === id); }

  /** A placed part's body: a sub-assembly whose parts were moved inside it (its `inner`) has its own. */
  bodyOf(it) { return (it?.inner && this.bodies[this.bodyKey(it)]) || this.bodies[it?.part]; }
  bodyKey(it) { return `${it.part}@${JSON.stringify(it.inner)}`; }

  /** A placed sub-assembly's own parts, where they stand in this placement: its `inner` {id: matrix} (moved here, in
   *  the sub-assembly's frame) over the matrices of the sub-assembly's document. */
  innerList(it) { return (this.hooks.partData(it.part)?.instances || []).map((i) => (it.inner?.[i.id] ? { ...i, matrix: it.inner[i.id] } : i)); }

  renderBar() {
    const bar = this.$('.m-cmdbar');
    const btn = (a, label, title, cls = '') => `<button class="chip ${cls} ${toolGroup(a)}" data-a="${a}" title="${esc(title)}">${label}</button>`;
    const parts = this.modelParts();
    bar.innerHTML = `
      <div class="menu as-insert">${btn('insert', '＋ Insert part ▾', parts.length ? 'Add a part of this project: a 3D model ◆, a quick part ▤ (drawing, picture, import) or another assembly ◇ (as one unit)' : 'Make a part first (＋ New 3D model, or open a drawing / picture)', 'tool')}
        <div class="menu-list">${parts.map((p) => `<button data-part="${p.id}" data-no-i18n>${p.kind === 'classic' ? '▤' : p.kind === 'assembly' ? '◇' : '◆'} ${esc(p.name)}</button>`).join('') || '<div class="hint">No parts yet</div>'}
          ${this.hooks.importFile ? '<div class="menu-sep"></div><button data-a="fromFile">📂 From a file (STEP / STL / OBJ / 3MF)…</button>' : ''}</div></div>
      <div class="as-jbar ${toolGroup('joint')}" title="${esc(t('Hold a part against another one: choose how, then click a face of the part to move and the face it goes to (S = touch)'))}"><span class="as-jlabel">🔗 ${esc(t('Joint'))}</span>
        ${Object.entries(JOINT_TYPES).map(([k, j]) => `<button class="${(k === 'fastener' ? this.bolt : this.mode !== 'idle' && this.jointType === k) ? 'on' : ''}" data-joint="${k}" title="${esc(`${t(j.name)}: ${t(j.hint)}`)}">${j.icon} <span>${esc(t(j.name))}</span></button>`).join('')}</div>
      ${btn('measure', '📏 Measure', 'Measure: click a spot (a face, a corner), then another one — the distance; two parallel flat faces: the gap between them; two round faces: how far apart their axes are', `tool ${this.measuring ? 'on' : ''}`)}
      ${btn('paint', '🎨 Paint', 'Colour faces of the placed parts, or whole parts — in this assembly: click them (Ctrl+click: more), then pick a colour', `tool ${this.painting ? 'on' : ''}`)}
      ${btn('section', '✂ Section', 'Look inside: cut the view along X, Y or Z', `tool ${this.section ? 'on' : ''}`)}
      ${btn('clashes', this.clashLabel(), 'Where parts overlap (go into each other) — checked after every change; click: the list, each one shown in the view', `tool ${this.clashPanel ? 'on' : ''} ${this.clashes?.length ? 'bad' : this.clashes ? 'good' : ''}`)}
      ${btn('fasteners', '🔩 Fasteners', 'Screws, heat-set inserts and pins where holes line up across parts — suggested, added with one click', `tool ${this.fastenerPanel ? 'on' : ''}`)}
      ${this.mech?.list.length ? btn('mech', '⚙ Mechanism', 'The mechanisms of this assembly: one slider each moves all of its parts, ▶ plays it', `tool ${this.mech.closed ? '' : 'on'}`) : ''}
      ${this.hooks.newSheet ? btn('sheet', '📄 Drawing', 'The assembly\'s drawing sheet to edit: its views, overall sizes, parts list and balloons — it follows the assembly; 📄 Drawings (PDF) in the panel makes the whole set', 'tool') : ''}
      <span class="sep"></span>
      <button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
      <span class="sep"></span>
      <label class="chip as-explode" title="Pull the parts apart to see them (the placement does not change) — 💥 in the list chooses which parts move">Explode <input type="range" min="0" max="1" step="0.01" value="${this.explode}"></label>
      <label class="chip as-exrespect" title="Explode along the joints: a joined part moves only the ways its joints leave free (a pin out of its hole along the axis), and goes along with the part it is on"><input type="checkbox" data-a="exRespect" ${this.explodeRespect ? 'checked' : ''}> Respect joints</label>`; // (the views: the view cube, top right)
    bar.querySelector('[data-a=insert]').disabled = !parts.length && !this.hooks.importSolid;
    for (const b of bar.querySelectorAll('[data-joint]')) b.disabled = this.doc.instances.length < 2;
    for (const a of ['paint', 'section']) bar.querySelector(`[data-a=${a}]`).disabled = !this.doc.instances.length;
    bar.querySelector('[data-a=clashes]').disabled = this.doc.instances.length < 2;
    const shb = bar.querySelector('[data-a=sheet]');
    if (shb) shb.disabled = !this.doc.instances.length;
    for (const b of bar.querySelectorAll('[data-joint]')) {
      b.addEventListener('click', () => {
        if (b.classList.contains('on')) { if (b.dataset.joint === 'fastener') this.cancelBolt(); else this.cancelJoint(); return; } // (the one on: off again)
        if (this.mode !== 'idle') this.cancelJoint();
        if (b.dataset.joint === 'fastener') { this.fastenerPanel = true; this.sel = null; this.sel2 = null; } // (one place for them: the panel, and the click goes on)
        this.startJoint(b.dataset.joint);
        if (b.dataset.joint === 'fastener') { this.render(); this.draw(); } else this.renderSuggest(); // (picking faces: the table goes)
      });
    }
    bar.querySelector('[data-a=insert]').addEventListener('click', (e) => { e.stopPropagation(); bar.querySelector('.as-insert').classList.toggle('open'); });
    for (const b of bar.querySelectorAll('[data-part]')) b.addEventListener('click', () => { bar.querySelector('.as-insert').classList.remove('open'); this.insert(b.dataset.part); });
    bar.querySelector('[data-a=fromFile]')?.addEventListener('click', () => { bar.querySelector('.as-insert').classList.remove('open'); this.insertFile(); });
    for (const b of bar.querySelectorAll('[data-a]:not([data-a=insert]):not([data-a=fromFile]):not([data-a=exRespect])')) b.addEventListener('click', () => this.action(b.dataset.a));
    bar.querySelector('[data-a=exRespect]').addEventListener('change', (e) => { this.explodeRespect = e.target.checked; this.exDirs = null; this.draw(); });
    const r = bar.querySelector('.as-explode input');
    r.addEventListener('input', () => { this.explode = +r.value; this.$('.as-list')?.classList.toggle('exploding', this.explode > 0); this.draw(); });
    this.updateUndo();
    fitBar(bar); // (icons only when the names do not fit)
  }

  updateUndo() {
    const u = this.$('.m-cmdbar [data-a=undo]'), r = this.$('.m-cmdbar [data-a=redo]');
    if (u) u.disabled = !this.history.canUndo();
    if (r) r.disabled = !this.history.canRedo();
  }

  action(a) {
    if (a === 'snap') return this.startJoint('touch');
    if (a === 'measure') return this.toggleMeasure();
    if (a === 'paint') return this.togglePaint();
    if (a === 'clashes') return this.toggleClashes();
    if (a === 'section') return this.toggleSection();
    if (a === 'sheet') { this.hooks.newSheet?.(); return null; }
    if (a === 'mech') { this.mech.toggle(); return null; }
    if (a === 'fasteners') { this.fastenerPanel = !this.fastenerPanel; this.sel = null; this.render(); this.draw(); return null; }
    if (a === 'undo') return this.history.go(-1);
    if (a === 'redo') return this.history.go(1);
    if (a.startsWith('view-')) return this.view.setView(a.slice(5));
    return null;
  }

  hint(text) {
    const h = this.$('.m-hint'), bar = this.$('.m-cmdbar');
    h.hidden = !text;
    h.textContent = text || '';
    if (bar) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`; // (under the bar, however many rows it has)
  }

  renderList() {
    const list = this.$('.as-list'), open = this.openPaths();
    this.$('.as-start').hidden = this.doc.instances.length > 0;
    list.innerHTML = '';
    list.classList.toggle('exploding', this.explode > 0);
    for (const it of this.doc.instances) {
      const b = this.bodies[it.part];
      const row = document.createElement('div');
      row.className = `mt-item${it.id === this.sel || it.id === this.sel2 ? ' on' : ''}${b?.error ? ' bad' : ''}`;
      row.innerHTML = `<span class="mt-icon">${this.partIcon(it.part)}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>
        ${b?.error ? '<span class="mt-warn">⚠</span>' : ''}
        <span class="mt-acts"><button class="mini" data-a="rename" title="Rename its part (its tab too)">🏷</button><button class="mini" data-a="dup" title="One more of this part">⧉</button><button class="mini danger" data-a="del" title="Take it out of the assembly">✕</button></span>
        <button class="mini as-boom${it.stay ? ' off' : ''}" data-a="boom" title="${it.stay ? 'Stays in place when exploded — click to let it move' : 'Moves when exploded — click to keep it in place (Ctrl+click: only this one moves)'}">💥</button>`;
      row.querySelector('.mt-name').textContent = this.partName(it.part);
      row.querySelector('.mt-what').textContent = `${it.id}${it.fixed ? ' 📌' : ''}`;
      const kids = this.kindOf(it.part) === 'assembly' ? instanceTree(this.bomCtx(), it.part, it.id) : null;
      if (kids) this.twist(row, it.id, kids, open);
      if (it.id === this.sel && this.selInner?.top === it.id) row.classList.add('has-inner');
      if (it.fixed) row.title = t('Fixed in place 📌');
      if (b?.error) row.title = b.error;
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'dup') return this.insert(it.part, it);
        if (a === 'rename') {
          renameInPlace(row.querySelector('.mt-name'), (n) => { this.hooks.renamePart?.(it.part, n); this.render(); this.hooks.onChange?.(); });
          return null;
        }
        if (a === 'del') return this.removeInst(it.id);
        if (a === 'boom') return this.toggleStay(it.id, e.ctrlKey || e.metaKey);
        if (a === 'twist') return this.toggleOpen(it.id);
        this.choose(it.id, e.ctrlKey || e.metaKey);
        return null;
      });
      list.appendChild(row);
      if (kids && open.has(it.id)) this.innerRows(list, it, kids, 1, open);
    }
  }

  /** ▸ / ▾ on a sub-assembly's row; folded: how many parts are in it (all levels). */
  twist(row, path, kids, open) {
    const on = open.has(path), b = document.createElement('button');
    b.className = 'mini as-twist';
    b.dataset.a = 'twist';
    b.textContent = on ? '▾' : '▸';
    b.title = t(on ? 'Hide its parts' : 'Show its parts');
    row.prepend(b);
    row.classList.add('as-node');
    if (!on) {
      let n = 0;
      const count = (nodes) => { for (const x of nodes) (x.children ? count(x.children) : n++); };
      count(kids);
      row.querySelector('.mt-what').textContent += ` · ${t2('{n} part(s)', { n })}`;
    }
  }

  /** A placed sub-assembly's own parts under its row, indented with a guide line; a sub-assembly in it folds open too.
   *  A click: that part lit in the view, what can be done with it in the panel (its top-level placement chosen). */
  innerRows(list, top, nodes, depth, open) {
    for (const n of nodes) {
      const inner = n.path.slice(top.id.length + 1), row = document.createElement('div');
      row.className = `mt-item as-inner-row${this.sel === top.id && this.selInner?.top === top.id && this.selInner.path === inner ? ' on' : ''}`;
      row.style.setProperty('--depth', depth);
      row.dataset.path = n.path;
      row.innerHTML = `<span class="mt-icon">${this.partIcon(n.part)}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>`;
      row.querySelector('.mt-name').textContent = this.partName(n.part);
      row.querySelector('.mt-what').textContent = n.id;
      row.title = t2('In {sub} — a click shows it in the view', { sub: this.partName(top.part) });
      if (n.children) this.twist(row, n.path, n.children, open);
      row.addEventListener('click', (e) => {
        if (e.target.closest('[data-a=twist]')) { this.toggleOpen(n.path); return; }
        this.chooseInner(top.id, inner, e.ctrlKey || e.metaKey);
      });
      list.appendChild(row);
      if (n.children && open.has(n.path)) this.innerRows(list, top, n.children, depth + 1, open);
    }
  }

  /** The sub-assemblies folded open in this assembly's list (localStorage a3d.asmTree: {assembly id: [paths]}). */
  openPaths() {
    let all = {};
    try { all = JSON.parse(localStorage.getItem('a3d.asmTree') || '{}') || {}; } catch { all = {}; }
    return new Set(all[this.hooks.selfId?.() || ''] || []);
  }

  toggleOpen(path) {
    const open = this.openPaths(), id = this.hooks.selfId?.() || '';
    if (open.has(path)) open.delete(path); else open.add(path);
    let all = {};
    try { all = JSON.parse(localStorage.getItem('a3d.asmTree') || '{}') || {}; } catch { all = {}; }
    all[id] = [...open];
    try { localStorage.setItem('a3d.asmTree', JSON.stringify(all)); } catch { /* private window */ }
    this.renderList();
  }

  /** A part inside a placed sub-assembly chosen in the list: its placement chosen, that part (path "I2" or "I2/I1"
   *  inside it) lit in the view; Ctrl: its placement as the second part (the joints between the two). */
  chooseInner(top, path, more = false) {
    if (more) { this.choose(top, true); return; }
    this.choose(top);
    this.selInner = { top, path };
    this.render();
    this.draw();
  }

  /** 💥 Which parts move in Explode: one on / off, or (only) just this one moves — and again: all of them. */
  toggleStay(id, only = false) {
    const all = this.doc.instances, it = this.inst(id);
    if (!it) return;
    if (only) {
      const already = all.every((x) => !!x.stay === (x.id !== id));
      for (const x of all) { if (already || x.id === id) delete x.stay; else x.stay = true; }
    } else if (it.stay) delete it.stay;
    else it.stay = true;
    if (!all.some((x) => !x.stay)) for (const x of all) delete x.stay; // none would move: all of them do
    this.commit();
  }

  /** What the BOM engine (bom.js) reads of the project. */
  bomCtx() {
    const self = this.active ? this.hooks.selfId?.() : null; // (the assembly on screen: its document here, the project's copy is 'live')
    return { partData: (id) => (id === self && !this.owner ? this.doc : this.hooks.partData(id)), kindOf: (id) => this.kindOf(id), partName: (id) => this.partName(id), massOf: (id) => this.massOf(id) };
  }

  /** A part's mass (g, each): a mass of its own (mass_g: a bought part's, from its maker), else its body as last built
   *  (volume × its material; a library part without one: none), or null. */
  massOf(pid) {
    const b = this.bodies[pid]?.body, data = this.hooks.partData(pid) || {}, mat = data.material || (data.library ? '' : 'PLA');
    if (b?.sub) return null;
    const own = +(data.mass_g ?? data.library?.mass_g);
    if (own > 0) return own;
    if (!b) return null;
    return b.mass_g ?? (b.volume && MATERIALS[mat] ? (b.volume / 1000) * MATERIALS[mat] : null);
  }

  /** ⚖ The assembly's mass and centre of mass, from each placed part's (the kernel's, once per part) moved by its
   *  placement -> {mass_g, cog: [x, y, z] | null, unknown: placed parts without a mass}. Cheap: run on every frame of ▶. */
  massProps() {
    let m = 0, unknown = 0;
    const c = new THREE.Vector3(), p = new THREE.Vector3(), M = new THREE.Matrix4();
    for (const it of this.doc.instances) {
      const b = this.bodyOf(it)?.body, mi = b?.sub ? b.mass_g : this.massOf(it.part);
      if (!b?.cog || !(mi > 0)) { unknown++; continue; }
      c.addScaledVector(p.set(...b.cog).applyMatrix4(M.fromArray(it.matrix)), mi);
      m += mi;
    }
    return { mass_g: +m.toFixed(2), cog: m > 0 ? c.multiplyScalar(1 / m).toArray().map((v) => +v.toFixed(3)) : null, unknown };
  }

  /** ⚖ The assembly's centre of mass marked in the view (⊕ in the Assembly panel) or not. */
  toggleCog() { this.cogOn = !this.cogOn; this.render(); this.draw(); }

  /** The ⊕ marker and the panel's CoG where the parts are now (draw: while they move too). */
  showCog() {
    const el = this.$?.('.as-cogv'), mp = this.cogOn || el ? this.massProps() : null;
    this.view.setCog(this.cogOn ? mp.cog : null, this.cogOn && mp.cog ? t('Centre of mass') : '');
    if (el && mp.cog) el.textContent = `${cogText(mp.cog)} mm`;
  }

  /** The assembly whose drawing set numbers this one's positions (the top one it is in), so the BOM and the balloons agree. */
  numberingOf(aid) { return this.hooks.setRoot?.(aid) || aid; }

  /** The bill of materials of every part, rolled up through the sub-assemblies (bom.js) -> rows
   *  [{pos, name, qty, maker, pn, description, order: {…}, material, mass_g (each), library (bool), buy, how / made (bom.js makeBuy)}]. */
  bomFlat(aid = this.hooks.selfId?.()) {
    return bomOf(this.bomCtx(), aid, { numbering: this.numberingOf(aid) }).rows.map((r) => ({ pos: r.pos, name: r.name, qty: r.qty, maker: r.maker, pn: r.pn, description: r.description,
      order: r.order, material: r.material, mass_g: r.mass_g, library: r.library, approx: r.approx, buy: r.buy, how: r.how, made: r.how }));
  }

  /** ⬇ BOM (CSV): the summary BOM (bom.js bomCsv: ; separated — Excel in Czech / German reads it —, UTF-8 with a BOM mark). */
  async exportBom() {
    const aid = this.hooks.selfId?.(), bom = bomOf(this.bomCtx(), aid, { numbering: this.numberingOf(aid) });
    const blob = new Blob([bomCsv(bom, t)], { type: 'text/csv' });
    if (await this.hooks.download(blob, `${this.hooks.safeName()} BOM.csv`)) this.hooks.toast(t2('BOM saved: {n} line(s).', { n: bom.rows.length }), 'ok');
  }

  /** 📋 BOM: the window with the whole BOM (Summary / Structured) of this assembly or any of its sub-assemblies. */
  openBom() {
    const aid = this.hooks.selfId?.(), seen = new Set([aid]), choices = [{ id: aid, name: this.partName(aid), depth: 0 }];
    const walk = (nodes, depth) => { for (const n of nodes) if (n.children) { if (!seen.has(n.part)) { seen.add(n.part); choices.push({ id: n.part, name: this.partName(n.part), depth }); } walk(n.children, depth + 1); } };
    walk(instanceTree(this.bomCtx(), aid), 1);
    this.bomWin = openBomWindow({ ctx: this.bomCtx(), aid, choices, numberingOf: (id) => this.numberingOf(id), download: this.hooks.download, toast: this.hooks.toast });
    return this.bomWin;
  }

  /** The parts list: part, how many, material, mass each and in all. */
  bom() {
    const rows = {};
    for (const it of this.doc.instances) {
      const r = (rows[it.part] = rows[it.part] || { part: it.part, name: this.partName(it.part), qty: 0 });
      r.qty++;
      const data = this.hooks.partData(it.part);
      r.lib = data?.library || null;
      r.material = data?.material || 'PLA';
      const b = this.bodies[it.part]?.body;
      if (b?.sub) r.material = '—';
      r.mass = b?.sub ? b.mass_g ?? null : this.massOf(it.part); // (as the BOM's: bom.js)
    }
    return Object.values(rows);
  }

  /** The joints shown now (listed, marked, their symbols in the view): between the two chosen parts, of the one
   *  chosen, or all of them. */
  shownJoints() {
    const all = (this.doc.mates || []).filter((m) => this.inst(m.move) && this.inst(m.onto));
    if (this.sel && this.sel2) return all.filter((m) => (m.move === this.sel && m.onto === this.sel2) || (m.move === this.sel2 && m.onto === this.sel));
    if (this.sel) return all.filter((m) => m.move === this.sel || m.onto === this.sel);
    return all;
  }

  /** A part clicked: chosen alone, or (Ctrl) as the second one — the joints between the two are shown. */
  choose(id, more = false) {
    this.selInner = null;
    if (more && this.sel && id && id !== this.sel) this.sel2 = this.sel2 === id ? null : id;
    else { this.sel = id || null; this.sel2 = null; }
    this.render();
    this.draw();
  }

  renderPair(box) {
    const a = this.inst(this.sel), b = this.inst(this.sel2), js = this.shownJoints();
    box.innerHTML = `<h2><span data-no-i18n>${esc(this.partName(a.part))}</span> ↔ <span data-no-i18n>${esc(this.partName(b.part))}</span></h2>
      <p class="hint">${esc(t2(js.length ? '{a} and {b} — the joints between them.' : '{a} and {b} — no joints between them yet.', { a: a.id, b: b.id }))}</p>
      ${js.length ? this.jointsHtml(null, js) : ''}
      <div class="row-actions wrap"><button class="btn small primary" data-a="joinPair">🔗 Join them</button><button class="btn small" data-a="onlyA">${esc(this.partName(a.part))} ${a.id}</button><button class="btn small" data-a="onlyB">${esc(this.partName(b.part))} ${b.id}</button></div>
      <p class="hint">Ctrl+click another part to compare it instead, a click alone shows one part.</p>`;
    this.bindJointRows(box);
    box.querySelector('[data-a=joinPair]').addEventListener('click', () => this.startJoint('touch', a.id));
    box.querySelector('[data-a=onlyA]').addEventListener('click', () => this.choose(a.id));
    box.querySelector('[data-a=onlyB]').addEventListener('click', () => this.choose(b.id));
  }

  renderProps() {
    const box = this.$('.mp-body'), it = this.inst(this.sel);
    this.drawJointTags();
    if (this.painting) { this.renderPaint(box); return; }
    if (this.clashPanel && !it) { this.renderClashes(box); return; }
    if (this.sel2 && it && this.inst(this.sel2) && !this.bolt && this.mode === 'idle') { this.renderPair(box); return; }
    if (this.bolt) { this.renderBolt(box); return; }
    this.view.setGhost([]);
    if (this.fastenerPanel && !it) { this.renderFasteners(box); return; }
    if (it && this.selInner?.top === it.id) { this.renderInner(box, it, this.selInner.path); return; }
    if (it) {
      const m = new THREE.Matrix4().fromArray(it.matrix), p = new THREE.Vector3().setFromMatrixPosition(m);
      const e = new THREE.Euler().setFromRotationMatrix(m, 'XYZ'), deg = (r) => Math.round((r * 180) / Math.PI * 10) / 10;
      const row = (k, v) => `<div class="field"><label>${k.toUpperCase()}</label><input type="number" step="any" data-k="${k}" value="${fmt(v)}"><span class="unit">mm</span></div>`;
      const rot = (k) => `<div class="as-rot"><label>↻ ${k.toUpperCase()}</label>
        <input type="range" min="-180" max="180" step="1" list="as-ticks" data-rot="${k}" value="${deg(e[k])}">
        <input type="number" step="any" data-rotn="${k}" value="${fmt(deg(e[k]))}"><span class="unit">°</span></div>`;
      const freePlace = `${row('x', p.x)}${row('y', p.y)}${row('z', p.z)}
        <h3>Turn</h3><datalist id="as-ticks"><option value="-180"></option><option value="-90"></option><option value="0"></option><option value="90"></option><option value="180"></option></datalist>
        ${rot('x')}${rot('y')}${rot('z')}
        <p class="hint">Slide to any angle — it catches at 0, ±90 and ±180°. Type an exact one in the box.</p>`;
      const dof = this.motionsOf(it.id), lp = this.mechanismOf(it.id);
      this.dof = dof;
      const loopHint = !lp ? '' : `<p class="hint as-loop ${lp.closed ? '' : 'bad'}">${esc(lp.closed ? t2('In a closed loop with {parts}: they move together, {n} way(s) for all of them — move one, the others follow.', { parts: lp.parts.filter((x) => x !== it.id).join(', '), n: lp.free ?? '?' })
        : t2('⚠ The closed loop {parts} cannot close here — a part is too short or too long for this place.', { parts: lp.parts.join('–') }))}</p>`;
      const place = dof ? `<h3>Moves</h3>${loopHint}${dof.count === 0 ? (lp?.free ? '' : '<p class="mp-count">🔒 Fully held — its joints fix it, it cannot move.</p>')
        : `<p class="hint">${dof.via ? t2('It is fixed on {part} — it moves with it: drive it here, {part} goes along.', { part: this.partName(this.inst(dof.via)?.part) })
          : t2('It can still move {n} way(s) — the ways its joints leave free. Slide, then let go: it stays there.', { n: dof.count })}</p>
        <div class="as-motions">${dof.motions.map((mo, i) => this.motionHtml(it, mo, i, dof.size)).join('')}</div>
        ${dof.unexplained > 0 ? `<p class="hint">${t2('…and {n} more way(s) that are not a plain move or turn.', { n: dof.unexplained })}</p>` : ''}`}
        <details class="as-free"><summary>Place it by hand (breaks its joints)</summary>${freePlace}</details>`
        : freePlace;
      const inner = this.innerMotions(it), miss = this.mech?.missing, missHere = miss && (!this.mech.list.length || this.mech.closed) && [miss.move.inst, miss.onto.inst].includes(it.id); // (no ⚙ widget: the line is here)
      box.innerHTML = `<h2 data-no-i18n>${esc(this.partName(it.part))}</h2><p class="hint">${it.id} — ${dof ? 'held by its joints.' : 'where its own origin is, and how it is turned.'}</p>
        ${missHere ? this.mech.missingHtml() : ''}
        ${inner ? this.innerHtml(it, inner) : ''}
        ${place}
        ${this.editHtml(it)}
        <h3>Look</h3>${this.lookHtml(it)}
        ${this.jointsHtml(it.id)}${couplingsHtml(this, it.id)}
        <div class="row-actions wrap"><button class="btn small" data-a="joinThis">🔗 Join it to another part</button></div>
        ${this.hooks.duplicatePart ? '<div class="row-actions"><button class="btn small" data-a="ownPart" title="Copy its part as a new part of the project and use the copy here — then it can be changed alone (the other copies stay as they are)">⧉ Make it its own part</button></div>' : ''}
        <div class="row-actions">${this.hooks.openPart ? `<button class="btn small primary" data-a="openPart" title="Open its part in its own tab (to change it — the assembly follows)">${this.kindOf(it.part) === 'assembly' ? '◇' : '◆'} ${esc(t('Open its part'))}</button>` : ''}<button class="btn small ${it.fixed ? 'on' : ''}" data-a="fix" title="${it.fixed ? 'Fixed in place: it is not moved by hand, joints bring the other parts to it — click to free it' : 'Fix it in place: it is not moved by hand, joints bring the other parts to it'}">📌 ${esc(t(it.fixed ? 'Fixed' : 'Fix in place'))}</button><button class="btn small" data-a="reset" title="Back to its place in its own model">Reset its place</button><button class="btn small danger" data-a="del">✕ ${esc(t('Take it out'))}</button></div>`;
      if (missHere) this.mech.bindMissing(box);
      for (const inp of box.querySelectorAll('input[data-k]')) {
        inp.addEventListener('change', () => this.setPos(inp.dataset.k, inp.value));
        inp.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') inp.blur(); });
      }
      for (const sl of box.querySelectorAll('input[data-rot]')) {
        const k = sl.dataset.rot, num = box.querySelector(`[data-rotn=${k}]`);
        sl.addEventListener('input', () => {
          let v = +sl.value;
          const near = Math.round(v / 90) * 90;
          if (Math.abs(v - near) <= 4) { v = near; sl.value = v; } // the 90° marks catch
          num.value = fmt(v);
          this.setRot(k, v, false);
        });
        sl.addEventListener('change', () => this.setRot(k, +num.value, true));
        num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
        num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) this.setRot(k, v, true); });
      }
      if (dof) this.bindMotions(box.querySelector('.as-motions') || box, it, dof);
      if (inner) this.bindInner(box, it, inner);
      this.bindJointRows(box);
      bindCouplingRows(this, box, renameInPlace);
      this.bindLook(box, it);
      box.querySelector('[data-a=editHere]')?.addEventListener('click', () => this.editInPlace(it.id));
      box.querySelector('[data-a=editLock]')?.addEventListener('click', () => this.toggleEditable(it.part));
      box.querySelector('[data-a=joinThis]').addEventListener('click', () => this.startJoint('touch', it.id));
      box.querySelector('[data-a=ownPart]')?.addEventListener('click', () => this.ownPart(it.id));
      box.querySelector('[data-a=fix]')?.addEventListener('click', () => this.toggleFixed(it.id));
      box.querySelector('[data-a=reset]').addEventListener('click', () => { if (!this.mayMove(it.id)) return; it.matrix = ID(); this.applyMates(); this.commit(); });
      box.querySelector('[data-a=del]').addEventListener('click', () => this.removeInst(it.id));
      box.querySelector('[data-a=openPart]')?.addEventListener('click', () => this.hooks.openPart(it.part));
      return;
    }
    const rows = this.bom(), total = rows.reduce((s, r) => s + (r.mass || 0) * r.qty, 0), mp = this.massProps();
    box.innerHTML = `<h2>Assembly</h2>
      ${rows.length ? `${this.jointsHtml(null)}${couplingsHtml(this, null)}<h3>Parts list</h3><table class="as-bom"><tr><th>Part</th><th>Qty</th><th>Material</th><th>Mass</th></tr>
        ${rows.map((r) => `<tr><td data-no-i18n>${esc(r.name)}</td><td>${r.qty}</td><td>${esc(t(r.material))}</td><td>${r.mass === null ? '—' : `${fmt(+(r.mass * r.qty).toFixed(1))} g`}</td></tr>`).join('')}
        <tr class="as-total"><td>Total</td><td>${rows.reduce((s, r) => s + r.qty, 0)}</td><td></td><td>${fmt(+total.toFixed(1))} g</td></tr></table>
        ${mp.cog ? `<div class="mp-facts as-mass"><span title="${esc(t('Centre of mass (centre of gravity) of the placed parts, in the assembly\'s coordinates — it follows them as they move'))}">CoG</span><b class="mp-cog"><span class="as-cogv" data-no-i18n>${cogText(mp.cog)} mm</span>
          <button class="btn small ${this.cogOn ? 'on' : ''}" data-a="cog" title="${esc(t('Show the centre of mass in the view (⊕)'))}">⊕</button></b>
          ${mp.unknown ? `<span></span><span class="mp-sub">${esc(t2('{n} part(s) without a mass left out', { n: mp.unknown }))}</span>` : ''}</div>` : ''}
        ${rows.some((r) => r.lib?.pn) ? `<div class="as-pns">${rows.filter((r) => r.lib?.pn).map((r) => `<div><span data-no-i18n>${r.qty}× ${esc(r.lib.pn)}</span> <i data-no-i18n>${esc(r.lib.maker || '')}</i></div>`).join('')}</div>` : ''}
        <div class="row-actions"><button class="btn small primary" data-a="bomWin" title="The bill of materials: every part with its total quantity from all levels (sub-assemblies counted in), material, mass, maker and part number — as a summary or as the assembly tree">📋 BOM</button><button class="btn small" data-a="bomCsv" title="The bill of materials as a CSV file (Excel): every part with its quantity, maker, part number, order numbers and mass — the parts inside sub-assemblies too">⬇ BOM (CSV)</button></div>
        <h3>Export</h3><div class="row-actions"><button class="btn small" data-x="stl" title="All parts in one STL, as placed">STL</button>
        <button class="btn small" data-x="step" title="All parts as separate bodies in one STEP file">STEP</button>
        <button class="btn small" data-x="iges" title="Every part placed in one IGES file (names, colours) — for CAD programs that ask for IGES; it has no assembly tree">IGES</button>
        <button class="btn small" data-x="glb" title="glTF for viewers and rendering: a node per placed part with its name, the colours and materials">GLB</button>
        ${this.hooks.newSheet ? '<button class="btn small" data-a="sheetHere" title="The assembly\'s drawing sheet to edit (views, parts list, balloons, your dimensions and texts)">📄 Drawing sheet</button>' : ''}
        ${this.hooks.drawingSet ? '<button class="btn small primary" data-a="drawingSet" title="One PDF: this assembly (its views, parts list and balloons), then each sub-assembly with its parts, then its own made parts — their drawing sheets when they have one">📄 Drawings (PDF)</button>' : ''}</div>
        <p class="hint">To print, open each part's tab and use 🖨 Prepare for 3D print there.</p>`
        : `<p class="hint">Insert parts of this project (3D models and quick parts) with ＋ Insert part, then join them with 🔗 Joint.</p>`}`;
    this.bindJointRows(box);
    bindCouplingRows(this, box, renameInPlace);
    for (const el of box.querySelectorAll('[data-x]')) el.addEventListener('click', () => this.export(el.dataset.x));
    box.querySelector('[data-a=bomCsv]')?.addEventListener('click', () => this.exportBom());
    box.querySelector('[data-a=bomWin]')?.addEventListener('click', () => this.openBom());
    box.querySelector('[data-a=cog]')?.addEventListener('click', () => this.toggleCog());
    box.querySelector('[data-a=drawingSet]')?.addEventListener('click', () => this.hooks.drawingSet());
    box.querySelector('[data-a=sheetHere]')?.addEventListener('click', () => this.hooks.newSheet());
  }

  /** A part inside a placed sub-assembly (chosen in the list): where it is, its moves inside the sub-assembly here
   *  (when its own joints leave it free: only in this placement), open its part / the sub-assembly, or choose the whole. */
  renderInner(box, it, path) {
    const ids = path.split('/'), node = (() => { let list = this.innerList(it), x = null; for (const id of ids) { x = list.find((q) => q.id === id); list = x && this.kindOf(x.part) === 'assembly' ? this.hooks.partData(x.part)?.instances || [] : []; } return x; })();
    if (!node) { this.selInner = null; this.renderProps(); return; }
    const sub = this.partName(it.part), name = this.partName(node.part);
    let inner = ids.length === 1 ? this.innerMotions(it) : null;
    if (inner) inner = { ...inner, parts: inner.parts.filter((q) => q.id === ids[0]) };
    if (inner && !inner.parts.length) inner = null;
    box.innerHTML = `<h2>${this.kindOf(node.part) === 'assembly' ? '◇' : '◆'} <span data-no-i18n>${esc(name)}</span></h2>
      <p class="hint">${esc(t2('{id} inside {sub} ({top}) — a part of {sub}: it moves with it, and it is changed in its own tab.', { id: path, sub, top: it.id }))}</p>
      ${inner ? this.innerHtml(it, inner) : `<p class="hint">${esc(t2('{sub} holds it in place — only {sub} itself is moved here.', { sub }))}</p>`}
      <div class="row-actions wrap">${this.hooks.openPart ? `<button class="btn small primary" data-a="openInner" title="${esc(t('Change it in its own tab (the assembly follows)'))}">${this.kindOf(node.part) === 'assembly' ? '◇' : '◆'} ${esc(t('Open its part'))}</button>
        <button class="btn small" data-a="openSub">◇ ${esc(t2('Open {sub}', { sub }))}</button>` : ''}
        <button class="btn small" data-a="wholeSub">${esc(t2('Choose the whole {sub}', { sub }))}</button></div>`;
    if (inner) this.bindInner(box, it, inner);
    box.querySelector('[data-a=openInner]')?.addEventListener('click', () => this.hooks.openPart(node.part));
    box.querySelector('[data-a=openSub]')?.addEventListener('click', () => this.hooks.openPart(it.part));
    box.querySelector('[data-a=wholeSub]').addEventListener('click', () => this.choose(it.id));
  }

  // ------------------------------------------------------------------ fasteners
  renderFasteners(box) {
    const cs = this.candidates = findCandidates(this);
    box.innerHTML = `<h2>🔩 Fasteners</h2>
      <p class="hint">Where holes line up through two parts, a screw (with a heat-set insert in the part below), a screw
      alone or a pin fits. Hover a suggestion to see its holes; Add puts it in, held by joints (it follows the parts).</p>
      ${cs.length ? `<div class="as-joints">${cs.map((c) => `<div class="as-jrow" data-cand="${c.id}"><span class="as-jt">${c.kind === 'pin' ? '📍' : '🔩'}</span>
        <span class="as-jw"><b>${esc(c.text)}</b> · ${esc(this.partName(this.inst(c.entry.inst)?.part))}${c.insert ? ` → ${esc(this.partName(this.inst(c.insert.inst)?.part))}` : ''}</span>
        <span></span><button class="btn small" data-add="${c.id}">Add</button></div>`).join('')}</div>
        <div class="row-actions"><button class="btn small primary" data-a="addAll">Add all (${cs.length})</button></div>`
        : cs.filled ? `<p class="mp-count">✓ Every hole that lines up has its fastener (${cs.filled}).</p>`
        : `<p class="mp-count">No holes line up between parts yet.</p><p class="hint">Put a hole in each part where they are to be fastened —
          e.g. Ø3.4 for an M3 screw in the top part and Ø4.0 for an M3 insert in the part below — join the parts, then look here again.</p>`}
      <h3>A new one</h3><p class="hint">Put a screw (with a nut or an insert) or a pin through parts that have no holes yet: click where it goes in — the holes are drilled for it.</p>
      <div class="row-actions"><button class="btn small primary" data-a="newBolt">🔩 Screw / pin through parts…</button></div>
      <div class="row-actions"><button class="btn small" data-a="closeF">Close</button></div>`;
    box.querySelector('[data-a=newBolt]').addEventListener('click', () => { this.fastenerPanel = false; this.startJoint('fastener'); this.renderProps(); });
    for (const row of box.querySelectorAll('[data-cand]')) {
      row.addEventListener('mouseenter', () => { this.hoverCand = cs.find((c) => c.id === row.dataset.cand); this.drawMarks(); });
      row.addEventListener('mouseleave', () => { this.hoverCand = null; this.drawMarks(); });
    }
    for (const b of box.querySelectorAll('[data-add]')) b.addEventListener('click', () => this.addFasteners([cs.find((c) => c.id === b.dataset.add)]));
    box.querySelector('[data-a=addAll]')?.addEventListener('click', () => this.addFasteners(cs));
    box.querySelector('[data-a=closeF]').addEventListener('click', () => { this.fastenerPanel = false; this.hoverCand = null; this.render(); this.draw(); });
  }

  /** 🔩 Screw / pin by its two holes: the suggestion for that pair, in from the first one. */
  async fastenerAt(from, to) {
    const cs = findCandidates(this);
    const has = (c, x) => c.holes.some((hh) => hh.inst === x.inst && hh.name === x.face.name);
    const inPart = (c, inst) => c.holes.some((hh) => hh.inst === inst); // any hole of the other part on that axis
    const c = cs.find((x) => x.entry.inst === from.inst && has(x, from) && inPart(x, to.inst)) || cs.find((x) => has(x, from) && inPart(x, to.inst));
    this.mode = 'idle';
    this.jointFrom = null;
    this.hoverFace = null;
    this.fastenerPanel = false;
    this.hint('');
    if (!c) {
      const d = (x) => `Ø${fmt(2 * (x.face.radius || 0))}`;
      this.hooks.toast(t2('These holes ({a}, {b}) do not line up, or fit no standard screw / pin — a screw needs a clearance hole in the part it goes in from (M3: Ø3.2–3.7) and one that fits it or an insert (M3 insert: Ø3.9–4.4) below.',
        { a: d(from), b: d(to) }), 'warning', 8000);
      this.renderBar();
      this.draw();
      return;
    }
    await this.addFasteners([c]);
  }

  /** A standard part in the project: the one already there with that name, or a new 3D model part. */
  ensurePart(mdl) {
    const have = this.hooks.parts().find((p) => p.kind === 'model' && p.name === mdl.name);
    return have ? have.id : this.hooks.addModelPart(mdl.name, { features: mdl.features, material: mdl.material, standard: true });
  }

  // ------------------------------------------------------------------ ⚠ collisions
  /** The ⚠ button's text: what the last check found. */
  clashLabel() {
    const n = this.clashes?.length;
    return this.doc.instances.length < 2 || !this.clashes ? '⚠ Collisions' : n ? `⚠ ${n} collision(s)` : '✓ No collisions';
  }

  /** The ⚠ button as the last check found (without drawing the bar again). */
  updateClashButton() {
    const b = this.$('.m-cmdbar [data-a=clashes]');
    if (!b) return;
    b.textContent = this.clashLabel();
    b.classList.toggle('bad', !!this.clashes?.length);
    b.classList.toggle('good', !!this.clashes && !this.clashes.length);
  }

  /** Checked again a moment after a change (the ⚠ button counts them, the list when it is open). */
  scheduleClashes(ms = 700) {
    clearTimeout(this.clashTimer);
    if (this.doc.instances.length < 2) { this.clashes = null; this.updateClashButton(); return; }
    this.clashTimer = setTimeout(() => this.checkClashes(true), ms);
  }

  toggleClashes() {
    this.clashPanel = !this.clashPanel;
    this.hoverClash = null;
    this.focusClash = null;
    if (this.clashPanel) { this.sel = null; this.sel2 = null; this.fastenerPanel = false; this.checkClashes(); }
    this.render();
    this.draw();
  }

  /** Every placed part (inside sub-assemblies too) for the kernel: [{id ('I3' or 'I3/I1'), part: {features}, matrix}]. */
  flatParts() {
    const flat = [];
    const expand = (list, parent, pre) => {
      for (const it of list) {
        const M = parent.clone().multiply(new THREE.Matrix4().fromArray(it.matrix)), id = pre ? `${pre}/${it.id}` : it.id;
        if (this.kindOf(it.part) === 'assembly') expand(this.innerList(it), M, id);
        else flat.push({ id, part: { features: this.bodies[it.part]?.features || this.hooks.partData(it.part)?.features || [], threads: this.hooks.partData(it.part)?.threads }, matrix: M.toArray() });
      }
    };
    expand(this.doc.instances, new THREE.Matrix4(), '');
    return flat;
  }

  /** quick: (after a change, in the background) big parts that overlap in many places are estimated, not computed. */
  async checkClashes(quick = false) {
    const run = (this.clashRun = (this.clashRun || 0) + 1);
    if (this.clashRid) cancelRid(this.clashRid); // (the older check's answer would be dropped: its job is stopped)
    const rid = (this.clashRid = newRid('c'));
    this.clashBusy = true;
    if (this.clashPanel) this.renderProps(); // (in the background: the panel on screen stays as it is)
    try {
      const res = await fetch('/api/assembly/clashes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances: this.flatParts(), quick, rid }) });
      const r = await res.json();
      if (run !== this.clashRun) return; // a newer check is on its way
      if (this.clashRid === rid) this.clashRid = null;
      if (r.cancelled || wasCancelled(rid)) { this.clashBusy = false; this.updateClashButton(); if (this.clashPanel) this.renderProps(); return; } // (✕ Stop: the last result stays)
      if (!res.ok) throw new Error(r.error || res.statusText);
      this.clashes = r.clashes;
    } catch (e) {
      if (run !== this.clashRun) return;
      this.clashes = null;
      if (this.clashPanel) this.hooks.toast(e.message, 'error', 6000);
    }
    this.clashBusy = false;
    if (this.focusClash) this.focusClash = (this.clashes || []).find((c) => c.a === this.focusClash.a && c.b === this.focusClash.b) || null; // (moved: the new box)
    this.updateClashButton();
    if (!this.clashPanel) return;
    this.renderProps();
    this.draw();
  }

  /** The placed part (top level) a clash's id is in: 'I3/I1' -> 'I3'. */
  topOf(id) { return String(id).split('/')[0]; }

  renderClashes(box) {
    this.hoverClash = null; // the rows are drawn anew (a row under the mouse goes without a mouseleave)
    const cs = this.clashes, name = (id) => {
      const top = this.inst(this.topOf(id));
      return `${this.partName(top?.part)} ${id}`;
    };
    box.innerHTML = `<h2>⚠ Collisions</h2>
      <p class="hint">Where parts go into each other (touching faces are fine) — checked again after every change. Click one: the view goes to it, the other parts see-through.</p>
      ${this.clashBusy ? `<p class="mp-count">${cs ? '' : 'Checking…'} <button class="btn small" data-a="stopC" title="${esc(t('Stop the check (the last result stays)'))}">✕ Stop</button></p>` : ''}${this.clashBusy && !cs ? '' : !cs ? '' : !cs.length ? '<p class="mp-count ok">✓ No parts overlap.</p>'
        : `<p class="mp-count">${t2('{n} overlap(s)', { n: cs.length })}${this.clashBusy ? ' …' : ''}</p><div class="as-joints">${cs.map((c, i) => `<div class="as-jrow as-clash ${this.focusClash === c ? 'on' : ''}" data-clash="${i}" title="${esc(t('Show it in the view (again: all of them)'))}">
          <span class="as-jt">⚠</span><span class="as-jw"><b data-no-i18n>${esc(name(c.a))}</b> ↔ <b data-no-i18n>${esc(name(c.b))}</b></span>
          <span class="as-jv" ${c.approx ? `title="${esc(t('Big parts that overlap in many places: estimated from their boxes — ↻ Check again computes it'))}"` : ''}>${c.approx ? '≈ ' : ''}${fmt(+c.volume.toFixed(c.volume < 10 ? 2 : 0))} mm³</span>
          <span class="as-jbtn"><button class="mini" data-cpick="${i}" title="Choose these two parts (their joints, their moves)">↗</button></span></div>`).join('')}</div>`}
      <div class="row-actions">${this.focusClash ? '<button class="btn small" data-a="allC">⤢ Show all</button>' : ''}<button class="btn small" data-a="recheck" ${this.clashBusy ? 'disabled' : ''}>↻ Check again</button><button class="btn small" data-a="closeC">Close</button></div>`;
    for (const row of box.querySelectorAll('[data-clash]')) {
      row.addEventListener('mouseenter', () => { this.hoverClash = cs[+row.dataset.clash]; this.draw(); });
      row.addEventListener('mouseleave', () => { this.hoverClash = null; this.draw(); });
      row.addEventListener('click', (e) => { if (!e.target.closest('[data-cpick]')) this.showClash(cs[+row.dataset.clash]); });
    }
    box.querySelector('[data-a=allC]')?.addEventListener('click', () => this.showClash(null));
    for (const b of box.querySelectorAll('[data-cpick]')) b.addEventListener('click', () => {
      const c = cs[+b.dataset.cpick];
      this.clashPanel = false;
      this.focusClash = null;
      this.view.setClashBoxes([]);
      this.sel = this.topOf(c.a);
      this.sel2 = this.topOf(c.b) !== this.sel ? this.topOf(c.b) : null;
      this.render();
      this.draw();
    });
    box.querySelector('[data-a=recheck]').addEventListener('click', () => this.checkClashes());
    box.querySelector('[data-a=stopC]')?.addEventListener('click', () => { if (this.clashRid) cancelRid(this.clashRid); });
    box.querySelector('[data-a=closeC]').addEventListener('click', () => this.toggleClashes());
  }

  /** One collision shown: the view goes to it (its red box), the parts not in it see-through; the same again, or null:
   *  all of them, the whole assembly in view. */
  showClash(c) {
    this.focusClash = c && this.focusClash !== c ? c : null;
    this.hoverClash = null;
    if (this.focusClash) this.view.focusBox(this.focusClash.bbox);
    else this.view.setView('iso');
    this.renderProps();
    this.draw();
  }

  // ------------------------------------------------------------------ 🎨 paint (this assembly's colours), ✂ section
  togglePaint() {
    this.painting = this.painting ? null : { by: 'face', sel: new Map() }; // sel: inst id -> Set(face ids)
    if (this.painting) { if (this.measuring) this.toggleMeasure(); this.cancelJoint(); if (this.bolt) this.cancelBolt(); this.fastenerPanel = false; this.sel = null; }
    this.hint(this.painting ? 'Paint — click a face of a part (or a whole part), Ctrl+click for more, then pick a colour. Esc ends.' : '');
    this.render();
    this.draw();
  }

  clickPaint(h, more) {
    const ps = this.painting;
    if (!h?.inst) { if (!more) ps.sel.clear(); this.drawMarks(); this.renderProps(); return; }
    const body = this.bodyOf(this.inst(h.inst))?.body;
    const ids = ps.by === 'part' ? (body?.faces || []).map((f) => f.id) : h.face ? [h.face.id] : [];
    if (!ids.length) return;
    if (!more) ps.sel.clear();
    const set = ps.sel.get(h.inst) || new Set();
    const all = more && ids.every((x) => set.has(x));
    for (const x of ids) (all ? set.delete(x) : set.add(x));
    if (set.size) ps.sel.set(h.inst, set); else ps.sel.delete(h.inst);
    this.drawMarks();
    this.renderProps();
  }

  renderPaint(box) {
    const ps = this.painting, n = [...ps.sel.values()].reduce((s, x) => s + x.size, 0), parts = ps.sel.size;
    const painted = (id) => paintedFaces(this.bodyOf(this.inst(id))?.body?.faces || [], this.inst(id)?.paint || []);
    const own = [...ps.sel.keys()].map((id) => this.inst(id)).filter(Boolean);
    let first = null;
    for (const [id, set] of ps.sel) { const now = painted(id), f = [...set].find((x) => now.has(x)); if (f !== undefined) { first = now.get(f).color; break; } }
    const colour = ps.by === 'part' ? own.find((x) => x.colour)?.colour : first;
    const anyFaces = this.doc.instances.some((x) => x.paint?.length);
    box.innerHTML = `<h2>🎨 Paint</h2>
      <div class="seg"><button data-by="face" class="${ps.by === 'face' ? 'on' : ''}">▢ Faces</button><button data-by="part" class="${ps.by === 'part' ? 'on' : ''}">◆ Whole parts</button></div>
      <p class="hint">${ps.by === 'part' ? 'Click a part' : 'Click a face'} — Ctrl+click adds more (or takes one away).</p>
      <p class="mp-count">${ps.by === 'part' ? (parts ? t2('{n} part(s) chosen', { n: parts }) : t('Nothing chosen yet')) : n ? t2('{n} face(s) chosen', { n }) : t('Nothing chosen yet')}</p>
      <div class="field"><label>Colour</label><input type="color" data-k="paint" value="${colour || '#d9dee6'}" ${parts ? '' : 'disabled'}></div>
      <div class="row-actions wrap"><button class="btn small" data-a="unpaint" ${parts ? '' : 'disabled'}>↺ Their own colour off</button>
        <button class="btn small" data-a="unpaintAll" ${anyFaces ? '' : 'disabled'}>Clear the painted faces</button></div>
      <p class="hint">The colours belong to this assembly — the parts keep their own (in their tabs and in other assemblies).</p>
      <div class="mp-actions"><button class="btn primary" data-a="donePaint">Done</button></div>`;
    for (const el of box.querySelectorAll('[data-by]')) el.addEventListener('click', () => { ps.by = el.dataset.by; ps.sel.clear(); this.drawMarks(); this.renderProps(); });
    const col = box.querySelector('[data-k=paint]');
    const apply = (color) => {
      for (const [id, set] of ps.sel) {
        const it = this.inst(id), faces = this.bodyOf(it)?.body?.faces;
        if (!it || !faces) continue;
        if (ps.by === 'part') { if (color) it.colour = color; else delete it.colour; continue; }
        const p = repaint(faces, it.paint || [], set, color);
        if (p.length) it.paint = p; else delete it.paint;
      }
      this.draw();
    };
    col.addEventListener('input', () => apply(col.value));
    col.addEventListener('change', () => this.commit());
    box.querySelector('[data-a=unpaint]').addEventListener('click', () => { apply(null); this.commit(); });
    box.querySelector('[data-a=unpaintAll]').addEventListener('click', () => { for (const it of this.doc.instances) delete it.paint; this.commit(); });
    box.querySelector('[data-a=donePaint]').addEventListener('click', () => this.togglePaint());
  }

  toggleSection() {
    if (this.section) {
      this.section = null;
      this.view.setSection(null);
      this.$('.m-section')?.remove();
    } else {
      const bb = this.view.shownBox();
      if (!bb) return;
      this.section = { axis: 'y', offset: sectionMiddle(bb, 'y'), flip: false };
      this.view.setSection(this.section);
      this.renderSection();
    }
    this.renderBar();
  }

  renderSection() {
    const bb = this.view.shownBox();
    if (!this.section || !bb) return;
    sectionBar(this.els.viewport, this.section, bb, { onChange: (s) => this.view.setSection(s), onClose: () => this.toggleSection() });
  }

  // ------------------------------------------------------------------ 📏 measure
  toggleMeasure() {
    this.measuring = this.measuring ? null : { a: null };
    if (this.measuring) { this.cancelJoint(); if (this.bolt) this.cancelBolt(); if (this.painting) this.togglePaint(); }
    else this.view.setSnapMark(null);
    this.view.setMeasure();
    this.hint(this.measuring ? 'Measure — click a spot, then another one (corners snap). Esc ends.' : '');
    if (!this.measuring) this.$('.m-measure')?.remove();
    this.renderBar();
  }

  measureBox(html) {
    let box = this.$('.m-measure');
    if (!box) {
      box = document.createElement('div');
      box.className = 'm-measure';
      this.els.viewport.appendChild(box);
    }
    box.innerHTML = html;
    floatBox(box, this.els.viewport, { kind: 'measure', min: [180, 60] });
  }

  clickMeasure(e) {
    const ms = this.measuring, mp = this.view.measurePoint(e.clientX, e.clientY);
    if (!mp) return;
    const f3 = (p) => `${fmt(+p.x.toFixed(3))}, ${fmt(+p.y.toFixed(3))}, ${fmt(+p.z.toFixed(3))}`;
    const face = mp.face && !mp.corner ? this.worldFace(mp.inst, mp.face.name) : null;
    const who = esc(this.partName(this.inst(mp.inst)?.part));
    if (!ms.a) {
      ms.a = { point: mp.point, face, inst: mp.inst };
      this.view.setMeasure([mp.point]);
      const what = face ? `<b>${face.type === 'cylinder' ? 'Round face' : face.type === 'plane' ? 'Flat face' : 'Face'}</b><span>Of</span><b data-no-i18n>${who} ${mp.inst}</b>
        <span>Area</span><b>${fmt(+face.area.toFixed(2))} mm²</b>${face.radius ? `<span>Ø</span><b>${fmt(+(2 * face.radius).toFixed(3))} mm</b>` : ''}`
        : `<b>${{ corner: 'Corner', midpoint: 'Midpoint', centre: 'Centre' }[mp.snap] || 'Point'}</b><span>Of</span><b data-no-i18n>${who} ${mp.inst}</b>`;
      this.measureBox(`<div class="mm-rows">${what}<span>Point</span><b>${f3(mp.point)}</b></div><p class="hint">Click a second spot for the distance.</p>`);
      return;
    }
    const a = ms.a, p = mp.point, dist = a.point.distanceTo(p);
    let extra = '';
    const fa = a.face, fb = face;
    if (fa?.normal && fb?.normal && Math.abs(fa.normal.dot(fb.normal)) > 0.9999) { // parallel flat faces: the gap between them
      extra = `<span>Faces apart</span><b>${fmt(+Math.abs(fb.centroid.clone().sub(fa.centroid).dot(fa.normal)).toFixed(3))} mm</b>`;
    } else if (fa?.axis && fb?.axis && Math.abs(fa.axis.d.dot(fb.axis.d)) > 0.9999) { // two round faces: their axes
      const v = fb.axis.o.clone().sub(fa.axis.o), off = v.clone().sub(fa.axis.d.clone().multiplyScalar(v.dot(fa.axis.d))).length();
      extra = `<span>Axes apart</span><b>${fmt(+off.toFixed(3))} mm</b>`;
    }
    this.view.setMeasure([a.point, p], `${fmt(+dist.toFixed(3))} mm`);
    this.measureBox(`<div class="mm-rows"><b>Distance</b><span></span><b>${fmt(+dist.toFixed(3))} mm</b>${extra}
      <span>Δx</span><b>${fmt(+Math.abs(p.x - a.point.x).toFixed(3))}</b><span>Δy</span><b>${fmt(+Math.abs(p.y - a.point.y).toFixed(3))}</b><span>Δz</span><b>${fmt(+Math.abs(p.z - a.point.z).toFixed(3))}</b></div>
      <p class="hint">Click again to measure from a new spot.</p>`);
    ms.a = null;
  }

  // ------------------------------------------------------------------ a new bolt: through the parts, holes drilled
  /** 🔩 Screw / pin clicked on a flat face: the point on it (x, y from the face's middle, on a 0.5 mm grid). */
  startBolt(h) {
    const f = h.face, it = this.inst(h.inst), M = new THREE.Matrix4().fromArray(it.matrix), N = new THREE.Matrix3().getNormalMatrix(M);
    if (!f.frame || !f.normal) { this.hooks.toast('A screw goes in at a flat face.', 'warning'); return; }
    const o = new THREE.Vector3(...f.frame.o).applyMatrix4(M), x = new THREE.Vector3(...f.frame.x).applyMatrix3(N).normalize(), n = f.normal.clone().normalize();
    const y = new THREE.Vector3().crossVectors(n, x), q = h.point.clone().sub(o), snap = (v) => Math.round(v * 2) / 2 || 0;
    this.bolt = { inst: h.inst, face: f.name, frame: { o: o.toArray(), x: x.toArray(), y: y.toArray(), n: n.toArray() },
      x: snap(q.dot(x)), y: snap(q.dot(y)), kind: this.bolt?.kind || 'nut', size: this.bolt?.size || 'M3', upto: null };
    this.mode = 'idle';
    this.jointFrom = null;
    this.hoverFace = null;
    this.hint('');
    this.sel = null;
    this.fastenerPanel = false;
    this.render();
    this.draw();
  }

  cancelBolt() { this.bolt = null; this.view.setGhost([]); this.render(); this.draw(); }

  /** What fits through the parts at the bolt's point (fasteners.js planBolt). */
  boltPlan() {
    const b = this.bolt, fr = b.frame, V = (a) => new THREE.Vector3(...a);
    const o = V(fr.o).addScaledVector(V(fr.x), b.x).addScaledVector(V(fr.y), b.y);
    const plan = planBolt(this, { o, d: V(fr.n).negate(), kind: b.kind, size: b.size, upto: b.upto, drillable: (pid) => this.kindOf(pid) === 'model' });
    const off = 'This point is off the face — move it back onto it.';
    if (!plan.error && plan.holes[0].inst !== b.inst) return { error: off, errorKey: off, errorVars: {}, stack: plan.stack };
    return plan;
  }

  renderBolt(box) {
    const b = this.bolt, plan = this.boltPlan(), parts = plan.stack || [], upto = b.upto || parts.length;
    this.view.setGhost(plan.error ? [] : plan.ghost);
    const opt = (cur, v, label) => `<option value="${v}" ${cur === v ? 'selected' : ''}>${esc(label)}</option>`;
    const holeText = (h) => `Ø${fmt(h.d)} ${h.through ? t('through') : t2('{d} mm deep', { d: fmt(h.depth) })} — ${esc(this.partName(h.part))}`;
    box.innerHTML = `<h2>🔩 Screw / pin through parts</h2>
      <p class="hint">${esc(t2('It goes in at the point on {part} and straight through the parts under it. Adding it drills the holes into those parts.', { part: this.partName(this.inst(b.inst)?.part) }))}</p>
      <div class="field"><label>What</label><select data-b="kind">${Object.entries(BOLT_KINDS).map(([k, v]) => opt(b.kind, k, t(v))).join('')}</select></div>
      <div class="field"><label>Size</label><select data-b="size">${Object.keys(SIZES).map((k) => opt(b.size, k, b.kind === 'pin' ? `Ø${SIZES[k].d}` : k)).join('')}</select></div>
      <div class="field"><label>X</label><input type="number" step="0.5" data-b="x" value="${fmt(b.x)}"><span class="unit">mm</span></div>
      <div class="field"><label>Y</label><input type="number" step="0.5" data-b="y" value="${fmt(b.y)}"><span class="unit">mm</span></div>
      <p class="hint">X, Y from the middle of the face — or click another point.</p>
      ${parts.length ? `<h3>Through</h3><div class="as-joints as-bolt-parts">${parts.map((p, k) => `<label class="as-jrow"><input type="checkbox" data-upto="${k + 1}" ${k < upto ? 'checked' : ''} ${k < 2 ? 'disabled' : ''}>
        <span class="as-jw"><b data-no-i18n>${esc(this.partName(p.part))}</b> <i>${p.inst}</i> · ${fmt(p.tout - p.tin)} mm</span></label>`).join('')}</div>` : ''}
      ${plan.error ? `<p class="mp-count as-bolt-msg bad">⚠ ${esc(t2(plan.errorKey, plan.errorVars))}</p>`
        : `<p class="mp-count as-bolt-msg">✓ <b data-no-i18n>${esc(plan.text)}</b></p><p class="hint as-bolt-holes" data-no-i18n>${esc(t('Holes'))}: ${plan.holes.map(holeText).join('; ')}</p>`}
      <div class="row-actions"><button class="btn small primary" data-a="addBolt" ${plan.error ? 'disabled' : ''}>Add</button><button class="btn small" data-a="cancelBolt">Cancel</button></div>`;
    for (const el of box.querySelectorAll('[data-b]')) {
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const k = el.dataset.b, v = k === 'x' || k === 'y' ? parseFloat(String(el.value).replace(',', '.')) : el.value;
        if ((k === 'x' || k === 'y') && !Number.isFinite(v)) return;
        b[k] = v;
        this.renderProps();
      });
    }
    for (const el of box.querySelectorAll('[data-upto]')) {
      el.addEventListener('change', () => { const k = +el.dataset.upto; b.upto = el.checked ? k : k - 1; this.renderProps(); });
    }
    box.querySelector('[data-a=addBolt]').addEventListener('click', () => this.addBolt(plan));
    box.querySelector('[data-a=cancelBolt]').addEventListener('click', () => this.cancelBolt());
  }

  /** Drill the plan's holes into the parts (a hole step in each part's own model, marked as this assembly's bolt),
   *  then put the screw + nut / insert, or the pin, in them, held by joints. */
  async addBolt(plan, quiet = false) {
    if (!plan || plan.error) return 0;
    const tag = `${this.hooks.selfId?.() || 'A'}:`;
    const id = `B${Math.max(0, ...(this.doc.bolts || []).map((x) => parseInt(String(x.id).slice(1), 10) || 0)) + 1}`;
    const o = new THREE.Vector3(...plan.o), D = new THREE.Vector3(...plan.d), holes = [], names = [];
    for (const h of plan.holes) {
      const it = this.inst(h.inst), data = this.hooks.partData(it.part), body = this.bodyOf(it)?.body;
      const Mi = new THREE.Matrix4().fromArray(it.matrix).invert();
      const pL = o.clone().addScaledVector(D, h.tin).applyMatrix4(Mi), nL = D.clone().negate().transformDirection(Mi);
      // on the part's own face where it goes in (the hole then follows that face), else on a plane of its own there
      const f = (body?.faces || []).find((x) => x.name === h.inFace && x.type === 'plane' && x.frame
        && new THREE.Vector3(...x.frame.n).dot(nL) > 0.9999 && Math.abs(pL.clone().sub(new THREE.Vector3(...x.frame.o)).dot(nL)) < 0.05);
      let plane, u = 0, v = 0;
      if (f) {
        const fo = new THREE.Vector3(...f.frame.o), fx = new THREE.Vector3(...f.frame.x), fy = new THREE.Vector3().crossVectors(new THREE.Vector3(...f.frame.n), fx);
        plane = { face: { name: f.name }, frame: f.frame };
        u = pL.clone().sub(fo).dot(fx);
        v = pL.clone().sub(fo).dot(fy);
      } else {
        const x = new THREE.Vector3(Math.abs(nL.x) < 0.9 ? 1 : 0, Math.abs(nL.x) < 0.9 ? 0 : 1, 0).projectOnPlane(nL).normalize();
        plane = { frame: { o: pL.toArray().map((q) => +q.toFixed(6)), x: x.toArray().map((q) => +q.toFixed(9)), n: nL.toArray().map((q) => +q.toFixed(9)) } };
      }
      const pt = [+u.toFixed(4), +v.toFixed(4)];
      // two of the same part in the stack, lying alike: one hole serves both
      const same = holes.find((x) => x.part === it.part && JSON.stringify(x.feature.points[0]) === JSON.stringify(pt) && JSON.stringify(x.feature.plane) === JSON.stringify(plane) && x.feature.d === h.d);
      if (same) { names.push(`${same.feature.id}:hole:0`); continue; }
      const fid = `F${Math.max(0, ...data.features.map((x) => parseInt(String(x.id).slice(1), 10) || 0)) + 1}`;
      const feature = { id: fid, type: 'hole', name: t2('Hole for {what}', { what: plan.text }), plane, points: [pt], d: h.d, through: h.through,
        ...(h.through ? {} : { depth: h.depth }), bolt: tag + id };
      data.features.push(feature);
      holes.push({ part: it.part, feature: structuredClone(feature) });
      names.push(`${fid}:hole:0`);
    }
    this.doc.bolts = [...(this.doc.bolts || []), { id, text: plan.text, holes }];
    await this.refresh(); // the parts with their new holes
    const first = plan.holes[0], last = plan.holes[plan.holes.length - 1];
    const c = plan.kind === 'pin'
      ? { kind: 'pin', text: plan.text, bolt: id, size: plan.pin, length: plan.length, entry: { inst: first.inst, hole: names[0], plane: first.inFace } }
      : { kind: 'screw', text: plan.text, bolt: id, size: plan.size, length: plan.length, entry: { inst: first.inst, hole: names[0], plane: first.inFace },
        insert: plan.kind === 'insert' ? { inst: last.inst, hole: names[names.length - 1], plane: last.inFace, length: plan.insert.length } : null,
        nut: plan.kind === 'nut' ? { inst: last.inst, hole: names[names.length - 1], plane: last.outFace } : null };
    this.bolt = null;
    this.view.setGhost([]);
    const n = await this.addFasteners([c], true);
    if (!quiet) {
      const where = [...new Set(plan.holes.map((h) => this.partName(h.part)))].join(', ');
      this.hooks.toast(t2('Added {what} — its holes are drilled into {parts} (a hole step in each part; Ctrl+Z takes it all back).', { what: plan.text, parts: where }), 'ok', 6000);
    }
    return n;
  }

  /** A fastener out: its screw, nut / insert or pin, and the holes drilled for it (when they were). */
  async removeFastener(gid) {
    const insts = this.doc.instances.filter((i) => i.fastener?.id === gid);
    if (!insts.length) return false;
    const f = insts[0].fastener, ids = new Set(insts.map((i) => i.id));
    this.doc.instances = this.doc.instances.filter((i) => !ids.has(i.id));
    this.doc.mates = (this.doc.mates || []).filter((m) => !ids.has(m.move) && !ids.has(m.onto));
    if (ids.has(this.sel)) this.sel = null;
    if (ids.has(this.sel2)) this.sel2 = null;
    this.hoverJoint = null;
    if (f.bolt) { this.doc.bolts = (this.doc.bolts || []).filter((b) => b.id !== f.bolt); this.syncDrills(); await this.refresh(); }
    this.commit();
    this.hooks.toast(t2(f.bolt ? '{what} taken out, with the holes drilled for it.' : '{what} taken out.', { what: f.text }), 'ok', 4000);
    return true;
  }

  /** The hole steps this assembly drilled into parts, as its bolts say (after an undo / redo). */
  syncDrills() {
    const tag = `${this.hooks.selfId?.() || 'A'}:`, want = new Map();
    for (const b of this.doc.bolts || []) for (const h of b.holes) want.set(h.part, [...(want.get(h.part) || []), h.feature]);
    for (const p of this.hooks.parts()) {
      const data = this.hooks.partData(p.id);
      if (!Array.isArray(data?.features)) continue;
      const mine = want.get(p.id) || [];
      const keep = data.features.filter((f) => !String(f.bolt || '').startsWith(tag) || mine.some((w) => w.id === f.id && w.bolt === f.bolt));
      const add = mine.filter((w) => !keep.some((f) => f.id === w.id));
      if (keep.length !== data.features.length || add.length) data.features = [...keep, ...structuredClone(add)];
    }
  }

  /** Put fasteners in: each a standard part held by joints (pin in hole + touch / flush). */
  async addFasteners(list, quiet = false) {
    let n = 0;
    for (const c of list.filter(Boolean)) {
      const gid = `K${Math.max(0, ...this.doc.instances.map((i) => parseInt(String(i.fastener?.id || '').slice(1), 10) || 0)) + 1}`;
      const tag = { id: gid, text: c.text || `${c.size}×${c.length} ${c.kind}`, ...(c.bolt ? { bolt: c.bolt } : {}) };
      const place = (kind, size, length) => {
        const mdl = fastenerModel(kind, size, length), it = { id: this.newId(), part: this.ensurePart(mdl), matrix: ID(), fastener: tag };
        this.doc.instances.push(it);
        return { it, faces: mdl.faces };
      };
      const join = (a, aFace, b, bFace, type) => this.addJoint({ inst: a.id, face: { name: aFace } }, { inst: b, face: { name: bFace } }, type);
      if (c.kind === 'pin') {
        const p = place('pin', c.size, c.length);
        join(p.it, p.faces.shaft, c.entry.inst, c.entry.hole, 'axis');
        join(p.it, p.faces.top, c.entry.inst, c.entry.plane, 'flush');
      } else {
        const s = place('screw', c.size, c.length);
        join(s.it, s.faces.shaft, c.entry.inst, c.entry.hole, 'axis');
        join(s.it, s.faces.seat, c.entry.inst, c.entry.plane, 'touch');
        if (c.insert) {
          const i = place('insert', c.size, c.insert.length);
          join(i.it, i.faces.shaft, c.insert.inst, c.insert.hole, 'axis');
          join(i.it, i.faces.top, c.insert.inst, c.insert.plane, 'flush');
        }
        if (c.nut) { // on the far side: the nut on the last part's face
          const nt = place('nut', c.size);
          join(nt.it, nt.faces.shaft, c.nut.inst, c.nut.hole, 'axis');
          join(nt.it, nt.faces.seat, c.nut.inst, c.nut.plane, 'touch');
        }
      }
      n++;
    }
    if (!n) return 0;
    this.hoverCand = null;
    await this.refresh(); // builds the new parts and puts them in place by their joints
    this.commit();
    if (!quiet) this.hooks.toast(`Added ${n} fastener(s) — they follow the parts (each a part of the project you can open).`, 'ok', 4000);
    return n;
  }

  // ------------------------------------------------------------------ editing a part from the assembly
  /** May this part be changed from this assembly? Locked unless the user unlocks it (no accidental changes). */
  editable(pid) { return !!this.doc.editable?.[pid]; }

  toggleEditable(pid) {
    const ed = { ...(this.doc.editable || {}) };
    if (ed[pid]) delete ed[pid];
    else ed[pid] = true;
    this.doc.editable = ed;
    this.render();
    this.hooks.onChange?.();
  }

  editHtml(it) {
    if (!this.hooks.editInPlace || this.kindOf(it.part) !== 'model') return '';
    const ed = this.editable(it.part);
    return `<h3>Edit</h3><div class="row-actions wrap"><button class="btn small ${ed ? 'primary' : ''}" data-a="editHere" ${ed ? '' : 'disabled'} title="Change its part in the 3D modeler, the rest of the assembly see-through around it (or double-click it)">✎ Edit it here</button>
      <button class="btn small ${ed ? 'on' : ''}" data-a="editLock" title="${ed ? 'Lock it: its part cannot be changed from this assembly' : 'Unlock it to change its part from this assembly'}">${ed ? '🔓 Editable from here' : '🔒 Locked'}</button></div>
      <p class="hint">${ed ? 'Every copy of its part changes (here and in other assemblies).' : 'Unlock it to change its part from here — locked, it cannot be changed by accident.'}</p>`;
  }

  /** Open a placed part's model in the 3D modeler, in place: the other parts shown see-through around it. */
  async editInPlace(instId) {
    const it = this.inst(instId);
    if (!it || !this.hooks.editInPlace) return;
    if (this.kindOf(it.part) !== 'model') { this.hooks.toast('Only 3D model parts can be changed here — open a quick part in its own tab.', 'info', 4000); return; }
    if (!this.editable(it.part)) { this.hooks.toast('Editing this part from the assembly is locked — 🔓 unlock it in its panel first.', 'warning', 5000); return; }
    const Mi = new THREE.Matrix4().fromArray(it.matrix).invert();
    const context = this.doc.instances.filter((o) => o.id !== instId && this.bodyOf(o)?.body).map((o) => ({
      positions: this.bodyOf(o).body.positions, matrix: Mi.clone().multiply(new THREE.Matrix4().fromArray(o.matrix)).toArray() }));
    await this.hooks.editInPlace(it.part, { context, back: this.hooks.selfId?.(), assembly: this.hooks.parts().find((p) => p.id === this.hooks.selfId?.())?.name, inst: instId });
  }

  /** Colour and see-through of a placed part: its own here (↺ back to its part's). */
  lookHtml(it) {
    const data = this.hooks.partData(it.part) || {}, l = this.lookOf(it), own = !!it.colour || Number.isFinite(it.opacity);
    const hex = `#${(l.colour ?? COLORS[Math.max(0, this.modelParts().findIndex((p) => p.id === it.part)) % COLORS.length]).toString(16).padStart(6, '0')}`;
    const pc = Math.round((1 - l.opacity) * 100);
    return `<div class="field"><label>Colour</label><input type="color" data-look="colour" value="${hex}"></div>
      <div class="field mp-look"><label>See-through</label><input type="range" min="0" max="90" step="5" data-look="clear" value="${pc}"><span class="unit">${pc} %</span></div>
      <p class="hint">${own ? 'Its own look in this assembly.' : data.color || Number.isFinite(data.opacity) ? "As its part (set in the part's panel)." : 'The assembly colours.'}</p>
      ${own ? '<div class="row-actions"><button class="btn small" data-look="reset">↺ As its part</button></div>' : ''}
      ${this.kindOf(it.part) === 'model' ? `<label class="check as-light" title="${esc(t('Simplified: a coarser mesh and less data — quicker to load and show; its joints still work, its edges cannot be picked. Collisions and drawings use the full part.'))}">
        <input type="checkbox" data-look="light" ${this.bodies[it.part]?.body?.light ? 'checked' : ''}> 🪶 ${esc(t('Simplified'))}${this.doc.light?.[it.part] === undefined && this.bodies[it.part]?.body?.light ? ` <i>${esc(t('(a big part: by itself)'))}</i>` : ''}</label>` : ''}`;
  }

  bindLook(box, it) {
    box.querySelector('[data-look=light]')?.addEventListener('change', async (e) => { // 🪶 simplified / full data, for every copy of the part
      this.doc.light = { ...(this.doc.light || {}), [it.part]: e.target.checked };
      await this.refresh();
      this.commit();
    });
    const col = box.querySelector('[data-look=colour]'), clr = box.querySelector('[data-look=clear]');
    col?.addEventListener('input', () => { it.colour = col.value; this.draw(); });
    col?.addEventListener('change', () => this.commit());
    clr?.addEventListener('input', () => { it.opacity = +(1 - clr.value / 100).toFixed(2); clr.nextElementSibling.textContent = `${clr.value} %`; this.draw(); });
    clr?.addEventListener('change', () => this.commit());
    box.querySelector('[data-look=reset]')?.addEventListener('click', () => { delete it.colour; delete it.opacity; this.commit(); });
  }

  /** "the top of Extrude 1" for a face of a placed part. */
  faceText(instId, name) { return this.partFaceText(this.inst(instId)?.part, name); }

  /** The same for a face of part `pid` (a sub-assembly's: "Arm I2: the top of Extrude 1"). */
  partFaceText(pid, name) {
    if (String(name).includes('/')) { // a face of a part inside a sub-assembly
      const [sub, rest] = String(name).split(/\/(.*)/s), si = (this.hooks.partData(pid)?.instances || []).find((x) => x.id === sub);
      return `${this.partName(si?.part)} ${sub}: ${si ? this.partFaceText(si.part, rest) : rest}`;
    }
    const pd = this.hooks.partData(pid), feats = pd?.features || [];
    const [fid, role] = String(name).split(':'), g = feats.find((f) => f.id === fid);
    if (pd?.library || g?.type === 'solid') { // a library or imported part: its steps' names mean nothing to the user — what the face is
      const f = this.bodies[pid]?.body?.faces?.find((x) => x.name === name || (x.names || []).includes(name));
      if (f?.type === 'cylinder' && f.radius) return t2('the round face Ø{d}', { d: fmt(+(2 * f.radius).toFixed(2)) });
      if (f?.type === 'plane') return t('a flat face');
    }
    if (fid === 'Q1') return `${t('face')} ${String(role).slice(1)}`;
    const what = { end: 'the top of', start: 'the bottom of', side: 'a wall of', hole: 'hole of', round: 'a rounding of', bottom: 'a hole bottom of' }[role] || 'a face of';
    return g ? `${t(what)} ${g.name}` : name;
  }

  /** The joints of a part (or all, id null) as rows: what holds what, its gap / flip, ✕. */
  jointsHtml(id, list = null) {
    const all = list || (this.doc.mates || []).filter((m) => id === null || m.move === id || m.onto === id);
    if (!all.length) return id === null ? '' : '<p class="hint">Not joined to anything — it stays where you put it.</p>';
    const fast = (m) => this.inst(m.move)?.fastener?.id, groups = [...new Set(all.map(fast).filter(Boolean))];
    const js = all.filter((m) => !fast(m)), bad = all.filter((m) => this.health?.get(m.id)?.ok === false).length;
    const dbl = esc(t('Double-click: give it your own name')); // (translated here: a joint's own name is not, nor its tooltip then)
    const fRow = (gid) => {
      const f = this.doc.instances.find((i) => i.fastener?.id === gid).fastener, mine = (this.doc.mates || []).filter((m) => fast(m) === gid);
      const into = [...new Set(mine.map((m) => m.onto).filter((x) => !this.inst(x)?.fastener))].map((x) => this.partName(this.inst(x)?.part));
      const off = mine.filter((m) => this.health?.get(m.id)?.ok === false);
      return `<div class="as-jrow as-frow ${off.length ? 'bad' : ''}" data-frow="${gid}"><span class="as-jt">🔩</span>
        <span class="as-jw"><b data-no-i18n>${esc(f.text || '')}</b> · ${esc(t('through'))} <span data-no-i18n>${esc(into.join(', '))}</span>${off.length ? ` — ⚠ ${esc(t('it does not sit in its holes'))}` : ''}</span>
        <span class="as-jbtn"><button class="mini danger" data-fdel="${gid}" title="${esc(f.bolt ? 'Take it out, with the holes drilled for it' : 'Take it out (its screw, nut / insert)')}">✕</button></span></div>`;
    };
    return `<h3>Joints</h3>${bad ? `<p class="mp-count bad as-jbad">⚠ ${esc(t2('{n} joint(s) do not hold — see the red ones.', { n: bad }))}</p>` : ''}<datalist id="as-ticks"><option value="-180"></option><option value="-90"></option><option value="0"></option><option value="90"></option><option value="180"></option></datalist><div class="as-joints">${groups.map(fRow).join('')}${js.map((m) => {
      const t = JOINT_TYPES[m.type || 'touch'] || JOINT_TYPES.touch, a = this.inst(m.move), b = this.inst(m.onto);
      const val = m.type === 'touch' || m.type === 'gap' || m.type === 'flush' || !m.type
        ? `<label class="as-jv">${m.type === 'flush' ? 'offset' : 'gap'} <input type="number" step="any" data-jgap="${m.id}" value="${fmt(m.gap || 0)}"> mm</label>`
        : m.type === 'axis' ? `<label class="as-jv" title="Distance along the axis between the facing ends of the two round faces (e.g. two plates 30 mm apart). Empty: it slides freely.">↕ <input type="number" step="any" data-jdist="${m.id}" value="${Number.isFinite(m.dist) ? fmt(m.dist) : ''}" placeholder="free"> mm</label>
          <button class="mini" data-jflip="${m.id}" title="Turn it the other way round">⇅</button>`
        : m.type === 'perp' ? '<span></span>'
        : `${m.type === 'angle' ? `<label class="as-jv">∠ <input type="number" step="any" data-jval="${m.id}" value="${fmt(m.value || 0)}"> °</label>` : ''}<button class="mini" data-jflip="${m.id}" title="Turn it the other way round">⇅</button>`;
      const spin = Math.round(Number.isFinite(m.angle) ? m.angle : this.spinNow(m)), why = this.whyNot(m);
      const turns = m.type !== 'parallel', rot = Number.isFinite(m.angle);
      return `<div class="as-jrow ${m.broken || why ? 'bad' : ''} ${m.locked ? 'locked' : ''}" data-jrow="${m.id}"><span class="as-jt">${t.icon} <span class="as-jname ${m.name ? 'own' : ''}" data-jname="${m.id}" title="${dbl}" ${m.name ? 'data-no-i18n' : ''}>${esc(m.name || t.name)}</span> <i>${m.id}</i></span>
        <span class="as-jw"><b data-no-i18n>${esc(this.partName(a?.part))}</b> <i>${m.move}</i> · ${esc(this.faceText(m.move, m.face))} → <b data-no-i18n>${esc(this.partName(b?.part))}</b> <i>${m.onto}</i> · ${esc(this.faceText(m.onto, m.ontoFace))}${m.broken ? ' — ⚠ a face is gone' : ''}</span>
        ${why ? `<span class="as-jwhy" data-no-i18n>⚠ ${esc(why)}</span>` : ''}
        ${val}<span class="as-jbtn"><button class="mini ${m.locked ? 'on' : ''}" data-jlock="${m.id}" title="${m.locked ? 'Locked: moving the part by hand cannot break it — click to unlock' : 'Lock it: then it cannot be broken by moving the part'}">${m.locked ? '🔒' : '🔓'}</button><button class="mini danger" data-jdel="${m.id}" title="Remove this joint (the part stays where it is)" ${m.locked ? 'disabled' : ''}>✕</button></span>
        ${this.gapSlider(m)}
        ${turns ? `<label class="as-jspin" title="${rot ? 'The angle its turn is locked at, against the other part — to turn both, use Moves of the part they are on' : 'Turn the part about this joint (about the axis, or on the face) — it stays free to turn'}">↻ <input type="range" min="-180" max="180" step="1" list="as-ticks" data-jspin="${m.id}" value="${spin}">
        <input type="number" step="any" data-jspinn="${m.id}" value="${spin}">°<button class="mini as-jrot ${rot ? 'on' : ''}" data-jrot="${m.id}" title="${rot ? 'Its turn is locked here — click to let it turn freely' : 'It may turn freely — click to lock its turn where it is now'}">${rot ? '🔒 locked' : '🔓 free'}</button></label>` : ''}</div>`;
    }).join('')}</div>`;
  }

  /** ⇅ A joint the other way round: a concentric one turns its part over end to end once (on its axis, about the
   *  middle of its round face — it then keeps that way); the others swap their direction (flip). */
  flipJoint(m) {
    if ((m.type || 'touch') === 'axis') {
      delete m.flip;
      const it = this.inst(m.move), f = this.worldFace(m.move, m.face), d = f.axis.d.clone().normalize();
      const mid = f.axis.o.clone().addScaledVector(d, f.span ? (f.span[0] + f.span[1]) / 2 : 0);
      const side = new THREE.Vector3(Math.abs(d.x) < 0.9 ? 1 : 0, Math.abs(d.x) < 0.9 ? 0 : 1, 0).projectOnPlane(d).normalize();
      const R = new THREE.Matrix4().makeTranslation(mid.x, mid.y, mid.z).multiply(new THREE.Matrix4().makeRotationAxis(side, Math.PI))
        .multiply(new THREE.Matrix4().makeTranslation(-mid.x, -mid.y, -mid.z));
      it.matrix = R.multiply(new THREE.Matrix4().fromArray(it.matrix)).toArray();
    } else m.flip = !m.flip;
    this.applyMates();
  }

  /** Turn a joined part about one of its joints by `deg` (about the axis, or on the face), its joints holding it —
   *  the turn stays free (not locked). */
  turnAbout(m, deg) {
    const fA = this.worldFace(m.onto, m.ontoFace), fB = this.worldFace(m.move, m.face);
    const dir = (m.type === 'axis' || !fA.normal ? fA.axis.d : fA.normal).clone().normalize();
    const p = m.type === 'axis' || !fA.normal ? fA.axis.o : fB.centroid;
    const R = new THREE.Matrix4().makeTranslation(p.x, p.y, p.z).multiply(new THREE.Matrix4().makeRotationAxis(dir, (deg * Math.PI) / 180))
      .multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z));
    const it = this.inst(m.move), was = [...it.matrix];
    it.matrix = this.holdPart(m.move, R.multiply(new THREE.Matrix4().fromArray(it.matrix))).toArray();
    this.applyMates(coupledWith(this, m.move).length ? { id: m.move, was, mo: { kind: 'turn', dir, point: p }, amount: deg } : null); // (⚙ coupled: the other part follows)
  }

  /** Each joint: does it hold where its part is now (jointMiss)? -> this.health: id -> {mm, deg, ok}. */
  checkJoints() {
    const h = new Map();
    for (const m of this.doc.mates || []) {
      try { const r = jointMiss(m, this.worldFace(m.move, m.face), this.worldFace(m.onto, m.ontoFace)); if (r) h.set(m.id, r); } catch { /* not built yet */ }
    }
    this.health = h;
    this.whyCache = new Map();
    return h;
  }

  /** The joints that do not hold now. */
  unmet() { return (this.doc.mates || []).filter((m) => this.health?.get(m.id)?.ok === false); }

  /** Why a joint does not hold (null: it holds): how far off, and which other joint of the part holds it elsewhere —
   *  the one that, left out, lets this one hold. */
  whyNot(m) {
    const r = this.health?.get(m.id);
    if (!r || r.ok) return null;
    if (this.whyCache?.has(m.id)) return this.whyCache.get(m.id);
    const off = [r.mm >= 0.05 ? `${fmt(+r.mm.toFixed(2))} mm` : '', r.deg >= 0.1 ? `${fmt(+r.deg.toFixed(1))}°` : ''].filter(Boolean).join(t(' and '));
    let by = null;
    const it = this.inst(m.move), M0 = new THREE.Matrix4().fromArray(it.matrix), lp = (this.loops || []).find((l) => !l.closed && l.parts.includes(m.move));
    if (lp) { // a closed loop that cannot close: not one joint's fault
      const why = t2('Not held — {off} off: the closed loop {parts} cannot close here — a part is too short or too long for this place. Move one of them back, or change a joint.', { off, parts: lp.parts.join('–') });
      this.whyCache.set(m.id, why);
      return why;
    }
    for (const o of (this.doc.mates || []).filter((x) => x.move === m.move && x.id !== m.id)) {
      try {
        const M = this.holdPart(m.move, M0.clone(), true, o.id);
        if (jointMiss(m, this.worldFace(m.move, m.face, M), this.worldFace(m.onto, m.ontoFace))?.ok) { by = o; break; }
      } catch { /* try the next one */ }
    }
    const jt = (x) => `${t((JOINT_TYPES[x.type || 'touch'] || JOINT_TYPES.touch).name)}${x.name ? ` “${x.name}”` : ''}`;
    const why = by ? t2('Not held — {off} off: {id} ({type}) holds {part} elsewhere. Change one of them, or ✕ one.', { off, id: by.id, type: jt(by), part: this.partName(it.part) })
      : t2('Not held — {off} off: these faces cannot be put like that (with its other joints).', { off });
    this.whyCache.set(m.id, why);
    return why;
  }

  /** The slider of a joint's gap (flat faces) or distance along the axis (concentric; only when it is set): ±50 mm, wider
   *  round a bigger value. */
  gapSlider(m) {
    const flat = !m.type || ['touch', 'gap', 'flush'].includes(m.type), axis = m.type === 'axis' && Number.isFinite(m.dist);
    if (!flat && !axis) return '';
    const v = flat ? +(m.gap || 0) : m.dist, span = Math.max(50, Math.ceil((Math.abs(v) * 2) / 10) * 10);
    return `<label class="as-jspin as-jgap" title="${flat ? 'The gap between the two faces (mm) — 0: touching' : 'The distance along the axis (mm)'}">↕ <input type="range" min="${-span}" max="${span}" step="0.5" data-jgaps="${m.id}" value="${v}">
      <input type="number" step="any" data-jgapn="${m.id}" value="${+v.toFixed(3)}">mm</label>`;
  }

  /** A Flush made on a part that is held already (by other joints, a loop) with the faces parallel: its offset as the
   *  parts stand now (rounded to 0.5 mm), so the part does not jump (a slider in line with a crank keeps its line)
   *  -> the offset (mm) or null (not parallel). */
  keepOffset(m) {
    try {
      const fB = this.worldFace(m.move, m.face), fA = this.worldFace(m.onto, m.ontoFace);
      if (!fA.normal || !fB.normal || fA.normal.dot(fB.normal) < 0.999) return null;
      m.gap = Math.round(fB.centroid.clone().sub(fA.centroid).dot(fA.normal) * 2) / 2 || 0;
      return m.gap;
    } catch { return null; }
  }

  /** Two holes made concentric: the distance between them along the axis is set (as it is once on the axis,
   *  rounded to 0.5 mm, not below 0 — overlapping parts end up touching), so it can be typed. */
  autoDistance(m) {
    try {
      this.applyMates();
      const g = axialGap(this.worldFace(m.move, m.face), this.worldFace(m.onto, m.ontoFace));
      if (!g) return;
      m.side = g.side;
      m.dist = Math.max(0, Math.round(g.dist * 2) / 2);
    } catch { /* faces not built: it stays free */ }
  }

  /** How far a joined part is turned about its joint now (degrees). */
  spinNow(m) {
    try {
      const fB = this.worldFace(m.move, m.face), fA = this.worldFace(m.onto, m.ontoFace);
      return spinOf(fB, fA, m.type === 'axis' || !fA.normal ? fA.axis.d : fA.normal);
    } catch { return 0; }
  }

  bindJointRows(box) {
    for (const row of box.querySelectorAll('.as-jrow.locked[data-jrow]')) { // locked 🔒: only unlocking changes it
      const free = !row.querySelector('[data-jrot]')?.classList.contains('on'); // (a free turn can still be driven)
      for (const el of row.querySelectorAll('input, button:not([data-jlock])')) {
        if (free && (el.matches('[data-jspin], [data-jspinn]'))) continue;
        el.disabled = true;
        el.title = 'Locked 🔒 — unlock the joint to change it';
      }
    }
    for (const row of box.querySelectorAll('[data-frow]')) {
      const ids = (this.doc.mates || []).filter((m) => this.inst(m.move)?.fastener?.id === row.dataset.frow).map((m) => m.id);
      row.addEventListener('mouseenter', () => { this.hoverJoint = ids; this.drawMarks(); });
      row.addEventListener('mouseleave', () => { this.hoverJoint = null; this.drawMarks(); });
    }
    for (const el of box.querySelectorAll('[data-fdel]')) el.addEventListener('click', () => this.removeFastener(el.dataset.fdel));
    for (const row of box.querySelectorAll('[data-jrow]')) {
      row.addEventListener('mouseenter', () => { this.hoverJoint = row.dataset.jrow; this.drawMarks(); });
      row.addEventListener('mouseleave', () => { this.hoverJoint = null; this.drawMarks(); });
    }
    for (const el of box.querySelectorAll('[data-jgap]')) {
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const m = this.doc.mates.find((x) => x.id === el.dataset.jgap), v = parseFloat(String(el.value).replace(',', '.'));
        if (!m || !Number.isFinite(v)) return;
        m.gap = v;
        if (m.type === 'touch' && v) m.type = 'gap';
        this.applyMates();
        this.commit();
      });
    }
    for (const el of box.querySelectorAll('[data-jdist]')) {
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const m = this.doc.mates.find((x) => x.id === el.dataset.jdist), raw = String(el.value).trim(), v = parseFloat(raw.replace(',', '.'));
        if (!m) return;
        if (!raw) { delete m.dist; delete m.side; } else if (Number.isFinite(v)) {
          if (!m.side) { try { m.side = axialGap(this.worldFace(m.move, m.face), this.worldFace(m.onto, m.ontoFace))?.side || 1; } catch { m.side = 1; } }
          m.dist = v;
        } else return;
        this.applyMates();
        this.commit();
      });
    }
    for (const el of box.querySelectorAll('[data-jname]')) {
      el.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        const m = this.doc.mates.find((x) => x.id === el.dataset.jname);
        if (!m.name) el.textContent = '';
        renameInPlace(el, (n) => { const v = String(n || '').trim(); if (v) m.name = v; else delete m.name; this.commit(); });
      });
    }
    for (const el of box.querySelectorAll('[data-jrot]')) {
      el.addEventListener('click', () => {
        const m = this.doc.mates.find((x) => x.id === el.dataset.jrot);
        if (Number.isFinite(m.angle)) delete m.angle;
        else m.angle = Math.round(this.spinNow(m));
        this.applyMates();
        this.commit();
      });
    }
    for (const el of box.querySelectorAll('[data-jval]')) {
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const m = this.doc.mates.find((x) => x.id === el.dataset.jval), v = parseFloat(String(el.value).replace(',', '.'));
        if (!m || !Number.isFinite(v)) return;
        m.value = Math.max(0, Math.min(180, v));
        this.applyMates();
        this.commit();
      });
    }
    // 𝑥 a joint's gap / distance / angle also takes an expression of the project's parameters (kept in its expr)
    for (const [attr, key] of [['jgap', 'gap'], ['jdist', 'dist'], ['jval', 'value']]) {
      for (const el of box.querySelectorAll(`[data-${attr}]`)) exprField(el, { owner: () => this.doc.mates.find((x) => x.id === el.dataset[attr]), key });
    }
    for (const el of box.querySelectorAll('[data-jflip]')) {
      el.addEventListener('click', () => { this.flipJoint(this.doc.mates.find((x) => x.id === el.dataset.jflip)); this.commit(); });
    }
    for (const el of box.querySelectorAll('[data-jlock]')) {
      el.addEventListener('click', () => { const m = this.doc.mates.find((x) => x.id === el.dataset.jlock); m.locked = !m.locked; this.commit(); });
    }
    for (const sl of box.querySelectorAll('[data-jgaps]')) {
      const m = this.doc.mates.find((x) => x.id === sl.dataset.jgaps), num = box.querySelector(`[data-jgapn="${m.id}"]`);
      const flat = m.type !== 'axis';
      const set = (v, final) => {
        if (flat) { m.gap = v; if ((m.type || 'touch') === 'touch' && v) m.type = 'gap'; } else m.dist = v;
        const typed = box.querySelector(flat ? `[data-jgap="${m.id}"]` : `[data-jdist="${m.id}"]`);
        if (typed) typed.value = +(+v).toFixed(3);
        this.applyMates();
        if (final) this.commit(); else this.draw();
      };
      sl.addEventListener('input', () => {
        let v = +sl.value;
        if (Math.abs(v) <= 0.75) { v = 0; sl.value = 0; } // the 0 catches
        num.value = v;
        set(v, false);
      });
      sl.addEventListener('change', () => set(+num.value, true));
      num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
      num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) set(v, true); });
    }
    for (const sl of box.querySelectorAll('[data-jspin]')) {
      const m = this.doc.mates.find((x) => x.id === sl.dataset.jspin), num = box.querySelector(`[data-jspinn="${m.id}"]`);
      const set = (v, final) => {
        if (Number.isFinite(m.angle)) { m.angle = v; this.applyMates(); } // locked: where it is locked
        else { try { this.turnAbout(m, v - this.spinNow(m)); } catch { return; } } // free: turned, it stays free
        if (final) this.commit(); else this.draw();
      };
      sl.addEventListener('input', () => {
        let v = +sl.value;
        const near = Math.round(v / 90) * 90;
        if (Math.abs(v - near) <= 4) { v = near; sl.value = v; }
        num.value = v;
        set(v, false);
      });
      sl.addEventListener('change', () => set(+num.value, true));
      num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
      num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) set(v, true); });
    }
    for (const el of box.querySelectorAll('[data-jdel]')) {
      el.addEventListener('click', () => { this.doc.mates = this.doc.mates.filter((x) => x.id !== el.dataset.jdel); this.hoverJoint = null; this.applyMates(); this.commit(); });
    }
  }

  /** The faces to colour: the face under the mouse while picking, the joint the mouse is on in the list, and the
   *  chosen part's joints (its own faces green, the faces it is held to blue). */
  drawMarks() {
    const marks = [], faceIds = (instId, name) => {
      const b = this.bodyOf(this.inst(instId))?.body;
      return b ? b.faces.filter((f) => f.name === name || (f.names || []).includes(name)).map((f) => f.id) : [];
    };
    const shown = new Set(this.sel ? this.shownJoints().map((m) => m.id) : []);
    for (const m of this.doc.mates || []) {
      const on = this.hoverJoint === m.id || (Array.isArray(this.hoverJoint) && this.hoverJoint.includes(m.id)) || (!this.hoverJoint && shown.has(m.id));
      if (!on) continue;
      marks.push({ inst: m.move, faces: faceIds(m.move, m.face), color: 0x3fb950 }, { inst: m.onto, faces: faceIds(m.onto, m.ontoFace), color: 0x58a6ff });
    }
    for (const c of this.doc.couplings || []) if (this.hoverJoint === c.id) marks.push({ inst: c.a, faces: faceIds(c.a, c.aFace), color: 0x3fb950 }, { inst: c.b, faces: faceIds(c.b, c.bFace), color: 0x58a6ff }); // (⚙ a coupling's two faces)
    for (const h of this.hoverCand?.holes || []) marks.push({ inst: h.inst, faces: faceIds(h.inst, h.name), color: 0xf2cc60 });
    for (const q of this.hoverMissing ? [this.hoverMissing.hole, this.hoverMissing.pin] : []) marks.push({ inst: q.inst, faces: faceIds(q.inst, q.name), color: 0xf2cc60 }); // (➕ Add joint: its hole and pin)
    if (this.jointFrom?.face) marks.push({ inst: this.jointFrom.inst, faces: [this.jointFrom.face.id], color: 0x3fb950 });
    for (const [inst, set] of this.painting?.sel || []) marks.push({ inst, faces: [...set], color: 0xff9e64 });
    if (this.hoverFace) marks.push({ inst: this.hoverFace.inst, faces: [this.hoverFace.face.id], color: this.hoverFace.ok ? 0xf2cc60 : 0x8b95a3 });
    if (this.mode === 'idle') for (const q of this.facePicks || []) if (this.inst(q.inst)) marks.push({ inst: q.inst, faces: faceIds(q.inst, q.face.name), color: 0xf2cc60 }); // (picked with no tool)
    this.view.setMarks(marks);
  }

  /** Each shown joint's symbol in the view, between its two faces: hover = its faces lit, click = its two parts. */
  drawJointTags() {
    if (!this.view?.setTags) return;
    const tags = [];
    if (this.mode === 'idle' && !this.painting && !this.measuring) {
      for (const m of this.shownJoints()) {
        let a, b;
        try { a = this.worldFace(m.move, m.face).centroid; b = this.worldFace(m.onto, m.ontoFace).centroid; } catch { continue; }
        const jt = JOINT_TYPES[m.type || 'touch'] || JOINT_TYPES.touch, el = document.createElement('div');
        const why = this.whyNot(m);
        el.className = `as-jtag${m.broken || why ? ' bad' : ''}${m.locked ? ' locked' : ''}`;
        el.textContent = why ? `⚠ ${jt.icon}` : jt.icon;
        el.title = `${m.id} ${m.name ? `“${m.name}” (${t(jt.name)})` : t(jt.name)}: ${this.partName(this.inst(m.move)?.part)} ${m.move} → ${this.partName(this.inst(m.onto)?.part)} ${m.onto}${why ? `\n⚠ ${why}` : ''}`;
        el.dataset.joint = m.id;
        for (const ev of ['pointerdown', 'pointerup']) el.addEventListener(ev, (x) => x.stopPropagation());
        el.addEventListener('mouseenter', () => { this.hoverJoint = m.id; this.drawMarks(); });
        el.addEventListener('mouseleave', () => { this.hoverJoint = null; this.drawMarks(); });
        el.addEventListener('click', (x) => { x.stopPropagation(); this.sel = m.move; this.sel2 = m.onto; this.render(); this.draw(); });
        tags.push({ p: a.clone().add(b).multiplyScalar(0.5).toArray(), el });
      }
    }
    this.view.setTags(tags);
  }

  renderStatus() {
    const n = this.doc.instances.length, j = (this.doc.mates || []).length, bad = this.unmet().length, el = this.$('.m-status');
    el.textContent = n ? `${n} part(s)${j ? ` · ${j} joint(s)` : ''}${bad ? ` · ⚠ ${bad} not held` : ''}` : '';
    el.classList.toggle('bad', !!bad);
  }

  // ------------------------------------------------------------------ bodies of the parts
  async refresh() {
    this.flexCache = null;
    const need = [...new Set(this.doc.instances.map((i) => i.part))];
    // sub-assemblies: their own parts first, then them as one body each
    const subs = need.filter((pid) => this.kindOf(pid) === 'assembly');
    const inner = new Set();
    const walk = (pid, seen = new Set()) => {
      if (seen.has(pid)) return;
      seen.add(pid);
      for (const i of this.hooks.partData(pid)?.instances || []) (this.kindOf(i.part) === 'assembly' ? walk(i.part, seen) : inner.add(i.part));
    };
    subs.forEach((pid) => walk(pid));
    const cancelled = await this.buildBodies([...new Set([...need.filter((pid) => !subs.includes(pid)), ...inner])]);
    for (const pid of subs) this.mergeAssembly(pid);
    for (const it of this.doc.instances) if (it.inner && subs.includes(it.part)) this.settleInner(it);
    const used = new Set(this.doc.instances.filter((it) => it.inner).map((it) => this.bodyKey(it)));
    for (const k of Object.keys(this.bodies)) if (k.includes('@') && !used.has(k)) delete this.bodies[k]; // (moved inside no more)
    this.applyMates();
    this.draw();
    this.mech?.render(); // (the loops are known now: ⚙ Mechanism and its button)
    this.renderBar();
    this.renderList();
    this.renderProps();
    if (cancelled) { this.hooks.toast(t('Cancelled — the parts not built are shown as they were (a change builds them).'), 'info', 6000); return; } // (no clash check either)
    this.scheduleClashes(); // (the ⚠ button tells)
  }

  /** A sub-assembly as one body: its parts' meshes placed by their matrices, face names "<its instance>/<name>".
   *  place: a placed sub-assembly whose parts were moved inside it (its `inner`) — that placement's own body. */
  mergeAssembly(pid, seen = new Set(), place = null) {
    const data = this.hooks.partData(pid), at = place?.inner ? this.bodyKey(place) : pid;
    if (!data || seen.has(pid)) return this.bodies[at];
    seen.add(pid);
    const list = place?.inner ? this.innerList(place) : data.instances || [];
    const key = JSON.stringify(data) + JSON.stringify(place?.inner || null) + list.map((i) => this.bodyOf(i)?.key || '').join('|');
    if (this.bodies[at]?.key === key) return this.bodies[at];
    const pos = [], ids = [], faces = [], edges = [];
    let vol = 0, mass = 0, box = null, off = 0;
    const cog = new THREE.Vector3();
    for (const it of list) {
      const sub = this.kindOf(it.part) === 'assembly' ? this.mergeAssembly(it.part, new Set(seen), it.inner ? it : null) : this.bodies[it.part];
      const b = sub?.body;
      if (!b) continue;
      const M = new THREE.Matrix4().fromArray(it.matrix), N = new THREE.Matrix3().getNormalMatrix(M), v = new THREE.Vector3();
      const P = b64(b.positions, Float32Array), F = b64(b.face_ids, Uint32Array);
      for (let k = 0; k < P.length; k += 3) { v.set(P[k], P[k + 1], P[k + 2]).applyMatrix4(M); pos.push(v.x, v.y, v.z); }
      for (const id of F) ids.push(id + off);
      const at = (a) => new THREE.Vector3(...a).applyMatrix4(M).toArray().map((x) => +x.toFixed(6));
      const dir = (a) => new THREE.Vector3(...a).applyMatrix3(N).normalize().toArray().map((x) => +x.toFixed(9));
      for (const f of b.faces) {
        faces.push({ ...f, id: f.id + off, name: `${it.id}/${f.name}`, names: (f.names || []).map((n) => `${it.id}/${n}`), centroid: at(f.centroid),
          ...(f.normal ? { normal: dir(f.normal) } : {}), ...(f.axis ? { axis: { o: at(f.axis.o), d: dir(f.axis.d) } } : {}),
          ...(f.frame ? { frame: { o: at(f.frame.o), x: dir(f.frame.x), n: dir(f.frame.n) } } : {}) });
      }
      for (const e of b.edges) {
        const q = [];
        for (let k = 0; k < e.pts.length; k += 3) q.push(...at([e.pts[k], e.pts[k + 1], e.pts[k + 2]]));
        edges.push({ ...e, pts: q, faces: e.faces.map((x) => x + off), mid: at(e.mid) });
      }
      off += Math.max(0, ...b.faces.map((f) => f.id)) + 1;
      vol += b.volume;
      const mi = (b.sub ? b.mass_g : this.massOf(it.part)) ?? (b.volume / 1000) * (MATERIALS[this.hooks.partData(it.part)?.material || 'PLA'] || 1.24);
      mass += mi;
      if (b.cog) cog.addScaledVector(new THREE.Vector3(...b.cog).applyMatrix4(M), mi);
      const bb = new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(M);
      box = box ? box.union(bb) : bb;
    }
    const enc = (arr, T) => { const u = new Uint8Array(new T(arr).buffer); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); return btoa(s); };
    this.bodies[at] = box ? { key, body: { positions: enc(pos, Float32Array), face_ids: enc(ids, Uint32Array), faces, edges, volume: vol, mass_g: mass,
      ...(mass > 0 ? { cog: cog.multiplyScalar(1 / mass).toArray() } : {}), bbox: [...box.min.toArray(), ...box.max.toArray()], sub: true } } : { key, error: 'This assembly has no parts with a solid yet.' };
    return this.bodies[at];
  }

  /** The 3D model / quick parts' bodies, from the kernel (unchanged ones are kept) -> whether any was cancelled (the
   *  busy box's Cancel: that part keeps the body it had, built again on the next change). */
  async buildBodies(need) {
    let cancelled = false;
    await Promise.all(need.map(async (pid) => {
      const data = this.hooks.partData(pid);
      if (!data) { this.bodies[pid] = { error: 'This part is no longer in the project.' }; return; }
      const lod = this.doc.light?.[pid] === true ? 'light' : this.doc.light?.[pid] === false ? 'full' : 'auto'; // 🪶
      const key = JSON.stringify([data.features || { model: data.model, values: data.values, layers: data.layers, bends: data.bends }, lod, data.threads]);
      if (this.bodies[pid]?.key === key) return;
      // the part's newest build wins: the kernel's processes may answer an older one later
      const want = (this.wanted ||= {});
      want[pid] = key;
      const rid = newRid('a'), stop = trackProgress(rid, t('Building the parts…'), { delay: 400 });
      try {
        const features = await this.partFeatures(pid, data);
        const { res, r } = await fetchRebuild({ features, lod, threads: data.threads }, rid, this.partName(pid));
        if (want[pid] !== key) return;
        if (r.cancelled || wasCancelled(rid)) { cancelled = true; if (!this.bodies[pid]?.body) this.bodies[pid] = { key: null, error: t('Cancelled — a change builds it.') }; return; }
        if (!res.ok) throw new Error(r.error || res.statusText);
        if (!r.ok && !r.body) throw new Error(r.features.flatMap((s) => s.issues).join(' ') || 'This part has no solid.');
        if (r.body) r.body.threads = r.threads?.holes || []; // (🔩 its threaded holes: drawn when its part shows them)
        this.bodies[pid] = r.body ? { key, body: r.body, features } : { key, error: 'This part has no solid yet.' };
      } catch (e) { if (want[pid] === key) this.bodies[pid] = { key, error: e.message }; } finally { stop(); }
    }));
    return cancelled;
  }

  draw() {
    // exploded: each part that moves (💥) pushed away from the middle of the ones that stay (of all, when all move)
    const centres = this.doc.instances.map((it) => {
      const b = this.bodyOf(it)?.body;
      if (!b) return null;
      const c = new THREE.Vector3((b.bbox[0] + b.bbox[3]) / 2, (b.bbox[1] + b.bbox[4]) / 2, (b.bbox[2] + b.bbox[5]) / 2);
      return c.applyMatrix4(new THREE.Matrix4().fromArray(it.matrix));
    });
    const stay = centres.filter((c, k) => c && this.doc.instances[k].stay), ok = stay.length ? stay : centres.filter(Boolean);
    const mid = ok.reduce((s, c) => s.add(c), new THREE.Vector3()).multiplyScalar(1 / (ok.length || 1));
    const box = new THREE.Box3();
    for (const c of centres) if (c) box.expandByPoint(c);
    const size = box.isEmpty() ? 0 : box.getSize(new THREE.Vector3()).length() || 0;
    const away = (c) => { // a part right at the middle goes up
      const v = c.clone().sub(mid);
      return v.length() > 1e-6 * (1 + size) ? v : new THREE.Vector3(0, 0, Math.max(size, 10) * 0.5);
    };
    const focus = this.clashPanel ? this.focusClash : null;
    const shownClashes = this.clashPanel ? (focus ? [focus] : this.hoverClash ? [this.hoverClash] : this.clashes || []) : [];
    const clashing = new Set(shownClashes.flatMap((c) => [this.topOf(c.a), this.topOf(c.b)]));
    this.view.setClashBoxes(shownClashes.map((c) => c.bbox));
    const along = this.explode && this.explodeRespect ? this.explodeAlong(centres, away) : null;
    this.view.setBodies(this.doc.instances.map((it, k) => {
      const c = it.stay ? null : centres[k];
      const look = this.lookOf(it);
      if (focus && !clashing.has(it.id)) look.opacity = Math.min(look.opacity ?? 1, 0.12); // the rest see-through
      const lit = this.innerLit(it);
      return { id: it.id, body: this.bodyOf(it)?.body, matrix: it.matrix, color: this.modelParts().findIndex((p) => p.id === it.part), ...look, threads: this.hooks.partData(it.part)?.threads,
        ...(lit ? { lit } : {}), selected: (it.id === this.sel && !lit) || it.id === this.sel2 || it.id === this.jointFrom?.inst, hover: it.id === this.hoverInst, clash: clashing.has(it.id),
        explode: along ? along.get(it.id)?.toArray() || null : this.explode && c ? away(c).multiplyScalar(this.explode * 1.2).toArray() : null };
    }));
    this.drawMarks();
    this.drawJointTags();
    this.showCog();
  }

  /** The faces' prefix of the inner part chosen in the list ("I2/") when `it` is its placement, else null. */
  innerLit(it) { return this.selInner && this.selInner.top === it.id && it.id === this.sel ? `${this.selInner.path}/` : null; }

  /** Explode respecting the joints: each joined part goes along with the part it is on, and moves itself only along
   *  the ways its joints leave free (its pull projected onto them) -> id -> its offset (THREE.Vector3). */
  explodeAlong(centres, away) {
    if (!this.exDirs) { // the free directions of each part, kept until the next change
      this.exDirs = new Map();
      for (const it of this.doc.instances) {
        let d = null;
        try { d = (this.doc.mates || []).some((m) => m.move === it.id) ? this.motionsOf(it.id, true) : null; } catch { d = null; }
        const basis = [];
        for (const mo of d ? d.motions.filter((x) => x.kind === 'move') : []) { // made orthonormal
          const v = mo.dir.clone().normalize();
          for (const b of basis) v.addScaledVector(b, -v.dot(b));
          if (v.length() > 1e-6) basis.push(v.normalize());
        }
        this.exDirs.set(it.id, d ? basis : null); // null: not joined, it moves freely
      }
    }
    const out = new Map(), idx = new Map(this.doc.instances.map((it, k) => [it.id, k]));
    const offsetOf = (id, seen = new Set()) => {
      if (out.has(id)) return out.get(id);
      const it = this.inst(id), c = centres[idx.get(id)], dirs = this.exDirs.get(id);
      const pull = !it.stay && c ? away(c).multiplyScalar(this.explode * 1.2) : new THREE.Vector3();
      let o;
      if (!dirs) o = pull;
      else {
        const parent = (this.doc.mates || []).find((m) => m.move === id)?.onto;
        seen.add(id);
        o = parent && !seen.has(parent) && this.inst(parent) ? offsetOf(parent, seen).clone() : new THREE.Vector3();
        for (const u of dirs) o.addScaledVector(u, pull.dot(u));
      }
      out.set(id, o);
      return o;
    };
    for (const it of this.doc.instances) offsetOf(it.id);
    return out;
  }

  commit() {
    this.exDirs = null;
    this.history.commit();
    this.render();
    this.draw();
    this.hooks.onChange?.();
    this.scheduleClashes(this.clashPanel ? 250 : 700);
  }

  /** How a placed part looks: its own colour / see-through in this assembly, else its part's -> {colour, opacity}. */
  lookOf(it) {
    const data = this.hooks.partData(it.part) || {};
    const colour = it.colour || lookColor(data), opacity = Number.isFinite(it.opacity) ? it.opacity : data.opacity;
    const paint = [...(it.colour ? [] : data.paint || []), ...(it.paint || [])];
    return { colour: colour ? new THREE.Color(colour).getHex() : null, opacity: Number.isFinite(opacity) ? opacity : 1, paint: paint.length ? paint : null, ownColour: !!it.colour,
      finish: finishOf(data.material) };
  }

  // ------------------------------------------------------------------ editing
  newId() {
    const n = Math.max(0, ...this.doc.instances.map((i) => parseInt(String(i.id).replace(/\D/g, ''), 10) || 0));
    return `I${n + 1}`;
  }

  async insert(partId, like = null) {
    await this.refresh();
    // a new part goes beside what is there (in +x), on the bed
    let x = 0;
    for (const it of this.doc.instances) {
      const b = this.bodies[it.part]?.body;
      if (!b) continue;
      const bb = new THREE.Box3(new THREE.Vector3(b.bbox[0], b.bbox[1], b.bbox[2]), new THREE.Vector3(b.bbox[3], b.bbox[4], b.bbox[5])).applyMatrix4(new THREE.Matrix4().fromArray(it.matrix));
      x = Math.max(x, bb.max.x + 10);
    }
    const m = like ? new THREE.Matrix4().fromArray(like.matrix) : new THREE.Matrix4().identity();
    const it = { id: this.newId(), part: partId, matrix: m.toArray(), ...(this.doc.instances.length ? {} : { fixed: true }) }; // (the first part: fixed in place)
    this.doc.instances.push(it);
    await this.refresh();
    const b = this.bodies[partId]?.body;
    if (b && this.doc.instances.length > 1) {
      const bb = new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(m);
      it.matrix = new THREE.Matrix4().makeTranslation(x - bb.min.x, 0, 0).multiply(m).toArray();
    }
    this.sel = it.id;
    this.commit();
    // the view follows only when it has to: the first part -> iso; a new one outside the view -> all fitted (seen from
    // where the camera looks now); one the user can already see -> the view stays (zoomed in on something: kept)
    if (this.doc.instances.length === 1) this.view.setView('iso');
    else if (b && !this.inView(new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(new THREE.Matrix4().fromArray(it.matrix)))) this.view.fit();
  }

  /** Is all of this box (world) inside the camera's view? */
  inView(box) {
    const cam = this.view.camera;
    cam.updateMatrixWorld();
    const f = new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    return [0, 1, 2, 3, 4, 5, 6, 7].every((k) =>
      f.containsPoint(new THREE.Vector3(k & 1 ? box.max.x : box.min.x, k & 2 ? box.max.y : box.min.y, k & 4 ? box.max.z : box.min.z)));
  }

  /** A placed part gets a part of its own: its part copied as a new part, this one uses the copy (joints stay). */
  async ownPart(instId) {
    const it = this.inst(instId);
    if (!it || !this.hooks.duplicatePart) return null;
    const id = await this.hooks.duplicatePart(it.part);
    if (!id) return null;
    this.copies = { ...(this.copies || {}), [id]: { asm: this.hooks.selfId?.(), data: JSON.stringify(this.hooks.partData(id)) } }; // (an undo takes it away again)
    it.part = id;
    await this.refresh();
    this.commit();
    this.hooks.toast(t2('{inst} now has a part of its own: {name} — change it without changing the others.', { inst: instId, name: this.partName(id) }), 'ok', 5000);
    return id;
  }

  /** After an undo / redo: a copy ⧉ Make it its own part made goes out of the project when nothing uses it any more and
   *  it was not changed; a redo brings it back. */
  tidyCopies() {
    const self = this.hooks.selfId?.();
    for (const [id, c] of Object.entries(this.copies || {})) {
      if (c.asm !== self) continue;
      const used = this.doc.instances.some((i) => i.part === id);
      if (used && c.taken) { this.hooks.putPartBack?.(c.taken); c.taken = null; continue; }
      if (used || c.taken || JSON.stringify(this.hooks.partData(id)) !== c.data) continue;
      const name = this.partName(id);
      c.taken = this.hooks.takePart?.(id) || null;
      if (c.taken) this.hooks.toast(t2('{name} (the copy made for it) is out of the project again.', { name }), 'info', 4000);
    }
  }

  /** ＋ Insert part ▾ From a file (or a file dropped on the view): a STEP / IGES / STL / OBJ becomes a 3D model part of the
   *  project and goes in; a STEP assembly, if wanted, a sub-assembly (its parts, as in the file). */
  insertFile(file = null) {
    const go = async (f) => {
      let r;
      try { r = await this.hooks.importFile(f); } catch (e) { this.hooks.toast(e.message.replace(/^MESH_TOO_BIG /, ''), 'error', 9000); return; }
      if (r) await this.insert(r.part || this.hooks.addModelPart(r.step.name, { features: [r.step] }));
    };
    if (file) return go(file);
    const inp = document.createElement('input');
    Object.assign(inp, { type: 'file', accept: '.step,.stp,.igs,.iges,.stl,.obj,.3mf' });
    inp.addEventListener('change', () => { if (inp.files[0]) go(inp.files[0]); });
    inp.click();
  }

  removeInst(id) {
    const fid = this.inst(id)?.fastener?.id;
    if (fid) return this.removeFastener(fid); // a screw goes with its nut and its holes
    this.doc.instances = this.doc.instances.filter((i) => i.id !== id);
    this.doc.mates = (this.doc.mates || []).filter((m) => m.move !== id && m.onto !== id);
    if (this.sel === id) this.sel = null;
    if (this.sel2 === id) this.sel2 = null;
    this.commit();
  }

  setPos(k, value) {
    const it = this.inst(this.sel), v = parseFloat(String(value).replace(',', '.'));
    if (!it || !Number.isFinite(v)) return;
    if (!this.mayMove(it.id)) { this.renderProps(); return; }
    const m = new THREE.Matrix4().fromArray(it.matrix);
    const e = m.elements;
    e[{ x: 12, y: 13, z: 14 }[k]] = v;
    it.matrix = m.toArray();
    this.applyMates(); // the parts joined onto it follow
    this.commit();
  }

  /** May this part be moved by hand? Not when a locked joint holds it; when unlocked joints hold it, only if the
   *  user agrees to break them (ask = false: break them without asking — the AI). */
  mayMove(id, ask = true) {
    if (this.inst(id)?.fixed) { this.hooks.toast(t('📌 It is fixed in place — free it (📌 in its panel) to move it.'), 'warning', 5000); return false; }
    const mine = (this.doc.mates || []).filter((m) => m.move === id);
    if (!mine.length) return true;
    if (mine.some((m) => m.locked)) {
      this.hooks.toast('A locked joint 🔒 holds this part — unlock it in the joints list to move the part by hand.', 'warning', 5000);
      return false;
    }
    if (ask && !window.confirm(t2('Moving it by hand breaks its {n} joint(s). Break them and move it?', { n: mine.length }))) return false;
    this.unjoinMoving(id);
    return true;
  }

  /** 📌 Fix a part in place (it is not moved by hand, joints bring the others to it) — or free it. A part its own
   *  joints move cannot be fixed: the part it hangs on is. */
  toggleFixed(id) {
    const it = this.inst(id);
    if (!it) return;
    if (!it.fixed && (this.doc.mates || []).some((m) => m.move === id)) {
      this.hooks.toast(t('It hangs on its joints — fix the part it is joined to instead.'), 'warning', 5000);
      return;
    }
    if (it.fixed) delete it.fixed; else it.fixed = true;
    this.commit();
  }

  // ------------------------------------------------------------------ joints: they hold
  unjoinMoving(id) { this.doc.mates = (this.doc.mates || []).filter((m) => m.move !== id); }
  unlink(id) { this.unjoinMoving(id); }
  mateOf(id) { return (this.doc.mates || []).find((m) => m.move === id); }

  /** Add a joint: part `from.inst` (face from.face) is held against `to.inst` (face to.face). */
  addJoint(from, to, type = 'touch', gap = 0) {
    if (this.inst(from.inst)?.fixed) { // 📌 a fixed part stays: the other one goes to it
      if (this.inst(to.inst)?.fixed) { this.hooks.toast(t('Both parts are fixed in place 📌 — free one of them to join them.'), 'warning', 5000); return false; }
      [from, to] = [to, from];
    }
    const fromName = from.face?.name, toName = to.face?.name;
    if (!fromName || !toName) return false;
    // no circles: the other part may not (through others) hang on this one
    const holdsOn = (x) => (this.doc.mates || []).filter((m) => m.move === x).map((m) => m.onto);
    const seen = new Set(), stack = [to.inst];
    while (stack.length) {
      const x = stack.pop();
      if (x === from.inst) { this.hooks.toast('Not joined: the other part already hangs on this one — join them the other way round.', 'warning', 5000); return false; }
      if (seen.has(x)) continue;
      seen.add(x);
      stack.push(...holdsOn(x));
    }
    const same = (this.doc.mates || []).find((m) => (m.move === from.inst && m.face === fromName && m.onto === to.inst && m.ontoFace === toName)
      || (m.move === to.inst && m.face === toName && m.onto === from.inst && m.ontoFace === fromName));
    if (same) {
      const was = t((JOINT_TYPES[same.type || 'touch'] || JOINT_TYPES.touch).name), now = t(JOINT_TYPES[type].name);
      if (same.locked) { this.hooks.toast(t2('These two faces are joined already by {id} ({type}), locked 🔒 — unlock it to change it.', { id: same.id, type: was }), 'warning', 5000); return false; }
      for (const k of ['flip', 'value', 'dist', 'side', 'angle']) delete same[k];
      Object.assign(same, { type, gap: +gap || 0 });
      this.hooks.toast(t2('These two faces were joined already ({id}, {was}) — that joint is now {type}, not a second one.', { id: same.id, was, type: now }), 'info', 5000);
      return same;
    }
    const n = Math.max(0, ...(this.doc.mates || []).map((m) => parseInt(String(m.id || '').slice(1), 10) || 0)) + 1;
    const m = { id: `J${n}`, type, move: from.inst, face: fromName, onto: to.inst, ontoFace: toName, gap: +gap || 0 };
    this.doc.mates = [...(this.doc.mates || []), m];
    return m;
  }

  /** Kept for the first-version name of a snap. */
  link(from, to) { this.addJoint(from, to, 'touch'); }

  /** A part moved or turned by hand (after mayMove): the parts joined onto it follow it. */
  movedByHand() { this.applyMates(); }

  /** A part (by id) at M held by its joints, the parts it hangs on staying where they are -> M. probe: only trying
   *  (nothing is noted on the joints). */
  holdPart(id, M, probe = false, skip = null) {
    let fixed = null;
    (this.doc.mates || []).filter((m) => m.move === id && m.id !== skip && this.inst(m.onto) && !this.insideMate(m)).forEach((m, k) => {
      try {
        const r = applyJoint(M, m, (MM) => this.worldFace(id, m.face, MM), this.worldFace(m.onto, m.ontoFace), k === 0, fixed, k === 0 && !m.centred);
        M = r.M;
        fixed = fixed || r.fixed;
        if (!probe) { delete m.broken; if (k === 0) m.centred = true; }
      } catch { if (!probe) m.broken = true; }
    });
    return M;
  }

  /** Place every joined part again: each part's joints in order, a part after the parts it hangs on (placeAll); then
   *  the closed loops together (closeLoops: a rod on a crank and a slider) and, when they moved, the parts on them.
   *  drive: {id, was} — a part moved by a slider, ▶ or the AI (was: its matrix before): it stays where it was put;
   *  with {mo, amount}: by how much (the parts coupled to it follow exactly, a turn past 180° too). */
  applyMates(drive = null) {
    const mates = (this.doc.mates || []).filter((m) => this.inst(m.move) && this.inst(m.onto));
    this.doc.mates = mates;
    if (this.doc.couplings) { this.doc.couplings = this.doc.couplings.filter((c) => this.inst(c.a) && this.inst(c.b)); if (!this.doc.couplings.length) delete this.doc.couplings; }
    const before = new Map(this.doc.instances.map((i) => [i.id, [...i.matrix]]));
    this.placeAll(mates);
    if (this.closeLoops(before, drive)) this.placeAll(mates);
    if (this.doc.couplings && !this.owner) followCouplings(this, before, drive); // (⚙ a gear's turn turns the other one)
    this.checkJoints();
  }

  /** Each joined part placed by its joints, after the parts it hangs on. A part goes along with the part it hangs on
   *  (its first joint's) as that one moved, then its joints set what they fix — so where it slid or turned freely
   *  stays. */
  placeAll(mates) {
    const movers = [...new Set(mates.map((m) => m.move))], done = new Set();
    for (let pass = 0; pass <= movers.length && done.size < movers.length; pass++) {
      for (const id of movers) {
        if (done.has(id)) continue;
        const mine = mates.filter((m) => m.move === id);
        if (mine.some((m) => movers.includes(m.onto) && !done.has(m.onto) && m.onto !== id)) continue; // its support first
        done.add(id);
        const it = this.inst(id);
        if (!this.bodyOf(it)?.body || mine.some((m) => !this.bodyOf(this.inst(m.onto))?.body)) continue; // not built yet
        const rigid = mine.filter((m) => !this.insideMate(m));
        if (rigid.length) {
          let M = new THREE.Matrix4().fromArray(it.matrix);
          const parent = this.inst(rigid[0].onto), P = new THREE.Matrix4().fromArray(parent.matrix);
          if (it.hang?.on === parent.id && it.hang.m.some((v, i) => Math.abs(v - parent.matrix[i]) > 1e-9)) {
            M = P.clone().multiply(new THREE.Matrix4().fromArray(it.hang.m).invert()).multiply(M); // it goes along
          }
          M = this.holdPart(id, M);
          it.matrix = tidy(M.toArray());
          it.hang = { on: parent.id, m: [...parent.matrix] };
        }
        if (rigid.length < mine.length) this.settleInner(it); // (joints on its parts that move inside it: they hold those)
      }
    }
  }

  /** The closed loops (loops.js) — a part joined onto two parts that move —: when their joints do not all hold, their
   *  parts are moved together (the least they can) until they do. A driven part in a loop (drive) stays where it was
   *  put and is followed from where it was in steps (a crank turned 90° at once: the rod and the slider follow it
   *  round); where the loop cannot follow it further (a dead point), the part stops at the last place that closes.
   *  -> this.loops [{id, parts, closed, stopped}]; true when a part was moved. */
  closeLoops(before, drive) {
    const mates = (this.doc.mates || []).filter((m) => !this.insideMate(m));
    const moves = (x) => { const i = this.inst(x); return !!i && !i.fixed && !!this.bodyOf(i)?.body && mates.some((m) => m.move === x); };
    this.loops = findLoops(mates, moves).map((parts, k) => ({ id: `L${k + 1}`, parts, closed: true }));
    const Mat = (a) => new THREE.Matrix4().fromArray(a), faceAt = (id, name, M) => this.worldFace(id, name, M);
    let changed = false;
    for (const lp of this.loops) {
      const held = mates.filter((m) => lp.parts.includes(m.move));
      const now = new Map(held.flatMap((m) => [m.move, m.onto]).map((x) => [x, Mat(this.inst(x).matrix)]));
      if (worstMiss(held, now, faceAt) < 1e-5) continue; // (it holds: placed one joint after another, nothing was off)
      const dr = drive?.was && lp.parts.includes(drive.id) ? drive : null, free = lp.parts.filter((x) => x !== dr?.id).map((x) => this.loopPart(x));
      const was = new Map(now); // (where the loop's parts were before: it held there)
      for (const f of free) if (before.has(f.id)) was.set(f.id, Mat(before.get(f.id)));
      let P = null;
      if (dr) { // followed from where it was, a step at a time
        const A = Mat(dr.was), B = Mat(this.inst(dr.id).matrix), path = screwBetween(A, B), n = stepsBetween(A, B, this.loopPart(dr.id).L);
        let S = new Map(was).set(dr.id, A), k = 1;
        const closedThen = worstMiss(held, S, faceAt) < 1e-4, at = (s) => solveLoop(free, held, new Map(S).set(dr.id, path(s)), faceAt);
        for (; k <= n; k++) {
          const r = at(k / n);
          if (!r.ok) break;
          S = r.P;
        }
        if (k > n) P = S;
        else if (closedThen) { // a dead point between the last step and this one: as near to it as it closes
          let lo = (k - 1) / n, hi = k / n;
          for (let q = 0; q < 8; q++) { const mid = (lo + hi) / 2, r = at(mid); if (r.ok) { lo = mid; S = r.P; } else hi = mid; }
          P = S;
          lp.stopped = true;
        }
      }
      for (const S of P ? [] : [was, now]) { // where it is: from where the parts were, else as placed one joint after another
        const r = solveLoop(free, held, S, faceAt);
        if (r.ok) { P = r.P; break; }
      }
      if (!P) { lp.closed = false; continue; }
      for (const id of [...free.map((f) => f.id), ...(dr ? [dr.id] : [])]) this.inst(id).matrix = tidy(P.get(id).toArray());
      for (const id of lp.parts) { const it = this.inst(id), on = it.hang && this.inst(it.hang.on); if (on) it.hang = { on: on.id, m: [...on.matrix] }; } // (they are where they go)
      changed = true;
    }
    return changed;
  }

  /** A part as the loop solve moves it: {id, c (its centre, in its own frame), L (its size)}. */
  loopPart(id) {
    const b = this.bodyOf(this.inst(id))?.body, bb = b?.bbox || [0, 0, 0, 1, 1, 1];
    return { id, c: new THREE.Vector3((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2), L: Math.max(1, Math.hypot(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])) };
  }

  /** The closed loop a part is in (this.loops), with how many ways its parts can move together (`free`) -> it or null. */
  loopOf(id) {
    const lp = (this.loops || []).find((l) => l.parts.includes(id));
    if (!lp || lp.free !== undefined) return lp || null;
    const held = (this.doc.mates || []).filter((m) => lp.parts.includes(m.move) && !this.insideMate(m));
    const P = new Map(held.flatMap((m) => [m.move, m.onto]).map((x) => [x, new THREE.Matrix4().fromArray(this.inst(x).matrix)]));
    try { lp.free = loopFreedom(lp.parts.map((x) => this.loopPart(x)), held, P, (i, n, M) => this.worldFace(i, n, M)); } catch { lp.free = null; }
    return lp;
  }

  /** How a joined part can still move: {count, motions: [{kind, dir, point, label}], centre, size}. */
  motionsOf(id, own = false) {
    const it = this.inst(id), b = this.bodyOf(it)?.body, mine = (this.doc.mates || []).filter((m) => m.move === id && this.inst(m.onto) && !this.insideMate(m));
    if (!it || !b || !mine.length) return null;
    const M = new THREE.Matrix4().fromArray(it.matrix);
    const c = new THREE.Vector3((b.bbox[0] + b.bbox[3]) / 2, (b.bbox[1] + b.bbox[4]) / 2, (b.bbox[2] + b.bbox[5]) / 2).applyMatrix4(M);
    const L = Math.max(1, Math.hypot(b.bbox[3] - b.bbox[0], b.bbox[4] - b.bbox[1], b.bbox[5] - b.bbox[2]));
    const cands = [], axisName = (v) => {
      const k = ['X', 'Y', 'Z'].find((_, i) => Math.abs(Math.abs(v.getComponent(i)) - 1) < 1e-6);
      return k || null;
    };
    for (const m of mine) { // first what the joints suggest: along / about their axis, along / about their face
      let fA;
      try { fA = this.worldFace(m.onto, m.ontoFace); } catch { continue; }
      const what = m.name ? `“${m.name}”` : this.faceText(m.onto, m.ontoFace), part = this.partName(this.inst(m.onto)?.part); // (the joint's own name when the user gave it one)
      if (fA.axis) {
        cands.push({ kind: 'move', dir: fA.axis.d.clone(), key: `${m.id}:along`, ref: m.id, how: t('along the axis'), label: t2('Along the axis of {face} ({part})', { face: what, part }) });
        cands.push({ kind: 'turn', dir: fA.axis.d.clone(), point: fA.axis.o.clone(), key: `${m.id}:turn`, ref: m.id, how: t('about the axis'), label: t2('Turn about the axis of {face} ({part})', { face: what, part }) });
      }
      if (fA.normal) {
        const n = fA.normal.clone(), u = new THREE.Vector3(1, 0, 0).projectOnPlane(n);
        if (u.length() < 1e-6) u.set(0, 1, 0).projectOnPlane(n);
        u.normalize();
        const v = new THREE.Vector3().crossVectors(n, u).normalize();
        [u, v].forEach((dir, k) => cands.push({ kind: 'move', dir, key: `${m.id}:${'uv'[k]}`, ref: m.id, how: axisName(dir) ? t2('along {axis}', { axis: axisName(dir) }) : `${t('along the face')} ${'uv'[k]}`,
          label: axisName(dir) ? t2('Along {axis} (on {face})', { axis: axisName(dir), face: what }) : t2('Along {face}', { face: what }) }));
        cands.push({ kind: 'turn', dir: n, point: c.clone(), key: `${m.id}:spin`, ref: m.id, how: t('on the face'), label: t2('Turn on {face} ({part})', { face: what, part }) });
        cands.push({ kind: 'move', dir: n.clone(), key: `${m.id}:away`, ref: m.id, how: t('away from the face'), label: t2('Away from {face}', { face: what }) });
      }
    }
    for (const [k, dir] of [['X', [1, 0, 0]], ['Y', [0, 1, 0]], ['Z', [0, 0, 1]]]) {
      cands.push({ kind: 'move', dir: new THREE.Vector3(...dir), key: k, how: t2('along {axis}', { axis: k }), label: t2('Along {axis}', { axis: k }) });
      cands.push({ kind: 'turn', dir: new THREE.Vector3(...dir), point: c.clone(), key: `turn${k}`, how: t2('about {axis}', { axis: k }), label: t2('Turn about {axis}', { axis: k }) });
    }
    const r = freeMotions(M, (MM) => this.holdPart(id, MM, true), c, L, cands);
    // readable names: "Turn: Crank", "Slide: Slider" (two of a kind: how, in brackets); the joint's words kept as `detail`
    const me = this.partName(it.part), kinds = {}, word = (mo) => t2(mo.kind === 'turn' ? 'Turn: {part}' : 'Slide: {part}', { part: me });
    for (const mo of r.motions) kinds[mo.kind] = (kinds[mo.kind] || 0) + 1;
    r.motions = r.motions.map((mo) => ({ ...mo, detail: mo.label, label: kinds[mo.kind] > 1 ? `${word(mo)} (${mo.how})` : word(mo) }));
    if (it.moveNames) r.motions = r.motions.map((mo) => (it.moveNames[mo.key] ? { ...mo, name: it.moveNames[mo.key], auto: mo.label, label: it.moveNames[mo.key] } : mo)); // (the user's own names)
    if (!r.count && !own) { // fixed on the part it hangs on: the ways that one can move (it goes along)
      const P = mine[0].onto, seen = new Set([...(this._via || []), id]);
      if (!seen.has(P) && mine.every((m) => m.onto === P)) {
        this._via = seen;
        let d = null;
        try { d = this.motionsOf(P); } finally { this._via = null; }
        if (d?.count) {
          const with_ = this.partName(this.inst(P)?.part);
          return { count: d.count, unexplained: d.unexplained, via: P, centre: c, size: L,
            motions: d.motions.map((m) => ({ ...m, via: m.via || P, label: m.label, detail: t2('{way} — with {part}', { way: m.detail || m.label, part: with_ }) })) }; // (its name: the part that turns)
        }
      }
    }
    return { ...r, centre: c, size: L };
  }

  // ------------------------------------------------------------------ a sub-assembly's own motions, in this one
  /** A placed sub-assembly's own joints at work on its parts as this placement has them (in its own frame): an engine
   *  like this one (holdPart, applyMates, motionsOf, motionPos, moveFree …) whose draw / commit keep the parts' places
   *  on the placement (its `inner`) -> it, or null (not a sub-assembly, or no joints in it). outer: with this
   *  assembly's joints on its moving parts (insideMate), the parts they are joined to as fixed stand-ins "^I1". */
  innerAsm(it, outer = true) {
    const data = it && this.kindOf(it.part) === 'assembly' ? this.hooks.partData(it.part) : null;
    if (!data?.mates?.length) return null;
    const sub = Object.create(this), list = structuredClone(this.innerList(it)), mates = structuredClone(data.mates);
    for (const i of list) { const on = i.hang && list.find((x) => x.id === i.hang.on); if (on) i.hang = { on: on.id, m: [...on.matrix] }; } // (as they stand: none goes along)
    if (outer) { // this assembly's joints on its parts that move inside it: the parts they are joined to stand still
      const Si = new THREE.Matrix4().fromArray(it.matrix).invert();
      for (const m of (this.doc.mates || []).filter((x) => x.move === it.id && this.insideMate(x))) {
        const y = this.inst(m.onto), [k, face] = String(m.face).split(/\/(.*)/s);
        if (!y) continue;
        if (!list.some((x) => x.id === `^${y.id}`)) list.push({ id: `^${y.id}`, part: y.part, from: y.id, ...(y.inner ? { inner: y.inner } : {}), fixed: true, matrix: Si.clone().multiply(new THREE.Matrix4().fromArray(y.matrix)).toArray() });
        mates.push({ ...structuredClone(m), id: `^${m.id}`, move: k, face, onto: `^${y.id}`, centred: true });
      }
    }
    Object.assign(sub, { doc: { instances: list, mates }, owner: it, _via: null, health: null, whyCache: null, travelNote: null, playing: null, flexCache: null });
    sub.draw = () => this.keepInner(it, sub, false);
    sub.commit = () => this.keepInner(it, sub, true);
    return sub;
  }

  /** The places of a sub-assembly's parts moved by its engine (innerAsm) kept on the placement — `inner`: those not
   *  where its own document has them —, its body made again. final: an undo step; false: a live preview; null: only
   *  kept (while refreshing). */
  keepInner(it, sub, final) {
    const own = new Map((this.hooks.partData(it.part)?.instances || []).map((i) => [i.id, i.matrix])), inner = {};
    for (const x of sub.doc.instances) {
      const m0 = own.get(x.id);
      if (m0 && x.matrix.some((v, q) => Math.abs(v - m0[q]) > 1e-7)) inner[x.id] = x.matrix.map((v) => (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v) : +v.toFixed(9)));
    }
    if (Object.keys(inner).length) it.inner = inner; else delete it.inner;
    this.mergeAssembly(it.part, new Set(), it);
    if (final === null) return;
    this.exDirs = null;
    this.applyMates(); // (the parts joined onto its moved parts follow)
    if (final) this.commit(); else this.draw();
  }

  /** A placement's moved parts held again by the sub-assembly's joints (they may have changed in its own tab). */
  settleInner(it) {
    const sub = this.innerAsm(it);
    if (!sub) { this.mergeAssembly(it.part, new Set(), it); return; }
    try { sub.applyMates(); } catch { /* as they were */ }
    this.keepInner(it, sub, null);
  }

  /** The parts that can move inside a sub-assembly by its own joints (ids; kept until the next refresh). */
  flexOf(it) {
    this.flexCache = this.flexCache || new Map();
    if (!this.flexCache.has(it.part)) {
      this.flexCache.set(it.part, new Set()); // (while it is worked out: none)
      const sub = this.innerAsm({ id: it.id, part: it.part, matrix: it.matrix }, false), ids = new Set();
      for (const id of sub ? [...new Set(sub.doc.mates.map((m) => m.move))] : []) {
        try { const d = sub.motionsOf(id); if (d?.count && !d.via) ids.add(id); } catch { /* not built */ }
      }
      this.flexCache.set(it.part, ids);
    }
    return this.flexCache.get(it.part);
  }

  /** Is a joint of this assembly on a part that moves inside a placed sub-assembly (its face "I2/…")? Then it holds
   *  that part inside it — when the sub-assembly is held otherwise too (another joint, or 📌 fixed); alone, it places
   *  the whole sub-assembly as before. */
  insideMate(m) {
    if (this.owner) return false; // (in a sub-assembly's engine: its own joints)
    const it = this.inst(m.move), k = String(m.face).split('/')[0];
    if (!it || !String(m.face).includes('/') || this.kindOf(it.part) !== 'assembly') return false;
    const flex = this.flexOf(it);
    if (!flex.has(k)) return false;
    return !!it.fixed || (this.doc.mates || []).some((x) => x.move === it.id && x !== m && !flex.has(String(x.face).split('/')[0]));
  }

  /** The ways a placed sub-assembly's parts can still move inside it, by its own joints -> {sub (its engine), parts:
   *  [{id, d (as motionsOf)}]} or null. A part fixed on another one that moves goes along: that one is driven. */
  innerMotions(it) {
    const sub = this.innerAsm(it);
    if (!sub) return null;
    const parts = [];
    for (const id of [...new Set(sub.doc.mates.map((m) => m.move))]) {
      let d = null;
      try { d = sub.motionsOf(id); } catch { d = null; }
      if (d?.count && !d.via && d.motions.length) parts.push({ id, d });
    }
    return parts.length ? { sub, parts } : null;
  }

  /** The Moves inside a sub-assembly: a slider per free motion of its parts (only in this placement). */
  innerHtml(it, inner) {
    const name = this.partName(it.part);
    return `<h3>${esc(t2('Moves inside {sub}', { sub: name }))}</h3><p class="hint">${esc(t2('Its own joints leave these free. Slide: its parts move here only — {sub} itself stays as it is.', { sub: name }))}</p>
      ${inner.parts.map((p, k) => { const x = inner.sub.inst(p.id); return `<div class="as-inner" data-inner="${k}"><div class="as-innerpart" data-no-i18n>${esc(this.partName(x.part))} ${p.id}</div>${p.d.motions.map((mo, i) => inner.sub.motionHtml(x, mo, i, p.d.size, true)).join('')}</div>`; }).join('')}
      ${it.inner ? `<div class="row-actions"><button class="btn small" data-a="innerReset" title="${esc(t2('Its parts back where {sub} has them', { sub: name }))}">${esc(t2('↺ As in {sub}', { sub: name }))}</button></div>` : ''}`;
  }

  bindInner(box, it, inner) {
    for (const el of box.querySelectorAll('[data-inner]')) {
      const p = inner.parts[+el.dataset.inner];
      inner.sub.bindMotions(el, inner.sub.inst(p.id), p.d);
    }
    box.querySelector('[data-a=innerReset]')?.addEventListener('click', () => { delete it.inner; this.mergeAssembly(it.part, new Set(), it); this.applyMates(); this.commit(); });
  }

  /** Where a part is along one of its free motions (mm, or degrees for a turn), measured from the face or axis of the
   *  joint that gives it (the world's origin and X / Y for plain X / Y / Z) — so it stays true when the parts move. */
  motionPos(id, mo) {
    if (mo.via) id = mo.via; // (where the part it is fixed on is)
    const it = this.inst(id), M = new THREE.Matrix4().fromArray(it.matrix), m = mo.ref && (this.doc.mates || []).find((x) => x.id === mo.ref);
    let fA = null;
    if (m) { try { fA = this.worldFace(m.onto, m.ontoFace); } catch { fA = null; } }
    const d = mo.dir.clone().normalize();
    if (mo.kind === 'move') {
      const o = fA ? (fA.axis && /:along$/.test(mo.key) ? fA.axis.o : fA.centroid) : new THREE.Vector3();
      return new THREE.Vector3().setFromMatrixPosition(M).sub(o).dot(d);
    }
    const nm = new THREE.Matrix3().getNormalMatrix(M);
    const own = { xdir: new THREE.Vector3(1, 0, 0).applyMatrix3(nm).normalize(), ydir: new THREE.Vector3(0, 1, 0).applyMatrix3(nm).normalize() };
    const deg = spinOf(own, fA || { xdir: new THREE.Vector3(1, 0, 0), ydir: new THREE.Vector3(0, 1, 0) }, d), lim = this.limitsOf(it, mo);
    if (!lim) return deg;
    // within its limits (they may span up to a full turn, e.g. 0 … 270°): the turn round that lies in them
    const c = [deg - 360, deg, deg + 360];
    return c.find((x) => x >= lim.min - 1e-6 && x <= lim.max + 1e-6) ?? c.sort((p, q) => Math.abs(p - (lim.min + lim.max) / 2) - Math.abs(q - (lim.min + lim.max) / 2))[0];
  }

  /** A free motion's own name (shown wherever the motion is: its row, ⚙ Mechanism, the AI's lists); empty: its own
   *  words again. Kept on the part that moves (a part fixed on another: that one's). -> the name. */
  nameMotion(id, mo, name) {
    const it = this.inst(mo.via || id), v = String(name || '').trim();
    if (!it || !mo.key) throw new Error('This motion cannot have a name.');
    if (v) it.moveNames = { ...(it.moveNames || {}), [mo.key]: v };
    else if (it.moveNames) { delete it.moveNames[mo.key]; if (!Object.keys(it.moveNames).length) delete it.moveNames; }
    this.commit();
    return v;
  }

  /** A motion's limits on its part ({min, max}) or null. */
  limitsOf(it, mo) { const x = mo.via ? this.inst(mo.via) : it; return (mo.key && x?.travel?.[mo.key]) || null; }

  /** The amount to go from position p0 to v (a turn the short way round). */
  stepTo(mo, p0, v, lim = null) { const a = v - p0; return mo.kind === 'turn' && !lim ? ((((a + 180) % 360) + 360) % 360) - 180 : a; } // (within limits: as it is)

  /** A free motion's row: a slider of where it is (between its limits when it has them), its limits ⇤⇥, ▶ and the
   *  travel check. */
  motionHtml(it, mo, i, size, only = false) {
    const turn = mo.kind === 'turn', u = turn ? '°' : 'mm', lim = this.limitsOf(it, mo);
    let pos = 0;
    try { pos = +this.motionPos(it.id, mo).toFixed(2); } catch { /* not built */ }
    const span = Math.max(10, Math.round(size));
    const lo = lim ? lim.min : turn ? -180 : Math.floor(pos - span), hi = lim ? lim.max : turn ? 180 : Math.ceil(pos + span);
    const note = this.travelNote?.inst === it.id && this.travelNote.key === mo.key ? this.travelNote : null;
    return `<div class="as-dof" data-dofrow="${i}"><label>${turn ? '↻' : '↔'} <span class="as-mname ${mo.name ? 'own' : ''}" data-mname="${i}" title="${esc(`${mo.detail ? `${mo.detail} · ` : ''}${t('Double-click: give this motion your own name')}`)}" ${mo.name ? 'data-no-i18n' : ''}>${esc(mo.label)}</span></label>
      <div class="as-dofrow"><input type="range" data-dof="${i}" min="${lo}" max="${hi}" step="${turn ? 1 : 0.5}" value="${pos}">
      <input type="number" step="any" data-dofn="${i}" value="${fmt(pos)}"><span class="unit">${u}</span>${only ? '</div></div>' : `
      <button class="mini ${lim ? 'on' : ''}" data-dlim="${i}" title="${esc(lim ? 'Its limits — click to take them off (it moves freely again)' : 'Limits: how far it may go each way (a cylinder\'s stroke, a slide\'s ends, a door\'s swing)')}">⇤⇥</button>
      <button class="mini" data-dlock="${i}" title="Lock it where it is: a joint holds this motion (its joint's turn or distance, or a new flush / gap / parallel joint)">🔒</button></div>
      ${lim ? `<div class="as-doflim"><label>min <input type="number" step="any" data-dmin="${i}" value="${fmt(lim.min)}"></label>
        <label>max <input type="number" step="any" data-dmax="${i}" value="${fmt(lim.max)}"></label><span class="unit">${u}</span>
        <button class="mini ${this.playing?.key === mo.key ? 'on' : ''}" data-dplay="${i}" title="Play: from min to max and back">${this.playing?.key === mo.key ? '■' : '▶'}</button>
        <select class="as-dspeed" data-dspeed="${i}" title="How fast ▶ plays">${[[0.25, '¼×'], [0.5, '½×'], [1, '1×'], [2, '2×'], [4, '4×']].map(([v, l]) => `<option value="${v}" ${(lim.speed || 1) === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
        <button class="mini ${lim.loop ? 'on' : ''}" data-dloop="${i}" title="${lim.loop ? 'It plays again and again (■ stops it) — click: once' : 'Play once — click: again and again, until ■'}">↻</button>
        <button class="btn small" data-dcheck="${i}" title="Move it from min to max in small steps and check for collisions on the way">⚠ Check the travel</button></div>` : ''}
      ${note ? `<p class="mp-count as-dofnote ${note.bad ? 'bad' : ''}" data-no-i18n>${esc(note.text)}</p>` : ''}</div>`}`;
  }

  bindMotions(box, it, dof) {
    for (const sl of box.querySelectorAll('[data-dof]')) {
      const i = +sl.dataset.dof, mo = dof.motions[i], num = box.querySelector(`[data-dofn="${i}"]`);
      let from = null, p0 = 0;
      const go = (v, final) => {
        const lim = this.limitsOf(it, mo);
        if (lim) v = Math.max(lim.min, Math.min(lim.max, v));
        if (!from) { from = [...this.inst(mo.via || it.id).matrix]; p0 = this.motionPos(it.id, mo); }
        this.moveFree(it.id, mo, this.stepTo(mo, p0, v, lim), from, final);
        if (final) from = null;
      };
      sl.addEventListener('input', () => { num.value = fmt(+sl.value); go(+sl.value, false); });
      sl.addEventListener('change', () => go(+sl.value, true));
      num.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') num.blur(); });
      num.addEventListener('change', () => { const v = parseFloat(String(num.value).replace(',', '.')); if (Number.isFinite(v)) go(v, true); });
    }
    for (const el of box.querySelectorAll('[data-mname]')) {
      el.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        const mo = dof.motions[+el.dataset.mname];
        el.textContent = mo.name || '';
        renameInPlace(el, (n) => this.nameMotion(it.id, mo, n));
        el.addEventListener('blur', () => { if (!el.textContent.trim()) el.textContent = mo.label; }, { once: true }); // (left empty: as it was)
      });
    }
    for (const b of box.querySelectorAll('[data-dlim]')) {
      b.addEventListener('click', () => {
        const mo = dof.motions[+b.dataset.dlim], turn = mo.kind === 'turn', p = Math.round(this.motionPos(it.id, mo));
        if (this.limitsOf(it, mo)) this.setTravel(it.id, mo, null);
        else this.setTravel(it.id, mo, turn ? { min: Math.max(-180, p - 90), max: Math.min(180, p + 90) } : { min: p - 10, max: p + 10 });
      });
    }
    for (const el of box.querySelectorAll('[data-dmin], [data-dmax]')) {
      el.addEventListener('keydown', (ev) => { ev.stopPropagation(); if (ev.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const mo = dof.motions[+(el.dataset.dmin ?? el.dataset.dmax)], lim = { ...this.limitsOf(it, mo) }, v = parseFloat(String(el.value).replace(',', '.'));
        if (!Number.isFinite(v)) return;
        lim[el.dataset.dmin !== undefined ? 'min' : 'max'] = v;
        this.setTravel(it.id, mo, lim);
      });
    }
    for (const b of box.querySelectorAll('[data-dlock]')) {
      b.addEventListener('click', () => {
        try { this.hooks.toast(this.lockMotion(it.id, dof.motions[+b.dataset.dlock]), 'success', 4000); } catch (e) { this.hooks.toast(e.message, 'warning', 6000); }
      });
    }
    for (const b of box.querySelectorAll('[data-dplay]')) b.addEventListener('click', () => this.playTravel(it.id, dof.motions[+b.dataset.dplay]));
    for (const el of box.querySelectorAll('[data-dspeed]')) el.addEventListener('change', () => this.setPlay(it.id, dof.motions[+el.dataset.dspeed], { speed: +el.value }));
    for (const b of box.querySelectorAll('[data-dloop]')) b.addEventListener('click', () => { const mo = dof.motions[+b.dataset.dloop]; this.setPlay(it.id, mo, { loop: !this.limitsOf(it, mo)?.loop }); });
    for (const b of box.querySelectorAll('[data-dcheck]')) b.addEventListener('click', () => this.checkTravel(it.id, dof.motions[+b.dataset.dcheck]));
  }

  /** A motion's limits set ({min, max}; a turn within ±180°) or taken off (null); a part outside them is put back
   *  inside. -> the limits. */
  setTravel(id, mo, lim) {
    if (mo.via) id = mo.via; // (the limits are the part's it is fixed on)
    const it = this.inst(id);
    if (!mo.key) throw new Error('This motion cannot have limits.');
    this.travelNote = null;
    if (!lim) {
      if (it.travel) delete it.travel[mo.key];
      if (it.travel && !Object.keys(it.travel).length) delete it.travel;
      this.commit();
      return null;
    }
    let { min, max } = lim;
    if (mo.kind === 'turn') { min = Math.max(-360, min); max = Math.min(360, max); } // (up to a full turn)
    if (min > max) [min, max] = [max, min];
    if (mo.kind === 'turn' && max - min > 360) max = min + 360; // (one turn at most: past it a turn's place is the same again)
    it.travel = { ...(it.travel || {}), [mo.key]: { ...(it.travel?.[mo.key] || {}), min: +min, max: +max } }; // (its speed / repeat kept)
    const p = this.motionPos(id, mo), into = Math.max(min, Math.min(max, p));
    if (Math.abs(into - p) > 1e-6) { this.moveFree(id, mo, this.stepTo(mo, p, into, it.travel[mo.key]), [...it.matrix], true); } else this.commit();
    return it.travel[mo.key];
  }

  /** 🔒 One free motion locked where the part is now: its joint's turn (angle) or distance along the axis (dist) set,
   *  else a new joint between faces of the parts it is joined to — flat faces across a move (flush / gap / touch, at
   *  the distance they are), or flat faces along a turn (parallel). -> what was done (a text); throws when none
   *  holds it. */
  lockMotion(id, mo) {
    if (mo.via) id = mo.via; // (fixed on another part: that one is locked)
    const count = () => { try { return this.motionsOf(id, true)?.count ?? 0; } catch { return 0; } };
    const before = count(), keep = structuredClone(this.doc.mates || []), dir = mo.dir.clone().normalize();
    const tried = (what) => {
      this.applyMates();
      if (count() < before) { this.commit(); return what; }
      this.doc.mates = structuredClone(keep);
      this.applyMates();
      return null;
    };
    const m = mo.ref && (this.doc.mates || []).find((x) => x.id === mo.ref);
    if (m && !m.locked) { // its own joint first
      if (mo.kind === 'turn' && /:(turn|spin)$/.test(mo.key) && !Number.isFinite(m.angle)) {
        m.angle = +this.spinNow(m).toFixed(3); // (where it is: not rounded to a whole degree)
        const r = tried(t2('{id}: its turn locked at {deg}°', { id: m.id, deg: m.angle }));
        if (r) return r;
      }
      if (mo.kind === 'move' && /:along$/.test(mo.key) && m.type === 'axis' && !Number.isFinite(m.dist)) {
        let g = null;
        try { g = axialGap(this.worldFace(m.move, m.face), this.worldFace(m.onto, m.ontoFace)); } catch { g = null; }
        if (g) {
          Object.assign(m, { side: g.side, dist: +g.dist.toFixed(4) });
          const r = tried(t2('{id}: its distance along the axis locked at {mm} mm', { id: m.id, mm: m.dist }));
          if (r) return r;
        }
      }
    }
    // a new joint onto a part it is joined to: faces that hold this motion, the nearest / biggest first
    const it = this.inst(id), mine = (this.doc.mates || []).filter((x) => x.move === id);
    const planes = (inst) => {
      const b = this.bodyOf(this.inst(inst))?.body;
      const names = [...new Set((b?.faces || []).filter((f) => f.type === 'plane').map((f) => f.name))];
      return names.map((n) => { try { return { name: n, f: this.worldFace(inst, n) }; } catch { return null; } }).filter(Boolean);
    };
    const own = planes(it.id), pairs = [];
    for (const onto of [...new Set(mine.map((x) => x.onto))]) {
      for (const a of planes(onto)) {
        for (const b of own) {
          if ((this.doc.mates || []).some((x) => (x.move === id && x.face === b.name && x.onto === onto && x.ontoFace === a.name))) continue;
          const nA = a.f.normal, nB = b.f.normal, along = nA.dot(nB);
          if (Math.abs(Math.abs(along) - 1) > 1e-4) continue; // parallel faces only
          if (mo.kind === 'move') {
            if (Math.abs(Math.abs(nA.dot(dir)) - 1) > 1e-4) continue; // across the move
            const gap = b.f.centroid.clone().sub(a.f.centroid).dot(nA);
            pairs.push({ onto, a, b, type: along < 0 ? (Math.abs(gap) < 0.005 ? 'touch' : 'gap') : 'flush', gap: +gap.toFixed(4), score: Math.abs(gap) - 1e-3 * Math.sqrt(a.f.area * b.f.area) });
          } else {
            if (Math.abs(nA.dot(dir)) > 1e-4) continue; // along the turn's axis
            pairs.push({ onto, a, b, type: 'parallel', flip: along < 0, score: -Math.sqrt(a.f.area * b.f.area) });
          }
        }
      }
    }
    pairs.sort((p, q) => p.score - q.score);
    for (const p of pairs.slice(0, 12)) {
      const n = Math.max(0, ...(this.doc.mates || []).map((x) => parseInt(String(x.id || '').slice(1), 10) || 0)) + 1;
      const j = { id: `J${n}`, type: p.type, move: id, face: p.b.name, onto: p.onto, ontoFace: p.a.name, gap: p.type === 'flush' || p.type === 'gap' ? p.gap : 0, ...(p.flip ? { flip: true } : {}) };
      this.doc.mates = [...(this.doc.mates || []), j];
      const r = tried(t2('{id} added: {type} {face} – {other}', { id: j.id, type: t(JOINT_TYPES[j.type].name), face: this.faceText(id, j.face), other: this.faceText(p.onto, j.ontoFace) }));
      if (r) return r;
    }
    throw new Error(t('No joint found that locks this motion — join it by hand (🔗 Join it to another part).'));
  }

  /** How ▶ plays a motion with limits: {speed (¼ … 4, 1: about 3 s there and back), loop (again and again)} — kept with
   *  its limits; a change works while it plays. */
  setPlay(id, mo, o) {
    if (mo.via) id = mo.via;
    const it = this.inst(id), lim = it?.travel?.[mo.key];
    if (!lim) throw new Error('Set its limits first (⇤⇥).');
    if (o.speed !== undefined) { const v = Math.max(0.25, Math.min(4, +o.speed || 1)); if (v === 1) delete lim.speed; else lim.speed = v; }
    if (o.loop !== undefined) { if (o.loop) lim.loop = true; else delete lim.loop; }
    this.history.commit();
    this.renderProps();
    return lim;
  }

  /** ▶ From min to max and back (about 3 s at 1×; ↻: again and again), then where it was; again: stop. */
  playTravel(id, mo) {
    if (this.playing) { this.playing.stop = true; return; }
    if (mo.via) id = mo.via;
    const it = this.inst(id), lim = this.limitsOf(it, mo);
    if (!lim) return;
    const snap = this.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]), from = [...it.matrix], p0 = this.motionPos(id, mo);
    const play = (this.playing = { key: mo.key, stop: false });
    let k = 0, last = performance.now();
    this.renderProps();
    const frame = (now) => {
      const L = this.limitsOf(it, mo) || lim; // (its speed / repeat as they are now)
      k += (now - last) / (3000 / (L.speed || 1));
      last = now;
      if (k >= 1 && L.loop && !play.stop) k -= Math.floor(k);
      if (play.stop || k >= 1) {
        for (const [iid, m, hang] of snap) { const x = this.inst(iid); if (x) { x.matrix = m; x.hang = hang; } }
        this.checkJoints();
        this.playing = null;
        this.draw();
        this.renderProps();
        return;
      }
      const v = lim.min + (lim.max - lim.min) * (0.5 - 0.5 * Math.cos(2 * Math.PI * k)), was = [...it.matrix]; // min -> max -> min
      it.matrix = this.holdPart(id, motionMatrix(mo, ((mo.kind === 'turn' ? Math.PI / 180 : 1) * this.stepTo(mo, p0, v, lim))).multiply(new THREE.Matrix4().fromArray(from)), true).toArray();
      this.applyMates({ id, was });
      this.draw();
      requestAnimationFrame(frame);
    };
    it.matrix = this.holdPart(id, motionMatrix(mo, ((mo.kind === 'turn' ? Math.PI / 180 : 1) * this.stepTo(mo, p0, lim.min, lim))).multiply(new THREE.Matrix4().fromArray(from)), true).toArray();
    this.applyMates({ id, was: from }); // (a closed loop follows it to min)
    requestAnimationFrame(frame);
  }

  /** ⚠ The travel checked: the part moved from min to max in `n` steps (the parts on it go along), the kernel tells the
   *  collisions at each step (/api/assembly/sweep) -> {free: true} or {hits: [{with, from, to, volume}]}; it ends where
   *  it was. Two parts that both move are not checked against each other (they go along together). range: {min, max}
   *  instead of its limits (⚙ Mechanism: a crank's full turn). */
  async checkTravel(id, mo, n = 24, range = null) {
    if (mo.via) id = mo.via;
    const it = this.inst(id), lim = range || this.limitsOf(it, mo);
    if (!lim) throw new Error('Set its limits first (⇤⇥).');
    const u = mo.kind === 'turn' ? '°' : 'mm';
    this.travelNote = { inst: id, key: mo.key, text: t('Checking the travel…') };
    this.renderProps();
    const snap = this.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]), from = new THREE.Matrix4().fromArray(it.matrix), p0 = this.motionPos(id, mo);
    const base = this.flatParts(), steps = [];
    try {
      for (let k = 0; k <= n; k++) {
        const v = lim.min + ((lim.max - lim.min) * k) / n, was = [...it.matrix];
        it.matrix = this.holdPart(id, motionMatrix(mo, (mo.kind === 'turn' ? Math.PI / 180 : 1) * this.stepTo(mo, p0, v, lim)).multiply(from.clone()), true).toArray();
        this.applyMates({ id, was });
        steps.push({ at: +v.toFixed(3), matrices: Object.fromEntries(this.flatParts().map((f) => [f.id, f.matrix])) });
      }
      // the parts that move at some step, at every step (also where one is where it started)
      const moving = new Set(steps.flatMap((s) => base.filter((f) => s.matrices[f.id].some((x, q) => Math.abs(x - f.matrix[q]) > 1e-7)).map((f) => f.id)));
      for (const s of steps) s.matrices = Object.fromEntries([...moving].map((k) => [k, s.matrices[k]]));
    } finally {
      for (const [iid, m, hang] of snap) { const x = this.inst(iid); if (x) { x.matrix = m; x.hang = hang; } }
      this.checkJoints();
      this.draw();
    }
    let r;
    try {
      const res = await fetch('/api/assembly/sweep', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances: base, steps }) });
      r = await res.json();
      if (!res.ok) throw new Error(r.error || res.statusText);
    } catch (e) {
      this.travelNote = { inst: id, key: mo.key, text: e.message, bad: true };
      this.renderProps();
      throw e;
    }
    const hits = new Map(); // the other part -> {from, to, volume}
    r.steps.forEach((s, k) => {
      const moving = new Set(Object.keys(steps[k].matrices));
      for (const c of s.clashes) {
        if (moving.has(c.a) && moving.has(c.b)) continue;
        const other = this.topOf(moving.has(c.a) ? c.b : c.a), h = hits.get(other) || { with: other, from: s.at, to: s.at, volume: 0 };
        h.from = Math.min(h.from, s.at);
        h.to = Math.max(h.to, s.at);
        h.volume = Math.max(h.volume, c.volume);
        hits.set(other, h);
      }
    });
    const list = [...hits.values()];
    const text = list.length
      ? list.map((h) => t2('⚠ It hits {part} ({id}) from {a} to {b} {u} — up to {v} mm³.', { part: this.partName(this.inst(h.with)?.part), id: h.with, a: fmt(h.from), b: fmt(h.to), u, v: fmt(+h.volume.toFixed(1)) })).join(' ')
      : t2('✓ Free all the way, {a} to {b} {u} — nothing in its way.', { a: fmt(lim.min), b: fmt(lim.max), u });
    this.travelNote = { inst: id, key: mo.key, text, bad: !!list.length };
    this.renderProps();
    return list.length ? { hits: list } : { free: true };
  }

  /** Move a joined part by one of its free motions (mm or degrees) from where it was (from: its matrix then);
   *  its joints hold it, the parts on it follow. final: an undo step (else a live preview; quiet: not even drawn). */
  moveFree(id, mo, amount, from, final, quiet = false) {
    if (mo.via) id = mo.via; // fixed on a part that moves: that one moves, it goes along
    const it = this.inst(id);
    if (!it) return;
    from = from || [...it.matrix];
    const M = motionMatrix(mo, mo.kind === 'turn' ? (amount * Math.PI) / 180 : amount).multiply(new THREE.Matrix4().fromArray(from)), was = [...it.matrix];
    it.matrix = this.holdPart(id, M).toArray();
    this.applyMates({ id, was, mo, amount }); // (in a closed loop the others follow it from where it was)
    if (final) this.commit(); else if (!quiet) this.draw();
  }

  /** The selected part turned to an angle (degrees) about X / Y / Z, about its own centre (the other two angles
   *  stay). final: an undo step (else a live preview while sliding). */
  setRot(axis, deg, final) {
    const it = this.inst(this.sel), b = this.bodyOf(it)?.body;
    if (!it || !b || !Number.isFinite(deg)) return;
    if (!this.rotAllowed) { // once per slide: may it move?
      if (!this.mayMove(it.id)) { this.renderProps(); return; }
      this.rotAllowed = true;
    }
    if (final) this.rotAllowed = false;
    const m = new THREE.Matrix4().fromArray(it.matrix);
    const c = new THREE.Vector3((b.bbox[0] + b.bbox[3]) / 2, (b.bbox[1] + b.bbox[4]) / 2, (b.bbox[2] + b.bbox[5]) / 2).applyMatrix4(m);
    const q = new THREE.Quaternion().setFromRotationMatrix(m), e = new THREE.Euler().setFromQuaternion(q, 'XYZ');
    e[axis] = (deg * Math.PI) / 180;
    const q2 = new THREE.Quaternion().setFromEuler(e), dq = q2.multiply(q.clone().invert());
    it.matrix = new THREE.Matrix4().makeTranslation(c.x, c.y, c.z).multiply(new THREE.Matrix4().makeRotationFromQuaternion(dq))
      .multiply(new THREE.Matrix4().makeTranslation(-c.x, -c.y, -c.z)).multiply(m).toArray().map((v) => (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v) : v));
    if (final) {
      this.movedByHand(it.id);
      this.commit();
    } else this.draw();
  }

  /** Turn the selected part by 90° about an axis through its own centre. */
  turn(axis) {
    const it = this.inst(this.sel), b = this.bodyOf(it)?.body;
    if (!it || !b) return;
    const m = new THREE.Matrix4().fromArray(it.matrix);
    if (!this.mayMove(it.id, false)) return;
    const c = new THREE.Vector3((b.bbox[0] + b.bbox[3]) / 2, (b.bbox[1] + b.bbox[4]) / 2, (b.bbox[2] + b.bbox[5]) / 2).applyMatrix4(m);
    const r = new THREE.Matrix4()[{ x: 'makeRotationX', y: 'makeRotationY', z: 'makeRotationZ' }[axis]](Math.PI / 2);
    it.matrix = new THREE.Matrix4().makeTranslation(c.x, c.y, c.z).multiply(r).multiply(new THREE.Matrix4().makeTranslation(-c.x, -c.y, -c.z)).multiply(m).toArray();
    this.movedByHand(it.id);
    this.commit();
  }

  // ------------------------------------------------------------------ a new joint: pick the two faces
  startJoint(type = 'touch', from = null) {
    if (this.doc.instances.length < 2) return;
    this.sel2 = null;
    this.jointType = type;
    this.mode = 'joint-from';
    this.jointFrom = from ? { inst: from, face: null } : null;
    this.jointHint();
  }
  startSnap() { this.startJoint('touch'); }

  cancelJoint() {
    this.mode = 'idle';
    this.jointFrom = null;
    this.hoverFace = null;
    this.hint('');
    this.renderBar();
    this.draw();
  }

  jointHint() {
    const t = JOINT_TYPES[this.jointType], f0 = this.jointFrom?.face;
    const what = t.faces === 'cylinder' ? 'a round face' : t.faces === 'mixed' ? (this.mode === 'joint-to' ? (f0?.type === 'cylinder' ? 'a flat face' : 'a round face') : 'a round or a flat face')
      : 'a flat face';
    if (t.faces === 'any' && this.mode === 'joint-from') {
      this.hint(`${t.icon} ${t.name}: click where it goes in — a point on a flat face (the holes are drilled for it), or a hole that is there. Esc cancels.`);
      this.renderBar();
      this.draw();
      return;
    }
    this.hint(this.mode === 'joint-from' ? `${t.icon} ${t.name}: click ${what} of the part to move${this.jointFrom ? ' (the selected one)' : ''} — Esc cancels.`
      : this.jointType === 'fastener' ? `${t.icon} ${t.name}: now click the other part (anywhere).` : `${t.icon} ${t.name}: now click ${what} of the other part.`);
    this.renderBar();
    this.draw();
  }

  /** The face under the mouse fits the joint being made? */
  faceFits(h) {
    if (!h?.face) return false;
    const want = JOINT_TYPES[this.jointType].faces;
    // a screw / pin: the second part is clicked anywhere (its hole is often hidden under the first part)
    if (this.jointType === 'fastener' && this.mode === 'joint-to') return h.inst !== this.jointFrom?.inst;
    if (want === 'any' || want === 'mixed') {
      if (h.face.type !== 'plane' && h.face.type !== 'cylinder') return false;
      if (want === 'mixed' && this.mode === 'joint-to' && h.face.type === this.jointFrom?.face?.type) return false; // the other kind
    } else if (h.face.type !== want) return false;
    if (this.mode === 'joint-from' && this.jointFrom?.inst && h.inst !== this.jointFrom.inst) return false;
    if (this.mode === 'joint-to' && h.inst === this.jointFrom?.inst) return false;
    return true;
  }

  /** For a joint: the face under the mouse, or — when that is not the kind it wants and it wants a round one — the
   *  round face of a circular edge near the mouse (a hole seen from the front: click its circle). */
  /** With no tool on: the edge of the part under the mouse lit (a line or a circle), and the snap points of the face
   *  under it (corners, edge middles, centres, quadrants — by the snap filters) as dots; by the hover filters. */
  hoverMarks(e, h0) {
    const v = this.view, mesh = h0?.inst ? (v.meshes || []).find((m) => m.userData.inst === h0.inst) : null, hk = hoverKinds();
    if (!mesh) { v.clearHoverMarks(); return; }
    const body = mesh.userData.body, src = [{ edges: body.edges, matrix: mesh.matrix, inst: h0.inst }];
    const eh = hk.edges ? v.edgeAt(src, e.clientX, e.clientY, 7, v.meshes) : null;
    v.setHoverEdges(eh ? [{ pts: eh.edge.pts, matrix: mesh.matrix }] : [], eh ? `${mesh.uuid}:${eh.i}` : '');
    const fi = h0.face ? body.faces.findIndex((f) => f.id === h0.face.id) : -1, kinds = snapKinds();
    if (!hk.points || fi < 0) { v.setHoverSnaps([]); return; }
    const key = `${mesh.uuid}:${fi}|${Object.entries(kinds).map(([k, on]) => (on ? k : '')).join('')}`;
    if (key !== v.hoverSnapKey) v.setHoverSnaps(snapPoints(body.edges.filter((ed) => ed.faces.includes(fi)), mesh.matrix, kinds), key);
  }

  /** The snap point a plain click (no tool on) takes: a corner, an edge's middle, a centre within 5 px (📏 Measure: 10)
   *  — but on a hole's or pin's round face, or near its rim, only a corner: the click picks that face then (a thin side
   *  or a small pin seen from afar would be all snap circles; joining wants the face). */
  idleSnap(e, h) {
    const sp = this.view.measurePoint(e.clientX, e.clientY, 5);
    if (sp?.snap && sp.snap !== 'corner' && (h?.face?.type === 'cylinder' || this.view.roundEdgeAt(e.clientX, e.clientY))) return null;
    return sp;
  }

  jointPick(e, h) {
    if (this.faceFits(h) || this.mode === 'idle') return h;
    const want = JOINT_TYPES[this.jointType]?.faces;
    if (want !== 'cylinder' && want !== 'mixed' && want !== 'any') return h;
    const r = this.view.roundEdgeAt(e.clientX, e.clientY);
    return r && this.faceFits(r) ? r : h;
  }

  clickJoint(h) {
    if (!this.faceFits(h)) {
      const kind = JOINT_TYPES[this.jointType].faces;
      const want = kind === 'cylinder' ? 'a round face (a hole, a pin)' : kind === 'mixed' ? (this.mode === 'joint-to' ? 'the other kind of face (round ↔ flat)' : 'a round or a flat face')
        : kind === 'any' ? 'a flat face or a hole' : 'a flat face';
      if (h) this.hooks.toast(this.mode === 'joint-to' && h.inst === this.jointFrom?.inst ? 'Now a face of the other part.' : `Click ${want}.`, 'info', 2500);
      return;
    }
    if (this.mode === 'joint-from' && this.jointType === 'fastener' && h.face.type === 'plane') { this.startBolt(h); return; } // a new bolt, drilled
    if (this.mode === 'joint-from') {
      this.jointFrom = { inst: h.inst, face: h.face };
      this.mode = 'joint-to';
      this.jointHint();
      return;
    }
    const type = this.jointType;
    if (type === 'fastener') { this.fastenerAt(this.jointFrom, h); return; }
    const mover = this.inst(this.jointFrom.inst)?.fixed ? h.inst : this.jointFrom.inst, placed = (this.doc.mates || []).some((m) => m.move === mover);
    const before = new Set(this.unmet().map((m) => m.id)), had = new Set((this.doc.mates || []).map((m) => m.id)), nj = this.addJoint(this.jointFrom, h, type, type === 'gap' ? 5 : 0);
    let kept = null;
    if (nj && type === 'flush' && placed && !had.has(nj.id)) kept = this.keepOffset(nj); // (a part held already: it does not jump)
    if (nj) {
      if (type === 'axis' && /:hole:/.test(this.jointFrom.face.name) && /:hole:/.test(h.face.name)) this.autoDistance(nj);
      if (type === 'angle') { // it starts at the angle the faces make now (rounded), then it holds
        const a = this.jointFrom.face.normal, b = h.face.normal;
        nj.value = a && b ? Math.round((a.angleTo(b) * 180) / Math.PI) : 45;
      }
      this.applyMates();
      this.sel = this.jointFrom.inst;
      const fights = this.unmet().filter((m) => !before.has(m.id));
      if (fights.length) this.hooks.toast(t2('{type} added, but it fights another joint: {ids} no longer hold — see the red joint(s) in the panel.', { type: t(JOINT_TYPES[type].name), ids: fights.map((m) => m.id).join(', ') }), 'warning', 7000);
      else if (kept !== null && kept !== 0) this.hooks.toast(t2('{type} — the offset {gap} mm kept, as the parts stand (0 in the panel lines them up).', { type: t(JOINT_TYPES[type].name), gap: fmt(kept) }), 'ok', 5000);
      else if (nj.id === this.doc.mates[this.doc.mates.length - 1].id) this.hooks.toast(`${JOINT_TYPES[type].name} — it now holds (change it or ✕ it in the panel).`, 'ok', 3000);
    }
    this.mode = 'idle';
    this.jointFrom = null;
    this.hoverFace = null;
    this.hint('');
    this.commit();
  }

  /** Move instance B so its face meets face A: B's face normal turns to face A's normal (opposite), centres meet. */
  snap(from, to) {
    const it = this.inst(from.inst);
    const nB = from.face.normal, nA = to.face.normal;
    if (!nB || !nA) { this.hooks.toast('Snap works on flat faces — click flat faces.', 'warning'); return false; }
    const q = new THREE.Quaternion().setFromUnitVectors(nB.clone().normalize(), nA.clone().negate().normalize());
    const R = new THREE.Matrix4().makeRotationFromQuaternion(q);
    const m = new THREE.Matrix4().makeTranslation(to.face.centroid.x, to.face.centroid.y, to.face.centroid.z)
      .multiply(R).multiply(new THREE.Matrix4().makeTranslation(-from.face.centroid.x, -from.face.centroid.y, -from.face.centroid.z))
      .multiply(new THREE.Matrix4().fromArray(it.matrix));
    it.matrix = m.toArray().map((v) => (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v) : +v.toFixed(9)));
    return true;
  }

  bindPointer() {
    const cv = this.view.renderer.domElement;
    // a part dragged from the project tree (☰) onto the view: it goes in
    const vp = this.els.viewport;
    // … or a STEP / STL / OBJ file from the computer (a STEP assembly: a sub-assembly, if wanted)
    vp.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('text/a3d-insert') || e.dataTransfer.types.includes('Files')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; vp.classList.add('drop-in'); } });
    vp.addEventListener('dragleave', () => vp.classList.remove('drop-in'));
    vp.addEventListener('drop', async (e) => {
      const pid = e.dataTransfer.getData('text/a3d-insert'), file = e.dataTransfer.files?.[0];
      vp.classList.remove('drop-in');
      if (!pid && file) {
        e.preventDefault();
        if (/\.(step|stp|igs|iges|stl|obj|3mf)$/i.test(file.name) && this.hooks.importFile) this.insertFile(file);
        else this.hooks.toast(t('Drop a STEP, IGES, STL, OBJ or 3MF file to put it into the assembly.'), 'warning', 5000);
        return;
      }
      if (!pid) return;
      e.preventDefault();
      if (!this.modelParts().some((q) => q.id === pid)) { this.hooks.toast(t('That part cannot go into this assembly (a drawing, or the assembly itself).'), 'warning', 5000); return; }
      await this.insert(pid);
    });
    // the chosen part dragged: it moves the way its joints let it (a crank turns, the rod and slider follow) — before
    // the view's own turning sees the press (capture); elsewhere a drag turns the view as always
    vp.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target !== cv || !this.sel || this.mode !== 'idle' || this.measuring || this.painting || this.bolt || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const drag = startDrag(this, this.sel, e);
      if (!drag) return;
      this.mech?.stop(false);
      this.view.controls.enabled = false;
      cv.style.cursor = 'grabbing';
      const move = (ev) => drag.move(ev), up = () => {
        window.removeEventListener('pointermove', move, true);
        window.removeEventListener('pointerup', up, true);
        this.view.controls.enabled = true;
        cv.style.cursor = '';
        drag.end();
      };
      window.addEventListener('pointermove', move, true);
      window.addEventListener('pointerup', up, true);
    }, true);
    let down = null;
    cv.addEventListener('pointerdown', (e) => {
      if (this.hoverEv) hoverNow(); // (a move not shown yet: as it came, before the press)
      if (e.button === 0) down = { x: e.clientX, y: e.clientY };
    });
    cv.addEventListener('pointermove', (e) => {
      if (down) return;
      this.hoverEv = e; // (the work once a frame: the mouse sends more moves than the screen shows)
      if (!this.hoverRaf) this.hoverRaf = requestAnimationFrame(() => { this.hoverRaf = 0; hoverNow(); });
    });
    const hoverNow = () => {
      const e = this.hoverEv;
      this.hoverEv = null;
      if (!e || down) return;
      if (this.measuring) { this.view.clearHoverMarks(); this.view.setSnapMark(this.view.measurePoint(e.clientX, e.clientY)); return; } // (where a click measures from)
      const h0 = this.view.pickInst(e.clientX, e.clientY), h = this.jointPick(e, h0);
      if (this.mode === 'idle') this.hoverMarks(e, h0);
      else this.view.clearHoverMarks();
      if (this.mode !== 'idle') {
        const key = h?.face ? `${h.inst}:${h.face.id}` : '';
        if (key !== this.hoverFaceKey) {
          this.hoverFaceKey = key;
          this.hoverFace = h?.face ? { inst: h.inst, face: h.face, ok: this.faceFits(h) } : null;
          this.drawMarks();
        }
        cv.style.cursor = h?.face && this.faceFits(h) ? 'crosshair' : '';
        return;
      }
      const id = h?.inst || null;
      if (id !== this.hoverInst) { this.hoverInst = id; this.draw(); }
      this.view.setSnapMark(this.idleSnap(e, h)); // (a corner, an edge's middle, a centre: it can be picked)
      cv.style.cursor = !h ? '' : h.inst === this.sel && (this.dof?.count || this.mech?.list.some((m) => m.parts.includes(h.inst))) ? 'grab' : 'pointer'; // (the chosen part that can move: drag it)
    };
    cv.addEventListener('pointerleave', () => { this.hoverEv = null; this.view.clearHoverMarks(); });
    cv.addEventListener('dblclick', (e) => { // a part double-clicked: edit it here (when unlocked)
      if (this.mode !== 'idle' || this.measuring || this.bolt) return;
      const h = this.view.pickInst(e.clientX, e.clientY);
      if (h?.inst) this.editInPlace(h.inst);
    });
    cv.addEventListener('pointerup', (e) => {
      if (e.button !== 0 || !down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4;
      down = null;
      if (moved) return;
      const h = this.view.pickInst(e.clientX, e.clientY);
      if (this.measuring) { this.clickMeasure(e); return; }
      if (this.painting) { this.clickPaint(h, e.ctrlKey || e.metaKey); return; }
      if (this.mode !== 'idle') { this.clickJoint(this.jointPick(e, h)); return; }
      if (this.bolt) { if (h?.face?.type === 'plane') this.startBolt(h); return; } // another point for the bolt
      const sp = this.idleSnap(e, h), more = e.ctrlKey || e.metaKey;
      this.snapPick = sp?.snap ? sp : null; // (a corner, an edge's middle, a centre: picked with its part)
      this.view.setMeasure(this.snapPick ? [sp.point] : []);
      const f = this.snapPick ? null : this.view.roundEdgeAt(e.clientX, e.clientY) || (h?.face ? h : null); // a face, or a hole's / pin's rim
      const pick = f && { inst: f.inst, face: f.face };
      const had = this.facePicks || [];
      if (more && !pick && had.length && !h) return; // (a Ctrl+click beside the parts: the face picked first stays)
      this.facePicks = !pick ? [] : more && had.length === 1 && had[0].inst !== pick.inst ? [had[0], pick] : [pick]; // (Ctrl: the other part's face)
      this.choose(this.snapPick ? sp.inst : h?.inst || pick?.inst || null, more);
      this.drawMarks();
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    const k = e.key.toLowerCase();
    if (e.key === 'Escape' && this.measuring) { this.toggleMeasure(); return; }
    if (e.key === 'Escape' && this.painting) { this.togglePaint(); return; }
    if (e.key === 'Escape' && this.mode !== 'idle') { this.cancelJoint(); return; }
    if (e.key === 'Escape' && this.bolt) { this.cancelBolt(); return; }
    if ((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')) { e.preventDefault(); this.history.go(k === 'y' || e.shiftKey ? 1 : -1); return; }
    if (k === 's' && !e.ctrlKey) this.startJoint('touch', this.sel);
    if (e.key === 'Delete' && this.sel) this.removeInst(this.sel);
  }

  // ------------------------------------------------------------------ for the AI
  /** A face of a placed part by its name (as find_refs names it in the part's own model), in world coordinates. */
  worldFace(instId, name, matrix = null) {
    const it = this.inst(instId);
    if (!it) throw new Error(`No part ${instId} in the assembly — see get_assembly.`);
    const b = this.bodyOf(it)?.body;
    if (!b) throw new Error(`${instId} has no solid.`);
    const f = b.faces.filter((x) => x.name === name || (x.names || []).includes(name)).sort((p, q) => q.area - p.area)[0];
    if (!f) {
      const flat = [...new Set(b.faces.filter((x) => x.type === 'plane' || x.type === 'cylinder').map((x) => x.name))];
      throw new Error(`${instId} has no face “${name}”. Its flat and round faces: ${flat.join(', ')} (find_refs in its part tells which is which).`);
    }
    const m = matrix || new THREE.Matrix4().fromArray(it.matrix), nm = new THREE.Matrix3().getNormalMatrix(m);
    const out = { ...f, centroid: new THREE.Vector3(...f.centroid).applyMatrix4(m),
      xdir: new THREE.Vector3(1, 0, 0).applyMatrix3(nm).normalize(), ydir: new THREE.Vector3(0, 1, 0).applyMatrix3(nm).normalize() };
    if (f.type === 'plane') out.normal = new THREE.Vector3(...f.normal).applyMatrix3(nm).normalize();
    if (f.type === 'cylinder' && f.axis) {
      out.axis = { o: new THREE.Vector3(...f.axis.o).applyMatrix4(m), d: new THREE.Vector3(...f.axis.d).applyMatrix3(nm).normalize() };
      out.span = this.cylSpan(b, name, f.axis);
    }
    return out;
  }

  /** How far a round face (all its pieces of that name) reaches along its axis: [from, to] mm from the axis' origin
   *  (from the mesh: a cylinder split in two halves has half the area, so its area does not tell the length). */
  cylSpan(body, name, axis) {
    body._spans = body._spans || {};
    if (body._spans[name]) return body._spans[name];
    body._P = body._P || b64(body.positions, Float32Array);
    body._F = body._F || b64(body.face_ids, Uint32Array);
    const ids = new Set(body.faces.filter((x) => x.name === name || (x.names || []).includes(name)).map((x) => x.id));
    const [o, d] = [axis.o, axis.d], L = Math.hypot(...d) || 1;
    let lo = Infinity, hi = -Infinity;
    for (let tr = 0; tr < body._F.length; tr++) {
      if (!ids.has(body._F[tr])) continue;
      for (let k = tr * 9; k < tr * 9 + 9; k += 3) {
        const s = ((body._P[k] - o[0]) * d[0] + (body._P[k + 1] - o[1]) * d[1] + (body._P[k + 2] - o[2]) * d[2]) / L;
        lo = Math.min(lo, s);
        hi = Math.max(hi, s);
      }
    }
    return (body._spans[name] = lo <= hi ? [lo, hi] : null);
  }

  /** For the AI: how a joined part can still move -> {free: [the ways]} or {fully_held: true} ({} when not joined); a
   *  part in a closed loop: its `loop` (summary's loops), held by it alone: {moves_with_loop}. */
  freeOf(id) {
    try {
      const d = this.motionsOf(id), lp = this.mechanismOf(id), loop = lp ? { loop: lp.id } : {};
      if (!d) return loop;
      if (!d.count) return lp?.free ? { moves_with_loop: lp.id } : { fully_held: true, ...loop };
      const it = this.inst(id);
      return { ...loop, free: d.motions.map((m) => m.label), at: d.motions.map((m) => { const l = this.limitsOf(it, m); return { motion: m.label, [m.kind === 'turn' ? 'deg' : 'mm']: +this.motionPos(id, m).toFixed(2), ...(l ? { min: l.min, max: l.max } : {}) }; }) };
    } catch { return {}; }
  }

  /** For the AI: how a sub-assembly's parts can move inside it -> {inner: [{part: "I3/I2", name, free, at}]} or {}. */
  innerOf(it) {
    let r = null;
    try { r = this.innerMotions(it); } catch { r = null; }
    return r ? { inner: r.parts.map(({ id }) => ({ part: `${it.id}/${id}`, name: this.partName(r.sub.inst(id).part), ...r.sub.freeOf(id) })) } : {};
  }

  /** The closed loop a part is in when it is a mechanism (its parts move together) or cannot close — not one that holds
   *  still (plates screwed together) -> it or null. */
  mechanismOf(id) { const lp = this.loopOf(id); return lp && (!lp.closed || lp.free) ? lp : null; }

  /** For the AI: the closed loops — their parts, do they close, how many ways they move together and which part's
   *  motion drives them (move_free it: the others follow). */
  loopsSummary() {
    return (this.loops || []).filter((l) => this.mechanismOf(l.parts[0])).map((l) => {
      const lp = this.loopOf(l.parts[0]), drive = l.parts.flatMap((x) => {
        let d = null;
        try { d = this.motionsOf(x, true); } catch { d = null; }
        return d?.count ? d.motions.map((mo, i) => `${x} motion ${i}: ${mo.label}`) : [];
      });
      return { id: l.id, parts: l.parts, closed: l.closed, free_motions: lp.free, ...(l.stopped ? { stopped: true } : {}), drive };
    });
  }

  summary() {
    const self = this.hooks.selfId?.(), totals = new Map(self ? bomOf(this.bomCtx(), self).rows.map((r) => [r.part, r.qty]) : []); // (rolled up through the sub-assemblies)
    return {
      parts: this.doc.instances.map((it) => {
        const b = this.bodyOf(it)?.body, m = new THREE.Matrix4().fromArray(it.matrix);
        const bb = b ? new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(m) : null;
        return { id: it.id, part: it.part, name: this.partName(it.part), ...(it.fixed ? { fixed: true } : {}), position: new THREE.Vector3().setFromMatrixPosition(m).toArray().map((v) => +v.toFixed(3)),
          bbox: bb ? [...bb.min.toArray(), ...bb.max.toArray()].map((v) => +v.toFixed(3)) : null, error: this.bodies[it.part]?.error, ...this.freeOf(it.id), ...this.innerOf(it) };
      }),
      ...(() => { const mp = this.massProps(); return mp.cog ? { mass_g: mp.mass_g, cog_mm: mp.cog, ...(mp.unknown ? { parts_without_mass: mp.unknown } : {}) } : {}; })(),
      ...(this.loops?.some((l) => this.mechanismOf(l.parts[0])) ? { loops: this.loopsSummary() } : {}),
      ...(this.mech?.list.length ? { mechanisms: this.mech.summary() } : {}),
      ...(this.doc.couplings?.length ? { couplings: couplingsSummary(this) } : {}),
      joints: (this.doc.mates || []).map((m) => ({ id: m.id, ...(m.name ? { name: m.name } : {}), type: m.type || 'touch', part: m.move, face: m.face, onto: m.onto, onto_face: m.ontoFace,
        ...(m.type === 'axis' ? { distance: Number.isFinite(m.dist) ? m.dist : null } : { gap: m.gap || 0 }), ...(m.type !== 'parallel' ? { rotation_locked: Number.isFinite(m.angle) } : {}), ...(m.broken ? { broken: true } : {}),
        ...(m.locked ? { locked: true } : {}), ...(this.inst(m.move)?.fastener ? { fastener: this.inst(m.move).fastener.id } : {}), ...(this.whyNot(m) ? { not_held: this.whyNot(m) } : {}) })),
      fasteners: [...new Map(this.doc.instances.filter((i) => i.fastener).map((i) => [i.fastener.id, i.fastener])).values()].map((f) => ({ id: f.id, text: f.text,
        parts: this.doc.instances.filter((i) => i.fastener?.id === f.id).map((i) => i.id), ...(f.bolt ? { drilled_holes: true } : {}) })),
      parts_list: this.bom().map((r) => ({ name: r.name, qty: r.qty, ...(this.kindOf(r.part) === 'assembly' ? { assembly: true } : { total: totals.get(r.part) ?? r.qty }),
        material: r.material, mass_g_each: r.mass === null || !Number.isFinite(r.mass) ? null : +r.mass.toFixed(2),
        ...(r.lib ? { maker: r.lib.maker || undefined, pn: r.lib.pn || undefined, bought: true } : {}) })),
    };
  }

  /** For the AI: the BOM of an assembly (this one, or any by id / name) -> {assembly, mode, parts, pieces, mass_g, rows}. */
  bomFor(aid, mode = 'summary') {
    const bom = bomOf(this.bomCtx(), aid, { mode, numbering: this.numberingOf(aid) });
    const facts = (r) => ({ material: r.material || undefined, mass_g_each: r.mass_g ?? undefined, maker: r.maker || undefined, pn: r.pn || undefined, make_buy: r.how });
    const rows = mode === 'structured'
      ? bom.lines.map((r) => ({ level: r.depth + 1, pos: r.pos, name: r.name, qty_per_parent: r.qty, total: r.total, ...(r.kind === 'assembly' ? { assembly: true } : facts(r)) }))
      : bom.rows.map((r) => ({ pos: r.pos, name: r.name, total: r.qty, ...facts(r), mass_g_total: r.mass_total_g ?? undefined,
        from: r.in.map((w) => (w.times > 1 ? `${w.assembly}: ${w.qty} × ${w.times}` : `${w.assembly}: ${w.qty}`)).join(' + ') }));
    return { assembly: bom.assembly.name, mode, parts: bom.kinds, pieces: bom.pieces, mass_g: bom.mass_g, ...(bom.mass_unknown ? { mass_unknown: bom.mass_unknown } : {}), rows };
  }

  handlers() {
    const need = () => { if (!this.active) throw new Error('No assembly is on screen — new_assembly, or open_part an assembly.'); };
    const settle = () => this.refresh();
    return {
      get_assembly: async () => { need(); await settle(); return { text: JSON.stringify(this.summary()) }; },
      get_bom: async ({ assembly: which, mode = 'summary' } = {}) => {
        const self = this.active ? this.hooks.selfId?.() : null;
        const a = which ? this.hooks.parts().find((p) => p.kind === 'assembly' && (p.id === which || p.name === which)) : null;
        if (which && !a) throw new Error(`No assembly “${which}” — list_parts lists them (kind assembly).`);
        const aid = a?.id || self;
        if (!aid) throw new Error('Which assembly? Give assembly (its id or name from list_parts), or open one.');
        if (mode !== 'summary' && mode !== 'structured') throw new Error('mode: summary (a row per part, its total from every level) or structured (the tree).');
        if (aid === self) await settle();
        const leaves = new Set(), walk = (nodes) => { for (const n of nodes) (n.children ? walk(n.children) : leaves.add(n.part)); };
        walk(instanceTree(this.bomCtx(), aid));
        await this.buildBodies([...leaves]); // (their masses; built ones are kept)
        return { text: JSON.stringify(this.bomFor(aid, mode)) };
      },
      insert_part: async ({ part }) => {
        need();
        const p = this.modelParts().find((q) => q.id === part || q.name === part);
        if (!p) throw new Error(`No part “${part}” that can go in (a 3D model or a quick part with a shape) — see list_parts.`);
        await this.insert(p.id);
        return { text: JSON.stringify(this.summary()) };
      },
      snap_faces: async ({ move, onto, type = 'touch', gap, value, lock_rotation, name }) => {
        need();
        await settle();
        if (COUPLING_TYPES[type]) { // ⚙ a coupling: one part's turn tied to the other's (value: the ratio)
          const c = addCoupling(this, { inst: move.part, face: this.worldFace(move.part, move.face) }, { inst: onto.part, face: this.worldFace(onto.part, onto.face) }, type, value ?? null);
          if (name) c.name = String(name).trim();
          this.sel = c.a;
          this.applyMates();
          this.commit();
          return { text: `${c.id} ${type}: ${c.a} ↔ ${c.b}, ${ratioText(c)} — move_free / drive_mechanism one of them, the other follows. ${JSON.stringify(this.summary())}` };
        }
        if (!JOINT_TYPES[type] || JOINT_TYPES[type].pick) throw new Error(`type is ${[...Object.keys(JOINT_TYPES).filter((k) => !JOINT_TYPES[k].pick), ...Object.keys(COUPLING_TYPES)].join(', ')} (screws and pins: suggest_fasteners / add_fasteners).`);
        const from = { inst: move.part, face: this.worldFace(move.part, move.face) };
        const to = { inst: onto.part, face: this.worldFace(onto.part, onto.face) };
        if (from.inst === to.inst) throw new Error('Join a face of one part to a face of another part.');
        const want = JOINT_TYPES[type].faces;
        if (want === 'mixed') {
          if (new Set([from.face.type, to.face.type, 'plane', 'cylinder']).size !== 2 || from.face.type === to.face.type) throw new Error('Tangent joins a round face and a flat face.');
        } else if (from.face.type !== want || to.face.type !== want) throw new Error(`${JOINT_TYPES[type].name} joins two ${want === 'cylinder' ? 'round' : 'flat'} faces.`);
        const nj = this.addJoint(from, to, type, type === 'axis' ? 0 : gap || 0);
        if (!nj) throw new Error('Not joined: the other part already hangs on this one (or the joint on these faces is locked).');
        if (type === 'axis' && Number.isFinite(+gap) && gap !== undefined && gap !== null) {
          this.applyMates();
          nj.side = axialGap(this.worldFace(nj.move, nj.face), this.worldFace(nj.onto, nj.ontoFace))?.side || 1;
          nj.dist = +gap;
        }
        if (lock_rotation && type !== 'parallel') { this.applyMates(); nj.angle = Math.round(this.spinNow(nj)); }
        if (name) nj.name = String(name).trim();
        if (type === 'angle') nj.value = Number.isFinite(+value) ? +value : Math.round((from.face.normal.angleTo(to.face.normal) * 180) / Math.PI);
        this.applyMates();
        this.sel = from.inst;
        this.commit();
        return { text: JSON.stringify(this.summary()) };
      },
      place_part: async ({ part, x, y, z, turn }) => {
        need();
        const it = this.inst(part);
        if (!it) throw new Error(`No part ${part} in the assembly.`);
        this.sel = it.id;
        if ((x ?? y ?? z) !== undefined || turn) {
          if (!this.mayMove(it.id, false)) throw new Error(it.fixed ? `${part} is fixed in place 📌 — joints bring other parts to it; the user frees it (📌 in its panel) to move it.` : `${part} is held by a locked joint — the user has to unlock it first.`);
        }
        for (const [k, v] of Object.entries({ x, y, z })) if (v !== undefined) this.setPos(k, v);
        for (const ax of [].concat(turn || [])) this.turn(ax);
        return { text: JSON.stringify(this.summary()) };
      },
      suggest_fasteners: async () => {
        need();
        await settle();
        const cs = findCandidates(this);
        return { text: JSON.stringify(cs.map((c) => ({ id: c.id, fastener: c.text, kind: c.kind, size: c.size, length: c.length,
          into: c.entry.inst, insert_in: c.insert?.inst || null }))) || '[]' };
      },
      add_fasteners: async ({ ids }) => {
        need();
        await settle();
        const cs = findCandidates(this), pick = ids?.length ? cs.filter((c) => ids.includes(c.id)) : cs;
        if (!pick.length) throw new Error(cs.length ? `No suggestion ${ids} — see suggest_fasteners.` : 'No holes line up between parts — put matching holes in both parts first.');
        const n = await this.addFasteners(pick);
        return { text: `Added ${n}. ${JSON.stringify(this.summary())}` };
      },
      bolt_parts: async ({ part, face, x = 0, y = 0, kind = 'nut', size = 'M3', through }) => {
        need();
        await settle();
        const f = this.worldFace(part, face), it = this.inst(part);
        if (f.type !== 'plane') throw new Error(`${face} is not flat — a screw goes in at a flat face.`);
        if (!BOLT_KINDS[kind]) throw new Error(`kind is ${Object.keys(BOLT_KINDS).join(', ')}.`);
        const M = new THREE.Matrix4().fromArray(it.matrix), N = new THREE.Matrix3().getNormalMatrix(M);
        const o = new THREE.Vector3(...f.frame.o).applyMatrix4(M), ax = new THREE.Vector3(...f.frame.x).applyMatrix3(N).normalize(), ay = new THREE.Vector3().crossVectors(f.normal, ax);
        const point = o.clone().addScaledVector(ax, +x || 0).addScaledVector(ay, +y || 0);
        this.startBolt({ inst: part, face: f, point });
        Object.assign(this.bolt, { kind, size, upto: through || null });
        const plan = this.boltPlan();
        if (plan.error) { this.cancelBolt(); throw new Error(plan.error); }
        await this.addBolt(plan, true);
        return { text: `Added ${plan.text}; holes drilled: ${plan.holes.map((h) => `Ø${h.d} ${h.through ? 'through' : `${h.depth} mm deep`} in ${this.partName(h.part)} (${h.inst})`).join(', ')}. ${JSON.stringify(this.summary())}` };
      },
      remove_from_assembly: async ({ part }) => { need(); this.removeInst(part); return { text: JSON.stringify(this.summary()) }; },
      set_travel: async ({ part, motion = 0, min, max, speed, loop }) => {
        need();
        await settle();
        const { it, mo } = this.motionFor(part, motion), only = min === undefined && max === undefined && (speed !== undefined || loop !== undefined);
        let l = only ? this.limitsOf(it, mo) : min === null || max === null || (min === undefined && max === undefined) ? this.setTravel(it.id, mo, null)
          : this.setTravel(it.id, mo, { min: +(min ?? this.limitsOf(it, mo)?.min ?? 0), max: +(max ?? this.limitsOf(it, mo)?.max ?? 0) });
        if (l && (speed !== undefined || loop !== undefined)) l = this.setPlay(it.id, mo, { speed, loop });
        return { text: `${it.id} — ${mo.label}: ${l ? `limits ${l.min} … ${l.max} ${mo.kind === 'turn' ? '°' : 'mm'}${l.speed ? `, ▶ ${l.speed}×` : ''}${l.loop ? ', ▶ again and again' : ''}` : 'no limits'}; now at ${+this.motionPos(it.id, mo).toFixed(2)}.` };
      },
      lock_motion: async ({ part, motion = 0 }) => {
        need();
        await settle();
        const { it, mo } = this.motionFor(part, motion), text = this.lockMotion(it.id, mo);
        return { text: `${text}. ${JSON.stringify(this.summary().parts.find((x) => x.id === (mo.via || it.id)))}` };
      },
      drive_mechanism: async ({ mechanism, to, driver, name, play } = {}) => {
        need();
        await settle();
        this.mech.render();
        let m = this.mech.find(mechanism);
        const again = () => { this.mech.render(); return this.mech.find(m.parts[0]); }; // (found again: its driver / name changed)
        if (driver !== undefined && driver !== null) { // {part, motion} or "I3 motion 0"
          const [p, k] = typeof driver === 'object' ? [driver.part, driver.motion ?? 0] : String(driver).split(/\s+motion\s+/);
          const { it, mo } = this.motionFor(p, k ?? 0);
          if (!m.drivers.some((d) => d.part === it.id && d.mo.key === mo.key)) throw new Error(`${it.id} — ${mo.label} does not drive ${m.id}; its drivers: ${m.drivers.map((d) => `${d.part} “${d.mo.label}”`).join(', ')}.`);
          this.mech.recFor(m).drive = { part: it.id, key: mo.key };
        }
        if (name !== undefined && name !== null) { const v = String(name).trim(), rec = this.mech.recFor(m); if (v) rec.name = v; else delete rec.name; }
        if ((driver !== undefined && driver !== null) || (name !== undefined && name !== null)) { this.commit(); m = again(); }
        if (!m.closed) throw new Error(`${m.id} “${m.name}” cannot close where its parts are — a part is too short or too long (get_assembly loops).`);
        let r = null;
        if (to !== undefined && to !== null) {
          if (!Number.isFinite(+to)) throw new Error('to: where its driver goes (degrees for a turn, mm for a slide).');
          this.mech.stop(false);
          r = driveTo(this, m, +to, true);
          m = again();
        }
        if (play === true) this.mech.play(m); else if (play === false) this.mech.stop();
        const s = this.mech.summary().find((x) => x.id === m.id), where = this.summary().parts.filter((x) => m.parts.includes(x.id)).map((x) => ({ id: x.id, name: x.name, position: x.position, ...(x.at ? { at: x.at } : {}) }));
        return { text: `${m.id} “${m.name}”, driven by ${m.driver.part} — ${m.driver.mo.label}: at ${s.at} ${m.turn ? '°' : 'mm'} (${m.min} … ${m.max}${m.full ? ', a full turn' : ''})${r?.stopped ? ' — stopped: it cannot go further that way (a dead point or its end)' : ''}${this.mech.playing?.key === m.key ? '; ▶ playing (play: false stops it)' : ''}. Its parts: ${JSON.stringify(where)}` };
      },
      record_animation: async ({ mechanism, format = 'gif', caption = true } = {}) => {
        need();
        await settle();
        this.mech.render();
        const m = this.mech.find(mechanism);
        if (!['gif', 'video'].includes(format)) throw new Error('format: gif or video.');
        const r = await saveAnimation(this.mech, m, { format, caption, download: false });
        if (!r) return { text: `The recording of ${m.id} “${m.name}” was cancelled.` };
        return { text: `${m.id} “${m.name}”: one ${m.full ? 'full turn' : 'cycle there and back'} saved as ${r.format.toUpperCase()} — ${r.path} (${r.frames} frames, ${r.width} × ${r.height} px, ${r.bytes} bytes; the user downloads it from ${r.url}).` };
      },
      name_motion: async ({ part, motion = 0, name = '' } = {}) => {
        need();
        await settle();
        const { it, mo } = this.motionFor(part, motion), v = this.nameMotion(it.id, mo, name);
        return { text: v ? `${mo.via || it.id}: the motion “${mo.auto || mo.label}” is called “${v}” now (get_assembly, its panel and ⚙ Mechanism show it).` : `${mo.via || it.id}: the motion has its own words again (“${mo.auto || mo.label}”).` };
      },
      check_travel: async ({ part, motion = 0 }) => {
        need();
        await settle();
        const { it, mo } = this.motionFor(part, motion), r = await this.checkTravel(it.id, mo);
        return { text: `${it.id} — ${mo.label} over ${JSON.stringify(this.limitsOf(it, mo))}: ${r.free ? 'free all the way.' : `hits ${r.hits.map((h) => `${h.with} (${this.partName(this.inst(h.with)?.part)}) from ${h.from} to ${h.to}, up to ${+h.volume.toFixed(1)} mm³`).join('; ')}.`}` };
      },
    };
  }

  /** A placed part and one of its free motions (its number or words of its name) — for the AI. A part inside a
   *  sub-assembly ("I3/I2", inside: true) -> also eng: the sub-assembly's engine that moves it (innerAsm). */
  motionFor(part, motion, inside = false) {
    const pick = (d) => {
      const mo = Number.isInteger(+motion) && d.motions[+motion] ? d.motions[+motion] : d.motions.find((x) => x.label.toLowerCase().includes(String(motion).toLowerCase()));
      if (!mo) throw new Error(`motion is one of: ${d.motions.map((x, i) => `${i}: ${x.label}`).join('; ')}.`);
      return mo;
    };
    if (String(part).includes('/')) { // a part inside a sub-assembly: its own joints move it, in this placement
      const [top, id] = String(part).split('/'), r = this.innerMotions(this.inst(top)), p = r?.parts.find((x) => x.id === id);
      if (!inside) throw new Error(`${part} is inside a sub-assembly: move_free moves it here; its limits and locks are its own assembly's (open_part it).`);
      if (!p) throw new Error(`${part} cannot move inside ${top} — get_assembly lists what can as \`inner\` of a sub-assembly.`);
      return { it: r.sub.inst(id), mo: pick(p.d), eng: r.sub };
    }
    const it = this.inst(part), d = it && this.motionsOf(it.id);
    if (!it) throw new Error('part is a placed id I… (get_assembly).');
    if (!d) throw new Error(`${it.id} is not joined — it has no free motions.`);
    if (!d.count) throw new Error(`${it.id} is fully held by its joints — it cannot move.`);
    return { it, mo: pick(d), eng: this };
  }

  // ------------------------------------------------------------------ the assembly as a project tab
  async load(data) {
    this.mech?.stop(false);
    this.doc = structuredClone(data || { instances: [] });
    this.doc.instances = this.doc.instances || [];
    this.doc.mates = (this.doc.mates || []).map((m, i) => ({ id: m.id || `J${i + 1}`, type: m.type || 'touch', gap: m.gap || 0, ...m }));
    this.sel = null;
    this.mode = 'idle';
    this.explode = 0;
    this.history.reset();
    this.render();
    await this.refresh();
    this.view.setView('iso');
  }

  payload() { return structuredClone(this.doc); }
  /** This assembly as a STEP tree (stepfile.js) for /api/assembly/export/step. */
  stepTree() { return stepTree(this, this.hooks.selfId?.() || 'root', this.hooks.safeName(), this.doc.instances); }
  hasBody() { return this.doc.instances.some((i) => this.bodies[i.part]?.body); }

  async export(fmtName) {
    const name = this.hooks.safeName();
    if (fmtName === 'stl') {
      const tris = [];
      for (const it of this.doc.instances) {
        const b = this.bodyOf(it)?.body;
        if (!b) continue;
        const pos = b64(b.positions, Float32Array), m = new THREE.Matrix4().fromArray(it.matrix), v = new THREE.Vector3();
        for (let i = 0; i < pos.length; i += 3) { v.set(pos[i], pos[i + 1], pos[i + 2]).applyMatrix4(m); tris.push(v.x, v.y, v.z); }
      }
      const n = tris.length / 9, buf = new ArrayBuffer(84 + n * 50), dv = new DataView(buf);
      new TextEncoder().encode('Auto3DModeler assembly').forEach((c, i) => dv.setUint8(i, c));
      dv.setUint32(80, n, true);
      for (let t = 0; t < n; t++) {
        const o = 84 + t * 50;
        for (let k = 0; k < 9; k++) dv.setFloat32(o + 12 + k * 4, tris[t * 9 + k], true);
      }
      if (await this.hooks.download(new Blob([buf], { type: 'model/stl' }), `${name}.stl`)) this.hooks.toast('Exported STL (in mm).', 'ok');
      return;
    }
    // a structured STEP (AP214): a product per part, placed instances, sub-assemblies nested — an assembly tree in
    // SolidWorks, CATIA, Solid Edge; IGES: every part placed in one file (it has no tree); GLB: glTF, a node per part
    const fmt = ['iges', 'glb'].includes(fmtName) ? fmtName : 'step', ext = { iges: 'igs' }[fmt] || fmt;
    const res = await fetch(`/api/assembly/export/${fmt}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tree: this.stepTree(), name }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json().catch(() => ({ error: res.statusText }))).error}`, 'error'); return; }
    if (await this.hooks.download(await res.blob(), `${name}.${ext}`)) {
      this.hooks.toast({ iges: 'Exported IGES (in mm) — every part placed in one file, with its name and colour.',
        glb: 'Exported GLB (glTF: a node per placed part with its name, colours and materials; metres, Y up).' }[fmt]
        || 'Exported STEP (in mm) — an assembly with its parts, as SolidWorks, CATIA and Solid Edge open it.', 'ok', 6000);
    }
  }
}
