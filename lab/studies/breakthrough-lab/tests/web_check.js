// Breakthrough Lab website check: drives the built Engineering 2.0 pages in Chromium (Playwright). Lab test, run on demand.
//   node lab/studies/breakthrough-lab/tests/web_check.js <site dir> [screenshot dir]
// Checks navigation, the Weakest Links filter, scenario selection and comparison, missing-data and out-of-range states, keyboard
// operation, phone-width layout, reading without JavaScript and without any 3D model. Exits 1 on the first failed check.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const site = path.resolve(process.argv[2]);
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null;
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.glb': 'model/gltf-binary' };
let failed = 0;
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${msg}`); if (!cond) failed++; };

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let f = path.join(site, p);
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!f.startsWith(site) || !fs.existsSync(f)) { res.writeHead(404); res.end('not found'); return; }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise((r) => server.listen(0, r));
  const base = `http://127.0.0.1:${server.address().port}/engineering/`;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  const requests = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('request', (r) => requests.push(r.url()));
  const shot = async (name) => { if (shots) { fs.mkdirSync(shots, { recursive: true }); await page.screenshot({ path: path.join(shots, name), fullPage: false }); } };

  // Landing page and navigation
  await page.goto(base, { waitUntil: 'load' });
  ok(await page.locator('#e2 .card').count() === 4, 'landing page shows the four Engineering 2.0 areas');
  await shot('01_engineering_landing.png');
  for (const area of ['baseline', 'weakest-links', 'breakthrough-lab', 'evolution']) {
    await page.goto(base + area + '/', { waitUntil: 'load' });
    ok(await page.locator('.subnav a[aria-current]').getAttribute('href').then((h) => h.endsWith(area + '/')), `${area}: sub-navigation marks the current area`);
    ok(await page.locator('.subnav a').count() === 4, `${area}: sub-navigation links all four areas`);
  }
  await page.goto(base + 'baseline/', { waitUntil: 'load' });
  ok(await page.locator('table.configs tbody tr').count() >= 8, 'baseline: configuration table lists the reference configurations');
  await shot('02_baseline.png');

  // Weakest Links filter
  await page.goto(base + 'weakest-links/', { waitUntil: 'load' });
  const filter = page.locator('form[data-filter=wl]');
  ok(await filter.isVisible(), 'weakest links: the filter appears with JavaScript');
  const total = await page.locator('.wl').count();
  await page.selectOption('form[data-filter=wl] select[name=tier]', '1');
  const shown = await page.locator('.wl:not([hidden])').count();
  ok(shown > 0 && shown < total, `weakest links: tier 1 filter shows ${shown} of ${total}`);
  ok((await page.locator('form[data-filter=wl] output').textContent()).includes(`${shown} of ${total}`), 'weakest links: the count is announced');
  ok(await page.locator('.wl:not([hidden]) .bt-tier-1').count() === shown, 'weakest links: every shown card is tier 1');
  await page.selectOption('form[data-filter=wl] select[name=tier]', '');
  await page.fill('form[data-filter=wl] input[name=q]', 'coil');
  ok(await page.locator('.wl:not([hidden])').count() >= 1, 'weakest links: text search finds the coil link');
  await page.fill('form[data-filter=wl] input[name=q]', '');
  await shot('03_weakest_links.png');

  // Breakthrough Lab: selection, comparison, states
  await page.goto(base + 'breakthrough-lab/', { waitUntil: 'load' });
  const data = JSON.parse(await page.locator('#bt-data').textContent());
  const status = () => page.locator('[data-result] .scenario-status .bt').first().getAttribute('class');
  ok(decodeURIComponent((await page.evaluate(() => location.hash)).slice(1)) === data.v4_key, 'lab: opens on the V4 equivalent');
  ok((await status()).includes('bt-st-CLOSES'), 'lab: the V4 equivalent closes');
  ok(await page.locator('[data-result] .panel h3', { hasText: 'Scientific reference' }).count() === 1, 'lab: shows the reference beside the scenario');
  await shot('04_breakthrough_lab.png');
  if (shots) await page.locator('[data-result]').screenshot({ path: path.join(shots, '07_scenario_comparison.png') });
  // keyboard: focus BT-001 L2 and move to L0 with the arrow keys (radio group)
  await page.focus('input[name="BT-001"][value="L2"]');
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('ArrowUp');
  ok(await page.isChecked('input[name="BT-001"][value="L0"]'), 'lab: radio levels are operable by keyboard');
  ok((await status()).includes('bt-st-DOES_NOT_CLOSE'), 'lab: coupling 0.15 with the V4 package does not close');
  ok((await page.locator('[data-result]').textContent()).includes('does not close'), 'lab: the reason is shown');
  // out of range and between table points
  await page.click('input[name="BT-001"][value="L2"]');
  await page.fill('input[type=number][data-bt="BT-001"]', '1.4');
  ok((await status()).includes('bt-st-OUT_OF_RANGE'), 'lab: a coupling above 1.0 is out of range');
  ok(await page.locator('[data-result] .panel').nth(1).locator('td.num').first().textContent().then((t) => t.trim().startsWith('–')), 'lab: out of range shows no numbers');
  await page.fill('input[type=number][data-bt="BT-001"]', '0.45');
  ok((await status()).includes('bt-st-NOT_COMPUTED'), 'lab: a value between table points is not computed (no interpolation)');
  await page.fill('input[type=number][data-bt="BT-001"]', '0.5');
  ok(await page.isChecked('input[name="BT-001"][value="L2"]') && (await status()).includes('bt-st-CLOSES'), 'lab: a table value selects its level');
  await page.fill('input[type=number][data-bt="BT-001"]', '');
  // inferred not computed (finite launcher on a non-closing case)
  const inferred = Object.keys(data.cases).find((k) => data.cases[k].status === 'NOT_COMPUTED');
  if (inferred) {
    await page.evaluate((k) => { location.hash = k; }, inferred);
    await page.reload({ waitUntil: 'load' });
    ok((await status()).includes('bt-st-NOT_COMPUTED'), 'lab: an inferred case is labelled not computed');
  }
  // presets
  await page.click('.preset >> nth=0');
  ok(await page.locator('.preset[aria-current]').count() === 1, 'lab: a preset selects its scenario');
  ok((await page.locator('[data-result]').textContent()).includes('not canon'), 'lab: every scenario is labelled not canon');
  // reference scenario selected: dependency note absent; SC-REF-FREE: dependency flagged
  const free = data.named.find((n) => n.id === 'SC-REF-FREE');
  await page.evaluate((k) => { location.hash = k; }, free.key);
  await page.reload({ waitUntil: 'load' });
  ok((await page.locator('[data-result]').textContent()).includes('BT-005 needs BT-001'), 'lab: an unmet dependency is flagged');

  // Ship Evolution
  await page.goto(base + 'evolution/', { waitUntil: 'load' });
  ok(await page.locator('svg.env').count() >= 6, 'evolution: true-scale envelopes drawn without JavaScript input');
  ok((await page.locator('svg.env text.none').count()) >= 1, 'evolution: a non-closing case is a labelled placeholder, not geometry');
  const opts = await page.locator('form[data-evo] option').count();
  ok(opts >= 1, `evolution: ${opts} computed cases can be drawn`);
  if (opts > 1) {
    await page.selectOption('form[data-evo] select', { index: opts - 1 });
    ok(await page.locator('[data-evo-out] svg.env').count() === 2, 'evolution: the chosen case is drawn');
  }
  await shot('05_ship_evolution.png');
  ok(!requests.some((u) => u.endsWith('.glb')), 'no Engineering 2.0 page loads a 3D model');
  ok(errors.length === 0, `no script errors (${errors.join(' | ')})`);

  // Phone width: no horizontal page scroll
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 } });
  for (const area of ['', 'baseline/', 'weakest-links/', 'breakthrough-lab/', 'evolution/']) {
    await phone.goto(base + area, { waitUntil: 'load' });
    const over = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    ok(over <= 1, `phone 390 px: /engineering/${area} has no horizontal scroll (${over} px)`);
  }
  if (shots) { await phone.goto(base + 'breakthrough-lab/', { waitUntil: 'load' }); await phone.screenshot({ path: path.join(shots, '06_lab_phone.png') }); }

  // Without JavaScript the numbers are still readable
  const nojs = await browser.newContext({ javaScriptEnabled: false });
  const p2 = await nojs.newPage();
  await p2.goto(base + 'breakthrough-lab/', { waitUntil: 'load' });
  ok(await p2.locator('[data-result] .panel table tr').count() >= 10, 'no JavaScript: the reference and V4 results are in the page');
  ok(await p2.locator('table.grid tbody tr').count() === Object.keys(data.cases).length, 'no JavaScript: every computed case is listed');
  await p2.goto(base + 'weakest-links/', { waitUntil: 'load' });
  ok(await p2.locator('.wl').count() === total && !(await p2.locator('form[data-filter=wl]').isVisible()), 'no JavaScript: the whole register shows, the filter stays hidden');

  await browser.close();
  server.close();
  console.log(failed ? `${failed} check(s) FAILED` : 'all checks passed');
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
