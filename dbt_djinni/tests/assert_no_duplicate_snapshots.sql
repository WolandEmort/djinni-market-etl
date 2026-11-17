SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    COUNT(*) AS records_count
FROM {{ ref('mart_market_trends') }}
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1