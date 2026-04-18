## Summary

Describe what changed and why.

## Roadmap Link (Required)

- Roadmap phase/gate item: `docs/roadmap.md` section + bullet reference

## Evidence (Required)

List exact checks run and outcomes.

- [ ] Backend tests
- [ ] Frontend typecheck/build
- [ ] Security scans (gitleaks, pip-audit, npm audit)
- [ ] Additional targeted checks (if applicable)

Artifacts / logs:
- Evidence file(s):
- CI run URL(s):

## Rollback Note (Required)

If this deploy regresses production, specify immediate rollback steps.

1. Revert commit(s):
2. Redeploy service(s):
3. Validate `/health` + smoke checks:

## Risk Review

- User-facing behavior impacted:
- Config/env changes required:
- Backward compatibility concerns:
