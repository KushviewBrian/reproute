# Reproute

Route-aware prospecting PWA for field insurance agents.

## Monorepo layout

- `backend/` FastAPI service
- `frontend/` React + Vite PWA
- `infra/` Docker and deploy config
- `scripts/` ingestion/backfill scripts
- `docs/` product docs

## Quickstart

1. Copy env template:
   ```bash
   cp .env.example .env
   ```
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

## Status

Core Phase 1-4 prototype flow is implemented (route -> leads -> save -> notes -> export).

## Validation scripts

- Spatial query index evidence:
  - `python scripts/explain_candidate_query.py --database-url "$INGEST_DATABASE_URL" --route-id "<route_uuid>"`
- Ingestion QA metrics:
  - `python scripts/ingest_overture.py --parquet data/indianapolis_places.parquet --database-url "$INGEST_DATABASE_URL"`
- Scoring quality/latency harness:
  - `python scripts/validate_scoring.py --api-base-url "http://localhost:8000" --token "<jwt>" --route-id "<id1>" --route-id "<id2>"`

See [docs/PHASE1_4_VALIDATION.md](/Users/brian/reproute/docs/PHASE1_4_VALIDATION.md) for the full playbook.
