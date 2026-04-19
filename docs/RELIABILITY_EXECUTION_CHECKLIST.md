# RepRoute Reliability Execution Checklist (Apr 20, 2026 → May 1, 2026)

This checklist operationalizes the 2-week hardening plan with proof-required gate exits.

## Gate 0 — Stabilization Baseline + Merge Controls

- [ ] Required checks enforced on `main`: backend tests, frontend typecheck/build, security scans.
- [ ] PR template/process includes: roadmap line item, test evidence, rollback note.
- [x] Production env contract documented and reviewed:
  - `DATABASE_TLS_VERIFY=true`
  - `DATABASE_SSL_CA_PEM` set
  - `POC_MODE=false`
  - `CLERK_JWKS_URL` + `CLERK_JWT_ISSUER` set
  - `CORS_ALLOW_ORIGINS` exact origins
- [x] Post-deploy smoke checklist documented (`/health`, route/leads, today, exports).

## Gate 1 — Phase 2 Security Closeout

- [x] P0 startup guards re-verified (TLS strict + emergency sunset, JWT config required, `poc_mode` refusal).
- [x] Admin import controls re-verified (secret + allowlist + path roots + single-job concurrency).
- [ ] Negative auth/authz suite green in CI:
  - invalid signature, wrong issuer, expired token
  - cross-user denial for routes/saved-leads/notes/export
- [ ] CI scanners green: gitleaks + `pip-audit` + `npm audit --audit-level=high`.
- [x] Security checklist section updated with commit refs and CI links (or explicit local-session `n/a`).

## Gate 2 — Evidence Closure (Phase 1 + Phase 3/4)

- [ ] Replace EXPLAIN placeholder with route-specific artifact.
- [ ] Commit one ingestion QA artifact with metrics + timestamp + command.
- [ ] Commit 5-route scoring validation artifact with `other_unknown_rate`.
- [ ] Document offline reconnect no-loss verification (status + notes).
- [ ] Document dedup spot-check and Today dashboard correctness checks.

## Gate 3 — Phase 5 MVP Runtime Completion

- [ ] Queue claim/cap/retry behavior verified in tests.
- [ ] Failure taxonomy assertions verified (`bot_blocked`/`unknown` handling).
- [ ] Endpoint auth and behavior verified:
  - `POST /leads/{business_id}/validate`
  - `GET /leads/{business_id}/validation`
  - `POST /admin/validation/run-due` (HMAC)
- [ ] Runtime evidence package committed (10+ sample runs + auth failure cases + payload snapshots).

## Gate 4 — Re-baseline + Next-Phase Lock

- [x] `docs/roadmap.md` statuses updated only with evidence-backed changes.
- [ ] Phase 6/7 design packet published (constraints, licensing, quota model, ops hardening sequence).
- [ ] Release candidate summary published:
  - closed items
  - residual risks
  - next queue

## Session Notes (2026-04-19)

- Roadmap consistency fixed (`Phase 6` status + stale immediate-sprint item) in `docs/roadmap.md`.
- Repo-local verification completed:
  - `python3 -m compileall backend/app backend/tests scripts`
  - `npm run -s typecheck`
  - `npm run -s build`
- Gate 1 verification session completed and documented:
  - Evidence artifact: `docs/evidence/phase2_security_signoff_2026-04-19.md`
  - Backend security tests: `58 passed`
  - Staging smoke: `/health` 200, HMAC missing/invalid rejected, protected endpoints reject missing bearer token
  - Frontend secret grep in `dist/`: no matches for `sk_|DATABASE_URL|service_role`
- Remaining blockers:
  - `INGEST_DATABASE_URL`
  - staging bearer token + route IDs
  - CI-linked verification URLs for Gate 1 are still pending

## Evidence entry template (required per gate item)

```text
Date (UTC):
Gate + checklist item:
Commit SHA:
CI run URL:
Command(s):
Outcome:
Artifact link(s):
Rollback note:
```
