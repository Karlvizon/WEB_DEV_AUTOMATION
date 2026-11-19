const { chromium } = require('playwright-core'); const path = require('path');
(async () => { const b = await chromium.launch({ channel: 'msedge' }); const p = await b.newPage({ viewport: { width: 1920, height: 1000 } });
 await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'));
 await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
 await p.evaluate(async () => { await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
 const r = await p.evaluate(() => { const m = {}; for (const i of document.querySelectorAll('.{{P}}-wrap img')) { const q = i.getBoundingClientRect(); if (!q.width) continue;
   const cs = getComputedStyle(i); let sc = q.width / i.naturalWidth; if (cs.objectFit === 'cover') sc = Math.max(q.width / i.naturalWidth, q.height / i.naturalHeight);
   const n = i.currentSrc.split('/').pop().replace('.webp', ''); m[n] = Math.max(m[n] || 0, sc); } return m; });
 console.log(JSON.stringify(r)); await b.close(); })();
