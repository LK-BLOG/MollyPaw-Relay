import io

p = r"D:\MollyPaw-Relay\tools\probe_anim.py"
s = io.open(p, encoding="utf-8").read()

# 在 Page.enable 后强制 emulateMedia
s = s.replace(
    '        ws.call("Page.enable")',
    '        ws.call("Page.enable")\n'
    '        # headless 默认 prefers-reduced-motion: reduce，命令行参数不生效，\n'
    '        # 必须用 CDP 的 Emulation.setEmulatedMedia 强制改掉\n'
    '        ws.call("Emulation.setEmulatedMedia", {\n'
    '            "features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]\n'
    '        })'
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
