{{ config(materialized='view') }}

WITH raw_data AS (
    SELECT *
    FROM {{ source('raw_djinni', 'djinni_market_snapshot') }}
)

SELECT
    CAST(snapshot_date AS DATE) AS snapshot_date,
    CAST(category AS VARCHAR(255)) AS category,
    CAST(experience_years AS VARCHAR(50)) AS experience_years,

    CASE experience_years
        WHEN '< 1' THEN 0
        WHEN '1'   THEN 1
        WHEN '2'   THEN 2
        WHEN '3'   THEN 3
        WHEN '5+'  THEN 5
        ELSE NULL
    END AS experience_sort_key,

    CAST(work_format AS VARCHAR(50)) AS work_format,

    CAST(candidates_count AS INTEGER) AS candidates_count,
    CAST(candidates_diff AS INTEGER) AS candidates_diff,
    CAST(candidates_avg_pokes AS NUMERIC(5,2)) AS candidates_avg_pokes,

    CAST(jobs_count AS INTEGER) AS jobs_count,
    CAST(jobs_diff AS INTEGER) AS jobs_diff,
    CAST(jobs_avg_applies AS NUMERIC(5,2)) AS jobs_avg_applies,

    CAST(djinni_index AS NUMERIC(5,2)) AS djinni_index,
    CAST(index_diff AS NUMERIC(5,2)) AS index_diff,
    CAST(index_applies_total AS INTEGER) AS index_applies_total,
    CAST(index_pokes_total AS INTEGER) AS index_pokes_total,

    CAST(cand_salary_min AS NUMERIC) AS cand_salary_min,
    CAST(cand_salary_mid AS NUMERIC) AS cand_salary_mid,
    CAST(cand_salary_max AS NUMERIC) AS cand_salary_max,

    CAST(jobs_salary_min AS NUMERIC) AS jobs_salary_min,
    CAST(jobs_salary_mid AS NUMERIC) AS jobs_salary_mid,
    CAST(jobs_salary_max AS NUMERIC) AS jobs_salary_max,

    CAST(updated_at AS TIMESTAMP) AS updated_at
FROM raw_data