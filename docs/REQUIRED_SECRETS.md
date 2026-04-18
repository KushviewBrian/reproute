# Required Secrets and IDs

Populate these before production deploys and CI releases.

## GitHub Actions secrets

- `RENDER_API_KEY`
- `RENDER_SERVICE_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_KV_NAMESPACE_ID`
- `CLOUDFLARE_R2_BUCKET`
- `DATABASE_URL`
- `CLERK_SECRET_KEY`
- `CLERK_PUBLISHABLE_KEY`
- `CLERK_JWT_ISSUER`
- `CLERK_JWKS_URL`
- `CLERK_AUDIENCE` (if configured in Clerk)
- `CLERK_AUTHORIZED_PARTY` (if configured in Clerk)
- `VALIDATION_HMAC_SECRET`
- `INGEST_DATABASE_URL` (for ingestion workflow)

## Runtime secrets (Render / backend)

- `DATABASE_URL`
- `DATABASE_SSL_CA_PEM`
- `SECRET_KEY`
- `REDIS_URL`
- `CLERK_JWT_ISSUER`
- `CLERK_JWKS_URL`
- `ADMIN_IMPORT_SECRET`
- `VALIDATION_HMAC_SECRET`

## Runtime non-secret config (must be explicitly set in production)

- `ENVIRONMENT=production`
- `POC_MODE=false`
- `DATABASE_TLS_VERIFY=true`
- `DATABASE_TLS_EMERGENCY_INSECURE_OVERRIDE=false`
- `CORS_ALLOW_ORIGINS=<exact frontend origins>`
- `VALIDATION_DAILY_CAP=50`
- `VALIDATION_MONTHLY_CAP=2000`
- `VALIDATION_PER_USER_DAILY_CAP=15`
- `VALIDATION_ADMIN_TOKEN_TTL_SECONDS=60`
- `ADMIN_ALLOWED_EMAILS=<comma-separated allowlist>`
- `ADMIN_IMPORT_ALLOWED_ROOTS=<comma-separated absolute paths>`

## Placeholder integration status

- Backend JWT verification supports JWKS signature verification + issuer/audience/azp checks when configured.
- Geocoding target points to `GEOCODE_WORKER_URL` placeholder until Worker is deployed.
