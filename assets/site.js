/* Property Media Japan: shared behaviour for every page */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.add('js');

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
    var setOpen = function (open, returnFocus) {
      links.classList.toggle('open', open);
      doc.body.classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      if (open) { var first = links.querySelector('a'); if (first) first.focus(); }
      else if (returnFocus) toggle.focus();
    };
    toggle.addEventListener('click', function () { setOpen(!links.classList.contains('open')); });
    links.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { setOpen(false); }); });
    doc.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && links.classList.contains('open')) setOpen(false, true);
    });
    window.addEventListener('resize', function () { if (window.innerWidth > 768 && links.classList.contains('open')) setOpen(false); });
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
  var contact = doc.getElementById('contact');
  var sticky = doc.querySelector('.sticky-cta');
  if (contact && sticky && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { sticky.classList.toggle('is-hidden', e.isIntersecting); });
    }, { threshold: 0.15 }).observe(contact);
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
    handle.setAttribute('aria-label', 'Compare before and after virtual staging');
    handle.setAttribute('aria-valuemin', '0');
    handle.setAttribute('aria-valuemax', '100');
    var set = function (p) {
      pct = Math.min(Math.max(p, 2), 98);
      after.style.clipPath = 'inset(0 ' + (100 - pct).toFixed(2) + '% 0 0)';
      handle.style.left = pct.toFixed(2) + '%';
      handle.setAttribute('aria-valuenow', Math.round(pct));
      handle.setAttribute('aria-valuetext', Math.round(pct) + '% after');
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
  });

  /* Click to play YouTube (nothing loads from YouTube until clicked) */
  doc.querySelectorAll('.video-facade').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var f = doc.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + btn.dataset.video + '?autoplay=1&rel=0';
      f.title = btn.getAttribute('aria-label') || 'Property video';
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.allowFullscreen = true;
      btn.replaceWith(f);
      f.focus();
    });
  });
})();
