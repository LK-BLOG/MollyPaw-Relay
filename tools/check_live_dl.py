#!/usr/bin/env python3
"""线上验收：打开官网下载区，等测速跑完，把状态和渲染结果打出来 + 截图。

用法：
    python tools/check_live_dl.py
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shot_site import MiniWS, find_browser  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEBUG_PORT = 9229
URL = "https://mollypaw-online.pages.dev/?mode=lite"

STATE_JS = r"""
(function () {
  function q(s) {
    var e = document.querySelector(s);
    return e ? e.textContent.trim().replace(/\s+/g, ' ') : '(无)';
  }
  var b = document.querySelector('.js-download[data-dl="primary"]');
  return {
    ver: q('[data-ver="name"]'),
    date: q('[data-ver="date"]'),
    size: q('[data-ver="size"]'),
    src: q('[data-ver="source"]'),
    route: q('[data-ver="route"]'),
    hint: q('#mirrorHint'),
    btnHref: b ? b.getAttribute('href') : null,
    btnDisabled: b ? b.classList.contains('is-disabled') : null,
    btnText: b ? b.textContent.trim().replace(/\s+/g, ' ') : null,
    mirrors: Array.prototype.map.call(
      document.querySelectorAll('.mirror-row'),
      function (r) { return r.textContent.trim().replace(/\s+/g, ' '); }
    ),
    relCount: document.querySelectorAll('.rel-item').length,
    relFirst: q('.rel-item')
  };
})()
"""


def main() -> int:
    chrome = find_browser()
    profile = tempfile.mkdtemp(prefix="mp-livedl-")
    proc = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--remote-allow-origins=*", "--window-size=1400,900", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(80):
            try:
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2
                ).read()
                for t in json.loads(raw):
                    if t.get("type") == "page":
                        ws_url = t["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            if ws_url:
                break
            time.sleep(0.3)
        if not ws_url:
            print("CDP 没起来")
            return 1

        ws = MiniWS(ws_url)
        ws.call("Page.enable")
        ws.call("Runtime.enable")
        ws.call("Emulation.setEmulatedMedia", {"features": [
            {"name": "prefers-reduced-motion", "value": "no-preference"}
        ]})
        ws.call("Page.navigate", {"url": URL})
        time.sleep(4.0)
        ws.call("Runtime.evaluate", {
            "expression": "document.fonts.ready", "awaitPromise": True
        })

        # 等测速结束（6 条 × 最多 9s 超时 + 错开 120ms，给足 25s）
        for i in range(26):
            st = ws.call("Runtime.evaluate", {
                "expression": STATE_JS, "returnByValue": True
            })["result"]["result"]["value"]
            busy = ("测速中", "待测速", "重试中")
            done = all(not any(b in m for b in busy) for m in st.get("mirrors", []))
            if st.get("mirrors") and done:
                break
            time.sleep(1.0)

        print(json.dumps(st, ensure_ascii=False, indent=2))

        geo = ws.call("Runtime.evaluate", {
            "expression": """(function(){
              var e=document.querySelector('#get'); window.scrollTo(0, e.getBoundingClientRect().top+window.scrollY);
              return {y: Math.round(window.scrollY)};
            })()""",
            "returnByValue": True,
        })["result"]["result"]["value"]
        time.sleep(0.8)
        cap = ws.call("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": 0, "y": 0, "width": 1400, "height": 1500, "scale": 1},
            "captureBeyondViewport": True,
        })
        out = os.path.join("shots", "live-dl.png")
        with open(out, "wb") as fh:
            fh.write(base64.b64decode(cap["result"]["data"]))
        print("saved", out, "scrollY=", geo["y"])
        return 0
    finally:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
