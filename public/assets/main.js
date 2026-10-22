/* MollyPaw Online — 官网交互（无依赖，纯原生 JS） */
(function () {
  'use strict';

  var RELAY_HOST = 'mollypaw-online.pages.dev';
  var HEALTH_URL = '/api/health';
  var APK_MANIFEST = '/download/manifest.json';

  /* ---------- 中继状态 ---------- */
  var tag = document.getElementById('relayTag');
  var retry = document.getElementById('relayRetry');

  function setTag(state, text) {
    if (!tag) return;
    tag.textContent = text;
    tag.className = 'tag' + (state ? ' ' + state : '');
  }

  function checkRelay() {
    if (!tag) return;
    setTag('', '检查中…');
    var started = Date.now();
    fetch(HEALTH_URL, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var ms = Date.now() - started;
        if (data && data.ok) {
          setTag('ok', '在线 · ' + ms + 'ms');
        } else {
          setTag('bad', '异常');
        }
      })
      .catch(function () {
        setTag('bad', '不可用');
      });
  }

  if (retry) retry.addEventListener('click', checkRelay);
  checkRelay();

  // 中继状态别一直打接口，进页面查一次就够；再点按钮手动重查。

  /* ---------- APK 版本信息 ---------- */
  var apkMeta = document.getElementById('apkMeta');
  var apkBtn = document.getElementById('apkBtn');

  fetch(APK_MANIFEST, { cache: 'no-store' })
    .then(function (r) {
      if (!r.ok) throw new Error('no manifest');
      return r.json();
    })
    .then(function (m) {
      if (apkMeta) {
        var parts = [];
        if (m.version) parts.push('v' + m.version);
        if (m.size) parts.push((m.size / 1048576).toFixed(1) + ' MB');
        if (m.built_at) parts.push(m.built_at.slice(0, 10));
        apkMeta.textContent = parts.length ? parts.join(' · ') : '准备好了';
      }
      if (apkBtn && m.file) apkBtn.setAttribute('href', '/download/' + m.file);
    })
    .catch(function () {
      if (apkMeta) apkMeta.textContent = '安装包还在路上，稍后再来。';
    });

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
