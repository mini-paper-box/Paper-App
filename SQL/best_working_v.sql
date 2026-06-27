WITH params AS (
-- 1	Langston Saturn 50x110
-- 2	United Rotary 66x113 4 Colour
-- 3	Eterna
-- 4	Bobst Specialty Gluer 115"
-- 5	Box King
-- 6	Nozomi Digital Printer
-- 7	Corrugator
-- 8	Hot Glue Gun
-- 9	Stripping
-- 10	Co-Packing
-- 11	Hand Assembly
-- 12	Colex ICutter
-- 13	Elitron
-- 14	Hot Melt Hand Gluers Black Pot
-- 15	Haire Gluer
-- 16	TableSaw
-- 17	Farm Out
-- 18	Bundling
-- 19	Finished Good
-- 20	Slitter 90"

    SELECT 20000 AS job_msf, 15 AS max_consec_days  -- <-- set your MSF and N days
),
process_list AS (
    SELECT id, process_name, ROW_NUMBER() OVER (ORDER BY id) AS sequence_order
    FROM process
    WHERE id IN (6,3,4)  -- <-- which processes (in order)
),
process_count AS (
    SELECT COUNT(*) AS n FROM process_list
),
future_dates AS (
    SELECT date('now', '+4 day') AS d
    UNION ALL
    SELECT date(d, '+1 day')
    FROM future_dates
    WHERE d < date('now', '+60 day')
),
capacity_per_day AS (
    SELECT 
        fd.d AS date,
        p.sequence_order,
        p.process_name,
        -- capacity for that process/day (use date-specific capacity or default row where date IS NULL)
        COALESCE(pc.max_sqft,
                 (SELECT max_sqft FROM process_capacity
                  WHERE process_name = p.process_name AND date IS NULL)
        )
        - COALESCE((
            SELECT SUM(CAST(o.msf AS REAL))
            FROM order_routing o
            WHERE o.process_nme = p.process_name
              AND substr(o.scheduled_dte,1,10) = fd.d
        ),0) AS available_sqft
    FROM future_dates fd
    JOIN process_list p
    LEFT JOIN process_capacity pc
           ON pc.date = fd.d AND pc.process_name = p.process_name
    WHERE strftime('%w', fd.d) NOT IN ('0','6')  -- skip weekends
),
windows AS (
    -- Anchor: first available day for each process
    SELECT 
        sequence_order,
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

    -- Recursive: extend to next available date for the same process
    SELECT
        w.sequence_order,
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
      ON w.total_available < p.job_msf       -- continue until job is completed
     AND w.days_used < p.max_consec_days     -- enforce max consecutive days
),
feasible_windows AS (
    -- windows that can fit the job for that process
    SELECT w.*
    FROM windows w, params
    WHERE w.total_available >= params.job_msf
),
-- Build chains in sequence, always picking the earliest next feasible window
chain AS (
    -- Anchor: earliest feasible window for the first process
    SELECT
        f.sequence_order,
        f.process_name,
        f.start_date,
        f.end_date,
        f.total_available,
        f.breakdown,
        f.start_date AS chain_start,
        f.end_date   AS chain_end
    FROM feasible_windows f
    WHERE f.sequence_order = 1
      AND f.start_date = (
            SELECT MIN(start_date)
            FROM feasible_windows
            WHERE sequence_order = 1
        )
      AND f.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows
            WHERE sequence_order = 1
              AND start_date = (
                    SELECT MIN(start_date)
                    FROM feasible_windows
                    WHERE sequence_order = 1
              )
        )

    UNION ALL

    -- Recursive: pick the earliest feasible window for next process that starts AFTER the previous ends
    SELECT
        n.sequence_order,
        n.process_name,
        n.start_date,
        n.end_date,
        n.total_available,
        n.breakdown,
        ch.chain_start,
        n.end_date AS chain_end
    FROM chain ch
    JOIN feasible_windows n
      ON n.sequence_order = ch.sequence_order + 1
     AND n.start_date >= date(ch.end_date, '+1 day')
    WHERE n.start_date = (
            SELECT MIN(start_date)
            FROM feasible_windows x
            WHERE x.sequence_order = ch.sequence_order + 1
              AND x.start_date >= date(ch.end_date, '+1 day')
        )
      AND n.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows x
            WHERE x.sequence_order = ch.sequence_order + 1
              AND x.start_date = (
                    SELECT MIN(start_date)
                    FROM feasible_windows y
                    WHERE y.sequence_order = ch.sequence_order + 1
                      AND y.start_date >= date(ch.end_date, '+1 day')
              )
        )
),
-- Among all chains that actually reach the last process, pick the earliest chain start
earliest_complete_chain AS (
    SELECT MIN(chain_start) AS chain_start
    FROM chain
    WHERE sequence_order = (SELECT n FROM process_count)
)
SELECT
    ch.sequence_order,
    ch.process_name,
    ch.start_date,
    ch.end_date,
    ch.total_available,
    ch.breakdown,
    ec.chain_start AS chain_start_date,
    (SELECT MAX(end_date) FROM chain WHERE chain_start = ec.chain_start) AS chain_end_date
FROM chain ch
CROSS JOIN earliest_complete_chain ec
WHERE ch.chain_start = ec.chain_start
ORDER BY ch.sequence_order;
