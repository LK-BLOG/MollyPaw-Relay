"""MollyPaw Relay — 本地开发中继（Python）。

用途：
  1. 本地端到端联调（不开公网、不依赖 Cloudflare）
  2. pytest 契约测试的基准实现之一

**行为必须与 worker/src/relay-room.js 完全一致** —— tests/test_relay_contract.py
会对两边跑同一组断言。改一边必须改另一边。

它和 JS 版一样是盲中继：不解密、不落盘任何 data 帧内容。
"""
import json
import os
import sys
import threading
import time
import weakref

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets.sync.server as ws_sync  # noqa: E402

PROTOCOL_VERSION = 1
MAX_FRAME = 1024 * 1024
RATE_WINDOW = 10.0
RATE_MAX = 120
HELLO_DEADLINE = 10.0

ROLE_PC = "pc"
ROLE_APP = "app"
ROLE_OBSERVER = "observer"
VALID_ROLES = {ROLE_PC, ROLE_APP, ROLE_OBSERVER}

# hello 里允许转发的字段白名单 —— 防止将来有人往里塞秘密。
# 必须与 worker/src/relay-room.js 的 HELLO_FIELDS 一致。
HELLO_FIELDS = ("v", "t", "r", "f", "dev", "eph", "hs", "pair_salt", "ts")


def _relayable_hello(frame) -> str:
    """按白名单裁剪 hello 再序列化。"""
    out = {k: frame[k] for k in HELLO_FIELDS if k in frame}
    return json.dumps(out, ensure_ascii=False)


def _is_room(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(c in "0123456789abcdef" for c in value)
    )


def _err(code, msg=""):
    return json.dumps({"v": PROTOCOL_VERSION, "t": "error", "code": code, "msg": msg})


def _bye(room, role, reason):
    return json.dumps(
        {"v": PROTOCOL_VERSION, "t": "bye", "r": room, "f": role, "reason": reason}
    )


class _Session:
    """一个 WebSocket 连接的会话状态。"""

    __slots__ = ("ws", "role", "dev", "room", "hello", "connected_at", "last_seen",
                 "frames", "window_start")

    def __init__(self, ws, room):
        self.ws = ws
        self.role = None
        self.dev = None
        self.room = room
        self.hello = None          # 收到并裁剪过的 hello 原始文本，供回放
        self.connected_at = time.time()
        self.last_seen = self.connected_at
        self.frames = 0
        self.window_start = self.connected_at


class RelayRoom:
    """一个房间。与 Durable Object 的 RelayRoom 一一对应。"""

    def __init__(self, name):
        self.name = name
        self._sessions = []
        self._lock = threading.RLock()

    # -- 内部工具 ----------------------------------------------------------

    def _all(self):
        with self._lock:
            return list(self._sessions)

    def _by_role(self, role):
        return [s for s in self._all() if s.role == role]

    @staticmethod
    def _send(session, text):
        try:
            session.ws.send(text)
        except Exception:
            pass

    @staticmethod
    def _close(session, code=1000, reason=""):
        try:
            session.ws.close(reason=reason)
        except Exception:
            pass

    def _broadcast_presence(self):
        payload = json.dumps({
            "v": PROTOCOL_VERSION,
            "t": "presence",
            "r": self.name,
            "pc": len(self._by_role(ROLE_PC)),
            "app": len(self._by_role(ROLE_APP)),
            "observer": len(self._by_role(ROLE_OBSERVER)),
        })
        for s in self._all():
            if s.role:
                self._send(s, payload)

    # -- 连接入口 ----------------------------------------------------------

    def attach(self, ws):
        session = _Session(ws, self.name)
        with self._lock:
            self._sessions.append(session)
        try:
            for raw in ws:
                if not self._handle(session, raw):
                    break
        except Exception:
            pass
        finally:
            with self._lock:
                if session in self._sessions:
                    self._sessions.remove(session)
            if session.role:
                self._broadcast_presence()

    # -- 帧处理 ------------------------------------------------------------

    def _handle(self, session, raw) -> bool:
        """处理一帧；返回 False 表示应当断开。"""
        if isinstance(raw, (bytes, bytearray)):
            self._send(session, _err("bad_frame", "binary frames are not supported"))
            self._close(session, 1002, "binary")
            return False

        if len(raw) > MAX_FRAME:
            self._send(session, _err("too_large"))
            self._close(session, 1009, "too_large")
            return False

        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            self._send(session, _err("bad_frame", "not json"))
            self._close(session, 1003, "bad_frame")
            return False

        now = time.time()
        session.last_seen = now

        # 速率限制
        if now - session.window_start > RATE_WINDOW:
            session.window_start = now
            session.frames = 0
        session.frames += 1
        if session.frames > RATE_MAX:
            self._send(session, _err("rate_limited"))
            self._close(session, 1008, "rate_limited")
            return False

        if frame.get("v") != PROTOCOL_VERSION:
            self._send(session, _err("version", f"server speaks v{PROTOCOL_VERSION}"))
            self._close(session, 1002, "version")
            return False

        ftype = frame.get("t")

        # 第一帧必须是 hello
        if not session.role:
            if ftype != "hello":
                self._send(session, _err("bad_frame", "first frame must be hello"))
                self._close(session, 1002, "no_hello")
                return False
            if now - session.connected_at > HELLO_DEADLINE:
                self._send(session, _err("bad_frame", "hello too late"))
                self._close(session, 1002, "hello_late")
                return False
            return self._handle_hello(session, frame)

        if frame.get("r") != session.room:
            self._send(session, _err("bad_room"))
            return True

        if ftype == "ping":
            self._send(session, json.dumps({
                "v": PROTOCOL_VERSION, "t": "pong",
                "r": session.room, "f": session.role, "ts": int(now * 1000),
            }))
            return True

        if ftype in ("pong", "bye"):
            return True

        if ftype != "data":
            self._send(session, _err("bad_frame", f"unexpected frame type {ftype}"))
            return True

        if frame.get("f") != session.role:
            self._send(session, _err("bad_role"))
            return True

        self._route(session, raw)
        return True

    def _handle_hello(self, session, frame) -> bool:
        room = frame.get("r")
        if not _is_room(room):
            self._send(session, _err("bad_room"))
            self._close(session, 1002, "bad_room")
            return False
        if room != session.room:
            self._send(session, _err("bad_room", "hello room does not match url room"))
            self._close(session, 1002, "bad_room")
            return False

        role = frame.get("f")
        if role not in VALID_ROLES:
            self._send(session, _err("bad_role"))
            self._close(session, 1002, "bad_role")
            return False

        # pc 唯一：新 pc 顶掉旧 pc
        if role == ROLE_PC:
            for other in self._by_role(ROLE_PC):
                if other is session:
                    continue
                self._send(other, _bye(room, ROLE_PC, "replaced"))
                other.role = None
                self._close(other, 1000, "replaced")

        wire = _relayable_hello(frame)

        # 新成员的 hello 转给已有成员（密钥交换靠它，PROTOCOL.md §3.1）
        for other in self._all():
            if other is session:
                continue
            if other.role:
                self._send(other, wire)

        session.role = role
        session.dev = frame.get("dev")
        session.hello = wire
        session.room = room

        # 已有成员的 hello 回放给新成员，省掉一次往返
        for other in self._all():
            if other is session:
                continue
            if other.role and other.hello:
                self._send(session, other.hello)

        self._broadcast_presence()
        return True

    def _route(self, session, raw):
        if session.role == ROLE_PC:
            for target in self._all():
                if target is session:
                    continue
                if target.role in (ROLE_APP, ROLE_OBSERVER):
                    self._send(target, raw)
            return

        # app / observer -> pc（pc 不在线则回离线提示）
        #
        # 中继**不检查 observer 调了什么方法**：它看不到明文，没能力区分
        # conv.list（允许）和 conv.delete（禁止）。越权由 PC 端按方法表拒绝。
        # 中继只保证"这帧是谁发的"（AAD 已绑定角色）。
        pcs = self._by_role(ROLE_PC)
        if not pcs:
            self._send(session, _err("offline", "电脑端已离线，请开启电脑后再试"))
            return
        for target in pcs:
            self._send(target, raw)


class DevRelay:
    """本地中继服务器。"""

    def __init__(self, host="127.0.0.1", port=18767):
        self.host = host
        self.port = port
        self._rooms = {}
        self._rooms_lock = threading.Lock()
        self._server = None

    def room(self, name) -> RelayRoom:
        with self._rooms_lock:
            if name not in self._rooms:
                self._rooms[name] = RelayRoom(name)
            return self._rooms[name]

    _ROOMS_BY_CONN = weakref.WeakKeyDictionary()

    @staticmethod
    def _extract_room(request):
        """从握手请求里取 ?room=；非法则返回 None。"""
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(request.path).query)
        room = (query.get("room") or [""])[0]
        return room if _is_room(room) else None

    def _process_request(self, connection, request):
        """握手前校验 room，非法直接拒绝，返回 HTTP 400。"""
        room = self._extract_room(request)
        if room is None:
            return connection.respond(400, "missing or malformed room query param\n")
        DevRelay._ROOMS_BY_CONN[connection] = room
        return None

    def _handler(self, ws):
        room = DevRelay._ROOMS_BY_CONN.get(ws)
        if not room:
            # 正常流程走不到这里（process_request 已拦），兜底
            ws.close()
            return
        self.room(room).attach(ws)

    def serve_forever(self):
        from websockets.sync.server import ServerConnection

        self._server = ws_sync.serve(
            self._handler,
            self.host,
            self.port,
            max_size=MAX_FRAME,
            process_request=self._process_request,
        )
        self._server.serve_forever()

    def start_background(self):
        """后台线程启动，返回线程对象。"""
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        # 等端口就绪，避免测试抢跑
        import socket

        for _ in range(100):
            with socket.socket() as s:
                if s.connect_ex((self.host, self.port)) == 0:
                    return thread
            time.sleep(0.02)
        raise RuntimeError(f"dev relay did not start on {self.host}:{self.port}")

    def shutdown(self):
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MollyPaw local relay (dev)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18767)
    args = parser.parse_args()

    relay = DevRelay(args.host, args.port)
    print(f"[MollyPaw Relay] listening on ws://{args.host}:{args.port}/server?room=<32 hex>")
    relay.serve_forever()


if __name__ == "__main__":
    main()
