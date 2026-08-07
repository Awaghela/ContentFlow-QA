# ContentFlow QA — Media Partner Onboarding Validation Platform

> Built for Google resume · Jan 2026  
> Python · JavaScript · SQL · FFmpeg · XML · PostgreSQL · Docker

---

## What it does

ContentFlow QA is a production-grade quality gate for streaming platforms onboarding new content partners. Before any partner's movies or shows go live to viewers, ContentFlow automatically validates every submitted asset across **40 scenarios in 6 categories**, catches failures, and generates a structured ops report.

### Validation categories

| Category | Checks | Description |
|---|---|---|
| Metadata | 12 | title, genre, rating, language, duration, year, synopsis... |
| XML / Feed | 8 | XSD schema, encoding, namespace, malformed tags |
| Asset availability | 6 | URL reachability, HTTPS, CDN headers, redirects |
| FFmpeg media probe | 8 | codec, bitrate, resolution, container, audio |
| Duplicate IDs | 3 | content_id uniqueness within batch and cross-partner |
| Go-live readiness | 3 | rights windows, launch dates, ratings lock |

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI |
| Validation engine | Python validators, FFmpeg/ffprobe, xmlschema, lxml |
| Database | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| Frontend | Single-page HTML/JS dashboard (no framework needed) |
| Containerisation | Docker, Docker Compose |
| Testing | pytest, 14 passing tests |
| CLI | `scripts/run_validation.py` |

---

## Quick start

### Option A — Docker (recommended)

```bash
cp .env.example .env
docker-compose up --build
```

- **Dashboard** → http://localhost:3000
- **API docs** → http://localhost:8000/docs
- **API health** → http://localhost:8000/

### Option B — CLI only

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/run_validation.py --partner acme --count 500
```

### Option C — Open dashboard directly

The dashboard is a single HTML file with no dependencies:

```bash
open frontend/index.html
```

---

## Dashboard features

- **Per-partner detail pages** — each partner has its own page with full metrics, scenario breakdown, issues table, go-live readiness, pipeline log, and remediation checklist
- **Add partner flow** — upload form creates a new partner profile with its own page instantly
- **Platform overview** — aggregate metrics across all partners
- **Ops report** — executive summary, partner status matrix, top failure scenarios
- **Validation runs history** — all runs with pass rates and partner links
- **Issues view** — all failures and warnings across all partners in one table
- **Pipeline view** — tech stack, radar chart of scenario coverage per partner

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/api/metrics` | Platform-wide aggregate metrics |
| GET | `/api/runs` | List all validation runs |
| POST | `/api/runs?partner=name` | Trigger a new validation run |
| GET | `/api/runs/{run_id}` | Full run details + results |
| GET | `/api/runs/{run_id}/report` | Ops-ready issue report |
| POST | `/api/upload` | Upload XML/JSON feed file |

---

## Project structure

```
contentflow-v2/
├── backend/
│   ├── main.py               FastAPI app
│   ├── config.py             Environment config
│   ├── models.py             SQLAlchemy ORM models
│   ├── database.py           DB connection
│   ├── validators/
│   │   ├── metadata.py       Metadata field validation
│   │   ├── xml_feed.py       XML/JSON feed parsing
│   │   ├── asset_check.py    URL reachability probes
│   │   ├── media_probe.py    FFmpeg video analysis
│   │   ├── duplicate_ids.py  content_id uniqueness
│   │   └── golive.py         Go-live readiness gate
│   ├── reports/
│   │   └── summary.py        Ops report generator
│   └── tests/                pytest test suite (14 tests)
├── frontend/
│   └── index.html            Full dashboard (single file)
├── scripts/
│   ├── run_validation.py     CLI pipeline runner
│   └── generate_sample_data.py
├── sql/
│   ├── schema.sql            PostgreSQL tables + views
│   └── seed.sql              4 partners, 3 runs seed data
├── docker/
│   ├── Dockerfile.backend    Python + FFmpeg
│   └── Dockerfile.frontend   Static file server
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Sample output

```
ContentFlow QA — Partner: acme_studios
Assets: 500  ·  Scenarios: 40

  ✅ Metadata validation       pass=2994  fail= 18  warn= 22
  ❌ XML / Feed parsing        pass=2964  fail=  6  warn=  0
  ✅ Asset availability        pass= 824  fail= 46  warn= 84
  ❌ FFmpeg media probe        pass=1887  fail= 58  warn= 32
  ❌ Duplicate ID scan         pass= 980  fail= 20  warn=  0
  ❌ Go-live readiness gate    pass=1982  fail= 16  warn=  2

Total checks : 11,935
Pass rate    : 97.5%

⚠️  164 assets failed. Escalate to partner for remediation.
```
