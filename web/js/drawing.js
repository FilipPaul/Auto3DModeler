// The original PDF page with an overlay of what the parser recognised.
const NS = 'http://www.w3.org/2000/svg';

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent?.appendChild(e);
  return e;
}

export class DrawingView {
  constructor(wrap) {
    this.wrap = wrap;
  }

  show(preview, model, statusOf) {
    this.wrap.innerHTML = '';
    const img = new Image();
    img.src = `data:image/png;base64,${preview.png}`;
    this.wrap.appendChild(img);

    // crop the view to the interesting part of the page
    const pts = [];
    for (const v of model.vertices) pts.push(v.draw);
    for (const p of model.params) {
      for (const t of p.draw?.tips || []) pts.push(t);
      const b = p.draw?.text_bbox;
      if (b) pts.push([b[0], b[1]], [b[2], b[3]]);
    }
    for (const i of model.issues) {
      for (const pt of i.draw?.points || []) pts.push(pt);
      const b = i.draw?.text_bbox;
      if (b) pts.push([b[0], b[1]], [b[2], b[3]]);
    }
    let [x0, y0, x1, y1] = [0, 0, preview.width, preview.height];
    if (pts.length) {
      x0 = Math.min(...pts.map((p) => p[0])); x1 = Math.max(...pts.map((p) => p[0]));
      y0 = Math.min(...pts.map((p) => p[1])); y1 = Math.max(...pts.map((p) => p[1]));
      const pad = Math.max(x1 - x0, y1 - y0) * 0.06 + 6;
      x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
      x1 = Math.min(preview.width, x1 + pad); y1 = Math.min(preview.height, y1 + pad);
    }
    const cw = x1 - x0, ch = y1 - y0;
    // emulate the crop with an inner container scaled so that the crop fills the width
    const inner = document.createElement('div');
    inner.style.cssText = `position:relative;width:${(preview.width / cw) * 100}%;margin-left:${(-x0 / cw) * 100}%;margin-top:${(-y0 / cw) * 100}%`;
    this.wrap.style.aspectRatio = `${cw} / ${ch}`;
    img.remove();
    inner.appendChild(img);
    this.wrap.appendChild(inner);

    const svg = el('svg', { viewBox: `0 0 ${preview.width} ${preview.height}`, preserveAspectRatio: 'none' }, inner);
    this.svg = svg;
    const lw = Math.max(cw, ch) / 300;

    for (const loop of model.loops) {
      const p = loop.vertices.map((id) => model.vertices[id].draw.join(',')).join(' ');
      el('polygon', { points: p, fill: loop.kind === 'hole' ? '#3fb95018' : '#3fb95010', stroke: '#3fb950', 'stroke-width': lw * 1.6, 'stroke-opacity': 0.9 }, svg);
    }

    this.paramEls = {};
    const colors = { drawing: '#1f6feb', estimated: '#d4a72c', default: '#d4a72c', user: '#8250df', reference: '#6e7781', conflict: '#f85149' };
    for (const p of model.params) {
      if (p.kind !== 'linear' || p.source === 'aligned') continue;
      const g = el('g', { 'data-param': p.id, cursor: 'pointer' }, svg);
      const st = statusOf(p.id);
      const c = colors[st] || colors.drawing;
      if (p.draw?.tips) {
        const [a, b] = p.draw.tips;
        el('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: c, 'stroke-width': lw * 1.8 }, g);
        for (const t of [a, b]) el('circle', { cx: t[0], cy: t[1], r: lw * 2.2, fill: c }, g);
        const tb = p.draw.text_bbox;
        if (tb) el('rect', { x: tb[0] - lw, y: tb[1] - lw, width: tb[2] - tb[0] + 2 * lw, height: tb[3] - tb[1] + 2 * lw, fill: 'none', stroke: c, 'stroke-width': lw, rx: lw * 2 }, g);
      } else {
        // undimensioned relation: dashed line between the two levels
        const lv = (id) => model.levels[id[0]].find((l) => l.id === id);
        const vs = model.vertices.filter((v) => v[p.axis] === p.lo || v[p.axis] === p.hi);
        if (!vs.length) continue;
        const lat = p.axis === 'x' ? Math.min(...vs.map((v) => v.draw[1])) - 8 * lw : Math.max(...vs.map((v) => v.draw[0])) + 8 * lw;
        const a = lv(p.lo).draw, b = lv(p.hi).draw;
        const [x1_, y1_, x2_, y2_] = p.axis === 'x' ? [a, lat, b, lat] : [lat, a, lat, b];
        el('line', { x1: x1_, y1: y1_, x2: x2_, y2: y2_, stroke: c, 'stroke-width': lw * 1.8, 'stroke-dasharray': `${lw * 4} ${lw * 3}` }, g);
        const t = el('text', { x: (x1_ + x2_) / 2, y: (y1_ + y2_) / 2 - lw * 3, fill: c, 'font-size': lw * 9, 'text-anchor': 'middle', 'font-family': 'Segoe UI, sans-serif', 'font-weight': 700 }, g);
        t.textContent = st === 'user' ? '✓ set' : '? missing';
      }
      el('title', {}, g).textContent = p.name;
      this.paramEls[p.id] = g;
    }

    this.issueEls = [];
    model.issues.forEach((iss, idx) => {
      const d = iss.draw;
      if (!d) return;
      const c = iss.severity === 'error' ? '#f85149' : iss.severity === 'warning' ? '#d4a72c' : '#1f6feb';
      const g = el('g', { 'data-issue': idx }, svg);
      if (iss.severity !== 'info' || iss.code === 'snapped_dimension') {
        for (const pt of d.points || []) el('circle', { cx: pt[0], cy: pt[1], r: lw * 5, fill: 'none', stroke: c, 'stroke-width': lw * 1.5 }, g);
        const b = d.text_bbox;
        if (b && !iss.params.length) el('rect', { x: b[0] - 2 * lw, y: b[1] - 2 * lw, width: b[2] - b[0] + 4 * lw, height: b[3] - b[1] + 4 * lw, fill: `${c}22`, stroke: c, 'stroke-width': lw * 1.4, 'stroke-dasharray': `${lw * 3} ${lw * 2}` }, g);
      }
      this.issueEls[idx] = g;
    });
  }

  flashParam(id) { this.flash(this.paramEls?.[id]); }

  flashIssue(idx) { this.flash(this.issueEls?.[idx]); }

  flash(g) {
    if (!g) return;
    g.classList.remove('flash');
    void g.getBBox();
    g.classList.add('flash');
  }

  highlight(id, on) {
    const g = this.paramEls?.[id];
    if (g) g.style.filter = on ? 'drop-shadow(0 0 2px #1f6feb)' : '';
  }
}
