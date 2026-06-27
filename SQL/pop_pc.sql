WITH RECURSIVE future_dates(d) AS (
    SELECT date('now')  -- start from today
    UNION ALL
    SELECT date(d, '+1 day')
    FROM future_dates
    WHERE d < date('now', '+90 day')  -- 90 days ahead
)
INSERT INTO process_capacity (process_name, date, max_sqft)
SELECT
    def.process_name,
    fd.d,
    def.max_sqft
FROM future_dates fd
CROSS JOIN process_capacity def
WHERE def.date IS NULL
  AND strftime('%w', fd.d) NOT IN ('0','6') -- skip weekends
  AND NOT EXISTS (
      SELECT 1
      FROM process_capacity pc
      WHERE pc.process_name = def.process_name
        AND pc.date = fd.d
  );