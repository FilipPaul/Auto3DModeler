// Standard holes for metric screws — the Hole panel's Type and Size fill a hole's sizes from this table (as
// auto3d/modeler/holes.py SIZES: clearance ISO 273 medium, counterbore for an ISO 4762 socket head, 90° countersink
// for an ISO 10642 flat head, tapped at the ISO 2306 tap drill).

// ISO metric coarse threads -> their tap drill
export const THREADS = { M2: 1.6, 'M2.5': 2.05, M3: 2.5, M4: 3.3, M5: 4.2, M6: 5, M8: 6.8, M10: 8.5, M12: 10.2, M16: 14, M20: 17.5 };

export const HOLE_SIZES = {
  "M2": {"clearance": 2.4, "cbore_d": 4.3, "cbore_depth": 2.4, "csk_d": 4.4},
  "M2.5": {"clearance": 2.9, "cbore_d": 5, "cbore_depth": 2.9, "csk_d": 5.5},
  "M3": {"clearance": 3.4, "cbore_d": 6.5, "cbore_depth": 3.4, "csk_d": 6.7},
  "M4": {"clearance": 4.5, "cbore_d": 8, "cbore_depth": 4.4, "csk_d": 9},
  "M5": {"clearance": 5.5, "cbore_d": 10, "cbore_depth": 5.4, "csk_d": 11.2},
  "M6": {"clearance": 6.6, "cbore_d": 11, "cbore_depth": 6.4, "csk_d": 13.4},
  "M8": {"clearance": 9, "cbore_d": 15, "cbore_depth": 8.6, "csk_d": 17.9},
  "M10": {"clearance": 11, "cbore_d": 18, "cbore_depth": 10.6, "csk_d": 22.4},
  "M12": {"clearance": 13.5, "cbore_d": 20, "cbore_depth": 12.6, "csk_d": 26.9},
  "M16": {"clearance": 17.5, "cbore_d": 26, "cbore_depth": 16.6, "csk_d": 33.6},
  "M20": {"clearance": 22, "cbore_d": 33, "cbore_depth": 20.6, "csk_d": 40.3},
};

// the Type choice: [value, label] ('' a simple hole, sized by its Ø; 'd_flat' a D hole for a shaft with a flat — no
// screw size)
export const HOLE_TYPES = [['', 'Simple'], ['clearance', 'Clearance hole'], ['counterbore', '⌴ Counterbore'], ['countersink', '⌵ Countersink'], ['tapped', 'Tapped'], ['d_flat', 'D (flat)']];

// D-shafts (as holes.py D_FLATS): Ø -> the size across the flat
export const D_FLATS = { 3: 2.5, 4: 3.5, 5: 4.5, 6: 5.5, 8: 7.5 };

/** A D hole's size across the flat for Ø d: a common D-shaft's, else 0.9 × d (the flat 0.8 × r from the centre). */
export function dFlat(d) { return D_FLATS[d] ?? +(0.9 * d).toFixed(2); }

/** The fields of a standard hole (as holes.py preset): {d, head?, head_d?, head_depth?, head_angle?, thread?}. */
export function holePreset(kind, size) {
  const s = HOLE_SIZES[size];
  if (!s || !HOLE_TYPES.some(([v]) => v && v === kind)) return null;
  if (kind === 'tapped') return { d: THREADS[size], thread: size };
  return { d: s.clearance, ...(kind === 'counterbore' ? { head: 'cbore', head_d: s.cbore_d, head_depth: s.cbore_depth } : {}),
    ...(kind === 'countersink' ? { head: 'csk', head_d: s.csk_d, head_angle: 90 } : {}) };
}

/** A hole step's type — a step made before the Type choice: from its thread / head. */
export function holeType(f) {
  if (f.hole_type) return f.hole_type;
  return f.thread ? 'tapped' : f.head === 'cbore' ? 'counterbore' : f.head === 'csk' ? 'countersink' : '';
}

/** Set a hole step's type and size: the table's sizes written on it (its earlier head / thread / sizes dropped);
 *  '' a simple hole (its Ø kept). */
export function setHoleStandard(f, kind, size) {
  for (const k of ['head', 'head_d', 'head_depth', 'head_angle', 'thread', 'hole_type', 'standard', 'flat', 'flat_angle']) delete f[k];
  if (kind === 'd_flat') return Object.assign(f, { hole_type: kind, flat: dFlat(f.d) }); // (its Ø kept)
  const p = kind && holePreset(kind, size);
  if (p) Object.assign(f, { hole_type: kind, standard: size }, p);
  return f;
}
