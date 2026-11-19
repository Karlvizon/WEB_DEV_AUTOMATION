// No live Compass page yet: inject the HTML field (CSS inside) + JS field into a real hustoncdjr.com page (headed Edge, bot shield)
// above the site footer, then diff every element against preview.html in the same browser and list theme leaks.
// usage: node livesim.js [url]
const { chromium } = require('playwright-core');
const FIELDS = process.env.CMSDIR || require('path').resolve(__dirname, '../..', JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).platform === 'dealer-inspire' ? 'cms-fields' : 'tools/_work/fields');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = process.argv[2] || 'https://www.bridgetoncadillac.com/';
const css = fs.readFileSync(path.join(FIELDS, '{{NAME}}.css'), 'utf8');
const js = fs.readFileSync(path.join(FIELDS, '{{NAME}}.js'), 'utf8');
const CDN = '{{CDN}}';
const grab = () => {
  const w = document.querySelector('#{{ID}} .{{P}}-wrap').getBoundingClientRect();
  return [...document.querySelectorAll('#{{ID}} .{{P}}-wrap h1,#{{ID}} .{{P}}-wrap h2,#{{ID}} .{{P}}-wrap h3,#{{ID}} .{{P}}-wrap h4,#{{ID}} .{{P}}-wrap p,#{{ID}} .{{P}}-wrap a,#{{ID}} .{{P}}-wrap img,#{{ID}} .{{P}}-stat,#{{ID}} .{{P}}-band,#{{ID}} .{{P}}-pc,#{{ID}} .{{P}}-split,#{{ID}} .{{P}}-c3,#{{ID}} .{{P}}-lc,#{{ID}} .{{P}}-trim,#{{ID}} .{{P}}-gal__cell,#{{ID}} .{{P}}-seo__card,#{{ID}} .{{P}}-cta')]
    .filter((e) => !e.closest('[data-clone]') && !e.closest('.{{P}}-car__track'))
    .map((e) => { const q = e.getBoundingClientRect(); const cs = getComputedStyle(e);
      return [e.tagName + '.' + String(e.className).split(' ').filter((c) => c.indexOf('stat-') !== 0)[0] || '', Math.round(q.left - w.left), Math.round(q.top - w.top), Math.round(q.width), Math.round(q.height), cs.fontFamily.split(',')[0].replace(/"/g, ''), cs.fontSize, cs.fontWeight, cs.color, cs.textTransform, cs.letterSpacing].join(','); });
};
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  for (const W of [1920, 390]) {
    const ctx = await b.newContext({ viewport: { width: W, height: 1000 }, locale: 'en-US' });
    const p = await ctx.newPage();
    for (let t = 0; t < 6; t++) {
      await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
      await p.waitForTimeout(6000);
      if (await p.evaluate(() => !!document.querySelector('footer')).catch(() => false)) break;
    }
    const sb = await p.evaluate(() => innerWidth - document.documentElement.clientWidth);
    const fieldHtml = fs.readFileSync(path.join(FIELDS, '{{NAME}}.html'), 'utf8');
    await p.route(CDN + '{{P}}-*', (r) => r.fulfill({ path: path.join(ROOT, 'assets/webp', r.request().url().split('/').pop()), contentType: 'image/webp' }));
    const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.evaluate(([css, html]) => {
      const holder = document.createElement('div'); holder.innerHTML = html;
      const foot = document.querySelector('footer'); foot.parentNode.insertBefore(holder.firstElementChild, foot);
    }, [css, fieldHtml]);
    await p.addScriptTag({ content: js });
    await p.evaluate(() => { document.querySelectorAll('#{{ID}} img').forEach((i) => { i.loading = 'eager'; }); document.getElementById('{{ID}}').scrollIntoView(); });
    await p.waitForTimeout(4000);
    const live = await p.evaluate(grab);
    const leaks = await p.evaluate(() => {
      const out = [];
      for (const e of document.querySelectorAll('#{{ID}} .{{P}}-wrap h1,#{{ID}} .{{P}}-wrap h2,#{{ID}} .{{P}}-wrap h3,#{{ID}} .{{P}}-wrap h4,#{{ID}} .{{P}}-wrap p,#{{ID}} .{{P}}-wrap a')) {
        const cs = getComputedStyle(e);
        if (!/Roboto/.test(cs.fontFamily)) out.push('font ' + cs.fontFamily.split(',')[0] + ' on ' + e.tagName + '.' + e.className);
        if (cs.textTransform === 'uppercase' && !/{{P}}-hero__|{{P}}-btn|{{P}}-trim__h/.test(e.className) && e.innerText !== e.innerText.toUpperCase()) out.push('uppercase on ' + e.tagName + '.' + e.className);
      }
      return [...new Set(out)].slice(0, 8);
    });
    const jsok = await p.evaluate(() => document.querySelector('#{{ID}} .{{P}}-car__track').style.transform);
    const st = (sel) => p.$eval(sel, (e) => { const c = getComputedStyle(e); return c.backgroundColor + ' ' + c.borderBottomColor + ' ' + c.color + ' ' + c.textDecorationLine; });
    const btn = '#{{ID}} .{{P}}-cta--top a.{{P}}-btn >> nth=0';
    await p.$eval('#{{ID}} .{{P}}-cta--top', (e) => e.scrollIntoView({ block: 'center' })); await p.waitForTimeout(300);
    const rest = await st(btn); await p.hover(btn); await p.waitForTimeout(400); const hov = await st(btn);
    await p.mouse.move(2, 2); await p.focus('#{{ID}} .{{P}}-cta--top a.{{P}}-btn >> nth=1'); await p.waitForTimeout(400); const focHeld = await p.evaluate(() => { const a = document.activeElement; return a ? (a.className + ' ' + (a.textContent || '').trim()).slice(0, 60) : 'none'; }); console.log('   focus held by: ' + focHeld);
    const foc = await st('#{{ID}} .{{P}}-cta--top a.{{P}}-btn >> nth=1');
    const states = `rest ${rest} | hover ${hov} | focus ${foc}`;
    const statesOk = rest.startsWith('rgb(0, 0, 102) rgb(255, 255, 255) rgb(255, 255, 255) none') && hov.startsWith('rgb(52, 58, 64) rgb(255, 255, 255) rgb(255, 255, 255) none') && foc.startsWith('rgb(52, 58, 64) rgb(255, 255, 255) rgb(255, 255, 255)');
    await p.screenshot({ path: path.join(ROOT, `qa/live/livesim-${W}.png`) });
    await ctx.close();
    const c2 = await b.newContext({ viewport: { width: W, height: 1000 } });
    const q = await c2.newPage();
    await q.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
    await q.waitForTimeout(3000);
    const ref = await q.evaluate(grab);
    await c2.close();
    const diffs = live.map((x, i) => [x, ref[i]]).filter(([x, y]) => x !== y);
    console.log(`${W}px live page + new HTML field (CSS inside, no CSS slot): ${live.length} elements, ${diffs.length} differ from preview; theme leaks: ${leaks.length ? leaks.join(' | ') : 'none'}; JS field ran: ${jsok ? 'yes (' + jsok + ')' : 'NO'}; JS errors from our field: ${errs.filter((m) => /gy-|CP\./.test(m)).length}; button states in theme ${statesOk ? 'ok' : 'WRONG'} (${states})`);
    diffs.slice(0, 6).forEach(([x, y]) => console.log('   live ' + x + '\n   prev ' + y));
  }
  await b.close();
})();
