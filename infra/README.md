# Infrastructure Deployment

This directory contains the Cloudflare Worker for geocoding and deployment configuration.

## Quick Start

### 1. Install Wrangler CLI

```bash
npm install
```

### 2. Login to Cloudflare

```bash
npx wrangler login
```

This will open your browser to authenticate.

### 3. Create KV Namespaces

```bash
# Production namespace
npx wrangler kv:namespace create "GEOCODE_CACHE"

# Preview namespace for development
npx wrangler kv:namespace create "GEOCODE_CACHE" --preview
```

Copy the IDs from the output and update them in `wrangler.toml`.

### 4. Deploy

```bash
# Deploy to development
npm run deploy

# Deploy to staging
npm run deploy:staging

# Deploy to production
npm run deploy:production
```

### 5. Test Locally

```bash
# Run worker locally
npm run dev
```

Then test it:
```bash
curl "http://localhost:8787?q=Indianapolis&limit=5"
```

### 6. Monitor Logs

```bash
# Stream live logs
npm run tail
```

## Environment Variables

The worker uses these environment variables (configured in `wrangler.toml`):

- `PHOTON_BASE_URL`: Upstream geocoding service (default: Photon/Komoot)
- `GEOCODE_CACHE`: KV namespace binding for caching results

## Update Backend

After deployment, copy your worker URL and update the backend:

```bash
# In backend/.env
GEOCODE_WORKER_URL=https://reproute-geocode.YOUR_SUBDOMAIN.workers.dev
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `npm run deploy` | Deploy to development |
| `npm run deploy:staging` | Deploy to staging environment |
| `npm run deploy:production` | Deploy to production environment |
| `npm run dev` | Run worker locally for testing |
| `npm run tail` | Stream live logs from deployed worker |

## Architecture

```
Frontend/Backend
     ↓
Cloudflare Worker (geocode-worker.js)
     ↓
[Check KV Cache]
     ↓
Photon API (https://photon.komoot.io/api)
```

The worker provides:
- **Caching**: Results cached for 24 hours in KV
- **Performance**: Global edge network
- **Reliability**: Graceful degradation if upstream fails
- **Cost**: Free tier covers most usage
