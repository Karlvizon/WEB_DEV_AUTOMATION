// Final mobile check (user, 2026-11-16: "include Final mobile check in automation if there is revisions").
// Run on every revision (Final MLP, Final Mobile Check or City Page) AFTER the fixes and qa_sweep.js, before "Claude is done":
// it checks the page the way QA's Final Mobile Check does and saves phone screenshots to look at.
// Usage: node final_mobile_check.js "<project folder>"
// Prints OK / FIX / CHECK lines per phone width and the screenshot files (<project>/qa/final-mobile/<width>-<n>.png).
// FIX = must be fixed. CHECK = look at the screenshot and decide by the "Mobile (Final Mobile Check)" rules in
// _mlp-toolkit/qa_feedback.md. Exit code 0 always (it is a report).
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright-core'));
const fs = require('fs'); const path = require('path');

const PHONES = [[390, 844], [375, 812], [430, 932]];
const SLICE = 3000;   // screenshot height per image (tall phone pages are cut into readable pieces)

(async () => {
  const dir = process.argv[2];
  const file = dir && path.join(dir, 'preview.html');
  if (!file || !fs.existsSync(file)) { console.log(`SKIP no preview.html in ${dir}`); return; }
  const shots = path.join(dir, 'qa', 'final-mobile');
  fs.mkdirSync(shots, { recursive: true });
  for (const f of fs.readdirSync(shots)) if (f.endsWith('.png')) fs.unlinkSync(path.join(shots, f));
  const b = await chromium.launch({ channel: 'msedge' });
  const out = [`FINAL MOBILE CHECK - ${path.basename(dir)}`];
  let fixes = 0;
  try {
    for (const [W, H] of PHONES) {
      const ctx = await b.newContext({ viewport: { width: W, height: H }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
      const p = await ctx.newPage();
      const errs = []; p.on('pageerror', (e) => errs.push(e.message));
      await p.goto('file:///' + file.split(path.sep).join('/'), { waitUntil: 'load' });
      await p.evaluate(async () => { document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; });
        await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))); await document.fonts.ready; });
      await p.waitForTimeout(800);
      const r = await p.evaluate((W) => {
        const wrap = document.querySelector('[class$="-wrap"]') || document.body;
        const R = (e) => e.getBoundingClientRect();
        const vis = (e) => { const s = getComputedStyle(e); const r = R(e); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
        // only clipping INSIDE the wrapper (slider tracks etc.) is on purpose; content cut off by the wrapper itself is a defect
        const clipped = (e) => { for (let a = e.parentElement; a && a !== wrap && a !== document.body; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o !== 'visible') return true; } return false; };
        const name = (e) => (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName.toLowerCase());
        const res = { scroll: document.documentElement.scrollWidth - W };
        // things sticking out past the screen edge (sideways scroll on phones)
        res.wide = [...wrap.querySelectorAll('*')].filter((e) => vis(e) && !e.closest('[data-clone]') && R(e).right > W + 1 && !clipped(e))
          .map((e) => `${name(e)} ${Math.round(R(e).right - W)}px`).filter((v, k, a) => a.indexOf(v) === k);
        // text too small to read on a phone (legal/disclaimer text can be 11-12px)
        res.tiny = [...wrap.querySelectorAll('h1,h2,h3,h4,h5,p,li,a,span,button,td,small')].filter((e) => vis(e) && !e.closest('[data-clone]')
          && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 11)
          .map((e) => `${name(e)} ${getComputedStyle(e).fontSize}`).filter((v, k, a) => a.indexOf(v) === k);
        // buttons / links too small to tap
        res.tap = [...wrap.querySelectorAll('a,button')].filter((e) => vis(e) && !e.closest('[data-clone]') && !e.closest('p,li') && (R(e).height < 36 || R(e).width < 36))
          .map((e) => `${(e.textContent || '').trim().slice(0, 24) || name(e)} ${Math.round(R(e).width)}x${Math.round(R(e).height)}`).filter((v, k, a) => a.indexOf(v) === k);
        // photos blown up past their file (blurry on phones)
        res.blurry = [...wrap.querySelectorAll('img')].filter((i) => { const r = R(i); if (r.width < 120 || !i.naturalWidth || i.closest('[data-clone]')) return false;
          let dw = r.width; if (getComputedStyle(i).objectFit === 'cover') dw = Math.max(r.width, r.height * i.naturalWidth / i.naturalHeight);
          return dw / i.naturalWidth > 1.1; }).map((i) => (i.currentSrc || i.src).split('/').pop()).filter((v, k, a) => a.indexOf(v) === k);
        // images that did not load
        res.broken = [...wrap.querySelectorAll('img')].filter((i) => i.complete && !i.naturalWidth && !i.closest('[data-clone]')).map((i) => (i.currentSrc || i.src).split('/').pop());
        // headings broken into one word per line (QA "fix the line break")
        res.lonely = [...wrap.querySelectorAll('h1,h2,h3')].filter((h) => vis(h)).filter((h) => { const words = h.textContent.trim().split(/\s+/).length;
          const lh = parseFloat(getComputedStyle(h).lineHeight) || parseFloat(getComputedStyle(h).fontSize) * 1.2; return words > 2 && Math.round(R(h).height / lh) >= words; })
          .map((h) => h.textContent.trim().slice(0, 40));
        // "&" left at the end (or start) of a heading line (QA 2026-11-16: "Put the Build & down" on 3 pages)
        res.amp = [...wrap.querySelectorAll('h1,h2,h3,h4')].filter((h) => h.getClientRects().length && !h.closest('[data-clone]')).map((h) => {
          const tw = document.createTreeWalker(h, NodeFilter.SHOW_TEXT); const toks = []; let n;
          while ((n = tw.nextNode())) { const re = /\S+/g; let m; while ((m = re.exec(n.data))) { const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length); const b = rg.getClientRects()[0]; if (b) toks.push({ t: m[0], top: Math.round(b.top) }); } }
          for (let k = 0; k < toks.length; k++) { if (toks[k].t !== '&') continue; const a = toks[k - 1], c = toks[k + 1];
            // short = 2 words or fewer on one side ("Build & Price") -> FIX; a break around "&" in a long title -> CHECK only
            if ((a && Math.abs(a.top - toks[k].top) > 3) || (c && Math.abs(c.top - toks[k].top) > 3)) return { t: h.textContent.trim().replace(/\s+/g, ' ').slice(0, 60), s: k <= 2 || toks.length - 1 - k <= 2 }; }
          return null; }).filter(Boolean);
        res.height = document.documentElement.scrollHeight;
        return res;
      }, W);
      const add = (bad, fix, ok) => { out.push(bad ? fix : ok); if (bad && fix.startsWith('FIX')) fixes++; };
      out.push(`-- ${W}px --`);
      add(r.scroll > 1, `FIX ${W} sideways scroll: page is ${r.scroll}px wider than the phone${r.wide.length ? ' - ' + r.wide.slice(0, 5).join('; ') : ''}`, `OK  ${W} no sideways scroll`);
      if (r.scroll <= 1) add(r.wide.length, `FIX ${W} content cut off at the screen edge: ${r.wide.slice(0, 5).join('; ')}`, `OK  ${W} nothing past the screen edge`);
      add(r.broken.length, `FIX ${W} images not loading: ${r.broken.slice(0, 6).join(', ')}`, `OK  ${W} all images load`);
      add(r.blurry.length, `FIX ${W} blurry photos (shown bigger than the file): ${r.blurry.slice(0, 6).join(', ')}`, `OK  ${W} no blurry photos`);
      add(r.tiny.length, `CHECK ${W} text under 11px: ${r.tiny.slice(0, 6).join('; ')}`, `OK  ${W} text size`);
      add(r.tap.length, `CHECK ${W} small tap targets (under 36px): ${r.tap.slice(0, 6).join('; ')}`, `OK  ${W} tap targets`);
      add(r.lonely.length, `CHECK ${W} heading one word per line: ${r.lonely.slice(0, 4).join('; ')}`, `OK  ${W} heading line breaks`);
      const ampFix = r.amp.filter((x) => x.s), ampChk = r.amp.filter((x) => !x.s);
      add(ampFix.length, `FIX ${W} "&" splits a short phrase across lines (QA: "Put the Build & down") - keep it together: ${ampFix.slice(0, 4).map((x) => x.t).join('; ')}`, `OK  ${W} no short "&" phrase split in headings`);
      if (ampChk.length) out.push(`CHECK ${W} "&" at a line break in a long heading (fine if it reads well): ${ampChk.slice(0, 4).map((x) => x.t).join('; ')}`);
      add(errs.length, `FIX ${W} script errors: ${errs.slice(0, 3).join(' | ')}`, `OK  ${W} no script errors`);
      // screenshots in pieces (only the 390 set is full length; 375/430 get the first screen to spot layout shifts)
      const total = W === 390 ? r.height : Math.min(r.height, H);
      for (let y = 0, n = 1; y < total; y += SLICE, n++) {
        const f = path.join(shots, `${W}-${n}.png`);
        await p.screenshot({ path: f, fullPage: true, clip: { x: 0, y, width: W, height: Math.min(SLICE, total - y) } });
        out.push(`SHOT ${f}`);
      }
      await ctx.close();
    }
  } finally { await b.close(); }
  out.push(fixes ? `RESULT ${fixes} FIX line(s) - fix them, run again` : 'RESULT no FIX lines - now look at the 390 screenshots against the Mobile rules in qa_feedback.md');
  console.log(out.join('\n'));
})().catch((e) => { console.log('ERROR ' + e.message); });
