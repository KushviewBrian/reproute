# RepRoute Security Plan (MVP → Pilot)

Last updated: April 17, 2026

## 1) Scope and Security Objective

Goal: protect user/account data, lead data, and system integrity from unauthorized access, data exfiltration, abuse, and service disruption.

Stack in scope:
- Frontend: React PWA on Cloudflare Pages
- Backend: FastAPI on Render
- Auth: Clerk JWT
- Data: Supabase Postgres/PostGIS (via pgbouncer pooler)
- Cache/rate-limit: Upstash Redis
- Geocode cache / validation scheduler: Cloudflare Workers + Workers KV

No plan is literally bulletproof. The objective is defense-in-depth with verified controls and fast incident response. Every control below has a build status so the open work is unambiguous.

---

## 2) Current High-Risk Gaps (P0 — Verification Pending)

These are confirmed open issues in the current codebase. Each must be closed before pilot.

### P0-1: Database TLS certificate verification disabled
**Status: CODE IMPLEMENTED WITH EMERGENCY OVERRIDE; VERIFICATION PENDING**

`backend/app/db/session.py` now supports strict verification, but it is controlled by `DATABASE_TLS_VERIFY` and can run with `CERT_NONE`:
```python
if settings.database_tls_verify:
    ssl_ctx.check_hostname = True
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
else:
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
```
`backend/app/main.py` now fails startup in production when TLS is insecure unless emergency override is explicitly enabled and not past sunset.

**Required fix:**
- In production, use `ssl.CERT_REQUIRED` with `check_hostname=True`.
- Load the appropriate CA bundle (`ssl.create_default_context()` with no overrides does this correctly).
- The pgbouncer pooler URL must be reachable with a valid cert and `DATABASE_TLS_VERIFY=true` in production.
- Emergency override control must remain disabled by default: `DATABASE_TLS_EMERGENCY_INSECURE_OVERRIDE=false`.
- Override sunset must be enforced and documented: `DATABASE_TLS_EMERGENCY_OVERRIDE_SUNSET` (date).

### P0-2: JWT signature verification is optional, not enforced
**Status: CODE IMPLEMENTED; VERIFICATION PENDING**

`backend/app/core/auth.py` now verifies signatures in all non-dev/test environments and startup fails in production if JWT config is missing.
```python
if settings.clerk_jwks_url:
    await _verify_token_signature(token, settings.clerk_jwks_url)
claims = jwt.get_unverified_claims(token)  # always runs regardless
```
Remaining work is full negative-auth regression coverage in CI/runtime.

**Required fix:**
- In production (`environment == "production"`), fail startup if `CLERK_JWKS_URL` or `CLERK_JWT_ISSUER` are empty.
- Remove the conditional — verification must always run in non-dev environments.
- `CLERK_AUDIENCE` and `CLERK_AUTHORIZED_PARTY` remain optional but should be set for defense-in-depth.

### P0-3: Admin endpoint accepts any authenticated user who knows the secret
**Status: CODE IMPLEMENTED; VERIFICATION PENDING**

`admin_import.py` now requires admin email allowlist membership, validates `parquet_path` against allowlisted roots, and enforces single-job concurrency plus global rate limit.

**Required fix:**
- Validate behavior in production with configured allowlist and root paths.
- Consider disabling the admin import endpoint entirely in production once GitHub Actions is the primary ingestion path.

### P0-4: `poc_mode` bypass has no production guard
**Status: CODE IMPLEMENTED; VERIFICATION PENDING**

Startup now fails if `environment == "production"` and `poc_mode == True`.

**Required fix:**
- Add startup check: if `environment == "production"` and `poc_mode == True`, log critical and refuse to start.

---

## 3) Threat Model (Practical)

Primary threats for this application:

| # | Threat | Notes |
|---|---|---|
| 1 | Broken object authorization (BOLA/IDOR) | Read/write another user's leads, notes, routes |
| 2 | Token abuse | Forged, replayed, or mis-scoped JWT |
| 3 | DB credential leakage / direct DB intrusion | Connection string in logs, env leak |
| 4 | Secret exposure | Repo, logs, frontend bundle, error responses |
| 5 | API abuse | Resource exhaustion, bot flooding, scraping |
| 6 | Supply chain compromise | Dependencies, build pipeline |
| 7 | Incident blind spots | Insufficient logs, no alerting |
| 8 | Stale auth cache | Revoked Clerk account still accepted in-memory |
| 9 | Admin command injection | Attacker-controlled paths in subprocess calls |

Data classification:
- **Sensitive**: user identity, notes, follow-up dates, internal API keys and secrets.
- **Business data**: prospect/business records, route associations, validation results.
- **Public data**: Overture business records (already public — lower sensitivity, still requires access control).

---

## 4) Security Architecture Controls

### 4.1 Identity and Session Security

**What's required:**
- Backend validates Clerk JWT signature against JWKS for every protected request.
- Enforce `iss`, `exp`, and `nbf` on every token. Enforce `aud` and `azp` when configured.
- Keep session tokens short-lived — Clerk handles this; do not extend lifetimes.
- Do not store tokens in localStorage on the client (Clerk SDK handles storage correctly by default).
- No privileged roles derived from mutable client-side state — all authorization is server-side.

**JWKS cache issue (resolved in code; verify in runtime):**
JWKS now uses a 1-hour TTL cache. Remaining work is integration validation during key rotation scenarios.

**User cache issue (resolved in code; verify in runtime):**
`_user_cache` is now TTL+LRU bounded (5 minutes, max 500 entries). Remaining work is runtime validation under auth churn.

**Implementation checklist:**
- [x] Startup validator: fail in production if `CLERK_JWKS_URL` or `CLERK_JWT_ISSUER` are empty
- [x] Remove conditional signature verification — always verify in non-dev environments
- [x] Add TTL to JWKS cache (1 hour); refresh on expiry
- [x] Replace unbounded `_user_cache` with TTL-based LRU cache (max 500 entries, 5-minute TTL)
- [ ] Unit tests: invalid signature, wrong issuer, expired token, missing JWKS URL

### 4.2 Authorization (Object and Function Level)

**What's required:**
- Every data fetch and mutation must be filtered by `user_id` — no endpoint may return or modify another user's data.
- No endpoint may accept a `user_id` from the client for authorization decisions.
- Admin endpoints require elevated policy beyond user auth (see P0-3).

**Current state:** User-scoped filtering is implemented in routes, leads, saved-leads, notes, and export. Cross-user access has not been systematically tested with negative tests.

**Implementation checklist:**
- [ ] Negative tests for cross-user access on all owned resources: routes, saved-leads, notes, export
- [x] Admin email allowlist in `admin_import.py`
- [x] `parquet_path` input validation in admin import
- [ ] Audit any new endpoint added for ownership filter before merging

### 4.3 Database Hardening

**What's required:**
- Strict TLS verification enforced in production (P0-1 re-close: no insecure fallback in prod)
- Least-privileged DB roles:
  - App role: `SELECT`, `INSERT`, `UPDATE`, `DELETE` on app tables only
  - Migration role: `CREATE`, `ALTER`, `DROP` — used only from CI/manual ops, not the running app
  - Optional read-only role for analytics/export queries
- Rotate DB credentials on schedule and immediately after any suspected leak
- No direct DB access from the frontend — all queries through the FastAPI backend
- pgbouncer pooler (port 6543) in use — `statement_cache_size=0` and `pool_pre_ping=False` already set correctly

**Supabase-specific:**
- Supabase Data API (PostgREST) is not used by this app — verify it is disabled or restricted for all app tables
- Never expose `service_role` key in frontend, logs, or public repos
- RLS is not relied upon for security (app enforces ownership in Python) — this is intentional and acceptable; do not add RLS as a false safety net without testing it end-to-end

**Implementation checklist:**
- [ ] Verify P0-1 in production/staging with live pooler cert chain; confirm emergency override stays disabled
- [ ] Create least-privileged DB app role; app connection string uses app role, not superuser
- [ ] Verify Supabase Data API is restricted or disabled for app tables
- [ ] Confirm `service_role` key is not in any env file committed to repo or in Render env vars accessible to the frontend

### 4.4 Secrets Management

**What's in scope for rotation:**
- Supabase DB password / connection URLs
- Clerk secret key and JWKS URL
- ORS API key
- Cloudflare API tokens
- Upstash Redis credentials
- Admin import secret
- Validation admin HMAC secret (when validation plan is built)

**Policy:**
- Secrets only in platform secret stores: Render env vars, GitHub Actions secrets, Cloudflare Worker secrets, Supabase vault.
- `.env` files excluded from git via `.gitignore` — verified.
- Pre-commit + CI secret scanning required (not yet active — see §4.7).
- Rotate all secrets **quarterly** or immediately on leak suspicion.

**Rotation procedure (for each secret):**
1. Generate new value in the target platform.
2. Update in all platform secret stores simultaneously.
3. Redeploy services (Render redeploys on env var change; CF Workers require `wrangler publish`).
4. Confirm no 401/403 spike in logs after rotation.
5. Invalidate old value in the issuing platform.
6. Log rotation event in incident/ops log.

**Implementation checklist:**
- [ ] Secret scanning active in GitHub Actions CI (e.g., `trufflesecurity/trufflehog-actions-scan` or `gitleaks/gitleaks-action`)
- [ ] Confirm no secrets in frontend bundle (run `grep -r "sk_" dist/` after build)
- [ ] Document secret owner and rotation reminder (calendar or automated alert)

### 4.5 API Security and Abuse Protection

**Current rate-limit coverage:**

| Endpoint group | Rate limited? | Limit |
|---|---|---|
| `POST /routes` | Yes | 60/hour per user |
| `GET /routes/{id}` | Yes | 180/min per user |
| `PATCH /routes/{id}` | Yes | 60/min per user |
| `GET /geocode` | Yes | 30/min per user |
| `GET /routes/{id}/leads` | Yes | 180/min per user |
| `POST /saved-leads` | Yes | 60/hour per user |
| `PATCH /saved-leads/{id}` | Yes | 60/hour per user |
| `DELETE /saved-leads/{id}` | Yes | 60/hour per user |
| `POST /notes` | Yes | 120/hour per user |
| `GET /notes` | **No** | — |
| `GET /export/routes/{id}/leads.csv` | Yes | 20/hour per user |
| `GET /export/saved-leads.csv` | Yes | 20/hour per user |
| `POST /admin/import/overture` | Yes | 5/day global |

Rate limiting fails open when Redis is unavailable (by design for reliability — acceptable but documented).

**What's required:**
- Extend rate limiting to saved-leads, notes, export, and admin import endpoints.
- Export endpoint: rate limit + enforce the existing 2,000-row query cap in code with a tested assertion.
- Body size limits: add middleware for max request size (suggested: 1 MB for API, 10 MB for admin import payload).
- Request timeouts: enforce at the application level, not just relying on Render's infrastructure timeout.
- Admin import: add per-job concurrency limit (max 1 running job at a time) to prevent resource exhaustion.

**Implementation checklist:**
- [x] Add `enforce_rate_limit` to saved-leads (write operations): 60/hour per user
- [x] Add `enforce_rate_limit` to notes (create): 120/hour per user
- [x] Add `enforce_rate_limit` to export: 20/hour per user
- [x] Add `enforce_rate_limit` to admin import: 5/day global
- [x] Add request body size limit middleware to `main.py`
- [x] Add concurrency guard to admin import (check for running jobs before queuing)

### 4.6 Frontend and Browser Security

**Security headers — current state:**
- Backend (`main.py`): middleware now sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and production-only HSTS.
- Frontend (Cloudflare Pages): `_headers` file added with CSP report-only + permissions/referrer/nosniff.

**Required headers and where to set them:**

For the backend (FastAPI middleware):
```
Strict-Transport-Security: max-age=63072000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

For the frontend (Cloudflare Pages `_headers` file in `frontend/public/`):
```
/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https://api.clerk.com https://clerk.reproute.app https://reproute.onrender.com; worker-src 'self'; frame-ancestors 'none'
  Permissions-Policy: geolocation=(self), camera=(), microphone=()
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
```

> Note: CSP `connect-src` must include the Clerk frontend API domain and the backend API URL. Start with report-only mode (`Content-Security-Policy-Report-Only`) first and check for violations before switching to enforce.

**Other frontend controls:**
- CORS: already restricted to known origins via `CORS_ALLOW_ORIGINS` env var — correct.
- User-entered note text must be rendered as text, not innerHTML — verify in LeadDetail and SavedLeads components.
- Never embed `CLERK_SECRET_KEY`, `DATABASE_URL`, or any backend secret in `VITE_*` env vars.

**Implementation checklist:**
- [x] Add security headers middleware to `main.py` (backend)
- [x] Add `frontend/public/_headers` for Cloudflare Pages (frontend)
- [ ] Deploy CSP in report-only mode first; review violations; then enforce
- [ ] Verify note text rendered as text content, not HTML
- [ ] Audit all `VITE_*` env vars — confirm no backend secrets

### 4.7 Supply Chain and CI/CD Security

**Required CI gates (minimum before pilot):**
- Tests (already running)
- Lint / type checks (already running)
- Dependency vulnerability scan: Python (`pip-audit` or `safety`) + Node (`npm audit`)
- Secret scan: `trufflesecurity/trufflehog-actions-scan` or `gitleaks/gitleaks-action`
- Migration safety checks when schema files change

**Branch protection (required on `main`):**
- Require PR review for changes touching: `auth.py`, `session.py`, `config.py`, `admin_import.py`, any migration, any CI workflow file
- Disallow force-push to `main`
- Require status checks to pass before merge

**Implementation checklist:**
- [ ] Add `pip-audit` step to Python CI job
- [ ] Add `npm audit --audit-level=high` step to Node CI job
- [ ] Add secret scanning action to CI
- [ ] Enable branch protection on `main` with required reviews for sensitive paths
- [ ] Pin third-party GitHub Actions to commit SHAs (not mutable tags)

### 4.8 Logging, Monitoring, and Detection

**Current state:** Basic `logging.basicConfig` is configured. Startup logs config values. No structured audit logs, no alerting, no log forwarding.

**Critical gap — Render log retention:** Render's free tier retains logs for a very short window (hours). If an incident is discovered days later, logs will be gone. Log forwarding to an external service must be set up before pilot for audit logging to be meaningful.

**Recommended free/cheap options:** Logtail (Better Stack free tier), Papertrail (free tier), or structured logs to Supabase (writes to a log table).

**Required structured audit events:**
| Event | Fields to log |
|---|---|
| Auth failure | timestamp, ip, reason, token_iss |
| Permission denial (403) | timestamp, user_id, endpoint, resource_id |
| Rate limit hit (429) | timestamp, user_id, endpoint, limit_key |
| Admin endpoint access | timestamp, user_id, endpoint, job_id |
| Note/status mutation | timestamp, user_id, business_id, old_value, new_value |
| Export triggered | timestamp, user_id, route_id, row_count |
| Validation run triggered | timestamp, user_id, business_id, checks |

**Alerts (minimum before pilot):**
- Spike in 401/403 responses (>20 in 5 minutes from a single IP)
- Repeated admin endpoint failures (>3 in 10 minutes)
- Unusual export volume (>10 exports in 1 hour from one user)
- Backend 5xx rate above 1% over 5 minutes
- `/health` check failure (uptime monitoring with alerting)

**Redaction requirements:**
- Never log `Authorization` header values, database URLs, or API keys
- Truncate or hash note text in mutation logs (log that a note was changed, not its content)

**Implementation checklist:**
- [ ] Set up log forwarding from Render to external log service
- [ ] Add structured audit log middleware or per-endpoint log calls for events above
- [ ] Set up uptime monitoring for `/health` with alerting (e.g., UptimeRobot free tier)
- [ ] Configure alert rules for auth/rate-limit spikes

### 4.9 Backup and Recovery

**Current state:** Supabase provides automated daily backups on paid plans. Free tier backups are limited — verify current Supabase backup policy for the active plan.

**Targets:**
- RPO (Recovery Point Objective): ≤ 24 hours
- RTO (Recovery Time Objective): ≤ 4 hours

**Requirements:**
- Verify automated backup is active and covers all app tables including PostGIS geometry columns.
- Run a restore drill to a staging environment before pilot — confirm `pg_restore` completes and app runs against restored DB.
- Monthly restore drill cadence post-launch.
- Document restore steps in ops runbook.

**Implementation checklist:**
- [ ] Verify Supabase backup schedule and retention for current plan
- [ ] Execute and document one successful restore drill before pilot
- [ ] Add monthly restore drill to ops calendar

### 4.10 Data Retention and Account Deletion

**Current state:** No data deletion policy exists. User data (notes, saved leads, routes) persists indefinitely.

**Required policy (define before pilot):**
- When a user deletes their Clerk account: what happens to their DB records?
- Decide: soft delete (mark inactive, retain for 30 days) or hard delete (cascade on user row deletion).
- For MVP: hard delete on user row deletion is simplest. Add `ON DELETE CASCADE` to all FK references to `user.id`.
- Inform users in privacy policy of retention period.

**Implementation checklist:**
- [ ] Define and document retention policy
- [ ] Add `ON DELETE CASCADE` to user-owned tables or implement deletion webhook from Clerk
- [ ] Add privacy policy page or notice to app (even minimal text before pilot)

---

## 5) Security Testing Plan

### 5.1 Automated Tests (required in CI)

- **Auth tests:** invalid signature, wrong issuer, expired token, missing JWKS URL (should all return 401).
- **Authorization tests:** cross-user access attempts for routes, saved-leads, notes, and export — all should return 403 or 404.
- **Input validation tests:** oversized payload, invalid UUIDs, malformed enum values, path traversal in admin parquet path.
- **Rate-limit tests:** exceed threshold, confirm 429; wait for window, confirm recovery.
- **POC mode test:** assert that `poc_mode=True` + `environment=production` triggers startup failure.

### 5.2 Manual Security Tests (per release)

- IDOR/BOLA checks on all endpoints with object IDs in the path.
- Forced-browse checks for `/admin/*` routes without secret header.
- CORS verification: confirm preflight rejects unknown origins.
- CSP verification in browser DevTools — no violations from normal app use.
- Secret exposure check: `grep -r "sk_\|DATABASE_URL\|service_role" dist/` after frontend build.
- Log review: confirm no tokens, passwords, or PII appear in Render log output.

### 5.3 External Validation (pre-pilot)

- Lightweight third-party API penetration test focused on OWASP API Top 10 categories.
- Minimum scope: auth bypass, BOLA, rate-limit bypass, admin endpoint isolation.

---

## 6) Incident Response Plan

### 6.1 Triggers

- Suspected credential or secret leak
- Confirmed unauthorized data access
- Repeated auth bypass attempts in logs
- Unexpected DB activity or anomalous export volume
- Clerk account compromise reported by user

### 6.2 Actions (first 60 minutes)

1. **Contain**
   - Rotate affected credentials immediately (see §4.4 rotation procedure)
   - If admin endpoint is involved: set `ADMIN_IMPORT_SECRET` to a new random value and redeploy
   - If DB credentials are involved: rotate Supabase DB password; update all services
   - If Clerk is involved: use Clerk dashboard to revoke sessions for affected user(s)

2. **Preserve**
   - Export current logs from Render and log forwarding service before they expire
   - Take Supabase DB snapshot if data may have been modified

3. **Eradicate**
   - Patch the exploited code path
   - Redeploy with fix and new credentials
   - Confirm no persistence mechanism remains

4. **Recover**
   - Verify system integrity: run smoke tests against production
   - Restore from backup if data was corrupted or deleted

5. **Communicate**
   - Internal incident note: timeline, scope, root cause, fix
   - User notice if personal data was accessed: describe what was accessed, when, and what was done

### 6.3 Owner and Contacts

- **Incident owner:** Brian (sole operator at MVP/pilot stage)
- **Clerk support:** clerk.com/support — for Clerk account or JWT issues
- **Supabase support:** supabase.com/support — for DB access or backup issues
- **Render support:** render.com/support — for infra/deploy issues
- **Cloudflare support:** cloudflare.com/support — for Worker or Pages issues

---

## 7) Implementation Roadmap

### Phase A (0–7 days) — Critical Lockdown
Close all P0 items.

- [x] Implement strict DB TLS startup guard in production with emergency override + sunset control (P0-1)
- [x] Make JWT signature verification unconditional in production (P0-2)
- [x] Add startup validator: fail if required auth env vars are missing in production
- [x] Add `poc_mode` production guard to startup (P0-4)
- [x] Add admin email allowlist + `parquet_path` validation (P0-3)
- [ ] Add secret scanning to CI

**Exit criteria:** All P0 items verified by test and production config validation, then deployed to production.

### Phase B (1–3 weeks) — Hardening

- [x] Add security headers to backend and Cloudflare Pages `_headers`
- [ ] Deploy CSP in report-only mode; review; enforce
- [x] Extend rate limiting to all uncovered endpoint groups
- [x] Add JWKS cache TTL and user cache TTL/LRU
- [ ] Add negative authorization tests across all resource endpoints
- [ ] Set up log forwarding from Render
- [ ] Add structured audit logging for mutations and admin access
- [ ] Add dependency scanning (pip-audit, npm audit) to CI
- [ ] Enable branch protection on `main`

**Exit criteria:** No known high-severity auth/authz gaps. Audit logs flowing to external service.

### Phase C (Pre-pilot) — Verification and Response Readiness

- [ ] Run DB restore drill and document result
- [ ] Define and implement data retention/deletion policy
- [ ] Add uptime monitoring + alerting for `/health`
- [ ] Run external API-focused pentest (OWASP API Top 10 scope)
- [ ] Complete incident response tabletop exercise
- [ ] Add privacy policy notice to app
- [ ] Sign off security checklist (§8)

**Exit criteria:** All §8 checklist items checked. Security sign-off before pilot launch.

---

## 8) Security Checklist (Definition of Done Before Pilot)

### P0 Items
- [ ] Production DB verified at runtime with `DATABASE_TLS_VERIFY=true` and emergency override disabled
- [x] JWT signature verification is unconditional in production (not gated on env var presence)
- [x] Startup fails in production if `CLERK_JWKS_URL` or `CLERK_JWT_ISSUER` are empty
- [x] Startup fails in production if `poc_mode=True`
- [x] Admin import requires email allowlist check, not only shared secret
- [x] `parquet_path` validated against allowed pattern before subprocess call

### Auth and Authorization
- [x] Clerk JWKS cache has TTL (≤ 1 hour)
- [x] User cache has TTL and max size (LRU eviction)
- [ ] Cross-user access negative tests pass for all owned resources
- [ ] `CLERK_AUDIENCE` and `CLERK_AUTHORIZED_PARTY` set in production env

### API and Infrastructure
- [x] Rate limiting active on saved-leads, notes, export, and admin import
- [x] Security headers configured on backend and Cloudflare Pages
- [ ] CSP enforced (not report-only) with no violations from normal use
- [x] Request body size limit middleware active

### Secrets and Supply Chain
- [ ] Secret scanning active in CI; no hardcoded secrets found in repo
- [ ] Frontend build contains no backend secrets (`grep` check passes)
- [ ] `pip-audit` and `npm audit` pass in CI with no high-severity findings
- [ ] Branch protection active on `main` with required reviews for sensitive paths

### Observability and Recovery
- [ ] Log forwarding active from Render to external log service
- [ ] Structured audit logs flowing for mutations and admin access
- [ ] Uptime monitoring active for `/health` with alerting
- [ ] DB backup verified active; restore drill completed successfully
- [ ] Data retention/deletion policy documented and implemented

### Process
- [ ] All secrets documented with rotation schedule and owner
- [ ] Incident response runbook tested in tabletop exercise
- [ ] Privacy policy notice in app

---

## 9) Standards Mapping (Reference)

This plan aligns with:
- **OWASP API Security Top 10 (2023):** broken object authorization, broken authentication, broken object property authorization, unrestricted resource consumption, broken function level authorization, server-side request forgery, security misconfiguration, injection.
- **OWASP ASVS categories:** authentication, access control, data protection, logging and monitoring, configuration hardening.

Relevant documentation:
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- Clerk session token validation: https://clerk.com/docs/how-to/validate-session-tokens
- Supabase hardening data API: https://supabase.com/docs/guides/database/hardening-data-api
- Cloudflare Pages custom headers: https://developers.cloudflare.com/pages/configuration/headers/
