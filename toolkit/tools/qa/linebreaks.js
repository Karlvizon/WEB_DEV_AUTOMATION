// usage: node linebreaks.js "<selector of paragraphs>" [--{{P}}-wd values...] -> last word of every line, per paragraph
const { chromium } = require('playwright-core');
const path = require('path');
const [sel, ...vals] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: 1920, height: 900 } });
  await p.goto('file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/'));
  await p.evaluate(() => document.fonts.ready);
  for (const v of (vals.length ? vals : [''])) {
    const r = await p.evaluate(([sel, v]) => [...document.querySelectorAll(sel)].map((el) => {
      if (v) el.style.setProperty('--{{P}}-wd', v + '%');
      const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const chars = [];
      while (tw.nextNode()) { const n = tw.currentNode; for (let i = 0; i < n.length; i++) chars.push([n, i]); }
      const rg = document.createRange(); let prevY = null, line = '', ends = [];
      for (const [n, i] of chars) { rg.setStart(n, i); rg.setEnd(n, i + 1); const q = rg.getBoundingClientRect(); if (!q.width) { line += n.data[i]; continue; }
        const y = q.bottom; if (prevY !== null && y > prevY + 8) { ends.push(line.trim().split(' ').slice(-2).join(' ')); line = ''; } prevY = Math.max(prevY || 0, y); line += n.data[i]; }
      return ends.join(' | ');
    }), [sel, v]);
    console.log('== ' + v); r.forEach((x, i) => console.log(i + 1, x));
  }
  await b.close();
})();
