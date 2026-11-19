// Full-page screenshot by capturing clips and stitching (Chromium can't capture very tall pages in one shot).
// usage: node fullshot.js <width> <out.png> [height=1000] [zoomFactor=1]
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const ROOT = path.resolve(__dirname, '../..');
const W = +process.argv[2] || 1920, OUT = process.argv[3], H = +process.argv[4] || 1000, DSF = +process.argv[5] || 1;
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DSF });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => window.innerWidth - document.documentElement.clientWidth);
  if (sb) await p.setViewportSize({ width: W + sb, height: H });
  await p.evaluate(() => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); });
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
  await p.waitForTimeout(2500);
  const total = await p.evaluate(() => document.documentElement.scrollHeight);
  const dir = path.join(path.dirname(OUT), '_parts-' + W + '-' + process.pid); fs.mkdirSync(dir, { recursive: true });
  const CH = Math.min(4000, total);
  await p.setViewportSize({ width: W + sb, height: CH });
  await p.waitForTimeout(1200);
  const parts = [];
  for (let y = 0, i = 0; y < total; y += CH, i++) {
    const top = Math.min(y, total - CH);
    await p.evaluate((t) => window.scrollTo(0, t), top);
    await p.waitForTimeout(250);
    const f = path.join(dir, `p${i}.png`);
    await p.screenshot({ path: f, clip: { x: 0, y: 0, width: W, height: CH } });
    parts.push(f + ':' + Math.round((y - top) * DSF));
  }
  execFileSync('python', ['-I', path.join(__dirname, 'stitch.py'), OUT, ...parts]);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`${W}px: ${total}px tall -> ${OUT}${errs.length ? '  JS errors: ' + errs.join(' | ') : ''}`);
  await b.close();
})();
