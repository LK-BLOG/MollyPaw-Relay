# MollyPaw Relay

手机 ↔ 电脑的**中继**。部署在 Cloudflare 上。

它的唯一职责：**把两头的连接对上，然后闪开**。
它不解析任何业务内容 —— 所有数据都是 AES-256-GCM 密文，
中继看到的是房间号、角色、时间戳、包长度，仅此而已。

```
Android App ──wss──┐
                   ├──> wss://mollypaw-online.pages.dev/server
PC (MollyPaw) ─wss─┘         │
                             └──> Durable Object（RelayRoom）
```

## 为什么要中继

电脑在家用宽带后面，外面进不来。
所以两端都**主动向外连**，中继负责把它们接上。

好处是两端都不需要公网 IP、不需要端口映射。

## 组成

| 目录 | 是什么 |
|---|---|
| `worker/` | Durable Object（`RelayRoom`）—— 真正的转发逻辑 |
| `functions/` | Pages Function —— `/server` 入口，把 WS 请求转给 DO |
| `public/` | 官网（`mollypaw-online.pages.dev`） |
| `relay/dev_server.py` | 本地开发用的 Python 中继（行为与 DO 一致） |
| `PROTOCOL.md` | **协议规范，唯一真源** |

## 为什么 Pages 而不是 workers.dev

`workers.dev` 在国内被 DNS 污染，解析到的地方连不上。
`pages.dev` 相对可用（跟主官网 `xiaokan-esn.pages.dev` 同一个思路）。

Pages Function 本身不能建 DO，但**可以绑定**独立 Worker 导出的 DO 类
（`wrangler.toml` 里的 `durable_objects.bindings`）。

## 部署

```bash
# 1) 先发 Worker（DO 住在里面）
cd worker
wrangler deploy

# 2) 再发 Pages（函数 + 官网）
cd ..
wrangler pages deploy public --project-name=mollypaw-online --branch=main
```

## 中继的行为约定

这些是**必须**满足的，Python 版与 JS 版要一致
（`tests/test_relay_contract.py` 会验）：

1. 连接建立后第一帧必须是合法 `hello`
2. 房间内 `pc` 唯一：新 `pc` 顶掉旧 `pc`
3. `observer` 的帧**照样转发**给 `pc` —— 越权由 `pc` 判。
   （中继看不到明文，没法区分 `conv.list` 和 `conv.delete`；
   硬拦的话观察端连会话列表都拉不到）
4. 单帧上限 1 MiB
5. 速率：120 帧 / 10 秒
6. 帧里的角色字段必须与连接声明的一致，否则 `bad_role`

## 本地开发

```bash
python relay/dev_server.py --port 18767
# 电脑端连 ws://127.0.0.1:18767/server
```

## 许可

GPLv3 · 灵感来自摩尼，一只可乐色和白色的小泰迪犬
