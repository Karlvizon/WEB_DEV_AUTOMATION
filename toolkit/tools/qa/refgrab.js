// Capture a reference page at phone width in headed Edge (bot shield): usage node refgrab.js <url> <outprefix> [width]
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
(async () => {
  const [url, out, wArg] = process.argv.slice(2); const W = +wArg || 390;
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: W, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const p = await ctx.newPage();
  for (let t = 0; t < 4; t++) { await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(7000); if (await p.evaluate(() => !!document.querySelector('.main-div')).catch(() => false)) break; }
  const info = await p.evaluate(() => { const m = document.querySelector('.main-div'); const r = m.getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; });
  for (let y = 0; y < info.top + info.h; y += 700) { await p.evaluate((y) => scrollTo(0, y), y); await p.waitForTimeout(150); }
  await p.waitForTimeout(1500);
  const el = await p.$('.main-div');
  let i = 0; const H = 3000;
  for (let y = 0; y < info.h; y += H, i++) {
    await el.screenshot({ path: `${out}-${i}.png`, clip: undefined }).catch(() => {});
    break;
  }
  await p.evaluate(() => { document.querySelectorAll('header,.header,[class*="sticky"],#header').forEach(e => e.style.setProperty('position','static','important')); });
  await p.addStyleTag({ content: '[id*="complyauto" i],[class*="complyauto" i],[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],iframe[title*="chat" i]{display:none !important}' });
  await p.evaluate(() => { [...document.querySelectorAll('body *')].forEach((e) => { const s = getComputedStyle(e); if ((s.position === 'fixed' || s.position === 'sticky') && !e.closest('.main-div')) e.style.setProperty('display', 'none', 'important'); }); });
  const parts = []; 
  await p.setViewportSize({ width: W, height: 1200 });
  for (let y = info.top, k = 0; y < info.top + info.h; y += 1200, k++) { await p.evaluate((y) => scrollTo(0, y), y); await p.waitForTimeout(300); const f = `${out}-p${k}.png`; await p.screenshot({ path: f }); parts.push(f); }
  fs.writeFileSync(out + '-parts.json', JSON.stringify({ parts, h: info.h }));
  console.log('main-div height', info.h, 'parts', parts.length);
  await b.close();
})();
