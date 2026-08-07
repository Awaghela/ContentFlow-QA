-- ContentFlow QA — PostgreSQL Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── ENUM TYPES (idempotent) ──────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE run_status AS ENUM ('queued', 'running', 'complete', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE issue_status AS ENUM ('pass', 'fail', 'warn');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── TABLES ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS validation_runs (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(16) NOT NULL UNIQUE,
    partner         VARCHAR(128) NOT NULL,
    status          run_status NOT NULL DEFAULT 'queued',
    asset_count     INTEGER NOT NULL DEFAULT 0,
    pass_count      INTEGER NOT NULL DEFAULT 0,
    fail_count      INTEGER NOT NULL DEFAULT 0,
    warn_count      INTEGER NOT NULL DEFAULT 0,
    pass_rate       NUMERIC(5,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runs_partner  ON validation_runs(partner);
CREATE INDEX IF NOT EXISTS idx_runs_status   ON validation_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created  ON validation_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS validation_results (
    id          BIGSERIAL PRIMARY KEY,
    run_id      VARCHAR(16) NOT NULL REFERENCES validation_runs(run_id) ON DELETE CASCADE,
    asset_id    VARCHAR(256) NOT NULL,
    category    VARCHAR(64) NOT NULL,
    scenario    VARCHAR(128) NOT NULL,
    status      issue_status NOT NULL,
    message     TEXT NOT NULL,
    detail      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_run_id   ON validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_asset_id ON validation_results(asset_id);
CREATE INDEX IF NOT EXISTS idx_results_status   ON validation_results(status);
CREATE INDEX IF NOT EXISTS idx_results_category ON validation_results(category);

-- ─── REPORTING VIEWS ──────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_run_category_summary AS
SELECT
    run_id,
    category,
    COUNT(*) FILTER (WHERE status = 'pass') AS pass_count,
    COUNT(*) FILTER (WHERE status = 'fail') AS fail_count,
    COUNT(*) FILTER (WHERE status = 'warn') AS warn_count,
    COUNT(*)                                AS total,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'pass')::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1
    ) AS pass_rate
FROM validation_results
GROUP BY run_id, category;

CREATE OR REPLACE VIEW v_top_failure_scenarios AS
SELECT
    category,
    scenario,
    COUNT(*) AS occurrence_count
FROM validation_results
WHERE status = 'fail'
GROUP BY category, scenario
ORDER BY occurrence_count DESC;
