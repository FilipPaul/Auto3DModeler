// More of the app for the AI (tool calls from the app's MCP server, applied like a user edit): the 2D drawing workspace
// (layers, shapes found by filters, sizes, use as a sketch / quick part), joints changed or removed, measuring between
// faces, the view (section, explode, sizes) for its screenshots, parts renamed or deleted, and the data the server
// writes as files (a coloured 3MF, the BOM as CSV, a drawing as DXF).
import * as THREE from 'three';
import { paintedFaces } from './modeler/paint.js';
import { sectionMiddle } from './modeler/sectionbar.js';

const b64 = (s, T) => { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); };
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
 *  state, disabled, where, el}] — where: bar (the top bar), tools (the workspace's toolbar), panel (its side panels). */
export function guiControls(where = 'all') {
  const out = [], seen = new Set();
  const shown = (el) => { if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const area = (el) => (el.closest('.topbar, header') ? 'bar' : el.closest('.m-cmdbar, .cmdbar, [class*=toolbar]') ? 'tools' : 'panel');
  for (const el of document.querySelectorAll('button, input, select, [data-jname], .chip, .as-list .mt-item')) {
    if (seen.has(el) || el.closest('#aiDrawer, #tab-ai, .ai-drawer') || !shown(el)) continue;
    if (el.tagName === 'INPUT' && el.type === 'hidden') continue;
    seen.add(el);
    const lab = el.closest('label'), row = el.closest('[data-jrow], .as-dof, .field');
    const isPart = el.matches('.mt-item');
    let label = (isPart ? `${el.querySelector('.mt-name')?.textContent || ''} ${el.querySelector('.mt-what')?.textContent || ''}`
      : el.tagName === 'INPUT' || el.tagName === 'SELECT' ? (lab?.textContent || el.placeholder || el.dataset.k || '') : el.textContent || el.title || '').replace(/\s+/g, ' ').trim();
    if ((el.tagName === 'INPUT' || el.tagName === 'SELECT') && row && row !== lab) label = `${(row.querySelector('label, .as-jt')?.textContent || '').replace(/\s+/g, ' ').trim()} › ${label}`.trim();
    if (!label) label = el.getAttribute('aria-label') || el.title || el.className || el.tagName.toLowerCase();
    const kind = isPart ? 'part' : el.tagName === 'SELECT' ? 'choice' : el.tagName === 'INPUT' ? (el.type === 'range' ? 'slider' : el.type === 'checkbox' ? 'checkbox' : 'box') : el.dataset.jname ? 'name' : 'button';
    const a = area(el);
    out.push({ n: out.length + 1, kind, label: label.slice(0, 90), title: (el.title || '').slice(0, 120) || undefined,
      state: kind === 'checkbox' ? (el.checked ? 'on' : 'off') : ['button', 'name', 'part'].includes(kind) ? (el.classList.contains('on') ? 'on' : undefined) : String(el.value),
      ...(kind === 'slider' ? { min: +el.min, max: +el.max } : {}), disabled: !!el.disabled || undefined, where: a, el });
  }
  return where === 'all' ? out : out.filter((c) => c.where === where); // (n: one numbering for all)
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
      const list = guiControls(where);
      return ok({ workspace: state.workspace, controls: list.map(({ el, ...c }) => c),
        toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent.trim()).slice(-3) });
    },
    gui_action: async ({ control, click, value }) => {
      const list = guiControls('all'), key = String(control ?? '').trim().toLowerCase();
      const c = list.find((x) => String(x.n) === key) || list.find((x) => x.label.toLowerCase() === key) || list.find((x) => x.label.toLowerCase().includes(key));
      if (!c) throw new Error(`No control “${control}” on screen — gui_state lists them (n or label).`);
      if (c.disabled) throw new Error(`“${c.label}” is greyed out (disabled)${c.title ? `: ${c.title}` : ''}.`);
      const el = c.el;
      if (value !== undefined && value !== null && /^(range|number|text|color)$/.test(el.type || '') || el.tagName === 'SELECT') {
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (click !== false) {
        el.dispatchEvent(new MouseEvent('mouseenter'));
        el.click();
      }
      await new Promise((r) => setTimeout(r, 400));
      return ok({ done: `${c.kind} “${c.label}”${value !== undefined ? ` = ${value}` : ' clicked'}`, workspace: state.workspace,
        toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent.trim()).slice(-3) });
    },

    // ---------------------------------------------------------------- drawing sheets (📄)
    sheet_open: async ({ part } = {}) => {
      const p = part ? project.parts.find((q) => q.id === part || q.name === part) : project.current;
      if (!p) throw new Error(`No part ${part} — see list_parts.`);
      if (p.kind === 'sheet') { await project.switchTo(p.id); } else {
        if (p.kind !== 'model') throw new Error(`${p.name} is not a 3D model — a drawing sheet is of a 3D model part.`);
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
    sheet_edit: async ({ preset, view_presets, paper, views, remove = [], restore, add = [], move = {} } = {}) => {
      need('sheet', 'This is for a drawing sheet (📄) — sheet_open opens one');
      const ed = sheet, done = [];
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
      const added = [].concat(add).map((spec) => ed.addFor(spec));
      if (added.length) done.push(`added ${added.join(', ')}`);
      ed.commit();
      return ok({ done: done.join('; ') || 'nothing', ...ed.summary() });
    },

    // ---------------------------------------------------------------- joints and measuring (assembly)
    edit_joint: async ({ id, gap, distance, lock_rotation, angle, flip, locked, name }) => {
      need('assembly', 'Joints are in an assembly');
      const a = assembly, m = (a.doc.mates || []).find((x) => x.id === id);
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
      if (!m) throw new Error(`No joint ${id} — get_assembly lists the joints.`);
      if (m.locked) throw new Error(`Joint ${id} is locked 🔒 — edit_joint {id, locked: false} first (only when the user wants it).`);
      a.doc.mates = a.doc.mates.filter((x) => x !== m);
      a.applyMates(); // (its other joints hold it again)
      a.commit();
      return ok(`Joint ${id} removed — ${m.move} stays where it is (held by its other joints, if any).`);
    },
    measure: async ({ a: A, b: B }) => {
      need('assembly', 'Measuring between parts is in an assembly (in a 3D model: get_model / find_refs give the sizes)');
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
      return ok(out);
    },

    // ---------------------------------------------------------------- the view (then get_screenshot)
    set_view: async ({ view, section, explode, sizes }) => {
      const ws = state.workspace;
      if (ws !== 'model' && ws !== 'assembly') throw new Error('The view is set in a 3D model or an assembly.');
      const host = ws === 'model' ? modeler : assembly, v = host.view;
      if (view) { if (!['iso', 'top', 'front', 'right'].includes(view)) throw new Error('view: iso, top, front or right.'); v.setView(view); }
      if (section !== undefined) {
        if (section === null || section === false) { if (host.section) host.toggleSection(); } else {
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
            const b = assembly.bodies[it.part]?.body;
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
      throw new Error('format: 3mf, bom, dxf or pdf (a drawing sheet).');
    },
  };
}
