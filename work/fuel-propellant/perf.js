// FPS V1.1 release readiness, item 2: Explore Ship cost at V1 and V1.1 in the same headless browser (SW evidence class: SwiftShader, the
// numbers are relative only, never device performance). node work/fuel-propellant/perf.js <site_dir> <out.json> [port]
// Per site, two runs: load (ready_ms, transferred bytes), the default whole-ship view and the Fuel drawer's whole and assembly views
// (draw calls, triangles, frame-time median and p95 over 12 s of requestAnimationFrame).
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const [site, out, port = '8766'] = process.argv.slice(2);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm', '.png': 'image/png', '.svg': 'image/svg+xml' };
const server = http.createServer((q, r) => {
  let p = path.join(site, decodeURIComponent(q.url.split('?')[0].split('#')[0]));
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, 'index.html');
  if (!fs.existsSync(p)) { r.writeHead(404); r.end(); return; }
  r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r);
}).listen(+port);
const FRAMES = `new Promise(r => { const t0 = performance.now(); let n = 0; const ts = []; let last = t0;
  const f = now => { n++; ts.push(now - last); last = now; if (now - t0 < 12000) requestAnimationFrame(f); else { ts.sort((a, b) => a - b);
  r({ frames: n, median_ms: +ts[Math.floor(ts.length / 2)].toFixed(1), p95_ms: +ts[Math.floor(ts.length * 0.95)].toFixed(1) }); } };
  requestAnimationFrame(f); })`;
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const res = { site, runs: [] };
  for (let k = 0; k < 2; k++) {
    const pg = await b.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
    const t0 = Date.now();
    await pg.goto(`http://localhost:${port}/viewer/index.html`);
    await pg.waitForFunction(() => window.wayfarer?.model && window.wayfarer.stats.ready_ms, null, { timeout: 300000 });
    const run = { wall_ready_ms: Date.now() - t0 };
    run.load = await pg.evaluate(() => ({ ready_ms: window.wayfarer.stats.ready_ms,
      transferred: performance.getEntriesByType('resource').reduce((a, e) => a + (e.transferSize || e.encodedBodySize || 0), 0),
      glb: performance.getEntriesByType('resource').filter(e => e.name.endsWith('.glb')).map(e => e.encodedBodySize) }));
    await pg.waitForTimeout(2000);
    const view = async () => ({ ...(await pg.evaluate(FRAMES)), calls: await pg.evaluate(() => window.wayfarer.renderer.info.render.calls),
      triangles: await pg.evaluate(() => window.wayfarer.renderer.info.render.triangles) });
    run.ship = await view();
    await pg.evaluate(() => window.wayfarer.openFuel());
    await pg.waitForFunction(() => window.wayfarer.fuel()?.state().data, null, { timeout: 60000 });
    for (const v of ['whole', 'assembly']) {
      const ok = await pg.evaluate(v => { const f = window.wayfarer.fuel(); f.setState('ACTIVE'); f.setView(v); return f.state().view === v; }, v);
      if (!ok) { run[v] = null; continue; }
      await pg.waitForTimeout(2500);
      run[v] = await view();
    }
    run.heap_MB = await pg.evaluate(() => performance.memory ? +(performance.memory.usedJSHeapSize / 1e6).toFixed(1) : null);
    res.runs.push(run); await pg.close();
  }
  fs.writeFileSync(out, JSON.stringify(res, null, 1)); console.log(JSON.stringify(res));
  await b.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
