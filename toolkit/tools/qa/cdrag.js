// Carousel drag/swipe/click test on preview.html at real speed. usage: node cdrag.js
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const URL = 'file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/');
const NC = (JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).carousel || [1, 2, 3, 4]).length;
const dot = (p) => p.evaluate(() => [...document.querySelectorAll('.{{P}}-car__dot')].findIndex((d) => d.getAttribute('aria-current') === 'true') + 1);
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const out = [];
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(URL, { waitUntil: 'load' }); await p.waitForTimeout(800);
  await p.evaluate(() => document.querySelector('.{{P}}-car').scrollIntoView({ block: 'center' })); await p.waitForTimeout(400);
  const box = await p.locator('.{{P}}-car').boundingBox();
  const cy = box.y + box.height * 0.35;
  async function drag(x0, dx) { await p.mouse.move(x0, cy); await p.mouse.down(); for (let i = 1; i <= 15; i++) { await p.mouse.move(x0 + dx * i / 15, cy); await p.waitForTimeout(16); } await p.mouse.up(); await p.waitForTimeout(900); }
  let d0 = await dot(p); await drag(1200, -300); let d1 = await dot(p); out.push(`mouse drag left 300px: dot ${d0} -> ${d1} ${d1 === d0 % NC + 1 ? 'ok' : 'WRONG'}`);
  d0 = d1; await drag(700, 300); d1 = await dot(p); out.push(`mouse drag right 300px: dot ${d0} -> ${d1} ${d1 === (d0 + 2) % 4 + 1 ? 'ok' : 'WRONG'}`);
  d0 = d1; await drag(900, -20); d1 = await dot(p); out.push(`mouse drag 20px (below 40 threshold): dot ${d0} -> ${d1} ${d1 === d0 ? 'ok (snaps back)' : 'WRONG'}`);
  const cur = await p.evaluate(() => getComputedStyle(document.querySelector('.{{P}}-car')).cursor); out.push(`cursor on carousel: ${cur}`);
  // drag starting on a CTA must not open it
  let pops = 0; ctx.on('page', () => pops++);
  const ctas = p.locator('.{{P}}-car__slide:not([data-clone]) .{{P}}-car__cta');
  const vis = []; for (let i = 0; i < NC; i++) { const r = await ctas.nth(i).boundingBox(); if (r && r.x > 0 && r.x + r.width < 1920) vis.push(i); }
  const r0 = await ctas.nth(vis[0]).boundingBox();
  await p.mouse.move(r0.x + 50, r0.y + 20); await p.mouse.down(); for (let i = 1; i <= 15; i++) { await p.mouse.move(r0.x + 50 - 200 * i / 15, r0.y + 20); await p.waitForTimeout(16); } await p.mouse.up(); await p.waitForTimeout(900);
  out.push(`drag starting on a CTA: new tabs opened ${pops} ${pops === 0 ? 'ok' : 'WRONG'}`);
  // plain clicks on every visible CTA (incl. side card) open it and do not move the carousel
  const vis2 = []; for (let i = 0; i < NC; i++) { const r = await ctas.nth(i).boundingBox(); if (r && r.x > 0 && r.x + r.width < 1920) vis2.push(i); }
  for (const i of vis2) {
    const before = await dot(p); pops = 0;
    await p.evaluate(() => document.querySelectorAll('.{{P}}-car__cta').forEach((a) => a.setAttribute('href', 'about:blank')));
    await ctas.nth(i).click({ delay: 150 }); await p.waitForTimeout(900);
    const after = await dot(p);
    out.push(`click CTA ${i + 1} (${vis2.length} visible): new tab ${pops} carousel ${before}->${after} ${pops === 1 && before === after ? 'ok' : 'WRONG'}`);
    for (const pg of ctx.pages()) if (pg !== p) await pg.close();
  }
  // keyboard
  await p.focus('.{{P}}-car'); d0 = await dot(p); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(800); d1 = await dot(p); out.push(`keyboard ArrowRight: ${d0} -> ${d1} ${d1 === d0 % NC + 1 ? 'ok' : 'WRONG'}`);
  // wrap-around via dots/arrows
  await p.click('.{{P}}-car__dot >> nth=' + (NC - 1)); await p.waitForTimeout(800); await p.click('.{{P}}-car__arrow--next'); await p.waitForTimeout(900); out.push(`wrap ${NC} -> next: ${await dot(p)} ${(await dot(p)) === 1 ? 'ok' : 'WRONG'}`);
  await p.click('.{{P}}-car__arrow--prev'); await p.waitForTimeout(900); out.push(`wrap 1 -> prev: ${await dot(p)} ${(await dot(p)) === NC ? 'ok' : 'WRONG'}`);
  out.push(`desktop JS errors ${errs.length}`);
  // touch swipe on phone
  const m = await b.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const q = await m.newPage(); await q.goto(URL, { waitUntil: 'load' }); await q.waitForTimeout(800);
  await q.evaluate(() => document.querySelector('.{{P}}-car').scrollIntoView({ block: 'center' })); await q.waitForTimeout(400);
  const mb = await q.locator('.{{P}}-car').boundingBox(); const cdp = await m.newCDPSession(q);
  async function swipe(x0, dx) { const y = mb.y + 120; await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x0, y }] }); for (let i = 1; i <= 10; i++) { await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x0 + dx * i / 10, y }] }); await q.waitForTimeout(16); } await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await q.waitForTimeout(900); }
  d0 = await dot(q); await swipe(300, -150); d1 = await dot(q); out.push(`phone swipe left: ${d0} -> ${d1} ${d1 === d0 % NC + 1 ? 'ok' : 'WRONG'}`);
  const cen = await q.evaluate(() => { const s = [...document.querySelectorAll('.{{P}}-car__slide')].map((e) => e.getBoundingClientRect()).find((r) => r.left >= -1 && r.right <= innerWidth + 1); return s ? Math.round(s.left + s.width / 2 - innerWidth / 2) : 'none whole'; });
  out.push(`phone active slide fully visible, centre offset ${cen}px`);
  console.log(out.join('\n')); await b.close();
})();
