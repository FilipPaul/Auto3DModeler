// ⚙ N in the top bar: what is working now — the kernel's jobs waiting or running (all windows' and the AI's, from
// GET /api/jobs) and this page's own requests still on their way (an upload) — nothing when idle. A click lists them:
// what · which part · how long (live) · ✕ Stop. A job working over 3 s with no progress box on screen makes the ⚙
// pulse, so a busy app does not look frozen. Polled every second while something runs, every 4 s when idle.
import { t } from './i18n.js';
import { cancelRid } from './progressbox.js';

const SKIP = /\/api\/(progress|jobs|agent|projects|chat|kernel|title-templates|printers|joints|library|windows)/; // (quick or long-polled)
const URL_KINDS = [[/\/api\/(model\/)?import\/assembly/, 'Reading an assembly'], [/\/api\/(model\/)?import/, 'Importing a file'],
  [/\/api\/solve/, 'Building a quick part'], [/\/api\/model\/rebuild/, 'Building a part'], [/\/api\/sheet\/(build|assembly)/, 'Making a drawing'],
  [/\/api\/assembly\/clashes/, 'Checking collisions'], [/\/api\/print\/plan/, 'Splitting for print'], [/export|\/api\/sheet\/pdf/, 'Exporting']];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const pending = new Map(); // this page's request id -> {url, kind, rid, at, abort}
const PAGE = Math.random().toString(36).slice(2, 8); // (this page's requests: "<PAGE>-<n>")
let jobs = [], fetched = 0, timer = null, n = 0, drawn = '';
let els = null, tabName = () => '';

/** fetch, with each slow request marked (X-A3D-Req: matched with the server's job; X-A3D-Tab: the part on screen). */
function wrapFetch() {
  const base = window.fetch.bind(window);
  window.fetch = (url, opts = {}) => {
    const u = String(url?.url || url);
    if (!/\/api\//.test(u) || SKIP.test(u) || (opts.method || 'GET').toUpperCase() === 'GET') return base(url, opts);
    const id = `${PAGE}-${++n}`, abort = opts.signal ? null : new AbortController();
    let rid = null;
    try { rid = opts.body instanceof FormData ? opts.body.get('rid') : typeof opts.body === 'string' && opts.body.includes('"rid"') ? JSON.parse(opts.body).rid : null; } catch { /* not JSON */ }
    const headers = new Headers(opts.headers || {});
    headers.set('X-A3D-Req', id);
    let tab = '';
    try { tab = tabName() || ''; } catch { /* (the page still starting) */ }
    headers.set('X-A3D-Tab', encodeURIComponent(tab));
    pending.set(id, { url: u, kind: URL_KINDS.find(([re]) => re.test(u))?.[1] || 'Working', what: (opts.body instanceof FormData && opts.body.get('file')?.name) || tab, rid, at: performance.now(), abort });
    soon();
    return base(url, { ...opts, headers, ...(abort ? { signal: abort.signal } : {}) }).finally(() => { pending.delete(id); show(); });
  };
}

function soon(ms = 600) { clearTimeout(timer); timer = setTimeout(poll, ms); }

async function poll() {
  clearTimeout(timer);
  try {
    const r = await (await fetch('/api/jobs')).json();
    jobs = r.jobs || [];
    fetched = performance.now();
  } catch { /* the server restarting: keep the last list */ }
  show();
  timer = setTimeout(poll, jobs.length || pending.size ? 1000 : 4000);
}

/** The rows: the server's jobs, then this page's requests the server has no job for (yet). */
function rows() {
  const age = (performance.now() - fetched) / 1000, mine = new Set(jobs.map((j) => j.req).filter(Boolean));
  // (a request of this page that has ended: its job is gone, whatever the last poll said)
  const out = jobs.filter((j) => !j.req?.startsWith(`${PAGE}-`) || pending.has(j.req)).map((j) => ({ ...j, secs: j.elapsed + age }));
  for (const [id, p] of pending) {
    const secs = (performance.now() - p.at) / 1000;
    if (!mine.has(id) && secs > 0.5) out.push({ id, local: true, kind: p.kind, what: p.what, state: 'running', secs, rid: p.rid });
  }
  return out;
}

const secsText = (s) => (s < 60 ? `${Math.floor(s)} s` : `${Math.floor(s / 60)} min ${Math.floor(s % 60)} s`);
const timeText = (j) => `${j.state === 'waiting' ? `${t('waiting')} · ` : ''}${secsText(j.secs)}${j.total ? ` · ${j.done + 1} / ${j.total}` : ''}`;

/** Is a progress box on screen (the busy box, the 3D model's)? */
const progressShown = () => [...document.querySelectorAll('#busy, .m-busy')].some((b) => !b.hidden && b.getClientRects().length);

function show() {
  if (!els) return;
  const list = rows();
  els.btn.hidden = !list.length;
  els.btn.querySelector('b').textContent = String(list.length);
  els.btn.classList.toggle('pulse', list.some((j) => j.secs > 3) && !progressShown());
  if (!list.length) { els.list.hidden = true; drawn = ''; return; }
  if (els.list.hidden) { drawn = ''; return; }
  const key = list.map((j) => `${j.id}:${j.state}:${!!j.stopping}`).join('|');
  if (key === drawn) { // (the same jobs: only their times, so a click on ✕ Stop is not lost to a redraw)
    for (const j of list) { const el = els.list.querySelector(`[data-id="${CSS.escape(j.id)}"] .jobs-time`); if (el) el.textContent = timeText(j); }
    return;
  }
  drawn = key;
  els.list.innerHTML = `<div class="jobs-head">${esc(t('Working now'))}</div>${list.map((j) => `<div class="jobs-row" data-id="${esc(j.id)}">
      <span class="jobs-kind">${esc(t(j.kind))}</span><span class="jobs-what" data-no-i18n>${esc(j.what || '')}</span>
      <span class="jobs-time" data-no-i18n>${esc(timeText(j))}</span>
      <button class="mini" data-stop="${esc(j.id)}" ${j.stopping ? 'disabled' : ''} title="${esc(t('Stop this job (the part stays as it was)'))}">${esc(t(j.stopping ? 'Stopping…' : '✕ Stop'))}</button></div>`).join('')}`;
}

async function stop(id) {
  const local = pending.get(id), job = jobs.find((j) => j.id === id);
  if (local) { if (local.rid) cancelRid(local.rid); else local.abort?.abort(); return; }
  if (!job) return;
  job.stopping = true;
  if (job.rid) cancelRid(job.rid); // (its page's Cancel: that page says Cancelled and does not send it again)
  await fetch(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }).catch(() => {});
  soon(200);
}

/** Start: the ⚙ button and its list in the top bar (#jobsBtn, #jobsList); tab: the part on screen's name. */
export function initJobs(tab) {
  tabName = tab || tabName;
  els = { btn: document.getElementById('jobsBtn'), list: document.getElementById('jobsList') };
  wrapFetch();
  els.btn.addEventListener('click', (e) => { e.stopPropagation(); els.list.hidden = !els.list.hidden; show(); });
  els.list.addEventListener('click', (e) => { e.stopPropagation(); const b = e.target.closest('[data-stop]'); if (b) { b.disabled = true; stop(b.dataset.stop); } });
  document.addEventListener('click', () => { els.list.hidden = true; });
  setInterval(() => { if (!els.btn.hidden) show(); }, 1000); // (the times, live)
  poll();
}
