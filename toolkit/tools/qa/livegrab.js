// Load the live page in a real (headed) Edge so the bot shield clears, then save source + computed facts.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = process.argv[2] || 'https://www.bridgetoncdjr.com/2026-jeep-compass-cherry-hill/';
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1000 }, locale: 'en-US' });
  const p = await ctx.newPage();
  for (let t = 0; t < 6; t++) {
    await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
    await p.waitForTimeout(7000);
    if (await p.evaluate(() => !!document.getElementById('jc-2026-compass')).catch(() => false)) break;
  }
  const html = await p.content();
  fs.writeFileSync(path.join(ROOT, 'qa/live/live.html'), html);
  const facts = await p.evaluate(() => {
    const root = document.getElementById('jc-2026-compass');
    if (!root) return { found: false, title: document.title };
    const pc = [...document.querySelectorAll('style,link[rel=stylesheet]')];
    const ours = [...document.styleSheets].filter((s) => { try { return [...s.cssRules].some((r) => (r.selectorText || '').includes('#jc-2026-compass')); } catch (e) { return false; } });
    const hero = root.querySelector('.cp-hero');
    const h = root.querySelector('h2');
    const cs = (e) => e ? getComputedStyle(e) : {};
    const anc = []; let a = root.parentElement; while (a && anc.length < 8) { anc.push(a.tagName + (a.id ? '#' + a.id : '') + (a.className ? '.' + String(a.className).trim().split(/\s+/).join('.') : '')); a = a.parentElement; }
    return { found: true, title: document.title, sheetsWithOurRules: ours.length, ourSheetOwners: ours.map((s) => (s.ownerNode && (s.ownerNode.id || s.ownerNode.tagName)) + ' ' + (s.href || 'inline')),
      heroDisplay: cs(hero).display, heroHeight: hero ? Math.round(hero.getBoundingClientRect().height) : 0,
      h2Font: cs(h).fontFamily, h2Transform: cs(h).textTransform, wrapWidth: Math.round(root.getBoundingClientRect().width), vw: document.documentElement.clientWidth,
      ancestors: anc, styleTags: pc.length, scripts: document.querySelectorAll('script#di-page-composer-scripts').length };
  });
  console.log(JSON.stringify(facts, null, 1));
  await p.screenshot({ path: path.join(ROOT, 'qa/live/live-1920.png') });
  await b.close();
})();
