const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1000 } })).newPage();
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const el = p.locator('img[src$="compass-wheel-hero.webp"]').locator('..');
  await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(1500);
  await el.screenshot({ path: path.join(ROOT, 'qa/_wheelhero.png') });
  console.log(await p.evaluate(() => { const i = document.querySelector('img[src$="compass-wheel-hero.webp"]'); return [i.naturalWidth, i.naturalHeight, i.currentSrc.split('/').pop()].join(' '); }));
  await b.close();
})();
