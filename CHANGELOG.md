# CHANGELOG

本文件是 **GitHub Release 文案的唯一来源**，发版时整段原样抠出来当发布说明。

## [0.0.0.2.1] - 2026-10-24

### 新增

- 官网下载中心按主站样式重做：版本号实时取自 GitHub Releases、
  六条国内镜像测速并自动选最快节点、镜像行始终占位（不再空白塌陷）
- 版本状态机三态：能取到版本 / 仓库没有版本 / 网络取不到，
  各给各的提示，不再一律显示「暂无可下载版本」

### 修复

- 下载区在「没取到 Release」时整块失效：按钮是死链、镜像列表为空
- `.dl-size` / `.dl-via` 被全局 `em` 高亮规则染成深底深字，还有一条多余橙色竖条
- 全局 `a { text-decoration: underline }` 把按钮和 Logo 也一起加了划线

[0.0.0.2.1]: https://github.com/LK-BLOG/MollyPaw-Relay/compare/beta-0.0.0.2.0...beta-0.0.0.2.1

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
