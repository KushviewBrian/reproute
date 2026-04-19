# Phase 7 — Ops Hardening Platform Setup Guide

Date: 2026-04-19
Commit: pending
Status: Code tasks complete. Platform tasks require Render/Supabase/external-account access.

---

## Code tasks completed this session

| Task | File | What changed |
|---|---|---|
| 7-A ORS retry + degraded fallback | `backend/app/services/routing_service.py` | 2 attempts, 1s delay, straight-line fallback on exhaustion, `degraded=True` flag |
| 7-A Geocode retry + degraded fallback | `backend/app/services/geocode_service.py` | 2 attempts, 0.5s delay, POC fallback on exhaustion |
| 7-A Unit tests | `backend/tests/unit/test_upstream_resilience.py` | 18 tests covering all error paths |
| 7-F duration_ms in audit log | `backend/app/main.py` | `time.monotonic()` around `call_next`, emitted as `duration_ms` in every `audit_event` line |

---

## Platform tasks (requires external access)

### 7-C — Log forwarding from Render

1. Sign in to [Render dashboard](https://dashboard.render.com)
2. Navigate to your backend service → **Logs** tab → **Log Streams**
3. Click **Add a Log Stream**
4. Choose **Logtail** (free tier: 1 GB/day, 3-day search)
   - Create account at https://betterstack.com/logtail
   - Generate a **Source token** for type "HTTP"
   - Paste token into Render's log stream form
5. Save. Wait 2 min, then hit any endpoint and confirm `audit_event` lines appear in Logtail.
6. Commit screenshot to `docs/evidence/phase7_log_forwarding_<date>.md`

Expected log line shape (search for `audit_event`):
```
audit_event method=POST path=/routes status=201 duration_ms=843 client=1.2.3.4
```

---

### 7-D — Uptime monitoring for `/health`

1. Go to https://uptimerobot.com → free account
2. **Add New Monitor**:
   - Type: **HTTP(s)**
   - Friendly name: `Reproute API`
   - URL: `https://reproute.onrender.com/health`
   - Monitoring interval: **5 minutes**
   - Keyword alert: enable "Check for keyword" → `"status":"ok"` (fails if DB or Redis is down)
3. Alert contact: add your email
4. Save. Confirm monitor shows green.
5. Commit screenshot to `docs/evidence/phase7_uptime_monitor_<date>.md`

---

### 7-E — Alert rules in Logtail (after 7-C is live)

Navigate to Logtail → your source → **Alerts** → **New Alert**. Create each:

| Alert name | Filter | Threshold | Window |
|---|---|---|---|
| 401/403 spike | `audit_event` AND (`status=401` OR `status=403`) | > 20 occurrences from same `client=` | 5 min |
| Admin failures | `audit_event` AND `path=/admin` AND `status` starts with `4` or `5` | > 3 | 10 min |
| Export volume | `audit_event` AND `path=/export` | > 10 from same client | 60 min |
| 5xx rate | `audit_event` AND `status` starts with `5` | > 1% of total audit events | 5 min |
| p95 latency | `audit_event` AND `path` matches `/routes\|/leads` AND `duration_ms` > 5000 | any | 5 min |

For each alert: set notification to email. Commit a screenshot of all 5 alert rules active.

---

### 7-G — DB least-privileged roles + PostgREST (Supabase)

1. In Supabase dashboard → **Settings** → **Database** → **Connection string**:
   - Confirm the app uses the `postgres` user only during migrations (`migrate.sh`)
   - For runtime, best practice is a role with no `SUPERUSER` and no `CREATEROLE`
2. **API** tab → **Exposed schemas**:
   - If `public` is listed, either remove it OR confirm Row Level Security (RLS) is enabled on all tables
   - Fastest safe option: remove `public` from exposed schemas (PostgREST only; FastAPI is unaffected)
3. Confirm `SUPABASE_SERVICE_ROLE_KEY` is **not** in any frontend `.env` or `frontend/dist/`
   - Run: `grep -r "service_role" frontend/dist/` — must return empty
4. Commit evidence to `docs/evidence/phase7_db_roles_<date>.md`

---

### 7-H — Backup + restore drill (Supabase)

1. Supabase dashboard → **Database** → **Backups**
   - Confirm daily backups are enabled (requires Pro plan or above)
   - Note the timestamp of the most recent backup
2. Test restore path:
   - Option A (Pro+): click **Restore** → select a point-in-time → restore to a *new* project
   - Option B (Free): download via `pg_dump`:
     ```bash
     pg_dump "$DATABASE_URL" --no-owner --no-acl -Fc -f backup_test_$(date +%Y%m%d).dump
     # Verify it's non-empty:
     ls -lh backup_test_*.dump
     ```
3. Document: backup policy, last backup timestamp, restore command/steps
4. Commit to `docs/evidence/phase7_backup_drill_<date>.md`

---

## Phase 7 Exit Criteria Checklist

### Code (all done ✅)
- [x] ORS retry + degraded fallback — 18 unit tests green
- [x] Geocode retry + degraded fallback — unit tests green
- [x] `duration_ms` in every `audit_event` log line

### Platform (pending — needs external access)
- [ ] Log forwarding active — `audit_event` lines visible in Logtail
- [ ] Uptime monitor live on `/health` with email alerting
- [ ] 5 alert rules configured and active in Logtail
- [ ] DB: `service_role` key not in frontend; PostgREST exposure verified/restricted
- [ ] Backup policy confirmed; restore path documented and drill completed
