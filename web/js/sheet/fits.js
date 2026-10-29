// ISO 286 fits for the drawing sheet — the table of auto3d/modeler/fits.py (holes H6 … H9, shafts f7 … p6) and H11 /
// h7 the sheet offers too, for nominal sizes up to 120 mm.

const RANGES = [3, 6, 10, 18, 30, 50, 80, 120]; // the upper ends of the size ranges (mm)
const TABLE = { // (upper, lower) deviations in µm, one pair per range
  H6: [[6, 0], [8, 0], [9, 0], [11, 0], [13, 0], [16, 0], [19, 0], [22, 0]],
  H7: [[10, 0], [12, 0], [15, 0], [18, 0], [21, 0], [25, 0], [30, 0], [35, 0]],
  H8: [[14, 0], [18, 0], [22, 0], [27, 0], [33, 0], [39, 0], [46, 0], [54, 0]],
  H9: [[25, 0], [30, 0], [36, 0], [43, 0], [52, 0], [62, 0], [74, 0], [87, 0]],
  H11: [[60, 0], [75, 0], [90, 0], [110, 0], [130, 0], [160, 0], [190, 0], [220, 0]],
  f7: [[-6, -16], [-10, -22], [-13, -28], [-16, -34], [-20, -41], [-25, -50], [-30, -60], [-36, -71]],
  g6: [[-2, -8], [-4, -12], [-5, -14], [-6, -17], [-7, -20], [-9, -25], [-10, -29], [-12, -34]],
  h6: [[0, -6], [0, -8], [0, -9], [0, -11], [0, -13], [0, -16], [0, -19], [0, -22]],
  h7: [[0, -10], [0, -12], [0, -15], [0, -18], [0, -21], [0, -25], [0, -30], [0, -35]],
  k6: [[6, 0], [9, 1], [10, 1], [12, 1], [15, 2], [18, 2], [21, 2], [25, 3]],
  m6: [[8, 2], [12, 4], [15, 6], [18, 7], [21, 8], [25, 9], [30, 11], [35, 13]],
  p6: [[12, 6], [20, 12], [24, 15], [29, 18], [35, 22], [42, 26], [51, 32], [59, 37]],
};
export const HOLE_FITS = ['H6', 'H7', 'H8', 'H9', 'H11'];
export const SHAFT_FITS = ['f7', 'g6', 'h6', 'h7', 'k6', 'm6', 'p6'];
/** The fits the sheet offers on a Ø dimension, most used first (a hole's, then a shaft's). */
export const FIT_LIST = { hole: ['H7', 'H8', 'H9', 'H11'], shaft: ['h6', 'h7', 'g6', 'f7', 'k6', 'm6', 'p6'] };

/** The (upper, lower) deviation in mm of size d in class fit, or null (unknown class / size). */
export function deviation(fit, d) {
  const rows = TABLE[fit];
  if (!rows || !(d > 0 && d <= RANGES[RANGES.length - 1])) return null;
  const [up, lo] = rows[RANGES.findIndex((top) => d <= top)];
  return [up / 1000, lo / 1000];
}

/** "+0.015 / 0" — a class's deviations at size d as written on a drawing ('' when out of the table). */
export function deviationText(fit, d) {
  const dev = deviation(fit, d);
  const s = (v) => (v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(3).replace(/0+$/, '')}`);
  return dev ? `${s(dev[0])} / ${s(dev[1])}` : '';
}
