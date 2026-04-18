/**
 * Validation cron worker — fires every 6 hours via CF Cron Trigger.
 *
 * Generates a short-lived HMAC-SHA256 token (same scheme as the backend's
 * verify_admin_hmac) and POSTs to /admin/validation/run-due on Render.
 * Also calls /admin/validation/prune once daily (on the 00:xx UTC firing).
 *
 * Required Worker env vars (set via wrangler secret / CF dashboard):
 *   BACKEND_URL            — e.g. https://reproute-backend.onrender.com
 *   VALIDATION_HMAC_SECRET — must match the backend env var exactly
 */

async function makeHmacToken(secret, timestamp) {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const msgData = encoder.encode(String(timestamp));
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, msgData);
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function callBackend(env, path, method = "POST") {
  const ts = Math.floor(Date.now() / 1000);
  const token = await makeHmacToken(env.VALIDATION_HMAC_SECRET, ts);
  const url = `${env.BACKEND_URL.replace(/\/$/, "")}${path}`;
  const resp = await fetch(url, {
    method,
    headers: {
      "X-Admin-Timestamp": String(ts),
      "X-Admin-Token": token,
      "Content-Type": "application/json",
    },
  });
  const body = await resp.text();
  return { status: resp.status, body };
}

export default {
  // fetch handler required by Workers runtime even for cron-only workers
  async fetch(_request, _env) {
    return new Response("validation-cron worker — no fetch interface", { status: 200 });
  },

  async scheduled(event, env, ctx) {
    const hour = new Date(event.scheduledTime).getUTCHours();

    // Run-due: every 6-hour firing
    const runDue = await callBackend(env, "/admin/validation/run-due?limit=50");
    console.log(`run-due status=${runDue.status} body=${runDue.body}`);

    // Prune: only on the midnight UTC firing (hour 0) to keep it once-daily
    if (hour === 0) {
      const prune = await callBackend(env, "/admin/validation/prune?retain_days=30");
      console.log(`prune status=${prune.status} body=${prune.body}`);
    }

    ctx.waitUntil(Promise.resolve());
  },
};
