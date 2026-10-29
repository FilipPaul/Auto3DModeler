// One size of the part, every view it can be dimensioned in. The server lists, per axis of the part and place along it,
// the views that show that place as a point a dimension hangs on (sheet.py places: an edge across the axis, a circle's
// centre where it is seen round, the view's box; the axis in the view's plane, never foreshortened — so never the iso
// view). A missing size of the sheet's check is one item with those views (its candidates), the best first (ISO 129:
// dimension a feature where its shape shows best — seen round, a visible edge rather than a hidden one, few lines to
// cross, next to the feature's other dimensions). Hovering it (its row, its orange ? on the drawing) shows a ghost of the
// dimension in each of them, where it would go; a click on a row adds it in the best view, a click on a ghost in that
// view. A dimension already there can move to another view the same way.
import { t } from '../i18n.js';

const fmt = (v) => (+(+v).toFixed(2)).toString();
const tv = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const r2 = (v) => Math.round(v * 100) / 100;
const ORDER = ['Front', 'Top', 'Right', 'Section'];
const HOW = { c: 3, b: 2.5, e: 2, h: 0 }; // (as sheet.py PLACE_HOW: round, the view's box, a visible edge, a hidden one)
const ACCENT = '#e8590c';
const NAMES = { x: 'Length', y: 'Width', z: 'Height' };

/** A view's right (k 0) / up (k 1) as an axis of the part -> {ax: 'x' | 'y' | 'z', s: ±1} or null (slanted). */
function axisOf(g, k) {
  const v = (k ? g?.up : g?.right) || [], i = [0, 1, 2].find((j) => Math.abs(Math.abs(v[j] || 0) - 1) < 1e-9);
  return i === undefined ? null : { ax: 'xyz'[i], s: Math.sign(v[i]) };
}

/** The server's places as a lookup (made once a geometry): `${ax}:${place}` -> [{view, key, dir, how}]. */
function lookup(G) {
  if (!G?.places) return null;
  if (G.placeMap) return G.placeMap;
  const m = new Map();
  for (const ax of ['x', 'y', 'z']) for (const [at, vs] of G.places[ax] || []) m.set(`${ax}:${r2(at)}`, vs.map(([view, key, dir, how]) => ({ view, key, dir, how })));
  Object.defineProperty(G, 'placeMap', { value: m, enumerable: false }); // (not saved with the sheet)
  return m;
}

/** The views drawn that show place `at` along axis `ax` (part mm) -> [{view, key, dir, how}]; skip(key): left out. */
export function placesAt(ed, ax, at, skip = () => false) {
  const m = lookup(ed.geo), drawn = ed.drawn();
  return (m?.get(`${ax}:${r2(at)}`) || []).filter((p) => drawn.includes(p.view) && !skip(p.key));
}

/** Where a candidate shows on its view (part mm): an edge's middle, else its point. */
function atOf(ed, c) {
  const g = ed.geo.views[c.view], ln = g.lines.find((l) => `${l.key}#0` === c.key);
  return ln ? [(ln.a[0] + ln.b[0]) / 2, (ln.a[1] + ln.b[1]) / 2] : g.points[c.key] || g.circles.find((x) => x.key === c.key)?.pm || g.box.slice(2);
}

/** The steps a point key is of ("E2:end+E2:side:l1#0" -> E2). */
const stepsOf = (key) => new Set(String(key || '').replace(/#.*$/, '').split('+').map((n) => n.split(':')[0]).filter((n) => n && n !== 'box' && n !== 'base'));

/** The side of view `v` a new dimension in direction `dir` goes: the outer one (toward the frame, not into the gap to
 *  the next view, where that view's own dimensions are) when it has room (15 mm), else the one with more room to the next
 *  view, the frame or the title block (a tie: below / left, as before). */
export function sideFor(ed, v, dir) {
  if (!ed.lay || !ed.centre(v)) return dir === 'h' ? 'b' : 'l';
  const pb = ed.paperBox(v), [pw, ph] = ed.lay.size, [ml, mt, mr, mb] = ed.frameOf().m, views = ed.drawn().filter((w) => w !== v).map((w) => ed.paperBox(w));
  const others = [...views, ...(ed.isoBox && !ed.d.off.Iso ? [ed.isoBox] : []), ...ed.keepRects()];
  const over = (a0, a1, b0, b1) => a0 < b1 && b0 < a1;
  const k = dir === 'h' ? 1 : 0, along = (o) => over(o[1 - k], o[3 - k], pb[1 - k], pb[3 - k]); // (beside the view across the dimension's way)
  const lo = { ok: (o) => along(o) && o[k + 2] <= pb[k] + 0.5, edge: k ? mt : ml }, hi = { ok: (o) => along(o) && o[k] >= pb[k + 2] - 0.5, edge: k ? ph - mb : pw - mr };
  const roomLo = pb[k] - Math.max(lo.edge, ...others.filter(lo.ok).map((o) => o[k + 2])), roomHi = Math.min(hi.edge, ...others.filter(hi.ok).map((o) => o[k])) - pb[k + 2];
  const viewLo = views.some(lo.ok), viewHi = views.some(hi.ok);
  const [first, low] = dir === 'h' ? ['b', false] : ['l', true]; // (as before: below, left)
  if (viewLo !== viewHi) { const outerLow = !viewLo; if ((outerLow ? roomLo : roomHi) >= 15) return outerLow ? (k ? 't' : 'l') : (k ? 'b' : 'r'); }
  const better = low ? roomHi > roomLo + 6 : roomLo > roomHi + 6;
  return better ? (first === 'b' ? 't' : 'r') : first;
}

/** How far out a new dimension on that side of view `v` goes: past the ones there (8 mm, then 7 mm a row). */
function offFor(ed, v, dir, side, but = null) {
  const offs = ed.allDims().filter((d) => d.view === v && d.kind === 'linear' && d.dir === dir && (d.side || (dir === 'h' ? 'b' : 'r')) === side && d.id !== but).map((d) => d.off ?? 8);
  return offs.length ? Math.max(...offs) + 7 : 8;
}

/** Lines of the view a dimension's extension line from the candidate's point to its side crosses. */
function crossings(ed, c, side) {
  const g = ed.geo.views[c.view];
  if (/^box#/.test(c.key) || g.lines.length > 3000) return 0;
  const p = atOf(ed, c), k = c.dir === 'h' ? 0 : 1, b = g.box, to = side === 't' ? b[3] : side === 'b' ? b[1] : side === 'l' ? b[0] : b[2];
  const lo = Math.min(p[1 - k], to) + 1e-3, hi = Math.max(p[1 - k], to) - 1e-3; // (along the other axis of the view)
  let n = 0;
  for (const ln of g.lines) {
    if (Math.abs(ln.a[1 - k] - ln.b[1 - k]) > 1e-3) continue; // (only lines across the extension line)
    const at = ln.a[1 - k], s0 = Math.min(ln.a[k], ln.b[k]), s1 = Math.max(ln.a[k], ln.b[k]);
    if (at > lo && at < hi && p[k] > s0 + 1e-3 && p[k] < s1 - 1e-3) n++;
  }
  return n;
}

/** How well a view takes the size (higher: better) — ISO 129: where the feature's shape shows (seen round, its edge
 *  seen, not hidden), its extension line crossing few lines, next to the feature's other dimensions; the views' order
 *  breaks a tie (front, top, right). */
function score(ed, c) {
  const side = sideFor(ed, c.view, c.dir), mine = stepsOf(c.key);
  const near = mine.size ? ed.allDims().filter((d) => d.view === c.view && [d.a, d.b].some((k) => [...stepsOf(k)].some((s) => mine.has(s)))).length : 0;
  return (HOW[c.how] ?? 2) - 0.4 * Math.min(5, crossings(ed, c, side)) + 0.5 * Math.min(2, near) - 0.01 * ORDER.indexOf(c.view);
}

/** The check's missing sizes (sheet.js check) each with its candidates, the best first; the item's view, key and dir
 *  are the best one's (as before: one view each, the first found). A place along an axis: the views the server lists;
 *  a Ø / R: the views where a circle of that size is seen; a hole's depth / head: its view. */
export function withViews(ed, missing, skip = () => false) {
  const G = ed.geo, drawn = ed.drawn();
  for (const m of missing) {
    const own = { view: m.view, key: m.key, dir: m.dir, how: 'e' };
    let cands = [];
    if (m.kind === 'dia' || m.kind === 'rad') {
      const c0 = G.views[m.view].circles.find((c) => c.key === m.key);
      for (const v of drawn) {
        const c = c0 && G.views[v]?.circles.find((x) => !!x.full === !!c0.full && Math.abs(x.r - c0.r) < 0.006 && !skip(x.key));
        if (c) cands.push({ view: v, key: v === m.view ? m.key : c.key, how: 'c' });
      }
    } else if (m.ax && m.v !== undefined) {
      cands = placesAt(ed, m.ax, m.v, skip).map((c) => (c.view === m.view && /^box#/.test(m.key) ? { ...c, key: m.key } : c));
      if (!lookup(G) && /^box#/.test(m.key)) { // (no places — an assembly's sheet: its box in each view showing that axis)
        for (const v of drawn) {
          const k = [0, 1].find((j) => axisOf(G.views[v], j)?.ax === m.ax);
          if (k !== undefined) cands.push({ view: v, key: `box#${'xy'[k]}${m.key.slice(-1)}`, dir: 'hv'[k], how: 'b' });
        }
      }
    }
    if (!cands.some((c) => c.view === m.view)) cands.push(own);
    for (const c of cands) c.score = score(ed, c);
    cands.sort((a, b) => b.score - a.score);
    m.cands = cands;
    const best = cands[0];
    if (best.view !== m.view || best.key !== m.key) Object.assign(m, { view: best.view, key: best.key, dir: best.dir ?? m.dir, at: atOf(ed, best) });
  }
  return missing;
}

/** The dimension a missing size becomes in candidate `c` (its view; none: the best): a linear one from the part's
 *  lowest place there (or the base part's edge) to it, on the side with room, past the dimensions there; a Ø / R on
 *  its circle; a hole step's size: its callout. */
export function candDim(ed, m, c = m.cands?.[0] || m) {
  if (m.kind === 'dia' || m.kind === 'rad' || m.kind === 'hole') {
    const co = m.hole && ed.calloutFor(c.view, c.key);
    return co || { view: c.view, kind: m.kind === 'rad' ? 'rad' : 'dia', a: c.key, count: 1, ang: m.kind === 'dia' ? 45 : 0, len: 6 };
  }
  const dir = c.dir || m.dir, side = sideFor(ed, c.view, dir);
  return { view: c.view, kind: 'linear', a: (c.view === m.view && m.from) || (dir === 'h' ? 'box#x0' : 'box#y0'), b: c.key, dir, side, off: offFor(ed, c.view, dir, side) };
}

/** ＋ a missing size in view `view` (none: its best) — one undo step; the ghosts go. */
export function addMissingIn(ed, m, view = null) {
  const c = (view && m.cands?.find((x) => x.view === view)) || m.cands?.[0] || m;
  setGhosts(ed, null);
  ed.addUser(candDim(ed, m, c));
}

/** A missing size as the suggestions say it: "↕ Height 30 (2 views)". */
export function missLabel(ed, m) {
  const n = m.cands?.length || 1, many = n > 1 ? ` (${tv('{n} views', { n })})` : '';
  if (m.kind === 'dia' || m.kind === 'rad' || m.kind === 'hole') return { icon: m.kind === 'hole' ? '⌖' : m.kind === 'dia' ? '⌀' : '◜', label: `${m.what}${many}` };
  const name = /^box#/.test(m.key) && m.ax ? t(NAMES[m.ax]) : `${m.what.charAt(0).toUpperCase()}${m.what.slice(1)} (${m.ax})`;
  return { icon: m.dir === 'h' ? '↔' : '↕', label: `${name} ${fmt(m.size ?? 0)}${many}` };
}

// ---------------------------------------------------------------- ghosts: a size shown in every view it can go in
/** Show the ghosts of `m` (a missing size: its candidates; or {ghosts: [{dim, run}]}) — or none (null). */
export function setGhosts(ed, m) {
  clearTimeout(ed.ghostT);
  const list = !m ? null : m.ghosts || (m.cands || []).map((c) => ({ dim: candDim(ed, m, c), run: () => addMissingIn(ed, m, c.view) }));
  ed.ghost = list?.length ? { of: m, list } : null;
  const svg = ed.svgEl;
  if (!svg) return;
  svg.querySelector('.sh-ghosts')?.remove();
  if (ed.ghost) svg.insertAdjacentHTML('beforeend', ghostSvg(ed));
}

/** The ghosts as SVG (sheet.js svg draws them too, when the sheet is drawn again under them): each a dimension as it
 *  would be drawn, dashed, faint, in the accent colour; a click on one adds it there. */
export function ghostSvg(ed) {
  if (!ed.ghost || !ed.geo) return '';
  const out = ed.ghost.list.map((g, i) => {
    if (!ed.drawn().includes(g.dim.view)) return '';
    const s = ed.dimSvg({ ...g.dim, id: 'ghost' }, false);
    if (!s) return '';
    return s.replace(/^<g data-dim="ghost" class="sh-dim">/, `<g class="sh-ghost" data-ghost="${i}" data-gview="${g.dim.view}" opacity="0.75" style="cursor:pointer"><title>${tv('Click: add it in this view ({v})', { v: ed.viewName(g.dim.view) })}</title>`)
      .replace(/#1b3a8a/g, ACCENT).replace(/<(line|polyline|path) /g, '<$1 stroke-dasharray="1.2 0.8" ');
  });
  return `<g class="sh-ghosts">${out.join('')}</g>`;
}

/** Hovering a row (on): its ghosts; off: they go after a moment (time to reach one on the drawing and click it). */
export function hoverGhosts(ed, m, on) {
  if (on) { setGhosts(ed, m); return; }
  clearTimeout(ed.ghostT);
  ed.ghostT = setTimeout(() => setGhosts(ed, null), 1500);
}

/** The drawing's side of it: an orange ? hovered shows its size's ghosts; a ghost keeps them while the mouse is on it;
 *  a click on a ghost adds that one (before the sheet's own click: not a pan, not a view chosen). */
export function bindGhosts(ed) {
  const st = ed.stage;
  st.addEventListener('pointerover', (e) => {
    if (ed.tool !== 'select') return;
    const mark = e.target.closest?.('[data-missmark]'), gh = e.target.closest?.('[data-ghost]');
    if (gh) clearTimeout(ed.ghostT);
    else if (mark) { const m = ed.checked?.missing[+mark.dataset.missmark]; if (m && ed.ghost?.of !== m) setGhosts(ed, m); else clearTimeout(ed.ghostT); }
  });
  st.addEventListener('pointerout', (e) => {
    if (ed.ghost && e.target.closest?.('[data-ghost], [data-missmark]')) hoverGhosts(ed, null, false);
  });
  st.addEventListener('pointerdown', (e) => {
    const gh = e.button === 0 && ed.tool === 'select' && e.target.closest?.('[data-ghost]');
    if (!gh || !ed.ghost) return;
    e.stopPropagation();
    e.preventDefault();
    ed.ghost.list[+gh.dataset.ghost]?.run();
  }, true);
}

// ---------------------------------------------------------------- the suggestions' rows
/** The sheet's next steps: each missing size once ("↕ Height 30 (2 views)"), the first few up with the other steps,
 *  the rest under ⋯ Show all. */
export function missRows(ed) {
  const ms = ed.checked?.missing || [];
  return ms.slice(0, 30).map((m, i) => {
    const { icon, label } = missLabel(ed, m);
    return { icon, label, rank: i < 4 ? 0.2 + i / 100 : 10 + i / 100, hover: (on) => hoverGhosts(ed, m, on),
      title: tv('Hover: where it can go ({views}); click: added in {v}', { views: (m.cands || [m]).map((c) => ed.viewName(c.view)).join(', '), v: ed.viewName(m.view) }),
      run: () => { addMissingIn(ed, m); } };
  });
}

/** The views a linear dimension could be in instead -> [{view, a, b, dir}] (both its ends seen there, the same way). */
export function otherViews(ed, d) {
  const G = ed.geo, g = G?.views[d.view];
  if (!g || d.kind !== 'linear' || d.ord) return [];
  const k = d.dir === 'h' ? 0 : 1, A = axisOf(g, k), pa = g.points[d.a], pb = g.points[d.b];
  if (!A || !pa || !pb) return [];
  const ends = [pa, pb].map((p) => placesAt(ed, A.ax, A.s * p[k]));
  const out = [];
  for (const v of ed.drawn()) {
    if (v === d.view) continue;
    const a = ends[0].find((c) => c.view === v), b = ends[1].find((c) => c.view === v);
    if (a && b && a.dir === b.dir && a.key !== b.key) out.push({ view: v, a: a.key, b: b.key, dir: a.dir, how: Math.min(HOW[a.how] ?? 2, HOW[b.how] ?? 2) });
  }
  return out.sort((x, y) => y.how - x.how || ORDER.indexOf(x.view) - ORDER.indexOf(y.view));
}

/** Dimension `d` moved to candidate `c`'s view — its tolerance, brackets and text before kept; one undo step. */
export function moveDim(ed, d, c) {
  setGhosts(ed, null);
  const side = sideFor(ed, c.view, c.dir), id = `u${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const keep = Object.fromEntries(['tol', 'ref', 'pre'].filter((k) => d[k]).map((k) => [k, d[k]]));
  if (ed.d.user.some((x) => x.id === d.id)) ed.d.user = ed.d.user.filter((x) => x.id !== d.id);
  else ed.d.hidden = [...new Set([...ed.d.hidden, d.id])];
  delete ed.d.dims[d.id];
  ed.d.user = [...ed.d.user, { id, view: c.view, kind: 'linear', a: c.a, b: c.b, dir: c.dir, side, off: offFor(ed, c.view, c.dir, side), ...keep }];
  ed.clearSel();
  ed.sel = id;
  ed.commit();
}

/** A chosen dimension's rows "⇄ Move to another view: Right", each showing where it would go (the ghosts). */
export function moveRows(ed, d) {
  const cs = otherViews(ed, d);
  if (!cs.length) return [];
  const ghosts = cs.map((c) => ({ dim: { view: c.view, kind: 'linear', a: c.a, b: c.b, dir: c.dir, side: sideFor(ed, c.view, c.dir), off: offFor(ed, c.view, c.dir, sideFor(ed, c.view, c.dir)), ...(d.pre ? { pre: d.pre } : {}) }, run: () => moveDim(ed, d, c) }));
  const of = { ghosts };
  return cs.map((c, i) => ({ icon: '⇄', label: tv('Move to another view: {v}', { v: ed.viewName(c.view) }), title: t('The same size in that view — this one goes (hover: where it would be)'), rank: 1.5 + i / 100,
    hover: (on) => hoverGhosts(ed, of, on), run: () => ghosts[i].run() }));
}
