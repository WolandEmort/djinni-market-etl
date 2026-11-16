SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    candidates_count,
    jobs_count,
    candidates_per_job
FROM {{ ref('mart_market_trends') }}
WHERE jobs_count > 0
  AND ABS(candidates_per_job - ROUND(candidates_count::numeric / jobs_count, 2)) > 0.01