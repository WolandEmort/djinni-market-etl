-- This test ensures there are no duplicate records for the same category, experience, and format on a single day.
-- If this query returns any rows, dbt will mark the test as failed.

SELECT
    snapshot_date,
    category,
    experience_years,
    work_format,
    COUNT(*) as records_count
FROM {{ ref('mart_market_overview') }}
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1