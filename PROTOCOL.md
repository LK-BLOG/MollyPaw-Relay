# MollyPaw Relay Protocol v1

手机 ↔ 电脑 跨局域网互联协议。**本文档是唯一真源**，三个实现必须逐字节一致：

| 实现 | 位置 | 语言 |
|---|---|---|
| PC 端 | `D:\MollyPaw Agent\agent\relay\` | Python |
| 中继 | `D:\MollyPaw-Relay\worker\` + `relay\dev_server.py` | JS / Python |
| 手机端 | `D:\MollyPaw-Android\` | Kotlin |

任何一方改协议，必须同步 `PROTOCOL_VERSION` 并更新本文档。

---

## 1. 拓扑

```
Android App ──wss──┐
                   ├──> mollypaw-online.pages.dev/server (Pages Function)
PC (MollyPaw) ─wss─┘            │
                                └──> RelayRoom (Durable Object)  ← 只转发密文
```

- **PC 和手机都是 WS 出站客户端**，双方都不需要公网 IP、不需要端口映射。
- 中继按 `room` 分组，一个 room 内角色固定三种：`pc`（唯一）、`app`（控制端）、`observer`（观察端，只读）。
- 中继**永不解析 `data` 帧的 `c` 字段**。它看到的只有：房间名、角色、seq、时间、包长度。

---

## 2. 连接地址

| 环境 | 地址 |
|---|---|
| 生产 | `wss://mollypaw-online.pages.dev/server?room=<room>` |
| 本地 PC 直连（不开中继） | `ws://127.0.0.1:18766/ws` |
| 本地开发中继 | `ws://127.0.0.1:18767/server?room=<room>` |

`room` 由 PSK 派生（见 §4.2），客户端自己算，不需要物化到中继配置里。

---

## 3. 帧格式

**所有帧都是单个 JSON 文本消息（WS text frame）。** 不用二进制帧。

```json
{"v":1,"t":"data","seq":12,"r":"<room>","f":"app","id":"<uuid>","n":"<b64>","c":"<b64>"}
```

| 字段 | 类型 | 出现于 | 说明 |
|---|---|---|---|
| `v` | int | 全部 | 协议版本，必须 == `1`，不等则中继断开并回 `error.version` |
| `t` | string | 全部 | `hello` \| `data` \| `ping` \| `pong` \| `bye` \| `error` \| `presence` |
| `r` | string | 全部 | room 名，小写 hex，32 字符 |
| `f` | string | 全部 | 发送方角色：`pc` \| `app` \| `observer` |
| `seq` | int | 全部 | 发送方**自己方向**的单调递增序号，从 1 开始 |
| `id` | string | data | 消息 uuid，用于请求/响应配对 |
| `n` | string | data | base64(12 字节 nonce) |
| `c` | string | data | base64(ciphertext ‖ 16 字节 GCM tag) |

### 3.1 明文帧（不经加密）

只有三种：

1. `hello`（客户端→中继，第一帧）
   ```json
   {"v":1,"t":"hello","r":"<room>","f":"pc","dev":"<device uuid>",
    "eph":"<b64 32B X25519 临时公钥>","hs":"<b64 16B 握手 nonce>","ts":1700000000}
   ```

   **`hello` 由中继转发给房间内其他已握手的成员。** 这是密钥交换能成立的
   前提：中继虽然看得到 `eph` / `hs`，但拿不到 PSK，所以推不出会话密钥。
   这等价于公开交换公钥，是标准做法。

   新成员加入时，中继把它自己的 `hello` 发给老成员，同时把老成员各自的
   `hello` 回放给新成员 —— 任何一方都不需要额外请求。

   **注意：PIN 绝不出现在 `hello` 里**（原因见 §5.1）。

2. `ping` / `pong`（双向，20 秒间隔）
   ```json
   {"v":1,"t":"ping","r":"<room>","f":"app","ts":1700000000}
   ```
3. `error`（中继→客户端）
   ```json
   {"v":1,"t":"error","code":"offline","msg":"电脑端已离线，请开启电脑后再试"}
   ```
4. `presence`（中继→房间内所有人，成员增减时广播）
   ```json
   {"v":1,"t":"presence","r":"<room>","pc":1,"app":2,"observer":0}
   ```

`code` 全集：`version` \| `bad_frame` \| `bad_room` \| `bad_role` \| `role_taken` \| `offline` \| `forbidden` \| `not_found` \| `internal` \| `too_large` \| `rate_limited`。

### 3.2 data 帧的 AAD 绑定

```
AAD = utf8("mollypaw/v1|" + room + "|" + from + "|" + str(seq))
```

**必须**用这个 AAD 做 AES-GCM。它锁定「哪间房、谁发的、第几帧」，防止：
- 中继把 A 房间的密文搬去 B 房间；
- 中继把 `observer` 的帧冒充成 `app`；
- 重放与乱序。

### 3.3 明文载荷（加密之后的内层）

```json
{"m":"chat.send","id":"<uuid>","p":{...}}
```

| 字段 | 说明 |
|---|---|
| `m` | 方法名 |
| `id` | 请求 id；响应回同 id |
| `p` | 参数对象 |
| `ok` | 仅响应：`true` / `false` |
| `e` | 仅失败响应：错误码 |
| `r` | 仅响应：返回值 |

---

## 4. 密码学

### 4.1 算法

| 用途 | 算法 |
|---|---|
| 密钥交换 | X25519（RFC 7748） |
| 密钥派生 | HKDF-SHA256（RFC 5869） |
| 对称加密 | AES-256-GCM，12 字节 nonce，16 字节 tag |
| 随机源 | CSPRNG（`os.urandom` / `SecureRandom` / `crypto.getRandomValues`） |

### 4.2 PSK 与 room

PSK 是用户自定义的预共享密钥（**唯一需要人工同步的秘密**）。

```
psk_bytes  = utf8(psk)                      # 不 trim、不做 unicode 归一化，原样字节
room       = hex(HKDF-SHA256(ikm=psk_bytes, salt="", info="mollypaw/v1/room"))[:32]
```

HKDF-Extract 的 salt 传**空字符串**，RFC 5869 规定等价于 32 字节全零，三方实现都必须按这个来。

### 4.3 会话密钥

```
shared     = X25519(my_eph_priv, peer_eph_pub)          # 32 字节
ikm        = shared ‖ psk_bytes                          # 64 字节
salt       = hs_pc ‖ hs_app                              # 各 16 字节，共 32 字节
key        = HKDF-SHA256(ikm, salt, info="mollypaw/v1/session")   # 32 字节
```

- `eph`：每次连接新生成的 X25519 临时密钥对（32 字节私钥 + 32 字节公钥）。
- `hs_pc` / `hs_app`：各自生成的 16 字节随机握手 nonce，放在自己的 `hello` 里。
- **salt 顺序固定 `hs_pc ‖ hs_app`**（不是按发送先后），两端必须一致。

### 4.4 密钥强度策略

```
len(psk) >= 16                     # 按字符数，不是字节数
且同时包含：小写字母、大写字母、数字
```

**不要求符号**，**不做字典词检查**（三方词表无法保证一致，宁可不做）。

不满足则**本地直接拒绝连接**，不发起 WS。错误码 `bad_key`，提示缺什么：

| 缺失项 | 提示 |
|---|---|
| 长度 < 16 | `密钥太短：至少 16 位，现在 N 位` |
| 缺小写 | `密钥需要至少一个小写字母` |
| 缺大写 | `密钥需要至少一个大写字母` |
| 缺数字 | `密钥需要至少一个数字` |

### 4.5 rekey

- 触发：**发出第 1000 个 data 帧** 或 **连接满 3600 秒**，先到先触发。
- 发起方：**pc**。pc 生成新临时密钥对，发 `data` 帧 `{"m":"rekey.offer","p":{"eph":"<b64>"}}`（用**旧密钥**加密）。
- app 回 `{"m":"rekey.accept","p":{"eph":"<b64>"}}`（旧密钥加密）。
- 双方用新 eph 重新跑 §4.3，`salt` 换成新的 `hs`（每轮 rekey 重新随机，pc 的在 offer 里带，app 的在 accept 里带）。
- **双密钥窗口**：新密钥生效后，**旧密钥继续可解 3 秒**（容忍在途帧）。
- 若 3 秒内 app 未回 accept，pc 放弃本轮，10 秒后重试。

---

## 5. 配对与设备

### 5.1 首次配对

**握手顺序（重要）**：`hello` 会被中继转发（§3.1），所以两端在配对开始前
**已经**各自拿到对方的 `eph` 和 `hs`，会话密钥（§4.3）此时就已派生好。
配对流程整体跑在这个临时会话密钥之上。

1. PC 设置页点「添加设备」，选角色（控制端 / 观察端），生成：
   - **PIN**：6 位数字（首位可为 0），TTL **300 秒**
   - **pair_salt**：32 字节随机数，与 PIN 同生命周期
   两者都只存内存。PC 把自己的 `pair_salt` 通过中继明文广播给房间内的 app
   （它就是防止跨会话预计算用的，不是秘密）。

2. 手机输入：中继地址、PSK、PIN、设备名。

3. app 发加密帧（用§4.3 临时会话密钥）：
   ```json
   {"m":"pair.req","p":{"dev_id":"<uuid>","dev_name":"<str>",
                        "dev_pub":"<b64 32B>","proof":"<b64>"}}
   ```
   ```
   dev_pub    = X25519 长期设备公钥（首次配对时本地生成并持久化）
   proof_key  = PBKDF2-HMAC-SHA256(password=utf8(PIN), salt=pair_salt,
                                   iterations=100000, dklen=32)
   proof      = HMAC-SHA256(proof_key, utf8(dev_id + "|" + dev_name))
   ```

4. PC 校验：PIN 未过期、`proof` 匹配、设备数 < 16。

5. 通过 → PC 回：
   ```json
   {"m":"pair.ok","p":{"role":"app|observer","token":"<b64 32B>","pc_pub":"<b64 32B>"}}
   ```
   写入 `data/relay/devices.json`，**并立即作废该 PIN**（一次性）。

6. 失败 → `{"m":"pair.err","p":{"e":"bad_proof","left":3}}`，app 提示重输，
   `left` 是剩余尝试次数。

**PIN 错误 5 次 → 立即作废**，PC 必须重新生成。

#### 残留风险（必须如实记录，不粉饰）

6 位 PIN 只有 10^6 种，而中继看得到 `pair_salt` 和 `proof` 的密文外层 ——
**理论上可以离线爆破**：100000 次 PBKDF2 × 10^6 = 10^11 次 HMAC，GPU 上约几分钟到几小时。

减小手段（都已实现，但无法归零）：

| 手段 | 作用 |
|---|---|
| PBKDF2 10 万次迭代 | 把单次尝试成本抬高 10^5 倍 |
| `pair_salt` 每轮随机 | 阻止跨会话预计算表 |
| TTL 300 秒 | 超过窗口后 PIN 作废，爆破出来也没用 |
| 一次性 | 配对成功即作废 |
| 服务端 5 次上限 | 挡在线爆破，不挡离线爆破 |
| PC 端可见提示 | 配对时 PC 界面显示发起方设备名与时间，人能发现异常 |

**要真正消除这条风险，得把 PIN 加长到 8 位以上或改用二维码。**
用户明确选择"6 位数字 + 不要二维码"，所以这条风险被接受并记录在此。

### 5.2 后续连接

配对拿到 `token` 后，每次连接都走 auth：

```json
{"m":"auth.req","p":{"dev_id":"<uuid>","token":"<b64 32B>","ts":<int>}}
```

- `token` **直接上送**（不需要 HMAC）。理由：整条连接已经被 §4.3 的临时会话密钥
  端到端加密，token 从没以明文离开过这条加密通道；而且它只在配对响应里出现过
  一次，之后只存 sha256。再套一层 HMAC 反而是自欺 —— 服务端手里只有 hash，
  根本没法当 HMAC key 用。
- `ts` 是客户端当前毫秒时间戳，PC 校验与自己时钟差 ≤ 120 秒。
- PC 校验：`sha256(b64decode(token)) == 存储的 token_hash`，且设备未吊销。
- 通过 → `{"m":"auth.ok","p":{"role":"app|observer","server_ts":<int>}}`。
- 失败 → `{"m":"auth.err","p":{"e":"unknown|revoked|stale_ts|bad_token"}}`。
- **PC 的时钟即权威**：`server_ts` 用于 app 校准本地偏移，避免手机时间不准。

`token` 泄露 = 等同于该设备的全部权限。所以它只存在设备的私有存储里，
手机端放 Android Keystore 加密的 DataStore，PC 端只留 hash。

### 5.3 设备注册表

`data/relay/devices.json`：

```json
{
  "devices": [
    {"dev_id":"<uuid>","name":"小戡的手机","role":"app","pub":"<b64>",
     "token_hash":"<sha256 hex>","added_at":1700000000,"last_seen":1700000000,"revoked":false}
  ],
  "pins": {}
}
```

- **token 只存 sha256**，明文只在配对响应里出现一次。
- 吊销 = 标记 `revoked:true`，PC 下次校验直接拒。
- 上限 **16 台设备**，超过则拒绝新增。

---

## 6. 方法表

`P` = 参数，`R` = 返回。`角色` 列表示**允许调用**的角色。

### 6.1 聊天

| 方法 | 角色 | P | R / 事件 |
|---|---|---|---|
| `chat.send` | app | `{text, conversation_id?}` | `{conversation_id, message_id}`；随后推 `chat.delta` 流 |
| `chat.stop` | app | `{}` | `{stopped: bool}` |
| `chat.delta` | pc→app 事件 | — | `{conversation_id, message_id, text, reasoning?, done, cancelled?}` |
| `chat.tool_call` | pc→app 事件 | — | `{name, args, request_id, danger_level}` |
| `chat.tool_result` | pc→app 事件 | — | `{request_id, result, success, rejected}` |

### 6.2 审批

| 方法 | 角色 | P | R |
|---|---|---|---|
| `approval.list` | app | `{}` | `{pending:[{req_id,name,args,danger,created_at}]}` |
| `approval.reply` | app | `{req_id, approved}` | `{ok:true}` |
| `approval.request` | pc→app 事件 | — | `{request_id, name, args, danger_level}` |

**不设超时**。连接断了请求仍在，重连后 `approval.list` 能拉到。

### 6.3 会话

| 方法 | 角色 | P | R |
|---|---|---|---|
| `conv.list` | app, observer | `{}` | `{conversations:[{id,title,updated_at}]}` |
| `conv.new` | app | `{}` | `{id}` |
| `conv.load` | app, observer | `{id}` | `{id,title,messages}` |
| `conv.delete` | app | `{id}` | `{ok:true}` |

### 6.4 配置

| 方法 | 角色 | P | R |
|---|---|---|---|
| `config.get` | app, observer | `{}` | 完整 config，**`api_key` 替换为 `"***"`，另有 `api_key_set` 布尔** |
| `config.save` | app | 任意 config 子集 | `{ok:true}`；**服务端强制剥离 `api_key`**，收到也忽略 |

`config.get` 对 `observer` 额外剥离 `base_url`、`provider_id`（减少信息面）。`api_key` 对所有角色都是 `***`。

### 6.5 文件

**无路径黑名单**（用户明确要求全盘）。每次访问写审计日志。

| 方法 | 角色 | P | R |
|---|---|---|---|
| `fs.list` | app | `{path}` | `{entries:[{name,is_dir,size,mtime}]}`，目录按名排序，最多 5000 项 |
| `fs.read` | app | `{path, offset?, len?}` | `{data_b64, size, eof}`，单次最多 256 KiB |
| `fs.stat` | app | `{path}` | `{size, mtime, is_dir}` |
| `fs.write` | app | `{path, data_b64, offset?}` | `{written}`，**需审批** |
| `fs.mkdir` | app | `{path}` | `{ok:true}`，**需审批** |
| `fs.delete` | app | `{path}` | `{ok:true}`，**需审批** |
| `fs.roots` | app | `{}` | `{roots:[{name,path}]}` |

`observer` 调用任何 `fs.*` → `forbidden`。

`fs.write` / `fs.mkdir` / `fs.delete` 走**审批通道**：PC 端弹出与工具调用同一套审批 UI，手机端 `approval.request` 也能看到。拒绝 → `{ok:false,e:"rejected"}`。

### 6.6 状态与设备

| 方法 | 角色 | P | R |
|---|---|---|---|
| `status.get` | app, observer | `{}` | `{pet_state, busy, connected_devices, balance?}` |
| `status.event` | pc→app 事件 | — | `{pet_state, busy}` |
| `device.list` | app | `{}` | `{devices:[{dev_id,name,role,added_at,last_seen,online}]}` |
| `device.revoke` | app | `{dev_id}` | `{ok:true}` |
| `server.ping` | 全体 | `{}` | `{server_ts}` |

---

## 7. 单飞与停止

- **全局单飞**：任何时刻只有一轮 agent 在跑。PC 本地 UI 和手机共用这条锁。
- 忙时 app 的 `chat.send` → `{ok:false,e:"busy"}`。
- `chat.stop` → PC 侧 `CancelToken.set()`，**1 秒内**：
  1. 关闭正在读的 HTTP 流（`response.close()`）；
  2. 杀掉正在跑的子进程树（Windows: `taskkill /T /F /PID`）；
  3. 丢弃本轮未持久化的历史（回滚到本轮开始前的 `history` 快照）；
  4. 向 app 推 `chat.delta{text:"",done:true,cancelled:true}`。
- PC 本地 UI 也要有停止按钮，同样调 `/api/stop`。

---

## 8. 断线与离线

- 心跳：20 秒无任何帧则发 `ping`；40 秒无响应则判定断线。
- 重连退避：1, 2, 4, 8, 16, 30, 30, 30… 秒，带 ±20% 抖动。
- **不做离线消息补发**（用户明确选择）。PC 不在线时：
  - 中继收到 `data` 帧但没有 `pc` 连接 → 不解密、不回显，中继无法解密，所以这个判断由**中继依据"是否有 pc 角色在线"**做出：
    中继看到 `f == "app"` 的 `data` 帧且 room 内无 `pc` 连接 → 回 `error{code:"offline"}`。
  - app 收到 `offline` → 弹提示 **「电脑端已离线，请开启电脑后再试」**。
- 重连后 app 主动调 `approval.list` + `conv.list` 恢复状态。

---

## 9. 中继行为规范

`RelayRoom`（Durable Object）与 `relay/dev_server.py` 必须行为一致：

1. 连接建立后**第一帧必须是合法 `hello`**；10 秒内没收到 → 关闭。
2. room 内 `pc` 唯一：已有 pc 连接时新 pc 连接 → 踢掉旧 pc（旧连接收 `bye{reason:"replaced"}`）。
3. `app` / `observer` 可多台并存，无上限（但 app 建议 ≤ 4）。
4. `seq` **不做去重或排序**（加密层已用 AAD 保证），中继只透传。
5. 单帧上限 **1 MiB**，超出 → `error{code:"too_large"}` 并关闭。
6. 转发规则：
   - `pc` 发的 → 所有 `app` + 所有 `observer`
   - `app` 发的 → `pc`
   - `observer` 发的 → `pc`
7. **中继不检查 observer 调了什么方法**，一律转发给 `pc`，由 PC 端按方法表
   拒绝越权（`forbidden`）。

   为什么不在中继拦：中继看不到明文方法名，它根本没能力区分
   `conv.list`（允许）和 `conv.delete`（禁止）。硬拦的结果是观察端连
   会话列表都拉不到，功能直接废掉。

   安全性由两层保证：
   - **密码学层**：AAD 绑定发送方角色（§3.2），observer 无法伪造 app 身份的帧；
   - **服务端层**：PC 端 `bridge.dispatch` 按 §6 方法表白名单校验，
     observer 任何写操作一律 `forbidden`。

   即"中继只保证谁发的，PC 保证能做什么"。
8. 速率：单连接 **120 帧 / 10 秒**，超出 → `error{code:"rate_limited"}` 并断开。
9. 中继不落任何 `data` 帧内容。`hello` 元数据（dev id、角色、时间）可记入日志用于排障。

---

## 10. 版本协商

- 客户端 `hello.v` != 1 → 中继回 `error{code:"version"}` 并关闭。
- 加密后的首个 `data` 帧应为 `{"m":"server.ping"}` / `{"m":"server.pong"}`，两端也各自校验协议版本（放在 `data` 帧的 `p.v` 里），不匹配则 app 提示「请升级应用」。
