// Print panel: printer profiles (built-in + custom), build-volume fit check and split into pieces.
const UNIT_IN_MM = { mm: 1, cm: 10, m: 1000, in: 25.4 };
const LS_KEY = 'a3d.printer';

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
    try { this.selected = localStorage.getItem(LS_KEY); } catch { /* private mode */ }
  }

  async load() {
    this.printers = await (await this.api('/api/printers')).json();
    if (!this.printers.some((p) => p.id === this.selected)) this.selected = this.printers[0]?.id;
    this.render();
  }

  printer() { return this.printers.find((p) => p.id === this.selected); }

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
    const [x0, y0, x1, y1] = body.solution.bbox;
    const [z0, z1] = body.solution.z_range || [0, body.solution.thickness];
    const size = [(x1 - x0) * s, (y1 - y0) * s, (z1 - z0) * s];
    const usable = [p.x - 2 * this.margin, p.y - 2 * this.margin, p.z];
    const flat = (size[0] <= usable[0] && size[1] <= usable[1]) || (size[1] <= usable[0] && size[0] <= usable[1]);
    const issues = [];
    if (size[2] > usable[2]) issues.push({ severity: 'error', message: `The part is ${size[2].toFixed(1)} mm tall but the ${p.name} can only print ${usable[2]} mm high.` });
    if (z0 < -1e-9) issues.push({ severity: 'warning', message: 'The back face has embossed design, so the part will not lie flat on the bed — print face-up with supports, or move the design to the front.' });
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
    try {
      const { solution, ...req } = body;
      const plan = await (await this.api('/api/print/plan', { ...req, printer: this.selected, margin: this.margin, split: true })).json();
      this.plan = { ...this.plan, issues: plan.issues };
      this.pieces = plan.pieces;
      const p = this.printer();
      const s = 1 / UNIT_IN_MM[body.model.unit];
      this.viewer.showPieces(plan.pieces, { x: (p.x - 2 * this.margin) * s, y: (p.y - 2 * this.margin) * s, z: p.z * s });
      this.viewer.setView('iso');
    } catch (e) { this.toast(e.message, 'error'); }
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
      const res = await this.api(`/api/export/${fmt}`, { ...body, printer: this.selected, margin: this.margin, split: true });
      const base = (body.model.source || 'part').replace(/\.pdf$/i, '').replace(/[^\w-]+/g, '_');
      this.download(await res.blob(), `${base}_${fmt}_pieces.zip`);
      this.toast(`Exported ${this.pieces.length} ${fmt.toUpperCase()} pieces (mm) as a ZIP.`, 'ok');
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
          <span>${q.orientation === 'rotated' ? 'rotate 90° on plate' : q.orientation === 'flat' ? '' : 'too big!'}</span></div>`).join('')}
      </div>
      <div class="row-actions">
        <button class="btn small accent" data-a="exp-stl">Export pieces STL (.zip)</button>
        <button class="btn small" data-a="exp-step">STEP (.zip)</button>
      </div>
      <button class="btn small" data-a="back">← Back to whole model</button>` : '';

    r.innerHTML = `
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
    on('back', 'click', () => this.exitSplit());
    on('exp-stl', 'click', () => this.exportPieces('stl'));
    on('exp-step', 'click', () => this.exportPieces('step'));
    r.querySelector('.printer-form')?.addEventListener('submit', (e) => { e.preventDefault(); this.savePrinter(e.target); });
  }
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
