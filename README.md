# TerpAdvisor

Intelligent course recommendation engine for UMD students. Combines a DAG-based prerequisite resolver, a multi-scorer recommendation pipeline, a CSP-based schedule optimizer, and a multi-semester graduation planner into a single full-stack web app.

**Live demo**: _coming soon_

---

## What it does

Course selection at UMD requires juggling Testudo, PlanetTerp, degree audit sheets, and scheduling constraints simultaneously. TerpAdvisor answers: **"Given what I've taken, what I still need, and how I like to learn — what should I take next semester?"**

### Core features

**Transcript import** — Paste raw Testudo transcript text or upload a PDF. The parser extracts completed courses, credits, grades, and gen-ed tags, handling withdrawals, repeats, and AP/transfer credits automatically.

**Degree audit** — Full requirement tracking for CS, Math, Information Science, Economics, Biological Sciences, and Mechanical Engineering. Shows progress per requirement group, remaining course options, and which courses satisfy the most unmet requirements.

**Smart recommendations** — Six scoring dimensions combined with user-adjustable weights:

| Scorer | Default weight | Signal |
|---|---|---|
| Requirement fulfillment | 35% | How many unmet requirements this course satisfies |
| GPA | 25% | Average grade from PlanetTerp grade distributions |
| Professor rating | 15% | PlanetTerp professor scores for offered sections |
| Review sentiment | 10% | NLTK keyword analysis of student reviews |
| Schedule fit | 10% | Conflict-free with already-selected sections |
| Students also took | 5% | Co-enrollment frequency (collaborative filtering) |

Each recommendation returns a full explanation breakdown and a one-sentence top reason.

**Schedule builder** — CSP solver (backtracking + forward checking) generates conflict-free schedules from your course selections, ranked by time preferences, gap minimization, day balance, and seat availability. Exports to `.ics` for direct import into Google Calendar.

**Multi-semester planner** — Topological sort over remaining required courses, greedily packed into semesters respecting credit caps and prerequisite ordering. Returns labeled semesters with warnings for unresolvable prereqs.

**Course detail** — GPA, full grade distribution, professor ratings, student reviews, prerequisites with your completion status, and section times — all from PlanetTerp and umd.io, cached in a three-tier store.

---

## Architecture

```
Frontend (Next.js + Tailwind)
    └── /api/* rewrites → Backend (FastAPI)
                              ├── DAG prereq engine
                              ├── Recommendation scorers
                              ├── CSP schedule solver
                              ├── Interval tree (conflict detection)
                              ├── Multi-layer cache (LRU → Redis → Postgres)
                              ├── Circuit breaker + rate limiter
                              └── External APIs: PlanetTerp, umd.io
```

**Stack**: Next.js 14 (App Router) · FastAPI · PostgreSQL · Redis · SQLAlchemy (async) · Celery · Docker

---

## Running locally

### Prerequisites

- Docker + Docker Compose
- Node 20+ and Python 3.11+

### With Docker (recommended)

```bash
docker-compose up
```

This starts Postgres, Redis, the FastAPI backend on `:8000`, and the Next.js frontend on `:3000`.

### Without Docker

**Backend**
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

The backend requires a running Postgres and Redis instance. Copy `.env.example` to `.env` and set `DATABASE_URL` and `REDIS_URL`.

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (DB + Redis status) |
| `POST` | `/api/recommendations` | Ranked course recommendations |
| `POST` | `/api/audit` | Degree audit with per-requirement progress |
| `POST` | `/api/plan` | Multi-semester graduation plan |
| `POST` | `/api/schedule/generate` | CSP-based schedule optimization |
| `POST` | `/api/schedule/export/ical` | Export schedule as `.ics` |
| `GET` | `/api/courses/{id}` | Course detail (grades, reviews, sections) |
| `POST` | `/api/courses/parse-transcript` | Parse pasted transcript text |
| `POST` | `/api/courses/parse-transcript-pdf` | Parse uploaded transcript PDF |

Interactive docs available at `http://localhost:8000/docs` when running locally.

---

## Tests

```bash
cd backend
python -m pytest tests/ -v   # 59 tests
```

---

## Deployment

See the [deployment guide](docs/deployment.md) for deploying free on Vercel (frontend) + Render (backend) + Neon (Postgres) + Upstash (Redis).

---

## Project structure

```
TerpAdvisor/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI route handlers
│   │   ├── engine/          # Core algorithms
│   │   │   ├── course_graph.py      # DAG prereq resolver
│   │   │   ├── recommender.py       # Recommendation pipeline
│   │   │   ├── scorers/             # Pluggable scoring strategies
│   │   │   ├── schedule_solver.py   # CSP schedule builder
│   │   │   ├── interval_tree.py     # Time conflict detection
│   │   │   ├── degree_audit.py      # Requirement tracking
│   │   │   └── planner.py           # Multi-semester planner
│   │   ├── integrations/    # PlanetTerp + umd.io clients
│   │   ├── cache/           # Multi-layer cache (LRU → Redis → Postgres)
│   │   ├── workers/         # Celery ETL tasks
│   │   └── models/          # SQLAlchemy models
│   └── tests/
└── frontend/
    └── src/
        ├── app/             # Next.js App Router pages
        └── components/      # UI components
```
