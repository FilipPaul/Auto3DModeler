// The drawing sheet of a 3D model part (📄): its views (front, top, right, iso) on an A4 / A3 page with a title block,
// and dimensions — made automatically for a preset (light / medium / full, auto3d/modeler/sheet.py: holes alike once,
// "8× Ø3 H7", a row by its pitch; a hole step's holes one callout "4× M3 ⌵ Ø5 × 90°"), moved by dragging, deleted (Del; an automatic one can be brought back), and added by
// clicking two points or a circle. A value is always measured from the part, never typed. The sheet follows its part:
// when the part changes the views and dimensions are made again, the revision goes up and the title block says when.
// The PDF is the same SVG the editor shows (/api/sheet/pdf); so is the DXF (/api/sheet/dxf: the paper 1:1 in mm, a layer
// per kind, the dimensions as real DXF dimensions from dxfDims).
//
// Sheet JSON (a project part of kind "sheet"):
//   {source: "<part id>", preset: "light" | "medium" | "full", vpreset: {Top: "full"} (a view's own), paper: null | "A4" | "A3", views: {Front: [x, y]} (moved),
//    off: {Iso: true} (views not shown), dims: {<id>: {side, off, ang, len}} (automatic ones moved), hidden: [<ids>],
//    user: [<dimension>], texts: {title, number, drawn, note, …} (typed into the title block), setTexts: {drawn, …}
//    (an assembly's sheet: the texts its whole drawing set shows — tbedit.js says which may go there),
//    viewNames: {Front: "Side A"} (renamed views), scale: null | [a, b] (the sheet's own, else the fit's),
//    vscale: {Top: [2, 1]} (a view's own scale, its label says it: "Top (2:1)"),
//    built: {geometry, layout, dims} (from the server), hash (of the part it was built from),
//    rev, created, changed}
import { History } from '../history.js';
import { t, getLang } from '../i18n.js';
import { ask } from '../choose.js';
import { renameInPlace } from '../rename.js';
import { HOLE_FITS, SHAFT_FITS, deviationText } from './fits.js';
import { itemNumbers as numbersOf, bomOf, makeBuy } from '../assembly/bom.js';
import { MATERIALS } from '../modeler/materials.js';
import { stepsAtBar, rolledText } from '../modeler/steptree.js';
import { showSuggest } from '../suggest.js';
import { sheetSuggest, tolText } from './sheetsuggest.js';
import { TB_EDIT, TB_COMPUTED, hitRect, propagates, remembered } from './tbedit.js';
import { TITLE_STYLES, BOM_STYLES, STYLE_TIPS, isStyle, isBomStyle, titleSize, titleBlock, partsList, bomWidth, bomHeight, bomRowsIn, grams, fontsReady } from './tbstyles.js';

const NS = 'http://www.w3.org/2000/svg';
const fmt = (v) => (+(+v).toFixed(2)).toString();
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const VIEWS = ['Front', 'Top', 'Right'];
const BOM_ROW = 5.5; // a BOM page's row (mm)
const PAPER = { A4: [297, 210], A3: [420, 297] }; // (as auto3d/modeler/sheet.py PAPERS, landscape mm)
const PRESETS = [['light', 'Light'], ['medium', 'Medium'], ['full', 'Full']];
const TEXTS = [['title', 'Title'], ['number', 'Drawing no.'], ['drawn', 'Drawn by'], ['note', 'Note']];
/** The fixed texts a title-block template holds (a sheet's own text of these overrides it). */
const TPL_TEXTS = ['company', 'address', 'drawn', 'note', 'tolstd', 'surface'];
const MORE_TEXTS = [['company', 'Company'], ['address', 'Address'], ['tolstd', 'Tolerance standard'], ['surface', 'Roughness (Ra)'], ['checked', 'Checked by'], ['approved', 'Approved by']];
/** The title block's fields that a template may leave out. */
const TB_FIELDS = [['company', 'Company / logo'], ['number', 'Drawing no.'], ['material', 'Material'], ['paper', 'Paper'], ['tolerances', 'Tolerances'], ['drawn', 'Drawn by'], ['created', 'Created'], ['changed', 'Changed'], ['note', 'Note']];
// the default for drawings that chose none (the owner's choice, 2026-10-28): B — ISO 7200 with its ISO 5457 frame
export const DEFAULT_TPL = { name: 'B — ISO 7200', builtin: true, layout: 'block', titleStyle: 'B', bomStyle: 'B', hide: [], texts: {}, logo: null,
  frame: { preset: 'iso', m: [20, 10, 10, 10], line: 0.7, zones: true, marks: true } };
/** The sheet's frame presets (as auto3d/title_templates.py FRAMES): margins [left, top, right, bottom] mm, the line's
 *  width (0: no frame), zones (grid references A… / 1… in the margins) and centring marks (ISO 5457). */
const FRAMES = {
  simple: { preset: 'simple', m: [10, 10, 10, 10], line: 0.5, zones: false, marks: false },
  iso: { preset: 'iso', m: [20, 10, 10, 10], line: 0.7, zones: true, marks: true },
  narrow: { preset: 'narrow', m: [5, 5, 5, 5], line: 0.35, zones: false, marks: false },
  none: { preset: 'none', m: [10, 10, 10, 10], line: 0, zones: false, marks: false },
};
const FRAME_CHOICES = [['simple', 'Simple (10 mm)', 'A thin frame 10 mm from the edge all round — as before'], ['iso', 'Standard ISO 5457', '20 mm on the left for filing, 10 mm elsewhere, a 0.7 mm frame, zones A… / 1… and centring marks'],
  ['narrow', 'Narrow', '5 mm all round — the most room for the views'], ['none', 'None', 'No frame line (10 mm left free for the printer)'], ['custom', 'Custom…', 'Your own margins, line, zones and centring marks']];
/** The standard drawing scales (ISO 5455) offered in the scale choices; Custom… takes any, e.g. 1:2522. */
const SCALE_LIST = [[10, 1], [5, 1], [2, 1], [1, 1], [1, 2], [1, 5], [1, 10], [1, 20], [1, 50], [1, 100]];
/** [min, max] of many numbers (a spread into Math.min overflows the stack past ~100 000). */
const span = (vs) => vs.reduce(([lo, hi], v) => [Math.min(lo, v), Math.max(hi, v)], [Infinity, -Infinity]);
/** A scale as written ("1:2522", "3:1", "1/5", "0.5", "2") -> [a, b] (both above 0), or null (as sheet.parse_scale). */
export function parseScale(text) {
  const m = /^\s*(\d+(?:[.,]\d+)?)\s*(?:[:/]\s*(\d+(?:[.,]\d+)?))?\s*$/.exec(String(text ?? ''));
  if (!m) return null;
  let a = parseFloat(m[1].replace(',', '.')), b = m[2] ? parseFloat(m[2].replace(',', '.')) : 1;
  if (!m[2] && a > 0 && a < 1) { b = 1 / a; a = 1; }
  if (!(a > 0 && b > 0 && Number.isFinite(a) && Number.isFinite(b))) return null;
  return [+a.toFixed(4), +b.toFixed(4)];
}
const scaleText = (s) => (s ? `${fmt(s[0])}:${fmt(s[1])}` : '');
const sameScale = (a, b) => !!a && !!b && Math.abs(a[0] / a[1] - b[0] / b[1]) < 1e-9;
/** An assembly sheet's iso view still where its layout put it (d.views.Iso: the right view's place, not moved by the
 *  user) — it follows a new layout. */
const isoLaid = (d) => { const a = d?.views?.Iso, b = d?.built?.layout?.views?.Right; return !!a && !!b && Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6; };
/** A circle of a hole step (its key has "<step>:hole:k" / ":cbore:k" / ":csk:k"; a pattern's copy "P1:2:H1:hole:0" too)
 *  -> [step id, 'hole' | 'head'], or null. */
const stepOf = (key) => { const m = /(?:^|[+:])([^:+]+):(hole|cbore|csk):\d+/.exec(key || ''); return m ? [m[1], m[2] === 'hole' ? 'hole' : 'head'] : null; };
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');

/** 4 × 4 placement matrices (column-major, as three.js keeps them): a · b. */
const mul4 = (a, b) => { const o = new Array(16).fill(0); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]; return o; };
const ID4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const post = async (url, body) => { const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); const r = await res.json(); if (!res.ok) throw new Error(r.error || res.statusText); return r; };

/** A logo picture -> a small data URL for the title block (a PNG / JPEG scaled to at most 600 × 300 px; an SVG as it
 *  is, when small). */
async function logoData(file) {
  const url = await new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => bad(new Error(t('The picture could not be read.'))); r.readAsDataURL(file); });
  if (/^data:image\/svg\+xml/.test(url)) { if (url.length > 300000) throw new Error(t('The logo is too big — use a smaller picture.')); return url; }
  const img = await new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => bad(new Error(t('The picture could not be read.'))); i.src = url; });
  const k = Math.min(1, 600 / img.width, 300 / img.height), c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(img.width * k));
  c.height = Math.max(1, Math.round(img.height * k));
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/png');
}

/** A short hash of what a sheet is made from: the part's steps, material and tolerances. */
export function partHash(data) {
  const s = JSON.stringify({ f: stepsAtBar(data), m: data?.material || '', t: data?.tolerance || '' }); // (⏮ drawn as its rollback bar stands)
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
    this.selView = null; // the chosen view (a click on it), or
    this.selGeo = null;  // the chosen edge / circle of a view {view, edge | c}, or
    this.selTitle = false; // the title block — each with its row of suggestions (sheetsuggest.js)
    this.tool = 'select'; // or 'dim' (＋ Dimension)
    this.pick = null;    // the first point of a new dimension {view, key}
    this.zoom = { k: 1, x: 0, y: 0 };
    this.history = new History({
      capture: () => ({ section: !!this.d?.section, balloons: this.d?.balloons, views: this.d?.views, off: this.d?.off, dims: this.d?.dims, hidden: this.d?.hidden, user: this.d?.user, preset: this.d?.preset, vpreset: this.d?.vpreset, paper: this.d?.paper, texts: this.d?.texts, setTexts: this.d?.setTexts, exploded: !!this.d?.exploded, viewNames: this.d?.viewNames, scale: this.d?.scale ?? null, vscale: this.d?.vscale, template: this.d?.template, tb: this.d?.tb, frame: this.d?.frame, bomPage: this.d?.bomPage }),
      restore: (s) => { const ex = !!this.d.exploded, sec = !!this.d.section; Object.assign(this.d, structuredClone(s)); if (!this.d.exploded) delete this.d.exploded; if (!this.d.section) delete this.d.section; if (!this.d.bomPage) delete this.d.bomPage; if (ex !== !!this.d.exploded || sec !== !!this.d.section || this.d.built?.preset !== this.d.preset || this.d.built?.vp !== JSON.stringify(this.d.vpreset || {}) || this.layKey() !== this.builtKey()) this.ensure(true); else this.render(); },
      onChange: () => this.renderBar(),
    });
    this.build();
    window.addEventListener('a3d:lang', () => { if (this.d) this.render(); }); // (texts built with t(): in the new language)
    this.tpls = [DEFAULT_TPL];
    this.loadTemplates();
    fontsReady.then(() => { if (this.d) this.render(); }); // (the title-block styles' texts measured in their own fonts)
  }

  // ------------------------------------------------------------------ title-block templates (auto3d/title_templates.py)
  /** The templates kept on the server (the app's, then the user's) -> this.tpls. */
  async loadTemplates() {
    try {
      const r = await (await fetch('/api/title-templates')).json();
      if (Array.isArray(r.templates) && r.templates.length) this.tpls = r.templates;
      if (this.d) this.render();
    } catch { /* the server's are not there: Modern only */ }
  }

  /** The template a sheet uses: its own (d.template), else its drawing set's (the top assembly's sheet's), else Modern. */
  tplName(d = this.d) {
    if (d?.template) return d.template;
    const root = d?.source && this.hooks.drawingCtx ? this.rootOf(d.source) : null;
    return (root && root !== d.source && this.hooks.drawingCtx().sheetOf(root)?.template) || DEFAULT_TPL.name;
  }

  tplOf(d = this.d) { const n = this.tplName(d); return this.tpls.find((x) => x.name === n) || this.tpls[0] || DEFAULT_TPL; }

  /** How a sheet's title block looks: its template, changed on this sheet by d.tb {titleStyle, bomStyle, hide, logo}.
   *  style: the title block's — block / strip (the app's Modern) or A … E (tbstyles.js); bomStyle: the parts list's —
   *  modern or A … E. (layout: block / strip as before, from older sheets and templates.) */
  tbOf(d = this.d) {
    const tp = this.tplOf(d), own = d?.tb || {};
    const style = [own.titleStyle, own.layout, tp.titleStyle, tp.layout].find((s) => s && (s === 'block' || s === 'strip' || isStyle(s))) || 'block';
    const bomStyle = [own.bomStyle, tp.bomStyle].find((s) => s === 'modern' || isBomStyle(s)) || 'modern';
    return { style, bomStyle, layout: style === 'strip' ? 'strip' : 'block', hide: new Set(own.hide || tp.hide || []), texts: tp.texts || {}, logo: own.logo !== undefined ? own.logo : tp.logo || null };
  }

  /** The title block's height (mm): a block 38, a strip 14, a style's own (A 21, B 40, C 34, D 28, E 56). */
  titleH(d = this.d) { const s = this.tbOf(d).style; return titleSize(s)?.[1] ?? (s === 'strip' ? 14 : 38); }

  /** 💾 Save as template…: the title block as this sheet shows it (layout, fields, fixed texts, logo, frame) under a
   *  name, kept on the server for every project; this sheet then uses it. */
  async saveTemplate(name = null) {
    const tp = this.tplOf(), own = name || await ask(t('Name of the title-block template'), tp.builtin ? t('My template') : tp.name, { hint: t('Kept for all your projects: its layout, the fields shown, the company, address, drawn by, note, tolerance standard, logo and frame.'), ok: 'Save' });
    if (!own) return null;
    const tb = this.tbOf(), X = this.d.texts || {}, texts = { ...tb.texts };
    for (const k of TPL_TEXTS) if (X[k] !== undefined) texts[k] = X[k];
    const body = { template: { name: own, layout: tb.layout, titleStyle: tb.style, bomStyle: tb.bomStyle, hide: [...tb.hide], texts, logo: tb.logo, frame: this.frameOf() } };
    const r = await post('/api/title-templates', body);
    this.tpls = r.templates;
    this.d.template = r.template.name;
    delete this.d.tb;
    delete this.d.frame; // (the template holds it now)
    const keep = { ...(this.d.texts || {}) };
    for (const k of TPL_TEXTS) delete keep[k];
    this.d.texts = keep;
    this.commit();
    this.hooks.toast?.(tv('Saved the title-block template “{name}”.', { name: r.template.name }), 'ok', 4000);
    return r.template.name;
  }

  /** Use a template on this sheet (its own changes of the title block dropped). */
  useTemplate(name) {
    if (!this.tpls.some((x) => x.name === name)) throw new Error(`No template ${name} — one of: ${this.tpls.map((x) => x.name).join(', ')}.`);
    this.d.template = name;
    delete this.d.tb;
    delete this.d.frame;
    this.history.commit();
    this.render();
    this.hooks.onChange?.();
    this.ensure();
  }

  /** Use for all drawings of this assembly: the template on every sheet of the drawing set this sheet is in (the top
   *  assembly's sheet made when it has none — new sheets of the set take it from there) -> how many sheets. */
  async useTemplateForSet(name = this.tplName()) {
    const root = this.rootOf(this.d.source);
    if (!root) throw new Error(t('This drawing is not in an assembly\'s drawing set.'));
    if (this.ownStyles()) { name = await this.saveTemplate(); if (!name) return 0; } // (this drawing's own mix of styles: kept as a template first, so the set can take it)
    this.useTemplate(name);
    const n = (await this.hooks.applyTemplate?.(root, name, this.pagesOf(root).map((p) => p.id))) || 0;
    this.hooks.toast?.(tv('Title block “{name}” on {n} drawing(s) of {asm} — new ones take it too.', { name, n, asm: this.hooks.partName(root) || root }), 'ok', 6000);
    return n;
  }

  async deleteTemplate(name) {
    const r = await fetch(`/api/title-templates/${encodeURIComponent(name)}`, { method: 'DELETE' }), j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    this.tpls = j.templates;
    if (this.d.template === name) delete this.d.template;
    this.commit();
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
    document.addEventListener('click', (e) => { if (!e.target.closest?.('.sh-vmenu')) this.closeViewMenus(); });
  }

  // ------------------------------------------------------------------ the sheet as a project part
  async load(data) {
    this.endEdit(false);
    this.dropAsk();
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
    this.clearSel();
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
    const inside = (data.instances || []).map((it) => [it.part, it.matrix, seen.has(it.part) ? '' : this.sourceHash(it.part, seen), ...(it.inner ? [it.inner] : [])]);
    const base = this.baseOf(id); // (another base part: other mounting holes; the first one's sheets keep their hash)
    return partHash({ features: inside, ...(base && base !== data.instances?.[0]?.id ? { base } : {}) });
  }

  /** The part an assembly stands on — its free holes are dimensioned (the mounting holes): the one fixed in place 📌,
   *  else the one most joints are made onto, else the first placed (not a screw / pin) -> its instance id or null. */
  baseOf(aid) {
    const data = this.hooks.partData(aid) || {}, insts = (data.instances || []).filter((it) => !it.fastener);
    const fixed = insts.find((it) => it.fixed);
    if (fixed) return fixed.id;
    const n = new Map();
    for (const m of data.mates || []) n.set(m.onto, (n.get(m.onto) || 0) + 1);
    return insts.reduce((a, it) => (!a || (n.get(it.id) || 0) > (n.get(a.id) || 0) ? it : a), null)?.id ?? null;
  }

  async ensure(force = false) {
    const src = this.hooks.partData(this.d.source);
    if (!src) { this.render(); return; }
    const asm = this.hooks.kindOf?.(this.d.source) === 'assembly';
    const h = this.sourceHash(this.d.source);
    const vp = JSON.stringify(this.d.vpreset || {});
    if (!force && this.d.built && !this.d.built.stale && this.d.hash === h && !!this.d.built.section === !!this.d.section && this.d.built.preset === this.d.preset && this.d.built.vp === vp && (this.d.built.paper ?? null) === (this.d.paper ?? null) && this.builtKey() === this.layKey()) return;
    // the same drawing already being made: wait for it (not a second job); cancelled: not made again on its own —
    // ↻ Try again or a change makes it
    const want = JSON.stringify([this.d.source, h, this.d.preset, vp, this.d.paper ?? null, !!this.d.section, this.layKey(), !!this.d.exploded]);
    if (!force && this.making?.want === want) return this.making.done;
    if (!force && this.cancelled === want) { this.render(); return; }
    let finish;
    this.making = { want, done: new Promise((ok) => { finish = ok; }) };
    const making = this.making;
    try { await this.make(asm, h, vp, src, want); } finally {
      if (this.making === making) this.making = null;
      finish();
    }
  }

  async make(asm, h, vp, src, want) {
    this.busy = true;
    this.error = null;
    this.render();
    const run = (this.buildRun = (this.buildRun || 0) + 1); // (a newer build on its way wins)
    const rid = `sh${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`, stop = this.hooks.progress?.(rid, t('Making the drawing…'));
    try {
      let r;
      if (asm) { // an assembly: its views, overall sizes, parts list and balloons
        const pg = await this.assemblyPage(this.d.source, this.hooks.drawingCtx(), this.d.exploded ? 2 : 0, this.d, rid);
        r = pg.built;
        this.d.asm = { rows: pg.rows };
        if (!this.d.asmLaid) { this.d.off = { ...this.d.off, Right: true }; this.d.views = { ...this.d.views, Iso: r.layout.views.Right }; this.d.asmLaid = true; }
        else if (!this.d.views?.Iso || isoLaid(this.d)) this.d.views = { ...this.d.views, Iso: r.layout.views.Right }; // (not moved by the user: where the new layout puts it)
      } else {
        const res = await fetch('/api/sheet/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part: src, preset: this.d.preset, paper: this.d.paper, per_view: this.d.vpreset || {}, section: !!this.d.section, ...this.layReq(), rid }) });
        r = await res.json();
        if (!res.ok) throw new Error(r.error || res.statusText);
      }
      if (run !== this.buildRun) return;
      if (this.d.hash && this.d.hash !== h) { this.d.rev += 1; this.d.changed = new Date().toISOString(); } // the part changed
      Object.assign(this.d, { built: { ...r, preset: this.d.preset, vp, paper: this.d.paper ?? null, section: !!this.d.section && !asm, lk: this.layKey() }, hash: h });
      this.error = null;
      this.cancelled = null;
    } catch (e) {
      if (run !== this.buildRun) return;
      this.error = e.message;
      if (/^cancelled/i.test(e.message)) { this.cancelled = want; if (this.geo) this.hooks.toast?.(t('Cancelled — the drawing was not made.'), 'info', 5000); }
      const again = this.toasted?.msg === e.message && performance.now() - this.toasted.at < 5000; // (opening runs it twice)
      if (!/^cancelled/i.test(e.message) && !again) this.hooks.toast?.(tv('The drawing could not be made: {e}', { e: t(e.message) }), 'error', 9000);
      this.toasted = { msg: e.message, at: performance.now() };
    } finally { stop?.(); }
    this.busy = false;
    this.render();
    this.hooks.onChange?.();
    if (!this.error && this.relaid()) this.replace(); // (made for the layout's places: the user's moved views placed for)
  }

  // ------------------------------------------------------------------ geometry on the paper
  get lay() { return this.d.built?.layout; }
  get geo() { return this.d.built?.geometry; }
  scale() { const s = this.lay?.scale || [1, 1]; return s[0] / s[1]; }

  /** The sheet's scale [a, b]: its own (d.scale) or the fit's. */
  scaleArr() { return this.d.scale || this.lay?.scale || [1, 1]; }

  /** A view's scale (paper mm per part mm): its own (d.vscale) or the sheet's. */
  vs(v) { const s = this.d.vscale?.[v]; return s ? s[0] / s[1] : this.scale(); }

  /** What the server's layout is made for: the sheet's own scale (and frame) — built again when it changes. */
  layKey(d = this.d) { const th = this.titleH(d), m = this.frameOf(d).m, dm = m.every((v) => v === 10), k = this.keepOut(d); return JSON.stringify({ s: d.scale || null, ...(th !== 38 ? { th } : {}), ...(dm ? {} : { m }), ...(k ? { k } : {}) }); }
  builtKey(d = this.d) { return d.built?.lk ?? JSON.stringify({ s: null }); }
  layReq(d = this.d) {
    const th = this.titleH(d), m = this.frameOf(d).m, dm = m.every((v) => v === 10), keep = this.keepOut(d);
    return { ...(d.scale ? { scale: scaleText(d.scale) } : {}), ...(th !== 38 || !dm || keep ? { frame: { title: th, m, ...(keep ? { keep, iso_at: 'Right' } : {}) } } : {}) };
  }

  /** An assembly sheet's keep-out for the layout (sheet.py _keep): its title block and the parts list on it as drawn
   *  there (rows past "… n more" are on the BOM page) — {paper: [[w, h], …] mm at the frame's bottom-right corner, h
   *  from the frame's bottom}; the views keep off their union. null: a part's sheet (its title block's band is left free). */
  keepOut(d = this.d) {
    if (this.hooks.kindOf?.(d.source) !== 'assembly') return null;
    const n = new Set((this.hooks.partData(d.source)?.instances || []).map((it) => it.part)).size;
    if (!n) return null;
    const out = {};
    for (const p of d.paper ? [d.paper] : ['A4', 'A3']) out[p] = this.listKeep(d, ...PAPER[p], n);
    return out;
  }

  /** The title block's and the parts list's rectangles [[w, h], [w, h]] (mm) on paper pw × ph with n rows — as asmSvg /
   *  asmStyled draw them. */
  listKeep(d, pw, ph, n) {
    const [, mt, , mb] = this.frameOf(d).m, th = this.titleH(d), tb = this.tbOf(d), tw = titleSize(tb.style)?.[0] ?? (pw >= 400 ? 180 : 150);
    if (isBomStyle(tb.bomStyle)) {
      const fit = bomRowsIn(tb.bomStyle, ph - mt - mb - th - 40), lines = n > fit ? Math.max(1, fit - 1) + 1 : n;
      return [[tw, th], [bomWidth(tb.bomStyle), th + bomHeight(tb.bomStyle, lines)]].map((r) => r.map((v) => +v.toFixed(2)));
    }
    const max = Math.max(1, Math.floor((ph - mt - mb - th - 40) / 5) - 1), lines = Math.min(n, max) + (n > max ? 1 : 0);
    return [[tw, th], [isStyle(tb.style) ? Math.max(tw, pw >= 400 ? 180 : 150) : tw, th + (lines + 1) * 5 + 1]];
  }

  /** The keep-out on this sheet's paper as rectangles [x0, y0, x1, y1] (y down) — a view over them: ⚠ (outside). */
  keepRects() {
    const k = this.lay && this.keepOut()?.[this.lay.paper], [pw, ph] = this.lay?.size || [0, 0], [, , mr, mb] = this.frameOf().m;
    return (k || []).map(([w, h]) => [pw - mr - w, ph - mb - h, pw - mr, ph - mb]);
  }

  /** The sheet's frame: its own (d.frame), else its title-block template's, else Simple (10 mm, 0.5 mm line). */
  frameOf(d = this.d) {
    const f = d?.frame || this.tplOf(d).frame || FRAMES.simple;
    if (f.preset !== 'custom' && FRAMES[f.preset]) return FRAMES[f.preset];
    const m = (Array.isArray(f.m) ? f.m : [f.m ?? 10]).map((v) => Math.max(0, Math.min(40, +v || 0)));
    return { preset: 'custom', m: [0, 1, 2, 3].map((i) => m[i] ?? m[0]), line: Math.max(0, Math.min(2, +(f.line ?? 0.5))), zones: !!f.zones, marks: !!f.marks };
  }

  /** The frame (ISO 5457): its line at the margins; zones — numbers across the top and bottom, letters down the sides,
   *  about 50 mm each, in the margins with short ticks between them; centring marks from the paper's edge 5 mm into the
   *  frame at the middle of each side. None: nothing. */
  frameSvg(pw, ph) {
    const f = this.frameOf(), [l, tp, r, b] = f.m, x1 = pw - r, y1 = ph - b, w = x1 - l, h = y1 - tp, lw = f.line;
    if (!lw) return '';
    const g = [`<g class="sh-frame"><rect x="${l}" y="${tp}" width="${w}" height="${h}" fill="none" stroke="#000" stroke-width="${lw}" data-frame="1"/>`];
    if (f.zones) {
      const even = (n) => Math.max(2, Math.round(n / 2) * 2), nx = even(w / 50), ny = even(h / 50), fs = 2.5;
      const out = (m) => Math.min(5, m); // (the ticks and letters in the margin, at most 5 mm out)
      for (let i = 0; i < nx; i++) {
        const xa = l + (w * i) / nx, xc = l + (w * (i + 0.5)) / nx;
        if (i) for (const [y, o] of [[tp, -out(tp)], [y1, out(b)]]) g.push(`<line x1="${xa}" y1="${y}" x2="${xa}" y2="${y + o}" stroke="#000" stroke-width="0.25"/>`);
        if (tp >= 3.5) g.push(`<text x="${xc}" y="${tp - out(tp) / 2 + fs * 0.35}" font-size="${fs}" text-anchor="middle" fill="#000">${i + 1}</text>`);
        if (b >= 3.5) g.push(`<text x="${xc}" y="${y1 + out(b) / 2 + fs * 0.35}" font-size="${fs}" text-anchor="middle" fill="#000">${i + 1}</text>`);
      }
      for (let i = 0; i < ny; i++) {
        const ya = tp + (h * i) / ny, yc = tp + (h * (i + 0.5)) / ny, letter = 'ABCDEFGHJKLMNPRSTUVWXYZ'[i] || '?';
        if (i) for (const [x, o] of [[l, -out(l)], [x1, out(r)]]) g.push(`<line x1="${x}" y1="${ya}" x2="${x + o}" y2="${ya}" stroke="#000" stroke-width="0.25"/>`);
        if (l >= 3.5) g.push(`<text x="${l - out(l) / 2}" y="${yc + fs * 0.35}" font-size="${fs}" text-anchor="middle" fill="#000">${letter}</text>`);
        if (r >= 3.5) g.push(`<text x="${x1 + out(r) / 2}" y="${yc + fs * 0.35}" font-size="${fs}" text-anchor="middle" fill="#000">${letter}</text>`);
      }
    }
    if (f.marks) {
      const mx = (l + x1) / 2, my = (tp + y1) / 2, sw = Math.max(0.5, lw);
      for (const [xa, ya, xb, yb] of [[mx, 0, mx, tp + 5], [mx, ph, mx, y1 - 5], [0, my, l + 5, my], [pw, my, x1 - 5, my]]) g.push(`<line x1="${xa}" y1="${ya}" x2="${xb}" y2="${yb}" stroke="#000" stroke-width="${sw}"/>`);
    }
    g.push('</g>');
    return g.join('');
  }

  /** Set the sheet's frame: a preset's name, or a custom one {m, line, zones, marks} — the views placed again. */
  setFrame(f) {
    this.d.frame = typeof f === 'string' ? { preset: f } : { preset: 'custom', ...this.frameOf(), ...f, ...(f.preset ? {} : { preset: 'custom' }) };
    this.d.views = {};
    this.history.commit();
    this.render();
    this.ensure();
  }

  /** The right panel's Frame: a preset choice; Custom… shows its margins, line, zones and centring marks. */
  framePanel() {
    const f = this.frameOf(), own = !!this.d.frame, tip = Object.fromEntries(FRAME_CHOICES.map(([k, , h]) => [k, h]));
    const num = (k, label, v, max) => `<label class="sh-fnum" title="${esc(t(label))} (mm)"><span>${esc(t(label))}</span><input type="number" min="0" max="${max}" step="0.5" data-fr="${k}" value="${v}"></label>`;
    return `<h3>${esc(t('Frame'))}</h3>
      <div class="field"><label>${esc(t('Frame'))}</label><select data-k="frame" title="${esc(t('The border line and the margins of the paper — kept in the title-block template, so a drawing set follows it'))}">${FRAME_CHOICES.map(([k, l]) => `<option value="${k}" ${f.preset === k ? 'selected' : ''} title="${esc(t(tip[k]))}">${esc(t(l))}</option>`).join('')}</select></div>
      <p class="hint">${esc(t(tip[f.preset] || ''))}${own ? '' : ` ${t('(from the title-block template)')}`}</p>
      ${f.preset === 'custom' ? `<div class="sh-fgrid">${num('l', 'Left', f.m[0], 40)}${num('t', 'Top', f.m[1], 40)}${num('r', 'Right', f.m[2], 40)}${num('b', 'Bottom', f.m[3], 40)}${num('line', 'Line', f.line, 2)}</div>
        <div class="sh-fchecks"><label class="check" title="${esc(t('Grid references along the edges: numbers across, letters down (ISO 5457)'))}"><input type="checkbox" data-fr="zones" ${f.zones ? 'checked' : ''}> ${esc(t('Zones'))}</label>
        <label class="check" title="${esc(t('Short thick lines at the middle of each side, for copying and folding'))}"><input type="checkbox" data-fr="marks" ${f.marks ? 'checked' : ''}> ${esc(t('Centring marks'))}</label></div>` : ''}`;
  }

  bindFramePanel(box) {
    box.querySelector('[data-k=frame]')?.addEventListener('change', (e) => this.setFrame(e.target.value === 'custom' ? { ...this.frameOf(), preset: 'custom', line: this.frameOf().line || 0.5 } : e.target.value)); // (Custom… from None: a line to start from)
    for (const el of box.querySelectorAll('[data-fr]')) {
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => {
        const f = this.frameOf(), k = el.dataset.fr, m = [...f.m];
        if (k === 'zones' || k === 'marks') { this.setFrame({ [k]: el.checked }); return; }
        const v = Math.max(0, parseFloat(el.value) || 0);
        if (k === 'line') { this.setFrame({ line: Math.min(2, v) }); return; }
        m['ltrb'.indexOf(k)] = Math.min(40, v);
        this.setFrame({ m });
      });
    }
  }

  /** A page's sheet data as drawn (a drawing set's page: what its set gives it). */
  pageData(d) { return d; }

  /** A scale choice (a <select>): `none` first ("as the sheet (1:2)" / "Auto (1:1)"), the standard scales, the one
   *  chosen when it is not standard, Custom… */
  scaleSelect(attr, now, none, title) {
    const std = SCALE_LIST.some((s) => sameScale(s, now));
    return `<select ${attr} title="${esc(title)}"><option value="">${esc(none)}</option>${SCALE_LIST.map((s) => `<option value="${scaleText(s)}" ${now && sameScale(s, now) ? 'selected' : ''}>${scaleText(s)}</option>`).join('')}
      ${now && !std ? `<option value="${scaleText(now)}" selected>${scaleText(now)}</option>` : ''}<option value="custom">${esc(t('Custom…'))}</option></select>`;
  }

  /** The value of a scale choice -> [a, b], null (as the sheet / auto) or undefined (Custom… cancelled). */
  async scaleFrom(sel, now) {
    if (sel.value !== 'custom') return sel.value ? parseScale(sel.value) : null;
    const v = await ask(t('Scale (paper : part), e.g. 1:2522 or 3:1'), now ? scaleText(now) : '1:1', { placeholder: '1:2', check: (x) => (parseScale(x) ? '' : t('Write it as two numbers, e.g. 1:2 or 3:1.')) });
    if (v === null) { sel.value = now ? scaleText(now) : ''; return undefined; }
    return parseScale(v);
  }

  /** Set the sheet's own scale (null: the automatic fit) — the views placed for it again. */
  async setSheetScale(s) {
    if (s) this.d.scale = s; else delete this.d.scale;
    this.d.views = {};
    this.history.commit();
    await this.ensure(true);
  }

  /** Set a view's own scale (null: the sheet's). */
  setViewScale(v, s) {
    const vs = { ...(this.d.vscale || {}) };
    if (s) vs[v] = s; else delete vs[v];
    this.d.vscale = vs;
    this.commit();
    this.replace();
  }

  /** Has the user moved a view, or given one its own scale? (Then the server's placing is for another layout.) */
  relaid() {
    return Object.keys(this.d.vscale || {}).length > 0 || this.drawn().some((v) => this.d.views[v] && this.lay?.views[v] && Math.hypot(this.d.views[v][0] - this.lay.views[v][0], this.d.views[v][1] - this.lay.views[v][1]) > 0.01);
  }

  /** A view moved by hand or at its own scale: the holes' positions and callouts placed clear again where the views
   *  are now (sheet.py place) — the automatic ones; a dimension the user moved stays where they put it. */
  async replace() {
    const b = this.d.built, G = this.geo;
    if (!b?.dims?.some((d) => d.pos || d.kind === 'dia' || d.kind === 'pcd') || !G) return;
    const views = Object.fromEntries(this.drawn().filter((v) => G.views[v] && this.centre(v)).map((v) => [v, this.centre(v)]));
    const slim = { iso: this.isoBox ? 1 : 0, holes: G.holes || {}, views: Object.fromEntries(Object.keys(views).map((v) => [v, { box: G.views[v].box, points: G.views[v].points, circles: G.views[v].circles, rings: G.views[v].rings || [], lines: [] }])) };
    const ib = this.isoBox, iso = ib ? [(ib[0] + ib[2]) / 2, (ib[1] + ib[3]) / 2, Math.max(ib[2] - ib[0], ib[3] - ib[1])] : null;
    let r;
    try { r = await post('/api/sheet/place', { geometry: slim, layout: { ...this.lay, views, iso, scale: this.scaleArr(), vscale: this.d.vscale || {} }, dims: b.dims }); } catch { return; }
    if (this.d.built !== b) return; // (built again meanwhile)
    b.dims = r.dims; // (an off view's: as they were)
    this.render();
    this.hooks.onChange?.();
  }

  /** Rename a view ('' or its standard name: back to that). */
  setViewName(v, name) {
    const n = String(name || '').trim().slice(0, 40), names = { ...(this.d.viewNames || {}) };
    if (!n || n === (v === 'Section' ? t('Section A–A') : t(v))) delete names[v]; else names[v] = n;
    this.d.viewNames = names;
    this.commit();
  }

  /** A view's label on the sheet made a text field over it (a double-click): Enter / leaving keeps it, Esc not. */
  renameOnSheet(v) {
    const lab = this.svgEl?.querySelector(`[data-vlabel="${v}"]`);
    if (!lab) return;
    const r = lab.getBoundingClientRect(), inp = document.createElement('input');
    inp.className = 'sh-rename';
    inp.value = this.viewName(v);
    inp.title = t('The view\'s name — Enter keeps it, Esc goes back; empty: its standard name');
    Object.assign(inp.style, { left: `${r.left + r.width / 2 - 80}px`, top: `${r.top - 4}px` });
    document.body.appendChild(inp);
    let done = false;
    const finish = (keep) => { if (done) return; done = true; const val = inp.value; inp.remove(); if (keep) this.setViewName(v, val); };
    inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false); });
    inp.addEventListener('blur', () => finish(true));
    setTimeout(() => { inp.focus(); inp.select(); }, 0);
  }

  /** A view's name on the sheet: the user's (d.viewNames) or its standard one ("Front", "Section A–A"). */
  viewName(v) { return this.d.viewNames?.[v] || (v === 'Section' ? t('Section A–A') : t(v)); }

  /** Its label: the name, and its own scale when that is not the sheet's ("Detail B (2:1)"). */
  viewLabel(v) { const s = this.d.vscale?.[v]; return s && !sameScale(s, this.scaleArr()) ? `${this.viewName(v)} (${scaleText(s)})` : this.viewName(v); }

  /** The views that reach past the frame (paper mm), or on an assembly's sheet over its parts list / title block (one
   *  the user moved there) -> [names]: a warning, the sheet still draws them. */
  outside() {
    if (!this.lay || !this.geo) return [];
    const [pw, ph] = this.lay.size, [ml, mt, mr, mb] = this.frameOf().m, keep = this.keepRects();
    const off = (b) => b[0] < ml - 0.5 || b[1] < mt - 0.5 || b[2] > pw - mr + 0.5 || b[3] > ph - mb + 0.5
      || keep.some((r) => b[0] < r[2] - 0.5 && r[0] < b[2] - 0.5 && b[1] < r[3] - 0.5 && r[1] < b[3] - 0.5);
    const out = this.drawn().filter((v) => off(this.paperBox(v)));
    if (this.isoBox && !this.d.off.Iso && off(this.isoBox)) out.push('Iso');
    return out;
  }

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
    const [w0, w1] = span(ws);
    for (let w = Math.ceil(w0 / 2) * 2; w <= w1; w += 2) {
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
    const g = this.geo.views[v], [cx, cy] = this.centre(v), s = this.vs(v), b = g.box;
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

  /** A circle of view v by its key — or a bolt circle's ring (geometry rings: {key, c, r, n, step, keys}). */
  circleOf(v, key) { const g = this.geo.views[v]; return g?.circles.find((c) => c.key === key) || g?.rings?.find((c) => c.key === key) || null; }

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
    if (d.kind === 'dia' || d.kind === 'rad' || d.kind === 'pcd') { const c = this.circleOf(d.view, d.a); return c ? (d.kind === 'rad' ? c.r : 2 * c.r) : null; }
    const a = g.points[d.a], b = g.points[d.b];
    if (!a || !b) return null;
    return d.dir === 'h' ? Math.abs(b[0] - a[0]) : Math.abs(b[1] - a[1]);
  }

  /** A dimension's text: its size (dimCore), its tolerance after it, in brackets when it is a reference dimension. */
  dimText(d, v) {
    const s = `${this.dimCore(d, v)}${d.tol ? ` ${d.tol}` : ''}`;
    return d.ref ? `(${s})` : s;
  }

  dimCore(d, v) {
    if (d.kind === 'dia') return `${d.count > 1 ? `${d.count}× ` : ''}${d.thread || `Ø${fmt(v)}`}${d.post || ''}${d.hole ? this.calloutRest(d.hole) : ''}`; // (a threaded hole: M5)
    if (d.kind === 'rad') return `${d.count > 1 ? `${d.count}× ` : ''}R${fmt(v)}`;
    if (d.kind === 'ang') return `${fmt(+v.toFixed(1))}°`;
    if (d.kind === 'pcd') return `${t('PCD')} Ø${fmt(v)} · ${d.count}× ${fmt(d.step)}°${d.start != null ? ` (${fmt(d.start)}°)` : ''}`; // (a bolt circle: its Ø and the angle between its holes)
    if (d.ord) return fmt(v); // (an ordinate: the distance from the edge's 0)
    return `${d.pre || ''}${fmt(v)}`;
  }

  /** What a hole callout says after the hole's size (ISO 129; as sheet.py callout): its depth ↧ — THRU when it has
   *  neither a thread nor a head —, its head (⌴ Ø6 ↧ 3.2 a counterbore, ⌵ Ø5 × 90° a countersink), ▲ a teardrop. */
  calloutRest(step) {
    const h = this.geo?.holes?.[step];
    if (!h) return '';
    let out = (h.flat ? ` D${fmt(h.flat)}` : '') + (h.through ? (h.thread || h.head ? '' : ` ${t('THRU')}`) : ` ↧ ${fmt(h.depth)}`); // (D: a D hole's size across the flat)
    if (h.head === 'cbore') out += ` ⌴ Ø${fmt(h.head_d)} ↧ ${fmt(h.head_depth)}`;
    if (h.head === 'csk') out += ` ⌵ Ø${fmt(h.head_d)} × ${fmt(h.head_angle)}°`;
    return out + (h.teardrop ? ' ▲' : '');
  }

  /** A hole callout on a hole step's circle in view `v` (all that step's holes there: "4× …"), or null (not a hole). */
  calloutFor(v, key) {
    const s = stepOf(key), h = s && this.geo?.holes?.[s[0]], cs = h ? this.geo.views[v].circles.filter((c) => c.full && stepOf(c.key)?.[0] === s[0] && stepOf(c.key)[1] === 'hole') : [];
    if (!cs.length) return null;
    const c = cs.find((x) => x.key === key) || cs[0];
    return { view: v, kind: 'dia', a: c.key, count: cs.length, hole: s[0], ang: 45, len: 6, ...(h.thread ? { thread: h.thread } : {}), ...(h.fit ? { post: ` ${h.fit}` } : {}) };
  }

  // ------------------------------------------------------------------ drawing (one SVG for the screen and the PDF)
  /** The sheet as SVG (mm). forPrint: no selection, no hover marks. */
  svg(forPrint = false) {
    const L = this.lay, G = this.geo;
    if (!L || !G) return '';
    const [pw, ph] = L.size, m = L.margin, th = this.titleH();
    const out = [`<svg xmlns="${NS}" width="${pw}mm" height="${ph}mm" viewBox="0 0 ${pw} ${ph}" font-family="Helvetica">`,
      `<rect x="0" y="0" width="${pw}" height="${ph}" fill="#fff"/>`, this.frameSvg(pw, ph)];
    const pl = (v, pts) => pts.map((p) => this.P(v, p).map((q) => q.toFixed(3)).join(',')).join(' ');
    for (const v of this.drawn()) {
      const g = G.views[v], pb = this.paperBox(v);
      out.push(`<g data-view="${v}" class="sh-view">`);
      if (!forPrint) out.push(`<rect x="${pb[0] - 2}" y="${pb[1] - 2}" width="${pb[2] - pb[0] + 4}" height="${pb[3] - pb[1] + 4}" fill="#fff" fill-opacity="0" stroke="none" class="sh-vhit"/>`);
      if (g.hatch) out.push(this.hatchSvg(v, g.hatch)); // (a section: its cut faces hatched)
      for (const p of g.hidden) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#666" stroke-width="0.25" stroke-dasharray="1.5 1"/>`);
      for (const p of g.visible) out.push(`<polyline points="${pl(v, p)}" fill="none" stroke="#000" stroke-width="0.5" stroke-linejoin="round"/>`);
      for (const c of g.circles) { // a threaded hole seen round: a thin ¾ circle at its major Ø (ISO 6410), open top right
        const s = c.full && stepOf(c.key), thr = s && s[1] === 'hole' && G.holes?.[s[0]]?.thread, R = thr && parseFloat(thr.slice(1)) / 2;
        if (!R || R <= c.r) continue;
        const arc = Array.from({ length: 37 }, (_, k) => { const a = Math.PI / 2 + (k / 36) * 1.5 * Math.PI; return [c.c[0] + R * Math.cos(a), c.c[1] + R * Math.sin(a)]; });
        out.push(`<polyline points="${pl(v, arc)}" fill="none" stroke="#000" stroke-width="0.25" class="sh-thread"/>`);
      }
      // its name below the dimensions under it
      const below = Math.max(0, ...this.allDims().filter((d) => d.view === v && d.kind === 'linear' && d.dir === 'h' && d.side !== 't').map((d) => (d.off ?? 8) + (d.ord ? 1 + 3.2 * 0.6 * String(fmt(this.value(d) ?? 0)).length : 0)), // (an ordinate's value stands past its row)
        ...this.allDims().filter((d) => d.view === v && (d.kind === 'dia' || d.kind === 'rad')).map((d) => this.leaderEnd(d) - pb[3] - 2.5)); // (a callout's text under the view: the name below it)
      out.push(`<text x="${(pb[0] + pb[2]) / 2}" y="${pb[3] + below + 8}" font-size="3.5" text-anchor="middle" fill="#334" data-vlabel="${v}" class="sh-vlabel">${esc(this.viewLabel(v))}</text></g>`);
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
      const [x0, x1, y0, y1] = [...span(xs), ...span(ys)]; // (not Math.min(...xs): a big part's 100 000 points overflow the stack)
      const [cx, cy, size] = this.d.views.Iso ? [...this.d.views.Iso, L.iso[2]] : L.iso;
      const k = this.d.vscale?.Iso ? this.vs('Iso') : size / Math.max(x1 - x0, y1 - y0, 1e-6); // (fitted into its cell, or at its own scale)
      this.isoMap = { at: (q) => [cx + (q[0] - (x0 + x1) / 2) * k, cy - (q[1] - (y0 + y1) / 2) * k], c: [cx, cy] };
      this.isoBox = [cx - (x1 - x0) * k / 2, cy - (y1 - y0) * k / 2, cx + (x1 - x0) * k / 2, cy + (y1 - y0) * k / 2];
      out.push('<g data-view="Iso" class="sh-view">');
      if (!forPrint) out.push(`<rect x="${cx - (x1 - x0) * k / 2 - 2}" y="${cy - (y1 - y0) * k / 2 - 2}" width="${(x1 - x0) * k + 4}" height="${(y1 - y0) * k + 4}" fill="#fff" fill-opacity="0" class="sh-vhit"/>`);
      for (const p of G.iso) out.push(`<polyline points="${p.map((q) => `${(cx + (q[0] - (x0 + x1) / 2) * k).toFixed(3)},${(cy - (q[1] - (y0 + y1) / 2) * k).toFixed(3)}`).join(' ')}" fill="none" stroke="#333" stroke-width="0.3"/>`);
      if (this.d.viewNames?.Iso || this.d.vscale?.Iso) out.push(`<text x="${cx}" y="${cy + (y1 - y0) * k / 2 + 7}" font-size="3.5" text-anchor="middle" fill="#334" data-vlabel="Iso" class="sh-vlabel">${esc(this.viewLabel('Iso'))}</text>`);
      out.push('</g>');
    } else this.isoBox = null;
    if (!forPrint && this.guides?.length) for (const [x1, y1, x2, y2] of this.guides) out.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#1f6feb" stroke-width="0.25" stroke-dasharray="2 1.5" class="sh-guide"/>`);
    if (!forPrint) out.push(this.selSvg());
    this.zeros = new Set(); // (an ordinate row's 0: drawn once)
    for (const d of this.allDims()) out.push(this.dimSvg(d, forPrint));
    if (this.d.asm) out.push(this.asmSvg(pw, ph, m, th));
    if (this.d.bom) out.push(this.bomSvg(pw, ph, th));
    if (!forPrint && this.tool === 'dim') out.push(this.snapMarks());
    if (!forPrint && this.checked) for (const m of this.checked.missing) { // what is missing: an orange ?
      const q = this.P(m.view, m.at);
      out.push(`<g class="sh-miss"><circle cx="${q[0]}" cy="${q[1]}" r="2" fill="#f59e0b" opacity="0.85"/><text x="${q[0]}" y="${q[1] + 1.1}" font-size="2.8" text-anchor="middle" fill="#fff">?</text></g>`);
    }
    out.push(this.titleSvg(pw, ph, m, th));
    out.push('</svg>');
    return out.join('').replace(/<text (?!data-ff)/g, '<text font-family="Helvetica" '); // (the PDF's converter does not inherit a font; a style's texts say theirs)
  }

  /** Where a Ø / R leader's shelf is (paper y, mm) — as dimSvg draws it; -Infinity when its circle is gone. */
  leaderEnd(d) {
    const c = this.circleOf(d.view, d.a);
    if (!c) return -Infinity;
    const C = this.P(d.view, c.c), R = c.r * this.vs(d.view);
    const ang = (d.kind === 'rad' ? Math.atan2(-(c.pm[1] - c.c[1]), c.pm[0] - c.c[0]) * 180 / Math.PI + (d.ang || 0) : d.ang ?? 45) * Math.PI / 180;
    return C[1] - Math.sin(ang) * (R + (d.len ?? 6));
  }

  /** What is chosen, marked in blue (not printed): a view's box, an edge, a circle. */
  selSvg() {
    const B = '#1f6feb', out = [];
    if (this.selView) {
      const b = this.selView === 'Iso' ? this.isoBox : this.drawn().includes(this.selView) ? this.paperBox(this.selView) : null;
      if (b) out.push(`<rect x="${b[0] - 3}" y="${b[1] - 3}" width="${b[2] - b[0] + 6}" height="${b[3] - b[1] + 6}" fill="#1f6feb" fill-opacity="0.04" stroke="${B}" stroke-width="0.35" stroke-dasharray="2 1.2" rx="1"/>`);
    }
    const g = this.selGeo;
    if (g?.edge) { const a = this.P(g.view, g.edge.a), b = this.P(g.view, g.edge.b); out.push(`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${B}" stroke-width="1" stroke-linecap="round" opacity="0.85"/>`); }
    if (g?.c) { const C = this.P(g.view, g.c.c); out.push(`<circle cx="${C[0]}" cy="${C[1]}" r="${g.c.r * this.vs(g.view)}" fill="none" stroke="${B}" stroke-width="0.9" opacity="0.85"/>`); }
    return out.length ? `<g class="sh-selmark" pointer-events="none">${out.join('')}</g>` : '';
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
      const X = this.P(d.view, a.X), r = d.r ?? 15, s = this.vs(d.view);
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
    if (d.kind === 'dia' || d.kind === 'rad' || d.kind === 'pcd') {
      const c = this.circleOf(d.view, d.a);
      if (!c) return '';
      const C = this.P(d.view, c.c), R = c.r * this.vs(d.view);
      if (d.kind === 'pcd') g.unshift(`<circle cx="${C[0]}" cy="${C[1]}" r="${R}" fill="none" stroke="#000" stroke-width="0.18" stroke-dasharray="6 1.2 1 1.2" class="sh-pcd"/>`); // the pitch circle (dash-dot, ISO 128)
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
      if (d.ord) { g.push(this.ordSvg(d, A, B, pb, off, txt, col, fs, forPrint), '</g>'); return g.join(''); }
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

  /** An ordinate dimension: an extension line from its point to the row (off from the view's side) with a jog when its
   *  value is moved along the row (d.sh, paper mm: clear of its neighbour), the value past the row; the row's 0 at the
   *  edge it is measured from, once per row (this.zeros). */
  ordSvg(d, A, B, pb, off, txt, col, fs, forPrint) {
    const h = d.dir === 'h', k = h ? 0 : 1, sgn = d.side === 't' || d.side === 'l' ? -1 : 1;
    const at = h ? (d.side === 't' ? pb[1] - off : pb[3] + off) : (d.side === 'l' ? pb[0] - off : pb[2] + off), out = [];
    const leg = (p, sh, label, grab) => {
      const m = p[k] + sh, j = at - sgn * 2.5, cross = (u) => (h ? [p[0], u] : [u, p[1]]), along = (u) => (h ? [m, u] : [u, m]);
      const pts = [cross(p[1 - k] + sgn), ...(sh ? [cross(j), along(at)] : [cross(at)]), along(at + sgn * 0.6)];
      out.push(`<polyline points="${pts.map((q) => q.join(',')).join(' ')}" fill="none" stroke="${col}" stroke-width="0.15"/>`);
      const T = h ? [m + fs * 0.35, at + sgn] : [at + sgn, m + fs * 0.35], anchor = (sgn > 0) === h ? 'end' : 'start'; // (h: turned to read upwards)
      out.push(`<text x="${T[0]}" y="${T[1]}" font-size="${fs}" text-anchor="${anchor}" fill="${col}"${h ? ` transform="rotate(-90 ${T[0]} ${T[1]})"` : ''}>${label}</text>`);
      if (grab) { const L = label.length * fs * 0.6 + 1; out.push(`<rect x="${h ? m - fs * 0.6 : sgn > 0 ? at : at - L - 1}" y="${h ? (sgn > 0 ? at : at - L - 1) : m - fs * 0.6}" width="${h ? fs * 1.2 : L + 1}" height="${h ? L + 1 : fs * 1.2}" fill="#fff" fill-opacity="0" class="sh-grab"/>`); }
    };
    const z = `${d.view}|${d.dir}|${d.side}|${off}`;
    if (!this.zeros?.has(z)) { this.zeros?.add(z); leg(A, 0, '0', false); }
    leg(B, d.sh || 0, txt, !forPrint);
    return out.join('');
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
        if (/^(box|base)#/.test(k)) continue;
        const q = this.P(v, p), first = !this.pick?.edge && this.pick?.view === v && this.pick.key === k;
        out.push(`<circle cx="${q[0]}" cy="${q[1]}" r="${first ? 1.2 : 0.6}" fill="${first ? '#1f6feb' : '#f59e0b'}" opacity="${first ? 1 : 0.7}"/>`);
      }
    }
    return `${out.join('')}</g>`;
  }

  /** The title block's width (mm): 150 on A4, 180 (ISO 7200's) on A3; a style's own (A, B, C 180, D 170, E 90). */
  titleW() { return titleSize(this.tb().style)?.[0] ?? ((this.lay?.size?.[0] || 297) >= 400 ? 180 : 150); }

  /** The texts the title block of sheet `d` shows: its template's, then its drawing set's (the top assembly's sheet's
   *  setTexts — "Ano" of the question after an edit), then its own. */
  textsOf(d = this.d) { return { ...this.tbOf(d).texts, ...(d._set || this.setTextsOf(d)), ...(d.texts || {}) }; }

  /** The drawing set's texts for sheet `d` (the top assembly's sheet's setTexts) — {} outside a set. */
  setTextsOf(d = this.d) {
    const root = d?.source && this.hooks.drawingCtx ? this.rootOf(d.source) : null;
    if (!root) return {};
    if (this.d?.source === root) return this.d.setTexts || {};
    return this.sheetsOf(new Set([root]))[0]?.setTexts || {};
  }

  /** The sheets (their data; the one on screen: this.d) of the project whose part is one of `ids`. */
  sheetsOf(ids) {
    return (this.hooks.parts?.() || []).filter((q) => q.kind === 'sheet').map((q) => (q.data === 'live' ? this.d : q.data))
      .filter((d) => d && typeof d === 'object' && ids.has(d.source));
  }

  /** The material a sheet shows: an assembly's typed one, else the part's (an assembly: its parts' are in its list). */
  matOf(F) {
    const src = this.hooks.partData(this.d.source) || {}, T = this.d.title || {}, asm = !!this.d.asm && !this.d.bom;
    if (asm && F.material) return F.material;
    return T.material ?? (this.d.asm ? (src.material ? t(src.material) : '—') : t(src.material || 'PLA'));
  }

  /** The title block's fields as text, for the styles A … E (tbstyles.js titleBlock): what the sheet and its part
   *  say, its own texts over its set's and its template's; — where nothing is known. */
  tbFields() {
    const src = this.hooks.partData(this.d.source) || {}, T = this.d.title || {}, X = this.d.texts || {}, tb = this.tb(), F = this.textsOf();
    const cs = getLang() === 'cs', d0 = this.d.changed ? new Date(this.d.changed) : null, p2 = (v) => String(v).padStart(2, '0');
    const asm = !!this.d.asm, bom = !!this.d.bom, mat = this.matOf(F);
    const what = [T.kind || (asm ? t('Assembly') : t('Part')), T.of ? `${t('in')} ${T.of}` : '', T.pos ? `${t('Pos.')} ${T.pos}` : ''].filter(Boolean);
    if (!bom) what.push(t(asm ? 'assembly drawing' : 'production drawing'));
    let mass = null;
    if (bom) mass = this.d.bom.mass_g || null;
    else if (asm) { try { const b = bomOf(this.bomCtx(), this.d.source, {}); mass = b.mass_unknown ? null : b.mass_g || null; } catch { mass = null; } }
    else if (this.d.built?.volume && MATERIALS[src.material || 'PLA']) mass = (this.d.built.volume / 1000) * MATERIALS[src.material || 'PLA'];
    return {
      name: X.title || T.part || this.hooks.partName(this.d.source) || '—', kind: what.join(' · '), number: F.number || '', rev: `${this.d.rev}`,
      material: mat, mass: mass ? grams(mass) : '', scale: bom ? '' : scaleText(this.scaleArr()), paper: this.lay?.paper || '', sheet: T.sheet || '1 / 1',
      tol: src.tolerance ? `${(F.tolstd || 'ISO 2768').replace(/-[a-z]+$/i, '')}-${src.tolerance}` : F.tolstd || '', surface: F.surface || '',
      drawn: F.drawn || '', checked: F.checked || '', approved: F.approved || '', company: F.company || '',
      address: String(F.address || '').split(/\s*[\n;]\s*|,\s+(?=\d)/).filter(Boolean), logo: tb.logo,
      date: d0 ? (cs ? `${d0.getDate()}. ${d0.getMonth() + 1}. ${d0.getFullYear()}` : `${d0.getFullYear()}-${p2(d0.getMonth() + 1)}-${p2(d0.getDate())}`) : '',
      dateShort: d0 ? (cs ? `${d0.getDate()}.${d0.getMonth() + 1}.${String(d0.getFullYear()).slice(2)}` : `${d0.getFullYear()}-${p2(d0.getMonth() + 1)}-${p2(d0.getDate())}`) : '',
      ro: new Set(asm && !bom ? [] : ['material']),
    };
  }

  /** How the title block looks: {layout: 'block' | 'strip', hide: Set of fields, texts (fixed: company, address, drawn,
   *  note, tolstd), logo (a data URL) or null}. */
  tb() { return this.tbOf(this.d); }

  /** The title block (ISO 7200 fields), clean and light: the part's name large, small muted labels over readable
   *  values, thin rules only between rows and short ones between cells; a company / logo column on the left; one
   *  outline. Black on white (prints in black and white), inside the frame at its bottom right. */
  titleSvg(pw, ph, m, th) {
    const L = this.lay, [, , mr, mb] = this.frameOf().m, W = this.titleW(), x0 = pw - mr - W, y0 = ph - mb - th;
    if (isStyle(this.tb().style)) return titleBlock(this.tb().style, x0, y0, this.tbFields()); // (A … E: as the owner's designs)
    const src = this.hooks.partData(this.d.source) || {}, T = this.d.title || {}, X = this.d.texts || {}, tb = this.tb(), F = this.textsOf();
    const on = (f) => !tb.hide.has(f), INK = '#000', MUTED = '#555', THIN = 0.13, ro = new Set(this.d.asm && !this.d.bom ? [] : ['material']);
    const fit = (s, w, fs) => { s = String(s ?? ''); const n = Math.max(1, Math.floor(w / (fs * 0.53))); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };
    const tol = src.tolerance ? `${(F.tolstd || 'ISO 2768').replace(/-[a-z]+$/i, '')}-${src.tolerance}` : F.tolstd || '—';
    const day = (iso) => (iso ? new Date(iso).toISOString().slice(0, 10) : '—');
    const name = X.title || T.part || this.hooks.partName(this.d.source) || '—';
    const mat = this.matOf(F);
    const what = [T.kind || (this.d.asm ? t('Assembly') : t('Part')), T.of ? `${t('in')} ${T.of}` : '', T.pos ? `${t('Pos.')} ${T.pos}` : ''].filter(Boolean).join(' · ');
    const g = [`<g class="sh-title"><rect x="${x0}" y="${y0}" width="${W}" height="${th}" fill="#fff" stroke="${INK}" stroke-width="0.35"/>`];
    const hit = (key, x, y, w, h) => g.push(hitRect(key, x, y, w, h, ro));
    const cell = (label, value, x, y, w, h, fs = 2.9, key = null, bold = false) => {
      g.push(`<text x="${x + 1.6}" y="${y + 3.4}" font-size="1.75" fill="${MUTED}">${esc(label)}</text>`);
      g.push(`<text x="${x + 1.6}" y="${y + h - 2.2}" font-size="${fs}" fill="${INK}"${bold ? ' font-weight="bold"' : ''}>${esc(fit(value, w - 3, fs))}</text>`);
      if (key) hit(key, x, y, w, h);
    };
    const row = (y, h, x, w, items) => { // cells by their weights, short rules between them
      const sum = items.reduce((a, it) => a + it[2], 0);
      let cx = x;
      items.forEach(([label, value, wt, key, fs, bold], i) => {
        const cw = (w * wt) / sum;
        if (i) g.push(`<line x1="${cx}" y1="${y + 1.6}" x2="${cx}" y2="${y + h - 1.6}" stroke="${INK}" stroke-width="${THIN}"/>`);
        cell(label, value, cx, y, cw, h, fs || 2.9, key, bold);
        cx += cw;
      });
    };
    const appLine = 'Auto3DModeler · mm';
    if (tb.layout === 'strip') { // one row: name, material, scale, paper, drawing no., rev, sheet
      row(y0, th, x0, W, [[what, name, 2.6, 'title', 3.6, true], ...(on('material') ? [[t('Material'), mat, 1.3, 'material']] : []),
        [t('Scale'), this.d.bom ? '—' : scaleText(this.scaleArr()), 0.8, 'scale'], ...(on('paper') ? [[t('Paper'), L.paper, 0.6, 'paper']] : []),
        ...(on('number') ? [[t('Drawing no.'), F.number || '', 1.3, 'number']] : []), ['Rev', `${this.d.rev}`, 0.5, 'rev'], ...(T.sheet ? [[t('Sheet'), T.sheet, 0.8, 'sheet']] : [])]);
      g.push(`<text x="${x0 + W - 1.2}" y="${y0 - 1.2}" font-size="1.6" fill="${MUTED}" text-anchor="end">${esc(appLine)}</text>`);
      g.push('</g>');
      return g.join('');
    }
    // the company / logo column
    const C = on('company') ? Math.round(W * 0.23) : 0, xm = x0 + C, M = W - C;
    if (C) {
      let y = y0 + 3;
      if (tb.logo) { g.push(`<image x="${x0 + 2}" y="${y}" width="${C - 4}" height="${th * 0.42}" preserveAspectRatio="xMidYMid meet" href="${esc(tb.logo)}"/>`); y += th * 0.42 + 1; }
      if (F.company) { const cf = Math.max(2.1, Math.min(3, (C - 4) / (F.company.length * 0.5))); g.push(`<text x="${x0 + 2}" y="${y + 3.4}" font-size="${cf.toFixed(2)}" font-weight="bold" fill="${INK}">${esc(fit(F.company, C - 4, cf * 0.9))}</text>`); y += 4.6; }
      if (!F.company && !tb.logo) g.push(`<text x="${x0 + 2}" y="${y + 3.4}" font-size="2.6" font-weight="bold" fill="${MUTED}">Auto3DModeler</text><text x="${x0 + 2}" y="${y + 6.6}" font-size="1.9" fill="${MUTED}">${esc(t('Dimensions in mm'))}</text>`);
      for (const ln of String(F.address || '').split(/\s*[\n;]\s*|,\s+(?=\d)/).filter(Boolean).slice(0, tb.logo ? 2 : 4)) { g.push(`<text x="${x0 + 2}" y="${y + 2.4}" font-size="1.9" fill="${MUTED}">${esc(fit(ln, C - 4, 1.9))}</text>`); y += 2.8; }
      if (F.company || tb.logo) g.push(`<text x="${x0 + 2}" y="${y0 + th - 2.2}" font-size="1.7" fill="${MUTED}">${esc(appLine)}</text>`);
      g.push(`<line x1="${xm}" y1="${y0}" x2="${xm}" y2="${y0 + th}" stroke="${INK}" stroke-width="${THIN}"/>`);
      if (on('company')) { hit('company', x0, y0, C, th * 0.4); hit('address', x0, y0 + th * 0.4, C, th * 0.6); }
    }
    // the part: its name large; the drawing number on its right
    const hA = th * 0.44, hB = (th - hA) / 2, dn = on('number') ? M * 0.3 : 0;
    const nfs = Math.max(3.4, Math.min(6.2, (M - dn - 4) / (Math.max(name.length, 6) * 0.56)));
    g.push(`<text x="${xm + 1.6}" y="${y0 + 4.2}" font-size="2.1" fill="${MUTED}">${esc(fit(what, M - dn - 3, 2.1))}</text>`);
    g.push(`<text x="${xm + 1.6}" y="${y0 + hA - 3}" font-size="${nfs.toFixed(2)}" font-weight="bold" fill="${INK}">${esc(fit(name, M - dn - 3, nfs))}</text>`);
    hit('title', xm, y0, M - dn, hA);
    if (dn) {
      g.push(`<line x1="${xm + M - dn}" y1="${y0 + 1.6}" x2="${xm + M - dn}" y2="${y0 + hA - 1.6}" stroke="${INK}" stroke-width="${THIN}"/>`);
      cell(t('Drawing no.'), F.number || '', xm + M - dn, y0, dn, hA, 3.6, 'number', true);
      if (!C) g.push(`<text x="${x0 + W - 1.2}" y="${y0 - 1.2}" font-size="1.6" fill="${MUTED}" text-anchor="end">${esc(appLine)}</text>`);
    }
    g.push(`<line x1="${xm}" y1="${y0 + hA}" x2="${x0 + W}" y2="${y0 + hA}" stroke="${INK}" stroke-width="${THIN}"/>`);
    row(y0 + hA, hB, xm, M, [...(on('material') ? [[t('Material'), mat, 1.35, 'material']] : []), [t('Scale'), this.d.bom ? '—' : scaleText(this.scaleArr()), 0.8, 'scale'],
      ...(on('paper') ? [[t('Paper'), L.paper, 0.65, 'paper']] : []), ...(on('tolerances') ? [[t('Tolerances'), tol, 1.3, 'tolstd']] : []), ...(T.sheet ? [[t('Sheet'), T.sheet, 0.85, 'sheet']] : [])]);
    g.push(`<line x1="${xm}" y1="${y0 + hA + hB}" x2="${x0 + W}" y2="${y0 + hA + hB}" stroke="${INK}" stroke-width="${THIN}"/>`);
    row(y0 + hA + hB, hB, xm, M, [...(on('drawn') ? [[t('Drawn by'), F.drawn || '', 1.1, 'drawn']] : []), ...(on('created') ? [[t('Created'), day(this.d.created), 0.95, 'created']] : []),
      ...(on('changed') ? [[`${t('Changed')} · Rev`, `${day(this.d.changed)} · ${this.d.rev}`, 1.25, 'changed']] : []), ...(on('note') ? [[t('Note'), F.note || '', 1.7, 'note', 2.6]] : [])]);
    g.push('</g>');
    return g.join('');
  }

  /** An assembly's page: the parts list (pos, name, qty, material, part number) above the title block, and a balloon
   *  with its position for each in the iso view. */
  asmSvg(pw, ph, m, th) {
    const [, mt, mr, mb] = this.frameOf().m, tb = this.tb(), W = isStyle(tb.style) ? Math.max(this.titleW(), (this.lay?.size?.[0] || 297) >= 400 ? 180 : 150) : this.titleW();
    if (isBomStyle(tb.bomStyle)) return this.asmStyled(pw, ph, mt, mr, mb, th, tb.bomStyle);
    const rows = this.d.asm.rows, max = Math.max(1, Math.floor((ph - mt - mb - th - 40) / 5) - 1), shown = rows.slice(0, max);
    const x0 = pw - mr - W, cols = [[t('Pos.'), 0.08], [t('Name'), 0.42], [t('Qty'), 0.08], [t('Material'), 0.17], [t('Part number'), 0.25]].map(([l, k]) => [l, W * k]);
    const n = shown.length + (rows.length > max ? 1 : 0), top = ph - mb - th - (n + 1) * 5 - 1, g = ['<g class="sh-bom">'];
    // the parts list as the title block: one outline, the header's labels small and muted over a rule, thin rules between rows
    g.push(`<rect x="${x0}" y="${top}" width="${W}" height="${(n + 1) * 5 + 1}" fill="#fff" stroke="#000" stroke-width="0.35"/>`);
    const row = (y, cells, head) => {
      let x = x0;
      cells.forEach((v, i) => {
        const w = cols[i][1], num = i === 0 || i === 2, fs = head ? 1.9 : 2.8, n = Math.max(1, Math.floor((w - 2.4) / (fs * 0.53)));
        const s = String(v ?? ''), txt = s.length > n ? `${s.slice(0, n - 1)}…` : s;
        if (i && !head) g.push(`<line x1="${x}" y1="${y + 1}" x2="${x}" y2="${y + 4}" stroke="#000" stroke-width="0.13"/>`);
        g.push(`<text x="${num ? x + w / 2 : x + 1.6}" y="${y + (head ? 3.9 : 3.7)}" font-size="${fs}" fill="${head ? '#555' : '#000'}"${num ? ' text-anchor="middle"' : ''}${!head && i === 0 ? ' font-weight="bold"' : ''}>${esc(txt)}</text>`);
        x += w;
      });
      g.push(`<line x1="${x0}" y1="${y + (head ? 6 : 5)}" x2="${x0 + W}" y2="${y + (head ? 6 : 5)}" stroke="#000" stroke-width="${head ? 0.25 : 0.13}"/>`);
    };
    row(top, cols.map((c) => c[0]), true);
    shown.forEach((r, i) => row(top + 1 + 5 * (i + 1), [r.pos, `${r.kind === 'assembly' ? '◇ ' : ''}${r.name}`, r.qty, t(r.material), r.pn || (r.bought ? t('bought') : '')], false));
    if (rows.length > max) g.push(`<text x="${x0 + 1.6}" y="${top + 1 + 5 * (shown.length + 1) + 3.6}" font-size="2.6">… ${rows.length - max} ${t('more')}</text>`);
    return this.balloonsSvg(g, rows);
  }

  /** A parts-list row as a style shows it (tbstyles.js partsList): mass each, the standard / order no. (else that
   *  part's drawing no.), make or buy. r: a parts-list row of an assembly sheet or a BOM page's line. */
  styledRow(r, page = false) {
    const pd = this.hooks.partData(r.part) || {}, asm = r.kind === 'assembly', ctx = this.hooks.drawingCtx?.();
    const how = asm ? 'assembly' : r.how || makeBuy(pd, r.name).how, mass = r.mass_g !== undefined ? r.mass_g : asm ? null : ctx?.massOf?.(r.part) ?? null;
    return { pos: r.pos ?? '', name: `${asm ? '◇ ' : ''}${r.name}`, qty: `${r.qty}`, total: `${r.total ?? ''}`, mat: asm || !r.material ? '' : t(r.material), bold: asm, depth: r.depth || 0,
      mass: asm ? '' : grams(mass), mass_total: asm ? '' : grams(r.mass_total_g), maker: r.maker || '', make: t({ bought: 'buy', 'made (3D print)': 'print 3D', made: 'make', assembly: 'assembly' }[how] || how),
      pn: r.pn || (page ? '' : ctx?.sheetOf?.(r.part)?.texts?.number || ''), mass_g: asm ? 0 : mass };
  }

  /** An assembly sheet's parts list in a style (A … E), directly on the title block at the frame's right; as many rows
   *  as fit (40 mm left for the views), then "… n more". */
  asmStyled(pw, ph, mt, mr, mb, th, style) {
    const rows = this.d.asm.rows, room = ph - mt - mb - th - 40, fit = bomRowsIn(style, room);
    const max = rows.length > fit ? Math.max(1, fit - 1) : rows.length, shown = rows.slice(0, max).map((r) => this.styledRow(r));
    const pieces = rows.reduce((a, r) => a + (+r.qty || 0), 0), masses = rows.map((r) => this.styledRow(r).mass_g);
    const mass = masses.every((m) => m !== null && m !== undefined) ? masses.reduce((a, m, i) => a + m * (+rows[i].qty || 0), 0) : 0;
    const { svg } = partsList(style, pw - mr, ph - mb - th, shown, { kinds: rows.length, pieces, mass: mass ? grams(mass) : '' }, { more: rows.length > max ? `… ${rows.length - max} ${t('more')}` : '' });
    return this.balloonsSvg(['<g class="sh-bom sh-bomstyled">', svg], rows);
  }

  /** The balloons of an assembly sheet's iso view (in g, the parts list's group) -> the group's SVG. */
  balloonsSvg(g, rows) {
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
        this.balloonAt[r.pos] = { at: b.map((v) => +v.toFixed(1)), end: p.map((v) => +v.toFixed(1)) }; // (the balloon, where its leader ends)
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
    const keep = this.d, at = this.balloonAt, template = this.tplName(d), _set = this.setTextsOf(d); // (its set's template and texts found while the sheet on screen is this.d)
    this.d = { views: {}, off: {}, dims: {}, hidden: [], user: [], rev: 1, ...d, template, _set };
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
  itemNumbers(root) { return numbersOf(this.bomCtx(), root); }

  /** What the BOM engine (assembly/bom.js) reads of the project; masses from the assembly's bodies when it has them. */
  bomCtx() {
    return { partData: (id) => this.hooks.partData(id), kindOf: (id) => this.hooks.kindOf?.(id), partName: (id) => this.hooks.partName(id) || id,
      massOf: (id) => this.hooks.drawingCtx?.().massOf?.(id) ?? null };
  }

  /** 📋 The BOM pages of assembly `aid` (its whole hierarchy rolled up: bom.js; positions as the set's balloons), on the
   *  paper and frame of its page (`built`), as many pages as its rows need. sd: its sheet's data (template, texts,
   *  bomPage: true | 'summary' | 'structured') -> [page data]. */
  bomPages(aid, sd, built, parent = '') {
    const mode = sd.bomPage === 'structured' ? 'structured' : 'summary', bom = bomOf(this.bomCtx(), aid, { mode, numbering: this.rootOf(aid) || aid });
    const [, ph] = built.layout.size, [, mt, , mb] = this.frameOf(sd).m, th = this.titleH(sd), bs = this.tbOf(sd).bomStyle;
    const per = isBomStyle(bs) ? Math.max(4, bomRowsIn(bs, ph - mb - th - mt - 4) - 1) // (a style's list on the title block, its own heading; a line for "… continued")
      : Math.max(4, Math.floor((ph - mb - th - 4 - (mt + 12) - 6.5) / BOM_ROW) - 1), lines = bom.lines, n = Math.max(1, Math.ceil(lines.length / per));
    const keep = ['template', 'tb', 'frame', 'texts', 'paper', 'scale', 'created', 'changed', 'rev', 'hash'];
    const base = Object.fromEntries(keep.filter((k) => sd[k] !== undefined).map((k) => [k, structuredClone(sd[k])]));
    return Array.from({ length: n }, (_, k) => ({ ...base, source: aid, off: { Front: true, Top: true, Right: true, Iso: true }, views: {}, dims: {}, hidden: [], user: [],
      built: { layout: built.layout, geometry: { views: {}, iso: [] }, dims: [], preset: 'light' },
      bom: { mode, lines: lines.slice(k * per, (k + 1) * per), page: k + 1, pages: n, kinds: bom.kinds, pieces: bom.pieces, mass_g: bom.mass_g, more: k + 1 < n },
      title: { kind: t('Bill of materials'), part: this.hooks.partName(aid) || aid, material: '—', of: parent } }));
  }

  /** A BOM page's table: the whole width inside the frame over the title block, in the parts list's style (one outline,
   *  muted header over a rule, thin rules between rows, the position bold, a sub-assembly's row bold and its parts
   *  indented in the structured one). */
  bomSvg(pw, ph, th) {
    if (isBomStyle(this.tb().bomStyle)) return this.bomPageStyled(pw, ph, th, this.tb().bomStyle);
    const B = this.d.bom, [ml, mt, mr] = this.frameOf().m, x0 = ml + 4, W = pw - mr - 4 - x0, structured = B.mode === 'structured';
    const cols = (structured ? [['Pos.', 0.05], ['Name', 0.27], ['Qty per parent', 0.07], ['Total qty', 0.06], ['Material', 0.11], ['Mass each (g)', 0.08], ['Maker', 0.1], ['Part number', 0.15], ['Make / buy', 0.11]]
      : [['Pos.', 0.05], ['Name', 0.3], ['Qty', 0.05], ['Material', 0.12], ['Mass each (g)', 0.08], ['Mass total (g)', 0.08], ['Maker', 0.1], ['Part number', 0.12], ['Make / buy', 0.1]]).map(([l, k]) => [t(l), W * k]);
    const NUM = new Set(structured ? [0, 2, 3, 5] : [0, 2, 4, 5]), g = ['<g class="sh-bompage">'], top = mt + 12;
    const kg = (v) => (v === null || v === undefined ? '' : String(+(+v).toFixed(2)));
    g.push(`<text x="${x0}" y="${mt + 8}" font-size="5" font-weight="bold" fill="#000">${esc(`${t('Bill of materials')} — ${this.hooks.partName(this.d.source) || ''}`)}</text>`);
    g.push(`<text x="${x0 + W}" y="${mt + 8}" font-size="2.6" fill="#555" text-anchor="end">${esc(`${t(structured ? 'Structured' : 'Summary')} · ${tv('{kinds} different part(s), {pieces} piece(s) in all', { kinds: B.kinds, pieces: B.pieces })}${B.pages > 1 ? ` · ${B.page} / ${B.pages}` : ''}`)}</text>`);
    const h = 6.5 + BOM_ROW * B.lines.length + (B.more ? BOM_ROW : 0);
    g.push(`<rect x="${x0}" y="${top}" width="${W}" height="${h}" fill="#fff" stroke="#000" stroke-width="0.35"/>`);
    const row = (y, cells, head, o = {}) => {
      let x = x0;
      cells.forEach((v, i) => {
        const w = cols[i][1], num = NUM.has(i), fs = head ? 2 : 2.8, ind = !head && i === 1 ? (o.depth || 0) * 3.5 : 0, n = Math.max(1, Math.floor((w - 2.4 - ind) / (fs * 0.53)));
        const str = String(v ?? ''), txt = str.length > n ? `${str.slice(0, n - 1)}…` : str, bold = !head && (i === 0 || (o.asm && i === 1));
        if (i && !head) g.push(`<line x1="${x}" y1="${y + 1}" x2="${x}" y2="${y + BOM_ROW - 1}" stroke="#000" stroke-width="0.13"/>`);
        g.push(`<text x="${num ? x + w / 2 : x + 1.6 + ind}" y="${y + (head ? 4.2 : 3.9)}" font-size="${fs}" fill="${head ? '#555' : '#000'}"${num ? ' text-anchor="middle"' : ''}${bold ? ' font-weight="bold"' : ''}>${esc(txt)}</text>`);
        x += w;
      });
      const yb = y + (head ? 6.5 : BOM_ROW);
      g.push(`<line x1="${x0}" y1="${yb}" x2="${x0 + W}" y2="${yb}" stroke="#000" stroke-width="${head ? 0.25 : 0.13}"/>`);
    };
    row(top, cols.map((c) => c[0]), true);
    B.lines.forEach((r, i) => {
      const asm = r.kind === 'assembly', how = asm ? t('assembly') : t(r.how);
      const cells = structured ? [r.pos ?? '', `${asm ? '◇ ' : ''}${r.name}`, r.qty, r.total, r.material ? t(r.material) : '', asm ? '' : kg(r.mass_g), r.maker || '', r.pn || '', how]
        : [r.pos ?? '', r.name, r.qty, r.material ? t(r.material) : '', kg(r.mass_g), kg(r.mass_total_g), r.maker || '', r.pn || '', how];
      row(top + 6.5 + BOM_ROW * i, cells, false, { depth: r.depth || 0, asm });
    });
    if (B.more) g.push(`<text x="${x0 + 1.6}" y="${top + 6.5 + BOM_ROW * B.lines.length + 3.9}" font-size="2.6" fill="#555">${esc(tv('… continued on the next page ({n} / {m})', { n: B.page + 1, m: B.pages }))}</text>`);
    g.push('</g>');
    return g.join('');
  }

  /** A BOM page in a parts-list style (A … E): the heading at the top of the frame, the table the whole width inside
   *  the frame, directly on the title block (B: its header at the bottom, the rows numbered bottom-up). */
  bomPageStyled(pw, ph, th, style) {
    const B = this.d.bom, [ml, , mr, mb] = this.frameOf().m, structured = B.mode === 'structured', W = pw - mr - ml;
    const title = `${t('Bill of materials')} — ${this.hooks.partName(this.d.source) || ''} · ${t(structured ? 'Structured' : 'Summary')}${B.pages > 1 ? ` · ${B.page} / ${B.pages}` : ''}`;
    const rows = B.lines.map((r) => this.styledRow(r, true));
    const more = B.more ? tv('… continued on the next page ({n} / {m})', { n: B.page + 1, m: B.pages }) : '';
    const list = partsList(style, pw - mr, ph - mb - th, rows, { kinds: B.kinds, pieces: B.pieces, mass: B.mass_g ? grams(B.mass_g) : '' }, { W, kind: structured ? 'structured' : 'summary', more, title, named: true });
    return `<g class="sh-bompage" data-style="${style}">${list.svg}</g>`;
  }

  async assemblyPage(aid, ctx, explode = 0, sd = null, rid = null) { // (sd: its sheet's data — its paper, scale, frame; rid: progress / Cancel)
    const flatten = (id, M = ID4, pre = '', inner = null) => (this.hooks.partData(id)?.instances || []).flatMap((it) => { // (inner: a sub-assembly's parts moved in this placement)
      const W = mul4(M, inner?.[it.id] || it.matrix || ID4), key = pre ? `${pre}/${it.id}` : it.id;
      if (ctx.kindOf(it.part) === 'assembly') return flatten(it.part, W, key, it.inner);
      return [{ id: key, part: { features: stepsAtBar(this.hooks.partData(it.part)) }, matrix: W }]; // (⏮ as its rollback bar stands)
    });
    const insts = this.hooks.partData(aid)?.instances || [];
    if (!insts.length) throw new Error(t('The assembly has no parts to draw.'));
    const r = await post('/api/sheet/assembly', { instances: flatten(aid), explode, base: this.baseOf(aid), ...(sd ? { paper: sd.paper || null, ...this.layReq(sd) } : {}), ...(rid ? { rid } : {}) }); // (explode: the iso view pulled apart)
    const groups = new Map();
    for (const it of insts) { if (!groups.has(it.part)) groups.set(it.part, []); groups.get(it.part).push(it.id); }
    const nums = this.itemNumbers(this.rootOf(aid) || aid); // (the set's numbers: the same part, the same number)
    // one balloon per item, on the copy that shows most (a sub-assembly: on the one of its parts that shows most), its
    // leader ending on a face of that part no other part hides (the server's spot; else the part's middle)
    const shows = (id) => {
      const ms = Object.entries(r.marks).filter(([k]) => k === id || k.startsWith(`${id}/`)).map(([, m]) => m);
      if (!ms.length) return null;
      const best = ms.reduce((a, m) => ((m.seen || 0) > (a.seen || 0) ? m : a));
      return { seen: ms.reduce((s, m) => s + (m.seen || 0), 0), iso: best.seen ? best.Iso : [ms.reduce((s, m) => s + m.Iso[0], 0) / ms.length, ms.reduce((s, m) => s + m.Iso[1], 0) / ms.length] };
    };
    const rows = [...groups].map(([part, ids], i) => {
      const pd = this.hooks.partData(part) || {}, kind = ctx.kindOf(part), nm = this.hooks.partName(part) || part;
      const on = ids.map((id) => ({ id, s: shows(id) })).filter((x) => x.s).reduce((a, x) => (!a || x.s.seen > a.s.seen ? x : a), null);
      return { pos: nums.get(part) ?? i + 1, part, name: nm, qty: ids.length, instances: ids, kind, material: kind === 'assembly' ? '—' : pd.material || 'PLA', pn: pd.library?.pn || '',
        bought: kind !== 'assembly' && (!!pd.library || ctx.bought(pd, nm)), iso: on?.s.iso || null, at: on?.id || null };
    }).sort((a, b) => a.pos - b.pos);
    return { built: { ...r, preset: 'light' }, rows };
  }

  async drawingSet(rootId, ctx) {
    const pages = [], drawn = new Set([rootId]), name = (id) => this.hooks.partName(id) || id, now = new Date().toISOString();
    const visit = async (aid, parent) => {
      if (!(this.hooks.partData(aid)?.instances || []).length) return;
      const ex = ctx.sheetOf(aid)?.exploded ? 2 : 0; // (its own sheet's iso view exploded)
      const own = ctx.sheetOf(aid), sd = this.pageData(own || { source: aid }); // its own sheet: the user's moves, dimensions, texts
      const { built, rows } = await this.cached(`a|${aid}|${this.sourceHash(aid)}|${ex}|${[...this.itemNumbers(this.rootOf(aid) || aid)].join()}|${sd.paper || ''}|${this.layKey(sd)}`, () => this.assemblyPage(aid, ctx, ex, sd));
      const base = own ? structuredClone(own) : { created: now, changed: now, off: { Right: true }, views: { Iso: built.layout.views.Right } };
      if (own && isoLaid(own)) base.views = { ...base.views, Iso: built.layout.views.Right }; // (its iso view where this layout puts it)
      pages.push({ name: name(aid), d: { ...base, source: aid, built, asm: { rows },
        title: { kind: parent ? t('Sub-assembly') : t('Assembly'), part: name(aid), material: '—', of: parent || '' } } });
      if (own?.bomPage) for (const d of this.bomPages(aid, sd, built, parent || '')) pages.push({ name: `${t('BOM')} ${name(aid)}`, bom: true, d });
      for (const row of rows) if (row.kind === 'assembly' && !drawn.has(row.part)) { drawn.add(row.part); await visit(row.part, name(aid)); }
      for (const row of rows) {
        if (row.kind !== 'model' || row.bought || drawn.has(row.part)) continue;
        drawn.add(row.part);
        pages.push({ name: row.name, part: row.part, parent: name(aid), pos: row.pos });
      }
    };
    await visit(rootId, null);
    if (!pages.length) throw new Error(t('The assembly has no parts to draw.'));
    await Promise.all(pages.filter((pg) => pg.part).map(async (pg) => { // (side by side: the kernel's processes draw several parts at once)
      const src = this.hooks.partData(pg.part), own = ctx.sheetOf(pg.part);
      const d = this.pageData(own ? structuredClone(own) : { source: pg.part, preset: 'medium', rev: 1, created: now, changed: now });
      if (!d.built || d.built.stale || d.hash !== partHash(src) || this.builtKey(d) !== this.layKey(d)) {
        const key = `p|${pg.part}|${partHash(src)}|${d.preset || 'medium'}|${d.paper || ''}|${JSON.stringify(d.vpreset || {})}|${this.layKey(d)}`;
        d.built = { ...(await this.cached(key, () => post('/api/sheet/build', { part: src, preset: d.preset || 'medium', paper: d.paper, per_view: d.vpreset || {}, ...this.layReq(d) }))), preset: d.preset || 'medium', paper: d.paper ?? null, lk: this.layKey(d) };
      }
      pg.d = { ...d, title: { part: pg.name, of: pg.parent, pos: pg.pos } };
    }));
    const n = pages.length;
    const svgs = pages.map((pg, i) => this.svgOf({ ...pg.d, title: { ...pg.d.title, sheet: `${i + 1} / ${n}` } }));
    return { svgs, ids: pages.map((pg) => pg.part || pg.d.source), bom: pages.map((pg) => !!pg.bom), pages: pages.map((pg) => (pg.part ? pg.name : pg.bom ? `📋 ${pg.name}` : `◇ ${pg.name}`)) };
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
      if (x.kind === 'dia' || x.kind === 'rad' || x.kind === 'pcd') { const v = this.value(x); return v === null ? null : { round: x.kind, v }; }
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
    if (this.setMode) { this.renderSuggest(); this.renderSet(); return; }
    this.stage.classList.remove('sh-set');
    if (!this.geo) {
      this.renderSuggest(); // (no drawing yet: being made, or why not with ↻ Try again)
      this.stage.innerHTML = this.error ? `<div class="sh-empty sh-failed"><p>${/^cancelled/i.test(this.error) ? esc(t('Cancelled — the drawing was not made.')) : `⚠ ${esc(tv('The drawing could not be made: {e}', { e: t(this.error) }))}`}</p>
          <button class="btn small" data-a="retry">↻ ${esc(t('Try again'))}</button></div>`
        : `<p class="hint sh-empty">${esc(this.hooks.partData(this.d.source) ? t('Making the drawing…') : t('Its part is not in the project any more.'))}</p>`;
      this.stage.querySelector('[data-a=retry]')?.addEventListener('click', () => this.ensure(true));
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
    const out = this.outside();
    if (this.selTitle) { // (its place: the title block's own drawing — each style lays it out its own way)
      const tb = svg.querySelector('.sh-title'), b = tb?.getBBox();
      if (b) tb.insertAdjacentHTML('beforeend', `<rect x="${b.x - 0.8}" y="${b.y - 0.8}" width="${b.width + 1.6}" height="${b.height + 1.6}" fill="#1f6feb" fill-opacity="0.05" stroke="#1f6feb" stroke-width="0.5" stroke-dasharray="2 1.2" pointer-events="none" class="sh-selmark"/>`);
    }
    this.renderSuggest();
    this.$('.sh-status').textContent = `${this.allDims().length} ${t('dimension(s)')}${lost ? ` · ⚠ ${lost} ${t('lost their points')}` : ''}${out.length ? ` · ⚠ ${tv('{views}: past the frame', { views: out.map((v) => this.viewName(v)).join(', ') })}` : ''} · ${t('Scale')} ${scaleText(this.scaleArr())} · Rev ${this.d.rev}`;
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
      <button class="chip primary" data-a="pdf" title="The sheet as a PDF — as you see it">⬇ PDF</button>
      <button class="chip" data-a="dxf" title="The sheet as a DXF for AutoCAD, SolidWorks or Solid Edge drafting: the paper in true size (mm), the views where they are, real dimensions, the title block; a layer per kind">⬇ DXF</button>${this.busy ? `<span class="sh-busy">${t('Making the drawing…')}</span>` : ''}`;
    for (const b of bar.querySelectorAll('[data-preset]')) b.addEventListener('click', () => this.setPreset(b.dataset.preset));
    for (const b of bar.querySelectorAll('[data-a]')) b.addEventListener('click', () => this.action(b.dataset.a));
  }

  renderLeft() {
    const box = this.$('.sh-left');
    if (!box || !this.d) return;
    const all = this.allDims(), hid = this.d.hidden.length, ck = this.checked || { missing: [], dup: new Set(), over: new Set(), ok: true };
    const vp = this.d.vpreset || {}, per = (v) => ck.missing.filter((m) => m.view === v).length;
    const out = this.outside(), sheetSc = scaleText(this.scaleArr());
    const vrows = [...VIEWS, 'Iso', ...(this.d.asm ? [] : ['Section'])];
    const own = (v) => vp[v] === 'all' ? t('All its sizes') : PRESETS.find(([k]) => k === vp[v])?.[1] && t(PRESETS.find(([k]) => k === vp[v])[1]);
    const vrow = (v) => {
      const on = v === 'Section' ? !!this.d.section : !this.d.off[v], dims = v !== 'Iso' && v !== 'Section' && !this.d.asm;
      const chk = v === 'Section'
        ? `<input type="checkbox" class="sh-vchk" data-sec ${on ? 'checked' : ''} title="${esc(t('The part cut through its middle (across X) and seen from the right, the cut hatched — in the right view\'s place; the cut marked A–A on the front view'))}">`
        : `<input type="checkbox" class="sh-vchk" data-v="${v}" ${on ? 'checked' : ''} title="${esc(t('Show this view on the sheet'))}">`;
      const state = !on || v === 'Iso' || v === 'Section' ? '' : per(v) ? `<b class="sh-vbad" title="${esc(t('Sizes missing in this view'))}">⚠ ${per(v)}</b>` : `<b class="sh-vok" title="${esc(t('Fully dimensioned'))}">✓</b>`;
      const menu = !dims ? '<span></span>' : `<div class="menu sh-vmenu"><button class="mini sh-vmore ${vp[v] ? 'on' : ''}" data-vmore="${v}" title="${esc(t('How many dimensions in this view — as the sheet, or its own'))}">⋯</button>
        <div class="menu-list"><div class="sh-vmhead">${esc(t('Dimensions in this view'))}</div>${[['', 'As the sheet'], ...PRESETS, ['all', 'All its sizes']].map(([k, l]) => `<button data-vpset="${k}" data-vpview="${v}" ${k === 'all' ? `title="${esc(t('Every size this view shows, also the ones given in another view'))}"` : ''}><i>${(vp[v] || '') === k ? '✓' : ''}</i>${esc(t(l))}</button>`).join('')}</div></div>`;
      return `<div class="sh-vrow ${on ? '' : 'off'}" data-vrow="${v}">${chk}<span class="sh-vcell"><span class="sh-vname" data-vname="${v}" title="${esc(t('Double-click to rename the view'))}" data-no-i18n>${esc(this.viewName(v))}</span>${dims && vp[v] ? `<i class="sh-vtag" data-no-i18n>${esc(own(v))}</i>` : ''}</span>
        <span class="sh-vstate">${state}</span>${menu}${this.scaleSelect(`data-vs="${v}" class="sh-vscale" ${on ? '' : 'disabled'}`, this.d.vscale?.[v], `${t('Sheet')} ${sheetSc}`, t('The view\'s scale — the sheet\'s, a standard one or your own (Custom…); a view at its own scale says it under its name'))}</div>`;
    };
    box.innerHTML = `<h3>Views</h3><div class="sh-views">${vrows.map(vrow).join('')}</div>
      <p class="hint sh-vhint">${esc(t('Drag a view to move it (Shift: freely). Double-click a name to rename it.'))}</p>
      ${out.length ? `<p class="mp-bad sh-outside">⚠ ${esc(tv('{views}: past the frame — choose a smaller scale or a bigger paper.', { views: out.map((v) => this.viewName(v)).join(', ') }))}</p>` : ''}
      ${this.d.asm ? `<p class="hint">${esc(t('An assembly drawing: its views, overall sizes and parts list — each part has its own drawing for its sizes.'))}</p>` : ''}
      ${this.geo?.simple ? `<p class="hint sh-simple">${esc(!this.geo.simple.left_out ? t('A big part: drawn from its mesh, without hidden lines.') : tv('A big part: drawn from its mesh, without hidden lines; {n} pieces smaller than {mm} mm are left out (too small to see at this scale).', { n: this.geo.simple.left_out, mm: this.geo.simple.under }))}</p>` : ''}
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
    box.querySelector('[data-sec]')?.addEventListener('change', (e) => this.setSection(e.target.checked)); // Section A–A: in the Right view's place (the Right view hidden)
    for (const el of box.querySelectorAll('[data-v]')) {
      el.addEventListener('change', () => { if (el.checked) delete this.d.off[el.dataset.v]; else this.d.off[el.dataset.v] = true; this.commit(); });
    }
    for (const el of box.querySelectorAll('[data-vs]')) {
      el.addEventListener('change', async () => { const s = await this.scaleFrom(el, this.d.vscale?.[el.dataset.vs]); if (s !== undefined) this.setViewScale(el.dataset.vs, s); });
    }
    for (const el of box.querySelectorAll('[data-vname]')) {
      el.addEventListener('dblclick', () => renameInPlace(el, (n) => this.setViewName(el.dataset.vname, n)));
    }
    for (const b of box.querySelectorAll('[data-vmore]')) { // ⋯ a view's own dimensions: a small menu
      b.addEventListener('click', (e) => { e.stopPropagation(); const m = b.parentElement, was = m.classList.contains('open'); this.closeViewMenus(); m.classList.toggle('open', !was); });
    }
    for (const b of box.querySelectorAll('[data-vpset]')) {
      b.addEventListener('click', () => { this.closeViewMenus(); this.setViewPreset(b.dataset.vpview, b.dataset.vpset || null); });
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

  /** A view's own dimensions ('light' / 'medium' / 'full' / 'all'; null: as the sheet) — the sheet made again. */
  setViewPreset(v, k) {
    const vpr = { ...(this.d.vpreset || {}) };
    if (k) vpr[v] = k; else delete vpr[v];
    this.d.vpreset = vpr;
    this.history.commit();
    this.ensure(true);
  }

  closeViewMenus() { for (const m of document.querySelectorAll('#shLeft .sh-vmenu.open')) m.classList.remove('open'); }

  /** ＋ every missing size (one by one: each new one may give others, e.g. a row's pitch). */
  addAllMissing(limit = 60) {
    let n = 0;
    for (let ck = this.check(); ck?.missing.length && n < limit; ck = this.check(), n++) this.addMissing(ck.missing[0]);
    return n;
  }

  /** The right panel's Title block: its template (▾, 💾 Save as template…, Use for all drawings of this assembly), the
   *  sheet's own texts, and (folded) the company, address, tolerance standard, logo, layout and the fields shown. */
  titlePanel() {
    const tp = this.tplOf(), tb = this.tbOf(), X = this.d.texts || {}, root = this.hooks.drawingCtx ? this.rootOf(this.d.source) : null;
    const from = !this.d.template && tp.name !== DEFAULT_TPL.name ? this.hooks.partName(root) : null;
    const inh = { ...tb.texts, ...this.setTextsOf() };
    const field = ([k, l]) => `<div class="field"><label>${esc(t(l))}</label><input type="text" data-text="${k}" value="${esc(X[k] || '')}" placeholder="${esc(k === 'title' ? this.hooks.partName(this.d.source) || '' : k === 'tolstd' ? inh.tolstd || 'ISO 2768' : inh[k] || '')}"></div>`;
    return `<h3>${esc(t('Title block'))}</h3>
      <div class="field"><label>${esc(t('Template'))}</label><select data-k="tpl" title="${esc(t('The title block\'s template: its layout, fields, company, logo and frame — Modern is the app\'s clean default'))}">${this.tpls.map((x) => `<option value="${esc(x.name)}" ${x.name === tp.name ? 'selected' : ''} data-no-i18n>${esc(x.builtin ? t(x.name) : x.name)}</option>`).join('')}</select></div>
      ${from ? `<p class="hint">${esc(tv('From the drawing set of {asm}.', { asm: from }))}</p>` : ''}
      <div class="field"><label>${esc(t('Title block style'))}</label><select data-k="tbstyle" title="${esc(t('How the title block looks — any style goes with any parts list'))}">${TITLE_STYLES.map(([k, l]) => `<option value="${k}" ${tb.style === k ? 'selected' : ''} title="${esc(t(STYLE_TIPS[k]))}">${esc(t(l))}</option>`).join('')}</select></div>
      <div class="field"><label>${esc(t('Parts list style'))}</label><select data-k="bomstyle" title="${esc(t('How the parts list of an assembly drawing and the BOM pages look'))}">${BOM_STYLES.map(([k, l]) => `<option value="${k}" ${tb.bomStyle === k ? 'selected' : ''}>${esc(t(l))}</option>`).join('')}</select></div>
      <p class="hint">${esc(t(STYLE_TIPS[tb.style] || ''))}${this.d.tb?.titleStyle || this.d.tb?.bomStyle ? ` ${t('(this drawing\'s — 💾 Save as template… keeps it)')}` : ''}</p>
      <div class="row-actions sh-tplbtns"><button class="btn small" data-a="saveTpl" title="${esc(t('Keep this title block (layout, fields, company, address, drawn by, note, tolerance standard, logo, frame) as a template for all your projects'))}">💾 ${esc(t('Save as template…'))}</button>
        ${tp.builtin ? '' : `<button class="mini danger" data-a="delTpl" title="${esc(t('Delete this template (drawings using it go back to Modern)'))}">✕</button>`}</div>
      ${root ? `<div class="row-actions"><button class="btn small" data-a="tplSet" title="${esc(t('This template on every drawing of the assembly\'s set — the assembly\'s, its sub-assemblies\' and its parts\' — and on new ones'))}">⇶ ${esc(t('Use for all drawings of this assembly'))}</button></div>` : ''}
      ${TEXTS.map(field).join('')}
      <details class="sh-tbmore" ${this.tbOpen ? 'open' : ''}><summary title="${esc(t('Company, address, tolerance standard, logo, layout and the fields shown'))}">${esc(t('Company, logo and fields'))}</summary>
        ${MORE_TEXTS.map(field).join('')}
        <div class="field"><label>${esc(t('Logo'))}</label><span class="sh-logo"><button class="btn small" data-a="logo" title="${esc(t('A picture (PNG, JPEG or SVG) in the title block\'s left column'))}">🖼 ${esc(t(tb.logo ? 'Change…' : 'Choose…'))}</button>${tb.logo ? `<button class="mini danger" data-a="nologo" title="${esc(t('No logo'))}">✕</button>` : ''}<input type="file" data-k="logofile" accept="image/png,image/jpeg,image/svg+xml" hidden></span></div>
        <div class="sh-tbfields" title="${esc(t('The fields the title block shows'))}">${TB_FIELDS.map(([k, l]) => `<label class="check"><input type="checkbox" data-tbf="${k}" ${tb.hide.has(k) ? '' : 'checked'}> ${esc(t(l))}</label>`).join('')}</div>
        <p class="hint">${esc(t('Changes here are this drawing\'s — 💾 Save as template… keeps them for all.'))}</p>
      </details>`;
  }

  /** Whether this drawing has its own title block / parts list style (not its template's yet). */
  ownStyles() { const tb = this.d?.tb || {}, tp = this.tplOf(); return (!!tb.titleStyle && tb.titleStyle !== (tp.titleStyle || tp.layout || 'block')) || (!!tb.bomStyle && tb.bomStyle !== (tp.bomStyle || 'modern')); }

  /** Title block style / parts list style of this sheet ({title: block | strip | A … E, bom: modern | A … E}) — any
   *  two together; 💾 Save as template… keeps them, ⇶ puts them on the whole drawing set. */
  setStyles({ title, bom } = {}) {
    const keys = TITLE_STYLES.map((x) => x[0]), bkeys = BOM_STYLES.map((x) => x[0]);
    if (title !== undefined && !keys.includes(title)) throw new Error(`No title block style ${title} — one of: ${keys.join(', ')}.`);
    if (bom !== undefined && !bkeys.includes(bom)) throw new Error(`No parts list style ${bom} — one of: ${bkeys.join(', ')}.`);
    const own = { ...(this.d.tb || {}) };
    if (title !== undefined) { own.titleStyle = title; delete own.layout; }
    if (bom !== undefined) own.bomStyle = bom;
    this.d.tb = own;
    this.history.commit();
    this.render();
    this.hooks.onChange?.();
    this.ensure(); // (another height: the views placed again)
  }

  bindTitlePanel(box) {
    const tbSet = (k, v) => { this.d.tb = { ...(this.d.tb || {}), [k]: v }; this.commit(); this.ensure(); };
    const fail = (e) => this.hooks.toast?.(e.message, 'error', 6000);
    box.querySelector('[data-k=tpl]')?.addEventListener('change', (e) => { try { this.useTemplate(e.target.value); } catch (err) { fail(err); } });
    box.querySelector('[data-a=saveTpl]')?.addEventListener('click', () => this.saveTemplate().catch(fail));
    box.querySelector('[data-a=delTpl]')?.addEventListener('click', () => this.deleteTemplate(this.tplName()).catch(fail));
    box.querySelector('[data-a=tplSet]')?.addEventListener('click', () => this.useTemplateForSet().catch(fail));
    box.querySelector('.sh-tbmore')?.addEventListener('toggle', (e) => { this.tbOpen = e.target.open; });
    box.querySelector('[data-k=tbstyle]')?.addEventListener('change', (e) => this.setStyles({ title: e.target.value }));
    box.querySelector('[data-k=bomstyle]')?.addEventListener('change', (e) => this.setStyles({ bom: e.target.value }));
    for (const c of box.querySelectorAll('[data-tbf]')) {
      c.addEventListener('change', () => { const hide = new Set(this.tbOf().hide); if (c.checked) hide.delete(c.dataset.tbf); else hide.add(c.dataset.tbf); tbSet('hide', [...hide]); });
    }
    const file = box.querySelector('[data-k=logofile]');
    box.querySelector('[data-a=logo]')?.addEventListener('click', () => file?.click());
    box.querySelector('[data-a=nologo]')?.addEventListener('click', () => tbSet('logo', null));
    file?.addEventListener('change', async () => { const f = file.files?.[0]; if (f) { try { tbSet('logo', await logoData(f)); } catch (e) { fail(e); } } });
  }

  /** ⏮ Drawn as the rollback bar stands (as SolidWorks does): its part rolled back in its history, or an assembly's
   *  parts that are — the line that says so, or ''. */
  rolledNote() {
    const id = this.d.source;
    if (this.hooks.kindOf?.(id) !== 'assembly') {
      const s = rolledText(this.hooks.partData(id));
      return s ? `⚠ ${t('The part is rolled back in its history')}: ${s}` : '';
    }
    const names = new Set(), seen = new Set();
    const walk = (aid) => {
      if (seen.has(aid)) return;
      seen.add(aid);
      for (const it of this.hooks.partData(aid)?.instances || []) {
        if (this.hooks.kindOf?.(it.part) === 'assembly') walk(it.part);
        else if (rolledText(this.hooks.partData(it.part))) names.add(this.hooks.partName(it.part) || it.part);
      }
    };
    walk(id);
    return names.size ? `⚠ ${t('Parts rolled back in their history')}: ${[...names].join(', ')}` : '';
  }

  renderProps() {
    const box = this.$('.sh-props');
    if (!box || !this.d) return;
    const d = this.sel && this.allDims().find((x) => x.id === this.sel), name = this.hooks.partName(this.d.source);
    box.innerHTML = `<h2>📄 ${esc(t('Drawing'))}</h2>
      <p class="hint">${esc(tv('Of {part} — it follows the part: change the part, the drawing is made again (a new revision).', { part: name || '?' }))}</p>
      ${this.rolledNote() ? `<p class="hint sh-rb-note" data-no-i18n>${esc(this.rolledNote())}</p>` : ''}
      <div class="mp-facts"><span>Rev</span><b data-no-i18n>${this.d.rev}</b><span>${esc(t('Changed'))}</span><b data-no-i18n>${esc(when(this.d.changed))}</b><span>${esc(t('Created'))}</span><b data-no-i18n>${esc(when(this.d.created))}</b></div>
      <div class="field"><label>Paper</label><select data-k="paper">${[['', 'Auto'], ['A4', 'A4'], ['A3', 'A3']].map(([v, l]) => `<option value="${v}" ${(this.d.paper || '') === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label>${esc(t('Scale'))}</label>${this.scaleSelect('data-k="scale"', this.d.scale, this.d.scale ? t('Auto') : `${t('Auto')} (${scaleText(this.lay?.scale || [1, 1])})`, t('The sheet\'s scale: Auto fits the views on the paper; or a standard one, or your own (Custom…, e.g. 1:2522). Dimensions always show the real sizes.'))}</div>
      ${d ? '' : this.titlePanel()}
      ${this.d.asm ? `<label class="check"><input type="checkbox" data-k="exploded" ${this.d.exploded ? 'checked' : ''}> ${esc(t('Iso view exploded'))}</label>` : ''}
      ${this.d.asm ? this.bomPanel() : ''}
      ${d ? '' : this.framePanel()}
      ${d ? `<h3>${esc(t('Dimension'))}</h3><p class="mp-count" data-no-i18n>${esc(this.value(d) === null ? '⚠ ?' : this.dimText(d, this.value(d)))}</p>
        <p class="hint">${esc(d.auto ? t('Made by the preset. Drag it to move it; Delete removes it (↺ brings it back).') : t('Your own. Drag it to move it; Delete removes it.'))}</p>
        ${this.value(d) === null ? `<p class="mp-bad">${esc(t('Its points are gone — the part changed. Delete it and add it again.'))}</p>` : ''}
        ${d.kind === 'dia' && !d.thread ? this.fitField(d) : ''}
        ${d.kind === 'pcd' || (d.kind === 'dia' && !d.thread) ? '' : `<div class="field"><label>${esc(t('Tolerance'))}</label><input type="text" data-k="tol" value="${esc(d.tol || '')}" placeholder="±0.1" title="${esc(t('A tolerance after the size: ±0.1, or +0.2/−0.1'))}"><span class="unit">mm</span></div>`}
        <label class="check" title="${esc(t('A reference dimension is in brackets: for information only, not to be checked'))}"><input type="checkbox" data-k="ref" ${d.ref ? 'checked' : ''}> ${esc(t('Reference dimension'))}</label>
        <div class="row-actions"><button class="btn small danger" data-a="del">✕ ${esc(t('Delete'))}</button></div>`
        : `<p class="hint">${esc(t('Drag a dimension or a view to move it. ＋ Dimension: click two points, or a circle. The values come from the part.'))}</p>`}
      ${name ? `<div class="row-actions"><button class="btn small" data-a="part">◆ ${esc(tv('Open {part}', { part: name }))}</button></div>` : ''}`;
    for (const el of box.querySelectorAll('[data-text]')) {
      el.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') el.blur(); });
      el.addEventListener('change', () => this.typed(el.dataset.text, el.value));
    }
    this.bindTitlePanel(box);
    this.bindFramePanel(box);
    box.querySelector('[data-k=exploded]')?.addEventListener('change', (e) => { // (the parts pulled apart in the iso view, balloons on them)
      if (e.target.checked) this.d.exploded = true; else delete this.d.exploded;
      delete this.d.balloons;
      this.history.commit();
      this.ensure(true);
    });
    this.bindBomPanel(box);
    box.querySelector('[data-k=paper]').addEventListener('change', (e) => { this.d.paper = e.target.value || null; this.d.views = {}; this.history.commit(); this.ensure(true); });
    box.querySelector('[data-k=scale]')?.addEventListener('change', async (e) => { const s = await this.scaleFrom(e.target, this.d.scale); if (s !== undefined) this.setSheetScale(s); });
    box.querySelector('[data-a=del]')?.addEventListener('click', () => this.remove(this.sel));
    box.querySelector('[data-k=fit]')?.addEventListener('change', (e) => { this.setFit(d.id, e.target.value); this.renderProps(); });
    const tol = box.querySelector('[data-k=tol]');
    tol?.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') tol.blur(); });
    tol?.addEventListener('change', () => { const v = tolText(tol.value); if (v === null) { this.hooks.toast?.(t('Write it as ±0.1 or +0.2/−0.1.'), 'warning', 4000); tol.value = d.tol || ''; return; } this.setDimProps(d.id, { tol: v || undefined }); });
    box.querySelector('[data-k=ref]')?.addEventListener('change', (e) => this.setDimProps(d.id, { ref: e.target.checked }));
    box.querySelector('[data-a=part]')?.addEventListener('click', () => this.hooks.openPart?.(this.d.source));
  }

  /** An assembly's sheet: 📋 Add BOM page — the whole BOM on its own page(s) after this one, in the drawing set and its
   *  PDF; Summary | Structured; 👁 shows it in 📚 All pages. */
  bomPanel() {
    const on = this.d.bomPage, mode = on === 'structured' ? 'structured' : 'summary';
    if (!on) return `<div class="row-actions"><button class="btn small" data-a="bomAdd" title="${esc(t('A page with the bill of materials of this assembly — every level rolled up, the positions as the balloons — after this page, in the drawing set and its PDF'))}">📋 ${esc(t('Add BOM page'))}</button></div>`;
    const n = this.d.built ? this.bomPages(this.d.source, this.d, this.d.built).length : 1;
    return `<h3>📋 ${esc(t('BOM page'))}</h3><span class="seg"><button class="${mode === 'summary' ? 'on' : ''}" data-bommode="summary" title="${esc(t('One row per part: how many in all, from every level of the assembly'))}">${esc(t('Summary'))}</button><button class="${mode === 'structured' ? 'on' : ''}" data-bommode="structured" title="${esc(t('The assembly tree: each sub-assembly with its parts, how many in each and in all'))}">${esc(t('Structured'))}</button></span>
      <p class="hint">${esc(tv('{n} page(s) after this one, in the drawing set and its PDF.', { n }))}</p>
      <div class="row-actions"><button class="btn small" data-a="bomShow" title="${esc(t('See it among all the pages of the drawing set'))}">👁 ${esc(t('Show it'))}</button><button class="btn small danger" data-a="bomDel">✕ ${esc(t('Remove BOM page'))}</button></div>`;
  }

  bindBomPanel(box) {
    const show = () => { this.setMode = true; this.setScrolled = false; this.toBom = true; this.seen = null; this.render(); };
    box.querySelector('[data-a=bomAdd]')?.addEventListener('click', () => { this.d.bomPage = 'summary'; this.commit(); show(); });
    box.querySelector('[data-a=bomShow]')?.addEventListener('click', show);
    box.querySelector('[data-a=bomDel]')?.addEventListener('click', () => { delete this.d.bomPage; this.commit(); });
    for (const b of box.querySelectorAll('[data-bommode]')) b.addEventListener('click', () => { this.d.bomPage = b.dataset.bommode; this.commit(); if (this.setMode) { this.setScrolled = false; this.toBom = true; this.render(); } });
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
   *  "4× 10" links its whole row); every circle needs its Ø, every arc its R. A hole step needs what makes it: its
   *  callout gives it all (its head's circles and edges too); else a countersink's angle, a counterbore's or a blind
   *  hole's depth by their own dimensions. -> {missing: [{view, dir, at, key, what, hole?}], dup: Set (the same
   *  distance twice), over: Set (a distance the others give already), ok}. */
  check() {
    const G = this.geo;
    if (!G) return null;
    if (this.d.asm) return this.asmCheck();
    const AX = { Front: ['x', 'z'], Top: ['x', 'y'], Right: ['y', 'z'] }, r2 = (v) => Math.round(v * 100) / 100;
    const uf = { x: new Map(), y: new Map(), z: new Map() };
    const find = (ax, v) => { const m = uf[ax]; let k = String(r2(v)); while (m.has(k) && m.get(k) !== k) k = m.get(k); if (!m.has(k)) m.set(k, k); return k; };
    const join = (ax, a, b) => { const p = find(ax, a), q = find(ax, b); if (p === q) return false; uf[ax].set(p, q); return true; };
    const shown = VIEWS.filter((v) => !this.d.off[v]), dims = this.allDims().filter((d) => !d.ref), seen = new Map(), dup = new Set(), over = new Set(); // (a reference dimension (in brackets) gives a size twice on purpose)
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
    for (const d of dims) { // a bolt circle ("PCD Ø60 · 6× 60°"): its holes are where its centre and its Ø put them
      const rg = d.kind === 'pcd' && shown.includes(d.view) && this.circleOf(d.view, d.a), g = G.views[d.view];
      if (!rg) continue;
      for (const c of g.circles) if (rg.keys.includes(c.key)) for (const k of [0, 1]) join(AX[d.view][k], rg.c[k], c.c[k]);
    }
    const fullR = new Set(dims.filter((d) => d.kind === 'dia' && this.value(d) !== null).map((d) => r2(this.value(d) / 2)));
    const holes = G.holes || {}, called = new Set(dims.filter((d) => d.hole && holes[d.hole] && shown.includes(d.view) && this.value(d) !== null).map((d) => d.hole));
    for (const id of called) if (holes[id].head) fullR.add(r2(holes[id].head_d / 2)); // (its callout gives its head's Ø)
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

    const decals = new Set((this.hooks.partData(this.d.source)?.features || []).filter((f) => f.type === 'decal').map((f) => f.id));
    const deco = (key) => decals.size > 0 && key.split('+').some((n) => decals.has(n.split(':')[0])); // (an edge of a decal step's faces)
    const diaTold = new Set(), holeAt = {};
    const stepFace = (key, face) => [...(key || '').matchAll(new RegExp(`(?:^|[+:])([^:+]+):(${face}):\\d+`, 'g'))].map((m) => m[1]); // (the hole steps a key's faces are of)
    const inCallout = (key) => stepFace(key, 'csk|cbore|cbore_floor|cbore_tear|bottom').some((id) => called.has(id));
    for (const v of shown) {
      const g = G.views[v];
      for (const c of g.circles) {
        if (deco(c.key)) continue; // (text / a picture on a face: not sized)
        const st = stepOf(c.key), h = st && holes[st[0]];
        if (h && st[1] === 'hole' && !holeAt[st[0]]) holeAt[st[0]] = { view: v, c };
        if (c.full) {
          for (const k of [0, 1]) need(v, k, c.c[k], `${c.key}#c`, c.c, `Ø${fmt(2 * c.r)}`);
          if (h && called.has(st[0])) continue; // (its callout gives it)
          const what = !h ? `Ø${fmt(2 * c.r)}` : st[1] === 'head' ? tv(h.head === 'csk' ? "the countersink's Ø{d} ({id})" : "the counterbore's Ø{d} ({id})", { d: fmt(2 * c.r), id: st[0] }) : `${h.thread || `Ø${fmt(2 * c.r)}`} (${st[0]})`;
          if (!fullR.has(r2(c.r)) && !diaTold.has(`d${r2(c.r)}`)) { diaTold.add(`d${r2(c.r)}`); missing.push({ view: v, kind: 'dia', key: c.key, at: c.pm, what, ...(h ? { hole: st[0] } : {}) }); }
        } else if (!arcR.has(r2(c.r)) && !diaTold.has(`r${r2(c.r)}`)) { diaTold.add(`r${r2(c.r)}`); missing.push({ view: v, kind: 'rad', key: c.key, at: c.pm, what: `R${fmt(c.r)}` }); }
      }
      for (const ln of g.lines) {
        if (/:round:|[:_]tear:|:flat:/.test(ln.key) || deco(ln.key) || inCallout(ln.key)) continue; // where a rounding begins: its R gives it; a teardrop's point: its Ø; a D hole's flat: its callout; text / a picture: decoration; a head's edges: its callout
        if (Math.abs(ln.a[0] - ln.b[0]) < 1e-3) need(v, 0, ln.a[0], `${ln.key}#0`, [(ln.a[0] + ln.b[0]) / 2, (ln.a[1] + ln.b[1]) / 2], t('an edge'));
        if (Math.abs(ln.a[1] - ln.b[1]) < 1e-3) need(v, 1, ln.a[1], `${ln.key}#0`, [(ln.a[0] + ln.b[0]) / 2, (ln.a[1] + ln.b[1]) / 2], t('an edge'));
      }
      need(v, 0, g.box[2], 'box#x1', [g.box[2], g.box[1]], t('the far end'));
      need(v, 1, g.box[3], 'box#y1', [g.box[2], g.box[3]], t('the top'));
    }
    // a hole step without its callout: what no circle shows — a countersink's angle, a counterbore's / a blind hole's depth
    const gives = (id, face, kind) => dims.some((d) => d.kind === kind && this.value(d) !== null && shown.includes(d.view) && [d.a, d.b].some((k) => stepFace(k, face).includes(id)));
    for (const [id, h] of Object.entries(holes)) {
      const at = holeAt[id];
      if (called.has(id) || !at) continue;
      const lack = [];
      if (h.head === 'csk' && !gives(id, 'csk', 'ang')) lack.push(tv("the countersink's angle ({id})", { id }));
      if (h.head === 'cbore' && !gives(id, 'cbore_floor', 'linear')) lack.push(tv("the counterbore's depth ({id})", { id }));
      if (!h.through && !gives(id, 'bottom', 'linear')) lack.push(tv(h.thread ? "the thread's depth ({id})" : "the hole's depth ({id})", { id }));
      for (const what of lack) missing.push({ view: at.view, kind: 'hole', hole: id, key: at.c.key, at: [at.c.c[0] + at.c.r * 0.7, at.c.c[1] - at.c.r * 0.7], what });
    }
    return { missing, dup, over, ok: !missing.length && !dup.size };
  }

  /** An assembly's sheet asks only for its own sizes: its overall length, width and height, each by a dimension in a
   *  view shown, and where its base part's mounting holes are (its free holes, geometry.mount; none: not asked) — the
   *  parts' holes, radii and edges belong on their own sheets, a bought part's never -> as check(). */
  asmCheck() {
    const G = this.geo, AX = { Front: ['x', 'z'], Top: ['x', 'y'], Right: ['y', 'z'] }, r2 = (v) => Math.round(v * 100) / 100;
    const shown = VIEWS.filter((v) => !this.d.off[v] && G.views[v]), dims = this.allDims(), have = new Set(), seen = new Map(), dup = new Set();
    for (const d of dims) {
      if (d.kind !== 'linear' || !shown.includes(d.view) || this.value(d) === null) continue;
      const g = G.views[d.view], k = d.dir === 'h' ? 0 : 1, size = r2(g.box[k + 2] - g.box[k]), ax = AX[d.view][k];
      if (Math.abs(r2(this.value(d)) - size) > 0.01) continue;
      if (seen.has(`${ax}:${d.view}`)) dup.add(d.id); else seen.set(`${ax}:${d.view}`, d.id);
      have.add(ax);
    }
    const what = { x: t('the overall length'), y: t('the overall width'), z: t('the overall height') }, missing = [];
    for (const ax of ['x', 'y', 'z']) {
      if (have.has(ax)) continue;
      const v = shown.find((w) => AX[w].includes(ax));
      if (!v) continue; // (no view shows it: nothing to dimension it in)
      const k = AX[v].indexOf(ax), g = G.views[v];
      missing.push({ view: v, dir: k ? 'v' : 'h', key: k ? 'box#y1' : 'box#x1', at: k ? [g.box[2], g.box[3]] : [g.box[2], g.box[1]], what: what[ax], ax });
    }
    // the base part's mounting holes (geometry.mount: its holes no screw / pin of the assembly is in): each linked by
    // dimensions to the base part's left / bottom edge (a pitch "3× 20" its whole row, a bolt circle its holes)
    for (const m of G.mount || []) {
      if (!shown.includes(m.view)) continue;
      const g = G.views[m.view], uf = [new Map(), new Map()];
      const find = (k, v) => { const u = uf[k]; let x = String(r2(v)); while (u.has(x) && u.get(x) !== x) x = u.get(x); if (!u.has(x)) u.set(x, x); return x; };
      const join = (k, a, b) => { const p = find(k, a), q = find(k, b); if (p !== q) uf[k].set(p, q); };
      for (const d of dims) {
        if (d.view !== m.view || this.value(d) === null) continue;
        if (d.kind === 'linear') {
          const k = d.dir === 'h' ? 0 : 1, a = g.points[d.a][k], b = g.points[d.b][k], n = parseInt(d.pre, 10);
          join(k, a, b);
          if (n > 1) for (let i = 1; i < n; i++) join(k, a + i * (b - a), a + (i + 1) * (b - a)); // (the rest of the row)
        }
        const rg = d.kind === 'pcd' && this.circleOf(d.view, d.a);
        if (rg) for (const c of g.circles) if (rg.keys.includes(c.key)) for (const k of [0, 1]) join(k, rg.c[k], c.c[k]);
      }
      const told = new Set();
      for (const c of g.circles) {
        if (!m.keys.includes(c.key)) continue;
        for (const k of [0, 1]) {
          const from = k ? 'base#y0' : 'base#x0', id = `${k}:${r2(c.c[k])}`;
          if (told.has(id) || find(k, c.c[k]) === find(k, g.points[from][k])) continue;
          told.add(id);
          missing.push({ view: m.view, dir: k ? 'v' : 'h', key: `${c.key}#c`, from, at: c.c, what: tv('a mounting hole (Ø{d})', { d: fmt(2 * c.r) }), ax: AX[m.view][k] });
        }
      }
    }
    return { missing, dup, over: new Set(), ok: !missing.length && !dup.size, assembly: true };
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
    this.stage.innerHTML = set.svgs.map((svg, i) => `<div class="sh-sheetpage" data-pageid="${set.ids[i]}"${set.bom[i] ? ' data-bom="1"' : ''} title="${esc(t('Double-click: edit this page'))}" data-no-i18n>${svg}</div>`).join('');
    if (this.setScrolled) this.stage.scrollTop = top;
    else { this.stage.querySelector(this.toBom ? '[data-bom]' : `[data-pageid="${this.d.source}"]`)?.scrollIntoView({ block: 'start' }); this.setScrolled = true; this.toBom = false; }
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
    const co = m.hole && this.calloutFor(m.view, m.key); // (a hole step's size, head, depth: its callout gives them all)
    if (co) { this.addUser(co); return; }
    if (m.kind === 'dia' || m.kind === 'rad') { this.addUser({ view: m.view, kind: m.kind, a: m.key, count: 1, ang: m.kind === 'dia' ? 45 : 0, len: 6 }); return; }
    const n = this.d.user.filter((d) => d.view === m.view && d.dir === m.dir).length;
    this.addUser({ view: m.view, kind: 'linear', a: m.from || (m.dir === 'h' ? 'box#x0' : 'box#y0'), b: m.key, dir: m.dir, side: m.dir === 'h' ? 'b' : 'l', off: 20 + 7 * n });
  }

  // ------------------------------------------------------------------ editing
  action(a) {
    if (a === 'dim') { this.tool = this.tool === 'dim' ? 'select' : 'dim'; this.dimOnce = false; this.pick = null; this.hoverEdge = null; this.hint(this.tool === 'dim' ? t('Click a point, an edge or a circle — an edge alone twice gives its length. Esc: done.') : ''); this.render(); }
    if (a === 'undo') this.history.go(-1);
    if (a === 'redo') this.history.go(1);
    if (a === 'fit') { this.zoom = { k: 1, x: 0, y: 0 }; this.applyZoom(); }
    if (a === 'setview') { this.setMode = !this.setMode; this.setScrolled = false; this.seen = null; this.tool = 'select'; this.pick = null; this.render(); }
    if (a === 'pdf') this.exportPdf();
    if (a === 'dxf') this.exportDxf();
  }

  hint(text) { const h = this.$('.sh-hint'); h.hidden = !text; h.textContent = text; }

  // ------------------------------------------------------------------ typing straight into the title block (tbedit.js)
  /** What the text box of title-block cell `k` starts with: the text the cell shows (typed, the set's, the template's). */
  cellValue(k) {
    const F = this.textsOf();
    if (k === 'title') return this.d.texts?.title || this.d.title?.part || this.hooks.partName(this.d.source) || '';
    if (k === 'tolstd') return F.tolstd || (this.hooks.partData(this.d.source)?.tolerance ? 'ISO 2768' : '');
    return F[k] || '';
  }

  /** A cell's tooltip text: where a computed one comes from, an editable one's name. */
  cellTip(k) { return t(TB_COMPUTED[k] || TB_EDIT[k]?.label || k); }

  /** The cells to type into on the sheet in their order (Tab goes along them). */
  cellKeys() { return [...new Set([...(this.svgEl?.querySelectorAll('.sh-title [data-tcell]:not([data-ro])') || [])].map((el) => el.dataset.tcell))]; }

  /** A text box over title-block cell `k`, in its place, at its size and in its font: Enter or a click elsewhere keeps
   *  the text, Esc leaves the cell as it was, Tab / Shift+Tab go to the next / previous cell -> whether it is shown. */
  editCell(k) {
    if (this.editing) this.endEdit(true);
    const cell = this.svgEl?.querySelector(`.sh-title [data-tcell="${k}"]:not([data-ro])`);
    if (!cell || !TB_EDIT[k] || !this.lay) return false;
    const vp = this.els.viewport, R = vp.getBoundingClientRect(), r = cell.getBoundingClientRect();
    const px = this.svgEl.getBoundingClientRect().width / this.lay.size[0]; // (screen px a paper mm)
    const b = cell.getBBox(), inside = [...this.svgEl.querySelectorAll('.sh-title text')].filter((el) => {
      const q = el.getBBox(), cx = q.x + q.width / 2, cy = q.y + q.height / 2;
      return cx >= b.x && cx <= b.x + b.width && cy >= b.y && cy <= b.y + b.height;
    });
    const big = inside.sort((a, c) => (+c.getAttribute('font-size') || 0) - (+a.getAttribute('font-size') || 0))[0]; // (its value, under a small label)
    const fs = Math.max(12, Math.min(40, (+big?.getAttribute('font-size') || 3) * px)), br = big?.getBoundingClientRect();
    const h = Math.min(r.height, Math.max(fs * 1.55, 20)), mid = br ? br.top + br.height / 2 : r.top + r.height / 2;
    const input = document.createElement('input');
    input.className = 'sh-tbedit';
    input.dataset.tbedit = k;
    input.value = this.cellValue(k);
    input.placeholder = t(TB_EDIT[k].label);
    input.title = `${t(TB_EDIT[k].label)} — ${t('Enter keeps it, Esc goes back, Tab: the next field')}`;
    Object.assign(input.style, {
      left: `${r.left - R.left}px`, width: `${Math.max(r.width, 90)}px`, height: `${h}px`,
      top: `${Math.max(r.top, Math.min(r.bottom - h, mid - h / 2)) - R.top}px`, fontSize: `${fs.toFixed(1)}px`,
      fontFamily: big ? getComputedStyle(big).fontFamily : 'Helvetica, Arial, sans-serif', fontWeight: big ? getComputedStyle(big).fontWeight : '400',
      paddingLeft: `${Math.max(2, (br ? br.left : r.left + 4) - r.left - 1.5)}px`,
    });
    vp.appendChild(input);
    const ed = { k, input, was: input.value };
    this.editing = ed;
    input.addEventListener('keydown', (e) => {
      e.stopPropagation(); // (the sheet's own keys: Delete, Esc, Ctrl+Z are the text's here)
      if (e.key === 'Enter') { e.preventDefault(); this.endEdit(true); } else if (e.key === 'Escape') { e.preventDefault(); this.endEdit(false); } else if (e.key === 'Tab') {
        e.preventDefault();
        const keys = this.cellKeys(), i = keys.indexOf(k), next = keys[(i + (e.shiftKey ? -1 : 1) + keys.length) % keys.length];
        this.endEdit(true);
        if (next) this.editCell(next);
      }
    });
    input.addEventListener('blur', () => { if (this.editing === ed) this.endEdit(true); });
    input.focus();
    input.select();
    return true;
  }

  /** The cell's text box closed: its text kept (keep) or not. */
  endEdit(keep) {
    const ed = this.editing;
    if (!ed) return;
    this.editing = null;
    ed.input.remove();
    if (keep && ed.input.value.trim() !== ed.was.trim()) this.typed(ed.k, ed.input.value);
  }

  /** A title-block text typed (in its cell or in the panel): this sheet's own — then, for a project-wide one on a
   *  sheet of an assembly's drawing set, the question whether every sheet of the set should say it too. */
  typed(k, v) {
    v = String(v ?? '').trim();
    const x = { ...(this.d.texts || {}) }, inh = { ...this.tbOf().texts, ...this.setTextsOf() };
    if (k === 'title' ? !v || v === (this.d.title?.part || this.hooks.partName(this.d.source)) : v === (inh[k] || '')) delete x[k]; // (as it would be anyway)
    else x[k] = v; // ('' over a template's / the set's text: empty here)
    this.d.texts = x;
    this.commit();
    this.askAll(k, v);
  }

  /** "Přepsat i ve všech listech sestavy?" — next to the title block, not in the way: Ano / Jen tady, and "neptat se
   *  znovu" (this field's answer kept for the session). Only for the fields tbedit.js TB_EDIT lets go to the set. */
  askAll(k, v) {
    this.dropAsk();
    const asm = !!this.d.asm && !this.d.bom, root = this.hooks.drawingCtx ? this.rootOf(this.d.source) : null;
    if (!root || !propagates(k, asm)) return;
    const n = this.pagesOf(root).filter((p) => TB_EDIT[k].propagate === true || p.kind === 'assembly').length;
    if (n < 2) return;
    const was = remembered.get(k);
    if (was === 'here') return;
    if (was === 'all') { this.setTextsAll({ [k]: v }); return; }
    const vp = this.els.viewport, R = vp.getBoundingClientRect(), tb = this.svgEl?.querySelector('.sh-title')?.getBoundingClientRect();
    const cell = this.svgEl?.querySelector(`.sh-title [data-tcell="${k}"]`)?.getBoundingClientRect(), box = document.createElement('div');
    box.className = 'sh-tbask';
    box.innerHTML = `<p><b>${esc(tv('Overwrite it on all sheets of the assembly “{asm}” too?', { asm: this.hooks.partName(root) || root }))}</b> <span class="muted">${esc(tv('({n} sheets)', { n }))}</span></p>
      <p class="hint">${esc(t(TB_EDIT[k].label))}: <b data-no-i18n>${esc(v || '—')}</b>${TB_EDIT[k].propagate === 'typed' ? ` · ${esc(t('the parts keep the material of their own models'))}` : ''}</p>
      <div class="row-actions"><button class="btn small primary" data-a="all" title="${esc(t('Every sheet of the drawing set shows this text — also the pages that have no sheet of their own yet'))}">${esc(t('Yes'))}</button>
        <button class="btn small" data-a="here" title="${esc(t('Only this drawing says it'))}">${esc(t('Only here'))}</button>
        <label class="check" title="${esc(t('This field\'s answer is kept until the app is closed'))}"><input type="checkbox" data-k="remember"> ${esc(t('don\'t ask again'))}</label></div>`;
    vp.appendChild(box);
    const at = cell || tb;
    if (at) {
      const w = box.offsetWidth, top = (tb || at).top - R.top - box.offsetHeight - 8;
      Object.assign(box.style, { left: `${Math.max(8, Math.min(R.width - w - 8, at.left - R.left))}px`, top: `${Math.max(54, top)}px` });
    }
    box.addEventListener('pointerdown', (e) => { if (!e.target.closest('input')) e.preventDefault(); }); // (the text being typed keeps its focus)
    const answer = (all) => {
      if (box.querySelector('[data-k=remember]').checked) remembered.set(k, all ? 'all' : 'here');
      this.dropAsk();
      if (all) this.setTextsAll({ [k]: v });
    };
    box.querySelector('[data-a=all]').addEventListener('click', () => answer(true));
    box.querySelector('[data-a=here]').addEventListener('click', () => answer(false));
    this.asking = box;
  }

  dropAsk() { this.asking?.remove(); this.asking = null; }

  /** Texts {field: value} on every sheet of this sheet's drawing set: kept as the set's (setTexts of the top assembly's
   *  sheet — made when it has none, as for a template — so the pages without a sheet of their own show them too), each
   *  sheet's own text of them taken away -> how many pages show them. Only the fields TB_EDIT lets go to the set. */
  setTextsAll(vals) {
    const root = this.rootOf(this.d.source), asm = !!this.d.asm && !this.d.bom;
    if (!root) return 0;
    vals = Object.fromEntries(Object.entries(vals).filter(([k]) => propagates(k, asm || k !== 'material')).map(([k, v]) => [k, String(v ?? '').trim()]));
    if (!Object.keys(vals).length) return 0;
    const pages = this.pagesOf(root), ids = new Set(pages.map((p) => p.id));
    if (!this.sheetsOf(new Set([root])).length) this.hooks.applyTemplate?.(root, this.tplName({ source: root }), [root]); // (the set's template stays as it was)
    const rs = this.sheetsOf(new Set([root]))[0];
    for (const d of this.sheetsOf(ids)) {
      const x = { ...(d.texts || {}) };
      for (const [k, v] of Object.entries(vals)) if (rs) delete x[k]; else x[k] = v;
      d.texts = x;
    }
    if (rs) rs.setTexts = { ...(rs.setTexts || {}), ...vals };
    this.history.commit();
    this.render();
    this.hooks.onChange?.();
    const n = pages.filter((p) => Object.keys(vals).some((k) => TB_EDIT[k].propagate === true) || p.kind === 'assembly').length;
    this.hooks.toast?.(tv('{fields} on all {n} sheets of {asm}.', { fields: Object.keys(vals).map((k) => t(TB_EDIT[k].label)).join(', '), n, asm: this.hooks.partName(root) || root }), 'ok', 5000);
    return n;
  }

  // ------------------------------------------------------------------ what is chosen, and its suggestions
  clearSel() { this.sel = null; this.selView = null; this.selGeo = null; this.selTitle = false; }

  /** The suggestions table (bottom left of the sheet) for what is chosen — or the sheet's next steps. */
  renderSuggest() {
    const vp = this.els.viewport, s = sheetSuggest(this);
    showSuggest(vp, s?.title || '', s?.items || [], s?.hint || '', s?.refs || '');
  }

  /** A dimension's own settings ({ref, tol, side …}; undefined / false: taken off) — an automatic one keeps them in
   *  d.dims (with its moved place). */
  setDimProps(id, props) {
    const u = this.d.user.find((x) => x.id === id), o = u || { ...(this.d.dims[id] || {}) };
    for (const [k, v] of Object.entries(props)) { if (v === undefined || v === false) delete o[k]; else o[k] = v; }
    if (!u) this.d.dims = { ...this.d.dims, [id]: o };
    this.commit();
  }

  /** Section A–A on (in the Right view's place, that view hidden) or off. */
  setSection(on) {
    if (on) { this.d.section = true; this.d.off = { ...this.d.off, Right: true }; } else delete this.d.section;
    if (!on && this.selView === 'Section') this.selView = null;
    this.history.commit();
    this.ensure(true);
  }

  /** The paper ('A4' / 'A3' / null: automatic) — the views placed again. */
  setPaper(p) { this.d.paper = p || null; this.d.views = {}; this.history.commit(); this.ensure(true); }

  /** A view taken off the sheet (Section A–A: the section off, the right view back). */
  hideView(v) {
    if (v === 'Section') { delete this.d.off.Right; this.setSection(false); return; }
    this.d.off = { ...this.d.off, [v]: true };
    if (this.selView === v) this.selView = null;
    this.commit();
    this.hooks.toast?.(tv('{v} hidden — ↶ or 👁 Show view brings it back.', { v: this.viewName(v) }), 'info', 3500);
  }

  /** The chosen edge's length / circle's Ø, R or hole callout as a dimension. */
  addGeoDim() {
    const g = this.selGeo;
    if (!g) return;
    this.selGeo = null;
    if (g.edge) { this.edgeLength(g.view, g.edge); return; }
    this.addUser((g.c.full && this.calloutFor(g.view, g.c.key)) || { view: g.view, kind: g.c.full ? 'dia' : 'rad', a: g.c.key, count: 1, ang: g.c.full ? 45 : 0, len: 6 });
  }

  /** ＋ Dimension from the chosen edge (or a circle's centre): the next click gives the distance / angle. */
  startDimFrom() {
    const g = this.selGeo, pts = g ? this.geo.views[g.view].points : {};
    this.clearSel();
    this.tool = 'dim';
    this.dimOnce = true;
    this.hoverEdge = null;
    if (g?.edge) this.pick = { view: g.view, edge: g.edge };
    else if (g?.c) { const key = Object.keys(pts).find((k) => Math.hypot(pts[k][0] - g.c.c[0], pts[k][1] - g.c.c[1]) < 1e-6); this.pick = key ? { view: g.view, key, at: this.P(g.view, g.c.c) } : null; }
    this.hint(t('Now click another edge or a point of the same view. Esc: done.'));
    this.render();
  }

  /** The right panel's "Company, logo and fields" opened and in sight. */
  openTitleMore() {
    this.clearSel();
    this.tbOpen = true;
    this.render();
    this.$('.sh-props .sh-tbmore')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  /** 🖨 Print: the sheet's PDF (the paper size it is drawn for) printed from a hidden frame. */
  async printPdf() {
    const svgs = [this.svg(true), ...(this.d.asm && this.d.bomPage && this.d.built ? this.bomPages(this.d.source, this.d, this.d.built).map((d) => this.svgOf(d)) : [])];
    const res = await fetch('/api/sheet/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ svgs, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast((await res.json()).error || res.statusText, 'error'); return; }
    const url = URL.createObjectURL(await res.blob());
    document.querySelector('iframe.sh-print')?.remove();
    const f = Object.assign(document.createElement('iframe'), { className: 'sh-print', src: url, title: 'print' });
    f.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0';
    f.addEventListener('load', () => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch { window.open(url, '_blank'); } });
    document.body.appendChild(f);
    this.hooks.toast?.(t('Printing the sheet — choose the printer in the dialog (the paper as drawn, landscape).'), 'info', 4000);
  }

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
        if (/^(box|base)#/.test(k) || k.endsWith('#m')) continue;
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
        const C = this.P(v, c.c), R = c.r * this.vs(v);
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
      if (ci) { this.addUser((ci.c.full && this.calloutFor(ci.view, ci.c.key)) || { view: ci.view, kind: ci.c.full ? 'dia' : 'rad', a: ci.c.key, count: 1, ang: ci.c.full ? 45 : 0, len: 6 }); return; } // (a hole: its callout)
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
    if (this.dimOnce) { this.dimOnce = false; this.tool = 'select'; this.pick = null; this.hoverEdge = null; this.hint(''); } // (one dimension from a suggestion: back to choosing, its table shows)
    this.commit();
  }

  bind() {
    let drag = null;
    this.stage.addEventListener('pointerdown', (e) => {
      if (!this.svgEl || e.button !== 0) return;
      const p = this.paperAt(e);
      if (this.tool === 'dim') { this.clickDim(p); return; }
      const dimEl = e.target.closest('[data-dim]'), viewEl = e.target.closest('[data-view]'), cell = e.target.closest('[data-tcell]');
      this.dropAsk(); // (a click elsewhere: the question not answered — the text stays this sheet's)
      if (this.editing) this.endEdit(true); // (a click elsewhere: the typed text kept)
      if (cell) e.preventDefault(); // (the mouse's own focus change would take the cell's text box away again)
      const lab = e.target.closest('[data-vlabel]');
      const again = lab && this.lastLabel?.v === lab.dataset.vlabel && performance.now() - this.lastLabel.at < 400;
      this.lastLabel = lab ? { v: lab.dataset.vlabel, at: performance.now() } : null;
      if (again) { e.preventDefault(); this.lastLabel = null; this.renameOnSheet(lab.dataset.vlabel); return; } // a double-click on a view's name: rename it
      const balloon = e.target.closest('[data-balloon]');
      if (balloon) { drag = { kind: 'balloon', pos: balloon.dataset.balloon, moved: false }; this.stage.setPointerCapture(e.pointerId); return; }
      if (dimEl) {
        this.clearSel();
        this.sel = dimEl.dataset.dim;
        drag = { kind: 'dim', id: this.sel, d: this.allDims().find((x) => x.id === this.sel), moved: false };
      } else if (viewEl) {
        const v = viewEl.dataset.view;
        drag = { kind: 'view', v, p, start: p, from: v === 'Iso' ? (this.d.views.Iso || this.lay.iso.slice(0, 2)) : this.centre(v), moved: false };
      } else {
        drag = { kind: 'pan', start: [e.clientX, e.clientY], from: { ...this.zoom }, moved: false, title: !!e.target.closest('.sh-title'), cell: cell?.dataset.tcell, ro: !!cell?.dataset.ro };
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
        if (Math.hypot(e.clientX - drag.start[0], e.clientY - drag.start[1]) > 3) drag.moved = true;
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
        this.d.views[drag.v] = this.snapView(drag.v, [drag.from[0] + p[0] - drag.start[0], drag.from[1] + p[1] - drag.start[1]], e.shiftKey);
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
          const C = this.P(d.view, c.c), R = c.r * this.vs(d.view), deg = Math.atan2(-(p[1] - C[1]), p[0] - C[0]) * 180 / Math.PI;
          if (d.kind === 'rad') o.ang = deg - Math.atan2(-(c.pm[1] - c.c[1]), c.pm[0] - c.c[0]) * 180 / Math.PI; else o.ang = Math.round(deg);
          o.len = Math.max(2, Math.round(Math.hypot(p[0] - C[0], p[1] - C[1]) - R));
        }
        this.setDim(d, o);
      }
      this.render();
    });
    this.stage.addEventListener('pointerup', () => {
      const had = this.guides?.length;
      this.guides = null;
      if (drag?.moved && drag.kind !== 'pan') { this.commit(); if (drag.kind === 'view') this.replace(); } // (a view dropped: its dimensions placed clear again)
      else if (drag && !drag.moved) this.clickSelect(drag); // (a click: what is under it chosen, its suggestions shown)
      else if (had) this.render();
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
      if (this.editing) this.endEdit(true);
      this.dropAsk();
      const r = this.stage.getBoundingClientRect(), f = e.deltaY < 0 ? 1.15 : 1 / 1.15, k = Math.min(12, Math.max(0.3, this.zoom.k * f));
      const mx = e.clientX - r.left - r.width / 2, my = e.clientY - r.top - r.height / 2; // the SVG scales about the stage's middle
      this.zoom.x = mx - (mx - this.zoom.x) * (k / this.zoom.k);
      this.zoom.y = my - (my - this.zoom.y) * (k / this.zoom.k);
      this.zoom.k = k;
      this.applyZoom();
    }, { passive: false });
  }

  /** A click (no drag): a view's edge or circle under it, else the view; the title block; empty paper: nothing. */
  clickSelect(drag) {
    if (drag.kind === 'dim' || drag.kind === 'balloon') { this.render(); return; }
    this.clearSel();
    if (drag.kind === 'view') {
      const v = drag.v, c = v !== 'Iso' ? this.circleAt(drag.p, 1.2) : null, ed = v !== 'Iso' && !c ? this.edgeAt(drag.p, 1) : null;
      if (c?.view === v) this.selGeo = { view: v, c: c.c };
      else if (ed?.view === v) this.selGeo = { view: v, edge: ed.edge };
      else this.selView = v;
    } else if (drag.title) this.selTitle = true;
    this.render();
    if (drag.cell && !drag.ro) this.editCell(drag.cell); // a cell of the title block: type into it right there
    else if (drag.cell) this.cellHint(this.cellTip(drag.cell));
  }

  /** A computed cell clicked: where its value comes from, in the hint for a few seconds. */
  cellHint(text) {
    this.hint(text);
    clearTimeout(this.tipT);
    this.tipT = setTimeout(() => { if (this.$('.sh-hint').textContent === text) this.hint(''); }, 4000);
  }

  /** A view dragged to `at` (its centre, paper mm): in line with the views it is projected from / to — Top under (or
   *  over) Front, Right and Section A–A beside it — when within 4 mm (a dashed guide shows it); free with Shift. */
  snapView(v, at, free = false) {
    this.guides = [];
    if (free || v === 'Iso') return at;
    const shown = this.drawn().filter((w) => w !== v), [pw, ph] = this.lay.size, out = [...at];
    const xs = v === 'Front' ? ['Top'] : v === 'Top' ? ['Front'] : [], ys = v === 'Front' ? ['Right', 'Section'] : v === 'Right' || v === 'Section' ? ['Front'] : [];
    const near = (k, list) => list.filter((w) => shown.includes(w)).map((w) => this.centre(w)[k]).find((c) => Math.abs(c - at[k]) < 4);
    const x = near(0, xs), y = near(1, ys);
    if (x !== undefined) { out[0] = x; this.guides.push([x, 0, x, ph]); }
    if (y !== undefined) { out[1] = y; this.guides.push([0, y, pw, y]); }
    return out;
  }

  /** The moved place of a dimension: an automatic one keeps it in `dims`, the user's in itself. */
  setDim(d, o) {
    const u = this.d.user.find((x) => x.id === d.id);
    if (u) Object.assign(u, o); else this.d.dims[d.id] = o;
  }

  key(e) {
    if (e.key === 'Escape' && document.querySelector('#shLeft .sh-vmenu.open')) { this.closeViewMenus(); e.preventDefault(); return; }
    if (e.key === 'Escape' && this.asking && !e.target.closest?.('input,select,textarea')) { this.dropAsk(); e.preventDefault(); return; }
    if (!this.active || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    if (e.key === 'Enter' && this.tool === 'dim' && this.pick?.edge) { this.edgeLength(this.pick.view, this.pick.edge); e.preventDefault(); return; } // its length
    if (e.key === 'Escape' && this.tool === 'dim') { if (this.pick) { this.pick = null; this.render(); } else this.action('dim'); e.preventDefault(); }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel) { this.remove(this.sel); e.preventDefault(); } else if ((e.key === 'Delete' || e.key === 'Backspace') && this.selView) { this.hideView(this.selView); e.preventDefault(); }
    if (e.key === 'Escape' && this.tool === 'select' && (this.sel || this.selView || this.selGeo || this.selTitle)) { this.clearSel(); this.render(); e.preventDefault(); }
    if (e.ctrlKey && e.key.toLowerCase() === 'z') { this.history.go(-1); e.preventDefault(); }
    if (e.ctrlKey && e.key.toLowerCase() === 'y') { this.history.go(1); e.preventDefault(); }
  }

  async exportPdf() {
    const svgs = [this.svg(true), ...(this.d.asm && this.d.bomPage && this.d.built ? this.bomPages(this.d.source, this.d, this.d.built).map((d) => this.svgOf(d)) : [])];
    const res = await fetch('/api/sheet/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ svgs, name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast((await res.json()).error || res.statusText, 'error'); return; }
    await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.pdf`);
  }

  /** The sheet for /api/sheet/dxf: its SVG as printed, its dimensions (dxfDims) and its scale. */
  dxfData() { return { svg: this.svg(true), dims: this.dxfDims(), scale: this.scale() }; }

  async exportDxf() {
    const res = await fetch('/api/sheet/dxf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...this.dxfData(), name: this.hooks.safeName() }) });
    if (!res.ok) { this.hooks.toast((await res.json()).error || res.statusText, 'error'); return; }
    if (await this.hooks.download(await res.blob(), `${this.hooks.safeName()}.dxf`)) this.hooks.toast(t('Exported the sheet as a DXF (mm, the paper 1:1, the views at the sheet\'s scale, real dimensions).'), 'ok', 6000);
  }

  /** The dimensions shown, where dimSvg draws them (paper mm, y down) — for the DXF's own dimensions: linear {dir, a, b,
   *  at (the dimension line's y / x)}, dia / rad {c, r (on the paper), u (out from the centre), end (the leader's end)},
   *  ang {X, u1, u2, r}; each with its text and value. */
  dxfDims() {
    const out = [], zeros = new Set();
    for (const d of this.allDims()) {
      const v = this.value(d);
      if (v === null) continue;
      const base = { id: d.id, kind: d.kind, text: this.dimText(d, v), value: v, scale: this.vs(d.view) }; // (its view's scale: a view at its own)
      if (d.kind === 'ang') {
        const a = this.angleOf(d);
        if (a) out.push({ ...base, X: this.P(d.view, a.X), u1: [a.u1[0], -a.u1[1]], u2: [a.u2[0], -a.u2[1]], r: d.r ?? 15 });
      } else if (d.kind === 'dia' || d.kind === 'rad' || d.kind === 'pcd') {
        const c = this.circleOf(d.view, d.a);
        if (!c) continue;
        if (d.kind === 'pcd') base.kind = 'dia'; // (a bolt circle: a Ø dimension of its pitch circle)
        const C = this.P(d.view, c.c), R = c.r * this.vs(d.view);
        const ang = (d.kind === 'rad' ? Math.atan2(-(c.pm[1] - c.c[1]), c.pm[0] - c.c[0]) * 180 / Math.PI + (d.ang || 0) : d.ang ?? 45) * Math.PI / 180;
        const u = [Math.cos(ang), -Math.sin(ang)];
        out.push({ ...base, c: C, r: R, u, end: [C[0] + u[0] * (R + (d.len ?? 6)), C[1] + u[1] * (R + (d.len ?? 6))] });
      } else {
        const gv = this.geo.views[d.view], pa = gv.points[d.a], pb = gv.points[d.b];
        if (!pa || !pb) continue;
        const box = this.paperBox(d.view), off = d.off ?? 8;
        const at = d.dir === 'h' ? (d.side === 't' ? box[1] - off : box[3] + off) : (d.side === 'l' ? box[0] - off : box[2] + off);
        if (d.ord) { // an ordinate: from the edge (origin) to its point, its value past the row; the row's 0 once
          const z = `${d.view}|${d.dir}|${d.side}|${off}`, o = this.P(d.view, pa);
          if (!zeros.has(z)) { zeros.add(z); out.push({ ...base, id: `${d.id}:0`, kind: 'ord', text: '0', value: 0, dir: d.dir, origin: o, at: o, row: at, sh: 0 }); }
          out.push({ ...base, kind: 'ord', dir: d.dir, origin: o, at: this.P(d.view, pb), row: at, sh: d.sh || 0 });
          continue;
        }
        out.push({ ...base, dir: d.dir, a: this.P(d.view, pa), b: this.P(d.view, pb), at });
      }
    }
    return out;
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
   *  {view, circle: key} (its Ø, or R of an arc; a hole step's circle: its callout "M3 ⌵ Ø5 × 90°") -> its id. */
  addFor(spec) {
    const g = this.geo?.views[spec.view];
    if (!g) throw new Error(`view is one of ${VIEWS.join(', ')}.`);
    if (spec.circle) {
      const c = g.circles.find((x) => x.key === spec.circle);
      if (!c) throw new Error(`No circle ${spec.circle} in ${spec.view} — get_sheet {points: "${spec.view}"} lists them.`);
      const co = c.full && !spec.post && this.calloutFor(spec.view, c.key);
      if (co) { this.addUser(co); return this.sel; }
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
    return { check: ck ? { fully_dimensioned: ck.ok && !ck.over.size, missing: ck.missing.map((m) => `${m.view}: ${m.what}${m.ax ? ` (${m.ax})` : ''} [${m.key}]`).slice(0, 30), twice: [...ck.dup, ...ck.over], ...(ck.assembly ? { asks_for: 'an assembly sheet: only its overall sizes (length, width, height) and where its base part\'s mounting holes are (its holes no screw / pin of the assembly is in) — each part\'s details belong on its own sheet, a bought part\'s nowhere' } : {}) } : null,
      part: this.hooks.partName(this.d.source), ...(Object.keys(this.d.texts || {}).length ? { texts: this.d.texts } : {}), preset: this.d.preset, ...(Object.keys(this.d.vpreset || {}).length ? { view_presets: this.d.vpreset } : {}), paper: this.lay?.paper, rev: this.d.rev, changed: this.d.changed,
      views: [...VIEWS, 'Iso'].filter((v) => !this.d.off[v]),
      scale: `${scaleText(this.scaleArr())}${this.d.scale ? '' : ' (auto)'}`,
      template: `${this.tplName()}${this.d.template ? '' : this.tplName() === DEFAULT_TPL.name ? ' (default)' : ' (the drawing set\'s)'}`,
      templates: this.tpls.map((x) => x.name),
      title_style: this.tb().style, bom_style: this.tb().bomStyle,
      frame: (({ preset, m, line, zones, marks }) => ({ preset, margins_mm: m, line, zones, marks, ...(this.d.frame ? {} : { from: 'the template' }) }))(this.frameOf()),
      ...(Object.keys(this.d.vscale || {}).length ? { view_scales: Object.fromEntries(Object.entries(this.d.vscale).map(([v, s]) => [v, scaleText(s)])) } : {}),
      ...(Object.keys(this.d.viewNames || {}).length ? { view_names: this.d.viewNames } : {}),
      ...(this.outside().length ? { past_the_frame: this.outside() } : {}),
      dims: this.allDims().map((d) => ({ id: d.id, view: d.view, kind: d.kind, text: this.value(d) === null ? null : this.dimText(d, this.value(d)), auto: !!d.auto, ...(this.value(d) === null ? { lost: true } : {}),
        ...(d.pos ? { hole_position: d.pos } : {}), ...(d.ord ? { ordinate: true } : {}), ...(d.tol ? { tol: d.tol } : {}), ...(d.ref ? { ref: true } : {}) })),
      deleted_auto: this.d.hidden.length,
      ...(this.d.asm?.rows ? { parts_list: this.d.asm.rows.map((r) => ({ pos: r.pos, name: r.name, part: r.part, qty: r.qty, ...(r.instances ? { instances: r.instances } : {}),
        balloon: this.balloonAt?.[r.pos] ? { at_mm: this.balloonAt[r.pos].at, leader_to_mm: this.balloonAt[r.pos].end, points_to: r.at || r.instances?.[0] || null } : null })),
      balloons: this.balloonCheck() } : {}) };
  }

  /** For the AI: do an assembly sheet's balloons agree with its parts list? One item per part on this level (a
   *  sub-assembly one item), its qty the copies placed here, one balloon each, pointing at one of its copies ->
   *  {count, ok, problems: [text]}. */
  balloonCheck() {
    const rows = this.d.asm?.rows || [], out = [], here = new Map(), drawn = !this.d.off.Iso && !!this.isoMap;
    for (const it of this.hooks.partData(this.d.source)?.instances || []) here.set(it.part, (here.get(it.part) || 0) + 1);
    const pos = new Map();
    for (const r of rows) pos.set(r.pos, [...(pos.get(r.pos) || []), r.name]);
    for (const [p, names] of pos) if (names.length > 1) out.push(`pos ${p} is given to ${names.length} items (${names.join(', ')})`);
    for (const r of rows) {
      const n = here.get(r.part) ?? r.instances?.length ?? r.qty;
      if (+r.qty !== n) out.push(`pos ${r.pos} ${r.name}: qty ${r.qty} but ${n} placed on this level`);
      const b = this.balloonAt?.[r.pos];
      if (drawn && !b) out.push(`pos ${r.pos} ${r.name}: no balloon (no copy of it shows in the iso view)`);
      if (b && r.at && !(r.instances || []).includes(r.at)) out.push(`pos ${r.pos} ${r.name}: its balloon points at ${r.at}, not one of its copies`);
    }
    for (const p of here.keys()) if (!rows.some((r) => r.part === p)) out.push(`${this.hooks.partName(p) || p}: placed but not in the parts list (the sheet is older — it is made again when the assembly changes)`);
    return { count: Object.keys(this.balloonAt || {}).length, ok: !out.length, ...(drawn ? {} : { note: 'the iso view is off: no balloons' }), problems: out };
  }
}
