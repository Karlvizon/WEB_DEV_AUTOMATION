// Open the dealer site in headed Edge (bot shield), save the source and list media-library paths and brand @font-face rules.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = process.argv[2] || 'https://www.bridgetongmc.com/';
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1000 } })).newPage();
  for (let t = 0; t < 5; t++) {
    await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
    await p.waitForTimeout(8000);
    if ((await p.title()) !== 'Dealer Website') break;
  }
  const html = await p.content();
  fs.writeFileSync(path.join(ROOT, 'qa/live/site.html'), html);
  const facts = await p.evaluate(() => {
    const faces = [];
    for (const s of document.styleSheets) { try { for (const r of s.cssRules) if (r.type === 5) faces.push(r.style.getPropertyValue('font-family') + ' ' + r.style.getPropertyValue('font-weight') + ' ' + (r.style.getPropertyValue('src') || '').slice(0, 160)); } catch (e) { faces.push('X ' + s.href); } }
    const used = new Set([...document.querySelectorAll('h1,h2,h3,p,a,button,span')].slice(0, 400).map((e) => getComputedStyle(e).fontFamily));
    return { title: document.title, faces, used: [...used] };
  });
  console.log(JSON.stringify(facts, null, 1));
  const m = html.match(/di-uploads-pod\d+\.dealerinspire\.com\/[a-z0-9-]+\/uploads\/\d{4}\/\d{2}\//g) || [];
  const c = {}; m.forEach((x) => { c[x] = (c[x] || 0) + 1; }); console.log(c);
  await b.close();
})();
