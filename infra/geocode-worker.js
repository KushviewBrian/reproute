export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") || "";
    const limit = url.searchParams.get("limit") || "5";
    if (!q) return new Response(JSON.stringify({ features: [] }), { headers: { "content-type": "application/json" } });

    const key = `geocode:${q.toLowerCase()}:${limit}`;
    const cached = await env.GEOCODE_CACHE.get(key);
    if (cached) {
      return new Response(cached, { headers: { "content-type": "application/json", "x-cache": "HIT" } });
    }

    const upstream = env.PHOTON_BASE_URL || "https://photon.komoot.io/api";
    const upstreamUrl = `${upstream}?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`;
    const resp = await fetch(upstreamUrl, { method: "GET" });
    if (!resp.ok) {
      return new Response(JSON.stringify({ features: [] }), {
        status: 200,
        headers: { "content-type": "application/json", "x-degraded": "true" },
      });
    }

    const text = await resp.text();
    await env.GEOCODE_CACHE.put(key, text, { expirationTtl: 60 * 60 * 24 });
    return new Response(text, { headers: { "content-type": "application/json", "x-cache": "MISS" } });
  },
};
