#!/usr/bin/env python3
"""实测：点模式切换按钮，采样幕布透明度与 data-mode，确认动画真的在跑。

用法：
    python tools/probe_anim.py --port 8899
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
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

DEBUG_PORT = 9225


class MiniWS:
    def __init__(self, url, timeout=30):
        import websocket
        self.ws = websocket.create_connection(
            url, timeout=timeout, origin="http://127.0.0.1", suppress_origin=False
        )
        self._id = 0

    def call(self, method, params=None, timeout=30):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.ws.settimeout(max(0.5, deadline - time.time()))
                raw = self.ws.recv()
            except Exception as exc:
                raise TimeoutError(f"{method}: {exc}") from exc
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("id") == mid:
                return data
        raise TimeoutError(f"{method} 超时")

    def eval(self, expr, timeout=20):
        res = self.call("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True
        }, timeout=timeout)
        return res.get("result", {}).get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def find_browser():
    for p in (
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ):
        if p and os.path.isfile(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def wait_port(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(0.3)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args()

    browser = find_browser()
    if not browser:
        print("找不到浏览器")
        return 1
    profile = tempfile.mkdtemp(prefix="probe-")
    proc = subprocess.Popen([
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-proxy-server", "--disable-extensions",
        # headless 默认 prefers-reduced-motion: reduce，会把站点动画全关掉
        "--force-prefers-reduced-motion=no-preference",
        f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*",
        f"--user-data-dir={profile}", "--window-size=1400,1000", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_port(DEBUG_PORT):
        proc.kill()
        return 1
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=5) as r:
        targets = json.loads(r.read().decode())
    page = next(t for t in targets if t.get("type") == "page")
    ws = MiniWS(page["webSocketDebuggerUrl"])
    try:
        ws.call("Page.enable")
        # headless 默认 prefers-reduced-motion: reduce，命令行参数不生效，
        # 必须用 CDP 的 Emulation.setEmulatedMedia 强制改掉
        ws.call("Emulation.setEmulatedMedia", {
            "features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]
        })
        ws.call("Runtime.enable")
        ws.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/"})
        time.sleep(3)

        print("reduced-motion:", ws.eval(
            "matchMedia('(prefers-reduced-motion: reduce)').matches"))
        print("hero 动画名:", ws.eval(
            "getComputedStyle(document.querySelector('.hero-copy > *')).animationName"))
        print("hero 动画时长:", ws.eval(
            "getComputedStyle(document.querySelector('.hero-copy > *')).animationDuration"))

        # 点技术版按钮，采样圆形扩散
        print("\n点击「技术版」后采样：")
        ws.eval("document.querySelector('.ms-btn[data-mode=\"dev\"]').click()")
        for i in range(14):
            rip = ws.eval(
                "(()=>{const r=document.querySelector('.mode-ripple');"
                "return r ? getComputedStyle(r).transform : '(none)';})()")
            mode = ws.eval("document.documentElement.getAttribute('data-mode')")
            print(f"  t+{i*70:4}ms  mode={mode}  ripple={rip}")
            time.sleep(0.07)
    finally:
        ws.close()
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
