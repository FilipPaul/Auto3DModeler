// Quick ray picking on big parts: a bounding volume tree over a mesh's triangles (built once per geometry, on the
// first ray), so a ray tests only the few triangles near it — not all of them (a 44 MB board: 2 million). The hits
// are the same as three.js' own Mesh.raycast gives (distance, point, face, faceIndex, normal), in the same order.
import * as THREE from 'three';

const LEAF = 8; // triangles in a leaf
const TREES = new WeakMap(); // positions -> their tree (a shown part's positions do not change; geometries may share them)

/** A tree over a non-indexed geometry's triangles (9 floats each) -> {bounds: 6 floats a node (its box), links: 2 a
 *  node — a leaf: [its first in order, count]; an inner node: [its right child, 0] (its left child: the next node),
 *  order: the triangles, a leaf's side by side}. */
function build(pos) {
  const n = pos.length / 9, order = new Uint32Array(n), cen = new Float32Array(n * 3), box = new Float32Array(n * 6);
  for (let t = 0; t < n; t++) {
    order[t] = t;
    const o = t * 9;
    for (let k = 0; k < 3; k++) {
      const a = pos[o + k], b = pos[o + 3 + k], c = pos[o + 6 + k];
      const lo = Math.min(a, b, c), hi = Math.max(a, b, c);
      box[t * 6 + k] = lo;
      box[t * 6 + 3 + k] = hi;
      cen[t * 3 + k] = (lo + hi) / 2;
    }
  }
  const bounds = [], links = []; // per node: its box; [right child or first triangle, count]
  const node = (from, to, depth) => {
    const id = links.length / 2;
    links.push(0, 0);
    let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    let cx0 = Infinity, cy0 = Infinity, cz0 = Infinity, cx1 = -Infinity, cy1 = -Infinity, cz1 = -Infinity;
    for (let i = from; i < to; i++) {
      const t = order[i], b = t * 6, c = t * 3;
      if (box[b] < x0) x0 = box[b]; if (box[b + 1] < y0) y0 = box[b + 1]; if (box[b + 2] < z0) z0 = box[b + 2];
      if (box[b + 3] > x1) x1 = box[b + 3]; if (box[b + 4] > y1) y1 = box[b + 4]; if (box[b + 5] > z1) z1 = box[b + 5];
      if (cen[c] < cx0) cx0 = cen[c]; if (cen[c + 1] < cy0) cy0 = cen[c + 1]; if (cen[c + 2] < cz0) cz0 = cen[c + 2];
      if (cen[c] > cx1) cx1 = cen[c]; if (cen[c + 1] > cy1) cy1 = cen[c + 1]; if (cen[c + 2] > cz1) cz1 = cen[c + 2];
    }
    const eps = 1e-6 * (Math.max(x1 - x0, y1 - y0, z1 - z0) + 1); // (a ray along a box's side still enters it)
    bounds.push(x0 - eps, y0 - eps, z0 - eps, x1 + eps, y1 + eps, z1 + eps);
    if (to - from <= LEAF) { links[id * 2] = from; links[id * 2 + 1] = to - from; return id; }
    // split at the middle of the longest side of the centres' box; all on one side: half and half
    const ext = [cx1 - cx0, cy1 - cy0, cz1 - cz0], ax = ext[0] >= ext[1] && ext[0] >= ext[2] ? 0 : ext[1] >= ext[2] ? 1 : 2;
    const mid = [(cx0 + cx1) / 2, (cy0 + cy1) / 2, (cz0 + cz1) / 2][ax];
    let i = from, j = to - 1;
    while (i <= j) {
      if (cen[order[i] * 3 + ax] < mid) i++;
      else { const s = order[i]; order[i] = order[j]; order[j] = s; j--; }
    }
    let cut = i;
    if (cut === from || cut === to || depth > 48) cut = (from + to) >> 1; // (deep: halves, the tree stays shallow)
    node(from, cut, depth + 1);
    links[id * 2] = node(cut, to, depth + 1); // (the left child is id + 1)
    links[id * 2 + 1] = 0;
    return id;
  };
  if (n) node(0, n, 0);
  return { bounds: new Float32Array(bounds), links: new Uint32Array(links), order };
}

/** The tree of a mesh's geometry (built now if it has none). */
export function treeOf(geometry) {
  const pos = geometry.attributes.position.array;
  let tr = TREES.get(pos);
  if (!tr) { tr = build(pos); TREES.set(pos, tr); }
  return tr;
}

const _inv = new THREE.Matrix4(), _ray = new THREE.Ray(), _sphere = new THREE.Sphere(), _at = new THREE.Vector3();
const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _c = new THREE.Vector3(), _p = new THREE.Vector3();
const _na = new THREE.Vector3(), _nb = new THREE.Vector3(), _nc = new THREE.Vector3();

/** Mesh.raycast through the tree (a non-indexed geometry: triangle t = vertices 3t … 3t + 2). */
function raycast(raycaster, intersects) {
  const geo = this.geometry, mat = this.material, mw = this.matrixWorld;
  if (mat === undefined || geo.index || Array.isArray(mat)) { THREE.Mesh.prototype.raycast.call(this, raycaster, intersects); return; }
  if (geo.boundingSphere === null) geo.computeBoundingSphere();
  _sphere.copy(geo.boundingSphere).applyMatrix4(mw);
  _ray.copy(raycaster.ray).recast(raycaster.near);
  if (!_sphere.containsPoint(_ray.origin)) {
    if (_ray.intersectSphere(_sphere, _at) === null) return;
    if (_ray.origin.distanceToSquared(_at) > (raycaster.far - raycaster.near) ** 2) return;
  }
  _inv.copy(mw).invert();
  _ray.copy(raycaster.ray).applyMatrix4(_inv);
  if (geo.boundingBox !== null && !_ray.intersectsBox(geo.boundingBox)) return;
  const { bounds, links, order } = treeOf(geo), pos = geo.attributes.position.array, nrm = geo.attributes.normal;
  const o = _ray.origin, d = _ray.direction, ix = 1 / d.x, iy = 1 / d.y, iz = 1 / d.z;
  const hitsBox = (k) => { // the slab test (a ray along an axis: 1 / 0 = ±Infinity works)
    const b = k * 6;
    let t0 = ((ix >= 0 ? bounds[b] : bounds[b + 3]) - o.x) * ix, t1 = ((ix >= 0 ? bounds[b + 3] : bounds[b]) - o.x) * ix;
    const ty0 = ((iy >= 0 ? bounds[b + 1] : bounds[b + 4]) - o.y) * iy, ty1 = ((iy >= 0 ? bounds[b + 4] : bounds[b + 1]) - o.y) * iy;
    if (t0 > ty1 || ty0 > t1) return false;
    if (ty0 > t0 || t0 !== t0) t0 = ty0;
    if (ty1 < t1 || t1 !== t1) t1 = ty1;
    const tz0 = ((iz >= 0 ? bounds[b + 2] : bounds[b + 5]) - o.z) * iz, tz1 = ((iz >= 0 ? bounds[b + 5] : bounds[b + 2]) - o.z) * iz;
    if (t0 > tz1 || tz0 > t1) return false;
    if (tz1 < t1 || t1 !== t1) t1 = tz1;
    return t1 >= 0;
  };
  const found = [];
  const stack = links.length ? [0] : [];
  while (stack.length) {
    const k = stack.pop();
    if (!hitsBox(k)) continue;
    const count = links[k * 2 + 1];
    if (!count) { stack.push(links[k * 2], k + 1); continue; }
    for (let i = links[k * 2], e = i + count; i < e; i++) found.push(order[i]);
  }
  found.sort((p, q) => p - q); // (three's order: by triangle; the raycaster sorts by distance after)
  for (const t of found) {
    const v = t * 9;
    _a.set(pos[v], pos[v + 1], pos[v + 2]);
    _b.set(pos[v + 3], pos[v + 4], pos[v + 5]);
    _c.set(pos[v + 6], pos[v + 7], pos[v + 8]);
    const hit = mat.side === THREE.BackSide ? _ray.intersectTriangle(_c, _b, _a, true, _p) : _ray.intersectTriangle(_a, _b, _c, mat.side === THREE.FrontSide, _p);
    if (hit === null) continue;
    const world = _p.clone().applyMatrix4(mw), distance = raycaster.ray.origin.distanceTo(world);
    if (distance < raycaster.near || distance > raycaster.far) continue;
    const x = { distance, point: world, object: this };
    if (nrm) {
      _na.fromBufferAttribute(nrm, t * 3); _nb.fromBufferAttribute(nrm, t * 3 + 1); _nc.fromBufferAttribute(nrm, t * 3 + 2);
      x.normal = THREE.Triangle.getInterpolation(_p, _a, _b, _c, _na, _nb, _nc, new THREE.Vector3());
      if (x.normal.dot(_ray.direction) > 0) x.normal.multiplyScalar(-1);
    }
    x.face = { a: t * 3, b: t * 3 + 1, c: t * 3 + 2, normal: THREE.Triangle.getNormal(_a, _b, _c, new THREE.Vector3()), materialIndex: 0 };
    x.faceIndex = t;
    intersects.push(x);
  }
}

/** A mesh picked through its tree from now on (the tree is built when the browser is idle, or on its first ray). */
export function accelerate(mesh) {
  mesh.raycast = raycast;
  const geo = mesh.geometry;
  if (!geo.index && !TREES.has(geo.attributes.position.array)) (window.requestIdleCallback || setTimeout)(() => treeOf(geo), { timeout: 3000 });
  return mesh;
}
