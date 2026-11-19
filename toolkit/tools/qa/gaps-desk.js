// Desktop vertical-gap audit: visible gap between consecutive content blocks (headings, buttons, cards, images) down the page.
// usage: node gaps-desk.js [width]   -> prints gaps over 40px (design px at 1920)
const { chromium } = require('playwright-core');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
(async () => {
  const W = +process.argv[2] || 1920;
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: W, height: 1000 } });
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => innerWidth - document.documentElement.clientWidth);
  await p.setViewportSize({ width: W + sb, height: 1000 }); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
  if (process.env.DBG) await p.evaluate(() => { window.DBG = 1; });
  const r = await p.evaluate(() => {
    const w = document.querySelector('.{{P}}-wrap').getBoundingClientRect();
    const sel = '.{{P}}-hero, .{{P}}-disc, .{{P}}-gal__in, .{{P}}-lg, .{{P}}-eng, .{{P}}-storm__bg, .{{P}}-storm__in, .{{P}}-cold, .{{P}}-wrap .{{P}}-pic, .{{P}}-wrap .{{P}}-r100, .{{P}}-gb__img, .{{P}}-g4, a.{{P}}-btn, .{{P}}-kicker, .{{P}}-wrap h2, .{{P}}-wrap h3.{{P}}-h2, .{{P}}-sub, .{{P}}-blk>.{{P}}-m, .{{P}}-stats, .{{P}}-fc, .{{P}}-ib, .{{P}}-dp, .{{P}}-fx, .{{P}}-oc, .{{P}}-band, .{{P}}-sr, .{{P}}-gb, .{{P}}-cn__hd, .{{P}}-ct, .{{P}}-trim, .{{P}}-seo__item, .{{P}}-legal';
    const els = [...document.querySelectorAll(sel)].filter((e) => !e.closest('[data-clone]') && !e.parentElement.closest('.{{P}}-ov,.{{P}}-gb,.{{P}}-dp,.{{P}}-ct,.{{P}}-ib,.{{P}}-fx,.{{P}}-oc,.{{P}}-band'));
    const boxes = els.map((e) => { const q = e.getBoundingClientRect(); return { t: q.top - w.top, b: q.bottom - w.top, n: (e.className + ' ' + (e.innerText || '').slice(0, 24)).replace(/\s+/g, ' ') }; }).sort((a, b) => a.t - b.t);
    const out = []; let maxB = boxes[0].b, last = boxes[0];
    for (const x of boxes.slice(1)) { if (x.t > maxB + 0.5) out.push([Math.round(x.t - maxB), last.n.slice(0, 40), x.n.slice(0, 40)]); if (x.b > maxB) { maxB = x.b; last = x; } }
    if (window.DBG) return boxes.slice(0, 30).map((x) => [Math.round(x.t), Math.round(x.b), x.n.slice(0, 30)]);
    return out;
  });
  if (process.env.DBG) { console.log(JSON.stringify(r)); await b.close(); return; }
  const s = 1920 / W;
  r.filter((g) => g[0] * s > 40).forEach((g) => console.log(String(Math.round(g[0] * s)).padStart(5), ' ', g[1].padEnd(42), '->', g[2]));
  await b.close();
})();
