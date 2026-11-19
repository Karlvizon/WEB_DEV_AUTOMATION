// Measure a page's mobile layout: every visible text/img/button box in order, with the vertical gap to the previous box.
// usage: node refmeasure.js <url|preview> <out.json> [width] [selector]
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
(async () => {
  const [url, out, wArg, selArg] = process.argv.slice(2); const W = +wArg || 390;
  const local = url === 'preview';
  const b = await chromium.launch(local ? { channel: 'msedge' } : { channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: W, height: 844 }, ...(W > 1024 ? { deviceScaleFactor: 1 } : { isMobile: true, hasTouch: true, deviceScaleFactor: 1, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' }) });
  const p = await ctx.newPage();
  const sel = selArg || '.main-div';
  if (local) await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  else for (let t = 0; t < 4; t++) { await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(7000); if (await p.evaluate((s) => !!document.querySelector(s), sel).catch(() => false)) break; }
  const top = await p.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { y: r.top + scrollY, h: r.height }; }, sel);
  for (let y = 0; y < top.y + top.h; y += 600) { await p.evaluate((y) => scrollTo(0, y), y); await p.waitForTimeout(120); }
  await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(1500);
  const data = await p.evaluate((s) => {
    const root = document.querySelector(s); const R = root.getBoundingClientRect();
    const els = [...root.querySelectorAll('h1,h2,h3,h4,p,li,img,a,button')].filter((e) => {
      const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return false;
      if (r.right < R.left + 2 || r.left > R.right - 2) return false;
      const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
      if (e.closest('[aria-hidden="true"],[data-clone]')) return false;
      if (e.tagName === 'A' && e.querySelector('img,h1,h2,h3,h4,p')) return false;
      return true; });
    const rows = els.map((e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); let bg = null, n = e; while (n && n !== root.parentElement) { const c = getComputedStyle(n).backgroundColor; if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') { bg = c; break; } n = n.parentElement; }
      return { tag: e.tagName, cls: String(e.className || '').slice(0, 40), text: (e.innerText || e.alt || '').trim().replace(/\s+/g, ' ').slice(0, 50), x: Math.round(r.left - R.left), y: Math.round(r.top - R.top), w: Math.round(r.width), h: Math.round(r.height), fs: cs.fontSize, fw: cs.fontWeight, lh: cs.lineHeight, ta: cs.textAlign, bg, rad: cs.borderRadius }; });
    rows.sort((a, b) => a.y - b.y || a.x - b.x);
    return { width: Math.round(R.width), height: Math.round(R.height), rows };
  }, sel);
  fs.writeFileSync(out, JSON.stringify(data, null, 1));
  const shots = path.join(path.dirname(out), path.basename(out, '.json'));
  const el = await p.$(sel); let i = 0;
  for (let y = 0; y < data.height; y += 2500, i++) { await el.screenshot({ path: `${shots}-${i}.png`, clip: undefined }).catch(() => {}); break; }
  await p.screenshot({ path: `${shots}-full.png`, fullPage: true }).catch(() => {});
  console.log(`${data.rows.length} boxes, wrapper ${data.width}x${data.height} -> ${out}`);
  await b.close();
})();
