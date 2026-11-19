// usage: node lines.js <width> "<selector>" [index]  -> the text of each rendered line of that element
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
(async () => {
  const W = +process.argv[2], sel = process.argv[3], idx = +(process.argv[4] || 0);
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: W, height: 1000 } });
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => innerWidth - document.documentElement.clientWidth);
  if (sb) await p.setViewportSize({ width: W + sb, height: 1000 });
  await p.evaluate(() => document.fonts.ready);
  const lines = await p.evaluate(([s, i]) => {
    const el = document.querySelectorAll(s)[i]; const out = []; let cur = '', top = null;
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let t; while ((t = walk.nextNode())) for (let k = 0; k < t.length; k++) {
      const r = document.createRange(); r.setStart(t, k); r.setEnd(t, k + 1); const q = r.getClientRects()[0]; if (!q) { cur += t.data[k]; continue; }
      if (top !== null && q.top > top + 2) { out.push(cur); cur = ''; } top = q.top; cur += t.data[k];
    }
    out.push(cur); return out.map((l) => l.trim() + '  [' + Math.round(el.getBoundingClientRect().width) + ']');
  }, [sel, idx]);
  console.log(lines.join('\n'));
  await b.close();
})();
