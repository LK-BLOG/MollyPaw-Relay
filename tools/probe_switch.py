#!/usr/bin/env python3
"""验收模式切换动画：把 View Transition 的动画**暂停在指定时刻**再截图。

为什么不用连拍：headless 的 captureScreenshot 一次要三四百毫秒，
等第一张回来动画早跑完了，只能拍到终态。
改成点完立刻 pause()，再手动设 currentTime，就能拿到确定性的中间帧。

用法：
    python tools/probe_switch.py --port 8899
输出：
    shots/switch/00-before.png  切换前（lite）
    1-at-000ms.png       刚开始（圆还没长出来）
    2-at-240ms.png       中途（圆扫过一半）
    3-at-479ms.png       即将铺满
    4-after.png          切换后（dev）
    另外打印 data-mode 与动画数量的采样序列，确认时序没提前切换。
"""
from __future__ import annotations

import argparse
import base64
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
from shot_site import MiniWS, find_browser  # noqa: E402

DEBUG_PORT = 9228

CLICK_AND_FREEZE = r"""
(async function () {
  var btns = document.querySelectorAll('.ms-btn');
  var b = btns[1];                       // 技术版
  var r = b.getBoundingClientRect();
  var clickPt = {x: r.left + r.width / 2, y: r.top + r.height / 2};

  window.__samples = [];
  var t0 = performance.now();
  (function tick() {
    var anims = document.getAnimations();
    var vt = anims.filter(function (a) {
      var pe = (a.effect && a.effect.pseudoElement) || '';
      return pe.indexOf('view-transition-new') >= 0;
    });
    window.__samples.push({
      t: Math.round(performance.now() - t0),
      mode: document.documentElement.getAttribute('data-mode'),
      vtCount: vt.length,
      clip: vt[0] ? (vt[0].effect.getKeyframes()[1] || {}).clipPath : null
    });
    if (performance.now() - t0 < 900) requestAnimationFrame(tick);
  })();

  b.click();

  // View Transition 的动画要等 transition.ready 之后才创建，
  // 所以点完那一刻 getAnimations() 是空的 —— 得等几帧再冻结。
  for (var i = 0; i < 40; i++) {
    var anims2 = document.getAnimations().filter(function (a) {
      var pe = (a.effect && a.effect.pseudoElement) || '';
      return pe.indexOf('view-transition-new') >= 0;
    });
    if (anims2.length) {
      anims2.forEach(function (a) { try { a.pause(); } catch (e) {} });
      return {frozen: anims2.length, click: clickPt, waited: i};
    }
    await new Promise(function (res) { requestAnimationFrame(res); });
  }
  return {frozen: 0, click: clickPt, waited: 40};
})()
"""

SET_TIME = r"""
(function (ms) {
  var n = 0;
  document.getAnimations().forEach(function (a) {
    var pe = (a.effect && a.effect.pseudoElement) || '';
    if (pe.indexOf('view-transition-new') >= 0 && a.playState === 'paused') {
      try { a.currentTime = ms; n++; } catch (e) {}
    }
  });
  return n;
})(%d)
"""


def shot(ws, path):
    res = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(res["result"]["data"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--out", default="shots/switch")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=820)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for f in os.listdir(args.out):
        if f.endswith(".png"):
            os.remove(os.path.join(args.out, f))

    chrome = find_browser()
    profile = tempfile.mkdtemp(prefix="mp-switch-")
    proc = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--remote-allow-origins=*",
            f"--window-size={args.width},{args.height}",
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
        ws.call("Emulation.setEmulatedMedia", {"features": [
            {"name": "prefers-reduced-motion", "value": "no-preference"}
        ]})
        ws.call("Emulation.setDeviceMetricsOverride", {
            "width": args.width, "height": args.height,
            "deviceScaleFactor": 1, "mobile": False,
        })
        ws.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/?mode=lite"})
        time.sleep(2.0)
        ws.call("Runtime.evaluate", {"expression": "document.fonts.ready", "awaitPromise": True})
        time.sleep(0.5)

        ws.call("Runtime.evaluate", {"expression": "window.scrollTo(0,0)"})
        time.sleep(0.3)
        shot(ws, os.path.join(args.out, "00-before.png"))

        ev = ws.call("Runtime.evaluate", {
            "expression": CLICK_AND_FREEZE,
            "returnByValue": True,
            "awaitPromise": True
        })
        info = (ev.get("result", ev).get("result") or ev.get("result", {})).get("value")
        if not isinstance(info, dict):
            print("Runtime.evaluate 返回异常:", json.dumps(ev, ensure_ascii=False)[:800])
            return 1
        print(f"点击点 {info['click']}，冻结动画 {info['frozen']} 个")
        if not info["frozen"]:
            print("!! 一个 view-transition 动画都没冻住 —— 说明浏览器不支持或动画没跑")
            return 1

        for label, ms in (("1-at-000ms", 0), ("2-at-310ms", 310), ("3-at-600ms", 600)):
            n = ws.call("Runtime.evaluate", {
                "expression": SET_TIME % ms, "returnByValue": True
            })["result"]["result"]["value"]
            time.sleep(0.25)
            shot(ws, os.path.join(args.out, label + ".png"))
            print(f"  {label}: 设了 {n} 个动画的 currentTime={ms}")

        # 放开动画，让它自然结束，确认最终落在 dev
        ws.call("Runtime.evaluate", {
            "expression": "document.getAnimations().forEach(function(a){try{a.play()}catch(e){}})"
        })
        time.sleep(1.2)
        shot(ws, os.path.join(args.out, "4-after.png"))

        samples = ws.call("Runtime.evaluate", {
            "expression": "JSON.stringify(window.__samples)", "returnByValue": True
        })["result"]["result"]["value"]
        rows = json.loads(samples)
        first_dev = next((r["t"] for r in rows if r["mode"] == "dev"), None)
        print(f"\n动画采样 {len(rows)} 帧；data-mode 首次变 dev 的时刻：{first_dev}ms")
        print("  （窗口里先 freeze 了，所以这里主要看有没有在动、有没有提前切换）")
        for r in rows[::6][:12]:
            print(f"    t={r['t']:4d}ms mode={r['mode']:4s} vt={r['vtCount']}")
        return 0
    finally:
        try:
            proc.kill()
        except Exception:
            pass


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
