import io

p = r"D:\MollyPaw-Relay\public\assets\js\main.js"
s = io.open(p, encoding="utf-8").read()

old_start = s.index("  function applyMode(mode) {")
old_end = s.index("  function bindModeSwitch() {")

new = '''  function applyMode(mode, origin) {
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

'''

s = s[:old_start] + new + s[old_end:]

bs = s.index("  function bindModeSwitch() {")
be = s.index("  // 首屏脚本已经把 data-mode 设好")
newbind = '''  function bindModeSwitch() {
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

'''
s = s[:bs] + newbind + s[be:]

anchor = "  function getMode() {"
theme = (
    "  /* 两种模式各自的主题色 —— 圆形扩散时用目标模式的主题色填 */\n"
    "  var MODE_THEME = { lite: '#FFF8F0', dev: '#1C1310' };\n\n"
)
s = s.replace(anchor, theme + anchor, 1)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
