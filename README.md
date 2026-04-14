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

Phase 0/1 scaffolding in progress. Provider credentials are placeholder-driven until infra setup is complete.
