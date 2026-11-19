// QA sweep (user, 2026-11-13: "1 and 2 is a great idea") - checks a page for the points QA keeps sending back,
// so they are fixed BEFORE QA reviews. List of points + history: _mlp-toolkit/qa_feedback.md ("Recurring QA points").
// Usage: node qa_sweep.js "<project folder>" ["<project folder>" ...]     (one Edge at a time, PC-friendly)
// Prints one block per project: OK lines and FIX lines. Exit code 0 always (it is a report).
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright-core'));
const fs = require('fs'); const path = require('path');

async function sweep(b, dir) {
  const file = path.join(dir, 'preview.html');
  if (!fs.existsSync(file)) return [`SKIP no preview.html`];
  const css = fs.readFileSync(file, 'utf8');
  const out = [];
  // WordPress (3 CMS fields): the JS lives ONLY in the JS field; HTML + CSS may be merged (user, 2026-11-16:
  // "make sure that the js is separated form the HTML but you can merge HTML and css"). One-file pages have no .js field.
  const cf = path.join(dir, 'cms-fields');
  if (fs.existsSync(cf)) { const fl = fs.readdirSync(cf); const hf = fl.filter((f) => f.endsWith('.html'));
    // City pages (user, 2026-11-16: "lets put back the JS just include it on the HTML"): the JS rides in the HTML field and the
    // JS field holds only the inert placeholder - fine. FIX only when real JS sits in BOTH fields (it would run twice).
    const jf = fl.filter((f) => f.endsWith('.js'));
    if (jf.length && hf.length) { const real = jf.some((f) => fs.readFileSync(path.join(cf, f), 'utf8').replace(/\s/g, '') !== '(function(){return;})();');
      const bad = hf.filter((f) => /<script/i.test(fs.readFileSync(path.join(cf, f), 'utf8')));
      out.push(bad.length && real ? `FIX WordPress JS in both the HTML field (${bad.join(', ')}) and the JS field - keep it in one place` : 'OK  WordPress JS in one field only'); } }
  // 3. flat edge-colour strip under phone photos (QA "fix the gradient effect here", Ram 2500 / Pacifica / Gladiator / Durango)
  out.push(/linear-gradient\(180deg,\s*var\(--edge/.test(css) ? 'FIX mobile gradient: text panels start with a flat edge-colour strip (fade the photo into the panel instead, as on Gladiator)' : 'OK  mobile gradient');
  for (const w of [1920, 1024, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 } }); const p = await ctx.newPage();
    await p.goto('file:///' + file.split(path.sep).join('/'), { waitUntil: 'load' });
    await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; }); await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); await document.fonts.ready; });
    const r = await p.evaluate((w) => {
      const wrap = document.querySelector('[class$="-wrap"]'); if (!wrap) return { err: 'no wrapper' };
      const pre = wrap.className.split(' ').find((c) => c.endsWith('-wrap')).replace(/-wrap$/, '');
      const q = (s) => document.querySelector(s); const R = (e) => e.getBoundingClientRect(); const res = { pre };
      const seo = q(`.${pre}-seo`);
      if (seo) {
        const first = seo.firstElementChild; const prev = seo.previousElementSibling;
        res.seoGap = prev ? Math.round(R(first).top - R(prev).bottom) : null; res.seoLeft = Math.round(R(first).left);
        res.title = !!q(`.${pre}-seo__t`);
        const body = q(`.${pre}-seo__p`) || seo.querySelector('p'); const legal = q(`.${pre}-legal p`) || q(`.${pre}-disc p`);
        if (body && legal) { res.bodyFont = getComputedStyle(body).fontFamily.split(',')[0]; res.legalFont = getComputedStyle(legal).fontFamily.split(',')[0]; res.bodyW = getComputedStyle(body).fontWeight; res.legalW = getComputedStyle(legal).fontWeight; res.legalSize = getComputedStyle(legal).fontSize; res.seoSizes = [...seo.querySelectorAll('h2,h3,p')].map((e) => getComputedStyle(e).fontSize).filter((v, i, a) => a.indexOf(v) === i); }
      }
      if (w === 1920) {
        const nm = q(`.${pre}-hero__nm`), tx = q(`.${pre}-hero__tx`);
        if (nm && tx) res.heroSame = Math.abs(R(nm).width - R(tx).width) < 2;
        if (nm) { const rg = document.createRange(); rg.selectNodeContents(nm); res.ruleShort = Math.round(Math.max(...[...rg.getClientRects()].map((x) => x.right)) - R(nm).right); }
        // blurry: stretched over 1.1x its file at 1920 (region files made at the frame size are 1.0 = sharp), counting crop overflow and cover scale
        // a texture under a near-opaque overlay (parent ::before/::after alpha >= 0.85, e.g. Blazer safety bg at 0.9) can't look blurry - skipped
        const veiled = (i) => ['::before', '::after'].some((ps) => { const m = (getComputedStyle(i.parentElement, ps).backgroundColor || '').match(/rgba\([^)]*,\s*([\d.]+)\)/); return !!m && Number(m[1]) >= 0.85; });
        res.blurry = [...document.images].filter((i) => { const r = R(i); if (r.width < 120 || !i.naturalWidth || i.closest('[data-clone]') || veiled(i)) return false;
          const cs = getComputedStyle(i); let dw = r.width;
          if (cs.objectFit === 'cover') dw = Math.max(r.width, r.height * i.naturalWidth / i.naturalHeight);
          return dw / i.naturalWidth > 1.1; }).map((i) => (i.currentSrc || i.src).split('/').pop()).filter((v, k, arr) => arr.indexOf(v) === k);
        // a photo block touching a coloured band (Gladiator "Steadily Connected")
        const bg = (e) => { const c = getComputedStyle(e).backgroundColor; return c !== 'rgba(0, 0, 0, 0)' && c !== 'rgb(255, 255, 255)' && c !== 'transparent'; };
        res.touch = [];
        const walk = (el, d) => { const kids = [...el.children].filter((k) => R(k).height > 8 && getComputedStyle(k).display !== 'none');
          for (let k = 1; k < kids.length; k++) { const a = R(kids[k - 1]), c = R(kids[k]); const g = c.top - a.bottom;
            if (g >= -1 && g < 4 && kids[k - 1].querySelector('img') && bg(kids[k]) && parseFloat(getComputedStyle(kids[k]).borderTopLeftRadius) > 0 && !kids[k - 1].contains(kids[k]) && !kids[k].hasAttribute('data-joined'))
              res.touch.push(`${kids[k - 1].className.split(' ')[0]} -> ${kids[k].className.split(' ')[0]}`); }
          if (d < 3) kids.forEach((k) => walk(k, d + 1)); };
        walk(wrap, 0);
      }
      // MOBILE QA points (user 2026-11-13: "specially in mobile preview since we always have a revision in that part")
      if (w === 390) {
        const R2 = (e) => e.getBoundingClientRect();
        // wide feature photos shown small on phones (Pacifica "Please zoom-in this image"): content photo wider than 2.5:1 that is not already a -m crop (Gladiator rule 2026-11-11)
        // data-whole = vehicle photo kept whole on purpose (Corvette mobile 2026-11-13 "Please zoom out this image": a crop cut the cars)
        // decorative texture (alt="") under a sibling scrim whose gradient never drops below 0.85 alpha (Mercedes-Benz of Columbus city pages
        // 2026-11-17: shortcut-panel texture behind a 0.855-0.95 scrim) is not a photo anyone reads - same idea as veiled() above
        const scrimmed = (i) => i.getAttribute('alt') === '' && [...i.parentElement.children].some((e) => { if (e === i) return false; const a = [...(getComputedStyle(e).backgroundImage || '').matchAll(/rgba\([^)]*,\s*([\d.]+)\)/g)].map((m) => Number(m[1])); return a.length > 0 && Math.min(...a) >= 0.85; });
        res.wide = [...document.querySelectorAll(`.${pre}-wrap img`)].filter((i) => { const r = R2(i); if (r.width < 250 || i.hasAttribute('data-whole') || scrimmed(i) || i.closest('[data-clone]') || i.closest(`.${pre}-hero__media`) || /gal/.test(i.className + (i.closest('[class*="gal"]') ? 'gal' : ''))) return false;
          const fr = (i.parentElement.tagName === 'PICTURE' ? i.parentElement.parentElement : i.parentElement).getBoundingClientRect(); return fr.height > 20 && fr.width / fr.height > 2.5 && !/-m\.webp/.test(i.currentSrc || i.src); })
          .map((i) => (i.currentSrc || i.src).split('/').pop()).filter((v, k, a) => a.indexOf(v) === k);
        // hero photo -> title gap (Ram 2500 "Please slightly reduce the spacing here"): about 20px
        const media = document.querySelector(`.${pre}-hero__media`), nm = document.querySelector(`.${pre}-hero__nm`);
        if (media && nm) { const rg = document.createRange(); rg.selectNodeContents(nm); const top = Math.min(...[...rg.getClientRects()].map((x) => x.top)); res.heroGap = Math.round(top - R2(media).bottom); }
        // blocks touching a coloured band on phones (Gladiator mobile "Kindly add some space here")
        const bg2 = (e) => { const c = getComputedStyle(e).backgroundColor; return c !== 'rgba(0, 0, 0, 0)' && c !== 'rgb(255, 255, 255)' && c !== 'transparent'; };
        res.mtouch = [];
        const walk2 = (el, d) => { const kids = [...el.children].filter((k) => R2(k).height > 8 && getComputedStyle(k).display !== 'none');
          for (let k = 1; k < kids.length; k++) { const a = R2(kids[k - 1]), c = R2(kids[k]); const g = c.top - a.bottom;
            if (g >= -1 && g < 8 && bg2(kids[k]) && !bg2(kids[k - 1]) && parseFloat(getComputedStyle(kids[k]).borderTopLeftRadius) > 0 && !kids[k - 1].contains(kids[k]))
              res.mtouch.push(`${kids[k - 1].className.split(' ')[0]} -> ${kids[k].className.split(' ')[0]}`); }
          if (d < 4) kids.forEach((k) => walk2(k, d + 1)); };
        walk2(wrap, 0);
        // heading -> content gap on phones (Blazer mobile 2026-11-13 "Reduce spacing here" on 8 heading gaps of 20-42px): keep about 12-16px
        res.hgap = [];
        wrap.querySelectorAll('h2').forEach((h) => { if (h.closest(`.${pre}-seo`) || h.closest(`.${pre}-hero`)) return;
          let g = /-head\b/.test(h.parentElement.className) ? h.parentElement : h; if (g === h && g.nextElementSibling && g.nextElementSibling.tagName === 'P') g = g.nextElementSibling;
          let n = g.nextElementSibling; while (n && getComputedStyle(n).display === 'contents') n = n.firstElementChild; // Trax gallery 2026-11-16: wrapper is display:contents on phones
          if (!n || R2(n).height < 8) return; const gap = Math.round(R2(n).top - R2(g).bottom);
          if (gap > 22) res.hgap.push(`"${h.innerText.trim().slice(0, 30)}" ${gap}px`); });
      }
      // hairline seam (user 2026-11-13, Durango): a photo box stacked edge-to-edge on a filled panel shows a 1px light line on
      // fractional-DPR phones unless the shared parent is filled with the panel colour (or the panel overlaps the photo by 1px).
      res.seams = [];
      if (w < 1025) document.querySelectorAll(`.${pre}-wrap img`).forEach((img) => {
        let m = img.parentElement.tagName === 'PICTURE' ? img.parentElement : img; while (m.parentElement && !m.nextElementSibling && !m.previousElementSibling) m = m.parentElement;
        const par = m.parentElement; if (!par || getComputedStyle(par).flexDirection !== 'column') return;
        [...par.children].forEach((n) => { if (n === m) return; const a = R(m), c = R(n), cs = getComputedStyle(n);
          if (cs.backgroundColor === 'rgba(0, 0, 0, 0)' || Math.abs(a.left - c.left) > 2) return;
          if (Math.abs(c.top - a.bottom) > 0.5) return;
          if (getComputedStyle(par).backgroundColor === 'rgba(0, 0, 0, 0)' && parseFloat(cs.marginTop) >= 0) res.seams.push(n.className.split(' ')[0] + ' / ' + (n.className.split(' ')[1] || '')); });
      });
      // missing space in a heading (user 2026-11-13, Huston CDJR: H2 "Why Davenport Drivers ChooseHuston CDJR" -> "Choose Huston").
      // innerText (not textContent) so a <br> counts as a break. Brand camel-case words are allowed: anything followed by
      // (R)/TM, my* apps (myBuick, myChevrolet), and the list below (add a brand word here if it shows up as a false FIX).
      const okCamel = /^(my[A-Z]\w*|CarPlay|OnStar|SiriusXM|eTorque|MyLink|LaneSense|ParkSense|ParkView|IntelliBeam|QuietTuning|WildPeak|BlueCruise|SmartWay|AutoStick|TowMax|MultiPro|PowerShift|DuraMax|EcoBoost|SelecTerrain|ProGrade|SafetySense|SmartSense|HondaSense|MaxCare|iPhone|YouTube|WiFi|McKinney|McAllen|DeSoto|LaGrange|DeKalb|SmartKey|ExpertSOLUTIONS)$/;
      res.glued = []; res.caps = [];
      if (w === 1920) wrap.querySelectorAll('h1,h2,h3,h4').forEach((h) => {
        const t = h.innerText.replace(/\s+/g, ' ').trim();
        const bad = [...t.matchAll(/[A-Za-z]*[a-z]{2}[A-Z][A-Za-z]*(?![A-Za-z])(.?)/g)].filter((m) => !/[®™℠]/.test(m[1]) && !okCamel.test(m[0].replace(/[^A-Za-z]$/, ''))).map((m) => m[0].replace(/[^A-Za-z]$/, ''))
          .concat(t.match(/[a-z][.,!?:;][A-Za-z]/g) || []);
        // block spans joined with no space in the source (QA Durango 2026-11-14: H1 "2027 DODGE DURANGOAvon Park, FL"):
        // innerText shows them on two lines, so also read the source text with <br> as a space and compare word joins.
        const cl = h.cloneNode(true); cl.querySelectorAll('br').forEach((b) => b.replaceWith(' '));
        const src = cl.textContent.replace(/\s+/g, ' ').trim();
        [...h.querySelectorAll('span,b,strong,em,a')].forEach((el) => { const nx = el.nextSibling, pv = el.previousSibling;
          const glue = (a, b) => /[A-Za-z0-9.,]$/.test(a) && /^[A-Za-z0-9]/.test(b);
          if (nx && glue(el.textContent, nx.textContent)) bad.push(`${el.textContent.trim().split(' ').pop()}|${nx.textContent.trim().split(' ')[0]}`);
          if (pv && pv.nodeType === 3 && glue(pv.textContent, el.textContent)) bad.push(`${pv.textContent.trim().split(' ').pop()}|${el.textContent.trim().split(' ')[0]}`); });
        if (bad.length) res.glued.push(`${h.tagName} "${src}" (${[...new Set(bad)].join(', ')})`);
        // ALL-CAPS heading text in the source (user 2026-11-14, Durango: "use normal text styling for headings, then just use
        // CSS to make it uppercase"). Reads textContent, so CSS text-transform does not hide it. Acronyms/brand caps allowed below.
        const okCaps = /^(ACTIV|HEMI|AWD|FWD|RWD|SRT|LED|SUV|SUVS|MSRP|CDJR|GMC|RAM|USB|GPS|EPA|MPG|BMW|AMG|SRX|XLT|LTZ|RST|ZR2|TRX|EV|AT4|HD|LB|CPO|VIN|APR|ADAS|RV|SXT|GTS|TPMS|NHTSA|IIHS|II|III|IV|VI|HP|DOHC|SOHC|CVT|GLC|GLE|GLS|GLA|GLB|CLA|CLE|EQS|EQE|EQB|MBUX|HVAC)$/;
        const caps = (src.match(/\b[A-Z][A-Z'’]{2,}\b/g) || []).filter((x) => !okCaps.test(x.replace(/['’]/g, '')));
        if (caps.length) res.caps.push(`${h.tagName} "${src.slice(0, 60)}" (${caps.slice(0, 4).join(', ')})`); });
      // same gap above every section label (QA Encore GX 2026-11-16: "make sure the spacing here is aligned with other" -
      // Exterior/Safety sat 40 under a CTA bar, the other sections 60). Unfilled sections only (bands have their own padding).
      if (w >= 1024) { const filled = (e) => { for (let a = e; a && a !== wrap; a = a.parentElement) { if (getComputedStyle(a).backgroundColor !== 'rgba(0, 0, 0, 0)') return true; } return false; };
        res.kgap = [...wrap.querySelectorAll(`.${pre}-kicker`)].map((k) => { let s = k; while (s.parentElement && s.parentElement !== wrap && !s.previousElementSibling) s = s.parentElement;
          const pv = s.previousElementSibling; if (!pv || filled(s) || R(pv).height < 8 || getComputedStyle(pv).position === 'absolute') return null;
          const gap = Math.round(R(k).top - R(pv).bottom); if (gap < 0) return null;
          return [k.textContent.trim().slice(0, 20), gap, pv.classList.contains(`${pre}-cta`)]; }).filter(Boolean);
        // a lone last card in a 2+ column grid sits centred (QA Encore GX 2026-11-16: "Center this" on the 7th feature card)
        res.lone = [];
        wrap.querySelectorAll('*').forEach((g) => { const cs = getComputedStyle(g); if (!(cs.display === 'grid' || (cs.display === 'flex' && cs.flexWrap === 'wrap'))) return;
          const kids = [...g.children].filter((k) => getComputedStyle(k).display !== 'none' && R(k).height > 8); if (kids.length < 3) return;
          const L = R(kids[kids.length - 1]), P = R(kids[kids.length - 2]), G = R(g); if (L.top < P.bottom - 2 || L.width > G.width * 0.8) return;
          const l = L.left - G.left, r = G.right - L.right; if (Math.abs(l - r) > 8) res.lone.push(`${g.className.split(' ')[0]} (last card ${Math.round(l)}px from the left, ${Math.round(r)}px from the right)`); }); }
      // "&" left at the end (or start) of a heading line (QA 2026-11-16, Encore GX + Envision + Trax mobile: "Put the Build & down" /
      // "Add this word below" - '2026 Buick Envision Build &' / 'Price'). A phrase like "Build & Price" must stay on one line.
      if (w === 390 || w === 1024) {
        res.amp = [...wrap.querySelectorAll('h1,h2,h3,h4')].filter((h) => h.getClientRects().length && !h.closest('[data-clone]')).map((h) => {
          const tw = document.createTreeWalker(h, NodeFilter.SHOW_TEXT); const toks = []; let n;
          while ((n = tw.nextNode())) { const re = /\S+/g; let m; while ((m = re.exec(n.data))) { const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length); const b = rg.getClientRects()[0]; if (b) toks.push({ t: m[0], top: Math.round(b.top) }); } }
          for (let k = 0; k < toks.length; k++) { if (toks[k].t !== '&') continue; const a = toks[k - 1], c = toks[k + 1];
            // short = 2 words or fewer on one side ("Build & Price") -> FIX; a break around "&" in a long title -> CHECK only
            if ((a && Math.abs(a.top - toks[k].top) > 3) || (c && Math.abs(c.top - toks[k].top) > 3)) return { t: h.textContent.trim().replace(/\s+/g, ' ').slice(0, 60), s: k <= 2 || toks.length - 1 - k <= 2 }; }
          return null; }).filter(Boolean);
      }
      return res; }, w);
    if (r.err) { out.push('SKIP ' + r.err); await ctx.close(); break; }
    if (r.amp) { const fx = r.amp.filter((x) => x.s), ck = r.amp.filter((x) => !x.s);
      out.push(fx.length ? `FIX "&" splits a short phrase across lines @${w} (QA: "Put the Build & down") - keep it together (e.g. wrap "Build & Price" in a nowrap span or break before it): ${fx.slice(0, 4).map((x) => x.t).join('; ')}` : `OK  no short "&" phrase split in headings @${w}`);
      if (ck.length) out.push(`CHECK "&" at a line break in a long heading @${w} (fine if it reads well): ${ck.slice(0, 4).map((x) => x.t).join('; ')}`); }
    if (r.seoGap !== undefined && r.seoGap !== null) out.push(Math.abs(r.seoGap - r.seoLeft) <= 3 ? `OK  MLP top margin = left margin at ${w} (${r.seoGap}px)` : `FIX MLP top margin at ${w}: ${r.seoGap}px but left margin ${r.seoLeft}px`);
    if (r.legalSize) out.push(r.seoSizes.length === 1 && r.seoSizes[0] === r.legalSize ? `OK  MLP content font size = disclaimer (${r.legalSize}) @${w}` : `FIX MLP content font size ${r.seoSizes.join('/')} vs disclaimer ${r.legalSize} @${w} (user 2026-11-13: always the same size)`);
    if (w === 390) {
      if (r.wide) out.push(r.wide.length ? `FIX mobile zoom: wide photos shown small on phones (>2.5:1) - add a 2.15:1 to 3:2 -m crop around the subject: ${r.wide.slice(0, 6).join(', ')}` : 'OK  no wide photos shown small on phones');
      if (r.heroGap !== undefined) out.push(r.heroGap > 26 ? `FIX mobile hero: photo to title is ${r.heroGap}px (keep about 20px)` : `OK  mobile hero photo to title ${r.heroGap}px`);
      if (r.hgap) out.push(r.hgap.length ? `CHECK mobile heading-to-content gap over 22px (QA Blazer: "Reduce spacing here"; keep 12-16px): ${r.hgap.slice(0, 6).join('; ')}` : 'OK  mobile heading-to-content gaps');
      if (r.mtouch) out.push(r.mtouch.length ? `FIX mobile spacing: block touching a coloured band (add 20px): ${[...new Set(r.mtouch)].slice(0, 4).join('; ')}` : 'OK  no block touching a band on phones');
    }
    if (r.kgap && r.kgap.some((x) => x[2]) && r.kgap.some((x) => !x[2])) { const v = r.kgap.filter((x) => !x[2]).map((x) => x[1]); const mode = v.sort((a, c) => v.filter((y) => y === c).length - v.filter((y) => y === a).length)[0];
      const off = r.kgap.filter((x) => x[2] && Math.abs(x[1] - mode) > 4); out.push(off.length ? `CHECK section label after a CTA bar @${w}: ${off.map((x) => x[0] + ' ' + x[1] + 'px').join(', ')} vs ${mode}px above the other labels (QA Encore GX / Trax: "make sure the spacing here is aligned with other", "shift this downward")` : `OK  labels after CTA bars have the usual gap @${w} (${mode}px)`); }
    if (r.lone) out.push(r.lone.length ? `CHECK lone last card not centred @${w} (QA Encore GX: "Center this"): ${r.lone.slice(0, 4).join('; ')}` : `OK  lone last cards centred @${w}`);
    if (r.seams && w < 1025) out.push(r.seams.length ? `FIX hairline seam risk @${w} (photo stacked on a panel with an unfilled parent): ${[...new Set(r.seams)].join('; ')} - give the parent the panel colour + overflow:hidden + radius, panel margin-top:-1px` : `OK  no photo/panel hairline seam @${w}`);
    if (w === 1920) {
      if (r.title !== undefined) out.push(r.title ? 'OK  MLP content title' : 'CHECK MLP content title missing (add it if the content doc has a title)');
      if (r.bodyFont) out.push(r.bodyFont === r.legalFont ? 'OK  disclaimer font = MLP content font' : `CHECK disclaimer font ${r.legalFont} vs MLP content ${r.bodyFont} (QA asked for the same font on Durango)`);
      // QA 2026-11-13 (Pacifica, Ram 2500, Cherokee, Gladiator): "change the font style of the disclaimers to match the MLP content" = weight too (Light 300 vs Regular 400)
      if (r.bodyW) out.push(r.bodyW === r.legalW ? 'OK  disclaimer weight = MLP content weight' : `FIX disclaimer font weight ${r.legalW} vs MLP content ${r.bodyW} (QA: same font style)`);
      if (r.ruleShort !== undefined) out.push(r.ruleShort > 2 ? `FIX hero rule ends ${r.ruleShort}px before the end of the title (QA Ram 2500: the line must match the full title)` : 'OK  hero rule reaches the end of the title');
      if (r.heroSame !== undefined) out.push(r.heroSame ? 'CHECK hero: the name rule spans the whole text box (template value) - compare the hero with the Figma' : 'OK  hero name box narrower than the text box');
      out.push(r.blurry.length ? `FIX blurry (stretched >1.1x) at 1920 (${r.blurry.length}): ${r.blurry.slice(0, 8).join(', ')}${r.blurry.length > 8 ? ' ...' : ''}` : 'OK  no blurry images at 1920');
      out.push(r.touch.length ? `FIX no space between photo and band: ${[...new Set(r.touch)].join('; ')}` : 'OK  no photo touching a band');
      out.push(r.glued.length ? `FIX missing space in heading (QA Huston CDJR: "ChooseHuston" -> "Choose Huston"): ${r.glued.slice(0, 6).join('; ')}` : 'OK  no missing spaces in headings');
      out.push(r.caps.length ? `FIX ALL-CAPS heading text (${r.caps.length}) - write Title Case in the HTML, uppercase via CSS text-transform (user 2026-11-14): ${r.caps.slice(0, 6).join('; ')}` : 'OK  heading text is not typed in ALL CAPS');
    }
    await ctx.close();
  }
  return out;
}

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const dir of process.argv.slice(2)) {
    let lines; try { lines = await sweep(b, dir); } catch (e) { lines = ['ERROR ' + e.message.split('\n')[0]]; }
    console.log(`== ${path.basename(path.dirname(dir))} / ${path.basename(dir)}`); lines.forEach((l) => console.log('   ' + l));
  }
  await b.close();
})();
