# Phase 2 Security Sign-off Evidence (2026-04-19)

Date (UTC): 2026-04-19T17:06:47Z
Baseline commit SHA: `7944b29`
CI run URL(s): n/a (repo-local/staging session)

## Scope

Gate 1 (Phase 2 Security Closeout) verification run:
- Startup guard/security regression suites
- Auth/authz negative-path suites
- Security scan commands aligned to `.github/workflows/ci.yml`
- Staging smoke checks for health, auth gating, and validation HMAC rejection

## Commands Executed

```bash
# Backend security suites
PYTHONPATH=$PWD/backend .venv313/bin/python -m pytest -q \
  backend/tests/test_security_auth_and_authz.py \
  backend/tests/test_admin_import_security.py \
  backend/tests/test_security_middleware.py \
  backend/tests/test_validation_routes.py \
  backend/tests/unit/test_validation_service.py

# Frontend parity checks
npm run -s typecheck
npm run -s build

# Dependency/security scans
HOME=/tmp PIP_CACHE_DIR=/tmp/pip-cache PIP_AUDIT_CACHE_DIR=/tmp/pip-audit-cache \
  PYTHONPATH=$PWD/backend .venv313/bin/pip-audit
HOME=/tmp npm audit --audit-level=high
/tmp/gitleaks-bin/gitleaks detect --source . --no-banner --redact --report-format json \
  --report-path /tmp/gitleaks-report.json

# Frontend secret exposure check (securityplan checklist)
(cd frontend && npm run -s build >/tmp/reproute_frontend_build_for_grep.log)
grep -R -n -E "sk_|DATABASE_URL|service_role" frontend/dist/

# Staging smoke checks
curl -sS -D - https://reproute.onrender.com/health
curl -sS -D - -X POST https://reproute.onrender.com/admin/validation/run-due
curl -sS -D - -X POST https://reproute.onrender.com/admin/validation/run-due \
  -H "X-Admin-Timestamp: <current_unix_ts>" -H "X-Admin-Token: invalidtoken"
curl -sS -D - -X POST https://reproute.onrender.com/routes \
  -H "content-type: application/json" \
  --data '{"origin":"Indianapolis, IN","stops":["Carmel, IN"]}'
curl -sS -D - https://reproute.onrender.com/saved-leads/today
curl -sS -D - https://reproute.onrender.com/export/saved-leads.csv
```

## Results

### Test suites and builds
- Backend security suite: **pass** (`58 passed in 0.94s`)
- Frontend `typecheck`: **pass**
- Frontend `build`: **pass** (non-blocking Vite chunk-size warnings)

### Security scans
- Initial scan attempt (before remediation):
  - `pip-audit`: **fail** (`pip 25.1.1` advisories + `starlette 0.47.3` CVE)
  - `gitleaks detect`: **fail** (1 finding on docs placeholder text in commit history)
- Remediation applied:
  - `backend/requirements.txt`: pinned `starlette==0.49.1`
  - `.github/workflows/ci.yml`: added explicit `python -m pip install --upgrade pip` step in backend job
  - `.gitleaks.toml`: added allowlist for known historical false-positive commit fingerprint
  - `docs/DEPLOYMENT_GUIDE.md`: placeholder text changed from `<shared-hmac-secret>` to `<set-in-secret-store>`
- Final scan rerun:
  - `pip-audit`: **pass** (`No known vulnerabilities found`)
  - `gitleaks detect`: **pass** (`no leaks found`)
- `npm audit --audit-level=high`: **pass at configured threshold**
  - reported `2 moderate` vulnerabilities (`vite`/`esbuild` chain), none high+

### Staging smoke and negative auth/HMAC checks
- `GET /health`: **200** with `{"status":"ok","db":"ok","redis":"ok"}`
- `POST /admin/validation/run-due` with missing headers: **401** (`Missing admin token headers`)
- `POST /admin/validation/run-due` with invalid signature: **401** (`Validation admin token invalid`)
- `POST /routes` without bearer token: **401** (`Missing bearer token`)
- `GET /saved-leads/today` without bearer token: **401** (`Missing bearer token`)
- `GET /export/saved-leads.csv` without bearer token: **401** (`Missing bearer token`)

### Frontend bundle secret grep
- `grep` check for `sk_|DATABASE_URL|service_role` in `frontend/dist`: **pass** (`no matches`)

## Gate 1 Status After This Run

- Verified in this session:
  - startup/security/authz/admin/HMAC tests
  - auth/HMAC rejection behavior in staging
  - `/health` staging smoke and security headers presence
- Still open before Gate 1 can be fully closed:
  - capture authenticated staging smoke for route+lead fetch/today/export success paths
  - attach CI run URL(s) for the same verification set
