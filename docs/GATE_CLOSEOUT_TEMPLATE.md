# RepRoute Gate Closeout Template

Use this block in every PR/deploy note during the reliability hardening cycle.

```md
## Gate Closeout

Date (UTC):
Commit SHA:
PR:
CI Run URL(s):
Deployed Env (staging/production):

### Gate 0 — Stabilization Baseline + Merge Controls
- [ ] Required checks enforced on `main`
- [ ] PR includes roadmap link + evidence + rollback note
- [ ] Production env contract confirmed (TLS/PEM/JWT/CORS/HMAC)
- [ ] Post-deploy smoke checklist documented

Evidence:
- Docs/Config links:
- CI checks:
- Rollback note:

### Gate 1 — Phase 2 Security Closeout
- [ ] Startup guards verified (`TLS strict`, `poc_mode`, JWT env requirements)
- [ ] Admin import protections verified (secret/allowlist/path/concurrency)
- [ ] Negative auth/authz tests green
- [ ] Security scans green (`gitleaks`, `pip-audit`, `npm audit`)
- [ ] Pooler compatibility smoke verified (route/leads/today/export)

Evidence:
- Test logs:
- CI run:
- Runtime smoke notes:

### Gate 2 — Evidence Closure (Phases 1/3/4)
- [ ] EXPLAIN artifact committed (route-specific)
- [ ] Ingestion QA artifact committed
- [ ] 5-route scoring artifact committed (`other_unknown_rate`)
- [ ] Offline reconnect no-loss evidence committed (status + notes)
- [ ] Dedup spot-check evidence committed
- [ ] Today dashboard correctness evidence committed

Evidence:
- Artifact paths:
- Commands used:
- Measurements (p95 / rate):

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
- API traces:
- Artifact paths:

### Gate 4 — Re-baseline + Next-Phase Lock
- [ ] Roadmap statuses updated with evidence-backed truth only
- [ ] Phase 6/7 design packet published
- [ ] Release candidate summary published (closed items, residual risks, next queue)

Evidence:
- Updated docs:
- Summary link:

## Final Acceptance Snapshot
- [ ] No open P0 security issues
- [ ] CI fully green on `main`
- [ ] Production smoke passes core flows
- [ ] Evidence log complete for items marked done
```

## Required Linked Sources

- `docs/roadmap.md`
- `docs/securityplan.md`
- `docs/PHASE1_4_VALIDATION.md`
- `docs/RELIABILITY_EXECUTION_CHECKLIST.md`
