#!/usr/bin/env python3
"""在真实渲染的页面上做无障碍审计（两种模式各跑一遍）。

查三件事：
  1. 每个有文字的元素，文字色 vs 实际背景色 的对比度 < 4.5 就报出来
     （逐级向上找第一个不透明的背景色）。
  2. 横向溢出（scrollWidth > clientWidth）的元素。
  3. 是否有冷色（蓝/绿/灰）出现在文字或大块背景上。

用法：
    python tools/audit_page.py --port 8899
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shot_site import MiniWS  # noqa: E402

DEBUG_PORT = 9226

AUDIT_JS = r"""
(function () {
  function parseColor(s) {
    var m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(',').map(function (x) { return parseFloat(x); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function lum(c) {
    function f(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function ratio(a, b) {
    var l1 = lum(a), l2 = lum(b);
    if (l1 < l2) { var t = l1; l1 = l2; l2 = t; }
    return (l1 + 0.05) / (l2 + 0.05);
  }
  function blend(fg, bg) {
    var a = fg.a;
    return {
      r: fg.r * a + bg.r * (1 - a),
      g: fg.g * a + bg.g * (1 - a),
      b: fg.b * a + bg.b * (1 - a),
      a: 1
    };
  }
  function effectiveBg(el) {
    var cur = el;
    while (cur) {
      var st = getComputedStyle(cur);
      var bg = parseColor(st.backgroundColor);
      if (bg && bg.a > 0.05) {
        var acc = bg;
        // 往上叠加更远的半透明背景
        var up = cur.parentElement;
        while (bg.a < 0.99 && up) {
          var st2 = getComputedStyle(up);
          var bg2 = parseColor(st2.backgroundColor);
          if (bg2 && bg2.a > 0.05) { acc = blend(acc, bg2); bg = bg2; }
          up = up.parentElement;
        }
        return acc;
      }
      cur = cur.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  }
  function isCold(c) {
    // 冷色判定：蓝/绿明显高于红
    return (c.b > c.r + 18) || (c.g > c.r + 22);
  }
  function label(el) {
    var t = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32);
    return el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).join('.') : '') + (t ? ' | ' + t : '');
  }

  var bad = [], cold = [];
  var all = document.body.querySelectorAll('*');
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity) < 0.1) continue;
    var r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;

    // --- 溢出 ---
    if (el.scrollWidth > el.clientWidth + 2 && st.overflowX !== 'auto' && st.overflowX !== 'scroll') {
      if (el === document.body || el === document.documentElement) {
        bad.push({ kind: 'overflow', el: label(el),
                   detail: el.scrollWidth + ' > ' + el.clientWidth });
      }
    }

    // --- 文字对比度 ---
    // 装饰性元素（图标/emoji）不算文字，不看对比度
    if (el.closest('[aria-hidden="true"]') || el.classList.contains('brand-paw')) continue;
    // 祖先里有渐变背景 —— backgroundColor 是透明的，算出来一定是白底，属于误报
    var gradAnc = false, up0 = el;
    while (up0) {
      var bi = getComputedStyle(up0).backgroundImage;
      if (bi && bi !== 'none' && bi.indexOf('gradient') >= 0) { gradAnc = true; break; }
      up0 = up0.parentElement;
    }
    if (gradAnc) continue;
    // 模式开关的滑块是 .ms-btn 的绝对定位兄弟节点，DOM 上查不到它压在文字下面
    if (el.closest('.mode-switch')) continue;
    var hasText = false;
    for (var c = 0; c < el.childNodes.length; c++) {
      var n = el.childNodes[c];
      if (n.nodeType === 3 && n.textContent.trim().length > 0) { hasText = true; break; }
    }
    if (!hasText) continue;
    var fg = parseColor(st.color);
    if (!fg) continue;
    var bg = effectiveBg(el);
    var fgc = fg.a < 0.99 ? blend(fg, bg) : fg;
    var cr = ratio(fgc, bg);
    var size = parseFloat(st.fontSize);
    var bold = parseInt(st.fontWeight, 10) >= 700;
    var large = size >= 24 || (bold && size >= 18.66);
    var need = large ? 3.0 : 4.5;
    if (cr < need) {
      bad.push({ kind: 'contrast', el: label(el),
                 ratio: Math.round(cr * 100) / 100, need: need,
                 fg: st.color, bg: 'rgb(' + Math.round(bg.r) + ',' + Math.round(bg.g) + ',' + Math.round(bg.b) + ')' });
    }
    if (isCold(fgc) && size >= 12) cold.push({ el: label(el), color: st.color });
  }

  return {
    mode: document.documentElement.getAttribute('data-mode'),
    docH: document.body.scrollHeight,
    bodyOverflow: document.body.scrollWidth > document.body.clientWidth,
    bad: bad.slice(0, 60),
    cold: cold.slice(0, 20)
  };
})()
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--chrome", default=None)
    args = ap.parse_args()

    chrome = args.chrome or _find_chrome()
    if not chrome:
        print("找不到 Chrome/Edge")
        return 2

    profile = tempfile.mkdtemp(prefix="mp-audit-")
    proc = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--remote-allow-origins=*",
            "--window-size=1385,900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        target = _wait_target()
        ws = MiniWS(target)
        ws.call("Page.enable")
        ws.call("Runtime.enable")

        rc = 0
        for mode in ("lite", "dev"):
            ws.call("Emulation.setEmulatedMedia", {"features": [
                {"name": "prefers-reduced-motion", "value": "no-preference"}
            ]})
            url = f"http://127.0.0.1:{args.port}/?mode={mode}"
            ws.call("Page.navigate", {"url": url})
            time.sleep(2.2)
            # 等字体/图片
            ws.call("Runtime.evaluate", {"expression": "document.fonts.ready", "awaitPromise": True})
            time.sleep(0.6)
            res = ws.call("Runtime.evaluate", {
                "expression": AUDIT_JS, "returnByValue": True, "awaitPromise": False
            })
            data = res.get("result", {}).get("result", {}).get("value") or {}
            print(f"\n================ {mode} ================")
            print(f"data-mode={data.get('mode')}  body 高={data.get('docH')}px  "
                  f"横向溢出={'是' if data.get('bodyOverflow') else '否'}")
            bad = data.get("bad") or []
            if not bad:
                print("  对比度/溢出：全部通过")
            for b in bad:
                if b["kind"] == "contrast":
                    print(f"  [对比度 {b['ratio']}:1 < {b['need']}] {b['el']}")
                    print(f"        文字 {b['fg']} / 背景 {b['bg']}")
                else:
                    print(f"  [横向溢出 {b['detail']}] {b['el']}")
                rc = 1
            cold = data.get("cold") or []
            if cold:
                print(f"  [冷色文字 {len(cold)} 处]")
                for c in cold:
                    print(f"        {c['el']} -> {c['color']}")
                rc = 1
        return rc
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def _find_chrome():
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def _wait_target(timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = urllib.request.urlopen(
                f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2
            ).read()
            for t in json.loads(raw):
                if t.get("type") == "page":
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("CDP 没起来")


if __name__ == "__main__":
    sys.exit(main())

