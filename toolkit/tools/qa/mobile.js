// Mobile buttons with an emulated 90px sticky header + 60px sticky bottom bar, and mobile spacing.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const views = [[390, 844], [844, 390], [375, 812], [320, 568], [430, 932], [768, 1024], [1024, 768]];
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const out = [];
  for (const [w, h] of views) {
    const p = await (await b.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })).newPage();
    const src = fs.readFileSync(path.join(ROOT, 'preview.html'), 'utf8')
      .replace('<body>', '<body><div style="position:sticky;top:0;height:90px;background:#222;z-index:50" id="fake-head"></div>')
      .replace('</body>', '<div style="position:sticky;bottom:0;height:60px;background:#222;z-index:50" id="fake-bar"></div></body>');
    const tmp = path.join(ROOT, 'qa/_chrome.html'); fs.writeFileSync(tmp, src);
    await p.goto('file:///' + tmp.split(path.sep).join('/'), { waitUntil: 'load' });
    await p.waitForTimeout(600);
    const r = await p.evaluate(async () => {
      const res = { bad: [] };
      const btns = [...document.querySelectorAll('.{{P}}-wrap a.{{P}}-btn,.{{P}}-wrap .{{P}}-car__slide:not([data-clone]) a.{{P}}-car__cta')].filter((b) => { const s = b.closest('.{{P}}-car__slide'); if (!s) return true; return Math.abs(s.getBoundingClientRect().left + s.getBoundingClientRect().width / 2 - innerWidth / 2) < 30; });
      const H = innerHeight;
      for (const bt of btns) {
        bt.scrollIntoView({ block: 'center' }); await new Promise((r) => setTimeout(r, 30));
        const q = bt.getBoundingClientRect();
        if (q.top < 90 || q.bottom > H - 60) res.bad.push('button hidden by site chrome "' + bt.innerText + '"');
        const hit = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
        if (!bt.contains(hit)) res.bad.push('button covered "' + bt.innerText + '"');
        const rg = document.createRange(); rg.selectNodeContents(bt); const t = rg.getBoundingClientRect();
        if (Math.abs((t.left + t.width / 2) - (q.left + q.width / 2)) > 1.5 || Math.abs((t.top + t.height / 2) - (q.top + q.height / 2)) > 2) res.bad.push('label off-centre "' + bt.innerText + '"');
        if (t.height > parseFloat(getComputedStyle(bt).lineHeight) * 1.5) res.bad.push('label wraps "' + bt.innerText + '"');
        if (q.height < 48) res.bad.push('button < 48px "' + bt.innerText + '"');
      }
      const sizes = btns.map((b) => { const q = b.getBoundingClientRect(); return Math.round(q.width) + 'x' + Math.round(q.height); });
      res.sizes = [...new Set(sizes)]; res.n = btns.length;
      const hero = [...document.querySelector('.{{P}}-cta--top').querySelectorAll('a')].map((a) => a.getBoundingClientRect());
      res.heroGaps = [...new Set(hero.slice(1).map((q, i) => Math.round(Math.max(q.top - hero[i].bottom, q.left - hero[i].right))).filter((v) => v >= 0))];
      const gap = (a, b) => (a && b ? Math.round(b.getBoundingClientRect().top - a.getBoundingClientRect().bottom) : 'n/a');
      const q = (s) => document.querySelector(s);
      const two = innerWidth > 768 ? 2 : 1;
      const nth = (s, i) => document.querySelectorAll(s)[i];
      const all = (s2) => document.querySelectorAll(s2);
      const ctas = all('.{{P}}-cta');
      const wcols = innerWidth > 768 ? 4 : 2;
      res.spacing = {
        'heading->sub': gap(q('.{{P}}-gb .{{P}}-h2'), q('.{{P}}-gb .{{P}}-sub')),
        'card image->title': gap(q('.{{P}}-g3 .{{P}}-fc .{{P}}-m'), q('.{{P}}-g3 .{{P}}-fc .{{P}}-t')),
        'card title->text': gap(q('.{{P}}-g3 .{{P}}-fc .{{P}}-t'), q('.{{P}}-g3 .{{P}}-fc .{{P}}-p')),
        'feature card->card': gap(nth('.{{P}}-g3 .{{P}}-fc', 0), nth('.{{P}}-g3 .{{P}}-fc', two)),
        'wheel->wheel row': all('.{{P}}-wh').length > wcols ? gap(nth('.{{P}}-wh', 0), nth('.{{P}}-wh', wcols)) : 'one row',
        'band->band': gap(nth('.{{P}}-band', 0), nth('.{{P}}-band', 1)),
        'trim->trim': gap(nth('.{{P}}-trim', 0), nth('.{{P}}-trim', two)),
        'seo item->item': gap(nth('.{{P}}-seo__item', 0), nth('.{{P}}-seo__item', 1)),
        'trims->CTA row': gap(q('.{{P}}-trims'), ctas[ctas.length - 1]),
        'section->CTA bar': gap(nth('.{{P}}-col.{{P}}-b', 1), ctas[1]),
        'CTA bar->section': gap(ctas[1], nth('.{{P}}-col.{{P}}-b', 2)),
        'carousel card internals': gap(q('.{{P}}-car__slide:not([data-clone]) .{{P}}-car__h'), q('.{{P}}-car__slide:not([data-clone]) .{{P}}-car__img')),
      };
      return res;
    });
    out.push(`${w}x${h}: ${r.bad.length ? r.bad.length + ' problems: ' + [...new Set(r.bad)].join('; ') : 'all ' + r.n + ' buttons fully visible between header and bottom bar, labels centred and single-line'}\n   button sizes ${r.sizes.join(' ')} | hero CTA gaps ${r.heroGaps.join(',')}px\n   spacing ${Object.entries(r.spacing).map(([k, v]) => k + ' ' + v).join(' | ')}`);
    await p.context().close();
  }
  fs.rmSync(path.join(ROOT, 'qa/_chrome.html'), { force: true });
  console.log(out.join('\n'));
  fs.writeFileSync(path.join(ROOT, 'qa/mobile.txt'), out.join('\n') + '\n');
  await b.close();
})();
