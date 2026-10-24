import io

p = r"D:\MollyPaw-Relay\public\assets\css\style.css"
s = io.open(p, encoding="utf-8").read()

# ── 1. h1 高亮：::after → ::before（z-index:-1 在 body 背景后被吞） ──
s = s.replace(
    """.hero h1 .hl {
  color: var(--text-accent);
  position: relative; display: inline-block;
}
/* h1 里的高亮：深棕字 + 橙色荧光块 */
.hero h1 .hl::after {
  content: ""; position: absolute; left: -4%; right: -4%; bottom: .06em;
  height: .32em; background: var(--orange); border-radius: 5px; z-index: -1;
  opacity: .75;
}
html[data-mode="dev"] .hero h1 .hl::after { opacity: .55; }""",
    """.hero h1 .hl {
  color: var(--text-accent);
  position: relative; display: inline-block; z-index: 0;
}
/* h1 高亮：深棕字 + 橙色荧光块。
   用 ::before 而不是 ::after —— 负 z-index 的伪元素会沉到 body 背景下面（消失）。 */
.hero h1 .hl::before {
  content: ""; position: absolute; left: -5%; right: -5%; bottom: .06em;
  height: .32em; background: var(--orange); border-radius: 5px; z-index: -1;
  opacity: .75;
}
html[data-mode="dev"] .hero h1 .hl::before { opacity: .55; }"""
)

# ── 2. 拓扑图节点框：fill 用了 page-bg，暗色下和页面底同色 → 框隐形 ──
s = s.replace(
    ".topo-node rect { fill: var(--page-bg); stroke: var(--line-strong); stroke-width: 1.5; }",
    ".topo-node rect { fill: var(--card-warm); stroke: var(--brown-300); stroke-width: 1.5; }"
)
s = s.replace(
    "html[data-mode=\"dev\"] .topo-node rect { fill: #1F1611; }",
    "html[data-mode=\"dev\"] .topo-node rect { fill: #33241A; stroke: #5C4231; }"
)
# 拓扑图里的图标：暗色下深棕看不见
s = s.replace(
    ".topo-node .ico { fill: none; stroke: var(--orange); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }",
    ".topo-node .ico { fill: none; stroke: var(--brown-700); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }"
)
s = s.replace(
    ".topo-node .lbl { fill: var(--text); font-size: 12.5px; font-weight: 700; }",
    ".topo-node .lbl { fill: var(--brown-900); font-size: 12.5px; font-weight: 800; }"
)
s = s.replace(
    ".topo-node .sub { fill: var(--text-mute); font-size: 10.5px; font-weight: 600; }",
    ".topo-node .sub { fill: var(--brown-600); font-size: 10.5px; font-weight: 600; }"
)
# 中继节点（强调）
s = s.replace(
    ".topo-relay rect { fill: var(--orange-soft); stroke: var(--orange); stroke-width: 1.6; }",
    ".topo-relay rect { fill: var(--orange); stroke: var(--brown-700); stroke-width: 1.8; }"
)
s = s.replace(
    "html[data-mode=\"dev\"] .topo-relay rect { fill: #3A2818; }",
    "html[data-mode=\"dev\"] .topo-relay rect { fill: #E0913F; stroke: #F0A457; }"
)
# 中继里的文字要压在橙块上 → 深棕
s = s.replace(
    """.topo-relay .lbl { fill: var(--text); }""",
    """.topo-relay .lbl { fill: var(--brown-900); }"""
)
# 暗色模式下中继节点里的文字反过来
s = s.replace(
    "html[data-mode=\"dev\"] .topo-enc { fill: #3A2818; }",
    """html[data-mode="dev"] .topo-enc { fill: #3A2818; }
html[data-mode="dev"] .topo-node .ico { stroke: var(--orange); }
html[data-mode="dev"] .topo-node .lbl { fill: var(--cream); }
html[data-mode="dev"] .topo-node .sub { fill: var(--text-soft); }
html[data-mode="dev"] .topo-relay .lbl { fill: #23160D; }
html[data-mode="dev"] .topo-relay .sub { fill: #3A2A1A; }"""
)

# ── 3. CTA 区（把绳子系上）：dev 下太丑，改成有质感的深色块 ──
s = s.replace(
    """.cta-band {
  padding: 76px 0; text-align: center;
  background: linear-gradient(135deg, var(--brown-700), var(--brown-900));
  color: var(--cream);
}
html[data-mode="dev"] .cta-band { background: linear-gradient(135deg, #2E2018, #1C1310); }
.cta-band h2 { color: var(--cream); font-size: clamp(30px, 4vw, 44px); margin-bottom: 8px; }
.cta-band p { color: rgba(255, 248, 240, .72); font-size: 17px; margin-bottom: 26px; }""",
    """.cta-band {
  padding: 84px 0; text-align: center;
  background: linear-gradient(150deg, var(--brown-700) 0%, var(--brown-900) 62%, #2E2018 100%);
  color: var(--cream);
  position: relative; overflow: hidden;
}
/* 暖光晕 —— 深色块上不做点渐变就死板 */
.cta-band::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(46% 60% at 22% 18%, rgba(212, 130, 58, .30), transparent 70%),
    radial-gradient(40% 52% at 80% 82%, rgba(212, 130, 58, .18), transparent 72%);
}
.cta-band .wrap { position: relative; z-index: 1; }
html[data-mode="dev"] .cta-band {
  background: linear-gradient(150deg, #3A2A1A 0%, #241A13 58%, #1C1310 100%);
  border-top: 1px solid var(--line-strong);
}
html[data-mode="dev"] .cta-band::before {
  background:
    radial-gradient(46% 60% at 22% 18%, rgba(224, 145, 63, .26), transparent 70%),
    radial-gradient(40% 52% at 80% 82%, rgba(224, 145, 63, .14), transparent 72%);
}
.cta-band h2 { color: var(--cream); font-size: clamp(30px, 4vw, 44px); margin-bottom: 10px; letter-spacing: -.02em; }
.cta-band p { color: rgba(255, 248, 240, .78); font-size: 17px; margin-bottom: 30px; }
html[data-mode="dev"] .cta-band h2 { color: var(--cream); }
html[data-mode="dev"] .cta-band p { color: var(--text-soft); }"""
)

# ── 4. CTA 按钮：深色区上用亮橙 + 深棕字 ──
s = s.replace(
    "/* CTA 区是深棕渐变底，主按钮改用橙 —— 深棕压深棕看不见 */\n.cta-band .btn-primary { background: var(--orange); color: var(--on-orange); }",
    "/* CTA 区是深色底，主按钮用亮橙 —— 深棕压深棕看不见 */\n"
    ".cta-band .btn-primary {\n"
    "  background: var(--orange); color: #23160D;\n"
    "  box-shadow: 0 10px 26px rgba(212, 130, 58, .34);\n"
    "}\n"
    ".cta-band .btn-primary:hover { background: var(--orange-600); color: #23160D; }"
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
