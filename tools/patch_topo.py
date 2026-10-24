import io
import re

p = r"D:\MollyPaw-Relay\public\index.html"
s = io.open(p, encoding="utf-8").read()

start = s.index('      <svg class="topo-svg"')
end = s.index('      </svg>') + len('      </svg>')

new = '''      <svg class="topo-svg" viewBox="0 0 460 330" role="img"
           aria-label="拓扑图：手机通过加密中继连接电脑，中继看不到内容">
        <!-- 双向连线：手机 ⇄ 中继 ⇄ 电脑 -->
        <path class="topo-wire topo-wire-dash" d="M 118 140 H 168" />
        <path class="topo-wire topo-wire-dash" d="M 292 140 H 342" />
        <path class="topo-arrow" d="M 168 140 l -11 -7 v 14 z" />
        <path class="topo-arrow" d="M 292 140 l 11 -7 v 14 z" />

        <!-- 手机 -->
        <g class="topo-node" transform="translate(28 46)">
          <rect x="0" y="0" width="90" height="188" rx="17" />
          <rect class="ico-solid" x="34" y="9" width="22" height="3.5" rx="1.75" />
          <g class="ico" transform="translate(28 34)">
            <rect x="0" y="0" width="34" height="56" rx="6" />
            <line x1="8" y1="47" x2="26" y2="47" />
          </g>
          <text class="lbl" x="45" y="126" text-anchor="middle">手机</text>
          <text class="sub" x="45" y="145" text-anchor="middle">Android App</text>
          <text class="sub" x="45" y="163" text-anchor="middle">控制端 / 观察端</text>
        </g>

        <!-- 中继：跟手机电脑一样高，实心橙块表示"焦点" -->
        <g class="topo-node topo-relay" transform="translate(168 46)">
          <rect x="0" y="0" width="124" height="188" rx="17" />
          <!-- 锁：锁体 + 锁梁，坐标对齐 -->
          <g class="ico" transform="translate(44 40)">
            <rect x="0" y="14" width="36" height="26" rx="5" />
            <path d="M8 14 V9 a10 10 0 0 1 20 0 v5" />
            <circle cx="18" cy="26" r="2.6" />
            <line x1="18" y1="28" x2="18" y2="33" />
          </g>
          <text class="lbl" x="62" y="126" text-anchor="middle">中继</text>
          <text class="sub" x="62" y="145" text-anchor="middle">盲转发</text>
          <text class="sub" x="62" y="163" text-anchor="middle">看不到明文</text>
        </g>

        <!-- 电脑 -->
        <g class="topo-node" transform="translate(342 46)">
          <rect x="0" y="0" width="90" height="188" rx="17" />
          <g class="ico" transform="translate(22 42)">
            <rect x="0" y="0" width="46" height="29" rx="3" />
            <line x1="23" y1="29" x2="23" y2="38" />
            <line x1="9" y1="38" x2="37" y2="38" />
          </g>
          <text class="lbl" x="45" y="126" text-anchor="middle">电脑</text>
          <text class="sub" x="45" y="145" text-anchor="middle">MollyPaw 桌面端</text>
          <text class="sub" x="45" y="163" text-anchor="middle">真正的计算在这里</text>
        </g>

        <!-- 端到端加密条：横跨两端 -->
        <g transform="translate(230 262)">
          <rect class="topo-enc" x="-160" y="-15" width="320" height="30" rx="15" />
          <g class="ico" transform="translate(-146 -10)">
            <rect x="0" y="9" width="20" height="14" rx="3" />
            <path d="M4.5 9 V6 a5.5 5.5 0 0 1 11 0 v3" />
          </g>
          <text class="topo-enc-lbl" x="20" y="5" text-anchor="middle">端到端加密 · 中继看不到内容</text>
        </g>

        <text class="topo-note" x="143" y="130" text-anchor="middle">WSS</text>
        <text class="topo-note" x="317" y="130" text-anchor="middle">WSS</text>

        <text class="topo-note" x="230" y="303" text-anchor="middle">手机和电脑两端直接对话，中间那台只负责传话</text>
        <text class="topo-note" x="230" y="322" text-anchor="middle">所有模型调用、文件读写、命令执行都发生在你自己那台电脑上</text>
      </svg>'''

s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("topo svg replaced")
