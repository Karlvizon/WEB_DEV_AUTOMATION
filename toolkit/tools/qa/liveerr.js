// Live page: where do the page's JS errors come from (our CMS JS field or the site's scripts)? + carousel works once.
// usage: node liveerr.js <url>
const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push((e.message + ' @ ' + (e.stack || '').split('\n').slice(1, 3).join(' ')).slice(0, 260)));
  let ok = false;
  for (let t = 0; t < 5 && !ok; t++) { await p.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {}); await p.waitForTimeout(7000); ok = await p.evaluate(() => !!document.getElementById('{{ID}}')).catch(() => false); }
  await p.evaluate(() => document.querySelector('#{{ID}} .{{P}}-disc').scrollIntoView());
  await p.waitForTimeout(800);
  const dot = () => p.evaluate(() => [...document.querySelectorAll('#{{ID}} .{{P}}-car__dot')].findIndex((d) => d.getAttribute('aria-current') === 'true'));
  const d0 = await dot();
  await p.click('#{{ID}} .{{P}}-car__arrow--next'); await p.waitForTimeout(900);
  const d1 = await dot();
  console.log(`carousel: dot ${d0 + 1} -> ${d1 + 1} after one click (${d1 === (d0 + 1) % 4 ? 'ok, one step' : 'WRONG'})`);
  console.log('JS errors:'); errs.forEach((e) => console.log('  ' + e));
  console.log('from our JS field (di-page-composer-scripts / CP feature code):', errs.filter((e) => /CP\.|carousel|{{P}}-|di-page-composer/.test(e)).length);
  await b.close();
})();
