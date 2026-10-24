/* MollyPaw Online — 官网交互（无依赖，纯原生 JS）
 *
 * 干三件事：
 *   1. 小白版 / 技术版切换（存 localStorage，URL 带 ?mode= 优先）
 *   2. 中继健康状态（/api/health）
 *   3. APK 版本信息（GitHub Releases latest）
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var HEALTH_URL = '/api/health';

  /* ---------- 模式：读取 / 应用 / 切换 ---------- */
  var MODES = {
    lite: { name: '小白版' },
    dev: { name: '技术版' }
  };

  /* 模式切换动画：View Transitions API。
     浏览器会给整页拍两张快照（旧主题 / 新主题），我们只让新快照用
     clip-path 的圆从点击位置长出来盖住旧的。

     为什么不用自己造的元素：
       自己铺一个实色 div 当幕布，只有"纯色铺满"这一种可能 ——
       内容、渐变、阴影全被一块色板盖住，看起来就是"硬切 + 一个圆在上面爬"。
       整页快照是真实内容，圆扫过的地方是真的在换主题。 */
  var SWITCH_MS = 620;

  function getMode() {
    var m = root.getAttribute('data-mode');
    return (m === 'dev' || m === 'lite') ? m : 'lite';
  }

  function applyMode(mode, origin) {
    if (!MODES[mode]) mode = 'lite';
    if (getMode() === mode) {
      syncModeUI(mode);
      return;
    }

    function swap() {
      root.setAttribute('data-mode', mode);
      syncModeUI(mode);
      persistMode(mode);
    }

    var reduced = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduced || !origin || typeof document.startViewTransition !== 'function') {
      swap();
      return;
    }

    var transition = document.startViewTransition(swap);
    transition.ready.then(function () {
      var x = origin.x;
      var y = origin.y;
      var r = Math.ceil(Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      ));
      document.documentElement.animate(
        { clipPath: ['circle(0px at ' + x + 'px ' + y + 'px)',
                     'circle(' + r + 'px at ' + x + 'px ' + y + 'px)'] },
        {
          duration: SWITCH_MS,
          easing: 'cubic-bezier(.4, 0, .2, 1)',
          pseudoElement: '::view-transition-new(root)'
        }
      );
    }).catch(function () { /* ready 被中断（又点了一次）—— 主题已经换好了，忽略 */ });
  }

  function persistMode(mode) {
    try {
      localStorage.setItem('mollypaw-mode', mode);
      var url = new URL(location.href);
      url.searchParams.set('mode', mode);
      history.replaceState(null, '', url);
    } catch (e) { /* 无痕模式 / file:// 限制，忽略 */ }
  }

  function syncModeUI(mode) {
    root.setAttribute('data-mode', mode);
    document.querySelectorAll('.ms-btn').forEach(function (b) {
      b.setAttribute('aria-selected', String(b.dataset.mode === mode));
    });
    var mobileLabel = document.querySelector('#modeBtnMobile .ms-label');
    if (mobileLabel) mobileLabel.textContent = MODES[mode].name;
  }

  function bindModeSwitch() {
    document.querySelectorAll('.ms-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var rect = btn.getBoundingClientRect();
        applyMode(btn.dataset.mode, {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        });
      });
    });
    var mobileBtn = document.getElementById('modeBtnMobile');
    if (mobileBtn) {
      mobileBtn.addEventListener('click', function () {
        var rect = mobileBtn.getBoundingClientRect();
        applyMode(getMode() === 'lite' ? 'dev' : 'lite', {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2
        });
      });
    }
  }

  // 首屏脚本已经把 data-mode 设好；这里补齐 UI 状态
  var bootMode = new URLSearchParams(location.search).get('mode');
  applyMode((bootMode === 'dev' || bootMode === 'lite') ? bootMode : getMode());
  bindModeSwitch();

  /* ---------- 导航：滚动阴影 + 移动端菜单 ---------- */
  var nav = document.getElementById('nav');
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle('scrolled', window.scrollY > 12);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  var toggle = document.getElementById('navToggle');
  var links = document.getElementById('navLinks');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    links.addEventListener('click', function (e) {
      if (e.target.closest('a')) {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ---------- 中继状态 ---------- */
  var tag = document.getElementById('relayTag');
  var dot = document.getElementById('relayDot');
  var retry = document.getElementById('relayRetry');

  function setRelay(state, text) {
    if (tag) {
      tag.textContent = text;
      tag.className = 'tag' + (state ? ' ' + state : '');
    }
    if (dot) dot.className = 'dot ' + (state || '');
  }

  function checkRelay() {
    if (!tag) return;
    setRelay('', '检查中…');
    var started = Date.now();
    fetch(HEALTH_URL, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var ms = Date.now() - started;
        if (data && data.ok) {
          setRelay('ok', '在线 · ' + ms + 'ms');
        } else {
          setRelay('bad', '异常');
        }
      })
      .catch(function () {
        setRelay('bad', '不可用');
      });
  }

  if (retry) retry.addEventListener('click', checkRelay);
  checkRelay();

  /* ============================================================
     下载中心：实时版本号 + 国内镜像测速
     逻辑从主官网 mollypaw.pages.dev 搬过来，产品换成 Android APK。
     ============================================================ */
  var APP_REPO = 'LK-BLOG/MollyPaw-Android';
  var RELEASES_API = 'https://api.github.com/repos/' + APP_REPO + '/releases?per_page=10';
  var DESKTOP_URL = 'https://mollypaw.pages.dev/#download';
  var MIRROR_TIMEOUT = 9000;

  // 加速前缀：挂在 https://github.com/... 原地址前面。
  // 顺序 = 优先尝试顺序；实测可达且最快的会排到最前，并接管「主下载按钮」。
  var MIRRORS = [
    { name: 'cdn.gh-proxy.org', label: '线路 A', prefix: 'https://cdn.gh-proxy.org/' },
    { name: 'ghproxy.net', label: '线路 B', prefix: 'https://ghproxy.net/' },
    { name: 'ghfast.top', label: '线路 C', prefix: 'https://ghfast.top/' },
    { name: 'ghfile.geekertao.top', label: '线路 D', prefix: 'https://ghfile.geekertao.top/' },
    { name: 'gh-proxy.com', label: '线路 E', prefix: 'https://gh-proxy.com/' },
    { name: 'gh.llkk.cc', label: '线路 F', prefix: 'https://gh.llkk.cc/' }
  ];

  var relState = { data: null, source: 'none', latest: null, rawUrl: null, isFileUrl: false };

  function tier(ms) {
    if (ms < 400) return '很快';
    if (ms < 1500) return '可用';
    if (ms < 4000) return '偏慢';
    return '很慢';
  }

  function fmtSize(bytes) {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function fmtDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
      '-' + String(d.getDate()).padStart(2, '0');
  }

  function setVer(key, text) {
    document.querySelectorAll('[data-ver="' + key + '"]').forEach(function (el) {
      el.textContent = text;
    });
  }

  // 只认 .apk —— 别的资产（源码 zip、mapping）不是给用户装的
  function mainAsset(rel) {
    if (!rel) return null;
    var list = rel.assets || [];
    for (var i = 0; i < list.length; i++) {
      if (/\.apk$/i.test(list[i].name || '')) return list[i];
    }
    return null;
  }

  function normalize(raw) {
    if (!Array.isArray(raw)) return [];
    return raw
      .filter(function (r) { return !r.draft; })
      .map(function (r) {
        return {
          tag: r.tag_name,
          name: r.name || r.tag_name,
          published: r.published_at,
          prerelease: !!r.prerelease,
          url: r.html_url,
          notes: (r.body || '').trim(),
          assets: (r.assets || []).map(function (a) {
            return {
              name: a.name, size: a.size,
              downloads: a.download_count, url: a.browser_download_url
            };
          })
        };
      });
  }

  function render() {
    var list = relState.data || [];
    var latest = list[0] || null;
    relState.latest = latest;

    if (latest) {
      setVer('name', (latest.name || latest.tag || '').trim() || latest.tag || '未知版本');
      var asset = mainAsset(latest);
      setVer('date', fmtDate(latest.published) ? '发布于 ' + fmtDate(latest.published) : '');
      setVer('size', asset ? fmtSize(asset.size) : '');
    } else {
      setVer('name', '暂无可下载版本');
      setVer('date', '');
      setVer('size', '');
    }

    var rawUrl = null;
    if (latest) {
      var a = mainAsset(latest);
      rawUrl = (a && a.url) || null;
    }
    relState.isFileUrl = !!rawUrl;
    if (!rawUrl) rawUrl = 'https://github.com/' + APP_REPO + '/releases/latest';
    relState.rawUrl = rawUrl;
    updatePrimaryDownload();

    var srcEl = document.querySelector('[data-ver="source"]');
    if (srcEl) {
      srcEl.className = 'ver-src ' + relState.source;
      srcEl.textContent = relState.source === 'live' ? 'GitHub 实时'
        : '拿不到版本信息，请手动去 Release 页';
    }

    var errEl = document.querySelector('[data-ver="error"]');
    if (errEl) {
      if (relState.source === 'none') {
        errEl.hidden = false;
        errEl.textContent = '⚠️ 没能从 GitHub 取到版本信息。可能是还没发版，或者网络/限流。' +
          '稍后点「重新获取」，或者直接去 Release 页看看。';
      } else {
        errEl.hidden = true;
      }
    }

    var routeEl = document.querySelector('[data-ver="route"]');
    if (!routeEl) {
      /* 没有 route 元素就算了 */
    } else if (relState.source === 'none') {
      routeEl.textContent = '还没拿到版本信息 —— 可能这个版本还没发。发版之后这里会自动显示版本号和测速结果。';
    } else if (!relState.isFileUrl) {
      routeEl.textContent = '取到版本了，但这个版本没有挂 APK 资产，所以没有可测速的文件。';
    } else if (!probeState.done) {
      routeEl.textContent = '正在测速，下载按钮会自动指向最快的节点…';
    }

    renderMirrors(rawUrl);
    renderReleases(list);
  }

  function renderReleases(list) {
    var box = document.getElementById('relList');
    if (!box) return;
    if (!list.length) {
      box.innerHTML = '<p class="mirror-loading">没取到版本记录，去 ' +
        '<a href="https://github.com/' + APP_REPO + '/releases" target="_blank" rel="noopener">' +
        'GitHub Releases</a> 看。</p>';
      return;
    }
    box.innerHTML = '';
    list.slice(0, 8).forEach(function (rel, i) {
      var item = document.createElement('div');
      item.className = 'rel-item';

      var head = document.createElement('div');
      head.className = 'rel-item-head';
      var strong = document.createElement('strong');
      strong.textContent = rel.name || rel.tag;
      head.appendChild(strong);
      if (i === 0) {
        var tag = document.createElement('span');
        tag.className = 'rel-tag latest';
        tag.textContent = '最新';
        head.appendChild(tag);
      } else if (rel.prerelease) {
        var pre = document.createElement('span');
        pre.className = 'rel-tag';
        pre.textContent = '预发布';
        head.appendChild(pre);
      }
      var date = document.createElement('span');
      date.className = 'rel-date';
      date.textContent = fmtDate(rel.published);
      head.appendChild(date);
      item.appendChild(head);

      if (rel.assets && rel.assets.length) {
        var assets = document.createElement('div');
        assets.className = 'rel-assets';
        rel.assets.forEach(function (a) {
          var link = document.createElement('a');
          link.className = 'rel-asset';
          link.href = a.url;
          link.target = '_blank';
          link.rel = 'noopener';
          link.textContent = '⬇ ' + a.name + (a.size ? '（' + fmtSize(a.size) + '）' : '');
          assets.appendChild(link);
        });
        item.appendChild(assets);
      }

      var notes = (rel.notes || '').trim();
      if (notes) {
        var p2 = document.createElement('p');
        p2.className = 'rel-notes';
        p2.textContent = notes.length > 900 ? notes.slice(0, 900) + '…' : notes;
        item.appendChild(p2);
      }
      box.appendChild(item);
    });
  }

  var probeState = { pending: 0, results: {}, best: null, done: false };
  var mirrorRendered = false;

  function renderMirrors(rawUrl) {
    var box = document.getElementById('mirrorList');
    if (!box || !rawUrl) return;
    var usable = relState.isFileUrl &&
      /^https:\/\/github\.com\/.+\/releases\/download\//.test(rawUrl);
    if (!usable) {
      box.innerHTML = '<p class="mirror-loading">没拿到下载文件地址，镜像拼不出来。' +
        '稍后点上面的「重新获取」，或者去 <a href="https://github.com/' + APP_REPO +
        '/releases" target="_blank" rel="noopener">Release 页</a> 自己找。</p>';
      return;
    }

    if (!mirrorRendered) {
      box.innerHTML = '';
      MIRRORS.forEach(function (m) {
        var row = document.createElement('div');
        row.className = 'mirror-row';

        var name = document.createElement('span');
        name.className = 'mirror-name';
        name.textContent = m.label + ' · ' + m.name;

        var host = document.createElement('span');
        host.className = 'mirror-host';
        host.textContent = m.prefix;

        var a = document.createElement('a');
        a.className = 'btn btn-outline mirror-go';
        a.textContent = '下载';
        a.target = '_blank';
        a.rel = 'noopener';
        a.setAttribute('aria-disabled', 'true');
        a.classList.add('is-disabled');

        var status = document.createElement('span');
        status.className = 'mirror-status wait';
        status.textContent = '测速中…';

        row.dataset.mirror = m.name;
        row.appendChild(name);
        row.appendChild(host);
        row.appendChild(a);
        row.appendChild(status);
        box.appendChild(row);

        m._row = row;
        m._link = a;
        m._status = status;
      });
      mirrorRendered = true;
    }

    probeState.pending = 0;
    probeState.results = {};
    probeState.best = null;
    probeState.done = false;
    MIRRORS.forEach(function (m) {
      m.ms = undefined;
      m._link.href = m.prefix + rawUrl;
      m._link.textContent = '下载';
      m._link.classList.add('is-disabled');
      m._link.setAttribute('aria-disabled', 'true');
      m._status.className = 'mirror-status wait';
      m._status.textContent = '待测速';
      m._row.classList.remove('best');
    });
    updatePrimaryDownload();
    scheduleProbe(rawUrl, true);
  }

  var probeScheduled = false;
  function scheduleProbe(rawUrl, force) {
    if (probeScheduled && !force) return;
    if (probeScheduled && force) { runProbes(rawUrl); return; }
    probeScheduled = true;
    var start = function () { runProbes(rawUrl); };
    if (window.requestIdleCallback) {
      window.requestIdleCallback(start, { timeout: 2500 });
    } else {
      setTimeout(start, 1200);
    }
  }

  function runProbes(rawUrl) {
    probeState.pending = 0;
    probeState.results = {};
    probeState.best = null;
    probeState.done = false;
    updatePrimaryDownload();
    MIRRORS.forEach(function (m, i) {
      setTimeout(function () {
        m._status.className = 'mirror-status wait';
        m._status.textContent = '测速中…';
        probeState.pending++;
        probe(m, rawUrl);
      }, i * 120);
    });
  }

  function reorderMirrors() {
    var box = document.getElementById('mirrorList');
    if (!box) return;
    var rows = Array.prototype.slice.call(box.children);
    rows.sort(function (a, b) {
      var ra = probeState.results[a.dataset.mirror];
      var rb = probeState.results[b.dataset.mirror];
      if (ra === undefined) ra = Infinity;
      if (rb === undefined) rb = Infinity;
      return ra - rb;
    });
    rows.forEach(function (r) { box.appendChild(r); });
  }

  function probe(m, rawUrl, attempt) {
    attempt = attempt || 1;
    var started = Date.now();
    var done = false;
    var ctrl = null;
    var url = m.prefix + rawUrl;
    m._status.className = 'mirror-status wait';
    m._status.textContent = attempt > 1 ? '重试中…' : '测速中…';

    var finish = function (ok, ms) {
      if (done) return;
      done = true;
      if (!ok && attempt < 2) {
        setTimeout(function () { probe(m, rawUrl, attempt + 1); }, 400);
        return;
      }
      probeState.pending--;
      probeState.results[m.name] = ok ? ms : Infinity;
      m.ms = ok ? ms : Infinity;
      if (ok) {
        m._row.classList.add('best');
        m._status.className = 'mirror-status ok';
        m._status.textContent = tier(ms) + ' · ' + ms + 'ms';
        if (m._link) {
          m._link.classList.remove('is-disabled');
          m._link.removeAttribute('aria-disabled');
        }
      } else {
        m._row.classList.remove('best');
        m._status.className = 'mirror-status bad';
        m._status.textContent = '连不上';
      }
      if (probeState.pending <= 0) onAllProbed();
    };

    var timer = setTimeout(function () {
      if (ctrl) { try { ctrl.abort(); } catch (e) {} }
      finish(false);
    }, MIRROR_TIMEOUT);

    // no-cors 模式下 Range 头会被静默丢弃，等于在后台下整个文件。
    // 所以在「拿到响应头」的瞬间立刻 abort，只保留首包耗时，不浪费流量。
    ctrl = ('AbortController' in window) ? new AbortController() : null;
    try {
      fetch(url, {
        method: 'GET',
        mode: 'no-cors',
        cache: 'no-store',
        signal: ctrl ? ctrl.signal : undefined
      })
        .then(function () {
          var ms = Date.now() - started;
          if (ctrl) { try { ctrl.abort(); } catch (e) {} }
          clearTimeout(timer);
          finish(true, ms);
        })
        .catch(function () { clearTimeout(timer); finish(false); });
    } catch (e) {
      clearTimeout(timer);
      finish(false);
    }
  }

  function onAllProbed() {
    probeState.done = true;
    reorderMirrors();
    var best = null;
    MIRRORS.forEach(function (m) {
      if (m.ms !== undefined && m.ms !== Infinity && (!best || m.ms < best.ms)) best = m;
    });
    probeState.best = best;
    updatePrimaryDownload();
    var route = document.querySelector('[data-ver="route"]');
    if (route) {
      if (best) {
        route.textContent = '已自动选择最快节点：' + best.name +
          '（' + best.ms + 'ms）。按钮点下去就是它。';
      } else {
        route.textContent = '这次测速都没通（这些公益节点经常抽风）。主按钮还是指向 ' +
          MIRRORS[0].name + '，多试几次，或者手动点下面的节点。';
      }
    }
  }

  function lockPrimaryDownload(reason) {
    document.querySelectorAll('.js-download[data-dl="primary"]').forEach(function (el) {
      el.setAttribute('href', '#get');
      el.classList.add('is-disabled');
      el.setAttribute('aria-disabled', 'true');
      var note = el.querySelector('.dl-via');
      if (!note) {
        note = document.createElement('em');
        note.className = 'dl-via';
        el.appendChild(note);
      }
      note.textContent = reason;
      note.classList.add('weak');
    });
  }

  function updatePrimaryDownload() {
    var raw = relState.rawUrl;

    if (!raw || !relState.isFileUrl) {
      // 拿到版本了但没有 .apk 资产 —— 别写"正在获取版本…"，那会让人一直等
      var why = relState.source === 'none' ? '版本没取到，往下滚手动下载'
        : (relState.latest ? '这个版本没挂 APK' : '正在获取版本…');
      lockPrimaryDownload(why);
      return;
    }
    if (!probeState.done) {
      lockPrimaryDownload('正在挑最快的线路…');
      return;
    }

    var isGithub = /^https:\/\/github\.com\//.test(raw);
    var prefix, noteText;
    if (probeState.best) {
      prefix = probeState.best.prefix;
      noteText = '已自动选好线路';
    } else {
      // 所有节点都没测通：指向默认节点，并如实说明；绝不回 GitHub 原地址
      prefix = MIRRORS[0].prefix;
      noteText = '线路不太好，下载慢就换下面的';
    }
    var chosen = (prefix && isGithub) ? (prefix + raw) : raw;
    document.querySelectorAll('.js-download[data-dl="primary"]').forEach(function (el) {
      el.setAttribute('href', chosen);
      el.setAttribute('rel', 'noopener');
      el.classList.remove('is-disabled');
      el.removeAttribute('aria-disabled');
      var note = el.querySelector('.dl-via');
      if (!note) {
        note = document.createElement('em');
        note.className = 'dl-via';
        el.appendChild(note);
      }
      note.textContent = noteText;
      note.classList.toggle('weak', !probeState.best);
    });
  }

  function loadReleases(force) {
    if (relState.data && !force) { render(); return; }
    setVer('source', '正在连 GitHub…');
    fetch(RELEASES_API, {
      headers: { Accept: 'application/vnd.github+json' },
      cache: 'no-store'
    })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (raw) {
        var list = normalize(raw);
        if (!list.length) throw new Error('empty');
        relState.data = list;
        relState.source = 'live';
        render();
      })
      .catch(function () {
        relState.data = [];
        relState.source = 'none';
        render();
      });
  }

  function bindDownload() {
    var btn = document.getElementById('verRefresh');
    if (btn) btn.addEventListener('click', function () { loadReleases(true); });

    // 桌面端按钮直接跳主官网下载区（那边发的是 exe）
    var desk = document.querySelector('.js-download[data-dl="desktop"]');
    if (desk) {
      desk.setAttribute('href', DESKTOP_URL);
      desk.classList.remove('is-disabled');
      desk.removeAttribute('aria-disabled');
    }

    // 禁用状态的下载链接一律拦截，别把用户丢到 GitHub 英文页
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('.is-disabled');
      if (!a) return;
      e.preventDefault();
      e.stopPropagation();
      var route = document.querySelector('[data-ver="route"]');
      if (route) {
        route.textContent = relState.rawUrl
          ? '线路还在挑，稍等一下～ 急的话往下滚，手动挑一个节点'
          : '版本还没拿到，稍等一下～ 或者滚到下面手动下载';
      }
    }, true);

    loadReleases(false);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && relState.source !== 'live') loadReleases(true);
    });
  }

  bindDownload();

  /* ---------- 平滑滚动（尊重 prefers-reduced-motion） ---------- */
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduced) {
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var id = a.getAttribute('href');
        if (id === '#') return;
        var el = document.querySelector(id);
        if (!el) return;
        e.preventDefault();
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', id);
      });
    });
  }

  /* ---------- 页脚年份 ---------- */
  var yr = document.getElementById('year');
  if (yr) yr.textContent = String(new Date().getFullYear());
})();
