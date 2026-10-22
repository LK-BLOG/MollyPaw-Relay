/**
 * GET /api/health — 中继健康检查。
 *
 * 这个页面被官网用来显示"中继在线"。它只报告服务自身状态，
 * 不泄露任何房间/设备信息。
 */
export async function onRequestGet(context) {
  const { env } = context;

  const bound = Boolean(env.RELAY_ROOM);

  return new Response(
    JSON.stringify({
      ok: bound,
      service: 'mollypaw-relay',
      version: Number(env.RELAY_VERSION || 1),
      protocol: 1,
      do_bound: bound,
      ts: Date.now(),
    }),
    {
      status: bound ? 200 : 503,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'cache-control': 'no-store',
        'access-control-allow-origin': '*',
      },
    }
  );
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET, OPTIONS',
      'access-control-allow-headers': 'content-type',
    },
  });
}
