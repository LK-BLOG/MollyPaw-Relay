#!/usr/bin/env python3
"""检查配色对比度（WCAG 2.1）+ 是否违反 BRAND.md 的冷色禁忌。

用法：
    python tools/contrast.py
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    l1, l2 = sorted([lum(a), lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# 品牌色（BRAND.md）
BRAND = {
    "brown900": "#3A2A1A",
    "brown700": "#6B4226",
    "brown600": "#8B5E3C",
    "brown500": "#A67B5B",
    "brown300": "#D2B48C",
    "brown200": "#E4D2BC",
    "brown100": "#F5EDE3",
    "white": "#FFFFFF",
    "cream": "#FFF8F0",
    "orange": "#D4823A",
    "orange600": "#B96C2A",
    "orangeSoft": "#F7E6D2",
}

# 暗色模式
DARK = {
    "page": "#1C1310",
    "card": "#261B14",
    "text": "#F6E7D6",
    "textSoft": "#D9C0A4",
    "textMute": "#A98A6B",
    "orange": "#E0913F",
    "orange600": "#F0A457",
    "orangeSoft": "#3A2818",
    "line": "#3A2A1F",
}

# (说明, 前景, 背景, 要求)
CHECKS_LIGHT = [
    ("正文 text", BRAND["brown700"], BRAND["cream"], 4.5),
    ("次级文字 text-soft", BRAND["brown600"], BRAND["cream"], 4.5),
    ("弱化文字 text-mute", BRAND["brown500"], BRAND["cream"], 3.0),
    ("正文在卡片上", BRAND["brown700"], BRAND["white"], 4.5),
    ("次级文字在卡片上", BRAND["brown600"], BRAND["white"], 4.5),
    ("橙按钮文字", "#23160D", BRAND["orange"], 4.5),
    ("链接/强调 orange-600", BRAND["orange600"], BRAND["cream"], 4.5),
    ("橙色大字 h1", BRAND["orange"], BRAND["cream"], 3.0),
    ("卡片图标 orange-600 on soft", BRAND["orange600"], BRAND["orangeSoft"], 4.5),
    ("页脚链接", BRAND["brown600"], BRAND["white"], 4.5),
]

CHECKS_DARK = [
    ("正文 text", DARK["text"], DARK["page"], 4.5),
    ("次级文字 text-soft", DARK["textSoft"], DARK["page"], 4.5),
    ("弱化文字 text-mute", DARK["textMute"], DARK["page"], 3.0),
    ("正文在卡片上", DARK["text"], DARK["card"], 4.5),
    ("次级文字在卡片上", DARK["textSoft"], DARK["card"], 4.5),
    ("橙按钮文字", "#23160D", DARK["orange"], 4.5),
    ("链接/强调 orange", DARK["orange600"], DARK["page"], 4.5),
    ("橙色大字 h1", DARK["orange"], DARK["page"], 3.0),
    ("卡片图标 orange on soft", DARK["orange"], DARK["orangeSoft"], 4.5),
]

# BRAND.md: 不使用冷色调（蓝、绿、灰）作为主色
COLD_HUES = (170, 260)  # 青色 ~ 蓝色区间


def is_cold(hex_color: str) -> bool:
    import colorsys
    h = hex_color.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    hue = colorsys.rgb_to_hls(r, g, b)[0] * 360
    sat = colorsys.rgb_to_hls(r, g, b)[1]
    return sat > 0.25 and COLD_HUES[0] <= hue <= COLD_HUES[1]


def run(name: str, checks) -> int:
    print(f"\n=== {name} ===")
    bad = 0
    for label, fg, bg, need in checks:
        r = ratio(fg, bg)
        ok = r >= need
        if not ok:
            bad += 1
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark} {label:34} {r:5.2f} (需 {need})  {fg} on {bg}")
    return bad


def main() -> int:
    bad = 0
    bad += run("浅色模式（小白版）", CHECKS_LIGHT)
    bad += run("暗色模式（技术版）", CHECKS_DARK)

    print("\n=== BRAND.md 冷色禁忌 ===")
    cold = 0
    for name, c in list(BRAND.items()) + list(DARK.items()):
        if is_cold(c):
            print(f"  FAIL {name} {c} —— 偏冷色，BRAND 禁止")
            cold += 1
    if not cold:
        print("  OK   品牌色里没有冷色")

    print()
    if bad:
        print(f"{bad} 项对比度不达标")
        return 1
    print("对比度全部达标")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
