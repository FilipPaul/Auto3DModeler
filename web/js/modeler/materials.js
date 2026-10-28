// The materials a part can be of: its density (g/cm³ — the mass) and the colour it is shown in when it has none of its
// own. Grouped as they are chosen: printed, engineering plastics, metals, other. (auto3d/modeler/materials.py has the
// same densities for the server.)

export const MATERIAL_GROUPS = [
  ['3D printing', [
    ['PLA', 1.24, '#d6dbe3'], ['PETG', 1.27, '#9cc7d6'], ['ABS', 1.04, '#ece6d6'], ['ASA', 1.07, '#dcdcd4'],
    ['TPU', 1.21, '#3d3d3d'], ['PA', 1.14, '#ece4d2'], ['PA-CF', 1.20, '#2e2e2e'], ['PC', 1.20, '#cfd8dc'], ['PP', 0.90, '#f0eee4']]],
  ['Engineering plastics', [
    ['POM', 1.41, '#f4f4ef'], ['PE-HD', 0.95, '#f2f2ea'], ['PA6-GF30', 1.36, '#2b2b2b'], ['PTFE', 2.20, '#f8f8f6'],
    ['PEEK', 1.32, '#c9ab72'], ['PMMA', 1.18, '#cfe7ef'], ['PVC', 1.38, '#9a9fa4']]],
  ['Metals', [
    ['aluminium', 2.70, '#c3c8cd'], ['aluminium 7075', 2.81, '#b4bac1'], ['steel', 7.85, '#8b9097'], ['steel C45', 7.85, '#7f858c'],
    ['stainless steel', 7.93, '#bcc1c6'], ['stainless steel 316', 8.00, '#c4c9ce'], ['tool steel', 7.80, '#6f747a'],
    ['cast iron', 7.20, '#5e6063'], ['brass', 8.50, '#c9a64b'], ['bronze', 8.80, '#a2753b'], ['copper', 8.96, '#b87333'],
    ['titanium', 4.43, '#8f9095'], ['zinc die-cast', 6.60, '#a9aeb4'], ['magnesium', 1.80, '#b5babf']]],
  ['Other', [
    ['rubber (EPDM)', 1.15, '#2a2a2a'], ['silicone', 1.15, '#e8e2d6'], ['plywood', 0.60, '#c9a46c'], ['MDF', 0.75, '#b58c5e'],
    ['glass', 2.50, '#d6ebf1'], ['carbon fibre (CFRP)', 1.60, '#262626'], ['FR4 (PCB)', 1.85, '#2f6b3a']]],
];

/** name -> density (g/cm³). */
export const MATERIALS = Object.fromEntries(MATERIAL_GROUPS.flatMap(([, ms]) => ms.map(([n, rho]) => [n, rho])));
/** name -> the colour a part of it is shown in (when it has no colour of its own). */
export const MATERIAL_COLOR = Object.fromEntries(MATERIAL_GROUPS.flatMap(([, ms]) => ms.map(([n, , c]) => [n, c])));

// how a material's surface looks: metals metallic (each as polished or rough as it usually is), the rest not
const FINISH = {
  aluminium: [0.9, 0.38], 'aluminium 7075': [0.9, 0.36], steel: [0.85, 0.42], 'steel C45': [0.85, 0.45], 'stainless steel': [0.95, 0.24],
  'stainless steel 316': [0.95, 0.22], 'tool steel': [0.85, 0.35], 'cast iron': [0.7, 0.62], brass: [0.95, 0.28], bronze: [0.9, 0.36],
  copper: [0.95, 0.3], titanium: [0.85, 0.4], 'zinc die-cast': [0.8, 0.45], magnesium: [0.75, 0.5],
  glass: [0, 0.06], PMMA: [0, 0.12], PC: [0, 0.25], 'rubber (EPDM)': [0, 0.9], silicone: [0, 0.8], TPU: [0, 0.8], plywood: [0, 0.8], MDF: [0, 0.85],
};
/** {metalness, roughness} of a material's surface (not chosen: a plain plastic). */
export const finishOf = (material) => { const f = FINISH[material]; return f ? { metalness: f[0], roughness: f[1] } : { metalness: 0.05, roughness: 0.55 }; };

/** A part's colour as shown: its own, else its material's (when one was chosen), else none (the default). */
export const lookColor = (part) => part?.color || (part?.material && MATERIAL_COLOR[part.material]) || null;
