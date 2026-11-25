// Measures how big a page's font draws the (R) when it is set at the SAME size as the text (font-size 1em, own font).
// Used by tools/tm_fix.py (user, 2026-11-25: "gets the size of the trademark symbol here [live Mercedes-Benz of Alexandria
// GLS page] and implement it to our pages ... and use it for the future pages"). GLS standard: drawn (R) width = 0.5 x text.
// Usage: node tm_measure.js "<project folder>" <prefix>   -> prints JSON {id, n, r1: {font: ratio}, all: median ratio}
const { chromium } = require('<toolkit>/node_modules/playwright-core');
const path = require('path');
(async () => {
  const [dir, pre] = process.argv.slice(2);
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 900 } })).newPage();
  await p.goto('file:///' + path.join(dir, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  await p.waitForTimeout(800);
  const res = await p.evaluate((pre) => {
    const wrap = document.querySelector(`.${pre}-wrap`);
    const id = wrap && wrap.closest('[id]') ? wrap.closest('[id]').id : '';
    const by = {}; const all = [];
    document.querySelectorAll(`.${pre}-r`).forEach((e) => {
      if (!/®/.test(e.textContent) || !e.offsetParent) return;
      e.style.setProperty('font-size', '1em', 'important'); e.style.setProperty('font-family', 'inherit', 'important');
      e.style.setProperty('vertical-align', 'baseline', 'important');
      const host = e.parentElement, hf = getComputedStyle(host); const rg = document.createRange(); rg.selectNodeContents(e);
      const r = rg.getBoundingClientRect().width / parseFloat(hf.fontSize);
      const fam = hf.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      (by[fam] = by[fam] || []).push(r); all.push(r);
    });
    const med = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };
    const r1 = {}; Object.keys(by).forEach((k) => { r1[k] = Math.round(med(by[k]) * 1000) / 1000; });
    return { id, n: all.length, r1, all: all.length ? Math.round(med(all) * 1000) / 1000 : null };
  }, pre);
  console.log(JSON.stringify(res));
  await b.close();
})();
