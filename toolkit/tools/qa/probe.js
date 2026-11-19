// usage: node probe.js <width> "<css selector>" ...  -> page-absolute boxes (x,y,w,h) of each match
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
(async () => {
  const W = +process.argv[2];
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: W, height: 1000 } });
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => innerWidth - document.documentElement.clientWidth);
  if (sb) await p.setViewportSize({ width: W + sb, height: 1000 });
  await p.evaluate(() => document.fonts.ready);
  for (const sel of process.argv.slice(3)) {
    const r = await p.evaluate((s) => [...document.querySelectorAll(s)].map((e) => { const q = e.getBoundingClientRect(); return [q.left, q.top + scrollY, q.width, q.height].map((v) => Math.round(v * 10) / 10).join(' '); }), sel);
    console.log(sel + '\n  ' + r.join('\n  '));
  }
  await b.close();
})();
