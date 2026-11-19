// Export the visible frame of every image at 1920 (page coords) to qa/imgboxes.json
const { chromium } = require('playwright-core');
const path = require('path'); const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
const W = +process.argv[2] || 1920;
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await (await b.newContext({ viewport: { width: W, height: 1000 } })).newPage();
  await p.goto('file:///' + path.join(ROOT, 'preview.html').split(path.sep).join('/'), { waitUntil: 'load' });
  await p.waitForTimeout(1500);
  const boxes = await p.evaluate(() => {
    const w = document.querySelector('.{{P}}-wrap').getBoundingClientRect();
    return [...document.querySelectorAll('.{{P}}-wrap img')].filter((i) => !i.closest('[data-clone]') && !i.closest('button')).map((i) => {
      let f = i.parentElement;
      while (f && getComputedStyle(f).overflow !== 'hidden' && f !== document.body) f = f.parentElement;
      const r = (f || i).getBoundingClientRect();
      const q = i.getBoundingClientRect();
      return { src: i.getAttribute('src').split('/').pop(), x: r.left - w.left, y: r.top - w.top + scrollY, w: r.width, h: r.height,
        img: { x: q.left - w.left, y: q.top - w.top + scrollY, w: q.width, h: q.height }, nat: [i.naturalWidth, i.naturalHeight] };
    });
  });
  fs.writeFileSync(path.join(ROOT, 'qa/imgboxes-' + W + '.json'), JSON.stringify(boxes, null, 1));
  console.log(boxes.length + ' image boxes');
  await b.close();
})();
