// Screenshot the first element matching each selector at a given width.
// usage: node secshot.js <width> <out-prefix> <selector> [selector...]
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const [W, OUT, ...sels] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: +W, height: 900 } });
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'));
  await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; })))); });
  await p.waitForTimeout(800);
  let k = 0;
  for (const s of sels) {
    const e = await p.$(s);
    if (e) await e.screenshot({ path: `${OUT}-${k}.png` });
    k++;
  }
  await b.close();
})();
