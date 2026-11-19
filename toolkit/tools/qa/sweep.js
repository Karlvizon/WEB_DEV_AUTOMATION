// Resize sweep 320 -> 3840 plus the device matrix widths. Reports every layout fault found.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const widths = [];
for (let w = 320; w <= 1100; w += 10) widths.push(w);
if (process.env.PLANT) widths.splice(0, widths.length, 390, 1024, 1920);
for (let w = 1120; w <= 3840; w += 40) widths.push(w);
if (!process.env.PLANT) [375, 390, 430, 768, 769, 1024, 1025, 1280, 1366, 1440, 1600, 1920, 2560, 3440, 3840].forEach((w) => { if (!widths.includes(w)) widths.push(w); });
if (process.env.WIDTHS) widths.splice(0, widths.length, ...process.env.WIDTHS.split(',').map(Number));
widths.sort((a, b) => a - b);
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 900 } })).newPage();
  const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  await p.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }));
  await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
  if (process.env.PLANT) await p.addStyleTag({ content: 'html #{{ID}} .{{P}}-wrap .{{P}}-cta--top a.{{P}}-btn{font-size:40px !important}html #{{ID}} .{{P}}-wrap .{{P}}-seo{width:120% !important;max-width:none !important}html #{{ID}} .{{P}}-wrap .{{P}}-g3 .{{P}}-fc .{{P}}-m img{object-fit:fill !important;height:50% !important}html #{{ID}} .{{P}}-wrap .{{P}}-spl .{{P}}-p{white-space:nowrap !important;font-size:40px !important}html #{{ID}} .{{P}}-wrap .{{P}}-cc .{{P}}-p{position:absolute !important;top:-200px !important}html #{{ID}} .{{P}}-wrap .{{P}}-tg__img img{-webkit-mask-image:linear-gradient(#000,transparent) !important;mask-image:linear-gradient(#000,transparent) !important}' });
  const faults = {}; let checked = 0;
  for (const w of widths) {
    await p.setViewportSize({ width: w, height: 900 });
    await p.waitForTimeout(120);
    const f = await p.evaluate(() => {
      const out = [];
      const vw = document.documentElement.clientWidth;
      const mobile = vw <= 1024;
      if (document.documentElement.scrollWidth > vw + 1) out.push('horizontal scroll ' + document.documentElement.scrollWidth);
      const inTrack = (e) => !!e.closest('.{{P}}-car__track');
      const texts = [...document.querySelectorAll('.{{P}}-wrap h1,.{{P}}-wrap h2,.{{P}}-wrap h3,.{{P}}-wrap h4,.{{P}}-wrap p,.{{P}}-wrap a,.{{P}}-wrap button')].filter((e) => !e.closest('[data-clone]'));
      const name = (e) => (e.className ? '.' + String(e.className).split(' ')[0] : e.tagName) + ' "' + (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 28) + '"';
      for (const e of texts) {
        const r = e.getBoundingClientRect(); if (!r.width) continue;
        if (!inTrack(e) && (r.left < -1 || r.right > vw + 1)) out.push('outside viewport ' + name(e));
        if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow !== 'visible') out.push('clipped ' + name(e));
        const box = e.closest('.{{P}}-fc,.{{P}}-oc,.{{P}}-band,.{{P}}-ec__box,.{{P}}-ovk,.{{P}}-cc,.{{P}}-tg,.{{P}}-wh,.{{P}}-spl,.{{P}}-sp,.{{P}}-trim,.{{P}}-car__slide,.{{P}}-cta,.{{P}}-seo__item');
        if (box && !inTrack(e)) { const q = box.getBoundingClientRect(); const tb = 1; if (r.left < q.left - 1 || r.right > q.right + 1 || r.top < q.top - 1 || r.bottom > q.bottom + tb) out.push('escapes card ' + name(e)); }
        if (e.matches('a.{{P}}-btn,a.{{P}}-car__cta')) { const rg = document.createRange(); rg.selectNodeContents(e); const t = rg.getBoundingClientRect(); if (t.width > r.width - 4 || t.height > r.height) out.push('label wider than button ' + name(e)); if (r.height < 44) out.push('tap target < 44 ' + name(e)); }
      }
      for (const i of document.querySelectorAll('.{{P}}-wrap img')) {
        if (i.closest('[data-clone]')) continue;
        if (!i.complete || !i.naturalWidth) { out.push('image not loaded ' + i.src.split('/').pop()); continue; }
        const r = i.getBoundingClientRect(); if (!r.width || inTrack(i)) continue;
        const fit = getComputedStyle(i).objectFit;
        const nat = i.naturalWidth / i.naturalHeight, shown = r.width / r.height;
        if (fit === 'fill' && Math.abs(shown / nat - 1) > 0.02) out.push('distorted ' + i.src.split('/').pop() + ' ' + shown.toFixed(3) + ' vs ' + nat.toFixed(3));
        if (mobile && !i.closest('.{{P}}-disc__bg,.{{P}}-trim') && !i.closest('button')) {
          if (!i.closest('.{{P}}-gal__cell') && Math.abs(shown / nat - 1) > 0.02) out.push('mobile image not natural aspect ' + i.src.split('/').pop());
          const ic = getComputedStyle(i); if ((ic.maskImage && ic.maskImage !== 'none') || (ic.webkitMaskImage && ic.webkitMaskImage !== 'none') || parseFloat(ic.opacity) < 1) out.push('mobile image faded or masked ' + i.src.split('/').pop());
          let f = i.parentElement; while (f && getComputedStyle(f).overflow === 'visible') f = f.parentElement;
          const q = f.getBoundingClientRect();
          const zoom = i.closest('.{{P}}-hero__media'); const v = zoom ? q : r;
          if (!zoom) { if (r.top < q.top - 1 || r.bottom > q.bottom + 1 || r.left < q.left - 1 || r.right > q.right + 1) out.push('mobile image cut by frame ' + i.src.split('/').pop()); }
          for (const t of texts) { const tr = t.getBoundingClientRect(); if (!tr.width || inTrack(t)) continue; if (tr.left < v.right && tr.right > v.left && tr.top < v.bottom && tr.bottom > v.top) { out.push('text over photo ' + name(t)); break; } }
        }
      }
      return [...new Set(out)];
    });
    checked++;
    for (const x of f) (faults[x] = faults[x] || []).push(w);
  }
  const lines = Object.entries(faults).map(([k, v]) => `${k}  @ ${v.length > 6 ? v.slice(0, 3).join(',') + ' ... ' + v.slice(-2).join(',') + ' (' + v.length + ' widths)' : v.join(',')}`);
  console.log(lines.join('\n') || 'no faults');
  console.log(`\n${checked} widths checked (320-3840), ${Object.keys(faults).length} distinct faults, JS errors: ${errs.length ? errs.join(' | ') : 'none'}`);
  if (!process.env.WIDTHS) fs.writeFileSync(path.join(ROOT, 'qa/sweep.txt'), lines.join('\n') + `\n${checked} widths, ${Object.keys(faults).length} faults, JS errors ${errs.length}\n`);
  await b.close();
})();
