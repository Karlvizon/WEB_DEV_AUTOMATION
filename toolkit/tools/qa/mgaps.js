// Mobile spacing audit: full-page shot plus the vertical gap between every pair of stacked blocks. usage: node mgaps.js [width] [tag]
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const W = +(process.argv[2] || 390); const TAG = process.argv[3] || 'now';
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: W, height: 844 }, deviceScaleFactor: 1 })).newPage();
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
  await p.waitForTimeout(400);
  const rows = await p.evaluate(() => {
    const out = [];
    const name = (e) => (e.className && typeof e.className == 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : e.tagName.toLowerCase());
    const walk = (el, depth) => {
      const kids = [...el.children].filter((k) => { const r = k.getBoundingClientRect(); const s = getComputedStyle(k); return r.height > 0 && s.display != 'none' && s.position != 'absolute' && !k.closest('.{{P}}-car__track'); });
      for (let i = 1; kids.length > i; i++) {
        const a = kids[i - 1].getBoundingClientRect(); const c = kids[i].getBoundingClientRect();
        if (c.top >= a.bottom - 1) out.push({ depth, gap: Math.round(c.top - a.bottom), y: Math.round(c.top + scrollY), a: name(kids[i - 1]).slice(0, 60), b: name(kids[i]).slice(0, 60) });
      }
      if (depth < 6) kids.forEach((k) => walk(k, depth + 1));
    };
    walk(document.querySelector('.{{P}}-wrap'), 0);
    return out.sort((x, y) => x.y - y.y);
  });
  fs.writeFileSync(path.join(ROOT, `qa/mgaps-${W}-${TAG}.txt`), rows.map((r) => `${String(r.y).padStart(6)} ${String(r.gap).padStart(4)}px d${r.depth}  ${r.a}  ->  ${r.b}`).join('\n'));
  await p.setViewportSize({ width: W, height: 1750 });
  const H = await p.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0, i = 0; H > y; y += 1750, i++) {
    await p.evaluate((yy) => scrollTo(0, yy), y); await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(ROOT, `qa/_seg-${W}-${TAG}-${String(i).padStart(2, '0')}.png`) });
  }
  await b.close();
})();
