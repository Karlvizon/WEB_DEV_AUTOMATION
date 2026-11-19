// usage: node fsizes.js  -> MLP vs disclaimer font sizes at several widths
const { chromium } = require('playwright-core'); const path = require('path');
(async () => { const b = await chromium.launch({ channel: 'msedge' }); const out = [];
  for (const w of [1920, 1440, 1366, 1024, 820, 768, 390, 320]) {
    const p = await (await b.newContext({ viewport: { width: w, height: 900 } })).newPage();
    await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'), { waitUntil: 'load' }); await p.evaluate(() => document.fonts.ready);
    const r = await p.evaluate(() => { const f = (s) => [...new Set([...document.querySelectorAll(s)].map((e) => { const c = getComputedStyle(e); return c.fontSize + '/' + c.fontWeight + '/lh ' + c.lineHeight; }))].join(' | '); return { q: f('.{{P}}-seo__q'), p: f('.{{P}}-seo__p'), l: f('.{{P}}-legal p') }; });
    out.push(`${String(w).padStart(4)}px  MLP question ${r.q}   MLP body ${r.p}   disclaimer ${r.l}`); }
  console.log(out.join('\n')); await b.close(); })();
