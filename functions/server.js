/**
 * MollyPaw Relay — Pages Function `/server`
 *
 * 手机和电脑都连这里：
 *   wss://mollypaw-online.pages.dev/server?room=<32 位 hex>
 *
 * 它只做一件事：把 WebSocket 请求转给 Durable Object。
 * 不改内容、不看内容、不缓存内容 —— 纯转发（PROTOCOL.md §1）。
 *
 * 之所以用 Pages Function 而不是 workers.dev：workers.dev 在国内被污染，
 * pages.dev 可用。DO 类由 mollypaw-relay-room 这个独立 Worker 提供。
 */

const ROOM_RE = /^[0-9a-f]{32}$/;

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const upgrade = (request.headers.get("Upgrade") || "").toLowerCase();
  if (upgrade !== "websocket") {
    return new Response(
      JSON.stringify({
        ok: false,
        error: "websocket_required",
        hint: "用 wss://mollypaw-online.pages.dev/server?room=<32位hex> 连接",
      }),
      {
        status: 426,
        headers: { "content-type": "application/json; charset=utf-8" },
      }
    );
  }

  const room = url.searchParams.get("room") || "";
  if (!ROOM_RE.test(room)) {
    return new Response(
      JSON.stringify({ ok: false, error: "bad_room" }),
      { status: 400, headers: { "content-type": "application/json; charset=utf-8" } }
    );
  }

  if (!env.RELAY_ROOM) {
    return new Response(
      JSON.stringify({ ok: false, error: "relay_not_bound" }),
      { status: 503, headers: { "content-type": "application/json; charset=utf-8" } }
    );
  }

  const id = env.RELAY_ROOM.idFromName(room);
  const stub = env.RELAY_ROOM.get(id);
  return stub.fetch(request);
}
