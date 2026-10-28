// The drawing sheet of a 3D model part (📄): its views (front, top, right, iso) on an A4 / A3 page with a title block,
// and dimensions — made automatically for a preset (light / medium / full, auto3d/modeler/sheet.py: holes alike once,
// "8× Ø3 H7", a row by its pitch), moved by dragging, deleted (Del; an automatic one can be brought back), and added by
// clicking two points or a circle. A value is always measured from the part, never typed. The sheet follows its part:
// when the part changes the views and dimensions are made again, the revision goes up and the title block says when.
// The PDF is the same SVG the editor shows (/api/sheet/pdf).
//
// Sheet JSON (a project part of kind "sheet"):
//   {source: "<part id>", preset: "light" | "medium" | "full", vpreset: {Top: "full"} (a view's own), paper: null | "A4" | "A3", views: {Front: [x, y]} (moved),
//    off: {Iso: true} (views not shown), dims: {<id>: {side, off, ang, len}} (automatic ones moved), hidden: [<ids>],
//    user: [<dimension>], texts: {title, number, drawn, note} (typed into the title block),
//    built: {geometry, layout, dims} (from the server), hash (of the part it was built from),
//    rev, created, changed}
import { History } from '../history.js';
import { t } from '../i18n.js';
import { HOLE_FITS, SHAFT_FITS, deviationText } from './fits.js';

const NS = 'http://www.w3.org/2000/svg';
const fmt = (v) => (+(+v).toFixed(2)).toString();
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const VIEWS = ['Front', 'Top', 'Right'];
const PRESETS = [['light', 'Light'], ['medium', 'Medium'], ['full', 'Full']];
const TEXTS = [['title', 'Title'], ['number', 'Drawing no.'], ['drawn', 'Drawn by'], ['note', 'Note']];
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');

/** 4 × 4 placement matrices (column-major, as three.js keeps them): a · b. */
const mul4 = (a, b) => { const o = new Array(16).fill(0); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]; return o; };
const ID4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const post = async (url, body) => { const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); const r = await res.json(); if (!res.ok) throw new Error(r.error || res.statusText); return r; };

/** A short hash of what a sheet is made from: the part's steps, material and tolerances. */
export function partHash(data) {
  const s = JSON.stringify({ f: data?.features || [], m: data?.material || '', t: data?.tolerance || '' });
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16);
}

export class SheetEditor {
  /** els: {left, viewport, right}; hooks: {toast, download, partData(id) -> the part's data now, partName(id), safeName(),
   *  onChange, openPart(id)} */
  constructor(els, hooks) {
    this.els = els;
    this.hooks = hooks;
    this.d = null;
    this.sel = null;     // the chosen dimension's id
    this.tool = 'select'; // or 'dim' (＋ Dimension)
    this.pick = null;    // the first point of a new dimension {view, key}
    this.zoom = { k: 1, x: 0, y: 0 };
    this.history = new History({
      capture: () => ({ section: !!this.d?.section, balloons: this.d?.balloons, views: this.d?.views, off: this.d?.off, dims: this.d?.dims, hidden: this.d?.hidden, user: this.d?.user, preset: this.d?.preset, vpreset: this.d?.vpreset, paper: this.d?.paper, texts: this.d?.texts, exploded: !!this.d?.exploded }),
      restore: (s) => { const ex = !!this.d.exploded, sec = !!this.d.section; Object.assign(this.d, structuredClone(s)); if (!this.d.exploded) delete this.d.exploded; if (!this.d.section) delete this.d.section; if (ex !== !!this.d.exploded || sec !== !!this.d.section || this.d.built?.preset !== this.d.preset || this.d.built?.vp !== JSON.stringify(this.d.vpreset || {})) this.ensure(true); else this.render(); },
      onChange: () => this.renderBar(),
    });
    this.build();
  }

  build() {
    const { left, viewport, right } = this.els;
    left.innerHTML = '<div class="mt-head"><b>Drawing</b><span class="mt-sub">its views and dimensions</span></div><div class="sh-left"></div>';
    viewport.innerHTML = '<div class="m-cmdbar sh-bar"></div><div class="m-hint sh-hint" hidden></div><div class="sh-stage"></div><div class="m-status sh-status"></div>';
    right.innerHTML = '<div class="mp-body sh-props"></div>';
    this.$ = (s) => viewport.querySelector(s) || left.querySelector(s) || right.querySelector(s);
    this.stage = this.$('.sh-stage');
    this.bind();
    window.addEventListener('keydown', (e) => this.key(e));
  }

  // ------------------------------------------------------------------ the sheet as a project part
  async load(data) {
    this.d = structuredClone(data || {});
    this.d.preset = this.d.preset || 'medium';
    this.d.views = this.d.views || {};
    this.d.off = this.d.off || {};
    this.d.dims = this.d.dims || {};
    this.d.hidden = this.d.hidden || [];
    this.d.user = this.d.user || [];
    this.d.rev = this.d.rev || 1;
    this.d.created = this.d.created || new Date().toISOString();
    this.d.changed = this.d.changed || this.d.created;
    this.sel = null;
    this.tool = 'select';
    this.pick = null;
    this.history.reset();
    this.render();
    await this.ensure();
    this.history.reset();
  }

  payload() { return structuredClone(this.d); }

  commit() { this.history.commit(); this.render(); this.hooks.onChange?.(); }

  /** Made from the part as it is now: built again when the part (or the preset) changed — then a new revision. */
  /** What a sheet is made from, as a hash: a part's steps; an assembly's placed parts and theirs (sub-assemblies too). */
  sourceHash(id, seen = new Set()) {
    const data = this.hooks.partData(id);
    if (!data) return null;
    if (this.hooks.kindOf?.(id) !== 'assembly') return partHash(data);
    seen.add(id);
    const inside = (data.instances || []).map((it) => [it.part, it.matrix, seen.has(it.part) ? '' : this.sourceHash(it.part, seen)]);
    return partHash({ features: inside });
  }

  async ensure(force = false) {
    const src = this.hooks.partData(this.d.source);
    if (!src) { this.render(); return; }
    const asm = this.hooks.kindOf?.(this.d.source) === 'assembly';
    const h = this.sourceHash(this.d.source);
    const vp = JSON.stringify(this.d.vpreset || {});
    if (!force && this.d.built && !this.d.built.stale && this.d.hash === h && !!this.d.built.section === !!this.d.section && this.d.built.preset === this.d.preset && this.d.built.vp === vp && (this.d.built.paper ?? null) === (this.d.paper ?? null)) return;
    this.busy = true;
    this.renderBar();
    try {
      let r;
      if (asm) { // an assembly: its views, overall sizes, parts list and balloons
        const pg = await this.assemblyPage(this.d.source, this.hooks.drawingCtx(), this.d.exploded ? 2 : 0);
        r = pg.built;
        this.d.asm = { rows: pg.rows };
        if (!this.d.asmLaid) { this.d.off = { ...this.d.off, Right: true }; this.d.views = { ...this.d.views, Iso: r.layout.views.Right }; this.d.asmLaid = true; }
      } else {
        const res = await fetch('/api/sheet/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: src, preset: this.d.preset, paper: this.d.paper, per_view: this.d.vpreset || {}, section: !!this.d.section }) });
        r = await res.json();
        if (!res.ok) throw new Error(r.error || res.statusText);
      }
      if (this.d.hash && this.d.hash !== h) { this.d.rev += 1; this.d.changed = new Date().toISOString(); } // the part changed
      Object.assign(this.d, { built: { ...r, preset: this.d.preset, vp, paper: this.d.paper ?? null, section: !!this.d.section && !asm }, hash: h });
      this.error = null;
    } catch (e) { this.error = e.message; }
    this.busy = false;
    this.render();
    this.hooks.onChange?.();
  }

  // ------------------------------------------------------------------ geometry on the paper
  get lay() { return this.d.built?.layout; }
  get geo() { return this.d.built?.geometry; }
  scale() { const s = this.lay?.scale || [1, 1]; return s[0] / s[1]; }

  /** A view's centre on the paper (moved by the user, else the layout's). */
  centre(v) { return this.d.views[v] || this.lay.views[v] || (v === 'Section' ? this.lay.views.Right : null); }

  /** The 2D views on the sheet: the shown ones of Front / Top / Right, and Section A–A when it is on. */
  drawn() { return [...VIEWS.filter((v) => !this.d.off[v]), ...(this.d.section && this.geo?.views.Section ? ['Section'] : [])]; }

  /** The hatching of a section's cut faces: 45° lines 2 mm apart (on the paper) inside the outlines (even-odd: holes
   *  left out) -> SVG lines. */
  hatchSvg(v, polys) {
    const P = polys.map((pl) => pl.map((q) => this.P(v, q))), rot = (q) => [(q[0] + q[1]) / Math.SQRT2, (q[1] - q[0]) / Math.SQRT2];
    const back = (u, w) => [(u - w) / Math.SQRT2, (u + w) / Math.SQRT2], R = P.map((pl) => pl.map(rot)), ws = R.flat().map((q) => q[1]);
    const out = [];
    for (let w = Math.ceil(Math.min(...ws) / 2) * 2; w <= Math.max(...ws); w += 2) {
      const xs = [];
      for (const pl of R) for (let i = 0; i < pl.length; i++) {
        const a = pl[i], b = pl[(i + 1) % pl.length];
        if ((a[1] <= w) !== (b[1] <= w)) xs.push(a[0] + (w - a[1]) / (b[1] - a[1]) * (b[0] - a[0]));
      }
      xs.sort((x, y) => x - y);
      for (let i = 0; i + 1 < xs.length; i += 2) {
        const A = back(xs[i], w), B = back(xs[i + 1], w);
        out.push(`<line x1="${A[0].toFixed(3)}" y1="${A[1].toFixed(3)}" x2="${B[0].toFixed(3)}" y2="${B[1].toFixed(3)}" stroke="#000" stroke-width="0.18"/>`);
      }
    }
    return out.join('');
  }

  /** A point of view v (part mm) -> the paper (mm). */
  P(v, p) {
    const g = this.geo.views[v], [cx, cy] = this.centre(v), s = this.scale(), b = g.box;
    return [cx + (p[0] - (b[0] + b[2]) / 2) * s, cy - (p[1] - (b[1] + b[3]) / 2) * s];
  }

  /** The view's box on the paper [x0, y0, x1, y1] (y down). */
  paperBox(v) {
    const b = this.geo.views[v].box, a = this.P(v, [b[0], b[3]]), c = this.P(v, [b[2], b[1]]);
    return [a[0], a[1], c[0], c[1]];
  }

  /** Every dimension shown: the automatic ones (not deleted; moved as the user moved them) and the user's. */
  allDims() {
    const hid = new Set(this.d.hidden);
    const auto = (this.d.built?.dims || []).filter((d) => !hid.has(d.id) && !this.d.off[d.view]).map((d) => ({ ...d, ...(this.d.dims[d.id] || {}), auto: true }));
    return [...auto, ...this.d.user.filter((d) => !this.d.off[d.view]).map((d) => ({ ...d, ...(this.d.dims[d.id] || {}) }))];
  }

  circleOf(v, key) { return this.geo.views[v]?.circles.find((c) => c.key === key) || null; }

  /** A dimension's value from the part, or null (its points are gone: the part changed). */
  /** An angle dimension's two edges as they meet: {X (where their lines cross), u1, u2 (from X along each, toward its
   *  far end), deg} in view coordinates, or null (an edge gone, or parallel). */
  angleOf(d) {
    const g = this.geo?.views[d.view], la = g?.lines.find((x) => x.key === d.a), lb = g?.lines.find((x) => x.key === d.b);
    if (!la || !lb) return null;
    const da = [la.b[0] - la.a[0], la.b[1] - la.a[1]], db = [lb.b[0] - lb.a[0], lb.b[1] - lb.a[1]], cr = da[0] * db[1] - da[1] * db[0];
    if (Math.abs(cr) < 1e-9 * Math.hypot(...da) * Math.hypot(...db)) return null;
    const s = ((lb.a[0] - la.a[0]) * db[1] - (lb.a[1] - la.a[1]) * db[0]) / cr, X = [la.a[0] + s * da[0], la.a[1] + s * da[1]];
    const away = (ln) => { // (toward the end farther from the corner)
      const far = Math.hypot(ln.a[0] - X[0], ln.a[1] - X[1]) > Math.hypot(ln.b[0] - X[0], ln.b[1] - X[1]) ? ln.a : ln.b, L = Math.hypot(far[0] - X[0], far[1] - X[1]) || 1;
      return [(far[0] - X[0]) / L, (far[1] - X[1]) / L];
    };
    const u1 = away(la), u2 = away(lb), deg = Math.acos(Math.max(-1, Math.min(1, u1[0] * u2[0] + u1[1] * u2[1]))) * 180 / Math.PI;
    return { X, u1, u2, deg, la, lb };
  }

  value(d) {
    const g = this.geo?.views[d.view];
    if (!g) return null;
    if (d.kind === 'ang') { const a = this.angleOf(d); return a ? +a.deg.toFixed(2) : null; }
    if (d.kind === 'dia' || d.kind === 'rad') { const c = this.circleOf(d.view, d.a); return c ? (d.kind === 'dia' ? 2 * c.r : c.r) : null; }
    const a = g.points[d.a], b = g.points[d.b];
    if (!a || !b) return null;
    return d.dir === 'h' ? Math.abs(b[0] - a[0]) : Math.abs(b[1] - a[1]);
  }

  dimText(d, v) {
    if (d.kind === 'dia') return `${d.count > 1 ? `${d.count}× ` : ''}${d.thread || `Ø${fmt(v)}`}${d.post || ''}`; // (a threaded hole: M5)
    if (d.kind === 'rad') return `${d.count > 1 ? `${d.count}× ` : ''}R${fmt(v)}`;
    if (d.kind === 'ang') return `${fmt(+v.toFixed(1))}°`;
    return `${d.pre || ''}${fmt(v)}`;
  }

  // ------------------------------------------------------------------ drawing (one SVG for the screen and the PDF)
  /** The sheet as SVG (mm). forPrint: no selection, no hover marks. */
  svg(forPrint = false) {
    const L = this.lay, G = this.geo;
    if (!L || !G) return '';
    const [pw, ph] = L.size, m = L.margin, th = L.title, s = this.scale();
    const out = [`<svg xmlns="${NS}" width="${pw}mm" height="${ph}mm" viewBox="0 0 ${pw} ${ph}" font-family="Helvetica">`,
      `<rect x="0" y="0" width="${pw}" height="${ph}" fill="#fff"/>`,
      `<rect x="${m}" y="${m}" width="${pw - 2 * m}" height="${ph - 2 * m}" fill="none" stroke="#000" stroke-width="0.5"/>`];
    const pl = (v, pts) => pts.map((p) => this.P(v, p).map((q) => q.toFixed(3)).join(',')).join(' ');
    for (const v of this.drawn()) {
      const g = G.views[v], pb = this.paperBox(v);
      out.push(`<g data-view="${v}" class="sh-view">`);
      if (!forPrint) out.push(`<rect x="${pb[0] - 2}" y="${pb[1] - 2}" width="${pb[2] - pb[0] + 4}" height="${pb[3] - pb[1] + 4}" fill="#fff" fill-opacity="0" stroke="none" class="sh-vhit"/>`);
      if (g.hatch) out.push(this.hatchSvg(v, g.hatch)); // (a section: its cut faces hatched)
      for (const p of g.hidden) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#666" stroke-width="0.25" stroke-dasharray="1.5 1"/>`);
      for (const p of g.visible) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#000" stroke-width="0.5" stroke-linejoin="round"/>`);
      // its name below the dimensions under it
      const below = Math.max(0, ...this.allDims().filter((d) => d.view === v && d.kind === 'linear' && d.dir === 'h' && d.side !== 't').map((d) => d.off ?? 8));
      out.push(`<text x="${(pb[0] + pb[2]) / 2}" y="${pb[3] + below + 8}" font-size="3.5" text-anchor="middle" fill="#334">${esc(v === 'Section' ? t('Section A–A') : t(v))}</text></g>`);
    }
    const cut = this.drawn().includes('Section') && this.drawn().includes('Front') && G.views.Section.cut;
    if (cut) { // where Section A–A is cut, on the front view: a dash-dot line, A at each end, arrows the way it is seen
      const [a, b] = cut.map((q) => this.P('Front', q)), top = a[1] < b[1] ? a : b, bot = a[1] < b[1] ? b : a;
      out.push(`<line x1="${top[0]}" y1="${top[1]}" x2="${bot[0]}" y2="${bot[1]}" stroke="#000" stroke-width="0.25" stroke-dasharray="6 1.2 1 1.2"/>`);
      for (const e of [top, bot]) {
        out.push(`<line x1="${e[0]}" y1="${e[1]}" x2="${e[0] - 4}" y2="${e[1]}" stroke="#000" stroke-width="0.35"/><path d="M${e[0] - 5},${e[1]} L${e[0] - 3},${e[1] - 0.8} L${e[0] - 3},${e[1] + 0.8} Z" fill="#000"/>`);
        out.push(`<text x="${e[0] + 1.5}" y="${e[1] + (e === top ? -1 : 3.5)}" font-size="3.5" fill="#000">A</text>`);
      }
    }
    if (!this.d.off.Iso && G.iso?.length) { // the iso view: fitted into its cell
      const pts = G.iso.flat(), xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const [cx, cy, size] = this.d.views.Iso ? [...this.d.views.Iso, L.iso[2]] : L.iso, k = size / Math.max(x1 - x0, y1 - y0, 1e-6);
      this.isoMap = { at: (q) => [cx + (q[0] - (x0 + x1) / 2) * k, cy - (q[1] - (y0 + y1) / 2) * k], c: [cx, cy] };
      out.push('<g data-view="Iso" class="sh-view">');
      if (!forPrint) out.push(`<rect x="${cx - (x1 - x0) * k / 2 - 2}" y="${cy - (y1 - y0) * k / 2 - 2}" width="${(x1 - x0) * k + 4}" height="${(y1 - y0) * k + 4}" fill="#fff" fill-opacity="0" class="sh-vhit"/>`);
      for (const p of G.iso) out.push(`<polyline points="${p.map((q) => `${(cx + (q[0] - (x0 + x1) / 2) * k).toFixed(3)},${(cy - (q[1] - (y0 + y1) / 2) * k).toFixed(3)}`).join(' ')}" fill="none" stroke="#333" stroke-width="0.3"/>`);
      out.push('</g>');
    }
    for (const d of this.allDims()) out.push(this.dimSvg(d, forPrint));
    if (this.d.asm) out.push(this.asmSvg(pw, ph, m, th));
    if (!forPrint && this.tool === 'dim') out.push(this.snapMarks());
    if (!forPrint && this.checked) for (const m of this.checked.missing) { // what is missing: an orange ?
      const q = this.P(m.view, m.at);
      out.push(`<g class="sh-miss"><circle cx="${q[0]}" cy="${q[1]}" r="2" fill="#f59e0b" opacity="0.85"/><text x="${q[0]}" y="${q[1] + 1.1}" font-size="2.8" text-anchor="middle" fill="#fff">?</text></g>`);
    }
    out.push(this.titleSvg(pw, ph, m, th, s));
    out.push('</svg>');
    return out.join('').replace(/<text /g, '<text font-family="Helvetica" '); // (the PDF's converter does not inherit a font)
  }

  /** One dimension: extension lines, the dimension line with arrows and its text (linear); a leader (Ø, R). */
  dimSvg(d, forPrint) {
    const v = this.value(d), lost = v === null, on = !forPrint && this.sel === d.id, same = !forPrint && !on && this.same?.has(d.id);
    const col = lost ? '#d97706' : on ? '#1f6feb' : same ? '#0f9d8a' : '#1b3a8a', sw = on || same ? 0.35 : 0.2, fs = 3.2;
    const arrow = (p, dir) => { // a filled arrowhead at p pointing along dir (unit)
      const [ux, uy] = dir, L = 2.2, W = 0.7;
      return `<path d="M${p[0]},${p[1]} L${p[0] - ux * L - uy * W},${p[1] - uy * L + ux * W} L${p[0] - ux * L + uy * W},${p[1] - uy * L - ux * W} Z" fill="${col}"/>`;
    };
    const g = [`<g data-dim="${d.id}" class="sh-dim${on ? ' on' : ''}${same ? ' same' : ''}">`];
    if (d.kind === 'ang') {
      const a = this.angleOf(d);
      if (!a) return '';
      const X = this.P(d.view, a.X), r = d.r ?? 15, s = this.scale();
      const pu = (u) => [u[0], -u[1]]; // (paper: y down)
      const U1 = pu(a.u1), U2 = pu(a.u2), at = (u, k) => [X[0] + u[0] * k, X[1] + u[1] * k];
      const sweep = U1[0] * U2[1] - U1[1] * U2[0] > 0 ? 1 : 0, A1 = at(U1, r), A2 = at(U2, r);
      g.push(`<path d="M${A1[0]},${A1[1]} A${r},${r} 0 0 ${sweep} ${A2[0]},${A2[1]}" fill="none" stroke="${col}" stroke-width="${sw}"/>`);
      const tan = (u, sgn) => [-u[1] * sgn, u[0] * sgn]; // (along the arc, out of it at that end)
      g.push(arrow(A1, tan(U1, sweep ? -1 : 1)), arrow(A2, tan(U2, sweep ? 1 : -1)));
      for (const [u, ln] of [[a.u1, a.la], [a.u2, a.lb]]) { // an edge that stops short of the arc (or starts past it): a line to it
        const k = [ln.a, ln.b].map((p) => ((p[0] - a.X[0]) * u[0] + (p[1] - a.X[1]) * u[1]) * s).sort((x, y) => x - y);
        const U = pu(u);
        if (r > k[1] + 0.5) g.push(`<line x1="${at(U, k[1] + 1)[0]}" y1="${at(U, k[1] + 1)[1]}" x2="${at(U, r + 1.5)[0]}" y2="${at(U, r + 1.5)[1]}" stroke="${col}" stroke-width="0.15"/>`);
        else if (r < k[0] - 0.5) g.push(`<line x1="${at(U, r - 1.5)[0]}" y1="${at(U, r - 1.5)[1]}" x2="${at(U, k[0] - 1)[0]}" y2="${at(U, k[0] - 1)[1]}" stroke="${col}" stroke-width="0.15"/>`);
      }
      const txt = esc(this.dimText(d, v)), mid = [U1[0] + U2[0], U1[1] + U2[1]], L = Math.hypot(...mid) || 1, m = [mid[0] / L, mid[1] / L];
      const T = at(m, r + 1.5 + Math.abs(m[0]) * txt.length * fs * 0.3 + Math.abs(m[1]) * fs * 0.6); // (clear of the arc, whichever way it points)
      g.push(`<text x="${T[0]}" y="${T[1] + 1.1}" font-size="${fs}" text-anchor="middle" fill="${col}">${txt}</text>`);
      if (!forPrint) g.push(`<rect x="${T[0] - txt.length * fs * 0.3 - 1}" y="${T[1] - fs + 0.6}" width="${txt.length * fs * 0.6 + 2}" height="${fs + 2}" fill="#fff" fill-opacity="0" class="sh-grab"/>`);
      g.push('</g>');
      return g.join('');
    }
    if (d.kind === 'dia' || d.kind === 'rad') {
      const c = this.circleOf(d.view, d.a);
      if (!c) return '';
      const C = this.P(d.view, c.c), R = c.r * this.scale();
      const ang = (d.kind === 'rad' ? Math.atan2(-(c.pm[1] - c.c[1]), c.pm[0] - c.c[0]) * 180 / Math.PI + (d.ang || 0) : d.ang ?? 45) * Math.PI / 180;
      const u = [Math.cos(ang), -Math.sin(ang)], on1 = [C[0] + u[0] * R, C[1] + u[1] * R], end = [C[0] + u[0] * (R + (d.len ?? 6)), C[1] + u[1] * (R + (d.len ?? 6))];
      const txt = esc(this.dimText(d, v)), right = u[0] >= 0, shelf = [end[0] + (right ? 1 : -1) * (txt.length * fs * 0.52 + 1), end[1]];
      g.push(`<polyline points="${on1.join(',')} ${end.join(',')} ${shelf.join(',')}" fill="none" stroke="${col}" stroke-width="${sw}"/>`, arrow(on1, [-u[0], -u[1]]));
      g.push(`<text x="${(end[0] + shelf[0]) / 2}" y="${end[1] - 0.8}" font-size="${fs}" text-anchor="middle" fill="${col}">${txt}</text>`);
      if (!forPrint) g.push(`<rect x="${Math.min(end[0], shelf[0])}" y="${end[1] - fs - 1}" width="${Math.abs(shelf[0] - end[0])}" height="${fs + 2}" fill="#fff" fill-opacity="0" class="sh-grab"/>`);
    } else {
      const gv = this.geo.views[d.view];
      const A = gv.points[d.a] ? this.P(d.view, gv.points[d.a]) : null, B = gv.points[d.b] ? this.P(d.view, gv.points[d.b]) : null;
      if (!A || !B) return '';
      const pb = this.paperBox(d.view), off = d.off ?? 8, txt = esc(this.dimText(d, v));
      if (d.dir === 'h') {
        const y = d.side === 't' ? pb[1] - off : pb[3] + off, sgn = d.side === 't' ? -1 : 1, x0 = Math.min(A[0], B[0]), x1 = Math.max(A[0], B[0]);
        for (const p of [A, B]) g.push(`<line x1="${p[0]}" y1="${p[1] + sgn * 1}" x2="${p[0]}" y2="${y + sgn * 1.5}" stroke="${col}" stroke-width="0.15"/>`);
        const out = x1 - x0 < 8; // a short one: the arrows from outside
        g.push(`<line x1="${out ? x0 - 5 : x0}" y1="${y}" x2="${out ? x1 + 5 : x1}" y2="${y}" stroke="${col}" stroke-width="${sw}"/>`, arrow([x0, y], out ? [1, 0] : [-1, 0]), arrow([x1, y], out ? [-1, 0] : [1, 0]));
        g.push(`<text x="${(x0 + x1) / 2}" y="${y - 0.9}" font-size="${fs}" text-anchor="middle" fill="${col}">${txt}</text>`);
        if (!forPrint) g.push(`<rect x="${x0 - 2}" y="${y - fs - 1.5}" width="${x1 - x0 + 4}" height="${fs + 3}" fill="#fff" fill-opacity="0" class="sh-grab"/>`);
      } else {
        const x = d.side === 'l' ? pb[0] - off : pb[2] + off, sgn = d.side === 'l' ? -1 : 1, y0 = Math.min(A[1], B[1]), y1 = Math.max(A[1], B[1]);
        for (const p of [A, B]) g.push(`<line x1="${p[0] + sgn * 1}" y1="${p[1]}" x2="${x + sgn * 1.5}" y2="${p[1]}" stroke="${col}" stroke-width="0.15"/>`);
        const out = y1 - y0 < 8;
        g.push(`<line x1="${x}" y1="${out ? y0 - 5 : y0}" x2="${x}" y2="${out ? y1 + 5 : y1}" stroke="${col}" stroke-width="${sw}"/>`, arrow([x, y0], out ? [0, 1] : [0, -1]), arrow([x, y1], out ? [0, -1] : [0, 1]));
        g.push(`<text x="${x - 0.9}" y="${(y0 + y1) / 2}" font-size="${fs}" text-anchor="middle" fill="${col}" transform="rotate(-90 ${x - 0.9} ${(y0 + y1) / 2})">${txt}</text>`);
        if (!forPrint) g.push(`<rect x="${x - fs - 1.5}" y="${y0 - 2}" width="${fs + 3}" height="${y1 - y0 + 4}" fill="#fff" fill-opacity="0" class="sh-grab"/>`);
      }
    }
    g.push('</g>');
    return g.join('');
  }

  /** ＋ Dimension: the points it can hang on (and the first one picked). */
  snapMarks() {
    const out = ['<g class="sh-snaps">'];
    for (const [e, col, w] of [[this.hoverEdge, '#f59e0b', 0.9], [this.pick?.edge ? this.pick : null, '#1f6feb', 1.1]]) {
      if (!e) continue;
      const a = this.P(e.view, e.edge.a), b = this.P(e.view, e.edge.b);
      out.push(`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${col}" stroke-width="${w}" stroke-linecap="round" opacity="0.8"/>`);
    }
    for (const v of this.drawn()) {
      for (const [k, p] of Object.entries(this.geo.views[v].points)) {
        if (k.startsWith('box#')) continue;
        const q = this.P(v, p), first = !this.pick?.edge && this.pick?.view === v && this.pick.key === k;
        out.push(`<circle cx="${q[0]}" cy="${q[1]}" r="${first ? 1.2 : 0.6}" fill="${first ? '#1f6feb' : '#f59e0b'}" opacity="${first ? 1 : 0.7}"/>`);
      }
    }
    return `${out.join('')}</g>`;
  }

  titleSvg(pw, ph, m, th, s) {
    const x0 = pw - m - 150, y0 = ph - m - th, src = this.hooks.partData(this.d.source) || {}, sc = this.lay.scale, T = this.d.title || {}, X = this.d.texts || {};
    const what = [T.kind || t('Part'), T.of ? `${t('in')} ${T.of}` : '', T.pos ? `${t('Pos.')} ${T.pos}` : ''].filter(Boolean).join(' · ');
    const cells = [
      [what, X.title || T.part || this.hooks.partName(this.d.source) || '—', 0, 0, 90, 12, 5, 'title'],
      [t('Material'), T.material ?? (src.material || 'PLA'), 90, 0, 60, 12, 3.6],
      [t('Scale'), `${sc[0]}:${sc[1]}`, 0, 12, 30, 9, 3.4],
      [t('Paper'), this.lay.paper, 30, 12, 30, 9, 3.4],
      [t('Tolerances'), src.tolerance ? `ISO 2768-${src.tolerance}` : '—', 60, 12, 90, 9, 3.4],
      [t('Created'), when(this.d.created), 0, 21, 50, 9, 3],
      [`${t('Changed')} · Rev`, `${when(this.d.changed)} · ${this.d.rev}`, 50, 21, 60, 9, 3],
      T.sheet ? [t('Sheet'), T.sheet, 110, 21, 40, 9, 3.4] : ['', 'Auto3DModeler · mm', 110, 21, 40, 9, 2.8],
      [t('Drawing no.'), X.number || '', 0, 30, 40, 8, 3.2, 'number'],
      [t('Drawn by'), X.drawn || '', 40, 30, 40, 8, 3.2, 'drawn'],
      [t('Note'), X.note || '', 80, 30, 70, 8, 2.9, 'note'],
    ];
    const g = [`<g class="sh-title"><rect x="${x0}" y="${y0}" width="150" height="${th}" fill="#fff" stroke="#000" stroke-width="0.5"/>`];
    for (const [k, v, x, y, w, h, fs, key] of cells) {
      g.push(`<rect x="${x0 + x}" y="${y0 + y}" width="${w}" height="${h}" fill="${key ? '#fff' : 'none'}" ${key ? 'fill-opacity="0"' : ''} stroke="#000" stroke-width="0.25"${key ? ` data-tcell="${key}" class="sh-tcell"` : ''}/>`);
      if (k) g.push(`<text x="${x0 + x + 1.2}" y="${y0 + y + 2.6}" font-size="2" fill="#555">${esc(k)}</text>`);
      g.push(`<text x="${x0 + x + 1.2}" y="${y0 + y + h - 1.8}" font-size="${fs}" fill="#000">${esc(v)}</text>`);
    }
    g.push('</g>');
    return g.join('');
  }

  /** An assembly's page: the parts list (pos, name, qty, material, part number) above the title block, and a balloon
   *  with its position for each in the iso view. */
  asmSvg(pw, ph, m, th) {
    const rows = this.d.asm.rows, max = Math.max(1, Math.floor((ph - 2 * m - th - 40) / 5) - 1), shown = rows.slice(0, max);
    const x0 = pw - m - 150, cols = [[t('Pos.'), 12], [t('Name'), 63], [t('Qty'), 12], [t('Material'), 25], [t('Part number'), 38]];
    const top = ph - m - th - (shown.length + 1 + (rows.length > max ? 1 : 0)) * 5, g = ['<g class="sh-bom">'];
    const row = (y, cells, head) => {
      let x = x0;
      cells.forEach((v, i) => {
        g.push(`<rect x="${x}" y="${y}" width="${cols[i][1]}" height="5" fill="${head ? '#eef1f6' : '#fff'}" stroke="#000" stroke-width="0.25"/>`);
        g.push(`<text x="${x + 1.2}" y="${y + 3.6}" font-size="${head ? 2.6 : 2.9}" fill="#000">${esc(String(v).slice(0, cols[i][1] > 30 ? 34 : 12))}</text>`);
        x += cols[i][1];
      });
    };
    row(top, cols.map((c) => c[0]), true);
    shown.forEach((r, i) => row(top + 5 * (i + 1), [r.pos, `${r.kind === 'assembly' ? '◇ ' : ''}${r.name}`, r.qty, r.material, r.pn || (r.bought ? t('bought') : '')], false));
    if (rows.length > max) g.push(`<text x="${x0 + 1.2}" y="${top + 5 * (shown.length + 1) + 3.6}" font-size="2.6">… ${rows.length - max} ${t('more')}</text>`);
    this.balloonAt = {};
    if (this.isoMap && !this.d.off.Iso) { // the balloons: out from the view, apart from each other, where the user put them
      const placed = [];
      for (const r of rows) {
        if (!r.iso) continue;
        const p = this.isoMap.at(r.iso), c = this.isoMap.c, L = Math.hypot(p[0] - c[0], p[1] - c[1]) || 1;
        let b = this.d.balloons?.[r.pos];
        if (!b) {
          let a = L > 1 ? Math.atan2(p[1] - c[1], p[0] - c[0]) : -Math.PI / 4;
          for (let k = 0; k < 14; k++) { // turned on until it is clear of the others
            b = [p[0] + Math.cos(a) * 18, p[1] + Math.sin(a) * 18];
            if (placed.every((q) => Math.hypot(q[0] - b[0], q[1] - b[1]) > 8.5)) break;
            a += (k % 2 ? -1 : 1) * 0.45 * (k + 1);
          }
        }
        placed.push(b);
        this.balloonAt[r.pos] = b.map((v) => +v.toFixed(1));
        const D = Math.hypot(b[0] - p[0], b[1] - p[1]) || 1, u = [(b[0] - p[0]) / D, (b[1] - p[1]) / D];
        g.push(`<line x1="${p[0]}" y1="${p[1]}" x2="${b[0] - u[0] * 3.4}" y2="${b[1] - u[1] * 3.4}" stroke="#1b3a8a" stroke-width="0.2"/><circle cx="${p[0]}" cy="${p[1]}" r="0.5" fill="#1b3a8a"/>`);
        g.push(`<g data-balloon="${r.pos}" class="sh-balloon"><circle cx="${b[0]}" cy="${b[1]}" r="3.4" fill="#fff" stroke="#1b3a8a" stroke-width="0.3"/><text x="${b[0]}" y="${b[1] + 1.2}" font-size="3.4" text-anchor="middle" fill="#1b3a8a">${r.pos}</text></g>`);
      }
    }
    g.push('</g>');
    return g.join('');
  }

  /** A sheet that is not on screen drawn (a page of a drawing set): its data with `built`. */
  svgOf(d) {
    const keep = this.d, at = this.balloonAt;
    this.d = { views: {}, off: {}, dims: {}, hidden: [], user: [], rev: 1, ...d };
    try { return this.svg(true); } finally { this.d = keep; this.isoMap = null; this.balloonAt = at; }
  }

  /** The drawing set of an assembly — its page (views, overall sizes, parts list, balloons), then each sub-assembly
   *  with its parts the same way, then its own made parts (their own sheet when they have one, with the user's
   *  dimensions; else made now) — every part once; bought and standard parts only in the lists.
   *  ctx: {kindOf(id), sheetOf(part id) -> a sheet's data or null, bought(data, name)} -> {svgs, pages: [names]}. */
  /** An assembly's page: its placed parts drawn together (views, overall sizes), its parts list (pos, name, qty,
   *  material, part number, bought) and where each one's balloon points -> {built, rows}. */
  /** One numbering of the parts for the whole drawing set from `root` (a part keeps its number on every page): the
   *  top assembly's parts first, then each sub-assembly's new ones, in the order of the pages -> Map(part id -> n). */
  itemNumbers(root) {
    const nums = new Map(), seen = new Set();
    const visit = (aid) => {
      if (seen.has(aid)) return;
      seen.add(aid);
      const parts = [...new Set((this.hooks.partData(aid)?.instances || []).map((it) => it.part))];
      for (const p of parts) if (!nums.has(p)) nums.set(p, nums.size + 1);
      for (const p of parts) if (this.hooks.kindOf?.(p) === 'assembly') visit(p);
    };
    visit(root);
    return nums;
  }

  async assemblyPage(aid, ctx, explode = 0) {
    const flatten = (id, M = ID4, pre = '') => (this.hooks.partData(id)?.instances || []).flatMap((it) => {
      const W = mul4(M, it.matrix || ID4), key = pre ? `${pre}/${it.id}` : it.id;
      if (ctx.kindOf(it.part) === 'assembly') return flatten(it.part, W, key);
      return [{ id: key, part: { features: this.hooks.partData(it.part)?.features || [] }, matrix: W }];
    });
    const insts = this.hooks.partData(aid)?.instances || [];
    if (!insts.length) throw new Error(t('The assembly has no parts to draw.'));
    const r = await post('/api/sheet/assembly', { instances: flatten(aid), explode }); // (explode: the iso view pulled apart)
    const groups = new Map();
    for (const it of insts) { if (!groups.has(it.part)) groups.set(it.part, []); groups.get(it.part).push(it.id); }
    const nums = this.itemNumbers(this.rootOf(aid) || aid); // (the set's numbers: the same part, the same number)
    const rows = [...groups].map(([part, ids], i) => {
      const pd = this.hooks.partData(part) || {}, kind = ctx.kindOf(part), nm = this.hooks.partName(part) || part;
      const iso = Object.entries(r.marks).filter(([k]) => k === ids[0] || k.startsWith(`${ids[0]}/`)).map(([, m]) => m.Iso); // (the first one of them: one balloon per item)
      return { pos: nums.get(part) ?? i + 1, part, name: nm, qty: ids.length, instances: ids, kind, material: kind === 'assembly' ? '—' : pd.material || 'PLA', pn: pd.library?.pn || '',
        bought: kind !== 'assembly' && (!!pd.library || ctx.bought(pd, nm)), iso: iso.length ? [iso.reduce((s, q) => s + q[0], 0) / iso.length, iso.reduce((s, q) => s + q[1], 0) / iso.length] : null };
    }).sort((a, b) => a.pos - b.pos);
    return { built: { ...r, preset: 'light' }, rows };
  }

  async drawingSet(rootId, ctx) {
    const pages = [], drawn = new Set([rootId]), name = (id) => this.hooks.partName(id) || id, now = new Date().toISOString();
    const visit = async (aid, parent) => {
      if (!(this.hooks.partData(aid)?.instances || []).length) return;
      const ex = ctx.sheetOf(aid)?.exploded ? 2 : 0; // (its own sheet's iso view exploded)
      const { built, rows } = await this.cached(`a|${aid}|${this.sourceHash(aid)}|${ex}|${[...this.itemNumbers(this.rootOf(aid) || aid)].join()}`, () => this.assemblyPage(aid, ctx, ex)), own = ctx.sheetOf(aid); // its own sheet: the user's moves, dimensions, texts
      const base = own ? structuredClone(own) : { created: now, changed: now, off: { Right: true }, views: { Iso: built.layout.views.Right } };
      pages.push({ name: name(aid), d: { ...base, source: aid, built, asm: { rows },
        title: { kind: parent ? t('Sub-assembly') : t('Assembly'), part: name(aid), material: '—', of: parent || '' } } });
      for (const row of rows) if (row.kind === 'assembly' && !drawn.has(row.part)) { drawn.add(row.part); await visit(row.part, name(aid)); }
      for (const row of rows) {
        if (row.kind !== 'model' || row.bought || drawn.has(row.part)) continue;
        drawn.add(row.part);
        pages.push({ name: row.name, part: row.part, parent: name(aid), pos: row.pos });
      }
    };
    await visit(rootId, null);
    if (!pages.length) throw new Error(t('The assembly has no parts to draw.'));
    for (const pg of pages) {
      if (!pg.part) continue;
      const src = this.hooks.partData(pg.part), own = ctx.sheetOf(pg.part);
      const d = own ? structuredClone(own) : { source: pg.part, preset: 'medium', rev: 1, created: now, changed: now };
      if (!d.built || d.built.stale || d.hash !== partHash(src)) {
        const key = `p|${pg.part}|${partHash(src)}|${d.preset || 'medium'}|${d.paper || ''}|${JSON.stringify(d.vpreset || {})}`;
        d.built = { ...(await this.cached(key, () => post('/api/sheet/build', { part: src, preset: d.preset || 'medium', paper: d.paper, per_view: d.vpreset || {} }))), preset: d.preset || 'medium', paper: d.paper ?? null };
      }
      pg.d = { ...d, title: { part: pg.name, of: pg.parent, pos: pg.pos } };
    }
    const n = pages.length;
    const svgs = pages.map((pg, i) => this.svgOf({ ...pg.d, title: { ...pg.d.title, sheet: `${i + 1} / ${n}` } }));
    return { svgs, ids: pages.map((pg) => pg.part || pg.d.source), pages: pages.map((pg) => (pg.part ? pg.name : `◇ ${pg.name}`)) };
  }

  /** A server build kept by its key (what it was made from), the last 40. */
  async cached(key, make) {
    this.cache = this.cache || new Map();
    if (!this.cache.has(key)) {
      this.cache.set(key, await make());
      if (this.cache.size > 40) this.cache.delete(this.cache.keys().next().value);
    }
    return structuredClone(this.cache.get(key));
  }

  // ------------------------------------------------------------------ the screen
  /** The dimensions giving the same size as `id` in the other views: a distance along the same direction of the part
   *  between the same places, a Ø / R of the same size -> Set of ids. */
  sameAs(id) {
    const all = this.allDims(), d = all.find((x) => x.id === id), views = this.geo?.views;
    if (!d || !views) return new Set();
    const sig = (x) => {
      const g = views[x.view];
      if (!g) return null;
      if (x.kind === 'dia' || x.kind === 'rad') { const v = this.value(x); return v === null ? null : { round: x.kind, v }; }
      const a = g.points[x.a], b = g.points[x.b], axis = x.dir === 'h' ? g.right : g.up;
      if (!a || !b || !axis) return null;
      const k = x.dir === 'h' ? 0 : 1;
      return { axis, at: [a[k], b[k]] };
    };
    const me = sig(d), out = new Set();
    if (!me) return out;
    const near = (p, q) => Math.abs(p - q) < 0.02;
    for (const x of all) {
      if (x.id === d.id || x.view === d.view) continue;
      const s = sig(x);
      if (!s) continue;
      if (me.round) { if (s.round === me.round && near(s.v, me.v)) out.add(x.id); continue; }
      if (s.round) continue;
      const dot = me.axis[0] * s.axis[0] + me.axis[1] * s.axis[1] + me.axis[2] * s.axis[2];
      if (Math.abs(Math.abs(dot) - 1) > 1e-6) continue; // another direction of the part
      const sg = Math.sign(dot), p = [...me.at].sort((u, w) => u - w), q = s.at.map((u) => sg * u).sort((u, w) => u - w);
      if (near(p[0], q[0]) && near(p[1], q[1])) out.add(x.id);
    }
    return out;
  }

  render() {
    this.same = this.sel && this.geo ? this.sameAs(this.sel) : null; // (shown with the chosen one)
    this.checked = this.d && this.geo && !this.d.asm ? this.check() : null; // (the panels show it; an assembly's sheet has no size check)
    this.renderBar();
    this.renderLeft();
    this.renderProps();
    if (!this.d) return;
    if (this.setMode) { this.renderSet(); return; }
    this.stage.classList.remove('sh-set');
    if (!this.geo) {
      this.stage.innerHTML = `<p class="hint sh-empty">${esc(this.error ? tv('The drawing could not be made: {e}', { e: this.error }) : this.hooks.partData(this.d.source) ? t('Making the drawing…') : t('Its part is not in the project any more.'))}</p>`;
      return;
    }
    this.stage.innerHTML = this.svg(false);
    const svg = this.stage.querySelector('svg');
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.setAttribute('data-no-i18n', '');
    this.svgEl = svg;
    this.applyZoom();
    const lost = this.allDims().filter((d) => this.value(d) === null).length;
    this.$('.sh-status').textContent = `${this.allDims().length} ${t('dimension(s)')}${lost ? ` · ⚠ ${lost} ${t('lost their points')}` : ''} · Rev ${this.d.rev}`;
  }

  applyZoom() {
    if (!this.svgEl) return;
    const { k, x, y } = this.zoom;
    this.svgEl.style.transform = `translate(${x}px, ${y}px) scale(${k})`;
  }

  renderBar() {
    const bar = this.$('.sh-bar');
    if (!bar || !this.d) return;
    bar.innerHTML = `${this.d.asm ? `<span class="sh-asm">◇ ${esc(t('Assembly drawing'))}</span>` : `<div class="seg sh-presets" title="How many dimensions it makes by itself">${PRESETS.map(([k, l]) => `<button class="chip ${this.d.preset === k ? 'on' : ''}" data-preset="${k}">${t(l)}</button>`).join('')}</div>`}
      <button class="chip tool ${this.tool === 'dim' ? 'on' : ''}" data-a="dim" title="Add a dimension: an edge (twice: its length), two edges (their distance, or their angle), two points, or a circle / arc (Ø / R) — its value is measured from the part">＋ Dimension</button>
      ${this.rootOf(this.d.source) ? `<button class="chip ${this.setMode ? 'on' : ''}" data-a="setview" title="${esc(t('All the pages of the drawing set, one below the other — scroll through them; double-click a page to edit it'))}">📚 ${esc(t('All pages'))}</button>` : ''}
      <span class="sep"></span><button class="chip" data-a="undo" title="Undo (Ctrl+Z)" ${this.history.canUndo() ? '' : 'disabled'}>↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)" ${this.history.canRedo?.() ? '' : 'disabled'}>↷</button>
      <span class="sep"></span><button class="chip" data-a="fit" title="The whole sheet">⤢ Fit</button>
      <button class="chip primary" data-a="pdf" title="The sheet as a PDF — as you see it">⬇ PDF</button>${this.busy ? `<span class="sh-busy">${t('Making the drawing…')}</span>` : ''}`;
    for (const b of bar.querySelectorAll('[data-preset]')) b.addEventListener('click', () => this.setPreset(b.dataset.preset));
    for (const b of bar.querySelectorAll('[data-a]')) b.addEventListener('click', () => this.action(b.dataset.a));
  }

  renderLeft() {
    const box = this.$('.sh-left');
    if (!box || !this.d) return;
    const all = this.allDims(), hid = this.d.hidden.length, ck = this.checked || { missing: [], dup: new Set(), over: new Set(), ok: true };
    const vp = this.d.vpreset || {}, per = (v) => ck.missing.filter((m) => m.view === v).length;
    box.innerHTML = `<h3>Views</h3><div class="sh-views">${[...VIEWS, 'Iso'].map((v) => `<div class="sh-vrow"><label class="check"><input type="checkbox" data-v="${v}" ${this.d.off[v] ? '' : 'checked'}> ${esc(t(v))}${v === 'Iso' || this.d.off[v] ? '' : per(v) ? ` <b class="sh-vbad" title="${esc(t('Sizes missing in this view'))}">⚠ ${per(v)}</b>` : ' <b class="sh-vok">✓</b>'}</label>
        ${v === 'Iso' || this.d.asm ? '' : `<select data-vp="${v}" title="${esc(t('How many dimensions in this view — as the sheet, or its own'))}"><option value="">${esc(t('as the sheet'))}</option>${PRESETS.map(([k, l]) => `<option value="${k}" ${vp[v] === k ? 'selected' : ''}>${esc(t(l))}</option>`).join('')}<option value="all" ${vp[v] === 'all' ? 'selected' : ''} title="${esc(t('Every size this view shows, also the ones given in another view'))}">${esc(t('All its sizes'))}</option></select>`}</div>`).join('')}</div>
      ${this.d.asm ? '' : `<label class="check sh-secrow" title="${esc(t('The part cut through its middle (across X) and seen from the right, the cut hatched — in the right view\'s place; the cut marked A–A on the front view'))}"><input type="checkbox" data-sec ${this.d.section ? 'checked' : ''}> ${esc(t('Section A–A'))}</label>`}
      ${this.d.asm ? `<p class="hint">${esc(t('An assembly drawing: its views, overall sizes and parts list — each part has its own drawing for its sizes.'))}</p>` : ''}
      <h3 ${this.d.asm ? 'hidden' : ''}>Check</h3>${this.d.asm ? '' : ck.ok && !ck.over.size ? `<p class="mp-count sh-ok">✓ ${esc(t('Fully dimensioned — every place and size is given once.'))}</p>` : ''}
      ${ck.missing.length ? `<p class="hint">${esc(tv('{n} size(s) missing (orange ? on the drawing):', { n: ck.missing.length }))}</p><div class="sh-miss-list">${ck.missing.slice(0, 40).map((m, i) => `<div class="sh-mrow">
        <span data-no-i18n>${esc(t(m.view))}: ${esc(m.what)}${m.ax ? ` <i>${m.ax}</i>` : ''}</span><button class="mini" data-miss="${i}" title="${esc(t('Add it (from the part\'s edge)'))}">＋</button></div>`).join('')}</div>
        <div class="row-actions"><button class="btn small" data-a="allMissing">＋ ${esc(t('Add all missing'))}</button></div>` : ''}
      ${ck.dup.size || ck.over.size ? `<p class="hint">${esc(tv('{n} dimension(s) give a size twice (marked ⧉ below).', { n: ck.dup.size + ck.over.size }))}</p>
        <div class="row-actions"><button class="btn small" data-a="dropTwice">✕ ${esc(t('Remove them'))}</button></div>` : ''}
      ${this.pagesHtml()}
      <h3>Dimensions</h3><div class="sh-dlist">${all.map((d) => { const v = this.value(d), twice = ck.dup.has(d.id) || ck.over.has(d.id); return `<div class="sh-drow ${this.sel === d.id ? 'on' : ''} ${v === null || twice ? 'bad' : ''}" data-d="${d.id}">
        <span data-no-i18n>${twice ? '⧉ ' : ''}${d.kind === 'linear' ? (d.dir === 'h' ? '↔ ' : '↕ ') : d.kind === 'ang' ? '∠ ' : ''}${esc(v === null ? '⚠ ?' : this.dimText(d, v))}</span><i>${esc(t(d.view))}${d.auto ? '' : ' · ✎'}</i><button class="mini danger" data-x="${d.id}" title="Delete it">✕</button></div>`; }).join('') || '<p class="hint">None.</p>'}</div>
      ${hid ? `<div class="row-actions"><button class="btn small" data-a="unhide">↺ ${esc(tv('Bring back deleted ones ({n})', { n: hid }))}</button></div>` : ''}`;
    box.querySelector('[data-sec]')?.addEventListener('change', (e) => { // Section A–A: in the Right view's place (the Right view hidden)
      if (e.target.checked) { this.d.section = true; this.d.off = { ...this.d.off, Right: true }; } else delete this.d.section;
      this.history.commit();
      this.ensure(true);
    });
    for (const el of box.querySelectorAll('[data-v]')) {
      el.addEventListener('change', () => { if (el.checked) delete this.d.off[el.dataset.v]; else this.d.off[el.dataset.v] = true; this.commit(); });
    }
    for (const el of box.querySelectorAll('[data-vp]')) {
      el.addEventListener('change', () => { const vpr = { ...(this.d.vpreset || {}) }; if (el.value) vpr[el.dataset.vp] = el.value; else delete vpr[el.dataset.vp]; this.d.vpreset = vpr; this.history.commit(); this.ensure(true); });
    }
    for (const row of box.querySelectorAll('[data-d]')) row.addEventListener('click', (e) => { if (!e.target.closest('[data-x]')) { this.sel = row.dataset.d; this.render(); } });
    for (const b of box.querySelectorAll('[data-x]')) b.addEventListener('click', () => this.remove(b.dataset.x));
    box.querySelector('[data-a=unhide]')?.addEventListener('click', () => { this.d.hidden = []; this.commit(); });
    for (const b of box.querySelectorAll('[data-page]')) {
      b.addEventListener('click', () => {
        if (this.setMode) { this.stage.querySelector(`[data-pageid="${b.dataset.page}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
        if (b.dataset.page !== this.d.source) this.hooks.openSheet?.(b.dataset.page);
      });
    }
    for (const b of box.querySelectorAll('[data-miss]')) b.addEventListener('click', () => this.addMissing(ck.missing[+b.dataset.miss]));
    box.querySelector('[data-a=allMissing]')?.addEventListener('click', () => this.addAllMissing());
    box.querySelector('[data-a=dropTwice]')?.addEventListener('click', () => { for (const id of [...ck.dup, ...ck.over]) this.remove(id); });
  }

  /** ＋ every missing size (one by one: each new one may give others, e.g. a row's pitch). */
  addAllMissing(limit = 60) {
    let n = 0;
    for (let ck = this.check(); ck?.missing.length && n < limit; ck = this.check(), n++) this.addMissing(ck.missing[0]);
    return n;
  }

  renderProps() {
    const box = this.$('.sh-props');
    if (!box || !this.d) return;
    const d = this.sel && this.allDims().find((x) => x.id === this.sel), name = this.hooks.partName(this.d.source);
    box.innerHTML = `<h2>📄 ${esc(t('Drawing'))}</h2>
      <p class="hint">${esc(tv('Of {part} — it follows the part: change the part, the drawing is made again (a new revision).', { part: name || '?' }))}</p>
      <div class="mp-facts"><span>Rev</span><b data-no-i18n>${this.d.rev}</b><span>${esc(t('Changed'))}</span><b data-no-i18n>${esc(when(this.d.changed))}</b><span>${esc(t('Created'))}</span><b data-no-i18n>${esc(when(this.d.created))}</b></div>
      ${d ? '' : `<h3>${esc(t('Title block'))}</h3>${TEXTS.map(([k, l]) => `<div class="field"><label>${esc(t(l))}</label><input type="text" data-text="${k}" value="${esc(this.d.texts?.[k] || '')}" placeholder="${esc(k === 'title' ? this.hooks.partName(this.d.source) || '' : '')}"></div>`).join('')}`}
      ${this.d.asm ? `<label class="check"><input type="checkbox" data-k="exploded" ${this.d.exploded ? 'checked' : ''}> ${esc(t('Iso view exploded'))}</label>` : ''}
      <div class="field"><label>Paper</label><select data-k="paper">${[['', 'Auto'], ['A4', 'A4'], ['A3', 'A3']].map(([v, l]) => `<option value="${v}" ${(this.d.paper || '') === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      ${d ? `<h3>${esc(t('Dimension'))}</h3><p class="mp-count" data-no-i18n>${esc(this.value(d) === null ? '⚠ ?' : this.dimText(d, this.value(d)))}</p>
        <p class="hint">${esc(d.auto ? t('Made by the preset. Drag it to move it; Delete removes it (↺ brings it back).') : t('Your own. Drag it to move it; Delete removes it.'))}</p>
        ${this.value(d) === null ? `<p class="mp-bad">${esc(t('Its points are gone — the part changed. Delete it and add it again.'))}</p>` : ''}
        ${d.kind === 'dia' && !d.thread ? this.fitField(d) : ''}
        <div class="row-actions"><button class="btn small danger" data-a="del">✕ ${esc(t('Delete'))}</button></div>`
        : `<p class="hint">${esc(t('Drag a dimension or a view to move it. ＋ Dimension: click two points, or a circle. The values come from the part.'))}</p>`}
      ${name ? `<div class="row-actions"><button class="btn small" data-a="part">◆ ${esc(tv('Open {part}', { part: name }))}</button></div>` : ''}`;
    for (const el of box.querySelectorAll('[data-text]')) {
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => { const x = { ...(this.d.texts || {}) }; if (el.value.trim()) x[el.dataset.text] = el.value.trim(); else delete x[el.dataset.text]; this.d.texts = x; this.commit(); });
    }
    box.querySelector('[data-k=exploded]')?.addEventListener('change', (e) => { // (the parts pulled apart in the iso view, balloons on them)
      if (e.target.checked) this.d.exploded = true; else delete this.d.exploded;
      delete this.d.balloons;
      this.history.commit();
      this.ensure(true);
    });
    box.querySelector('[data-k=paper]').addEventListener('change', (e) => { this.d.paper = e.target.value || null; this.d.views = {}; this.history.commit(); this.ensure(true); });
    box.querySelector('[data-a=del]')?.addEventListener('click', () => this.remove(this.sel));
    box.querySelector('[data-k=fit]')?.addEventListener('change', (e) => { this.setFit(d.id, e.target.value); this.renderProps(); });
    box.querySelector('[data-a=part]')?.addEventListener('click', () => this.hooks.openPart?.(this.d.source));
  }

  /** A Ø dimension's fit (ISO 286): holes H6 … H9, shafts (a pin, a boss, an axle) f7 … p6 — with its deviations. */
  fitField(d) {
    const now = (d.post || '').trim(), v = this.value(d), dev = now && v ? deviationText(now, v) : '';
    const opt = (f) => `<option value="${f}" ${f === now ? 'selected' : ''}>${f}</option>`;
    return `<div class="field"><label>Fit</label><select data-k="fit" title="${esc(t('An ISO 286 fit: H for a hole, a small letter for a shaft (h6 a sliding fit, k6 / m6 a push fit, p6 a press fit)'))}">
      <option value="">—</option><optgroup label="${esc(t('Hole'))}">${HOLE_FITS.map(opt).join('')}</optgroup><optgroup label="${esc(t('Shaft'))}">${SHAFT_FITS.map(opt).join('')}</optgroup></select></div>
      ${dev ? `<p class="hint" data-no-i18n>${esc(`${now}: ${dev} mm`)}</p>` : ''}`;
  }

  /** Set (or with '': take off) the fit of Ø dimension `id` — drawn after its size (Ø8 h6). */
  setFit(id, fit) {
    if (fit && !HOLE_FITS.includes(fit) && !SHAFT_FITS.includes(fit)) throw new Error(`fit: one of ${[...HOLE_FITS, ...SHAFT_FITS].join(', ')}.`);
    const d = this.allDims().find((x) => x.id === id);
    if (!d || d.kind !== 'dia') throw new Error(`${id} is not a Ø dimension — get_sheet lists them.`);
    const u = this.d.user.find((x) => x.id === id);
    if (u) u.post = fit ? ` ${fit}` : '';
    else this.d.dims = { ...this.d.dims, [id]: { ...(this.d.dims[id] || {}), post: fit ? ` ${fit}` : '' } };
    this.commit();
  }

  // ------------------------------------------------------------------ is it fully dimensioned?
  /** The part's sizes as a reader of the drawing finds them. On each axis of the part (x: across in the front and top;
   *  y: up in the top, across in the right; z: up in the front and right) every place that needs one — a circle's
   *  centre, a straight edge, the far end — must be linked by dimensions to the part's lowest place there (a pitch
   *  "4× 10" links its whole row); every circle needs its Ø, every arc its R. -> {missing: [{view, dir, at, key, what}],
   *  dup: Set (the same distance twice), over: Set (a distance the others give already), ok}. */
  check() {
    const G = this.geo;
    if (!G) return null;
    const AX = { Front: ['x', 'z'], Top: ['x', 'y'], Right: ['y', 'z'] }, r2 = (v) => Math.round(v * 100) / 100;
    const uf = { x: new Map(), y: new Map(), z: new Map() };
    const find = (ax, v) => { const m = uf[ax]; let k = String(r2(v)); while (m.has(k) && m.get(k) !== k) k = m.get(k); if (!m.has(k)) m.set(k, k); return k; };
    const join = (ax, a, b) => { const p = find(ax, a), q = find(ax, b); if (p === q) return false; uf[ax].set(p, q); return true; };
    const shown = VIEWS.filter((v) => !this.d.off[v]), dims = this.allDims(), seen = new Map(), dup = new Set(), over = new Set();
    for (const d of dims) {
      if (d.kind !== 'linear' || this.value(d) === null || !shown.includes(d.view)) continue;
      if ((this.d.vpreset || {})[d.view] === 'all') continue; // (a view with all its sizes repeats them on purpose)
      const g = G.views[d.view], k = d.dir === 'h' ? 0 : 1, ax = AX[d.view][k], a = r2(g.points[d.a][k]), b = r2(g.points[d.b][k]);
      const sig = `${ax}:${Math.min(a, b)}:${Math.max(a, b)}`;
      if (seen.has(sig)) { dup.add(d.id); continue; }
      seen.set(sig, d.id);
      if (!join(ax, a, b)) over.add(d.id);
      const n = parseInt(d.pre, 10);
      if (n > 1) for (let i = 1; i < n; i++) join(ax, r2(a + i * (b - a)), r2(a + (i + 1) * (b - a))); // the rest of the row
    }
    const fullR = new Set(dims.filter((d) => d.kind === 'dia' && this.value(d) !== null).map((d) => r2(this.value(d) / 2)));
    const arcR = new Set(dims.filter((d) => d.kind === 'rad' && this.value(d) !== null).map((d) => r2(this.value(d))));
    // a circle of a known size: its edges are where its centre is ± its radius (a tangent edge, a boss's side)
    for (const v of shown) {
      for (const c of G.views[v].circles) {
        if (!(c.full ? fullR : arcR).has(r2(c.r))) continue;
        for (const k of [0, 1]) { join(AX[v][k], c.c[k], c.c[k] + c.r); join(AX[v][k], c.c[k], c.c[k] - c.r); }
      }
    }
    const lowest = { x: G.views.Front.box[0], y: G.views.Top.box[1], z: G.views.Front.box[1] };
    const missing = [], told = new Set();
    const need = (v, k, value, key, at, what) => {
      const ax = AX[v][k], id = `${ax}:${r2(value)}`;
      if (told.has(id) || find(ax, value) === find(ax, lowest[ax])) return;
      told.add(id);
      missing.push({ view: v, dir: k ? 'v' : 'h', at, key, what, ax });
    };

    const diaTold = new Set();
    for (const v of shown) {
      const g = G.views[v];
      for (const c of g.circles) {
        if (c.full) {
          for (const k of [0, 1]) need(v, k, c.c[k], `${c.key}#c`, c.c, `Ø${fmt(2 * c.r)}`);
          if (!fullR.has(r2(c.r)) && !diaTold.has(`d${r2(c.r)}`)) { diaTold.add(`d${r2(c.r)}`); missing.push({ view: v, kind: 'dia', key: c.key, at: c.pm, what: `Ø${fmt(2 * c.r)}` }); }
        } else if (!arcR.has(r2(c.r)) && !diaTold.has(`r${r2(c.r)}`)) { diaTold.add(`r${r2(c.r)}`); missing.push({ view: v, kind: 'rad', key: c.key, at: c.pm, what: `R${fmt(c.r)}` }); }
      }
      for (const ln of g.lines) {
        if (ln.key.includes(':round:')) continue; // where a rounding begins: its R gives it
        if (Math.abs(ln.a[0] - ln.b[0]) < 1e-3) need(v, 0, ln.a[0], `${ln.key}#0`, [(ln.a[0] + ln.b[0]) / 2, (ln.a[1] + ln.b[1]) / 2], t('an edge'));
        if (Math.abs(ln.a[1] - ln.b[1]) < 1e-3) need(v, 1, ln.a[1], `${ln.key}#0`, [(ln.a[0] + ln.b[0]) / 2, (ln.a[1] + ln.b[1]) / 2], t('an edge'));
      }
      need(v, 0, g.box[2], 'box#x1', [g.box[2], g.box[1]], t('the far end'));
      need(v, 1, g.box[3], 'box#y1', [g.box[2], g.box[3]], t('the top'));
    }
    return { missing, dup, over, ok: !missing.length && !dup.size };
  }

  /** The pages of a drawing set from an assembly down (the assembly, each sub-assembly then its parts, its own made
   *  parts; each once; bought ones not) -> [{id, name, kind, depth}]. */
  pagesOf(rootId) {
    const ctx = this.hooks.drawingCtx?.();
    if (!ctx) return [];
    const out = [], seen = new Set([rootId]);
    const visit = (aid, depth) => {
      out.push({ id: aid, name: this.hooks.partName(aid) || aid, kind: 'assembly', depth });
      const ids = [...new Set((this.hooks.partData(aid)?.instances || []).map((it) => it.part))];
      for (const id of ids) if (ctx.kindOf(id) === 'assembly' && !seen.has(id)) { seen.add(id); visit(id, depth + 1); }
      for (const id of ids) {
        const pd = this.hooks.partData(id) || {}, nm = this.hooks.partName(id) || id;
        if (ctx.kindOf(id) !== 'model' || pd.library || ctx.bought(pd, nm) || seen.has(id)) continue;
        seen.add(id);
        out.push({ id, name: nm, kind: 'model', depth: depth + 1 });
      }
    };
    visit(rootId, 0);
    return out;
  }

  /** The left panel's Pages: an assembly's whole set (a click opens that page's sheet — made when it has none); a part's
   *  sheet: the assemblies it is in. */
  /** The top assembly a part / assembly is in (through its sub-assemblies) — the drawing set it is a page of — or null. */
  rootOf(id) {
    const parts = this.hooks.parts?.() || [], seen = new Set([id]);
    const parentOf = (x) => parts.find((q) => q.kind === 'assembly' && !seen.has(q.id) && (this.hooks.partData(q.id)?.instances || []).some((it) => it.part === x));
    let cur = id, p;
    while ((p = parentOf(cur))) { seen.add(p.id); cur = p.id; }
    return this.hooks.kindOf?.(cur) === 'assembly' ? cur : null;
  }

  /** The left panel's Pages: the whole set this sheet is a page of (on every page of it), this page marked; a click
   *  opens that page's sheet — or, in 📚 All pages, goes to it. */
  pagesHtml() {
    const root = this.hooks.drawingCtx ? this.rootOf(this.d.source) : null;
    if (!root) return '';
    const pages = this.pagesOf(root);
    return `<h3>${esc(t('Pages'))}</h3><div class="sh-pages">${pages.map((p, i) => `<button class="sh-page ${p.id === (this.setMode ? this.seen || this.d.source : this.d.source) ? 'on' : ''}" data-page="${p.id}" style="padding-left:${6 + 12 * p.depth}px" title="${esc(this.setMode ? t('Go to this page') : t('Open its drawing sheet'))}">
      <i>${i + 1}</i> ${p.kind === 'assembly' ? '◇' : '◆'} <span data-no-i18n>${esc(p.name)}</span></button>`).join('')}</div>`;
  }

  /** 📚 All pages: the drawing set one page below the other, to scroll through (double-click a page: edit it). */
  async renderSet() {
    const root = this.rootOf(this.d.source);
    if (!root) { this.setMode = false; this.render(); return; }
    const run = (this.setRun = (this.setRun || 0) + 1);
    this.svgEl = null;
    this.stage.classList.add('sh-set');
    if (!this.stage.querySelector('.sh-sheetpage')) this.stage.innerHTML = `<p class="hint sh-empty">${esc(t('Making the pages…'))}</p>`;
    let set;
    try { set = await this.drawingSet(root, this.hooks.drawingCtx()); } catch (e) { this.stage.innerHTML = `<p class="hint sh-empty">${esc(e.message)}</p>`; return; }
    if (run !== this.setRun || !this.setMode) return;
    const top = this.stage.scrollTop;
    this.stage.innerHTML = set.svgs.map((svg, i) => `<div class="sh-sheetpage" data-pageid="${set.ids[i]}" title="${esc(t('Double-click: edit this page'))}" data-no-i18n>${svg}</div>`).join('');
    if (this.setScrolled) this.stage.scrollTop = top;
    else { this.stage.querySelector(`[data-pageid="${this.d.source}"]`)?.scrollIntoView({ block: 'start' }); this.setScrolled = true; }
    this.$('.sh-status').textContent = tv('{n} pages — scroll; double-click one to edit it', { n: set.svgs.length });
  }

  /** In 📚 All pages: the page in sight marked in Pages. */
  markSeen() {
    const st = this.stage, pages = [...st.querySelectorAll('.sh-sheetpage')], r = st.getBoundingClientRect(), at = r.top + r.height / 3;
    const end = st.scrollTop + st.clientHeight >= st.scrollHeight - 4; // (the last page cannot come up to the top)
    const seen = (end ? pages[pages.length - 1] : pages.find((p) => p.getBoundingClientRect().bottom > at))?.dataset.pageid;
    if (!seen || seen === this.seen) return;
    this.seen = seen;
    for (const b of this.$('.sh-left').querySelectorAll('.sh-page')) b.classList.toggle('on', b.dataset.page === seen);
  }

  /** ＋ a missing size: from the part's lowest place in that view to it (a Ø / R on its circle). */
  addMissing(m) {
    if (m.kind === 'dia' || m.kind === 'rad') { this.addUser({ view: m.view, kind: m.kind, a: m.key, count: 1, ang: m.kind === 'dia' ? 45 : 0, len: 6 }); return; }
    const n = this.d.user.filter((d) => d.view === m.view && d.dir === m.dir).length;
    this.addUser({ view: m.view, kind: 'linear', a: m.dir === 'h' ? 'box#x0' : 'box#y0', b: m.key, dir: m.dir, side: m.dir === 'h' ? 'b' : 'l', off: 20 + 7 * n });
  }

  // ------------------------------------------------------------------ editing
  action(a) {
    if (a === 'dim') { this.tool = this.tool === 'dim' ? 'select' : 'dim'; this.pick = null; this.hoverEdge = null; this.hint(this.tool === 'dim' ? t('Click a point, an edge or a circle — an edge alone twice gives its length. Esc: done.') : ''); this.render(); }
    if (a === 'undo') this.history.go(-1);
    if (a === 'redo') this.history.go(1);
    if (a === 'fit') { this.zoom = { k: 1, x: 0, y: 0 }; this.applyZoom(); }
    if (a === 'setview') { this.setMode = !this.setMode; this.setScrolled = false; this.seen = null; this.tool = 'select'; this.pick = null; this.render(); }
    if (a === 'pdf') this.exportPdf();
  }

  hint(text) { const h = this.$('.sh-hint'); h.hidden = !text; h.textContent = text; }

  async setPreset(p) {
    if (p === this.d.preset) return;
    this.d.preset = p;
    this.history.commit();
    await this.ensure(true);
  }

  remove(id) {
    if (!id) return;
    if (this.d.user.some((d) => d.id === id)) this.d.user = this.d.user.filter((d) => d.id !== id);
    else this.d.hidden = [...new Set([...this.d.hidden, id])];
    delete this.d.dims[id];
    if (this.sel === id) this.sel = null;
    this.commit();
  }

  /** The paper point (mm) under the mouse. */
  paperAt(e) {
    const pt = this.svgEl.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const p = pt.matrixTransform(this.svgEl.getScreenCTM().inverse());
    return [p.x, p.y];
  }

  /** The point a dimension can hang on nearest the mouse (within reach) -> {view, key, at} or null. */
  snapAt(p, reach = 2.5) {
    let best = null;
    for (const v of this.drawn()) {
      for (const [k, q] of Object.entries(this.geo.views[v].points)) {
        if (k.startsWith('box#') || k.endsWith('#m')) continue;
        const a = this.P(v, q), dist = Math.hypot(a[0] - p[0], a[1] - p[1]);
        if (dist < reach && (!best || dist < best.dist)) best = { view: v, key: k, at: a, dist };
      }
    }
    return best;
  }

  /** A circle / arc of a view whose line is under the mouse -> {view, c} or null. */
  circleAt(p, reach = 1.5) {
    for (const v of this.drawn()) {
      for (const c of this.geo.views[v].circles) {
        const C = this.P(v, c.c), R = c.r * this.scale();
        if (Math.abs(Math.hypot(p[0] - C[0], p[1] - C[1]) - R) < reach) return { view: v, c };
      }
    }
    return null;
  }

  /** A straight edge of a view under the mouse (its line within reach) -> {view, edge} or null. */
  edgeAt(p, reach = 1.2) {
    let best = null;
    for (const v of this.drawn()) {
      for (const ln of this.geo.views[v].lines) {
        const a = this.P(v, ln.a), b = this.P(v, ln.b), dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy;
        if (L2 < 1e-6) continue;
        const k = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)), dist = Math.hypot(a[0] + k * dx - p[0], a[1] + k * dy - p[1]);
        if (dist < reach && (!best || dist < best.dist)) best = { view: v, edge: ln, dist };
      }
    }
    return best;
  }

  /** An edge runs across (h), up (v) or slanted (s). */
  edgeDir(ln) { return Math.abs(ln.a[1] - ln.b[1]) < 1e-3 ? 'h' : Math.abs(ln.a[0] - ln.b[0]) < 1e-3 ? 'v' : 's'; }

  /** An edge's length as a dimension (a slanted one: its longer side). */
  edgeLength(view, ln) {
    const dir = this.edgeDir(ln) === 's' ? (Math.abs(ln.b[0] - ln.a[0]) >= Math.abs(ln.b[1] - ln.a[1]) ? 'h' : 'v') : this.edgeDir(ln);
    this.pick = null;
    this.addUser({ view, kind: 'linear', a: `${ln.key}#0`, b: `${ln.key}#1`, dir, side: dir === 'h' ? 'b' : 'r', off: 14 });
  }

  /** ＋ Dimension: a point and another (their distance), an edge (again: its length) and another edge (the distance
   *  between them) or a point, or a circle (its Ø / R). */
  clickDim(p) {
    const s = this.snapAt(p, 1.6), e = s ? null : this.edgeAt(p), ci = s || e ? null : this.circleAt(p), pk = this.pick;
    const lin = (view, a, b, dir) => {
      this.pick = null;
      this.addUser({ view, kind: 'linear', a, b, dir, side: dir === 'h' ? 'b' : 'r', off: 14 });
    };
    if (!pk) {
      if (s) { this.pick = s; this.render(); return; }
      if (e) { this.pick = { view: e.view, edge: e.edge }; this.hint(t('An edge: click it again for its length, or another edge / a point for the distance.')); this.render(); return; }
      if (ci) { this.addUser({ view: ci.view, kind: ci.c.full ? 'dia' : 'rad', a: ci.c.key, count: 1, ang: ci.c.full ? 45 : 0, len: 6 }); return; }
      this.hooks.toast(t('Click a point (an orange dot), an edge or the line of a circle.'), 'info', 2500);
      return;
    }
    const other = s || e;
    if (!other || other.view !== pk.view) { this.hooks.toast(t('Now another point or edge of the same view.'), 'info', 2500); return; }
    if (pk.edge && e && e.edge === pk.edge) { this.edgeLength(pk.view, pk.edge); return; } // the same edge again: its length
    if (pk.edge || e) { // an edge and another edge or a point: the distance across the edge
      const E = pk.edge ? pk.edge : e.edge, O = pk.edge ? other : pk;
      const ed = this.edgeDir(E), od = O.edge ? this.edgeDir(O.edge) : null;
      if (O.edge && this.angleOf({ view: pk.view, a: E.key, b: O.edge.key })) { // two edges that meet at an angle: it
        this.pick = null;
        this.addUser({ view: pk.view, kind: 'ang', a: E.key, b: O.edge.key, r: 15 });
        return;
      }
      if (ed === 's' || (od && od !== ed)) { this.hooks.toast(t('Two edges that are not parallel (or slanted) have no distance here — click points instead.'), 'warning', 4000); return; }
      lin(pk.view, `${E.key}#0`, O.edge ? `${O.edge.key}#0` : O.key, ed === 'v' ? 'h' : 'v'); // up-going edges are apart across, flat ones up
      return;
    }
    if (s.key === pk.key) return;
    const a = pk.at, b = s.at;
    lin(s.view, pk.key, s.key, Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v');
  }

  addUser(d) {
    const id = `u${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
    this.d.user = [...this.d.user, { id, ...d }];
    this.sel = id;
    this.commit();
  }

  bind() {
    let drag = null;
    this.stage.addEventListener('pointerdown', (e) => {
      if (!this.svgEl || e.button !== 0) return;
      const p = this.paperAt(e);
      if (this.tool === 'dim') { this.clickDim(p); return; }
      const dimEl = e.target.closest('[data-dim]'), viewEl = e.target.closest('[data-view]'), cell = e.target.closest('[data-tcell]');
      const twice = cell && this.lastCell?.key === cell.dataset.tcell && performance.now() - this.lastCell.at < 400; // (a pointerdown has no click count)
      this.lastCell = cell ? { key: cell.dataset.tcell, at: performance.now() } : null;
      if (twice) { // a double-click on a title-block cell: its field in the panel
        e.preventDefault(); // (the mouse's own focus change would take it away again)
        this.sel = null;
        this.renderProps();
        const inp = this.$(`.sh-props [data-text=${cell.dataset.tcell}]`);
        setTimeout(() => { inp?.focus(); inp?.select(); }, 0);
        return;
      }
      const balloon = e.target.closest('[data-balloon]');
      if (balloon) { drag = { kind: 'balloon', pos: balloon.dataset.balloon, moved: false }; this.stage.setPointerCapture(e.pointerId); return; }
      if (dimEl) {
        this.sel = dimEl.dataset.dim;
        drag = { kind: 'dim', id: this.sel, d: this.allDims().find((x) => x.id === this.sel), moved: false };
      } else if (viewEl) {
        const v = viewEl.dataset.view;
        drag = { kind: 'view', v, start: p, from: v === 'Iso' ? (this.d.views.Iso || this.lay.iso.slice(0, 2)) : this.centre(v), moved: false };
      } else {
        this.sel = null;
        drag = { kind: 'pan', start: [e.clientX, e.clientY], from: { ...this.zoom }, moved: false };
      }
      this.stage.setPointerCapture(e.pointerId);
      this.render();
    });
    this.stage.addEventListener('pointermove', (e) => {
      if (!drag && this.tool === 'dim' && this.svgEl) { // the edge a click would take lights up
        const p = this.paperAt(e), h = this.snapAt(p, 1.6) ? null : this.edgeAt(p);
        if ((h?.edge || null) !== (this.hoverEdge?.edge || null)) { this.hoverEdge = h; cancelAnimationFrame(this.hoverRaf); this.hoverRaf = requestAnimationFrame(() => this.render()); }
        return;
      }
      if (!drag || !this.svgEl) return;
      if (drag.kind === 'pan') {
        this.zoom.x = drag.from.x + e.clientX - drag.start[0];
        this.zoom.y = drag.from.y + e.clientY - drag.start[1];
        this.applyZoom();
        return;
      }
      const p = this.paperAt(e);
      drag.moved = true;
      if (drag.kind === 'balloon') {
        this.d.balloons = { ...(this.d.balloons || {}), [drag.pos]: [+p[0].toFixed(2), +p[1].toFixed(2)] };
      } else if (drag.kind === 'view') {
        this.d.views[drag.v] = [drag.from[0] + p[0] - drag.start[0], drag.from[1] + p[1] - drag.start[1]];
      } else {
        const d = drag.d, o = { ...(this.d.dims[d.id] || {}) };
        if (d.kind === 'linear') {
          const pb = this.paperBox(d.view);
          if (d.dir === 'h') { o.side = p[1] < (pb[1] + pb[3]) / 2 ? 't' : 'b'; o.off = Math.max(3, o.side === 't' ? pb[1] - p[1] : p[1] - pb[3]); } else { o.side = p[0] < (pb[0] + pb[2]) / 2 ? 'l' : 'r'; o.off = Math.max(3, o.side === 'l' ? pb[0] - p[0] : p[0] - pb[2]); }
          o.off = Math.round(o.off * 2) / 2;
        } else if (d.kind === 'ang') {
          const a = this.angleOf(d);
          if (!a) return;
          const X = this.P(d.view, a.X);
          o.r = Math.max(4, Math.round(Math.hypot(p[0] - X[0], p[1] - X[1]) * 2) / 2);
        } else {
          const c = this.circleOf(d.view, d.a);
          if (!c) return;
          const C = this.P(d.view, c.c), R = c.r * this.scale(), deg = Math.atan2(-(p[1] - C[1]), p[0] - C[0]) * 180 / Math.PI;
          if (d.kind === 'rad') o.ang = deg - Math.atan2(-(c.pm[1] - c.c[1]), c.pm[0] - c.c[0]) * 180 / Math.PI; else o.ang = Math.round(deg);
          o.len = Math.max(2, Math.round(Math.hypot(p[0] - C[0], p[1] - C[1]) - R));
        }
        this.setDim(d, o);
      }
      this.render();
    });
    this.stage.addEventListener('pointerup', () => {
      if (drag?.moved && drag.kind !== 'pan') this.commit();
      drag = null;
    });
    this.stage.addEventListener('scroll', () => { if (this.setMode) this.markSeen(); });
    this.stage.addEventListener('dblclick', (e) => { // 📚 All pages: a page to edit
      const pg = this.setMode && e.target.closest('[data-pageid]');
      if (!pg) return;
      this.setMode = false;
      if (pg.dataset.pageid === this.d.source) this.render(); else this.hooks.openSheet?.(pg.dataset.pageid, { setMode: false });
    });
    this.stage.addEventListener('wheel', (e) => {
      if (this.setMode) return; // (it scrolls)
      e.preventDefault();
      const r = this.stage.getBoundingClientRect(), f = e.deltaY < 0 ? 1.15 : 1 / 1.15, k = Math.min(12, Math.max(0.3, this.zoom.k * f));
      const mx = e.clientX - r.left - r.width / 2, my = e.clientY - r.top - r.height / 2; // the SVG scales about the stage's middle
      this.zoom.x = mx - (mx - this.zoom.x) * (k / this.zoom.k);
      this.zoom.y = my - (my - this.zoom.y) * (k / this.zoom.k);
      this.zoom.k = k;
      this.applyZoom();
    }, { passive: false });
  }

  /** The moved place of a dimension: an automatic one keeps it in `dims`, the user's in itself. */
  setDim(d, o) {
    const u = this.d.user.find((x) => x.id === d.id);
    if (u) Object.assign(u, o); else this.d.dims[d.id] = o;
  }

  key(e) {
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    if (e.key === 'Enter' && this.tool === 'dim' && this.pick?.edge) { this.edgeLength(this.pick.view, this.pick.edge); e.preventDefault(); return; } // its length
    if (e.key === 'Escape' && this.tool === 'dim') { if (this.pick) { this.pick = null; this.render(); } else this.action('dim'); e.preventDefault(); }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel) { this.remove(this.sel); e.preventDefault(); }
    if (e.ctrlKey && e.key.toLowerCase() === 'z') { this.history.go(-1); e.preventDefault(); }
    if (e.ctrlKey && e.key.toLowerCase() === 'y') { this.history.go(1); e.preventDefault(); }
  }

  async exportPdf() {
    const res = await fetch('/api/sheet/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ svg: this.svg(true), name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast((await res.json()).error || res.statusText, 'error'); return; }
    await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.pdf`);
  }

  /** For the AI: the points and circles of a view a dimension can hang on (near the view's lower-left first). */
  pointsOf(v) {
    const g = this.geo?.views[v];
    if (!g) throw new Error(`view is one of ${VIEWS.join(', ')}.`);
    const r = (p) => p.map((x) => +x.toFixed(2));
    return { box: g.box.map((x) => +x.toFixed(2)),
      points: Object.entries(g.points).filter(([k]) => !k.endsWith('#m')).map(([k, p]) => ({ key: k, at: r(p) })).sort((a, b) => a.at[1] - b.at[1] || a.at[0] - b.at[0]).slice(0, 120),
      circles: g.circles.map((c) => ({ key: c.key, centre: r(c.c), d: +(2 * c.r).toFixed(3), full: c.full })).slice(0, 80) };
  }

  /** For the AI: a dimension added — {view, a, b, dir?} (two point keys; dir "h" / "v", else by the points) or
   *  {view, circle: key} (its Ø, or R of an arc) -> its id. */
  addFor(spec) {
    const g = this.geo?.views[spec.view];
    if (!g) throw new Error(`view is one of ${VIEWS.join(', ')}.`);
    if (spec.circle) {
      const c = g.circles.find((x) => x.key === spec.circle);
      if (!c) throw new Error(`No circle ${spec.circle} in ${spec.view} — get_sheet {points: "${spec.view}"} lists them.`);
      this.addUser({ view: spec.view, kind: c.full ? 'dia' : 'rad', a: c.key, count: Math.max(1, +spec.count || 1), ang: c.full ? 45 : 0, len: 6, ...(spec.post ? { post: ` ${spec.post}` } : {}) });
      return this.sel;
    }
    if (spec.edges) {
      const [ka, kb] = [].concat(spec.edges).map((k) => String(k).replace(/#[01]$/, ''));
      for (const k of [ka, kb]) if (!g.lines.some((x) => x.key === k)) throw new Error(`No edge ${k} in ${spec.view} — get_sheet {points: "${spec.view}"} lists them (a line's ends are <edge>#0 / #1).`);
      if (!this.angleOf({ view: spec.view, a: ka, b: kb })) throw new Error('These two edges are parallel — no angle between them.');
      this.addUser({ view: spec.view, kind: 'ang', a: ka, b: kb, r: 15 });
      return this.sel;
    }
    const a = g.points[spec.a], b = g.points[spec.b];
    if (!a || !b) throw new Error(`No point ${!a ? spec.a : spec.b} in ${spec.view} — get_sheet {points: "${spec.view}"} lists them.`);
    const dir = spec.dir === 'h' || spec.dir === 'v' ? spec.dir : Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v';
    this.addUser({ view: spec.view, kind: 'linear', a: spec.a, b: spec.b, dir, side: dir === 'h' ? 'b' : 'r', off: 14, ...(spec.pre ? { pre: `${spec.pre} ` } : {}) });
    return this.sel;
  }

  /** For the AI: the sheet's dimensions with their values. */
  summary() {
    const ck = this.check();
    return { check: ck ? { fully_dimensioned: ck.ok && !ck.over.size, missing: ck.missing.map((m) => `${m.view}: ${m.what}${m.ax ? ` (${m.ax})` : ''}`).slice(0, 30), twice: [...ck.dup, ...ck.over] } : null,
      part: this.hooks.partName(this.d.source), ...(Object.keys(this.d.texts || {}).length ? { texts: this.d.texts } : {}), preset: this.d.preset, ...(Object.keys(this.d.vpreset || {}).length ? { view_presets: this.d.vpreset } : {}), paper: this.lay?.paper, rev: this.d.rev, changed: this.d.changed,
      views: [...VIEWS, 'Iso'].filter((v) => !this.d.off[v]),
      dims: this.allDims().map((d) => ({ id: d.id, view: d.view, kind: d.kind, text: this.value(d) === null ? null : this.dimText(d, this.value(d)), auto: !!d.auto, ...(this.value(d) === null ? { lost: true } : {}) })),
      deleted_auto: this.d.hidden.length,
      ...(this.d.asm?.rows ? { parts_list: this.d.asm.rows.map((r) => ({ pos: r.pos, name: r.name, part: r.part, qty: r.qty, ...(r.instances ? { instances: r.instances } : {}),
        balloon: this.balloonAt?.[r.pos] ? { at_mm: this.balloonAt[r.pos], points_to: r.instances?.[0] || null } : null })) } : {}) };
  }
}
