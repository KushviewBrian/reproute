# Required Secrets and IDs

Populate these while implementation continues.

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

## Runtime env vars

See `.env.example` for complete local defaults.

## Placeholder integration status

- Backend JWT verification supports JWKS signature verification + issuer/audience/azp checks when configured.
- Geocoding target points to `GEOCODE_WORKER_URL` placeholder until Worker is deployed.
