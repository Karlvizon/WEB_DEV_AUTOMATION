// Live page: diff the JS field against the page, check every wrapper image URL (status, -1 renames), reload-check images at 1920.
const { chromium } = require('playwright-core'); const fs = require('fs'); const path = require('path');
const ROOT = path.resolve(__dirname, '../..'); const URL = process.argv[2];
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1000 } }); const p = await ctx.newPage();
  for (let t = 0; t < 6; t++) { await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(6000); if (await p.$('#{{ID}}')) break; }
  const js = await p.evaluate(() => [...document.scripts].filter((x) => x.textContent.includes('{{ID}}')).map((x) => x.textContent)[0]);
  fs.writeFileSync(path.join(ROOT, 'qa/live/live.js'), js);
  const field = fs.readFileSync(path.join(ROOT, 'cms-fields/{{NAME}}.js'), 'utf8');
  const a = js.replace(/\s+/g, ' ').trim(), f = field.replace(/\s+/g, ' ').trim();
  let i = 0; while (i < a.length && a[i] === f[i]) i++;
  console.log('JS live', a.length, 'field', f.length, a === f ? 'IDENTICAL' : 'first difference at ' + i + '\n live : ' + a.slice(Math.max(0, i - 80), i + 80) + '\n field: ' + f.slice(Math.max(0, i - 80), i + 80));
  const srcs = await p.evaluate(() => [...new Set([...document.querySelectorAll('#{{ID}} img, #{{ID}} source')].map((e) => e.getAttribute('src') || e.getAttribute('srcset')))]);
  const fieldHtml = fs.readFileSync(path.join(ROOT, 'cms-fields/{{NAME}}.html'), 'utf8');
  const fieldSrcs = [...new Set([...fieldHtml.matchAll(/(?:src|srcset)="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, '&')))].filter((s) => /\.webp/.test(s));
  const missing = fieldSrcs.filter((s) => !srcs.includes(s)), extra = srcs.filter((s) => !fieldSrcs.includes(s));
  console.log('image URLs on page', srcs.length, '| in field', fieldSrcs.length, '| changed vs field:', missing.length, extra.length, missing.slice(0, 5), extra.slice(0, 5));
  const bad = [];
  for (const s of srcs) {
    let st = 0; for (let t = 0; t < 3 && st !== 200; t++) { const r = await p.request.get(s, { maxRedirects: 5 }).catch(() => null); st = r ? r.status() : 0; }
    if (st !== 200) bad.push(st + ' ' + s);
  }
  const dash1 = [];
  for (const s of srcs) { const u = s.replace(/\.webp$/, '-1.webp'); const r = await p.request.get(u).catch(() => null); if (r && r.status() === 200) dash1.push(u.split('/').pop()); }
  console.log('URL status: ' + (srcs.length - bad.length) + '/' + srcs.length + ' return 200', bad, '| -1 duplicates in library:', dash1.length ? dash1 : 'none');
  await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); for (let y = 0; y < document.body.scrollHeight; y += 800) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } });
  await p.waitForTimeout(5000);
  const broken = await p.evaluate(() => [...document.querySelectorAll('#{{ID}} img')].filter((i) => !(i.complete && i.naturalWidth)).map((i) => i.currentSrc.split('/').pop()));
  console.log('1920 after scrolling the page: images not decoded:', broken.length ? broken : 'none');
  await b.close();
})();
