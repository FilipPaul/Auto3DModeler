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
      capture: () => ({ views: this.d?.views, off: this.d?.off, dims: this.d?.dims, hidden: this.d?.hidden, user: this.d?.user, preset: this.d?.preset, vpreset: this.d?.vpreset, paper: this.d?.paper, texts: this.d?.texts }),
      restore: (s) => { Object.assign(this.d, structuredClone(s)); if (this.d.built?.preset !== this.d.preset || this.d.built?.vp !== JSON.stringify(this.d.vpreset || {})) this.ensure(true); else this.render(); },
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
  async ensure(force = false) {
    const src = this.hooks.partData(this.d.source);
    if (!src) { this.render(); return; }
    const h = partHash(src);
    const vp = JSON.stringify(this.d.vpreset || {});
    if (!force && this.d.built && !this.d.built.stale && this.d.hash === h && this.d.built.preset === this.d.preset && this.d.built.vp === vp && (this.d.built.paper ?? null) === (this.d.paper ?? null)) return;
    this.busy = true;
    this.renderBar();
    try {
      const res = await fetch('/api/sheet/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: src, preset: this.d.preset, paper: this.d.paper, per_view: this.d.vpreset || {} }) });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || res.statusText);
      if (this.d.hash && this.d.hash !== h) { this.d.rev += 1; this.d.changed = new Date().toISOString(); } // the part changed
      Object.assign(this.d, { built: { ...r, preset: this.d.preset, vp, paper: this.d.paper ?? null }, hash: h });
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
  centre(v) { return this.d.views[v] || this.lay.views[v]; }

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
  value(d) {
    const g = this.geo?.views[d.view];
    if (!g) return null;
    if (d.kind === 'dia' || d.kind === 'rad') { const c = this.circleOf(d.view, d.a); return c ? (d.kind === 'dia' ? 2 * c.r : c.r) : null; }
    const a = g.points[d.a], b = g.points[d.b];
    if (!a || !b) return null;
    return d.dir === 'h' ? Math.abs(b[0] - a[0]) : Math.abs(b[1] - a[1]);
  }

  dimText(d, v) {
    if (d.kind === 'dia') return `${d.count > 1 ? `${d.count}× ` : ''}Ø${fmt(v)}${d.post || ''}`;
    if (d.kind === 'rad') return `${d.count > 1 ? `${d.count}× ` : ''}R${fmt(v)}`;
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
    for (const v of VIEWS) {
      if (this.d.off[v]) continue;
      const g = G.views[v], pb = this.paperBox(v);
      out.push(`<g data-view="${v}" class="sh-view">`);
      if (!forPrint) out.push(`<rect x="${pb[0] - 2}" y="${pb[1] - 2}" width="${pb[2] - pb[0] + 4}" height="${pb[3] - pb[1] + 4}" fill="#fff" fill-opacity="0" stroke="none" class="sh-vhit"/>`);
      for (const p of g.hidden) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#666" stroke-width="0.25" stroke-dasharray="1.5 1"/>`);
      for (const p of g.visible) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#000" stroke-width="0.5" stroke-linejoin="round"/>`);
      // its name below the dimensions under it
      const below = Math.max(0, ...this.allDims().filter((d) => d.view === v && d.kind === 'linear' && d.dir === 'h' && d.side !== 't').map((d) => d.off ?? 8));
      out.push(`<text x="${(pb[0] + pb[2]) / 2}" y="${pb[3] + below + 8}" font-size="3.5" text-anchor="middle" fill="#334">${esc(t(v))}</text></g>`);
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
    out.push(this.titleSvg(pw, ph, m, th, s));
    out.push('</svg>');
    return out.join('').replace(/<text /g, '<text font-family="Helvetica" '); // (the PDF's converter does not inherit a font)
  }

  /** One dimension: extension lines, the dimension line with arrows and its text (linear); a leader (Ø, R). */
  dimSvg(d, forPrint) {
    const v = this.value(d), lost = v === null, on = !forPrint && this.sel === d.id;
    const col = lost ? '#d97706' : on ? '#1f6feb' : '#1b3a8a', sw = on ? 0.35 : 0.2, fs = 3.2;
    const arrow = (p, dir) => { // a filled arrowhead at p pointing along dir (unit)
      const [ux, uy] = dir, L = 2.2, W = 0.7;
      return `<path d="M${p[0]},${p[1]} L${p[0] - ux * L - uy * W},${p[1] - uy * L + ux * W} L${p[0] - ux * L + uy * W},${p[1] - uy * L - ux * W} Z" fill="${col}"/>`;
    };
    const g = [`<g data-dim="${d.id}" class="sh-dim${on ? ' on' : ''}">`];
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
    for (const v of VIEWS) {
      if (this.d.off[v]) continue;
      for (const [k, p] of Object.entries(this.geo.views[v].points)) {
        if (k.startsWith('box#')) continue;
        const q = this.P(v, p), first = this.pick?.view === v && this.pick.key === k;
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
    if (this.isoMap && !this.d.off.Iso) { // the balloons
      for (const r of rows) {
        if (!r.iso) continue;
        const p = this.isoMap.at(r.iso), c = this.isoMap.c, L = Math.hypot(p[0] - c[0], p[1] - c[1]) || 1;
        const u = L > 1 ? [(p[0] - c[0]) / L, (p[1] - c[1]) / L] : [0.7, -0.7], b = [p[0] + u[0] * 16, p[1] + u[1] * 16];
        g.push(`<line x1="${p[0]}" y1="${p[1]}" x2="${b[0] - u[0] * 3.4}" y2="${b[1] - u[1] * 3.4}" stroke="#1b3a8a" stroke-width="0.2"/><circle cx="${p[0]}" cy="${p[1]}" r="0.5" fill="#1b3a8a"/>`);
        g.push(`<circle cx="${b[0]}" cy="${b[1]}" r="3.4" fill="#fff" stroke="#1b3a8a" stroke-width="0.3"/><text x="${b[0]}" y="${b[1] + 1.2}" font-size="3.4" text-anchor="middle" fill="#1b3a8a">${r.pos}</text>`);
      }
    }
    g.push('</g>');
    return g.join('');
  }

  /** A sheet that is not on screen drawn (a page of a drawing set): its data with `built`. */
  svgOf(d) {
    const keep = this.d;
    this.d = { views: {}, off: {}, dims: {}, hidden: [], user: [], rev: 1, ...d };
    try { return this.svg(true); } finally { this.d = keep; this.isoMap = null; }
  }

  /** The drawing set of an assembly — its page (views, overall sizes, parts list, balloons), then each sub-assembly
   *  with its parts the same way, then its own made parts (their own sheet when they have one, with the user's
   *  dimensions; else made now) — every part once; bought and standard parts only in the lists.
   *  ctx: {kindOf(id), sheetOf(part id) -> a sheet's data or null, bought(data, name)} -> {svgs, pages: [names]}. */
  async drawingSet(rootId, ctx) {
    const pages = [], drawn = new Set([rootId]), name = (id) => this.hooks.partName(id) || id, now = new Date().toISOString();
    const flatten = (aid, M = ID4, pre = '') => (this.hooks.partData(aid)?.instances || []).flatMap((it) => {
      const W = mul4(M, it.matrix || ID4), id = pre ? `${pre}/${it.id}` : it.id;
      if (ctx.kindOf(it.part) === 'assembly') return flatten(it.part, W, id);
      return [{ id, part: { features: this.hooks.partData(it.part)?.features || [] }, matrix: W }];
    });
    const visit = async (aid, parent) => {
      const insts = this.hooks.partData(aid)?.instances || [];
      if (!insts.length) return;
      const r = await post('/api/sheet/assembly', { instances: flatten(aid) });
      const groups = new Map();
      for (const it of insts) { if (!groups.has(it.part)) groups.set(it.part, []); groups.get(it.part).push(it.id); }
      const rows = [...groups].map(([part, ids], i) => {
        const pd = this.hooks.partData(part) || {}, kind = ctx.kindOf(part), nm = name(part);
        const iso = Object.entries(r.marks).filter(([k]) => k === ids[0] || k.startsWith(`${ids[0]}/`)).map(([, m]) => m.Iso);
        return { pos: i + 1, part, name: nm, qty: ids.length, kind, material: kind === 'assembly' ? '—' : pd.material || 'PLA', pn: pd.library?.pn || '',
          bought: kind !== 'assembly' && (!!pd.library || ctx.bought(pd, nm)), iso: iso.length ? [iso.reduce((s, q) => s + q[0], 0) / iso.length, iso.reduce((s, q) => s + q[1], 0) / iso.length] : null };
      });
      pages.push({ name: name(aid), d: { source: aid, built: { ...r, preset: 'light' }, asm: { rows }, created: now, changed: now, off: { Right: true }, views: { Iso: r.layout.views.Right },
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
      if (!d.built || d.built.stale || d.hash !== partHash(src)) d.built = { ...(await post('/api/sheet/build', { part: src, preset: d.preset || 'medium', paper: d.paper })), preset: d.preset || 'medium', paper: d.paper ?? null };
      pg.d = { ...d, title: { part: pg.name, of: pg.parent, pos: pg.pos } };
    }
    const n = pages.length;
    const svgs = pages.map((pg, i) => this.svgOf({ ...pg.d, title: { ...pg.d.title, sheet: `${i + 1} / ${n}` } }));
    return { svgs, pages: pages.map((pg) => (pg.part ? pg.name : `◇ ${pg.name}`)) };
  }

  // ------------------------------------------------------------------ the screen
  render() {
    this.renderBar();
    this.renderLeft();
    this.renderProps();
    if (!this.d) return;
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
    bar.innerHTML = `<div class="seg sh-presets" title="How many dimensions it makes by itself">${PRESETS.map(([k, l]) => `<button class="chip ${this.d.preset === k ? 'on' : ''}" data-preset="${k}">${t(l)}</button>`).join('')}</div>
      <button class="chip tool ${this.tool === 'dim' ? 'on' : ''}" data-a="dim" title="Add a dimension: click two points (a corner, a hole's centre), or a circle / arc (Ø / R) — its value is measured from the part">＋ Dimension</button>
      <span class="sep"></span><button class="chip" data-a="undo" title="Undo (Ctrl+Z)" ${this.history.canUndo() ? '' : 'disabled'}>↶</button><button class="chip" data-a="redo" title="Redo (Ctrl+Y)" ${this.history.canRedo?.() ? '' : 'disabled'}>↷</button>
      <span class="sep"></span><button class="chip" data-a="fit" title="The whole sheet">⤢ Fit</button>
      <button class="chip primary" data-a="pdf" title="The sheet as a PDF — as you see it">⬇ PDF</button>${this.busy ? `<span class="sh-busy">${t('Making the drawing…')}</span>` : ''}`;
    for (const b of bar.querySelectorAll('[data-preset]')) b.addEventListener('click', () => this.setPreset(b.dataset.preset));
    for (const b of bar.querySelectorAll('[data-a]')) b.addEventListener('click', () => this.action(b.dataset.a));
  }

  renderLeft() {
    const box = this.$('.sh-left');
    if (!box || !this.d) return;
    const all = this.allDims(), hid = this.d.hidden.length;
    const vp = this.d.vpreset || {};
    box.innerHTML = `<h3>Views</h3><div class="sh-views">${[...VIEWS, 'Iso'].map((v) => `<div class="sh-vrow"><label class="check"><input type="checkbox" data-v="${v}" ${this.d.off[v] ? '' : 'checked'}> ${esc(t(v))}</label>
        ${v === 'Iso' ? '' : `<select data-vp="${v}" title="${esc(t('How many dimensions in this view — as the sheet, or its own'))}"><option value="">${esc(t('as the sheet'))}</option>${PRESETS.map(([k, l]) => `<option value="${k}" ${vp[v] === k ? 'selected' : ''}>${esc(t(l))}</option>`).join('')}</select>`}</div>`).join('')}</div>
      <h3>Dimensions</h3><div class="sh-dlist">${all.map((d) => { const v = this.value(d); return `<div class="sh-drow ${this.sel === d.id ? 'on' : ''} ${v === null ? 'bad' : ''}" data-d="${d.id}">
        <span data-no-i18n>${d.kind === 'linear' ? (d.dir === 'h' ? '↔ ' : '↕ ') : ''}${esc(v === null ? '⚠ ?' : this.dimText(d, v))}</span><i>${esc(t(d.view))}${d.auto ? '' : ' · ✎'}</i><button class="mini danger" data-x="${d.id}" title="Delete it">✕</button></div>`; }).join('') || '<p class="hint">None.</p>'}</div>
      ${hid ? `<div class="row-actions"><button class="btn small" data-a="unhide">↺ ${esc(tv('Bring back deleted ones ({n})', { n: hid }))}</button></div>` : ''}`;
    for (const el of box.querySelectorAll('[data-v]')) {
      el.addEventListener('change', () => { if (el.checked) delete this.d.off[el.dataset.v]; else this.d.off[el.dataset.v] = true; this.commit(); });
    }
    for (const el of box.querySelectorAll('[data-vp]')) {
      el.addEventListener('change', () => { const vpr = { ...(this.d.vpreset || {}) }; if (el.value) vpr[el.dataset.vp] = el.value; else delete vpr[el.dataset.vp]; this.d.vpreset = vpr; this.history.commit(); this.ensure(true); });
    }
    for (const row of box.querySelectorAll('[data-d]')) row.addEventListener('click', (e) => { if (!e.target.closest('[data-x]')) { this.sel = row.dataset.d; this.render(); } });
    for (const b of box.querySelectorAll('[data-x]')) b.addEventListener('click', () => this.remove(b.dataset.x));
    box.querySelector('[data-a=unhide]')?.addEventListener('click', () => { this.d.hidden = []; this.commit(); });
  }

  renderProps() {
    const box = this.$('.sh-props');
    if (!box || !this.d) return;
    const d = this.sel && this.allDims().find((x) => x.id === this.sel), name = this.hooks.partName(this.d.source);
    box.innerHTML = `<h2>📄 ${esc(t('Drawing'))}</h2>
      <p class="hint">${esc(tv('Of {part} — it follows the part: change the part, the drawing is made again (a new revision).', { part: name || '?' }))}</p>
      <div class="mp-facts"><span>Rev</span><b data-no-i18n>${this.d.rev}</b><span>${esc(t('Changed'))}</span><b data-no-i18n>${esc(when(this.d.changed))}</b><span>${esc(t('Created'))}</span><b data-no-i18n>${esc(when(this.d.created))}</b></div>
      ${d ? '' : `<h3>${esc(t('Title block'))}</h3>${TEXTS.map(([k, l]) => `<div class="field"><label>${esc(t(l))}</label><input type="text" data-text="${k}" value="${esc(this.d.texts?.[k] || '')}" placeholder="${esc(k === 'title' ? this.hooks.partName(this.d.source) || '' : '')}"></div>`).join('')}`}
      <div class="field"><label>Paper</label><select data-k="paper">${[['', 'Auto'], ['A4', 'A4'], ['A3', 'A3']].map(([v, l]) => `<option value="${v}" ${(this.d.paper || '') === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      ${d ? `<h3>${esc(t('Dimension'))}</h3><p class="mp-count" data-no-i18n>${esc(this.value(d) === null ? '⚠ ?' : this.dimText(d, this.value(d)))}</p>
        <p class="hint">${esc(d.auto ? t('Made by the preset. Drag it to move it; Delete removes it (↺ brings it back).') : t('Your own. Drag it to move it; Delete removes it.'))}</p>
        ${this.value(d) === null ? `<p class="mp-bad">${esc(t('Its points are gone — the part changed. Delete it and add it again.'))}</p>` : ''}
        <div class="row-actions"><button class="btn small danger" data-a="del">✕ ${esc(t('Delete'))}</button></div>`
        : `<p class="hint">${esc(t('Drag a dimension or a view to move it. ＋ Dimension: click two points, or a circle. The values come from the part.'))}</p>`}
      ${name ? `<div class="row-actions"><button class="btn small" data-a="part">◆ ${esc(tv('Open {part}', { part: name }))}</button></div>` : ''}`;
    for (const el of box.querySelectorAll('[data-text]')) {
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => { const x = { ...(this.d.texts || {}) }; if (el.value.trim()) x[el.dataset.text] = el.value.trim(); else delete x[el.dataset.text]; this.d.texts = x; this.commit(); });
    }
    box.querySelector('[data-k=paper]').addEventListener('change', (e) => { this.d.paper = e.target.value || null; this.d.views = {}; this.history.commit(); this.ensure(true); });
    box.querySelector('[data-a=del]')?.addEventListener('click', () => this.remove(this.sel));
    box.querySelector('[data-a=part]')?.addEventListener('click', () => this.hooks.openPart?.(this.d.source));
  }

  // ------------------------------------------------------------------ editing
  action(a) {
    if (a === 'dim') { this.tool = this.tool === 'dim' ? 'select' : 'dim'; this.pick = null; this.hint(this.tool === 'dim' ? t('Click a point (a corner, a hole\'s centre) and another one — or a circle / arc for its Ø / R. Esc: done.') : ''); this.render(); }
    if (a === 'undo') this.history.go(-1);
    if (a === 'redo') this.history.go(1);
    if (a === 'fit') { this.zoom = { k: 1, x: 0, y: 0 }; this.applyZoom(); }
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
    for (const v of VIEWS) {
      if (this.d.off[v]) continue;
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
    for (const v of VIEWS) {
      if (this.d.off[v]) continue;
      for (const c of this.geo.views[v].circles) {
        const C = this.P(v, c.c), R = c.r * this.scale();
        if (Math.abs(Math.hypot(p[0] - C[0], p[1] - C[1]) - R) < reach) return { view: v, c };
      }
    }
    return null;
  }

  clickDim(p) {
    const s = this.snapAt(p);
    if (!this.pick) {
      if (s) { this.pick = s; this.render(); return; }
      const ci = this.circleAt(p);
      if (ci) { this.addUser({ view: ci.view, kind: ci.c.full ? 'dia' : 'rad', a: ci.c.key, count: 1, ang: ci.c.full ? 45 : 0, len: 6 }); return; }
      this.hooks.toast(t('Click a point (an orange dot) or the line of a circle.'), 'info', 2500);
      return;
    }
    if (!s || s.view !== this.pick.view || s.key === this.pick.key) { this.hooks.toast(t('Now another point of the same view.'), 'info', 2500); return; }
    const a = this.pick.at, b = s.at, dir = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v';
    this.addUser({ view: s.view, kind: 'linear', a: this.pick.key, b: s.key, dir, side: dir === 'h' ? 'b' : 'r', off: 14 });
    this.pick = null;
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
      if (!drag || !this.svgEl) return;
      if (drag.kind === 'pan') {
        this.zoom.x = drag.from.x + e.clientX - drag.start[0];
        this.zoom.y = drag.from.y + e.clientY - drag.start[1];
        this.applyZoom();
        return;
      }
      const p = this.paperAt(e);
      drag.moved = true;
      if (drag.kind === 'view') {
        this.d.views[drag.v] = [drag.from[0] + p[0] - drag.start[0], drag.from[1] + p[1] - drag.start[1]];
      } else {
        const d = drag.d, o = { ...(this.d.dims[d.id] || {}) };
        if (d.kind === 'linear') {
          const pb = this.paperBox(d.view);
          if (d.dir === 'h') { o.side = p[1] < (pb[1] + pb[3]) / 2 ? 't' : 'b'; o.off = Math.max(3, o.side === 't' ? pb[1] - p[1] : p[1] - pb[3]); } else { o.side = p[0] < (pb[0] + pb[2]) / 2 ? 'l' : 'r'; o.off = Math.max(3, o.side === 'l' ? pb[0] - p[0] : p[0] - pb[2]); }
          o.off = Math.round(o.off * 2) / 2;
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
    this.stage.addEventListener('wheel', (e) => {
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
    if (e.key === 'Escape' && this.tool === 'dim') { this.action('dim'); e.preventDefault(); }
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
    const a = g.points[spec.a], b = g.points[spec.b];
    if (!a || !b) throw new Error(`No point ${!a ? spec.a : spec.b} in ${spec.view} — get_sheet {points: "${spec.view}"} lists them.`);
    const dir = spec.dir === 'h' || spec.dir === 'v' ? spec.dir : Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v';
    this.addUser({ view: spec.view, kind: 'linear', a: spec.a, b: spec.b, dir, side: dir === 'h' ? 'b' : 'r', off: 14, ...(spec.pre ? { pre: `${spec.pre} ` } : {}) });
    return this.sel;
  }

  /** For the AI: the sheet's dimensions with their values. */
  summary() {
    return { part: this.hooks.partName(this.d.source), ...(Object.keys(this.d.texts || {}).length ? { texts: this.d.texts } : {}), preset: this.d.preset, ...(Object.keys(this.d.vpreset || {}).length ? { view_presets: this.d.vpreset } : {}), paper: this.lay?.paper, rev: this.d.rev, changed: this.d.changed,
      views: [...VIEWS, 'Iso'].filter((v) => !this.d.off[v]),
      dims: this.allDims().map((d) => ({ id: d.id, view: d.view, kind: d.kind, text: this.value(d) === null ? null : this.dimText(d, this.value(d)), auto: !!d.auto, ...(this.value(d) === null ? { lost: true } : {}) })),
      deleted_auto: this.d.hidden.length };
  }
}
