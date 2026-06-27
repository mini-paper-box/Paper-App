DECLARE @lookahead_days INT = 60;
DECLARE @run_qty INT = 30000;
DECLARE @docket INT = 170024;
DECLARE @lead_time INT = 4;

SET DATEFIRST 1; -- Monday = 1

---------------------------------------------------
-- Step 1: Docket routing
---------------------------------------------------
WITH docket_routing_cte AS (
    SELECT
        dr.docket_id,
        dr.sequence AS seq_order,
        dr.process_id,
        dr.routing_dsc AS process_name,
        @run_qty * (d.sqfpm / 1000.0) AS run_sqft
    FROM docket d
    JOIN docket_routing dr
        ON dr.docket_id = CASE 
                             WHEN d.linked_docket_id > 0 THEN d.linked_docket_id 
                             ELSE d.docket_id 
                          END
    WHERE d.docket_id = @docket
),

---------------------------------------------------
-- Step 2: Assign sequential chain steps
---------------------------------------------------
docket_routing_ordered AS (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY seq_order) AS chain_step,
        -- First process needs lead time, others start after previous completes
        CASE WHEN ROW_NUMBER() OVER (ORDER BY seq_order) = 1 
             THEN @lead_time 
             ELSE 0 
        END AS process_lead_time
    FROM docket_routing_cte
),

---------------------------------------------------
-- Step 3: Future workdays (skip weekends & holidays)
---------------------------------------------------
future_dates AS (
    -- Start lookahead from today + lead time
    SELECT DATEADD(DAY, @lead_time, CAST(GETDATE() AS DATE)) AS d, 0 AS weekday_count
    UNION ALL
    SELECT DATEADD(DAY, 1, d),
           CASE WHEN DATEPART(WEEKDAY, DATEADD(DAY,1,d)) NOT IN (6,7)
                    AND NOT EXISTS (SELECT 1 FROM company_holidays h WHERE h.holiday_dte = DATEADD(DAY,1,d))
                THEN weekday_count + 1 ELSE weekday_count END
    FROM future_dates
    WHERE weekday_count < @lookahead_days
),
future_workdays AS (
    SELECT d
    FROM future_dates
    WHERE DATEPART(WEEKDAY,d) NOT IN (6,7)
      AND NOT EXISTS (SELECT 1 FROM company_holidays h WHERE h.holiday_dte = d)
),

---------------------------------------------------
-- Step 4: Historical process tracking
---------------------------------------------------
track_process AS (
    SELECT 
        t.docket_id,
        t.process_id,
        t.process_nme,
        CAST(t.start_date AS DATE) AS process_date,
        c.qty_per_min,
        t.setup_min,
        t.run_min,
        c.qty_per_min * (d.sqfpm / 1000.0) AS sqft_per_min,
        t.process_qty * (d.sqfpm / 1000.0) AS total_process_sqft
    FROM track t
    JOIN docket d ON d.docket_id = t.docket_id
    CROSS APPLY (SELECT CAST(t.process_qty AS DECIMAL(18,4)) / NULLIF(t.run_min,0)) c(qty_per_min)
    WHERE t.run_min > 0
),

process_data AS (
    SELECT 
        process_id,
        process_date,
        COUNT(*) AS job_process_per_day,
        SUM(run_min) AS total_run_time,
        SUM(setup_min) AS total_setup_time,
        SUM(total_process_sqft) AS total_msf
    FROM track_process
    GROUP BY process_id, process_date
),

process_capacity AS (
    SELECT 
        process_id,
        AVG(job_process_per_day * 1.0) AS avg_job,
        AVG(total_msf) AS avg_sqft,
        MAX(total_msf) AS max_sqft
    FROM process_data
    GROUP BY process_id
),

---------------------------------------------------
-- Step 5: Booked capacity per day
---------------------------------------------------
booked_per_day AS (
    SELECT
        sv.process_id,
        CAST(sv.schedule_dte AS DATE) AS schedule_date,
        SUM(sv.msf) AS booked_sqft,
        COUNT(*) AS booked_jobs
    FROM schedule_view sv
    WHERE sv.schedule_dte >= CAST(GETDATE() AS DATE)
      AND sv.schedule_dte < DATEADD(DAY, @lookahead_days * 2, CAST(GETDATE() AS DATE))
    GROUP BY sv.process_id, CAST(sv.schedule_dte AS DATE)
),

---------------------------------------------------
-- Step 6: Capacity per day
---------------------------------------------------
capacity_per_day AS (
    SELECT
        fd.d AS date,
        drc.seq_order,
        drc.chain_step,
        drc.process_id,
        drc.process_name,
        drc.run_sqft,
        ISNULL(pc.avg_job,0) - ISNULL(b.booked_jobs,0) AS available_jobs,
        ISNULL(pc.avg_sqft,0) - ISNULL(b.booked_sqft,0) AS available_sqft
    FROM future_workdays fd
    CROSS JOIN docket_routing_ordered drc
    LEFT JOIN process_capacity pc
        ON drc.process_id = pc.process_id
    LEFT JOIN booked_per_day b
        ON drc.process_id = b.process_id
       AND b.schedule_date = fd.d
),

---------------------------------------------------
-- Step 7: Running capacity totals with proper windowing
---------------------------------------------------
capacity_running AS (
    SELECT
        seq_order,
        chain_step,
        process_id,
        process_name,
        date,
        run_sqft,
        available_sqft,
        available_jobs,
        -- Cumulative capacity - but reset when we have a gap
        SUM(CASE WHEN available_sqft > 0 THEN available_sqft ELSE 0 END) OVER (
            PARTITION BY process_id 
            ORDER BY date 
            ROWS UNBOUNDED PRECEDING
        ) AS cumulative_sqft,
        SUM(CASE WHEN available_jobs > 0 THEN available_jobs ELSE 0 END) OVER (
            PARTITION BY process_id 
            ORDER BY date 
            ROWS UNBOUNDED PRECEDING
        ) AS cumulative_jobs
    FROM capacity_per_day
),

---------------------------------------------------
-- Step 8: Find windows where process can complete
---------------------------------------------------
process_windows AS (
    SELECT
        seq_order,
        chain_step,
        process_id,
        process_name,
        run_sqft,
        date AS potential_end_date,
        cumulative_sqft,
        -- Find the actual start date by looking back at when accumulation began
        (
            SELECT MIN(cr2.date)
            FROM capacity_running cr2
            WHERE cr2.process_id = cr1.process_id
              AND cr2.date <= cr1.date
              AND cr2.cumulative_sqft <= cr1.cumulative_sqft
              AND cr2.cumulative_sqft >= cr1.cumulative_sqft - cr1.run_sqft
        ) AS potential_start_date
    FROM capacity_running cr1
    WHERE cumulative_sqft >= run_sqft
),

---------------------------------------------------
-- Step 9: Find first viable date ranges per process
---------------------------------------------------
first_viable_date AS (
    SELECT
        seq_order,
        chain_step,
        process_id,
        process_name,
        MIN(potential_start_date) AS earliest_start_date,
        MIN(potential_end_date) AS earliest_completion_date,
        MAX(run_sqft) AS run_sqft
    FROM process_windows
    WHERE potential_start_date IS NOT NULL
    GROUP BY seq_order, chain_step, process_id, process_name
),

---------------------------------------------------
-- Step 10: Pre-calculate next available dates for cascade
---------------------------------------------------
next_available_after AS (
    SELECT DISTINCT
        pw.seq_order,
        pw.chain_step,
        pw.process_id,
        prev_dates.prev_end_date,
        MIN(pw.potential_start_date) AS next_start_date,
        MIN(pw.potential_end_date) AS next_completion_date
    FROM process_windows pw
    CROSS JOIN (
        SELECT DISTINCT potential_end_date AS prev_end_date 
        FROM process_windows
        WHERE potential_end_date >= DATEADD(DAY, @lead_time, CAST(GETDATE() AS DATE))
    ) prev_dates
    WHERE pw.potential_start_date > prev_dates.prev_end_date
      AND pw.potential_start_date IS NOT NULL
      AND pw.potential_end_date IS NOT NULL
    GROUP BY pw.seq_order, pw.chain_step, pw.process_id, prev_dates.prev_end_date
),

---------------------------------------------------
-- Step 11: Build cascading chain recursively
---------------------------------------------------
chain AS (
    -- Anchor: First process (chain_step = 1)
    SELECT
        fvd.seq_order,
        fvd.chain_step,
        fvd.process_id,
        fvd.process_name,
        fvd.earliest_start_date AS start_date,
        fvd.earliest_completion_date AS end_date,
        fvd.run_sqft,
        CAST(fvd.earliest_start_date AS DATE) AS chain_start,
        CAST(fvd.earliest_completion_date AS DATE) AS chain_end
    FROM first_viable_date fvd
    WHERE fvd.chain_step = 1

    UNION ALL

    -- Recursive: Each subsequent process starts AFTER previous ends
    SELECT
        fvd.seq_order,
        fvd.chain_step,
        fvd.process_id,
        fvd.process_name,
        naa.next_start_date AS start_date,
        naa.next_completion_date AS end_date,
        fvd.run_sqft,
        c.chain_start,
        CAST(naa.next_completion_date AS DATE) AS chain_end
    FROM chain c
    JOIN first_viable_date fvd
        ON fvd.chain_step = c.chain_step + 1
    JOIN next_available_after naa
        ON naa.chain_step = fvd.chain_step
       AND naa.process_id = fvd.process_id
       AND naa.prev_end_date = c.end_date
       AND naa.next_start_date > c.end_date  -- Critical: start must be after previous ends
       AND naa.next_completion_date IS NOT NULL
)

---------------------------------------------------
-- Step 12: Return complete chain with schedule dates
---------------------------------------------------
SELECT
    seq_order,
    chain_step,
    process_name,
    start_date AS schedule_date,
    end_date AS completion_date,
    DATEDIFF(DAY, start_date, end_date) + 1 AS days_required,
    run_sqft,
    chain_start AS job_start_date,
    chain_end AS job_completion_date,
    DATEDIFF(DAY, chain_start, chain_end) + 1 AS total_days,
    DATEDIFF(DAY, GETDATE(), chain_start) AS actual_lead_time_days,
    CASE 
        WHEN DATEDIFF(DAY, GETDATE(), chain_start) >= @lead_time 
        THEN 'Meets Lead Time (' + CAST(@lead_time AS VARCHAR(10)) + ' days)'
        ELSE 'Below Lead Time (Required: ' + CAST(@lead_time AS VARCHAR(10)) + ', Actual: ' + CAST(DATEDIFF(DAY, GETDATE(), chain_start) AS VARCHAR(10)) + ')'
    END AS lead_time_status
FROM chain
WHERE (SELECT COUNT(*) FROM chain) = (SELECT COUNT(*) FROM docket_routing_ordered)
ORDER BY chain_step
OPTION (MAXRECURSION 100);