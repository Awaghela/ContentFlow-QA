# ContentFlow QA — Deployment Guide

## Architecture

```
┌─────────────────┐      HTTPS       ┌──────────────────┐
│   Frontend      │ ───────────────► │   FastAPI        │
│   (Vercel)      │   /api/*         │   (Railway)      │
│   index.html    │ ◄─────────────── │   backend/       │
└─────────────────┘   JSON           └────────┬─────────┘
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │  PostgreSQL      │
                                     │  (Railway)       │
                                     └──────────────────┘
```

## 1. Backend on Railway

Already deployed at:
```
https://contentflow-qa-production.up.railway.app
```

Verify:
- `GET /` → service info
- `GET /docs` → interactive Swagger UI
- `GET /api/partners` → 4 seeded partners

## 2. Frontend on Vercel

```bash
cd frontend
npx vercel --prod
```

The frontend reads `API_BASE` from the top of the `<script>` block in `index.html`.
Change it if your Railway URL differs:

```js
const API_BASE = 'https://YOUR-APP.up.railway.app';
```

Or override at runtime from the browser console:
```js
localStorage.setItem('cfq_api', 'https://your-url.up.railway.app');
location.reload();
```

## 3. Local development

```bash
# Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend — just open it
open frontend/index.html
```

Set the API base to localhost in the browser console:
```js
localStorage.setItem('cfq_api', 'http://localhost:8000');
```

## 4. Docker Compose (all three services)

```bash
cp .env.example .env
docker-compose up --build
```

- Dashboard → http://localhost:3000
- API       → http://localhost:8000
- Postgres  → localhost:5432

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Service health |
| GET | `/api/metrics` | Platform aggregate metrics |
| GET | `/api/partners` | All partner profiles |
| GET | `/api/partners/{id}` | Partner detail + latest run |
| POST | `/api/partners` | Create a new partner |
| POST | `/api/partners/{id}/runs` | Trigger validation pipeline |
| GET | `/api/runs` | All validation runs |
| GET | `/api/runs/{id}` | Full run results |
| GET | `/api/runs/{id}/report` | Ops-review report |
| GET | `/api/scenarios` | Validation scenario catalogue |
| POST | `/api/upload` | Upload XML/JSON feed |

## Tests

```bash
python3 -m pytest backend/tests/test_workflows.py -v
# 35 workflow cases across 300 partner-content records
```
