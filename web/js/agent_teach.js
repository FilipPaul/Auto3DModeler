// The AI teaching the user (tool gui_highlight): a pulsing ring around a control (or a spot of the view) with a
// speech-bubble tip, the rest of the screen dimmed lightly. It never blocks anything: the ring and the dimming let
// every click through. It stays until the user clicks the highlighted thing, presses Escape or ✕, or the AI shows
// the next one (or clears it); with wait the tool answers when the user did it, so the AI can lead step by step.
import { guiControls } from './agent_more.js';

const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const PAD = 5, SPOT = 26;            // px around a control; a view spot's ring radius
const WAIT_S = 60, MAX_WAIT_S = 120; // wait: how long by default / at most (a tool call may take 140 s)

function viewEl() { return [...document.querySelectorAll('section.viewport')].find((v) => v.offsetParent && v.getBoundingClientRect().width > 0); }

/** A control on screen by its n or label (as gui_action finds it). */
function findControl(control) {
  const list = guiControls('all'), want = String(control).trim().toLowerCase();
  return list.find((x) => String(x.n) === want) || list.find((x) => x.label.toLowerCase() === want) || list.find((x) => x.label.toLowerCase().includes(want))
    || list.find((x) => (x.title || '').toLowerCase().includes(want));
}

export function teachHandlers() {
  let cur = null;   // the tip shown: {ring, tip, target, done (a promise of the outcome), finish(outcome), …}
  let last = null;  // what happened to the previous tip, for the AI

  const close = (outcome) => { if (cur) cur.finish(outcome); };

  /** Show a tip at a control ({el, label}) or a spot of the view ([x, y] 0 … 1). */
  function show({ c, at, text, step }) {
    const ring = document.createElement('div'), tip = document.createElement('div');
    ring.className = `teach-ring${at ? ' spot' : ''}`;
    tip.className = 'teach-tip';
    tip.innerHTML = `<div class="teach-head">${step ? `<span class="teach-step" data-no-i18n>${escapeHtml(step)}</span>` : ''}<span class="teach-who">✨ AI</span>
      <button type="button" class="teach-x" title="Close the tip (Esc)">✕</button></div><div class="teach-text" data-no-i18n>${escapeHtml(text || '')}</div>`;
    document.body.append(ring, tip);
    let el = c?.el || null, label = c?.label || '', raf = 0, lost = 0;
    const box = () => {
      if (at) {
        const v = viewEl()?.getBoundingClientRect();
        if (!v) return null;
        const x = v.left + at[0] * v.width, y = v.top + at[1] * v.height;
        return { left: x - SPOT, top: y - SPOT, width: 2 * SPOT, height: 2 * SPOT };
      }
      if (!el?.isConnected && Date.now() - lost > 400) { // (the panel was drawn anew: the same control again)
        lost = Date.now();
        el = label ? findControl(label)?.el || null : null;
      }
      const r = el?.isConnected ? el.getBoundingClientRect() : null;
      return r && r.width ? { left: r.left - PAD, top: r.top - PAD, width: r.width + 2 * PAD, height: r.height + 2 * PAD } : null;
    };
    const place = () => {
      const r = box();
      ring.hidden = !r;
      const tw = tip.offsetWidth, th = tip.offsetHeight, W = innerWidth, H = innerHeight;
      if (r) {
        Object.assign(ring.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
        const below = r.top + r.height + 12 + th < H, x = Math.max(8, Math.min(W - tw - 8, r.left + r.width / 2 - tw / 2));
        tip.classList.toggle('above', !below);
        Object.assign(tip.style, { left: `${x}px`, top: `${below ? r.top + r.height + 12 : Math.max(8, r.top - th - 12)}px` });
        tip.style.setProperty('--arrow', `${Math.max(14, Math.min(tw - 14, r.left + r.width / 2 - x))}px`);
      } else Object.assign(tip.style, { left: `${(W - tw) / 2}px`, top: '64px' }); // (the control went away: the tip stays in sight)
      raf = requestAnimationFrame(place);
    };
    const hit = (e) => {
      if (tip.contains(e.target)) return false;
      if (at) { const r = box(); return r && Math.hypot(e.clientX - (r.left + SPOT), e.clientY - (r.top + SPOT)) <= SPOT + 6; }
      if (!el) return false;
      if (el.contains(e.target)) return true;
      const r = el.getBoundingClientRect(); // (something drawn over it, e.g. a label: where the press was)
      return !!(e.clientX || e.clientY) && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    };
    const onPress = (e) => { if (hit(e)) finish('clicked'); };
    const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish('closed'); } };
    let resolve;
    const done = new Promise((r) => { resolve = r; });
    const t = { ring, tip, done, what: at ? `the spot [${at.map((v) => +(+v).toFixed(3)).join(', ')}] of the view` : `“${label}”`, finish: null };
    function finish(outcome) {
      if (t.ended) return;
      t.ended = outcome;
      cancelAnimationFrame(raf);
      removeEventListener('pointerdown', onPress, true);
      removeEventListener('click', onPress, true);
      removeEventListener('keydown', onKey, true);
      ring.remove();
      tip.remove();
      if (cur === t) cur = null;
      last = { what: t.what, outcome };
      resolve(outcome);
    }
    t.finish = finish;
    tip.querySelector('.teach-x').addEventListener('click', () => finish('closed'));
    addEventListener('pointerdown', onPress, true); // (capture: seen first, never stopped — the click goes on to the control)
    addEventListener('click', onPress, true);       // (a click by the keyboard, or a control drawn anew on pointerdown)
    addEventListener('keydown', onKey, true);
    el?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
    place();
    cur = t;
    return t;
  }

  const said = { clicked: 'the user clicked it', closed: 'the user closed the tip (Esc / ✕) without clicking it', replaced: 'replaced by the next tip', cleared: 'cleared' };
  const lastLine = () => (last ? `Before: ${last.what} — ${said[last.outcome] || last.outcome}.` : '');

  return {
    gui_highlight: async ({ control, at, text = '', step, wait = false, timeout = WAIT_S, clear = false } = {}) => {
      if (clear) {
        const had = cur?.what;
        close('cleared');
        return { text: had ? `Removed the tip at ${had}.` : `No tip was shown. ${lastLine()}`.trim() };
      }
      const hasControl = control !== undefined && control !== null && control !== '';
      if (!hasControl && !at) throw new Error('control (its n or label from gui_state) or at = [x, y] (0 … 1 across and down the view), and text — or clear: true.');
      if (!String(text).trim()) throw new Error('text: a short tip for the user (what to do there), in their language.');
      let c = null;
      if (hasControl) {
        c = findControl(control);
        if (!c) throw new Error(`No control “${control}” on screen — gui_state lists what is shown (a control in a closed menu or panel: highlight what opens it first).`);
      } else if (!Array.isArray(at) || at.length !== 2 || !at.every((v) => Number.isFinite(+v))) throw new Error('at: [x, y], 0 … 1 across and down the view.');
      else if (!viewEl()) throw new Error('No view on screen for at.');
      close('replaced');
      const before = lastLine();
      const t = show({ c, at: at ? at.map(Number) : null, text: String(text).slice(0, 300), step: step !== undefined && step !== null && step !== '' ? String(step).slice(0, 12) : '' });
      const where = `${t.what}${c?.disabled ? ' (it is greyed out now — say what makes it usable)' : ''}`;
      if (!wait) return { text: `Shown at ${where} with your tip; it stays until the user clicks it, presses Esc or you show the next one. ${before}`.trim() };
      const s = Math.max(1, Math.min(MAX_WAIT_S, +timeout || WAIT_S));
      const outcome = await Promise.race([t.done, new Promise((r) => { setTimeout(() => r('timeout'), s * 1000); })]);
      if (outcome === 'clicked') return { text: `Done: the user clicked ${t.what} — the tip is gone. Look at what changed (gui_state / get_screenshot), then show the next step.` };
      if (outcome === 'closed') return { text: `The user closed the tip at ${t.what} (Esc / ✕) without clicking it — ask whether they want to go on.` };
      if (outcome === 'timeout') return { text: `The user has not clicked ${t.what} in ${s} s — the tip is still shown. Wait again (gui_highlight with the same control and wait), explain it another way, or clear it.` };
      return { text: `The tip at ${t.what} was ${said[outcome] || outcome}.` };
    },
  };
}
