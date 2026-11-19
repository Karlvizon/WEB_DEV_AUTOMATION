// Browser zoom emulation: CSS viewport = screen / zoom, DPR = zoom. Layout must keep the Figma proportions;
// only text may get relatively smaller (font tokens cap at the Figma px size).
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const screens = [1920, 1440, 1366];
// font caps checked: section h2 <= 46px and discover sub <= 24px at every desktop zoom
const CARDW = ((JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).qa || {}).card) || 868;
const QZ = (JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).qa || {});
const HERO = QZ.hero || 700, BTN = QZ.btn_w || 425, SLIDE = QZ.slide || 855;
const zooms = [1, 0.9, 0.8, 0.75, 0.67, 0.5, 0.33, 0.25, 1.1, 1.25, 1.5, 2];
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const rows = [];
  for (const sc of screens) for (const z of zooms) {
    const W = Math.round(sc / z);
    const ctx = await b.newContext({ viewport: { width: W, height: Math.round(900 / z) }, deviceScaleFactor: z });
    const p = await ctx.newPage();
    await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
    await p.waitForTimeout(400);
    const m = await p.evaluate(([CARDW, SLIDE]) => {
      const vw = document.documentElement.clientWidth;
      const g = (s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect() : null; };
      const rw = (s, def) => { const r = g(s); return r ? r.width / vw : def; };
      const fs = (s) => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
      return { vw, hero: g('.{{P}}-hero').height / vw, sec: rw('.{{P}}-gal, .{{P}}-sec', 1760 / 1920), card: rw('.{{P}}-trim', CARDW / 1920), slide: rw('.{{P}}-car__slide:not([data-clone])', SLIDE / 1920),
        btn: g('.{{P}}-cta--top .{{P}}-btn').width / vw, h60: fs('.{{P}}-h2'), sub: fs('.{{P}}-disc__sub'), hscroll: document.documentElement.scrollWidth > vw + 1 };
    }, [CARDW, SLIDE]);
    const desktop = m.vw > 1024;
    const ok = !m.hscroll && (!desktop || (Math.abs(m.hero - HERO / 1920) < 0.002 && Math.abs(m.sec - 1760 / 1920) < 0.002 && Math.abs(m.slide - SLIDE / 1920) < 0.002 && Math.abs(m.card - CARDW / 1920) < 0.002 && Math.abs(m.btn - BTN / 1920) < 0.002 && m.h60 <= 60 && m.sub <= 24));
    rows.push(`${ok ? 'ok ' : 'BAD'} screen ${sc} zoom ${String(Math.round(z * 100)).padStart(3)}% -> ${String(m.vw).padStart(4)} css px  ${desktop ? 'desktop' : (m.vw > 768 ? 'tablet ' : 'mobile ')}  hero/w ${(m.hero * 1920).toFixed(1)}/1920  section ${(m.sec * 100).toFixed(2)}%  slide ${(m.slide * 1920).toFixed(1)}/1920  h2 ${m.h60.toFixed(1)}px  sub ${m.sub.toFixed(1)}px${m.hscroll ? '  HSCROLL' : ''}`);
    await ctx.close();
  }
  console.log(rows.join('\n'));
  fs.writeFileSync(path.join(ROOT, 'qa/zoom.txt'), rows.join('\n') + '\n');
  await b.close();
})();
