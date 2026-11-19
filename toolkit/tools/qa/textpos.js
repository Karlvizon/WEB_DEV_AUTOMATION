// Compare every visible Figma text node (figma/texts.json, absolute px in frame 1:5) with the page at a true 1920px content width.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const nodes = JSON.parse(fs.readFileSync(path.join(ROOT, 'figma/texts.json'), 'utf8'));
(async () => {
  const LIVE = process.env.LIVE;
  const b = await chromium.launch(LIVE ? { channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] } : { channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } });
  const p = await ctx.newPage();
  if (LIVE) {
    for (let t = 0; t < 6; t++) { await p.goto(LIVE, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(6000); if (await p.evaluate(() => !!document.getElementById('{{ID}}')).catch(() => false)) break; }
  } else await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => window.innerWidth - document.documentElement.clientWidth);
  await p.setViewportSize({ width: 1920 + sb, height: 1080 });
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(800);
  const match = (list) => p.evaluate((nodes) => {
    const norm = (s) => s.replace(/[\u2019]/g, "'").replace(/\u2192/g, '->').replace(/\s+/g, ' ').trim().toLowerCase();
    const wrap = document.querySelector('.{{P}}-wrap').getBoundingClientRect();
    const els = [...document.querySelectorAll('.{{P}}-wrap .{{P}}-hero__yr,.{{P}}-wrap .{{P}}-hero__nm,.{{P}}-wrap .{{P}}-hero__loc,.{{P}}-wrap h2,.{{P}}-wrap h3,.{{P}}-wrap h4,.{{P}}-wrap p,.{{P}}-wrap a,.{{P}}-wrap ul,.{{P}}-wrap .{{P}}-legal')].filter((e) => !e.closest('[data-clone]')).filter((e) => { const q = e.getBoundingClientRect(); return q.right > 0 && innerWidth > q.left; });
    const used = new Set();
    return nodes.map((n) => {
      const key = norm(n.name);
      const dist = (e) => { const q = e.getBoundingClientRect(); return Math.abs(q.top - wrap.top - (n.ym === undefined ? n.y : n.ym)) + Math.abs(q.left + q.width / 2 - wrap.left - n.x - n.w / 2) / 4; }; const near = (list) => list.sort((a, b) => dist(a) - dist(b))[0];
      if (n.sel) { const pool = [...document.querySelectorAll(n.sel)].filter((e) => !used.has(e)); const e1 = near(pool); if (e1) { used.add(e1); const r1 = e1.getBoundingClientRect(); return { ...n, px: r1.left - wrap.left, py: r1.top - wrap.top, pw: r1.width, ph: r1.height, lines: 0, cls: e1.className, al: 'left' }; } }
      const tight = (s2) => s2.replace(/\s+/g, '');
      let el = near(els.filter((e) => !used.has(e) && norm(e.innerText) === key)) || near(els.filter((e) => !used.has(e) && tight(norm(e.innerText)) === tight(key))) || near(els.filter((e) => !used.has(e) && norm(e.innerText).startsWith(key.slice(0, 40))));
      if (!el) return { ...n, miss: true };
      used.add(el);
      const r = el.getBoundingClientRect();
      const rg = document.createRange(); rg.selectNodeContents(el); const t = rg.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(el).lineHeight);
      const box = { x: r.left - wrap.left, y: r.top - wrap.top, w: r.width, h: r.height };
      const ink = { x: t.left - wrap.left, y: t.top - wrap.top, w: t.width, h: t.height };
      const pick = n.box ? box : (Math.abs(ink.w - n.w) < Math.abs(box.w - n.w) ? ink : box);
      const vy = n.box ? box : (Math.abs(ink.h - n.h) < Math.abs(box.h - n.h) ? ink : box);
      return { ...n, px: pick.x, py: vy.y, pw: pick.w, ph: vy.h, lines: Math.round(t.height / lh), cls: el.className, al: getComputedStyle(el).textAlign };
    });
  }, list);
  // pass 1: texts that occur once in Figma give each sub-section's vertical shift; pass 2 matches every node near its shifted spot
  const count = {}; nodes.forEach((n) => { count[n.name] = (count[n.name] || 0) + 1; });
  const first = await match(nodes.filter((n) => count[n.name] === 1));
  const g1 = {}; first.filter((r) => !r.miss).forEach((r) => { (g1[r.g] = g1[r.g] || []).push(r.py - r.y); });
  const s1 = {}; Object.keys(g1).forEach((g) => { const v = g1[g].sort((x, y) => x - y); s1[g] = v[Math.floor(v.length / 2)]; });
  nodes.forEach((n) => { n.ym = n.y + (s1[n.g] || 0); });
  const res = await match(nodes);
  // Desktop spacing rules (CTA bars 20px, grey bands 20px) and the MLP copy shift whole sub-sections on purpose,
  // so each node is also judged relative to the median vertical shift of its Figma sub-section (n.g).
  const shift = {};
  const byG = {};
  res.filter((r) => !r.miss).forEach((r) => { (byG[r.g] = byG[r.g] || []).push(r.py - r.y); });
  Object.keys(byG).forEach((g) => { const v = byG[g].sort((x, y) => x - y); shift[g] = v[Math.floor(v.length / 2)]; });
  let bad = 0;
  const out = [];
  for (const r of res) {
    if (!r.miss) r.py -= shift[r.g];
    if (r.miss) { out.push(`MISS ${r.id} "${r.name.slice(0, 50)}"`); bad++; continue; }
    const d = [r.px - r.x, r.py - r.y, r.pw - r.w, r.ph - r.h].map((v) => Math.round(v * 10) / 10);
    const okc = Math.abs(d[0] + d[2] / 2) <= 3 && Math.abs(d[1]) <= 3 && Math.abs(d[3]) <= 3;
    const okb = Math.abs(d[0]) <= 3 && Math.abs(d[1]) <= 3 && Math.abs(d[2]) <= 3 && d[3] < -3 && r.h % 28 === 0 && r.h >= 168;
    const ok = d.every((v) => Math.abs(v) <= 3);
    const okl = /left|start/.test(r.al) && Math.abs(d[0]) <= 3 && Math.abs(d[1]) <= 3 && Math.abs(d[3]) <= 3;
    if (!ok && !okc && !okb && !okl) bad++;
    out.push(`${ok ? 'ok  ' : okc ? 'okC ' : okb ? 'okB ' : okl ? 'okL ' : 'BAD '} ${r.id.padEnd(8)} y${String(Math.round(r.y)).padStart(6)} dx ${String(d[0]).padStart(6)} dy ${String(d[1]).padStart(6)} dw ${String(d[2]).padStart(6)} dh ${String(d[3]).padStart(6)} L${r.lines} "${r.name.slice(0, 45)}"`);
  }
  if (!LIVE) fs.writeFileSync(path.join(ROOT, 'qa/shifts.json'), JSON.stringify(shift));
  out.push('section shifts (page y - Figma y): ' + Object.keys(shift).map((g) => g + ' ' + Math.round(shift[g])).join(', '));
  console.log(out.join('\n'));
  console.log(`\n${res.length} text nodes, ${res.length - bad} within 3px, ${bad} off (scrollbar ${sb}px)`);
  fs.mkdirSync(path.join(ROOT, 'qa'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, LIVE ? 'qa/textpos-live.txt' : 'qa/textpos.txt'), out.join('\n') + `\n${res.length} nodes, ${bad} off\n`);
  await b.close();
})();
