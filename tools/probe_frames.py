#!/usr/bin/env python3
"""连拍：点一下模式切换，把过渡过程逐帧截下来。

用来肉眼验收动画 —— 只看终态是看不出"硬切"和"中间露缝"的。

用法：
    python tools/probe_frames.py --port 8899 --from lite --frames 12
输出：
    shots/frames/frame-00.png ... 以及每帧的时间戳/状态
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

DEBUG_PORT = 9227


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--from", dest="src", default="lite", choices=["lite", "dev"])
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--out", default="shots/frames")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=820)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for f in os.listdir(args.out):
        if f.endswith(".png"):
            os.remove(os.path.join(args.out, f))

    chrome = find_browser()
    profile = tempfile.mkdtemp(prefix="mp-frames-")
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
        # 无头默认 reduced-motion: reduce，会把动画整个关掉
        ws.call("Emulation.setEmulatedMedia", {"features": [
            {"name": "prefers-reduced-motion", "value": "no-preference"}
        ]})
        ws.call("Emulation.setDeviceMetricsOverride", {
            "width": args.width, "height": args.height,
            "deviceScaleFactor": 1, "mobile": False,
        })
        ws.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/?mode={args.src}"})
        time.sleep(2.0)
        ws.call("Runtime.evaluate", {"expression": "document.fonts.ready", "awaitPromise": True})
        time.sleep(0.4)

        info = ws.call("Runtime.evaluate", {
            "expression": """
              (function(){
                var btns = document.querySelectorAll('.ms-btn');
                var b = btns[1];  // 技术版
                var r = b.getBoundingClientRect();
                return {x: r.left + r.width/2, y: r.top + r.height/2,
                        label: b.textContent.trim()};
              })()
            """,
            "returnByValue": True,
        })["result"]["result"]["value"]
        print(f"点击 {info['label']} @ ({info['x']:.0f}, {info['y']:.0f})")

        t0 = time.time()
        # 在同一帧里触发点击，然后立刻开始连拍
        ws.call("Runtime.evaluate", {
            "expression": "document.querySelectorAll('.ms-btn')[1].click()"
        })

        for i in range(args.frames):
            shot = ws.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False
            })
            data = shot["result"]["data"]
            path = os.path.join(args.out, f"frame-{i:02d}.png")
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(data))
            state = ws.call("Runtime.evaluate", {
                "expression": "(document.documentElement.getAttribute('data-mode')||'') + '|' + "
                              "String(!!document.querySelector('::view-transition'))",
                "returnByValue": True,
            })["result"]["result"]["value"]
            print(f"  frame {i:02d}  t={int((time.time()-t0)*1000):4d}ms  mode={state}")
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
