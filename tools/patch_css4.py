import io

p = r"D:\MollyPaw-Relay\public\assets\css\style.css"
s = io.open(p, encoding="utf-8").read()

# 通用 .ico 样式（条子里的锁不在 .topo-node 内，之前没样式 → 变实心黑块）
s = s.replace(
    ".topo-node .ico { fill: none; stroke: var(--brown-700); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }",
    """/* 图标通用样式 —— 必须给 .ico 本身定义，
   否则 .topo-enc 里的锁（不在 .topo-node 内）会变成实心黑块 */
.ico { fill: none; stroke: var(--brown-700); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
.ico-solid { fill: var(--brown-300); stroke: none; }
html[data-mode="dev"] .ico { stroke: var(--orange); }
html[data-mode="dev"] .ico-solid { fill: var(--brown-300); }"""
)

# 去掉重复的 .topo-node .ico（已被通用 .ico 覆盖）
s = s.replace(
    """html[data-mode="dev"] .topo-node .ico { stroke: var(--orange); }
html[data-mode="dev"] .topo-node .lbl { fill: var(--cream); }""",
    """html[data-mode="dev"] .topo-node .lbl { fill: var(--cream); }"""
)

# 加密条里的锁用深棕（在浅橙底上看得清）
s = s.replace(
    ".topo-enc { fill: var(--orange-soft); stroke: var(--orange); stroke-width: 1.4; }",
    ".topo-enc { fill: var(--orange-soft); stroke: var(--orange); stroke-width: 1.4; }\n"
    ".topo-enc .ico { stroke: var(--brown-700); stroke-width: 1.8; }\n"
    "html[data-mode=\"dev\"] .topo-enc .ico { stroke: var(--orange); }"
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
