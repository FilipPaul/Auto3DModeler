// ⟳ New version in the top bar: the app server keeps running for hours while the checkout moves on (a merge, a
// pull) — then the server runs older Python than the files, and new AI tools answer "Unknown tool". GET /api/version
// says it (stale: the checkout's HEAD is not the commit the server started at); the page also keeps the commit it was
// loaded with (pageBuild — sent with the AI's polls, so a problem report says which page made it) and tells when the
// server now runs another one (restarted: reload the page). Asked every minute and when the window comes back to the
// front. Quiet: a small mark, nothing blocks. Not in the built app (BUILD.json, no git: never stale).

const EVERY = 60000;
let page = '', el = null, last = 0;

/** The commit this page was loaded with ('' until /api/version answered, or with no git). */
export const pageBuild = () => page;

async function check() {
  last = Date.now();
  let v;
  try { v = await (await fetch('/api/version')).json(); } catch { return; } // (the server restarting)
  if (!page) page = v.commit || '';
  const server = !!v.stale, reload = !server && !!page && !!v.commit && v.commit !== page;
  el.hidden = !server && !reload;
  el.dataset.kind = server ? 'server' : reload ? 'page' : '';
  el.textContent = server ? '⟳ New version — restart the app' : '⟳ New version — reload the page'; // (Czech: the page's i18n observer)
  el.title = server
    ? 'The app\'s files were updated, but its server still runs the older code it started with — new tools may be missing. Close the app and start it again.'
    : 'The app\'s server runs newer code than this page — reload the page (F5) to use it.';
}

export function initStaleNotice() {
  el = document.createElement('button');
  el.className = 'stale-note';
  el.id = 'staleNote';
  el.hidden = true;
  document.querySelector('.project-bar')?.appendChild(el);
  el.addEventListener('click', () => { if (el.dataset.kind === 'page') location.reload(); });
  check();
  setInterval(check, EVERY);
  window.addEventListener('focus', () => { if (Date.now() - last > 5000) check(); });
}
