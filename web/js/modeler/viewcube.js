// The view cube in the top-right corner of a 3D view (the 3D model, the assembly): it turns with the camera; a click on
// a face looks from that side, on an edge or a corner from in between (the iso view from that corner), ⌂ goes back to
// the usual iso view. Plain DOM in CSS 3D (crisp labels at any size): each face is turned by the camera's rotation
// whenever the view is drawn; the faces turned away are hidden, so the ones shown never overlap. It sits just under the
// view's command bar (however many rows the bar has), so the bar keeps the whole width.
import * as THREE from 'three';
import { t } from '../i18n.js';

const S = 48; // a face's size (px): the cube stays within ~84 px however it is turned
// each face: its outward normal n, and which way its label reads (right r, up u) seen from outside — the way
// ModelView.setView turns the camera for that side (Z up; the top seen with +Y up, the bottom with -Y up)
const FACES = [
  { label: 'TOP', n: [0, 0, 1], r: [1, 0, 0], u: [0, 1, 0] },
  { label: 'BOTTOM', n: [0, 0, -1], r: [1, 0, 0], u: [0, -1, 0] },
  { label: 'FRONT', n: [0, -1, 0], r: [1, 0, 0], u: [0, 0, 1] },
  { label: 'BACK', n: [0, 1, 0], r: [-1, 0, 0], u: [0, 0, 1] },
  { label: 'RIGHT', n: [1, 0, 0], r: [0, 1, 0], u: [0, 0, 1] },
  { label: 'LEFT', n: [-1, 0, 0], r: [0, -1, 0], u: [0, 0, 1] },
];
/** A face's side name for setView, by its normal ("0,0,1" -> 'top'). */
const SIDE = { '0,0,1': 'top', '0,0,-1': 'bottom', '0,-1,0': 'front', '0,1,0': 'back', '1,0,0': 'right', '-1,0,0': 'left' };

export class ViewCube {
  /** container: the view's element (the cube goes in its top-right corner); look(dir): turn the camera — dir a side
   *  name ('top', 'iso' …) or a direction [x, y, z] to look from. */
  constructor(container, look) {
    this.look = look;
    this.el = document.createElement('div');
    this.el.className = 'view-cube';
    this.el.dataset.noI18n = ''; // (labelled here, through t(): the page's translator leaves it alone)
    // a face = 3 × 3 cells: the middle one is the face, the side ones its edges, the corner ones its corners; a cell's
    // data-dir is where it looks from (the normal plus the cell's offset), so the cells of one edge or corner on
    // neighbouring faces share it and light up together
    this.el.innerHTML = `<div class="vc-cube">${FACES.map((f) => `<div class="vc-face"><b></b>${[1, 0, -1].map((j) => [-1, 0, 1].map((i) =>
      `<i data-dir="${[0, 1, 2].map((k) => f.n[k] + i * f.r[k] + j * f.u[k]).join(',')}"></i>`).join('')).join('')}</div>`).join('')}</div>
      <button class="vc-home" data-dir="iso">⌂</button>`;
    this.faces = [...this.el.querySelectorAll('.vc-face')];
    this.el.addEventListener('pointermove', (e) => this.hover(e.target.closest?.('[data-dir]')?.dataset.dir || ''));
    this.el.addEventListener('pointerleave', () => this.hover(''));
    this.el.addEventListener('click', (e) => {
      const dir = e.target.closest?.('[data-dir]')?.dataset.dir;
      if (!dir) return;
      this.look(dir === 'iso' ? 'iso' : SIDE[dir] || dir.split(',').map(Number));
    });
    for (const ev of ['pointerdown', 'pointerup', 'dblclick', 'contextmenu']) this.el.addEventListener(ev, (e) => e.stopPropagation());
    container.appendChild(this.el);
    const bar = container.closest('.viewport')?.querySelector(':scope > .m-cmdbar');
    if (bar) { // (under the bar: the view is inset 0 in the viewport, so the bar's place is the cube's too)
      const under = () => { this.el.style.top = `${bar.offsetTop + bar.offsetHeight + 6}px`; };
      new ResizeObserver(under).observe(bar);
      under();
    }
    this.label();
    window.addEventListener('a3d:lang', () => this.label());
  }

  label() {
    this.faces.forEach((el, k) => { el.querySelector('b').textContent = t(FACES[k].label); });
    this.el.title = t('Click a face, an edge or a corner of the cube: the view from there');
    this.el.querySelector('.vc-home').title = t('View from the front-right, above');
  }

  /** Light the cells looking from dir (a face, the two halves of an edge, the three parts of a corner). */
  hover(dir) {
    if (dir === this.lit) return;
    this.lit = dir;
    for (const c of this.el.querySelectorAll('[data-dir]')) c.classList.toggle('hi', !!dir && c.dataset.dir === dir);
  }

  /** Turn the cube as the camera sees the world (no perspective: it reads the same at any zoom). */
  update(camera) {
    camera.updateMatrixWorld();
    const R = new THREE.Matrix4().extractRotation(camera.matrixWorldInverse);
    const flip = new THREE.Matrix4().makeScale(1, -1, 1); // (the camera's y is up, CSS's down)
    FACES.forEach((f, k) => {
      const n = new THREE.Vector3(...f.n), r = new THREE.Vector3(...f.r), u = new THREE.Vector3(...f.u);
      const el = this.faces[k], toward = n.clone().applyMatrix4(R).z; // (> 0: the face looks at us)
      el.style.visibility = toward > 1e-3 ? '' : 'hidden';
      if (toward <= 1e-3) return;
      // the face's own plane (x right, y down as in CSS) placed on the cube: x -> r, y -> -u, out -> n, half a size out
      const F = new THREE.Matrix4().makeBasis(r, u.clone().negate(), n).setPosition(n.clone().multiplyScalar(S / 2));
      el.style.transform = `matrix3d(${flip.clone().multiply(R).multiply(F).elements.map((v) => +v.toFixed(6)).join(',')})`;
    });
  }
}
