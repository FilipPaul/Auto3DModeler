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

export function moreHandlers({ state, project, modeler, assembly, drawing2d, t2 }) {
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
    drawing_layers: async ({ show = [], hide = [], only = null }) => {
      const ed = D();
      const names = new Set(ed.d.layers.map((l) => l.name)), bad = [...show, ...hide, ...(only || [])].filter((n) => !names.has(n));
      if (bad.length) throw new Error(`No layer ${bad.join(', ')}. Layers: ${[...names].join(', ')}.`);
      for (const l of ed.d.layers) {
        if (only) l.visible = only.includes(l.name);
        if (show.includes(l.name)) l.visible = true;
        if (hide.includes(l.name)) l.visible = false;
      }
      ed.commit();
      return ok(`Shown: ${ed.d.layers.filter((l) => l.visible !== false).map((l) => l.name).join(', ') || 'none'}.`);
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

    // ---------------------------------------------------------------- joints and measuring (assembly)
    edit_joint: async ({ id, gap, distance, lock_rotation, angle, flip, locked }) => {
      need('assembly', 'Joints are in an assembly');
      const a = assembly, m = (a.doc.mates || []).find((x) => x.id === id);
      if (!m) throw new Error(`No joint ${id} — get_assembly lists the joints.`);
      if (gap !== undefined) { m.gap = +gap; if (m.type === 'touch' && +gap) m.type = 'gap'; }
      if (distance !== undefined) {
        if (m.type !== 'axis') throw new Error('distance is for a concentric (axis) joint; flat joints take gap.');
        if (distance === null) { delete m.dist; delete m.side; } else { if (!m.side) m.side = 1; m.dist = +distance; }
      }
      if (lock_rotation !== undefined) { if (lock_rotation) m.angle = Math.round(a.spinNow(m)); else delete m.angle; }
      if (angle !== undefined) { if (m.type === 'angle') m.value = Math.max(0, Math.min(180, +angle)); else m.angle = +angle; }
      if (flip) m.flip = !m.flip;
      if (locked !== undefined) m.locked = !!locked;
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
      throw new Error('format: 3mf, bom or dxf.');
    },
  };
}
