// The busy box: slow requests (an import, a sheet, a print split, an assembly's parts …) with their progress and ✕ Cancel.
// A request carries an id (rid); while it runs the box polls the server's progress for it. Several can run at once:
// the box shows the newest, Cancel stops them all. After Cancel the box says "Cancelling…" until they have ended
// (the polled stage no longer writes over it), then it is gone — the callers do not send the work again on their own.
// The box floats in the workspace on screen (it moves to that view's viewport when it shows).

const ops = new Map(); // rid -> {label, stage, cancelled}
let box = null, polling = false;
let sink = null; // the loading card (busy.js): takes the stage while it is up -> true

/** The loading card's hook: sink({text, frac, cancelling} | null) -> true when it shows them (the box stays hidden). */
export const setStageSink = (fn) => { sink = fn; };

export const newRid = (p = 'r') => `${p}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

/** The workspace's viewport on screen (the box goes there). */
function shownViewport() {
  return [...document.querySelectorAll('main .viewport')].find((v) => v.getClientRects().length) || null;
}

function el() {
  if (!box) {
    box = document.getElementById('busy');
    box.querySelector('.busy-cancel').addEventListener('click', cancelAll);
  }
  return box;
}

function show() {
  const b = el(), shown = [...ops.values()].filter((o) => o.shown);
  if (!shown.length) { b.hidden = true; sink?.(null); return; }
  const op = shown[shown.length - 1], cancelling = [...ops.values()].some((o) => o.cancelled);
  if (sink?.({ text: cancelling ? 'Cancelling…' : op.stage || null, frac: !cancelling && op.total ? (op.done + 1) / op.total : null, cancelling })) { b.hidden = true; return; }
  const vp = shownViewport();
  if (vp && b.parentElement !== vp) vp.appendChild(b);
  b.querySelector('.busy-text').textContent = cancelling ? 'Cancelling…' : op.stage || op.label;
  b.querySelector('.busy-cancel').disabled = cancelling;
  b.classList.toggle('indeterminate', cancelling || !op.total);
  if (!cancelling && op.total) b.querySelector('.busy-bar i').style.width = `${Math.round(((op.done + 1) / op.total) * 100)}%`;
  b.hidden = false;
}

async function poll() {
  if (polling) return;
  polling = true;
  while (ops.size) {
    const [rid, op] = [...ops.entries()].pop();
    if (!op.cancelled) {
      try {
        const st = await (await fetch(`/api/progress/${rid}`)).json();
        if (ops.get(rid) === op && !op.cancelled && st.stage) Object.assign(op, { stage: st.total ? `${st.stage} ${st.done + 1} / ${st.total}` : st.stage, done: st.done, total: st.total });
      } catch { /* keep the last status */ }
      show();
    }
    await new Promise((ok) => setTimeout(ok, 300));
  }
  polling = false;
}

/** Show the box for the request rid (label: what it does) -> stop() for when it has ended (done, failed or cancelled).
 *  delay (ms): shown only if it takes that long (quick ones do not flash it). */
export function trackProgress(rid, label, { delay = 0 } = {}) {
  const op = { label, stage: '', cancelled: false, shown: !delay };
  ops.set(rid, op);
  if (delay) setTimeout(() => { if (ops.get(rid) === op) { op.shown = true; show(); } }, delay);
  show();
  setTimeout(poll, 250);
  return () => {
    if (ops.get(rid) !== op) return;
    ops.delete(rid);
    show();
  };
}

const cancelledRids = new Set(); // (the last 200)
/** Whether rid was cancelled (its caller says "Cancelled" and does not try again). */
export const wasCancelled = (rid) => cancelledRids.has(rid);

/** Cancel one request (the server stops its kernel job: that process is killed and started again for the next one). */
export function cancelRid(rid) {
  const op = ops.get(rid);
  if (op) op.cancelled = true;
  cancelledRids.add(rid);
  if (cancelledRids.size > 200) cancelledRids.delete(cancelledRids.values().next().value);
  show();
  return fetch(`/api/progress/${rid}/cancel`, { method: 'POST' }).catch(() => {});
}

/** ✕ Cancel: everything the box is waiting for. */
export function cancelAll() {
  for (const [rid, op] of ops) if (!op.cancelled) cancelRid(rid);
}
