SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    cand_salary_min,
    cand_salary_max,
    jobs_salary_min,
    jobs_salary_max,
    candidates_per_job
FROM {{ ref('mart_market_trends') }}
WHERE cand_salary_min > cand_salary_max
   OR jobs_salary_min > jobs_salary_max
   OR candidates_per_job < 0