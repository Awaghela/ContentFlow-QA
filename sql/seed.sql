-- ContentFlow QA — Development Seed Data
-- Only inserts if the table is empty (safe to re-run)

INSERT INTO validation_runs (run_id, partner, status, asset_count, pass_count, fail_count, warn_count, pass_rate, created_at, completed_at)
SELECT * FROM (VALUES
  ('run-20260101', 'acme_studios', 'complete'::run_status, 500, 447, 31, 22, 89.40, '2026-01-10 09:00:00+00'::timestamptz, '2026-01-10 09:04:12+00'::timestamptz),
  ('run-20260108', 'globalmax',    'complete'::run_status, 320, 305, 12,  3, 95.31, '2026-01-15 14:30:00+00'::timestamptz, '2026-01-15 14:32:45+00'::timestamptz),
  ('run-20260115', 'indie_films',  'complete'::run_status, 80,   68, 10,  2, 85.00, '2026-01-20 11:00:00+00'::timestamptz, '2026-01-20 11:01:30+00'::timestamptz)
) AS v(run_id, partner, status, asset_count, pass_count, fail_count, warn_count, pass_rate, created_at, completed_at)
WHERE NOT EXISTS (SELECT 1 FROM validation_runs LIMIT 1);

INSERT INTO validation_results (run_id, asset_id, category, scenario, status, message)
SELECT * FROM (VALUES
  ('run-20260101', 'CF-0001', 'metadata',      'required_field_missing',  'fail'::issue_status, 'Required field title is missing'),
  ('run-20260101', 'CF-0002', 'metadata',      'invalid_rating',          'fail'::issue_status, 'Rating SUPER-SAFE is not recognised'),
  ('run-20260101', 'CF-0003', 'xml_feed',      'xml_parse_error',         'fail'::issue_status, 'XML is malformed'),
  ('run-20260101', 'CF-0004', 'media_probe',   'invalid_video_codec',     'fail'::issue_status, 'Codec wmv3 is not allowed'),
  ('run-20260101', 'CF-0005', 'duplicate_ids', 'duplicate_within_batch',  'fail'::issue_status, 'content_id appears 2 times'),
  ('run-20260101', 'CF-0006', 'golive',        'avail_expired',           'fail'::issue_status, 'Rights window expired 15 days ago'),
  ('run-20260101', 'CF-0007', 'metadata',      'recommended_fields',      'warn'::issue_status, 'synopsis, cast missing'),
  ('run-20260101', 'CF-0008', 'asset_check',   'not_served_from_cdn',     'warn'::issue_status, 'Not served from known CDN'),
  ('run-20260101', 'CF-0009', 'metadata',      'required_field_title',    'pass'::issue_status, 'title present'),
  ('run-20260101', 'CF-0010', 'golive',        'avail_start_ok',          'pass'::issue_status, 'Rights window open')
) AS v(run_id, asset_id, category, scenario, status, message)
WHERE NOT EXISTS (SELECT 1 FROM validation_results LIMIT 1);
