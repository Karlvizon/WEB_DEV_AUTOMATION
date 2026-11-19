// Before/after images for the review note (user, 2026-11-13: production features).
// Usage: node beforeafter.js "<project folder>" "<old preview.html>" <width> "<label>|<css selector>" ["<label>|<selector>" ...]
//   e.g. node beforeafter.js "<Projects folder>/Huston CDJR/2027 Dodge Durango, Huston CDJR" "...tools/_work/rev1-backup/preview.html" 1920 "1-hero|.dgo-hero__tx"
// Writes <project>/before-after/<label>.png (BEFORE left, AFTER right, labelled). production.py pack copies them into to-post/.
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright-core'));
const fs = require('fs'); const path = require('path');
const [proj, oldFile, width, ...jobs] = process.argv.slice(2);
const url = (f) => 'file:///' + path.resolve(f).split(path.sep).join('/');

async function shot(b, file, w, sel) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 } }); const p = await ctx.newPage();
  await p.goto(url(file), { waitUntil: 'load' });
  await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); await document.fonts.ready; });
  const el = p.locator(sel).first(); await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(250);
  const buf = await el.screenshot({ timeout: 15000 }); await ctx.close(); return buf;
}

(async () => {
  const b = await chromium.launch({ channel: 'msedge' }); const w = Number(width) || 1920;
  // the old file is copied next to preview.html so its relative image paths (assets/webp/...) resolve the same way
  const oldTmp = path.join(proj, '_before_tmp.html'); fs.copyFileSync(oldFile, oldTmp);
  const outDir = path.join(proj, 'before-after'); fs.mkdirSync(outDir, { recursive: true });
  for (const job of jobs) {
    const [label, sel] = job.split('|');
    try {
      const a = await shot(b, oldTmp, w, sel); const z = await shot(b, path.join(proj, 'preview.html'), w, sel);
      const ctx = await b.newContext({ viewport: { width: 1600, height: 400 } }); const p = await ctx.newPage();
      await p.setContent(`<html><body style="margin:0;font:600 18px Arial;background:#fff"><div id="w" style="display:flex;gap:24px;padding:16px;align-items:flex-start">
        <div style="flex:1"><div style="color:#c00;margin-bottom:6px">BEFORE</div><img style="max-width:100%;border:1px solid #ccc" src="data:image/png;base64,${a.toString('base64')}"></div>
        <div style="flex:1"><div style="color:#080;margin-bottom:6px">AFTER</div><img style="max-width:100%;border:1px solid #ccc" src="data:image/png;base64,${z.toString('base64')}"></div></div></body></html>`);
      await p.waitForTimeout(200);
      const out = path.join(outDir, `${label}.png`); await p.locator('#w').screenshot({ path: out }); await ctx.close();
      console.log('ok', out);
    } catch (e) { console.log('FAIL', label, e.message.split('\n')[0]); }
  }
  fs.unlinkSync(oldTmp); await b.close();
})();
