# Deployment

Production topology:

| Layer | Service | Notes |
|---|---|---|
| Frontend | **Vercel** | Next.js, rewrites `/api/*` to the backend |
| Backend API + Celery worker + Celery beat | **Northflank** | three services from one image |
| Redis (cache + Celery broker) | **Northflank Redis addon** | |
| Postgres | **Neon** | serverless, autoscaling |

> Migrating off Render? Render's free plan only ran the web service — the Celery
> worker, beat, and Redis had nowhere to live. Northflank runs all of them, so this
> move also turns the background ETL and cache-warming back on.

---

## 1. Database — Neon

The Neon project (`terpadvisor`, db `neondb`) already has the schema applied.

1. In the [Neon console](https://console.neon.tech) → project → **Connect**, copy the
   **direct** connection string (not the `-pooler` one). The app keeps its own
   SQLAlchemy pool, so a direct endpoint avoids pgbouncer surprises.
2. Set it as `DATABASE_URL`. You can paste the console string verbatim —
   [`config.py`](../backend/app/config.py) normalizes it:
   - adds the `+asyncpg` driver,
   - strips libpq-only params (`sslmode`, `channel_binding`, `ssl`) that asyncpg rejects,
   - derives `DATABASE_URL_SYNC` (psycopg2, for Celery + Alembic),
   - auto-enables SSL for `*.neon.tech` hosts (`ssl=require` for asyncpg,
     `sslmode=require` for psycopg2, both via `connect_args`).
3. Apply migrations and seed:
   ```bash
   cd backend
   alembic upgrade head
   python scripts/seed_real_data.py     # or let the Celery ETL populate it
   ```
4. Migrating existing data off the old DB? `pg_dump` it and restore into Neon:
   ```bash
   pg_dump "$OLD_DATABASE_URL" -Fc -f dump.pgc
   pg_restore --no-owner -d "$NEON_DATABASE_URL_SYNC" dump.pgc
   ```

> **Pooled endpoint instead?** If you must use the `-pooler` host, the asyncpg engine
> already sets `statement_cache_size=0` ([`session.py`](../backend/app/db/session.py)),
> which is what keeps prepared statements working through pgbouncer transaction pooling.

---

## 2. Backend — Northflank

Create a project, then add a **Redis** addon (Marketplace → Redis). It exposes a
connection string used for both `REDIS_URL` and `CELERY_BROKER_URL`. This is the one
free managed database on the Sandbox tier (Postgres lives on Neon).

All services share the same build ([`backend/Dockerfile`](../backend/Dockerfile), build
context `backend/`) and differ only by start command.

**Free Sandbox tier (2 services + 1 database):** fold the scheduler into the worker
with Celery's embedded beat (`-B`), so you only need two services:

| Service | Start command | Public? |
|---|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | yes, port 8000 |
| `celery-worker` | `celery -A app.workers.celery_app worker -B --loglevel=warning` | no |

`-B` runs beat in-process. That's fine for a single worker; if you ever scale the worker
to >1 replica, split beat into its own service so the schedule doesn't fire multiple times:

| Service | Start command | Public? |
|---|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | yes, port 8000 |
| `celery-worker` | `celery -A app.workers.celery_app worker --loglevel=warning` | no |
| `celery-beat` | `celery -A app.workers.celery_app beat --loglevel=warning` | no |

Environment variables (set on all three):

```
DATABASE_URL=<neon direct connection string>
REDIS_URL=<northflank redis addon url>/0
CELERY_BROKER_URL=<northflank redis addon url>/1
CORS_ORIGINS=["https://<your-frontend>.vercel.app"]
SECRET_KEY=<random 32+ char string>
DEMO_MODE=false
```

`DATABASE_URL_SYNC` and `DATABASE_SSL` are derived automatically — only set them to
override.

---

## 3. Frontend — Vercel

- `NEXT_PUBLIC_API_URL` → the Northflank `api` service URL.
- Make sure that origin is listed in the backend's `CORS_ORIGINS`.

---

## 4. Cut over

1. Deploy Neon + Northflank, point the frontend at the new API.
2. Verify: `GET https://<api>/api/health` returns DB **and** Redis healthy.
3. Confirm the Celery beat schedule is firing (cache-warming task, every 6h).
4. Decommission the Render services. [`render.yaml`](../render.yaml) is kept only for
   reference and is no longer the source of truth.
