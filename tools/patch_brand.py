import io

p = r"D:\MollyPaw-Relay\public\index.html"
s = io.open(p, encoding="utf-8").read()

# 顶部导航的 brand
s = s.replace(
    '      <span class="brand-text">Molly<em>Paw</em></span>',
    '      <span class="brand-text">MollyPaw <em>Online</em></span>'
)

# 页脚的 brand
s = s.replace(
    '      <span class="brand-paw" aria-hidden="true">🐾</span>\n      <b>MollyPaw Online</b>',
    '      <span class="brand-paw" aria-hidden="true">🐾</span>\n      <b>MollyPaw <em>Online</em></b>'
)

io.open(p, "w", encoding="utf-8", newline="").write(s)

# CSS：Online 更突出
c = r"D:\MollyPaw-Relay\public\assets\css\style.css"
css = io.open(c, encoding="utf-8").read()

css = css.replace(
    """.brand-text em { font-style: normal; color: var(--orange); }""",
    """/* 品牌名：MollyPaw 是产品本体，Online 是本站特色 —— 后者更突出 */
.brand-text { font-size: 19px; letter-spacing: -.015em; }
.brand-text em {
  font-style: normal; color: var(--orange);
  font-weight: 900;
  padding: 2px 9px; margin-left: 2px;
  background: var(--orange-soft); border-radius: 7px;
  font-size: .82em; letter-spacing: .01em;
  display: inline-block; vertical-align: 2px;
}
html[data-mode="dev"] .brand-text em { background: #3A2818; color: var(--orange); }
.foot b em {
  font-style: normal; color: var(--orange); font-weight: 900;
}"""
)

io.open(c, "w", encoding="utf-8", newline="").write(css)
print("patched")
