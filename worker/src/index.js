/**
 * MollyPaw Relay — Worker 入口，只负责导出 RelayRoom Durable Object。
 *
 * Durable Object 类**必须**由独立 Worker 导出，Pages 项目的 Function
 * 通过 `durable_objects.bindings[].script_name` 绑过来（PROTOCOL.md §1）。
 *
 * 这个 Worker 本身不对外提供 HTTP 服务；所有流量走 Pages 的 /server Function。
 */

import { RelayRoom } from "./relay-room.js";

export { RelayRoom };

export default {
  async fetch(request, env) {
    // 直接打这个 worker 的域名时，转发到同名 room 的 DO（方便本地 wrangler dev 调试）。
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response(
        JSON.stringify({ ok: true, service: "mollypaw-relay-room", version: 1 }),
        { headers: { "content-type": "application/json" } }
      );
    }

    const upgrade = (request.headers.get("Upgrade") || "").toLowerCase();
    if (upgrade !== "websocket") {
      return new Response(
        "MollyPaw RelayRoom. WebSocket endpoint is served via Pages /server.",
        { status: 426 }
      );
    }

    const room = url.searchParams.get("room") || "";
    if (!/^[0-9a-f]{32}$/.test(room)) {
      return new Response("bad room", { status: 400 });
    }
    const stub = env.RELAY_ROOM.get(env.RELAY_ROOM.idFromName(room));
    return stub.fetch(request);
  },
};
