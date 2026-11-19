// Carousel (arrows, dots, wrap-around, keyboard, swipe, focus), button hover/focus colours, links, reduced motion.
// Desktop shows a centred PAIR of category cards (Figma: Trucks + Electrics), the active card is the left one; phones show one centred card.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = 'file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/');
const NAMES = JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).carousel || ['New Jeep® SUVs', 'New Jeep® Trucks', 'New Jeep® Electrics', 'New Jeep® Hybrids'];
const NC = NAMES.length;
const N = NAMES.length;
const W = 'rgb(255, 255, 255)', K = 'rgb(0, 0, 0)', NAVY = 'rgb(0, 0, 102)', SLATE = 'rgb(52, 58, 64)';
const PJ = JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8'));
const QA = Object.assign({ btn: [NAVY, W, SLATE, W], arrow: [SLATE, NAVY], car_cta: [W, K, K, W], pair: true }, PJ.qa || {});
const SITE = (PJ.site || 'https://www.hustoncdjr.com').replace(/\/$/, '');
const out = []; let fails = 0;
const ok = (c, msg) => { out.push((c ? 'ok   ' : 'FAIL ') + msg); if (!c) fails++; };
const state = (p) => p.evaluate((PAIR) => {
  const view = document.querySelector('.{{P}}-car').getBoundingClientRect(); const mid = view.left + view.width / 2;
  const sec = document.querySelector('.{{P}}-disc').getBoundingClientRect();
  const pair = PAIR ? innerWidth > 1024 : false;
  const slides = [...document.querySelectorAll('.{{P}}-car__slide')];
  const key = (s) => { const r = s.getBoundingClientRect(); return Math.abs((pair ? r.right : r.left + r.width / 2) - mid); };
  const s = slides.slice().sort((a, b) => key(a) - key(b))[0];
  const r = s.getBoundingClientRect(); const last = pair ? s.nextElementSibling.getBoundingClientRect() : r;
  const dot = [...document.querySelectorAll('.{{P}}-car__dot')].findIndex((d) => d.getAttribute('aria-current') === 'true');
  return { name: s.querySelector('h3').innerText.trim(), whole: r.left >= Math.max(view.left, sec.left) - 1 && last.right <= Math.min(pair ? sec.right : view.right, innerWidth) + 1, offset: Math.round((pair ? r.right : r.left + r.width / 2) - mid), dot };
}, QA.pair);
async function carousel(p, label) {
  let c = await state(p);
  ok(c.name === NAMES[1] && c.dot === 1 && Math.abs(c.offset) <= 1, `${label}: starts on ${c.name} (offset ${c.offset}px), dot 2 active (Figma shows Trucks + Electrics)`);
  ok(c.whole, `${label}: active slide${label === '1920' ? ' pair' : ''} fully visible`);
  let good = true; const seen = [];
  for (let i = 2; i < 10; i++) {
    await p.click('.{{P}}-car__arrow--next'); await p.waitForTimeout(750);
    c = await state(p); seen.push(c.name.replace('New Jeep® ', ''));
    if (c.name !== NAMES[i % N] || c.dot !== i % N || Math.abs(c.offset) > 1 || !c.whole) good = false;
  }
  ok(good, `${label}: next arrow steps one slide per click and wraps (${seen.join(' > ')})`);
  good = true;
  for (let i = 9; i > 1; i--) {
    await p.click('.{{P}}-car__arrow--prev'); await p.waitForTimeout(750);
    c = await state(p); if (c.name !== NAMES[(i - 1) % N] || Math.abs(c.offset) > 1 || !c.whole) good = false;
  }
  ok(good, `${label}: prev arrow steps back and wraps`);
  for (const d of [0, N - 1, N - 2]) {
    await p.click(`.{{P}}-car__dot >> nth=${d}`); await p.waitForTimeout(750); c = await state(p);
    ok(c.name === NAMES[d] && c.dot === d && c.whole, `${label}: dot ${d + 1} shows ${c.name}`);
  }
}
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const errs = [];
  let p = await (await b.newContext({ viewport: { width: 1920, height: 1000 } })).newPage();
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(URL, { waitUntil: 'load' }); await p.evaluate(() => document.fonts.ready);
  await p.evaluate(() => document.querySelector('.{{P}}-disc').scrollIntoView()); await p.waitForTimeout(400);
  await carousel(p, '1920');
  await p.click('.{{P}}-car__dot >> nth=' + (NC - 1)); await p.waitForTimeout(750);
  await p.focus('.{{P}}-car'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(750);
  let c = await state(p); ok(c.name === NAMES[0], 'keyboard ArrowRight on the carousel steps forward (wraps to ' + c.name + ')');
  await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(750); c = await state(p); ok(c.name === NAMES[N - 1], 'keyboard ArrowLeft steps back (' + c.name + ')');
  await p.focus('.{{P}}-car__slide:not([data-clone]) a.{{P}}-car__cta >> nth=1'); await p.waitForTimeout(750); c = await state(p);
  ok(c.name === NAMES[1], 'tabbing to a slide link brings that slide into the active position');
  ok(await p.$$eval('.{{P}}-car__slide[data-clone] a', (a) => a.every((x) => x.tabIndex === -1)), 'clone slides are out of the tab order');
  const bg = (s) => p.$eval(s, (e) => getComputedStyle(e).backgroundColor);
  const col = (s) => p.$eval(s, (e) => getComputedStyle(e).color);
  const states = [
    ['.{{P}}-cta--top a.{{P}}-btn >> nth=0', ...QA.btn, 'VIEW INVENTORY (hero bar; Figma slate = its hover state)'],
    ['.{{P}}-cta--top a.{{P}}-btn >> nth=3', ...QA.btn, 'GET PRE-APPROVED (hero bar)'],
    ['.{{P}}-cta__row--solo a.{{P}}-btn >> nth=0', ...QA.btn, 'VIEW INVENTORY (single bar; Figma slate = hover)'],
    ['.{{P}}-cta__row--solo a.{{P}}-btn >> nth=1', ...QA.btn, 'GET A QUOTE (single bar)'],
    ['.{{P}}-cta:not(.{{P}}-cta--top) .{{P}}-cta__row:not(.{{P}}-cta__row--solo) a.{{P}}-btn >> nth=0', ...QA.btn, 'VIEW INVENTORY (closing bar)'],
    ['.{{P}}-car__arrow--next', QA.arrow[0], null, QA.arrow[1], null, 'carousel arrow'],
    ['.{{P}}-car__slide:not([data-clone]) a.{{P}}-car__cta >> nth=1', ...QA.car_cta, 'carousel CTA'],
  ];
  for (const [s, rb, rc, hb, hc, name] of states) {
    await p.mouse.move(0, 0); await p.evaluate(() => document.activeElement && document.activeElement.blur()); await p.waitForTimeout(300);
    await p.$eval(s, (e) => e.scrollIntoView({ block: 'center' })); await p.waitForTimeout(800);
    const box0 = await p.$eval(s, (e) => JSON.stringify(e.getBoundingClientRect()));
    ok(await bg(s) === rb && (rc === null || await col(s) === rc), `${name} at rest ${rb} / ${rc}`);
    await p.hover(s); await p.waitForTimeout(350);
    ok(await bg(s) === hb && (hc === null || await col(s) === hc), `${name} hover ${hb} / ${hc}`);
    ok(await p.$eval(s, (e) => JSON.stringify(e.getBoundingClientRect())) === box0, `${name} hover does not move or resize it`);
    await p.mouse.move(0, 0); await p.focus(s); await p.waitForTimeout(350);
    ok(await bg(s) === hb, `${name} focus state = hover state`);
  }
  await p.mouse.move(0, 0);
  const links = await p.$$eval('.{{P}}-wrap a', (as) => as.map((a) => [a.getAttribute('href'), a.target, a.rel, a.className]));
  const cta = links.filter((l) => /{{P}}-btn|{{P}}-car__cta/.test(l[3]));
  ok(cta.every(([h]) => h.indexOf(SITE + '/') === 0), `all ${cta.length} button links go to ${SITE} (the links sent for this project)`);
  ok(links.every(([, t, r]) => t === '_blank' && r === 'noopener'), `all ${links.length} links open in a new tab (target=_blank rel=noopener)`);
  ok(!(await p.$$('[data-todo-link]')).length, 'no button is missing its link');
  await p.context().close();
  p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(URL, { waitUntil: 'load' }); await p.evaluate(() => document.fonts.ready);
  await p.evaluate(() => document.querySelector('.{{P}}-car').scrollIntoView({ block: 'center' })); await p.waitForTimeout(400);
  await carousel(p, '390 phone');
  const swipe = (dx) => p.evaluate((dx) => {
    const v = document.querySelector('.{{P}}-car'); const r = v.getBoundingClientRect(); const y = r.top + r.height / 2, x = r.left + r.width / 2;
    const t = (cx) => new Touch({ identifier: 1, target: v, clientX: cx, clientY: y });
    v.dispatchEvent(new TouchEvent('touchstart', { touches: [t(x)], changedTouches: [t(x)], bubbles: true }));
    [0.25, 0.5, 0.75, 1].forEach((f) => v.dispatchEvent(new TouchEvent('touchmove', { touches: [t(x + dx * f)], changedTouches: [t(x + dx * f)], bubbles: true })));
    v.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [t(x + dx)], bubbles: true }));
  }, dx);
  c = await state(p); const before = c.dot;
  await swipe(-120); await p.waitForTimeout(750); c = await state(p); ok(c.dot === (before + 1) % N && c.whole, 'phone: swipe left goes to the next slide, shown whole');
  await swipe(120); await p.waitForTimeout(750); c = await state(p); ok(c.dot === before, 'phone: swipe right goes back');
  await swipe(-20); await p.waitForTimeout(750); c = await state(p); ok(c.dot === before, 'phone: a 20px nudge (under the 40px minimum) does not change slide');
  await p.context().close();
  p = await (await b.newContext({ viewport: { width: 1920, height: 1000 }, reducedMotion: 'reduce' })).newPage();
  await p.goto(URL, { waitUntil: 'load' });
  ok(await p.$eval('.{{P}}-car__track', (t) => getComputedStyle(t).transitionDuration === '0s'), 'prefers-reduced-motion: carousel moves without animation');
  ok(await p.$eval('a.{{P}}-btn', (t) => getComputedStyle(t).transitionDuration === '0s'), 'prefers-reduced-motion: no button colour transitions');
  ok(!errs.length, 'no JS errors' + (errs.length ? ': ' + errs.join(' | ') : ''));
  console.log(out.join('\n') + `\n\n${out.length} checks, ${fails} failed`);
  fs.writeFileSync(path.join(ROOT, 'qa/interact.txt'), out.join('\n') + `\n${out.length} checks, ${fails} failed\n`);
  await b.close();
})();
