# CHANGELOG

本文件是 **GitHub Release 文案的唯一来源**，发版时整段原样抠出来当发布说明。

## [0.0.0.2.0] - 2026-10-22

首个正式版本。MollyPaw 手机端 ↔ 电脑端的中继服务器。

### 新增

- **Durable Object 中继**（`RelayRoom`）：按房间路由，盲转发
- **Pages Function `/server`**：把 WebSocket 请求转给 DO
- `/api/health`：健康检查
- 官网 `mollypaw-online.pages.dev`
- `PROTOCOL.md`：协议规范（唯一真源）

### 说明

- 中继**看不到任何业务内容** —— 全部是端到端加密的密文
- 观察端（observer）的帧照样转发给电脑端，越权判定在电脑端做。
  理由：中继看不到明文，硬拦的话观察端连会话列表都拿不到
- 本地开发用 Python 中继（`relay/dev_server.py`），行为与 DO 一致

### 下载

- 无二进制产物，Pages 自动部署到 `mollypaw-online.pages.dev`

### 验证

- 16 项协议契约测试通过

[0.0.0.2.0]: https://github.com/LK-BLOG/MollyPaw-Relay/releases/tag/beta-0.0.0.2.0
