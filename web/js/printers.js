// Print panel: printer profiles (built-in + custom), build-volume fit check and split into pieces.
import { newRid, trackProgress } from './progressbox.js';
const UNIT_IN_MM = { mm: 1, cm: 10, m: 1000, in: 25.4 };
const LS_KEY = 'a3d.printer';
const LS_JOINT = 'a3d.joint';
// what each joint parameter means (all sizes in mm)
const PARAM_LABELS = {
  width: 'Width (mm)', depth: 'Depth (mm)', angle: 'Flare angle °', count: 'Count per cut (0 = auto)',
  clearance: 'Fit clearance (mm)', size: 'Knob size (mm)', alternate: 'Alternate knob direction',
  length: 'Length (mm)', height: 'Height (mm)', face: 'Face', margin: 'Edge margin (mm)',
  screws: 'Screw holes', screw: 'Screw size (M…)',
  skin: 'Front skin (mm)', glue: 'Glue', groove: 'Glue channel (mm)', port: 'Glue port Ø (mm)',
};
const GLUE_OPTIONS = [
  ['ports', 'Channel + injection ports (back)'], ['groove', 'Glue channel only'], ['none', 'No glue features'],
];
const JOINT_HELP = {
  none: 'Straight cut — glue the pieces (a glue channel and back-side injection ports keep glue off the front).',
  dovetail: 'Trapezoid tabs through the full thickness — the dovetail outline shows on the front. No extra parts.',
  hidden_dovetail: 'Dovetails only behind a straight front skin: the front stays flat with a hairline seam. Pieces alternate male (print front-up) / female (print front-down); male pieces drop into the female sockets from the back.',
  puzzle: 'Round jigsaw knobs printed into the cut — press together. No extra parts.',
  butterfly: 'Bow-tie keys inlaid across each seam, printed separately and pressed in.',
  dowel: 'Rectangular pins in pockets inside the cut faces, printed separately.',
  plate: 'A thin plate recessed across each seam (back by default), with optional screw pilot holes.',
};

export class PrintPanel {
  constructor(root, { api, getBody, viewer, toast, download }) {
    this.root = root;
    this.api = api;
    this.getBody = getBody;
    this.viewer = viewer;
    this.toast = toast;
    this.download = download;
    this.printers = [];
    this.selected = null;
    this.margin = 5;
    this.showVolume = true;
    this.plan = null;
    this.pieces = null;
    this.joints = [];
    this.joint = { type: 'none' };
    try {
      this.selected = localStorage.getItem(LS_KEY);
      this.joint = JSON.parse(localStorage.getItem(LS_JOINT)) || this.joint;
    } catch { /* private mode */ }
  }

  async load() {
    [this.printers, this.joints] = await Promise.all([
      this.api('/api/printers').then((r) => r.json()), this.api('/api/joints').then((r) => r.json())]);
    if (!this.printers.some((p) => p.id === this.selected)) this.selected = this.printers[0]?.id;
    if (!this.joints.some((j) => j.id === this.joint.type)) this.joint = { type: 'none' };
    this.render();
  }

  jointSpec() { return this.joints.find((j) => j.id === this.joint.type) || { params: {} }; }

  /** Joint request = defaults overridden by the user's values. */
  jointRequest() { return { ...this.jointSpec().params, ...this.joint }; }

  setJoint(patch, resplit = true) {
    this.joint = patch.type && patch.type !== this.joint.type ? { type: patch.type } : { ...this.joint, ...patch };
    try { localStorage.setItem(LS_JOINT, JSON.stringify(this.joint)); } catch { /* ignore */ }
    if (this.pieces && resplit) {
      clearTimeout(this.resplitTimer);
      this.resplitTimer = setTimeout(() => this.split(), 250);
    } else this.render();
  }

  printer() { return this.printers.find((p) => p.id === this.selected); }

  /** A part with an exact model (a 3D model part's printing copy, a STEP file): its pieces are cut from it. */
  exactModel() {
    const m = this.getBody()?.model;
    return m?.kind === 'mesh' && /\.(step|stp)$/i.test(m.mesh_id || '') && !(m.extras || []).length;
  }

  /** Called after every model rebuild. */
  async refresh() {
    if (this.pieces) this.exitSplit(false);
    await this.check();
  }

  /** Fit check (same rules as the server's planner, computed locally for instant feedback). */
  async check() {
    const body = this.getBody();
    const p = this.printer();
    if (!body || !p || !body.solution) { this.plan = null; this.render(); return; }
    const s = UNIT_IN_MM[body.model.unit];
    // bent parts: use the bounding box of the bent shape
    const [x0, y0, x1, y1] = body.solution.bbox3 ? body.solution.bbox3.slice(0, 4) : body.solution.bbox;
    const [z0, z1] = body.solution.z_range || [0, body.solution.thickness];
    const size = [(x1 - x0) * s, (y1 - y0) * s, (z1 - z0) * s];
    const usable = [p.x - 2 * this.margin, p.y - 2 * this.margin, p.z];
    const flat = (size[0] <= usable[0] && size[1] <= usable[1]) || (size[1] <= usable[0] && size[0] <= usable[1]);
    const issues = [];
    if (size[2] > usable[2]) issues.push({ severity: 'error', message: `The part is ${size[2].toFixed(1)} mm tall but the ${p.name} can only print ${usable[2]} mm high.` });
    if (body.solution.bent) issues.push({ severity: 'info', message: 'The part is bent: curved parts usually need supports. You can also print it flat (hide the bends) and heat-bend it afterwards.' });
    if (z0 < -1e-9 && !body.solution.bent) issues.push({ severity: 'warning', message: 'The back face has embossed design, so the part will not lie flat on the bed — print face-up with supports, or move the design to the front.' });
    this.plan = { size_mm: size, usable_mm: usable, fits: flat && size[2] <= usable[2], issues };
    this.updateVolume();
    this.render();
  }

  updateVolume() {
    const p = this.printer();
    const body = this.getBody();
    if (!p || !body || !this.showVolume || !this.plan || this.plan.error) { this.viewer.setBuildVolume(null); return; }
    const s = 1 / UNIT_IN_MM[body.model.unit];
    this.viewer.setBuildVolume({ x: p.x * s, y: p.y * s, z: p.z * s, margin: this.margin * s, fits: this.plan.fits });
  }

  async split() {
    const body = this.getBody();
    if (!body) return;
    this.busy = true;
    this.render();
    const rid = newRid('p'), stop = trackProgress(rid, 'Splitting the part…', { delay: 300 });
    try {
      const { solution, ...req } = body;
      const wasShown = !!this.pieces;
      const plan = await (await this.api('/api/print/plan', { ...req, printer: this.selected, margin: this.margin, split: true, joint: this.jointRequest(), rid })).json();
      this.plan = { ...this.plan, issues: plan.issues };
      this.pieces = plan.pieces;
      this.connectors = plan.connectors || [];
      this.notes = plan.notes || [];
      const p = this.printer();
      const s = 1 / UNIT_IN_MM[body.model.unit];
      this.viewer.showPieces(plan.pieces, { x: (p.x - 2 * this.margin) * s, y: (p.y - 2 * this.margin) * s, z: p.z * s },
        this.connectors, plan.seams || []);
      if (!wasShown) this.viewer.setView('iso');
    } catch (e) { this.toast(e.message, /^cancelled/i.test(e.message) ? 'info' : 'error'); } finally { stop(); }
    this.busy = false;
    this.render();
  }

  exitSplit(render = true) {
    this.pieces = null;
    this.viewer.showPieces(null);
    this.updateVolume();
    if (render) { this.viewer.setView('iso'); this.render(); }
  }

  async exportPieces(fmt) {
    const { solution, ...body } = this.getBody();
    try {
      const res = await this.api(`/api/export/${fmt}`, { ...body, printer: this.selected, margin: this.margin, split: true, joint: this.jointRequest() });
      const base = (body.model.source || 'part').replace(/\.pdf$/i, '').replace(/[^\w-]+/g, '_');
      this.download(await res.blob(), `${base}_${fmt}_pieces.zip`);
      const extra = (this.connectors || []).reduce((n, g) => n + g.qty, 0);
      this.toast(`Exported ${this.pieces.length} pieces${extra ? ` + connector parts (${extra} to print)` : ''} as ${fmt.toUpperCase()} (mm) with an assembly sheet.`, 'ok', 6000);
    } catch (e) { this.toast(`Export failed: ${e.message}`, 'error'); }
  }

  async savePrinter(form) {
    const data = Object.fromEntries(new FormData(form));
    try {
      const saved = await (await this.api('/api/printers', data)).json();
      await this.load();
      this.selected = saved.id;
      this.persist();
      this.editing = false;
      this.toast(`Printer “${saved.name}” saved.`, 'ok');
      await this.check();
    } catch (e) { this.toast(e.message, 'error'); }
  }

  async deletePrinter() {
    const p = this.printer();
    if (!p || p.builtin || !confirm(`Delete printer “${p.name}”?`)) return;
    try {
      await this.api(`/api/printers/${encodeURIComponent(p.id)}`, null, 'DELETE');
      this.selected = null;
      await this.load();
      await this.check();
    } catch (e) { this.toast(e.message, 'error'); }
  }

  persist() { try { localStorage.setItem(LS_KEY, this.selected); } catch { /* ignore */ } }

  render() {
    const r = this.root;
    const p = this.printer();
    const plan = this.plan;
    const opts = this.printers.map((q) => `<option value="${q.id}" ${q.id === this.selected ? 'selected' : ''}>${esc(q.name)}${q.builtin ? '' : ' (custom)'}</option>`).join('');
    let status = '<div class="empty small">Load a drawing to check printability.</div>';
    if (plan?.error) status = `<div class="fit bad">${esc(plan.error)}</div>`;
    else if (plan && p) {
      const [w, h, z] = plan.size_mm;
      const [ux, uy] = plan.usable_mm;
      status = `
        <div class="fit ${plan.fits ? 'ok' : 'bad'}">
          <b>${plan.fits ? '✓ Fits on the build plate' : '✕ Does not fit in one piece'}</b>
          <div>Part: ${w.toFixed(1)} × ${h.toFixed(1)} × ${z.toFixed(1)} mm</div>
          <div>Usable plate: ${ux.toFixed(0)} × ${uy.toFixed(0)} × ${plan.usable_mm[2].toFixed(0)} mm</div>
        </div>
        ${plan.issues.map((i) => `<div class="fit-note ${i.severity}">${esc(i.message)}</div>`).join('')}`;
    }
    const piecesHtml = this.pieces ? `
      <div class="pieces">
        ${this.pieces.map((q) => `<div class="piece ${q.orientation === 'too big' ? 'bad' : ''}"><b>#${q.index}</b>
          ${q.size_mm[0].toFixed(1)} × ${q.size_mm[1].toFixed(1)} × ${q.size_mm[2].toFixed(1)} mm
          <span>${[q.orientation === 'rotated' ? 'rotate 90° on plate' : q.orientation === 'flat' ? '' : 'too big!', q.flip ? 'back face up' : '', q.exact ? 'exact' : ''].filter(Boolean).join(' · ')}</span></div>`).join('')}
        ${(this.connectors || []).map((g) => `<div class="piece connector"><b>${g.qty} ×</b> ${esc(g.name)}
          ${g.size_mm[0].toFixed(1)} × ${g.size_mm[1].toFixed(1)} × ${g.size_mm[2].toFixed(1)} mm<span>extra part</span></div>`).join('')}
      </div>
      ${(this.notes || []).map((n) => `<div class="fit-note">${esc(n)}</div>`).join('')}
      <div class="row-actions">
        <button class="btn small accent" data-a="exp-stl">Export pieces STL (.zip)</button>
        <button class="btn small" data-a="exp-step">STEP (.zip)</button>
      </div>
      <button class="btn small" data-a="back">← Back to whole model</button>` : '';

    const rolled = this.getBody()?.model?.rollback_note; // (⏮ a 3D model's printing copy made while its bar was up)
    r.innerHTML = `
      ${rolled ? `<div class="fit-note warning print-rb-note" data-no-i18n>${esc(rolled)}</div>` : ''}
      <div class="field"><label>Printer</label><select data-a="printer">${opts}</select></div>
      <div class="row-actions">
        <button class="btn small" data-a="new">+ New printer</button>
        ${p && !p.builtin ? '<button class="btn small" data-a="edit">Edit</button><button class="btn small" data-a="del">Delete</button>' : ''}
      </div>
      ${this.editing ? `
        <form class="printer-form">
          <input type="hidden" name="id" value="${this.editing === 'edit' ? esc(p.id) : ''}">
          <div class="field"><label>Name</label><input name="name" required value="${this.editing === 'edit' ? esc(p.name) : ''}" placeholder="e.g. Prusa MK4"></div>
          <div class="field three"><label>Volume (mm)</label>
            <input name="x" type="number" min="10" step="1" required placeholder="X" value="${this.editing === 'edit' ? p.x : ''}">
            <input name="y" type="number" min="10" step="1" required placeholder="Y" value="${this.editing === 'edit' ? p.y : ''}">
            <input name="z" type="number" min="10" step="1" required placeholder="Z" value="${this.editing === 'edit' ? p.z : ''}"></div>
          <div class="row-actions"><button type="button" class="btn small" data-a="cancel">Cancel</button><button class="btn small primary">Save printer</button></div>
        </form>` : ''}
      ${p ? `<p class="hint">Build volume ${p.x} × ${p.y} × ${p.z} mm</p>` : ''}
      <div class="field"><label>Bed margin (mm)</label><input type="number" min="0" step="1" data-a="margin" value="${this.margin}"></div>
      <label class="check"><input type="checkbox" data-a="vol" ${this.showVolume ? 'checked' : ''}> Show build volume in 3D</label>
      <h3>Fit check</h3>
      ${status}
      <h3>Joining split pieces</h3>
      <div class="field"><label>Joint</label><select data-a="joint">${this.joints.map((j) =>
        `<option value="${j.id}" ${j.id === this.joint.type ? 'selected' : ''}>${esc(j.name)}</option>`).join('')}</select></div>
      <p class="hint">${esc(JOINT_HELP[this.joint.type] || '')}</p>
      <div class="joint-params">${Object.entries(this.jointSpec().params).map(([k, def]) => {
        const v = this.joint[k] ?? def;
        const label = PARAM_LABELS[k] || k;
        if (typeof def === 'boolean') return `<label class="check"><input type="checkbox" data-jp="${k}" ${v ? 'checked' : ''}> ${label}</label>`;
        if (k === 'glue') return `<div class="field"><label>${label}</label><select data-jp="glue">${GLUE_OPTIONS.map(([val, txt]) => `<option value="${val}" ${v === val ? 'selected' : ''}>${txt}</option>`).join('')}</select></div>`;
        if ((k === 'groove' || k === 'port') && (this.joint.glue ?? this.jointSpec().params.glue) === 'none') return '';
        if (k === 'port' && (this.joint.glue ?? this.jointSpec().params.glue) !== 'ports') return '';
        if (k === 'face') return `<div class="field"><label>${label}</label><select data-jp="${k}"><option value="top" ${v === 'top' ? 'selected' : ''}>Front (top)</option><option value="bottom" ${v === 'bottom' ? 'selected' : ''}>Back (bottom)</option></select></div>`;
        return `<div class="field"><label>${label}</label><input type="number" step="${k === 'clearance' ? 0.05 : k === 'count' ? 1 : 0.5}" min="0" data-jp="${k}" value="${v}"></div>`;
      }).join('')}</div>
      ${plan && !plan.error && !this.pieces && this.exactModel() ? '<p class="hint exact-hint">The pieces are cut from the exact 3D model — curved walls stay smooth.</p>' : ''}
      ${plan && !plan.error && !this.pieces ? `<button class="btn ${plan.fits ? '' : 'primary'} split-btn" data-a="split" ${this.busy ? 'disabled' : ''}>${this.busy ? 'Splitting…' : plan.fits ? 'Split anyway' : 'Split to fit this printer'}</button>` : ''}
      ${piecesHtml}`;

    const on = (a, ev, fn) => r.querySelector(`[data-a="${a}"]`)?.addEventListener(ev, fn);
    on('printer', 'change', (e) => { this.selected = e.target.value; this.persist(); this.exitSplit(false); this.check(); });
    on('new', 'click', () => { this.editing = 'new'; this.render(); });
    on('edit', 'click', () => { this.editing = 'edit'; this.render(); });
    on('del', 'click', () => this.deletePrinter());
    on('cancel', 'click', () => { this.editing = false; this.render(); });
    on('margin', 'change', (e) => { this.margin = Math.max(0, parseFloat(e.target.value) || 0); this.exitSplit(false); this.check(); });
    on('vol', 'change', (e) => { this.showVolume = e.target.checked; this.updateVolume(); });
    on('split', 'click', () => this.split());
    on('joint', 'change', (e) => this.setJoint({ type: e.target.value }));
    r.querySelectorAll('[data-jp]').forEach((el) => el.addEventListener('change', () => {
      const k = el.dataset.jp;
      const v = el.type === 'checkbox' ? el.checked : el.tagName === 'SELECT' ? el.value : parseFloat(el.value);
      if (typeof v === 'number' && !Number.isFinite(v)) return;
      this.setJoint({ [k]: v });
    }));
    on('back', 'click', () => this.exitSplit());
    on('exp-stl', 'click', () => this.exportPieces('stl'));
    on('exp-step', 'click', () => this.exportPieces('step'));
    r.querySelector('.printer-form')?.addEventListener('submit', (e) => { e.preventDefault(); this.savePrinter(e.target); });
  }
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
