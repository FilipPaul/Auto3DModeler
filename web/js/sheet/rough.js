// Surface roughness on the drawing sheet (ISO 21920-1, as ISO 1302 before it): the check-mark symbol on a surface's
// edge with its Ra in µm, and the general roughness in the title block. A symbol stands on its edge when the edge is
// on top of the view (its tip on the line, read from below); on any other edge it stands on a short reference line
// with a leader to the edge (an arrowhead on it). The symbol is drawn with lines, a circle and a text only — the PDF
// and the DXF (sheetdxf.py: layer "symbols") take it from the same SVG.
//
// Sheet JSON: rough: [{id, view, edge (its line's key), k (0…1 along it), off: [dx, dy] (paper mm from the point on the
// edge to the symbol's tip; [0, 0] / none: on the edge), ra (µm), proc: 'any' | 'remove' | 'keep'}]

/** The Ra values offered (µm, the R10 series a drawing uses): ground … rough. */
export const RA_LIST = [0.4, 0.8, 1.6, 3.2, 6.3, 12.5, 25];

/** Material removal — [label, tooltip]; the symbol: open ✓, closed by a bar (machined), a circle in it (not allowed). */
export const PROCS = {
  any: ['Any process', 'Any process — the basic symbol'],
  remove: ['Machined', 'Material must be removed (machined) — the symbol closed by a bar'],
  keep: ['No removal', 'Material must not be removed (as cast, printed or rolled) — a circle in the symbol'],
};

const fmt = (v) => (+(+v).toFixed(3)).toString();

/** A roughness as written: 3.2 / "3,2" / "Ra 3.2" / "ra3,2" -> "Ra 3.2"; text that is not one stays as it is; '' none. */
export function raText(v) {
  if (v === null || v === undefined || v === '') return '';
  const m = /^\s*(?:Ra\s*)?(\d+(?:[.,]\d+)?)\s*(?:µm|um)?\s*$/i.exec(String(v));
  return m ? `Ra ${fmt(m[1].replace(',', '.'))}` : String(v).trim();
}

/** A Ra value from what the user / the AI gives (3.2, "Ra 3,2") -> a number above 0, or null. */
export function raValue(v) {
  const m = /^\s*(?:Ra\s*)?(\d+(?:[.,]\d+)?)\s*(?:µm|um)?\s*$/i.exec(String(v ?? ''));
  const x = m ? +m[1].replace(',', '.') : NaN;
  return x > 0 && x < 1000 ? x : null;
}

const H1 = 3.5, H2 = 7.5, TAN = Math.tan(Math.PI / 6), FS = 3.2; // (ISO 21920 for a 2.5 mm text: H1 = 3.5, H2 = 7.5; legs 60° to the line)

/** How wide the symbol's text is (paper mm, as the sheet guesses a Helvetica text's width). */
const textW = (s) => s.length * FS * 0.56;

/** Where a symbol is: A the point on its edge, T its tip, n the edge's outward normal (paper, y down), on (it stands on
 *  the edge itself), or null (the edge is gone: the part changed). P(view, point) maps to the paper; centre: the
 *  view's centre on the paper. */
export function roughPlace(r, line, P, centre) {
  if (!line) return null;
  const a = P(line.a), b = P(line.b), k = Math.max(0, Math.min(1, r.k ?? 0.5));
  const A = [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  let n = [-(b[1] - a[1]) / L, (b[0] - a[0]) / L];
  if ((A[0] - centre[0]) * n[0] + (A[1] - centre[1]) * n[1] < 0) n = [-n[0], -n[1]]; // (away from the view's middle)
  const off = r.off || defaultOff(n);
  const on = !off[0] && !off[1];
  return { A, T: [A[0] + off[0], A[1] + off[1]], n, on, sits: n[1] < -0.9 };
}

/** Where a new symbol goes from its edge: on it (an edge on top), else out on a leader clear of the view. */
export function defaultOff(n) {
  if (n[1] < -0.9) return [0, 0];
  return [n[0] * 16 + (n[0] < -0.5 ? -textW('Ra 0.0') - 6 : Math.abs(n[0]) < 0.5 ? 8 : 0), n[1] * 12 + 6]; // (past the dimensions beside it)
}

/** The symbol as SVG (paper mm). col: its colour; grab: a transparent box to click / drag it (not printed). */
export function roughSvg(r, at, col, grab) {
  const { A, T, on } = at, [x, y] = T, txt = raText(r.ra), w = textW(txt), out = [];
  const ln = (x1, y1, x2, y2, sw = 0.25) => `<line x1="${fmt(x1)}" y1="${fmt(y1)}" x2="${fmt(x2)}" y2="${fmt(y2)}" stroke="${col}" stroke-width="${sw}"/>`;
  const tx = x + (H2 - 1) * TAN + 0.6, barEnd = tx + w + 0.6;
  out.push(`<polyline points="${fmt(x - H1 * TAN)},${fmt(y - H1)} ${fmt(x)},${fmt(y)} ${fmt(x + H2 * TAN)},${fmt(y - H2)} ${fmt(barEnd)},${fmt(y - H2)}" fill="none" stroke="${col}" stroke-width="0.25" stroke-linejoin="round"/>`);
  if (r.proc === 'remove') out.push(ln(x - H1 * TAN, y - H1, x + H1 * TAN, y - H1));
  if (r.proc === 'keep') out.push(`<circle cx="${fmt(x)}" cy="${fmt(y - 2.2)}" r="1.1" fill="none" stroke="${col}" stroke-width="0.25"/>`);
  out.push(`<text x="${fmt(tx)}" y="${fmt(y - H2 + 1 + FS * 0.72)}" font-size="${FS}" fill="${col}">${txt}</text>`);
  if (!on) { // on a reference line, a leader from the edge (its arrowhead on the edge)
    const s0 = [x - 3, y], s1 = [Math.max(x + 3, x + H1 * TAN + 1), y], E = Math.hypot(s0[0] - A[0], s0[1] - A[1]) <= Math.hypot(s1[0] - A[0], s1[1] - A[1]) ? s0 : s1;
    out.push(ln(s0[0], s0[1], s1[0], s1[1]), ln(A[0], A[1], E[0], E[1], 0.2));
    const L = Math.hypot(E[0] - A[0], E[1] - A[1]) || 1, u = [(E[0] - A[0]) / L, (E[1] - A[1]) / L], h = 2.2, W = 0.7;
    out.push(`<path d="M${fmt(A[0])},${fmt(A[1])} L${fmt(A[0] + u[0] * h - u[1] * W)},${fmt(A[1] + u[1] * h + u[0] * W)} L${fmt(A[0] + u[0] * h + u[1] * W)},${fmt(A[1] + u[1] * h - u[0] * W)} Z" fill="${col}"/>`);
  }
  if (grab) out.push(`<rect x="${fmt(x - H1 * TAN - 1)}" y="${fmt(y - H2 - 1)}" width="${fmt(barEnd - x + H1 * TAN + 2)}" height="${fmt(H2 + 2)}" fill="#fff" fill-opacity="0" class="sh-grab"/>`);
  return out.join('');
}

/** A point p (paper) on the edge: {k (0…1 along it), dist (from the line), out (on the outward side)}. */
export function onEdge(p, line, P, n) {
  const a = P(line.a), b = P(line.b), dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy || 1;
  const k = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)), q = [a[0] + k * dx, a[1] + k * dy];
  return { k, dist: Math.hypot(p[0] - q[0], p[1] - q[1]), out: (p[0] - q[0]) * n[0] + (p[1] - q[1]) * n[1] >= -0.3 };
}
