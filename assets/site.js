/* Property Media Japan: shared behaviour for every page */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.add('js');
  var ja = (root.getAttribute('lang') || '').indexOf('ja') === 0;
  var T = ja
    ? { open: 'メニューを開く', close: 'メニューを閉じる', slider: 'バーチャルステージングの前後を比較', after: function (n) { return '加工後を' + n + '%表示'; }, video: '物件動画', yt: '（YouTube）' }
    : { open: 'Open menu', close: 'Close menu', slider: 'Compare before and after virtual staging', after: function (n) { return n + '% after'; }, video: 'Property video', yt: ' (YouTube)' };

  /* Reduced motion: keep background videos still (poster frame) instead of playing */
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    doc.querySelectorAll('video[autoplay]').forEach(function (v) { v.removeAttribute('autoplay'); v.pause(); });
  }

  /* Footer year */
  var year = doc.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* Nav background after scrolling */
  var nav = doc.getElementById('nav');
  if (nav) {
    var onScroll = function () { nav.classList.toggle('scrolled', window.scrollY > 60); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* Mobile menu */
  var toggle = doc.getElementById('navToggle');
  var links = doc.getElementById('navLinks');
  if (toggle && links) {
    links.querySelectorAll('a.active').forEach(function (a) { a.setAttribute('aria-current', 'page'); });
    var behind = doc.querySelectorAll('main, footer, .sticky-cta-wrap');
    var setOpen = function (open, returnFocus) {
      links.classList.toggle('open', open);
      behind.forEach(function (el) { if (open) el.setAttribute('inert', ''); else el.removeAttribute('inert'); });
      doc.body.classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? T.close : T.open);
      if (open) { var first = links.querySelector('a'); if (first) first.focus(); }
      else if (returnFocus) toggle.focus();
    };
    toggle.addEventListener('click', function () { setOpen(!links.classList.contains('open')); });
    links.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { setOpen(false); }); });
    doc.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && links.classList.contains('open')) setOpen(false, true);
    });
    window.addEventListener('resize', function () { if (window.innerWidth > 1023 && links.classList.contains('open')) setOpen(false); });
  }

  /* Reveal on scroll */
  var reveals = doc.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); } });
    }, { threshold: 0, rootMargin: '0px 0px -8% 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add('visible'); });
  }

  /* Hide the sticky quote bar while the contact section is on screen */
  var sticky = doc.querySelector('.sticky-cta');
  if (sticky) {
    var inView = 0, top = true;
    var update = function () { sticky.classList.toggle('is-hidden', top || inView > 0); };
    var onTop = function () { var t = window.scrollY < window.innerHeight * 0.6; if (t !== top) { top = t; update(); } };
    window.addEventListener('scroll', onTop, { passive: true });
    onTop(); update();
    if ('IntersectionObserver' in window) {
      var io2 = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting && !e.target._in) { e.target._in = true; inView++; }
          else if (!e.isIntersecting && e.target._in) { e.target._in = false; inView--; }
        });
        update();
      }, { threshold: 0.05 });
      [doc.getElementById('contact'), doc.querySelector('footer')].forEach(function (el) { if (el) io2.observe(el); });
    }
  }

  /* FAQ accordion */
  doc.querySelectorAll('.faq-question').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var item = btn.closest('.faq-item');
      var wasOpen = item.classList.contains('open');
      doc.querySelectorAll('.faq-item.open').forEach(function (i) {
        i.classList.remove('open');
        i.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
      });
      if (!wasOpen) { item.classList.add('open'); btn.setAttribute('aria-expanded', 'true'); }
    });
  });

  /* Before and after sliders: pointer, touch and keyboard */
  doc.querySelectorAll('[data-slider]').forEach(function (slider) {
    var track = slider.querySelector('.ba-slider-track');
    var after = slider.querySelector('.ba-after');
    var handle = slider.querySelector('.ba-slider-handle');
    if (!track || !after || !handle) return;
    var pct = 50, dragging = false;
    handle.setAttribute('role', 'slider');
    handle.setAttribute('tabindex', '0');
    handle.setAttribute('aria-label', T.slider);
    handle.setAttribute('aria-valuemin', '0');
    handle.setAttribute('aria-valuemax', '100');
    var set = function (p) {
      pct = Math.min(Math.max(p, 2), 98);
      after.style.clipPath = 'inset(0 ' + (100 - pct).toFixed(2) + '% 0 0)';
      handle.style.left = pct.toFixed(2) + '%';
      handle.setAttribute('aria-valuenow', Math.round(pct));
      handle.setAttribute('aria-valuetext', T.after(Math.round(pct)));
      slider.classList.add('active');
    };
    var fromX = function (x) { var r = track.getBoundingClientRect(); set((x - r.left) / r.width * 100); };
    slider.addEventListener('pointerdown', function (e) { dragging = true; fromX(e.clientX); if (slider.setPointerCapture) slider.setPointerCapture(e.pointerId); });
    slider.addEventListener('pointermove', function (e) { if (dragging) fromX(e.clientX); });
    slider.addEventListener('pointerup', function () { dragging = false; });
    slider.addEventListener('pointercancel', function () { dragging = false; });
    handle.addEventListener('keydown', function (e) {
      var step = e.shiftKey ? 10 : 4;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { set(pct - step); e.preventDefault(); }
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { set(pct + step); e.preventDefault(); }
      if (e.key === 'Home') { set(0); e.preventDefault(); }
      if (e.key === 'End') { set(100); e.preventDefault(); }
    });
    handle.setAttribute('aria-valuenow', '50');
    handle.setAttribute('aria-valuetext', T.after(50));
  });

  /* Click to play YouTube (nothing loads from YouTube until clicked) */
  doc.querySelectorAll('.video-facade').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var f = doc.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + btn.dataset.video + '?autoplay=1&rel=0' + (ja ? '&hl=ja&cc_lang_pref=ja' : '');
      f.title = (btn.getAttribute('aria-label') || T.video).replace(/^[^:：]*[:：]\s*/, '') + T.yt;
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.allowFullscreen = true;
      btn.replaceWith(f);
      f.focus();
    });
  });
})();
