// Full-window viewer with wheel zoom and drag pan, for the Drawing tab (PDF page or picture with
// its recognised outline). Shows a copy of the given element; Esc / ✕ / click outside closes it.

export function openLightbox(source, { title = '', actions = [], mmAcross = null } = {}) {
  const root = document.createElement('div');
  root.className = 'lightbox';
  root.innerHTML = `
    <div class="lb-box">
      <div class="lb-head"><b></b><span class="lb-hint">wheel = zoom · drag = pan · double-click = fit</span><span class="lb-measure"></span><span class="lb-acts"></span>
        <button class="chip lb-out">−</button><span class="lb-val">100%</span><button class="chip lb-in">+</button><button class="chip lb-fit">Fit</button>
        <button class="icon-btn lb-x" title="Close (Esc)">✕</button></div>
      <div class="lb-stage"><div class="lb-content"></div></div>
    </div>`;
  root.querySelector('.lb-head b').textContent = title;
  for (const [label, fn, cls] of actions) {
    const b = document.createElement('button');
    b.className = `btn small ${cls || ''}`;
    b.textContent = label;
    b.addEventListener('click', () => { close(); fn(); });
    root.querySelector('.lb-acts').appendChild(b);
  }
  document.body.appendChild(root);
  const stage = root.querySelector('.lb-stage'), content = root.querySelector('.lb-content');
  const copy = source.cloneNode(true);
  copy.removeAttribute('id');
  content.appendChild(copy);
  // measuring (when the drawing's real width is known): two clicks, distance in mm
  const NS = 'http://www.w3.org/2000/svg';
  const msvg = document.createElementNS(NS, 'svg');
  msvg.classList.add('lb-msvg');
  content.appendChild(msvg);
  let measuring = false, mpts = [];
  if (mmAcross > 0) {
    const mb = document.createElement('button');
    mb.className = 'chip lb-mbtn';
    mb.textContent = '📏 Measure';
    mb.title = 'Click two points on the drawing (distance in mm)';
    mb.addEventListener('click', () => { measuring = !measuring; mb.classList.toggle('on', measuring); stage.classList.toggle('measuring', measuring); });
    root.querySelector('.lb-acts').before(mb);
  }
  const drawMeasure = () => {
    const W = content.clientWidth, H = content.clientHeight;
    msvg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    msvg.innerHTML = '';
    const P = mpts.map(([fx, fy]) => [fx * W, fy * H]);
    for (const [x, y] of P) {
      const c = document.createElementNS(NS, 'circle');
      Object.entries({ cx: x, cy: y, r: 3 / z, fill: '#39d0d8' }).forEach(([k, v]) => c.setAttribute(k, v));
      msvg.appendChild(c);
    }
    if (P.length === 2) {
      const l = document.createElementNS(NS, 'line');
      Object.entries({ x1: P[0][0], y1: P[0][1], x2: P[1][0], y2: P[1][1], stroke: '#39d0d8', 'stroke-width': 2 }).forEach(([k, v]) => l.setAttribute(k, v));
      msvg.appendChild(l);
      const [a, b] = mpts;
      const mm = Math.hypot((b[0] - a[0]) * mmAcross, (b[1] - a[1]) * mmAcross * (H / W));
      root.querySelector('.lb-measure').textContent = `📏 ${(+mm.toFixed(2))} mm  (Δx ${(+(Math.abs(b[0] - a[0]) * mmAcross).toFixed(2))}, Δy ${(+(Math.abs(b[1] - a[1]) * mmAcross * H / W).toFixed(2))})`;
    }
  };

  // the copy keeps the source's aspect ratio; it is laid out at a fitted width, then transformed
  const aspect = source.clientWidth / Math.max(1, source.clientHeight);
  let z = 1, pan = [0, 0], base = 1;
  const layout = () => {
    const W = stage.clientWidth, H = stage.clientHeight;
    base = Math.min((W - 24) / aspect, H - 24);
    Object.assign(content.style, { width: `${base * aspect}px`, height: `${base}px` });
    content.style.transform = `translate(${pan[0]}px, ${pan[1]}px) scale(${z})`;
    if (mpts.length) drawMeasure();
    root.querySelector('.lb-val').textContent = `${Math.round(z * 100)}%`;
  };
  const zoomAt = (f, cx, cy) => {
    const r = stage.getBoundingClientRect();
    const x = (cx ?? r.left + r.width / 2) - r.left - r.width / 2, y = (cy ?? r.top + r.height / 2) - r.top - r.height / 2;
    const nz = Math.min(30, Math.max(0.5, z * f));
    // keep the point under the cursor in place (content is centred, transform origin = centre)
    pan = [x - ((x - pan[0]) / z) * nz, y - ((y - pan[1]) / z) * nz];
    z = nz;
    layout();
  };
  const fit = () => { z = 1; pan = [0, 0]; layout(); };
  const ro = new ResizeObserver(layout);
  ro.observe(stage);
  stage.addEventListener('wheel', (e) => { e.preventDefault(); zoomAt(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)), e.clientX, e.clientY); }, { passive: false });
  let drag = null;
  stage.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    if (measuring && e.button === 0) {
      const r = content.getBoundingClientRect();
      const pt = [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height];
      mpts = mpts.length === 1 ? [mpts[0], pt] : [pt];
      drawMeasure();
      return;
    }
    drag = { from: [e.clientX, e.clientY], pan0: [...pan] };
    stage.setPointerCapture(e.pointerId);
    stage.classList.add('panning');
  });
  stage.addEventListener('pointermove', (e) => {
    if (!drag) return;
    pan = [drag.pan0[0] + e.clientX - drag.from[0], drag.pan0[1] + e.clientY - drag.from[1]];
    layout();
  });
  const up = () => { drag = null; stage.classList.remove('panning'); };
  stage.addEventListener('pointerup', up);
  stage.addEventListener('pointercancel', up);
  stage.addEventListener('dblclick', fit);
  stage.addEventListener('dragstart', (e) => e.preventDefault());
  root.querySelector('.lb-in').addEventListener('click', () => zoomAt(1.5));
  root.querySelector('.lb-out').addEventListener('click', () => zoomAt(1 / 1.5));
  root.querySelector('.lb-fit').addEventListener('click', fit);

  const onKey = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); close(); }
    else if (e.key === '+' || e.key === '=') zoomAt(1.5);
    else if (e.key === '-') zoomAt(1 / 1.5);
    else if (e.key === '0') fit();
  };
  window.addEventListener('keydown', onKey, true);
  root.querySelector('.lb-x').addEventListener('click', close);
  root.addEventListener('pointerdown', (e) => { if (e.target === root) close(); });
  function close() {
    ro.disconnect();
    window.removeEventListener('keydown', onKey, true);
    root.remove();
  }
  layout();
  return { close, zoomAt, get zoom() { return z; } };
}
