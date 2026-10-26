// Turning the 3D view without limits (as in CAD programs): a left drag turns the view about the screen's own axes —
// across the screen about its upright, up / down about its level — so the part can go over the top and round as far as
// you like. Right drag pans, the wheel zooms (to the point it turns about). A small drop-in for the parts of
// three.js' OrbitControls the app uses: target, update(), enabled, enableRotate, enableDamping, dampingFactor,
// mouseButtons {LEFT, MIDDLE, RIGHT} (0 turn, 1 zoom, 2 pan, null nothing) and the 'change' event.
import * as THREE from 'three';

const ROTATE = 0, DOLLY = 1, PAN = 2;

export class FreeControls extends THREE.EventDispatcher {
  constructor(camera, dom) {
    super();
    this.camera = camera;
    this.dom = dom;
    this.target = new THREE.Vector3();
    this.enabled = true;
    this.enableRotate = true;
    this.enableDamping = true;
    this.dampingFactor = 0.12;
    this.rotateSpeed = 1;
    this.zoomSpeed = 1;
    this.mouseButtons = { LEFT: ROTATE, MIDDLE: DOLLY, RIGHT: PAN };
    this.turn = { x: 0, y: 0 }; // what is still to turn (radians about the screen's upright / level), slowing down
    this.drag = null;
    dom.style.touchAction = 'none';
    dom.addEventListener('contextmenu', (e) => e.preventDefault());
    dom.addEventListener('pointerdown', (e) => this.down(e));
    dom.addEventListener('pointermove', (e) => this.move(e));
    dom.addEventListener('pointerup', (e) => this.up(e));
    dom.addEventListener('pointercancel', (e) => this.up(e));
    dom.addEventListener('wheel', (e) => this.wheel(e), { passive: false });
  }

  down(e) {
    if (!this.enabled) return;
    const what = [this.mouseButtons.LEFT, this.mouseButtons.MIDDLE, this.mouseButtons.RIGHT][e.button];
    if (what === null || what === undefined || (what === ROTATE && !this.enableRotate)) return;
    this.drag = { what, x: e.clientX, y: e.clientY, id: e.pointerId };
    this.turn = { x: 0, y: 0 };
    this.dom.setPointerCapture?.(e.pointerId);
  }

  move(e) {
    const d = this.drag;
    if (!d || !this.enabled || e.pointerId !== d.id) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y, h = this.dom.clientHeight || 1;
    d.x = e.clientX;
    d.y = e.clientY;
    if (d.what === ROTATE) {
      const k = (2 * Math.PI * this.rotateSpeed) / h;
      this.rotate(-dx * k, -dy * k);
      if (this.enableDamping) this.turn = { x: -dx * k, y: -dy * k };
    } else if (d.what === PAN) this.pan(dx, dy);
    else if (d.what === DOLLY) this.dolly(Math.pow(0.95, -dy * 0.2 * this.zoomSpeed));
    this.changed();
  }

  up(e) {
    if (!this.drag || e.pointerId !== this.drag.id) return;
    this.drag = null;
    this.dom.releasePointerCapture?.(e.pointerId);
  }

  wheel(e) {
    if (!this.enabled) return;
    e.preventDefault();
    const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    this.dolly(Math.pow(0.95, (dy / 100) * this.zoomSpeed * 2)); // wheel up (dy < 0): closer
    this.changed();
  }

  /** Turn the camera round the target: a about the screen's upright, b about its level. */
  rotate(a, b) {
    const cam = this.camera, off = cam.position.clone().sub(this.target);
    const up = cam.up.clone().normalize(), back = off.clone().normalize();
    const right = new THREE.Vector3().crossVectors(up, back).normalize();
    const screenUp = new THREE.Vector3().crossVectors(back, right).normalize();
    const q = new THREE.Quaternion().setFromAxisAngle(screenUp, a).multiply(new THREE.Quaternion().setFromAxisAngle(right, b));
    off.applyQuaternion(q);
    cam.up.copy(screenUp.applyQuaternion(q));
    cam.position.copy(this.target).add(off);
    cam.lookAt(this.target);
  }

  pan(dx, dy) {
    const cam = this.camera, h = this.dom.clientHeight || 1, dist = cam.position.distanceTo(this.target);
    const k = cam.isPerspectiveCamera ? (2 * dist * Math.tan(((cam.fov / 2) * Math.PI) / 180)) / h : (cam.top - cam.bottom) / cam.zoom / h;
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 0), upv = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 1);
    const move = right.multiplyScalar(-dx * k).add(upv.multiplyScalar(dy * k));
    cam.position.add(move);
    this.target.add(move);
  }

  dolly(f) {
    const cam = this.camera;
    if (cam.isOrthographicCamera) { cam.zoom = Math.max(1e-4, cam.zoom * f); cam.updateProjectionMatrix(); return; }
    const off = cam.position.clone().sub(this.target).multiplyScalar(1 / f);
    if (off.length() < 1e-3) return;
    cam.position.copy(this.target).add(off);
  }

  /** Called every frame: the turn left over after a drag slows down (damping); the camera looks at the target. */
  update() {
    const cam = this.camera;
    // the camera's up stays across its view direction (presets set it)
    const back = cam.position.clone().sub(this.target).normalize(), up = cam.up.clone();
    up.addScaledVector(back, -up.dot(back));
    if (up.lengthSq() > 1e-12) cam.up.copy(up.normalize());
    cam.lookAt(this.target);
    if (!this.drag && this.enableDamping && (Math.abs(this.turn.x) > 1e-5 || Math.abs(this.turn.y) > 1e-5)) {
      this.turn.x *= 1 - this.dampingFactor * 2;
      this.turn.y *= 1 - this.dampingFactor * 2;
      this.rotate(this.turn.x, this.turn.y);
      this.changed();
      return true;
    }
    return false;
  }

  changed() { this.dispatchEvent({ type: 'change' }); }

  dispose() { /* the listeners go with the canvas */ }
}
