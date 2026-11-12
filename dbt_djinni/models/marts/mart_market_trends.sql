{{ config(materialized='table') }}

WITH stg_market AS (
    SELECT *
    FROM {{ ref('stg_djinni_market_snapshot') }}
    WHERE candidates_count IS NOT NULL OR jobs_count IS NOT NULL
),

current_data AS (
    SELECT
        snapshot_date,
        category,
        experience_years,
        experience_sort_key,
        work_format,
        candidates_count,
        jobs_count,
        cand_salary_mid,
        jobs_salary_mid,
        ROUND(candidates_count / NULLIF(jobs_count, 0), 2) AS candidates_per_job,
        (cand_salary_mid - jobs_salary_mid) AS salary_expectation_gap
    FROM stg_market
)

SELECT
    c.snapshot_date,
    c.category,
    c.experience_years,
    c.experience_sort_key,
    c.work_format,

    c.candidates_count,
    c.jobs_count,
    c.candidates_per_job,
    c.cand_salary_mid,
    c.jobs_salary_mid,
    c.salary_expectation_gap,

    prev_7d.candidates_count AS candidates_count_7d_ago,
    (c.candidates_count - prev_7d.candidates_count) AS candidates_change_7d,

    prev_7d.jobs_count AS jobs_count_7d_ago,
    (c.jobs_count - prev_7d.jobs_count) AS jobs_change_7d,

    (c.candidates_per_job - prev_7d.candidates_per_job) AS competition_change_7d,

    prev_30d.candidates_count AS candidates_count_30d_ago,
    (c.candidates_count - prev_30d.candidates_count) AS candidates_change_30d,

    prev_30d.jobs_count AS jobs_count_30d_ago,
    (c.jobs_count - prev_30d.jobs_count) AS jobs_change_30d

FROM current_data c
LEFT JOIN current_data prev_7d
    ON c.category = prev_7d.category
    AND c.experience_years = prev_7d.experience_years
    AND c.work_format = prev_7d.work_format
    AND prev_7d.snapshot_date = c.snapshot_date - INTERVAL '7 days'

LEFT JOIN current_data prev_30d
    ON c.category = prev_30d.category
    AND c.experience_years = prev_30d.experience_years
    AND c.work_format = prev_30d.work_format
    AND prev_30d.snapshot_date = c.snapshot_date - INTERVAL '30 days'