// Small pictures of parts for the project tree's hover preview: a 3D model or an assembly drawn in iso by one offscreen
// renderer (its bodies made light by the server, kept by what they are made from), a drawing sheet as its own SVG.
import * as THREE from 'three';
import { fetchRebuild } from './modeler/packed.js';

const W = 220, H = 160;
let R = null;
const bodies = new Map(); // what a body is made from (its steps) -> the body
const pics = new Map();   // what a picture shows -> its data URL

const b64 = (s, T) => { // (a binary answer's arrays come as typed arrays already: modeler/packed.js)
  if (typeof s !== 'string') return s;
  const bin = atob(s), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new T(bytes.buffer);
};

/** A body of steps (light: a coarse mesh), kept while the steps are the same. */
export async function bodyOf(features) {
  const key = JSON.stringify(features);
  if (bodies.has(key)) return bodies.get(key);
  const { res, r } = await fetchRebuild({ features, lod: 'light' });
  const b = res.ok ? r.body || null : null;
  if (bodies.size > 60) bodies.delete(bodies.keys().next().value);
  bodies.set(key, b);
  return b;
}

/** Bodies drawn together in iso: [{body, matrix (16 numbers) or none, color}] -> a PNG data URL (or null). */
export function picture(list, key) {
  if (key && pics.has(key)) return pics.get(key);
  const items = list.filter((x) => x.body?.positions);
  if (!items.length) return null;
  if (!R) {
    R = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    R.setPixelRatio(1);
    R.setSize(W, H);
  }
  const scene = new THREE.Scene(), box = new THREE.Box3(), geos = [];
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 1.1);
  sun.position.set(0.6, -1, 1.4);
  scene.add(sun);
  for (const { body, matrix, color } of items) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(b64(body.positions, Float32Array), 3));
    geo.computeVertexNormals();
    geos.push(geo);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: color || 0x9db4d0, roughness: 0.6, metalness: 0.05 }));
    if (matrix) mesh.applyMatrix4(new THREE.Matrix4().fromArray(matrix));
    scene.add(mesh);
    box.expandByObject(mesh);
  }
  const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length() || 1;
  const cam = new THREE.PerspectiveCamera(30, W / H, size / 100, size * 10);
  cam.up.set(0, 0, 1);
  cam.position.copy(c).addScaledVector(new THREE.Vector3(1, -1.25, 0.95).normalize(), size * 1.9);
  cam.lookAt(c);
  R.render(scene, cam);
  const url = R.domElement.toDataURL('image/png');
  for (const g of geos) g.dispose();
  if (key) { if (pics.size > 80) pics.delete(pics.keys().next().value); pics.set(key, url); }
  return url;
}

/** An SVG text as a picture. */
export const svgPicture = (svg) => (svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` : null);
