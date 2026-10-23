#!/usr/bin/env python3
"""截指定区域（CSS 选择器）的局部图，用来检查小细节。

用法：
    python tools/shot_zone.py --port 8899 --sel ".topo" --out shots/topo.png
"""
from __future__ import annotations

import argparse
import base64
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

DEBUG_PORT = 9227


class MiniWS:
    def __init__(self, url, timeout=30):
        import websocket
        self.ws = websocket.create_connection(
            url, timeout=timeout, origin="http://127.0.0.1", suppress_origin=False)
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
        r = self.call("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True},
                      timeout=timeout)
        return r.get("result", {}).get("result", {}).get("value")

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
    ap.add_argument("--sel", default=".topo")
    ap.add_argument("--out", default="shots/zone.png")
    ap.add_argument("--mode", default="lite")
    ap.add_argument("--scale", type=float, default=2.0)
    args = ap.parse_args()

    browser = find_browser()
    if not browser:
        print("找不到浏览器")
        return 1
    profile = tempfile.mkdtemp(prefix="zone-")
    proc = subprocess.Popen([
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-proxy-server", "--disable-extensions",
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
        ws.call("Runtime.enable")
        ws.call("Emulation.setEmulatedMedia", {
            "features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]})
        ws.call("Emulation.setDeviceMetricsOverride", {
            "width": 1400, "height": 1000, "deviceScaleFactor": args.scale, "mobile": False})
        ws.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/?mode={args.mode}"})
        time.sleep(2.5)

        box = ws.eval(
            f"(()=>{{const e=document.querySelector({args.sel!r});"
            "if(!e) return null;"
            "const r=e.getBoundingClientRect();"
            "return {x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height};})()"
        )
        if not box:
            print("没找到元素:", args.sel)
            return 1
        print("区域:", box)
        clip = {"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"], "scale": 1}
        res = ws.call("Page.captureScreenshot", {
            "format": "png", "clip": clip, "captureBeyondViewport": True}, timeout=60)
        data = res.get("result", {}).get("data")
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"-> {args.out} ({os.path.getsize(args.out)//1024}KB)")
    finally:
        ws.close()
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
