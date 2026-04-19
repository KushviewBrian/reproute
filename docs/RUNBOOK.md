# RepRoute Operational Runbook

Last updated: April 19, 2026  
Incident owner: Brian  
On-call path: direct — no pager rotation for pilot phase

---

## 1. Health check

```bash
curl -s https://reproute-backend.onrender.com/health | python3 -m json.tool
```

Expected response:
```json
{"status": "ok", "db": "ok", "redis": "ok"}
```

Any non-`ok` field means the named dependency is down. Follow the section for that dependency below.

---

## 2. Triggering a data ingestion run

### Prerequisites
- `INGEST_DATABASE_URL` — direct Supabase connection string (not the pooler URL)
- `data/indianapolis_places.parquet` — current Overture extract for the metro

### Run
```bash
cd /Users/brian/reproute
python scripts/ingest_overture.py \
  --parquet data/indianapolis_places.parquet \
  --database-url "$INGEST_DATABASE_URL"
```

### What it does
1. Upserts business rows from the parquet file
2. Classifies each business into an insurance class
3. After the refresh, marks rows not seen in this run as `possibly_closed`
4. Logs a `stale_record_update` line with row count to stdout

### Verifying it worked
```bash
# Row count and classification distribution
psql "$INGEST_DATABASE_URL" -c \
  "SELECT insurance_class, count(*) FROM business GROUP BY 1 ORDER BY 2 DESC LIMIT 15;"
```

Stale-record check:
```bash
psql "$INGEST_DATABASE_URL" -c \
  "SELECT count(*) FROM business WHERE operating_status = 'possibly_closed';"
```

---

## 3. Quota exhaustion

### ORS (routing) quota exhausted
**Symptom:** Route creation returns a GeoJSON with `properties.degraded = true`; audit log shows `ors_all_attempts_failed`.

**What happens automatically:** The routing service falls back to a straight-line mock route. Users see a route and leads, but the path is not road-accurate. A `degraded` banner should be shown in the UI if the front end checks the flag.

**Fix:**
1. Check ORS dashboard at https://openrouteservice.org/dev/#/home for quota reset time
2. If quota is permanently exhausted, upgrade the ORS plan or wait for the monthly reset
3. No restart needed — the retry + fallback is automatic on every request

### Photon (geocoding) quota / outage
**Symptom:** Address search returns POC fallback results (Indianapolis coordinates for any query); audit log shows `geocode_all_attempts_failed`.

**What happens automatically:** Geocode service falls back to the built-in POC city lookup. Route creation may place waypoints at wrong coordinates.

**Fix:**
1. Check https://photon.komoot.io — if the public instance is down, wait for recovery (usually < 1 hour)
2. Alternative: point `GEOCODE_WORKER_URL` at a self-hosted Photon instance or `https://nominatim.openstreetmap.org/search?q={q}&format=json` (different response shape — requires geocode_service.py update)
3. Set `GEOCODE_WORKER_URL` in Render env vars → redeploy

### Overpass (OSM enrichment) quota / outage
**Symptom:** `osm_enriched_at` is being set but `osm_phone` / `osm_website` are null; audit log shows `overpass_all_attempts_failed`.

**What happens automatically:** Enrichment is skipped for that business; `osm_enriched_at` is still written so the 30-day freshness gate prevents hammering a downed endpoint.

**Fix:**
1. Try alternate endpoint: set `OVERPASS_ENDPOINT=https://overpass.kumi.systems/api/interpreter` in Render env vars
2. Increase timeout if latency is the issue: set `OVERPASS_TIMEOUT_SECONDS=15`
3. No restart needed after env var change on Render — service reloads automatically

### Clerk (authentication) quota / outage
**Symptom:** All authenticated requests return 401; Clerk dashboard shows incident.

**What happens automatically:** Nothing — auth is hard-gated. Users cannot log in.

**Fix:**
1. Check https://status.clerk.com
2. If Clerk is down: no workaround for pilot phase — notify pilot users and wait
3. If JWKS cache is stale: restart the Render service to force a fresh JWKS fetch (`render restart` or via dashboard)

### Validation cap reached
**Symptom:** `POST /leads/{id}/validate` returns 429 with `"detail": "Validation cap exceeded"`.

**Current caps:** 50/day global, 2000/month global, 15/day per user.

**Fix:**
- Daily cap resets at midnight UTC automatically (Redis key TTL = 48h)
- To check current usage:
  ```bash
  redis-cli -u "$REDIS_URL" get "validation:global:day:$(date +%Y-%m-%d)"
  redis-cli -u "$REDIS_URL" get "validation:global:month:$(date +%Y-%m)"
  ```
- To raise caps temporarily (pilot only): update `VALIDATION_DAILY_CAP` in Render env vars

---

## 4. Backend outage on Render

### Render service is down / sleeping
Free-tier Render services sleep after 15 minutes of inactivity.

**Fix:**
```bash
# Wake it up
curl -s https://reproute-backend.onrender.com/health
# First request takes ~30s on free tier to cold-start
```

For pilot, upgrade to Render Starter ($7/mo) to prevent sleeping.

### Render deploy failed
1. Go to Render dashboard → reproute-backend → **Deploys**
2. Click the failed deploy → read the build log
3. Common causes:
   - `requirements.txt` dependency conflict → check pip output
   - Missing env var → look for `RuntimeError` or `ValidationError` at startup
   - Migration failed → see section 5

### Rolling back a bad deploy
```bash
# Via Render dashboard:
# Deploys tab → find the last good deploy → click "Rollback to this deploy"

# Or via git:
git revert HEAD --no-edit
git push origin main
# Render auto-deploys on push to main
```

---

## 5. Database

### Running migrations
```bash
cd backend
DATABASE_URL="$PRODUCTION_DATABASE_URL" alembic upgrade head
```

Migrations are also run automatically on Render deploy via the build command if `scripts/migrate.sh` is wired in. Check `render.yaml` for the current build command.

### Migration failed mid-deploy
Alembic migrations are transactional where Postgres supports it. If a migration fails:
1. The failed migration is rolled back automatically (DDL in Postgres is transactional)
2. The previous schema version remains active
3. Fix the migration script, push, and redeploy

### Checking migration state
```bash
cd backend
DATABASE_URL="$INGEST_DATABASE_URL" alembic current
DATABASE_URL="$INGEST_DATABASE_URL" alembic history --verbose
```

### Connection pool exhaustion
**Symptom:** `asyncpg.TooManyConnectionsError` in logs.

**Fix:**
1. Check Supabase dashboard → Database → Connection pooling → enable PgBouncer in transaction mode
2. Set `DATABASE_URL` to the PgBouncer port (5432 pooler, not 5432 direct)
3. Reduce `max_overflow` in SQLAlchemy engine config if needed

---

## 6. Redis

### Redis unavailable
**Symptom:** `rate_limit_redis_unavailable CRITICAL` in logs; rate limiting is bypassed (fail-open).

**What happens automatically:** App continues to serve traffic but rate limiting and route caching are inactive. Enrichment quota enforcement is also bypassed with a CRITICAL log.

**Fix:**
1. Check Upstash dashboard for the Redis instance status
2. Verify `REDIS_URL` in Render env vars is correct (`rediss://` for TLS)
3. Restart the Render service after fixing the URL

---

## 7. Cloudflare Workers

### Validation cron not firing
**Symptom:** `lead_validation_run` rows stuck in `queued` status; no `POST /admin/validation/run-due` hits in audit logs.

**Check:**
```bash
cd infra
npx wrangler tail --name reproute-validation-cron
```

**Fix:**
1. Verify the cron trigger is active: Cloudflare dashboard → Workers → reproute-validation-cron → Triggers
2. Redeploy the worker: `npx wrangler deploy --config wrangler.validation-cron.toml`
3. Manual trigger (emergency):
   ```bash
   TIMESTAMP=$(date +%s)
   SIG=$(echo -n "${TIMESTAMP}" | openssl dgst -sha256 -hmac "$VALIDATION_HMAC_SECRET" -hex | awk '{print $2}')
   curl -X POST https://reproute-backend.onrender.com/admin/validation/run-due \
     -H "X-HMAC-Timestamp: $TIMESTAMP" \
     -H "X-HMAC-Signature: $SIG"
   ```

### Geocode worker returning errors
**Symptom:** Geocoding fails for all queries; `geocode_worker_error` in logs.

**Fix:**
1. Check worker health: `curl https://reproute-geocode.<subdomain>.workers.dev/?q=Indianapolis`
2. Check KV namespace binding in Cloudflare dashboard
3. Redeploy: `cd infra && npx wrangler deploy`

---

## 8. Cloudflare Pages (frontend)

### Deploy failed
1. Cloudflare dashboard → Pages → reproute → Deployments → click failed deploy → build log
2. Common causes: missing `VITE_*` env var, npm install failure
3. Check that `VITE_API_BASE_URL` and `VITE_CLERK_PUBLISHABLE_KEY` are set in Pages project settings → Environment variables

### Rolling back frontend
Cloudflare Pages keeps all previous deployments.
1. Pages → Deployments → find last good deploy → **Rollback to this deployment**
2. Instant, no rebuild required

---

## 9. Support contacts

| Service | Support URL | Notes |
|---|---|---|
| Clerk | https://clerk.com/support | Dashboard chat for paid plans |
| Supabase | https://supabase.com/support | Dashboard ticket |
| Render | https://render.com/support | Dashboard ticket; free tier = community forum only |
| Cloudflare | https://developers.cloudflare.com | Workers free tier = community only |
| Upstash | https://upstash.com | Dashboard support |
| ORS | https://openrouteservice.org/contact | Email |

---

## 10. Pilot participant SLA

- **P0** (app down, no users can log in): respond within 1 hour, target fix within 4 hours
- **P1** (major feature broken — route creation, lead save, export): respond within 4 hours, fix within 24 hours
- **P2** (degraded mode — enrichment down, validation cap hit, slow geocoding): notify participants, fix within 48 hours
- **P3** (cosmetic / minor): next scheduled deploy

Notify pilot participants via direct message when a P0 or P1 is active and when it is resolved.
