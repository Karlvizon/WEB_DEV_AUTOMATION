// Element screenshots at a phone width for side-by-side review. usage: node mshot.js <width> <selector>...
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const [W, ...sels] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: +W, height: 900 }, deviceScaleFactor: 2 })).newPage();
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
  for (const [i, s] of sels.entries()) await p.locator(s).first().screenshot({ path: path.join(ROOT, `qa/_m${i}.png`) });
  await b.close();
})();
