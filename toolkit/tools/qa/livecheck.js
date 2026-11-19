// Check the PUBLISHED page as it is (no field swapping) in a headed Edge (the bot shield blocks headless/curl).
// For each width: source facts, theme leaks, images, links, horizontal scroll, and element geometry vs preview.html
// rendered at the same wrapper width (so the comparison is not skewed by the theme container or scrollbar).
// usage: node livecheck.js [url]
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = process.argv[2];
const ID = '{{ID}}';
const OUT = path.join(ROOT, 'qa/live'); fs.mkdirSync(OUT, { recursive: true });
const WIDTHS = (process.env.WIDTHS || '1920,1440,1024,768,390,375').split(',').map(Number);
const SEL = 'h1,h2,h3,h4,p,a,img,button,.{{P}}-stat,.{{P}}-band,.{{P}}-pc,.{{P}}-split,.{{P}}-c3,.{{P}}-lc,.{{P}}-trim,.{{P}}-gal__cell,.{{P}}-seo__card,.{{P}}-cta,.{{P}}-hero__box,.{{P}}-ov,.{{P}}-safety,.{{P}}-legal';
const grab = ([id, sel]) => {
  const root = document.getElementById(id); const wrap = root.querySelector('.{{P}}-wrap'); const w = wrap.getBoundingClientRect();
  return [...wrap.querySelectorAll(sel)].filter((e) => !e.closest('.{{P}}-car__track')).map((e) => {
    const q = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return { k: e.tagName + '.' + String(e.className).split(' ')[0] + ' ' + (e.innerText || e.getAttribute('alt') || '').trim().slice(0, 30),
      g: [q.left - w.left, q.top - w.top, q.width, q.height].map((v) => Math.round(v)),
      s: [cs.fontFamily.split(',')[0].replace(/"/g, ''), cs.fontSize, cs.fontWeight, cs.color, cs.textTransform, cs.letterSpacing, cs.backgroundColor].join('|') };
  });
};
async function settle(p) {
  await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; setTimeout(r, 15000); }))); });
  await p.waitForTimeout(1500);
}
async function shot(p, file, sel) {
  const r = await p.evaluate((s) => { const e = document.querySelector(s).getBoundingClientRect(); return { x: e.left + scrollX, y: e.top + scrollY, w: e.width, h: e.height }; }, sel);
  const parts = []; const dir = path.join(OUT, '_p'); fs.mkdirSync(dir, { recursive: true });
  const vh = await p.evaluate(() => innerHeight);
  for (let y = 0, i = 0; y < r.h; y += vh, i++) {
    const top = Math.min(r.y + y, r.y + r.h - vh);
    await p.evaluate((t) => window.scrollTo(0, t), Math.max(0, top)); await p.waitForTimeout(250);
    const sy = await p.evaluate(() => scrollY);
    const f = path.join(dir, `p${i}.png`);
    await p.screenshot({ path: f, clip: { x: Math.max(0, r.x), y: 0, width: Math.min(r.w, await p.evaluate(() => document.documentElement.clientWidth)), height: vh } });
    parts.push(f + ':' + Math.round(r.y + y - sy));
  }
  require('child_process').execFileSync('python', ['-I', path.join(__dirname, 'stitch.py'), file, ...parts]);
  fs.rmSync(dir, { recursive: true, force: true });
}
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const report = [];
  let sourceDone = false;
  for (const W of WIDTHS) {
    const ctx = await b.newContext({ viewport: { width: W, height: 900 }, locale: 'en-US', isMobile: W < 1025 && W < 800, hasTouch: W < 800 });
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    const bad404 = []; p.on('response', (r) => { if (r.url().includes('/uploads/') && r.status() >= 400) bad404.push(r.status() + ' ' + r.url().split('/').pop()); });
    for (let t = 0; t < 6; t++) {
      await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
      await p.waitForTimeout(6000);
      if (await p.evaluate((id) => !!document.getElementById(id), ID).catch(() => false)) break;
    }
    if (!(await p.evaluate((id) => !!document.getElementById(id), ID).catch(() => false))) { report.push(`${W}px: wrapper #${ID} NOT FOUND (title: ${await p.title()})`); await ctx.close(); continue; }
    await settle(p);
    if (!sourceDone) {
      sourceDone = true;
      const html = await p.content(); fs.writeFileSync(path.join(OUT, 'live.html'), html);
      const field = fs.readFileSync(path.join(ROOT, 'cms-fields/{{NAME}}.html'), 'utf8');
      const src = await p.evaluate((id) => {
        const root = document.getElementById(id);
        const raw = document.documentElement.outerHTML;
        const slot = raw.match(/<!-- di page composer css -->([\s\S]*?)<!-- eof: di page composer css -->/);
        return { slotFilled: slot ? slot[1].trim().length > 0 : 'slot comment not found', brInside: root.querySelectorAll('br').length,
          styleInside: root.querySelectorAll('style').length, scripts: [...document.scripts].filter((s) => s.textContent.includes(id)).length,
          todo: root.querySelectorAll('[data-todo-link]').length, hrefHash: root.querySelectorAll('a[href="#"]').length,
          pTags: root.querySelectorAll('p').length, emptyP: [...root.querySelectorAll('p')].filter((x) => !x.textContent.trim()).length,
          imgs: root.querySelectorAll('img').length, ancestors: (() => { const a = []; let e = root.parentElement; while (e && a.length < 6) { a.push(e.tagName + (e.id ? '#' + e.id : '') + (e.className ? '.' + String(e.className).trim().split(/\s+/).slice(0, 2).join('.') : '')); e = e.parentElement; } return a; })() };
      }, ID);
      const fieldP = (field.match(/<p[\s>]/g) || []).length, fieldImg = (field.match(/<img /g) || []).length;
      const liveCss = await p.evaluate((id) => document.getElementById(id).querySelector('style') ? document.getElementById(id).querySelector('style').textContent.length : 0, ID);
      report.push(`SOURCE: CSS slot filled: ${src.slotFilled} | <style> inside wrapper: ${src.styleInside} (CSS ${liveCss} chars) | <br> inside wrapper: ${src.brInside} | page scripts mentioning the id: ${src.scripts}`);
      report.push(`SOURCE: <p> live ${src.pTags} vs field ${fieldP} (empty <p> added by WordPress: ${src.emptyP}) | <img> live ${src.imgs} vs field ${fieldImg} | placeholder links live: ${src.todo} data-todo-link, ${src.hrefHash} href="#"`);
      report.push(`SOURCE: wrapper sits in ${src.ancestors.join(' < ')}`);
      const fieldCss = fs.readFileSync(path.join(ROOT, 'cms-fields/{{NAME}}.css'), 'utf8').trim();
      const fieldJs = fs.readFileSync(path.join(ROOT, 'cms-fields/{{NAME}}.js'), 'utf8').trim();
      const fresh = await p.evaluate(([css, js]) => {
        const st = document.querySelector('#{{ID}} style');
        const norm = (t) => t.replace(/\s+/g, ' ').trim();
        const scripts = [...document.scripts].filter((x) => x.textContent.includes('{{ID}}'));
        return { cssSame: st ? norm(st.textContent) === norm(css) : false, jsCount: scripts.length,
          jsSame: scripts.some((x) => norm(x.textContent).indexOf(norm(js)) >= 0), jsHasGuard: scripts.some((x) => x.textContent.includes('data-cp-ready')),
          ran: document.getElementById('{{ID}}').getAttribute('data-cp-ready'), composerScript: !!document.getElementById('di-page-composer-scripts') };
      }, [fieldCss, fieldJs]);
      report.push(`SOURCE: live <style> identical to current CSS field: ${fresh.cssSame} | JS field on page: ${fresh.jsCount} copy(ies), current JS field contained unchanged: ${fresh.jsSame}, has run-once guard: ${fresh.jsHasGuard}, ran (data-cp-ready): ${fresh.ran} | #di-page-composer-scripts present: ${fresh.composerScript}`);
    }
    const facts = await p.evaluate((id) => {
      const root = document.getElementById(id); const wrap = root.querySelector('.{{P}}-wrap');
      const vw = document.documentElement.clientWidth; const r = wrap.getBoundingClientRect();
      const leaks = [];
      for (const e of wrap.querySelectorAll('h1,h2,h3,h4,p,a,span,b,button')) {
        const cs = getComputedStyle(e);
        if (!/^"?(Roboto|Anton|Noto Sans Symbols)/.test(cs.fontFamily)) leaks.push('font ' + cs.fontFamily.split(',')[0] + ' on ' + e.tagName);
        if (cs.textTransform === 'uppercase' && !e.closest('.{{P}}-hero__mdl') && !e.closest('.{{P}}-badge') && e.innerText !== e.innerText.toUpperCase()) leaks.push('uppercase on ' + e.tagName + '.' + e.className);
      }
      const broken = [...wrap.querySelectorAll('img')].filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src').split('/').pop());
      return { vw, wrapX: Math.round(r.left), wrapW: Math.round(r.width), hscroll: document.documentElement.scrollWidth > vw + 1 ? document.documentElement.scrollWidth : 0,
        leaks: [...new Set(leaks)].slice(0, 6), broken: [...new Set(broken)] };
    }, ID);
    const live = await p.evaluate(grab, [ID, SEL]);
    const car = await p.evaluate(async () => { const dot = () => [...document.querySelectorAll('#{{ID}} .{{P}}-car__dot')].findIndex((d) => d.getAttribute('aria-current') === 'true'); const a = dot(); document.querySelector('#{{ID}} .{{P}}-car__arrow--next').click(); await new Promise((r) => setTimeout(r, 900)); const b = dot(); document.querySelector('#{{ID}} .{{P}}-car__arrow--prev').click(); await new Promise((r) => setTimeout(r, 900)); return [a + 1, b + 1, dot() + 1]; });
    let hover = 'n/a (touch)';
    if (W >= 1025) { const sel = '#{{ID}} .{{P}}-cta a.{{P}}-btn >> nth=0'; await p.$eval('#{{ID}} .{{P}}-cta', (e) => e.scrollIntoView({ block: 'center' })); await p.waitForTimeout(300); const bg = () => p.$eval(sel, (e) => getComputedStyle(e).backgroundColor); const r0 = await bg(); await p.hover(sel); await p.waitForTimeout(400); const r1 = await bg(); await p.mouse.move(2, 2); hover = (r0 === 'rgb(141, 0, 6)' && r1 === 'rgb(255, 255, 255)') ? 'ok (red -> white)' : `WRONG (${r0} -> ${r1})`; }
    await shot(p, path.join(OUT, `live-${W}.png`), '#' + ID);
    await ctx.close();
    const c2 = await b.newContext({ viewport: { width: facts.wrapW, height: 900 }, isMobile: W < 800, hasTouch: W < 800 });
    const q = await c2.newPage();
    await q.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
    const qsb = await q.evaluate(() => innerWidth - document.documentElement.clientWidth);
    if (qsb) { await q.setViewportSize({ width: facts.wrapW + qsb, height: 900 }); await q.waitForTimeout(500); }
    await settle(q);
    const ref = await q.evaluate(grab, [ID, SEL]);
    await c2.close();
    const n = Math.min(live.length, ref.length); let gd = 0, sd = 0; const ex = [];
    for (let i = 0; i < n; i++) {
      const dg = live[i].g.map((v, j) => Math.abs(v - ref[i].g[j]));
      if (Math.max(...dg) > 2) { gd++; ex.unshift(`   geom ${live[i].k} live ${live[i].g} preview ${ref[i].g}`); }
      if (live[i].s !== ref[i].s) { sd++; if (ex.length < 8) ex.push(`   style ${live[i].k} live ${live[i].s} | preview ${ref[i].s}`); }
    }
    report.push(`${W}px window -> page ${facts.vw}px, wrapper x${facts.wrapX} w${facts.wrapW}${facts.wrapW !== facts.vw ? ' (NOT full width)' : ''} | ${live.length} elements live vs ${ref.length} preview | geometry >2px off: ${gd} | style differs: ${sd} | hscroll: ${facts.hscroll || 'none'} | theme leaks: ${facts.leaks.join('; ') || 'none'} | broken images: ${facts.broken.join(', ') || 'none'} | upload 4xx: ${[...new Set(bad404)].join(', ') || 'none'} | carousel dot ${car[0]} -> next ${car[1]} -> prev ${car[2]} | button hover ${hover} | JS errors on page: ${errs.length}${errs.length ? ' (' + errs.map((m) => m.slice(0, 60)).join(' / ') + ')' : ''}`);
    report.push(...ex);
  }
  console.log(report.join('\n'));
  fs.writeFileSync(path.join(ROOT, 'qa/livecheck.txt'), report.join('\n') + '\n');
  await b.close();
})();
