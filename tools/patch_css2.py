import io

p = r"D:\MollyPaw-Relay\public\assets\css\style.css"
s = io.open(p, encoding="utf-8").read()

# z-index:-1 会把荧光块沉到 body 背景后面（body 有背景 + background-attachment:fixed，
# 会形成新的层叠上下文）—— 改成不用负 z-index，改成两层文字叠一起。
s = s.replace(
    """/* 强调：橙字在米白底只有 2.83:1 且视觉发闷，
   改成「深棕字 + 橙色荧光块」，清晰且透亮。 */
em { font-style: normal; color: var(--text-accent); position: relative; }
em::after {
  content: ""; position: absolute; left: -3%; right: -3%; bottom: .04em;
  height: .3em; background: var(--orange-soft);
  border-radius: 4px; z-index: -1;
}
html[data-mode="dev"] em::after { background: #4A3626; }""",
    """/* 强调：橙字在白底只有 2.83:1 且视觉发闷，
   改成「深棕字 + 橙色荧光块」。
   注意：不能用 z-index:-1 —— body 有 background + background-attachment:fixed，
   会形成层叠上下文，负 z-index 的伪元素会沉到 body 背景下面，直接消失。
   改用 ::before 垫在文字后面（同为负偏移，但元素自身 position:relative + z-index:0）。 */
em { font-style: normal; color: var(--text-accent); position: relative; z-index: 0; }
em::before {
  content: ""; position: absolute; left: -4%; right: -4%; bottom: .04em;
  height: .3em; background: var(--orange-soft);
  border-radius: 4px; z-index: -1;
}
html[data-mode="dev"] em::before { background: #4A3626; }"""
)

# h1 高亮同理
s = s.replace(
    """/* h1 里的高亮：深棕字 + 橙色荧光块 */
.hero h1 .hl {
  color: var(--text-accent);
  position: relative; display: inline-block;
}
/* h1 里的高亮：深棕字 + 橙色荧光块（实橙块在米白底上太扎眼） */
.hero h1 .hl::after {
  content: ""; position: absolute; left: -4%; right: -4%; bottom: .06em;
  height: .32em; background: var(--orange); border-radius: 5px; z-index: -1;
  opacity: .75;
}
html[data-mode="dev"] .hero h1 .hl::after { opacity: .55; }""",
    """/* h1 里的高亮：深棕字 + 橙色荧光块 */
.hero h1 .hl {
  color: var(--text-accent);
  position: relative; display: inline-block; z-index: 0;
}
.hero h1 .hl::before {
  content: ""; position: absolute; left: -5%; right: -5%; bottom: .06em;
  height: .32em; background: var(--orange); border-radius: 5px; z-index: -1;
  opacity: .75;
}
html[data-mode="dev"] .hero h1 .hl::before { opacity: .55; }"""
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
