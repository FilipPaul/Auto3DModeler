// The tools coloured by what they do, the same in the sketch, the 3D model and the assembly: make (blue), modify
// (amber), copy (purple), details (teal), define / join (green), look and check (grey).

const GROUPS = {
  make: ['rect', 'line', 'circle', 'spline', 'arc', 'outline', 'sketch', 'extrude', 'revolve', 'loft', 'sweep', 'solidFile', 'insert'],
  modify: ['round', 'trim', 'extend', 'construction', 'fillet', 'chamfer', 'shell', 'draft'],
  copy: ['mirror', 'offset', 'pattern'],
  detail: ['rib', 'hole', 'decal', 'fasteners'],
  define: ['relate', 'dim', 'autodim', 'joint'],
  inspect: ['paint', 'measure', 'section', 'planes', 'clashes'],
};
const OF = Object.fromEntries(Object.entries(GROUPS).flatMap(([g, as]) => as.map((a) => [a, g])));

/** The class colouring a toolbar button by its group ('' for the others). */
export const toolGroup = (a) => (OF[a] ? `g-${OF[a]}` : '');
