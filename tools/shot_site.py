#!/usr/bin/env python3
"""用 CDP 截静态网站（本地 http server 起的），两种模式都截。

用法：
    python tools/shot_site.py --port 8899 --out shots
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

DEBUG_PORT = 9224


class MiniWS:
    """最小 CDP WebSocket 客户端（用 websocket-client，项目已依赖）。"""

    def __init__(self, url, timeout=30):
        import websocket
        self.ws = websocket.create_connection(
            url, timeout=timeout, origin="http://127.0.0.1", suppress_origin=False
        )
        self._id = 0

    def call(self, method, params=None, timeout=30):
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.ws.settimeout(max(0.5, deadline - time.time()))
                raw = self.ws.recv()
            except Exception as exc:
                raise TimeoutError(f"CDP {method} 等待响应失败: {exc}") from exc
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("id") == msg_id:
                return data
        raise TimeoutError(f"CDP {method} 超时")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def find_browser():
    for path in (
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ):
        if path and os.path.isfile(path):
            return path
    return shutil.which("msedge") or shutil.which("chrome")


def wait_for_port(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(0.3)
    return None


def launch(browser, port=DEBUG_PORT, size=(1400, 1000)):
    profile = tempfile.mkdtemp(prefix="site-cdp-")
    args = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-proxy-server",
        "--disable-extensions",
        # headless 默认 prefers-reduced-motion: reduce，
        # 会把站点的动画全部关掉，截图就看不出动效 —— 强制关掉这个偏好。
        "--force-prefers-reduced-motion=no-preference",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        f"--window-size={size[0]},{size[1]}",
        "--hide-scrollbars",
        "about:blank",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_for_port(port):
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        return None, None, None
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        targets = json.loads(r.read().decode())
    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page:
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        return None, None, None
    return proc, profile, page["webSocketDebuggerUrl"]


def shot(ws, url, out_path, full_page=True, mode=None):
    ws.call("Page.enable")
    # headless 默认 prefers-reduced-motion: reduce，会把站点动画全关掉，
    # 命令行参数不生效，必须用 CDP 的 Emulation.setEmulatedMedia 强制改掉
    ws.call("Emulation.setEmulatedMedia", {
        "features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]
    })
    ws.call("Emulation.setDeviceMetricsOverride", {
        "width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
    })
    ws.call("Page.navigate", {"url": url})
    time.sleep(2.5)
    if mode:
        ws.call("Runtime.evaluate", {
            "expression": f"document.documentElement.setAttribute('data-mode','{mode}');"
                          "localStorage.setItem('mollypaw-mode','%s');" % mode
        })
        time.sleep(1.0)
    # 滚动一遍触发 IntersectionObserver 的渐显 —— 否则 captureBeyondViewport
    # 拍到的是所有 .reveal 元素都还没显示的初始状态
    ws.call("Runtime.evaluate", {
        "expression": """
        (async () => {
          const h = document.body.scrollHeight;
          for (let y = 0; y < h; y += 400) {
            window.scrollTo(0, y);
            await new Promise(r => setTimeout(r, 40));
          }
          window.scrollTo(0, 0);
          await new Promise(r => setTimeout(r, 700));
        })()
        """
    })
    time.sleep(1.2)
    params = {"format": "png"}
    if full_page:
        params["captureBeyondViewport"] = True
    res = ws.call("Page.captureScreenshot", params, timeout=60)
    data = res.get("result", {}).get("data")
    if not data:
        raise RuntimeError("截图失败：没有拿到 data")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data))
    print(f"  -> {out_path}  ({os.path.getsize(out_path)//1024}KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--out", default="shots")
    ap.add_argument("--path", default="/")
    args = ap.parse_args()

    browser = find_browser()
    if not browser:
        print("找不到 Edge/Chrome")
        return 1

    os.makedirs(args.out, exist_ok=True)
    proc, profile, ws_url = launch(browser)
    if not ws_url:
        print("浏览器启动失败")
        return 1

    ws = MiniWS(ws_url)
    try:
        base = f"http://127.0.0.1:{args.port}{args.path}"
        for mode in ("lite", "dev"):
            print(f"截 {mode} ...")
            shot(ws, base + f"?mode={mode}", os.path.join(args.out, f"site-{mode}.png"), mode=mode)
    finally:
        ws.close()
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
