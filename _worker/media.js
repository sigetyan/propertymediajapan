// Serves /media/* (self hosted video) with HTTP range support.
// Static assets answer every request with the whole file and no length, which Safari and iOS will not play.
// The body is streamed, never buffered, so several range requests at once stay within memory limits.
// Everything else on the site is served as plain static assets without running this Worker.
const SIZES = {
  "/media/kamana/kamana-lakehouse-apartment.mp4": 2561430,
  "/media/kamana/kamana-lakehouse-film.mp4": 22606855,
  "/media/kamana/kamana-lakehouse-lakeview-luxe-room.mp4": 5748981,
  "/media/kamana/kamana-lakehouse-nest-brunch.mp4": 1964114,
  "/media/kamana/kamana-lakehouse-nest-dinner-cocktails.mp4": 4335214,
  "/media/kamana/kamana-lakehouse-private-dining.mp4": 2075793,
  "/media/kamana/kamana-lakehouse-remarkable-room.mp4": 2502716,
  "/media/kamana/kamana-lakehouse-residence-suite.mp4": 4677701,
  "/media/kamana/kamana-lakehouse-soak-hot-tubs.mp4": 7329362
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/media/')) return env.ASSETS.fetch(request);
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    const size = SIZES[url.pathname];
    if (size === undefined) return env.ASSETS.fetch(request);

    const headers = new Headers({
      'Content-Type': 'video/mp4',
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'public, max-age=2592000',
      'X-Content-Type-Options': 'nosniff',
    });

    let start = 0, end = size - 1, status = 200;
    const m = /^bytes=(\d*)-(\d*)$/.exec((request.headers.get('Range') || '').trim());
    if (m && (m[1] !== '' || m[2] !== '')) {
      if (m[1] === '') {
        start = Math.max(0, size - Number(m[2]));
      } else {
        start = Number(m[1]);
        if (m[2] !== '') end = Math.min(Number(m[2]), size - 1);
      }
      if (start >= size || start > end) {
        headers.set('Content-Range', `bytes */${size}`);
        return new Response(null, { status: 416, headers });
      }
      status = 206;
      headers.set('Content-Range', `bytes ${start}-${end}/${size}`);
    }
    const length = end - start + 1;
    headers.set('Content-Length', String(length));
    if (request.method === 'HEAD') return new Response(null, { status, headers });

    const res = await env.ASSETS.fetch(new Request(url.origin + url.pathname, { method: 'GET' }));
    if (!res.ok || !res.body) return res;

    const { readable, writable } = new FixedLengthStream(length);
    ctx.waitUntil((async () => {
      const reader = res.body.getReader();
      const writer = writable.getWriter();
      let pos = 0;
      try {
        while (pos <= end) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunkStart = pos;
          pos += value.byteLength;
          if (pos <= start) continue;
          const s = Math.max(0, start - chunkStart);
          const e = Math.min(value.byteLength, end + 1 - chunkStart);
          if (e > s) await writer.write(value.subarray(s, e));
        }
        await writer.close();
      } catch (err) {
        try { await writer.abort(err); } catch (_) {}
      } finally {
        try { await reader.cancel(); } catch (_) {}
      }
    })());
    return new Response(readable, { status, headers });
  },
};
