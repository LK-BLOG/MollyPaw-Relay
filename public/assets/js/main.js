/* MollyPaw Online — 官网交互（无依赖，纯原生 JS）
 *
 * 干三件事：
 *   1. 小白版 / 技术版切换（存 localStorage，URL 带 ?mode= 优先）
 *   2. 中继健康状态（/api/health）
 *   3. APK 版本信息（/download/manifest.json）
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var HEALTH_URL = '/api/health';
  var APK_MANIFEST = '/download/manifest.json';

  /* ---------- 模式：读取 / 应用 / 切换 ---------- */
  var MODES = {
    lite: { name: '小白版' },
    dev: { name: '技术版' }
  };

  /* 两种模式各自的主题色 —— 圆形扩散时用目标模式的主题色填 */
  var MODE_THEME = { lite: '#FFF8F0', dev: '#1C1310' };

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

    var reduced = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var target = MODE_THEME[mode] || '#000';

    if (reduced || !origin) {
      // 用户关了动画，或者没有来源坐标 —— 直接切
      root.setAttribute('data-mode', mode);
      syncModeUI(mode);
      persistMode(mode);
      return;
    }

    // 圆形扩散：从点击点长出一圈目标模式的主题色
    var r = Math.ceil(Math.hypot(
      Math.max(origin.x, window.innerWidth - origin.x),
      Math.max(origin.y, window.innerHeight - origin.y)
    ));
    var rip = document.createElement('div');
    rip.className = 'mode-ripple';
    rip.style.width = rip.style.height = (r * 2) + 'px';
    rip.style.left = (origin.x - r) + 'px';
    rip.style.top = (origin.y - r) + 'px';
    rip.style.background = target;
    document.body.appendChild(rip);

    // 先让它有一帧在 scale(0)，否则浏览器会直接跳到终态
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        rip.classList.add('grow');
      });
    });

    // 扩散到一半时换主题色，让新配色从圆心开始显现
    setTimeout(function () {
      root.setAttribute('data-mode', mode);
      syncModeUI(mode);
    }, 300);

    // 扩散完淡出圆形
    setTimeout(function () {
      rip.classList.add('fade');
      setTimeout(function () {
        if (rip.parentNode) rip.parentNode.removeChild(rip);
      }, 260);
    }, 620);

    persistMode(mode);
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

  /* ---------- APK 版本信息 ---------- */
  var apkMeta = document.getElementById('apkMeta');
  var apkBtn = document.getElementById('apkBtn');

  if (apkMeta) {
    fetch(APK_MANIFEST, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('no manifest');
        return r.json();
      })
      .then(function (m) {
        var parts = [];
        if (m.version) parts.push('v' + m.version);
        if (m.size) parts.push((m.size / 1048576).toFixed(1) + ' MB');
        if (m.built_at) parts.push(String(m.built_at).slice(0, 10));
        apkMeta.textContent = parts.length ? parts.join(' · ') : '准备好了';
        if (apkBtn && m.file) apkBtn.setAttribute('href', '/download/' + m.file);
      })
      .catch(function () {
        apkMeta.textContent = '安装包还在路上，稍后再来。';
      });
  }

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
