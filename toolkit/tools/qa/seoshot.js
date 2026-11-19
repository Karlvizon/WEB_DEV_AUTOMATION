const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const w of [1920, 900, 390]) {
    const p = await (await b.newContext({ viewport: { width: w, height: 1000 } })).newPage();
    await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
    await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(500);
    await p.locator('section[aria-label^="Buy, test drive"]').screenshot({ path: path.join(ROOT, `qa/_seo-${w}.png`) });
    console.log(w, await p.evaluate(() => { const c = [...document.querySelectorAll('.cp-seo')].map((e) => Math.round(e.getBoundingClientRect().height)); return 'card heights ' + c.join(','); }));
  }
  await b.close();
})();
