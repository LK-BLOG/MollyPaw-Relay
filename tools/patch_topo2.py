import io

p = r"D:\MollyPaw-Relay\public\index.html"
s = io.open(p, encoding="utf-8").read()

anchor = '<svg class="topo-svg"'
i = s.index(anchor)
j = s.index('</svg>', i) + len('</svg>')

new = '''<svg class="topo-svg" viewBox="0 0 460 330" role="img"
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

        <!-- 中继：服务器机架（不再用锁 —— 锁的 path 画出来像墓碑） -->
        <g class="topo-node topo-relay" transform="translate(168 46)">
          <rect x="0" y="0" width="124" height="188" rx="17" />
          <g class="ico" transform="translate(36 38)">
            <rect x="0" y="0" width="52" height="62" rx="6" />
            <line x1="8" y1="15" x2="44" y2="15" />
            <line x1="8" y1="31" x2="44" y2="31" />
            <line x1="8" y1="47" x2="34" y2="47" />
            <circle class="ico-dot" cx="41" cy="47" r="2.6" />
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

        <!-- 端到端加密：盾牌（不是锁） -->
        <g transform="translate(230 262)">
          <rect class="topo-enc" x="-160" y="-15" width="320" height="30" rx="15" />
          <g class="ico" transform="translate(-146 -11)">
            <path d="M10 0 L19 3.4 V11 C19 16.4 10 21 10 21 C10 21 1 16.4 1 11 V3.4 Z" />
            <path d="M6.2 10.6 L9 13.4 L14 7.8" />
          </g>
          <text class="topo-enc-lbl" x="22" y="5" text-anchor="middle">端到端加密 · 中继看不到内容</text>
        </g>

        <text class="topo-note" x="143" y="130" text-anchor="middle">WSS</text>
        <text class="topo-note" x="317" y="130" text-anchor="middle">WSS</text>

        <text class="topo-note" x="230" y="303" text-anchor="middle">手机和电脑两端直接对话，中间那台只负责传话</text>
        <text class="topo-note" x="230" y="322" text-anchor="middle">所有模型调用、文件读写、命令执行都发生在你自己那台电脑上</text>
      </svg>'''

s = s[:i] + new + s[j:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("topo replaced, len:", len(s))
