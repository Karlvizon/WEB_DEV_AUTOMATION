// Live page check after publishing (user, 2026-11-12: "Live page check after you publish").
// usage: node livepage.js "<project folder>" <live url>
// Opens the PUBLISHED page in a headed Edge window (dealer bot shields block headless) at 1920 and 390 and checks:
//   - the page is up and our wrapper (#<project id>) is on it (otherwise: "not published yet")
//   - every image in the wrapper loads (broken / still pointing at local assets/ files)
//   - every link in the wrapper has a real href; buttons stay on the dealer's own site
//   - the dealer theme does not restyle our text: font family / size / weight / transform / spacing of every
//     h1-h4, p, a, button vs preview.html rendered at the same width
//   - no horizontal scroll, and JS errors on the page
// Writes <project>/qa/live.txt and qa/live.json; the last line of live.txt is the verdict.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(process.argv[2]); const URL = process.argv[3];
const PJ = path.join(ROOT, 'project.json');
// older projects have no project.json: take the page id from the wrapper in preview.html
const PROJ = fs.existsSync(PJ) ? JSON.parse(fs.readFileSync(PJ, 'utf8'))
  : { id: (fs.readFileSync(path.join(ROOT, 'preview.html'), 'utf8').match(/class="main-div"\s+id="([^"]+)"|id="([^"]+)"\s+class="main-div"/) || []).slice(1).find(Boolean) };
if (!PROJ.id) { console.log('no page id found (project.json / preview.html)'); process.exit(2); }
const ID = PROJ.id;
// dealer domain: project.json "site", else the domain most CTA buttons in preview.html point to (the live URL can be a
// temporary CMS domain such as dealerXXXX.dealeron.com)
const guessSite = () => {
  const hosts = {}; const src = fs.readFileSync(path.join(ROOT, 'preview.html'), 'utf8');
  for (const m of src.matchAll(/<a\s[^>]*class="[^"]*(?:btn|cta)[^"]*"[^>]*href="(https?:\/\/[^"\/]+)/gi)) { const h = m[1].replace(/^https?:\/\/(www\.)?/, ''); hosts[h] = (hosts[h] || 0) + 1; }
  return Object.entries(hosts).sort((a, b) => b[1] - a[1]).map((e) => e[0])[0];
};
const SITE = PROJ.site ? (new globalThis.URL(PROJ.site)).hostname.replace(/^www\./, '') : (guessSite() || (new globalThis.URL(URL)).hostname.replace(/^www\./, ''));
const PREVIEW = 'file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/');
const out = []; const log = (s) => { out.push(s); console.log(s); };

const snap = ([id, site]) => {
  const root = document.getElementById(id);
  if (!root) return null;
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const els = [...root.querySelectorAll('h1,h2,h3,h4,p,a,button')].filter((e) => vis(e) && (e.textContent || '').trim());
  const type = els.map((e) => { const c = getComputedStyle(e); return [e.tagName, (e.textContent || '').trim().slice(0, 40), c.fontFamily.split(',')[0].replace(/["']/g, '').trim(), c.fontSize, c.fontWeight, c.textTransform, c.letterSpacing]; });
  const imgs = [...root.querySelectorAll('img')].map((i) => ({ src: i.currentSrc || i.getAttribute('src') || '', ok: i.complete && i.naturalWidth > 0, local: /^(\.\/)?assets\//.test(i.getAttribute('src') || '') }));
  const links = [...root.querySelectorAll('a')].map((a) => {
    const href = a.getAttribute('href') || ''; let host = '';
    try { host = new URL(a.href).hostname.replace(/^www\./, ''); } catch (e) { }
    const btn = /btn|cta/i.test(a.className);
    return { text: (a.textContent || '').trim().slice(0, 40), href, missing: !href || href === '#', offsite: btn && host && host !== site && !host.endsWith('.' + site) };
  });
  return { type, imgs, links, hscroll: document.documentElement.scrollWidth > window.innerWidth + 1 };
};

(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled', '--window-position=-2400,0'] });
  let problems = 0; let live = true; const res = {};
  for (const [w, h, mobile] of [[1920, 1080, false], [390, 844, true]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile });
    const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', (e) => errs.push(e.message.slice(0, 160)));
    let status = 0;
    for (let t = 0; t < 4; t++) {
      const r = await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => null);
      status = r ? r.status() : 0; await p.waitForTimeout(6000);
      if (await p.$('#' + ID)) break;
    }
    if (!(await p.$('#' + ID))) { live = false; log(`${w}px: page HTTP ${status}; our page (#${ID}) is not on it -> not published yet`); await ctx.close(); break; }
    // load lazy images, then measure
    await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } window.scrollTo(0, 0); });
    await p.waitForTimeout(2500);
    const L = await p.evaluate(snap, [ID, SITE]);
    // images that did not render (lazy / hidden carousel slides): ask the server for the file itself
    const seen = {};
    for (const im of L.imgs) {
      if (im.ok || im.local || !im.src) continue;
      if (!(im.src in seen)) { const r = await ctx.request.get(im.src, { timeout: 30000 }).catch(() => null); seen[im.src] = r ? r.status() : 0; }
      im.ok = seen[im.src] > 0 && seen[im.src] < 400; im.status = seen[im.src];
    }
    const wrapW = await p.evaluate((id) => document.getElementById(id).getBoundingClientRect().width, ID);
    await ctx.close();
    // preview at the same viewport width
    const pc = await b.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile });
    const pp = await pc.newPage(); await pp.goto(PREVIEW, { waitUntil: 'load' }); await pp.evaluate(() => document.fonts.ready); await pp.waitForTimeout(1000);
    const P = await pp.evaluate(snap, [ID, SITE]); await pc.close();
    const diff = [];
    const n = Math.min(L.type.length, P.type.length);
    for (let i = 0; i < n; i++) {
      const a = L.type[i], q = P.type[i];
      if (a[0] !== q[0] || a[1] !== q[1]) continue;
      const k = [2, 3, 4, 5, 6].filter((j) => a[j] !== q[j] && !(j === 3 && Math.abs(parseFloat(a[j]) - parseFloat(q[j])) < 1.5));
      if (k.length) diff.push(`${a[0]} "${a[1]}": ` + k.map((j) => `${['', '', 'font', 'size', 'weight', 'transform', 'spacing'][j]} live ${a[j]} vs ${q[j]}`).join(', '));
    }
    const broken = L.imgs.filter((i) => !i.ok), local = L.imgs.filter((i) => i.local);
    const missing = L.links.filter((l) => l.missing), off = L.links.filter((l) => l.offsite);
    const pr = broken.length + local.length + missing.length + off.length + diff.length + (L.hscroll ? 1 : 0) + (L.type.length !== P.type.length ? 1 : 0);
    problems += pr;
    log(`${w}px: page found | wrapper ${Math.round(wrapW)}px | images ${L.imgs.length - broken.length}/${L.imgs.length} load` +
        `${local.length ? `, ${local.length} still point at local assets/ (not uploaded)` : ''} | links ${L.links.length}, missing ${missing.length}, buttons off-site ${off.length}` +
        ` | theme style changes ${diff.length}${L.type.length !== P.type.length ? ` (text elements live ${L.type.length} vs preview ${P.type.length})` : ''}` +
        ` | horizontal scroll ${L.hscroll ? 'YES' : 'no'} | page JS errors ${errs.length}`);
    broken.slice(0, 10).forEach((i) => log(`   broken image (HTTP ${i.status}): ` + i.src));
    local.slice(0, 5).forEach((i) => log('   local image path: ' + i.src));
    missing.forEach((l) => log(`   link without href: "${l.text}"`));
    off.forEach((l) => log(`   button to another site: "${l.text}" -> ${l.href}`));
    diff.slice(0, 15).forEach((d) => log('   theme: ' + d));
    errs.slice(0, 5).forEach((e) => log('   JS error: ' + e));
    res[w] = { status, images: L.imgs.length, broken: broken.length, local: local.length, missing: missing.length, offsite: off.length, theme: diff.length, hscroll: L.hscroll, jsErrors: errs.length };
  }
  await b.close();
  const verdict = !live ? 'NOT LIVE YET' : problems ? `LIVE ISSUES ${problems}` : 'LIVE OK';
  log(verdict);
  fs.mkdirSync(path.join(ROOT, 'qa'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'qa/live.txt'), out.join('\n'));
  fs.writeFileSync(path.join(ROOT, 'qa/live.json'), JSON.stringify({ url: URL, at: new Date().toISOString(), verdict, res }, null, 1));
})();
