## Gate Closeout

Date (UTC): 2026-04-19
Commit SHA: pending local commit
PR: n/a (local session)
CI Run URL(s): n/a (local + staging runtime checks)
Deployed Env (staging/production): staging runtime checks against `https://reproute.onrender.com`

### Gate 0 — Stabilization Baseline + Merge Controls
- [ ] Required checks enforced on `main`
- [x] PR includes roadmap link + evidence + rollback note
- [x] Production env contract confirmed (TLS/PEM/JWT/CORS/HMAC)
- [x] Post-deploy smoke checklist documented

Evidence:
- Docs/Config links:
  - `docs/DEPLOYMENT_GUIDE.md`
  - `docs/REQUIRED_SECRETS.md`
  - `docs/roadmap.md`
  - `docs/evidence/session_roadmap_closure_2026-04-19.md`
- CI checks: local-only (`compileall`, frontend typecheck/build)
- Rollback note:
  - Revert this session commit to restore prior docs/frontend queue behavior.

### Gate 1 — Phase 2 Security Closeout
- [x] Startup guards verified (`TLS strict`, `poc_mode`, JWT env requirements)
- [x] Admin import protections verified (secret/allowlist/path/concurrency)
- [x] Negative auth/authz tests green
- [ ] Security scans green (`gitleaks`, `pip-audit`, `npm audit`) in CI (local rerun is green)
- [ ] Pooler compatibility smoke verified (route/leads/today/export authenticated success paths)

Evidence:
- Test logs:
  - `PYTHONPATH=$PWD/backend .venv313/bin/python -m pytest -q ...` => `58 passed in 0.94s`
  - `npm run -s typecheck` => pass
  - `npm run -s build` => pass
  - `pip-audit` => pass after remediation (`No known vulnerabilities found`)
  - `npm audit --audit-level=high` => pass threshold (moderate-only findings)
  - `gitleaks detect` => pass after allowlist of known historical false-positive commit
- CI run:
  - n/a in this session
- Runtime smoke notes:
  - `GET /health` => 200 with `{"status":"ok","db":"ok","redis":"ok"}`
  - `POST /admin/validation/run-due` missing headers => 401
  - `POST /admin/validation/run-due` invalid signature => 401
  - protected endpoints without bearer token (`POST /routes`, `GET /saved-leads/today`, `GET /export/saved-leads.csv`) => 401
  - Full artifact: `docs/evidence/phase2_security_signoff_2026-04-19.md`

### Gate 2 — Evidence Closure (Phases 1/3/4)
- [ ] EXPLAIN artifact committed (route-specific)
- [ ] Ingestion QA artifact committed
- [ ] 5-route scoring artifact committed (`other_unknown_rate`)
- [ ] Offline reconnect no-loss evidence committed (status + notes)
- [ ] Dedup spot-check evidence committed
- [ ] Today dashboard correctness evidence committed

Evidence:
- Artifact paths:
  - `docs/evidence/session_roadmap_closure_2026-04-19.md`
- Commands used:
  - `python3 -m compileall backend/app backend/tests scripts`
  - `npm run -s typecheck`
  - `npm run -s build`
  - attempted: `scripts/explain_candidate_query.py` (blocked local dependency)
- Measurements (p95 / rate):
  - blocked pending staging token/route IDs

### Gate 3 — Phase 5 MVP Runtime Completion
- [ ] Queue claim/cap/retry tests pass
- [ ] Failure taxonomy assertions pass
- [ ] Endpoint auth/behavior verified:
  - [ ] `POST /leads/{business_id}/validate`
  - [ ] `GET /leads/{business_id}/validation`
  - [ ] `POST /admin/validation/run-due` (HMAC)
- [ ] Runtime evidence package committed (10+ runs + auth-failure cases)

Evidence:
- Test logs:
  - Existing coverage in repo; Gate 3 runtime package not rerun in this session
- API traces:
  - blocked pending staging credentials
- Artifact paths:
  - `docs/evidence/session_roadmap_closure_2026-04-19.md`

### Gate 4 — Re-baseline + Next-Phase Lock
- [x] Roadmap statuses updated with evidence-backed truth only
- [ ] Phase 6/7 design packet published
- [ ] Release candidate summary published (closed items, residual risks, next queue)

Evidence:
- Updated docs:
  - `docs/roadmap.md`
  - `docs/PHASE1_4_VALIDATION.md`
  - `docs/RELIABILITY_EXECUTION_CHECKLIST.md`
- Summary link:
  - `docs/evidence/session_roadmap_closure_2026-04-19.md`

## Final Acceptance Snapshot
- [ ] No open P0 security issues
- [ ] CI fully green on `main`
- [ ] Production smoke passes core flows
- [ ] Evidence log complete for items marked done
