// mdsite client-side search over search-index.json. Substring + light fuzzy
// scoring, keyboard navigable. No backend, no network beyond the local index.
(function () {
  'use strict';

  var input = document.getElementById('search-input');
  var box = document.getElementById('search-results');
  if (!input || !box) return;

  var INDEX_URL = (window.MDSITE_BASE || document.querySelector('link[rel=stylesheet]').getAttribute('href').replace(/assets\/style\.css$/, '')) + 'search-index.json';
  var index = null;
  var loading = false;
  var activeIdx = -1;
  var results = [];

  function loadIndex() {
    if (index || loading) return;
    loading = true;
    fetch(INDEX_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; })
      .catch(function () { index = []; });
  }
  input.addEventListener('focus', loadIndex);

  function score(item, q) {
    var t = item.title.toLowerCase();
    var body = item.text.toLowerCase();
    var ti = t.indexOf(q);
    if (ti === 0) return 100;
    if (ti > 0) return 70 - ti;
    // Heading matches rank above plain body matches.
    var headings = item.headings || [];
    for (var h = 0; h < headings.length; h++) {
      if (headings[h].toLowerCase().indexOf(q) >= 0) return 55;
    }
    var bi = body.indexOf(q);
    if (bi >= 0) return 40 - Math.min(bi, 30) / 30 * 10;
    // light fuzzy: all chars in order
    var qi = 0;
    for (var i = 0; i < t.length && qi < q.length; i++) {
      if (t[i] === q[qi]) qi++;
    }
    return qi === q.length ? 10 : -1;
  }

  function snippet(text, q) {
    var i = text.toLowerCase().indexOf(q);
    if (i < 0) return text.slice(0, 100);
    var start = Math.max(0, i - 30);
    return (start > 0 ? '…' : '') + text.slice(start, start + 100) + '…';
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // Escape, then wrap each (case-insensitive) occurrence of the query in <mark>.
  function highlight(text, q) {
    var lower = text.toLowerCase();
    var out = '';
    var from = 0;
    var i;
    while (q && (i = lower.indexOf(q, from)) >= 0) {
      out += escapeHtml(text.slice(from, i));
      out += '<mark>' + escapeHtml(text.slice(i, i + q.length)) + '</mark>';
      from = i + q.length;
    }
    out += escapeHtml(text.slice(from));
    return out;
  }

  function render(q) {
    if (!q) { box.hidden = true; box.innerHTML = ''; return; }
    if (!index) { box.hidden = false; box.innerHTML = '<div class="r-empty">Loading…</div>'; return; }
    results = index
      .map(function (it) { return { it: it, s: score(it, q) }; })
      .filter(function (r) { return r.s > 0; })
      .sort(function (a, b) { return b.s - a.s; })
      .slice(0, 12)
      .map(function (r) { return r.it; });

    activeIdx = -1;
    if (!results.length) {
      box.hidden = false;
      box.innerHTML = '<div class="r-empty">No results</div>';
      return;
    }
    box.innerHTML = results.map(function (it, i) {
      return '<a href="' + it.url + '" data-i="' + i + '">' +
        '<span class="r-title">' + highlight(it.title, q) + '</span>' +
        '<span class="r-snippet">' + highlight(snippet(it.text, q), q) + '</span></a>';
    }).join('');
    box.hidden = false;
  }

  function setActive(i) {
    var links = box.querySelectorAll('a');
    links.forEach(function (l) { l.classList.remove('active'); });
    if (i >= 0 && i < links.length) {
      links[i].classList.add('active');
      links[i].scrollIntoView({ block: 'nearest' });
    }
    activeIdx = i;
  }

  input.addEventListener('input', function () { render(input.value.trim().toLowerCase()); });

  input.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(activeIdx + 1, results.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(activeIdx - 1, 0)); }
    else if (e.key === 'Enter') {
      var target = activeIdx >= 0 ? results[activeIdx] : results[0];
      if (target) window.location.href = target.url;
    } else if (e.key === 'Escape') { box.hidden = true; input.blur(); }
  });

  document.addEventListener('click', function (e) {
    if (!box.contains(e.target) && e.target !== input) box.hidden = true;
  });
})();
