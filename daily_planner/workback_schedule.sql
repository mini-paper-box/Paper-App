-- 1️⃣ Create target table
CREATE TABLE IF NOT EXISTS workback_schedule (
    order_id INTEGER,
    order_line_nbr INTEGER,
    process_id INTEGER,
    process_nme TEXT,
    order_seq INTEGER,
    planned_start TEXT,
    planned_end TEXT
);

DELETE FROM workback_schedule;

-- 2️⃣ Recursive workback schedule
WITH RECURSIVE
OrderedProcesses AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (PARTITION BY r.order_id, r.order_line_nbr ORDER BY r.order_seq DESC) AS rn
    FROM order_routing r
    WHERE r.process_id != 234
),
AdjustedDates AS (
    -- Recursive function to move any date backward until it lands on a weekday and not a holiday
    SELECT date(substr(requested_dte,1,10), '-1 day') AS dt
    UNION ALL
    SELECT date(dt, '-1 day')
    FROM AdjustedDates
    WHERE strftime('%w', dt) IN ('0','6') OR dt IN (SELECT date FROM holiday)
),
Workback AS (
    -- Anchor: last process
    SELECT
        op.order_id,
        op.order_line_nbr,
        op.process_id,
        op.process_nme,
        op.order_seq,
        (SELECT MAX(dt) FROM AdjustedDates) AS planned_end,
        date((SELECT MAX(dt) FROM AdjustedDates), '-1 day') AS planned_start,
        op.rn
    FROM OrderedProcesses op
    WHERE op.rn = 1

    UNION ALL

    -- Recursive previous processes
    SELECT
        op.order_id,
        op.order_line_nbr,
        op.process_id,
        op.process_nme,
        op.order_seq,
        prev.planned_start AS planned_end,
        (
            -- subtract 1 day repeatedly until valid weekday and not holiday
            SELECT MAX(dt)
            FROM (
                SELECT date(prev.planned_start, '-' || n || ' day') AS dt
                FROM (SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5) nums
                WHERE strftime('%w', date(prev.planned_start, '-' || n || ' day')) NOT IN ('0','6')
                  AND date(prev.planned_start, '-' || n || ' day') NOT IN (SELECT date FROM holiday)
            )
        ) AS planned_start,
        op.rn
    FROM OrderedProcesses op
    JOIN Workback prev
      ON op.order_id = prev.order_id
     AND op.order_line_nbr = prev.order_line_nbr
     AND op.rn = prev.rn + 1
)

INSERT INTO workback_schedule (
    order_id, order_line_nbr, process_id, process_nme, order_seq, planned_start, planned_end
)
SELECT order_id, order_line_nbr, process_id, process_nme, order_seq, planned_start, planned_end
FROM Workback
ORDER BY order_id, order_line_nbr, order_seq;
