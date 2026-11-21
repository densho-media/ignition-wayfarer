// WOS layout matrix: screenshots + function assertions. node matrix.js <site_url> <out_dir> [pages...]
const { chromium } = require('playwright');
const fs = require('fs');
const [base, out, ...only] = process.argv.slice(2);
const VIEWPORTS = [
  ['ultrawide', 2560, 1080, false], ['desktop', 1920, 1080, false], ['laptop', 1366, 768, false],
  ['tablet-land', 1180, 820, true], ['tablet-port', 820, 1180, true], ['phone-port', 390, 844, true], ['phone-land', 844, 390, true],
];
const PAGES = [['overview', ''], ['ship', 'viewer/'], ['dust', 'engineering/dust/'], ['system', 'status/'], ['records', 'engineering/']];
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const results = [];
  for (const [pname, path] of PAGES) {
    if (only.length && !only.includes(pname)) continue;
    let ids0 = null;
    for (const [vname, w, h, touch] of VIEWPORTS) {
      if (process.env.VIEWS && !process.env.VIEWS.split(',').includes(vname)) continue;
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, hasTouch: touch, isMobile: touch && w < 1000, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      await page.goto(base + path, { waitUntil: 'load' });
      if (pname === 'ship') await page.waitForFunction(() => window.wayfarer || document.querySelector('#status.error'), null, { timeout: 180000 }).catch(() => {});
      if (pname === 'dust') { await page.click('#load').catch(() => {}); await page.waitForFunction(() => document.querySelector('#stage.live'), null, { timeout: 60000 }).catch(() => {}); await page.waitForTimeout(1500); }
      await page.waitForTimeout(400);
      const m = await page.evaluate(() => {
        const de = document.documentElement, bar = document.querySelector('.wos-bar'), nav = document.querySelector('.wos-nav');
        const work = document.getElementById('wos-work');
        const r = e => e && e.getBoundingClientRect();
        const vis = e => { const b = r(e); return b && b.width > 0 && b.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
        const navLinks = [...document.querySelectorAll('.wos-nav a')];
        const inView = e => { const b = r(e); return b.left >= -1 && b.top >= -1 && b.right <= innerWidth + 1 && b.bottom <= innerHeight + 1; };
        const ids = [...document.querySelectorAll('button[id], a[id], input[id], [data-view], [data-style], [data-mode], .wos-nav a')]
          .map(e => e.id || e.dataset.view || e.dataset.style || e.dataset.mode || e.textContent.trim()).sort();
        const wb = r(work);
        const small = [...document.querySelectorAll('.wos-bar a, .wos-bar summary, .wos-nav a')].filter(vis)
          .filter(e => { const b = r(e); return b.height < 44 || b.width < 44; }).map(e => e.textContent.trim().slice(0, 20));
        return {
          overflowX: de.scrollWidth > innerWidth + 1, pageScrolls: de.scrollHeight > innerHeight + 1,
          barInView: !!bar && inView(bar), navLinks: navLinks.length, navVisible: navLinks.filter(a => vis(a) && inView(a)).length,
          workShare: wb ? +((Math.min(wb.width, innerWidth) * Math.min(wb.height, innerHeight)) / (innerWidth * innerHeight)).toFixed(2) : null,
          station: document.querySelector('.wos-station') && getComputedStyle(document.querySelector('.wos-station')).display !== 'none'
            ? document.querySelector('.wos-station').innerText.trim() : '',
          small, ids,
        };
      });
      const parity = ids0 ? JSON.stringify(ids0) === JSON.stringify(m.ids) : true;
      if (!ids0) ids0 = m.ids;
      const coarse = touch;
      results.push({ page: pname, viewport: vname, overflowX: m.overflowX, pageScrolls: m.pageScrolls, barInView: m.barInView,
        nav: `${m.navVisible}/${m.navLinks}`, workShare: m.workShare, station: m.station, parity,
        smallTargets: coarse ? m.small : [], errors });
      await page.screenshot({ path: `${out}/${pname}_${vname}.png`, timeout: 120000 }).catch(e => errors.push('screenshot: ' + e.message.slice(0, 60)));
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(`${out}/matrix.json`, JSON.stringify(results, null, 1));
  for (const r of results) console.log(JSON.stringify(r));
})();
