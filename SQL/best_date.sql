WITH RECURSIVE
future_dates AS (
    SELECT date('now', '+5 day') AS d
    UNION ALL
    SELECT date(d, '+1 day')
    FROM future_dates
    WHERE d < date('now', '+60 day')
),
capacity_per_day AS (
    SELECT 
        fd.d AS date,
        COALESCE(pc.max_sqft, 
                 (SELECT max_sqft 
                  FROM process_capacity 
                  WHERE process_name = 'Langston Saturn 50x110' AND date IS NULL)
        ) 
        - COALESCE((
            SELECT SUM(CAST(o.msf AS REAL))
            FROM order_routing o
            WHERE o.process_nme = 'Langston Saturn 50x110'
              AND substr(o.requested_dte,1,10) = fd.d
        ),0) AS available_sqft
    FROM future_dates fd
    LEFT JOIN process_capacity pc
        ON pc.date = fd.d 
       AND pc.process_name = 'Langston Saturn 50x110'
    WHERE strftime('%w', fd.d) NOT IN ('0','6') -- skip weekends
),
windows AS (
    -- Anchor
    SELECT 
        date AS start_date,
        date AS end_date,
        available_sqft,
        available_sqft AS total_available,
        1 AS days_used,
        date || ':' || available_sqft AS breakdown
    FROM capacity_per_day
    WHERE available_sqft > 0

    UNION ALL

    -- Recursive step
    SELECT 
        w.start_date,
        c.date AS end_date,
        c.available_sqft,
        w.total_available + c.available_sqft AS total_available,
        w.days_used + 1,
        w.breakdown || ' | ' || c.date || ':' || c.available_sqft
    FROM windows w
    JOIN capacity_per_day c
      ON c.date = date(w.end_date, '+1 day')
    WHERE w.days_used < 10   -- N: max consecutive days
)
SELECT start_date, end_date, total_available, days_used, breakdown
FROM windows
WHERE total_available >= 700000   -- job MSF requirement
  AND start_date IN (SELECT date FROM capacity_per_day WHERE available_sqft > 0)
ORDER BY start_date, days_used
LIMIT 1;
