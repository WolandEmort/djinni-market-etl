SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    cand_salary_min,
    cand_salary_max,
    jobs_salary_min,
    jobs_salary_max,
    candidates_per_job,
    salary_expectation_gap,
    candidates_change_7d
FROM {{ ref('mart_market_trends') }}
WHERE cand_salary_min > cand_salary_max
   OR jobs_salary_min > jobs_salary_max
   OR candidates_per_job < 0
   OR (cand_salary_mid IS NOT NULL AND jobs_salary_mid IS NOT NULL AND salary_expectation_gap != (cand_salary_mid - jobs_salary_mid))
   OR (candidates_count_7d_ago IS NOT NULL AND candidates_change_7d != (candidates_count - candidates_count_7d_ago))