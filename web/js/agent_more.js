// More of the app for the AI (tool calls from the app's MCP server, applied like a user edit): the 2D drawing workspace
// (layers, shapes found by filters, sizes, use as a sketch / quick part), joints changed or removed, measuring between
// faces, the view (section, explode, sizes) for its screenshots, parts renamed or deleted, and the data the server
// writes as files (a coloured 3MF, the BOM as CSV, a drawing as DXF).
import * as THREE from 'three';
import { paintedFaces } from './modeler/paint.js';
import { sectionMiddle } from './modeler/sectionbar.js';
import { parseScale, DEFAULT_TPL } from './sheet/sheet.js';
import { tolText } from './sheet/sheetsuggest.js';
import { propagates } from './sheet/tbedit.js';
import { animState } from './assembly/anim.js';
import { suggestTables, runSuggestion } from './suggest.js';
import { t } from './i18n.js';

const b64 = (s, T) => { if (typeof s !== 'string') return s; const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); };
const r3 = (v) => +(+v).toFixed(3);
const hex = (c) => (typeof c === 'number' ? `#${c.toString(16).padStart(6, '0')}` : c);

/** A body's triangles grouped by the colour each face shows (its painted colour, its file's colour, else `base`),
 *  moved by `matrix` -> [{name, color, positions}]. */
export function colouredGroups(body, { base = '#d9dee6', paint = [], matrix = null, name = 'part', fileColours = true } = {}) {
  const pos = b64(body.positions, Float32Array), ids = b64(body.face_ids, Uint32Array), M = matrix ? new THREE.Matrix4().fromArray(matrix) : null;
  const painted = paintedFaces(body.faces, paint || []), byFace = new Map();
  for (const f of body.faces) byFace.set(f.id, painted.get(f.id)?.color || (fileColours && f.color) || base);
  const groups = new Map(), v = new THREE.Vector3();
  for (let t = 0; t < ids.length; t++) {
    const c = hex(byFace.get(ids[t]) || base);
    if (!groups.has(c)) groups.set(c, []);
    const g = groups.get(c);
    for (let k = 0; k < 3; k++) {
      v.set(pos[t * 9 + k * 3], pos[t * 9 + k * 3 + 1], pos[t * 9 + k * 3 + 2]);
      if (M) v.applyMatrix4(M);
      g.push(r3(v.x), r3(v.y), r3(v.z));
    }
  }
  const many = groups.size > 1;
  return [...groups].map(([color, positions]) => ({ name: many ? `${name} (${color})` : name, color, positions }));
}

/** The controls the user sees now (buttons, sliders, boxes, choices; not the AI chat): [{n, kind, label, title,
 *  state, disabled, where, el}] — where: bar (the top bar), tools (the workspace's toolbar), suggest (the suggestions
 *  table: its rows, ⋯ Show all, its head), panel (its side panels). */
export function guiControls(where = 'all') {
  const out = [], seen = new Set();
  const shown = (el) => { if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const area = (el) => (el.closest('.topbar, header') ? 'bar' : el.closest('.view-suggest, .sg-menu') ? 'suggest' : el.closest('.m-cmdbar, .cmdbar, [class*=toolbar]') ? 'tools' : 'panel');
  for (const el of document.querySelectorAll('button, input, select, [data-jname], .chip, .as-list .mt-item, #modelLeft .mt-tree .mt-item')) {
    if (seen.has(el) || el.closest('#aiDrawer, #tab-ai, .ai-drawer') || !shown(el)) continue;
    if (el.tagName === 'INPUT' && el.type === 'hidden') continue;
    seen.add(el);
    const lab = el.closest('label'), row = el.closest('[data-jrow], .as-dof, .as-rot, .field');
    const isPart = el.matches('.as-list .mt-item'), isStep = el.matches('#modelLeft .mt-item'); // (an assembly's part, a model's step)
    let label = (isPart || isStep ? `${el.querySelector('.mt-name')?.textContent || ''} ${el.querySelector('.mt-what')?.textContent || ''}${isStep ? ` [${el.dataset.id}]` : ''}`
      : el.tagName === 'INPUT' || el.tagName === 'SELECT' ? (lab?.textContent || el.placeholder || el.dataset.k || '') : el.textContent || el.title || '').replace(/\s+/g, ' ').trim();
    if ((el.tagName === 'INPUT' || el.tagName === 'SELECT') && row && row !== lab) { // (its row's name first: "↻ X", a joint's, a motion's)
      const name = (row.querySelector('label, .as-jt')?.textContent || '').replace(/\s+/g, ' ').trim();
      label = label && label !== name ? `${name} › ${label}`.trim() : name;
    }
    const dimRow = el.tagName === 'BUTTON' && el.closest('.sk-dim, .sk-label'); // (a sketch dimension's 🔒 / 🔓 / ✕: which one)
    if (dimRow) label = `${(dimRow.querySelector('.sk-val, :scope > span')?.textContent || '').replace(/\s+/g, ' ').trim()} › ${label}`;
    if (!label) label = el.getAttribute('aria-label') || el.title || el.className || el.tagName.toLowerCase();
    const kind = isStep ? 'step' : isPart ? 'part' : el.tagName === 'SELECT' ? 'choice' : el.tagName === 'INPUT' ? (el.type === 'range' ? 'slider' : el.type === 'checkbox' ? 'checkbox' : 'box') : el.dataset.jname ? 'name' : 'button';
    const a = area(el);
    out.push({ n: out.length + 1, kind, label: label.slice(0, 90), title: (el.title || '').slice(0, 120) || undefined,
      state: kind === 'checkbox' ? (el.checked ? 'on' : 'off') : ['button', 'name', 'part', 'step'].includes(kind) ? (el.classList.contains('on') ? 'on' : el.classList.contains('off') ? 'off' : undefined)
        : kind === 'choice' ? `${el.selectedOptions[0]?.textContent?.trim() || ''}${el.value && el.value !== el.selectedOptions[0]?.textContent?.trim() ? ` (${el.value})` : ''}` : String(el.value),
      ...(kind === 'slider' ? { min: +el.min, max: +el.max } : {}), disabled: !!el.disabled || undefined, where: a, el });
  }
  // in a sketch: each size label on the view, its name and value (locked 🔒, free 🔓, set by the others ＝)
  for (const el of document.querySelectorAll('#modelViewport .sk-label')) {
    if (seen.has(el) || !el.getBoundingClientRect().width) continue;
    seen.add(el);
    const val = (el.querySelector('.sk-val')?.textContent || '').replace(/\s+/g, ' ').trim();
    const st = el.classList.contains('locked') ? 'locked' : el.classList.contains('driven') ? 'set by the others' : el.classList.contains('dist') ? 'reference' : 'free';
    out.push({ n: out.length + 1, kind: 'dim', label: `${el.dataset.dim ? `${el.dataset.dim}: ` : ''}${val}`.slice(0, 90), state: st, where: 'view', el });
  }
  // on a drawing sheet: its dimensions, views and title-block cells (drawn, not controls — clicked where they are)
  for (const el of document.querySelectorAll('#shViewport [data-dim], #shViewport [data-view], #shViewport [data-tcell]')) {
    if (seen.has(el) || !el.getBoundingClientRect().width) continue;
    seen.add(el);
    const kind = el.dataset.dim ? 'dim' : el.dataset.tcell ? 'cell' : 'view';
    const label = kind === 'dim' ? `${el.dataset.dim}: ${el.textContent.replace(/\s+/g, ' ').trim()}` : kind === 'cell' ? `title ${el.dataset.tcell}` : `view ${el.dataset.view}`;
    out.push({ n: out.length + 1, kind, label: label.slice(0, 90), state: el.classList.contains('on') ? 'on' : undefined, where: 'view', el });
  }
  return where === 'all' ? out : out.filter((c) => c.where === where); // (n: one numbering for all)
}

// ---------------------------------------------------------------------------------------------- the suggestions table
// The product works through it (select something -> the table offers what fits it): the AI reads it as the user sees
// it — its title, what it is about, its rows in their order (with gui_action's numbers) and those under ⋯ Show all.

/** A label as compared: no accents, no icons, lower case ("◎ Díra zde" -> "dira zde"). */
const plain = (s) => String(s ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

/** The suggestions table on screen (a menu opened over it first) for gui_state / gui_action, or null: {title, about
 *  (what is selected), hint, where, rows: [{n, icon, label, section, rank_pos}] (as shown, top to bottom), more (rows
 *  under ⋯ Show all), all (their labels, the most relevant first), show_all (its n)}. */
export function suggestInfo(list = guiControls('all')) {
  const tables = suggestTables(), s = tables.find((x) => x.menu) || tables[0];
  if (!s) return null;
  const nOf = (el) => (el ? list.find((c) => c.el === el)?.n : undefined);
  const shown = s.rows.filter((r) => r.shown).sort((a, b) => a.i - b.i), hidden = s.rows.filter((r) => !r.shown);
  const label = (r) => `${r.icon} ${r.label}`.trim();
  return { title: s.title, about: s.refs || s.title, ...(s.hint ? { hint: s.hint } : {}),
    where: s.menu ? 'a menu' : s.docked ? 'docked in the left panel' : 'floating over the view (bottom left)',
    rows: shown.map((r) => ({ n: nOf(s.box.querySelector(`[data-sg="${r.i}"]`)), icon: r.icon, label: r.label, ...(r.section ? { section: r.section } : {}), rank_pos: r.rank_pos })),
    more: hidden.length, ...(hidden.length ? { all: hidden.map(label), show_all: nOf(s.box.querySelector('[data-sg-all]')) } : {}),
    run: 'gui_action {suggest: "<label or part of it>"} runs a row (one under ⋯ Show all too)' };
}

/** The table's row a label means (Czech or English, part of it, no accents needed): the closest match, the most
 *  relevant of equals -> {box, row} or null. */
function findSuggestion(tables, want) {
  const w = String(want).trim(), keys = [...new Set([w, w[0]?.toUpperCase() + w.slice(1)].flatMap((x) => [plain(x), plain(t(x))]))].filter(Boolean); // (English: through its Czech text)
  let best = null;
  for (const s of tables) {
    for (const r of s.rows) {
      const l = plain(r.label), li = plain(`${r.icon} ${r.label}`);
      const score = Math.max(...keys.map((k) => (l === k || li === k ? 4 : l.startsWith(k) ? 3 : ` ${l} `.includes(` ${k} `) ? 2 : l.includes(k) ? 1 : 0)));
      if (score && (!best || score > best.score || (score === best.score && r.rank_pos < best.row.rank_pos))) best = { box: s.box, row: r, score };
    }
  }
  return best;
}

/** A point of the view on screen where a named thing shows (as the user would aim at it): a face of the 3D model
 *  ("F2:end", or a step's id: any of its faces), an assembly's part ("I2") or a face of it ("I2 F2:end") — the middle
 *  of where it is seen, not under a panel or the table. -> [x, y] on the page, or null when it is not in sight. */
function pointOf(state, modeler, assembly, what) {
  const view = viewEl(), vr = view?.getBoundingClientRect(), want = String(what).trim();
  if (!vr) throw new Error('No view on screen.');
  const named = (f, n) => !!f && [f.name, ...(f.names || [])].some((q) => q === n || q?.startsWith(`${n}:`));
  let test;
  if (state.workspace === 'model') test = (x, y) => named(modeler.view.pick(x, y)?.face, want);
  else if (state.workspace === 'assembly') {
    const [inst, face] = want.split(/\s+/);
    test = (x, y) => { const h = assembly.view.pickInst(x, y); return h?.inst === inst && (!face || named(h.face, face)); };
  } else throw new Error('pick is for the 3D model or an assembly on screen — on a sheet use control (its dimensions, views, cells).');
  const hits = [], N = 48;
  for (let j = 1; j < N; j++) {
    for (let i = 1; i < N; i++) {
      const x = vr.left + (i / N) * vr.width, y = vr.top + (j / N) * vr.height;
      if (document.elementFromPoint(x, y)?.tagName !== 'CANVAS') continue; // (a panel, the table, a label over it)
      if (test(x, y)) hits.push([x, y]);
    }
  }
  if (!hits.length) return null;
  const mx = hits.reduce((a, p) => a + p[0], 0) / hits.length, my = hits.reduce((a, p) => a + p[1], 0) / hits.length;
  return hits.reduce((a, p) => (Math.hypot(p[0] - mx, p[1] - my) < Math.hypot(a[0] - mx, a[1] - my) ? p : a));
}

/** The window as the user sees it, as a picture (the AI chat left out): the 3D view / the sheet as drawn on screen
 *  and the page over it — the suggestions table, panels, labels, bars — drawn box by box from the page (backgrounds,
 *  borders, text, the fields' values; no HTML-to-canvas library is in the app), at most 1400 px wide -> get_screenshot's
 *  answer {text (where the table is on it), image}. */
export async function screenshotUI() {
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const W = innerWidth, H = innerHeight, k = Math.min(1, 1400 / W), skip = '#aiDrawer, #tab-ai, .ai-drawer, script, style, link, template';
  const c = document.createElement('canvas');
  c.width = Math.round(W * k);
  c.height = Math.round(H * k);
  const ctx = c.getContext('2d');
  ctx.scale(k, k);
  ctx.fillStyle = getComputedStyle(document.body).backgroundColor || '#0d1117';
  ctx.fillRect(0, 0, W, H);
  // a drawing sheet (a big SVG): as a picture, loaded first (the rest is drawn at once, in the page's order)
  const sheets = new Map();
  for (const svg of document.querySelectorAll('section.viewport svg')) {
    const r = svg.getBoundingClientRect();
    if (r.width < 150 || r.height < 150 || svg.closest(skip)) continue;
    const img = new Image(), url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' }));
    await new Promise((ok) => { img.onload = ok; img.onerror = ok; img.src = url; });
    if (img.naturalWidth || img.width) sheets.set(svg, img);
  }
  const seen = (col) => !!col && col !== 'transparent' && !/^rgba\(.*,\s*0\)$|\/\s*0\)$/.test(col); // (rgb(), color(srgb …) of color-mix: not fully transparent)
  const cut = (a, r) => { const x0 = Math.max(a[0], r.left), y0 = Math.max(a[1], r.top), x1 = Math.min(a[2], r.right), y1 = Math.min(a[3], r.bottom); return [x0, y0, Math.max(x0, x1), Math.max(y0, y1)]; };
  const text = (s, cs, r, clip) => {
    if (r.right < clip[0] || r.left > clip[2] || r.bottom < clip[1] || r.top > clip[3]) return;
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    ctx.fillStyle = cs.color;
    ctx.textBaseline = 'middle';
    ctx.fillText(s, r.left, r.top + r.height / 2);
  };
  const later = []; // (what floats over the rest — z-index above 0: the table, panels over the view — drawn after it)
  const walk = (el, clip, over = false) => {
    if (el.matches(skip)) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || +cs.opacity === 0) return;
    if (cs.position === 'fixed') clip = [0, 0, W, H];
    if (!over && cs.position !== 'static' && +cs.zIndex > 0) { later.push([+cs.zIndex, el, clip]); return; }
    const r = el.getBoundingClientRect(), vis = cs.visibility !== 'hidden', tag = el.tagName;
    if (vis && r.width && r.height) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clip[0], clip[1], clip[2] - clip[0], clip[3] - clip[1]);
      ctx.clip();
      if (seen(cs.backgroundColor)) { ctx.fillStyle = cs.backgroundColor; ctx.fillRect(r.left, r.top, r.width, r.height); }
      if (parseFloat(cs.borderTopWidth) > 0 && seen(cs.borderTopColor) && tag !== 'CANVAS') { ctx.strokeStyle = cs.borderTopColor; ctx.lineWidth = 1; ctx.strokeRect(r.left + 0.5, r.top + 0.5, r.width - 1, r.height - 1); }
      try {
        if (tag === 'CANVAS' || (tag === 'IMG' && el.complete)) ctx.drawImage(el, r.left, r.top, r.width, r.height);
        else if (sheets.has(el)) ctx.drawImage(sheets.get(el), r.left, r.top, r.width, r.height);
      } catch { /* (a picture from elsewhere: left out) */ }
      const val = tag === 'SELECT' ? el.selectedOptions[0]?.textContent : tag === 'TEXTAREA' || (tag === 'INPUT' && /^(text|number|search|)$/.test(el.type)) ? el.value || el.placeholder : null;
      if (val) text(String(val).trim(), cs, { left: r.left + 4, right: r.right, top: r.top, bottom: r.bottom, height: r.height }, clip);
      if (tag === 'INPUT' && el.type === 'checkbox' && el.checked) text('✓', cs, r, clip);
      ctx.restore();
    }
    if (['CANVAS', 'IMG', 'INPUT', 'SELECT', 'TEXTAREA'].includes(tag) || sheets.has(el) || el instanceof SVGElement) return;
    const inner = cs.overflow !== 'visible' && r.width ? cut(clip, r) : clip;
    for (const n of el.childNodes) {
      if (n.nodeType === 1) walk(n, inner, over);
      else if (n.nodeType === 3 && vis && n.textContent.trim()) {
        const range = document.createRange();
        range.selectNodeContents(n);
        const rects = [...range.getClientRects()].filter((q) => q.width);
        if (!rects.length) continue;
        ctx.save();
        ctx.beginPath();
        ctx.rect(inner[0], inner[1], inner[2] - inner[0], inner[3] - inner[1]);
        ctx.clip();
        if (rects.length === 1) text(n.textContent.replace(/\s+/g, ' ').trim(), cs, rects[0], inner);
        else { // (wrapped over lines: its words flowed into them)
          ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
          const words = n.textContent.split(/\s+/).filter(Boolean);
          for (const q of rects) {
            let line = '';
            while (words.length && ctx.measureText(`${line} ${words[0]}`.trim()).width <= q.width * 1.05 + 2) line = `${line} ${words.shift()}`.trim();
            if (!line && words.length) line = words.shift();
            text(line, cs, q, inner);
          }
        }
        ctx.restore();
      }
    }
  };
  walk(document.body, [0, 0, W, H]);
  for (const [, el, clip] of later.sort((a, b) => a[0] - b[0])) walk(el, clip, true);
  const sg = suggestTables()[0], box = sg && !sg.box.classList.contains('lw-off') ? sg.box.getBoundingClientRect() : null;
  const at = box ? { suggestions_box: [box.left, box.top, box.right, box.bottom].map((v) => Math.round(v * k)) } : {};
  return { text: `The window as the user sees it (the AI chat left out), ${c.width} × ${c.height} px${box ? `; the suggestions table “${sg.title}” at ${at.suggestions_box.join(', ')} (left, top, right, bottom px) — gui_state lists its rows` : ''}. ${JSON.stringify(at)}`,
    image: c.toDataURL('image/png').split(',')[1] };
}

/** The workspace's view on screen (the 3D view, the drawing, the sheet). */
/** Two faces of the 3D model on screen ({face} or a face name each) -> as an assembly's measure: their centres apart,
 *  the angle between them, the gap between two parallel flat faces (a wall's thickness), two round faces' axes apart
 *  and their Ø. */
function measureModel(modeler, A, B) {
  const b = modeler.result?.body;
  if (!b) throw new Error('The model has no solid yet.');
  const face = (x) => {
    const name = typeof x === 'string' ? x : x?.face;
    const f = name && b.faces.find((q) => q.name === name || (q.names || []).includes(name));
    if (!f) throw new Error(`No face named “${name}” — find_refs gives the face names.`);
    return f;
  };
  const fa = face(A), fb = face(B), V = (p) => new THREE.Vector3(...p);
  const out = { centres_apart: r3(V(fa.centroid).distanceTo(V(fb.centroid))) };
  if (fa.normal && fb.normal) {
    const na = V(fa.normal), ang = (na.angleTo(V(fb.normal)) * 180) / Math.PI;
    out.angle_between_normals = r3(ang);
    if (ang < 0.5 || ang > 179.5) out.gap_between_faces = r3(Math.abs(V(fb.centroid).sub(V(fa.centroid)).dot(na.normalize())));
  }
  if (fa.axis && fb.axis) {
    const d = V(fa.axis.d).normalize(), off = V(fb.axis.o).sub(V(fa.axis.o));
    if (Math.abs(Math.abs(d.dot(V(fb.axis.d).normalize())) - 1) < 1e-4) out.axes_apart = r3(off.sub(d.clone().multiplyScalar(off.dot(d))).length());
  }
  const dia = [fa, fb].filter((f) => f.radius).map((f) => r3(2 * f.radius));
  if (dia.length) out.diameters = dia;
  return out;
}

function viewEl() { return [...document.querySelectorAll('section.viewport')].find((v) => v.offsetParent && v.getBoundingClientRect().width > 0); }

/** What is at a point of the screen, in words (for the AI). */
function underAt(x, y) {
  const el = document.elementFromPoint(x, y);
  if (!el) return 'nothing';
  const d = el.closest('[data-dim]'), c = el.closest('[data-tcell]'), v = el.closest('[data-view]'), b = el.closest('button');
  if (d) return `dimension ${d.dataset.dim}`;
  if (c) return `title cell ${c.dataset.tcell}`;
  if (v) return `view ${v.dataset.view}`;
  if (b) return `button ${b.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)}`;
  return el.tagName === 'CANVAS' ? 'the 3D view' : el.tagName.toLowerCase();
}

/** A mouse press / drag / double-click as the user's, at screen points: pointer + mouse events on what is there. A
 *  pointer capture asked for (a drag) gets the rest, as in the browser (what was pressed may be drawn anew). */
async function gesture(path, { double = false } = {}) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const [x0, y0] = path[0], end = path[path.length - 1];
  if (!document.elementFromPoint(x0, y0)) throw new Error('That point is off the screen.');
  let captured = null;
  const ev = (el, type, [x, y], buttons) => {
    const o = { bubbles: true, cancelable: true, composed: true, clientX: x, clientY: y, button: 0, buttons, pointerId: 1, pointerType: 'mouse', isPrimary: true, detail: 1 };
    el.dispatchEvent(type.startsWith('pointer') ? new PointerEvent(type, o) : new MouseEvent(type, o));
  };
  const to = (p) => captured || document.elementFromPoint(...p) || document.body;
  const cap = Element.prototype.setPointerCapture, rel = Element.prototype.releasePointerCapture;
  Element.prototype.setPointerCapture = function () { captured = this; }; // (a made-up pointer cannot be captured)
  Element.prototype.releasePointerCapture = function () { captured = null; };
  try {
    for (let k = 0; k < (double ? 2 : 1); k++) {
      captured = null;
      const down = document.elementFromPoint(x0, y0);
      ev(down, 'pointerdown', path[0], 1);
      ev(down.isConnected ? down : to(path[0]), 'mousedown', path[0], 1);
      if (path.length > 1) {
        for (let s = 1; s <= 10; s++) { // the drag in steps
          const p = [x0 + ((end[0] - x0) * s) / 10, y0 + ((end[1] - y0) * s) / 10];
          ev(to(p), 'pointermove', p, 1);
          ev(to(p), 'mousemove', p, 1);
          await sleep(16);
        }
      }
      const up = to(end);
      ev(up, 'pointerup', end, 0);
      ev(up, 'mouseup', end, 0);
      ev(up, 'click', end, 0);
      await sleep(80);
    }
    if (double) ev(to(path[0]), 'dblclick', path[0], 0);
  } finally {
    Element.prototype.setPointerCapture = cap;
    Element.prototype.releasePointerCapture = rel;
  }
}

/** A key press (e.g. "Delete", "Enter", "Escape", "ctrl+z") on what has the focus. */
function press(spec) {
  const parts = String(spec).split('+').map((s) => s.trim()), key0 = parts.pop(), mods = parts.map((m) => m.toLowerCase());
  const named = { del: 'Delete', delete: 'Delete', enter: 'Enter', esc: 'Escape', escape: 'Escape', tab: 'Tab', backspace: 'Backspace', space: ' ', up: 'ArrowUp', down: 'ArrowDown', left: 'ArrowLeft', right: 'ArrowRight' };
  const key = named[key0.toLowerCase()] || (key0.length === 1 ? (mods.includes('shift') ? key0.toUpperCase() : key0.toLowerCase()) : key0);
  const o = { key, code: key.length === 1 ? `Key${key.toUpperCase()}` : key, bubbles: true, cancelable: true,
    ctrlKey: mods.includes('ctrl') || mods.includes('control'), shiftKey: mods.includes('shift'), altKey: mods.includes('alt'), metaKey: mods.includes('meta') };
  const el = document.activeElement && document.activeElement !== document.body ? document.activeElement : document.body;
  el.dispatchEvent(new KeyboardEvent('keydown', o));
  el.dispatchEvent(new KeyboardEvent('keyup', o));
}

export function moreHandlers({ state, project, modeler, assembly, drawing2d, sheet, drawingSet, t2 }) {
  const need = (ws, what) => { if (state.workspace !== ws) throw new Error(`${what} — the part on screen is not one (open_part one).`); };
  const D = () => { need('drawing', 'This is for a 2D drawing (a DXF / DWG / Gerber / ODB++ opened as a 📐 drawing)'); return drawing2d; };
  const FIELDS = ['shape', 'layer', 'dia', 'r', 'len', 'w', 'color', 'text'];
  const ok = (text) => ({ text: typeof text === 'string' ? text : JSON.stringify(text) });

  const shapeOf = (e) => ({ id: e.id, t: e.t, layer: e.layer, ...(e.r ? { d: r3(2 * e.r) } : {}), ...(e.c ? { c: e.c.map(r3) } : {}),
    ...(e.a ? { a: e.a.map(r3), b: e.b.map(r3) } : {}), ...(e.w ? { w: e.w } : {}), ...(e.t === 'text' ? { text: e.text } : {}) });

  return {
    // ---------------------------------------------------------------- 2D drawings
    get_drawing: async () => {
      const ed = D(), d = ed.d, count = {};
      for (const e of d.entities) { const k = `${e.layer}`; count[k] = (count[k] || 0) + 1; }
      const kinds = {};
      for (const e of d.entities) kinds[e.t] = (kinds[e.t] || 0) + 1;
      const bb = ed.bbox(d.entities);
      return ok({ source: d.source, units: d.file_units || 'mm', pcb: d.pcb || undefined, shapes: kinds, size_mm: bb ? [r3(bb[2] - bb[0]), r3(bb[3] - bb[1])] : null,
        layers: d.layers.map((l) => ({ name: l.name, shown: l.visible !== false, shapes: count[l.name] || 0, ...(l.kind ? { kind: l.kind } : {}) })),
        selected: ed.sel.size, filters: ed.filters });
    },
    drawing_find: async ({ filters = [], select = true }) => {
      const ed = D();
      for (const f of filters) if (!FIELDS.includes(f.field)) throw new Error(`filter field is one of ${FIELDS.join(', ')} (op: is / is not / is any of for shape, layer, color; = ≠ < > ≤ ≥ for numbers; contains / is for text).`);
      ed.filters = filters.map((f) => ({ field: f.field, op: f.op || (['shape', 'layer', 'color'].includes(f.field) ? 'is' : f.field === 'text' ? 'contains' : '='), value: f.value }));
      const found = ed.matches();
      if (select) ed.sel = new Set(found.map((e) => e.id));
      ed.updateMatches();
      ed.renderProps();
      return ok({ found: found.length, selected: ed.sel.size, first: found.slice(0, 15).map(shapeOf) });
    },
    drawing_layers: async ({ show = [], hide = [], only = null, color = {}, new: add = null, active = null }) => {
      const ed = D();
      if (add) {
        if (ed.d.layers.some((l) => l.name === add)) throw new Error(`There is a layer ${add} already.`);
        ed.d.layers = [...ed.d.layers, { name: String(add), color: '#7ee787', visible: true }];
        ed.d.active = String(add);
      }
      const names = new Set(ed.d.layers.map((l) => l.name));
      const bad = [...show, ...hide, ...(only || []), ...Object.keys(color || {}), ...(active ? [active] : [])].filter((n) => !names.has(n));
      if (bad.length) throw new Error(`No layer ${bad.join(', ')}. Layers: ${[...names].join(', ')}.`);
      for (const [n, c] of Object.entries(color || {})) if (!/^#[0-9a-f]{6}$/i.test(c)) throw new Error(`color of ${n}: "#rrggbb", not ${c}.`);
      ed.d.layers = ed.d.layers.map((l) => {
        const x = { ...l };
        if (only) x.visible = only.includes(l.name);
        if (show.includes(l.name)) x.visible = true;
        if (hide.includes(l.name)) x.visible = false;
        if (color?.[l.name]) x.color = color[l.name];
        return x;
      });
      if (active) ed.d.active = active;
      ed.commit();
      return ok(`Shown: ${ed.d.layers.filter((l) => l.visible !== false).map((l) => l.name).join(', ') || 'none'}; new shapes go on ${ed.d.active}.`);
    },
    drawing_delete: async ({ what = 'selection' }) => {
      const ed = D(), ids = what === 'found' ? new Set(ed.matches().map((e) => e.id)) : new Set(ed.sel);
      if (!ids.size) throw new Error(what === 'found' ? 'The filters find nothing (drawing_find).' : 'Nothing is selected — drawing_find the shapes first.');
      const n = ids.size;
      ed.sel = ids;
      ed.removeSel();
      return ok(`${n} shape(s) deleted; ${ed.d.entities.length} left.`);
    },
    drawing_add: async ({ shapes = [], layer = null }) => {
      const ed = D(), on = layer || ed.d.active;
      if (!ed.d.layers.some((l) => l.name === on)) throw new Error(`No layer ${on} — drawing_layers {new: "${on}"} makes it.`);
      const P = (p, what) => { if (!Array.isArray(p) || p.length !== 2 || !p.every((v) => Number.isFinite(+v))) throw new Error(`${what}: [x, y] in mm.`); return p.map((v) => +v); };
      const add = shapes.map((s) => {
        if (s.line) return { t: 'line', a: P(s.line.a, 'line.a'), b: P(s.line.b, 'line.b') };
        if (s.circle) { const d = +(s.circle.d ?? 2 * +s.circle.r); if (!(d > 0)) throw new Error('circle.d: its diameter (mm).'); return { t: 'circle', c: P(s.circle.c, 'circle.c'), r: d / 2 }; }
        throw new Error('A shape is {line: {a, b}} or {circle: {c, d}}.');
      });
      if (!add.length) throw new Error('shapes: [{line: {a, b}} | {circle: {c, d}}].');
      for (const sh of add) ed.d.entities = [...ed.d.entities, { id: ed.newId(), layer: on, ...sh }];
      ed.commit();
      return ok(`${add.length} shape(s) drawn on ${on}.`);
    },
    drawing_units: async ({ units }) => {
      const ed = D();
      if (!['mm', 'cm', 'm', 'in'].includes(units)) throw new Error('units: mm, cm, m or in.');
      const was = ed.d.file_units || 'mm';
      ed.setUnits(units);
      const bb = ed.bbox(ed.d.entities);
      return ok(`One unit of the file is ${units} now (was ${was}); its size: ${bb ? `${r3(bb[2] - bb[0])} × ${r3(bb[3] - bb[1])} mm` : '—'}.`);
    },
    drawing_set_size: async ({ kind, value }) => {
      const ed = D();
      if (!['dia', 'r', 'len'].includes(kind)) throw new Error('kind: dia (circles / arcs Ø), r (their radius) or len (lines).');
      if (!ed.sel.size) throw new Error('Nothing is selected — drawing_find the shapes first.');
      ed.setSize(kind, value);
      return ok(`${ed.sel.size} selected shape(s): ${kind} = ${value} mm (circles keep their centres, lines their start).`);
    },
    drawing_use: async ({ as = 'sketch', what = 'selection' }) => {
      const ed = D(), shown = ed.d.entities.filter((x) => ed.shown(x));
      const pick = what === 'all' ? shown : what === 'found' ? ed.matches() : shown.filter((x) => ed.sel.has(x.id));
      if (!pick.length) throw new Error(what === 'selection' ? 'Nothing is selected (drawing_find, or what: "all").' : 'No shapes.');
      const d = { ...ed.payload(), entities: structuredClone(pick) };
      if (as === 'sketch') await ed.hooks.useAsSketch?.(d); else await ed.hooks.useAsQuick?.(d);
      return ok(`${pick.length} shape(s) used as ${as === 'sketch' ? 'the sketch of a new 3D model (on screen now: get_model)' : 'a quick part (on screen now: get_part)'}.`);
    },

    // ---------------------------------------------------------------- the GUI as the user sees it
    gui_state: async ({ where = 'all' } = {}) => {
      const list = guiControls(where), sg = suggestInfo(guiControls('all'));
      // the 3D model's step tree as the user sees it: names, what each makes, turned off / failing / selected / being changed
      const rows = state.workspace === 'model' ? [...document.querySelectorAll('#modelLeft .mt-item')] : [];
      // (nested as shown: depth 1 = under its parent — a step's sketch under the step, a reference point under 'ref')
      const steps = rows.length ? rows.map((r) => ({ id: r.dataset.id, name: r.querySelector('.mt-name')?.textContent || '', what: r.querySelector('.mt-what')?.textContent || '',
        ...(r.dataset.parent ? { parent: r.dataset.parent, depth: +r.dataset.depth || 1 } : {}), ...(r.hidden ? { folded: true } : {}),
        ...(r.classList.contains('off') ? { off: true } : {}), ...(r.classList.contains('bad') ? { failed: r.title || true } : {}),
        ...(r.classList.contains('on') ? { selected: true } : {}), ...(r.classList.contains('editing') ? { editing: true } : {}),
        ...(r.classList.contains('rolled') ? { state: 'rolled_back' } : {}) })) : undefined; // (⏮ under the rollback bar: kept, not built)
      const bar = rows.length && document.querySelector('#modelLeft .mt-rollbar.rolled'); // (the bar up: under which top-level step)
      const above = bar && [...document.querySelectorAll('#modelLeft .mt-tree > *')].slice(0, [...bar.parentNode.children].indexOf(bar)).reverse().find((r) => r.matches('.mt-item[data-depth="0"]'));
      // 🎬 an animation being recorded (its progress) or the last one saved (its file)
      const anim = state.workspace === 'assembly' ? animState(assembly?.mech) : null;
      // ⚙ Mechanism's rows (a sub-assembly's own ones too: `inside` — its placement)
      const mechs = state.workspace === 'assembly' && !assembly?.mech?.closed ? (assembly?.mech?.list || []).map((m) => ({ id: m.id, name: m.name, ...(m.inside ? { inside: m.inside } : {}) })) : [];
      if (where === 'suggest') return ok({ workspace: state.workspace, suggestions: sg || 'No suggestions table on screen — select something (gui_action at / pick) and it shows what fits it.', controls: list.map(({ el, ...c }) => c) });
      return ok({ workspace: state.workspace, ...(sg ? { suggestions: sg } : {}), controls: list.map(({ el, ...c }) => c), ...(steps ? { steps } : {}), ...(bar ? { rollback_bar: { under: above?.dataset.id || null } } : {}), ...(anim ? { animation: anim } : {}), ...(mechs.length ? { mechanisms: mechs } : {}),
        toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent.trim()).slice(-3) });
    },
    gui_action: async ({ control, click, value, key: keys, at, at_mm, drag_to, double, suggest, pick } = {}) => {
      const shown = () => { const sg = suggestInfo(); return { workspace: state.workspace, selected: state.workspace === 'assembly' ? assembly.sel || null : state.workspace === 'sheet' ? sheet.sel || null : undefined,
        toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent.trim()).slice(-3), ...(sg ? { suggestions: sg } : {}) }; };
      const settle = () => new Promise((r) => setTimeout(r, 400));
      // the controls changed by it (a part chosen: its panel): the list with their new numbers comes with the answer
      const sig = (list) => list.map((x) => `${x.kind}|${x.label}`).join('\n');
      const fresh = (was) => { const list = guiControls('all'); return sig(list) === was ? {} : { controls_changed: 'the controls on screen changed — their numbers now (gui_state\'s were before):', controls: list.map(({ el, title, ...x }) => x) }; };
      const before = sig(guiControls('all'));
      // a row of the suggestions table, by its label (one under ⋯ Show all: that opened first, as the user would)
      if (suggest !== undefined && suggest !== null && suggest !== '') {
        const tables = suggestTables();
        if (!tables.length) throw new Error('No suggestions table on screen — select something first (gui_action at / pick: a face, a part, a dimension), then gui_state shows what it offers.');
        const hit = findSuggestion(tables, suggest);
        if (!hit) throw new Error(`No suggestion “${suggest}” — the table “${tables[0].title}” offers: ${tables[0].rows.map((r) => `${r.icon} ${r.label}`.trim()).join(', ')}.`);
        if (!runSuggestion(hit.box, hit.row.i)) throw new Error(`The row “${hit.row.label}” could not be clicked — gui_state for the table now.`);
        await settle();
        return ok({ done: `suggestion “${`${hit.row.icon} ${hit.row.label}`.trim()}” clicked${hit.row.shown ? '' : ' (it was under ⋯ Show all: that opened first)'}`, ...shown(), ...fresh(before) });
      }
      // a named face / part clicked where it shows on screen (the table then offers what fits it)
      if (pick !== undefined && pick !== null && pick !== '') {
        const p = pointOf(state, modeler, assembly, pick);
        if (!p) throw new Error(`“${pick}” is not in sight in the view — find_refs / get_assembly give the names; set_view (another side) may show it.`);
        const under = underAt(...p), vb = viewEl().getBoundingClientRect();
        await gesture([p]);
        await settle();
        return ok({ done: `clicked ${pick} (${under})`, at: [r3((p[0] - vb.left) / vb.width), r3((p[1] - vb.top) / vb.height)], ...shown(), ...fresh(before) });
      }
      let c = null;
      if (control !== undefined && control !== null && control !== '') {
        const list = guiControls('all'), want = String(control).trim().toLowerCase();
        c = list.find((x) => String(x.n) === want) || list.find((x) => x.label.toLowerCase() === want) || list.find((x) => x.label.toLowerCase().includes(want));
        if (!c) throw new Error(`No control “${control}” on screen — gui_state lists them (n or label).`);
        if (c.disabled) throw new Error(`“${c.label}” is greyed out (disabled)${c.title ? `: ${c.title}` : ''}.`);
      }
      // a point: of the view (at: [x, y] 0 … 1 across / down it), of the sheet's paper (at_mm), or a drawn thing's middle
      const view = viewEl(), vr = view?.getBoundingClientRect();
      const ofView = (p, what) => {
        if (!vr) throw new Error('No view on screen.');
        if (!Array.isArray(p) || p.length !== 2 || !p.every((v) => Number.isFinite(+v))) throw new Error(`${what}: [x, y], 0 … 1 across and down the view.`);
        return [vr.left + +p[0] * vr.width, vr.top + +p[1] * vr.height];
      };
      const ofPaper = (p) => {
        if (state.workspace !== 'sheet' || !sheet.svgEl) throw new Error('at_mm is a point on a drawing sheet\'s paper (mm from its top left) — open the sheet first.');
        const q = sheet.svgEl.createSVGPoint();
        [q.x, q.y] = [+p[0], +p[1]];
        const s = q.matrixTransform(sheet.svgEl.getScreenCTM());
        return [s.x, s.y];
      };
      let from = null;
      if (at_mm) from = ofPaper(at_mm);
      else if (at) from = ofView(at, 'at');
      else if (c && (['dim', 'cell', 'view'].includes(c.kind) || drag_to || double)) { const r = c.el.getBoundingClientRect(); from = [r.left + r.width / 2, r.top + r.height / 2]; }
      if (from) {
        const under = underAt(...from), to = drag_to ? (at_mm ? ofPaper(drag_to) : ofView(drag_to, 'drag_to')) : null;
        await gesture(to ? [from, to] : [from], { double: !!double });
        if (keys) press(keys);
        await settle();
        return ok({ done: `${double ? 'double-clicked' : to ? 'dragged' : 'clicked'} ${under}${to ? ` to ${underAt(...to)}` : ''}${keys ? `, then ${keys}` : ''}`, ...shown(), ...fresh(before) });
      }
      if (!c) {
        if (!keys) throw new Error('control (from gui_state), a point (at / at_mm) or a key.');
        press(keys);
        await settle();
        return ok({ done: `pressed ${keys}`, ...shown(), ...fresh(before) });
      }
      const el = c.el;
      if (keys) {
        el.focus();
        press(keys);
        await settle();
        return ok({ done: `pressed ${keys} on ${c.kind} “${c.label}”`, ...shown(), ...fresh(before) });
      }
      const typed = /^(range|number|text|color)$/.test(el.type || '') || el.tagName === 'SELECT', given = value !== undefined && value !== null;
      if (given && !typed) { // (a value for a button: the panel changed under the AI's numbers — never click it then)
        const on = c.kind === 'checkbox' && [true, false, 'on', 'off', 'true', 'false', 1, 0].includes(value);
        if (!on) throw new Error(`n ${c.n} is a ${c.kind} (“${c.label}”), not a slider, box or choice — nothing done. The controls may have changed since gui_state: call it again for the numbers now.`);
        if (el.checked !== [true, 'on', 'true', 1].includes(value)) el.click(); // (a checkbox set on / off)
      } else if (given) {
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (click !== false) {
        el.dispatchEvent(new MouseEvent('mouseenter'));
        el.click();
      }
      await settle();
      return ok({ done: `${c.kind} “${c.label}”${given ? ` = ${value}` : ' clicked'}`, ...shown(), ...fresh(before) });
    },

    // ---------------------------------------------------------------- drawing sheets (📄)
    sheet_open: async ({ part } = {}) => {
      const p = part ? project.parts.find((q) => q.id === part || q.name === part) : project.current;
      if (!p) throw new Error(`No part ${part} — see list_parts.`);
      if (p.kind === 'sheet') { await project.switchTo(p.id); } else {
        if (p.kind !== 'model' && p.kind !== 'assembly') throw new Error(`${p.name} is not a 3D model or an assembly — a drawing sheet is of one.`);
        await project.newSheet(p.id, `${p.name} — ${t2('drawing', {})}`);
      }
      await sheet.ensure();
      return ok(sheet.summary());
    },
    get_sheet: async ({ points } = {}) => {
      need('sheet', 'This is for a drawing sheet (📄) — sheet_open opens one');
      await sheet.ensure();
      return ok({ ...sheet.summary(), ...(points ? { [points]: sheet.pointsOf(points) } : {}) });
    },
    sheet_edit: async ({ preset, view_presets, paper, views, remove = [], restore, add = [], move = {}, dims, texts, all_sheets, complete, drop_twice, fits, scale, view_scales, view_names, template, template_all, save_template, frame, title_style, bom_style, all_pages } = {}) => {
      need('sheet', 'This is for a drawing sheet (📄) — sheet_open opens one');
      const ed = sheet, done = [];
      if (all_pages !== undefined) {
        if (all_pages && !ed.rootOf(ed.d.source)) throw new Error('This sheet is not in an assembly — it has no drawing set.');
        if (!!all_pages !== !!ed.setMode) ed.action('setview');
        done.push(all_pages ? 'all the sheets of the drawing set shown, one below the other' : 'this sheet alone again');
      }
      if (template !== undefined) {
        await ed.loadTemplates();
        ed.useTemplate(template || DEFAULT_TPL.name);
        done.push(`title block ${template || DEFAULT_TPL.name}`);
      }
      if (title_style !== undefined || bom_style !== undefined) {
        ed.setStyles({ ...(title_style !== undefined ? { title: title_style || 'block' } : {}), ...(bom_style !== undefined ? { bom: bom_style || 'modern' } : {}) });
        await ed.ensure();
        done.push(`title block style ${ed.tb().style}, parts list style ${ed.tb().bomStyle}`);
      }
      if (frame !== undefined) {
        if (frame === null) { delete ed.d.frame; ed.d.views = {}; ed.history.commit(); await ed.ensure(); } else {
          if (typeof frame === 'string' ? !['simple', 'iso', 'narrow', 'none'].includes(frame) : typeof frame !== 'object') throw new Error('frame: "simple" | "iso" | "narrow" | "none" | {m: [left, top, right, bottom] mm, line: mm, zones, marks} | null (the template\'s).');
          ed.setFrame(frame);
          await ed.ensure();
        }
        done.push(`frame ${typeof frame === 'string' ? frame : frame ? 'custom' : 'as the template'}`);
      }
      const sc = (v, what) => { if (v === null || v === '') return null; const s = parseScale(v); if (!s) throw new Error(`${what}: a scale such as "1:2", "2:1" or "1:2522" (null: ${what === 'scale' ? 'automatic' : 'the sheet\'s'}).`); return s; };
      if (scale !== undefined) {
        const s = sc(scale, 'scale');
        if (s) ed.d.scale = s; else delete ed.d.scale;
        ed.d.views = {};
        done.push(`scale ${scale || 'auto'}`);
      }
      for (const [v, s] of Object.entries(view_scales || {})) {
        if (!['Front', 'Top', 'Right', 'Iso', 'Section'].includes(v)) throw new Error('view_scales: {Front | Top | Right | Iso | Section: "2:1" | null}.');
        const k = sc(s, 'view_scales');
        ed.d.vscale = { ...(ed.d.vscale || {}) };
        if (k) ed.d.vscale[v] = k; else delete ed.d.vscale[v];
        done.push(`${v} ${s || 'at the sheet\'s scale'}`);
      }
      for (const [v, n] of Object.entries(view_names || {})) {
        if (!['Front', 'Top', 'Right', 'Iso', 'Section'].includes(v)) throw new Error('view_names: {Front | Top | Right | Iso | Section: "name" | null}.');
        const names = { ...(ed.d.viewNames || {}) };
        if (String(n ?? '').trim()) names[v] = String(n).trim().slice(0, 40); else delete names[v];
        ed.d.viewNames = names;
        done.push(`${v} named ${n || 'as standard'}`);
      }
      if (scale !== undefined) await ed.ensure(true);
      if (preset !== undefined) {
        if (!['light', 'medium', 'full'].includes(preset)) throw new Error('preset: light, medium or full.');
        ed.d.preset = preset;
        done.push(`preset ${preset}`);
      }
      if (paper !== undefined) {
        if (paper && !['A4', 'A3'].includes(paper)) throw new Error('paper: "A4", "A3" or null (chosen by the size).');
        ed.d.paper = paper || null;
        ed.d.views = {};
        done.push(`paper ${paper || 'auto'}`);
      }
      for (const [v, p] of Object.entries(view_presets || {})) {
        if (!['Front', 'Top', 'Right'].includes(v) || (p && !['light', 'medium', 'full'].includes(p))) throw new Error('view_presets: {Front | Top | Right: "light" | "medium" | "full" | null (as the sheet)}.');
        ed.d.vpreset = { ...(ed.d.vpreset || {}) };
        if (p) ed.d.vpreset[v] = p; else delete ed.d.vpreset[v];
        done.push(`${v} ${p || 'as the sheet'}`);
      }
      if (preset !== undefined || paper !== undefined || view_presets) await ed.ensure(true);
      for (const [v, on] of Object.entries(views || {})) {
        if (!['Front', 'Top', 'Right', 'Iso'].includes(v)) throw new Error('views: {Front | Top | Right | Iso: true / false}.');
        if (on) delete ed.d.off[v]; else ed.d.off[v] = true;
        done.push(`${v} ${on ? 'shown' : 'hidden'}`);
      }
      if (restore) { ed.d.hidden = []; done.push('the deleted ones back'); }
      for (const [k, v] of Object.entries(texts || {})) {
        if (!['title', 'number', 'drawn', 'note', 'company', 'address', 'tolstd', 'surface', 'checked', 'approved', 'material'].includes(k)) throw new Error('texts: {title, number, drawn, note, company, address, tolstd, surface, checked, approved, material (an assembly\'s sheet)} — the title block\'s own texts.');
        ed.d.texts = { ...(ed.d.texts || {}) };
        if (String(v ?? '').trim()) ed.d.texts[k] = String(v).trim(); else delete ed.d.texts[k];
        done.push(`${k}: ${v || '—'}`);
      }
      if (texts && all_sheets) { // the project-wide ones on every sheet of the assembly's drawing set (sheet/tbedit.js says which)
        const asm = !!ed.d.asm && !ed.d.bom, go = Object.fromEntries(Object.entries(texts).filter(([k]) => propagates(k, asm)));
        const kept = Object.keys(texts).filter((k) => !(k in go));
        if (!ed.rootOf(ed.d.source)) done.push('all_sheets: this sheet is not in an assembly\'s drawing set');
        else if (Object.keys(go).length) done.push(`${Object.keys(go).join(', ')} on all ${ed.setTextsAll(go)} sheets of the set`);
        if (kept.length) done.push(`${kept.join(', ')} kept on this sheet only (each drawing's own)`);
      }
      const ids = new Set(ed.allDims().map((d) => d.id).concat(ed.d.hidden, ed.d.user.map((d) => d.id)));
      for (const id of [].concat(remove)) {
        if (!ids.has(id)) throw new Error(`No dimension ${id} — get_sheet lists them.`);
        ed.remove(id);
      }
      if ([].concat(remove).length) done.push(`${[].concat(remove).length} removed`);
      for (const [id, o] of Object.entries(move || {})) {
        const d = ed.allDims().find((x) => x.id === id);
        if (!d) throw new Error(`No dimension ${id} — get_sheet lists them.`);
        const keep = {};
        if (o.side !== undefined) { if (!(d.dir === 'h' ? ['t', 'b'] : ['l', 'r']).includes(o.side)) throw new Error(`side of ${id}: ${d.dir === 'h' ? '"t" (above) or "b" (below)' : '"l" (left) or "r" (right)'}.`); keep.side = o.side; }
        if (o.off !== undefined) keep.off = Math.max(3, +o.off);
        if (o.ang !== undefined) keep.ang = +o.ang;
        if (o.len !== undefined) keep.len = Math.max(2, +o.len);
        ed.setDim(d, { ...(ed.d.dims[id] || {}), ...keep });
      }
      if (Object.keys(move || {}).length) done.push(`${Object.keys(move).length} moved`);
      for (const [id, f] of Object.entries(fits || {})) { ed.setFit(id, f || ''); done.push(`${id} ${f || 'no fit'}`); }
      for (const [id, o] of Object.entries(dims || {})) { // a dimension's tolerance (±0.1, +0.2/−0.1) and reference (in brackets)
        const d = ed.allDims().find((x) => x.id === id);
        if (!d) throw new Error(`No dimension ${id} — get_sheet lists them.`);
        if (!o || typeof o !== 'object') throw new Error(`dims: {${id}: {tol: "±0.1" | "+0.2/-0.1" | null, ref: true | false}}.`);
        const props = {};
        if (o.tol !== undefined) {
          if (o.tol && (d.kind === 'pcd' || (d.kind === 'dia' && !d.thread))) throw new Error(`${id} is a Ø — give it a fit (fits {${id}: "H7"}), not a tolerance.`);
          const v = tolText(o.tol || '');
          if (v === null) throw new Error(`tol of ${id}: write it as "±0.1" or "+0.2/-0.1" (null: none).`);
          props.tol = v || undefined;
        }
        if (o.ref !== undefined) props.ref = !!o.ref;
        ed.setDimProps(id, props);
        done.push(`${id} ${[o.tol !== undefined && (props.tol || 'no tolerance'), o.ref !== undefined && (o.ref ? 'a reference dimension' : 'not a reference')].filter(Boolean).join(', ')}`);
      }
      const added = [].concat(add).map((spec) => ed.addFor(spec));
      if (added.length) done.push(`added ${added.join(', ')}`);
      if (drop_twice) { const ck = ed.check(); const ids = [...ck.dup, ...ck.over]; for (const id of ids) ed.remove(id); done.push(`${ids.length} given twice removed`); }
      if (complete) done.push(`${ed.addAllMissing()} missing size(s) added`);
      ed.commit();
      if (save_template) done.push(`saved as the template ${await ed.saveTemplate(String(save_template))}`);
      if (template_all) {
        if (ed.ownStyles()) throw new Error('This drawing\'s own title block / parts list style is not in a template yet — give save_template "<name>" with template_all.');
        done.push(`${await ed.useTemplateForSet()} drawing(s) of the set use ${ed.tplName()}`);
      }
      return ok({ done: done.join('; ') || 'nothing', ...ed.summary() });
    },

    // ---------------------------------------------------------------- joints and measuring (assembly)
    edit_joint: async ({ id, gap, distance, lock_rotation, angle, flip, locked, name, ratio }) => {
      need('assembly', 'Joints are in an assembly');
      const a = assembly, m = (a.doc.mates || []).find((x) => x.id === id), cp = (a.doc.couplings || []).find((x) => x.id === id);
      if (cp) { // ⚙ a coupling: its ratio, the way round, its name
        if (ratio !== undefined) { if (!(+ratio > 0)) throw new Error('ratio is a number above 0.'); cp.ratio = +ratio; }
        if (flip !== undefined) { if (flip) cp.flip = !cp.flip; }
        if (name !== undefined) { if (String(name || '').trim()) cp.name = String(name).trim(); else delete cp.name; }
        a.commit();
        return ok(a.summary().couplings.find((c) => c.id === id));
      }
      if (ratio !== undefined && m) throw new Error(`ratio is for a coupling (G…: gear / belt / rack); ${id} is a joint.`);
      if (!m) throw new Error(`No joint ${id} — get_assembly lists the joints.`);
      if (m.locked && locked !== false && [gap, distance, lock_rotation, angle, flip].some((v) => v !== undefined && v !== false)) {
        throw new Error(`Joint ${id} is locked 🔒 — edit_joint {id, locked: false} first (only when the user wants it).`);
      }
      if (gap !== undefined) { m.gap = +gap; if (m.type === 'touch' && +gap) m.type = 'gap'; }
      if (distance !== undefined) {
        if (m.type !== 'axis') throw new Error('distance is for a concentric (axis) joint; flat joints take gap.');
        if (distance === null) { delete m.dist; delete m.side; } else { if (!m.side) m.side = 1; m.dist = +distance; }
      }
      if (lock_rotation !== undefined) { if (lock_rotation) m.angle = Math.round(a.spinNow(m)); else delete m.angle; }
      if (angle !== undefined) { if (m.type === 'angle') m.value = Math.max(0, Math.min(180, +angle)); else m.angle = +angle; }
      if (flip) a.flipJoint(m);
      if (locked !== undefined) m.locked = !!locked;
      if (name !== undefined) { if (String(name || '').trim()) m.name = String(name).trim(); else delete m.name; }
      a.applyMates();
      a.commit();
      return ok(a.summary().joints.find((j) => j.id === id));
    },
    remove_joint: async ({ id }) => {
      need('assembly', 'Joints are in an assembly');
      const a = assembly, m = (a.doc.mates || []).find((x) => x.id === id);
      if (!m && (a.doc.couplings || []).some((c) => c.id === id)) { // ⚙ a coupling: the parts turn on their own again
        a.doc.couplings = a.doc.couplings.filter((c) => c.id !== id);
        a.commit();
        return ok(`Coupling ${id} removed — its two parts move on their own again.`);
      }
      if (!m) throw new Error(`No joint ${id} — get_assembly lists the joints.`);
      if (m.locked) throw new Error(`Joint ${id} is locked 🔒 — edit_joint {id, locked: false} first (only when the user wants it).`);
      a.doc.mates = a.doc.mates.filter((x) => x !== m);
      a.applyMates(); // (its other joints hold it again)
      a.commit();
      return ok(`Joint ${id} removed — ${m.move} stays where it is (held by its other joints, if any).`);
    },
    measure: async ({ a: A, b: B }) => {
      // (📏 also a row of the measurements table, as the user's: its main value as the table shows it)
      const row = (host, fa, fb, na, nb) => { const r = host.ms.addPair({ kind: 'face', face: fa, id: na, at: fa.centroid }, { kind: 'face', face: fb, id: nb, at: fb.centroid }), s = host.ms.summary().at(-1); return { table_row: s.n, value: s.value, unit: s.unit, kind: r.kind, details: s.details }; };
      if (state.workspace === 'model') { // (two faces of the 3D model on screen)
        const out = measureModel(modeler, A, B), f = (x) => modeler.result.body.faces.find((q) => q.name === (x?.face ?? x) || (q.names || []).includes(x?.face ?? x));
        return ok({ ...row(modeler, f(A), f(B), A?.face ?? A, B?.face ?? B), ...out });
      }
      need('assembly', 'Measuring between faces is in a 3D model or an assembly');
      const fa = assembly.worldFace(A.part, A.face), fb = assembly.worldFace(B.part, B.face);
      const out = { centres_apart: r3(fa.centroid.distanceTo(fb.centroid)) };
      if (fa.normal && fb.normal) {
        const ang = (fa.normal.angleTo(fb.normal) * 180) / Math.PI;
        out.angle_between_normals = r3(ang);
        if (ang < 0.5 || ang > 179.5) out.gap_between_faces = r3(Math.abs(fb.centroid.clone().sub(fa.centroid).dot(fa.normal)));
      }
      if (fa.axis && fb.axis) {
        const d = fa.axis.d.clone().normalize(), off = fb.axis.o.clone().sub(fa.axis.o);
        if (Math.abs(Math.abs(d.dot(fb.axis.d.clone().normalize())) - 1) < 1e-4) out.axes_apart = r3(off.sub(d.multiplyScalar(off.dot(d))).length());
        out.diameters = [r3(2 * fa.radius), r3(2 * fb.radius)];
      }
      return ok({ ...row(assembly, fa, fb, `${A.part}·${A.face}`, `${B.part}·${B.face}`), ...out });
    },
    list_measurements: async () => {
      const host = state.workspace === 'model' ? modeler : state.workspace === 'assembly' ? assembly : null;
      if (!host) throw new Error('The 📏 measurements are kept in a 3D model or an assembly — open_part one.');
      return ok({ measurements: host.ms.summary() });
    },
    clear_measurements: async () => {
      const host = state.workspace === 'model' ? modeler : state.workspace === 'assembly' ? assembly : null;
      if (!host) throw new Error('The 📏 measurements are kept in a 3D model or an assembly — open_part one.');
      const n = host.ms.rows().length;
      host.ms.clear();
      return ok(`${n} measurement(s) cleared (↶ in the toast brings them back).`);
    },

    // ---------------------------------------------------------------- the view (then get_screenshot)
    set_view: async ({ view, section, explode, sizes }) => {
      const ws = state.workspace;
      if (ws !== 'model' && ws !== 'assembly') throw new Error('The view is set in a 3D model or an assembly.');
      const host = ws === 'model' ? modeler : assembly, v = host.view;
      if (view) { if (!['iso', 'top', 'front', 'right'].includes(view)) throw new Error('view: iso, top, front or right.'); v.setView(view); }
      if (section !== undefined) {
        if (section === null || section === false || ['off', 'none', ''].includes(String(section).toLowerCase())) { if (host.section) host.toggleSection(); v.setSection?.(null); } else {
          const axis = section.axis || 'y';
          if (!host.section) host.toggleSection();
          const bb = ws === 'model' ? host.result?.body?.bbox : v.shownBox();
          if (host.section && bb) {
            Object.assign(host.section, { axis, offset: Number.isFinite(+section.offset) ? +section.offset : sectionMiddle(bb, axis), flip: !!section.flip });
            v.setSection(host.section);
            host.renderSection();
          }
        }
      }
      if (explode !== undefined) {
        if (ws !== 'assembly') throw new Error('explode is for an assembly.');
        assembly.explode = Math.max(0, Math.min(1, +explode || 0));
        assembly.render();
        assembly.draw();
      }
      if (sizes) modeler.setSizeMode(sizes);
      return ok(`View${view ? ` ${view}` : ''}${host.section ? `, cut along ${host.section.axis} at ${r3(host.section.offset)} mm` : ''}${ws === 'assembly' && assembly.explode ? `, exploded ${assembly.explode}` : ''} — get_screenshot to look.`);
    },

    // ---------------------------------------------------------------- the project's parts
    rename_part: async ({ id, name }) => {
      const p = project.parts.find((q) => q.id === id || q.name === id);
      if (!p || !String(name || '').trim()) throw new Error('id (or the name) of a part from list_parts, and the new name.');
      project.rename(p.id, String(name).trim());
      return ok(`${p.id} is “${p.name}” now.`);
    },
    delete_part: async ({ id }) => {
      const p = project.parts.find((q) => q.id === id || q.name === id);
      if (!p) throw new Error(`No part ${id} — see list_parts.`);
      const used = project.usedBy(p.id);
      if (used.length) throw new Error(`“${p.name}” is used in ${used.join(', ')} — take it out there first.`);
      if (project.parts.length < 2) throw new Error('It is the only part of the project.');
      await project.remove(p.id, false);
      return ok(`“${p.name}” deleted from the project.`);
    },

    // ---------------------------------------------------------------- data the server writes as files
    export_data: async ({ format }) => {
      const ws = state.workspace;
      if (format === '3mf') {
        if (ws === 'model') {
          const b = modeler.result?.body;
          if (!b) throw new Error('The model has no solid yet.');
          return { text: 'ok', data: { title: project.current?.name || 'part', groups: colouredGroups(b, { base: modeler.part.color || '#d9dee6', paint: modeler.part.paint, name: project.current?.name || 'part' }) } };
        }
        if (ws === 'assembly') {
          await assembly.refresh();
          const groups = assembly.doc.instances.flatMap((it) => {
            const b = assembly.bodyOf(it)?.body;
            if (!b) return [];
            const look = assembly.lookOf(it);
            return colouredGroups(b, { base: look.colour !== null && look.colour !== undefined ? hex(look.colour) : '#d9dee6', paint: look.paint, matrix: it.matrix,
              name: `${assembly.partName(it.part)} ${it.id}`, fileColours: !look.ownColour });
          });
          return { text: 'ok', data: { title: project.current?.name || 'assembly', groups } };
        }
        throw new Error('3MF is for a 3D model or an assembly.');
      }
      if (format === 'bom') {
        need('assembly', 'The BOM is of an assembly');
        const rows = assembly.bomFlat(), shops = [...new Set(rows.flatMap((r) => Object.keys(r.order || {})))];
        return { text: 'ok', data: { name: project.current?.name || 'assembly', rows, shops } };
      }
      if (format === 'dxf' && ws === 'sheet') { // a drawing sheet: the paper 1:1, its views, real dimensions
        await sheet.ensure();
        return { text: 'ok', data: { name: project.current?.name || 'drawing', sheet: sheet.dxfData() } };
      }
      if (format === 'dxf') {
        const ed = D(), shown = { ...ed.d, entities: ed.d.entities.filter((e) => ed.shown(e)) };
        if (!shown.entities.length) throw new Error('Nothing on the shown layers.');
        return { text: 'ok', data: { name: (ed.d.source || project.current?.name || 'drawing').replace(/\.[^.]+$/, ''), drawing: shown } };
      }
      if (format === 'pdf' && state.workspace === 'assembly') { // an assembly: its drawing set, one PDF
        const set = await drawingSet(project.active);
        return { text: 'ok', data: { name: `${project.current?.name || 'assembly'} — drawings`, svgs: set.svgs, pages: set.pages } };
      }
      if (format === 'pdf') { // a drawing sheet: as it is drawn
        need('sheet', 'A drawing sheet');
        await sheet.ensure();
        return { text: 'ok', data: { name: project.current?.name || 'drawing', svg: sheet.svg(true) } };
      }
      throw new Error('format: 3mf, bom, dxf (a 2D drawing or a drawing sheet) or pdf (a drawing sheet).');
    },
  };
}
