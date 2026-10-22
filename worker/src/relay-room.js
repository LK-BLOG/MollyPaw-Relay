/**
 * MollyPaw Relay — RelayRoom Durable Object
 *
 * PROTOCOL.md §9 的实现。这是一个**盲中继**：
 *   - 从不解析 data 帧的 `n` / `c` 字段，只做路由。
 *   - 不落任何消息内容。hello 的公开字段（role/dev/eph/hs）用于路由与密钥交换。
 *
 * 行为必须与 `relay/dev_server.py` 完全一致。
 */

const PROTOCOL_VERSION = 1;
const MAX_FRAME = 1024 * 1024; // 1 MiB
const RATE_WINDOW_MS = 10 * 1000;
const RATE_MAX_FRAMES = 120;
const HELLO_DEADLINE_MS = 10 * 1000;

const ROLE_PC = "pc";
const ROLE_APP = "app";
const ROLE_OBSERVER = "observer";
const VALID_ROLES = new Set([ROLE_PC, ROLE_APP, ROLE_OBSERVER]);

const ROOM_RE = /^[0-9a-f]{32}$/;

/** hello 里允许转发的字段白名单 —— 防止将来有人往里塞秘密。 */
const HELLO_FIELDS = ["v", "t", "r", "f", "dev", "eph", "hs", "pair_salt", "ts"];

function err(code, msg = "") {
  return JSON.stringify({ v: PROTOCOL_VERSION, t: "error", code, msg });
}

function bye(room, role, reason) {
  return JSON.stringify({ v: PROTOCOL_VERSION, t: "bye", r: room, f: role, reason });
}

/** 按白名单裁剪 hello，再序列化。 */
function relayableHello(frame) {
  const out = {};
  for (const key of HELLO_FIELDS) {
    if (frame[key] !== undefined) out[key] = frame[key];
  }
  return JSON.stringify(out);
}

export class RelayRoom {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  static _defaultMeta() {
    return {
      role: null,
      dev: null,
      room: null,
      hello: null,
      connectedAt: Date.now(),
      lastSeen: Date.now(),
      frames: 0,
      windowStart: Date.now(),
    };
  }

  async fetch(request) {
    const upgrade = (request.headers.get("Upgrade") || "").toLowerCase();
    if (upgrade !== "websocket") {
      return new Response("MollyPaw relay expects a WebSocket upgrade.", {
        status: 426,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    const url = new URL(request.url);
    const room = url.searchParams.get("room") || "";
    if (!ROOM_RE.test(room)) {
      return new Response("bad room", { status: 400 });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];

    // Hibernation API：连接空闲时不消耗时长
    this.ctx.acceptWebSocket(server);
    const meta = RelayRoom._defaultMeta();
    meta.room = room;
    server.serializeAttachment(meta);

    return new Response(null, { status: 101, webSocket: client });
  }

  _meta(ws) {
    return ws.deserializeAttachment() || RelayRoom._defaultMeta();
  }

  _save(ws, meta) {
    ws.serializeAttachment(meta);
  }

  _all() {
    return this.ctx.getWebSockets();
  }

  _byRole(role) {
    return this._all().filter((ws) => this._meta(ws).role === role);
  }

  _send(ws, text) {
    try {
      ws.send(text);
    } catch (_) {
      /* 连接已断，交给 close 处理 */
    }
  }

  _close(ws, code = 1000, reason = "") {
    try {
      ws.close(code, reason);
    } catch (_) {
      /* 忽略重复关闭 */
    }
  }

  async webSocketMessage(ws, message) {
    if (typeof message !== "string") {
      this._send(ws, err("bad_frame", "binary frames are not supported"));
      this._close(ws, 1002, "binary");
      return;
    }
    if (message.length > MAX_FRAME) {
      this._send(ws, err("too_large"));
      this._close(ws, 1009, "too_large");
      return;
    }

    let frame;
    try {
      frame = JSON.parse(message);
    } catch (_) {
      this._send(ws, err("bad_frame", "not json"));
      this._close(ws, 1003, "bad_frame");
      return;
    }

    const meta = this._meta(ws);
    const now = Date.now();
    meta.lastSeen = now;

    // ---- 速率限制 ----
    if (now - meta.windowStart > RATE_WINDOW_MS) {
      meta.windowStart = now;
      meta.frames = 0;
    }
    meta.frames += 1;
    if (meta.frames > RATE_MAX_FRAMES) {
      this._save(ws, meta);
      this._send(ws, err("rate_limited"));
      this._close(ws, 1008, "rate_limited");
      return;
    }

    // ---- 版本 ----
    if (frame.v !== PROTOCOL_VERSION) {
      this._save(ws, meta);
      this._send(ws, err("version", `server speaks v${PROTOCOL_VERSION}`));
      this._close(ws, 1002, "version");
      return;
    }

    const type = frame.t;

    // ---- 第一帧必须是 hello ----
    if (!meta.role) {
      if (type !== "hello") {
        this._save(ws, meta);
        this._send(ws, err("bad_frame", "first frame must be hello"));
        this._close(ws, 1002, "no_hello");
        return;
      }
      if (now - meta.connectedAt > HELLO_DEADLINE_MS) {
        this._send(ws, err("bad_frame", "hello too late"));
        this._close(ws, 1002, "hello_late");
        return;
      }
      this._handleHello(ws, meta, frame);
      return;
    }

    this._save(ws, meta);

    if (frame.r !== meta.room) {
      this._send(ws, err("bad_room"));
      return;
    }
    if (type === "ping") {
      this._send(
        ws,
        JSON.stringify({
          v: PROTOCOL_VERSION,
          t: "pong",
          r: meta.room,
          f: meta.role,
          ts: Date.now(),
        })
      );
      return;
    }
    if (type === "pong" || type === "bye") {
      return;
    }
    if (type !== "data") {
      this._send(ws, err("bad_frame", `unexpected frame type ${type}`));
      return;
    }

    if (frame.f !== meta.role) {
      // 声称的角色与会话不符 —— 典型的冒充尝试
      this._send(ws, err("bad_role"));
      return;
    }

    this._route(ws, meta, message);
  }

  _handleHello(ws, meta, frame) {
    const room = frame.r;
    if (!ROOM_RE.test(room || "")) {
      this._send(ws, err("bad_room"));
      this._close(ws, 1002, "bad_room");
      return;
    }
    if (room !== meta.room) {
      this._send(ws, err("bad_room", "hello room does not match url room"));
      this._close(ws, 1002, "bad_room");
      return;
    }
    const role = frame.f;
    if (!VALID_ROLES.has(role)) {
      this._send(ws, err("bad_role"));
      this._close(ws, 1002, "bad_role");
      return;
    }

    // pc 唯一：新 pc 顶掉旧 pc
    if (role === ROLE_PC) {
      for (const other of this._byRole(ROLE_PC)) {
        if (other === ws) continue;
        this._send(other, bye(room, ROLE_PC, "replaced"));
        const om = this._meta(other);
        om.role = null;
        this._save(other, om);
        this._close(other, 1000, "replaced");
      }
    }

    const wire = relayableHello(frame);

    // 新成员的 hello 转给已有成员（密钥交换靠它，PROTOCOL.md §3.1）
    for (const other of this._all()) {
      if (other === ws) continue;
      if (this._meta(other).role) this._send(other, wire);
    }

    meta.role = role;
    meta.dev = frame.dev || null;
    meta.hello = wire;
    meta.room = room;
    this._save(ws, meta);

    // 已有成员的 hello 回放给新成员，省掉一次往返
    for (const other of this._all()) {
      if (other === ws) continue;
      const om = this._meta(other);
      if (om.role && om.hello) this._send(ws, om.hello);
    }

    this._broadcastPresence(room);
  }

  _route(ws, meta, raw) {
    if (meta.role === ROLE_PC) {
      // pc -> 所有 app + 所有 observer
      for (const target of this._all()) {
        if (target === ws) continue;
        const tm = this._meta(target);
        if (tm.role === ROLE_APP || tm.role === ROLE_OBSERVER) {
          this._send(target, raw);
        }
      }
      return;
    }

    // app / observer -> pc（pc 不在线则回离线提示）
    //
    // 中继**不检查 observer 调了什么方法**：它看不到明文，没能力区分
    // conv.list（允许）和 conv.delete（禁止）。越权由 PC 端按方法表拒绝。
    // 中继只保证"这帧是谁发的"（AAD 已绑定角色）。
    const pcs = this._byRole(ROLE_PC);
    if (pcs.length === 0) {
      this._send(ws, err("offline", "电脑端已离线，请开启电脑后再试"));
      return;
    }
    for (const target of pcs) {
      this._send(target, raw);
    }
  }

  _broadcastPresence(room) {
    const presence = {
      v: PROTOCOL_VERSION,
      t: "presence",
      r: room,
      pc: this._byRole(ROLE_PC).length,
      app: this._byRole(ROLE_APP).length,
      observer: this._byRole(ROLE_OBSERVER).length,
    };
    const text = JSON.stringify(presence);
    for (const target of this._all()) {
      if (this._meta(target).role) this._send(target, text);
    }
  }

  async webSocketClose(ws) {
    const meta = this._meta(ws);
    if (meta.room) this._broadcastPresence(meta.room);
  }

  async webSocketError(ws) {
    const meta = this._meta(ws);
    if (meta.room) this._broadcastPresence(meta.room);
  }
}
