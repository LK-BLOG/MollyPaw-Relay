import io
import re

p = r"D:\MollyPaw-Relay\public\assets\css\style.css"
s = io.open(p, encoding="utf-8").read()

# 1. 页面底：白到米白的极窄渐变（保留暖调但不发闷）
s = s.replace(
    "  --page-bg: #FFFFFF;\n  --card-bg: #FFFFFF;",
    "  --page-bg: #FFFFFF;\n  --card-bg: #FFFFFF;\n"
    "  --card-warm: #FFFCF8;   /* 卡片底：一点点暖，靠阴影浮起 */"
)

# 2. body 背景加渐变
s = s.replace(
    """html[data-mode="lite"] body {
  background:
    radial-gradient(60% 42% at 12% 4%, rgba(212, 130, 58, .07), transparent 70%),
    radial-gradient(52% 38% at 88% 22%, rgba(166, 123, 91, .08), transparent 72%),
    var(--page-bg);
  background-attachment: fixed;
}""",
    """html[data-mode="lite"] body {
  background:
    radial-gradient(58% 40% at 10% 2%, rgba(212, 130, 58, .10), transparent 70%),
    radial-gradient(50% 36% at 90% 18%, rgba(166, 123, 91, .10), transparent 72%),
    linear-gradient(180deg, #FFFFFF 0%, #FFFCF8 45%, #FFF9F2 100%);
  background-attachment: fixed;
}"""
)

# 3. 卡片用暖白 + 更明显的阴影
s = s.replace(
    """.card {
  background: var(--card-bg); border: 1px solid var(--line-strong);
  border-radius: var(--radius); padding: 28px 24px;
  box-shadow: var(--shadow-s);""",
    """.card {
  background: var(--card-warm); border: 1px solid var(--line-strong);
  border-radius: var(--radius); padding: 28px 24px;
  box-shadow: var(--shadow-s);"""
)

# 4. 步骤卡片、dl 卡片、plain-card、faq 详情也用暖白
s = s.replace(
    """.steps li {
  display: flex; gap: 18px; align-items: flex-start;
  background: var(--card-bg); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 22px 24px;
}""",
    """.steps li {
  display: flex; gap: 18px; align-items: flex-start;
  background: var(--card-warm); border: 1px solid var(--line-strong);
  border-radius: var(--radius); padding: 22px 24px;
  box-shadow: var(--shadow-s);
}"""
)

s = s.replace(
    """.dl-main, .dl-side {
  background: var(--card-bg); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 28px 26px;
}""",
    """.dl-main, .dl-side {
  background: var(--card-warm); border: 1px solid var(--line-strong);
  border-radius: var(--radius); padding: 28px 26px;
  box-shadow: var(--shadow-s);
}"""
)

s = s.replace(
    """.plain-card {
  background: var(--card-bg); border: 1px solid var(--line-strong);""",
    """.plain-card {
  background: var(--card-warm); border: 1px solid var(--line-strong);"""
)

s = s.replace(
    """.faq details, #faq details {
  background: var(--card-bg); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 0 22px; overflow: hidden;
  transition: border-color .2s;
}""",
    """.faq details, #faq details {
  background: var(--card-warm); border: 1px solid var(--line-strong);
  border-radius: var(--radius); padding: 0 22px; overflow: hidden;
  box-shadow: var(--shadow-s);
  transition: border-color .2s;
}"""
)

# 5. 暗色模式：card-warm 跟着走
s = s.replace(
    "  --orange-soft: #3A2818;\n  --on-orange: #23160D;",
    "  --orange-soft: #3A2818;\n  --on-orange: #23160D;\n  --card-warm: #261B14;"
)

# 6. 导航/页脚/拓扑图卡片
s = s.replace(
    "background: rgba(255, 248, 240, .90);",
    "background: rgba(255, 255, 255, .92);"
)
s = s.replace(
    "background: rgba(255, 248, 240, .97);",
    "background: rgba(255, 255, 255, .98);"
)
s = s.replace(
    """.topo {
  background: var(--card-bg); border: 1px solid var(--line-strong);""",
    """.topo {
  background: var(--card-warm); border: 1px solid var(--line-strong);"""
)

# 7. section-alt 改成暖白渐变（之前米色渐变像蒙灰）
s = s.replace(
    """.section-alt {
  background: linear-gradient(180deg, var(--brown-100), var(--page-bg));
  border-block: 1px solid var(--line);
}""",
    """.section-alt {
  background: linear-gradient(180deg, #FFF9F2 0%, #FFFCF8 100%);
  border-block: 1px solid var(--brown-200);
}"""
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
