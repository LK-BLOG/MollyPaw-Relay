"""中继契约测试 —— Python 本地中继必须与 Durable Object 行为一致。

这些断言来自 PROTOCOL.md §9「中继行为规范」。
两边（Python / JS）跑同一组用例，任何一边跑偏都会被抓住。

放在这个仓库里（而不是只放主仓库），是为了让 Relay 仓库能独立 CI：
契约测试跟着中继代码一起走，改了协议就得改这里。
"""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from relay.dev_server import DevRelay, PROTOCOL_VERSION  # noqa: E402

import websockets.sync.client as ws_client  # noqa: E402

ROOM_A = "a" * 32
ROOM_B = "b" * 32
PORT = 18977


@pytest.fixture(scope="module")
def relay():
    r = DevRelay("127.0.0.1", PORT)
    r.start_background()
    yield r
    r.shutdown()


def url(room, base=None):
    return f"ws://127.0.0.1:{PORT}/server?room={room}"


def hello(role, room=ROOM_A, dev="dev-1", **extra):
    frame = {"v": PROTOCOL_VERSION, "t": "hello", "r": room, "f": role, "dev": dev}
    frame.update(extra)
    return json.dumps(frame)


def data_frame(text="payload", seq=1, role="app", room=ROOM_A, msg_id="m1"):
    return json.dumps({
        "v": PROTOCOL_VERSION, "t": "data", "r": room, "f": role,
        "seq": seq, "id": msg_id, "n": "AAAA", "c": "BBBB",
    })


def recv(ws, timeout=3.0):
    return json.loads(ws.recv(timeout=timeout))


def drain(ws, timeout=0.4):
    out = []
    while True:
        try:
            out.append(json.loads(ws.recv(timeout=timeout)))
        except Exception:
            return out


# --------------------------------------------------------------------------
# 握手
# --------------------------------------------------------------------------


def test_first_frame_must_be_hello(relay):
    with ws_client.connect(url(ROOM_A)) as ws:
        ws.send(data_frame())
        frame = recv(ws)
        assert frame["code"] == "bad_frame"


def test_hello_requires_valid_room(relay):
    with ws_client.connect(url(ROOM_A)) as ws:
        ws.send(hello("app", room="zzz"))
        assert recv(ws)["code"] == "bad_room"


def test_hello_room_must_match_url(relay):
    with ws_client.connect(url(ROOM_B)) as ws:
        ws.send(hello("app", room=ROOM_A))
        assert recv(ws)["code"] == "bad_room"


def test_hello_rejects_bad_role(relay):
    with ws_client.connect(url(ROOM_A)) as ws:
        ws.send(hello("admin"))
        assert recv(ws)["code"] == "bad_role"


def test_bad_room_query_param_rejected(relay):
    with pytest.raises(Exception):
        with ws_client.connect(f"ws://127.0.0.1:{PORT}/server?room=nope"):
            pass


def test_version_mismatch_rejected(relay):
    with ws_client.connect(url(ROOM_A)) as ws:
        ws.send(json.dumps({"v": 99, "t": "hello", "r": ROOM_A, "f": "app"}))
        assert recv(ws)["code"] == "version"


def test_binary_frame_rejected(relay):
    with ws_client.connect(url(ROOM_A)) as ws:
        ws.send(b"\x00\x01\x02")
        assert recv(ws)["code"] == "bad_frame"


# --------------------------------------------------------------------------
# 转发
# --------------------------------------------------------------------------


def test_pc_to_app_and_observer(relay):
    with ws_client.connect(url(ROOM_A)) as pc, \
         ws_client.connect(url(ROOM_A)) as app, \
         ws_client.connect(url(ROOM_A)) as obs:
        pc.send(hello("pc"))
        app.send(hello("app"))
        obs.send(hello("observer"))
        drain(app); drain(obs); drain(pc)

        pc.send(data_frame(role="pc", text="from-pc"))
        got_app = [f for f in drain(app) if f["t"] == "data"]
        got_obs = [f for f in drain(obs) if f["t"] == "data"]
        assert len(got_app) == 1 and got_app[0]["c"] == "BBBB"
        assert len(got_obs) == 1 and got_obs[0]["c"] == "BBBB"


def test_app_to_pc(relay):
    with ws_client.connect(url(ROOM_A)) as pc, \
         ws_client.connect(url(ROOM_A)) as app:
        pc.send(hello("pc"))
        app.send(hello("app"))
        drain(app); drain(pc)

        app.send(data_frame(role="app"))
        got = [f for f in drain(pc) if f["t"] == "data"]
        assert len(got) == 1 and got[0]["f"] == "app"


def test_observer_frames_reach_pc(relay):
    """观察端的帧**照样转发**给 pc —— 越权判定在 pc 端做。

    理由：中继看不到明文，分不清 conv.list（允许）和 conv.delete（禁止）。
    硬拦的话观察端连会话列表都拉不到，功能直接废掉。
    """
    with ws_client.connect(url(ROOM_A)) as pc, \
         ws_client.connect(url(ROOM_A)) as obs:
        pc.send(hello("pc"))
        obs.send(hello("observer"))
        drain(pc); drain(obs)

        obs.send(data_frame(role="observer", msg_id="obs-1"))
        got = [f for f in drain(pc) if f["t"] == "data"]
        assert len(got) == 1, "观察端的帧应转发给 pc"
        assert got[0]["f"] == "observer"
        assert got[0]["id"] == "obs-1"


def test_offline_error_when_no_pc(relay):
    with ws_client.connect(url(ROOM_B)) as app:
        app.send(hello("app", room=ROOM_B))
        drain(app)
        app.send(data_frame(role="app", room=ROOM_B))
        frame = recv(app)
        assert frame["code"] == "offline"
        assert "电脑端已离线" in frame["msg"]


def test_role_spoof_rejected(relay):
    """app 声称自己是 pc —— 必须被拒。"""
    with ws_client.connect(url(ROOM_A)) as app:
        app.send(hello("app"))
        drain(app)
        app.send(data_frame(role="pc"))
        assert recv(app)["code"] == "bad_role"


# --------------------------------------------------------------------------
# 房间隔离 / pc 唯一 / 心跳
# --------------------------------------------------------------------------


def test_rooms_are_isolated(relay):
    with ws_client.connect(url(ROOM_A)) as pc_a, \
         ws_client.connect(url(ROOM_B)) as app_b:
        pc_a.send(hello("pc", room=ROOM_A))
        app_b.send(hello("app", room=ROOM_B))
        drain(pc_a); drain(app_b)

        pc_a.send(data_frame(role="pc", room=ROOM_A))
        assert not [f for f in drain(app_b) if f["t"] == "data"]


def test_second_pc_replaces_first(relay):
    with ws_client.connect(url(ROOM_A)) as pc1, \
         ws_client.connect(url(ROOM_A)) as pc2:
        pc1.send(hello("pc", dev="first"))
        drain(pc1)
        pc2.send(hello("pc", dev="second"))
        drain(pc2)
        frames = drain(pc1)
        assert any(f["t"] == "bye" and f.get("reason") == "replaced" for f in frames)


def test_ping_pong(relay):
    with ws_client.connect(url(ROOM_A)) as app:
        app.send(hello("app"))
        drain(app)
        app.send(json.dumps({
            "v": PROTOCOL_VERSION, "t": "ping", "r": ROOM_A, "f": "app", "ts": 1,
        }))
        frame = recv(app)
        assert frame["t"] == "pong" and frame["f"] == "app"


def test_presence_broadcast(relay):
    with ws_client.connect(url(ROOM_A)) as pc, \
         ws_client.connect(url(ROOM_A)) as app:
        pc.send(hello("pc"))
        drain(pc)
        app.send(hello("app"))
        frames = []
        for _ in range(4):
            frames.extend(drain(pc, timeout=0.5))
        presence = [f for f in frames if f["t"] == "presence"]
        assert presence
        assert presence[-1]["pc"] == 1
        assert presence[-1]["app"] == 1
