// Final check of the PUBLISHED page in one headed Edge window (the bot shield blocks headless/curl).
// usage: node livefinal.js <url>
// For 1920 and 390: source facts, JS ran once, images (loaded, full size, no -1 renames, mobile <picture> sources),
// theme leaks (every wrapper element's box + type style vs preview.html rendered at the same wrapper width),
// horizontal scroll and JS errors. One browser, pages opened one after another (user PC rule 2026-11-11).
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const URL = process.argv[2];
const PREVIEW = 'file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/');
const ID = '{{ID}}';
const LOCAL = {}; fs.readdirSync(path.join(ROOT, 'assets/webp')).forEach((f) => { LOCAL[f] = 1; });
function size(f) { const b = fs.readFileSync(path.join(ROOT, 'assets/webp', f)); const i = b.indexOf('VP8 '); if (i < 0) return null; return [b.readUInt16LE(i + 14) & 0x3fff, b.readUInt16LE(i + 16) & 0x3fff]; }
const snap = () => {
  const root = document.getElementById('{{ID}}'); const w = root.querySelector('.{{P}}-wrap'); const R = w.getBoundingClientRect();
  return [...w.querySelectorAll('*')].filter((e) => !e.closest('[data-clone]') && !['SOURCE', 'PICTURE', 'BR'].includes(e.tagName)).map((e) => {
    const r = e.getBoundingClientRect(); const c = getComputedStyle(e);
    return [e.tagName, String(e.className).slice(0, 40), Math.round(r.left - R.left), Math.round(r.top - R.top), Math.round(r.width), Math.round(r.height), c.fontFamily.split(',')[0].replace(/"/g, ''), c.fontSize, c.fontWeight, c.color, c.textTransform, c.backgroundColor];
  });
};
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const out = []; const log = (s) => { out.push(s); console.log(s); };
  for (const [W, H, mobile] of [[1920, 1080, false], [390, 844, true]]) {
    const ctx = await b.newContext(mobile ? { viewport: { width: W, height: H }, isMobile: true, hasTouch: true, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' } : { viewport: { width: W, height: H } });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    let ok = false;
    for (let t = 0; t < 5 && !ok; t++) { await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(6000); ok = await p.evaluate((id) => !!document.getElementById(id), ID).catch(() => false); }
    if (!ok) { log(`${W}px: page wrapper #${ID} NOT FOUND`); await ctx.close(); continue; }
    await p.evaluate(async () => { document.querySelectorAll('#{{ID}} img').forEach((i) => { i.loading = 'eager'; }); for (let y = 0; y < document.body.scrollHeight; y += 900) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); });
    await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.querySelectorAll('#{{ID}} img')].map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; })))); });
    await p.waitForTimeout(1500);
    const facts = await p.evaluate((id) => {
      const root = document.getElementById(id); const html = document.documentElement.outerHTML;
      const slot = (html.match(/<!-- di page composer css -->([\s\S]*?)<!-- eof: di page composer css -->/) || [, null])[1];
      const imgs = [...root.querySelectorAll('img')].filter((i) => !i.closest('[data-clone]') && i.getBoundingClientRect().width > 0);
      return {
        wrappers: document.querySelectorAll('#' + id).length, styles: root.querySelectorAll('style').length, brs: root.querySelectorAll('br').length, ps: root.querySelectorAll('p:empty').length,
        ready: root.getAttribute('data-cp-ready'), slot: slot === null ? 'not found' : slot.trim().length + ' chars',
        jsField: !!document.getElementById('di-page-composer-scripts'), fontLinks: root.querySelectorAll('link[href*="fonts.googleapis"]').length,
        roboto: document.fonts.check('700 20px Roboto') && document.fonts.check('italic 300 20px Roboto'),
        hscroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        wrapW: root.querySelector('.{{P}}-wrap').getBoundingClientRect().width,
        imgs: imgs.map((i) => [i.currentSrc, i.complete, i.naturalWidth, i.naturalHeight]),
        links: [...root.querySelectorAll('a')].map((a) => a.href).filter((h) => !/hustoncdjr\.com/.test(h) && !/fueleconomy|siriusxm/.test(h)),
      };
    }, ID);
    log(`\n== LIVE ${W}px  (${URL})`);
    log(`wrapper x${facts.wrappers}, <style> in HTML field ${facts.styles}, page composer CSS slot ${facts.slot}, JS field present ${facts.jsField}, JS ran (data-cp-ready) ${facts.ready}`);
    log(`<br> inside wrapper ${facts.brs}, empty <p> injected ${facts.ps}, font links ${facts.fontLinks}, Roboto incl. italic loaded ${facts.roboto}, horizontal scroll ${facts.hscroll}px, wrapper width ${facts.wrapW}px`);
    let bad = 0; const renames = [];
    for (const [src, done, nw, nh] of facts.imgs) {
      const f = decodeURIComponent(src.split('/').pop().split('?')[0]);
      if (!done || !nw) { bad++; log(`IMAGE NOT LOADED ${src}`); continue; }
      if (/-\d\.webp$/.test(f) && !LOCAL[f]) renames.push(f);
      if (LOCAL[f]) { const s = size(f); if (s && (s[0] !== nw || s[1] !== nh)) { bad++; log(`IMAGE SIZE DIFFERS ${f}: CDN ${nw}x${nh} vs local ${s[0]}x${s[1]}`); } }
      else { bad++; log(`IMAGE NOT FROM THIS BUILD ${f}`); }
    }
    log(`images shown ${facts.imgs.length}, problems ${bad}${renames.length ? ', -1 renames: ' + renames.join(' ') : ''}`);
    log(`links not on hustoncdjr.com: ${facts.links.length ? facts.links.join(' ') : 'none'}`);
    const live = await p.evaluate(snap);
    const pp = await (await b.newContext(mobile ? { viewport: { width: Math.round(facts.wrapW), height: H }, isMobile: true, hasTouch: true } : { viewport: { width: Math.round(facts.wrapW), height: H } })).newPage();
    await pp.goto(PREVIEW, { waitUntil: 'load' });
    const sb = await pp.evaluate(() => innerWidth - document.documentElement.clientWidth); if (sb) await pp.setViewportSize({ width: Math.round(facts.wrapW) + sb, height: H });
    await pp.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); await document.fonts.ready; await Promise.all([...document.images].map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; })))); });
    await pp.waitForTimeout(800);
    const prev = await pp.evaluate(snap); await pp.context().close();
    let diffs = 0; const ex = [];
    const n = Math.min(live.length, prev.length);
    for (let i = 0; i < n; i++) {
      const a = live[i], c = prev[i];
      const geo = Math.max(Math.abs(a[2] - c[2]), Math.abs(a[3] - c[3]), Math.abs(a[4] - c[4]), Math.abs(a[5] - c[5]));
      const type = a.slice(6).join('|') !== c.slice(6).join('|');
      if (geo > 2 || type || a[0] !== c[0]) { diffs++; if (ex.length < 12) ex.push(`  ${a[0]}.${a[1]}  live ${a.slice(2, 6).join(',')} ${type ? a.slice(6).join('|') : ''}  preview ${c.slice(2, 6).join(',')} ${type ? c.slice(6).join('|') : ''}`); }
    }
    log(`elements compared ${n} (live ${live.length}, preview ${prev.length}), differ from preview (box >2px or type style): ${diffs}`);
    ex.forEach(log);
    log(`JS errors on page: ${errs.length ? errs.slice(0, 5).join(' | ') : 'none'}`);
    await p.screenshot({ path: path.join(ROOT, `qa/live-${W}-top.png`) });
    await ctx.close();
  }
  fs.writeFileSync(path.join(ROOT, 'qa/live-final.txt'), out.join('\n') + '\n');
  await b.close();
})();
