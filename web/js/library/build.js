// 📚 Library parts -> 3D model steps. A library item (library/*.json, or the user's in data/library/) describes a real
// part (a standard screw, a bearing, a SMC cylinder, a SICK sensor…): its sizes as a table, an optional second choice
// (a length), the names it is ordered by, and its shape as a few simple steps whose numbers may be formulas of the
// chosen size's values:
//   {"revolve": [[r, z], …]}                       a half-section (r from the axis, z up), turned round the Z axis
//   {"extrude": {shape}, "z": z0, "h": height, "op": "add" | "cut", "holes": [{shape}…], "at": [[x, y]…], "plane": "XY" | "XZ" | "YZ"}
//   "color": "#rrggbb" on a step: the faces it makes in that colour (a rod, a connector); the item's "color" is the rest
//   shapes: {"circle": {"d", "x", "y"}}, {"rect": {"w", "h", "x", "y", "r"}} (x, y: its middle), {"hex": {"s", "x", "y"}}
//   (s across the flats), {"polygon": {"n", "d", "x", "y"}} (n corners on Ø d), {"polyline": [[x, y]…]}
// A step with "when": a formula is made only where that formula is above 0 (e.g. "top - 10").
// A number may be a formula such as "L + k" or "dk / 2" (+ - * / ^, ( ), min, max, sqrt, sin, cos, tan, pi), of the
// size's values, `L` (the second choice) and the item's `vars`.
import { sketchFromShapes } from '../modeler/agent_model.js';
import { stepsHash } from '../parts.js';

// ------------------------------------------------------------------ formulas
const FN = { min: Math.min, max: Math.max, sqrt: Math.sqrt, sin: Math.sin, cos: Math.cos, tan: Math.tan, abs: Math.abs, round: Math.round, floor: Math.floor, ceil: Math.ceil };

/** A formula of the values in `vars` -> a number (a number stays itself). Throws on anything else. */
export function evaluate(expr, vars = {}) {
  if (typeof expr === 'number') return expr;
  if (typeof expr !== 'string') throw new Error(`Not a number: ${JSON.stringify(expr)}`);
  const src = expr, toks = src.match(/\d+\.?\d*(?:e[+-]?\d+)?|\.\d+|[A-Za-z_]\w*|[-+*/^(),]/g) || [];
  if (toks.join('') !== src.replace(/\s+/g, '')) throw new Error(`Cannot read the formula “${src}”.`);
  let i = 0;
  const peek = () => toks[i], next = () => toks[i++];
  const primary = () => {
    const tk = next();
    if (tk === undefined) throw new Error(`The formula “${src}” ends too soon.`);
    if (tk === '(') { const v = sum(); if (next() !== ')') throw new Error(`A “)” is missing in “${src}”.`); return v; }
    if (tk === '-') return -power();
    if (tk === '+') return power();
    if (/^[\d.]/.test(tk)) return parseFloat(tk);
    if (tk === 'pi') return Math.PI;
    if (FN[tk] && peek() === '(') {
      next();
      const args = [sum()];
      while (peek() === ',') { next(); args.push(sum()); }
      if (next() !== ')') throw new Error(`A “)” is missing in “${src}”.`);
      return FN[tk](...args);
    }
    if (tk in vars) return evaluate(vars[tk], vars);
    throw new Error(`“${tk}” is not known in “${src}”.`);
  };
  const power = () => { const b = primary(); if (peek() === '^') { next(); return b ** power(); } return b; };
  const product = () => {
    let v = power();
    while (peek() === '*' || peek() === '/') v = next() === '*' ? v * power() : v / power();
    return v;
  };
  const sum = () => {
    let v = product();
    while (peek() === '+' || peek() === '-') v = next() === '+' ? v + product() : v - product();
    return v;
  };
  const v = sum();
  if (i !== toks.length) throw new Error(`Cannot read the formula “${src}”.`);
  if (!Number.isFinite(v)) throw new Error(`The formula “${src}” gives no number.`);
  return v;
}

/** `text` with {name} replaced by the values (numbers rounded); {name:03} pads a whole number with zeros to 3 digits
 *  (a part number such as igus E2.15.10.028.0). */
export const fill = (text, vars) => String(text || '').replace(/\{(\w+)(?::0(\d))?\}/g, (_, k, pad) => {
  const v = vars[k];
  if (v === undefined) return '';
  const s = typeof v === 'number' ? String(+v.toFixed(3)) : String(v);
  return pad ? s.padStart(+pad, '0') : s;
});

// ------------------------------------------------------------------ choices
/** The sizes of an item: [{key, …values}] in their order. */
export const sizesOf = (item) => Object.entries(item.sizes || { '': {} }).map(([key, v]) => ({ key, ...v }));

/** The second choice (a length) for a size: {name, values, unit} or null. */
export function lengthsOf(item, sizeKey) {
  const l = item.lengths;
  if (!l) return null;
  const values = Array.isArray(l.values) ? l.values : (l.values || {})[sizeKey] || l.default || [];
  return values.length ? { name: l.name || 'Length', values, unit: l.unit || 'mm', param: l.param || 'L' } : null;
}

/** All the values for a choice: the item's vars, the size's values, the length. */
export function varsOf(item, sizeKey, length) {
  const size = (item.sizes || {})[sizeKey] || {};
  const vars = { ...(item.vars || {}), ...size, size: sizeKey };
  const l = lengthsOf(item, sizeKey);
  if (l) vars[l.param] = length ?? l.values[0];
  return vars;
}

// ------------------------------------------------------------------ the steps
const num = (v, vars) => +evaluate(v, vars).toFixed(4);

function shapesOf(spec, vars, at = [[0, 0]]) {
  const out = [];
  for (const [ax, ay] of at.map((p) => p.map((v) => num(v, vars)))) {
    if (spec.circle) out.push({ circle: { x: ax + num(spec.circle.x ?? 0, vars), y: ay + num(spec.circle.y ?? 0, vars), d: num(spec.circle.d, vars) } });
    else if (spec.rect) {
      const w = num(spec.rect.w, vars), h = num(spec.rect.h, vars), r = num(spec.rect.r ?? 0, vars);
      out.push({ rect: { x: ax + num(spec.rect.x ?? 0, vars) - w / 2, y: ay + num(spec.rect.y ?? 0, vars) - h / 2, w, h, r } });
    } else if (spec.hex || spec.polygon) {
      const n = spec.hex ? 6 : Math.round(num(spec.polygon.n, vars)), R = spec.hex ? num(spec.hex.s, vars) / Math.sqrt(3) : num(spec.polygon.d, vars) / 2;
      const p = spec.hex || spec.polygon, cx = ax + num(p.x ?? 0, vars), cy = ay + num(p.y ?? 0, vars), a0 = num(p.turn ?? 0, vars) * Math.PI / 180;
      out.push({ polyline: { points: Array.from({ length: n }, (_, i) => [+(cx + R * Math.cos(a0 + (2 * Math.PI * i) / n)).toFixed(4), +(cy + R * Math.sin(a0 + (2 * Math.PI * i) / n)).toFixed(4)]) } });
    } else if (spec.polyline) out.push({ polyline: { points: spec.polyline.map(([x, y]) => [ax + num(x, vars), ay + num(y, vars)]) } });
    else throw new Error(`A shape is circle, rect, hex, polygon or polyline: ${JSON.stringify(spec)}`);
  }
  return out;
}

/** The key of a choice among an item's real models (the maker's STEP files the user attached). */
export const modelKey = (sizeKey, length) => `${sizeKey}|${length ?? ''}`;

/** An item and the choice (size, length) -> {name, data (the 3D model part: its steps and the library facts)}.
 *  A real model (the maker's STEP) attached to that choice is used instead of the drawn one. */
export function buildPart(item, sizeKey = sizesOf(item)[0]?.key, length) {
  const vars = varsOf(item, sizeKey, length), features = [], paint = [];
  let n = 0;
  const id = () => `F${++n}`;
  const second = lengthsOf(item, sizeKey), chosen = second ? vars[second.param] : undefined; // (the second choice: a length, a stroke, a bend radius R)
  const real = item.models?.[modelKey(sizeKey, chosen)];
  if (real) features.push({ id: id(), type: 'solid', name: real.file.replace(/\.[^.]+$/, ''), blob: real.blob, file: real.file, op: 'add' });
  // a part saved from a 3D model: its own steps, as they are
  else if (item.features?.length) features.push(...structuredClone(item.features));
  for (const step of real ? [] : item.shape || []) {
    if (step.when !== undefined && !(evaluate(step.when, vars) > 0)) continue; // a step only some sizes have (its formula > 0)
    if (step.revolve) {
      const pts = step.revolve.map(([r, z]) => [num(r, vars), num(z, vars)]);
      const sk = id();
      features.push({ id: sk, type: 'sketch', name: `Sketch ${n}`, plane: { datum: 'XZ' }, ...sketchFromShapes([{ polyline: { points: pts } }], true) });
      features.push({ id: id(), type: 'revolve', name: `Revolve ${n}`, sketch: sk, axis: 'y', angle: 360, op: step.op === 'cut' ? 'cut' : 'add' });
      if (step.color) paint.push({ feature: `F${n}`, color: step.color });
      continue;
    }
    if (step.extrude) {
      const at = step.at || [[0, 0]], shapes = [...shapesOf(step.extrude, vars, at), ...(step.holes || []).flatMap((hs) => shapesOf(hs, vars, at))];
      const h = num(step.h, vars), z = num(step.z ?? 0, vars), sk = id();
      features.push({ id: sk, type: 'sketch', name: `Sketch ${n}`, plane: { datum: step.plane || 'XY', ...(z ? { offset: z } : {}) }, ...sketchFromShapes(shapes, true) });
      features.push({ id: id(), type: 'extrude', name: `Extrude ${n}`, sketch: sk, op: step.op === 'cut' ? 'cut' : 'add', d: Math.abs(h), through: false, symmetric: false,
        // h goes along the plane's normal (+z) when above 0, a cut too (the kernel cuts against the normal unless flipped)
        flip: step.op === 'cut' ? h > 0 : h < 0 });
      if (step.color) paint.push({ feature: `F${n}`, color: step.color });
      continue;
    }
    throw new Error(`A step is revolve or extrude: ${JSON.stringify(step).slice(0, 80)}`);
  }
  const order = {};
  for (const [k, v] of Object.entries({ ...(item.order || {}), ...(vars.order || {}) })) order[k] = fill(v, vars);
  const name = fill(item.title || item.name, vars);
  const pn = fill(vars.pn ?? item.pn ?? '', vars);
  // the maker's pages for this choice: its datasheet, its own 3D model (STEP, to download there), its product page
  const links = Object.fromEntries(['datasheet', 'cad', 'page'].map((k) => [k, fill(item[k], vars)]).filter(([, v]) => /^https:\/\//.test(v)));
  return {
    name,
    data: {
      features,
      ...(item.color && !real ? { color: item.color } : {}),
      ...(!real && (paint.length || item.paint?.length) ? { paint: [...paint, ...structuredClone(item.paint || [])] } : {}),
      material: item.material || undefined,
      library: { id: item.id, item: item.name, category: item.category, size: sizeKey, ...(chosen !== undefined ? { length: chosen } : {}),
        maker: item.maker || '', pn, description: fill(item.description || item.name, vars), order, approx: !!item.approx && !real, standard: item.standard || '',
        ...(item.description_cs ? { description_cs: fill(item.description_cs, vars) } : {}), ...(item.accuracy ? { accuracy: item.accuracy } : {}),
        ...(Object.keys(links).length ? { links } : {}),
        ...(real ? { real: real.file } : {}), steps: stepsHash(features) },
    },
  };
}

// The shops a part is looked up at — their search pages (always there, no guessed order codes), each checked to find
// a part number. Mechanical parts go to the mechanical shops first, electronic ones to the electronic; the maker's
// own shop (SMC, SICK, SKF) first of all.
const SHOPS = {
  smc: { shop: 'SMC', url: 'https://www.smc.eu/cs-cz/search?searchTerm={q}' },
  sick: { shop: 'SICK', url: 'https://www.sick.com/cz/cs/search?text={q}' },
  skf: { shop: 'SKF', url: 'https://www.skf.com/group/search-results?q={q}' },
  ingun: { shop: 'INGUN', url: 'https://ingun.com/en/search?search={q}' },
  misumi: { shop: 'MISUMI', url: 'https://cz.misumi-ec.com/vona2/result/?Keyword={q}' },
  rs: { shop: 'RS Components', url: 'https://cz.rs-online.com/web/c/?searchTerm={q}' },
  conrad: { shop: 'Conrad', url: 'https://www.conrad.cz/cs/search.html?search={q}' },
  tme: { shop: 'TME', url: 'https://www.tme.eu/cz/katalog/?search={q}' },
  mouser: { shop: 'Mouser', url: 'https://cz.mouser.com/c/?q={q}' },
  farnell: { shop: 'Farnell', url: 'https://cz.farnell.com/search?st={q}' },
  gme: { shop: 'GM Electronic', url: 'https://www.gme.cz/hledani?search={q}' },
};
const MAKER_SHOP = { SMC: 'smc', SICK: 'sick', SKF: 'skf', INGUN: 'ingun' };
const MECHANICAL = ['misumi', 'rs', 'conrad', 'tme'], ELECTRONIC = ['mouser', 'farnell', 'tme', 'gme', 'rs', 'conrad'];

/** The shops where a part number is looked up: [{shop, url}] — lib: the part's library facts (its category, maker). */
export function shopLinks(pn, lib = {}) {
  if (!pn) return [];
  const q = encodeURIComponent(pn), top = String(lib.category || '').split(' / ')[0];
  const electronic = ['Panel', 'Sensors', 'Test probes', 'Receptacles', 'Cable clips', 'Cable ties'].includes(top) && lib.maker !== 'SMC';
  const keys = [...new Set([MAKER_SHOP[lib.maker], ...(electronic ? ELECTRONIC : MECHANICAL)].filter(Boolean))];
  return keys.map((k) => ({ shop: SHOPS[k].shop, url: SHOPS[k].url.replace('{q}', q) }));
}
