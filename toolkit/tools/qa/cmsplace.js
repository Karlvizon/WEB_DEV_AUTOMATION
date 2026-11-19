// Reassemble the three CMS fields three ways inside a hostile "dealer theme" page and compare against preview.html.
// Image URLs are pointed back at the local files for this test (the CDN copies are uploaded separately).
const { chromium } = require('playwright-core');
const FIELDS = process.env.CMSDIR || require('path').resolve(__dirname, '../..', JSON.parse(require('fs').readFileSync(require('path').resolve(__dirname, '../../project.json'), 'utf8')).platform === 'dealer-inspire' ? 'cms-fields' : 'tools/_work/fields');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const CDN = '{{CDN}}';
const local = (s) => process.env.CDNLIVE ? s : (CDN ? s.split(CDN).join('../assets/webp/') : s.split('assets/webp/').join('../assets/webp/'));
const css = local(fs.readFileSync(path.join(FIELDS, '{{NAME}}.css'), 'utf8'));
const html = local(fs.readFileSync(path.join(FIELDS, '{{NAME}}.html'), 'utf8'));
const js = fs.readFileSync(path.join(FIELDS, '{{NAME}}.js'), 'utf8');
const THEME = '<style>body{margin:0;font-family:Arial;font-size:15px;line-height:1.8;color:#333}h1,h2,h3,h4{font-family:"DM Sans",Georgia,serif;text-transform:uppercase;margin:0 0 20px;line-height:1.1;letter-spacing:2px}p{margin:0 0 25px;padding:4px}a{color:#d00;text-decoration:underline}a:hover{color:#900}img{max-width:100%;height:auto;border:3px solid red}button{background:#eee;border:1px solid #999;border-radius:0;padding:6px 12px}section{padding:40px 0}.row{margin:0}</style>';
const shell = (head, body) => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${THEME}${head}</head><body><header style="height:90px;background:#222"></header><div id="di-page-composer"><div class="container-fluid"><div class="row"><div class="col-xs-12 inner-wysiwyg">${body}</div></div></div></div><footer style="height:200px;background:#222"></footer></body></html>`;
const variants = {
  normal: shell('', `${html}<style>${css}</style><script id="di-page-composer-scripts">${js}</script>`),
  'js-in-head': shell(`<script id="di-page-composer-scripts">${js}</script>`, `<!-- di page composer css --><style>${css}</style><!-- eof: di page composer css -->${html}`),
  'css-merged-after-site-css': shell(`<style>${css}</style>`, `${html}<script>${js}</script>`),
  'css-field-not-output (real site)': shell('<!-- di page composer css --><!-- eof: di page composer css -->', `${html}<script>${js}</script>`),
  'js-field-output-twice': shell(`<script>${js}</script>`, `${html}<script>${js}</script>`),
  'html-inserted-late': shell(`<script>${js}</script>`, `<div id="late-slot"></div><template id="late-html">${html}</template><script>addEventListener('load', function () { setTimeout(function () { document.getElementById('late-slot').replaceWith(document.getElementById('late-html').content.cloneNode(true)); }, 1200); });</script>`),
};
const grab = () => {
  const w = document.querySelector('.{{P}}-wrap').getBoundingClientRect();
  return [...document.querySelectorAll('.{{P}}-wrap h1,.{{P}}-wrap h2,.{{P}}-wrap h3,.{{P}}-wrap h4,.{{P}}-wrap p,.{{P}}-wrap a,.{{P}}-wrap button,.{{P}}-wrap img,.{{P}}-stat,.{{P}}-band,.{{P}}-pc,.{{P}}-split,.{{P}}-c3,.{{P}}-lc,.{{P}}-trim,.{{P}}-gal__cell,.{{P}}-seo__card,.{{P}}-car__slide')]
    .filter((e) => !e.closest('[data-clone]') && e.getClientRects().length)
    .map((e) => { const q = e.getBoundingClientRect(); const cs = getComputedStyle(e);
      return [e.tagName, Math.round(q.left - w.left), Math.round(q.top - w.top), Math.round(q.width), Math.round(q.height), cs.fontFamily.split(',')[0], cs.fontSize, cs.fontWeight, cs.color, cs.textTransform, cs.backgroundColor].join(','); });
};
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const out = [];
  for (const W of [1920, 390]) {
    const c0 = await b.newContext({ viewport: { width: W, height: 1000 } });
    const q = await c0.newPage();
    await q.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
    await q.waitForTimeout(2500);
    const ref = await q.evaluate(grab);
    await c0.close();
    for (const [name, doc] of Object.entries(variants)) {
      const f = path.join(ROOT, 'qa', `_cms-${name}.html`); fs.writeFileSync(f, doc);
      const ctx = await b.newContext({ viewport: { width: W, height: 1000 } });
      const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
      await p.goto('file:///' + f.split(path.sep).join('/'), { waitUntil: 'load' });
      await p.waitForTimeout(2500);
      const got = await p.evaluate(grab);
      const step = await p.evaluate(async () => {
        const dot = () => [...document.querySelectorAll('.{{P}}-car__dot')].findIndex((d) => d.getAttribute('aria-current') === 'true');
        const a = dot(); const nx = document.querySelector('.{{P}}-car__arrow--next'); if (!nx) return [-1, -1]; nx.click();
        await new Promise((r) => setTimeout(r, 900));
        return [a, dot()];
      });
      const fonts = await p.evaluate(() => ({ roboto: (() => { const l = document.querySelector('link[href*="fonts.googleapis"]'); if (!l) return 'n/a (no Google font)'; const fam = decodeURIComponent((l.href.match(/family=([^:&]+)/) || [])[1] || '').replace(/\+/g, ' '); return fam + ' ' + document.fonts.check('400 20px "' + fam + '"'); })(), link: document.querySelectorAll('link[href*="fonts.googleapis"]').length, clones: document.querySelectorAll('.{{P}}-car__slide[data-clone]').length, tf: (document.querySelector('.{{P}}-car__track') ? getComputedStyle(document.querySelector('.{{P}}-car__track')).transform : 'none') }));
      const diffs = got.map((x, i) => [x, ref[i]]).filter(([x, y]) => x !== y);
      out.push(`${W}px ${name.padEnd(26)} ${got.length} elements, ${diffs.length} differ from preview | font loaded ${fonts.roboto} (font links ${fonts.link}) | static clones ${fonts.clones} | carousel next: dot ${step[0] + 1} -> ${step[1] + 1} ${step[1] === step[0] + 1 ? 'ok (one step per click)' : 'WRONG'} | JS errors ${errs.length}`);
      diffs.slice(0, 4).forEach(([x, y]) => out.push(`     cms  ${x}\n     prev ${y}`));
      await ctx.close();
      fs.rmSync(f);
    }
  }
  console.log(out.join('\n'));
  fs.writeFileSync(path.join(ROOT, 'qa/cmsplace.txt'), out.join('\n') + '\n');
  await b.close();
})();
