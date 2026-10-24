import io

p = r"D:\MollyPaw-Relay\tools\probe_anim.py"
s = io.open(p, encoding="utf-8").read()

start = s.index("        print(\"JS 错误:\"")
end = s.index("    finally:\n        ws.close()")

new = '''        print("reduced-motion:", ws.eval(
            "matchMedia('(prefers-reduced-motion: reduce)').matches"))
        print("hero 动画名:", ws.eval(
            "getComputedStyle(document.querySelector('.hero-copy > *')).animationName"))
        print("hero 动画时长:", ws.eval(
            "getComputedStyle(document.querySelector('.hero-copy > *')).animationDuration"))

        # 点技术版按钮，采样圆形扩散
        print("\\n点击「技术版」后采样：")
        ws.eval("document.querySelector('.ms-btn[data-mode=\\"dev\\"]').click()")
        for i in range(14):
            rip = ws.eval(
                "(()=>{const r=document.querySelector('.mode-ripple');"
                "return r ? getComputedStyle(r).transform : '(none)';})()")
            mode = ws.eval("document.documentElement.getAttribute('data-mode')")
            print(f"  t+{i*70:4}ms  mode={mode}  ripple={rip}")
            time.sleep(0.07)
'''

s = s[:start] + new + s[end:]

# headless 默认开 reduced-motion，加参数关掉
s = s.replace(
    '"--no-proxy-server", "--disable-extensions",',
    '"--no-proxy-server", "--disable-extensions",\n'
    '        # headless 默认 prefers-reduced-motion: reduce，会把站点动画全关掉\n'
    '        "--force-prefers-reduced-motion=no-preference",'
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
