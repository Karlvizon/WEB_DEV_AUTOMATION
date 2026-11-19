// Measure type sizes, alignment and gaps of a live reference page at phone width (headed Edge, bot shield).
// usage: node refmeasure2.js <url> <pageId> <prefix> [width]   e.g. ... hc-2027-grand-cherokee gch 390
// Without a url (url = "local") it measures this project's preview.html with the same probes.
const { chromium } = require('playwright-core');
const path = require('path');
(async () => {
  const [url, id, pre, wArg] = process.argv.slice(2); const W = +wArg || 390;
  const local = url === 'local';
  const b = await chromium.launch({ channel: 'msedge', headless: !local ? false : true, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await b.newContext({ viewport: { width: W, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const p = await ctx.newPage();
  const target = local ? 'file:///' + path.resolve(__dirname, '../../preview.html').split(path.sep).join('/') : url;
  await p.goto(target, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
  await p.waitForSelector('#' + id, { timeout: 60000 });
  await p.waitForTimeout(3000);
  const r = await p.evaluate(([id, pre]) => {
    const root = document.getElementById(id);
    const q = (s) => root.querySelector(s.replace(/\$/g, pre + '-'));
    const st = (s) => { const e = q(s); if (!e) return s + ' -'; const c = getComputedStyle(e); const b = e.getBoundingClientRect();
      return `${s.replace(/\$/g, '')}: ${c.fontSize}/${c.lineHeight} w${c.fontWeight} ${c.textAlign} ls${c.letterSpacing} box ${Math.round(b.width)}x${Math.round(b.height)}`; };
    const sels = ['.$hero__nm', '.$hero__loc', '.$hero__p', 'a.$btn', '.$disc__h', '.$disc__sub', '.$car__h', '.$car__p', '.$kicker__t', '.$h2', '.$sub',
      '.$fc .$t', '.$fc .$p', '.$fc>.$m', '.$band .$bh', '.$band .$bp', '.$band__tx', '.$oc .$t', '.$oc .$p', '.$oc>.$tx', '.$whc', '.$trim__h', '.$trim__l', '.$trim__p', '.$seo__q', '.$seo__p', '.$legal p', '.$b', '.$ovk__tx .$t', '.$ovk__tx .$p'];
    const gap = (a, b) => { const x = q(a), y = q(b); if (!x || !y) return '-'; return Math.round(y.getBoundingClientRect().top - x.getBoundingClientRect().bottom); };
    const fcs = [...root.querySelectorAll('.' + pre + '-g3 .' + pre + '-fc')];
    const fcGap = fcs.length > 1 ? Math.round(fcs[1].getBoundingClientRect().top - fcs[0].getBoundingClientRect().bottom) : '-';
    const sec = [...root.querySelectorAll('.' + pre + '-b')].slice(0, 6).map((e) => { const c = getComputedStyle(e); return Math.round(e.getBoundingClientRect().width) + 'w mt' + c.marginTop; });
    return [...sels.map(st), 'h2->sub ' + gap('.$h2', '.$sub'), 'fc card->card ' + fcGap, 'fc img->title ' + gap('.$fc>.$m', '.$fc .$t'), 'fc title->text ' + gap('.$fc .$t', '.$fc .$p'), 'sections ' + sec.join(' | ')];
  }, [id, pre]);
  console.log((local ? 'LOCAL ' : 'REF ') + W + 'px\n' + r.join('\n'));
  await b.close();
})();
