// The assembly workspace: 3D model parts of the project placed together — insert a part, snap it face to face onto
// another one with joints that hold (touch, gap, flush, pin in hole, parallel — joints.js), move it and turn it to any
// angle, an exploded view, a parts list with masses, export the whole as STL or STEP. No motion (parts do not move).
//
// Assembly JSON (in the project file, `parts[].assembly`):
//   {"instances": [{"id": "I1", "part": "P2", "matrix": [16 numbers, three.js column-major]}],
//    "mates": [{"id": "J1", "type": "touch" | "gap" | "flush" | "axis" | "parallel", "move": "I2", "face": "F2:start",
//               "onto": "I1", "ontoFace": "F2:end", "gap": 0, "flip": false}]}   joints that hold (joints.js)
import * as THREE from 'three';
import { History } from '../history.js';
import { ModelView } from '../modeler/view.js';
import { JOINT_TYPES, applyJoint } from './joints.js';
import { MATERIALS } from '../modeler/modeler.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
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
      const mat = new THREE.MeshStandardMaterial({ color: it.selected ? 0x6cb6ff : COLORS[it.color % COLORS.length], roughness: 0.55, metalness: 0.05,
        side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, emissive: it.hover ? 0x1b2a44 : 0x000000 });
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

  fitBox() {
    const box = new THREE.Box3();
    for (const m of this.meshes || []) box.expandByObject(m);
    return box.isEmpty() ? new THREE.Box3().setFromObject(this.datumGroup) : box;
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
      capture: () => ({ instances: this.doc.instances, mates: this.doc.mates }),
      restore: async (s) => { this.doc.instances = s.instances; this.doc.mates = s.mates || []; this.mode = 'idle'; this.render(); await this.refresh(); },
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
  modelParts() { return this.hooks.parts().filter((p) => p.kind === 'model' || (p.kind === 'classic' && this.hooks.partData(p.id)?.model)); }

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
      <div class="menu as-insert">${btn('insert', '＋ Insert part ▾', parts.length ? 'Add a part of this project: a 3D model ◆ or a quick part ▤ (drawing, picture, import)' : 'Make a part first (＋ New 3D model, or open a drawing / picture)', 'tool')}
        <div class="menu-list">${parts.map((p) => `<button data-part="${p.id}" data-no-i18n>${p.kind === 'classic' ? '▤' : '◆'} ${esc(p.name)}</button>`).join('') || '<div class="hint">No parts yet</div>'}</div></div>
      <div class="menu as-joint">${btn('joint', `🔗 Joint ▾`, 'Hold a part against another one: choose how, then click a face of the part to move and the face it goes to (S = touch)', `tool ${this.mode !== 'idle' ? 'on' : ''}`)}
        <div class="menu-list">${Object.entries(JOINT_TYPES).map(([k, j]) => `<button data-joint="${k}" title="${esc(j.hint)}">${j.icon} ${esc(j.name)}</button>`).join('')}</div></div>
      <span class="sep"></span>
      <button class="chip" data-a="undo" title="Undo (Ctrl+Z)">↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)">↷</button>
      <span class="sep"></span>
      <label class="chip as-explode" title="Pull the parts apart to see them (the placement does not change)">Explode <input type="range" min="0" max="1" step="0.01" value="${this.explode}"></label>
      <span class="sep"></span>
      ${btn('view-iso', 'Iso', 'View from the front-right, above')}${btn('view-top', 'Top', 'View from above')}${btn('view-front', 'Front', 'View from the front')}${btn('view-right', 'Right', 'View from the right')}`;
    bar.querySelector('[data-a=insert]').disabled = !parts.length;
    bar.querySelector('[data-a=joint]').disabled = this.doc.instances.length < 2;
    bar.querySelector('[data-a=joint]').addEventListener('click', (e) => {
      e.stopPropagation();
      if (this.mode !== 'idle') { this.cancelJoint(); return; }
      bar.querySelector('.as-joint').classList.toggle('open');
    });
    for (const b of bar.querySelectorAll('[data-joint]')) b.addEventListener('click', () => { bar.querySelector('.as-joint').classList.remove('open'); this.startJoint(b.dataset.joint); });
    bar.querySelector('[data-a=insert]').addEventListener('click', (e) => { e.stopPropagation(); bar.querySelector('.as-insert').classList.toggle('open'); });
    for (const b of bar.querySelectorAll('[data-part]')) b.addEventListener('click', () => { bar.querySelector('.as-insert').classList.remove('open'); this.insert(b.dataset.part); });
    for (const b of bar.querySelectorAll('[data-a]:not([data-a=insert]):not([data-a=joint])')) b.addEventListener('click', () => this.action(b.dataset.a));
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
      row.innerHTML = `<span class="mt-icon">◆</span><span class="mt-name" data-no-i18n></span><span class="mt-what"></span>
        ${b?.error ? '<span class="mt-warn">⚠</span>' : ''}
        <span class="mt-acts"><button class="mini" data-a="dup" title="One more of this part">⧉</button><button class="mini danger" data-a="del" title="Take it out of the assembly">✕</button></span>`;
      row.querySelector('.mt-name').textContent = this.partName(it.part);
      row.querySelector('.mt-what').textContent = it.id;
      if (b?.error) row.title = b.error;
      row.addEventListener('click', (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (a === 'dup') return this.insert(it.part, it);
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
      const v = this.bodies[it.part]?.body?.volume;
      r.mass = v ? (v / 1000) * MATERIALS[r.material] : null;
    }
    return Object.values(rows);
  }

  renderProps() {
    const box = this.$('.mp-body'), it = this.inst(this.sel);
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
        ${this.jointsHtml(it.id)}
        <div class="row-actions wrap"><button class="btn small" data-a="joinThis">🔗 Join it to another part</button></div>
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
      box.querySelector('[data-a=joinThis]').addEventListener('click', () => this.startJoint('touch', it.id));
      box.querySelector('[data-a=reset]').addEventListener('click', () => { it.matrix = ID(); this.unjoinMoving(it.id); this.commit(); });
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

  /** "the top of Extrude 1" for a face of a placed part. */
  faceText(instId, name) {
    const it = this.inst(instId), feats = this.hooks.partData(it?.part)?.features || [];
    const [fid, role, sub] = String(name).split(':'), g = feats.find((f) => f.id === fid);
    if (fid === 'Q1') return `face ${String(role).slice(1)}`;
    const what = { end: 'the top of', start: 'the bottom of', side: 'a wall of', hole: 'hole of', round: 'a rounding of', bottom: 'a hole bottom of' }[role] || 'a face of';
    return g ? `${what} ${g.name}` : name;
  }

  /** The joints of a part (or all, id null) as rows: what holds what, its gap / flip, ✕. */
  jointsHtml(id) {
    const js = (this.doc.mates || []).filter((m) => id === null || m.move === id || m.onto === id);
    if (!js.length) return id === null ? '' : '<p class="hint">Not joined to anything — it stays where you put it.</p>';
    return `<h3>Joints</h3><div class="as-joints">${js.map((m) => {
      const t = JOINT_TYPES[m.type || 'touch'] || JOINT_TYPES.touch, a = this.inst(m.move), b = this.inst(m.onto);
      const val = m.type === 'touch' || m.type === 'gap' || m.type === 'flush' || !m.type
        ? `<label class="as-jv">${m.type === 'flush' ? 'offset' : 'gap'} <input type="number" step="any" data-jgap="${m.id}" value="${fmt(m.gap || 0)}"> mm</label>`
        : `<button class="mini" data-jflip="${m.id}" title="Turn it the other way round">⇅</button>`;
      return `<div class="as-jrow ${m.broken ? 'bad' : ''}" data-jrow="${m.id}"><span class="as-jt">${t.icon} ${esc(t.name)}</span>
        <span class="as-jw"><b data-no-i18n>${esc(this.partName(a?.part))}</b> · ${esc(this.faceText(m.move, m.face))} → <b data-no-i18n>${esc(this.partName(b?.part))}</b> · ${esc(this.faceText(m.onto, m.ontoFace))}${m.broken ? ' — ⚠ a face is gone' : ''}</span>
        ${val}<button class="mini danger" data-jdel="${m.id}" title="Remove this joint (the part stays where it is)">✕</button></div>`;
    }).join('')}</div>`;
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
    for (const el of box.querySelectorAll('[data-jflip]')) {
      el.addEventListener('click', () => { const m = this.doc.mates.find((x) => x.id === el.dataset.jflip); m.flip = !m.flip; this.applyMates(); this.commit(); });
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
    this.applyMates();
    this.draw();
    this.renderList();
    this.renderProps();
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
      return { id: it.id, body: this.bodies[it.part]?.body, matrix: it.matrix, color: this.modelParts().findIndex((p) => p.id === it.part),
        selected: it.id === this.sel || it.id === this.jointFrom?.inst, hover: it.id === this.hoverInst,
        explode: this.explode && c ? c.clone().sub(mid).multiplyScalar(this.explode * 1.2).toArray() : null };
    }));
    this.drawMarks();
  }

  commit() { this.history.commit(); this.render(); this.draw(); this.hooks.onChange?.(); }

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

  removeInst(id) {
    this.doc.instances = this.doc.instances.filter((i) => i.id !== id);
    this.doc.mates = (this.doc.mates || []).filter((m) => m.move !== id && m.onto !== id);
    if (this.sel === id) this.sel = null;
    this.commit();
  }

  setPos(k, value) {
    const it = this.inst(this.sel), v = parseFloat(String(value).replace(',', '.'));
    if (!it || !Number.isFinite(v)) return;
    const m = new THREE.Matrix4().fromArray(it.matrix);
    const e = m.elements;
    e[{ x: 12, y: 13, z: 14 }[k]] = v;
    it.matrix = m.toArray();
    this.movedByHand(it.id);
    this.commit();
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

  /** A part moved or turned by hand is no longer held by its joints; the parts joined onto it follow it. */
  movedByHand(id) {
    if (this.mateOf(id)) { this.unjoinMoving(id); this.hooks.toast('Moved by hand — its joints are removed (the parts joined onto it still follow it).', 'info', 4000); }
    this.applyMates();
  }

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
    const t = JOINT_TYPES[this.jointType], what = t.faces === 'cylinder' ? 'a round face' : 'a flat face';
    this.hint(this.mode === 'joint-from' ? `${t.icon} ${t.name}: click ${what} of the part to move${this.jointFrom ? ' (the selected one)' : ''} — Esc cancels.`
      : `${t.icon} ${t.name}: now click ${what} of the other part.`);
    this.renderBar();
    this.draw();
  }

  /** The face under the mouse fits the joint being made? */
  faceFits(h) {
    if (!h?.face) return false;
    const want = JOINT_TYPES[this.jointType].faces;
    if (h.face.type !== want) return false;
    if (this.mode === 'joint-from' && this.jointFrom?.inst && h.inst !== this.jointFrom.inst) return false;
    if (this.mode === 'joint-to' && h.inst === this.jointFrom?.inst) return false;
    return true;
  }

  clickJoint(h) {
    if (!this.faceFits(h)) {
      const want = JOINT_TYPES[this.jointType].faces === 'cylinder' ? 'a round face (a hole, a pin)' : 'a flat face';
      if (h) this.hooks.toast(this.mode === 'joint-to' && h.inst === this.jointFrom?.inst ? 'Now a face of the other part.' : `Click ${want}.`, 'info', 2500);
      return;
    }
    if (this.mode === 'joint-from') {
      this.jointFrom = { inst: h.inst, face: h.face };
      this.mode = 'joint-to';
      this.jointHint();
      return;
    }
    const type = this.jointType;
    if (this.addJoint(this.jointFrom, h, type, type === 'gap' ? 5 : 0)) {
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
    cv.addEventListener('pointerup', (e) => {
      if (e.button !== 0 || !down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4;
      down = null;
      if (moved) return;
      const h = this.view.pickInst(e.clientX, e.clientY);
      if (this.mode !== 'idle') { this.clickJoint(h); return; }
      this.sel = h?.inst || null;
      this.render();
      this.draw();
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    const k = e.key.toLowerCase();
    if (e.key === 'Escape' && this.mode !== 'idle') { this.cancelJoint(); return; }
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
    const out = { ...f, centroid: new THREE.Vector3(...f.centroid).applyMatrix4(m) };
    if (f.type === 'plane') out.normal = new THREE.Vector3(...f.normal).applyMatrix3(nm).normalize();
    if (f.type === 'cylinder' && f.axis) out.axis = { o: new THREE.Vector3(...f.axis.o).applyMatrix4(m), d: new THREE.Vector3(...f.axis.d).applyMatrix3(nm).normalize() };
    return out;
  }

  summary() {
    return {
      parts: this.doc.instances.map((it) => {
        const b = this.bodies[it.part]?.body, m = new THREE.Matrix4().fromArray(it.matrix);
        const bb = b ? new THREE.Box3(new THREE.Vector3(...b.bbox.slice(0, 3)), new THREE.Vector3(...b.bbox.slice(3))).applyMatrix4(m) : null;
        return { id: it.id, part: it.part, name: this.partName(it.part), position: new THREE.Vector3().setFromMatrixPosition(m).toArray().map((v) => +v.toFixed(3)),
          bbox: bb ? [...bb.min.toArray(), ...bb.max.toArray()].map((v) => +v.toFixed(3)) : null, error: this.bodies[it.part]?.error };
      }),
      joints: (this.doc.mates || []).map((m) => ({ id: m.id, type: m.type || 'touch', part: m.move, face: m.face, onto: m.onto, onto_face: m.ontoFace, gap: m.gap || 0, ...(m.broken ? { broken: true } : {}) })),
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
      snap_faces: async ({ move, onto, type = 'touch', gap = 0 }) => {
        need();
        await settle();
        if (!JOINT_TYPES[type]) throw new Error(`type is ${Object.keys(JOINT_TYPES).join(', ')}.`);
        const from = { inst: move.part, face: this.worldFace(move.part, move.face) };
        const to = { inst: onto.part, face: this.worldFace(onto.part, onto.face) };
        if (from.inst === to.inst) throw new Error('Join a face of one part to a face of another part.');
        const want = JOINT_TYPES[type].faces;
        if (from.face.type !== want || to.face.type !== want) throw new Error(`${JOINT_TYPES[type].name} joins two ${want === 'cylinder' ? 'round' : 'flat'} faces.`);
        if (!this.addJoint(from, to, type, gap)) throw new Error('Not joined: the other part already hangs on this one.');
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
        for (const [k, v] of Object.entries({ x, y, z })) if (v !== undefined) this.setPos(k, v);
        for (const ax of [].concat(turn || [])) this.turn(ax);
        return { text: JSON.stringify(this.summary()) };
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
    const instances = this.doc.instances.map((it) => ({ part: { features: this.bodies[it.part]?.features || this.hooks.partData(it.part)?.features || [] }, matrix: it.matrix }));
    const res = await fetch('/api/assembly/export/step', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instances, name }) });
    if (!res.ok) { this.hooks.toast(`Export failed: ${(await res.json().catch(() => ({ error: res.statusText }))).error}`, 'error'); return; }
    if (await this.hooks.download(await res.blob(), `${name}.step`)) this.hooks.toast('Exported STEP (in mm).', 'ok');
  }
}
