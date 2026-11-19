// Blurry photo list for upscale_stretched.py (2026-11-13, Final MLP automation).
// Same test as qa_sweep.js "blurry": an image shown over 1.1x its file width at 1920 (cover scale counted).
// Usage: node blurry_list.js "<project folder>"   -> prints JSON {"<file name>": <displayed width px at 1920>, ...}
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright-core'));
const path = require('path');

(async () => {
  const dir = process.argv[2]; const file = path.join(dir, 'preview.html');
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 900 } })).newPage();
  await p.goto('file:///' + file.split(path.sep).join('/'), { waitUntil: 'load' });
  await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
  const res = await p.evaluate(() => {
    const out = {};
    document.querySelectorAll('img').forEach((i) => {
      const r = i.getBoundingClientRect(); if (r.width < 120 || !i.naturalWidth || i.closest('[data-clone]')) return;
      let dw = r.width; if (getComputedStyle(i).objectFit === 'cover') dw = Math.max(r.width, r.height * i.naturalWidth / i.naturalHeight);
      if (dw / i.naturalWidth > 1.1) { const n = (i.currentSrc || i.src).split('/').pop(); out[n] = Math.max(out[n] || 0, Math.ceil(dw)); }
    });
    return out;
  });
  console.log(JSON.stringify(res));
  await b.close();
})();
