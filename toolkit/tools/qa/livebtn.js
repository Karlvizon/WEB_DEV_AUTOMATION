// Live page, phone/tablet: every CTA button must scroll fully into view clear of the real site header/bottom bar.
// The cookie-consent banner is hidden for the test (a visitor dismisses it once); it is reported separately.
const { chromium } = require('playwright-core');
const URL = process.argv[2];
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  for (const [w, h] of (process.env.SIZES ? process.env.SIZES.split(',').map((s) => s.split('x').map(Number)) : [[390, 844], [375, 812], [844, 390], [768, 1024], [1024, 768]])) {
    const p = await (await b.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true })).newPage();
    for (let t = 0; t < 6; t++) { await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(6000); if (await p.evaluate(() => !!document.getElementById('{{ID}}')).catch(() => false)) break; }
    const consent = await p.evaluate(() => { const c = [...document.querySelectorAll('div,section,aside')].filter((e) => /Your Privacy & Cookies/.test(e.textContent || '') && getComputedStyle(e).position === 'fixed'); c.forEach((e) => { e.style.setProperty('display', 'none', 'important'); }); return c.length; });
    await p.waitForTimeout(500);
    const r = await p.evaluate(async () => {
      const bad = []; const btns = [...document.querySelectorAll('#{{ID}} a.{{P}}-btn,#{{ID}} a.{{P}}-cta2,#{{ID}} .{{P}}-car__arrow')];
      let topBar = 0, botBar = 0;
      for (const bt of btns) {
        document.documentElement.style.setProperty('scroll-behavior', 'auto', 'important'); document.body.style.setProperty('scroll-behavior', 'auto', 'important'); const y0 = bt.getBoundingClientRect(); window.scrollTo({ top: scrollY + y0.top - (innerHeight - y0.height) / 2, behavior: 'instant' }); await new Promise((r) => setTimeout(r, 1400));
        const q = bt.getBoundingClientRect();
        const pts = [[q.left + q.width / 2, q.top + 3], [q.left + q.width / 2, q.bottom - 3], [q.left + 4, q.top + q.height / 2], [q.right - 4, q.top + q.height / 2]];
        const hidden = pts.filter(([x, y]) => { const e = document.elementFromPoint(x, y); return !e || !bt.contains(e); });
        if (hidden.length) { const e = document.elementFromPoint(pts[0][0], pts[0][1]); bad.push(bt.innerText.trim() + ' covered by ' + (e ? e.tagName + '.' + String(e.className).split(' ')[0] : 'nothing')); }
      }
      for (const e of document.querySelectorAll('body *')) { const cs = getComputedStyle(e); if (cs.position === 'fixed' || cs.position === 'sticky') { const q = e.getBoundingClientRect(); if (q.height > 20 && q.height < 200 && q.width > innerWidth * 0.8) { if (q.top <= 1) topBar = Math.max(topBar, q.bottom); else if (q.bottom >= innerHeight - 1) botBar = Math.max(botBar, innerHeight - q.top); } } }
      return { n: btns.length, bad, topBar: Math.round(topBar), botBar: Math.round(botBar) };
    });
    console.log(`${w}x${h}: ${r.n} buttons, ${r.bad.length ? r.bad.length + ' blocked: ' + r.bad.join('; ') : 'all fully visible and clickable'} | site header ${r.topBar}px, bottom bar ${r.botBar}px | cookie banner present: ${consent ? 'yes (hidden for test)' : 'no'}`);
    await p.context().close();
  }
  await b.close();
})();
