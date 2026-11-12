{{ config(materialized='view') }}

WITH raw_data AS (
    SELECT *
    FROM {{ source('raw_djinni', 'djinni_market_snapshot') }}
)

SELECT
    CAST(snapshot_date AS DATE) AS snapshot_date,
    category,
    experience_years,

    CASE experience_years
        WHEN '< 1' THEN 0
        WHEN '1'   THEN 1
        WHEN '2'   THEN 2
        WHEN '3'   THEN 3
        WHEN '5+'  THEN 5
        ELSE NULL
    END AS experience_sort_key,

    work_format,

    candidates_count,
    jobs_count,
    cand_salary_min,
    cand_salary_mid,
    cand_salary_max,
    jobs_salary_min,
    jobs_salary_mid,
    jobs_salary_max,

    updated_at
FROM raw_data