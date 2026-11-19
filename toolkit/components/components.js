(function () {
  var CP = { features: [] };
  CP.ready = function (fn) {
    if (document.readyState == 'loading') { document.addEventListener('DOMContentLoaded', fn); } else { fn(); }
  };
  CP.later = function (fn, ms) {
    var job = { live: true, start: 0 };
    job.cancel = function () { job.live = false; };
    function tick(now) {
      if (!job.live) { return; }
      if (!job.start) { job.start = now; }
      if (now - job.start >= ms) { job.live = false; fn(); } else { requestAnimationFrame(tick); }
    }
    requestAnimationFrame(tick);
    return job;
  };
  CP.feature = function (name, rootSelector, init) {
    CP.features.push({ name: name, root: rootSelector, init: init });
  };
  CP.up = function (el, cls, stop) {
    while (el) {
      if (el.classList) {
        if (el.classList.contains(cls)) { return el; }
      }
      if (el === stop) { return null; }
      el = el.parentElement;
    }
    return null;
  };
  CP.start = function (tries) {
    var page = document.getElementById('{{ID}}');
    if (!page) {
      if (tries > 0) { CP.later(function () { CP.start(tries - 1); }, 250); }
      return;
    }
    if (page.getAttribute('data-cp-ready')) { return; }
    page.setAttribute('data-cp-ready', 'yes');
    for (var i = 0; CP.features.length > i; i++) {
      var f = CP.features[i];
      var root = page.querySelector(f.root);
      if (root) {
        try { f.init(root, page); } catch (err) { f.failed = true; }
      }
    }
  };
  CP.feature('carousel', '.{{P}}-disc', function (section) {
    var view = section.querySelector('.{{P}}-car');
    var track = section.querySelector('.{{P}}-car__track');
    if (!view) { return; }
    if (!track) { return; }
    var slides = track.querySelectorAll('.{{P}}-car__slide');
    var dots = section.querySelectorAll('.{{P}}-car__dot');
    var arrows = section.querySelectorAll('.{{P}}-car__arrow');
    var prev = arrows[0];
    var next = arrows[1];
    var count = dots.length;
    var lead = 2;
    if (2 > arrows.length) { return; }
    if (!count) { return; }
    if (lead + count + 3 > slides.length) { return; }
    var pos = lead + 1;
    var settleJob = null;
    var reduce = false;
    var narrow = null;
    var drag = { on: false, mode: null, x: 0, y: 0, dx: 0, moved: false, swallow: false };
    if (typeof matchMedia == 'function') {
      reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      narrow = matchMedia('(max-width: 1024px)');
    }
    function offsetFor(p) {
      var a = slides[p];
      var anchor = a.offsetWidth;
      if (narrow) {
        if (narrow.matches) { anchor = a.offsetWidth / 2; }
      }
      return view.clientWidth / 2 - (a.offsetLeft + anchor);
    }
    function setX(x) {
      track.style.setProperty('transform', 'translate3d(' + Math.round(x) + 'px,0,0)', 'important');
    }
    function place(animate) {
      if (reduce) { animate = false; }
      track.classList.toggle('is-still', !animate);
      setX(offsetFor(pos));
      view.scrollLeft = 0;
    }
    function current() {
      return ((pos - lead) % count + count) % count;
    }
    function paint() {
      var on = current();
      for (var d = 0; count > d; d++) {
        dots[d].setAttribute('aria-current', String(d === on));
      }
    }
    function normalise() {
      var moved = false;
      if (pos >= lead + count) { pos -= count; moved = true; }
      if (lead > pos) { pos += count; moved = true; }
      if (moved) { place(false); }
    }
    function go(p) {
      pos = p;
      place(true);
      paint();
      if (settleJob) { settleJob.cancel(); }
      settleJob = CP.later(normalise, 650);
    }
    function step(dir) {
      normalise();
      go(pos + dir);
    }
    track.addEventListener('transitionend', function (e) {
      if (e.target === track) { normalise(); }
    });
    prev.addEventListener('click', function () { step(-1); });
    next.addEventListener('click', function () { step(1); });
    Array.prototype.forEach.call(dots, function (dot, n) {
      dot.addEventListener('click', function () { normalise(); go(lead + n); });
    });
    function onKey(e) {
      if (e.keyCode == 37) { e.preventDefault(); step(-1); }
      if (e.keyCode == 39) { e.preventDefault(); step(1); }
    }
    view.addEventListener('keydown', onKey);
    Array.prototype.forEach.call(dots, function (dot) { dot.addEventListener('keydown', onKey); });
    function begin(x, y, mode) {
      normalise();
      drag.on = true;
      drag.mode = mode;
      drag.x = x;
      drag.y = y;
      drag.dx = 0;
      drag.moved = false;
    }
    function follow(x, y) {
      if (!drag.on) { return; }
      var dx = x - drag.x;
      if (!drag.moved) {
        if (6 > Math.abs(dx)) { return; }
        if (drag.mode == 'touch') {
          if (Math.abs(y - drag.y) > Math.abs(dx)) { drag.on = false; return; }
        }
        drag.moved = true;
        view.classList.add('is-drag');
        track.classList.add('is-still');
      }
      drag.dx = dx;
      setX(offsetFor(pos) + dx);
    }
    function finish(cancel) {
      if (!drag.on) { return; }
      drag.on = false;
      view.classList.remove('is-drag');
      if (!drag.moved) { return; }
      if (drag.mode == 'mouse') { drag.swallow = true; }
      var dx = drag.dx;
      if (cancel) { dx = 0; }
      var w = slides[pos].offsetWidth;
      var n = 0;
      if (Math.abs(dx) >= 40) { n = Math.max(1, Math.round(Math.abs(dx) / w)); }
      if (n > 2) { n = 2; }
      if (dx > 0) { n = 0 - n; }
      go(pos + n);
    }
    view.addEventListener('mousedown', function (e) {
      if (e.button !== 0) { return; }
      e.preventDefault();
      begin(e.clientX, e.clientY, 'mouse');
    });
    document.addEventListener('mousemove', function (e) {
      if (drag.mode == 'mouse') { follow(e.clientX, e.clientY); }
    });
    document.addEventListener('mouseup', function () {
      if (drag.mode == 'mouse') { finish(false); drag.mode = null; }
    });
    view.addEventListener('touchstart', function (e) {
      if (e.touches.length == 1) { begin(e.touches[0].clientX, e.touches[0].clientY, 'touch'); }
    }, { passive: true });
    view.addEventListener('touchmove', function (e) {
      if (drag.mode == 'touch') { follow(e.touches[0].clientX, e.touches[0].clientY); }
    }, { passive: true });
    view.addEventListener('touchend', function () {
      if (drag.mode == 'touch') { finish(false); drag.mode = null; }
    });
    view.addEventListener('touchcancel', function () {
      if (drag.mode == 'touch') { finish(true); drag.mode = null; }
    });
    view.addEventListener('click', function (e) {
      if (drag.swallow) { e.preventDefault(); e.stopPropagation(); drag.swallow = false; }
    }, true);
    view.addEventListener('dragstart', function (e) { e.preventDefault(); });
    view.addEventListener('scroll', function () { view.scrollLeft = 0; });
    track.addEventListener('focusin', function (e) {
      if (drag.mode == 'mouse') { return; }
      var slide = CP.up(e.target, '{{P}}-car__slide', track);
      if (!slide) { return; }
      for (var s = 0; slides.length > s; s++) {
        if (slides[s] === slide) {
          if (s !== pos) { normalise(); go(s); }
        }
      }
      view.scrollLeft = 0;
    });
    addEventListener('resize', function () { place(false); });
    addEventListener('load', function () { place(false); });
    place(false);
    paint();
  });
  CP.feature('gallery-zoom', '.{{P}}-gal', function (gallery) {
    var cells = gallery.querySelectorAll('.{{P}}-gal__cell');
    function set(cell, on) {
      cell.classList.toggle('is-zoomed', on);
      cell.setAttribute('aria-pressed', String(on));
    }
    function toggle(cell) {
      var on = !cell.classList.contains('is-zoomed');
      Array.prototype.forEach.call(cells, function (c) { set(c, false); });
      set(cell, on);
    }
    function onKey(cell, e) {
      var k = e.keyCode;
      if (k == 13) { e.preventDefault(); toggle(cell); }
      if (k == 32) { e.preventDefault(); toggle(cell); }
    }
    Array.prototype.forEach.call(cells, function (cell) {
      cell.addEventListener('click', function () { toggle(cell); });
      cell.addEventListener('keydown', function (e) { onKey(cell, e); });
    });
  });
  CP.ready(function () { CP.start(40); });
})();
