// The assembly workspace: 3D model parts of the project placed together — insert a part, snap it face to face onto
// another one with joints that hold (touch, gap, flush, concentric, parallel, perpendicular, angle, tangent —
// joints.js), put a screw (+ nut / insert) or a pin through parts, drilling their holes, move it and turn it to any
// angle, an exploded view, a parts list with masses, export the whole as STL or STEP. No motion (parts do not move).
//
// Assembly JSON (in the project file, `parts[].assembly`):
//   {"instances": [{"id": "I1", "part": "P2", "matrix": [16 numbers, three.js column-major]}],
//    "mates": [{"id": "J1", "type": "touch" | "gap" | "flush" | "axis" | "parallel" | "perp" | "angle" | "tangent",
//               "move": "I2", "face": "F2:start", "onto": "I1", "ontoFace": "F2:end", "gap": 0, "value": 30, "flip": false}],
//    "bolts": [{"id": "B1", "text": "M3×20 screw + M3 nut", "holes": [{"part": "P2", "feature": {the hole step drilled}}]}]}
import * as THREE from 'three';
import { History } from '../history.js';
import { t } from '../i18n.js';
import { renameInPlace } from '../rename.js';
import { paintedFaces } from '../modeler/paint.js';
import { ModelView } from '../modeler/view.js';
import { JOINT_TYPES, applyJoint, spinOf, axialGap } from './joints.js';
import { fastenerModel, findCandidates, planBolt, isStandard, BOLT_KINDS, SIZES } from './fasteners.js';
import { MATERIALS } from '../modeler/modeler.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const ID = () => new THREE.Matrix4().identity().toArray();
const COLORS = [0xd9dee6, 0x9ecbff, 0xffd8a8, 0xb5f5c5, 0xe2c6ff, 0xffc2c2, 0xfff3b0];

const b64 = (s, T) => {
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};

/** The 3D view with several parts, each with its own placement. */
class AsmView extends ModelView {
  setBodies(list) {
    this.clear(this.bodyGroup);
    this.meshes = [];
    let box = null;
    for (const it of list) {
      if (!it.body) continue;
      const pos = b64(it.body.positions, Float32Array), ids = b64(it.body.face_ids, Uint32Array);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.computeVertexNormals();
      const o = Number.isFinite(it.opacity) ? it.opacity : 1;
      const mat = new THREE.MeshStandardMaterial({ color: it.selected ? 0x6cb6ff : it.colour || COLORS[it.color % COLORS.length], roughness: 0.55, metalness: 0.05,
        side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, emissive: it.hover ? 0x1b2a44 : 0x000000,
        transparent: o < 1, opacity: o, depthWrite: o >= 1 });
      const painted = !it.selected && !it.ownColour ? paintedFaces(it.body.faces, it.paint || []) : null;
      const fromFile = !it.selected && !it.ownColour ? it.body.faces.filter((f) => f.color) : [];
      if (painted?.size || fromFile.length) { // faces painted in their part, or coloured in its STEP file
        const base = new THREE.Color(it.colour || COLORS[it.color % COLORS.length]), col = new Float32Array(pos.length);
        const byId = new Map(fromFile.map((f) => [f.id, new THREE.Color(f.color)]));
        for (const [id, p] of painted) byId.set(id, new THREE.Color(p.color));
        for (let tr = 0; tr < ids.length; tr++) {
          const c = byId.get(ids[tr]) || base;
          for (let k = 0; k < 3; k++) col.set([c.r, c.g, c.b], tr * 9 + k * 3);
        }
        geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
        mat.vertexColors = true;
        mat.color.set(0xffffff);
      }
      const mesh = new THREE.Mesh(geo, mat);
      mesh.matrixAutoUpdate = false;
      mesh.matrix.fromArray(it.matrix);
      if (it.explode) mesh.matrix.premultiply(new THREE.Matrix4().makeTranslation(...it.explode));
      mesh.userData = { inst: it.id, faceIds: ids, body: it.body };
      this.bodyGroup.add(mesh);
      const seg = [];
      for (const { pts: pl } of it.body.edges) for (let i = 0; i + 5 < pl.length; i += 3) seg.push(pl[i], pl[i + 1], pl[i + 2], pl[i + 3], pl[i + 4], pl[i + 5]);
      const eg = new THREE.BufferGeometry();
      eg.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
      const lines = new THREE.LineSegments(eg, this.edgeMaterial);
      lines.matrixAutoUpdate = false;
      lines.matrix.copy(mesh.matrix);
      this.bodyGroup.add(lines);
      this.meshes.push(mesh);
      mesh.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(mesh);
      box = box ? box.union(bb) : bb;
    }
    this.mesh = this.meshes[0] || null; // fitting the view, the origin size
    if (box) { const s = box.getSize(new THREE.Vector3()); this.size = Math.max(s.x, s.y, s.z, 1); this.sizeOrigin(); }
    this.showDatums(!this.meshes.length);
    this.invalidate();
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
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, depthWrite: false }));
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
  measurePoint(clientX, clientY) {
    const h = this.pickInst(clientX, clientY), r = this.renderer.domElement.getBoundingClientRect();
    let best = null, bd = 10;
    for (const mesh of this.meshes || []) {
      for (const e of mesh.userData.body.edges || []) {
        const n = e.pts.length;
        if (e.faces.length < 2 || Math.hypot(e.pts[0] - e.pts[n - 3], e.pts[1] - e.pts[n - 2], e.pts[2] - e.pts[n - 1]) < 1e-6) continue;
        for (const k of [0, n - 3]) {
          const p = new THREE.Vector3(e.pts[k], e.pts[k + 1], e.pts[k + 2]).applyMatrix4(mesh.matrix), q = p.clone().project(this.camera);
          const dd = Math.hypot(r.left + (q.x + 1) / 2 * r.width - clientX, r.top + (1 - q.y) / 2 * r.height - clientY);
          if (dd < bd) { bd = dd; best = { p, inst: mesh.userData.inst }; }
        }
      }
    }
    if (!best && !h?.point) return null;
    return { point: best ? best.p : h.point.clone(), corner: !!best, face: h?.face || null, inst: best ? best.inst : h.inst };
  }

  /** What is under the mouse: {inst, face (in world coordinates)} or null. */
  pickInst(clientX, clientY) {
    const h = this.ray(clientX, clientY).intersectObjects(this.meshes || [], false)[0];
    if (!h) return null;
    const { inst, faceIds, body } = h.object.userData;
    const f = body.faces.find((x) => x.id === faceIds[h.faceIndex]);
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
      capture: () => ({ instances: this.doc.instances, mates: this.doc.mates, bolts: this.doc.bolts || [] }),
      restore: async (s) => {
        this.doc.instances = s.instances; this.doc.mates = s.mates || []; this.doc.bolts = s.bolts || []; this.mode = 'idle'; this.bolt = null;
        this.syncDrills(); // the holes drilled for bolts: back as they were
        this.render();
        await this.refresh();
      },
      onChange: () => this.updateUndo(),
    });
    this.build();
    this.view = new AsmView(this.els.view);
    this.bindPointer();
    this.render();
  }

  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = `<div class="mt-head"><b>Assembly</b><span class="mt-sub">its parts</span></div><div class="as-list"></div>
      <div class="mt-start as-start" hidden><p><b>Put parts together</b></p><ol><li><b>＋ Insert part</b> — a 3D model of this project</li>
      <li><b>🧲 Snap</b> — click a face of one part, then the face it goes onto</li><li>Nudge or turn it in the panel on the right</li></ol></div>`;
    viewport.innerHTML = `<div class="m-cmdbar"></div><div class="m-hint" hidden></div><div class="m-view"></div><div class="m-status"></div>`;
    right.innerHTML = '<div class="mp-body"></div>';
    this.els.view = viewport.querySelector('.m-view');
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
  }

  render() { this.renderBar(); this.renderList(); this.renderProps(); this.renderStatus(); }

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

  renderBar() {
    const bar = this.$('.m-cmdbar');
    const btn = (a, label, title, cls = '') => `<button class="chip ${cls}" data-a="${a}" title="${esc(title)}">${label}</button>`;
    const parts = this.modelParts();
    bar.innerHTML = `
      <div class="menu as-insert">${btn('insert', '＋ Insert part ▾', parts.length ? 'Add a part of this project: a 3D model ◆, a quick part ▤ (drawing, picture, import) or another assembly ◇ (as one unit)' : 'Make a part first (＋ New 3D model, or open a drawing / picture)', 'tool')}
        <div class="menu-list">${parts.map((p) => `<button data-part="${p.id}" data-no-i18n>${p.kind === 'classic' ? '▤' : p.kind === 'assembly' ? '◇' : '◆'} ${esc(p.name)}</button>`).join('') || '<div class="hint">No parts yet</div>'}
          ${this.hooks.importSolid ? '<div class="menu-sep"></div><button data-a="fromFile">📂 From a file (STEP / STL / OBJ)…</button>' : ''}</div></div>
      <div class="menu as-joint">${btn('joint', `🔗 Joint ▾`, 'Hold a part against another one: choose how, then click a face of the part to move and the face it goes to (S = touch)', `tool ${this.mode !== 'idle' ? 'on' : ''}`)}
        <div class="menu-list">${Object.entries(JOINT_TYPES).map(([k, j]) => `<button data-joint="${k}" title="${esc(j.hint)}">${j.icon} ${esc(j.name)}</button>`).join('')}</div></div>
      ${btn('measure', '📏 Measure', 'Measure: click a spot (a face, a corner), then another one — the distance; two parallel flat faces: the gap between them; two round faces: how far apart their axes are', `tool ${this.measuring ? 'on' : ''}`)}
      ${btn('fasteners', '🔩 Fasteners', 'Screws, heat-set inserts and pins where holes line up across parts — suggested, added with one click', `tool ${this.fastenerPanel ? 'on' : ''}`)}
      <span class="sep"></span>
      <button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
      <span class="sep"></span>
      <label class="chip as-explode" title="Pull the parts apart to see them (the placement does not change)">Explode <input type="range" min="0" max="1" step="0.01" value="${this.explode}"></label>
      <span class="sep"></span>
      ${btn('view-iso', 'Iso', 'View from the front-right, above')}${btn('view-top', 'Top', 'View from above')}${btn('view-front', 'Front', 'View from the front')}${btn('view-right', 'Right', 'View from the right')}`;
    bar.querySelector('[data-a=insert]').disabled = !parts.length && !this.hooks.importSolid;
    bar.querySelector('[data-a=joint]').disabled = this.doc.instances.length < 2;
    bar.querySelector('[data-a=joint]').addEventListener('click', (e) => {
      e.stopPropagation();
      if (this.mode !== 'idle') { this.cancelJoint(); return; }
      bar.querySelector('.as-joint').classList.toggle('open');
    });
    for (const b of bar.querySelectorAll('[data-joint]')) b.addEventListener('click', () => { bar.querySelector('.as-joint').classList.remove('open'); this.startJoint(b.dataset.joint); });
    bar.querySelector('[data-a=insert]').addEventListener('click', (e) => { e.stopPropagation(); bar.querySelector('.as-insert').classList.toggle('open'); });
    for (const b of bar.querySelectorAll('[data-part]')) b.addEventListener('click', () => { bar.querySelector('.as-insert').classList.remove('open'); this.insert(b.dataset.part); });
    bar.querySelector('[data-a=fromFile]')?.addEventListener('click', () => { bar.querySelector('.as-insert').classList.remove('open'); this.insertFile(); });
    for (const b of bar.querySelectorAll('[data-a]:not([data-a=insert]):not([data-a=joint]):not([data-a=fromFile])')) b.addEventListener('click', () => this.action(b.dataset.a));
    const r = bar.querySelector('.as-explode input');
    r.addEventListener('input', () => { this.explode = +r.value; this.draw(); });
    this.updateUndo();
  }

  updateUndo() {
    const u = this.$('.m-cmdbar [data-a=undo]'), r = this.$('.m-cmdbar [data-a=redo]');
    if (u) u.disabled = !this.history.canUndo();
    if (r) r.disabled = !this.history.canRedo();
  }

  action(a) {
    if (a === 'snap') return this.startJoint('touch');
    if (a === 'measure') return this.toggleMeasure();
    if (a === 'fasteners') { this.fastenerPanel = !this.fastenerPanel; this.sel = null; this.render(); this.draw(); return null; }
    if (a === 'undo') return this.history.go(-1);
    if (a === 'redo') return this.history.go(1);
    if (a.startsWith('view-')) return this.view.setView(a.slice(5));
    return null;
  }

  hint(text) { const h = this.$('.m-hint'); h.hidden = !text; h.textContent = text || ''; }

  renderList() {
    const list = this.$('.as-list');
    this.$('.as-start').hidden = this.doc.instances.length > 0;
    list.innerHTML = '';
    for (const it of this.doc.instances) {
      const b = this.bodies[it.part];
      const row = document.createElement('div');
      row.className = `mt-item${it.id === this.sel ? ' on' : ''}${b?.error ? ' bad' : ''}`;
      row.innerHTML = `<span class="mt-icon">${this.kindOf(it.part) === 'assembly' ? '◇' : this.kindOf(it.part) === 'classic' ? '▤' : '◆'}</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>
        ${b?.error ? '<span class="mt-warn">⚠</span>' : ''}
        <span class="mt-acts"><button class="mini" data-a="rename" title="Rename its part (its tab too)">🏷</button><button class="mini" data-a="dup" title="One more of this part">⧉</button><button class="mini danger" data-a="del" title="Take it out of the assembly">✕</button></span>`;
      row.querySelector('.mt-name').textContent = this.partName(it.part);
      row.querySelector('.mt-what').textContent = it.id;
      if (b?.error) row.title = b.error;
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'dup') return this.insert(it.part, it);
        if (a === 'rename') {
          renameInPlace(row.querySelector('.mt-name'), (n) => { this.hooks.renamePart?.(it.part, n); this.render(); this.hooks.onChange?.(); });
          return null;
        }
        if (a === 'del') return this.removeInst(it.id);
        this.sel = it.id;
        this.render();
        this.draw();
        return null;
      });
      list.appendChild(row);
    }
  }

  /** The parts list: part, how many, material, mass each and in all. */
  bom() {
    const rows = {};
    for (const it of this.doc.instances) {
      const r = (rows[it.part] = rows[it.part] || { part: it.part, name: this.partName(it.part), qty: 0 });
      r.qty++;
      const data = this.hooks.partData(it.part);
      r.material = data?.material || 'PLA';
      const b = this.bodies[it.part]?.body, v = b?.volume;
      if (b?.sub) r.material = '—';
      r.mass = b?.mass_g ?? (v ? (v / 1000) * MATERIALS[r.material] : null);
    }
    return Object.values(rows);
  }

  renderProps() {
    const box = this.$('.mp-body'), it = this.inst(this.sel);
    if (this.bolt) { this.renderBolt(box); return; }
    this.view.setGhost([]);
    if (this.fastenerPanel && !it) { this.renderFasteners(box); return; }
    if (it) {
      const m = new THREE.Matrix4().fromArray(it.matrix), p = new THREE.Vector3().setFromMatrixPosition(m);
      const e = new THREE.Euler().setFromRotationMatrix(m, 'XYZ'), deg = (r) => Math.round((r * 180) / Math.PI * 10) / 10;
      const row = (k, v) => `<div class="field"><label>${k.toUpperCase()}</label><input type="number" step="any" data-k="${k}" value="${fmt(v)}"><span class="unit">mm</span></div>`;
      const rot = (k) => `<div class="as-rot"><label>${k.toUpperCase()}</label>
        <input type="range" min="-180" max="180" step="1" list="as-ticks" data-rot="${k}" value="${deg(e[k])}">
        <input type="number" step="any" data-rotn="${k}" value="${fmt(deg(e[k]))}"><span class="unit">°</span></div>`;
      box.innerHTML = `<h2 data-no-i18n>${esc(this.partName(it.part))}</h2><p class="hint">${it.id} — where its own origin is, and how it is turned.</p>
        ${row('x', p.x)}${row('y', p.y)}${row('z', p.z)}
        <h3>Turn</h3><datalist id="as-ticks"><option value="-180"></option><option value="-90"></option><option value="0"></option><option value="90"></option><option value="180"></option></datalist>
        ${rot('x')}${rot('y')}${rot('z')}
        <p class="hint">Slide to any angle — it catches at 0, ±90 and ±180°. Type an exact one in the box.</p>
        ${this.editHtml(it)}
        <h3>Look</h3>${this.lookHtml(it)}
        ${this.jointsHtml(it.id)}
        <div class="row-actions wrap"><button class="btn small" data-a="joinThis">🔗 Join it to another part</button></div>
        ${this.hooks.duplicatePart ? '<div class="row-actions"><button class="btn small" data-a="ownPart" title="Copy its part as a new part of the project and use the copy here — then it can be changed alone (the other copies stay as they are)">⧉ Make it its own part</button></div>' : ''}
        <div class="row-actions"><button class="btn small" data-a="reset" title="Back to its place in its own model">Reset its place</button><button class="btn small danger" data-a="del">Take it out</button></div>`;
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
      this.bindJointRows(box);
      this.bindLook(box, it);
      box.querySelector('[data-a=editHere]')?.addEventListener('click', () => this.editInPlace(it.id));
      box.querySelector('[data-a=editLock]')?.addEventListener('click', () => this.toggleEditable(it.part));
      box.querySelector('[data-a=joinThis]').addEventListener('click', () => this.startJoint('touch', it.id));
      box.querySelector('[data-a=ownPart]')?.addEventListener('click', () => this.ownPart(it.id));
      box.querySelector('[data-a=reset]').addEventListener('click', () => { if (!this.mayMove(it.id)) return; it.matrix = ID(); this.applyMates(); this.commit(); });
      box.querySelector('[data-a=del]').addEventListener('click', () => this.removeInst(it.id));
      return;
    }
    const rows = this.bom(), total = rows.reduce((s, r) => s + (r.mass || 0) * r.qty, 0);
    box.innerHTML = `<h2>Assembly</h2>
      ${rows.length ? `${this.jointsHtml(null)}<h3>Parts list</h3><table class="as-bom"><tr><th>Part</th><th>Qty</th><th>Material</th><th>Mass</th></tr>
        ${rows.map((r) => `<tr><td data-no-i18n>${esc(r.name)}</td><td>${r.qty}</td><td>${r.material}</td><td>${r.mass === null ? '—' : `${fmt(+(r.mass * r.qty).toFixed(1))} g`}</td></tr>`).join('')}
        <tr class="as-total"><td>Total</td><td>${rows.reduce((s, r) => s + r.qty, 0)}</td><td></td><td>${fmt(+total.toFixed(1))} g</td></tr></table>
        <h3>Export</h3><div class="row-actions"><button class="btn small" data-x="stl" title="All parts in one STL, as placed">STL</button>
        <button class="btn small" data-x="step" title="All parts as separate bodies in one STEP file">STEP</button></div>
        <p class="hint">To print, open each part's tab and use 🖨 Prepare for 3D print there.</p>`
        : `<p class="hint">Insert parts of this project (3D models and quick parts) with ＋ Insert part, then join them with 🔗 Joint.</p>`}`;
    this.bindJointRows(box);
    for (const el of box.querySelectorAll('[data-x]')) el.addEventListener('click', () => this.export(el.dataset.x));
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

  // ------------------------------------------------------------------ 📏 measure
  toggleMeasure() {
    this.measuring = this.measuring ? null : { a: null };
    if (this.measuring) { this.cancelJoint(); if (this.bolt) this.cancelBolt(); }
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
        : `<b>Corner</b><span>Of</span><b data-no-i18n>${who} ${mp.inst}</b>`;
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
      const it = this.inst(h.inst), data = this.hooks.partData(it.part), body = this.bodies[it.part]?.body;
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
      ? { kind: 'pin', size: plan.pin, length: plan.length, entry: { inst: first.inst, hole: names[0], plane: first.inFace } }
      : { kind: 'screw', size: plan.size, length: plan.length, entry: { inst: first.inst, hole: names[0], plane: first.inFace },
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
      const place = (kind, size, length) => {
        const mdl = fastenerModel(kind, size, length), it = { id: this.newId(), part: this.ensurePart(mdl), matrix: ID() };
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
    const context = this.doc.instances.filter((o) => o.id !== instId && this.bodies[o.part]?.body).map((o) => ({
      positions: this.bodies[o.part].body.positions, matrix: Mi.clone().multiply(new THREE.Matrix4().fromArray(o.matrix)).toArray() }));
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
      ${own ? '<div class="row-actions"><button class="btn small" data-look="reset">↺ As its part</button></div>' : ''}`;
  }

  bindLook(box, it) {
    const col = box.querySelector('[data-look=colour]'), clr = box.querySelector('[data-look=clear]');
    col?.addEventListener('input', () => { it.colour = col.value; this.draw(); });
    col?.addEventListener('change', () => this.commit());
    clr?.addEventListener('input', () => { it.opacity = +(1 - clr.value / 100).toFixed(2); clr.nextElementSibling.textContent = `${clr.value} %`; this.draw(); });
    clr?.addEventListener('change', () => this.commit());
    box.querySelector('[data-look=reset]')?.addEventListener('click', () => { delete it.colour; delete it.opacity; this.commit(); });
  }

  /** "the top of Extrude 1" for a face of a placed part. */
  faceText(instId, name) {
    const it = this.inst(instId);
    if (String(name).includes('/')) { // a face of a part inside a sub-assembly
      const [sub, rest] = String(name).split(/\/(.*)/s), si = (this.hooks.partData(it?.part)?.instances || []).find((x) => x.id === sub);
      return `${this.partName(si?.part)} ${sub}: ${rest}`;
    }
    const feats = this.hooks.partData(it?.part)?.features || [];
    const [fid, role, sub] = String(name).split(':'), g = feats.find((f) => f.id === fid);
    if (fid === 'Q1') return `face ${String(role).slice(1)}`;
    const what = { end: 'the top of', start: 'the bottom of', side: 'a wall of', hole: 'hole of', round: 'a rounding of', bottom: 'a hole bottom of' }[role] || 'a face of';
    return g ? `${what} ${g.name}` : name;
  }

  /** The joints of a part (or all, id null) as rows: what holds what, its gap / flip, ✕. */
  jointsHtml(id) {
    const js = (this.doc.mates || []).filter((m) => id === null || m.move === id || m.onto === id);
    if (!js.length) return id === null ? '' : '<p class="hint">Not joined to anything — it stays where you put it.</p>';
    return `<h3>Joints</h3><datalist id="as-ticks"><option value="-180"></option><option value="-90"></option><option value="0"></option><option value="90"></option><option value="180"></option></datalist><div class="as-joints">${js.map((m) => {
      const t = JOINT_TYPES[m.type || 'touch'] || JOINT_TYPES.touch, a = this.inst(m.move), b = this.inst(m.onto);
      const val = m.type === 'touch' || m.type === 'gap' || m.type === 'flush' || !m.type
        ? `<label class="as-jv">${m.type === 'flush' ? 'offset' : 'gap'} <input type="number" step="any" data-jgap="${m.id}" value="${fmt(m.gap || 0)}"> mm</label>`
        : m.type === 'axis' ? `<label class="as-jv" title="Distance along the axis between the facing ends of the two round faces (e.g. two plates 30 mm apart). Empty: it slides freely.">↕ <input type="number" step="any" data-jdist="${m.id}" value="${Number.isFinite(m.dist) ? fmt(m.dist) : ''}" placeholder="free"> mm</label>
          <button class="mini ${Number.isFinite(m.angle) ? 'on' : ''}" data-jrot="${m.id}" title="${Number.isFinite(m.angle) ? 'Its turn about the axis is locked — click to let it turn freely' : 'Lock its turn about the axis (where it is now)'}">${Number.isFinite(m.angle) ? '↻🔒' : '↻🔓'}</button><button class="mini" data-jflip="${m.id}" title="Turn it the other way round">⇅</button>`
        : m.type === 'perp' ? '<span></span>'
        : `${m.type === 'angle' ? `<label class="as-jv">∠ <input type="number" step="any" data-jval="${m.id}" value="${fmt(m.value || 0)}"> °</label>` : ''}<button class="mini" data-jflip="${m.id}" title="Turn it the other way round">⇅</button>`;
      const spin = Math.round(Number.isFinite(m.angle) ? m.angle : this.spinNow(m));
      return `<div class="as-jrow ${m.broken ? 'bad' : ''} ${m.locked ? 'locked' : ''}" data-jrow="${m.id}"><span class="as-jt">${t.icon} ${esc(t.name)}</span>
        <span class="as-jw"><b data-no-i18n>${esc(this.partName(a?.part))}</b> <i>${m.move}</i> · ${esc(this.faceText(m.move, m.face))} → <b data-no-i18n>${esc(this.partName(b?.part))}</b> <i>${m.onto}</i> · ${esc(this.faceText(m.onto, m.ontoFace))}${m.broken ? ' — ⚠ a face is gone' : ''}</span>
        ${val}<span class="as-jbtn"><button class="mini ${m.locked ? 'on' : ''}" data-jlock="${m.id}" title="${m.locked ? 'Locked: moving the part by hand cannot break it — click to unlock' : 'Lock it: then it cannot be broken by moving the part'}">${m.locked ? '🔒' : '🔓'}</button><button class="mini danger" data-jdel="${m.id}" title="Remove this joint (the part stays where it is)" ${m.locked ? 'disabled' : ''}>✕</button></span>
        <label class="as-jspin" title="Turn the part about this joint (about the axis, or on the face)">↻ <input type="range" min="-180" max="180" step="1" list="as-ticks" data-jspin="${m.id}" value="${spin}">
        <input type="number" step="any" data-jspinn="${m.id}" value="${spin}">°</label></div>`;
    }).join('')}</div>`;
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
    for (const el of box.querySelectorAll('[data-jflip]')) {
      el.addEventListener('click', () => { const m = this.doc.mates.find((x) => x.id === el.dataset.jflip); m.flip = !m.flip; this.applyMates(); this.commit(); });
    }
    for (const el of box.querySelectorAll('[data-jlock]')) {
      el.addEventListener('click', () => { const m = this.doc.mates.find((x) => x.id === el.dataset.jlock); m.locked = !m.locked; this.commit(); });
    }
    for (const sl of box.querySelectorAll('[data-jspin]')) {
      const m = this.doc.mates.find((x) => x.id === sl.dataset.jspin), num = box.querySelector(`[data-jspinn="${m.id}"]`);
      const set = (v, final) => { m.angle = v; this.applyMates(); if (final) this.commit(); else this.draw(); };
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
      el.addEventListener('click', () => { this.doc.mates = this.doc.mates.filter((x) => x.id !== el.dataset.jdel); this.hoverJoint = null; this.commit(); });
    }
  }

  /** The faces to colour: the face under the mouse while picking, the joint the mouse is on in the list, and the
   *  chosen part's joints (its own faces green, the faces it is held to blue). */
  drawMarks() {
    const marks = [], faceIds = (instId, name) => {
      const b = this.bodies[this.inst(instId)?.part]?.body;
      return b ? b.faces.filter((f) => f.name === name || (f.names || []).includes(name)).map((f) => f.id) : [];
    };
    for (const m of this.doc.mates || []) {
      const on = this.hoverJoint === m.id || (!this.hoverJoint && this.sel && (m.move === this.sel || m.onto === this.sel));
      if (!on) continue;
      marks.push({ inst: m.move, faces: faceIds(m.move, m.face), color: 0x3fb950 }, { inst: m.onto, faces: faceIds(m.onto, m.ontoFace), color: 0x58a6ff });
    }
    for (const h of this.hoverCand?.holes || []) marks.push({ inst: h.inst, faces: faceIds(h.inst, h.name), color: 0xf2cc60 });
    if (this.jointFrom?.face) marks.push({ inst: this.jointFrom.inst, faces: [this.jointFrom.face.id], color: 0x3fb950 });
    if (this.hoverFace) marks.push({ inst: this.hoverFace.inst, faces: [this.hoverFace.face.id], color: this.hoverFace.ok ? 0xf2cc60 : 0x8b95a3 });
    this.view.setMarks(marks);
  }

  renderStatus() {
    const n = this.doc.instances.length, j = (this.doc.mates || []).length;
    this.$('.m-status').textContent = n ? `${n} part(s)${j ? ` · ${j} joint(s)` : ''}` : '';
  }

  // ------------------------------------------------------------------ bodies of the parts
  async refresh() {
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
    await this.buildBodies([...new Set([...need.filter((pid) => !subs.includes(pid)), ...inner])]);
    for (const pid of subs) this.mergeAssembly(pid);
    this.applyMates();
    this.draw();
    this.renderList();
    this.renderProps();
  }

  /** A sub-assembly as one body: its parts' meshes placed by their matrices, face names "<its instance>/<name>". */
  mergeAssembly(pid, seen = new Set()) {
    const data = this.hooks.partData(pid);
    if (!data || seen.has(pid)) return this.bodies[pid];
    seen.add(pid);
    const key = JSON.stringify(data) + (data.instances || []).map((i) => this.bodies[i.part]?.key || '').join('|');
    if (this.bodies[pid]?.key === key) return this.bodies[pid];
    const pos = [], ids = [], faces = [], edges = [];
    let vol = 0, mass = 0, box = null, off = 0;
    for (const it of data.instances || []) {
      const sub = this.kindOf(it.part) === 'assembly' ? this.mergeAssembly(it.part, seen) : this.bodies[it.part];
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
      mass += b.mass_g ?? (b.volume / 1000) * (MATERIALS[this.hooks.partData(it.part)?.material || 'PLA'] || 1.24);
      const bb = new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(M);
      box = box ? box.union(bb) : bb;
    }
    const enc = (arr, T) => { const u = new Uint8Array(new T(arr).buffer); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); return btoa(s); };
    this.bodies[pid] = box ? { key, body: { positions: enc(pos, Float32Array), face_ids: enc(ids, Uint32Array), faces, edges, volume: vol, mass_g: mass,
      bbox: [...box.min.toArray(), ...box.max.toArray()], sub: true } } : { key, error: 'This assembly has no parts with a solid yet.' };
    return this.bodies[pid];
  }

  /** The 3D model / quick parts' bodies, from the kernel (unchanged ones are kept). */
  async buildBodies(need) {
    await Promise.all(need.map(async (pid) => {
      const data = this.hooks.partData(pid);
      if (!data) { this.bodies[pid] = { error: 'This part is no longer in the project.' }; return; }
      const key = JSON.stringify(data.features || { model: data.model, values: data.values, layers: data.layers, bends: data.bends });
      if (this.bodies[pid]?.key === key) return;
      try {
        const features = await this.partFeatures(pid, data);
        const res = await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: { features } }) });
        const r = await res.json();
        if (!res.ok) throw new Error(r.error || res.statusText);
        if (!r.ok && !r.body) throw new Error(r.features.flatMap((s) => s.issues).join(' ') || 'This part has no solid.');
        this.bodies[pid] = r.body ? { key, body: r.body, features } : { key, error: 'This part has no solid yet.' };
      } catch (e) { this.bodies[pid] = { key, error: e.message }; }
    }));
  }

  draw() {
    // exploded: each part pushed away from the middle of the assembly
    const centres = this.doc.instances.map((it) => {
      const b = this.bodies[it.part]?.body;
      if (!b) return null;
      const c = new THREE.Vector3((b.bbox[0] + b.bbox[3]) / 2, (b.bbox[1] + b.bbox[4]) / 2, (b.bbox[2] + b.bbox[5]) / 2);
      return c.applyMatrix4(new THREE.Matrix4().fromArray(it.matrix));
    });
    const ok = centres.filter(Boolean), mid = ok.reduce((s, c) => s.add(c), new THREE.Vector3()).multiplyScalar(1 / (ok.length || 1));
    this.view.setBodies(this.doc.instances.map((it, k) => {
      const c = centres[k];
      const look = this.lookOf(it);
      return { id: it.id, body: this.bodies[it.part]?.body, matrix: it.matrix, color: this.modelParts().findIndex((p) => p.id === it.part), ...look,
        selected: it.id === this.sel || it.id === this.jointFrom?.inst, hover: it.id === this.hoverInst,
        explode: this.explode && c ? c.clone().sub(mid).multiplyScalar(this.explode * 1.2).toArray() : null };
    }));
    this.drawMarks();
  }

  commit() { this.history.commit(); this.render(); this.draw(); this.hooks.onChange?.(); }

  /** How a placed part looks: its own colour / see-through in this assembly, else its part's -> {colour, opacity}. */
  lookOf(it) {
    const data = this.hooks.partData(it.part) || {};
    const colour = it.colour || data.color, opacity = Number.isFinite(it.opacity) ? it.opacity : data.opacity;
    return { colour: colour ? new THREE.Color(colour).getHex() : null, opacity: Number.isFinite(opacity) ? opacity : 1, paint: it.colour ? null : data.paint || null, ownColour: !!it.colour };
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
    const it = { id: this.newId(), part: partId, matrix: m.toArray() };
    this.doc.instances.push(it);
    await this.refresh();
    const b = this.bodies[partId]?.body;
    if (b && this.doc.instances.length > 1) {
      const bb = new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(m);
      it.matrix = new THREE.Matrix4().makeTranslation(x - bb.min.x, 0, 0).multiply(m).toArray();
    }
    this.sel = it.id;
    this.commit();
    if (this.doc.instances.length === 1 || !like) this.view.setView('iso');
  }

  /** A placed part gets a part of its own: its part copied as a new part, this one uses the copy (joints stay). */
  async ownPart(instId) {
    const it = this.inst(instId);
    if (!it || !this.hooks.duplicatePart) return null;
    const id = await this.hooks.duplicatePart(it.part);
    if (!id) return null;
    it.part = id;
    await this.refresh();
    this.commit();
    this.hooks.toast(t2('{inst} now has a part of its own: {name} — change it without changing the others.', { inst: instId, name: this.partName(id) }), 'ok', 5000);
    return id;
  }

  /** ＋ Insert part ▾ From a file: a STEP / STL / OBJ becomes a 3D model part of the project, and goes in. */
  insertFile() {
    const inp = document.createElement('input');
    Object.assign(inp, { type: 'file', accept: '.step,.stp,.stl,.obj' });
    inp.addEventListener('change', async () => {
      const file = inp.files[0];
      if (!file) return;
      let step;
      try { step = await this.hooks.importSolid(file); } catch (e) { this.hooks.toast(e.message.replace(/^MESH_TOO_BIG /, ''), 'error', 9000); return; }
      await this.insert(this.hooks.addModelPart(step.name, { features: [step] }));
    });
    inp.click();
  }

  removeInst(id) {
    this.doc.instances = this.doc.instances.filter((i) => i.id !== id);
    this.doc.mates = (this.doc.mates || []).filter((m) => m.move !== id && m.onto !== id);
    if (this.sel === id) this.sel = null;
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

  // ------------------------------------------------------------------ joints: they hold
  unjoinMoving(id) { this.doc.mates = (this.doc.mates || []).filter((m) => m.move !== id); }
  unlink(id) { this.unjoinMoving(id); }
  mateOf(id) { return (this.doc.mates || []).find((m) => m.move === id); }

  /** Add a joint: part `from.inst` (face from.face) is held against `to.inst` (face to.face). */
  addJoint(from, to, type = 'touch', gap = 0) {
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
    const n = Math.max(0, ...(this.doc.mates || []).map((m) => parseInt(String(m.id || '').slice(1), 10) || 0)) + 1;
    this.doc.mates = [...(this.doc.mates || []), { id: `J${n}`, type, move: from.inst, face: fromName, onto: to.inst, ontoFace: toName, gap: +gap || 0 }];
    return true;
  }

  /** Kept for the first-version name of a snap. */
  link(from, to) { this.addJoint(from, to, 'touch'); }

  /** A part moved or turned by hand (after mayMove): the parts joined onto it follow it. */
  movedByHand() { this.applyMates(); }

  /** Place every joined part again: each part's joints in order, a part after the parts it hangs on. */
  applyMates() {
    const mates = (this.doc.mates || []).filter((m) => this.inst(m.move) && this.inst(m.onto));
    this.doc.mates = mates;
    const movers = [...new Set(mates.map((m) => m.move))], done = new Set();
    for (let pass = 0; pass <= movers.length && done.size < movers.length; pass++) {
      for (const id of movers) {
        if (done.has(id)) continue;
        const mine = mates.filter((m) => m.move === id);
        if (mine.some((m) => movers.includes(m.onto) && !done.has(m.onto) && m.onto !== id)) continue; // its support first
        done.add(id);
        const it = this.inst(id);
        if (!this.bodies[it.part]?.body || mine.some((m) => !this.bodies[this.inst(m.onto).part]?.body)) continue; // not built yet
        let M = new THREE.Matrix4().fromArray(it.matrix), fixed = null;
        mine.forEach((m, k) => {
          try {
            const r = applyJoint(M, m, (MM) => this.worldFace(id, m.face, MM), this.worldFace(m.onto, m.ontoFace), k === 0, fixed);
            M = r.M;
            fixed = fixed || r.fixed;
            delete m.broken;
          } catch { m.broken = true; }
        });
        it.matrix = M.toArray().map((v) => (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v) : +v.toFixed(9)));
      }
    }
  }

  /** The selected part turned to an angle (degrees) about X / Y / Z, about its own centre (the other two angles
   *  stay). final: an undo step (else a live preview while sliding). */
  setRot(axis, deg, final) {
    const it = this.inst(this.sel), b = this.bodies[it?.part]?.body;
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
    const it = this.inst(this.sel), b = this.bodies[it?.part]?.body;
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
    if (this.addJoint(this.jointFrom, h, type, type === 'gap' ? 5 : 0)) {
      if (type === 'axis' && /:hole:/.test(this.jointFrom.face.name) && /:hole:/.test(h.face.name)) this.autoDistance(this.doc.mates[this.doc.mates.length - 1]);
      if (type === 'angle') { // it starts at the angle the faces make now (rounded), then it holds
        const m = this.doc.mates[this.doc.mates.length - 1], a = this.jointFrom.face.normal, b = h.face.normal;
        m.value = a && b ? Math.round((a.angleTo(b) * 180) / Math.PI) : 45;
      }
      this.applyMates();
      this.sel = this.jointFrom.inst;
      this.hooks.toast(`${JOINT_TYPES[type].name} — it now holds (change it or ✕ it in the panel).`, 'ok', 3000);
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
    let down = null;
    cv.addEventListener('pointerdown', (e) => { if (e.button === 0) down = { x: e.clientX, y: e.clientY }; });
    cv.addEventListener('pointermove', (e) => {
      if (down) return;
      const h = this.view.pickInst(e.clientX, e.clientY);
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
      cv.style.cursor = h ? 'pointer' : '';
    });
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
      if (this.mode !== 'idle') { this.clickJoint(h); return; }
      if (this.bolt) { if (h?.face?.type === 'plane') this.startBolt(h); return; } // another point for the bolt
      this.sel = h?.inst || null;
      this.render();
      this.draw();
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    const k = e.key.toLowerCase();
    if (e.key === 'Escape' && this.measuring) { this.toggleMeasure(); return; }
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
    const b = this.bodies[it.part]?.body;
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

  summary() {
    return {
      parts: this.doc.instances.map((it) => {
        const b = this.bodies[it.part]?.body, m = new THREE.Matrix4().fromArray(it.matrix);
        const bb = b ? new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(m) : null;
        return { id: it.id, part: it.part, name: this.partName(it.part), position: new THREE.Vector3().setFromMatrixPosition(m).toArray().map((v) => +v.toFixed(3)),
          bbox: bb ? [...bb.min.toArray(), ...bb.max.toArray()].map((v) => +v.toFixed(3)) : null, error: this.bodies[it.part]?.error };
      }),
      joints: (this.doc.mates || []).map((m) => ({ id: m.id, type: m.type || 'touch', part: m.move, face: m.face, onto: m.onto, onto_face: m.ontoFace,
        ...(m.type === 'axis' ? { distance: Number.isFinite(m.dist) ? m.dist : null, rotation_locked: Number.isFinite(m.angle) } : { gap: m.gap || 0 }), ...(m.broken ? { broken: true } : {}) })),
      parts_list: this.bom().map((r) => ({ name: r.name, qty: r.qty, material: r.material, mass_g_each: r.mass === null ? null : +r.mass.toFixed(2) })),
    };
  }

  handlers() {
    const need = () => { if (!this.active) throw new Error('No assembly is on screen — new_assembly, or open_part an assembly.'); };
    const settle = () => this.refresh();
    return {
      get_assembly: async () => { need(); await settle(); return { text: JSON.stringify(this.summary()) }; },
      insert_part: async ({ part }) => {
        need();
        const p = this.modelParts().find((q) => q.id === part || q.name === part);
        if (!p) throw new Error(`No part “${part}” that can go in (a 3D model or a quick part with a shape) — see list_parts.`);
        await this.insert(p.id);
        return { text: JSON.stringify(this.summary()) };
      },
      snap_faces: async ({ move, onto, type = 'touch', gap, value, lock_rotation }) => {
        need();
        await settle();
        if (!JOINT_TYPES[type] || JOINT_TYPES[type].pick) throw new Error(`type is ${Object.keys(JOINT_TYPES).filter((k) => !JOINT_TYPES[k].pick).join(', ')} (screws and pins: suggest_fasteners / add_fasteners).`);
        const from = { inst: move.part, face: this.worldFace(move.part, move.face) };
        const to = { inst: onto.part, face: this.worldFace(onto.part, onto.face) };
        if (from.inst === to.inst) throw new Error('Join a face of one part to a face of another part.');
        const want = JOINT_TYPES[type].faces;
        if (want === 'mixed') {
          if (new Set([from.face.type, to.face.type, 'plane', 'cylinder']).size !== 2 || from.face.type === to.face.type) throw new Error('Tangent joins a round face and a flat face.');
        } else if (from.face.type !== want || to.face.type !== want) throw new Error(`${JOINT_TYPES[type].name} joins two ${want === 'cylinder' ? 'round' : 'flat'} faces.`);
        if (!this.addJoint(from, to, type, type === 'axis' ? 0 : gap || 0)) throw new Error('Not joined: the other part already hangs on this one.');
        const nj = this.doc.mates[this.doc.mates.length - 1];
        if (type === 'axis' && Number.isFinite(+gap) && gap !== undefined && gap !== null) {
          this.applyMates();
          nj.side = axialGap(this.worldFace(nj.move, nj.face), this.worldFace(nj.onto, nj.ontoFace))?.side || 1;
          nj.dist = +gap;
        }
        if (type === 'axis' && lock_rotation) { this.applyMates(); nj.angle = Math.round(this.spinNow(nj)); }
        if (type === 'angle') this.doc.mates[this.doc.mates.length - 1].value = Number.isFinite(+value) ? +value : Math.round((from.face.normal.angleTo(to.face.normal) * 180) / Math.PI);
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
          if (!this.mayMove(it.id, false)) throw new Error(`${part} is held by a locked joint — the user has to unlock it first.`);
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
    };
  }

  // ------------------------------------------------------------------ the assembly as a project tab
  async load(data) {
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
  hasBody() { return this.doc.instances.some((i) => this.bodies[i.part]?.body); }

  async export(fmtName) {
    const name = this.hooks.safeName();
    if (fmtName === 'stl') {
      const tris = [];
      for (const it of this.doc.instances) {
        const b = this.bodies[it.part]?.body;
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
    const flat = [];
    const expand = (list, parent) => {
      for (const it of list) {
        const M = parent.clone().multiply(new THREE.Matrix4().fromArray(it.matrix));
        if (this.kindOf(it.part) === 'assembly') expand(this.hooks.partData(it.part)?.instances || [], M);
        else flat.push({ part: { features: this.bodies[it.part]?.features || this.hooks.partData(it.part)?.features || [] }, matrix: M.toArray() });
      }
    };
    expand(this.doc.instances, new THREE.Matrix4());
    const instances = flat;
    const res = await fetch('/api/assembly/export/step', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances, name }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json().catch(() => ({ error: res.statusText }))).error}`, 'error'); return; }
    if (await this.hooks.download(await res.blob(), `${name}.step`)) this.hooks.toast('Exported STEP (in mm).', 'ok');
  }
}
