"""Client-side chart engine and motion, as strings.

Served inline for the same reason there is no CSS framework here: a local tool
does not earn a build step, and inlining means one request and no cache to bust.

The charts are progressive. The server renders the numbers as a real table and
hands the JS a JSON payload; the JS replaces the table with an animated SVG. Turn
JavaScript off and the page is still a set of readable tables, which is also the
accessible view -- no value is ever reachable only by hovering.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- js

SITE_JS = r"""
(function () {
  'use strict';

  var BLUE = '#4169e1';
  var RED  = '#c8102e';
  var GRID = 'rgba(255,255,255,.10)';
  var SVGNS = 'http://www.w3.org/2000/svg';

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function el(name, attrs) {
    var node = document.createElementNS(SVGNS, name);
    for (var key in attrs) {
      if (attrs[key] !== null && attrs[key] !== undefined) {
        node.setAttribute(key, attrs[key]);
      }
    }
    return node;
  }

  function fmt(n) {
    if (Math.abs(n) >= 10000) {
      return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    }
    return (Math.round(n * 10) / 10).toLocaleString();
  }

  function niceMax(v) {
    if (v <= 0) return 1;
    var steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500,
                 1000, 2000, 2500, 5000, 10000, 20000, 50000, 100000];
    for (var i = 0; i < steps.length; i++) {
      if (v <= steps[i]) return steps[i];
    }
    return Math.ceil(v * 1.1);
  }

  // ---------------------------------------------------------------- tooltip
  var tip = null;
  function showTip(html, x, y) {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'tip';
      document.body.appendChild(tip);
    }
    tip.innerHTML = html;
    tip.classList.add('on');
    var box = tip.getBoundingClientRect();
    var left = x + 14;
    if (left + box.width > window.innerWidth - 12) left = x - box.width - 14;
    tip.style.left = left + 'px';
    tip.style.top = (y - box.height - 12) + 'px';
  }
  function hideTip() { if (tip) tip.classList.remove('on'); }

  // A defs block per chart, so the gradient id cannot collide across charts.
  var gradSeq = 0;
  function gradient(svg, colour, vertical) {
    var id = 'g' + (++gradSeq);
    var defs = el('defs', {});
    var lg = el('linearGradient', {
      id: id, x1: '0', y1: '0',
      x2: vertical ? '0' : '1', y2: vertical ? '1' : '0'
    });
    lg.appendChild(el('stop', { offset: '0%',   'stop-color': colour, 'stop-opacity': '1' }));
    lg.appendChild(el('stop', { offset: '100%', 'stop-color': colour, 'stop-opacity': '.55' }));
    defs.appendChild(lg);
    svg.appendChild(defs);
    return 'url(#' + id + ')';
  }

  function axis(svg, x1, x2, y, value) {
    svg.appendChild(el('line', {
      x1: x1, y1: y, x2: x2, y2: y, stroke: GRID, 'stroke-width': 1
    }));
    var text = el('text', { x: x1 - 10, y: y + 3.5, 'text-anchor': 'end', 'class': 'tick' });
    text.textContent = fmt(value);
    svg.appendChild(text);
  }

  // ---------------------------------------------------------------- columns
  function columns(host, data) {
    var W = host.clientWidth || 900, H = 210;
    var padL = 52, padR = 14, padT = 16, padB = 34;
    var pw = W - padL - padR, ph = H - padT - padB;
    var top = niceMax(Math.max.apply(null, data.rows.map(function (r) { return r[1]; })));
    var slot = pw / data.rows.length;
    var bw = Math.min(26, slot - 8);

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'plot', role: 'img',
                          'aria-label': data.title || '' });
    var fill = gradient(svg, BLUE, true);
    for (var t = 0; t <= 2; t++) axis(svg, padL, W - padR, padT + ph - ph * t / 2, top * t / 2);

    data.rows.forEach(function (row, i) {
      var h = top ? ph * (row[1] / top) : 0;
      var x = padL + slot * i + (slot - bw) / 2;
      var y = padT + ph - h;

      if (row[1] > 0) {
        var rect = el('rect', {
          x: x, y: y, width: bw, height: Math.max(h, 2),
          rx: Math.min(4, bw / 2), fill: fill, 'class': 'mark'
        });
        if (!reduceMotion) {
          // Grow from the baseline: scale about the bottom edge.
          rect.style.transformOrigin = (x + bw / 2) + 'px ' + (padT + ph) + 'px';
          rect.style.transform = 'scaleY(0)';
          rect.style.transition = 'transform .62s cubic-bezier(.22,.9,.3,1) ' + (i * 40) + 'ms';
        }
        svg.appendChild(rect);
      }
      // Hit target spans the whole slot, so the pointer never has to find a
      // 2px-tall bar.
      var hit = el('rect', {
        x: padL + slot * i, y: padT, width: slot, height: ph, fill: 'transparent',
        'class': 'hit'
      });
      hit.addEventListener('mousemove', function (e) {
        showTip('<b>' + fmt(row[1]) + '</b><span>' + row[0] + (data.unit || '') + '</span>',
                e.clientX, e.clientY);
      });
      hit.addEventListener('mouseleave', hideTip);
      svg.appendChild(hit);

      var label = el('text', {
        x: padL + slot * i + slot / 2, y: H - 12, 'text-anchor': 'middle', 'class': 'tick'
      });
      label.textContent = row[0];
      svg.appendChild(label);
    });

    host.appendChild(svg);
    return function () {
      svg.querySelectorAll('.mark').forEach(function (m) { m.style.transform = 'scaleY(1)'; });
    };
  }

  // ---------------------------------------------------------------- bars
  function bars(host, data) {
    var W = host.clientWidth || 900;
    var rowH = 42, labelW = Math.min(210, Math.max(120, W * 0.2)), valueW = 64;
    var H = rowH * data.rows.length + 10;
    var track = W - labelW - valueW - 16;
    var top = niceMax(Math.max.apply(null, data.rows.map(function (r) { return r[1]; })));
    var bh = 16;

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'plot', role: 'img',
                          'aria-label': data.title || '' });
    var fill = gradient(svg, data.tone === 'red' ? RED : BLUE, false);

    data.rows.forEach(function (row, i) {
      var y = i * rowH + 6;
      var w = top ? track * (row[1] / top) : 0;
      var mid = y + bh / 2;

      var name = el('text', { x: 0, y: mid + 4, 'class': 'cat' });
      name.textContent = row[0];
      svg.appendChild(name);

      svg.appendChild(el('rect', {
        x: labelW, y: y, width: track, height: bh, rx: 3, fill: 'rgba(255,255,255,.045)'
      }));

      if (row[1] > 0) {
        var bar = el('rect', {
          x: labelW, y: y, width: Math.max(w, 3), height: bh, rx: 3,
          fill: fill, 'class': 'mark'
        });
        if (!reduceMotion) {
          bar.style.transformOrigin = labelW + 'px 0';
          bar.style.transform = 'scaleX(0)';
          bar.style.transition = 'transform .66s cubic-bezier(.22,.9,.3,1) ' + (i * 55) + 'ms';
        }
        svg.appendChild(bar);
      }

      var value = el('text', { x: labelW + track + 12, y: mid + 4, 'class': 'val' });
      value.textContent = fmt(row[1]);
      svg.appendChild(value);

      var hit = el('rect', {
        x: 0, y: y - 6, width: W, height: rowH, fill: 'transparent', 'class': 'hit'
      });
      hit.addEventListener('mousemove', function (e) {
        showTip('<b>' + fmt(row[1]) + '</b><span>' + row[0] + '</span>', e.clientX, e.clientY);
      });
      hit.addEventListener('mouseleave', hideTip);
      svg.appendChild(hit);
    });

    host.appendChild(svg);
    return function () {
      svg.querySelectorAll('.mark').forEach(function (m) { m.style.transform = 'scaleX(1)'; });
    };
  }

  // ---------------------------------------------------------------- line
  function line(host, data) {
    var W = host.clientWidth || 900, H = 230;
    var padL = 52, padR = 54, padT = 18, padB = 34;
    var pw = W - padL - padR, ph = H - padT - padB;
    var top = niceMax(Math.max.apply(null, data.rows.map(function (r) { return r[1]; })));
    var step = pw / Math.max(1, data.rows.length - 1);

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'plot', role: 'img',
                          'aria-label': data.title || '' });
    for (var t = 0; t <= 2; t++) axis(svg, padL, W - padR, padT + ph - ph * t / 2, top * t / 2);

    var pts = data.rows.map(function (r, i) {
      return [padL + step * i, padT + ph - (top ? ph * (r[1] / top) : 0)];
    });

    var area = 'M ' + pts[0][0] + ' ' + (padT + ph) + ' ' +
      pts.map(function (p) { return 'L ' + p[0] + ' ' + p[1]; }).join(' ') +
      ' L ' + pts[pts.length - 1][0] + ' ' + (padT + ph) + ' Z';
    var wash = el('path', { d: area, fill: BLUE, 'fill-opacity': '.10', 'class': 'wash' });
    svg.appendChild(wash);

    var path = el('path', {
      d: 'M ' + pts.map(function (p) { return p[0] + ' ' + p[1]; }).join(' L '),
      fill: 'none', stroke: BLUE, 'stroke-width': 2,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round'
    });
    svg.appendChild(path);

    var dot = el('circle', { cx: pts[pts.length - 1][0], cy: pts[pts.length - 1][1],
                             r: 4.5, fill: BLUE, stroke: '#000', 'stroke-width': 2 });
    svg.appendChild(dot);

    var cross = el('line', { y1: padT, y2: padT + ph, stroke: 'rgba(255,255,255,.28)',
                             'stroke-width': 1, opacity: 0 });
    svg.appendChild(cross);

    pts.forEach(function (p, i) {
      var hit = el('rect', {
        x: p[0] - step / 2, y: padT, width: step, height: ph, fill: 'transparent', 'class': 'hit'
      });
      hit.addEventListener('mousemove', function (e) {
        cross.setAttribute('x1', p[0]);
        cross.setAttribute('x2', p[0]);
        cross.setAttribute('opacity', 1);
        showTip('<b>' + fmt(data.rows[i][1]) + '</b><span>' + data.rows[i][0] + '</span>',
                e.clientX, e.clientY);
      });
      hit.addEventListener('mouseleave', function () {
        cross.setAttribute('opacity', 0);
        hideTip();
      });
      svg.appendChild(hit);
    });

    [0, data.rows.length - 1].forEach(function (i) {
      var t = el('text', {
        x: pts[i][0], y: H - 12,
        'text-anchor': i === 0 ? 'start' : 'end', 'class': 'tick'
      });
      t.textContent = data.rows[i][0];
      svg.appendChild(t);
    });

    host.appendChild(svg);

    var length = path.getTotalLength ? path.getTotalLength() : 0;
    if (!reduceMotion && length) {
      path.style.strokeDasharray = length;
      path.style.strokeDashoffset = length;
      path.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.3,.8,.3,1)';
      wash.style.opacity = 0;
      wash.style.transition = 'opacity .8s ease .35s';
      dot.style.opacity = 0;
      dot.style.transition = 'opacity .3s ease .95s';
    }
    return function () {
      path.style.strokeDashoffset = 0;
      wash.style.opacity = 1;
      dot.style.opacity = 1;
    };
  }

  // ---------------------------------------------------------------- split
  function split(host, data) {
    var W = host.clientWidth || 900, H = 74, bh = 26;
    var total = data.rows.reduce(function (a, r) { return a + r[1]; }, 0);
    if (!total) return function () {};
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'plot', role: 'img',
                          'aria-label': data.title || '' });
    var lw = W * (data.rows[0][1] / total);
    var parts = [
      { x: 0, w: lw - 1, colour: BLUE, row: data.rows[0] },
      { x: lw + 1, w: W - lw - 1, colour: RED, row: data.rows[1] }
    ];
    parts.forEach(function (p, i) {
      if (p.w <= 0) return;
      var rect = el('rect', { x: p.x, y: 0, width: p.w, height: bh, rx: 3,
                              fill: p.colour, 'class': 'mark' });
      if (!reduceMotion) {
        rect.style.transformOrigin = (i === 0 ? '0' : W + 'px') + ' 0';
        rect.style.transform = 'scaleX(0)';
        rect.style.transition = 'transform .7s cubic-bezier(.22,.9,.3,1) ' + (i * 90) + 'ms';
      }
      rect.addEventListener('mousemove', function (e) {
        showTip('<b>' + fmt(p.row[1]) + '</b><span>' + p.row[0] + '</span>', e.clientX, e.clientY);
      });
      rect.addEventListener('mouseleave', hideTip);
      svg.appendChild(rect);

      var sw = el('rect', { x: i * 190, y: bh + 22, width: 9, height: 9, rx: 2, fill: p.colour });
      svg.appendChild(sw);
      var label = el('text', { x: i * 190 + 16, y: bh + 31, 'class': 'cat' });
      label.textContent = p.row[0] + '  ' + fmt(p.row[1]);
      svg.appendChild(label);
    });
    host.appendChild(svg);
    return function () {
      svg.querySelectorAll('.mark').forEach(function (m) { m.style.transform = 'scaleX(1)'; });
    };
  }

  var KINDS = { columns: columns, bars: bars, line: line, split: split };

  // ---------------------------------------------------------------- boot
  function draw(host) {
    var data;
    try { data = JSON.parse(host.getAttribute('data-chart')); } catch (e) { return; }
    if (!data || !data.rows || !data.rows.length) return;
    var build = KINDS[data.kind];
    if (!build) return;
    host.innerHTML = '';
    var play = build(host, data);
    host.classList.add('ready');
    return play;
  }

  function boot() {
    var hosts = [].slice.call(document.querySelectorAll('[data-chart]'));
    if (!hosts.length) return;

    hosts.forEach(function (host) {
      var play = draw(host);
      if (!play) return;
      if (reduceMotion || !window.IntersectionObserver) { play(); return; }
      var seen = false;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !seen) {
            seen = true;
            requestAnimationFrame(play);
            io.disconnect();
          }
        });
      }, { threshold: 0.2 });
      io.observe(host);
    });

    var resizeTimer;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        hosts.forEach(function (host) {
          var play = draw(host);
          if (play) play();
        });
      }, 180);
    });
  }

  // ---------------------------------------------------------------- motion
  function reveal() {
    if (reduceMotion || !window.IntersectionObserver) {
      document.querySelectorAll('.rise').forEach(function (n) { n.classList.add('in'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.rise').forEach(function (n) { io.observe(n); });
  }

  function countUp() {
    var nodes = [].slice.call(document.querySelectorAll('[data-count]'));
    if (!nodes.length) return;
    nodes.forEach(function (node) {
      var target = parseFloat(node.getAttribute('data-count'));
      var suffix = node.getAttribute('data-suffix') || '';
      var decimals = (node.getAttribute('data-count').split('.')[1] || '').length;
      if (reduceMotion || !isFinite(target)) { return; }
      var started = false;
      function run() {
        if (started) return;
        started = true;
        var t0 = performance.now(), dur = 900;
        function tick(now) {
          var k = Math.min(1, (now - t0) / dur);
          var eased = 1 - Math.pow(1 - k, 3);
          var value = target * eased;
          node.textContent = (decimals
            ? value.toFixed(decimals)
            : Math.round(value).toLocaleString()) + suffix;
          if (k < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      }
      if (!window.IntersectionObserver) { run(); return; }
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { run(); io.disconnect(); }
        });
      }, { threshold: 0.5 });
      io.observe(node);
    });
  }

  // ---------------------------------------------------------------- filter
  // The jobs table is long; let it be searched without a round trip.
  function tableFilter() {
    var input = document.getElementById('table-filter');
    if (!input) return;
    var rows = [].slice.call(document.querySelectorAll('[data-filterable] tbody tr'));
    var note = document.getElementById('filter-count');
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
        row.style.display = hit ? '' : 'none';
        if (hit) shown++;
      });
      if (note) note.textContent = shown + ' of ' + rows.length;
    });
  }

  function start() { boot(); reveal(); countUp(); tableFilter(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
"""


def _sha256_of(script: str) -> str:
    """The CSP hash for the inline script.

    The script is static, so a hash beats a nonce here: it needs no per-request
    state and still lets the policy refuse every *other* inline script. Computed
    from the same string the page emits, so the two cannot drift.
    """
    import base64
    import hashlib

    digest = hashlib.sha256(script.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


SITE_JS_HASH = _sha256_of(SITE_JS)
