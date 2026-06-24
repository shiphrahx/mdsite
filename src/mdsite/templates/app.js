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

  // ---- Highlight current nav link (rendered once, marked client-side) ----
  (function () {
    var here = location.pathname.replace(/\/+$/, '/') || '/';
    document.querySelectorAll('.nav-tree a').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var path = href.replace(/[?#].*$/, '');
      if (path === here || (path !== '/' && here === path)) {
        a.classList.add('current');
      }
    });
  })();

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

  // ---- Code block copy buttons ----
  (function () {
    var blocks = document.querySelectorAll('.markdown-body pre');
    if (!blocks.length) return;

    function copyText(text, btn) {
      function done() {
        var prev = btn.getAttribute('data-label') || 'Copy';
        btn.classList.add('copied');
        btn.textContent = 'Copied';
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.textContent = prev;
        }, 1500);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        // Fallback for non-secure contexts (e.g. file://, plain http).
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    }

    blocks.forEach(function (pre) {
      pre.classList.add('has-copy');
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.textContent = 'Copy';
      btn.setAttribute('data-label', 'Copy');
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      btn.addEventListener('click', function () {
        var code = pre.querySelector('code');
        copyText((code || pre).innerText.replace(/\n$/, ''), btn);
      });
      pre.appendChild(btn);
    });
  })();

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
