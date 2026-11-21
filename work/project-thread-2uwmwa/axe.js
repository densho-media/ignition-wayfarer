const { chromium } = require('playwright'); const fs = require('fs');
const [base, ...pages] = process.argv.slice(2);
const src = fs.readFileSync(__dirname + '/axe/node_modules/axe-core/axe.min.js', 'utf8');
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const [vw, vh, t] of [[1366, 768, false], [390, 844, true]]) for (const p of pages) {
    const ctx = await b.newContext({ viewport: { width: vw, height: vh }, hasTouch: t, isMobile: t }); const pg = await ctx.newPage();
    await pg.goto(base + p, { waitUntil: 'load' }); await pg.waitForTimeout(800);
    await pg.addScriptTag({ content: src });
    const r = await pg.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa'] })).violations
      .map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, t: v.nodes.slice(0, 3).map(n => n.target.join(' ')) })));
    console.log(JSON.stringify({ page: p || '/', vw, violations: r }));
    await ctx.close();
  }
  await b.close();
})();
