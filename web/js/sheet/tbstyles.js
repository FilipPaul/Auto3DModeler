// The drawing sheet's title-block and parts-list styles A–E (📄), drawn as SVG in mm for the screen and the PDF — as
// the owner's chosen designs (drawn at 5 px = 1 mm; every size here is theirs / 5):
//   A "Strip" 180 × 21 (IBM Plex Sans Condensed), B "ISO 7200" 180 × 40 (IBM Plex Sans), C "Dark band" 180 × 34
//   (Barlow), D "Minimal" 170 × 28 (Inter), E "Column" 90 × 56 (IBM Plex Sans Condensed); each with its parts list.
// Any title block goes with any parts list (a template's titleStyle and bomStyle). The fonts are in web/fonts (OFL);
// every text says its font (data-ff), so auto3d/modeler/sheet.py pdf() writes it with the same font file.
import { t, getLang } from '../i18n.js';
import { hitRect } from './tbedit.js';

/** The fonts: data-ff -> the CSS family (web/fonts/fonts.css; the PDF: auto3d/modeler/sheet.py FONT_FILES). */
export const FAMILY = { plexc: 'IBM Plex Sans Condensed', plex: 'IBM Plex Sans', barlow: 'Barlow', inter: 'Inter' };
const WEIGHTS = { plexc: [400, 600, 700], plex: [400, 500, 600, 700], barlow: [400, 600, 700], inter: [400, 500, 600, 700] };
/** Resolves when the styles' fonts are loaded (texts are measured with them: fit, right-aligned). */
export const fontsReady = typeof document === 'undefined' || !document.fonts ? Promise.resolve()
  : Promise.all(Object.entries(WEIGHTS).flatMap(([k, ws]) => ws.map((w) => document.fonts.load(`${w} 10px "${FAMILY[k]}"`)))).catch(() => null);

/** The title-block styles a sheet can use: [key, English name] (block / strip: the app's Modern ones). */
export const TITLE_STYLES = [['block', 'Modern'], ['strip', 'Modern — strip'], ['A', 'A — Strip'], ['B', 'B — ISO 7200'], ['C', 'C — Dark band'], ['D', 'D — Minimal'], ['E', 'E — Column']];
/** The parts-list styles: [key, English name]. */
export const BOM_STYLES = [['modern', 'Modern'], ['A', 'A — Strip'], ['B', 'B — ISO 7200'], ['C', 'C — Dark band'], ['D', 'D — Minimal'], ['E', 'E — Column']];
export const STYLE_TIPS = {
  block: 'The app\'s clean title block: the name large, then its facts in two rows', strip: 'The app\'s low strip: one row — the most room for the views',
  A: '180 × 21 mm, one row: the name, drawing no., material, scale, sheet, revision', B: '180 × 40 mm, the full ISO 7200 grid: drawn / checked / approved, material, mass, tolerances, roughness, projection',
  C: '180 × 34 mm, a black band with the name and drawing no., the facts below', D: '170 × 28 mm, no grid: the name large, six facts beside it',
  E: '90 × 56 mm, a narrow column in the corner — the most room beside it',
};

const TB = { A: { w: 180, h: 21, ff: 'plexc' }, B: { w: 180, h: 40, ff: 'plex' }, C: { w: 180, h: 34, ff: 'barlow' }, D: { w: 170, h: 28, ff: 'inter' }, E: { w: 90, h: 56, ff: 'plexc' } };
export const isStyle = (s) => !!TB[s];
/** A style's title block [width, height] (mm), or null (the Modern ones: sheet.js). */
export const titleSize = (s) => (TB[s] ? [TB[s].w, TB[s].h] : null);

const INK = '#111418', MUTED = '#5b6470', SUB = '#3d4450', RULE = '#c3c8cf', HAIR = '#e3e6ea', BAND = '#1d2127', ONBAND = '#c9ced6';
const n2 = (v) => +(+v).toFixed(2);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const up = (s) => String(s ?? '').toLocaleUpperCase(getLang() === 'cs' ? 'cs' : 'en');

let ctx2d = null;
/** A text's width (mm) in a style's font: the canvas measures it with the loaded font (+ letter spacing per letter). */
export function measure(s, fs, ff, w = 400, ls = 0) {
  s = String(s ?? '');
  if (!s) return 0;
  if (typeof document === 'undefined') return s.length * fs * 0.52 + ls * s.length;
  ctx2d = ctx2d || document.createElement('canvas').getContext('2d');
  ctx2d.font = `${w} 100px "${FAMILY[ff]}", Helvetica, Arial, sans-serif`;
  return (ctx2d.measureText(s).width * fs) / 100 + ls * s.length;
}

/** The SVG of a style's texts, lines and boxes. */
class Pen {
  constructor(ff) { this.ff = ff; this.g = []; }

  /** A text at its baseline; max: clipped with … to that width; shrink: [the smallest size] to fit before clipping. */
  text(x, y, s, { fs = 3, w = 400, fill = INK, anchor = 'start', ls = 0, max = 0, shrink = 0 } = {}) {
    s = String(s ?? '');
    if (!s) return 0;
    if (max > 0 && shrink) while (fs > shrink && measure(s, fs, this.ff, w, ls) > max) fs = n2(fs - 0.1);
    if (max > 0 && measure(s, fs, this.ff, w, ls) > max) {
      while (s.length > 1 && measure(`${s}…`, fs, this.ff, w, ls) > max) s = s.slice(0, -1).trimEnd();
      s = `${s}…`;
    }
    this.g.push(`<text data-ff="${this.ff}" font-family="'${FAMILY[this.ff]}', Helvetica, Arial, sans-serif" font-weight="${w}" x="${n2(x)}" y="${n2(y)}" font-size="${n2(fs)}" fill="${fill}"${anchor !== 'start' ? ` text-anchor="${anchor}"` : ''}${ls ? ` letter-spacing="${ls}"` : ''}>${esc(s)}</text>`);
    return measure(s, fs, this.ff, w, ls);
  }

  line(x1, y1, x2, y2, stroke = RULE, sw = 0.2) { this.g.push(`<line x1="${n2(x1)}" y1="${n2(y1)}" x2="${n2(x2)}" y2="${n2(y2)}" stroke="${stroke}" stroke-width="${sw}"/>`); }

  rect(x, y, w, h, fill = 'none', stroke = 'none', sw = 0) { this.g.push(`<rect x="${n2(x)}" y="${n2(y)}" width="${n2(w)}" height="${n2(h)}" fill="${fill}"${stroke !== 'none' ? ` stroke="${stroke}" stroke-width="${sw}"` : ''}/>`); }

  /** A cell to click and type into (tbedit.js; a computed one: its tooltip says where it comes from). */
  hit(key, x, y, w, h) { this.g.push(hitRect(key, x, y, w, h, this.ro)); }

  /** The first-angle projection symbol (ISO 5456-2): the cone's side (its big end at x) and its end view, H high. */
  projection(x, cy, H, col = INK, sw = 0.24) {
    const L = 1.5 * H, c = x + L + 1.08 * H;
    this.g.push(`<path d="M${n2(x)},${n2(cy - H / 2)} L${n2(x + L)},${n2(cy - H / 4)} L${n2(x + L)},${n2(cy + H / 4)} L${n2(x)},${n2(cy + H / 2)} Z" fill="none" stroke="${col}" stroke-width="${sw}"/>`);
    for (const r of [0.58 * H, 0.29 * H]) this.g.push(`<circle cx="${n2(c)}" cy="${n2(cy)}" r="${n2(r)}" fill="none" stroke="${col}" stroke-width="${sw}"/>`);
    return L + 1.66 * H; // (its width)
  }

  image(href, x, y, w, h, align = 'xMinYMid') { this.g.push(`<image x="${n2(x)}" y="${n2(y)}" width="${n2(w)}" height="${n2(h)}" preserveAspectRatio="${align} meet" href="${esc(href)}"/>`); }
}

/** The company's mark: its logo, else its first word in capitals (RAFIONTECH), else the app's name. */
function mark(f) { const w = String(f.company || '').trim().split(/[\s,]+/)[0].replace(/[^\p{L}\p{N}&+-]/gu, ''); return up(w || 'Auto3DModeler'); }

/** A style's title block with its top-left corner at (x, y). f: the fields as text (sheet.js tbFields): name, kind,
 *  number, rev, material, mass, scale, paper, sheet, tol, surface, drawn, date, dateShort, checked, approved,
 *  company, address [lines], logo, ro (a Set: the cells computed on this sheet — the material of a part's). Each
 *  field's cell is a place to click and type (data-tcell, tbedit.js). */
export function titleBlock(style, x, y, f) {
  const S = TB[style], P = new Pen(S.ff), { w: W, h: H } = S;
  P.ro = f.ro;
  const label = (lx, ly, s, o = {}) => P.text(lx, ly, up(s), { fs: 1.8, fill: MUTED, ls: 0.12, ...o });
  const dash = (v) => (v === undefined || v === null || v === '' ? '—' : String(v));
  if (style === 'D') { P.rect(x, y, W, H, '#fff'); P.line(x, y, x + W, y, INK, 0.4); }
  else P.rect(x, y, W, H, '#fff', INK, 0.4);
  const word = (cx, base, fs, max, o = {}) => P.text(cx, base, mark(f), { fs, w: 700, ls: 0.2, max, shrink: fs * 0.6, ...o });
  if (style === 'A') { // one row: the mark | the name | drawing no. | material | scale | sheet | revision
    const X = [0, 24.4, 82.4, 112.4, 142.4, 154.4, 167.4, W];
    for (const v of X.slice(1, -1)) P.line(x + v, y + 0.2, x + v, y + H);
    if (f.logo) P.image(f.logo, x + 1.6, y + 1.4, 21.2, 8.6, 'xMidYMid');
    else word(x + 12.2, y + 9.7, 3.4, 21, { anchor: 'middle' });
    P.projection(x + 12.2 - 3.8, y + 13.3, 2.4);
    P.hit('company', x, y, 24.4, H);
    const cell = (i, lab, val, sub, pad, o = {}) => {
      const cx = x + X[i] + pad, cw = X[i + 1] - X[i] - 2 * pad;
      label(cx, y + 4.2, lab, { max: cw });
      P.text(cx, y + 11.6, dash(val), { fs: 3.6, w: 600, max: cw, shrink: 2.6, ...o });
      if (sub) P.text(cx, y + 18.4, sub, { fs: 2.4, fill: SUB, max: cw });
    };
    label(x + 27.2, y + 4.2, t('Name'));
    P.text(x + 27.2, y + 12.5, f.name, { fs: 6, w: 700, max: 52.4, shrink: 3.6 });
    P.text(x + 27.2, y + 18.4, [f.drawn ? `${t('Drawn by')} ${f.drawn}` : '', f.date, f.tol].filter(Boolean).join(' · '), { fs: 2.4, fill: SUB, max: 52.4 });
    P.hit('title', x + 24.4, y, 58, 14.2);
    P.hit('drawn', x + 24.4, y + 14.2, 58, H - 14.2);
    cell(2, t('Drawing no.'), f.number, f.mass ? `${t('Mass')} ${f.mass}` : '', 2.4);
    P.hit('number', x + 82.4, y, 30, 14.2);
    P.hit('mass', x + 82.4, y + 14.2, 30, H - 14.2);
    cell(3, t('Material'), f.material, f.surface || '', 2.4);
    P.hit('material', x + 112.4, y, 30, 14.2);
    P.hit('surface', x + 112.4, y + 14.2, 30, H - 14.2);
    cell(4, t('Scale'), f.scale, f.paper, 1.6);
    P.hit('scale', x + 142.4, y, 12, H);
    cell(5, t('Sheet'), f.sheet, '', 1.6);
    P.hit('sheet', x + 154.4, y, 13, H);
    cell(6, t('Revision'), f.rev, '', 1.6);
    P.hit('rev', x + 167.4, y, W - 167.4, H);
  } else if (style === 'B') { // ISO 7200: company + projection | a 2 × 4 grid of facts | the name over drawing no., rev, scale, sheet
    P.line(x + 34.4, y + 0.2, x + 34.4, y + H);
    P.line(x + 110.4, y + 0.2, x + 110.4, y + H);
    P.line(x + 0.2, y + 24.4, x + 34.4, y + 24.4);
    if (f.logo) P.image(f.logo, x + 2.8, y + 2.6, 28.8, 8);
    else word(x + 3.2, y + 7.4, 4, 28.4);
    const addr = [f.company, ...(f.address || [])].filter(Boolean).slice(0, f.logo ? 2 : 3);
    if (!addr.length) addr.push(t('Dimensions in mm'));
    addr.forEach((ln, i) => P.text(x + 3.2, y + 12.2 + 3.24 * i, ln, { fs: 2.4, fill: SUB, max: 28.8 }));
    P.hit('company', x, y, 34.4, 13.4);
    P.hit('address', x, y + 13.4, 34.4, 11);
    P.projection(x + 3.2, y + 32.2, 3.2, INK, 0.28);
    P.text(x + 15.96, y + 32.86, t('Projection'), { fs: 2.4, fill: SUB, max: 17.6 });
    P.text(x + 15.96, y + 36.1, t('ISO first angle'), { fs: 2.4, fill: SUB, max: 17.6 });
    const grid = [[t('Drawn by'), f.drawn, 'drawn'], [t('Date'), f.date, 'date'], [t('Checked'), f.checked, 'checked'], [t('Approved'), f.approved, 'approved'],
      [t('Material'), f.material, 'material'], [t('Mass'), f.mass, 'mass'], [t('Tolerances'), f.tol, 'tolstd'], [t('Roughness'), f.surface, 'surface']];
    for (let r = 1; r < 4; r++) P.line(x + 34.4, y + 0.4 + 9.9 * r, x + 110.4, y + 0.4 + 9.9 * r, HAIR);
    P.line(x + 72.4, y + 0.4, x + 72.4, y + H, HAIR);
    grid.forEach(([lab, val, key], i) => {
      const cx = x + (i % 2 ? 74.3 : 36.4), top = y + 0.4 + 9.9 * Math.floor(i / 2);
      label(cx, top + 3.0, lab, { max: 34 });
      P.text(cx, top + 6.4, dash(val), { fs: 3, w: 500, max: 34 });
      if (key) P.hit(key, cx - 1.9, top, 38, 9.9);
    });
    label(x + 113.6, y + 4.6, t('Name'));
    P.text(x + 113.6, y + 13.7, f.name, { fs: 6.8, w: 700, max: 63.2, shrink: 3.6 });
    P.text(x + 113.6, y + 19.6, f.kind, { fs: 2.4, fill: SUB, max: 63.2 });
    P.hit('title', x + 110.4, y, 69.6, 22.8);
    P.line(x + 110.4, y + 22.8, x + W, y + 22.8);
    const X = [110.4, 140.4, 152.4, 166.4, W];
    for (const v of X.slice(1, -1)) P.line(x + v, y + 22.8, x + v, y + H, HAIR);
    [[t('Drawing no.'), f.number, 2.8], [t('Rev.'), f.rev, 1.6], [t('Scale'), f.scale, 1.6], [t('Sheet'), f.sheet, 1.6]].forEach(([lab, val, pad], i) => {
      const cx = x + X[i] + pad, cw = X[i + 1] - X[i] - 2 * pad;
      label(cx, y + 26.6, lab, { max: cw });
      P.text(cx, y + 36.8, dash(val), { fs: 4, w: 700, max: cw, shrink: 2.6 });
    });
    P.hit('number', x + 110.4, y + 22.8, 30, 17.2);
    ['rev', 'scale', 'sheet'].forEach((k, i) => P.hit(k, x + X[i + 1], y + 22.8, X[i + 2] - X[i + 1], 17.2));
  } else if (style === 'C') { // a black band (the name, what it is; drawing no., rev) over the mark and five pairs of facts
    P.rect(x + 0.2, y + 0.2, W - 0.2, 12.2, BAND);
    const right = x + 176.4, revW = measure(`${t('rev.')} ${f.rev}`, 3, 'barlow');
    P.text(right, y + 8.2, `${t('rev.')} ${f.rev}`, { fs: 3, fill: ONBAND, anchor: 'end' });
    const numW = f.number ? P.text(right - revW - 2.8, y + 8.2, f.number, { fs: 4.4, w: 700, fill: '#fff', anchor: 'end', ls: 0.1, max: 46 }) : 0;
    const room = 176.4 - 4 - revW - (numW ? numW + 2.8 : 0) - 6;
    const nw = P.text(x + 4, y + 9, f.name, { fs: 6.4, w: 700, fill: '#fff', max: Math.max(20, room * 0.7), shrink: 3.6 });
    P.text(x + 4 + nw + 3.2, y + 9, f.kind, { fs: 2.8, fill: ONBAND, max: Math.max(0, room - nw - 3.2) });
    P.hit('title', x, y, 120, 12.4);
    P.hit('number', x + 120, y, 60, 12.4);
    const X = [0.2, 28.4, 60.3, 92.2, 124.1, 156, W];
    X.slice(1, -1).forEach((v, i) => P.line(x + v, y + 12.4, x + v, y + H, i === 0 || i === 4 ? RULE : HAIR));
    P.line(x + 28.4, y + 23.2, x + W, y + 23.2, HAIR);
    if (f.logo) P.image(f.logo, x + 3.2, y + 14.2, 22, 6.6);
    else word(x + 3.2, y + 18.2, 3.4, 22.4);
    P.projection(x + 3.6, y + 29.4, 2.8, INK, 0.26);
    P.hit('company', x, y + 12.4, 28.4, 21.6);
    const pairs = [[[t('Material'), f.material, 'material'], [t('Mass'), f.mass, 'mass']], [[t('Tolerances'), f.tol, 'tolstd'], [t('Roughness'), f.surface, 'surface']], [[t('Drawn by'), f.drawn, 'drawn'], [t('Date'), f.date, 'date']],
      [[t('Checked'), f.checked, 'checked'], [t('Sheet size'), f.paper, 'paper']], [[t('Scale'), f.scale, 'scale'], [t('Sheet'), f.sheet, 'sheet']]];
    pairs.forEach((pr, i) => pr.forEach(([lab, val, key], j) => {
      const cx = x + X[i + 1] + 2.4, cw = X[i + 2] - X[i + 1] - 4.4, big = i === 4;
      P.text(cx, y + (j ? 26.4 : 15.6), up(lab), { fs: 2, fill: MUTED, ls: 0.12, max: cw });
      P.text(cx, y + (j ? (big ? 31.2 : 30.2) : (big ? 20.4 : 19.4)), dash(val), { fs: big ? 4.4 : 3.4, w: big ? 700 : 600, max: cw, shrink: 2.6 });
      if (key) P.hit(key, x + X[i + 1], y + (j ? 23.2 : 12.4), X[i + 2] - X[i + 1], 10.8);
    }));
  } else if (style === 'D') { // no grid: the mark, the name large, drawing no. · rev · sheet | a hairline | six facts
    if (f.logo) P.image(f.logo, x + 3.6, y + 2.6, 40, 5);
    else word(x + 3.6, y + 6.6, 2.6, 50, { fill: SUB, ls: 0.4 });
    P.projection(x + 69.6 - 8.4, y + 5.4, 2.4, SUB, 0.24);
    P.hit('company', x, y, 74, 8);
    P.text(x + 3.6, y + 16.43, f.name, { fs: 6.8, w: 700, ls: -0.1, max: 66, shrink: 3.6 });
    P.hit('title', x, y + 8, 74, 10);
    const nw = f.number ? P.text(x + 3.6, y + 24.2, f.number, { fs: 4, w: 600, max: 34 }) : 0;
    P.text(x + 3.6 + (nw ? nw + 2.8 : 0), y + 24.2, `${t('rev.')} ${f.rev} · ${t('Sheet').toLocaleLowerCase()} ${f.sheet}`, { fs: 3, fill: MUTED, max: 66 - nw });
    P.hit('number', x, y + 18, 74, 10);
    P.rect(x + 82, y + 3.6, 0.2, 21.6, '#d3d7dc');
    const facts = [[t('Material'), f.material, 'material'], [t('Scale'), [f.scale, f.paper].filter(Boolean).join(' · '), 'scale'], [t('Drawn by'), f.drawn, 'drawn'],
      [t('Tolerances'), f.tol, 'tolstd'], [t('Mass'), f.mass, 'mass'], [t('Date'), f.date, 'date']];
    facts.forEach(([lab, val, key], i) => {
      const cx = x + 85.8 + 28.07 * (i % 3), top = i < 3 ? 0 : 11.8;
      P.text(cx, y + 5.6 + top, up(lab), { fs: 2, fill: MUTED, ls: 0.16, max: 24.4 });
      P.text(cx, y + 9.8 + top, dash(val), { fs: 3.2, w: 500, max: 24.4 });
      if (key) P.hit(key, cx - 1, y + 2 + top, 27, 10);
    });
  } else if (style === 'E') { // a column: the mark | the name, drawing no., rev | material, tolerances, mass | drawn, date, scale, sheet
    for (const v of [9.2, 28.4, 42.4]) P.line(x + 0.2, y + v, x + W, y + v);
    if (f.logo) P.image(f.logo, x + 3.2, y + 1.6, 40, 6);
    else word(x + 3.2, y + 5.9, 3.2, 60);
    P.projection(x + 87.2 - 7.6, y + 4.8, 2.4);
    P.hit('company', x, y, W, 9.2);
    label(x + 3.2, y + 13, t('Name'));
    P.text(x + 3.2, y + 19.7, f.name, { fs: 6, w: 700, max: 83.6, shrink: 3.6 });
    P.hit('title', x, y + 9.2, W, 11);
    const nw = f.number ? P.text(x + 3.2, y + 25.2, f.number, { fs: 3.6, w: 600, max: 60 }) : 0;
    P.text(x + 3.2 + (nw ? nw + 2.4 : 0), y + 25.2, `${t('rev.')} ${f.rev}`, { fs: 2.6, fill: SUB });
    P.hit('number', x, y + 20.2, W, 8.2);
    const row = (top, cells) => {
      const cw = (W - 0.4) / cells.length;
      cells.forEach(([lab, val, key], i) => {
        const cx = x + 0.4 + cw * i;
        if (i) P.line(cx, y + top, cx, y + top + 14, HAIR);
        label(cx + 2.4, y + top + 3.4, lab, { max: cw - 4 });
        P.text(cx + 2.4, y + top + 7.6, dash(val), { fs: 3, w: 600, max: cw - 4, shrink: 2.2 });
        if (key) P.hit(key, cx, y + top, cw, 14);
      });
    };
    row(28.4, [[t('Material'), f.material, 'material'], [t('Tolerances'), f.tol, 'tolstd'], [t('Mass'), f.mass, 'mass']]);
    row(42.4, [[t('Drawn by'), f.drawn, 'drawn'], [t('Date'), f.dateShort, 'date'], [t('Scale'), f.scale, 'scale'], [t('Sheet'), f.sheet, 'sheet']]);
  }
  return `<g class="sh-title" data-style="${style}">${P.g.join('')}</g>`;
}

// ------------------------------------------------------------------------------------------------ the parts lists
/** Each style's parts list: its font, width, header (on top; B: a grey band at the bottom, the rows numbered
 *  bottom-up), row height, rules, summary line — and its columns' widths (mm, as drawn 180 wide; scaled to the
 *  width it gets). */
const BOMS = {
  A: { ff: 'plexc', w: 180, row: 8.2, top: 7.4, foot: 6.8, cols: { pos: 10, name: 58, qty: 10, mat: 30, mass: 18, pn: 34, make: 19.6 } },
  B: { ff: 'plex', w: 180, row: 8.2, top: 0.4, band: 7.6, foot: 6.8, cols: { pos: 10, name: 56, qty: 10, mat: 30, mass: 18, pn: 34, make: 21.6 } },
  C: { ff: 'barlow', w: 180, row: 8.2, top: 15.4, foot: 0, cols: { pos: 10.8, name: 55.2, qty: 10, mat: 30, mass: 18, pn: 34, make: 21.6 } },
  D: { ff: 'inter', w: 170, row: 8.2, top: 14.6, foot: 0, pad: 3.6, cols: { pos: 8.8, name: 50, qty: 8.8, mat: 28, mass: 16, pn: 32, make: 19.2 } },
  E: { ff: 'plexc', w: 90, row: 10.2, top: 7, foot: 6, cols: { pos: 8, name: 38, qty: 8, mat: 35.6 } },
};
export const isBomStyle = (s) => !!BOMS[s];
export const bomWidth = (s) => BOMS[s]?.w || null;
/** How tall a style's list of n rows is (mm). */
export const bomHeight = (s, n) => { const B = BOMS[s]; return B.top + (B.band || 0) + B.foot + B.row * n; };
/** How many rows fit in h mm (at least 1). */
export const bomRowsIn = (s, h) => { const B = BOMS[s]; return Math.max(1, Math.floor((h - B.top - (B.band || 0) - B.foot) / B.row)); };

/** Grams as the list writes them: 102 g, 11,9 g, 0,42 g, 1,25 kg (a decimal comma in Czech); null: —. */
export function grams(g) {
  if (g === null || g === undefined || !Number.isFinite(+g)) return '—';
  g = +g;
  const [v, u] = g >= 10000 ? [g / 1000, 'kg'] : [g, 'g'], a = Math.abs(v);
  const s = String(+v.toFixed(a >= 100 ? 0 : a >= 10 ? 1 : 2));
  return `${getLang() === 'cs' ? s.replace('.', ',') : s} ${u}`;
}

/** "6 items", "6 položek": a count with its word (Czech: 1 / 2–4 / 5+). */
export function count(n, one, many) {
  if (getLang() !== 'cs') return `${n} ${n === 1 ? one : many}`;
  return `${n} ${t(n === 1 ? one : n >= 2 && n <= 4 ? `${many} (2–4)` : many)}`;
}

/** The columns a list shows: the parts list of an assembly sheet (pos, name, qty, material, mass, standard / order
 *  no., make or buy) or a BOM page's (summary: + mass total, maker; structured: qty per parent + total, maker). */
function columns(style, kind) {
  const B = BOMS[style], c = B.cols, m = style === 'A' ? t('Mass') : t('Mass/pc');
  const pn = style === 'B' ? t('Standard / order number') : t('Standard / order no.');
  if (style === 'E') return [{ k: 'pos', l: t('Pos.'), w: c.pos }, { k: 'name', l: t('Name / standard'), w: c.name }, { k: 'qty', l: t('Qty'), w: c.qty, r: 1 }, { k: 'mat', l: t('Material · make/buy'), w: c.mat }];
  const name = { k: 'name', l: style === 'B' ? t('Name / designation') : t('Name'), w: c.name };
  if (kind === 'summary') return [{ k: 'pos', l: t('Pos.'), w: c.pos }, name, { k: 'qty', l: t('Qty'), w: c.qty, r: 1 }, { k: 'mat', l: t('Material'), w: c.mat }, { k: 'mass', l: m, w: c.mass, r: 1 },
    { k: 'mass_total', l: t('Mass total'), w: c.mass + 2, r: 1 }, { k: 'maker', l: t('Maker'), w: 24, sub: 1 }, { k: 'pn', l: pn, w: c.pn, sub: 1 }, { k: 'make', l: t('Make/buy'), w: c.make, sub: 1 }];
  if (kind === 'structured') return [{ k: 'pos', l: t('Pos.'), w: c.pos }, name, { k: 'qty', l: t('Qty per parent'), w: c.qty + 6, r: 1 }, { k: 'total', l: t('Total qty'), w: c.qty + 4, r: 1 },
    { k: 'mat', l: t('Material'), w: c.mat }, { k: 'mass', l: m, w: c.mass, r: 1 }, { k: 'maker', l: t('Maker'), w: 24, sub: 1 }, { k: 'pn', l: pn, w: c.pn, sub: 1 }, { k: 'make', l: t('Make/buy'), w: c.make, sub: 1 }];
  return [{ k: 'pos', l: t('Pos.'), w: c.pos }, name, { k: 'qty', l: t('Qty'), w: c.qty, r: 1 }, { k: 'mat', l: t('Material'), w: c.mat }, { k: 'mass', l: m, w: c.mass, r: 1 },
    { k: 'pn', l: pn, w: c.pn, sub: 1 }, { k: 'make', l: t('Make/buy'), w: c.make, sub: 1 }];
}

/** A style's parts list, its bottom right corner at (x1, yb) — on the title block — W wide (else the style's).
 *  rows: [{pos, name, qty, total, mat, mass, mass_total, maker, pn, make, bold (a sub-assembly), depth}] as text;
 *  sum: {kinds, pieces, mass (text or '')}; o: {kind: 'sheet' | 'summary' | 'structured', more: a last line
 *  ("… 3 more"), title (C / D: the band's / heading's, B: its summary's; named: A / E's summary too — a BOM page)}
 *  -> {svg, h}. */
export function partsList(style, x1, yb, rows, sum, o = {}) {
  const B = BOMS[style], P = new Pen(B.ff), W = o.W || B.w, x0 = x1 - W, lines = rows.length + (o.more ? 1 : 0);
  const h = bomHeight(style, lines), y0 = yb - h, pad = B.pad || 0;
  const cols = columns(style, o.kind || 'sheet'), k = (W - 0.4 - 2 * pad) / cols.reduce((a, c) => a + c.w, 0);
  let cx = x0 + 0.4 + pad;
  for (const c of cols) { c.x = cx; c.w *= k; cx += c.w; }
  const items = count(sum.kinds, 'item', 'items'), pcs = count(sum.pieces, 'pc', 'pcs');
  const title = o.title || t('Parts list');
  if (style === 'D') { P.rect(x0, y0, W, h, '#fff'); P.line(x0, y0, x1, y0, INK, 0.4); }
  else P.rect(x0, y0, W, h, '#fff', INK, 0.4);
  // the header's labels
  const head = (base, o2) => cols.forEach((c, i) => {
    const pl = style === 'B' && i === 0 ? c.w / 2 : style === 'D' ? (c.k === 'mat' ? 2 : c.k === 'pn' ? 3.2 : 0) : style === 'C' ? 2 : c.k === 'pos' || c.k === 'qty' ? 1.6 : 2;
    const rx = c.x + c.w - (style === 'D' ? (c.k === 'qty' ? 1.6 : 0) : pl);
    P.text(c.r ? rx : style === 'B' && i === 0 ? c.x + c.w / 2 : c.x + pl, base, up(c.l), { ...o2, anchor: c.r ? 'end' : style === 'B' && i === 0 ? 'middle' : 'start', max: c.w - 1.6 });
  });
  // a row's cells
  const cell = (c, r, top) => {
    const v = r[c.k] ?? '', base = top + (style === 'C' ? 5.4 : style === 'B' ? 5.1 : 5.2), D = style === 'D';
    const pl = style === 'C' || style === 'B' ? 2 : D ? (c.k === 'mat' ? 2 : c.k === 'pn' || c.k === 'maker' ? 3.2 : 0) : c.k === 'pos' || c.k === 'qty' ? 1.6 : 2;
    const fs = style === 'C' ? 3.4 : style === 'B' ? 3 : 3.2, sfs = style === 'C' ? 3 : style === 'B' ? 2.6 : 2.8;
    if (c.k === 'pos') {
      if (style === 'C' && v !== '') {
        P.g.push(`<circle cx="${n2(c.x + 4.8)}" cy="${n2(top + 4)}" r="2.65" fill="none" stroke="${INK}" stroke-width="0.3"/>`);
        P.text(c.x + 4.8, top + 5, v, { fs: 2.8, w: 700, anchor: 'middle' });
      } else if (style === 'B') P.text(c.x + c.w / 2, base, v, { fs, w: 700, anchor: 'middle' });
      else P.text(c.x + pl, base, v, { fs, w: D ? 600 : 700, fill: D ? SUB : INK });
      return;
    }
    const ind = c.k === 'name' ? (r.depth || 0) * 3.5 : 0, max = c.w - pl - (c.r ? 1.2 : 1.6) - ind;
    const rx = c.x + c.w - (D ? (c.k === 'qty' ? 1.6 : 0) : pl);
    if (c.r) P.text(rx, base, v, { fs, w: c.k === 'qty' || c.k === 'total' ? 700 : 400, anchor: 'end', max });
    else if (c.sub) P.text(c.x + pl, base - 0.2 + (style === 'D' ? 0.1 : 0), v, { fs: sfs, fill: c.k === 'make' ? INK : D ? MUTED : SUB, max });
    else P.text(c.x + pl + ind, base, v, { fs, w: c.k === 'name' || r.bold ? 600 : 400, max });
  };
  if (style === 'E') { // two lines a row: name over its standard / drawing no.; material over make · mass
    head(y0 + 4.3, { fs: 1.8, fill: MUTED, ls: 0.12 });
    P.line(x0 + 0.2, y0 + 7, x1, y0 + 7, INK, 0.2);
    const [cp, cn, cq, cm] = cols;
    rows.forEach((r, i) => {
      const top = y0 + 7 + B.row * i;
      P.text(cp.x + 1.6, top + 6.2, r.pos ?? '', { fs: 3.2, w: 700 });
      P.text(cn.x + 1.6 + (r.depth || 0) * 2.5, top + 4.6, r.name, { fs: 3, w: 600, max: cn.w - 3.2 - (r.depth || 0) * 2.5 });
      P.text(cn.x + 1.6 + (r.depth || 0) * 2.5, top + 7.8, [r.pn, r.maker].filter(Boolean).join(' · '), { fs: 2.4, fill: SUB, max: cn.w - 3.2 });
      P.text(cq.x + cq.w - 1.6, top + 6.2, o.kind === 'structured' ? `${r.qty}/${r.total}` : r.qty, { fs: 3.2, w: 700, anchor: 'end', max: cq.w - 2 });
      P.text(cm.x + 1.6, top + 4.5, r.mat, { fs: 2.8, max: cm.w - 3.2 });
      P.text(cm.x + 1.6, top + 7.7, [r.make, r.mass && r.mass !== '—' ? r.mass : ''].filter(Boolean).join(' · '), { fs: 2.4, fill: SUB, max: cm.w - 3.2 });
      P.line(x0 + 0.2, top + B.row, x1, top + B.row, RULE);
    });
    if (o.more) P.text(x0 + 2, y0 + 7 + B.row * rows.length + 6.2, o.more, { fs: 2.6, fill: SUB });
    P.text(x0 + 2, yb - 2.1, `${o.named ? `${title} · ` : ''}${items} · ${pcs}`, { fs: 2.4, fill: SUB, max: W * 0.7 });
    if (sum.mass) P.text(x1 - 1.6, yb - 2.1, `Σ ${sum.mass}`, { fs: 2.4, fill: SUB, anchor: 'end' });
    return { svg: `<g class="sh-bom" data-style="E">${P.g.join('')}</g>`, h };
  }
  const tail = [sum.mass ? `${items} · ${pcs} · ${sum.mass}` : `${items} · ${pcs}`].join('');
  if (style === 'A') {
    head(y0 + 4.5, { fs: 2, fill: MUTED, ls: 0.12 });
    P.line(x0 + 0.2, y0 + 7.4, x1, y0 + 7.4, INK, 0.2);
  } else if (style === 'C') {
    P.rect(x0 + 0.2, y0 + 0.2, W - 0.2, 9, BAND);
    P.text(x0 + 3.6, y0 + 6.4, title, { fs: 4, w: 700, fill: '#fff', max: W * 0.5 });
    P.text(x1 - 3.2, y0 + 5.9, tail, { fs: 2.8, fill: ONBAND, anchor: 'end', max: W * 0.45 });
    head(y0 + 13.1, { fs: 2.2, w: 600, fill: MUTED, ls: 0.12 });
    P.line(x0 + 0.2, y0 + 15.4, x1, y0 + 15.4, INK, 0.2);
  } else if (style === 'D') {
    P.text(x0 + 3.6, y0 + 5.8, up(title), { fs: 2.6, w: 700, fill: SUB, ls: 0.4, max: W * 0.5 });
    P.text(x1 - 3.6, y0 + 5.8, tail, { fs: 2.6, fill: MUTED, anchor: 'end', max: W * 0.45 });
    head(y0 + 12.8, { fs: 2, fill: MUTED, ls: 0.16 });
    P.line(x0 + 3.6, y0 + 14.6, x1 - 3.6, y0 + 14.6, INK, 0.2);
  }
  const order = style === 'B' ? [...rows].reverse() : rows, off = style === 'B' && o.more ? 1 : 0;
  if (style === 'B' && o.more) P.text(x0 + 2.8, y0 + 0.4 + 5.1, o.more, { fs: 2.6, fill: SUB });
  order.forEach((r, i) => {
    const top = y0 + B.top + B.row * (i + off);
    for (const c of cols) cell(c, r, top);
    if (style === 'B') cols.slice(1).forEach((c) => P.line(c.x, top, c.x, top + 8, HAIR));
    if (style === 'D') P.line(x0 + 3.6, top + B.row, x1 - 3.6, top + B.row, HAIR);
    else P.line(x0 + 0.2, top + B.row, x1, top + B.row, style === 'C' ? '#d6dade' : RULE);
  });
  if (o.more && style !== 'B') P.text(x0 + 2.4 + pad, y0 + B.top + B.row * rows.length + 5.2, o.more, { fs: 2.6, fill: SUB });
  if (style === 'B') {
    const yb0 = y0 + 0.4 + B.row * lines;
    P.rect(x0 + 0.2, yb0, W - 0.2, 7.2, '#f1f3f5');
    P.line(x0 + 0.2, yb0 + 7.4, x1, yb0 + 7.4, INK, 0.4);
    head(yb0 + 4.3, { fs: 2, w: 600, fill: SUB, ls: 0.12 });
    P.text(x0 + 2.8, yb - 2.5, `${title} · ${items} · ${pcs}`, { fs: 2.6, fill: SUB });
    if (sum.mass) P.text(x1 - 2.4, yb - 2.5, `Σ ${sum.mass}`, { fs: 2.6, fill: SUB, anchor: 'end' });
  } else if (style === 'A') {
    P.text(x0 + 2.4, yb - 2.5, `${o.named ? `${title} · ` : ''}${tv('{items} · {pcs} in all', { items, pcs })}`, { fs: 2.6, fill: SUB, max: W * 0.7 });
    if (sum.mass) P.text(x1 - 2, yb - 2.5, tv('total mass {m}', { m: sum.mass }), { fs: 2.6, fill: SUB, anchor: 'end' });
  }
  return { svg: `<g class="sh-bom" data-style="${style}">${P.g.join('')}</g>`, h };
}
