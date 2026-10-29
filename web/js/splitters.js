// Panels you can make wider or narrower: drag the edge between a side panel and the view (or the AI chat's left
// edge). The widths are CSS variables on <html>, the same for every workspace, and remembered; double-click an edge
// for the usual width again.
import { t } from './i18n.js';

const KEY = 'a3d.panels';
const SIDES = {
  left: { prop: '--left-w', def: 340, min: 200 },
  right: { prop: '--right-w', def: 310, min: 220 },
  chat: { prop: '--chat-w', def: 440, min: 300 },
};

function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } }
function save(w) { try { localStorage.setItem(KEY, JSON.stringify(w)); } catch { /* ignore */ } }
let resetSide = null; // (initSplitters: a panel back to its usual width)

/** A panel back to its usual width (↺ Default layout). */
export function resetWidth(side) { resetSide?.(side); }

/** layout: the main grid; drawer: the AI chat drawer. */
export function initSplitters(layout, drawer) {
  const root = document.documentElement, widths = load();
  const max = (side) => Math.max(SIDES[side].min, Math.round(window.innerWidth * (side === 'chat' ? 0.6 : 0.45)));
  const apply = (side, w) => {
    if (w === undefined) { root.style.removeProperty(SIDES[side].prop); return; }
    root.style.setProperty(SIDES[side].prop, `${Math.min(max(side), Math.max(SIDES[side].min, Math.round(w)))}px`);
  };
  for (const side of Object.keys(SIDES)) apply(side, widths[side]);
  const current = (side) => parseFloat(getComputedStyle(root).getPropertyValue(SIDES[side].prop)) || SIDES[side].def;

  const handle = (side, parent) => {
    const h = document.createElement('div');
    h.className = `splitter split-${side}`;
    h.title = t('Drag to make the panel wider or narrower — double-click for the usual width');
    h.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      h.setPointerCapture(e.pointerId);
      const x0 = e.clientX, w0 = current(side), dir = side === 'left' ? 1 : -1;
      document.body.classList.add('resizing');
      h.classList.add('on');
      const move = (ev) => apply(side, w0 + dir * (ev.clientX - x0));
      const up = () => {
        h.removeEventListener('pointermove', move);
        document.body.classList.remove('resizing');
        h.classList.remove('on');
        widths[side] = current(side);
        save(widths);
      };
      h.addEventListener('pointermove', move);
      h.addEventListener('pointerup', up, { once: true });
      h.addEventListener('pointercancel', up, { once: true });
    });
    h.addEventListener('dblclick', () => resetSide(side));
    parent.appendChild(h);
    return h;
  };
  resetSide = (side) => { delete widths[side]; save(widths); apply(side, undefined); };
  handle('left', layout);
  handle('right', layout);
  if (drawer) handle('chat', drawer);
  // a smaller window: the panels stay within their limits
  window.addEventListener('resize', () => { for (const side of Object.keys(SIDES)) if (widths[side] !== undefined) apply(side, widths[side]); });
}
