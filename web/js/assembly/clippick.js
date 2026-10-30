// 📎 Picking a cable clip for a point of a harness (assembly/harness.js): a see-through ghost of the clip in the view
// where it would go (its mounting face on the point's face, the cable along it, the point on its axis) while the mouse
// or the keyboard is on its row — in the suggestions or in the pick list — with a small label (name, cable Ø, how it
// is fixed); and the pick list: every clip, tie mount and tie of the library grouped by type, the ones that hold the
// bundle first, the others greyed with why (too small, too loose, only on a tie mount). A click puts it there (a
// point that has a clip: swaps it, the point kept); ☐ For all points on faces puts the same clip on each that has none.
// Each clip's mesh is built by the kernel once (cableparts.js clipGeometry) and only moved.
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { t, getLang } from '../i18n.js';
import { floatBox, scrollFade } from '../floatbox.js';
import { clipChoices, clipPlace, clipGeometry } from '../library/cableparts.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (v) => { const s = String(+(+v).toFixed(2)); return getLang() === 'cs' ? s.replace('.', ',') : s; };
const GHOST = 0xf2cc60; // (the app's preview colour: setGhost, the hole previews)

const GROUPS = [['clip', 'P-clips'], ['tie mount', 'Tie mounts'], ['tie', 'Cable ties']];
const ICONS = { // (small line drawings: a P-clamp's loop on its foot, a square tie mount, a tie with its head)
  clip: '<svg viewBox="0 0 20 20"><circle cx="9" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 8v8h13" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="14" cy="16" r="1.2" fill="currentColor"/></svg>',
  'tie mount': '<svg viewBox="0 0 20 20"><rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 10h6M10 7v6" stroke="currentColor" stroke-width="1.6"/></svg>',
  tie: '<svg viewBox="0 0 20 20"><rect x="2" y="8.5" width="12" height="3" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="14" y="6.5" width="4" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
};

/** How a clip is fixed, in plain words: "screw M4", "adhesive or screw M3", "on a tie mount". */
export function mountText(c) {
  if (c.mount === 'tie' || c.kind === 'tie') return t('on a tie mount');
  if (c.mount === 'adhesive') return c.screw ? t2('adhesive or screw {s}', { s: c.screw }) : t('adhesive');
  return c.screw ? t2('screw {s}', { s: c.screw }) : t('screwed');
}

/** Why a clip does not hold the bundle: "Ø 3.2 max — too small". */
export function whyText(c) {
  if (c.why === 'small') return t2('Ø {d} max — too small', { d: num(c.dmax) });
  if (c.why === 'large') return t2('Ø {d} min — too loose', { d: num(c.dmin) });
  return t('Goes round the bundle on a tie mount');
}

const shortName = (c) => (c.item.maker && c.label.startsWith(`${c.item.maker} `) ? c.label.slice(c.item.maker.length + 1) : c.label);
const rangeText = (c) => `Ø ${num(c.dmin)}–${num(c.dmax)}`;

export class ClipPick {
  constructor(tool) {
    this.tool = tool;
    this.asm = tool.asm;
    this.objs = new Map(); // item id|size -> {obj (the mesh and its edges), label} — made once, then only moved
    this.tok = 0; // (the newest ghost asked for wins: a mesh still building for a row left is not shown)
    this.shown = null; // the ghost in the view: {key, h, i, matrix, axis, text}
    this.at = null; // the pick list open for {h, i}
    this.box = null;
  }

  // ---------------------------------------------------------------- the ghost
  /** The ghost of clip choice c (clipChoices' / clipsFor's) at point i of harness h, where a click would put it. */
  async ghost(h, i, c) {
    const tok = ++this.tok, pose = c && c.fits !== false ? this.tool.clipPose(h, i) : null;
    if (!pose) { this.hide(); return; }
    const P = clipPlace(c, pose.face, pose.n, pose.dir, { d: pose.D }), key = `${c.item.id}|${P.size}`;
    let o = this.objs.get(key);
    if (!o) {
      let g;
      try { g = await clipGeometry(c.item, P.size); } catch { return; }
      if (tok !== this.tok) return;
      o = this.objs.get(key) || this.make(g);
      this.objs.set(key, o);
    }
    if (tok !== this.tok) return;
    const v = this.asm.view, text = `📎 ${shortName(c)} · ${rangeText(c)} mm · ${mountText(c)}`;
    if (!this.group) { this.group = new THREE.Group(); this.group.name = 'clipGhost'; v.scene.add(this.group); }
    this.clear();
    o.obj.matrix.copy(P.M);
    o.obj.matrixWorldNeedsUpdate = true;
    for (const m of o.obj.children) m.material.clippingPlanes = v.clip || [];
    o.label.element.firstChild.textContent = text;
    o.label.position.fromArray(P.axis?.o || pose.face.toArray());
    this.group.add(o.obj, o.label);
    this.shown = { key, h: h.id, i, matrix: P.M.toArray(), axis: P.axis, text };
    v.invalidate();
  }

  /** A clip's see-through mesh with its edges, and its label (made once per clip and size). */
  make(g) {
    const obj = new THREE.Group();
    obj.matrixAutoUpdate = false;
    const mesh = new THREE.Mesh(g.geo, new THREE.MeshStandardMaterial({ color: GHOST, emissive: 0x3a2e08, roughness: 0.6, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }));
    const lines = new THREE.LineSegments(g.edges, new THREE.LineBasicMaterial({ color: GHOST, transparent: true, opacity: 0.9 }));
    mesh.renderOrder = lines.renderOrder = 5;
    obj.add(mesh, lines);
    obj.userData.clipGhost = true;
    const el = document.createElement('div'), sp = document.createElement('span');
    el.style.pointerEvents = 'none';
    sp.className = 'hn-tag hn-ghost';
    el.appendChild(sp);
    return { obj, label: new CSS2DObject(el) };
  }

  clear() {
    if (!this.group) return;
    for (const o of [...this.group.children]) { this.group.remove(o); if (o.isCSS2DObject) o.element.remove(); }
  }

  /** No ghost (the row left, a clip put in, the list closed). */
  hide() {
    this.tok++;
    if (!this.shown) return;
    this.clear();
    this.shown = null;
    this.asm.view?.invalidate();
  }

  // ---------------------------------------------------------------- the pick list
  /** 📎 The pick list for point i of harness h (a point on a face, or one with a clip: swap it), over the view. */
  open(h, i) {
    this.close();
    const pose = this.tool.clipPose(h, i);
    if (!pose) { this.asm.hooks.toast(t('A clip goes on a point lying on a part\'s face.'), 'warning', 5000); return; }
    const all = clipChoices(pose.D), cur = pose.current, best = all.find((c) => c.fits);
    const free = (h.points || []).filter((p) => p.inst && p.n && !p.clip).length; // (☐ for all: the points on faces with no clip yet)
    const row = (c, k) => {
      const on = cur && cur.item === c.item.id && cur.size === c.size;
      return `<button class="hnc-row${c.fits ? '' : ' off'}${on ? ' on' : ''}" data-ci="${k}" ${c.fits ? '' : 'aria-disabled="true" tabindex="-1"'} title="${esc(c.label)}${c.fits ? '' : ` — ${esc(whyText(c))}`}">
        <span class="hnc-ic">${ICONS[c.kind] || ICONS.clip}</span><span class="hnc-n">${esc(c.size)}${c === best && !cur ? ` <i class="hnc-best">${esc(t('snuggest'))}</i>` : ''}${on ? ' ✓' : ''}</span>
        <span class="hnc-d">${rangeText(c)}</span><span class="hnc-m">${esc(c.fits ? mountText(c) : whyText(c))}</span></button>`;
    };
    const vp = this.asm.els.viewport, box = document.createElement('div');
    box.className = 'hn-clips';
    box.dataset.noI18n = '';
    box.innerHTML = `<div class="hnc-head"><b>📎 ${esc(t(cur ? 'Swap the clip' : 'Choose a clip'))}</b><button class="vs-x" data-hcx title="${esc(t('Close (Esc)'))}">✕</button></div>
      <p class="hnc-sub">${esc(t2('Point {n} · bundle Ø{d} mm — point at a row: preview, click: put it there', { n: i + 1, d: num(pose.D) }))}</p>
      <div class="hnc-list">${GROUPS.map(([kind, name]) => {
        const list = all.map((c, k) => [c, k]).filter(([c]) => c.kind === kind);
        return list.length ? `<div class="hnc-sec">${esc(t(name))}</div>${list.map(([c, k]) => row(c, k)).join('')}` : '';
      }).join('')}</div>
      ${!cur && free > 1 ? `<label class="hnc-all" title="${esc(t('The clip you click goes on every point of this harness that lies on a face and has no clip yet — one undo step'))}"><input type="checkbox" data-hcall> ${esc(t2('For all points on faces ({n})', { n: free }))}</label>` : ''}`;
    for (const ev of ['pointerdown', 'pointerup', 'click', 'dblclick', 'wheel']) box.addEventListener(ev, (x) => x.stopPropagation());
    vp.appendChild(box);
    floatBox(box, vp, { kind: 'clips', handle: '.hnc-head', min: [220, 140] });
    scrollFade(box.querySelector('.hnc-list'));
    this.box = box;
    this.at = { h: h.id, i };
    const rows = [...box.querySelectorAll('.hnc-row:not(.off)')];
    for (const b of box.querySelectorAll('.hnc-row')) {
      const c = all[+b.dataset.ci];
      if (!c.fits) continue;
      b.addEventListener('mouseenter', () => this.ghost(h, i, c));
      b.addEventListener('mouseleave', () => this.hide());
      b.addEventListener('focus', () => this.ghost(h, i, c));
      b.addEventListener('blur', () => this.hide());
      b.addEventListener('click', () => {
        const every = box.querySelector('[data-hcall]')?.checked;
        this.close();
        (every ? this.tool.clipAll(h, c) : this.tool.clipAt(h, i, c)).catch((e) => this.asm.hooks.toast(e.message, 'warning', 6000));
      });
    }
    box.addEventListener('keydown', (e) => { // (the keyboard: ↑ ↓ through the rows — each one previewed —, Enter puts it, Esc closes)
      e.stopPropagation();
      if (e.key === 'Escape') { this.close(); return; }
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      e.preventDefault();
      const k = rows.indexOf(document.activeElement), n = rows.length;
      rows[k < 0 ? (e.key === 'ArrowDown' ? 0 : n - 1) : (k + (e.key === 'ArrowDown' ? 1 : n - 1)) % n]?.focus();
    });
    box.querySelector('[data-hcx]').addEventListener('click', () => this.close());
    (box.querySelector('.hnc-row.on') || rows[0])?.scrollIntoView?.({ block: 'nearest' });
  }

  /** The pick list closed (and its ghost gone). */
  close() {
    this.hide();
    this.box?.remove();
    this.box = null;
    this.at = null;
  }
}
