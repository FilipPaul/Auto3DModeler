// Waiting for the page's next frames. A hidden or covered window gets no animation frames at all, so a plain
// `await requestAnimationFrame` there never ends (an AI tool call that waits for one hangs, and the app stops
// answering the AI) — this one also ends after `ms` by the clock.

/** Resolves after `n` animation frames, or after `ms` milliseconds when the page gets no frames. */
export function nextFrames(n = 2, ms = 120) {
  return new Promise((done) => {
    let left = n, over = false;
    const end = () => { if (!over) { over = true; clearTimeout(timer); done(); } };
    const timer = setTimeout(end, ms);
    const tick = () => { if (over) return; if (--left <= 0) end(); else requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}
