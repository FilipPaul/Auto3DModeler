// ✂ The section's caps: a part's triangles sliced by the cut plane into closed outlines, filled in the plane — so a
// cut part looks solid (its bores, seats and channels open) instead of hollow. Exact to the drawn triangles; an
// outline that does not close (a mesh with a gap) is left open rather than filled wrong.
import * as THREE from 'three';

/** The cap of a mesh cut by plane (world space; kept: plane.distanceToPoint ≥ 0) -> a BufferGeometry in world space,
 *  or null (the plane misses it, or no outline closes). */
export function capGeometry(mesh, plane) {
  const loops = sliceLoops(mesh, plane);
  if (!loops.length) return null;
  // the plane's own 2D axes: u, v in it (n = u × v points to the kept side)
  const n = plane.normal, u = new THREE.Vector3(), v = new THREE.Vector3();
  u.set(Math.abs(n.x) < 0.9 ? 1 : 0, Math.abs(n.x) < 0.9 ? 0 : 1, 0).cross(n).normalize();
  v.crossVectors(n, u);
  const flat = loops.map((l) => l.map((p) => new THREE.Vector2(p.dot(u), p.dot(v))));
  // nesting: a loop inside an even number of others is an outline, inside an odd number a hole (of the smallest
  // outline round it)
  const area = flat.map((l) => Math.abs(THREE.ShapeUtils.area(l)));
  const inside = flat.map((l, i) => flat.map((o, j) => j !== i && area[j] > area[i] && contains(o, l[0])));
  const depth = inside.map((row) => row.filter(Boolean).length);
  const pos = [], o = n.clone().multiplyScalar(-plane.constant); // (the plane's point nearest the origin)
  flat.forEach((outer, i) => {
    if (depth[i] % 2 || area[i] < 1e-12) return;
    const holes = flat.filter((_, j) => depth[j] === depth[i] + 1 && inside[j][i]);
    const pts = [...outer, ...holes.flat()];
    for (const tri of THREE.ShapeUtils.triangulateShape(outer, holes)) {
      for (const k of tri) pos.push(o.x + u.x * pts[k].x + v.x * pts[k].y, o.y + u.y * pts[k].x + v.y * pts[k].y, o.z + u.z * pts[k].x + v.z * pts[k].y);
    }
  });
  if (!pos.length) return null;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  const nrm = new Float32Array(pos.length);
  for (let i = 0; i < nrm.length; i += 3) nrm.set([-n.x, -n.y, -n.z], i); // (facing the side cut away: the viewer's)
  geo.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
  return geo;
}

/** The closed outlines where the plane cuts the mesh's triangles -> [[Vector3 …] …] (world space). */
function sliceLoops(mesh, plane) {
  const g = mesh.geometry, P = g.attributes.position, idx = g.index, m = mesh.matrixWorld;
  const nv = P.count, w = new Float32Array(nv * 3), d = new Float64Array(nv), p = new THREE.Vector3();
  for (let i = 0; i < nv; i++) {
    p.fromBufferAttribute(P, i).applyMatrix4(m);
    w[i * 3] = p.x; w[i * 3 + 1] = p.y; w[i * 3 + 2] = p.z;
    d[i] = plane.distanceToPoint(p);
  }
  const box = new THREE.Box3().setFromBufferAttribute(P), q = Math.max(box.getSize(p).length(), 1) * 1e-7;
  const keyOf = (x, y, z) => `${Math.round(x / q)},${Math.round(y / q)},${Math.round(z / q)}`;
  const pts = new Map(); // key -> the point
  // where an edge a–b crosses: worked out the same way from both triangles that share it (from its lower end, by
  // position: the triangles have vertices of their own, at the same places)
  const lower = (a, b) => w[a * 3] - w[b * 3] || w[a * 3 + 1] - w[b * 3 + 1] || w[a * 3 + 2] - w[b * 3 + 2];
  const cross = (a, b) => {
    if (lower(b, a) < 0) [a, b] = [b, a];
    const t = d[a] / (d[a] - d[b]);
    const x = w[a * 3] + (w[b * 3] - w[a * 3]) * t, y = w[a * 3 + 1] + (w[b * 3 + 1] - w[a * 3 + 1]) * t, z = w[a * 3 + 2] + (w[b * 3 + 2] - w[a * 3 + 2]) * t;
    const k = keyOf(x, y, z);
    if (!pts.has(k)) pts.set(k, new THREE.Vector3(x, y, z));
    return k;
  };
  const segs = [], ends = new Map(); // key -> the segments ending there
  const nt = idx ? idx.count / 3 : nv / 3;
  for (let t = 0; t < nt; t++) {
    const i = idx ? [idx.getX(t * 3), idx.getX(t * 3 + 1), idx.getX(t * 3 + 2)] : [t * 3, t * 3 + 1, t * 3 + 2];
    const s = i.map((k) => d[k] >= 0);
    if (s[0] === s[1] && s[1] === s[2]) continue;
    const ks = [];
    for (let e = 0; e < 3; e++) if (s[e] !== s[(e + 1) % 3]) ks.push(cross(i[e], i[(e + 1) % 3]));
    if (ks.length !== 2 || ks[0] === ks[1]) continue;
    const sg = segs.length;
    segs.push(ks);
    for (const k of ks) { if (!ends.has(k)) ends.set(k, []); ends.get(k).push(sg); }
  }
  // chain the segments into loops; one that ends before coming back is dropped
  const used = new Uint8Array(segs.length), loops = [];
  for (let s0 = 0; s0 < segs.length; s0++) {
    if (used[s0]) continue;
    used[s0] = 1;
    const start = segs[s0][0], loop = [start];
    let at = segs[s0][1], closed = false;
    for (let guard = 0; guard <= segs.length; guard++) {
      if (at === start) { closed = true; break; }
      loop.push(at);
      const next = ends.get(at).find((k) => !used[k]);
      if (next === undefined) break;
      used[next] = 1;
      at = segs[next][0] === at ? segs[next][1] : segs[next][0];
    }
    if (closed && loop.length >= 3) loops.push(loop.map((k) => pts.get(k)));
  }
  return loops;
}

/** Is the point inside the polygon (even-odd)? */
function contains(poly, pt) {
  let inn = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j];
    if ((a.y > pt.y) !== (b.y > pt.y) && pt.x < ((b.x - a.x) * (pt.y - a.y)) / (b.y - a.y) + a.x) inn = !inn;
  }
  return inn;
}
