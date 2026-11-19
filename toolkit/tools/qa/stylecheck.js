// Computed-style audit at 1920 against the Figma values (file fjhKmh5MKiohKT7HghkX1J, frame 1:2, design context per section).
// PLANT=1 injects 4 wrong values first to prove the checker catches them.
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const W = 'rgb(255, 255, 255)', K = 'rgb(0, 0, 0)', NAVY = 'rgb(0, 0, 102)', SLATE = 'rgb(52, 58, 64)', GREY = 'rgb(243, 243, 243)';
const SH = 'rgba(0, 0, 0, 0.25) 0px 4px 4px 0px';
const E = [ // selector, property, expected  (Figma fjhKmh5MKiohKT7HghkX1J, design context per section)
  // hero 1:5
  ['.{{P}}-hero', 'height', '700px'], ['.{{P}}-hero__tx', 'width', '361px'], ['.{{P}}-hero__nm', 'fontSize', '60px'], ['.{{P}}-hero__nm', 'fontWeight', '700'], ['.{{P}}-hero__nm', 'borderBottomWidth', '3px'], ['.{{P}}-hero__nm', 'borderBottomColor', W],
  ['.{{P}}-hero__loc', 'fontSize', '48px'], ['.{{P}}-hero__loc', 'fontWeight', '400'], ['.{{P}}-hero__p', 'fontSize', '20px'], ['.{{P}}-hero__p', 'borderTopWidth', '1px'], ['.{{P}}-hero__p', 'paddingTop', '10px'],
  // CTA bars 1:12
  ['.{{P}}-cta', 'height', '130px'], ['.{{P}}-cta', 'backgroundColor', GREY], ['.{{P}}-cta__row', 'columnGap', '20px'], ['a.{{P}}-btn', 'width', '425px'], ['a.{{P}}-btn', 'height', '74px'], ['a.{{P}}-btn', 'backgroundColor', NAVY],
  ['a.{{P}}-btn', 'color', W], ['a.{{P}}-btn', 'borderTopLeftRadius', '10px'], ['a.{{P}}-btn', 'fontSize', '28px'], ['a.{{P}}-btn', 'fontWeight', '700'],
  // discover 1:22 + carousel
  ['.{{P}}-disc', 'height', '1111px'], ['.{{P}}-disc__h', 'fontSize', '60px'], ['.{{P}}-disc__sub', 'fontSize', '24px'], ['.{{P}}-car__slide', 'width', '855px'], ['.{{P}}-car__slide', 'height', '804px'], ['.{{P}}-car__panel', 'width', '661px'],
  ['.{{P}}-car__panel', 'backgroundColor', 'rgba(30, 30, 30, 0.7)'], ['.{{P}}-car__panel', 'borderTopLeftRadius', '20px'], ['.{{P}}-car__h', 'fontSize', '48px'], ['.{{P}}-car__img', 'height', '423px'], ['.{{P}}-car__tx', 'width', '529px'], ['.{{P}}-car__p', 'fontSize', '24px'],
  ['a.{{P}}-car__cta', 'width', '340px'], ['a.{{P}}-car__cta', 'height', '58px'], ['a.{{P}}-car__cta', 'borderTopColor', 'rgb(129, 129, 129)'], ['.{{P}}-car__arrow', 'width', '82px'], ['.{{P}}-car__arrow', 'backgroundColor', SLATE], ['.{{P}}-car__nav', 'columnGap', '411px'],
  // overview 1:80
  ['.{{P}}-ov .{{P}}-h2', 'fontSize', '46px'], ['.{{P}}-ov .{{P}}-h2', 'fontWeight', '700'], ['.{{P}}-ov .{{P}}-sub', 'fontSize', '20px'], ['.{{P}}-ov .{{P}}-head', 'width', '1288px'], ['.{{P}}-ov__box', 'width', '1760px'], ['.{{P}}-ov__box', 'height', '925px'], ['.{{P}}-ov__box', 'borderTopLeftRadius', '10px'],
  ['.{{P}}-ovk', 'width', '551px'], ['.{{P}}-ovk .{{P}}-m', 'height', '313px'], ['.{{P}}-ovk__tx', 'height', '84px'], ['.{{P}}-ovk__tx', 'backgroundColor', K], ['.{{P}}-ovk .{{P}}-t', 'fontSize', '28px'], ['.{{P}}-ovk .{{P}}-t', 'fontWeight', '500'], ['.{{P}}-ov__cards', 'columnGap', '8px'],
  // category titles
  ['.{{P}}-kicker__t', 'fontSize', '20px'], ['.{{P}}-kicker__t', 'fontWeight', '700'], ['.{{P}}-kicker__t', 'color', NAVY], ['.{{P}}-kicker__t', 'letterSpacing', '2px'], ['.{{P}}-cat .{{P}}-top .{{P}}-head', 'width', '1354px'],
  // capability 1: stats + header
  ['.{{P}}-st', 'width', '430px'], ['.{{P}}-st', 'height', '152px'], ['.{{P}}-st', 'backgroundColor', GREY], ['.{{P}}-st', 'borderBottomWidth', '2px'], ['.{{P}}-st', 'borderTopLeftRadius', '20px'], ['.{{P}}-st', 'borderBottomLeftRadius', '0px'], ['.{{P}}-stats', 'columnGap', '14px'],
  ['.{{P}}-st__v', 'fontSize', '46px'], ['.{{P}}-st__v', 'fontWeight', '500'], ['.{{P}}-st__l', 'fontSize', '20px'], ['.{{P}}-st__l', 'fontWeight', '300'], ['.{{P}}-blk>.{{P}}-h595', 'height', '595px'], ['.{{P}}-blk>.{{P}}-h595', 'borderTopLeftRadius', '20px'],
  // capability 2 cards
  ['.{{P}}-g3 .{{P}}-fc', 'width', '571.3px'], ['.{{P}}-g3 .{{P}}-fc .{{P}}-m', 'height', '286px'], ['.{{P}}-g3 .{{P}}-fc .{{P}}-m', 'borderTopLeftRadius', '20px'], ['.{{P}}-g2 .{{P}}-fc .{{P}}-m', 'height', '322px'], ['.{{P}}-g3', 'columnGap', '23px'],
  ['.{{P}}-fc .{{P}}-t', 'fontSize', '28px'], ['.{{P}}-fc .{{P}}-t', 'letterSpacing', '-0.56px'], ['.{{P}}-fc .{{P}}-p', 'fontSize', '20px'], ['.{{P}}-fc .{{P}}-p', 'fontWeight', '300'], ['.{{P}}-fc', 'rowGap', '10px'],
  // capability 3 image / black text rows
  ['.{{P}}-ib>.{{P}}-m', 'width', '869px'], ['.{{P}}-ib>.{{P}}-m', 'height', '468px'], ['.{{P}}-ib__tx', 'backgroundColor', K], ['.{{P}}-ib__tx', 'borderTopLeftRadius', '20px'], ['.{{P}}-ib__in', 'width', '649px'],
  // capability 4 / technology 3 dark panels
  ['.{{P}}-dp', 'height', '1165px'], ['.{{P}}-dp', 'borderTopLeftRadius', '20px'], ['.{{P}}-bc', 'width', '511px'], ['.{{P}}-bc .{{P}}-m', 'height', '268px'], ['.{{P}}-bc__tx', 'height', '161px'], ['.{{P}}-bc__tx', 'backgroundColor', K], ['.{{P}}-bc', 'borderTopLeftRadius', '10px'], ['.{{P}}-bcs__row', 'columnGap', '15px'],
  ['.{{P}}-dh844', 'height', '844px'], ['.{{P}}-cw759', 'width', '759px'], ['.{{P}}-cw759 .{{P}}-m', 'height', '453px'], ['.{{P}}-bh150', 'height', '150px'],
  // capability 5 cards
  ['.{{P}}-fx', 'width', '869px'], ['.{{P}}-fx', 'height', '427px'], ['.{{P}}-fx', 'backgroundColor', K], ['.{{P}}-fx', 'paddingLeft', '25px'], ['.{{P}}-fx', 'columnGap', '28px'], ['.{{P}}-fx>.{{P}}-m', 'width', '334px'], ['.{{P}}-fx>.{{P}}-m', 'height', '386px'], ['.{{P}}-fx>.{{P}}-tx', 'width', '450px'],
  // bands
  ['.{{P}}-band', 'height', '500px'], ['.{{P}}-band', 'borderTopLeftRadius', '20px'], ['.{{P}}-band', 'paddingLeft', '60px'], ['.{{P}}-band', 'paddingTop', '80px'], ['.{{P}}-band', 'boxShadow', SH], ['.{{P}}-bh', 'fontSize', '46px'], ['.{{P}}-bh', 'fontWeight', '700'], ['.{{P}}-bp', 'fontSize', '20px'], ['.{{P}}-band__tx', 'width', '566px'],
  // utility / technology split rows
  ['.{{P}}-sr>.{{P}}-m', 'width', '868px'], ['.{{P}}-sr>.{{P}}-m', 'height', '374px'], ['.{{P}}-sr>.{{P}}-tx', 'width', '851px'], ['.{{P}}-sr--park>.{{P}}-m', 'width', '869px'], ['.{{P}}-sr--park>.{{P}}-m', 'height', '322px'],
  // design 1 cards, design 2 wheels band
  ['.{{P}}-oc', 'width', '869px'], ['.{{P}}-oc', 'height', '344px'], ['.{{P}}-oc', 'boxShadow', SH], ['.{{P}}-oc', 'paddingLeft', '25px'], ['.{{P}}-oc>.{{P}}-tx', 'width', '348px'],
  ['.{{P}}-gb', 'backgroundColor', GREY], ['.{{P}}-gb', 'width', '1920px'], ['.{{P}}-gb', 'paddingTop', '40px'], ['.{{P}}-gb__in', 'width', '1759px'], ['.{{P}}-wh', 'width', '411px'], ['.{{P}}-wh .{{P}}-m', 'height', '404px'], ['.{{P}}-whs', 'columnGap', '38px'], ['.{{P}}-whs', 'rowGap', '20px'], ['.{{P}}-whc', 'fontWeight', '300'],
  // connected
  ['.{{P}}-cn__hd', 'width', '1757px'], ['.{{P}}-cn__hd', 'height', '160px'], ['.{{P}}-cn__hd', 'backgroundColor', SLATE], ['.{{P}}-cn__hd', 'borderTopLeftRadius', '10px'], ['.{{P}}-ct', 'width', '872px'], ['.{{P}}-ct', 'height', '365px'], ['.{{P}}-ct .{{P}}-t', 'fontSize', '46px'], ['.{{P}}-ct .{{P}}-t', 'fontWeight', '500'], ['.{{P}}-ct>.{{P}}-tx', 'width', '300px'],
  // trims
  ['.{{P}}-trim', 'width', '868px'], ['.{{P}}-trim', 'height', '324px'], ['.{{P}}-trim', 'borderTopWidth', '2px'], ['.{{P}}-trim', 'borderTopColor', 'rgba(52, 58, 64, 0.6)'], ['.{{P}}-trim', 'borderTopLeftRadius', '20px'], ['.{{P}}-trim .{{P}}-m', 'width', '500px'],
  ['.{{P}}-trim .{{P}}-m', 'height', '285px'], ['.{{P}}-trim__tx', 'width', '291px'], ['.{{P}}-trim__h', 'fontSize', '42px'], ['.{{P}}-trim__h', 'fontWeight', '500'], ['.{{P}}-trim__rule', 'width', '94px'], ['.{{P}}-trim__rule', 'backgroundColor', NAVY],
  ['.{{P}}-trim__l', 'fontWeight', '300'], ['.{{P}}-trim__p', 'fontSize', '28px'], ['.{{P}}-trim__p', 'fontWeight', '500'],
  // disclaimers and MLP copy (same size question / body)
  ['.{{P}}-legal p', 'fontSize', '20px'], ['.{{P}}-legal p', 'fontWeight', '300'], ['.{{P}}-legal p', 'lineHeight', '24px'], ['.{{P}}-seo__q', 'fontSize', '20px'], ['.{{P}}-seo__q', 'fontWeight', '700'], ['.{{P}}-seo__p', 'fontSize', '20px'], ['.{{P}}-seo__p', 'fontWeight', '400'],
  ['h1.{{P}}-hero__h', 'textTransform', 'none'], ['.{{P}}-h2', 'textTransform', 'none'],
];
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1000 } });
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  const sb = await p.evaluate(() => innerWidth - document.documentElement.clientWidth);
  await p.setViewportSize({ width: 1920 + sb, height: 1000 });
  await p.evaluate(() => document.fonts.ready);
  if (process.env.PLANT) await p.addStyleTag({ content: 'html #{{ID}} .{{P}}-wrap a.{{P}}-btn{border-radius:4px !important}html #{{ID}} .{{P}}-wrap .{{P}}-kicker__t{color:#f00 !important}html #{{ID}} .{{P}}-trim{height:330px !important}html body #{{ID}} .{{P}}-wrap .{{P}}-fc .{{P}}-p{font-weight:400 !important}' });
  const res = await p.evaluate((E) => E.map(([s, prop, exp]) => {
    const e = document.querySelector('#{{ID}} ' + s); if (!e) return [s, prop, exp, 'MISSING'];
    const cs = getComputedStyle(e); let v = cs[prop];
    if (/^(width|height)$/.test(prop)) v = Math.round(e.getBoundingClientRect()[prop] * 10) / 10 + 'px';
    return [s, prop, exp, v];
  }), E);
  const fam = await p.evaluate(() => ['.{{P}}-car__h', '.{{P}}-h2', '.{{P}}-legal p', 'h1.{{P}}-hero__h', 'a.{{P}}-btn', '.{{P}}-trim__h'].map((s) => [s, getComputedStyle(document.querySelector('#{{ID}} ' + s)).fontFamily.split(',')[0].replace(/"/g, '')]));
  const loaded = await p.evaluate(() => ['300 20px Roboto', '400 20px Roboto', '500 20px Roboto', '700 20px Roboto', '400 24px Roboto'].map((f) => [f, document.fonts.check(f)]));
  const out = []; let bad = 0;
  for (const [s, prop, exp, v] of res) { const ok = v === exp; if (!ok) bad++; out.push(`${ok ? 'ok ' : 'BAD'} ${s} ${prop}: ${v}${ok ? '' : ' (Figma ' + exp + ')'}`); }
  for (const [s, v] of fam) { const ok = v === 'Roboto'; if (!ok) bad++; out.push(`${ok ? 'ok ' : 'BAD'} ${s} fontFamily: ${v}`); }
  for (const [f, ok] of loaded) { if (!ok) bad++; out.push(`${ok ? 'ok ' : 'BAD'} font loaded: ${f}`); }
  console.log(out.filter((l) => !l.startsWith('ok')).join('\n'));
  console.log(`${out.length} computed-style checks, ${bad} off${process.env.PLANT ? ' (PLANT run: 4 wrong values injected)' : ''}`);
  if (!process.env.PLANT) fs.writeFileSync(path.join(ROOT, 'qa/stylecheck.txt'), out.join('\n') + `\n${out.length} checks, ${bad} off\n`);
  await b.close();
})();
