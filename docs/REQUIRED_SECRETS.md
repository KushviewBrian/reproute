# Required Secrets and IDs

Populate these while implementation continues.

## GitHub Actions secrets

- `FLY_API_TOKEN`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_KV_NAMESPACE_ID`
- `CLOUDFLARE_R2_BUCKET`
- `DATABASE_URL`
- `CLERK_SECRET_KEY`
- `CLERK_PUBLISHABLE_KEY`
- `CLERK_JWT_ISSUER`

## Runtime env vars

See `.env.example` for complete local defaults.

## Placeholder integration status

- Backend JWT verification currently parses unverified claims with issuer check.
- Replace with full JWKS verification once Clerk tenant values are available.
- Geocoding target points to `GEOCODE_WORKER_URL` placeholder until Worker is deployed.
