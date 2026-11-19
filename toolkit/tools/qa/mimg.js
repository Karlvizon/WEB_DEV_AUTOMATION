// Mobile/tablet images: shown aspect = file aspect, nothing cut by its frame, no mask/opacity on content photos.
const { chromium } = require('playwright-core'); const path = require('path'); const fs = require('fs');
const BBOX = JSON.parse(fs.readFileSync(path.join(__dirname, 'vehicle-bbox.json'), 'utf8')); // measured from THIS project's files (alpha / non-white bounding box)
(async () => { const b = await chromium.launch({ channel: 'msedge' }); const out = [];
  for (const W of [320, 390, 768, 900, 1024]) {
    const p = await b.newPage({ viewport: { width: W, height: 900 } });
    await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'));
    await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); });
    const bad = await p.evaluate((BBOX) => [...document.querySelectorAll('#{{ID}} img')].filter((i) => i.getBoundingClientRect().width > 0 && !i.closest('[data-clone]') && !i.closest('[class$=\"sf__bg\"]') && !i.closest('.{{P}}-gal__cell') && !i.closest('.{{P}}-car__arrow,.{{P}}-disc__bg')).map((i) => {
      let r = i.getBoundingClientRect(); if (getComputedStyle(i).objectFit === 'contain') { const nk = i.naturalWidth / i.naturalHeight, bw = r.width, bh = r.height; const w = Math.min(bw, bh * nk), h = w / nk; r = { left: r.left + (bw - w) / 2, top: r.top + (bh - h) / 2, width: w, height: h, right: r.left + (bw + w) / 2, bottom: r.top + (bh + h) / 2 }; } const fr = i.parentElement.tagName === 'PICTURE' ? i.parentElement.parentElement : i.parentElement; const f = fr.getBoundingClientRect(); const cs = getComputedStyle(i);
      const a = r.width / r.height, n = i.naturalWidth / i.naturalHeight; const errs = [];
      const cut = i.closest('.{{P}}-trim,.{{P}}-car__img,.{{P}}-hero__media');
      if (cut) { const k = i.currentSrc.split('/').pop().replace('.webp', ''); const bb = BBOX[k]; const vx0 = (f.left - r.left) / r.width, vy0 = (f.top - r.top) / r.height, vx1 = (f.right - r.left) / r.width, vy1 = (f.bottom - r.top) / r.height;
        if (Math.abs(a / n - 1) > 0.01) errs.push('distorted'); if (vx0 > bb[0] + 0.002 || vy0 > bb[1] + 0.002 || bb[2] > vx1 + 0.002 || bb[3] > vy1 + 0.002) errs.push('vehicle cut by frame (visible ' + [vx0, vy0, vx1, vy1].map((v) => v.toFixed(3)).join(',') + ')');
        return errs.length ? i.currentSrc.split('/').pop() + ': ' + errs.join(', ') : null; }
      if (Math.abs(a / n - 1) > 0.01) errs.push(`aspect ${a.toFixed(3)} vs file ${n.toFixed(3)}`);
      if (r.left < f.left - 1 || r.right > f.right + 1 || r.top < f.top - 1 || r.bottom > f.bottom + 1) errs.push('cut by frame');
      if (parseFloat(cs.opacity) < 1 || (cs.maskImage && cs.maskImage !== 'none')) errs.push('masked/faded');
      return errs.length ? i.currentSrc.split('/').pop() + ': ' + errs.join(', ') : null; }).filter(Boolean), BBOX);
    out.push(`${W}px: ${bad.length ? bad.length + ' bad\n  ' + bad.join('\n  ') : 'all content images whole, aspect = file, not masked; trim/category cut-outs: vehicle fully inside its frame'}`); await p.close(); }
  console.log(out.join('\n')); fs.writeFileSync(path.resolve(__dirname, '../../qa/mobile-images.txt'), out.join('\n') + '\n'); await b.close(); })();
