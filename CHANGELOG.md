# CHANGELOG

## [0.0.0.2.0] - 2026-10-22

首个正式版本。

### 新增

- Durable Object 中继（`RelayRoom`）：按房间路由，盲转发
- Pages Function `/server`：把 WebSocket 请求转给 DO
- `/api/health`：健康检查
- 官网 `mollypaw-online.pages.dev`
- 本地开发用 Python 中继（`relay/dev_server.py`），行为与 DO 一致
- `PROTOCOL.md`：协议规范（唯一真源）

### 说明

- 中继**看不到任何业务内容** —— 全部是端到端加密的密文
- 观察端（observer）的帧照样转发给电脑端，越权判定在电脑端做。
  理由：中继看不到明文，硬拦的话观察端连会话列表都拿不到

[0.0.0.2.0]: https://github.com/LK-BLOG/MollyPaw-Relay/releases/tag/beta-0.0.0.2.0
