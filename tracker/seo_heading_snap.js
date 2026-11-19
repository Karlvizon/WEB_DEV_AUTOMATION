// SEO auto-fix check (2026-11-17): how every heading LOOKS in a page, so seo_fix.py can prove a fix kept the look.
// Prints JSON {"<file>": {"1920": [[tag, innerText, w, h], ...], "390": [...]}} - innerText applies CSS text-transform,
// so "UP TO 8 PASSENGERS" typed in caps and "Up to 8 Passengers" + uppercase CSS read the same.
// Usage: node seo_heading_snap.js "<toolkit root>" "<file1.html>" ["<file2.html>" ...]
const path = require('path');
const { chromium } = require(path.join(process.argv[2], 'node_modules', 'playwright-core'));
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: true });
  const out = {};
  for (const f of process.argv.slice(3)) {
    out[f] = {};
    for (const w of [1920, 390]) {
      const p = await b.newPage({ viewport: { width: w, height: 1000 } });
      try { await p.goto('file:///' + f.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 30000 }); } catch (e) { /* offline fonts etc. */ }
      await p.waitForTimeout(800);
      out[f][w] = await p.evaluate(() => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h) => {
        const r = h.getBoundingClientRect();
        return [h.tagName, h.innerText.replace(/\s+/g, ' ').trim(), Math.round(r.width), Math.round(r.height)];
      }));
      await p.close();
    }
  }
  await b.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e)); process.exit(1); });
