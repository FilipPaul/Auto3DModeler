// ✂ The section bar over a 3D view (3D model and assembly): the axis, where the cut is (a slider), ⇄ the other side, ✕.
import { floatBox } from '../floatbox.js';

const fmt = (v) => (+(+v).toFixed(3)).toString();
const K = { x: 0, y: 1, z: 2 };

/** The middle of a bounding box [x0, y0, z0, x1, y1, z1] along an axis. */
export const sectionMiddle = (bb, axis) => +((bb[K[axis]] + bb[K[axis] + 3]) / 2).toFixed(3);

/** Show (or update) the bar in `viewport` for section s = {axis, offset, flip} over the box bb.
 *  onChange(s): the cut moved; onClose(): ✕. */
export function sectionBar(viewport, s, bb, { onChange, onClose }) {
  const i = K[s.axis], lo = bb[i], hi = bb[i + 3];
  let box = viewport.querySelector('.m-section');
  if (!box) { box = document.createElement('div'); box.className = 'm-section'; viewport.appendChild(box); }
  box.innerHTML = `<span>✂</span><div class="seg">${['x', 'y', 'z'].map((a) => `<button data-ax="${a}" class="${a === s.axis ? 'on' : ''}">${a.toUpperCase()}</button>`).join('')}</div>
    <input type="range" min="${lo}" max="${hi}" step="${(hi - lo) / 200 || 0.1}" value="${s.offset}"><b>${fmt(s.offset)} mm</b>
    <button class="mini" data-flip title="Show the other side">⇄</button><button class="mini" data-x title="No section">✕</button>`;
  for (const b of box.querySelectorAll('[data-ax]')) b.addEventListener('click', () => {
    s.axis = b.dataset.ax;
    s.offset = sectionMiddle(bb, s.axis);
    onChange(s);
    sectionBar(viewport, s, bb, { onChange, onClose });
  });
  const r = box.querySelector('input');
  r.addEventListener('input', () => { s.offset = +r.value; box.querySelector('b').textContent = `${fmt(s.offset)} mm`; onChange(s); });
  box.querySelector('[data-flip]').addEventListener('click', () => { s.flip = !s.flip; onChange(s); });
  box.querySelector('[data-x]').addEventListener('click', () => onClose());
  return floatBox(box, viewport, { kind: 'section', min: [230, 30] }); // (the ⠿ on its left end moves it)
}
