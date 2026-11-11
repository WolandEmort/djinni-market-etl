{{ config(materialized='view') }}

WITH raw_data AS (
    SELECT *
    FROM {{ source('raw_djinni', 'djinni_market_snapshot') }}
)

SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    candidates_count,
    jobs_count,

    -- Calculate competition: candidates per 1 job
    -- NULLIF prevents division by zero errors
    ROUND(candidates_count / NULLIF(jobs_count, 0), 2) AS candidates_per_job,

    cand_salary_mid,
    jobs_salary_mid,

    -- Financial metric: gap between candidate expectations and market offers
    -- Positive value: candidates expect more. Negative value: market offers more.
    (cand_salary_mid - jobs_salary_mid) AS salary_expectation_gap

FROM raw_data
-- Filter out empty rows where there are neither candidates nor jobs
WHERE candidates_count IS NOT NULL OR jobs_count IS NOT NULL