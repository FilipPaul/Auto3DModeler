// 🎬 Save animation (⚙ Mechanism ⋯): one full cycle of a mechanism's driver — a full turn, else there and back, at the
// speed ▶ plays it — from the view as it is, saved and downloaded: a looping GIF (default: plays everywhere, phones too;
// the frames are drawn here and made into one GIF by the server — auto3d/animation.py, a job of the ⚙ list) or a video
// the browser records itself (MediaRecorder: MP4 where it can, else WebM). The 3D only — no labels, sizes or marks —
// with the mechanism's name as a small caption if wanted, at most 1280 px across. A progress line in the row with
// Cancel; a frame at a time, so the page stays responsive. The parts end where they were.
import { t } from '../i18n.js';
import { newRid, cancelRid } from '../progressbox.js';
import { driveTo, posOf } from './mechanism.js';

const GIF_FPS = 20, VIDEO_FPS = 25, MAX_W = 1280;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const mb = (b) => (b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);
const tick = () => new Promise((ok) => setTimeout(ok, 0));

/** The video this browser can record from a canvas -> {mime, ext} (MP4 first: phones play it), or null. */
export function videoKind() {
  const MR = window.MediaRecorder;
  if (!MR || !HTMLCanvasElement.prototype.captureStream) return null;
  for (const [mime, ext] of [['video/mp4;codecs=avc1', 'mp4'], ['video/mp4', 'mp4'], ['video/webm;codecs=vp9', 'webm'], ['video/webm;codecs=vp8', 'webm'], ['video/webm', 'webm']]) {
    try { if (MR.isTypeSupported(mime)) return { mime, ext }; } catch { /* (an old browser) */ }
  }
  return null;
}

/** The driver's places over one cycle, a frame each at fps: a full turn round from where it is, else there and back
 *  as ▶ plays it (back at a dead point / an end) — a generator, the parts moved to each as it goes. */
function* cycle(asm, m, fps) {
  const n = Math.max(24, Math.min(400, Math.round((4 * fps) / (m.speed || 1)))), p0 = posOf(asm, m);
  if (m.full) {
    for (let k = 0; k < n; k++) { driveTo(asm, m, (((p0 + (360 * k) / n) % 360) + 360) % 360); yield { k, n }; }
    return;
  }
  const step = ((m.max - m.min) * 2) / n;
  let v = p0, dir = 1;
  for (let k = 0; k < n; k++) {
    if (k) {
      v += dir * step;
      if (v >= m.max) { v = m.max; dir = -1; } else if (v <= m.min) { v = m.min; dir = 1; }
      const r = driveTo(asm, m, v);
      if (r.stopped) { dir = -dir; v = r.at; }
    }
    yield { k, n };
  }
}

/** The picture size: the view's shape, at most 1280 px across (even numbers: a video wants them). */
function frameSize(asm) {
  const el = asm.view.container, cw = el.clientWidth || 1200, ch = el.clientHeight || 900;
  const w = Math.min(MAX_W, cw) & ~1;
  return { w, h: Math.round((w * ch) / cw) & ~1 };
}

/** A frame of the view as it is (fit: false — the user's view), with the caption in its bottom left corner. */
function frame(asm, w, h, caption) {
  return asm.view.snapshot({ w, h, fit: false, over: caption ? (ctx) => {
    const fs = Math.max(12, Math.round(w / 64)), pad = Math.round(fs * 0.6);
    ctx.font = `600 ${fs}px system-ui, "Segoe UI", sans-serif`;
    const tw = ctx.measureText(caption).width;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    ctx.fillRect(pad, h - pad - fs * 1.6, tw + fs, fs * 1.6);
    ctx.fillStyle = '#f0f3f6';
    ctx.textBaseline = 'middle';
    ctx.fillText(caption, pad + fs / 2, h - pad - fs * 0.8);
  } : null });
}

const toBlob = (c) => new Promise((ok, bad) => c.toBlob((b) => (b ? ok(b) : bad(new Error('The frame could not be drawn.'))), 'image/png'));
async function answer(r) {
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

/** One cycle of mechanism m recorded -> {file, path, url, bytes, frames, width, height, format} (null: cancelled).
 *  format 'gif' | 'video'; caption: the mechanism's name on it; job: {cancel} (set it to stop), onProgress(stage, done,
 *  total); download: the file downloaded too. */
export async function recordAnimation(asm, m, { format = 'gif', caption = true, job = {}, onProgress = () => {}, download = true } = {}) {
  const video = format === 'video' ? videoKind() : null;
  if (format === 'video' && !video) throw new Error(t('This browser cannot record a video — save a GIF.'));
  const { w, h } = frameSize(asm), aid = newRid('a'), fps = video ? VIDEO_FPS : GIF_FPS, cap = caption ? m.name : null;
  const snap = asm.doc.instances.map((x) => [x.id, [...x.matrix], structuredClone(x.hang)]);
  const gone = () => job.cancel || !document.body.classList.contains('ws-assembly') || asm.active === false;
  const sent = []; // (frames on their way)
  let rec = null, chunks = [], ctx = null, track = null, res = null, frames = 0;
  try {
    if (video) {
      const c = document.createElement('canvas');
      Object.assign(c, { width: w, height: h });
      ctx = c.getContext('2d');
      const stream = c.captureStream(0);
      track = stream.getVideoTracks()[0];
      rec = new MediaRecorder(stream, { mimeType: video.mime, videoBitsPerSecond: 8e6 });
      rec.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data); };
      rec.start();
    }
    const t0 = performance.now();
    for (const { k, n } of cycle(asm, m, fps)) {
      if (gone()) return null;
      const c = frame(asm, w, h, cap);
      if (video) {
        ctx.drawImage(c, 0, 0);
        track.requestFrame?.();
        const wait = t0 + ((k + 1) * 1000) / fps - performance.now(); // (the video's clock: a frame each 1/fps s)
        await new Promise((ok) => setTimeout(ok, Math.max(0, wait)));
      } else {
        const b = await toBlob(c);
        sent.push(fetch(`/api/anim/${aid}/frame/${k}`, { method: 'POST', headers: { 'Content-Type': 'image/png' }, body: b }).then(answer));
        if (sent.length >= 4) await sent.shift(); // (a few on their way at once)
        await tick();
      }
      frames = k + 1;
      onProgress('Recording', k + 1, n);
    }
    if (gone()) return null;
    if (video) {
      const done = new Promise((ok) => { rec.onstop = ok; });
      rec.stop();
      await done;
      rec = null;
      onProgress('Saving the video', 0, 0);
      const blob = new Blob(chunks, { type: video.mime.split(';')[0] });
      res = await answer(await fetch(`/api/anim/${aid}/video/${video.ext}?name=${encodeURIComponent(m.name)}`, { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob }));
      Object.assign(res, { frames, width: w, height: h, fps, format: video.ext });
    } else {
      await Promise.all(sent);
      const rid = job.rid = newRid('anim');
      onProgress('Making the GIF', 0, 0);
      let polling = true;
      (async () => { // (the server's progress: "Making the GIF 12 / 80")
        while (polling) {
          await new Promise((ok) => setTimeout(ok, 300));
          try { const st = await (await fetch(`/api/progress/${rid}`)).json(); if (polling && st.stage && st.total) onProgress(st.stage, st.done + 1, st.total); } catch { /* the next */ }
        }
      })();
      try {
        res = await answer(await fetch(`/api/anim/${aid}/gif`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: m.name, fps, rid }) }));
      } finally { polling = false; }
      if (res.cancelled) return null;
      res.format = 'gif';
    }
  } finally {
    if (rec && rec.state !== 'inactive') try { rec.stop(); } catch { /* (gone) */ }
    if (!res) Promise.allSettled(sent).then(() => fetch(`/api/anim/${aid}`, { method: 'DELETE' })).catch(() => {}); // (after the last frame got there)
    for (const [iid, mat, hang] of snap) { const x = asm.inst(iid); if (x) { x.matrix = mat; x.hang = hang; } }
    asm.checkJoints();
    asm.draw();
  }
  if (download) {
    const a = document.createElement('a');
    a.href = res.url;
    a.download = res.file;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  return res;
}

/** The 🎬 line of a mechanism's ⋯ (panel: its MechanismPanel): the choice GIF / video, the caption, 🎬 Save animation —
 *  while it records, its progress and Cancel; after, what was saved. */
export function animHtml(panel, m, k) {
  const a = panel.anim || (panel.anim = { format: 'gif', caption: true, notes: {} }), vk = videoKind(), mine = a.job?.key === m.key;
  const note = a.notes[m.key];
  return `<div class="mc-acts mc-anim">
      <button class="btn small" data-mcanim="${k}" ${a.job ? 'disabled' : ''} title="${esc(t('Record one full cycle of it from this view and download it'))}">${esc(t('🎬 Save animation'))}</button>
      <select data-mcafmt="${k}" title="${esc(t('GIF plays everywhere (phones too); a video is smaller and smoother'))}"><option value="gif">GIF</option>${vk
        ? `<option value="video" ${a.format === 'video' ? 'selected' : ''}>${esc(t('Video'))} (${vk.ext.toUpperCase()})</option>` : ''}</select>
      <label class="mc-cap" title="${esc(t('The mechanism\'s name in a corner of the picture'))}"><input type="checkbox" data-mcacap="${k}" ${a.caption ? 'checked' : ''}> ${esc(t('Name'))}</label></div>
    ${mine ? `<p class="mp-count as-dofnote mc-anote" data-no-i18n><span class="mc-astage">${esc(stageText(a.job))}</span> <button class="btn small" data-mcacancel>${esc(t('Cancel'))}</button></p>`
      : note ? `<p class="mp-count as-dofnote ${note.bad ? 'bad' : ''}" data-no-i18n>${esc(noteText(note))}</p>` : ''}`;
}

const noteText = (x) => (x.msg ? t2(x.msg, x.vars || {}) : x.text); // (in the language on screen when drawn)
const stageText = (j) => `🎬 ${t(j.stage || 'Recording')}${j.total ? ` ${j.done} / ${j.total}` : '…'}`;

/** The 🎬 line's handlers (after MechanismPanel.draw); while it records, the row's other controls wait. */
export function bindAnim(panel) {
  const box = panel.box, a = panel.anim;
  if (!a) return;
  for (const s of box.querySelectorAll('[data-mcafmt]')) s.addEventListener('change', () => { a.format = s.value; });
  for (const c of box.querySelectorAll('[data-mcacap]')) c.addEventListener('change', () => { a.caption = c.checked; });
  for (const b of box.querySelectorAll('[data-mcanim]')) b.addEventListener('click', () => saveAnimation(panel, panel.list[+b.dataset.mcanim]).catch(() => {}));
  box.querySelector('[data-mcacancel]')?.addEventListener('click', () => cancelAnimation(panel));
  const row = a.job && box.querySelector(`[data-mckey="${CSS.escape(a.job.key)}"]`);
  if (row) for (const el of row.querySelectorAll('input, select, button:not([data-mcacancel])')) el.disabled = true;
}

/** 🎬 Save animation of mechanism m with the row's choices (opts: the AI's) -> what was saved (null: cancelled). */
export async function saveAnimation(panel, m, opts = {}) {
  const a = panel.anim || (panel.anim = { format: 'gif', caption: true, notes: {} });
  if (a.job) throw new Error(t('An animation is being recorded — wait for it or cancel it.'));
  if (!m?.closed || !m.driver) throw new Error(t('This mechanism cannot move here.'));
  panel.stop(false);
  const job = a.job = { key: m.key, name: m.name, stage: 'Recording', done: 0, total: 0, cancel: false };
  delete a.notes[m.key];
  panel.more.add(m.key);
  panel.draw();
  const show = (stage, done, total) => {
    Object.assign(job, { stage, done, total });
    const el = panel.box.querySelector('.mc-astage');
    if (el) el.textContent = stageText(job);
  };
  try {
    const r = await recordAnimation(panel.asm, m, { format: opts.format || a.format, caption: opts.caption ?? a.caption, job, onProgress: show, download: opts.download ?? true });
    a.notes[m.key] = r ? { msg: '🎬 Saved: {file} ({n} frames, {size})', vars: { file: r.file, n: r.frames, size: mb(r.bytes) }, file: r } : { msg: '🎬 Cancelled.' };
    return r;
  } catch (e) {
    a.notes[m.key] = { text: `🎬 ${e.message}`, bad: true };
    throw e;
  } finally {
    a.job = null;
    panel.render();
  }
}

/** Cancel: the recording stops at its next frame (the GIF being made: its server job too). */
export function cancelAnimation(panel) {
  const j = panel.anim?.job;
  if (!j) return false;
  j.cancel = true;
  if (j.rid) cancelRid(j.rid);
  return true;
}

/** For the AI (gui_state): the recording under way, or the last one saved. */
export function animState(panel) {
  const a = panel?.anim;
  if (!a) return null;
  if (a.job) return { recording: a.job.name, stage: a.job.stage, done: a.job.done, total: a.job.total };
  const last = Object.values(a.notes).map((x) => x.file).filter(Boolean).pop();
  return last ? { saved: last.file, path: last.path, frames: last.frames, format: last.format } : null;
}
