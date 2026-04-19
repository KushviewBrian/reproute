# ReRoute Deployment Guide

This guide walks you through setting up all external services for ReRoute.

## Prerequisites

- Node.js 18+ installed
- Python 3.11+ installed
- Git repository connected to GitHub

## Production Reliability Baseline (Gate 0/1)

Use this as the required deployment contract before any `main` release:

- `ENVIRONMENT=production`
- `POC_MODE=false`
- `DATABASE_TLS_VERIFY=true`
- `DATABASE_SSL_CA_PEM` populated with the full provider CA chain (PEM text)
- `DATABASE_TLS_EMERGENCY_INSECURE_OVERRIDE=false` (default/off)
- `CLERK_JWT_ISSUER` and `CLERK_JWKS_URL` both set and valid
- `CORS_ALLOW_ORIGINS` includes the exact frontend origin(s), scheme included
- `VALIDATION_HMAC_SECRET` set (required for `/admin/validation/run-due`)

Post-deploy smoke checks (required):

1. `GET /health` returns `200`.
2. Route create + lead fetch succeeds.
3. Today dashboard loads without API network errors.
4. Saved leads export and route export succeed.
5. Validation endpoints auth behavior is correct:
   - user trigger/read works for owned data
   - admin run-due rejects missing/invalid HMAC headers.

---

## 1. Clerk Setup (Authentication)

### Steps:
1. Go to [clerk.com](https://clerk.com) and sign up
2. Click **"Add application"**
3. Choose authentication methods (Email, Google, etc.)
4. Once created, go to **API Keys** in the sidebar
5. Copy the following:
   - **Publishable Key** → Use in frontend
   - **Secret Key** → Keep secure, use in backend if needed

### JWT Template Configuration:
1. In Clerk Dashboard, go to **JWT Templates**
2. Click **"New template"** → Choose **"Blank"**
3. Name it: `reproute`
4. In the **Claims** section, add:
   ```json
   {
     "email": "{{user.primary_email_address}}",
     "email_verified": "{{user.primary_email_address_verified}}"
   }
   ```
5. Save the template
6. Copy the **Issuer URL** (looks like: `https://your-app.clerk.accounts.dev`)
7. The JWKS URL will be: `https://your-app.clerk.accounts.dev/.well-known/jwks.json`

### Environment Variables to Set:
```bash
# Frontend (.env)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...

# Backend (.env)
CLERK_JWT_ISSUER=https://your-app.clerk.accounts.dev
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
CLERK_AUDIENCE=  # Leave blank unless you set it in JWT template
CLERK_AUTHORIZED_PARTY=  # Leave blank unless you set it in JWT template
```

---

## 2. Cloudflare Worker Setup (Geocoding Cache)

### Steps:
1. Go to [cloudflare.com](https://cloudflare.com) and sign up
2. In the dashboard, click **Workers & Pages** in the sidebar
3. Click **Create Application** → **Create Worker**
4. Give it a name (e.g., `reproute-geocode`)

### Deploy with Wrangler:

```bash
# Navigate to infra directory
cd /Users/brian/reproute/infra

# Install Wrangler
npm install

# Login to Cloudflare
npx wrangler login

# Create KV namespace for caching
npx wrangler kv:namespace create "GEOCODE_CACHE"
# Copy the ID from output, e.g.: { binding = "GEOCODE_CACHE", id = "abc123..." }

# Create preview namespace for testing
npx wrangler kv:namespace create "GEOCODE_CACHE" --preview
# Copy the preview_id from output

# Edit wrangler.toml and replace "placeholder" with your actual IDs
```

### Update wrangler.toml:
Replace the placeholder IDs with the ones you just created:
```toml
kv_namespaces = [
  { binding = "GEOCODE_CACHE", id = "YOUR_ACTUAL_ID", preview_id = "YOUR_PREVIEW_ID" }
]
```

### Deploy:
```bash
# Deploy to development
npx wrangler deploy

# Your worker URL will be displayed, e.g.:
# https://reproute-geocode.your-subdomain.workers.dev
```

### Environment Variables to Set:
```bash
# Backend (.env)
GEOCODE_WORKER_URL=https://reproute-geocode.your-subdomain.workers.dev
```

---

## 3. Upstash Redis Setup (Caching)

### Steps:
1. Go to [upstash.com](https://upstash.com) and sign up
2. Click **Create Database**
3. Choose:
   - **Type**: Redis
   - **Name**: reproute-cache
   - **Region**: Choose closest to your backend (e.g., US East)
   - **Type**: Pay as you go (free tier available)
4. Click **Create**
5. In the database dashboard, open the **Redis** connection details
6. Copy the Redis connection URL (`rediss://...` recommended for production)

### Environment Variables to Set:
```bash
# Backend (.env)
REDIS_URL=rediss://default:<password>@<host>:<port>
```

---

## 4. Render Setup (Backend Hosting)

### Steps:
1. Go to [render.com](https://render.com) and sign up
2. Connect your GitHub account
3. Click **New** → **Web Service**
4. Select your `reproute` repository
5. Configure:
   - **Name**: reproute-backend
   - **Region**: Choose closest to your users
   - **Branch**: main
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (or Starter for production)

### Environment Variables in Render:
Add all these in the **Environment** section:

```
ENVIRONMENT=production
POC_MODE=false
DATABASE_URL=postgresql+asyncpg://postgres:<YOUR_DB_PASSWORD>@db.<YOUR_PROJECT_REF>.supabase.co:5432/postgres
DATABASE_TLS_VERIFY=true
DATABASE_SSL_CA_PEM=<full-pem-chain>
DATABASE_TLS_EMERGENCY_INSECURE_OVERRIDE=false
DATABASE_TLS_EMERGENCY_OVERRIDE_SUNSET=2026-06-30
REDIS_URL=rediss://default:<password>@<host>:<port>
SECRET_KEY=<generate-a-long-random-string>
CORS_ALLOW_ORIGINS=https://your-frontend-domain.com
GEOCODE_WORKER_URL=https://reproute-geocode.your-subdomain.workers.dev
ORS_BASE_URL=https://api.openrouteservice.org
ORS_API_KEY=<your-openrouteservice-key>
CLERK_JWT_ISSUER=https://your-app.clerk.accounts.dev
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
CLERK_AUDIENCE=
CLERK_AUTHORIZED_PARTY=
ADMIN_IMPORT_SECRET=<admin-import-secret>
ADMIN_ALLOWED_EMAILS=you@example.com
ADMIN_IMPORT_ALLOWED_ROOTS=/tmp,/var/data
VALIDATION_HMAC_SECRET=<shared-hmac-secret>
VALIDATION_DAILY_CAP=50
VALIDATION_MONTHLY_CAP=2000
VALIDATION_PER_USER_DAILY_CAP=15
VALIDATION_ADMIN_TOKEN_TTL_SECONDS=60
```

6. Click **Create Web Service**

### Get your backend URL:
Once deployed, Render will give you a URL like: `https://reproute-backend.onrender.com`

---

## 5. Deploy Frontend (Render or Vercel)

### Option A: Render
1. Click **New** → **Static Site**
2. Select your repository
3. Configure:
   - **Name**: reproute-frontend
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Publish Directory**: `dist`

### Option B: Vercel (Recommended)
1. Go to [vercel.com](https://vercel.com) and sign up
2. Click **Add New** → **Project**
3. Import your GitHub repository
4. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### Environment Variables for Frontend:
```
VITE_API_BASE_URL=https://reproute-backend.onrender.com
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

---

## 6. Final Steps

### Update CORS in Backend:
Update your backend `.env` or Render environment variables:
```
CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app,https://reproute-frontend.onrender.com
```

### Test the Deployment:
1. Visit your frontend URL
2. Try logging in with Clerk
3. Test creating a route
4. Check that geocoding works through Cloudflare Worker
5. Verify Redis caching is working
6. Verify `GET https://<backend>/health` returns `200`
7. Verify one `POST /admin/validation/run-due` call with invalid HMAC returns `401`

---

## Quick Reference

| Service | Purpose | URL Pattern |
|---------|---------|-------------|
| **Clerk** | Authentication | `https://your-app.clerk.accounts.dev` |
| **Cloudflare Worker** | Geocoding cache | `https://reproute-geocode.*.workers.dev` |
| **Upstash Redis** | Application cache | `redis://*` / `rediss://*` |
| **Render Backend** | API server | `https://reproute-backend.onrender.com` |
| **Vercel/Render Frontend** | Web app | `https://reproute.vercel.app` |

---

## Troubleshooting

### "CORS error" in browser:
- Make sure backend `CORS_ALLOW_ORIGINS` includes your frontend URL
- Restart the backend service after changing environment variables

### "Authentication failed":
- Verify Clerk JWT issuer and JWKS URLs are correct
- Check that JWT template includes `email` claim
- Ensure frontend has correct Clerk publishable key

### "Network error: unable to reach API":
- Verify frontend `VITE_API_BASE_URL` points to the backend host
- Verify backend `CORS_ALLOW_ORIGINS` includes the exact frontend origin
- Verify backend startup logs show no TLS/JWT/POC guard refusal
- Verify `DATABASE_SSL_CA_PEM` is present when `DATABASE_TLS_VERIFY=true`

### "Geocoding not working":
- Check Cloudflare Worker is deployed: visit the URL directly
- Verify `GEOCODE_WORKER_URL` in backend matches your worker URL
- Check KV namespace is properly bound in wrangler.toml

### "Redis connection error":
- Verify `REDIS_URL` format (must be Redis protocol URL, `redis://` or `rediss://`)
- App should degrade gracefully if Redis is unavailable
- Check Upstash dashboard for connection limits

---

## Cost Estimates (as of April 2026)

- **Clerk**: Free up to 10k MAU
- **Cloudflare Workers**: Free up to 100k requests/day
- **Upstash Redis**: Free up to 10k requests/day
- **Render**: Free tier available (sleeps after inactivity)
- **Vercel**: Free for personal projects

**Total for hobby/small projects: $0/month** 🎉
