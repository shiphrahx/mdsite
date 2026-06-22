// mdsite client behavior: theme toggle, sidebar collapse, TOC scroll-sync.
// Fully offline — no network requests.
(function () {
  'use strict';

  var root = document.documentElement;

  // ---- Theme toggle (persisted) ----
  function currentTheme() {
    var t = root.getAttribute('data-theme');
    if (t) return t;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  var themeBtn = document.querySelector('.theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('mdsite-theme', next); } catch (e) {}
    });
  }

  // ---- Mobile sidebar toggle ----
  var sidebar = document.getElementById('sidebar');
  var navToggle = document.querySelector('.nav-toggle');
  if (navToggle && sidebar) {
    navToggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });
  }

  // ---- Collapsible folders (state persisted) ----
  var COLLAPSE_KEY = 'mdsite-collapsed';
  var collapsed = {};
  try { collapsed = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}'); } catch (e) {}

  function saveCollapsed() {
    try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed)); } catch (e) {}
  }

  document.querySelectorAll('.nav-folder').forEach(function (folder) {
    var id = folder.getAttribute('data-path') || '';
    if (collapsed[id]) folder.classList.add('collapsed');
    var label = folder.querySelector('.folder-label');
    if (label) {
      label.addEventListener('click', function () {
        folder.classList.toggle('collapsed');
        collapsed[id] = folder.classList.contains('collapsed');
        saveCollapsed();
      });
    }
  });

  // ---- TOC scroll-sync ----
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (tocLinks.length) {
    var idToLink = {};
    var targets = [];
    tocLinks.forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var id = href.charAt(0) === '#' ? href.slice(1) : '';
      if (!id) return;
      var el = document.getElementById(id);
      if (el) { idToLink[id] = a; targets.push(el); }
    });

    var activeLink = null;
    function setActive(id) {
      var link = idToLink[id];
      if (link === activeLink) return;
      if (activeLink) activeLink.classList.remove('active');
      if (link) link.classList.add('active');
      activeLink = link;
    }

    if ('IntersectionObserver' in window) {
      var visible = new Set();
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) visible.add(e.target.id);
          else visible.delete(e.target.id);
        });
        // Pick the topmost visible heading.
        var best = null, bestTop = Infinity;
        visible.forEach(function (id) {
          var el = document.getElementById(id);
          if (!el) return;
          var top = el.getBoundingClientRect().top;
          if (top < bestTop) { bestTop = top; best = id; }
        });
        if (best) setActive(best);
      }, { rootMargin: '-10% 0px -75% 0px', threshold: 0 });
      targets.forEach(function (t) { obs.observe(t); });
    }
  }
})();
