# TerpAdvisor

Intelligent course recommendation engine for UMD students.

## Project Structure

- `backend/` — Python FastAPI backend with recommendation engine
- `frontend/` — Next.js + Tailwind frontend

## Backend Commands

```bash
cd backend
pip install -e ".[dev]"      # Install dependencies
python -m pytest tests/ -v   # Run tests (59 tests)
uvicorn app.main:app --reload  # Start dev server on :8000
```

## Frontend Commands

```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Start dev server on :3000
```

## Docker

```bash
docker-compose up  # Start Postgres, Redis, backend, Celery worker/beat
```

## Architecture Highlights

- `backend/app/engine/` — Core algorithms (DAG prereq engine, recommendation scorers, schedule CSP solver, interval tree)
- `backend/app/integrations/` — Resilient API clients with circuit breaker + rate limiter
- `backend/app/cache/` — Multi-layer cache (LRU → Redis → Postgres) with stampede prevention
- `backend/app/workers/` — Celery background tasks for ETL data pipeline

## API Endpoints

- `GET /api/health` — Health check
- `POST /api/recommendations` — Get personalized recommendations
- `GET /api/audit` — Degree audit
- `POST /api/plan` — Multi-semester plan generation
- `POST /api/schedule/generate` — CSP-based schedule optimization
