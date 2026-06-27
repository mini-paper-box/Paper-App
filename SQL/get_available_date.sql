WITH params AS (
    SELECT 
        20000 AS job_msf, 
        15 AS max_consec_days,
        6  AS skip_weekdays       -- how many weekdays to skip before scheduling
),
process_sequence(seq_order, pid) AS (
    VALUES (1,2),(2,1)            -- define ordered process IDs
),
process_list AS (
    SELECT p.id, p.process_name, s.seq_order
    FROM process_sequence s
    JOIN process p ON p.id = s.pid
    ORDER BY s.seq_order
),
process_count AS (
    SELECT COUNT(*) AS n FROM process_list
),
future_dates AS (
    -- Anchor: today
    SELECT date('now') AS d, 0 AS weekday_count
    UNION ALL
    -- Recursive: add 1 day
    SELECT date(d, '+1 day'),
           CASE 
               WHEN strftime('%w', date(d, '+1 day')) NOT IN ('0','6') 
                    AND NOT EXISTS (SELECT 1 FROM holiday h WHERE h.date = date(d, '+1 day'))
               THEN weekday_count + 1 
               ELSE weekday_count 
           END
    FROM future_dates
    WHERE weekday_count < (SELECT skip_weekdays + 60 FROM params) -- enough lookahead
),
future_workdays AS (
    -- Only valid workdays after skipping the first N weekdays
    SELECT d
    FROM future_dates, params
    WHERE weekday_count >= params.skip_weekdays
      AND strftime('%w', d) NOT IN ('0','6')
      AND NOT EXISTS (SELECT 1 FROM holiday h WHERE h.date = d)
),
capacity_per_day AS (
    SELECT 
        fd.d AS date,
        p.seq_order,
        p.process_name,
        COALESCE(pc.max_sqft,
                 (SELECT max_sqft 
                  FROM process_capacity
                  WHERE process_name = p.process_name 
                    AND date IS NULL)
        )
        - COALESCE((
            SELECT SUM(CAST(o.msf AS REAL))
            FROM order_routing o
            WHERE o.process_nme = p.process_name
              AND substr(o.scheduled_dte,1,10) = fd.d
        ),0) AS available_sqft
    FROM future_workdays fd
    JOIN process_list p
    LEFT JOIN process_capacity pc
           ON pc.date = fd.d AND pc.process_name = p.process_name
),
windows AS (
    SELECT 
        seq_order,
        process_name,
        date AS start_date,
        date AS end_date,
        available_sqft,
        available_sqft AS total_available,
        1 AS days_used,
        date || ':' || available_sqft AS breakdown
    FROM capacity_per_day
    WHERE available_sqft > 0

    UNION ALL

    SELECT
        w.seq_order,
        w.process_name,
        w.start_date,
        c.date AS end_date,
        c.available_sqft,
        w.total_available + c.available_sqft AS total_available,
        w.days_used + 1 AS days_used,
        w.breakdown || ' | ' || c.date || ':' || c.available_sqft AS breakdown
    FROM windows w
    JOIN capacity_per_day c
      ON c.process_name = w.process_name
     AND c.date = (
           SELECT MIN(fd2.date)
           FROM capacity_per_day fd2
           WHERE fd2.process_name = w.process_name
             AND fd2.date > w.end_date
             AND fd2.available_sqft > 0
       )
    JOIN params p
      ON w.total_available < p.job_msf
     AND w.days_used < p.max_consec_days
),
feasible_windows AS (
    SELECT w.* 
    FROM windows w, params
    WHERE w.total_available >= params.job_msf
),
chain AS (
    -- Anchor: first process earliest feasible window
    SELECT
        f.seq_order,
        f.process_name,
        f.start_date,
        f.end_date,
        f.total_available,
        f.breakdown,
        f.start_date AS chain_start,
        f.end_date   AS chain_end
    FROM feasible_windows f
    WHERE f.seq_order = 1
      AND f.start_date = (SELECT MIN(start_date) 
                          FROM feasible_windows 
                          WHERE seq_order = 1)
      AND f.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows
            WHERE seq_order = 1
              AND start_date = (SELECT MIN(start_date) 
                                FROM feasible_windows 
                                WHERE seq_order = 1)
        )

    UNION ALL

    -- Recursive: link next process
    SELECT
        n.seq_order,
        n.process_name,
        n.start_date,
        n.end_date,
        n.total_available,
        n.breakdown,
        ch.chain_start,
        n.end_date AS chain_end
    FROM chain ch
    JOIN feasible_windows n
      ON n.seq_order = ch.seq_order + 1
     AND n.start_date >= date(ch.end_date, '+1 day')
    WHERE n.start_date = (
            SELECT MIN(start_date)
            FROM feasible_windows x
            WHERE x.seq_order = ch.seq_order + 1
              AND x.start_date >= date(ch.end_date, '+1 day')
        )
      AND n.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows x
            WHERE x.seq_order = ch.seq_order + 1
              AND x.start_date = (
                    SELECT MIN(start_date)
                    FROM feasible_windows y
                    WHERE y.seq_order = ch.seq_order + 1
                      AND y.start_date >= date(ch.end_date, '+1 day')
              )
        )
),
earliest_complete_chain AS (
    SELECT MIN(chain_start) AS chain_start
    FROM chain
    WHERE seq_order = (SELECT n FROM process_count)
)
SELECT
    ch.seq_order,
    ch.process_name,
    ch.start_date,
    ch.end_date,
    ch.total_available,
    ch.breakdown,
    ec.chain_start AS chain_start_date,
    (SELECT MAX(end_date) 
     FROM chain 
     WHERE chain_start = ec.chain_start) AS chain_end_date
FROM chain ch
CROSS JOIN earliest_complete_chain ec
WHERE ch.chain_start = ec.chain_start
ORDER BY ch.seq_order;
