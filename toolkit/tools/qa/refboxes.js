// Dump layout containers (flex/grid/background/border boxes) with padding/gap at a phone width.
// usage: node refboxes.js <url|preview> <out.json> [width] [selector]
const { chromium } = require('playwright-core'); const path = require('path'); const fs = require('fs');
(async () => {
  const [url, out, wArg, selArg] = process.argv.slice(2); const W = +wArg || 390; const sel = selArg || '.main-div'; const local = url === 'preview';
  const b = await chromium.launch(local ? { channel: 'msedge' } : { channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: W, height: 844 }, ...(W > 1024 ? { deviceScaleFactor: 1 } : { isMobile: true, hasTouch: true, deviceScaleFactor: 1, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' }) });
  const p = await ctx.newPage();
  if (local) await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  else for (let t = 0; t < 4; t++) { await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(7000); if (await p.evaluate((s) => !!document.querySelector(s), sel).catch(() => false)) break; }
  await p.waitForTimeout(1500);
  const data = await p.evaluate((s) => {
    const root = document.querySelector(s); const R = root.getBoundingClientRect(); const rows = [];
    for (const e of root.querySelectorAll('*')) {
      if (e.closest('[aria-hidden="true"],[data-clone]')) continue;
      const r = e.getBoundingClientRect(); if (r.width < 60 || r.height < 20) continue; if (r.right < R.left + 2 || r.left > R.right - 2) continue;
      const c = getComputedStyle(e); if (c.display === 'none') continue;
      const bg = c.backgroundColor !== 'rgba(0, 0, 0, 0)' ? c.backgroundColor : ''; const bgi = c.backgroundImage !== 'none' ? 'img' : '';
      const bd = parseFloat(c.borderTopWidth) > 0 ? c.borderTopWidth + ' ' + c.borderTopColor : '';
      const pad = [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft].map((v) => Math.round(parseFloat(v))).join(' ');
      const flex = /flex|grid/.test(c.display);
      if (!(bg || bgi || bd || flex || pad !== '0 0 0 0')) continue;
      rows.push({ tag: e.tagName, cls: String(e.className || '').slice(0, 45), y: Math.round(r.top - R.top), x: Math.round(r.left - R.left), w: Math.round(r.width), h: Math.round(r.height), disp: c.display, gap: c.rowGap + '/' + c.columnGap, cols: c.gridTemplateColumns === 'none' ? '' : c.gridTemplateColumns, pad, mt: c.marginTop, bg: bg + bgi, bd, rad: c.borderTopLeftRadius, sh: c.boxShadow === 'none' ? (c.filter === 'none' ? '' : 'f') : 's' });
    }
    return rows; }, sel);
  fs.writeFileSync(out, JSON.stringify(data, null, 1)); console.log(data.length + ' containers -> ' + out); await b.close();
})();
