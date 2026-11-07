// WEB-002 click-to-load launcher, shared by Explore Interior (../interior/) and Explore Exterior (../exterior/) and the play/ hub.
// The page fetches only play.json (past the browser cache) and, on Start, opens the content-named Godot page of the one shared
// package; the hash tells the engine which experience to start (shell.html, godot/scripts/web_page.gd). Nothing heavy loads before
// Start, and the other experience's files are never requested: both scenes live in the same engine and pack.
//   wayfarerLaunch({ hash: '' | '#exterior', touch: true | false })
function wayfarerLaunch(opts) {
  const start = document.getElementById('start'), size = document.getElementById('size'), cap = document.getElementById('cap');
  const here = location.pathname.replace(/[^/]*$/, '');
  const playDir = here.endsWith('/play/') ? '' : '../play/';
  let play = null;
  fetch(playDir + 'play.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject(new Error(`play.json ${r.status}`))).then(p => {
    play = p;
    const mb = Object.values(p.bytes).reduce((a, b) => a + b, 0) / 1e6;
    size.textContent = `Pressing Start downloads the Godot ${p.godot_short} engine and the ship package: ${mb.toFixed(0)} MB, `
      + `less over the wire when the server compresses it, and cached for later visits (both experiences share it).`;
    if (!start.dataset.blocked) start.disabled = false;
  }).catch(err => { size.textContent = `This release has no interactive build (${err.message}).`; start.disabled = true; });
  // Capability probe without starting anything heavy: a throwaway WebGL 2 context, released at once.
  (() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const touchOnly = matchMedia('(pointer: coarse)').matches && !matchMedia('(pointer: fine)').matches;
    const notes = [];
    if (!gl) { notes.push('This browser did not provide WebGL 2, which the engine needs. Explore Ship may still work.'); start.disabled = true; start.dataset.blocked = '1'; }
    else gl.getExtension('WEBGL_lose_context')?.loseContext();
    if (!WebAssembly?.validate) notes.push('WebAssembly is unavailable.');
    if (touchOnly) notes.push(opts.touch
      ? 'Touch device: the game shows touch controls. It needs a recent phone and the download above; Explore Ship is the lighter choice.'
      : 'Touch device: this experience is flown with a keyboard (thrusters on 12 keys); it has no touch controls yet. Explore Interior and '
        + 'Explore Ship work with touch.');
    cap.textContent = notes.join(' ');
  })();
  start.addEventListener('click', () => { if (play && !start.dataset.blocked) location.assign(playDir + play.entry + (opts.hash || '')); });
}
