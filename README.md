# Reproute

Route-aware prospecting PWA for field insurance agents.

## Monorepo layout

- `backend/` FastAPI service
- `frontend/` React + Vite PWA
- `infra/` Docker, Cloudflare Worker, and deploy config
- `scripts/` ingestion/backfill scripts
- `docs/` product docs

## Quickstart

1. Copy env templates:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
   Edit both files — the defaults work for local development with Docker.

2. Start local dependencies:
   ```bash
   docker compose -f infra/docker-compose.yml up -d db redis
   ```

3. Backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

Visit `http://localhost:5173`. Sign in via Clerk (set `VITE_CLERK_PUBLISHABLE_KEY` in `frontend/.env`).

## Deployment

See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) for full Render + Cloudflare Pages setup.
See [`docs/REQUIRED_SECRETS.md`](docs/REQUIRED_SECRETS.md) for the complete list of required env vars.

## Operations

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for:
- Triggering ingestion runs
- Quota exhaustion responses (ORS, Photon, Overpass, Clerk, validation caps)
- Backend / DB / Redis outage playbooks
- Cloudflare Worker troubleshooting
- Rollback steps (Render + Cloudflare Pages)
- Pilot participant SLA

## Status

Phases 1-7 code-complete. Evidence sign-off and platform setup (log forwarding, uptime monitor, alert rules) pending before pilot.

## Validation scripts

- Spatial query index evidence:
  ```bash
  python scripts/explain_candidate_query.py \
    --database-url "$INGEST_DATABASE_URL" \
    --route-id "<route_uuid>"
  ```
- Ingestion QA metrics:
  ```bash
  python scripts/ingest_overture.py \
    --parquet data/indianapolis_places.parquet \
    --database-url "$INGEST_DATABASE_URL"
  ```
- Scoring quality/latency harness:
  ```bash
  python scripts/validate_scoring.py \
    --api-base-url "http://localhost:8000" \
    --token "<jwt>" \
    --route-id "<id1>" \
    --route-id "<id2>"
  ```

See [`docs/PHASE1_4_VALIDATION.md`](docs/PHASE1_4_VALIDATION.md) for the full evidence playbook.
